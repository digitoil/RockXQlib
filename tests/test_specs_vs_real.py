# -*- coding: utf-8 -*-
"""AST 静态规格必须与真实节点类（NodeGraphQt 实例化）一致，防止两边漂移。
没有 PySide6 / NodeGraphQt 时跳过。python -m unittest tests.test_specs_vs_real"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import PySide6.QtWidgets  # noqa: F401
    import NodeGraphQt  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "需要 PySide6 与 NodeGraphQt")
class SpecsVsReal(unittest.TestCase):
    def test_core_specs_match(self):
        from pipeline.backends import make_graph
        from pipeline.specs import extract_specs
        _graph, real = make_graph("qt")
        for t, a in extract_specs().items():
            self.assertIn(t, real, t)
            for k in ("inputs", "outputs", "props"):
                self.assertEqual(real[t][k], a[k], "%s.%s" % (t, k))


if __name__ == "__main__":
    unittest.main()
