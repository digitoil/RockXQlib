# -*- coding: utf-8 -*-
"""流水线层测试（无需 Qt / qlib）。运行: python -m unittest tests.test_pipeline -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.workflow_schema import validate_workflow  # noqa: E402
from pipeline.definition import compile_pipeline, parse_overrides  # noqa: E402
from pipeline.dryrun import FakeGraph  # noqa: E402
from pipeline.llm import extract_json, generate_pipeline  # noqa: E402
from pipeline.runner import prepare, record_run, run_pipeline  # noqa: E402
from pipeline.runs import find_run, list_runs  # noqa: E402
from pipeline.specs import extract_specs  # noqa: E402
from pipeline.sweep import expand, parse_grid, run_sweep  # noqa: E402

TEMPLATE = ROOT / "pipelines" / "lgb_alpha158.yaml"
CHAIN = {"name": "t", "params": {"u": "csi300"},
         "steps": ["init", {"type": "data", "props": {"instruments": "${u}"}},
                   "dataset", {"type": "model", "props": {"model_params": {"a": 1}}},
                   "strategy", "backtest"]}


class SpecsTest(unittest.TestCase):
    def test_core_nodes_extracted(self):
        s = extract_specs()
        self.assertEqual(len(s), 7)
        self.assertEqual(s["qlib.core.model"]["outputs"], ["model", "predictions"])
        self.assertIn("model_class", s["qlib.core.model"]["props"])


class CompileTest(unittest.TestCase):
    def test_chain_autowires_by_port_name(self):
        wf, errs = compile_pipeline(CHAIN)
        self.assertEqual(errs, [])
        links = {(l["from"], l["to"]) for l in wf["links"]}
        self.assertEqual(links, {
            ("n1.initialized_qlib", "n2.initialized_qlib"),
            ("n2.qlib_data", "n3.qlib_data"),
            ("n3.dataset", "n4.dataset"),
            ("n4.predictions", "n5.predictions"),
            ("n5.strategy", "n6.strategy")})
        ok, _ = validate_workflow(wf, specs=extract_specs())
        self.assertTrue(ok)

    def test_params_and_json_props(self):
        wf, _ = compile_pipeline(CHAIN, overrides={"u": "csi500"})
        self.assertEqual(wf["nodes"][1]["props"]["instruments"], "csi500")
        self.assertEqual(json.loads(wf["nodes"][3]["props"]["model_params"]), {"a": 1})

    def test_node_override_and_errors(self):
        wf, errs = compile_pipeline(CHAIN, overrides={"n3.train_end": "2014-06-30"})
        self.assertEqual(errs, [])
        self.assertEqual(wf["nodes"][2]["props"]["train_end"], "2014-06-30")
        _, errs = compile_pipeline(CHAIN, overrides={"nope": 1})
        self.assertTrue(errs)
        _, errs = compile_pipeline(CHAIN, overrides={"n99.x": 1})
        self.assertTrue(errs)
        bad = {"steps": [{"type": "data", "props": {"instruments": "${missing}"}}]}
        self.assertTrue(compile_pipeline(bad)[1])

    def test_unknown_prop_rejected_by_prepare(self):
        doc = {"steps": ["init", {"type": "data", "props": {"bogus": 1}}]}
        _, errs, _ = prepare(doc)
        self.assertTrue(any("bogus" in e for e in errs))

    def test_template_valid(self):
        wf, errs, warns = prepare(str(TEMPLATE))
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])
        self.assertEqual(len(wf["nodes"]), 6)

    def test_parse_overrides(self):
        self.assertEqual(parse_overrides(["a=1", "b=x", "c=[1,2]"]),
                         {"a": 1, "b": "x", "c": [1, 2]})


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runs = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_artifacts(self):
        rec = run_pipeline(str(TEMPLATE), backend="dry", runs_dir=self.runs)
        self.assertEqual(rec["status"], "success")
        d = Path(rec["run_dir"])
        for f in ("workflow.json", "manifest.json", "run.log"):
            self.assertTrue((d / f).exists(), f)
        self.assertFalse((d / "metrics.json").exists(), "演练不得伪造指标")
        self.assertEqual(find_run("latest", self.runs)["run_id"], rec["run_id"])

    def test_invalid_pipeline_recorded_not_executed(self):
        rec = run_pipeline({"steps": ["init", {"type": "nope"}]}, backend="dry",
                           runs_dir=self.runs)
        self.assertEqual(rec["status"], "invalid")

    def test_data_flow_failure_surfaces(self):
        # 模型节点不产出 predictions -> 策略节点必须失败，而不是静默通过
        specs = extract_specs()
        g = FakeGraph(specs, executors={"qlib.core.model": lambda n, i: {"model": 1}})
        rec = run_pipeline(CHAIN, backend="dry", runs_dir=self.runs,
                           graph_and_specs=(g, specs))
        self.assertEqual(rec["status"], "partial")
        failed = [r for r in rec["records"] if not r["ok"]]
        self.assertTrue(failed)

    def test_metrics_persisted_when_present(self):
        # record_run 是 GUI 与 CLI 共用的落盘路径
        wf, _, _ = prepare(CHAIN)
        d = record_run(wf, {"status": "success", "elapsed": 1.0, "ok_count": 6, "total": 6,
                            "metrics": {"sharpe": 1.5}}, runs_dir=self.runs)
        self.assertEqual(json.loads((d / "metrics.json").read_text())["sharpe"], 1.5)
        self.assertEqual(len(list_runs(self.runs)), 1)

    def test_sweep(self):
        grid = parse_grid(["u=csi300,csi500", "n3.train_start=2008-01-01,2010-01-01"])
        self.assertEqual(len(expand(grid)), 4)
        res = run_sweep(CHAIN, grid, backend="dry", runs_dir=self.runs)
        self.assertEqual(len(res), 4)
        self.assertTrue(all(r["status"] == "success" for r in res))
        self.assertEqual(len({r["config_hash"] for r in res}), 4)
        self.assertTrue(list(self.runs.glob("sweep_*.csv")))


class LlmTest(unittest.TestCase):
    GOOD = json.dumps({"name": "g", "steps": ["init", "data", "dataset", "model",
                                               "strategy", "backtest"]})

    def test_extract_json_fenced(self):
        self.assertEqual(extract_json("好的\n```json\n{\"a\": 1}\n```"), {"a": 1})
        with self.assertRaises(ValueError):
            extract_json("没有json")

    def test_repair_loop(self):
        replies = iter(["不是json", json.dumps({"steps": [{"type": "zzz"}]}), self.GOOD])
        seen = []

        def chat(msgs):
            seen.append(msgs[-1]["content"])
            return next(replies)
        doc, trail = generate_pipeline("x", chat)
        self.assertIsNotNone(doc)
        self.assertEqual(len(trail), 3)
        self.assertIn("未通过校验", seen[1])  # 错误被喂回给模型

    def test_gives_up_without_draft(self):
        doc, trail = generate_pipeline("x", lambda m: "胡说", max_rounds=2)
        self.assertIsNone(doc)
        self.assertEqual(len(trail), 2)


if __name__ == "__main__":
    unittest.main()


class CompareTest(unittest.TestCase):
    def test_diff_and_best(self):
        from pipeline.runs import best_of, compare_text, diff_props
        with tempfile.TemporaryDirectory() as t:
            runs = []
            for end, sharpe, dd in (("2008-01-01", 1.0, -0.30), ("2010-01-01", 1.4, -0.20)):
                wf, _, _ = prepare(CHAIN, {"n3.train_start": end})
                d = record_run(wf, {"status": "success", "elapsed": 1,
                                    "metrics": {"sharpe": sharpe, "max_drawdown": dd}},
                               runs_dir=Path(t), tag=end[:4])
                runs.append(json.loads((d / "manifest.json").read_text()) | {"run_dir": str(d)})
            self.assertEqual([x["key"] for x in diff_props(runs)], ["n3.train_start"])
            self.assertEqual(best_of(runs), {"sharpe": 1, "max_drawdown": 1})
            self.assertIn("n3.train_start", compare_text(runs))


class LintTest(unittest.TestCase):
    def _errs(self, overrides):
        _, errs, warns = prepare(CHAIN, overrides)
        return errs, warns

    def test_clean_defaults(self):
        errs, _ = self._errs({})
        self.assertEqual(errs, [])

    def test_bad_json_and_date(self):
        errs, _ = self._errs({"n4.model_params": "{oops"})
        self.assertTrue(any("JSON" in e for e in errs))
        errs, _ = self._errs({"n3.train_end": "2015/12/31"})
        self.assertTrue(any("YYYY-MM-DD" in e for e in errs))

    def test_segment_overlap_is_leak(self):
        errs, _ = self._errs({"n3.train_end": "2016-06-30"})  # 与 valid_start 2015 重叠
        self.assertTrue(any("前视泄漏" in e for e in errs))

    def test_reversed_range(self):
        errs, _ = self._errs({"n6.start_time": "2021-01-01", "n6.end_time": "2020-01-01"})
        self.assertTrue(any("晚于" in e for e in errs))

    def test_backtest_outside_test_and_benchmark_warn(self):
        _, warns = self._errs({"n6.start_time": "2010-01-01", "n6.benchmark": "SH000905"})
        self.assertTrue(any("早于测试集" in w for w in warns))
        self.assertTrue(any("基准" in w for w in warns))
