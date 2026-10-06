#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 工作流引擎
与Qlib原生工作流集成的高性能工作流执行引擎
"""

import os
import sys
import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import networkx as nx

logger = logging.getLogger(__name__)

try:
    import qlib
    from qlib.workflow import R
    from qlib.utils import init_instance_by_config
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

class RockXQlibWorkflowStatus(Enum):
    """工作流状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"

class RockXQlibExecutionMode(Enum):
    """执行模式枚举"""
    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"      # 并行执行
    PIPELINE = "pipeline"      # 流水线执行
    ADAPTIVE = "adaptive"      # 自适应执行

@dataclass
class RockXQlibWorkflowNode:
    """工作流节点"""
    node_id: str
    node_type: str
    node_instance: Any
    inputs: Dict[str, Any] = None
    outputs: Dict[str, Any] = None
    dependencies: List[str] = None
    execution_time: float = 0.0
    status: str = "idle"
    error_message: str = ""

    def __post_init__(self):
        if self.inputs is None:
            self.inputs = {}
        if self.outputs is None:
            self.outputs = {}
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class RockXQlibWorkflowConnection:
    """工作流连接"""
    from_node: str
    to_node: str
    from_port: str
    to_port: str
    data_type: str = "any"

@dataclass
class RockXQlibExecutionResult:
    """执行结果"""
    success: bool
    workflow_id: str
    execution_time: float
    node_results: Dict[str, Any] = None
    error_message: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.node_results is None:
            self.node_results = {}
        if self.metadata is None:
            self.metadata = {}

class RockXQlibWorkflow:
    """工作流定义"""

    def __init__(self, workflow_id: str, name: str = ""):
        self.workflow_id = workflow_id
        self.name = name or f"Workflow_{workflow_id}"
        self.nodes = {}  # node_id -> WorkflowNode
        self.connections = []  # List[WorkflowConnection]
        self.execution_order = []  # 执行顺序
        self.dependency_graph = nx.DiGraph()

        # 工作流配置
        self.execution_mode = RockXQlibExecutionMode.ADAPTIVE
        self.max_parallel_workers = 4
        self.timeout = 3600  # 1小时超时
        self.retry_count = 3
        self.enable_caching = True

        # 状态
        self.status = RockXQlibWorkflowStatus.IDLE
        self.created_time = time.time()
        self.last_execution_time = None

        # 统计信息
        self.execution_count = 0
        self.total_execution_time = 0.0
        self.success_count = 0
        self.failure_count = 0

    def add_node(self, node_id: str, node_type: str, node_instance: Any,
                inputs: Optional[Dict[str, Any]] = None,
                dependencies: Optional[List[str]] = None) -> bool:
        """添加节点"""
        try:
            if node_id in self.nodes:
                logger.warning(f"节点 {node_id} 已存在，将更新")

            node = RockXQlibWorkflowNode(
                node_id=node_id,
                node_type=node_type,
                node_instance=node_instance,
                inputs=inputs or {},
                dependencies=dependencies or []
            )

            self.nodes[node_id] = node

            # 更新依赖图
            self.dependency_graph.add_node(node_id)
            for dep in node.dependencies:
                self.dependency_graph.add_edge(dep, node_id)

            # 重新计算执行顺序
            self._calculate_execution_order()

            logger.info(f"节点 {node_id} 添加成功")
            return True

        except Exception as e:
            logger.error(f"添加节点失败: {e}")
            return False

    def connect_nodes(self, from_node: str, to_node: str,
                     from_port: str = "output", to_port: str = "input") -> bool:
        """连接节点"""
        try:
            if from_node not in self.nodes:
                raise ValueError(f"源节点 {from_node} 不存在")
            if to_node not in self.nodes:
                raise ValueError(f"目标节点 {to_node} 不存在")

            connection = RockXQlibWorkflowConnection(
                from_node=from_node,
                to_node=to_node,
                from_port=from_port,
                to_port=to_port
            )

            self.connections.append(connection)

            # 更新依赖关系
            if to_node not in self.nodes[from_node].dependencies:
                self.nodes[to_node].dependencies.append(from_node)
                self.dependency_graph.add_edge(from_node, to_node)

            # 重新计算执行顺序
            self._calculate_execution_order()

            logger.info(f"节点连接成功: {from_node} -> {to_node}")
            return True

        except Exception as e:
            logger.error(f"连接节点失败: {e}")
            return False

    def _calculate_execution_order(self):
        """计算执行顺序"""
        try:
            # 检查是否有循环依赖
            if not nx.is_directed_acyclic_graph(self.dependency_graph):
                cycles = list(nx.simple_cycles(self.dependency_graph))
                raise ValueError(f"工作流存在循环依赖: {cycles}")

            # 拓扑排序
            self.execution_order = list(nx.topological_sort(self.dependency_graph))
            logger.debug(f"执行顺序: {self.execution_order}")

        except Exception as e:
            logger.error(f"计算执行顺序失败: {e}")
            self.execution_order = []

    def validate_workflow(self) -> Tuple[bool, List[str]]:
        """验证工作流"""
        errors = []

        try:
            # 检查节点
            if not self.nodes:
                errors.append("工作流没有节点")
                return False, errors

            # 检查依赖关系
            for node_id, node in self.nodes.items():
                for dep in node.dependencies:
                    if dep not in self.nodes:
                        errors.append(f"节点 {node_id} 的依赖 {dep} 不存在")

            # 检查循环依赖
            if not nx.is_directed_acyclic_graph(self.dependency_graph):
                cycles = list(nx.simple_cycles(self.dependency_graph))
                errors.append(f"存在循环依赖: {cycles}")

            # 检查节点配置
            for node_id, node in self.nodes.items():
                if not hasattr(node.node_instance, 'execute'):
                    errors.append(f"节点 {node_id} 没有 execute 方法")

            return len(errors) == 0, errors

        except Exception as e:
            errors.append(f"验证工作流失败: {e}")
            return False, errors

    def get_execution_plan(self) -> Dict[str, Any]:
        """获取执行计划"""
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'execution_order': self.execution_order,
            'execution_mode': self.execution_mode.value,
            'max_parallel_workers': self.max_parallel_workers,
            'timeout': self.timeout,
            'node_count': len(self.nodes),
            'connection_count': len(self.connections),
            'estimated_execution_time': sum(node.execution_time for node in self.nodes.values())
        }

class RockXQlibWorkflowEngine:
    """工作流执行引擎"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running_workflows = {}  # workflow_id -> workflow
        self.workflow_results = {}   # workflow_id -> result
        self.lock = threading.Lock()

        # 统计信息
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.start_time = time.time()

        # 初始化Qlib
        self._initialize_qlib()

    def _initialize_qlib(self):
        """初始化Qlib"""
        try:
            if QLIB_AVAILABLE:
                # 这里可以设置Qlib的默认配置
                logger.info("Qlib工作流引擎初始化成功")
            else:
                logger.warning("Qlib不可用，部分功能将受限")
        except Exception as e:
            logger.error(f"初始化Qlib失败: {e}")

    def execute_workflow(self, workflow: RockXQlibWorkflow,
                        inputs: Optional[Dict[str, Any]] = None) -> RockXQlibExecutionResult:
        """执行工作流"""
        start_time = time.time()

        try:
            # 验证工作流
            is_valid, errors = workflow.validate_workflow()
            if not is_valid:
                return RockXQlibExecutionResult(
                    success=False,
                    workflow_id=workflow.workflow_id,
                    execution_time=time.time() - start_time,
                    error_message=f"工作流验证失败: {errors}"
                )

            # 更新状态
            with self.lock:
                workflow.status = RockXQlibWorkflowStatus.RUNNING
                self.running_workflows[workflow.workflow_id] = workflow
                self.total_executions += 1

            # 根据执行模式选择执行策略
            if workflow.execution_mode == RockXQlibExecutionMode.SEQUENTIAL:
                result = self._execute_sequential(workflow, inputs or {})
            elif workflow.execution_mode == RockXQlibExecutionMode.PARALLEL:
                result = self._execute_parallel(workflow, inputs or {})
            elif workflow.execution_mode == RockXQlibExecutionMode.PIPELINE:
                result = self._execute_pipeline(workflow, inputs or {})
            else:  # ADAPTIVE
                result = self._execute_adaptive(workflow, inputs or {})

            # 更新统计
            execution_time = time.time() - start_time
            workflow.execution_count += 1
            workflow.total_execution_time += execution_time
            workflow.last_execution_time = time.time()

            if result.success:
                workflow.success_count += 1
                self.successful_executions += 1
                workflow.status = RockXQlibWorkflowStatus.COMPLETED
            else:
                workflow.failure_count += 1
                self.failed_executions += 1
                workflow.status = RockXQlibWorkflowStatus.FAILED

            # 保存结果
            with self.lock:
                self.workflow_results[workflow.workflow_id] = result
                if workflow.workflow_id in self.running_workflows:
                    del self.running_workflows[workflow.workflow_id]

            result.execution_time = execution_time
            return result

        except Exception as e:
            error_msg = f"执行工作流失败: {e}"
            logger.error(error_msg)

            with self.lock:
                if workflow.workflow_id in self.running_workflows:
                    del self.running_workflows[workflow.workflow_id]
                workflow.status = RockXQlibWorkflowStatus.FAILED

            return RockXQlibExecutionResult(
                success=False,
                workflow_id=workflow.workflow_id,
                execution_time=time.time() - start_time,
                error_message=error_msg
            )

    def _execute_sequential(self, workflow: RockXQlibWorkflow, inputs: Dict[str, Any]) -> RockXQlibExecutionResult:
        """顺序执行"""
        try:
            node_results = {}
            current_inputs = inputs.copy()

            for node_id in workflow.execution_order:
                node = workflow.nodes[node_id]

                # 准备节点输入
                node_inputs = self._prepare_node_inputs(node, current_inputs, node_results)

                # 执行节点
                node_start_time = time.time()
                try:
                    node_outputs = node.node_instance.execute(node_inputs)
                    node.execution_time = time.time() - node_start_time
                    node.status = "completed"

                    # 保存节点结果
                    node_results[node_id] = {
                        'outputs': node_outputs,
                        'execution_time': node.execution_time,
                        'status': 'completed'
                    }

                    # 更新当前输入
                    if isinstance(node_outputs, dict):
                        current_inputs.update(node_outputs)

                except Exception as e:
                    node.status = "failed"
                    node.error_message = str(e)
                    node_results[node_id] = {
                        'error': str(e),
                        'execution_time': time.time() - node_start_time,
                        'status': 'failed'
                    }
                    raise

            return RockXQlibExecutionResult(
                success=True,
                workflow_id=workflow.workflow_id,
                execution_time=0,  # 将在外部设置
                node_results=node_results
            )

        except Exception as e:
            return RockXQlibExecutionResult(
                success=False,
                workflow_id=workflow.workflow_id,
                execution_time=0,
                error_message=str(e),
                node_results=node_results
            )

    def _execute_parallel(self, workflow: RockXQlibWorkflow, inputs: Dict[str, Any]) -> RockXQlibExecutionResult:
        """并行执行"""
        try:
            # 将节点按依赖关系分组
            execution_groups = self._group_nodes_by_dependency(workflow)
            node_results = {}
            current_inputs = inputs.copy()

            for group in execution_groups:
                # 并行执行同组节点
                futures = {}
                for node_id in group:
                    node = workflow.nodes[node_id]
                    node_inputs = self._prepare_node_inputs(node, current_inputs, node_results)

                    future = self.executor.submit(self._execute_node, node, node_inputs)
                    futures[node_id] = future

                # 等待当前组完成
                for node_id, future in futures.items():
                    try:
                        result = future.result(timeout=workflow.timeout)
                        node_results[node_id] = result

                        # 更新输入
                        if result.get('success') and isinstance(result.get('outputs'), dict):
                            current_inputs.update(result['outputs'])

                    except Exception as e:
                        node_results[node_id] = {
                            'success': False,
                            'error': str(e),
                            'status': 'failed'
                        }
                        raise

            return RockXQlibExecutionResult(
                success=True,
                workflow_id=workflow.workflow_id,
                execution_time=0,
                node_results=node_results
            )

        except Exception as e:
            return RockXQlibExecutionResult(
                success=False,
                workflow_id=workflow.workflow_id,
                execution_time=0,
                error_message=str(e),
                node_results=node_results
            )

    def _execute_pipeline(self, workflow: RockXQlibWorkflow, inputs: Dict[str, Any]) -> RockXQlibExecutionResult:
        """流水线执行"""
        # 流水线执行类似于顺序执行，但可以优化数据传输
        return self._execute_sequential(workflow, inputs)

    def _execute_adaptive(self, workflow: RockXQlibWorkflow, inputs: Dict[str, Any]) -> RockXQlibExecutionResult:
        """自适应执行"""
        # 根据节点特性和依赖关系自动选择最佳执行策略
        if len(workflow.nodes) <= 2:
            return self._execute_sequential(workflow, inputs)
        else:
            return self._execute_parallel(workflow, inputs)

    def _group_nodes_by_dependency(self, workflow: RockXQlibWorkflow) -> List[List[str]]:
        """按依赖关系分组节点"""
        groups = []
        remaining_nodes = set(workflow.nodes.keys())

        while remaining_nodes:
            # 找到没有未完成依赖的节点
            current_group = []
            for node_id in list(remaining_nodes):
                node = workflow.nodes[node_id]
                if all(dep not in remaining_nodes for dep in node.dependencies):
                    current_group.append(node_id)

            if not current_group:
                # 如果找不到可执行的节点，说明有循环依赖
                raise ValueError("检测到循环依赖")

            groups.append(current_group)
            remaining_nodes -= set(current_group)

        return groups

    def _prepare_node_inputs(self, node: RockXQlibWorkflowNode,
                           global_inputs: Dict[str, Any],
                           node_results: Dict[str, Any]) -> Dict[str, Any]:
        """准备节点输入"""
        inputs = {}

        # 添加全局输入
        inputs.update(global_inputs)

        # 添加节点配置的输入
        inputs.update(node.inputs)

        # 添加依赖节点的输出
        for dep_id in node.dependencies:
            if dep_id in node_results and 'outputs' in node_results[dep_id]:
                dep_outputs = node_results[dep_id]['outputs']
                if isinstance(dep_outputs, dict):
                    inputs.update(dep_outputs)

        # 处理信号占位符替换
        self._handle_signal_placeholders(node, inputs, node_results)

        return inputs

    def _handle_signal_placeholders(self, node: RockXQlibWorkflowNode,
                                  inputs: Dict[str, Any],
                                  node_results: Dict[str, Any]):
        """处理信号占位符替换"""
        try:
            # 检查节点是否有信号占位符标记
            if hasattr(node.node_instance, 'get_property'):
                has_placeholder = node.node_instance.get_property('_has_signal_placeholder')
                if not has_placeholder:
                    return

                # 查找模型节点的预测结果
                predictions = None
                for dep_id in node.dependencies:
                    if dep_id in node_results and 'outputs' in node_results[dep_id]:
                        dep_outputs = node_results[dep_id]['outputs']
                        if isinstance(dep_outputs, dict) and 'predictions' in dep_outputs:
                            predictions = dep_outputs['predictions']
                            break

                if predictions is not None:
                    # 替换信号占位符
                    signal_placeholder = node.node_instance.get_property('_signal_placeholder')
                    if signal_placeholder == '<PRED>':
                        # 将预测结果设置为信号
                        node.node_instance.set_property('signal', predictions)
                        logger.info(f"节点 {node.node_id} 的<PRED>占位符已替换为预测结果")

                        # 更新输入
                        inputs['signal'] = predictions

        except Exception as e:
            logger.warning(f"处理信号占位符失败: {e}")

    def _execute_node(self, node: RockXQlibWorkflowNode, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个节点"""
        start_time = time.time()

        try:
            # 执行节点
            outputs = node.node_instance.execute(inputs)

            execution_time = time.time() - start_time
            node.execution_time = execution_time
            node.status = "completed"

            # 处理节点输出，确保信号正确传递
            processed_outputs = self._process_node_outputs(node, outputs, inputs)

            return {
                'success': True,
                'outputs': processed_outputs,
                'execution_time': execution_time,
                'status': 'completed'
            }

        except Exception as e:
            execution_time = time.time() - start_time
            node.status = "failed"
            node.error_message = str(e)

            return {
                'success': False,
                'error': str(e),
                'execution_time': execution_time,
                'status': 'failed'
            }

    def _process_node_outputs(self, node: RockXQlibWorkflowNode,
                            outputs: Any, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理节点输出，确保信号正确传递"""
        try:
            # 如果输出是字典，直接返回
            if isinstance(outputs, dict):
                return outputs

            # 如果输出是其他类型，包装成字典
            processed_outputs = {}

            # 根据节点类型处理输出
            if node.node_type == 'qlib.core.model':
                # 模型节点输出预测结果
                processed_outputs['predictions'] = outputs
                processed_outputs['model'] = node.node_instance

            elif node.node_type == 'qlib.core.strategy':
                # 策略节点输出策略对象和信号
                processed_outputs['strategy'] = outputs
                if hasattr(node.node_instance, 'signal'):
                    processed_outputs['signal'] = node.node_instance.signal

            elif node.node_type == 'qlib.core.dataset':
                # 数据集节点输出数据集对象
                processed_outputs['dataset'] = outputs

            elif node.node_type == 'qlib.core.backtest':
                # 回测节点输出回测结果
                processed_outputs['backtest_result'] = outputs

            else:
                # 其他节点类型，使用通用输出
                processed_outputs['output'] = outputs

            return processed_outputs

        except Exception as e:
            logger.warning(f"处理节点输出失败: {e}")
            return {'output': outputs} if outputs is not None else {}

    def get_workflow_status(self, workflow_id: str) -> Optional[RockXQlibWorkflowStatus]:
        """获取工作流状态"""
        with self.lock:
            if workflow_id in self.running_workflows:
                return RockXQlibWorkflowStatus.RUNNING
            elif workflow_id in self.workflow_results:
                result = self.workflow_results[workflow_id]
                return RockXQlibWorkflowStatus.COMPLETED if result.success else RockXQlibWorkflowStatus.FAILED
            else:
                return None

    def get_workflow_result(self, workflow_id: str) -> Optional[RockXQlibExecutionResult]:
        """获取工作流结果"""
        with self.lock:
            return self.workflow_results.get(workflow_id)

    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        try:
            with self.lock:
                if workflow_id in self.running_workflows:
                    workflow = self.running_workflows[workflow_id]
                    workflow.status = RockXQlibWorkflowStatus.CANCELLED
                    del self.running_workflows[workflow_id]
                    logger.info(f"工作流 {workflow_id} 已取消")
                    return True
                return False
        except Exception as e:
            logger.error(f"取消工作流失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'uptime': uptime,
                'total_executions': self.total_executions,
                'successful_executions': self.successful_executions,
                'failed_executions': self.failed_executions,
                'running_workflows': len(self.running_workflows),
                'success_rate': self.successful_executions / max(self.total_executions, 1),
                'executions_per_minute': self.total_executions / max(uptime / 60, 1)
            }

    def create_qlib_workflow_from_config(self, workflow_config: Dict[str, Any]) -> RockXQlibWorkflow:
        """从配置创建qlib工作流"""
        try:
            workflow_id = workflow_config.get('workflow_id', f"qlib_workflow_{int(time.time())}")
            workflow = RockXQlibWorkflow(workflow_id, workflow_config.get('name', 'Qlib Workflow'))

            # 解析节点配置
            nodes_config = workflow_config.get('nodes', [])
            for node_config in nodes_config:
                node_id = node_config.get('id')
                node_type = node_config.get('type')
                node_name = node_config.get('name', f'Node_{node_id}')

                # 创建节点实例（这里需要根据实际需求实现）
                # 暂时使用占位符
                node_instance = None

                # 添加节点
                workflow.add_node(
                    node_id=node_id,
                    node_type=node_type,
                    node_instance=node_instance,
                    inputs=node_config.get('properties', {}),
                    dependencies=node_config.get('dependencies', [])
                )

            # 解析连接配置
            connections_config = workflow_config.get('connections', [])
            for conn_config in connections_config:
                workflow.connect_nodes(
                    from_node=conn_config.get('from_node'),
                    to_node=conn_config.get('to_node'),
                    from_port=conn_config.get('from_port', 'output'),
                    to_port=conn_config.get('to_port', 'input')
                )

            logger.info(f"Qlib工作流 {workflow_id} 创建成功")
            return workflow

        except Exception as e:
            logger.error(f"创建Qlib工作流失败: {e}")
            raise

    def execute_qlib_workflow_with_signal_handling(self, workflow_config: Dict[str, Any]) -> RockXQlibExecutionResult:
        """执行带信号处理的qlib工作流"""
        try:
            # 创建工作流
            workflow = self.create_qlib_workflow_from_config(workflow_config)

            # 验证工作流
            is_valid, errors = workflow.validate_workflow()
            if not is_valid:
                return RockXQlibExecutionResult(
                    success=False,
                    workflow_id=workflow.workflow_id,
                    execution_time=0,
                    error_message=f"工作流验证失败: {errors}"
                )

            # 执行工作流
            result = self.execute_workflow(workflow)

            # 处理信号占位符
            if result.success:
                self._post_process_signal_placeholders(workflow, result)

            return result

        except Exception as e:
            logger.error(f"执行Qlib工作流失败: {e}")
            return RockXQlibExecutionResult(
                success=False,
                workflow_id=workflow_config.get('workflow_id', 'unknown'),
                execution_time=0,
                error_message=str(e)
            )

    def _post_process_signal_placeholders(self, workflow: RockXQlibWorkflow, result: RockXQlibExecutionResult):
        """后处理信号占位符"""
        try:
            # 查找所有策略节点
            strategy_nodes = []
            for node_id, node in workflow.nodes.items():
                if node.node_type == 'qlib.core.strategy':
                    strategy_nodes.append(node)

            # 为每个策略节点处理信号占位符
            for strategy_node in strategy_nodes:
                if hasattr(strategy_node.node_instance, 'get_property'):
                    has_placeholder = strategy_node.node_instance.get_property('_has_signal_placeholder')
                    if has_placeholder:
                        # 查找对应的模型节点输出
                        predictions = None
                        for dep_id in strategy_node.dependencies:
                            if dep_id in result.node_results and 'outputs' in result.node_results[dep_id]:
                                dep_outputs = result.node_results[dep_id]['outputs']
                                if isinstance(dep_outputs, dict) and 'predictions' in dep_outputs:
                                    predictions = dep_outputs['predictions']
                                    break

                        if predictions is not None:
                            # 替换信号占位符
                            strategy_node.node_instance.set_property('signal', predictions)
                            logger.info(f"策略节点 {strategy_node.node_id} 的信号占位符已替换")

        except Exception as e:
            logger.warning(f"后处理信号占位符失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            # 取消所有运行中的工作流
            with self.lock:
                for workflow_id in list(self.running_workflows.keys()):
                    self.cancel_workflow(workflow_id)

            # 关闭线程池
            self.executor.shutdown(wait=True)

            logger.info("工作流引擎清理完成")

        except Exception as e:
            logger.error(f"工作流引擎清理失败: {e}")
