# -*- coding: utf-8 -*-
"""流水线菜单入口的离屏测试：空白画布不崩溃、任何异常都被接住。
没装 PySide6 时跳过。python -m unittest tests.test_pipeline_panel_qt"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "需要 PySide6")
class PanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from gui.pipeline_panel import PipelineGuiMixin
        from pipeline.dryrun import FakeGraph
        from pipeline.specs import extract_specs
        import pipeline.runner as R
        import pipeline.runs as RU

        self.boxes = []
        self._saved = {n: getattr(QMessageBox, n) for n in
                       ("information", "warning", "critical", "question")}
        for n in self._saved:
            setattr(QMessageBox, n, staticmethod(
                lambda *a, _n=n, **k: (self.boxes.append((_n, a[1:3])), QMessageBox.Yes)[1]))
        self._exec = QDialog.exec
        QDialog.exec = lambda s: QDialog.Rejected

        self.tmp = tempfile.TemporaryDirectory()
        self._dirs = (R.DEFAULT_RUNS_DIR, RU.DEFAULT_RUNS_DIR)
        R.DEFAULT_RUNS_DIR = RU.DEFAULT_RUNS_DIR = Path(self.tmp.name)
        self.R, self.RU = R, RU

        specs = extract_specs()

        class Win(PipelineGuiMixin, QMainWindow):
            def __init__(s):
                super().__init__()
                s.graph = FakeGraph(specs)
                s.logs = []

            def log_message(s, m, lvl="INFO"): s.logs.append((lvl, m))
            def _specs_for_pipeline(s): return specs

        self.win = Win()

    def tearDown(self):
        for n, f in self._saved.items():
            setattr(QMessageBox, n, f)
        QDialog.exec = self._exec
        self.R.DEFAULT_RUNS_DIR, self.RU.DEFAULT_RUNS_DIR = self._dirs
        self.tmp.cleanup()

    def test_blank_canvas_sweep_and_runs_do_not_crash(self):
        self.win.pipeline_sweep()
        self.win.pipeline_show_runs()
        kinds = [k for k, _ in self.boxes]
        self.assertEqual(kinds, ["information", "information"])
        self.assertIn("没有节点", self.boxes[0][1][1])
        self.assertEqual([l for l in self.win.logs if l[0] == "ERROR"], [])

    def test_exception_is_caught_logged_and_shown(self):
        import pipeline.runs as RU
        orig = RU.list_runs
        RU.list_runs = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            self.win.pipeline_show_runs()      # 不应抛出
        finally:
            RU.list_runs = orig
        self.assertEqual(self.boxes[-1][0], "critical")
        self.assertTrue(any("boom" in m for lvl, m in self.win.logs if lvl == "ERROR"))

    def test_shadowed_package_reports_location(self):
        # 模拟 import 失败（同名目录遮蔽）：要给出 pipeline 包的位置而不是闪退
        import builtins
        real = builtins.__import__

        def fake(name, *a, **k):
            if name == "pipeline.runs":
                raise ImportError("cannot import name list_runs")
            return real(name, *a, **k)
        builtins.__import__ = fake
        try:
            self.win.pipeline_show_runs()
        finally:
            builtins.__import__ = real
        kind, (_title, text) = self.boxes[-1]
        self.assertEqual(kind, "critical")
        self.assertIn("pipeline 包位置", text)

    def test_malformed_manifests_listed_safely(self):
        d = Path(self.tmp.name)
        (d / "bad1").mkdir(); (d / "bad1" / "manifest.json").write_text("[1,2]")
        (d / "bad2").mkdir(); (d / "bad2" / "manifest.json").write_text("{not json")
        (d / "ok").mkdir(); (d / "ok" / "manifest.json").write_text(
            '{"status": "success", "elapsed": null, "metrics": {"s": 1.0}}')
        self.win.pipeline_show_runs()
        self.assertEqual(self.boxes, [])          # 有记录，直接开窗口，没有错误提示
        self.assertEqual([l for l in self.win.logs if l[0] == "ERROR"], [])


if __name__ == "__main__":
    unittest.main()
