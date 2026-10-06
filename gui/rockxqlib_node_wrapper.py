#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 节点包装器
将RockXQlib节点包装为NodeGraphQt节点
"""

import logging
from typing import Any, Dict, Optional

try:
    from NodeGraphQt import BaseNode
    from NodeGraphQt.constants import NodePropWidgetEnum
    NODEGRAPH_AVAILABLE = True
except ImportError:
    NODEGRAPH_AVAILABLE = False
    BaseNode = object
    NodePropWidgetEnum = object

logger = logging.getLogger(__name__)

class RockXQlibNodeWrapper(BaseNode):
    """RockXQlib节点包装器基类"""
    
    def __init__(self, rockx_node):
        super().__init__()
        
        self.rockx_node = rockx_node
        self.setup_node()
    
    def setup_node(self):
        """设置节点"""
        # 设置节点基本信息
        self.set_name(self.rockx_node.get_name())
        self.set_color(*self.rockx_node.get_color())
        
        # 设置端口
        self.setup_ports()
        
        # 设置属性
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
            
            # 根据类型设置属性控件
            widget_type = self.get_widget_type(prop_type)
            
            self.add_property(
                prop_name,
                default_value,
                widget_type=widget_type,
                tab='属性'
            )
    
    def get_widget_type(self, prop_type):
        """获取属性控件类型"""
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
            self.rockx_node.set_input(input_port.name(), data)
            
            # 执行节点
            result = self.rockx_node.execute()
            
            # 更新输出端口
            if result:
                for output_port in self.output_ports():
                    output_data = self.rockx_node.get_output(output_port.name())
                    if output_data is not None:
                        output_port.set_value(output_data)
            
            # 更新节点状态
            self.update_node_status()
            
        except Exception as e:
            logger.error(f"节点执行失败 {self.name()}: {e}")
            self.set_tooltip(f"执行失败: {e}")
    
    def on_property_changed(self, property_name, property_value):
        """属性变化时的处理"""
        try:
            # 更新底层节点属性
            self.rockx_node.set_rockx_property(property_name, property_value)
            
            logger.info(f"属性更新: {property_name} = {property_value}")
            
        except Exception as e:
            logger.error(f"属性更新失败 {property_name}: {e}")
    
    def update_node_status(self):
        """更新节点状态"""
        try:
            status = self.rockx_node.get_status()
            status_message = self.rockx_node.get_status_message()
            
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
            result = self.rockx_node.execute()
            self.update_node_status()
            return result
        except Exception as e:
            logger.error(f"节点执行失败: {e}")
            self.set_tooltip(f"执行失败: {e}")
            return None
    
    def get_rockx_node(self):
        """获取底层RockXQlib节点"""
        return self.rockx_node
