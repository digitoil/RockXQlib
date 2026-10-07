# -*- coding: utf-8 -*-
"""qlib 数据目录体检：回答「这份数据能不能信、能用到哪一天」。

## 为什么需要

流水线跑出来的指标好不好，第一步取决于数据。而数据出问题时**往往不报错**，
只是结果悄悄不对：

- 日历只到 2020 年，但工作流写 `end_time: 2022-01-01` → qlib 找不到数据，
  部分区间静默为空，回测照跑、指标照样输出
- 某个标的的 bin 文件长度和清单声明的区间对不上 → 该标的的序列整体错位
- `close` 是归一化复权价还是原始价，直接决定 `$close` 能不能当价格读

这个模块**直接读 bin/txt**，不 init qlib（不需要 `qlib.init`，也就不用等它加载
几百 MB 的特征），几秒内给出结论。

## qlib 数据格式（本模块依赖的约定）

    <uri>/calendars/<freq>.txt        每行一个交易日，升序
    <uri>/instruments/<name>.txt      SYMBOL\\tSTART\\tEND（制表符分隔）
    <uri>/features/<sym>/<field>.<freq>.bin
        float32 数组：第 0 个是「起始日历下标」，其后是该标的的逐日值
        （见 qlib/data/storage/file_storage.py 的
          `np.hstack([index, data_array]).astype("<f").tofile(fp)`）

所以「该标的覆盖 calendar[si : si+n]」，这也是本模块校验区间一致性的依据。

## 关于官方 cn_data 的两个事实（体检会报告）

1. **`close` 是归一化复权价**（每只标的首值恰为 1.0），其逐日比值与存储的
   `change` 完全相等；`raw = close / factor` 才是真实价（实测 sh600000
   2020-09-25：7.41408 / 0.78290 = 9.47，与真实收盘一致）。
   所以**不要把 `$close` 当价格看**，它是可直接用于收益计算的复权序列。
2. **qlib 官方公开数据冻结在 2020-09-25**，不是本机下载不全。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from core.qlib_paths import find_qlib_data_path, is_qlib_data_dir

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "pipelines"

#: 官方 cn_data 的字段集合
OFFICIAL_FIELDS: Tuple[str, ...] = ("open", "high", "low", "close",
                                   "volume", "factor", "change")
#: 缺了这些就没法做特征（其余缺了只是能力受限）
REQUIRED_FIELDS: Tuple[str, ...] = ("close",)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TS_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

# ---- 阈值（都在官方 cn_data 上实测过，确保不产生假警报）----
#: 相邻交易日间隔超过这个天数就提示（A 股最长假约 9 天）
MAX_CALENDAR_GAP_DAYS = 15
#: 单只标的价格逻辑矛盾超过这个天数才报（官方数据有极少量舍入边界）
PRICE_CONFLICT_MIN_DAYS = 10
#: 单日涨跌幅超过这个值（A 股上限 20%）提示，多数是除权/停复牌痕迹
CHANGE_ALERT = 0.21
#: NaN 比例超过这个值提示（长期停牌）
NAN_RATIO_ALERT = 0.5
#: 抽样数量上限（超过则随机抽样）
DEFAULT_SAMPLE = 400
#: 父目录条目超过这个数就跳过「同级残留」检查（见 :func:`_check_extras`）
_MAX_SIBLINGS = 200

LEVEL_ICON = {"error": "✗", "warn": "⚠", "info": "·"}


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------

@dataclass
class Issue:
    level: str          # 'error' | 'warn' | 'info'
    where: str
    message: str
    hint: str = ""

    def __str__(self) -> str:
        s = "%s %s: %s" % (LEVEL_ICON.get(self.level, "?"), self.where, self.message)
        return s + ("\n      → %s" % self.hint if self.hint else "")


@dataclass
class BinInfo:
    """一个特征 bin 文件的内容摘要。"""

    field: str
    start_index: int
    n: int
    n_valid: int
    first: float
    last: float

    @property
    def nan_ratio(self) -> float:
        return 1.0 - (self.n_valid / self.n) if self.n else 1.0


@dataclass
class InstrumentCheck:
    symbol: str
    start: str = ""
    end: str = ""
    bin_start: str = ""
    bin_end: str = ""
    fields: Tuple[str, ...] = ()
    missing_fields: Tuple[str, ...] = ()
    n: int = 0                    # 该标的的有效日数（用于算问题占比）
    nan_ratio: float = 0.0
    price_conflicts: int = 0
    big_changes: int = 0
    max_change: float = 0.0
    problems: List[str] = field(default_factory=list)


@dataclass
class Report:
    provider_uri: str = ""
    usable: bool = False
    freq: str = "day"
    calendar: List[str] = field(default_factory=list)
    instrument_lists: Dict[str, Dict[str, Tuple[str, str]]] = field(default_factory=dict)
    n_feature_dirs: int = 0
    field_counts: Dict[str, int] = field(default_factory=dict)
    checked: List[InstrumentCheck] = field(default_factory=list)
    sampled: bool = False
    n_total_instruments: int = 0
    disk_mb: float = 0.0
    issues: List[Issue] = field(default_factory=list)

    # ---- 派生 ----

    @property
    def start(self) -> str:
        return self.calendar[0] if self.calendar else ""

    @property
    def end(self) -> str:
        return self.calendar[-1] if self.calendar else ""

    @property
    def days(self) -> int:
        return len(self.calendar)

    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "error"]

    def warns(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "warn"]

    def add(self, level: str, where: str, message: str, hint: str = "") -> None:
        self.issues.append(Issue(level, where, message, hint))


# --------------------------------------------------------------------------
# 原始读取
# --------------------------------------------------------------------------

def read_calendar(uri: str, freq: str = "day") -> List[str]:
    p = Path(uri) / "calendars" / ("%s.txt" % freq)
    if not p.is_file():
        return []
    out: List[str] = []
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if s:
                out.append(s)
    return out


def read_instrument_list(uri: str, name: str) -> Dict[str, Tuple[str, str]]:
    """读 ``instruments/<name>.txt`` -> ``{SYMBOL: (start, end)}``。"""
    p = Path(uri) / "instruments" / name
    if not p.is_file():
        return {}
    out: Dict[str, Tuple[str, str]] = {}
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                parts = line.split()
            if len(parts) < 3:
                continue
            out[parts[0]] = (parts[1], parts[2])
    return out


def list_instrument_lists(uri: str) -> List[str]:
    d = Path(uri) / "instruments"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file())


def read_field(uri: str, symbol: str, field: str,
               freq: str = "day") -> Optional[BinInfo]:
    """读一个 bin 文件。文件不存在或为空返回 ``None``。"""
    p = Path(uri) / "features" / symbol.lower() / ("%s.%s.bin" % (field.lower(), freq))
    if not p.is_file():
        return None
    try:
        arr = np.fromfile(p, dtype="<f")
    except OSError:
        return None
    if arr.size == 0:
        return None
    start = int(arr[0])
    vals = arr[1:]
    valid = vals[np.isfinite(vals)]
    return BinInfo(field=field, start_index=start, n=int(vals.size),
                   n_valid=int(valid.size),
                   first=float(valid[0]) if valid.size else float("nan"),
                   last=float(valid[-1]) if valid.size else float("nan"))


def feature_dirs(uri: str) -> List[Path]:
    d = Path(uri) / "features"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_dir())


def _dir_size_mb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total / 1024 / 1024


# --------------------------------------------------------------------------
# 体检
# --------------------------------------------------------------------------

def check(provider_uri: Optional[str] = None, freq: str = "day",
          sample: int = DEFAULT_SAMPLE, deep: bool = False,
          templates_dir: Optional[Path] = None,
          check_templates: bool = True) -> Report:
    """体检一个 qlib 数据目录。

    Args:
        provider_uri: 数据目录；留空则用 :func:`core.qlib_paths.find_qlib_data_path` 探测。
        freq: 频率，默认 ``day``。
        sample: 抽查多少只标的（``deep=True`` 时忽略，全查）。
        deep: 全量检查（3875 只 × 7 字段约 2.7 万个文件，慢但彻底）。
        templates_dir: 模板目录，用于「模板区间 vs 数据覆盖」对照。
        check_templates: 是否做模板对照。
    """
    rep = Report(freq=freq)

    if not provider_uri:
        provider_uri = find_qlib_data_path()
    if not provider_uri:
        rep.add("error", "数据目录",
                "未找到任何可用的 qlib 数据目录",
                "用 --provider-uri 指定，或设置环境变量 QLIB_PROVIDER_URI")
        return rep
    rep.provider_uri = str(provider_uri)

    if not is_qlib_data_dir(provider_uri):
        rep.add("error", "数据目录",
                "不是 qlib 数据目录（需同时有 calendars/ features/ instruments/）",
                "确认路径是否指到了数据目录本身，而不是它的父目录")
        return rep
    rep.usable = True

    # ---- 日历 ----
    rep.calendar = read_calendar(provider_uri, freq)
    if not rep.calendar:
        rep.add("error", "calendars/%s.txt" % freq, "日历为空或不存在",
                "qlib 靠日历对齐所有特征；没有日历什么都读不出来")
        return rep
    _check_calendar(rep)

    # ---- 清单 ----
    _check_instruments(rep)

    # ---- 特征 ----
    _check_features(rep, sample=sample, deep=deep)

    # ---- 体积 ----
    try:
        rep.disk_mb = _dir_size_mb(Path(provider_uri))
    except OSError:
        pass
    _check_extras(rep)

    # ---- 与工作流模板对照 ----
    if check_templates:
        _check_templates(rep, templates_dir or TEMPLATES_DIR)

    return rep


def _check_calendar(rep: Report) -> None:
    cal = rep.calendar
    # 排序与重复
    bad_fmt = [d for d in cal[:50] if not _DATE_RE.match(d)]
    if bad_fmt:
        rep.add("error", "calendars/%s.txt" % rep.freq,
                "日期格式不是 YYYY-MM-DD，例如 %r" % bad_fmt[0])
    dup = len(cal) - len(set(cal))
    if dup:
        rep.add("error", "calendars/%s.txt" % rep.freq,
                "有 %d 个重复交易日" % dup, "重复日会让特征序列错位")
    if cal != sorted(cal):
        rep.add("error", "calendars/%s.txt" % rep.freq, "日期不是升序",
                "qlib 按行号当日期下标，乱序会让所有特征对错日期")

    # 间隔异常：逐个列出（长假最长约 9 天，超过 15 天基本就是日历缺了交易日）
    gaps: List[Tuple[str, str, int]] = []
    prev = None
    for d in cal:
        if prev is not None:
            n = _days_between(prev, d)
            if n is not None and n > MAX_CALENDAR_GAP_DAYS:
                gaps.append((prev, d, n))
        prev = d
    if gaps:
        detail = "；".join("%s→%s(%d天)" % g for g in gaps[:6])
        more = "；另有 %d 处" % (len(gaps) - 6) if len(gaps) > 6 else ""
        rep.add("warn", "calendars/%s.txt" % rep.freq,
                "有 %d 处相邻交易日间隔超过 %d 天：%s%s"
                % (len(gaps), MAX_CALENDAR_GAP_DAYS, detail, more),
                "长假通常不超过 9 天。这些区间里 qlib 认为「没有交易日」，"
                "所以跨过缺口的滚动特征（如 Ref($close, 20)）实际跨了更长的日历时间，"
                "会失真。需要的话补全日历并重灌数据")

    # 陈旧程度
    age = _age_years(rep.end)
    if age is not None:
        if age >= 1.0:
            rep.add("warn", "数据覆盖",
                    "日历末日 %s，距今 %.1f 年" % (rep.end, age),
                    "任何回测/研究的区间都不能超过这一天；要研究更近的行情需要导入新数据"
                    "（python -m pipeline data-import）")
        else:
            rep.add("info", "数据覆盖", "日历末日 %s（距今 %.1f 年）" % (rep.end, age))


def _check_instruments(rep: Report) -> None:
    names = list_instrument_lists(rep.provider_uri)
    if not names:
        rep.add("error", "instruments/", "没有任何标的清单文件",
                "qlib 的 market 参数（如 csi300）就是这里的文件名")
        return
    for name in names:
        rows = read_instrument_list(rep.provider_uri, name)
        rep.instrument_lists[name] = rows
        # all.txt 是「本数据快照里到底有哪些标的」的权威清单；csiXXX 是**指数成分**，
        # 成分历史会延伸出快照之外（退市/调出），所以两者严重程度不同。
        is_all = name == "all.txt"
        if not rows:
            rep.add("warn", "instruments/%s" % name, "清单为空")
            continue
        # 日期格式 / 起止颠倒
        bad = []
        for sym, (s, e) in rows.items():
            if not (_DATE_RE.match(s) and _DATE_RE.match(e)):
                bad.append("%s 日期格式异常 (%s, %s)" % (sym, s, e))
            elif s > e:
                bad.append("%s 起止颠倒 (%s > %s)" % (sym, s, e))
        if bad:
            rep.add("error", "instruments/%s" % name,
                    "%d 条记录有问题，例如 %s" % (len(bad), bad[0]))
        # 结束日晚于数据末日
        if rep.calendar:
            over = sorted(sym for sym, (_s, e) in rows.items() if e > rep.end)
            if over:
                if is_all:
                    rep.add("warn", "instruments/%s" % name,
                            "%d 只标的的结束日 %s 晚于日历末日 %s，例如 %s"
                            % (len(over), rows[over[0]][1], rep.end, over[0]),
                            "all.txt 应当与数据严格一致；不一致说明清单没跟着数据更新")
                else:
                    rep.add("info", "instruments/%s" % name,
                            "%d 只成分股的结束日晚于数据末日（最长 %s），例如 %s"
                            % (len(over), max(rows[s][1] for s in over), over[0]),
                            "指数成分历史通常比数据快照长，属正常；但用这个清单当"
                            "股票池时，超出的那段取不到数、会被静默跳过")


def _check_features(rep: Report, sample: int, deep: bool) -> None:
    dirs = feature_dirs(rep.provider_uri)
    rep.n_feature_dirs = len(dirs)
    if not dirs:
        rep.add("error", "features/", "没有任何标的的特征目录")
        return

    # all.txt 是权威清单，必须与 features 严格一致
    have = {p.name for p in dirs}
    if "all.txt" in rep.instrument_lists:
        allx = {k.lower() for k in rep.instrument_lists["all.txt"]}
        miss = sorted(allx - have)
        extra = sorted(have - allx)
        if miss:
            rep.add("error", "features/",
                    "%d 只标的在 all.txt 里但没有特征目录，例如 %s"
                    % (len(miss), ", ".join(miss[:3])),
                    "这些标的被选进股票池时取不到数，会被静默跳过")
        if extra:
            rep.add("info", "features/",
                    "%d 个特征目录不在 all.txt 里，例如 %s"
                    % (len(extra), ", ".join(extra[:3])),
                    "按 all.txt 取数时它们不会被用到")
    # 指数成分清单允许有快照之外的成分（已退市/已调出），只作提示
    for name, rows in rep.instrument_lists.items():
        if name == "all.txt" or not rows:
            continue
        miss = sorted({s.lower() for s in rows} - have)
        if miss:
            rep.add("info", "instruments/%s" % name,
                    "%d 只成分股在数据快照里没有数据（多为已退市），例如 %s"
                    % (len(miss), ", ".join(miss[:3])),
                    "用这个清单当股票池时它们会被静默跳过，股票池实际小于声明值")

    # 字段齐全性
    counts: Dict[str, int] = {}
    for d in dirs:
        for p in d.iterdir():
            if p.name.endswith(".%s.bin" % rep.freq):
                f = p.name[: -(len(rep.freq) + 5)]
                counts[f] = counts.get(f, 0) + 1
    rep.field_counts = counts
    for f in OFFICIAL_FIELDS:
        n = counts.get(f, 0)
        if n == 0 and f in REQUIRED_FIELDS:
            rep.add("error", "features/", "没有任何标的带 `%s` 字段" % f,
                    "缺少 close 就无法构造任何收益类特征")
        elif n == 0:
            rep.add("warn", "features/", "没有任何标的带 `%s` 字段" % f,
                    "Alpha158/360 不直接用 factor，但缺了它就无法还原真实价"
                    if f == "factor" else "")
        elif n < len(dirs):
            example = next((d.name for d in dirs
                            if not (d / ("%s.%s.bin" % (f, rep.freq))).is_file()), "?")
            rep.add("info", "features/", "`%s` 只覆盖 %d / %d 只标的（缺 %s 等）"
                    % (f, n, len(dirs), example))

    # 抽样检查
    total = len(dirs)
    rep.n_total_instruments = total
    if deep or sample <= 0 or sample >= total:
        picked = dirs
        rep.sampled = False
    else:
        rng = np.random.default_rng(20261007)
        idx = sorted(rng.choice(total, size=sample, replace=False).tolist())
        picked = [dirs[i] for i in idx]
        rep.sampled = True

    # 用哪个清单做区间对照？优先 all.txt，否则最大的那个
    ref_rows: Dict[str, Tuple[str, str]] = {}
    if "all.txt" in rep.instrument_lists:
        ref_rows = {k.lower(): v for k, v in rep.instrument_lists["all.txt"].items()}
    elif rep.instrument_lists:
        biggest = max(rep.instrument_lists.values(), key=len)
        ref_rows = {k.lower(): v for k, v in biggest.items()}

    for d in picked:
        rep.checked.append(_check_instrument(rep, d, ref_rows))

    # 汇总
    conflict = sum(c.price_conflicts for c in rep.checked)
    big = sum(c.big_changes for c in rep.checked)
    nan_bad = [c for c in rep.checked if c.nan_ratio > NAN_RATIO_ALERT]

    # 逐标的问题**按类型聚合**提升到报告级 —— 只写在「逐标的检查」里容易被忽略，
    # 但也不能一个标的报一条（几千只时报告就没法看了）。
    kinds: Dict[str, List[str]] = {}
    for c in rep.checked:
        for prob in c.problems:
            key = re.sub(r"\d+", "N", prob.split("：")[0])
            kinds.setdefault(key, []).append(c.symbol)
    for key, syms in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
        rep.add("error", "features/",
                "%d 只标的：%s（例如 %s）" % (len(syms), key, syms[0]),
                "详见上面的「逐标的检查」")
    if conflict:
        # 单只标的超过阈值的情况已经记在它的 problems 里（见「逐标的检查」），
        # 这里只是总量提示 —— 官方数据也有极少量舍入边界，别当警报。
        n_rows = sum(c.n for c in rep.checked) or 1
        rep.add("info", "features/",
                "抽查中发现 %d 处 high/low 与 close 矛盾（占 %.5f%%）"
                % (conflict, 100.0 * conflict / n_rows),
                "数量大（单只超过 %d 天）才说明有问题；个别舍入边界可忽略"
                % PRICE_CONFLICT_MIN_DAYS)
    if big:
        worst = max(rep.checked, key=lambda c: c.max_change)
        rep.add("info", "features/",
                "抽查中发现 %d 处 |单日涨跌幅| > %.0f%%（最大 %.1f%%，出现在 %s）"
                % (big, CHANGE_ALERT * 100, worst.max_change * 100, worst.symbol),
                "A 股涨跌停上限 20%；超出多为除权/停复牌/数据错误，可人工核对")
    if nan_bad:
        rep.add("info", "features/",
                "%d / %d 只标的的 NaN 比例超过 %.0f%%（长期停牌或退市前）"
                % (len(nan_bad), len(rep.checked), NAN_RATIO_ALERT * 100))


def _check_instrument(rep: Report, d: Path, ref_rows: Dict[str, Tuple[str, str]]
                      ) -> InstrumentCheck:
    sym = d.name
    ic = InstrumentCheck(symbol=sym)
    fields = tuple(sorted(p.name[: -(len(rep.freq) + 5)] for p in d.iterdir()
                          if p.name.endswith(".%s.bin" % rep.freq)))
    ic.fields = fields
    ic.missing_fields = tuple(f for f in OFFICIAL_FIELDS if f not in fields)

    bins: Dict[str, BinInfo] = {}
    for f in fields:
        info = read_field(rep.provider_uri, sym, f, rep.freq)
        if info is None:
            ic.problems.append("`%s` 文件为空" % f)
            continue
        bins[f] = info
        # 下标越界
        if rep.calendar:
            if info.start_index < 0 or info.start_index >= len(rep.calendar):
                ic.problems.append("`%s` 起始下标 %d 越界（日历 %d 天）"
                                   % (f, info.start_index, len(rep.calendar)))
            elif info.start_index + info.n > len(rep.calendar):
                ic.problems.append("`%s` 长度越界：下标 %d + %d > 日历 %d 天"
                                   % (f, info.start_index, info.n, len(rep.calendar)))

    close = bins.get("close")
    if close is not None and rep.calendar:
        # 起始下标越界时不能再拿去索引日历（会 IndexError）——
        # 上面已经把它记成问题了，这里只跳过区间计算。
        in_range = 0 <= close.start_index < len(rep.calendar)
        if in_range:
            end_i = min(close.start_index + close.n - 1, len(rep.calendar) - 1)
            ic.bin_start = rep.calendar[close.start_index]
            ic.bin_end = rep.calendar[end_i]
        ic.n = close.n
        ic.nan_ratio = close.nan_ratio
        declared = ref_rows.get(sym)
        if declared:
            ic.start, ic.end = declared
            if in_range and (ic.bin_start != declared[0] or ic.bin_end != declared[1]):
                ic.problems.append("区间不符：清单声明 %s→%s，bin 实际 %s→%s"
                                   % (declared[0], declared[1], ic.bin_start, ic.bin_end))

    # 价格逻辑
    vals = {}
    for f in ("open", "high", "low", "close"):
        if f in bins:
            vals[f] = _values(rep.provider_uri, sym, f, rep.freq)
    if {"high", "low", "close"} <= set(vals):
        h, l, c = vals["high"], vals["low"], vals["close"]
        n = min(len(h), len(l), len(c))
        h, l, c = h[:n], l[:n], c[:n]
        m = np.isfinite(h) & np.isfinite(l) & np.isfinite(c)
        if m.any():
            ic.price_conflicts = int(np.sum(h[m] < l[m] - 1e-6)
                                     + np.sum(h[m] < c[m] - 1e-6)
                                     + np.sum(l[m] > c[m] + 1e-6))
            if ic.price_conflicts > PRICE_CONFLICT_MIN_DAYS:
                ic.problems.append("high/low 与 close 矛盾 %d 天" % ic.price_conflicts)

    # 异常涨跌
    chg = _values(rep.provider_uri, sym, "change", rep.freq)
    if chg is not None and chg.size:
        v = np.abs(chg[np.isfinite(chg)])
        if v.size:
            ic.big_changes = int(np.sum(v > CHANGE_ALERT))
            ic.max_change = float(v.max())

    # 归一化约定
    if close is not None and np.isfinite(close.first) and abs(close.first - 1.0) > 1e-4:
        ic.problems.append("close 首值 %.4f（非 1.0，不是官方归一化约定）" % close.first)

    return ic


def _values(uri: str, symbol: str, field: str, freq: str) -> Optional[np.ndarray]:
    p = Path(uri) / "features" / symbol / ("%s.%s.bin" % (field, freq))
    if not p.is_file():
        return None
    try:
        arr = np.fromfile(p, dtype="<f")
    except OSError:
        return None
    return arr[1:] if arr.size else None


def _check_extras(rep: Report) -> None:
    """提示同目录下的「同一数据家族」残留（未下完的空目录、冗余压缩包）。

    ⚠️ 这个检查**必须有界**。最初写成「遍历父目录里所有目录、并逐个
    ``iterdir()`` 判空」，在官方数据上没问题（父目录只有 2 个条目），
    但数据目录若放在临时目录下，父目录可能有上万个条目 —— 直接挂死
    （实测 19 个用例跑了 98 秒，还有的挂住不动）。

    所以：**父目录条目超过 200 个就直接跳过** —— 那种目录（临时目录、
    下载目录）本来就不是「数据家族」的存放处，扫它没有意义。
    """
    base = Path(rep.provider_uri)
    parent = base.parent
    try:
        entries = list(parent.iterdir())
    except OSError:
        return
    if len(entries) > _MAX_SIBLINGS:
        return

    tokens = [t for t in re.split(r"[^a-z0-9]+", base.name.lower()) if len(t) >= 3]

    def related(name: str) -> bool:
        n = name.lower()
        if n.startswith(base.name.lower()):
            return True
        return any(t in n for t in tokens)

    probed = 0
    zips = 0
    for e in entries:
        try:
            if e.is_dir() and e != base:
                if is_qlib_data_dir(str(e)):
                    if not read_calendar(str(e), rep.freq):
                        rep.add("info", "同级目录",
                                "%s 结构完整但没有日历（未下载完？）" % e.name)
                elif related(e.name) and probed < 20:
                    probed += 1
                    if not any(e.iterdir()):
                        rep.add("info", "同级目录", "%s 是空目录" % e.name)
            elif e.is_file() and e.suffix.lower() == ".zip" and zips < 3 \
                    and related(e.name):
                zips += 1
                mb = e.stat().st_size / 1024 / 1024
                rep.add("info", "同级文件", "%s（%.0f MB）" % (e.name, mb),
                        "若数据已解压，这个压缩包可以删掉腾空间")
        except OSError:
            continue


def _check_templates(rep: Report, templates_dir: Path) -> None:
    """把模板里声明的 provider_uri 与区间跟数据覆盖对照。

    这是最实用的一条检查：49 个官方模板都写着 ``end_time: 2020-08-01``，
    正好落在数据范围内；用户一旦把区间改到 2021 就会「跑得通但取不到数」。
    """
    if not rep.calendar or not templates_dir.is_dir():
        return
    try:
        import yaml
    except ImportError:
        return

    outside: List[Tuple[str, str, str]] = []      # (模板, 属性, 值)
    other_uri: List[Tuple[str, str]] = []
    benchmarks: Dict[str, List[str]] = {}         # 基准代码 -> 用到它的模板
    n = 0
    for f in sorted(templates_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        n += 1
        for st in (doc.get("steps") or []):
            if not isinstance(st, dict):
                continue
            for k, v in (st.get("props") or {}).items():
                if not isinstance(v, str) or not v:
                    continue
                if k == "provider_uri" and v != rep.provider_uri:
                    other_uri.append((f.name, v))
                elif k == "benchmark":
                    benchmarks.setdefault(v.upper(), []).append(f.name)
                elif k.endswith(("_time", "_start", "_end")) and _DATE_RE.match(v):
                    if v < rep.start or v > rep.end:
                        outside.append((f.name, k, v))
    if outside:
        show = outside[:5]
        rep.add("warn", "模板区间",
                "%d 处模板日期超出数据覆盖（%s → %s），例如 %s"
                % (len(outside), rep.start, rep.end,
                   "；".join("%s.%s=%s" % t for t in show)),
                "超出的部分取不到数：qlib 不报错，但该区间是空的，回测结果会失真")

    # 基准必须能在数据里找到，否则回测直接抛
    # ValueError: The benchmark ['SH000300'] does not exist
    have = set()
    for name, rows in rep.instrument_lists.items():
        if name == "all.txt":
            have.update(k.upper() for k in rows)
    missing: Dict[str, List[str]] = {}
    if have:
        missing = {b: fs for b, fs in benchmarks.items() if b and b not in have}
        if missing:
            first = sorted(missing)[0]
            rep.add("warn", "模板基准",
                    "%d 个基准代码不在数据里：%s（例如 %s 用到 %s）"
                    % (len(missing), ", ".join(sorted(missing)[:4]),
                       missing[first][0], first),
                    "回测节点的「基准」默认 SH000300；数据里没有它时回测会直接失败。"
                    "把指数一起导入，或把该属性留空")

    if other_uri:
        rep.add("info", "模板数据源",
                "%d 个模板的 provider_uri 与本目录不同，例如 %s → %s"
                % (len(other_uri), other_uri[0][0], other_uri[0][1]))
    if n and not outside and not missing:
        rep.add("info", "模板区间", "%d 个模板的日期区间都在数据覆盖范围内" % n)


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def _days_between(a: str, b: str) -> Optional[int]:
    from datetime import date
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days
    except ValueError:
        return None


def _age_years(end: str) -> Optional[float]:
    from datetime import date
    try:
        d = date.fromisoformat(end)
    except ValueError:
        return None
    return (date.today() - d).days / 365.25


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------

def format_report(rep: Report, max_issues: int = 40) -> str:
    L: List[str] = []
    L.append("=" * 66)
    L.append("qlib 数据体检")
    L.append("=" * 66)
    L.append("目录    %s" % (rep.provider_uri or "(未指定)"))
    if not rep.usable:
        L.append("")
        for i in rep.issues:
            L.append(str(i))
        return "\n".join(L)

    L.append("频率    %s" % rep.freq)
    L.append("覆盖    %s → %s（%d 个交易日）" % (rep.start, rep.end, rep.days))
    if rep.disk_mb:
        L.append("体积    %.0f MB" % rep.disk_mb)
    L.append("")

    # 清单
    L.append("【标的清单】")
    if rep.instrument_lists:
        w = max(len(k) for k in rep.instrument_lists)
        for name, rows in rep.instrument_lists.items():
            if not rows:
                L.append("  %-*s  0 只" % (w, name))
                continue
            starts = min(v[0] for v in rows.values())
            ends = max(v[1] for v in rows.values())
            L.append("  %-*s  %5d 只   %s → %s" % (w, name, len(rows), starts, ends))
    else:
        L.append("  （无）")
    L.append("")

    # 字段
    L.append("【字段覆盖】")
    if rep.field_counts:
        w = max(len(k) for k in rep.field_counts)
        for f in sorted(rep.field_counts, key=lambda x: (-rep.field_counts[x], x)):
            mark = " " if f in OFFICIAL_FIELDS else "*"
            L.append("  %s%-*s  %5d / %d 只" % (mark, w, f, rep.field_counts[f],
                                               rep.n_feature_dirs))
        if any(f not in OFFICIAL_FIELDS for f in rep.field_counts):
            L.append("  （* = 非官方字段）")
    else:
        L.append("  （无）")
    L.append("")

    # 抽查
    if rep.checked:
        scope = ("抽查 %d / %d 只" % (len(rep.checked), rep.n_total_instruments)
                 if rep.sampled else "全部 %d 只" % len(rep.checked))
        L.append("【逐标的检查】%s" % scope)
        ok = [c for c in rep.checked if not c.problems]
        L.append("  区间与清单一致      %d / %d" % (len(ok), len(rep.checked)))
        nan = np.array([c.nan_ratio for c in rep.checked])
        L.append("  NaN 比例            中位 %.1f%%，最大 %.1f%%"
                 % (float(np.median(nan)) * 100, float(nan.max()) * 100))
        L.append("  价格逻辑矛盾        %d 处" % sum(c.price_conflicts for c in rep.checked))
        L.append("  |日涨跌| > %.0f%%     %d 处（最大 %.1f%%）"
                 % (CHANGE_ALERT * 100, sum(c.big_changes for c in rep.checked),
                    max((c.max_change for c in rep.checked), default=0.0) * 100))
        bad = [c for c in rep.checked if c.problems]
        for c in bad[:8]:
            L.append("    · %s: %s" % (c.symbol, "；".join(c.problems[:2])))
        if len(bad) > 8:
            L.append("    ... 另有 %d 只" % (len(bad) - 8))
        L.append("")

    # 问题
    errs = rep.errors()
    warns = rep.warns()
    infos = [i for i in rep.issues if i.level == "info"]
    if errs:
        L.append("【错误】%d 条" % len(errs))
        for i in errs[:max_issues]:
            L.append("  " + str(i))
        L.append("")
    if warns:
        L.append("【警告】%d 条" % len(warns))
        for i in warns[:max_issues]:
            L.append("  " + str(i))
        L.append("")
    if infos:
        L.append("【提示】%d 条" % len(infos))
        for i in infos[:max_issues]:
            L.append("  " + str(i))
        L.append("")

    # 结论
    L.append("=" * 66)
    if errs:
        L.append("结论：数据存在 %d 个错误，先修好再用。" % len(errs))
    elif warns:
        L.append("结论：结构自洽，但有 %d 条警告需要注意（见上）。" % len(warns))
    else:
        L.append("结论：数据自洽，可直接使用。")
    if rep.calendar:
        L.append("      可用区间 %s → %s" % (rep.start, rep.end))
    L.append("=" * 66)
    return "\n".join(L)


def report_json(rep: Report) -> Dict[str, Any]:
    """机器可读版本（给 GUI / CI 用）。"""
    return {
        "provider_uri": rep.provider_uri,
        "usable": rep.usable,
        "freq": rep.freq,
        "start": rep.start,
        "end": rep.end,
        "days": rep.days,
        "disk_mb": round(rep.disk_mb, 1),
        "instruments": {k: len(v) for k, v in rep.instrument_lists.items()},
        "fields": rep.field_counts,
        "n_feature_dirs": rep.n_feature_dirs,
        "checked": len(rep.checked),
        "sampled": rep.sampled,
        "errors": [str(i) for i in rep.errors()],
        "warnings": [str(i) for i in rep.warns()],
        "infos": [str(i) for i in rep.issues if i.level == "info"],
    }
