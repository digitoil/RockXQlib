# -*- coding: utf-8 -*-
"""把 CSV 行情导入成 qlib 的 bin 数据目录。

## 为什么需要

qlib 官方公开的 cn_data **冻结在 2020-09-25**（不是本机下载不全，是官方数据
就这么新）。想研究之后的行情，只能自己灌数据 —— 而 qlib 的导入脚本在
``scripts/dump_bin.py``，本项目里没有（``scripts/`` 目录不存在）。

这个模块做同一件事，但把几个**最容易静默出错**的地方显式化。

## qlib 的数据格式

    <uri>/calendars/<freq>.txt        每行一个交易日，升序
    <uri>/instruments/all.txt         SYMBOL\\tSTART\\tEND（制表符分隔）
    <uri>/features/<sym>/<f>.<freq>.bin
        float32：[起始日历下标] + 逐日值

关键点：**bin 里没有日期**，只有「从日历的哪一天开始」。所以日历是所有标的
共享的时间轴，改日历就等于改所有标的的对齐。

## 三个容易静默出错的地方（本模块的处理）

### 1. 价格基准（最危险）

官方数据的 ``close`` 是**归一化复权价**（每只标的首值恰为 1.0），
``raw = close / factor``。如果你把原始价直接追加进去，接缝处会凭空多出一个
几十个百分点的「收益」—— 回测不会报错，只是结果全错。

所以追加时**必须**把新数据的基准对齐到已有数据：

- 有日期重叠 → 用重叠段的中位数比值算缩放系数 ``k``（最可靠）
- 没有重叠但 CSV 带 ``factor`` 列 → 用 ``raw × factor`` 对齐
- 都没有 → **拒绝导入这个标的**并说明原因，不猜

写完还会做**接缝自检**：计算接缝日的收益率，超过涨跌停上限就报警。

### 2. 标的代码格式

qlib 要求 ``SH600000`` / ``SZ000001`` 这种「大写交易所前缀 + 代码」，
目录名则用小写。而数据源五花八门：``600000.SH``（tushare）、
``sh600000``、``600000``（无交易所）、``000300.XSHG``（聚宽）。
本模块统一归一化；只有 6 位纯数字时才靠首位数字猜交易所（并提示）。

### 3. 增量与日历

- 新日期**晚于**已有日历末日 → 追加（只改被导入的标的，其余文件不动）
- 新日期**落在**已有日历内 → 覆盖那几天
- 新日期**早于**已有日历首日 → 会让所有已有标的的下标整体位移，
  需要重写全部 bin（几千个文件）。默认拒绝并说明，避免误操作。

### 4. `factor` 必须写，否则回测会退化

qlib 用 ``$factor`` 做「100 股整手」的成交单位取整。缺了它
（``qlib/backtest/exchange.py`` 会警告 *"trade unit 100 is not supported
in adjusted_price mode"*）回测会切到 adjusted_price 模式、**关闭整手取整**，
成交结果与官方数据跑出来的不可比。

本模块不做复权，所以默认写常数 ``1.0``；输入带 ``factor`` 列则原样透传；
追加时新日期沿用最后一个已知因子，避免跳变。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .data_health import Issue, read_calendar, read_instrument_list

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: 需要写进 bin 的字段（顺序即写入顺序）
FIELDS: Tuple[str, ...] = ("open", "high", "low", "close", "volume", "factor", "change")
#: 缺了就无法计算的字段
NEEDED: Tuple[str, ...] = ("close",)

# 列名别名（统一小写、去掉空格与下划线后匹配）
_ALIASES: Dict[str, Tuple[str, ...]] = {
    "date":   ("date", "datetime", "time", "tradedate", "tradeday", "day",
               "日期", "交易日期", "交易日", "时间"),
    "symbol": ("symbol", "code", "instrument", "ticker", "tscode", "secid",
               "股票代码", "证券代码", "代码", "标的"),
    "open":   ("open", "openprice", "开盘价", "开盘", "今开"),
    "high":   ("high", "highprice", "最高价", "最高", "最高价"),
    "low":    ("low", "lowprice", "最低价", "最低"),
    "close":  ("close", "closeprice", "收盘价", "收盘", "最新价", "今收"),
    "volume": ("volume", "vol", "成交量", "成交股数", "成交额"),
    "factor": ("factor", "adjfactor", "adjustfactor", "复权因子", "后复权因子"),
    "change": ("change", "pctchg", "pctchange", "return", "ret", "涨跌幅", "涨幅"),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SYM_RE = re.compile(r"^(?:(?P<ex1>[A-Za-z]{2})\.?(?P<code1>\d{6})"
                     r"|(?P<code2>\d{6})\.?(?P<ex2>[A-Za-z]{2,4}))$")

#: 看起来像指数而不是股票（沪市 000xxx / 深市 399xxx）。
#: 用途：导入「股票 + 指数」时，自动生成的股票池要把指数剔掉 ——
#: 指数不该被当成可交易标的选进持仓。
_INDEX_RE = re.compile(r"^(?:SH000\d{3}|SZ399\d{3})$")

#: 无交易所前缀时按首位数字猜（A 股约定）
_EX_BY_HEAD = {"6": "SH", "9": "SH", "5": "SH",     # 沪市股票/基金/B股
               "0": "SZ", "2": "SZ", "3": "SZ", "1": "SZ",   # 深市
               "4": "BJ", "8": "BJ"}                # 北交所
_EX_ALIAS = {"SH": "SH", "SS": "SH", "XSHG": "SH", "SHA": "SH",
             "SZ": "SZ", "XSHE": "SZ", "SHE": "SZ",
             "BJ": "BJ", "BSE": "BJ", "NEEQ": "BJ"}

#: 接缝收益率超过这个值就报警（A 股涨跌停上限 20%）
SEAM_ALERT = 0.21


def is_index_like(symbol: str) -> bool:
    """``SH000300`` / ``SZ399006`` 这类看着是指数而不是个股。"""
    return bool(_INDEX_RE.match(symbol.upper()))


@dataclass
class SymbolPlan:
    """一个标的的导入计划（写盘前的结果）。"""

    symbol: str
    n_days: int = 0
    first_date: str = ""
    last_date: str = ""
    scale: float = 1.0
    scale_from: str = ""          # 'overlap' | 'factor' | 'first-close' | 'none'
    is_new: bool = True
    seam_return: Optional[float] = None
    problems: List[str] = field(default_factory=list)


@dataclass
class ImportResult:
    out_dir: str = ""
    freq: str = "day"
    dry_run: bool = False
    created: bool = False          # True=新建目录，False=追加到已有目录
    calendar_start: str = ""
    calendar_end: str = ""
    n_days: int = 0
    n_days_added: int = 0
    n_symbols: int = 0
    n_rows: int = 0
    instrument_list: str = ""      # 额外生成的股票池清单名（""=没生成）
    n_index_like: int = 0          # 被剔出股票池的指数类代码数
    plans: List[SymbolPlan] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)

    def add(self, level: str, where: str, message: str, hint: str = "") -> None:
        self.issues.append(Issue(level, where, message, hint))

    @property
    def written(self) -> bool:
        return not self.dry_run and not self.errors()

    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "error"]


# --------------------------------------------------------------------------
# 符号与列名
# --------------------------------------------------------------------------

def normalize_symbol(raw: Any) -> Optional[str]:
    """``600000.SH`` / ``sh600000`` / ``600000`` -> ``SH600000``。"""
    if raw is None:
        return None
    s = str(raw).strip().upper().replace(" ", "")
    if not s:
        return None
    m = _SYM_RE.match(s)
    if m:
        if m.group("code1"):
            code, ex = m.group("code1"), m.group("ex1")
        else:
            code, ex = m.group("code2"), m.group("ex2")
        ex = _EX_ALIAS.get(ex)
        if ex:
            return ex + code
        return None
    # 纯数字（含 1 位指数代码，如 300 -> 沪深300 的 000300）
    digits = re.sub(r"\D", "", s)
    if len(digits) == 6:
        ex = _EX_BY_HEAD.get(digits[0])
        return (ex + digits) if ex else None
    return None


def _norm_key(s: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(s).strip().lower())


def map_columns(cols: Iterable[Any]) -> Dict[str, Any]:
    """把实际列名映射到标准字段名（返回 ``{标准名: 原列名}``）。"""
    lookup: Dict[str, Any] = {}
    for c in cols:
        lookup.setdefault(_norm_key(c), c)
    out: Dict[str, Any] = {}
    for field_name, aliases in _ALIASES.items():
        for a in aliases:
            k = _norm_key(a)
            if k in lookup:
                out[field_name] = lookup[k]
                break
    return out


# --------------------------------------------------------------------------
# 读取
# --------------------------------------------------------------------------

def _read_csv_any(path: Path) -> pd.DataFrame:
    """按常见编码依次尝试（国内数据源常是 GBK）。"""
    last: Optional[Exception] = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str,
                               keep_default_na=False, na_values=[""])
        except UnicodeDecodeError as e:
            last = e
            continue
        except Exception:
            raise
    raise last if last else RuntimeError("无法读取 %s" % path)


def load_source(source: str, res: ImportResult,
                limit: Optional[int] = None) -> Dict[str, pd.DataFrame]:
    """读入 CSV，返回 ``{SYMBOL: DataFrame(date + 字段)}``。

    支持两种形态：
    - **单个文件**：长表，必须含 date 与 symbol 两列
    - **目录**：每个 CSV 是一只标的（文件名当代码，或文件里有 symbol 列）
    """
    src = Path(source)
    frames: List[pd.DataFrame] = []
    if src.is_dir():
        files = sorted(p for p in src.rglob("*")
                       if p.suffix.lower() in (".csv", ".txt", ".tsv"))
        if not files:
            res.add("error", str(src), "目录里没有 CSV/TXT 文件")
            return {}
        if limit:
            files = files[:limit]
        res.add("info", str(src), "目录模式：读取 %d 个文件" % len(files))
        for f in files:
            try:
                df = _read_csv_any(f)
            except Exception as e:
                res.add("warn", f.name, "读取失败：%s" % e)
                continue
            if "symbol" not in map_columns(df.columns):
                # 没有代码列 -> 用文件名当代码
                sym = normalize_symbol(f.stem)
                if sym:
                    df["__symbol__"] = sym
                else:
                    res.add("warn", f.name, "无法从文件名识别标的代码，已跳过")
                    continue
            frames.append(df)
    elif src.is_file():
        try:
            df = _read_csv_any(src)
        except Exception as e:
            res.add("error", str(src), "读取失败：%s" % e)
            return {}
        frames.append(df)
    else:
        res.add("error", str(source), "路径不存在")
        return {}

    if not frames:
        return {}

    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    colmap = map_columns(df.columns)
    if "date" not in colmap:
        res.add("error", "CSV", "找不到日期列（支持 date/datetime/日期/交易日期 等）",
                "实际列名：%s" % ", ".join(str(c) for c in list(df.columns)[:12]))
        return {}
    sym_col = colmap.get("symbol") or ("__symbol__" if "__symbol__" in df.columns else None)
    if sym_col is None:
        res.add("error", "CSV", "找不到标的代码列（支持 symbol/code/ts_code/代码 等）",
                "单只标的的文件可以用文件名当代码；多标的必须有代码列")
        return {}
    missing = [f for f in NEEDED if f not in colmap]
    if missing:
        res.add("error", "CSV", "缺少必需列：%s" % ", ".join(missing),
                "实际列名：%s" % ", ".join(str(c) for c in list(df.columns)[:12]))
        return {}

    # 归一化
    d = pd.DataFrame()
    d["date"] = pd.to_datetime(df[colmap["date"]], errors="coerce").dt.strftime("%Y-%m-%d")
    bad_date = int(d["date"].isna().sum())
    if bad_date:
        res.add("warn", "CSV", "%d 行的日期无法解析，已丢弃" % bad_date)
    syms = df[sym_col].map(normalize_symbol)
    bad_sym = int(syms.isna().sum())
    if bad_sym:
        sample = sorted(set(str(x) for x in df.loc[syms.isna(), sym_col].head(5)))
        res.add("warn", "CSV", "%d 行的代码无法识别，已丢弃（例：%s）"
                % (bad_sym, ", ".join(sample)),
                "支持的写法：600000.SH / sh600000 / 600000（6 位纯数字会按首位猜交易所）")
    d["symbol"] = syms
    for f in FIELDS:
        if f in colmap:
            d[f] = pd.to_numeric(df[colmap[f]], errors="coerce")
    d = d.dropna(subset=["date", "symbol"])
    if d.empty:
        res.add("error", "CSV", "清洗后没有可用数据")
        return {}

    res.n_rows = int(len(d))
    out: Dict[str, pd.DataFrame] = {}
    for sym, g in d.groupby("symbol", sort=True):
        g = g.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        out[str(sym)] = g.reset_index(drop=True)
    return out


# --------------------------------------------------------------------------
# 写盘
# --------------------------------------------------------------------------

def _bin_path(uri: Path, symbol: str, fld: str, freq: str) -> Path:
    return uri / "features" / symbol.lower() / ("%s.%s.bin" % (fld, freq))


def _read_bin(path: Path) -> Optional[Tuple[int, np.ndarray]]:
    if not path.is_file():
        return None
    try:
        arr = np.fromfile(path, dtype="<f")
    except OSError:
        return None
    if arr.size == 0:
        return None
    return int(arr[0]), arr[1:]


def _write_bin(path: Path, start: int, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.hstack([np.float32(start), values.astype("<f")]).tofile(path)


def _series_for(df: pd.DataFrame, fld: str, dates: Sequence[str]) -> Dict[str, float]:
    if fld not in df.columns:
        return {}
    pos = {d: i for i, d in enumerate(dates)}
    out: Dict[str, float] = {}
    for dt, v in zip(df["date"], df[fld]):
        if dt in pos and v == v:          # v == v 过滤 NaN
            out[dt] = float(v)
    return out


def _derive_change_from_array(close: np.ndarray) -> np.ndarray:
    """按官方 cn_data 的语义从 close 序列派生 ``change``。

    实测官方数据（sh600000，在 close 缺失的 3 天上）：
      - ``change`` 的 NaN 集合 = ``close`` 的 NaN 集合 ∪ {第 0 天}
      - 紧跟在缺失日之后的那天，``change = close[t] / close[上一个有效日] - 1``
        （即跨越缺口，而不是用前一天）

    这里刻意在**组装完成的整条序列**上算，而不是只算新导入的那一段 ——
    否则追加时第一天的 change 会算不出来（拿不到上一段最后一个收盘）。
    """
    out = np.full(close.shape, np.nan, dtype="<f")
    prev = np.nan
    for i, c in enumerate(close):
        if not np.isfinite(c):
            continue
        if np.isfinite(prev) and prev != 0:
            out[i] = c / prev - 1.0
        prev = c
    return out


def _assemble(old: Optional[Tuple[int, np.ndarray]], start: int, n: int,
              values: Dict[int, float]) -> np.ndarray:
    """把「已有序列」和「新值」拼成一条长度 n、起始下标 start 的数组。

    新值覆盖旧值；没值的位置是 NaN。
    """
    out = np.full(n, np.nan, dtype="<f")
    if old is not None:
        o_start, o_vals = old
        for j, v in enumerate(o_vals):
            p = o_start + j - start
            if 0 <= p < n:
                out[p] = v
    for pos, v in values.items():
        p = pos - start
        if 0 <= p < n:
            out[p] = v
    return out


def _write_symbol(plan: SymbolPlan, df: pd.DataFrame, uri: Path,
                  merged: Sequence[str], idx: Dict[str, int],
                  freq: str, old_len: int, res: ImportResult) -> None:
    sym, scale = plan.symbol, plan.scale
    dates = list(df["date"])

    # 目标区间 = 已有数据覆盖范围 ∪ 新数据覆盖范围。
    # 只动被导入的标的，其余文件保持原样 —— 日历只往后长，已有下标不会变。
    new_pos = [idx[d] for d in dates]
    start, end = min(new_pos), max(new_pos)
    old_close = _read_bin(_bin_path(uri, sym, "close", freq))
    if old_close is not None:
        start = min(start, old_close[0])
        end = max(end, old_close[0] + len(old_close[1]) - 1)
    n = end - start + 1

    # close 先写：它决定 change 的派生，也决定区间是否合理
    close_vals = {idx[d]: v * scale for d, v in _series_for(df, "close", dates).items()}
    close_arr = _assemble(old_close, start, n, close_vals)
    _write_bin(_bin_path(uri, sym, "close", freq), start, close_arr)

    # 写完自检：组装后的整条序列不该出现涨跌停之外的跳变。
    # 这是最后一道网 —— 无论缩放算错、覆盖了不同基准的数据、还是源数据本身
    # 有除权，都会在这里现形，而不是等到回测结果离谱才发现。
    if close_arr.size > 1:
        with np.errstate(invalid="ignore", divide="ignore"):
            r = close_arr[1:] / close_arr[:-1] - 1.0
        finite = r[np.isfinite(r)]
        if finite.size:
            worst = float(np.max(np.abs(finite)))
            if worst > SEAM_ALERT:
                res.add("warn", sym,
                        "组装后的序列里最大单日涨跌 %.1f%%，超过涨跌停上限 %.0f%%"
                        % (worst * 100, SEAM_ALERT * 100),
                        "通常是价格基准没对齐（新数据与已有数据的复权方式不同），"
                        "或源数据本身有未处理的除权。请核对数据源")

    for fld in FIELDS:
        if fld == "close":
            continue
        if fld == "change":
            given = _series_for(df, "change", dates)
            if given:
                arr = _assemble(_read_bin(_bin_path(uri, sym, fld, freq)), start, n,
                                {idx[d]: v for d, v in given.items()})
            else:
                # 没有就用整条 close 序列派生（与官方语义一致）
                arr = _derive_change_from_array(close_arr)
            _write_bin(_bin_path(uri, sym, fld, freq), start, arr)
            continue
        if fld == "factor":
            _write_factor(sym, df, uri, dates, idx, start, n, freq)
            continue

        series = _series_for(df, fld, dates)
        if not series:
            continue
        if fld in ("open", "high", "low"):
            series = {k: v * scale for k, v in series.items()}
        arr = _assemble(_read_bin(_bin_path(uri, sym, fld, freq)), start, n,
                        {idx[d]: v for d, v in series.items()})
        _write_bin(_bin_path(uri, sym, fld, freq), start, arr)


def _write_factor(sym: str, df: pd.DataFrame, uri: Path, dates: Sequence[str],
                  idx: Dict[str, int], start: int, n: int, freq: str) -> None:
    """写 ``factor``。

    qlib 用它做「100 股整手」的成交单位取整；**缺了会退化成 adjusted_price
    模式并关闭整手取整**（见 ``qlib/backtest/exchange.py:222`` 的警告
    "trade unit 100 is not supported in adjusted_price mode"）。
    官方 cn_data 有逐日复权因子，所以不会踩到；导入的数据必须自己写。

    本模块**不做任何复权**，所以默认写常数 ``1.0``（"因子就是 1"）；输入带
    ``factor`` 列就原样透传。追加到已有数据时，新日期沿用最后一个已知因子，
    避免序列在接缝处跳变。
    """
    path = _bin_path(uri, sym, "factor", freq)
    old = _read_bin(path)
    given = _series_for(df, "factor", dates)
    if given:
        values = {idx[d]: v for d, v in given.items()}
    else:
        last = 1.0
        if old is not None:
            finite = old[1][np.isfinite(old[1])]
            if finite.size:
                last = float(finite[-1])
        values = {idx[d]: last for d in dates}
    _write_bin(path, start, _assemble(old, start, n, values))


def import_csv(source: str, out_dir: str, *, freq: str = "day",
               normalize: bool = True, dry_run: bool = False,
               limit: Optional[int] = None,
               instrument_list: Optional[str] = None) -> ImportResult:
    """把 CSV 导入成 qlib bin 目录。

    Args:
        source: CSV 文件或包含 CSV 的目录。
        out_dir: 目标 qlib 数据目录（不存在则新建；存在则增量合并）。
        normalize: 新标的的 OHLC 是否按首日收盘归一化（默认 True，
            与官方 cn_data 的约定一致，使 ``close`` 首值为 1.0）。
            追加到已有标的时**总是**按重叠段对齐，与此开关无关。
        dry_run: 只算不写。
        limit: 目录模式下最多读几个文件（调试用）。
        instrument_list: 额外生成一个股票池清单文件（如 ``mypool`` →
            ``instruments/mypool.txt``），内容是导入的标的中**剔掉指数**的部分。
            工作流里就能写 ``instruments: mypool``。不指定则只写 ``all.txt``
            （它包含指数，不适合直接当股票池）。
    """
    res = ImportResult(out_dir=str(out_dir), freq=freq, dry_run=dry_run)
    uri = Path(out_dir)

    # 1) 读入
    by_symbol = load_source(source, res, limit=limit)
    if not by_symbol:
        if not res.errors():
            res.add("error", str(source), "没有读到任何数据")
        return res
    res.n_symbols = len(by_symbol)

    # 2) 日历
    old_cal = read_calendar(str(uri), freq) if uri.is_dir() else []
    new_dates = sorted({d for g in by_symbol.values() for d in g["date"]})
    if not new_dates:
        res.add("error", "CSV", "没有有效日期")
        return res
    res.created = not old_cal

    if old_cal:
        if new_dates[0] < old_cal[0]:
            res.add("error", "日历",
                    "新数据最早日期 %s 早于已有日历首日 %s"
                    % (new_dates[0], old_cal[0]),
                    "往前插日期会让所有已有标的的下标整体位移，需要重写全部 bin。"
                    "请把数据导入到一个新目录，或先自行补齐日历")
            return res
        merged = sorted(set(old_cal) | set(new_dates))
        res.n_days_added = len(merged) - len(old_cal)
    else:
        merged = new_dates
        res.n_days_added = len(merged)
    res.calendar_start, res.calendar_end, res.n_days = merged[0], merged[-1], len(merged)
    idx = {d: i for i, d in enumerate(merged)}
    old_len = len(old_cal)

    # 3) 逐标的规划
    touched: List[SymbolPlan] = []
    for sym in sorted(by_symbol):
        plan = _plan_symbol(sym, by_symbol[sym], uri, merged, idx, old_len, freq,
                            normalize, res)
        touched.append(plan)
    res.plans = touched

    ok_plans = [p for p in touched if not p.problems]
    if not ok_plans:
        res.add("error", "导入", "所有标的都无法导入（见上面的原因）")
        return res
    skipped = len(touched) - len(ok_plans)
    if skipped:
        res.add("warn", "导入", "%d 个标的被跳过" % skipped,
                "原因见各标的的说明；其余 %d 个可以正常导入" % len(ok_plans))

    if dry_run:
        return res

    # 4) 写盘
    for plan in ok_plans:
        _write_symbol(plan, by_symbol[plan.symbol], uri, merged, idx, freq, old_len, res)
    _write_calendar(uri, merged, freq)
    _write_instruments(uri, ok_plans, merged, freq)
    if instrument_list:
        _write_named_list(uri, instrument_list, ok_plans, res)
    _warn_missing_benchmark(uri, ok_plans, res)
    return res


def _write_named_list(uri: Path, name: str, plans: Sequence[SymbolPlan],
                      res: ImportResult) -> None:
    """写一个「剔除指数」的股票池清单。

    为什么需要：``all.txt`` 里既有股票也有指数（回测基准要用到指数），
    直接把它当股票池会让指数被当成可交易标的选进持仓。
    """
    name = name.strip()
    if not name.endswith(".txt"):
        name += ".txt"
    stocks = [p for p in plans if not p.problems and not is_index_like(p.symbol)]
    excluded = [p.symbol for p in plans if not p.problems and is_index_like(p.symbol)]
    res.instrument_list = name
    res.n_index_like = len(excluded)
    p = uri / "instruments" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for plan in sorted(stocks, key=lambda x: x.symbol):
            f.write("%s\t%s\t%s\n" % (plan.symbol, plan.first_date, plan.last_date))
    res.add("info", "instruments/%s" % name,
            "已生成股票池：%d 只%s"
            % (len(stocks), ("（剔除 %d 个指数：%s）"
                             % (len(excluded), ", ".join(excluded[:4]))
                             if excluded else "")),
            "工作流里把 instruments 设成 %s 即可" % name[:-4])


def _warn_missing_benchmark(uri: Path, plans: Sequence[SymbolPlan],
                            res: ImportResult) -> None:
    """导入的数据里没有指数时提醒：回测节点的默认基准是 SH000300。

    实测踩过：只导入个股后跑回测，qlib 抛
    ``ValueError: The benchmark ['SH000300'] does not exist`` ——
    报错很明确，但用户不容易想到「基准也得在数据里」。
    """
    have = {p.symbol for p in plans if not p.problems}
    if any(is_index_like(s) for s in have):
        return
    res.add("warn", "回测基准",
            "导入的数据里没有任何指数（如 SH000300 / SH000905）",
            "回测节点的「基准」属性默认是 SH000300，数据里没有它时回测会直接失败。"
            "要么把指数一起导入，要么把该属性留空/改成数据里有的代码")


def _plan_symbol(sym: str, df: pd.DataFrame, uri: Path, merged: Sequence[str],
                 idx: Dict[str, int], old_len: int, freq: str,
                 normalize: bool, res: ImportResult) -> SymbolPlan:
    """决定缩放系数、起止与是否需要跳过。"""
    plan = SymbolPlan(symbol=sym)
    dates = list(df["date"])
    plan.n_days = len(dates)
    plan.first_date, plan.last_date = dates[0], dates[-1]

    close = _series_for(df, "close", dates)
    if not close:
        plan.problems.append("没有有效的 close")
        return plan
    first_close = close[min(close, key=lambda d: idx[d])]

    old = _read_bin(_bin_path(uri, sym, "close", freq))
    plan.is_new = old is None

    if old is None:
        # 新标的：按首日收盘归一化，与官方约定一致
        if normalize and first_close:
            plan.scale = 1.0 / first_close
            plan.scale_from = "first-close"
        else:
            plan.scale, plan.scale_from = 1.0, "none"
        return plan

    # 已有标的。先分清这次是「延伸数据」还是「只改已有日期的值」——
    # 两者的价格基准假设完全不同：
    #
    # - 有新日期（idx >= old_len）：输入是一个**数据源**，它的复权方式未必和
    #   已有数据一样，所以必须靠重叠段把基准对齐，否则接缝处会凭空多一个收益。
    # - 没有新日期：输入是**修正值**，本来就该和已有数据同基准。此时若还按重叠
    #   缩放，缩放系数会被修正值本身带偏 —— 极端情况下（只改一天且改的是首日）
    #   会算出「正好抵消」的系数，写入后什么都没变，用户以为改好了其实没有。
    has_new = any(idx[d] >= old_len for d in dates)
    old_start, old_vals = old

    if not has_new:
        plan.scale, plan.scale_from = 1.0, "none(覆盖)"
        return plan

    overlap = [(idx[d], close[d]) for d in close
               if idx[d] < old_len and old_start <= idx[d] < old_start + len(old_vals)
               and np.isfinite(old_vals[idx[d] - old_start]) and old_vals[idx[d] - old_start] != 0]
    if overlap:
        ratios = [float(old_vals[i - old_start]) / raw for i, raw in overlap if raw]
        if ratios:
            plan.scale = float(np.median(ratios))
            plan.scale_from = "overlap"
    elif "factor" in df.columns and df["factor"].notna().any():
        plan.scale, plan.scale_from = 1.0, "factor"
    else:
        plan.problems.append(
            "无法确定价格基准：新数据与已有数据没有日期重叠，且没有 factor 列")
        res.add("warn", sym, plan.problems[-1],
                "已有数据是归一化复权价（首值 1.0）。直接追加原始价会在接缝处"
                "产生假的暴涨暴跌。请让新数据覆盖至少一天已有日期，"
                "或提供 factor 列，或把数据导到新目录")
        return plan

    # 接缝自检：用重叠段的最后一个共同日之后的第一个新日期算收益率
    common = sorted(d for d in close if idx[d] < old_len
                    and old_start <= idx[d] < old_start + len(old_vals)
                    and np.isfinite(old_vals[idx[d] - old_start]))
    after = sorted(d for d in close if idx[d] >= old_len)
    if common and after:
        last_common = common[-1]
        base = float(old_vals[idx[last_common] - old_start])
        nxt = after[0]
        nxt_val = close[nxt] * plan.scale
        if base:
            r = nxt_val / base - 1.0
            plan.seam_return = r
            if abs(r) > SEAM_ALERT:
                plan.problems.append(
                    "接缝收益率 %.1f%% 超过涨跌停上限，价格基准可能不对" % (r * 100))
                res.add("warn", sym, plan.problems[-1],
                        "已按重叠段缩放（k=%.6f），但仍异常，请检查数据源是否"
                        "已复权、或复权方式与已有数据不同" % plan.scale)
    return plan


def _write_calendar(uri: Path, merged: Sequence[str], freq: str) -> None:
    p = uri / "calendars" / ("%s.txt" % freq)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for d in merged:
            f.write(d + "\n")


def _write_instruments(uri: Path, plans: Sequence[SymbolPlan],
                       merged: Sequence[str], freq: str) -> None:
    """合并 ``instruments/all.txt``（保留已有条目与顺序，更新被导入的）。"""
    p = uri / "instruments" / "all.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = read_instrument_list(str(uri), "all.txt")

    for plan in plans:
        # 结束日取「最后一个有值的那天」
        last = plan.last_date
        start = plan.first_date
        if plan.symbol in rows:
            start = min(start, rows[plan.symbol][0])
            last = max(last, rows[plan.symbol][1])
        rows[plan.symbol] = (start, last)

    with p.open("w", encoding="utf-8", newline="\n") as f:
        for sym in sorted(rows):
            f.write("%s\t%s\t%s\n" % (sym, rows[sym][0], rows[sym][1]))


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------

def format_result(res: ImportResult) -> str:
    L: List[str] = []
    L.append("=" * 66)
    L.append("CSV → qlib 数据导入" + ("（演练，未写盘）" if res.dry_run else ""))
    L.append("=" * 66)
    L.append("目标目录  %s" % res.out_dir)
    L.append("模式      %s" % ("新建" if res.created else "追加到已有目录"))
    L.append("日历      %s → %s（%d 天，新增 %d）"
             % (res.calendar_start, res.calendar_end, res.n_days, res.n_days_added))
    L.append("数据      %d 个标的 / %d 行" % (res.n_symbols, res.n_rows))
    if res.instrument_list:
        L.append("股票池    instruments/%s（已剔除 %d 个指数）"
                 % (res.instrument_list, res.n_index_like))
    L.append("")

    if res.plans:
        L.append("【标的】")
        w = max(len(p.symbol) for p in res.plans)
        shown = res.plans[:12]
        for p in shown:
            tag = "新建" if p.is_new else "追加"
            seam = ("  接缝 %.2f%%" % (p.seam_return * 100)) if p.seam_return is not None else ""
            bad = ("  ✗ " + p.problems[0]) if p.problems else ""
            L.append("  %-*s  %s  %s→%s  %3d 天  缩放 %-11s k=%.6f%s%s"
                     % (w, p.symbol, tag, p.first_date, p.last_date, p.n_days,
                        p.scale_from, p.scale, seam, bad))
        if len(res.plans) > len(shown):
            L.append("  ... 另有 %d 个标的" % (len(res.plans) - len(shown)))
        L.append("")

    for level, title in (("error", "错误"), ("warn", "警告"), ("info", "提示")):
        items = [i for i in res.issues if i.level == level]
        if items:
            L.append("【%s】%d 条" % (title, len(items)))
            for i in items:
                L.append("  " + str(i))
            L.append("")

    L.append("=" * 66)
    if res.errors():
        L.append("结论：有 %d 个错误，未写盘。" % len(res.errors()))
    elif res.dry_run:
        L.append("结论：演练通过，可去掉 --dry-run 真正写入。")
    else:
        L.append("结论：已写入 %d 个标的，可用区间 %s → %s"
                 % (len([p for p in res.plans if not p.problems]),
                    res.calendar_start, res.calendar_end))
        L.append("      建议接着跑：python -m pipeline data-check --provider-uri \"%s\""
                 % res.out_dir)
    L.append("=" * 66)
    return "\n".join(L)
