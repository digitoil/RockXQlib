# -*- coding: utf-8 -*-
"""qlib 研究实验（无 GUI）。

不依赖官方 cn_data。集成测试自己灌一小段行情，再走
``task_train`` → recorder → 重新加载 pred.pkl。
没装 qlib / lightgbm 时集成测试跳过；配置错误和缺数据的用例始终跑，
并且必须抛错，不能返回成功。
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.qlib_file_exp import RockXFileExpManager  # noqa: E402
from core.qlib_research import (  # noqa: E402
    QlibResearchError,
    load_workflow_config,
    run_qlib_experiment,
    validate_workflow_config,
)
from pipeline.cli import build_parser  # noqa: E402

MINIMAL = ROOT / "workflows" / "lgb_close_minimal.yaml"
ALPHA = ROOT / "workflows" / "lgb_alpha158.yaml"
_QLIB = importlib.util.find_spec("qlib") is not None and importlib.util.find_spec("lightgbm") is not None


class FileRecorderTest(unittest.TestCase):
    def test_roundtrip_without_claiming_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            uri = "file:" + tmp
            manager = RockXFileExpManager(uri, "exp")
            exp = manager.start_exp(experiment_name="exp", recorder_name="r1")
            rec = exp.active_recorder
            rec.log_params(model="LGBModel")
            rec.log_metrics(step=0, l2=0.5)
            rec.log_metrics(step=1, l2=0.25)
            rec.save_objects(**{"pred.pkl": {"rows": 3}})
            rec_id = rec.id
            manager.end_exp("FINISHED")

            again = RockXFileExpManager(uri, "exp")
            loaded = again.get_exp(experiment_name="exp", create=False).get_recorder(
                recorder_id=rec_id, create=False)
            self.assertEqual(loaded.load_object("pred.pkl"), {"rows": 3})
            self.assertEqual(loaded.list_metrics()["l2"], 0.25)
            self.assertEqual(loaded.list_params()["model"], "LGBModel")
            self.assertIn("pred.pkl", loaded.list_artifacts())
            with self.assertRaises(Exception):
                loaded.load_object("missing.pkl")


class ConfigTest(unittest.TestCase):
    def test_minimal_yaml_is_a_real_task(self):
        cfg = load_workflow_config(MINIMAL)
        self.assertEqual(cfg["task"]["model"]["class"], "LGBModel")
        self.assertEqual(cfg["task"]["dataset"]["class"], "DatasetH")
        classes = [r["class"] for r in cfg["task"]["record"]]
        self.assertEqual(classes, ["SignalRecord", "SigAnaRecord", "PortAnaRecord"])

    def test_missing_provider_is_an_error(self):
        with self.assertRaises(QlibResearchError) as ctx:
            validate_workflow_config({"task": {"model": {"class": "LGBModel", "module_path": "x"},
                                              "dataset": {"class": "DatasetH", "module_path": "y"},
                                              "record": [{"class": "SignalRecord"}]}})
        self.assertIn("provider_uri", str(ctx.exception))

    def test_directory_that_is_not_qlib_data_fails_before_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "qlib_init": {"provider_uri": tmp},
                "task": {
                    "model": {"class": "LGBModel", "module_path": "qlib.contrib.model.gbdt"},
                    "dataset": {"class": "DatasetH", "module_path": "qlib.data.dataset"},
                    "record": [{"class": "SignalRecord", "module_path": "qlib.workflow.record_temp"}],
                },
            }
            with self.assertRaises(QlibResearchError) as ctx:
                run_qlib_experiment(cfg, uri_folder=os.path.join(tmp, "mlruns"))
            self.assertIn("数据目录不可用", str(ctx.exception))

    def test_signal_record_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("calendars", "features", "instruments"):
                Path(tmp, name).mkdir()
            cfg = {
                "qlib_init": {"provider_uri": tmp},
                "task": {
                    "model": {"class": "LGBModel", "module_path": "qlib.contrib.model.gbdt"},
                    "dataset": {"class": "DatasetH", "module_path": "qlib.data.dataset"},
                },
            }
            with self.assertRaises(QlibResearchError) as ctx:
                validate_workflow_config(cfg)
            self.assertIn("SignalRecord", str(ctx.exception))

    def test_alpha158_config_refuses_missing_cn_data(self):
        provider = os.path.expanduser("~/.qlib/qlib_data/cn_data")
        from core.qlib_paths import is_qlib_data_dir
        if is_qlib_data_dir(provider):
            self.skipTest("本机已有 cn_data，不在单元测试里跑完整 Alpha158")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(QlibResearchError) as ctx:
                run_qlib_experiment(ALPHA, uri_folder=tmp)
            self.assertIn("数据目录不可用", str(ctx.exception))

    def test_cli_exposes_qrun(self):
        args = build_parser().parse_args(
            ["qrun", str(MINIMAL), "--provider-uri", "/tmp/qlib-data"])
        self.assertEqual(args.cmd, "qrun")
        self.assertEqual(args.provider_uri, "/tmp/qlib-data")


@unittest.skipUnless(_QLIB, "需要 pyqlib 与 lightgbm 才跑真实训练")
class TinyQlibExperimentTest(unittest.TestCase):
    def test_train_record_and_backtest(self):
        import numpy as np
        import pandas as pd

        from pipeline.data_import import import_csv

        cfg = load_workflow_config(MINIMAL)
        handler = cfg["task"]["dataset"]["kwargs"]["handler"]["kwargs"]
        start = pd.Timestamp(handler["start_time"]) - pd.offsets.BDay(30)
        end = pd.Timestamp(handler["end_time"])
        dates = pd.bdate_range(start, end)
        symbols = ["600000.SH", "600004.SH", "600005.SH", "600006.SH", "600007.SH", "000300.SH"]
        rng = np.random.default_rng(7)
        rows = []
        for sym in symbols:
            price = 10.0 + float(rng.random())
            for i, day in enumerate(dates):
                shock = float(np.clip(rng.normal(0.0004, 0.008), -0.04, 0.04))
                close = round(price * (1 + shock), 4)
                open_ = round(price * (1 + float(rng.normal(0, 0.001))), 4)
                high = round(max(open_, close) * 1.002, 4)
                low = round(min(open_, close) * 0.998, 4)
                high = max(high, open_, close)
                low = min(low, open_, close)
                rows.append({
                    "date": day.strftime("%Y-%m-%d"),
                    "symbol": sym,
                    "open": open_, "high": high, "low": low, "close": close,
                    "volume": 1_000_000 + i * 100,
                })
                price = close

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "prices.csv"
            pd.DataFrame(rows).to_csv(csv_path, index=False)
            data_dir = tmp_path / "qlib_data"
            imported = import_csv(str(csv_path), str(data_dir), instrument_list="pool")
            self.assertFalse(imported.errors(), imported)
            self.assertTrue((data_dir / "instruments" / "pool.txt").is_file())
            self.assertTrue((data_dir / "features" / "sh000300" / "close.day.bin").is_file())

            summary = run_qlib_experiment(
                MINIMAL,
                provider_uri=str(data_dir),
                uri_folder=tmp_path / "mlruns",
                experiment_name="tiny",
            )
            self.assertEqual(summary["status"], "success")
            pred = summary["prediction"]
            self.assertGreater(pred["rows"], 0)
            self.assertEqual(pred["reloaded_rows"], pred["rows"])
            self.assertGreaterEqual(pred.get("n_instruments") or 0, 2)
            self.assertIn("pred.pkl", summary["artifacts"])
            self.assertTrue(any("report_normal" in name for name in summary["artifacts"]))
            self.assertIn("IC", summary["metrics"])
            self.assertIsInstance(summary["metrics"]["IC"], float)
            summary_path = Path(summary["recorder_dir"]) / "summary.json"
            self.assertTrue(summary_path.is_file())
            # 摘要里的预测行数必须和磁盘上的一致，不能是写死的。
            import json
            on_disk = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["prediction"]["rows"], pred["rows"])
