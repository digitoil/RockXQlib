# -*- coding: utf-8 -*-
"""``pipeline/qlib_benchmarks.py`` 的单元测试。

用临时目录构造假的 qlib benchmarks，不依赖真实的 examples/ 目录。
"""
from __future__ import annotations

import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.qlib_benchmarks import (
    Benchmark,
    convert,
    discover,
    dump,
    import_all,
    to_yaml,
)

# 一份最小但结构完整的 qlib 官方配置（字段名与真实文件一致）
QLIB_CFG = """\
qlib_init:
    provider_uri: "~/.qlib/qlib_data/cn_data"
    region: cn
market: &market csi300
benchmark: &benchmark SH000300
data_handler_config: &data_handler_config
    start_time: 2008-01-01
    end_time: 2020-08-01
    fit_start_time: 2008-01-01
    fit_end_time: 2014-12-31
    instruments: *market
port_analysis_config: &port_analysis_config
    strategy:
        class: TopkDropoutStrategy
        module_path: qlib.contrib.strategy
        kwargs:
            signal: <PRED>
            topk: 50
            n_drop: 5
    backtest:
        start_time: 2017-01-01
        end_time: 2020-08-01
        account: 100000000
        benchmark: *benchmark
        exchange_kwargs:
            limit_threshold: 0.095
            deal_price: close
            open_cost: 0.0005
            close_cost: 0.0015
            min_cost: 5
task:
    model:
        class: LGBModel
        module_path: qlib.contrib.model.gbdt
        kwargs:
            loss: mse
            learning_rate: 0.2
            max_depth: 8
    dataset:
        class: DatasetH
        module_path: qlib.data.dataset
        kwargs:
            handler:
                class: Alpha158
                module_path: qlib.contrib.data.handler
                kwargs: *data_handler_config
            segments:
                train: [2008-01-01, 2014-12-31]
                valid: [2015-01-01, 2016-12-31]
                test: [2017-01-01, 2020-08-01]
"""


def _make_benchmarks(root: Path, files) -> None:
    """files: [(相对路径, 内容)]"""
    for rel, text in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


class TestDiscover(unittest.TestCase):
    def test_slug_and_market_parsing(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _make_benchmarks(root, [
                ("LightGBM/workflow_config_lightgbm_Alpha158.yaml", QLIB_CFG),
                ("CatBoost/workflow_config_catboost_Alpha360_csi500.yaml", QLIB_CFG),
            ])
            bms = discover(root)
        slugs = [b.slug for b in bms]
        self.assertIn("qlib_lightgbm_alpha158", slugs)
        self.assertIn("qlib_catboost_alpha360_csi500", slugs)
        m = [b for b in bms if b.slug.endswith("csi500")][0]
        self.assertEqual(m.market, "csi500")
        self.assertEqual(m.handler, "Alpha360")

    def test_model_name_filled(self):
        """模型类名要在 discover 阶段就填好（列表展示要用）。"""
        with TemporaryDirectory() as td:
            root = Path(td)
            _make_benchmarks(root, [("LightGBM/workflow_config_lightgbm_Alpha158.yaml", QLIB_CFG)])
            bms = discover(root)
        self.assertEqual(bms[0].model, "LGBModel")
        self.assertEqual(bms[0].model_module, "qlib.contrib.model.gbdt")

    def test_missing_dir_returns_empty(self):
        with TemporaryDirectory() as td:
            self.assertEqual(discover(Path(td) / "nope"), [])

    def test_non_matching_filenames_ignored(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _make_benchmarks(root, [
                ("LightGBM/README.md", "x"),
                ("LightGBM/workflow_config_bad.yaml", QLIB_CFG),   # 不含 AlphaNNN
                ("LightGBM/workflow_config_lightgbm_Alpha158.yaml", QLIB_CFG),
            ])
            bms = discover(root)
        self.assertEqual(len(bms), 1)


class TestConvert(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        root = Path(self._td.name)
        _make_benchmarks(root, [("LightGBM/workflow_config_lightgbm_Alpha158.yaml", QLIB_CFG)])
        self.bm = discover(root)[0]

    def tearDown(self):
        self._td.cleanup()

    def _props(self, doc, step_type):
        for s in doc["steps"]:
            if s["type"] == step_type:
                return s.get("props", {})
        return {}

    def test_steps_order(self):
        doc, _ = convert(self.bm, provider_uri="D:/data")
        self.assertEqual([s["type"] for s in doc["steps"]],
                         ["init", "data", "dataset", "model", "strategy", "backtest"])

    def test_init_uses_given_provider_uri(self):
        doc, notes = convert(self.bm, provider_uri="D:/my/data")
        self.assertEqual(self._props(doc, "init")["provider_uri"], "D:/my/data")
        self.assertEqual(self._props(doc, "init")["region"], "cn")
        self.assertTrue(any("provider_uri" in n for n in notes))

    def test_model_hyperparams_preserved(self):
        """官方超参必须一字不差地带过来 —— 这是本模块的核心价值。"""
        doc, _ = convert(self.bm, provider_uri="D:/data")
        p = self._props(doc, "model")
        self.assertEqual(p["model_class"], "LGBModel")
        self.assertEqual(p["module_path"], "qlib.contrib.model.gbdt")
        self.assertEqual(p["model_params"],
                         {"loss": "mse", "learning_rate": 0.2, "max_depth": 8})

    def test_segments_and_handler(self):
        doc, _ = convert(self.bm, provider_uri="D:/data")
        p = self._props(doc, "dataset")
        self.assertEqual(p["handler_class"], "Alpha158")
        self.assertEqual(p["train_start"], "2008-01-01")
        self.assertEqual(p["train_end"], "2014-12-31")
        self.assertEqual(p["valid_start"], "2015-01-01")
        self.assertEqual(p["test_end"], "2020-08-01")
        # data_handler_config 原样透传（含 fit_start/fit_end）
        hk = p["handler_kwargs"]
        self.assertEqual(hk["fit_start_time"], "2008-01-01")
        self.assertEqual(hk["fit_end_time"], "2014-12-31")
        self.assertEqual(hk["instruments"], "csi300")

    def test_strategy_signal_split_out(self):
        doc, _ = convert(self.bm, provider_uri="D:/data")
        p = self._props(doc, "strategy")
        self.assertEqual(p["strategy_class"], "TopkDropoutStrategy")
        self.assertEqual(p["signal"], "<PRED>", "signal 要单独成属性")
        self.assertNotIn("signal", p["strategy_params"], "signal 不应重复留在 params 里")
        self.assertEqual(p["strategy_params"], {"topk": 50, "n_drop": 5})

    def test_backtest_includes_exchange_kwargs(self):
        doc, _ = convert(self.bm, provider_uri="D:/data")
        p = self._props(doc, "backtest")
        self.assertEqual(p["initial_capital"], 100000000)
        self.assertEqual(p["benchmark"], "SH000300")
        self.assertEqual(p["exchange_kwargs"]["open_cost"], 0.0005)
        self.assertEqual(p["exchange_kwargs"]["min_cost"], 5)

    def test_dates_become_strings(self):
        """YAML 会把 2008-01-01 解析成 date 对象，必须转成字符串。"""
        doc, _ = convert(self.bm, provider_uri="D:/data")
        for v in (self._props(doc, "data")["start_time"],
                  self._props(doc, "backtest")["start_time"]):
            self.assertIsInstance(v, str)
            self.assertEqual(v, "2008-01-01" if v.startswith("2008") else "2017-01-01")

    def test_unmapped_top_keys_reported(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _make_benchmarks(root, [("X/workflow_config_x_Alpha158.yaml",
                                     QLIB_CFG + "\nsome_extra_key: 1\n")])
            bm = discover(root)[0]
            _doc, notes = convert(bm, provider_uri="D:/data")
        self.assertTrue(any("some_extra_key" in n for n in notes),
                        "未映射的键要提示，不能静默丢弃：%s" % notes)


class TestYamlOutput(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        root = Path(self._td.name)
        _make_benchmarks(root, [("LightGBM/workflow_config_lightgbm_Alpha158.yaml", QLIB_CFG)])
        self.bm = discover(root)[0]

    def tearDown(self):
        self._td.cleanup()

    def test_no_yaml_anchors(self):
        """共享对象会让 dumper 输出 &id001/*id001，模板要给人看，必须避免。"""
        doc, notes = convert(self.bm, provider_uri="D:/data")
        text = to_yaml(doc, notes)
        self.assertNotIn("&id", text)
        self.assertNotIn("*id", text)

    def test_header_contains_run_hint(self):
        doc, notes = convert(self.bm, provider_uri="D:/data")
        text = to_yaml(doc, notes)
        self.assertIn("python -m pipeline run", text)
        self.assertIn(self.bm.slug, text)

    def test_output_is_loadable_yaml(self):
        import yaml
        doc, notes = convert(self.bm, provider_uri="D:/data")
        obj = yaml.safe_load(to_yaml(doc, notes))
        self.assertEqual(obj["name"], self.bm.slug)
        self.assertEqual(len(obj["steps"]), 6)


class TestImportAll(unittest.TestCase):
    def test_dump_and_skip_existing(self):
        with TemporaryDirectory() as td:
            root, out = Path(td) / "bench", Path(td) / "out"
            _make_benchmarks(root, [("LightGBM/workflow_config_lightgbm_Alpha158.yaml", QLIB_CFG)])
            bm = discover(root)[0]

            p1 = dump(bm, out, provider_uri="D:/data")
            self.assertTrue(p1.exists())
            first = p1.read_text(encoding="utf-8")

            p1.write_text("手工改过", encoding="utf-8")
            dump(bm, out, provider_uri="D:/data")            # 默认不覆盖
            self.assertEqual(p1.read_text(encoding="utf-8"), "手工改过")
            dump(bm, out, provider_uri="D:/data", overwrite=True)
            self.assertNotEqual(p1.read_text(encoding="utf-8"), "手工改过")
            self.assertIn("qlib_lightgbm_alpha158", first)

    def test_import_all_limit(self):
        with TemporaryDirectory() as td:
            root, out = Path(td) / "bench", Path(td) / "out"
            _make_benchmarks(root, [
                ("A/workflow_config_a_Alpha158.yaml", QLIB_CFG),
                ("B/workflow_config_b_Alpha360.yaml", QLIB_CFG),
            ])
            made = import_all(root, out, provider_uri="D:/data", limit=1)
            self.assertEqual(len(made), 1)
            self.assertEqual(len(list(out.glob("*.yaml"))), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
