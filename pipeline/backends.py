# -*- coding: utf-8 -*-
"""图后端：把工作流 dict 落成「可被 NodeGraphWorkflowRunner 执行的节点图」。

- ``dry``：FakeGraph，无需 Qt / qlib，用于 CI 与接线验证
- ``qt`` ：真实 NodeGraphQt（offscreen，无需显示器），执行真实 qlib 节点
"""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from .specs import extract_specs


def make_graph(backend: str) -> Tuple[Any, Dict[str, Dict[str, Any]]]:
    """返回 ``(graph, specs)``。"""
    if backend == "dry":
        from .dryrun import FakeGraph
        specs = extract_specs()
        return FakeGraph(specs), specs
    if backend == "qt":
        return _make_qt_graph()
    raise ValueError("未知后端 %r（可选: dry / qt）" % backend)


def _make_qt_graph() -> Tuple[Any, Dict[str, Dict[str, Any]]]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from NodeGraphQt import NodeGraph
    except ImportError as e:
        raise RuntimeError(
            "qt 后端需要 PySide6 与 NodeGraphQt（%s）。"
            "只想验证接线请加 --backend dry。" % e)
    from core.unified_node_manager import UnifiedNodeManager

    QApplication.instance() or QApplication([])
    graph = NodeGraph()
    mgr = UnifiedNodeManager()
    for _ident, cls in mgr.registry.get_all_nodes().items():
        graph.register_node(cls)
    # 规格取自真实节点类，保证校验与实际一致
    from core.workflow_schema import collect_specs_from_graph
    return graph, collect_specs_from_graph(graph)
