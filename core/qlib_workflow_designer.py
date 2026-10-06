#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib工作流设计器
严格按照设计文档实现
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List, Tuple
import json
import time
from datetime import datetime

from .qlib_workflow import QlibWorkflow
# 避免导入Qt相关的节点编辑器
# from .qlib_node_editor import QlibNodeEditor

logger = logging.getLogger(__name__)

class QlibWorkflowDesigner:
    """工作流设计器"""
    
    def __init__(self, design_dir: str = "./workflows"):
        self.design_dir = design_dir
        self.canvas = None
        self.toolbox = None
        self.property_panel = None
        # 避免创建Qt相关的节点编辑器
        self.node_editor = None
        self.current_workflow = None
        self.workflow_templates = {}
        
        # 创建设计目录
        os.makedirs(design_dir, exist_ok=True)
        
        # 加载工作流模板
        self._load_workflow_templates()
        
        logger.info(f"工作流设计器初始化完成: {design_dir}")
    
    def _load_workflow_templates(self):
        """加载工作流模板"""
        try:
            templates_file = os.path.join(self.design_dir, "templates.json")
            
            if os.path.exists(templates_file):
                with open(templates_file, 'r', encoding='utf-8') as f:
                    self.workflow_templates = json.load(f)
                
                logger.info(f"加载了 {len(self.workflow_templates)} 个工作流模板")
            else:
                # 创建默认模板
                self._create_default_templates()
                
        except Exception as e:
            logger.error(f"加载工作流模板失败: {e}")
            self.workflow_templates = {}
    
    def _create_default_templates(self):
        """创建默认工作流模板"""
        try:
            # 数据预处理模板
            self.workflow_templates["数据预处理"] = {
                "name": "数据预处理工作流",
                "description": "标准的数据预处理工作流",
                "nodes": [
                    {"type": "QlibAlphaNode", "name": "Alpha数据", "position": [100, 100]},
                    {"type": "QlibProcessorNode", "name": "数据预处理", "position": [300, 100]},
                    {"type": "QlibNormalizeNode", "name": "数据标准化", "position": [500, 100]},
                    {"type": "QlibFeatureNode", "name": "特征工程", "position": [700, 100]}
                ],
                "connections": [
                    {"from": "Alpha数据", "to": "数据预处理", "from_port": "alpha_data", "to_port": "data"},
                    {"from": "数据预处理", "to": "数据标准化", "from_port": "processed_data", "to_port": "data"},
                    {"from": "数据标准化", "to": "特征工程", "from_port": "normalized_data", "to_port": "data"}
                ]
            }
            
            # 模型训练模板
            self.workflow_templates["模型训练"] = {
                "name": "模型训练工作流",
                "description": "标准的模型训练工作流",
                "nodes": [
                    {"type": "QlibDataNode", "name": "训练数据", "position": [100, 100]},
                    {"type": "QlibModelNode", "name": "模型训练", "position": [300, 100]},
                    {"type": "QlibModelNode", "name": "模型评估", "position": [500, 100]}
                ],
                "connections": [
                    {"from": "训练数据", "to": "模型训练", "from_port": "data", "to_port": "train_data"},
                    {"from": "模型训练", "to": "模型评估", "from_port": "model", "to_port": "model"}
                ]
            }
            
            # 保存模板
            self._save_workflow_templates()
            
        except Exception as e:
            logger.error(f"创建默认模板失败: {e}")
    
    def _save_workflow_templates(self):
        """保存工作流模板"""
        try:
            templates_file = os.path.join(self.design_dir, "templates.json")
            
            with open(templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.workflow_templates, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"保存工作流模板失败: {e}")
    
    def design_workflow(self) -> QlibWorkflow:
        """设计工作流"""
        try:
            # 创建新的工作流
            workflow_name = f"工作流_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            workflow = QlibWorkflow(workflow_name)
            
            # 设置当前工作流
            self.current_workflow = workflow
            
            logger.info(f"开始设计工作流: {workflow_name}")
            return workflow
            
        except Exception as e:
            logger.error(f"设计工作流失败: {e}")
            return None
    
    def create_workflow_from_template(self, template_name: str) -> Optional[QlibWorkflow]:
        """从模板创建工作流"""
        try:
            if template_name not in self.workflow_templates:
                logger.error(f"模板不存在: {template_name}")
                return None
            
            template = self.workflow_templates[template_name]
            
            # 创建工作流
            workflow_name = f"{template['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            workflow = QlibWorkflow(workflow_name)
            
            # 创建节点
            node_mapping = {}
            for node_config in template['nodes']:
                node_type = node_config['type']
                node_name = node_config['name']
                position = node_config.get('position', [100, 100])
                
                # 创建节点
                node = self._create_node_from_type(node_type)
                if node:
                    node.set_property('name', node_name)
                    workflow.add_node(node)
                    node_mapping[node_name] = node
            
            # 创建连接
            for connection_config in template['connections']:
                from_name = connection_config['from']
                to_name = connection_config['to']
                from_port = connection_config['from_port']
                to_port = connection_config['to_port']
                
                if from_name in node_mapping and to_name in node_mapping:
                    from_node = node_mapping[from_name]
                    to_node = node_mapping[to_name]
                    
                    workflow.connect_nodes(
                        from_node.get_node_id(),
                        to_node.get_node_id(),
                        from_port,
                        to_port
                    )
            
            self.current_workflow = workflow
            logger.info(f"从模板创建工作流成功: {workflow_name}")
            return workflow
            
        except Exception as e:
            logger.error(f"从模板创建工作流失败: {e}")
            return None
    
    def _create_node_from_type(self, node_type: str):
        """根据类型创建节点"""
        try:
            # 导入节点类
            if node_type == "QlibAlphaNode":
                from ..nodes.qlib_data_nodes import QlibAlphaNode
                return QlibAlphaNode()
            elif node_type == "QlibHighFreqNode":
                from ..nodes.qlib_data_nodes import QlibHighFreqNode
                return QlibHighFreqNode()
            elif node_type == "QlibCustomDataNode":
                from ..nodes.qlib_data_nodes import QlibCustomDataNode
                return QlibCustomDataNode()
            elif node_type == "QlibProcessorNode":
                from ..nodes.qlib_data_nodes import QlibProcessorNode
                return QlibProcessorNode()
            elif node_type == "QlibNormalizeNode":
                from ..nodes.qlib_data_nodes import QlibNormalizeNode
                return QlibNormalizeNode()
            elif node_type == "QlibFeatureNode":
                from ..nodes.qlib_data_nodes import QlibFeatureNode
                return QlibFeatureNode()
            elif node_type == "QlibFilterNode":
                from ..nodes.qlib_data_nodes import QlibFilterNode
                return QlibFilterNode()
            elif node_type == "QlibCacheNode":
                from ..nodes.qlib_data_nodes import QlibCacheNode
                return QlibCacheNode()
            elif node_type == "QlibStorageNode":
                from ..nodes.qlib_data_nodes import QlibStorageNode
                return QlibStorageNode()
            else:
                logger.error(f"不支持的节点类型: {node_type}")
                return None
                
        except Exception as e:
            logger.error(f"创建节点失败: {e}")
            return None
    
    def add_node_to_workflow(self, workflow: QlibWorkflow, node_type: str, 
                            position: Tuple[int, int] = None) -> bool:
        """添加节点到工作流"""
        try:
            if not workflow:
                logger.error("工作流为空")
                return False
            
            # 创建节点
            node = self._create_node_from_type(node_type)
            if not node:
                return False
            
            # 设置位置属性
            if position:
                node.set_property('position_x', position[0])
                node.set_property('position_y', position[1])
            
            # 添加到工作流
            success = workflow.add_node(node)
            if success:
                logger.info(f"节点添加到工作流成功: {node_type}")
            
            return success
            
        except Exception as e:
            logger.error(f"添加节点到工作流失败: {e}")
            return False
    
    def connect_nodes_in_workflow(self, workflow: QlibWorkflow, 
                                from_node_id: str, to_node_id: str,
                                from_port: str, to_port: str) -> bool:
        """在工作流中连接节点"""
        try:
            if not workflow:
                logger.error("工作流为空")
                return False
            
            # 连接节点
            success = workflow.connect_nodes(from_node_id, to_node_id, from_port, to_port)
            if success:
                logger.info(f"节点连接成功: {from_node_id} -> {to_node_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"连接节点失败: {e}")
            return False
    
    def validate_workflow_design(self, workflow: QlibWorkflow) -> Dict[str, Any]:
        """验证工作流设计"""
        try:
            if not workflow:
                return {'valid': False, 'errors': ['工作流为空']}
            
            # 验证工作流
            is_valid = workflow.validate_workflow()
            
            # 获取验证结果
            validation_result = {
                'valid': is_valid,
                'errors': workflow.error_messages.copy(),
                'warnings': [],
                'node_count': len(workflow.nodes),
                'connection_count': len(workflow.connections),
                'execution_order': workflow.get_execution_order(),
                'parallel_groups': workflow.get_parallel_groups()
            }
            
            # 检查孤立节点
            isolated_nodes = []
            for node_id, node in workflow.nodes.items():
                # 检查是否有输入或输出连接
                has_input = any(to_node == node_id for from_node, to_node in workflow.connections.keys())
                has_output = any(from_node == node_id for from_node, to_node in workflow.connections.keys())
                
                if not has_input and not has_output:
                    isolated_nodes.append(node_id)
            
            if isolated_nodes:
                validation_result['warnings'].append(f"发现孤立节点: {isolated_nodes}")
            
            logger.info(f"工作流设计验证: {'通过' if is_valid else '失败'}")
            return validation_result
            
        except Exception as e:
            logger.error(f"验证工作流设计失败: {e}")
            return {'valid': False, 'errors': [f'验证失败: {e}']}
    
    def optimize_workflow_design(self, workflow: QlibWorkflow) -> Dict[str, Any]:
        """优化工作流设计"""
        try:
            if not workflow:
                return {'success': False, 'message': '工作流为空'}
            
            # 执行优化
            workflow.optimize_execution()
            
            # 获取优化结果
            optimization_result = {
                'success': True,
                'execution_order': workflow.get_execution_order(),
                'parallel_groups': workflow.get_parallel_groups(),
                'node_count': len(workflow.nodes),
                'connection_count': len(workflow.connections),
                'optimization_suggestions': []
            }
            
            # 生成优化建议
            suggestions = []
            
            # 检查并行执行机会
            parallel_groups = workflow.get_parallel_groups()
            if parallel_groups:
                suggestions.append(f"发现 {len(parallel_groups)} 个并行执行组")
            
            # 检查缓存机会
            cache_nodes = [node for node in workflow.nodes.values() 
                          if hasattr(node, 'get_property') and 
                          node.get_property('cache_enabled', False)]
            if cache_nodes:
                suggestions.append(f"发现 {len(cache_nodes)} 个可缓存节点")
            
            # 检查内存使用
            large_nodes = []
            for node in workflow.nodes.values():
                if hasattr(node, 'get_property'):
                    memory_limit = node.get_property('memory_limit', 0)
                    if memory_limit > 1024 * 1024 * 1024:  # 1GB
                        large_nodes.append(node.get_node_id())
            
            if large_nodes:
                suggestions.append(f"发现 {len(large_nodes)} 个高内存使用节点")
            
            optimization_result['optimization_suggestions'] = suggestions
            
            logger.info(f"工作流设计优化完成: {len(suggestions)} 个建议")
            return optimization_result
            
        except Exception as e:
            logger.error(f"优化工作流设计失败: {e}")
            return {'success': False, 'message': f'优化失败: {e}'}
    
    def save_workflow(self, workflow: QlibWorkflow, path: str) -> bool:
        """保存工作流"""
        try:
            if not workflow:
                logger.error("工作流为空")
                return False
            
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # 保存工作流
            success = workflow.save_workflow(path)
            if success:
                logger.info(f"工作流保存成功: {path}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存工作流失败: {e}")
            return False
    
    def load_workflow(self, path: str) -> Optional[QlibWorkflow]:
        """加载工作流"""
        try:
            if not os.path.exists(path):
                logger.error(f"工作流文件不存在: {path}")
                return None
            
            # 创建工作流
            workflow = QlibWorkflow("加载的工作流")
            
            # 加载工作流
            success = workflow.load_workflow(path)
            if success:
                self.current_workflow = workflow
                logger.info(f"工作流加载成功: {path}")
                return workflow
            else:
                logger.error(f"工作流加载失败: {path}")
                return None
                
        except Exception as e:
            logger.error(f"加载工作流失败: {e}")
            return None
    
    def create_workflow_template(self, name: str, workflow: QlibWorkflow, 
                               description: str = "") -> bool:
        """创建工作流模板"""
        try:
            if not workflow:
                logger.error("工作流为空")
                return False
            
            # 创建工作流模板
            template = {
                "name": name,
                "description": description,
                "created_time": datetime.now().isoformat(),
                "nodes": [],
                "connections": []
            }
            
            # 添加节点信息
            for node_id, node in workflow.nodes.items():
                node_info = {
                    "type": node.__class__.__name__,
                    "name": node.get_property('name', node_id),
                    "position": [
                        node.get_property('position_x', 100),
                        node.get_property('position_y', 100)
                    ],
                    "properties": node.get_all_properties()
                }
                template["nodes"].append(node_info)
            
            # 添加连接信息
            for (from_node_id, to_node_id), (from_port, to_port) in workflow.connections.items():
                from_node = workflow.get_node(from_node_id)
                to_node = workflow.get_node(to_node_id)
                
                if from_node and to_node:
                    connection_info = {
                        "from": from_node.get_property('name', from_node_id),
                        "to": to_node.get_property('name', to_node_id),
                        "from_port": from_port,
                        "to_port": to_port
                    }
                    template["connections"].append(connection_info)
            
            # 保存模板
            self.workflow_templates[name] = template
            self._save_workflow_templates()
            
            logger.info(f"工作流模板创建成功: {name}")
            return True
            
        except Exception as e:
            logger.error(f"创建工作流模板失败: {e}")
            return False
    
    def get_workflow_templates(self) -> Dict[str, Any]:
        """获取工作流模板列表"""
        return self.workflow_templates.copy()
    
    def get_available_node_types(self) -> List[str]:
        """获取可用节点类型列表"""
        # 返回默认的节点类型列表
        return [
            'QlibAlphaNode', 'QlibHighFreqNode', 'QlibCustomDataNode',
            'QlibProcessorNode', 'QlibFeatureNode', 'QlibNormalizeNode',
            'QlibFilterNode', 'QlibCacheNode', 'QlibStorageNode'
        ]
    
    def get_node_categories(self) -> List[str]:
        """获取节点分类列表"""
        return ['数据', '模型', '策略', '回测']
    
    def get_workflow_statistics(self, workflow: QlibWorkflow) -> Dict[str, Any]:
        """获取工作流统计信息"""
        try:
            if not workflow:
                return {}
            
            # 统计节点类型
            node_types = {}
            for node in workflow.nodes.values():
                node_type = node.__class__.__name__
                node_types[node_type] = node_types.get(node_type, 0) + 1
            
            # 统计连接
            connection_stats = {
                'total_connections': len(workflow.connections),
                'input_connections': 0,
                'output_connections': 0
            }
            
            for (from_node, to_node), (from_port, to_port) in workflow.connections.items():
                connection_stats['input_connections'] += 1
                connection_stats['output_connections'] += 1
            
            # 执行顺序统计
            execution_order = workflow.get_execution_order()
            parallel_groups = workflow.get_parallel_groups()
            
            statistics = {
                'node_count': len(workflow.nodes),
                'connection_count': len(workflow.connections),
                'node_types': node_types,
                'connection_stats': connection_stats,
                'execution_order_length': len(execution_order),
                'parallel_groups_count': len(parallel_groups),
                'workflow_complexity': len(workflow.nodes) * len(workflow.connections)
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"获取工作流统计信息失败: {e}")
            return {}
    
    def export_workflow_diagram(self, workflow: QlibWorkflow, output_path: str) -> bool:
        """导出工作流图表"""
        try:
            if not workflow:
                logger.error("工作流为空")
                return False
            
            # 创建工作流图表数据
            diagram_data = {
                'nodes': [],
                'connections': [],
                'metadata': {
                    'name': workflow.name,
                    'node_count': len(workflow.nodes),
                    'connection_count': len(workflow.connections),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            # 添加节点信息
            for node_id, node in workflow.nodes.items():
                node_info = {
                    'id': node_id,
                    'name': node.get_property('name', node_id),
                    'type': node.__class__.__name__,
                    'position': [
                        node.get_property('position_x', 100),
                        node.get_property('position_y', 100)
                    ],
                    'properties': node.get_all_properties(),
                    'status': node.get_status()
                }
                diagram_data['nodes'].append(node_info)
            
            # 添加连接信息
            for (from_node_id, to_node_id), (from_port, to_port) in workflow.connections.items():
                connection_info = {
                    'from_node': from_node_id,
                    'to_node': to_node_id,
                    'from_port': from_port,
                    'to_port': to_port
                }
                diagram_data['connections'].append(connection_info)
            
            # 保存图表数据
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(diagram_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"工作流图表导出成功: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出工作流图表失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理资源（避免Qt依赖）
            pass
            
            self.current_workflow = None
            self.workflow_templates.clear()
            
            logger.info("工作流设计器清理完成")
            
        except Exception as e:
            logger.error(f"工作流设计器清理失败: {e}")
