#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 图形界面核心
基于NodeGraphQt的图形节点编辑器
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional

# 添加NodeGraphQt路径
try:
    # 尝试从RockXFWV21导入NodeGraphQt
    nodegraphqt_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'RockXFWV21', 'NodeGraphQt')
    if os.path.exists(nodegraphqt_path):
        sys.path.insert(0, nodegraphqt_path)
    
    from NodeGraphQt import NodeGraph, BaseNode
    from NodeGraphQt.constants import NodePropWidgetEnum
    NODEGRAPH_AVAILABLE = True
except ImportError:
    NODEGRAPH_AVAILABLE = False
    BaseNode = object
    NodeGraph = object
    NodePropWidgetEnum = object

logger = logging.getLogger(__name__)

class RockXQlibGraph:
    """RockXQlib图形界面核心类"""
    
    def __init__(self):
        if not NODEGRAPH_AVAILABLE:
            raise ImportError("NodeGraphQt not available. Please install NodeGraphQt.")
        
        self.graph = NodeGraph()
        self.node_wrappers = {}
        self.setup_graph()
    
    def setup_graph(self):
        """设置图形界面"""
        # 设置图形界面属性
        self.graph.set_background_color(50, 50, 50)
        self.graph.set_grid_mode(True)
        
        # 注册自定义节点
        self.register_custom_nodes()
        
        logger.info("✅ RockXQlib图形界面初始化成功")
    
    def register_custom_nodes(self):
        """注册自定义节点"""
        try:
            # 导入所有RockXQlib节点
            from ..nodes.data_nodes import (
                RockXQlibDataNode, RockXQlibAlphaNode, 
                RockXQlibHighFreqNode, RockXQlibCustomDataNode
            )
            from ..nodes.model_nodes import (
                RockXQlibModelNode, RockXQlibLinearNode, RockXQlibTreeNode,
                RockXQlibLSTMNode, RockXQlibTransformerNode, 
                RockXQlibDNNNode, RockXQlibTabNetNode
            )
            from ..nodes.strategy_nodes import (
                RockXQlibStrategyNode, RockXQlibSignalNode,
                RockXQlibPortfolioNode, RockXQlibRiskNode
            )
            from ..nodes.backtest_nodes import (
                RockXQlibBacktestNode, RockXQlibSimulatorNode, RockXQlibAnalysisNode
            )
            
            # 注册数据节点
            self.register_node_class(RockXQlibDataNode, "数据/基础数据")
            self.register_node_class(RockXQlibAlphaNode, "数据/Alpha因子")
            self.register_node_class(RockXQlibHighFreqNode, "数据/高频数据")
            self.register_node_class(RockXQlibCustomDataNode, "数据/自定义数据")
            
            # 注册模型节点
            self.register_node_class(RockXQlibModelNode, "模型/基础模型")
            self.register_node_class(RockXQlibLinearNode, "模型/线性模型")
            self.register_node_class(RockXQlibTreeNode, "模型/树模型")
            self.register_node_class(RockXQlibLSTMNode, "模型/LSTM模型")
            self.register_node_class(RockXQlibTransformerNode, "模型/Transformer")
            self.register_node_class(RockXQlibDNNNode, "模型/深度神经网络")
            self.register_node_class(RockXQlibTabNetNode, "模型/TabNet")
            
            # 注册策略节点
            self.register_node_class(RockXQlibStrategyNode, "策略/基础策略")
            self.register_node_class(RockXQlibSignalNode, "策略/信号生成")
            self.register_node_class(RockXQlibPortfolioNode, "策略/组合管理")
            self.register_node_class(RockXQlibRiskNode, "策略/风险管理")
            
            # 注册回测节点
            self.register_node_class(RockXQlibBacktestNode, "回测/回测执行")
            self.register_node_class(RockXQlibSimulatorNode, "回测/模拟器")
            self.register_node_class(RockXQlibAnalysisNode, "回测/结果分析")
            
            logger.info("✅ 所有RockXQlib节点注册成功")
            
        except Exception as e:
            logger.error(f"❌ 节点注册失败: {e}")
    
    def register_node_class(self, node_class, category):
        """注册单个节点类"""
        try:
            # 创建节点包装器
            wrapper_class = self.create_node_wrapper(node_class)
            
            # 注册到NodeGraphQt
            self.graph.register_node(wrapper_class)
            
            # 添加到节点树
            self.graph.add_node_to_tree(wrapper_class, category)
            
            logger.info(f"✅ 节点注册成功: {node_class.__name__} -> {category}")
            
        except Exception as e:
            logger.error(f"❌ 节点注册失败 {node_class.__name__}: {e}")
    
    def create_node_wrapper(self, node_class):
        """创建节点包装器类"""
        
        class RockXQlibNodeWrapper(BaseNode):
            """RockXQlib节点包装器"""
            
            # 节点属性
            __identifier__ = f"RockXQlib.{node_class.__name__}"
            NODE_NAME = node_class.__name__
            
            def __init__(self):
                super().__init__()
                
                # 创建底层RockXQlib节点
                self.rockx_node = node_class()
                
                # 设置节点属性
                self.set_name(self.rockx_node.get_name())
                self.set_color(*self.rockx_node.get_color())
                
                # 添加输入输出端口
                self.setup_ports()
                
                # 添加属性
                self.setup_properties()
            
            def setup_ports(self):
                """设置输入输出端口"""
                # 添加输入端口
                for port_name, port_type in self.rockx_node.get_input_ports().items():
                    self.add_input(port_name)
                
                # 添加输出端口
                for port_name, port_type in self.rockx_node.get_output_ports().items():
                    self.add_output(port_name)
            
            def setup_properties(self):
                """设置节点属性"""
                for prop_name, prop_info in self.rockx_node.get_rockx_properties().items():
                    prop_type = prop_info.get('type', str)
                    default_value = prop_info.get('default', '')
                    display_name = prop_info.get('display_name', prop_name)
                    tooltip = prop_info.get('tooltip', '')
                    
                    # 根据类型设置属性
                    if prop_type == bool:
                        self.add_property(
                            prop_name, 
                            default_value, 
                            widget_type=NodePropWidgetEnum.CHECKBOX.value,
                            tab='属性'
                        )
                    elif prop_type == int:
                        self.add_property(
                            prop_name, 
                            default_value, 
                            widget_type=NodePropWidgetEnum.SPINBOX.value,
                            tab='属性'
                        )
                    elif prop_type == float:
                        self.add_property(
                            prop_name, 
                            default_value, 
                            widget_type=NodePropWidgetEnum.DOUBLE_SPINBOX.value,
                            tab='属性'
                        )
                    else:
                        self.add_property(
                            prop_name, 
                            default_value, 
                            widget_type=NodePropWidgetEnum.LINE_EDIT.value,
                            tab='属性'
                        )
            
            def on_input_changed(self, input_port, data):
                """输入变化时的处理"""
                try:
                    # 更新底层节点输入
                    self.rockx_node.set_input(input_port.name(), data)
                    
                    # 执行节点
                    result = self.rockx_node.execute()
                    
                    # 更新输出端口
                    if result:
                        for output_port in self.output_ports():
                            output_data = self.rockx_node.get_output(output_port.name())
                            if output_data is not None:
                                output_port.set_value(output_data)
                    
                except Exception as e:
                    logger.error(f"节点执行失败 {self.name()}: {e}")
            
            def on_property_changed(self, property_name, property_value):
                """属性变化时的处理"""
                try:
                    # 更新底层节点属性
                    self.rockx_node.set_rockx_property(property_name, property_value)
                    
                except Exception as e:
                    logger.error(f"属性更新失败 {property_name}: {e}")
        
        return RockXQlibNodeWrapper
    
    def add_node(self, node_type, position=None):
        """添加节点到图形界面"""
        try:
            # 创建节点
            node = self.graph.create_node(node_type)
            
            # 设置位置
            if position:
                node.set_pos(*position)
            
            logger.info(f"✅ 节点添加成功: {node_type}")
            return node
            
        except Exception as e:
            logger.error(f"❌ 节点添加失败: {e}")
            return None
    
    def connect_nodes(self, output_node, output_port, input_node, input_port):
        """连接两个节点"""
        try:
            # 创建连接
            connection = self.graph.create_connection(
                output_node, output_port, input_node, input_port
            )
            
            logger.info(f"✅ 节点连接成功: {output_node.name()} -> {input_node.name()}")
            return connection
            
        except Exception as e:
            logger.error(f"❌ 节点连接失败: {e}")
            return None
    
    def execute_workflow(self):
        """执行工作流"""
        try:
            # 获取所有节点
            nodes = self.graph.all_nodes()
            
            # 按依赖关系排序
            sorted_nodes = self.topological_sort(nodes)
            
            # 执行节点
            results = {}
            for node in sorted_nodes:
                try:
                    # 执行节点
                    result = node.rockx_node.execute()
                    results[node.name()] = result
                    
                    logger.info(f"✅ 节点执行成功: {node.name()}")
                    
                except Exception as e:
                    logger.error(f"❌ 节点执行失败 {node.name()}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 工作流执行失败: {e}")
            return {}
    
    def topological_sort(self, nodes):
        """拓扑排序节点"""
        # 简化的拓扑排序实现
        # 实际实现应该考虑节点间的依赖关系
        return nodes
    
    def save_workflow(self, file_path):
        """保存工作流"""
        try:
            self.graph.save_session(file_path)
            logger.info(f"✅ 工作流保存成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 工作流保存失败: {e}")
            return False
    
    def load_workflow(self, file_path):
        """加载工作流"""
        try:
            self.graph.load_session(file_path)
            logger.info(f"✅ 工作流加载成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 工作流加载失败: {e}")
            return False
    
    def get_graph_widget(self):
        """获取图形界面组件"""
        return self.graph.widget
