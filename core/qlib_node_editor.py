#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib节点编辑器
严格按照设计文档实现
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List, Tuple, Type
from abc import ABC, abstractmethod
import json
import inspect

# 添加NodeGraphQt路径
try:
    nodegraphqt_path = os.path.join(os.path.dirname(__file__), '..', '..', 'RockXFWV21', 'NodeGraphQt')
    if os.path.exists(nodegraphqt_path):
        sys.path.insert(0, nodegraphqt_path)
    
    from NodeGraphQt import NodeGraph, BaseNode
    from NodeGraphQt.constants import NodePropWidgetEnum
    NODEGRAPH_AVAILABLE = True
except ImportError:
    NODEGRAPH_AVAILABLE = False
    BaseNode = object
    NodePropWidgetEnum = object

from .qlib_base_node import QlibBaseNode
from .qlib_workflow import QlibWorkflow

logger = logging.getLogger(__name__)

class QlibNodeEditor:
    """节点编辑器"""
    
    def __init__(self):
        self.node_graph = None
        self.property_editor = None
        self.node_toolbox = None
        self.registered_nodes = {}
        self.node_factory = {}
        
        # 初始化NodeGraphQt
        if NODEGRAPH_AVAILABLE:
            self._initialize_node_graph()
        
        # 注册默认节点
        self._register_default_nodes()
        
        logger.info("节点编辑器初始化完成")
    
    def _initialize_node_graph(self):
        """初始化NodeGraphQt图形界面"""
        try:
            self.node_graph = NodeGraph()
            self.node_graph.set_background_color(50, 50, 50)
            self.node_graph.set_grid_mode(True)
            logger.info("NodeGraphQt图形界面初始化成功")
        except Exception as e:
            logger.error(f"NodeGraphQt初始化失败: {e}")
            self.node_graph = None
    
    def _register_default_nodes(self):
        """注册默认节点类型"""
        try:
            # 导入所有可用的节点类型
            from ..nodes.qlib_data_nodes import (
                QlibAlphaNode, QlibHighFreqNode, QlibCustomDataNode,
                QlibProcessorNode, QlibFeatureNode, QlibNormalizeNode,
                QlibFilterNode, QlibCacheNode, QlibStorageNode
            )
            
            # 注册数据节点
            self.register_node_class(QlibAlphaNode, "数据/Alpha因子")
            self.register_node_class(QlibHighFreqNode, "数据/高频数据")
            self.register_node_class(QlibCustomDataNode, "数据/自定义数据")
            self.register_node_class(QlibProcessorNode, "数据/数据预处理")
            self.register_node_class(QlibFeatureNode, "数据/特征工程")
            self.register_node_class(QlibNormalizeNode, "数据/数据标准化")
            self.register_node_class(QlibFilterNode, "数据/数据过滤")
            self.register_node_class(QlibCacheNode, "数据/数据缓存")
            self.register_node_class(QlibStorageNode, "数据/数据存储")
            
            logger.info("默认节点类型注册完成")
            
        except Exception as e:
            logger.error(f"默认节点注册失败: {e}")
    
    def register_node_class(self, node_class: Type[QlibBaseNode], category: str = "其他"):
        """注册节点类"""
        try:
            if not issubclass(node_class, QlibBaseNode):
                logger.error(f"节点类必须继承自QlibBaseNode: {node_class}")
                return False
            
            # 创建节点包装器
            wrapper_class = self._create_node_wrapper(node_class)
            
            # 注册到NodeGraphQt
            if self.node_graph:
                self.node_graph.register_node(wrapper_class)
                self.node_graph.add_node_to_tree(wrapper_class, category)
            
            # 保存到注册表
            self.registered_nodes[node_class.__name__] = {
                'class': node_class,
                'wrapper': wrapper_class,
                'category': category
            }
            
            logger.info(f"节点类注册成功: {node_class.__name__} -> {category}")
            return True
            
        except Exception as e:
            logger.error(f"节点类注册失败: {e}")
            return False
    
    def _create_node_wrapper(self, node_class: Type[QlibBaseNode]):
        """创建节点包装器类"""
        
        class QlibNodeWrapper(BaseNode):
            """Qlib节点包装器"""
            
            # 节点属性
            __identifier__ = f"Qlib.{node_class.__name__}"
            NODE_NAME = node_class.__name__
            
            def __init__(self):
                super().__init__()
                
                # 创建底层Qlib节点
                self.qlib_node = node_class()
                
                # 设置节点属性
                self.set_name(self.qlib_node.get_name())
                self.set_color(*self.qlib_node.get_color())
                
                # 添加输入输出端口
                self._setup_ports()
                
                # 添加属性
                self._setup_properties()
            
            def _setup_ports(self):
                """设置输入输出端口"""
                # 添加输入端口
                for port_name, port_type in self.qlib_node.get_input_ports().items():
                    self.add_input(port_name)
                
                # 添加输出端口
                for port_name, port_type in self.qlib_node.get_output_ports().items():
                    self.add_output(port_name)
            
            def _setup_properties(self):
                """设置节点属性"""
                for prop_name, prop_info in self.qlib_node.get_rockx_properties().items():
                    prop_type = prop_info.get('type', str)
                    default_value = prop_info.get('default', '')
                    display_name = prop_info.get('display_name', prop_name)
                    tooltip = prop_info.get('tooltip', '')
                    
                    # 根据类型设置属性控件
                    widget_type = self._get_widget_type(prop_type)
                    
                    self.add_property(
                        prop_name,
                        default_value,
                        widget_type=widget_type,
                        tab='属性'
                    )
            
            def _get_widget_type(self, prop_type):
                """获取属性控件类型"""
                if not NODEGRAPH_AVAILABLE:
                    return NodePropWidgetEnum.LINE_EDIT.value
                
                if prop_type == bool:
                    return NodePropWidgetEnum.CHECKBOX.value
                elif prop_type == int:
                    return NodePropWidgetEnum.SPINBOX.value
                elif prop_type == float:
                    return NodePropWidgetEnum.DOUBLE_SPINBOX.value
                elif prop_type == list:
                    return NodePropWidgetEnum.LINE_EDIT.value
                elif prop_type == dict:
                    return NodePropWidgetEnum.LINE_EDIT.value
                else:
                    return NodePropWidgetEnum.LINE_EDIT.value
            
            def on_input_changed(self, input_port, data):
                """输入变化时的处理"""
                try:
                    # 更新底层节点输入
                    self.qlib_node.set_input(input_port.name(), data)
                    
                    # 执行节点
                    result = self.qlib_node.execute()
                    
                    # 更新输出端口
                    if result:
                        for output_port in self.output_ports():
                            output_data = self.qlib_node.get_output(output_port.name())
                            if output_data is not None:
                                output_port.set_value(output_data)
                    
                    # 更新节点状态
                    self._update_node_status()
                    
                except Exception as e:
                    logger.error(f"节点执行失败 {self.name()}: {e}")
                    self.set_tooltip(f"执行失败: {e}")
            
            def on_property_changed(self, property_name, property_value):
                """属性变化时的处理"""
                try:
                    # 更新底层节点属性
                    self.qlib_node.set_rockx_property(property_name, property_value)
                    
                    logger.info(f"属性更新: {property_name} = {property_value}")
                    
                except Exception as e:
                    logger.error(f"属性更新失败 {property_name}: {e}")
            
            def _update_node_status(self):
                """更新节点状态"""
                try:
                    status = self.qlib_node.get_status()
                    status_message = self.qlib_node.get_status_message()
                    
                    # 根据状态设置节点颜色
                    if status == "success":
                        self.set_color(0, 150, 0)  # 绿色
                    elif status == "failed":
                        self.set_color(150, 0, 0)  # 红色
                    elif status == "warning":
                        self.set_color(150, 150, 0)  # 黄色
                    else:
                        self.set_color(100, 100, 100)  # 灰色
                    
                    # 设置工具提示
                    self.set_tooltip(f"状态: {status}\n消息: {status_message}")
                    
                except Exception as e:
                    logger.error(f"状态更新失败: {e}")
            
            def execute(self):
                """执行节点"""
                try:
                    result = self.qlib_node.execute()
                    self._update_node_status()
                    return result
                except Exception as e:
                    logger.error(f"节点执行失败: {e}")
                    self.set_tooltip(f"执行失败: {e}")
                    return None
            
            def get_qlib_node(self):
                """获取底层Qlib节点"""
                return self.qlib_node
        
        return QlibNodeWrapper
    
    def create_node(self, node_type: str, position: Tuple[int, int] = None) -> Optional[Any]:
        """创建节点"""
        try:
            if node_type not in self.registered_nodes:
                logger.error(f"未注册的节点类型: {node_type}")
                return None
            
            if not self.node_graph:
                logger.error("NodeGraphQt未初始化")
                return None
            
            # 创建节点
            node = self.node_graph.create_node(node_type)
            
            # 设置位置
            if position:
                node.set_pos(*position)
            
            logger.info(f"节点创建成功: {node_type}")
            return node
            
        except Exception as e:
            logger.error(f"节点创建失败: {e}")
            return None
    
    def edit_node_properties(self, node: QlibBaseNode) -> Dict[str, Any]:
        """编辑节点属性"""
        try:
            if not node:
                logger.error("节点为空")
                return {}
            
            # 获取节点属性
            properties = node.get_all_properties()
            
            # 创建属性编辑器
            property_editor = {
                'node_id': node.get_node_id(),
                'node_name': node.get_name(),
                'properties': properties,
                'input_ports': node.get_input_ports(),
                'output_ports': node.get_output_ports(),
                'status': node.get_status(),
                'status_message': node.get_status_message()
            }
            
            logger.info(f"节点属性编辑: {node.get_node_id()}")
            return property_editor
            
        except Exception as e:
            logger.error(f"节点属性编辑失败: {e}")
            return {}
    
    def validate_node_connections(self, node: QlibBaseNode) -> bool:
        """验证节点连接"""
        try:
            if not node:
                logger.error("节点为空")
                return False
            
            # 验证输入端口
            input_ports = node.get_input_ports()
            for port_name, port_type in input_ports.items():
                input_data = node.get_input(port_name)
                if input_data is None:
                    logger.warning(f"输入端口 {port_name} 未连接")
                    continue
                
                # 验证数据类型
                if not self._validate_data_type(input_data, port_type):
                    logger.error(f"输入端口 {port_name} 数据类型不匹配")
                    return False
            
            # 验证输出端口
            output_ports = node.get_output_ports()
            for port_name, port_type in output_ports.items():
                output_data = node.get_output(port_name)
                if output_data is None:
                    logger.warning(f"输出端口 {port_name} 无数据")
                    continue
                
                # 验证数据类型
                if not self._validate_data_type(output_data, port_type):
                    logger.error(f"输出端口 {port_name} 数据类型不匹配")
                    return False
            
            logger.info(f"节点连接验证通过: {node.get_node_id()}")
            return True
            
        except Exception as e:
            logger.error(f"节点连接验证失败: {e}")
            return False
    
    def _validate_data_type(self, data: Any, expected_type: str) -> bool:
        """验证数据类型"""
        try:
            if expected_type == "dataframe":
                return isinstance(data, pd.DataFrame)
            elif expected_type == "series":
                return isinstance(data, pd.Series)
            elif expected_type == "array":
                return isinstance(data, (np.ndarray, list))
            elif expected_type == "dict":
                return isinstance(data, dict)
            elif expected_type == "str":
                return isinstance(data, str)
            elif expected_type == "int":
                return isinstance(data, int)
            elif expected_type == "float":
                return isinstance(data, float)
            elif expected_type == "bool":
                return isinstance(data, bool)
            else:
                return True  # 未知类型，默认通过
                
        except Exception as e:
            logger.warning(f"数据类型验证失败: {e}")
            return True
    
    def get_node_toolbox(self) -> Dict[str, List[str]]:
        """获取节点工具箱"""
        try:
            toolbox = {}
            
            for node_name, node_info in self.registered_nodes.items():
                category = node_info['category']
                if category not in toolbox:
                    toolbox[category] = []
                toolbox[category].append(node_name)
            
            logger.info(f"节点工具箱: {len(toolbox)} 个分类")
            return toolbox
            
        except Exception as e:
            logger.error(f"获取节点工具箱失败: {e}")
            return {}
    
    def get_node_info(self, node_type: str) -> Dict[str, Any]:
        """获取节点信息"""
        try:
            if node_type not in self.registered_nodes:
                logger.error(f"未注册的节点类型: {node_type}")
                return {}
            
            node_info = self.registered_nodes[node_type]
            node_class = node_info['class']
            
            # 创建临时节点实例获取信息
            temp_node = node_class()
            
            info = {
                'name': node_class.__name__,
                'category': node_info['category'],
                'description': temp_node.get_property('description', ''),
                'input_ports': temp_node.get_input_ports(),
                'output_ports': temp_node.get_output_ports(),
                'properties': temp_node.get_all_properties(),
                'docstring': node_class.__doc__ or ''
            }
            
            # 清理临时节点
            temp_node.cleanup()
            
            return info
            
        except Exception as e:
            logger.error(f"获取节点信息失败: {e}")
            return {}
    
    def create_workflow_from_graph(self) -> Optional[QlibWorkflow]:
        """从图形界面创建工作流"""
        try:
            if not self.node_graph:
                logger.error("NodeGraphQt未初始化")
                return None
            
            # 创建工作流
            workflow = QlibWorkflow("从图形界面创建的工作流")
            
            # 获取所有节点
            nodes = self.node_graph.all_nodes()
            
            # 添加节点到工作流
            for node in nodes:
                if hasattr(node, 'get_qlib_node'):
                    qlib_node = node.get_qlib_node()
                    workflow.add_node(qlib_node)
            
            # 获取所有连接
            connections = self.node_graph.all_connections()
            
            # 添加连接到工作流
            for connection in connections:
                from_node = connection.input_node()
                to_node = connection.output_node()
                from_port = connection.input_port()
                to_port = connection.output_port()
                
                if hasattr(from_node, 'get_qlib_node') and hasattr(to_node, 'get_qlib_node'):
                    from_qlib_node = from_node.get_qlib_node()
                    to_qlib_node = to_node.get_qlib_node()
                    
                    workflow.connect_nodes(
                        from_qlib_node.get_node_id(),
                        to_qlib_node.get_node_id(),
                        from_port.name(),
                        to_port.name()
                    )
            
            logger.info(f"从图形界面创建工作流成功: {len(nodes)} 个节点, {len(connections)} 个连接")
            return workflow
            
        except Exception as e:
            logger.error(f"从图形界面创建工作流失败: {e}")
            return None
    
    def load_workflow_to_graph(self, workflow: QlibWorkflow):
        """将工作流加载到图形界面"""
        try:
            if not self.node_graph:
                logger.error("NodeGraphQt未初始化")
                return False
            
            # 清空当前图形
            self.node_graph.clear()
            
            # 添加节点到图形界面
            node_mapping = {}
            for node_id, node in workflow.nodes.items():
                node_type = node.__class__.__name__
                if node_type in self.registered_nodes:
                    graph_node = self.create_node(node_type)
                    if graph_node:
                        node_mapping[node_id] = graph_node
            
            # 添加连接
            for (from_node_id, to_node_id), (from_port, to_port) in workflow.connections.items():
                if from_node_id in node_mapping and to_node_id in node_mapping:
                    from_graph_node = node_mapping[from_node_id]
                    to_graph_node = node_mapping[to_node_id]
                    
                    # 创建连接
                    self.node_graph.create_connection(
                        from_graph_node, from_port,
                        to_graph_node, to_port
                    )
            
            logger.info(f"工作流加载到图形界面成功: {len(node_mapping)} 个节点")
            return True
            
        except Exception as e:
            logger.error(f"工作流加载到图形界面失败: {e}")
            return False
    
    def get_graph_widget(self):
        """获取图形界面组件"""
        if self.node_graph:
            return self.node_graph.widget
        return None
    
    def get_available_nodes(self) -> List[str]:
        """获取可用节点列表"""
        return list(self.registered_nodes.keys())
    
    def get_node_categories(self) -> List[str]:
        """获取节点分类列表"""
        categories = set()
        for node_info in self.registered_nodes.values():
            categories.add(node_info['category'])
        return list(categories)
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.node_graph:
                self.node_graph.clear()
            
            self.registered_nodes.clear()
            self.node_factory.clear()
            
            logger.info("节点编辑器清理完成")
            
        except Exception as e:
            logger.error(f"节点编辑器清理失败: {e}")
