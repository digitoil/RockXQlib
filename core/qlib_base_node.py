#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib基础节点接口
严格按照设计文档实现
"""

import os
import sys
import logging
import hashlib
import pickle
from typing import Dict, Any, Optional, List, Tuple, Union
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

# 添加NodeGraphQt路径
try:
    nodegraphqt_path = os.path.join(os.path.dirname(__file__), '..', '..', 'RockXFWV21', 'NodeGraphQt')
    if os.path.exists(nodegraphqt_path):
        sys.path.insert(0, nodegraphqt_path)
    
    from NodeGraphQt import BaseNode
    NODEGRAPH_AVAILABLE = True
except ImportError:
    NODEGRAPH_AVAILABLE = False
    BaseNode = object

logger = logging.getLogger(__name__)

class QlibBaseNode(BaseNode):
    """Qlib基础节点接口"""
    
    def __init__(self):
        super().__init__()
        self._qlib_config = {}
        self._execution_context = None
        self._cache_manager = None
        self._node_id = None
        self._status = "idle"  # idle, running, success, failed, warning
        self._status_message = ""
        self._input_values = {}
        self._output_values = {}
        self._properties = {}
        self._execution_time = 0.0
        self._memory_usage = 0.0

        # 端口元数据（与 core/base_node.py 的 RockXQlibBaseNode 保持同一设计：
        # 既记录端口的业务类型，又调用 NodeGraphQt 原生 add_input/add_output
        # 建立可视端口。backtest/model/strategy/data 节点用的是 add_input_port
        # 这套 API，此前基类没提供，导致这些节点无法实例化。）
        self._input_ports = {}
        self._output_ports = {}

        # add_rockx_property 声明的属性类型，get_property 据此做类型转换
        self._rockx_property_types = {}

        # 初始化节点
        self._initialize_node()
    
    def _initialize_node(self):
        """初始化节点"""
        # 生成唯一节点ID
        self._node_id = self._generate_node_id()
        
        # 设置默认属性
        self._setup_default_properties()
        
        # 设置输入输出端口
        self._setup_ports()
        
        logger.debug(f"节点初始化完成: {self.__class__.__name__} (ID: {self._node_id})")
    
    def _generate_node_id(self) -> str:
        """生成唯一节点ID"""
        import time
        import random
        timestamp = str(int(time.time() * 1000))
        random_id = str(random.randint(1000, 9999))
        return f"{self.__class__.__name__}_{timestamp}_{random_id}"
    
    def _setup_default_properties(self):
        """设置默认属性"""
        # 基础属性
        self._properties = {
            'name': self.__class__.__name__,
            'description': f"{self.__class__.__name__}节点",
            'version': '1.0.0',
            'enabled': True,
            'timeout': 300,  # 5分钟超时
            'retry_count': 3,
            'cache_enabled': True,
            'parallel_enabled': False,
            'memory_limit': 1024 * 1024 * 1024,  # 1GB内存限制
        }
    
    def _setup_ports(self):
        """设置输入输出端口 - 子类实现"""
        pass

    def add_input_port(self, name: str, data_type: Any = "any",
                       required: bool = True, description: str = "",
                       default_value: Any = None):
        """添加输入端口。

        与 core/base_node.py 的 RockXQlibBaseNode.add_input_port 对齐：
        记录业务元数据，同时在 NodeGraphQt 上建立真实可视端口，
        这样节点既能在画布上连线，又能携带数据类型信息。
        """
        self._input_ports[name] = {
            "name": name,
            "data_type": data_type,
            "required": required,
            "description": description,
            "default_value": default_value,
        }
        try:
            self.add_input(name)
        except Exception as e:
            logger.warning(f"节点 {self.__class__.__name__} 建立输入端口 {name} 失败: {e}")
        return name

    def add_output_port(self, name: str, data_type: Any = "any",
                        description: str = ""):
        """添加输出端口，语义同 add_input_port。"""
        self._output_ports[name] = {
            "name": name,
            "data_type": data_type,
            "description": description,
        }
        try:
            self.add_output(name)
        except Exception as e:
            logger.warning(f"节点 {self.__class__.__name__} 建立输出端口 {name} 失败: {e}")
        return name

    def get_port_info(self) -> Dict[str, Any]:
        """返回端口元数据，便于属性面板与校验逻辑使用。"""
        return {
            "inputs": dict(self._input_ports),
            "outputs": dict(self._output_ports),
        }


    def validate_config(self) -> bool:
        """验证节点配置"""
        try:
            # 验证基础配置
            if not self._properties.get('enabled', True):
                self._set_status("warning", "节点已禁用")
                return False
            
            # 验证超时设置
            timeout = self._properties.get('timeout', 300)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                self._set_status("failed", "无效的超时设置")
                return False
            
            # 验证重试次数
            retry_count = self._properties.get('retry_count', 3)
            if not isinstance(retry_count, int) or retry_count < 0:
                self._set_status("failed", "无效的重试次数设置")
                return False
            
            # 验证内存限制
            memory_limit = self._properties.get('memory_limit', 1024 * 1024 * 1024)
            if not isinstance(memory_limit, (int, float)) or memory_limit <= 0:
                self._set_status("failed", "无效的内存限制设置")
                return False
            
            # 子类特定验证
            if not self._validate_specific_config():
                return False
            
            self._set_status("success", "配置验证通过")
            return True
            
        except Exception as e:
            self._set_status("failed", f"配置验证失败: {e}")
            logger.error(f"配置验证失败 {self.__class__.__name__}: {e}")
            return False
    
    def _validate_specific_config(self) -> bool:
        """子类特定的配置验证 - 子类重写"""
        return True
    
    def prepare_execution(self) -> bool:
        """准备执行环境"""
        try:
            # 检查节点状态
            if self._status == "running":
                self._set_status("warning", "节点正在运行中")
                return False
            
            # 验证配置
            if not self.validate_config():
                return False
            
            # 准备执行上下文
            self._execution_context = {
                'node_id': self._node_id,
                'start_time': None,
                'end_time': None,
                'inputs': self._input_values.copy(),
                'outputs': {},
                'memory_usage': 0,
                'error_count': 0,
            }
            
            # 子类特定准备
            if not self._prepare_specific_execution():
                return False
            
            self._set_status("success", "执行环境准备完成")
            return True
            
        except Exception as e:
            self._set_status("failed", f"执行环境准备失败: {e}")
            logger.error(f"执行环境准备失败 {self.__class__.__name__}: {e}")
            return False
    
    def _prepare_specific_execution(self) -> bool:
        """子类特定的执行准备 - 子类重写"""
        return True
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点逻辑"""
        try:
            # 准备执行
            if not self.prepare_execution():
                return {}
            
            # 记录开始时间
            import time
            start_time = time.time()
            self._execution_context['start_time'] = start_time
            
            # 设置状态
            self._set_status("running", "正在执行...")
            
            # 更新输入
            self._input_values.update(inputs)
            
            # 执行具体逻辑
            result = self._execute_logic(inputs)
            
            # 记录结束时间
            end_time = time.time()
            self._execution_context['end_time'] = end_time
            self._execution_time = end_time - start_time
            
            # 更新输出
            self._output_values.update(result)
            
            # 设置成功状态
            self._set_status("success", f"执行完成，耗时: {self._execution_time:.2f}秒")
            
            return result
            
        except Exception as e:
            # 设置失败状态
            self._set_status("failed", f"执行失败: {e}")
            logger.error(f"节点执行失败 {self.__class__.__name__}: {e}")
            return {}
    
    @abstractmethod
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行具体逻辑 - 子类必须实现"""
        pass
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理执行上下文
            if self._execution_context:
                self._execution_context.clear()
                self._execution_context = None
            
            # 清理输入输出
            self._input_values.clear()
            self._output_values.clear()
            
            # 子类特定清理
            self._cleanup_specific()
            
            # 重置状态
            self._set_status("idle", "资源清理完成")
            
            logger.debug(f"节点资源清理完成: {self.__class__.__name__}")
            
        except Exception as e:
            logger.error(f"节点资源清理失败 {self.__class__.__name__}: {e}")
    
    def _cleanup_specific(self):
        """子类特定的清理 - 子类重写"""
        pass
    
    def _set_status(self, status: str, message: str = ""):
        """设置节点状态"""
        self._status = status
        self._status_message = message
        logger.debug(f"节点状态更新: {self.__class__.__name__} -> {status}: {message}")
    
    def get_status(self) -> str:
        """获取节点状态"""
        return self._status
    
    def get_status_message(self) -> str:
        """获取状态消息"""
        return self._status_message
    
    def get_node_id(self) -> str:
        """获取节点ID"""
        return self._node_id
    
    def get_execution_time(self) -> float:
        """获取执行时间"""
        return self._execution_time
    
    def get_memory_usage(self) -> float:
        """获取内存使用量"""
        return self._memory_usage
    
    def add_rockx_property(self, name: str, prop_type: type = str,
                           default: Any = None, label: str = "",
                           description: str = ""):
        """注册节点属性（设计文档约定的统一接口）。

        此前基类未提供该方法，导致 backtest / model / strategy 共 18 个节点
        一实例化就报 AttributeError: 'XXX' object has no attribute 'add_rockx_property'。

        NodeGraphQt 只提供「文本输入 / 下拉菜单 / 勾选框」三类控件，没有数值控件，
        因此 int/float 也用文本框承载；声明的 Python 类型记在 _rockx_property_types，
        由 get_property 负责转换，保证下游拿到的仍是数值类型。

        属性同时写入 NodeGraphQt 的属性存储（属性编辑器据此显示与编辑）与节点自身的
        _properties，两边保持一致——这是属性编辑器此前空白、改了不生效的根因。
        """
        label = label or name
        self._rockx_property_types[name] = prop_type
        ui_value = default

        try:
            if prop_type is bool:
                ui_value = bool(default) if default is not None else False
                self.add_checkbox(name, label, label, ui_value, tooltip=description)
            elif isinstance(prop_type, (list, tuple)):
                items = [str(x) for x in prop_type]
                self.add_combo_menu(name, label, items, tooltip=description)
                ui_value = str(default) if default is not None else (items[0] if items else "")
            else:
                ui_value = "" if default is None else str(default)
                self.add_text_input(name, label, ui_value, tooltip=description)
        except Exception as e:
            logger.warning(f"节点 {self.__class__.__name__} 注册属性 {name} 失败: {e}")

        self._properties[name] = default if default is not None else ui_value
        try:
            super().set_property(name, ui_value, push_undo=False)
        except Exception:
            pass
        return name

    def set_property(self, key: str, value: Any, **kwargs):
        """设置属性：同步写入节点字典与 NodeGraphQt 属性存储。

        ⚠️ 必须接受 ``**kwargs`` 并透传给 super()。

        NodeGraphQt 内部会以关键字参数调用本方法，例如
        ``NodeGraphQt/base/graph.py`` 的 ``create_node()``：

            n.set_property('selected', False, push_undo=True)

        原实现把签名写死为 ``(key, value)``，于是**从节点树拖拽创建节点**
        （`_on_node_data_dropped` -> `create_node`）时会抛：

            TypeError: set_property() got an unexpected keyword argument 'push_undo'

        表现为「拖拽没反应」，而报错发生在 NodeGraphQt 内部、指向框架代码，
        极难定位。这里改为透传，默认 ``push_undo=False``（保持原行为）。
        """
        self._properties[key] = value
        kwargs.setdefault('push_undo', False)
        try:
            super().set_property(key, value, **kwargs)
        except Exception:
            pass

    def get_property(self, key: str, default: Any = None) -> Any:
        """获取属性。

        取值顺序：NodeGraphQt 属性存储（属性编辑器改的就是它）
        → 节点自身 _properties → default。
        最后按 add_rockx_property 声明的类型转换，避免下游拿到字符串。
        """
        value = None
        found = False
        try:
            raw = super().get_property(key)
            if raw is not None:
                value, found = raw, True
        except Exception:
            pass
        if not found and key in self._properties:
            value, found = self._properties[key], True
        if not found:
            return default

        declared = self._rockx_property_types.get(key)
        if declared and declared is not bool and value is not None:
            try:
                if declared is int:
                    return int(float(value))
                if declared is float:
                    return float(value)
                if declared is str:
                    return str(value)
            except (TypeError, ValueError):
                return value
        return value

    def set_input(self, port_name: str, value: Any):
        """设置输入"""
        self._input_values[port_name] = value
    
    def get_input(self, port_name: str, default: Any = None) -> Any:
        """获取输入"""
        return self._input_values.get(port_name, default)
    
    def set_output(self, port_name: str, value: Any):
        """设置输出"""
        self._output_values[port_name] = value
    
    def get_output(self, port_name: str, default: Any = None) -> Any:
        """获取输出"""
        return self._output_values.get(port_name, default)
    
    def get_all_inputs(self) -> Dict[str, Any]:
        """获取所有输入"""
        return self._input_values.copy()
    
    def get_all_outputs(self) -> Dict[str, Any]:
        """获取所有输出"""
        return self._output_values.copy()
    
    def get_all_properties(self) -> Dict[str, Any]:
        """获取所有属性"""
        return self._properties.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'node_id': self._node_id,
            'class_name': self.__class__.__name__,
            'status': self._status,
            'status_message': self._status_message,
            'properties': self._properties.copy(),
            'execution_time': self._execution_time,
            'memory_usage': self._memory_usage,
            'inputs': self._input_values.copy(),
            'outputs': self._output_values.copy(),
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """从字典恢复"""
        self._node_id = data.get('node_id', self._node_id)
        self._status = data.get('status', 'idle')
        self._status_message = data.get('status_message', '')
        self._properties.update(data.get('properties', {}))
        self._execution_time = data.get('execution_time', 0.0)
        self._memory_usage = data.get('memory_usage', 0.0)
        self._input_values.update(data.get('inputs', {}))
        self._output_values.update(data.get('outputs', {}))
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.__class__.__name__}(id={self._node_id}, status={self._status})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"{self.__class__.__name__}(id={self._node_id}, status={self._status}, execution_time={self._execution_time:.2f}s)"
