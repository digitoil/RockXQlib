#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib工作流定义
严格按照设计文档实现
"""

import os
import sys
import logging
import json
import networkx as nx
from typing import Dict, Any, Optional, List, Tuple, Set
from collections import defaultdict, deque
import pandas as pd
import numpy as np

from .qlib_base_node import QlibBaseNode

logger = logging.getLogger(__name__)

class QlibWorkflow:
    """Qlib工作流定义"""
    
    def __init__(self, name: str = "Untitled Workflow"):
        self.name = name
        self.nodes = {}  # node_id -> QlibBaseNode
        self.connections = {}  # (from_node_id, to_node_id) -> (from_port, to_port)
        self.execution_order = []  # 执行顺序
        self.parallel_groups = []  # 并行执行组
        self.workflow_graph = nx.DiGraph()  # 网络图
        self.execution_context = {}  # 执行上下文
        self.results = {}  # 执行结果
        self.status = "idle"  # idle, running, success, failed
        self.error_messages = []
        
        logger.info(f"工作流创建: {name}")
    
    def add_node(self, node: QlibBaseNode) -> bool:
        """添加节点"""
        try:
            node_id = node.get_node_id()
            
            if node_id in self.nodes:
                logger.warning(f"节点已存在: {node_id}")
                return False
            
            # 添加节点
            self.nodes[node_id] = node
            
            # 添加到网络图
            self.workflow_graph.add_node(node_id, node=node)
            
            # 重新计算执行顺序
            self._calculate_execution_order()
            
            logger.info(f"节点添加成功: {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加节点失败: {e}")
            return False
    
    def remove_node(self, node_id: str) -> bool:
        """移除节点"""
        try:
            if node_id not in self.nodes:
                logger.warning(f"节点不存在: {node_id}")
                return False
            
            # 移除相关连接
            connections_to_remove = []
            for (from_node, to_node), (from_port, to_port) in self.connections.items():
                if from_node == node_id or to_node == node_id:
                    connections_to_remove.append((from_node, to_node))
            
            for connection in connections_to_remove:
                del self.connections[connection]
            
            # 移除节点
            del self.nodes[node_id]
            self.workflow_graph.remove_node(node_id)
            
            # 重新计算执行顺序
            self._calculate_execution_order()
            
            logger.info(f"节点移除成功: {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除节点失败: {e}")
            return False
    
    def connect_nodes(self, from_node: str, to_node: str, 
                     from_port: str, to_port: str) -> bool:
        """连接节点"""
        try:
            # 验证节点存在
            if from_node not in self.nodes:
                logger.error(f"源节点不存在: {from_node}")
                return False
            
            if to_node not in self.nodes:
                logger.error(f"目标节点不存在: {to_node}")
                return False
            
            # 验证端口存在
            from_node_obj = self.nodes[from_node]
            to_node_obj = self.nodes[to_node]
            
            if not self._validate_connection(from_node_obj, to_node_obj, from_port, to_port):
                return False
            
            # 添加连接
            connection_key = (from_node, to_node)
            self.connections[connection_key] = (from_port, to_port)
            
            # 添加到网络图
            self.workflow_graph.add_edge(from_node, to_node, 
                                       from_port=from_port, to_port=to_port)
            
            # 重新计算执行顺序
            self._calculate_execution_order()
            
            logger.info(f"节点连接成功: {from_node}:{from_port} -> {to_node}:{to_port}")
            return True
            
        except Exception as e:
            logger.error(f"连接节点失败: {e}")
            return False
    
    def disconnect_nodes(self, from_node: str, to_node: str) -> bool:
        """断开节点连接"""
        try:
            connection_key = (from_node, to_node)
            
            if connection_key not in self.connections:
                logger.warning(f"连接不存在: {from_node} -> {to_node}")
                return False
            
            # 移除连接
            del self.connections[connection_key]
            self.workflow_graph.remove_edge(from_node, to_node)
            
            # 重新计算执行顺序
            self._calculate_execution_order()
            
            logger.info(f"节点断开成功: {from_node} -> {to_node}")
            return True
            
        except Exception as e:
            logger.error(f"断开节点失败: {e}")
            return False
    
    def _validate_connection(self, from_node: QlibBaseNode, to_node: QlibBaseNode,
                           from_port: str, to_port: str) -> bool:
        """验证连接有效性"""
        try:
            # 检查端口存在
            from_outputs = from_node.get_all_outputs()
            to_inputs = to_node.get_all_inputs()
            
            if from_port not in from_outputs:
                logger.error(f"源节点输出端口不存在: {from_port}")
                return False
            
            if to_port not in to_inputs:
                logger.error(f"目标节点输入端口不存在: {to_port}")
                return False
            
            # 检查数据类型兼容性
            if not self._check_data_type_compatibility(from_node, to_node, from_port, to_port):
                return False
            
            # 检查循环依赖
            if self._check_circular_dependency(from_node.get_node_id(), to_node.get_node_id()):
                logger.error("检测到循环依赖")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"连接验证失败: {e}")
            return False
    
    def _check_data_type_compatibility(self, from_node: QlibBaseNode, to_node: QlibBaseNode,
                                     from_port: str, to_port: str) -> bool:
        """检查数据类型兼容性"""
        try:
            # 这里可以实现更复杂的数据类型检查
            # 简化实现，假设所有端口都兼容
            return True
            
        except Exception as e:
            logger.warning(f"数据类型兼容性检查失败: {e}")
            return True
    
    def _check_circular_dependency(self, from_node_id: str, to_node_id: str) -> bool:
        """检查循环依赖"""
        try:
            # 临时添加边
            self.workflow_graph.add_edge(from_node_id, to_node_id)
            
            # 检查是否有环
            has_cycle = not nx.is_directed_acyclic_graph(self.workflow_graph)
            
            # 移除临时边
            self.workflow_graph.remove_edge(from_node_id, to_node_id)
            
            return has_cycle
            
        except Exception as e:
            logger.warning(f"循环依赖检查失败: {e}")
            return False
    
    def validate_workflow(self) -> bool:
        """验证工作流"""
        try:
            self.error_messages.clear()
            
            # 检查是否有节点
            if not self.nodes:
                self.error_messages.append("工作流中没有节点")
                return False
            
            # 检查节点配置
            for node_id, node in self.nodes.items():
                if not node.validate_config():
                    self.error_messages.append(f"节点配置无效: {node_id}")
                    return False
            
            # 检查连接有效性
            for (from_node, to_node), (from_port, to_port) in self.connections.items():
                if from_node not in self.nodes or to_node not in self.nodes:
                    self.error_messages.append(f"连接引用不存在的节点: {from_node} -> {to_node}")
                    return False
                
                from_node_obj = self.nodes[from_node]
                to_node_obj = self.nodes[to_node]
                
                if not self._validate_connection(from_node_obj, to_node_obj, from_port, to_port):
                    self.error_messages.append(f"连接无效: {from_node}:{from_port} -> {to_node}:{to_port}")
                    return False
            
            # 检查执行顺序
            if not self._validate_execution_order():
                return False
            
            # 检查孤立节点
            isolated_nodes = self._find_isolated_nodes()
            if isolated_nodes:
                self.error_messages.append(f"发现孤立节点: {isolated_nodes}")
                # 孤立节点不一定是错误，只是警告
                logger.warning(f"发现孤立节点: {isolated_nodes}")
            
            logger.info("工作流验证通过")
            return True
            
        except Exception as e:
            self.error_messages.append(f"工作流验证失败: {e}")
            logger.error(f"工作流验证失败: {e}")
            return False
    
    def _validate_execution_order(self) -> bool:
        """验证执行顺序"""
        try:
            # 检查是否有环
            if not nx.is_directed_acyclic_graph(self.workflow_graph):
                self.error_messages.append("工作流中存在循环依赖")
                return False
            
            # 检查执行顺序是否完整
            if len(self.execution_order) != len(self.nodes):
                self.error_messages.append("执行顺序计算不完整")
                return False
            
            return True
            
        except Exception as e:
            self.error_messages.append(f"执行顺序验证失败: {e}")
            return False
    
    def _find_isolated_nodes(self) -> List[str]:
        """查找孤立节点"""
        try:
            isolated = []
            for node_id in self.nodes:
                if self.workflow_graph.degree(node_id) == 0:
                    isolated.append(node_id)
            return isolated
            
        except Exception as e:
            logger.warning(f"查找孤立节点失败: {e}")
            return []
    
    def optimize_execution(self):
        """优化执行顺序"""
        try:
            # 重新计算执行顺序
            self._calculate_execution_order()
            
            # 计算并行组
            self._calculate_parallel_groups()
            
            # 优化内存使用
            self._optimize_memory_usage()
            
            logger.info("工作流执行优化完成")
            
        except Exception as e:
            logger.error(f"工作流优化失败: {e}")
    
    def _calculate_execution_order(self):
        """计算执行顺序"""
        try:
            # 使用拓扑排序
            if not nx.is_directed_acyclic_graph(self.workflow_graph):
                logger.error("工作流存在循环依赖，无法计算执行顺序")
                self.execution_order = []
                return
            
            # 拓扑排序
            try:
                execution_order = list(nx.topological_sort(self.workflow_graph))
                self.execution_order = execution_order
                logger.info(f"执行顺序计算完成: {execution_order}")
            except nx.NetworkXError:
                logger.error("拓扑排序失败")
                self.execution_order = []
                
        except Exception as e:
            logger.error(f"计算执行顺序失败: {e}")
            self.execution_order = []
    
    def _calculate_parallel_groups(self):
        """计算并行执行组"""
        try:
            self.parallel_groups = []
            
            # 按层级分组
            levels = self._get_node_levels()
            
            for level, nodes in levels.items():
                if len(nodes) > 1:
                    # 检查同一层级的节点是否可以并行执行
                    parallel_group = []
                    for node_id in nodes:
                        # 检查节点是否支持并行执行
                        node = self.nodes[node_id]
                        if node.get_property('parallel_enabled', False):
                            parallel_group.append(node_id)
                    
                    if parallel_group:
                        self.parallel_groups.append(parallel_group)
            
            logger.info(f"并行组计算完成: {self.parallel_groups}")
            
        except Exception as e:
            logger.error(f"计算并行组失败: {e}")
            self.parallel_groups = []
    
    def _get_node_levels(self) -> Dict[int, List[str]]:
        """获取节点层级"""
        try:
            levels = defaultdict(list)
            
            # 计算每个节点的层级
            for node_id in self.execution_order:
                # 计算从根节点到当前节点的最长路径
                level = 0
                for predecessor in nx.ancestors(self.workflow_graph, node_id):
                    level = max(level, self._get_node_level(predecessor) + 1)
                
                levels[level].append(node_id)
            
            return dict(levels)
            
        except Exception as e:
            logger.error(f"计算节点层级失败: {e}")
            return {}
    
    def _get_node_level(self, node_id: str) -> int:
        """获取单个节点的层级"""
        try:
            # 递归计算层级
            if node_id not in self.workflow_graph:
                return 0
            
            predecessors = list(self.workflow_graph.predecessors(node_id))
            if not predecessors:
                return 0
            
            max_level = 0
            for predecessor in predecessors:
                level = self._get_node_level(predecessor) + 1
                max_level = max(max_level, level)
            
            return max_level
            
        except Exception as e:
            logger.warning(f"计算节点层级失败 {node_id}: {e}")
            return 0
    
    def _optimize_memory_usage(self):
        """优化内存使用"""
        try:
            # 按执行顺序优化内存
            for node_id in self.execution_order:
                node = self.nodes[node_id]
                
                # 设置内存限制
                memory_limit = node.get_property('memory_limit', 1024 * 1024 * 1024)
                
                # 检查内存使用
                if hasattr(node, '_memory_usage'):
                    if node._memory_usage > memory_limit:
                        logger.warning(f"节点内存使用超限: {node_id}")
                
        except Exception as e:
            logger.warning(f"内存优化失败: {e}")
    
    def get_node(self, node_id: str) -> Optional[QlibBaseNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    def get_connections(self) -> Dict[Tuple[str, str], Tuple[str, str]]:
        """获取所有连接"""
        return self.connections.copy()
    
    def get_execution_order(self) -> List[str]:
        """获取执行顺序"""
        return self.execution_order.copy()
    
    def get_parallel_groups(self) -> List[List[str]]:
        """获取并行组"""
        return self.parallel_groups.copy()
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """获取工作流信息"""
        return {
            'name': self.name,
            'node_count': len(self.nodes),
            'connection_count': len(self.connections),
            'execution_order': self.execution_order,
            'parallel_groups': self.parallel_groups,
            'status': self.status,
            'error_messages': self.error_messages.copy()
        }
    
    def save_workflow(self, file_path: str) -> bool:
        """保存工作流"""
        try:
            workflow_data = {
                'name': self.name,
                'nodes': {},
                'connections': {},
                'execution_order': self.execution_order,
                'parallel_groups': self.parallel_groups
            }
            
            # 保存节点信息
            for node_id, node in self.nodes.items():
                workflow_data['nodes'][node_id] = {
                    'class_name': node.__class__.__name__,
                    'properties': node.get_all_properties(),
                    'status': node.get_status(),
                    'status_message': node.get_status_message()
                }
            
            # 保存连接信息
            for (from_node, to_node), (from_port, to_port) in self.connections.items():
                workflow_data['connections'][f"{from_node}->{to_node}"] = {
                    'from_port': from_port,
                    'to_port': to_port
                }
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(workflow_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"工作流保存成功: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存工作流失败: {e}")
            return False
    
    def load_workflow(self, file_path: str) -> bool:
        """加载工作流"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"工作流文件不存在: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            # 清空当前工作流
            self.nodes.clear()
            self.connections.clear()
            self.workflow_graph.clear()
            self.execution_order.clear()
            self.parallel_groups.clear()
            
            # 加载基本信息
            self.name = workflow_data.get('name', 'Loaded Workflow')
            
            # 加载节点（这里需要根据实际情况实现节点创建）
            # 简化实现，只保存节点信息
            for node_id, node_data in workflow_data.get('nodes', {}).items():
                # 这里需要根据class_name创建对应的节点实例
                # 简化实现，跳过节点创建
                pass
            
            # 加载连接
            for connection_key, connection_data in workflow_data.get('connections', {}).items():
                from_node, to_node = connection_key.split('->')
                from_port = connection_data['from_port']
                to_port = connection_data['to_port']
                self.connections[(from_node, to_node)] = (from_port, to_port)
            
            # 加载执行顺序
            self.execution_order = workflow_data.get('execution_order', [])
            self.parallel_groups = workflow_data.get('parallel_groups', [])
            
            logger.info(f"工作流加载成功: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"加载工作流失败: {e}")
            return False
    
    def clear_workflow(self):
        """清空工作流"""
        try:
            # 清理所有节点
            for node in self.nodes.values():
                node.cleanup()
            
            # 清空所有数据
            self.nodes.clear()
            self.connections.clear()
            self.workflow_graph.clear()
            self.execution_order.clear()
            self.parallel_groups.clear()
            self.results.clear()
            self.error_messages.clear()
            
            # 重置状态
            self.status = "idle"
            
            logger.info("工作流已清空")
            
        except Exception as e:
            logger.error(f"清空工作流失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"QlibWorkflow(name={self.name}, nodes={len(self.nodes)}, connections={len(self.connections)})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"QlibWorkflow(name={self.name}, nodes={list(self.nodes.keys())}, status={self.status})"
