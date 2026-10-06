# -*- coding: utf-8 -*-
"""无 Qt 的演练后端：用同一套 ``deserialize_graph`` + ``NodeGraphWorkflowRunner`` 走完流水线。

用途：CI / 无 qlib 环境下验证「接线、拓扑顺序、端口数据流、属性合法性」。
不产生任何行情或绩效数据 —— 演练节点只检查上游数据到位并往下游放一个标记，
绝不伪造指标（项目原则：宁可失败也不造假）。

也可以通过 ``executors`` 注入真实/测试逻辑::

    FakeGraph(specs, executors={"qlib.core.model": lambda node, inputs: {...}})
"""
from __future__ import annotations

import itertools
from typing import Any, Callable, Dict, List, Optional

_ids = itertools.count(1)


class FakePort:
    def __init__(self, node: "FakeNode", name: str, kind: str):
        self._node, self._name, self._kind = node, name, kind
        self._peers: List["FakePort"] = []
        self.data: Any = None

    def name(self): return self._name
    def type_(self): return self._kind
    def node(self): return self._node
    def connected_ports(self): return list(self._peers)

    def connect_to(self, other: "FakePort"):
        if self._kind == other._kind:
            raise ValueError("端口方向相同，无法连接")
        self._peers.append(other)
        other._peers.append(self)


class _Model:
    def __init__(self): self.to_dict: Dict[str, Dict[str, Any]] = {}


class FakeNode:
    def __init__(self, spec: Dict[str, Any], type_id: str,
                 executor: Optional[Callable] = None):
        self.type_ = type_id
        self.id = "fake%d" % next(_ids)
        self._name = spec.get("name", type_id)
        self._pos = [0, 0]
        self._executor = executor
        self._in = {p: FakePort(self, p, "in") for p in spec.get("inputs", [])}
        self._out = {p: FakePort(self, p, "out") for p in spec.get("outputs", [])}
        self.model = _Model()
        self.model.to_dict[self.id] = {"custom": dict(spec.get("defaults", {}))}
        self._result: Optional[Dict[str, Any]] = None

    def name(self): return self._name
    def set_name(self, n): self._name = n
    def pos(self): return self._pos
    def inputs(self): return self._in or None
    def outputs(self): return self._out or None
    def set_property(self, k, v): self.model.to_dict[self.id]["custom"][k] = v
    def get_property(self, k): return self.model.to_dict[self.id]["custom"][k]
    def get_execution_result(self): return self._result

    def execute(self) -> bool:
        inputs = {}
        for name, port in self._in.items():
            ups = port.connected_ports()
            if not ups:
                self._result = {"status": "failed",
                                "error": "输入端口 %s 没有连线" % name}
                return False
            if ups[0].data is None:
                self._result = {"status": "failed",
                                "error": "上游没有给 %s 提供数据" % name}
                return False
            inputs[name] = ups[0].data
        props = dict(self.model.to_dict[self.id]["custom"])
        if self._executor:
            outs = self._executor(self, inputs) or {}
        else:
            outs = {p: {"dry_run": True, "from": self._name} for p in self._out}
        for p, v in outs.items():
            if p in self._out:
                self._out[p].data = v
        self._result = {"status": "success", "dry_run": self._executor is None,
                        "props": props}
        return True


class FakeGraph:
    """实现 ``deserialize_graph`` / ``collect_specs_from_graph`` 用到的那部分 NodeGraph 接口。"""

    def __init__(self, specs: Dict[str, Dict[str, Any]],
                 executors: Optional[Dict[str, Callable]] = None):
        self._specs = specs
        self._executors = executors or {}
        self._nodes: List[FakeNode] = []

    def registered_nodes(self): return list(self._specs)
    def all_nodes(self): return list(self._nodes)

    def create_node(self, type_id, pos=None):
        if type_id not in self._specs:
            raise KeyError("未注册的节点类型: %s" % type_id)
        n = FakeNode(self._specs[type_id], type_id, self._executors.get(type_id))
        if pos:
            n._pos = list(pos)
        self._nodes.append(n)
        return n

    def remove_node(self, node):
        self._nodes.remove(node)
