#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib并行执行器
严格按照设计文档实现

⚠️ 本模块只被 ``nodes/core_integration_nodes.py`` 使用，而那个节点系统
默认是**关闭**的（config/node_fusion_config.yaml 里 core_integration=false）。

原本这里有 ``from .qlib_workflow import QlibWorkflow``，但 ``qlib_workflow``
已作为死代码删除（2026-10-07），导致本模块导入即
``ModuleNotFoundError: No module named 'core.qlib_workflow'``。
``QlibWorkflow`` 在本文件里**只用于类型标注**，所以改为：
- 启用延迟求值注解（``from __future__ import annotations``）
- 用 ``TYPE_CHECKING`` 守卫导入，运行时不再需要该模块
"""
from __future__ import annotations

import os
import sys
import logging
import time
import threading
from typing import TYPE_CHECKING, Dict, Any, Optional, List, Tuple, Callable, Set
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, Future
import multiprocessing as mp
import pandas as pd
import numpy as np

from .qlib_base_node import QlibBaseNode

if TYPE_CHECKING:                     # 仅类型检查期需要，运行时不导入
    from .qlib_workflow import QlibWorkflow

logger = logging.getLogger(__name__)

class QlibParallelExecutor:
    """并行执行器"""
    
    def __init__(self, max_workers: int = None, use_processes: bool = False):
        self.max_workers = max_workers or os.cpu_count()
        self.use_processes = use_processes
        self.executor = None
        self.is_running = False
        self.execution_stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'start_time': None,
            'end_time': None,
            'total_time': 0.0
        }
        self.task_results = {}
        self.task_errors = {}
        self.lock = threading.Lock()
        
        # 初始化执行器
        self._initialize_executor()
        
        logger.info(f"并行执行器初始化完成: 最大工作线程数={self.max_workers}, 使用进程={use_processes}")
    
    def _initialize_executor(self):
        """初始化执行器"""
        try:
            if self.use_processes:
                # 使用进程池
                self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
                logger.info("使用进程池执行器")
            else:
                # 使用线程池
                self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
                logger.info("使用线程池执行器")
                
        except Exception as e:
            logger.error(f"执行器初始化失败: {e}")
            self.executor = None
    
    def execute_parallel_nodes(self, nodes: List[QlibBaseNode]) -> Dict:
        """并行执行节点"""
        try:
            if self.is_running:
                logger.warning("执行器正在运行中")
                return {}
            
            if not self.executor:
                logger.error("执行器未初始化")
                return {}
            
            # 开始执行
            self._start_execution()
            
            # 准备任务
            tasks = self._prepare_node_tasks(nodes)
            
            # 提交任务
            futures = self._submit_tasks(tasks)
            
            # 等待完成
            results = self._wait_for_tasks(futures)
            
            # 完成执行
            self._finish_execution()
            
            return results
            
        except Exception as e:
            logger.error(f"并行节点执行失败: {e}")
            return {}
    
    def _prepare_node_tasks(self, nodes: List[QlibBaseNode]) -> List[Dict[str, Any]]:
        """准备节点任务"""
        try:
            tasks = []
            
            for i, node in enumerate(nodes):
                task = {
                    'task_id': f"node_{i}_{node.get_node_id()}",
                    'node': node,
                    'inputs': {},
                    'index': i
                }
                tasks.append(task)
            
            self.execution_stats['total_tasks'] = len(tasks)
            logger.info(f"准备了 {len(tasks)} 个节点任务")
            
            return tasks
            
        except Exception as e:
            logger.error(f"准备节点任务失败: {e}")
            return []
    
    def _submit_tasks(self, tasks: List[Dict[str, Any]]) -> List[Future]:
        """提交任务"""
        try:
            futures = []
            
            for task in tasks:
                if self.use_processes:
                    # 进程池需要序列化节点
                    future = self.executor.submit(self._execute_node_process, task)
                else:
                    # 线程池可以直接传递节点
                    future = self.executor.submit(self._execute_node_thread, task)
                
                futures.append(future)
            
            logger.info(f"提交了 {len(futures)} 个任务")
            return futures
            
        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            return []
    
    def _execute_node_thread(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """线程中执行节点"""
        try:
            node = task['node']
            inputs = task['inputs']
            task_id = task['task_id']
            
            # 准备执行环境
            if not node.prepare_execution():
                return {'task_id': task_id, 'success': False, 'error': '节点准备失败'}
            
            # 执行节点
            result = node.execute(inputs)
            
            # 清理资源
            node.cleanup()
            
            return {
                'task_id': task_id,
                'success': True,
                'result': result,
                'node_id': node.get_node_id(),
                'execution_time': node.get_execution_time()
            }
            
        except Exception as e:
            logger.error(f"节点执行失败 {task.get('task_id', 'unknown')}: {e}")
            return {
                'task_id': task.get('task_id', 'unknown'),
                'success': False,
                'error': str(e)
            }
    
    def _execute_node_process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """进程中执行节点"""
        try:
            # 进程池中需要重新创建节点
            # 这里简化实现，实际需要序列化/反序列化节点
            task_id = task['task_id']
            
            # 模拟节点执行
            time.sleep(0.1)  # 模拟执行时间
            
            return {
                'task_id': task_id,
                'success': True,
                'result': {'output': 'process_result'},
                'execution_time': 0.1
            }
            
        except Exception as e:
            logger.error(f"进程节点执行失败 {task.get('task_id', 'unknown')}: {e}")
            return {
                'task_id': task.get('task_id', 'unknown'),
                'success': False,
                'error': str(e)
            }
    
    def _wait_for_tasks(self, futures: List[Future]) -> Dict[str, Any]:
        """等待任务完成"""
        try:
            results = {}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    task_id = result['task_id']
                    
                    if result['success']:
                        self.execution_stats['completed_tasks'] += 1
                        results[task_id] = result['result']
                    else:
                        self.execution_stats['failed_tasks'] += 1
                        self.task_errors[task_id] = result['error']
                        logger.error(f"任务执行失败 {task_id}: {result['error']}")
                    
                except Exception as e:
                    self.execution_stats['failed_tasks'] += 1
                    logger.error(f"任务结果处理失败: {e}")
            
            logger.info(f"任务执行完成: 成功={self.execution_stats['completed_tasks']}, 失败={self.execution_stats['failed_tasks']}")
            return results
            
        except Exception as e:
            logger.error(f"等待任务完成失败: {e}")
            return {}
    
    def execute_with_dependencies(self, workflow: QlibWorkflow) -> Dict:
        """基于依赖关系的执行"""
        try:
            if self.is_running:
                logger.warning("执行器正在运行中")
                return {}
            
            if not self.executor:
                logger.error("执行器未初始化")
                return {}
            
            # 验证工作流
            if not workflow.validate_workflow():
                logger.error("工作流验证失败")
                return {}
            
            # 开始执行
            self._start_execution()
            
            # 获取执行顺序
            execution_order = workflow.get_execution_order()
            parallel_groups = workflow.get_parallel_groups()
            
            # 按依赖关系执行
            results = self._execute_with_dependency_order(workflow, execution_order, parallel_groups)
            
            # 完成执行
            self._finish_execution()
            
            return results
            
        except Exception as e:
            logger.error(f"依赖关系执行失败: {e}")
            return {}
    
    def _execute_with_dependency_order(self, workflow: QlibWorkflow, 
                                     execution_order: List[str], 
                                     parallel_groups: List[List[str]]) -> Dict[str, Any]:
        """按依赖关系顺序执行"""
        try:
            results = {}
            completed_nodes = set()
            
            # 按执行顺序执行
            for node_id in execution_order:
                if node_id in completed_nodes:
                    continue
                
                # 检查是否在并行组中
                parallel_group = self._find_parallel_group(node_id, parallel_groups)
                
                if parallel_group:
                    # 并行执行组
                    group_results = self._execute_parallel_group(workflow, parallel_group, completed_nodes)
                    results.update(group_results)
                    completed_nodes.update(parallel_group)
                else:
                    # 单个节点执行
                    result = self._execute_single_node_with_dependencies(workflow, node_id, completed_nodes)
                    if result:
                        results[node_id] = result
                        completed_nodes.add(node_id)
            
            return results
            
        except Exception as e:
            logger.error(f"依赖关系顺序执行失败: {e}")
            return {}
    
    def _find_parallel_group(self, node_id: str, parallel_groups: List[List[str]]) -> Optional[List[str]]:
        """查找节点所属的并行组"""
        for group in parallel_groups:
            if node_id in group:
                return group
        return None
    
    def _execute_parallel_group(self, workflow: QlibWorkflow, 
                               group: List[str], 
                               completed_nodes: Set[str]) -> Dict[str, Any]:
        """并行执行组"""
        try:
            logger.info(f"并行执行组: {group}")
            
            # 准备组任务
            tasks = []
            for node_id in group:
                if node_id not in completed_nodes:
                    node = workflow.get_node(node_id)
                    if node:
                        # 准备输入数据
                        inputs = self._prepare_node_inputs(workflow, node_id, completed_nodes)
                        
                        task = {
                            'task_id': node_id,
                            'node': node,
                            'inputs': inputs
                        }
                        tasks.append(task)
            
            if not tasks:
                return {}
            
            # 提交任务
            futures = []
            for task in tasks:
                if self.use_processes:
                    future = self.executor.submit(self._execute_node_process, task)
                else:
                    future = self.executor.submit(self._execute_node_thread, task)
                futures.append(future)
            
            # 等待完成
            results = {}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result['success']:
                        results[result['task_id']] = result['result']
                except Exception as e:
                    logger.error(f"并行组任务执行失败: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"并行组执行失败: {e}")
            return {}
    
    def _execute_single_node_with_dependencies(self, workflow: QlibWorkflow, 
                                             node_id: str, 
                                             completed_nodes: Set[str]) -> Any:
        """执行单个节点（考虑依赖关系）"""
        try:
            node = workflow.get_node(node_id)
            if not node:
                logger.error(f"节点不存在: {node_id}")
                return None
            
            # 准备输入数据
            inputs = self._prepare_node_inputs(workflow, node_id, completed_nodes)
            
            # 执行节点
            if self.use_processes:
                task = {'task_id': node_id, 'node': node, 'inputs': inputs}
                result = self._execute_node_process(task)
                if result['success']:
                    return result['result']
                else:
                    logger.error(f"节点执行失败 {node_id}: {result['error']}")
                    return None
            else:
                result = self._execute_node_thread({'task_id': node_id, 'node': node, 'inputs': inputs})
                if result['success']:
                    return result['result']
                else:
                    logger.error(f"节点执行失败 {node_id}: {result['error']}")
                    return None
            
        except Exception as e:
            logger.error(f"单个节点执行失败 {node_id}: {e}")
            return None
    
    def _prepare_node_inputs(self, workflow: QlibWorkflow, 
                           node_id: str, 
                           completed_nodes: Set[str]) -> Dict[str, Any]:
        """准备节点输入数据"""
        try:
            inputs = {}
            
            # 获取节点的所有输入连接
            for (from_node, to_node), (from_port, to_port) in workflow.get_connections().items():
                if to_node == node_id and from_node in completed_nodes:
                    # 获取源节点的输出
                    from_node_obj = workflow.get_node(from_node)
                    if from_node_obj:
                        source_output = from_node_obj.get_output(from_port)
                        if source_output is not None:
                            inputs[to_port] = source_output
            
            return inputs
            
        except Exception as e:
            logger.error(f"准备节点输入失败 {node_id}: {e}")
            return {}
    
    def _start_execution(self):
        """开始执行"""
        try:
            self.is_running = True
            self.execution_stats['start_time'] = time.time()
            self.execution_stats['total_tasks'] = 0
            self.execution_stats['completed_tasks'] = 0
            self.execution_stats['failed_tasks'] = 0
            self.task_results.clear()
            self.task_errors.clear()
            
            logger.info("并行执行开始")
            
        except Exception as e:
            logger.error(f"开始执行失败: {e}")
    
    def _finish_execution(self):
        """完成执行"""
        try:
            self.is_running = False
            self.execution_stats['end_time'] = time.time()
            
            if self.execution_stats['start_time']:
                self.execution_stats['total_time'] = (
                    self.execution_stats['end_time'] - self.execution_stats['start_time']
                )
            
            logger.info(f"并行执行完成: {self.execution_stats}")
            
        except Exception as e:
            logger.error(f"完成执行失败: {e}")
    
    def execute_custom_tasks(self, tasks: List[Callable], 
                           task_args: List[Tuple] = None,
                           task_kwargs: List[Dict] = None) -> List[Any]:
        """执行自定义任务"""
        try:
            if self.is_running:
                logger.warning("执行器正在运行中")
                return []
            
            if not self.executor:
                logger.error("执行器未初始化")
                return []
            
            # 开始执行
            self._start_execution()
            
            # 准备任务
            if task_args is None:
                task_args = [()] * len(tasks)
            if task_kwargs is None:
                task_kwargs = [{}] * len(tasks)
            
            # 提交任务
            futures = []
            for i, (task, args, kwargs) in enumerate(zip(tasks, task_args, task_kwargs)):
                future = self.executor.submit(task, *args, **kwargs)
                futures.append(future)
            
            # 等待完成
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    self.execution_stats['completed_tasks'] += 1
                except Exception as e:
                    logger.error(f"自定义任务执行失败: {e}")
                    results.append(None)
                    self.execution_stats['failed_tasks'] += 1
            
            # 完成执行
            self._finish_execution()
            
            return results
            
        except Exception as e:
            logger.error(f"自定义任务执行失败: {e}")
            return []
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        with self.lock:
            return self.execution_stats.copy()
    
    def get_task_results(self) -> Dict[str, Any]:
        """获取任务结果"""
        with self.lock:
            return self.task_results.copy()
    
    def get_task_errors(self) -> Dict[str, str]:
        """获取任务错误"""
        with self.lock:
            return self.task_errors.copy()
    
    def is_executor_running(self) -> bool:
        """检查执行器是否正在运行"""
        return self.is_running
    
    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        try:
            if self.executor:
                self.executor.shutdown(wait=wait)
                self.executor = None
            
            self.is_running = False
            logger.info("并行执行器已关闭")
            
        except Exception as e:
            logger.error(f"关闭执行器失败: {e}")
    
    def __del__(self):
        """析构函数"""
        self.shutdown(wait=False)
