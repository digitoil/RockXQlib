#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流序列化与校验  (core/workflow_schema.py)

提供「节点图 <-> 简洁 JSON」的双向转换、校验、以及给 LLM 的节点说明书。

================== 为什么不用 NodeGraphQt 自带的 save_session ==================

``graph.save_session(path)`` 能用，但格式是**框架私有**的：
- 含大量 UI 状态（画布缩放、选择状态、视图参数…），人类不可读
- 无法校验（存进去什么都能存，读回来才发现问题）
- 不适合作为 LLM 的输出目标（字段冗余、语义不明）

================== 本模块格式的设计目标 ==================

1. **人类可读** —— 一眼看懂工作流结构
2. **LLM 友好** —— 字段少、语义明确、易生成（第 2 步「LLM 生成工作流」的基础）
3. **可校验** —— 节点类型 / 属性 / 端口 / 环 都能提前发现
4. **稳定引用** —— 用自定义 id（``n1``/``n2``…），**不用** NodeGraphQt 的 hex id
   （``0x24ff7c4b770`` 这种重启后会变，不能做跨会话引用）

================== 格式示例 ==================

```json
{
  "version": "1.0",
  "name": "LGBModel 沪深300",
  "nodes": [
    {"id": "n1", "type": "qlib.core.init", "name": "Qlib初始化",
     "pos": [100, 100],
     "props": {"provider_uri": "E:/.../cn_data", "region": "cn"}},
    {"id": "n2", "type": "qlib.core.data", "name": "Qlib数据获取",
     "pos": [340, 100],
     "props": {"instruments": "csi300", "start_time": "2019-01-01"}}
  ],
  "links": [
    {"from": "n1.initialized_qlib", "to": "n2.initialized_qlib"}
  ]
}
```

``links`` 用 ``"节点id.端口名"`` 的紧凑形式 —— LLM 最容易生成这种结构。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "SCHEMA_VERSION",
    "serialize_graph",
    "deserialize_graph",
    "validate_workflow",
    "collect_specs_from_graph",
    "describe_schema",
    "dump_workflow",
    "load_workflow",
]

SCHEMA_VERSION = "1.0"

# 框架注入的属性，不属于"业务参数"，序列化时跳过
_FRAMEWORK_PROP_KEYS = {"subgraph_session"}


# ==========================================================================
# 序列化：节点图 -> dict
# ==========================================================================
def serialize_graph(graph: Any, name: str = "") -> Dict[str, Any]:
    """把 NodeGraphQt 节点图转成简洁 dict。

    Args:
        graph: ``NodeGraphQt.NodeGraph`` 实例。
        name:  工作流名称（可选）。

    Returns:
        ``{"version", "name", "nodes", "links"}``
    """
    nodes = list(graph.all_nodes() or [])
    if not nodes:
        return {"version": SCHEMA_VERSION, "name": name, "nodes": [], "links": []}

    # ---- 建立「节点对象 -> 稳定 id」映射 ----
    # 用 n1/n2/... 而不是 node.id()：后者是 hex 串且重启会变
    id_of: Dict[int, str] = {}
    for i, node in enumerate(nodes, 1):
        id_of[id(node)] = "n%d" % i

    out_nodes: List[Dict[str, Any]] = []
    for node in nodes:
        out_nodes.append({
            "id": id_of[id(node)],
            "type": _node_type(node),
            "name": _node_name(node),
            "pos": _node_pos(node),
            "props": _node_props(node),
        })

    # ---- 连线：从输出端口出发，找到对端的输入端口 ----
    links: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for node in nodes:
        src_id = id_of[id(node)]
        for port_name, port in (_safe_ports(node.outputs())).items():
            for peer in _connected_ports(port):
                peer_node = _port_node(peer)
                if peer_node is None:
                    continue
                tgt_id = id_of.get(id(peer_node))
                if tgt_id is None:
                    continue  # 连到了图外（不该发生）
                link = {
                    "from": "%s.%s" % (src_id, port_name),
                    "to": "%s.%s" % (tgt_id, _port_name(peer)),
                }
                key = (link["from"], link["to"])
                if key not in seen:
                    seen.add(key)
                    links.append(link)

    return {
        "version": SCHEMA_VERSION,
        "name": name,
        "nodes": out_nodes,
        "links": links,
    }


# ==========================================================================
# 反序列化：dict -> 节点图（重建）
# ==========================================================================
def deserialize_graph(
    data: Dict[str, Any],
    graph: Any,
    *,
    clear: bool = True,
    specs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[bool, List[str]]:
    """把 dict 重建为节点图。

    Args:
        data:   ``serialize_graph`` 产出的结构（或 LLM 生成的同构结构）。
        graph:  目标 ``NodeGraph``。
        clear:  是否先清空现有节点。
        specs:  节点规格（用于校验）；None 时跳过类型/端口校验。

    Returns:
        ``(ok, errors)`` —— 失败时 ``ok=False`` 且 errors 列出具体原因，
        调用方应**不要**把半成品留在画布上。
    """
    ok, errors = validate_workflow(data, specs=specs)
    if not ok:
        return False, errors

    if clear:
        for node in list(graph.all_nodes() or []):
            try:
                graph.remove_node(node)
            except Exception:
                pass

    id_to_node: Dict[str, Any] = {}
    for spec in data.get("nodes", []):
        nid = spec["id"]
        try:
            pos = spec.get("pos") or [0, 0]
            node = graph.create_node(spec["type"], pos=[int(pos[0]), int(pos[1])])
        except Exception as e:
            errors.append("创建节点失败 %s (%s): %s" % (nid, spec.get("type"), e))
            continue

        for k, v in (spec.get("props") or {}).items():
            try:
                node.set_property(k, v)
            except Exception as e:
                errors.append("设置属性失败 %s.%s: %s" % (nid, k, e))

        if spec.get("name"):
            try:
                node.set_name(spec["name"])
            except Exception:
                pass
        id_to_node[nid] = node

    for link in data.get("links", []):
        try:
            src_id, src_port = _split_ref(link["from"])
            tgt_id, tgt_port = _split_ref(link["to"])
            src_node = id_to_node[src_id]
            tgt_node = id_to_node[tgt_id]
            out_ports = _safe_ports(src_node.outputs())
            in_ports = _safe_ports(tgt_node.inputs())
            out_ports[src_port].connect_to(in_ports[tgt_port])
        except Exception as e:
            errors.append("连线失败 %s -> %s: %s"
                          % (link.get("from"), link.get("to"), e))

    # ⚠️ 注意区分「错误」与「警告」：errors 里可能含 `[警告]` 前缀的提示
    # （如孤立节点）。警告不应导致反序列化失败 —— 否则一个孤立的装饰节点
    # 就会让整个导入流程失败。
    real_errors = [e for e in errors if not e.startswith("[警告]")]
    return (not real_errors), errors


# ==========================================================================
# 校验
# ==========================================================================
def validate_workflow(
    data: Any,
    specs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[bool, List[str]]:
    """校验工作流结构。

    只做**结构层面**的检查（不需要真的建图），因此可以：
    - 在落盘前检查
    - 在把 LLM 输出落到画布前检查（这是最重要的用途）

    检查项：
    1. 顶层结构（version/nodes/links 的类型）
    2. 节点 id 唯一、非空
    3. 节点 type 在可用列表内（需要 ``specs``）
    4. props 的 key 合法（需要 ``specs``）
    5. links 引用的节点/端口存在（需要 ``specs``）
    6. 端口方向正确（输出 -> 输入）
    7. 无环
    8. 孤立节点提示（warning 级）
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return False, ["工作流数据必须是 dict（对象），实际是 %s" % type(data).__name__]

    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return False, ["缺少 nodes 字段，或 nodes 为空列表"]

    links = data.get("links")
    if links is None:
        links = []
    if not isinstance(links, list):
        return False, ["links 必须是列表"]

    # ---- 节点 ----
    node_ids: Set[str] = set()
    type_of: Dict[str, str] = {}
    for i, spec in enumerate(nodes):
        where = "nodes[%d]" % i
        if not isinstance(spec, dict):
            errors.append("%s 必须是对象" % where)
            continue
        nid = spec.get("id")
        if not nid or not isinstance(nid, str):
            errors.append("%s 缺少合法的 id" % where)
            continue
        if nid in node_ids:
            errors.append("节点 id 重复: %s" % nid)
            continue
        node_ids.add(nid)

        ntype = spec.get("type")
        if not ntype or not isinstance(ntype, str):
            errors.append("节点 %s 缺少 type" % nid)
            continue
        type_of[nid] = ntype

        if specs is not None:
            if ntype not in specs:
                errors.append("节点 %s 的类型不存在: %s（可用: %s）"
                              % (nid, ntype, ", ".join(sorted(specs)[:8])))
            else:
                allowed = set(specs[ntype].get("props") or [])
                for k in (spec.get("props") or {}):
                    if allowed and k not in allowed:
                        errors.append("节点 %s 的属性不存在: %s（可用: %s）"
                                      % (nid, k, ", ".join(sorted(allowed))))

    # ---- 连线 ----
    in_deg: Dict[str, int] = {nid: 0 for nid in node_ids}
    adj: Dict[str, Set[str]] = {nid: set() for nid in node_ids}
    connected: Set[str] = set()

    for i, link in enumerate(links):
        where = "links[%d]" % i
        if not isinstance(link, dict):
            errors.append("%s 必须是对象" % where)
            continue
        src_ref, tgt_ref = link.get("from"), link.get("to")
        if not src_ref or not tgt_ref:
            errors.append("%s 缺少 from/to" % where)
            continue

        try:
            src_id, src_port = _split_ref(src_ref)
            tgt_id, tgt_port = _split_ref(tgt_ref)
        except ValueError as e:
            errors.append("%s 引用格式错误（应为 '节点id.端口名'）: %s" % (where, e))
            continue

        if src_id not in node_ids:
            errors.append("%s 引用了不存在的节点: %s" % (where, src_id))
            continue
        if tgt_id not in node_ids:
            errors.append("%s 引用了不存在的节点: %s" % (where, tgt_id))
            continue

        if specs is not None and src_id in type_of and tgt_id in type_of:
            src_out = set(specs.get(type_of[src_id], {}).get("outputs") or [])
            tgt_in = set(specs.get(type_of[tgt_id], {}).get("inputs") or [])
            if src_out and src_port not in src_out:
                errors.append("%s 源端口不存在: %s.%s（可用: %s）"
                              % (where, type_of[src_id], src_port,
                                 ", ".join(sorted(src_out))))
            if tgt_in and tgt_port not in tgt_in:
                errors.append("%s 目标端口不存在: %s.%s（可用: %s）"
                              % (where, type_of[tgt_id], tgt_port,
                                 ", ".join(sorted(tgt_in))))

        connected.add(src_id)
        connected.add(tgt_id)
        if src_id != tgt_id:
            adj[src_id].add(tgt_id)
            in_deg[tgt_id] = in_deg.get(tgt_id, 0) + 1

    # ---- 环检测（Kahn）----
    if len(node_ids) > 1:
        queue = [n for n in node_ids if in_deg.get(n, 0) == 0]
        visited = 0
        deg = dict(in_deg)
        while queue:
            cur = queue.pop()
            visited += 1
            for nxt in adj.get(cur, ()):
                deg[nxt] -= 1
                if deg[nxt] == 0:
                    queue.append(nxt)
        if visited < len(node_ids):
            stuck = sorted(n for n in node_ids if deg.get(n, 0) > 0)
            errors.append("工作流存在环（无法确定执行顺序），涉及节点: %s"
                          % ", ".join(stuck))

    # ---- 孤立节点（warning，不阻断）----
    if len(node_ids) > 1:
        isolated = sorted(n for n in node_ids if n not in connected)
        if isolated:
            errors.append("[警告] 以下节点没有任何连线，运行时会被跳过: %s"
                          % ", ".join(isolated))

    real_errors = [e for e in errors if not e.startswith("[警告]")]
    return (not real_errors), errors


# ==========================================================================
# 节点规格收集（供校验与 LLM 说明书使用）
# ==========================================================================
def collect_specs_from_graph(graph: Any) -> Dict[str, Dict[str, Any]]:
    """从已注册的节点类收集「类型 -> {inputs, outputs, props, name}」。

    端口与属性都定义在 ``__init__`` 里（add_input/add_output/add_*_input），
    类对象上读不到，因此需要**实例化一个临时节点**。为控制开销，
    每个类型只实例化一次并缓存。

    注意：不要把它放进热路径（如每帧调用）—— 实例化节点有成本。
    """
    specs: Dict[str, Dict[str, Any]] = {}
    try:
        types = list(graph.registered_nodes() or [])
    except Exception:
        return specs

    for t in types:
        # 跳过框架内置的装饰节点（BackdropNode 等）—— 它们不参与工作流，
        # 混进规格表只会干扰校验和 LLM 说明书。
        if t.startswith("nodeGraphQt."):
            continue
        try:
            node = graph.create_node(t, pos=[0, 0])
        except Exception as e:
            logger.debug("收集规格时创建节点失败 %s: %s", t, e)
            continue
        try:
            specs[t] = {
                "name": _node_name(node),
                "inputs": sorted(_safe_ports(node.inputs()).keys()),
                "outputs": sorted(_safe_ports(node.outputs()).keys()),
                "props": sorted(_node_props(node).keys()),
            }
        finally:
            try:
                graph.remove_node(node)
            except Exception:
                pass
    return specs


def describe_schema(specs: Optional[Dict[str, Dict[str, Any]]] = None,
                    *, as_json: bool = False) -> str:
    """生成给 LLM 的节点说明书。

    Args:
        specs:    ``collect_specs_from_graph`` 的结果。为 None 时用内置兜底表。
        as_json:  True 返回 JSON 文本（适合放进 prompt），
                  False 返回人类可读的分段文本。
    """
    table = specs if specs else _FALLBACK_SPECS

    if as_json:
        return json.dumps(table, ensure_ascii=False, indent=2)

    lines: List[str] = []
    lines.append("可用的节点类型（type）、端口与属性：")
    lines.append("")
    for t in sorted(table):
        info = table[t]
        lines.append("- %s  （%s）" % (t, info.get("name") or ""))
        if info.get("inputs"):
            lines.append("    输入端口: %s" % ", ".join(info["inputs"]))
        if info.get("outputs"):
            lines.append("    输出端口: %s" % ", ".join(info["outputs"]))
        if info.get("props"):
            lines.append("    属性: %s" % ", ".join(info["props"]))
        lines.append("")
    lines.append("连线格式：{\"from\": \"节点id.输出端口\", \"to\": \"节点id.输入端口\"}")
    return "\n".join(lines)


# ==========================================================================
# 文件读写
# ==========================================================================
def dump_workflow(data: Dict[str, Any], path: str) -> None:
    """把工作流写到 JSON 文件（UTF-8，不转义中文）。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_workflow(path: str) -> Dict[str, Any]:
    """从 JSON 文件读取工作流。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==========================================================================
# 内部工具（NodeGraphQt 的接口比较啰嗦，统一收口到这里）
# ==========================================================================
def _safe_ports(ports: Any) -> Dict[str, Any]:
    """NodeGraphQt 在「该方向没有端口」时返回 None，不是空 dict。"""
    return ports or {}


def _node_type(node: Any) -> str:
    try:
        return node.type_()
    except TypeError:
        return node.type_


def _node_name(node: Any) -> str:
    try:
        return node.name()
    except TypeError:
        return node.name


def _node_pos(node: Any) -> List[int]:
    try:
        p = node.pos()
        return [int(p[0]), int(p[1])]
    except Exception:
        return [0, 0]


def _node_props(node: Any) -> Dict[str, Any]:
    """读取节点的业务属性。

    NodeGraphQt 把自定义属性存在 ``model.to_dict[node.id]['custom']`` 里，
    读取用 ``node.get_property(name)``（属性编辑器用的就是这条路径）。
    """
    props: Dict[str, Any] = {}
    try:
        raw = node.model.to_dict.get(node.id, {}).get("custom", {}) or {}
    except Exception:
        return props

    for k in raw:
        if k in _FRAMEWORK_PROP_KEYS:
            continue
        try:
            props[k] = node.get_property(k)
        except Exception:
            pass
    return props


def _connected_ports(port: Any) -> List[Any]:
    try:
        return list(port.connected_ports() or [])
    except Exception:
        return []


def _port_node(port: Any) -> Any:
    try:
        return port.node()
    except Exception:
        return None


def _port_name(port: Any) -> str:
    try:
        return port.name()
    except TypeError:
        return port.name


def _split_ref(ref: str) -> Tuple[str, str]:
    """把 ``"n1.initialized_qlib"`` 拆成 ``("n1", "initialized_qlib")``。

    用 rsplit 而非 split —— 节点 id 不含点，但端口名理论上可能含。
    """
    if not isinstance(ref, str) or "." not in ref:
        raise ValueError("引用 %r 格式错误，应为 '节点id.端口名'" % (ref,))
    node_id, port = ref.rsplit(".", 1)
    if not node_id or not port:
        raise ValueError("引用 %r 格式错误，应为 '节点id.端口名'" % (ref,))
    return node_id, port


# 兜底规格表：仅当调用方没提供 specs 时用于 describe_schema 的展示。
# 真正的校验请用 collect_specs_from_graph() 从实际节点类收集，避免过时。
_FALLBACK_SPECS: Dict[str, Dict[str, Any]] = {
    "qlib.core.init": {
        "name": "Qlib初始化",
        "inputs": [],
        "outputs": ["initialized_qlib"],
        "props": ["provider_uri", "region", "enable_exp_recorder"],
    },
    "qlib.core.data": {
        "name": "Qlib数据获取",
        "inputs": ["initialized_qlib"],
        "outputs": ["qlib_data"],
        "props": ["instruments", "start_time", "end_time", "fields"],
    },
    "qlib.core.dataset": {
        "name": "Qlib数据集",
        "inputs": ["qlib_data"],
        "outputs": ["dataset"],
        "props": ["handler_class", "instruments", "train_start", "train_end",
                  "valid_start", "valid_end", "test_start", "test_end"],
    },
    "qlib.core.model": {
        "name": "Qlib模型",
        "inputs": ["dataset"],
        "outputs": ["model", "predictions"],
        "props": ["model_class", "model_params"],
    },
    "qlib.core.strategy": {
        "name": "Qlib策略",
        "inputs": ["predictions"],
        "outputs": ["strategy", "signals"],
        "props": ["strategy_class", "module_path", "signal",
                  "strategy_params", "strategy_kwargs"],
    },
    "qlib.core.backtest": {
        "name": "Qlib回测",
        "inputs": ["strategy"],
        "outputs": ["backtest_results"],
        "props": ["start_time", "end_time", "initial_capital",
                  "benchmark", "strategy_config"],
    },
}
