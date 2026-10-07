# -*- coding: utf-8 -*-
"""数据管理（体检 + CSV 导入）的测试。

两部分：
1. **体检**：在临时目录里手工造各种「坏数据」，逐条验证检查项真的会报、
   且严重程度合适（错误 / 警告 / 提示）。造数据比找一个坏数据集可靠得多。
2. **导入**：覆盖新建、增量追加、价格基准对齐、编码与列名兼容、
   以及几个**必须拒绝**的情形（拒绝比猜一个缩放系数安全）。

真实仓库的断言放在最后：官方 cn_data 应当 0 错误、0 误报。
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.data_health import (check, format_report, read_calendar, read_field,
                                  read_instrument_list, report_json)
from pipeline.data_import import (import_csv, is_index_like, map_columns,
                                  normalize_symbol)

REAL_DATA = Path(r"E:\2025\RockX20251003\RockXFWV21\qlib_data\cn_data")

#: 测试临时目录前缀。**刻意不做清理**，原因见下。
_TMP_PREFIX = "rockx_data_test_"


class _TmpCase(unittest.TestCase):
    """每个用例一个全新的临时目录，**跑完不删除**。

    为什么不清：本机删目录极慢 —— 沙箱的 shim 包了 ``os.rmdir``，
    单次约 0.9 秒；一次 ``shutil.rmtree`` 清 251 个目录花了 **237 秒**，
    而 51 个用例本身只要 15 秒。删目录成了整个套件最贵的操作。

    试过「固定目录 + 不清理」，但残留文件会让第二次运行结果不同
    （追加类用例尤其敏感）。所以改成：**每用例一个全新目录，永不删除**。
    每个目录约 10 KB，位于系统临时目录下，可随时手动删掉
    ``%TEMP%/rockx_data_test_*``。
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix=_TMP_PREFIX))


# --------------------------------------------------------------------------
# 造数据的小工具
# --------------------------------------------------------------------------

def _write_bin(path: Path, start: int, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.hstack([np.float32(start), np.asarray(values, dtype="<f")]).tofile(path)


def _make_dataset(root: Path, cal, instruments=None, series=None,
                  freq: str = "day") -> Path:
    """手工拼一个 qlib 数据目录。

    Args:
        cal: 日历日期列表
        instruments: ``{清单名: {代码: (start, end)}}``
        series: ``{代码: {字段: (起始下标, [值...])}}``
    """
    (root / "calendars").mkdir(parents=True, exist_ok=True)
    (root / "features").mkdir(parents=True, exist_ok=True)
    (root / "instruments").mkdir(parents=True, exist_ok=True)
    (root / "calendars" / ("%s.txt" % freq)).write_text(
        "\n".join(cal) + "\n", encoding="utf-8")
    for name, rows in (instruments or {}).items():
        (root / "instruments" / name).write_text(
            "".join("%s\t%s\t%s\n" % (s, a, b) for s, (a, b) in rows.items()),
            encoding="utf-8")
    for sym, fields in (series or {}).items():
        for fld, (start, vals) in fields.items():
            _write_bin(root / "features" / sym / ("%s.%s.bin" % (fld, freq)),
                       start, vals)
    return root


def _good_dataset(root: Path) -> Path:
    """一份「体检应当全绿」的最小数据集。"""
    cal = ["2024-01-%02d" % d for d in range(2, 21)]
    vals = [1.0 + 0.01 * i for i in range(len(cal))]
    fields = {"close": (0, vals),
              "open": (0, [v * 0.99 for v in vals]),
              "high": (0, [v * 1.02 for v in vals]),
              "low": (0, [v * 0.98 for v in vals]),
              "volume": (0, [1e6] * len(cal)),
              "factor": (0, [1.0] * len(cal)),
              "change": (0, [float("nan")] + [0.01] * (len(cal) - 1))}
    return _make_dataset(
        root, cal,
        instruments={"all.txt": {"SH600000": (cal[0], cal[-1]),
                                 "SZ000001": (cal[0], cal[-1])}},
        series={"sh600000": fields, "sz000001": fields})


class HealthBasicsTest(_TmpCase):
    def test_good_dataset_has_no_errors(self):
        rep = check(str(_good_dataset(self.tmp / "d")), check_templates=False)
        self.assertTrue(rep.usable)
        self.assertEqual([str(i) for i in rep.errors()], [])
        self.assertEqual(rep.days, 19)
        self.assertEqual(rep.start, "2024-01-02")
        self.assertEqual(rep.n_feature_dirs, 2)
        self.assertEqual(rep.instrument_lists["all.txt"]["SH600000"],
                         ("2024-01-02", "2024-01-20"))

    def test_missing_dir_is_error(self):
        rep = check(str(self.tmp / "nope"), check_templates=False)
        self.assertFalse(rep.usable)
        self.assertTrue(rep.errors())

    def test_not_a_qlib_dir_is_error(self):
        d = self.tmp / "empty"
        d.mkdir()
        rep = check(str(d), check_templates=False)
        self.assertFalse(rep.usable)
        self.assertIn("不是 qlib 数据目录", rep.errors()[0].message)

    def test_duplicate_calendar_dates(self):
        cal = ["2024-01-02", "2024-01-03", "2024-01-03", "2024-01-04"]
        _make_dataset(self.tmp / "d", cal)
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("重复交易日" in e.message for e in rep.errors()))

    def test_unsorted_calendar(self):
        cal = ["2024-01-03", "2024-01-02", "2024-01-04"]
        _make_dataset(self.tmp / "d", cal)
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("升序" in e.message for e in rep.errors()))

    def test_bad_date_format(self):
        cal = ["2024/01/02", "2024-01-03"]
        _make_dataset(self.tmp / "d", cal)
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("YYYY-MM-DD" in e.message for e in rep.errors()))

    def test_calendar_gap_warns(self):
        cal = ["2024-01-02", "2024-01-03", "2024-03-01"]
        _make_dataset(self.tmp / "d", cal)
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("间隔超过" in w.message for w in rep.warns()))

    def test_stale_data_warns(self):
        rep = check(str(_good_dataset(self.tmp / "d")), check_templates=False)
        self.assertTrue(any("距今" in w.message for w in rep.warns()))

    def test_instrument_range_reversed(self):
        cal = ["2024-01-02", "2024-01-03"]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": ("2024-01-03", "2024-01-02")}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("起止颠倒" in e.message for e in rep.errors()))

    def test_bin_start_index_out_of_range(self):
        cal = ["2024-01-02", "2024-01-03", "2024-01-04"]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[-1])}},
                      series={"sh600000": {"close": (99, [1.0, 1.1])}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("越界" in e.message for e in rep.errors()))

    def test_bin_length_overflows_calendar(self):
        cal = ["2024-01-02", "2024-01-03"]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[1])}},
                      series={"sh600000": {"close": (1, [1.0] * 5)}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("长度越界" in e.message for e in rep.errors()))

    def test_range_mismatch_against_instruments(self):
        """bin 覆盖的区间和清单声明不一致 —— 整体错位的信号。"""
        cal = ["2024-01-%02d" % d for d in range(2, 11)]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[-1])}},
                      series={"sh600000": {"close": (2, [1.0] * 3)}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("区间不符" in e.message for e in rep.errors()))

    def test_all_nan_symbol_is_reported(self):
        cal = ["2024-01-%02d" % d for d in range(2, 11)]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[-1])}},
                      series={"sh600000": {"close": (0, [float("nan")] * len(cal))}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertEqual(rep.checked[0].nan_ratio, 1.0)

    def test_high_below_low_is_counted(self):
        cal = ["2024-01-%02d" % d for d in range(2, 31)]
        n = len(cal)
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[-1])}},
                      series={"sh600000": {
                          "close": (0, [1.0] * n),
                          "high": (0, [0.9] * n),      # 故意反了
                          "low": (0, [1.1] * n)}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertGreaterEqual(rep.checked[0].price_conflicts, n)

    def test_missing_close_is_error(self):
        cal = ["2024-01-02", "2024-01-03"]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[1])}},
                      series={"sh600000": {"volume": (0, [1e6, 1e6])}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("没有任何标的带 `close`" in e.message for e in rep.errors()))

    def test_all_txt_mismatch_is_error(self):
        """all.txt 是权威清单，与 features 不一致就是错误。"""
        cal = ["2024-01-02", "2024-01-03"]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[1]),
                                               "SZ000001": (cal[0], cal[1])}},
                      series={"sh600000": {"close": (0, [1.0, 1.1])}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertTrue(any("SZ000001".lower() in e.message for e in rep.errors()))

    def test_membership_list_gap_is_only_info(self):
        """指数成分里有快照外的股票是正常的，不该报错。"""
        cal = ["2024-01-02", "2024-01-03"]
        _make_dataset(self.tmp / "d", cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[1])},
                                   "csi300.txt": {"SH600000": (cal[0], cal[1]),
                                                  "SH600999": (cal[0], cal[1])}},
                      series={"sh600000": {"close": (0, [1.0, 1.1])}})
        rep = check(str(self.tmp / "d"), check_templates=False)
        self.assertEqual([str(i) for i in rep.errors()], [])
        self.assertTrue(any("没有数据（多为已退市）" in i.message
                            for i in rep.issues if i.level == "info"))

    def test_report_json_shape(self):
        rep = check(str(_good_dataset(self.tmp / "d")), check_templates=False)
        j = report_json(rep)
        for k in ("provider_uri", "usable", "start", "end", "days",
                  "instruments", "fields", "errors", "warnings", "infos"):
            self.assertIn(k, j)
        self.assertEqual(j["days"], 19)

    def test_format_report_mentions_verdict(self):
        rep = check(str(_good_dataset(self.tmp / "d")), check_templates=False)
        self.assertIn("结论", format_report(rep))
        self.assertIn("可用区间", format_report(rep))


class HealthTemplateCrossCheckTest(_TmpCase):
    """模板 vs 数据的对照（区间、基准）。"""

    def setUp(self):
        super().setUp()
        self.data = _good_dataset(self.tmp / "d")
        self.tdir = self.tmp / "pipelines"
        self.tdir.mkdir()

    def _template(self, name, steps):
        import yaml
        (self.tdir / name).write_text(yaml.safe_dump({"steps": steps},
                                                     allow_unicode=True),
                                      encoding="utf-8")

    def test_date_outside_coverage_warns(self):
        self._template("a.yaml", [
            {"type": "init", "props": {"provider_uri": str(self.data)}},
            {"type": "backtest", "props": {"end_time": "2025-01-01"}}])
        rep = check(str(self.data), templates_dir=self.tdir)
        self.assertTrue(any("超出数据覆盖" in w.message for w in rep.warns()))

    def test_dates_inside_coverage_are_clean(self):
        self._template("a.yaml", [
            {"type": "init", "props": {"provider_uri": str(self.data)}},
            {"type": "backtest", "props": {"end_time": "2024-01-15"}}])
        rep = check(str(self.data), templates_dir=self.tdir)
        self.assertFalse(any("超出数据覆盖" in w.message for w in rep.warns()))

    def test_missing_benchmark_warns(self):
        """回测基准不在数据里 -> qlib 会直接抛，必须提前提示。"""
        self._template("a.yaml", [
            {"type": "backtest", "props": {"benchmark": "SH000300"}}])
        rep = check(str(self.data), templates_dir=self.tdir)
        self.assertTrue(any("基准" in w.where for w in rep.warns()))

    def test_benchmark_present_is_clean(self):
        cal = read_calendar(str(self.data))
        _make_dataset(self.data, cal,
                      instruments={"all.txt": {"SH600000": (cal[0], cal[-1]),
                                               "SH000300": (cal[0], cal[-1])}},
                      series={"sh600000": {"close": (0, [1.0] * len(cal))},
                              "sh000300": {"close": (0, [1.0] * len(cal))}})
        self._template("a.yaml", [
            {"type": "backtest", "props": {"benchmark": "SH000300"}}])
        rep = check(str(self.data), templates_dir=self.tdir)
        self.assertFalse(any("基准" in w.where for w in rep.warns()))


# --------------------------------------------------------------------------
# 导入
# --------------------------------------------------------------------------

class SymbolTest(unittest.TestCase):
    def test_common_formats(self):
        for raw, want in (("600000.SH", "SH600000"), ("sh600000", "SH600000"),
                          ("SH600000", "SH600000"), ("600000.XSHG", "SH600000"),
                          ("000001.SZ", "SZ000001"), ("sz000001", "SZ000001"),
                          ("000300.SH", "SH000300"), ("000001.XSHE", "SZ000001")):
            self.assertEqual(normalize_symbol(raw), want, raw)

    def test_bare_code_guesses_exchange(self):
        self.assertEqual(normalize_symbol("600000"), "SH600000")
        self.assertEqual(normalize_symbol("000001"), "SZ000001")
        self.assertEqual(normalize_symbol("300750"), "SZ300750")
        self.assertEqual(normalize_symbol("688981"), "SH688981")
        self.assertEqual(normalize_symbol("830799"), "BJ830799")

    def test_invalid(self):
        for raw in ("", None, "abc", "12345", "600000.XX"):
            self.assertIsNone(normalize_symbol(raw), raw)

    def test_index_like(self):
        self.assertTrue(is_index_like("SH000300"))
        self.assertTrue(is_index_like("SH000905"))
        self.assertTrue(is_index_like("SZ399006"))
        self.assertFalse(is_index_like("SH600000"))
        self.assertFalse(is_index_like("SZ000001"))     # 平安银行是指数码段但深市个股

    def test_column_aliases(self):
        cols = ["日期", "股票代码", "开盘价", "最高价", "最低价", "收盘价", "成交量"]
        m = map_columns(cols)
        self.assertEqual(m["date"], "日期")
        self.assertEqual(m["symbol"], "股票代码")
        self.assertEqual(m["close"], "收盘价")
        m2 = map_columns(["trade_date", "ts_code", "open", "high", "low",
                          "close", "vol", "adj_factor"])
        self.assertEqual(m2["date"], "trade_date")
        self.assertEqual(m2["volume"], "vol")
        self.assertEqual(m2["factor"], "adj_factor")


class ImportTest(_TmpCase):
    def setUp(self):
        super().setUp()
        self.dates = pd.bdate_range("2024-01-02", periods=20).strftime("%Y-%m-%d")
        self.csv = self.tmp / "a.csv"
        self._write(self.csv, self.dates, base=10.0)

    def _write(self, path, dates, base=10.0, drift=0.01, symbols=("600000.SH",),
               start_j=0, **kw):
        rows = []
        for sym in symbols:
            for j, d in enumerate(dates):
                px = base * (1 + drift * (start_j + j))
                rows.append({"date": d, "symbol": sym, "open": px * 0.99,
                             "high": px * 1.02, "low": px * 0.98, "close": px,
                             "volume": 1e6 + j, **kw})
        pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")
        return rows

    def _read(self, out, sym, fld="close"):
        p = Path(out) / "features" / sym / ("%s.day.bin" % fld)
        a = np.fromfile(p, dtype="<f")
        return int(a[0]), a[1:]

    # ---- 新建 ----

    def test_fresh_import(self):
        out = self.tmp / "d"
        res = import_csv(str(self.csv), str(out))
        self.assertEqual(res.n_symbols, 1)
        self.assertTrue(res.created)
        self.assertEqual(res.calendar_start, self.dates[0])
        self.assertEqual(res.calendar_end, self.dates[-1])
        self.assertEqual(read_calendar(str(out)), list(self.dates))
        self.assertEqual(read_instrument_list(str(out), "all.txt"),
                         {"SH600000": (self.dates[0], self.dates[-1])})

    def test_close_normalized_to_one(self):
        """与官方约定一致：每只标的首值恰为 1.0。"""
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        si, v = self._read(out, "sh600000")
        self.assertEqual(si, 0)
        self.assertAlmostEqual(float(v[0]), 1.0, places=6)
        # 末值应为 (1+0.01*19)
        self.assertAlmostEqual(float(v[-1]), 1.19, places=5)

    def test_open_high_low_scaled_together(self):
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        for fld in ("open", "high", "low"):
            _si, v = self._read(out, "sh600000", fld)
            self.assertAlmostEqual(float(v[0]), {"open": 0.99, "high": 1.02,
                                                 "low": 0.98}[fld], places=5)

    def test_change_is_derived(self):
        """没有 change 列时按官方语义从 close 派生。"""
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        _si, c = self._read(out, "sh600000", "close")
        _si, ch = self._read(out, "sh600000", "change")
        self.assertEqual(len(ch), len(c))
        self.assertFalse(np.isfinite(ch[0]))          # 第一天没有前值
        r = c[1:] / c[:-1] - 1
        np.testing.assert_allclose(ch[1:], r, rtol=1e-5, atol=1e-7)

    def test_dry_run_writes_nothing(self):
        out = self.tmp / "d"
        res = import_csv(str(self.csv), str(out), dry_run=True)
        self.assertTrue(res.dry_run)
        self.assertFalse(out.exists())

    def test_chinese_columns_and_gbk(self):
        out = self.tmp / "d"
        rows = [{"日期": d, "股票代码": "600000.SH", "开盘价": 9.9,
                 "最高价": 10.2, "最低价": 9.8, "收盘价": 10.0, "成交量": 1e6}
                for d in self.dates]
        p = self.tmp / "cn.csv"
        pd.DataFrame(rows).to_csv(p, index=False, encoding="gbk")
        res = import_csv(str(p), str(out))
        self.assertEqual(res.n_symbols, 1)
        self.assertAlmostEqual(float(self._read(out, "sh600000")[1][0]), 1.0, places=6)

    def test_per_symbol_directory(self):
        """目录模式：每个文件一只标的，文件名当代码（文件里没有代码列）。"""
        src = self.tmp / "src"
        src.mkdir()
        for fname, base in (("600000.SH.csv", 10.0), ("000001.SZ.csv", 20.0)):
            rows = [{"date": d, "open": base * 0.99, "high": base * 1.02,
                     "low": base * 0.98, "close": base, "volume": 1e6}
                    for d in self.dates]
            pd.DataFrame(rows).to_csv(src / fname, index=False, encoding="utf-8")
        out = self.tmp / "d"
        res = import_csv(str(src), str(out))
        self.assertEqual(res.n_symbols, 2)
        self.assertEqual({p.name for p in (out / "features").iterdir()},
                         {"sh600000", "sz000001"})

    def test_missing_close_column_is_error(self):
        p = self.tmp / "bad.csv"
        pd.DataFrame([{"date": d, "symbol": "600000.SH", "volume": 1}
                      for d in self.dates]).to_csv(p, index=False)
        res = import_csv(str(p), str(self.tmp / "d"))
        self.assertTrue(any("缺少必需列" in e.message for e in res.errors()))

    def test_unrecognized_columns_list_actual(self):
        p = self.tmp / "bad.csv"
        pd.DataFrame([{"A": 1, "B": 2}]).to_csv(p, index=False)
        res = import_csv(str(p), str(self.tmp / "d"))
        self.assertTrue(any("找不到日期列" in e.message for e in res.errors()))

    # ---- 增量追加 ----

    def test_append_with_overlap_aligns_scale(self):
        """带重叠时按重叠段算缩放，接缝不能出现假收益。"""
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        d2 = pd.bdate_range("2024-01-24", periods=15).strftime("%Y-%m-%d")
        self._write(self.tmp / "b.csv", d2, base=10.0, start_j=16)
        res = import_csv(str(self.tmp / "b.csv"), str(out))
        self.assertFalse(res.created)
        plan = res.plans[0]
        self.assertEqual(plan.scale_from, "overlap")
        self.assertAlmostEqual(plan.scale, 0.1, places=6)
        _si, v = self._read(out, "sh600000")
        r = v[1:] / v[:-1] - 1
        finite = r[np.isfinite(r)]
        self.assertLess(float(np.max(np.abs(finite))), 0.05)   # 无暴涨暴跌
        self.assertEqual(len(v), len(read_calendar(str(out))))

    def test_append_preserves_old_values(self):
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        before = self._read(out, "sh600000")[1].copy()
        d2 = pd.bdate_range("2024-01-24", periods=15).strftime("%Y-%m-%d")
        self._write(self.tmp / "b.csv", d2, base=10.0, start_j=16)
        import_csv(str(self.tmp / "b.csv"), str(out))
        after = self._read(out, "sh600000")[1]
        np.testing.assert_allclose(after[:len(before)], before, rtol=1e-6)

    def test_append_untouched_symbol_keeps_its_file(self):
        """只导入一只标的时，另一只的 bin 不该被改动。"""
        out = self.tmp / "d"
        self._write(self.csv, self.dates, symbols=("600000.SH", "000001.SZ"))
        import_csv(str(self.csv), str(out))
        other = out / "features" / "sz000001" / "close.day.bin"
        before = other.read_bytes()
        d2 = pd.bdate_range("2024-01-24", periods=15).strftime("%Y-%m-%d")
        self._write(self.tmp / "b.csv", d2, base=10.0, start_j=16,
                    symbols=("600000.SH",))
        import_csv(str(self.tmp / "b.csv"), str(out))
        self.assertEqual(other.read_bytes(), before)

    def test_append_without_overlap_or_factor_is_refused(self):
        """无法确定价格基准时**必须拒绝**，不能猜。"""
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        d2 = pd.bdate_range("2024-03-01", periods=5).strftime("%Y-%m-%d")
        self._write(self.tmp / "c.csv", d2, base=15.0)
        res = import_csv(str(self.tmp / "c.csv"), str(out))
        self.assertTrue(res.errors())
        self.assertTrue(any("无法确定价格基准" in w.message for w in res.issues))

    def test_append_with_factor_column_is_allowed(self):
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        d2 = pd.bdate_range("2024-03-01", periods=5).strftime("%Y-%m-%d")
        self._write(self.tmp / "c.csv", d2, base=15.0, factor=0.5)
        res = import_csv(str(self.tmp / "c.csv"), str(out))
        self.assertEqual(res.errors(), [])
        self.assertEqual(res.plans[0].scale_from, "factor")

    def test_dates_before_calendar_are_refused(self):
        """往前插日期会让所有已有 bin 的下标位移，必须拒绝。"""
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        d2 = pd.bdate_range("2023-12-01", periods=5).strftime("%Y-%m-%d")
        self._write(self.tmp / "c.csv", d2)
        res = import_csv(str(self.tmp / "c.csv"), str(out))
        self.assertTrue(res.errors())
        self.assertTrue(any("早于已有日历首日" in e.message for e in res.errors()))

    def test_overwrite_existing_dates(self):
        """新数据落在已有日历内 -> 覆盖那几天，日历不变。

        注意断言的是**比值**而不是绝对值：写入时按重叠段缩放，所以覆盖后
        归一化序列的起点仍是 1.0（这是对的 —— 保持整条序列同一基准）。
        覆盖生效的证据是「首日相对次日」的比例变了。
        """
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        cal_before = read_calendar(str(out))
        _si, before = self._read(out, "sh600000")
        ratio_before = before[1] / before[0]

        rows = [{"date": self.dates[0], "symbol": "600000.SH", "open": 5.0,
                 "high": 5.5, "low": 4.5, "close": 5.0, "volume": 1}]
        p = self.tmp / "fix.csv"
        pd.DataFrame(rows).to_csv(p, index=False)
        res = import_csv(str(p), str(out))
        self.assertEqual(res.n_days_added, 0)
        self.assertEqual(read_calendar(str(out)), cal_before)
        _si, after = self._read(out, "sh600000")
        # 纯覆盖（没有新日期）按「同基准修正值」处理 -> 直接写入，改的值真的生效
        self.assertAlmostEqual(float(after[0]), 5.0, places=5)
        self.assertNotAlmostEqual(float(after[1] / after[0]), float(ratio_before),
                                  places=3)
        self.assertEqual(res.plans[0].scale_from, "none(覆盖)")
        # 修正值与邻居差太多，写完自检应当报警（而不是悄悄写进去）
        self.assertTrue(any("最大单日涨跌" in w.message for w in res.issues))

    # ---- factor（qlib 用它做整手取整，缺了会退化）----

    def test_factor_written_as_one_when_absent(self):
        """没有 factor 列也要写 —— 否则 qlib 会切到 adjusted_price 模式并
        关闭「100 股整手」取整（实测 exchange.py 的警告）。"""
        out = self.tmp / "d"
        import_csv(str(self.csv), str(out))
        si, f = self._read(out, "sh600000", "factor")
        self.assertEqual(si, 0)
        self.assertTrue(np.all(np.isfinite(f)))
        np.testing.assert_allclose(f, 1.0)

    def test_factor_passed_through_when_given(self):
        out = self.tmp / "d"
        p = self.tmp / "f.csv"
        rows = [{"date": d, "symbol": "600000.SH", "open": 9.9, "high": 10.2,
                 "low": 9.8, "close": 10.0, "volume": 1e6, "factor": 0.5}
                for d in self.dates]
        pd.DataFrame(rows).to_csv(p, index=False)
        import_csv(str(p), str(out))
        _si, f = self._read(out, "sh600000", "factor")
        np.testing.assert_allclose(f, 0.5)

    def test_factor_continues_last_value_on_append(self):
        """追加时新日期沿用最后一个已知因子，避免序列跳变。"""
        out = self.tmp / "d"
        p = self.tmp / "f.csv"
        rows = [{"date": d, "symbol": "600000.SH", "open": 9.9, "high": 10.2,
                 "low": 9.8, "close": 10.0, "volume": 1e6, "factor": 0.5}
                for d in self.dates]
        pd.DataFrame(rows).to_csv(p, index=False)
        import_csv(str(p), str(out))
        d2 = pd.bdate_range("2024-01-24", periods=15).strftime("%Y-%m-%d")
        self._write(self.tmp / "b.csv", d2, base=10.0, start_j=16)
        import_csv(str(self.tmp / "b.csv"), str(out))
        _si, f = self._read(out, "sh600000", "factor")
        self.assertTrue(np.all(np.isfinite(f)))
        np.testing.assert_allclose(f, 0.5)      # 新段沿用了 0.5

    # ---- 股票池 ----

    def test_instrument_list_excludes_index(self):
        out = self.tmp / "d"
        self._write(self.csv, self.dates, symbols=("600000.SH", "000300.SH"))
        res = import_csv(str(self.csv), str(out), instrument_list="mypool")
        self.assertEqual(res.instrument_list, "mypool.txt")
        self.assertEqual(res.n_index_like, 1)
        pool = read_instrument_list(str(out), "mypool.txt")
        self.assertEqual(set(pool), {"SH600000"})
        allx = read_instrument_list(str(out), "all.txt")
        self.assertEqual(set(allx), {"SH600000", "SH000300"})

    def test_warns_when_no_benchmark_available(self):
        out = self.tmp / "d"
        res = import_csv(str(self.csv), str(out))
        self.assertTrue(any("没有任何指数" in w.message for w in res.issues))

    def test_no_benchmark_warning_when_index_present(self):
        out = self.tmp / "d"
        self._write(self.csv, self.dates, symbols=("600000.SH", "000300.SH"))
        res = import_csv(str(self.csv), str(out))
        self.assertFalse(any("没有任何指数" in w.message for w in res.issues))


class ImportRoundTripTest(_TmpCase):
    """导入 -> 体检 -> 全绿。两个模块互为验证。"""

    def test_imported_dataset_passes_health_check(self):
        dates = pd.bdate_range("2023-01-03", periods=120).strftime("%Y-%m-%d")
        rows = []
        for sym, base in (("600000.SH", 8.0), ("000001.SZ", 15.0),
                          ("300750.SZ", 180.0), ("000300.SH", 4000.0)):
            for j, d in enumerate(dates):
                px = base * (1 + 0.001 * j)
                rows.append({"date": d, "symbol": sym, "open": px * 0.99,
                             "high": px * 1.01, "low": px * 0.98,
                             "close": px, "volume": 1e6 + j})
        csv = self.tmp / "a.csv"
        pd.DataFrame(rows).to_csv(csv, index=False)
        out = self.tmp / "d"
        import_csv(str(csv), str(out), instrument_list="pool")

        rep = check(str(out), check_templates=False)
        self.assertEqual([str(i) for i in rep.errors()], [],
                         "导入的数据不该有错误")
        self.assertEqual(rep.days, 120)
        self.assertEqual(rep.n_feature_dirs, 4)
        self.assertIn("pool.txt", rep.instrument_lists)
        # 基准 SH000300 在数据里 -> 不该报「缺基准」
        self.assertFalse(any("基准" in w.where for w in rep.warns()))


class RealDataTest(unittest.TestCase):
    """对官方 cn_data 的断言：不能有错误、不能误报。"""

    @unittest.skipUnless(REAL_DATA.is_dir(), "本机没有官方 cn_data")
    def test_official_dataset_is_clean(self):
        rep = check(str(REAL_DATA), sample=150, check_templates=False)
        self.assertTrue(rep.usable)
        self.assertEqual([str(i) for i in rep.errors()], [],
                         "官方数据不该有错误级问题")
        self.assertEqual(rep.start, "1999-11-10")
        self.assertEqual(rep.days, 4943)
        self.assertIn("all.txt", rep.instrument_lists)
        # 官方 7 个字段齐全
        for f in ("open", "high", "low", "close", "volume"):
            self.assertEqual(rep.field_counts.get(f), rep.n_feature_dirs, f)

    @unittest.skipUnless(REAL_DATA.is_dir(), "本机没有官方 cn_data")
    def test_official_bin_reader_matches_format(self):
        """bin 首 4 字节是起始日历下标 —— 读错会让所有序列错位。"""
        info = read_field(str(REAL_DATA), "sh600000", "close")
        self.assertIsNotNone(info)
        self.assertEqual(info.start_index, 0)
        self.assertEqual(info.n, 4943)
        self.assertAlmostEqual(info.first, 1.0, places=6)

    @unittest.skipUnless(REAL_DATA.is_dir(), "本机没有官方 cn_data")
    def test_official_benchmark_check_has_no_false_positive(self):
        """官方数据带 SH000300/905/903，不该报缺基准。"""
        rep = check(str(REAL_DATA), sample=50)
        self.assertFalse(any("基准代码不在数据里" in w.message for w in rep.warns()))


class DataCheckGuiTest(unittest.TestCase):
    """GUI 菜单入口「数据体检」的离屏测试。没装 PySide6 时跳过。"""

    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication, QMainWindow
        except ImportError as e:                       # pragma: no cover
            raise unittest.SkipTest("需要 PySide6: %s" % e)
        cls.app = QApplication.instance() or QApplication([])
        cls.QMainWindow = QMainWindow

    def _fake(self):
        from PySide6.QtWidgets import QDialog, QMessageBox
        from gui.pipeline_panel import PipelineGuiMixin
        from pipeline.dryrun import FakeGraph
        from pipeline.specs import extract_specs

        QDialog.exec = lambda self: QDialog.Rejected          # 不阻塞
        QMessageBox.critical = staticmethod(lambda *a, **k: None)

        class Fake(self.QMainWindow, PipelineGuiMixin):
            def __init__(self):
                super().__init__()
                self.graph = FakeGraph(extract_specs())
                self.msgs = []
                self.status_label = None

            def log_message(self, m, level="INFO"):
                self.msgs.append((level, m))
        return Fake()

    def test_provider_uri_empty_when_no_init_node(self):
        self.assertEqual(self._fake()._canvas_provider_uri(), "")

    def test_data_check_logs_summary(self):
        f = self._fake()
        f.data_check()                       # 不抛异常
        self.assertTrue(any("数据体检" in m for _lv, m in f.msgs),
                        "体检后应当在日志里留一行摘要")

    def test_data_check_survives_missing_data(self):
        """没有任何数据目录时也不能崩（自动探测失败是常见情况）。"""
        import pipeline.data_health as H
        f = self._fake()
        old = H.find_qlib_data_path
        H.find_qlib_data_path = lambda *a, **k: None
        try:
            f.data_check()
        finally:
            H.find_qlib_data_path = old
        self.assertTrue(any("数据体检" in m for _lv, m in f.msgs))


if __name__ == "__main__":
    unittest.main()
