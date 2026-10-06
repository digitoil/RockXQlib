#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib执行引擎
严格按照设计文档实现
"""

import os
import sys
import logging
import time
import threading
from typing import Dict, Any, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

from .qlib_base_node import QlibBaseNode
from .qlib_workflow import QlibWorkflow

logger = logging.getLogger(__name__)

class QlibExecutionEngine:
    """Qlib执行引擎"""
    
    def __init__(self, max_workers: int = None):
        self.workflow = None
        self.execution_context = {}
        self.cache_manager = None
        self.parallel_executor = None
        self.max_workers = max_workers or os.cpu_count()
        self.execution_thread = None
        self.is_running = False
        self.is_paused = False
        self.is_stopped = False
        self.execution_results = {}
        self.execution_errors = {}
        self.execution_stats = {
            'total_nodes': 0,
            'completed_nodes': 0,
            'failed_nodes': 0,
            'start_time': None,
            'end_time': None,
            'total_time': 0.0
        }
        
        # 初始化并行执行器
        self.parallel_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        logger.info(f"执行引擎初始化完成，最大工作线程数: {self.max_workers}")
    
    def execute_workflow(self, workflow: QlibWorkflow) -> Dict:
        """执行工作流"""
        try:
            if self.is_running:
                logger.warning("执行引擎正在运行中")
                return self.execution_results
            
            # 设置工作流
            self.workflow = workflow
            
            # 验证工作流
            if not workflow.validate_workflow():
                logger.error("工作流验证失败")
                return {}
            
            # 优化执行
            workflow.optimize_execution()
            
            # 初始化执行上下文
            self._initialize_execution_context()
            
            # 开始执行
            self._start_execution()
            
            # 等待执行完成
            self._wait_for_completion()
            
            return self.execution_results
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            return {}
    
    def _initialize_execution_context(self):
        """初始化执行上下文"""
        try:
            self.execution_context = {
                'workflow_id': id(self.workflow),
                'start_time': time.time(),
                'nodes': {},
                'connections': {},
                'data_flow': {},
                'memory_usage': 0,
                'error_count': 0
            }
            
            # 初始化节点上下文
            for node_id, node in self.workflow.nodes.items():
                self.execution_context['nodes'][node_id] = {
                    'status': 'pending',
                    'start_time': None,
                    'end_time': None,
                    'execution_time': 0.0,
                    'memory_usage': 0.0,
                    'inputs': {},
                    'outputs': {},
                    'error': None
                }
            
            # 初始化连接上下文
            for (from_node, to_node), (from_port, to_port) in self.workflow.connections.items():
                connection_key = f"{from_node}:{from_port}->{to_node}:{to_port}"
                self.execution_context['connections'][connection_key] = {
                    'from_node': from_node,
                    'to_node': to_node,
                    'from_port': from_port,
                    'to_port': to_port,
                    'data': None,
                    'status': 'pending'
                }
            
            logger.info("执行上下文初始化完成")
            
        except Exception as e:
            logger.error(f"执行上下文初始化失败: {e}")
    
    def _start_execution(self):
        """开始执行"""
        try:
            self.is_running = True
            self.is_paused = False
            self.is_stopped = False
            
            # 重置统计信息
            self.execution_stats = {
                'total_nodes': len(self.workflow.nodes),
                'completed_nodes': 0,
                'failed_nodes': 0,
                'start_time': time.time(),
                'end_time': None,
                'total_time': 0.0
            }
            
            # 清空结果
            self.execution_results.clear()
            self.execution_errors.clear()
            
            # 开始执行线程
            self.execution_thread = threading.Thread(target=self._execute_workflow_thread)
            self.execution_thread.start()
            
            logger.info("工作流执行开始")
            
        except Exception as e:
            logger.error(f"开始执行失败: {e}")
            self.is_running = False
    
    def _execute_workflow_thread(self):
        """执行工作流线程"""
        try:
            execution_order = self.workflow.get_execution_order()
            parallel_groups = self.workflow.get_parallel_groups()
            
            # 按顺序执行节点
            for i, node_id in enumerate(execution_order):
                if self.is_stopped:
                    break
                
                # 检查是否暂停
                while self.is_paused and not self.is_stopped:
                    time.sleep(0.1)
                
                if self.is_stopped:
                    break
                
                # 检查是否在并行组中
                parallel_group = self._find_parallel_group(node_id, parallel_groups)
                
                if parallel_group:
                    # 并行执行组
                    self._execute_parallel_group(parallel_group)
                else:
                    # 单个节点执行
                    self._execute_single_node(node_id)
            
            # 执行完成
            self._finish_execution()
            
        except Exception as e:
            logger.error(f"工作流执行线程失败: {e}")
            self._finish_execution()
    
    def _find_parallel_group(self, node_id: str, parallel_groups: List[List[str]]) -> Optional[List[str]]:
        """查找节点所属的并行组"""
        for group in parallel_groups:
            if node_id in group:
                return group
        return None
    
    def _execute_parallel_group(self, group: List[str]):
        """并行执行组"""
        try:
            logger.info(f"并行执行组: {group}")
            
            # 准备输入数据
            group_inputs = {}
            for node_id in group:
                inputs = self._prepare_node_inputs(node_id)
                group_inputs[node_id] = inputs
            
            # 并行执行
            futures = {}
            for node_id in group:
                if not self.is_stopped:
                    future = self.parallel_executor.submit(
                        self._execute_node_with_context, node_id, group_inputs[node_id]
                    )
                    futures[future] = node_id
            
            # 等待完成
            for future in as_completed(futures):
                if self.is_stopped:
                    break
                
                node_id = futures[future]
                try:
                    result = future.result()
                    self._handle_node_result(node_id, result)
                except Exception as e:
                    self._handle_node_error(node_id, e)
            
        except Exception as e:
            logger.error(f"并行组执行失败: {e}")
    
    def _execute_single_node(self, node_id: str):
        """执行单个节点"""
        try:
            logger.info(f"执行节点: {node_id}")
            
            # 准备输入数据
            inputs = self._prepare_node_inputs(node_id)
            
            # 执行节点
            result = self._execute_node_with_context(node_id, inputs)
            
            # 处理结果
            self._handle_node_result(node_id, result)
            
        except Exception as e:
            self._handle_node_error(node_id, e)
    
    def _prepare_node_inputs(self, node_id: str) -> Dict[str, Any]:
        """准备节点输入数据"""
        try:
            inputs = {}
            
            # 获取节点的所有输入连接
            for (from_node, to_node), (from_port, to_port) in self.workflow.connections.items():
                if to_node == node_id:
                    # 获取源节点的输出
                    source_output = self.execution_context['nodes'][from_node]['outputs'].get(from_port)
                    if source_output is not None:
                        inputs[to_port] = source_output
            
            return inputs
            
        except Exception as e:
            logger.error(f"准备节点输入失败 {node_id}: {e}")
            return {}
    
    def _execute_node_with_context(self, node_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """在上下文中执行节点"""
        try:
            # 更新节点状态
            self.execution_context['nodes'][node_id]['status'] = 'running'
            self.execution_context['nodes'][node_id]['start_time'] = time.time()
            
            # 获取节点
            node = self.workflow.get_node(node_id)
            if node is None:
                raise ValueError(f"节点不存在: {node_id}")
            
            # 执行节点
            result = node.execute(inputs)
            
            # 更新执行时间
            end_time = time.time()
            start_time = self.execution_context['nodes'][node_id]['start_time']
            execution_time = end_time - start_time
            
            self.execution_context['nodes'][node_id]['end_time'] = end_time
            self.execution_context['nodes'][node_id]['execution_time'] = execution_time
            
            return result
            
        except Exception as e:
            logger.error(f"节点执行失败 {node_id}: {e}")
            raise
    
    def _handle_node_result(self, node_id: str, result: Dict[str, Any]):
        """处理节点执行结果"""
        try:
            # 更新节点状态
            self.execution_context['nodes'][node_id]['status'] = 'completed'
            self.execution_context['nodes'][node_id]['outputs'] = result
            
            # 更新统计信息
            self.execution_stats['completed_nodes'] += 1
            
            # 保存结果
            self.execution_results[node_id] = result
            
            logger.info(f"节点执行完成: {node_id}")
            
        except Exception as e:
            logger.error(f"处理节点结果失败 {node_id}: {e}")
    
    def _handle_node_error(self, node_id: str, error: Exception):
        """处理节点执行错误"""
        try:
            # 更新节点状态
            self.execution_context['nodes'][node_id]['status'] = 'failed'
            self.execution_context['nodes'][node_id]['error'] = str(error)
            
            # 更新统计信息
            self.execution_stats['failed_nodes'] += 1
            
            # 保存错误
            self.execution_errors[node_id] = str(error)
            
            logger.error(f"节点执行失败: {node_id}, 错误: {error}")
            
        except Exception as e:
            logger.error(f"处理节点错误失败 {node_id}: {e}")
    
    def _finish_execution(self):
        """完成执行"""
        try:
            # 更新统计信息
            self.execution_stats['end_time'] = time.time()
            if self.execution_stats['start_time']:
                self.execution_stats['total_time'] = (
                    self.execution_stats['end_time'] - self.execution_stats['start_time']
                )
            
            # 更新状态
            self.is_running = False
            
            # 记录执行结果
            logger.info(f"工作流执行完成: {self.execution_stats}")
            
        except Exception as e:
            logger.error(f"完成执行失败: {e}")
    
    def _wait_for_completion(self, timeout: float = None):
        """等待执行完成"""
        try:
            if self.execution_thread and self.execution_thread.is_alive():
                self.execution_thread.join(timeout=timeout)
            
        except Exception as e:
            logger.error(f"等待执行完成失败: {e}")
    
    def execute_node(self, node: QlibBaseNode, inputs: Dict) -> Dict:
        """执行单个节点"""
        try:
            if self.is_running:
                logger.warning("执行引擎正在运行中，无法执行单个节点")
                return {}
            
            # 准备执行环境
            if not node.prepare_execution():
                return {}
            
            # 执行节点
            result = node.execute(inputs)
            
            # 清理资源
            node.cleanup()
            
            return result
            
        except Exception as e:
            logger.error(f"单个节点执行失败: {e}")
            return {}
    
    def execute_parallel(self, nodes: List[QlibBaseNode]) -> Dict:
        """并行执行节点"""
        try:
            if self.is_running:
                logger.warning("执行引擎正在运行中，无法并行执行节点")
                return {}
            
            results = {}
            futures = {}
            
            # 提交任务
            for i, node in enumerate(nodes):
                future = self.parallel_executor.submit(self.execute_node, node, {})
                futures[future] = i
            
            # 等待完成
            for future in as_completed(futures):
                node_index = futures[future]
                try:
                    result = future.result()
                    results[node_index] = result
                except Exception as e:
                    logger.error(f"并行节点执行失败 {node_index}: {e}")
                    results[node_index] = {}
            
            return results
            
        except Exception as e:
            logger.error(f"并行执行失败: {e}")
            return {}
    
    def pause_execution(self):
        """暂停执行"""
        try:
            if self.is_running and not self.is_paused:
                self.is_paused = True
                logger.info("执行已暂停")
            
        except Exception as e:
            logger.error(f"暂停执行失败: {e}")
    
    def resume_execution(self):
        """恢复执行"""
        try:
            if self.is_running and self.is_paused:
                self.is_paused = False
                logger.info("执行已恢复")
            
        except Exception as e:
            logger.error(f"恢复执行失败: {e}")
    
    def stop_execution(self):
        """停止执行"""
        try:
            if self.is_running:
                self.is_stopped = True
                self.is_paused = False
                logger.info("执行已停止")
            
        except Exception as e:
            logger.error(f"停止执行失败: {e}")
    
    def get_execution_status(self) -> Dict[str, Any]:
        """获取执行状态"""
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'is_stopped': self.is_stopped,
            'stats': self.execution_stats.copy(),
            'results_count': len(self.execution_results),
            'errors_count': len(self.execution_errors)
        }
    
    def get_execution_results(self) -> Dict[str, Any]:
        """获取执行结果"""
        return self.execution_results.copy()
    
    def get_execution_errors(self) -> Dict[str, str]:
        """获取执行错误"""
        return self.execution_errors.copy()
    
    def get_node_status(self, node_id: str) -> Dict[str, Any]:
        """获取节点状态"""
        if node_id in self.execution_context.get('nodes', {}):
            return self.execution_context['nodes'][node_id].copy()
        return {}
    
    def cleanup(self):
        """清理执行引擎"""
        try:
            # 停止执行
            self.stop_execution()
            
            # 等待线程结束
            if self.execution_thread and self.execution_thread.is_alive():
                self.execution_thread.join(timeout=5.0)
            
            # 关闭并行执行器
            if self.parallel_executor:
                self.parallel_executor.shutdown(wait=True)
            
            # 清理上下文
            self.execution_context.clear()
            self.execution_results.clear()
            self.execution_errors.clear()
            
            logger.info("执行引擎清理完成")
            
        except Exception as e:
            logger.error(f"执行引擎清理失败: {e}")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()
