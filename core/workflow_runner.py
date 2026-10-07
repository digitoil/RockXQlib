#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RockXQlib 节点图工作流执行器（面向 NodeGraphQt 真实端口数据流）。

## 为什么需要这个模块

项目里原本有两个"工作流引擎"，各管一段，但都没真正接上 GUI：

1. ``core/workflow_engine.py`` 里的 ``RockXQlibWorkflowEngine``
   —— 设计完整（networkx 依赖图、串行/并行/流水线/自适应四种模式），
   但它假定的节点契约是::

       outputs = node.execute(inputs)      # 传入 inputs 字典，返回 outputs

   而**真实节点的契约是**::

       ok = node.execute()                 # 无参；数据通过真实端口流动
       value = node.get_input('port_name') # 从上游 output port 的 .data 取
       node.set_output('port_name', value) # 写到自己的 output port

   两者不兼容 —— 直接调 ``execute(inputs)`` 会
   ``TypeError: execute() takes 1 positional argument but 2 were given``。
   所以那个引擎从未真正跑起来过。
   ⚠️ 该文件已于 2026-10-07 作为死代码删除（零引用）；
   保留这段说明是为了让后人知道**为什么**不能回头用"两套引擎"的思路。

2. ``launch_gui_complete_integration.py`` 里的 ``WorkflowExecutionThread``
   —— 能跑真实节点，但顺序靠硬编码的 ``node.id == 'qlib_init'`` 判断
   （NodeGraphQt 的 id 是 ``'0x24ff7c4b770'`` 这种十六进制串，永远匹配不上），
   且 ``node_timeout=60s`` / ``max_execution_time=300s`` 对真实量化任务太短
   （单个 Alpha158 处理器节点就要 127 秒）。

本模块补齐这一层：**按真实端口连线做拓扑排序 + 用正确的节点契约执行**。

## 执行契约

- 数据流由真实端口连线承载，执行顺序必须与连线一致
- ``node.execute()`` 无参，返回 ``bool``
- 结果通过 ``node.get_execution_result()`` 取回
- 只在**节点之间**做协作式取消（Python 无法安全中断正在执行的节点）

超时是"卡死兜底"而非正常限制，默认单节点 1 小时、整体 8 小时。
"""

from __future__ import annotations

import contextlib
import inspect
import io
import logging
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "topological_sort_nodes",
    "NodeGraphWorkflowRunner",
    "collect_inputs_from_ports",
    "publish_outputs_to_ports",
    "DEFAULT_NODE_TIMEOUT",
    "DEFAULT_TOTAL_TIMEOUT",
]

# 只作为卡死兜底；正常量化任务不应被这些数字限制
DEFAULT_NODE_TIMEOUT: float = 3600.0
DEFAULT_TOTAL_TIMEOUT: float = 8 * 3600.0


# --------------------------------------------------------------------------
# 节点信息读取（NodeGraphQt 的 name 是方法、type_ 是类属性，需兼容）
# --------------------------------------------------------------------------

def node_label(node: Any) -> str:
    """取节点显示名。"""
    try:
        name = getattr(node, "name", None)
        if callable(name):
            return str(name())
        if name:
            return str(name)
    except Exception:
        pass
    return getattr(node, "NODE_NAME", None) or node.__class__.__name__


def node_type_id(node: Any) -> str:
    """取节点类型标识（用于展示与分类）。"""
    for attr in ("type_", "__identifier__"):
        val = getattr(node, attr, None)
        if isinstance(val, str) and val:
            return val
    return node.__class__.__name__


class _Tee(io.TextIOBase):
    """边转发边记录节点的 print 输出。

    真实节点失败时常只 ``print("❌ …原因")`` 然后 ``return False``，
    执行结果里没有原因。记录下来，运行汇总里才有可供人和 LLM 诊断的信息。
    """

    def __init__(self, real: Any) -> None:
        self.real = real
        self.lines: List[str] = []

    def write(self, text: str) -> int:
        try:
            self.real.write(text)
        except Exception:
            pass
        self.lines.extend(t for t in text.splitlines() if t.strip())
        return len(text)

    def flush(self) -> None:
        try:
            self.real.flush()
        except Exception:
            pass

    def failure_hint(self, limit: int = 3) -> str:
        keys = ("❌", "失败", "错误", "Error", "不可用", "未初始化", "不存在")
        hits = [l.strip() for l in self.lines if any(k in l for k in keys)]
        return " | ".join(hits[-limit:])


def _is_output_port(port: Any) -> bool:
    """判断端口是否为输出端口。

    ⚠️ 实测 NodeGraphQt 的 ``port.type_()`` 返回的是 **``'out'`` / ``'in'``**
    （见 ``PortTypeEnum.OUT = 'out'``、``PortTypeEnum.IN = 'in'``），
    并不是 ``'output'`` / ``'input'``。一开始按 ``'output'`` 判断，
    结果所有端口都被判为非输出 → 零条边 → 静默退化成"按创建顺序执行"，
    正好又回到原实现那个 bug 上。

    这里同时接受两种写法，兼容不同 NodeGraphQt 版本。
    判断失败时按"不是输出"处理，宁可漏也不误判。
    """
    try:
        t = str(port.type_()).lower()
    except Exception:
        return False
    return t in ("out", "output")


# --------------------------------------------------------------------------
# 两套节点契约的桥接
#
# 项目里同时存在两种节点基类，执行契约不同：
#
#   新契约（nodes/qlib_core_nodes.py::QlibCoreBaseNode）
#       ok = node.execute()                 无参，返回 bool
#       数据走**真实端口**：
#           node.get_input('port') 读上游 output_port.data
#           node.set_output('port', v) 写自己的 output_port.data
#
#   旧契约（core/qlib_base_node.py::QlibBaseNode）
#       result = node.execute(inputs)       传字典，返回 dict（{} 表示失败）
#       数据走**内部字典**：
#           node.get_input('port') 读 self._input_values
#           node.set_output('port', v) 写 self._output_values
#
# 一键运行必须同时支持两者，否则启用 existing_nodes 之后
# （model_nodes / strategy_nodes / backtest_nodes 都基于旧契约）
# 会直接 TypeError: execute() takes 2 positional arguments but 1 was given。
#
# 桥接方式：对旧契约节点，从真实端口收集 inputs 传进去，
# 执行完再把返回的 dict 写回真实端口 —— 这样新旧节点可以混在一条链路里。
# --------------------------------------------------------------------------

def _port_data(port: Any, default: Any = None) -> Any:
    """从端口取数据（兼容 data / value 两种属性名）。"""
    for attr in ("data", "value"):
        if hasattr(port, attr):
            val = getattr(port, attr)
            if val is not None:
                return val
    return default


def collect_inputs_from_ports(node: Any) -> Dict[str, Any]:
    """从节点的**真实输入端口**收集上游数据，组成 ``{端口名: 数据}``。

    供旧契约 ``execute(inputs)`` 使用，让走内部字典的节点也能拿到
    通过连线传来的数据。
    """
    inputs: Dict[str, Any] = {}
    try:
        ports = node.inputs() or {}
    except Exception:
        return inputs

    for name, in_port in ports.items():
        try:
            conns = in_port.connected_ports() or []
        except Exception:
            continue
        if not conns:
            continue
        # connected_ports() 从输入端口出发返回的是**上游的输出端口**
        inputs[name] = _port_data(conns[0])
    return inputs


def publish_outputs_to_ports(node: Any, values: Any) -> None:
    """把执行结果写回节点的**真实输出端口**，供下游读取。

    旧契约的 ``set_output()`` 只写 ``self._output_values``，
    真实端口上什么都没有 —— 于是下游若用新契约（读端口）就拿不到数据。
    这里把结果补写到端口上，打通两种契约。
    """
    if not isinstance(values, dict) or not values:
        return
    try:
        ports = node.outputs() or {}
    except Exception:
        return
    if not ports:
        return

    wrote = False
    for name, out_port in ports.items():
        if name in values and values[name] is not None:
            try:
                setattr(out_port, "data", values[name])
                wrote = True
            except Exception:
                pass

    # 兜底：只有一个输出端口、且返回值里没有同名键时，
    # 老节点常返回 {'data': ...} / {'output': ...} 这类通用键
    if not wrote and len(ports) == 1:
        only_port = next(iter(ports.values()))
        for key in ("data", "output", "result"):
            if key in values and values[key] is not None:
                try:
                    setattr(only_port, "data", values[key])
                except Exception:
                    pass
                break


def _execute_needs_args(node: Any) -> bool:
    """判断 ``node.execute`` 是否需要传参（即是否为旧契约）。

    通过检查签名里有没有**必填**的位置参数来判断。
    拿不到签名时保守认为不需要（新契约更常见）。
    """
    fn = getattr(node, "execute", None)
    if not callable(fn):
        return False
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    for p in sig.parameters.values():
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD):
            if p.default is inspect.Parameter.empty:
                return True
    return False



def topological_sort_nodes(nodes: Sequence[Any]) -> Tuple[List[Any], List[str]]:
    """按真实端口连线做拓扑排序（Kahn 算法）。

    边的方向是「上游 output port → 下游 input port」。
    数据既然通过端口流动，连线就是唯一的执行顺序真相 ——
    不依赖节点名、id 或任何硬编码顺序。

    Args:
        nodes: NodeGraphQt 节点列表（通常是 ``graph.all_nodes()``）。

    Returns:
        ``(sorted_nodes, warnings)``

        - 图中存在环时，环上节点追加到末尾并给出警告（不阻断执行，
          让用户至少能看到部分结果）。
        - 完全没有连线时，回退为原顺序并提示。
    """
    nodes = [n for n in nodes if n is not None]
    if not nodes:
        return [], []

    warnings: List[str] = []
    by_id: Dict[int, Any] = {id(n): n for n in nodes}
    node_ids: Set[int] = set(by_id)
    order_index: Dict[int, int] = {id(n): i for i, n in enumerate(nodes)}

    # ---- 1. 从端口连线构建邻接表与入度 ----
    edges: Dict[int, Set[int]] = {nid: set() for nid in node_ids}
    indeg: Dict[int, int] = {nid: 0 for nid in node_ids}
    edge_count = 0

    for node in nodes:
        try:
            out_ports = node.outputs() or {}
        except Exception as e:
            warnings.append(f"{node_label(node)} 读取输出端口失败: {e}")
            continue

        for _port_name, out_port in out_ports.items():
            # 只从输出端口出发
            if not _is_output_port(out_port):
                continue
            try:
                targets = out_port.connected_ports() or []
            except Exception:
                continue

            for target in targets:
                try:
                    down_node = target.node()
                except Exception:
                    continue
                if down_node is None:
                    continue
                dnid = id(down_node)
                if dnid not in node_ids or dnid == id(node):
                    continue  # 不在本次集合内，或自环
                if dnid not in edges[id(node)]:
                    edges[id(node)].add(dnid)
                    indeg[dnid] += 1
                    edge_count += 1

    # ---- 2. 无连线则回退 ----
    if edge_count == 0 and len(nodes) > 1:
        warnings.append(
            "节点之间没有任何连线，无法按数据流排序，已按当前顺序执行。"
            "请先把上游的输出端口连到下游的输入端口。")
        return list(nodes), warnings

    # ---- 3. Kahn 算法（同层保持原始顺序，结果稳定可复现）----
    ready: List[int] = sorted(
        [nid for nid, d in indeg.items() if d == 0],
        key=lambda x: order_index[x])
    sorted_ids: List[int] = []

    while ready:
        nid = ready.pop(0)
        sorted_ids.append(nid)
        for down in sorted(edges.get(nid, ()), key=lambda x: order_index[x]):
            indeg[down] -= 1
            if indeg[down] == 0:
                ready.append(down)
                ready.sort(key=lambda x: order_index[x])

    # ---- 4. 有环时把剩余节点补到末尾 ----
    if len(sorted_ids) < len(nodes):
        placed = set(sorted_ids)
        remaining = sorted((nid for nid in by_id if nid not in placed),
                           key=lambda x: order_index[x])
        names = "、".join(node_label(by_id[nid]) for nid in remaining)
        warnings.append(
            f"检测到循环依赖（涉及: {names}）。这些节点会排在最后执行，"
            f"结果可能不正确，请检查连线是否成环。")
        sorted_ids.extend(remaining)

    return [by_id[nid] for nid in sorted_ids], warnings


# --------------------------------------------------------------------------
# 执行器
# --------------------------------------------------------------------------

class NodeGraphWorkflowRunner:
    """执行 NodeGraphQt 节点图（与 Qt 解耦，可单独测试）。

    通过回调向外汇报进度；GUI 侧把它包进 QThread 即可。

    Args:
        nodes: 待执行节点。也可稍后 ``set_nodes()``。
        node_timeout: 单节点超时秒数，None 表示不限制。
        total_timeout: 整体超时秒数，None 表示不限制。
        on_progress: ``(message, level)``
        on_node_start: ``(label, index, total)``
        on_node_end: ``(label, ok, elapsed, detail)``
    """

    def __init__(
        self,
        nodes: Optional[Sequence[Any]] = None,
        node_timeout: Optional[float] = DEFAULT_NODE_TIMEOUT,
        total_timeout: Optional[float] = DEFAULT_TOTAL_TIMEOUT,
        on_progress: Optional[Callable[[str, str], None]] = None,
        on_node_start: Optional[Callable[[str, int, int], None]] = None,
        on_node_end: Optional[Callable[[str, bool, float, str], None]] = None,
    ) -> None:
        self.nodes: List[Any] = list(nodes) if nodes else []
        self.node_timeout = node_timeout
        self.total_timeout = total_timeout
        self.on_progress = on_progress
        self.on_node_start = on_node_start
        self.on_node_end = on_node_end

        self._should_stop = False
        self.records: List[Dict[str, Any]] = []
        self.metrics: Optional[Dict[str, Any]] = None
        self.backtest_result: Any = None

    # ---- 对外 ----

    def set_nodes(self, nodes: Sequence[Any]) -> None:
        self.nodes = list(nodes)

    def request_stop(self) -> None:
        """请求停止（协作式：当前节点跑完后生效）。"""
        self._should_stop = True
        self._emit("正在停止工作流（等待当前节点结束）...", "WARNING")

    @property
    def stopped(self) -> bool:
        return self._should_stop

    # ---- 内部 ----

    def _emit(self, message: str, level: str = "INFO") -> None:
        if self.on_progress:
            try:
                self.on_progress(message, level)
            except Exception:
                pass
        lvl = {"ERROR": logging.ERROR, "WARNING": logging.WARNING}.get(level, logging.INFO)
        logger.log(lvl, message)

    def _read_result(self, node: Any) -> Optional[Dict[str, Any]]:
        """取节点执行结果（优先 get_execution_result）。"""
        try:
            getter = getattr(node, "get_execution_result", None)
            res = getter() if callable(getter) else None
            if res is None:
                res = getattr(node, "_execution_result", None)
            return res if isinstance(res, dict) else None
        except Exception:
            return None

    def _collect_metrics(self, node: Any) -> None:
        """回收回测指标与原始结果，供 UI 渲染。"""
        res = self._read_result(node)
        if not res:
            return
        if res.get("metrics"):
            self.metrics = res["metrics"]
        if res.get("backtest_result") is not None:
            self.backtest_result = res["backtest_result"]

    def _execute_node(self, node: Any) -> Any:
        """执行单个节点，自动适配新旧两种契约。

        - 新契约 ``execute()``：无参，数据走真实端口，返回 bool
        - 旧契约 ``execute(inputs)``：传字典，返回 dict（``{}`` 表示失败）

        旧契约执行完会把返回的 dict 补写到真实端口上，
        这样新旧节点可以混在同一条链路里。
        """
        fn = getattr(node, "execute")
        if not _execute_needs_args(node):
            return fn()

        # 旧契约：从真实端口收集上游数据传进去
        inputs = collect_inputs_from_ports(node)
        result = fn(inputs)

        # 把结果写回真实端口，供下游（可能是新契约）读取
        publish_outputs_to_ports(node, result)
        # 老节点的 set_output 只写了 _output_values，也一并合并
        try:
            extra = node.get_all_outputs() if hasattr(node, "get_all_outputs") else None
            if isinstance(extra, dict):
                publish_outputs_to_ports(node, extra)
        except Exception:
            pass
        return result

    # ---- 主流程 ----

    def run(self) -> Dict[str, Any]:
        """执行工作流，返回汇总字典。"""
        started = time.time()

        if not self.nodes:
            self._emit("没有可执行的节点", "WARNING")
            return {"status": "empty", "ok_count": 0, "total": 0,
                    "elapsed": 0.0, "records": [], "metrics": None}

        # 1) 拓扑排序
        ordered, warnings = topological_sort_nodes(self.nodes)
        for w in warnings:
            self._emit(w, "WARNING")

        total = len(ordered)
        self._emit(f"开始执行工作流：{total} 个节点（已按数据流拓扑排序）", "INFO")
        self._emit("执行顺序: " + " → ".join(node_label(n) for n in ordered), "INFO")

        # 2) 逐节点执行
        ok_count = 0
        for idx, node in enumerate(ordered, start=1):
            label = node_label(node)

            if self._should_stop:
                self._emit("工作流已被用户停止", "WARNING")
                break
            if self.total_timeout is not None and (time.time() - started) > self.total_timeout:
                self._emit(f"工作流整体超时（>{self.total_timeout:g}s），停止执行", "ERROR")
                break

            if self.on_node_start:
                try:
                    self.on_node_start(label, idx, total)
                except Exception:
                    pass

            if not callable(getattr(node, "execute", None)):
                self._emit(f"⚠️ {label} 没有 execute() 方法，跳过", "WARNING")
                self.records.append({"node": label, "type": node_type_id(node),
                                     "ok": False, "elapsed": 0.0,
                                     "detail": "无 execute 方法"})
                continue

            self._emit(f"[{idx}/{total}] 执行 {label} ...", "INFO")
            t0 = time.time()
            ok = False
            detail = ""

            tee = _Tee(sys.stdout)
            try:
                # 注意：真实节点契约是 execute() 无参，数据走端口
                # 自动适配新旧契约（旧契约返回 dict，{} 为失败 → bool({}) 为 False）
                with contextlib.redirect_stdout(tee):
                    ok = bool(self._execute_node(node))
                elapsed = time.time() - t0
                res = self._read_result(node)
                status = (res or {}).get("status")

                if ok and status == "partial":
                    detail = (res or {}).get("train_error") or "部分完成"
                    self._emit(f"⚠️ {label} 部分完成（{detail}），耗时 {elapsed:.2f}s",
                               "WARNING")
                elif ok:
                    self._emit(f"✅ {label} 完成，耗时 {elapsed:.2f}s", "SUCCESS")
                    ok_count += 1
                else:
                    detail = str((res or {}).get("error") or "")
                    if not detail:
                        err_fn = getattr(node, "get_error_message", None)
                        detail = (err_fn() if callable(err_fn) else None) or ""
                    if not detail or detail == "返回 False":
                        detail = tee.failure_hint() or "返回 False"
                    self._emit(f"❌ {label} 执行失败: {detail}", "ERROR")

                if ok:
                    self._collect_metrics(node)

            except Exception as e:
                elapsed = time.time() - t0
                detail = f"{type(e).__name__}: {e}"
                hint = tee.failure_hint()
                if hint:
                    detail += " | " + hint
                self._emit(f"❌ {label} 执行异常: {detail}", "ERROR")
                self._emit(f"堆栈:\n{traceback.format_exc()}", "ERROR")

            self.records.append({"node": label, "type": node_type_id(node),
                                 "ok": ok, "elapsed": elapsed, "detail": detail})
            if self.on_node_end:
                try:
                    self.on_node_end(label, ok, elapsed, detail)
                except Exception:
                    pass

        # 3) 汇总
        total_elapsed = time.time() - started
        level = "SUCCESS" if ok_count == total else "WARNING"
        self._emit(
            f"工作流结束：成功 {ok_count}/{total} 个节点，总耗时 {total_elapsed:.2f}s", level)

        return {
            "status": "success" if ok_count == total else "partial",
            "ok_count": ok_count,
            "total": total,
            "elapsed": total_elapsed,
            "records": self.records,
            "metrics": self.metrics,
            "backtest_result": self.backtest_result,
        }
