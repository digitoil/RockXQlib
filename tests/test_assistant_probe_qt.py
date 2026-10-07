# -*- coding: utf-8 -*-
"""助手面板「检测」按钮的离屏测试。

不真连网络：把 ``pipeline.llm_probe.diagnose`` 换成固定返回值。
（``AssistantDock._probe_worker`` 是**在函数内**导入 diagnose 的，
所以打补丁能生效。）
"""
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


def _fake_result(ok=True, reachable=True, models=("qwen3.5:9b",), error="",
                 base_url="http://localhost:11434/v1"):
    from pipeline.llm_probe import ProbeResult
    return ProbeResult(base_url=base_url, ok=ok, reachable=reachable,
                       protocol="openai" if ok else "",
                       models=list(models), error=error,
                       hints=[] if ok else ["启动服务：`ollama serve`"])


@unittest.skipUnless(HAVE_QT, "需要 PySide6")
class CheckLlmTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from pipeline.dryrun import FakeGraph
        from pipeline.specs import extract_specs
        from gui.assistant_dock import AssistantDock
        import pipeline.llm_probe as lp

        specs = extract_specs()

        class Win(QMainWindow):
            def __init__(s):
                super().__init__()
                s.graph = FakeGraph(specs)
                s.logs = []

            def _specs_for_pipeline(s): return specs
            def log_message(s, m, lvl="INFO"): s.logs.append(m)
            def run_workflow(s): pass

        self.win = Win()
        self.lp = lp
        self._orig = lp.diagnose
        self.dock = AssistantDock(self.win)

    def tearDown(self):
        self.lp.diagnose = self._orig

    def _patch(self, primary, all_results=None):
        self.lp.diagnose = lambda *a, **k: (primary, all_results or [primary])

    def _wait(self, cond, secs=8):
        end = time.time() + secs
        while time.time() < end:
            self.app.processEvents()
            if cond():
                return True
            time.sleep(0.02)
        return False

    # ---- 用例 ----

    def test_ok_autofills_model_and_shows_report(self):
        self._patch(_fake_result(ok=True, models=["qwen3.5:9b", "deepseek-r1:8b"]))
        self.dock.model.clear()
        self.dock.check_llm()
        self.assertTrue(self._wait(lambda: self.dock.model.text() == "qwen3.5:9b"),
                        "可用时应自动填入第一个模型")
        text = self.dock.view.toPlainText()
        self.assertIn("LLM 端点检测", text)
        self.assertIn("qwen3.5:9b", text)
        self.assertIn("已自动填入模型", self.dock.status.text())

    def test_ok_keeps_user_typed_model(self):
        """用户已填模型时不应被覆盖。"""
        self._patch(_fake_result(ok=True, models=["qwen3.5:9b"]))
        self.dock.model.setText("my-model")
        self.dock.check_llm()
        self._wait(lambda: "端点可用" in self.dock.status.text()
                   or "已自动填入" in self.dock.status.text())
        self.assertEqual(self.dock.model.text(), "my-model")
        self.assertIn("端点可用", self.dock.status.text())

    def test_unavailable_does_not_autofill(self):
        self._patch(_fake_result(ok=False, reachable=False, models=[],
                                 error="连接被拒绝：服务未启动或端口不对"))
        self.dock.model.clear()
        self.dock.check_llm()
        self._wait(lambda: "不可用" in self.dock.status.text())
        self.assertEqual(self.dock.model.text(), "", "不可用时不填模型")
        text = self.dock.view.toPlainText()
        self.assertIn("连接被拒绝", text)
        self.assertIn("ollama serve", text, "应带上可操作建议")

    def test_empty_model_triggers_probe(self):
        """模型名为空时点发送：应自动触发检测并返回 False，而不是只弹一句提示。"""
        calls = []

        def spy(base_url=None, api_key="", timeout=4.0, models_dir=None):
            calls.append(base_url)
            r = _fake_result(ok=True, models=["m1"])
            return r, [r]

        self.lp.diagnose = spy
        self.dock.model.clear()
        ok = self.dock._ensure_assistant()
        self.assertFalse(ok, "模型为空时不应继续调用 LLM")
        self.assertTrue(self._wait(lambda: bool(calls)), "应触发一次探测")

    def test_failure_message_mentions_check_button(self):
        self.dock._on_failed("ConnectionError: refused")
        self.assertIn("检测", self.dock.view.toPlainText())

    def test_probe_worker_shape(self):
        """工作函数应返回 (ProbeResult, 文本)，且不依赖 Qt。"""
        self._patch(_fake_result(ok=True, models=["m1", "m2"]))
        primary, report = self.dock._probe_worker("http://x/v1", "")
        self.assertEqual(primary.models, ["m1", "m2"])
        self.assertIn("LLM 端点检测", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
