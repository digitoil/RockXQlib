# -*- coding: utf-8 -*-
"""助手面板的离屏冒烟测试。没装 PySide6 时自动跳过。python -m unittest tests.test_assistant_dock_qt"""
import json
import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from PySide6.QtWidgets import QApplication, QMainWindow
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "需要 PySide6")
class DockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from core.workflow_schema import deserialize_graph
        from pipeline.dryrun import FakeGraph
        from pipeline.runner import prepare
        from pipeline.specs import extract_specs
        from gui.assistant_dock import AssistantDock
        import pipeline.llm as llm

        specs = extract_specs()

        class Win(QMainWindow):
            def __init__(s):
                super().__init__()
                s.graph = FakeGraph(specs)
                s.logs, s.ran = [], 0

            def _specs_for_pipeline(s): return specs
            def log_message(s, m, lvl="INFO"): s.logs.append(m)
            def run_workflow(s): s.ran += 1

        self.win = Win()
        wf, _, _ = prepare({"steps": ["init", "data", "dataset", "model", "strategy", "backtest"]})
        deserialize_graph(wf, self.win.graph)
        self.replies = []
        self._orig = llm.openai_compatible_chat
        llm.openai_compatible_chat = lambda *a, **k: (lambda msgs: self.replies.pop(0))
        self.llm = llm
        self.dock = AssistantDock(self.win)
        self.dock.model.setText("fake")

    def tearDown(self):
        self.llm.openai_compatible_chat = self._orig

    def _wait(self, cond, secs=5):
        end = time.time() + secs
        while time.time() < end and not cond():
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(cond())

    def _model_node(self):
        return next(n for n in self.win.graph.all_nodes() if n.type_ == "qlib.core.model")

    def _proposal_reply(self, cls):
        from core.workflow_schema import serialize_graph
        from pipeline.assistant import slim_workflow
        wf = slim_workflow(serialize_graph(self.win.graph))
        for n in wf["nodes"]:
            if n["type"] == "qlib.core.model":
                n["props"] = {**n["props"], "model_class": cls}
        return json.dumps({"reply": "换好了", "workflow": wf, "run": True})

    def test_propose_apply_undo(self):
        self.replies.append(self._proposal_reply("XGBModel"))
        self.dock.inp.setPlainText("换成 XGB")
        self.dock.send()
        self._wait(lambda: self.dock.pending is not None)
        self.assertEqual(self._model_node().get_property("model_class"), "LGBModel")  # 未确认不改画布
        self.assertTrue(self.dock.apply_btn.isEnabled())
        self.dock.apply(run=False)
        self.assertEqual(self._model_node().get_property("model_class"), "XGBModel")
        self.assertEqual(self.win.ran, 0)
        self.dock.undo()
        self.assertEqual(self._model_node().get_property("model_class"), "LGBModel")

    def test_apply_and_run_then_diagnose(self):
        self.replies.append(self._proposal_reply("XGBModel"))
        self.dock.inp.setPlainText("换并运行")
        self.dock.send()
        self._wait(lambda: self.dock.pending is not None)
        self.dock.apply(run=True)
        self.assertEqual(self.win.ran, 1)
        self.assertFalse(self.dock.diag_btn.isEnabled())   # 还没有运行结果
        self.dock.on_run_finished({"status": "partial", "ok_count": 1, "total": 6,
                                   "records": [{"node": "数据", "ok": False, "detail": "no data"}]})
        self.assertTrue(self.dock.diag_btn.isEnabled())
        self.replies.append(json.dumps({"reply": "数据目录有问题", "workflow": None, "run": False}))
        self.dock.diagnose()
        self._wait(lambda: "数据目录有问题" in self.dock.view.toPlainText())

    def test_llm_failure_is_reported_not_raised(self):
        def boom(msgs): raise ConnectionError("refused")
        self.llm.openai_compatible_chat = lambda *a, **k: boom
        self.dock.inp.setPlainText("hi")
        self.dock.send()
        self._wait(lambda: "调用 LLM 失败" in self.dock.view.toPlainText())
        self.assertTrue(self.dock.send_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
