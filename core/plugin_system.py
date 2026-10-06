#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 插件系统
提供插件管理、动态加载、扩展机制
"""

import os
import sys
import json
import logging
import threading
import importlib.util
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

class RockXQlibPluginType(Enum):
    """插件类型枚举"""
    NODE = "node"
    TRANSFORMER = "transformer"
    VALIDATOR = "validator"
    AI_MODEL = "ai_model"
    STRATEGY = "strategy"
    CUSTOM = "custom"

class RockXQlibPluginStatus(Enum):
    """插件状态枚举"""
    LOADED = "loaded"
    UNLOADED = "unloaded"
    ERROR = "error"
    DISABLED = "disabled"

@dataclass
class RockXQlibPluginInfo:
    """插件信息"""
    plugin_id: str
    name: str
    version: str
    plugin_type: RockXQlibPluginType
    description: str
    author: str
    dependencies: List[str] = None
    config_schema: Dict[str, Any] = None
    status: RockXQlibPluginStatus = RockXQlibPluginStatus.UNLOADED
    load_time: Optional[float] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.config_schema is None:
            self.config_schema = {}

class RockXQlibPlugin:
    """插件基类"""
    
    def __init__(self, plugin_id: str, plugin_config: Dict[str, Any]):
        self.plugin_id = plugin_id
        self.plugin_config = plugin_config
        self.is_initialized = False
        self.lock = threading.Lock()
        
        # 统计信息
        self.execution_count = 0
        self.total_execution_time = 0.0
        self.error_count = 0
        self.start_time = None
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            with self.lock:
                if not self.is_initialized:
                    self._initialize_specific()
                    self.is_initialized = True
                    self.start_time = time.time()
                    logger.info(f"插件 {self.plugin_id} 初始化成功")
                return True
        except Exception as e:
            logger.error(f"插件 {self.plugin_id} 初始化失败: {e}")
            return False
    
    def _initialize_specific(self):
        """子类特定的初始化逻辑"""
        pass
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行插件"""
        try:
            if not self.is_initialized:
                raise RuntimeError("插件未初始化")
            
            start_time = time.time()
            
            with self.lock:
                result = self._execute_specific(inputs)
                
                # 更新统计
                execution_time = time.time() - start_time
                self.execution_count += 1
                self.total_execution_time += execution_time
                
                return result
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"插件 {self.plugin_id} 执行失败: {e}")
            raise
    
    def _execute_specific(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """子类特定的执行逻辑"""
        raise NotImplementedError("子类必须实现 _execute_specific 方法")
    
    def cleanup(self):
        """清理插件"""
        try:
            with self.lock:
                if self.is_initialized:
                    self._cleanup_specific()
                    self.is_initialized = False
                    logger.info(f"插件 {self.plugin_id} 清理完成")
        except Exception as e:
            logger.error(f"插件 {self.plugin_id} 清理失败: {e}")
    
    def _cleanup_specific(self):
        """子类特定的清理逻辑"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            uptime = time.time() - self.start_time if self.start_time else 0
            return {
                'plugin_id': self.plugin_id,
                'is_initialized': self.is_initialized,
                'uptime': uptime,
                'execution_count': self.execution_count,
                'total_execution_time': self.total_execution_time,
                'average_execution_time': self.total_execution_time / max(self.execution_count, 1),
                'error_count': self.error_count,
                'error_rate': self.error_count / max(self.execution_count, 1)
            }

class RockXQlibNodePlugin(RockXQlibPlugin):
    """节点插件基类"""
    
    def __init__(self, plugin_id: str, plugin_config: Dict[str, Any]):
        super().__init__(plugin_id, plugin_config)
        self.node_class = None
    
    def _initialize_specific(self):
        """初始化节点类"""
        # 子类应该设置 self.node_class
        pass
    
    def create_node(self, **kwargs):
        """创建节点实例"""
        if not self.node_class:
            raise RuntimeError("节点类未定义")
        return self.node_class(**kwargs)

class RockXQlibTransformerPlugin(RockXQlibPlugin):
    """数据转换器插件基类"""
    
    def _execute_specific(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据转换"""
        data = inputs.get('data')
        if data is None:
            raise ValueError("输入数据不能为空")
        
        transformed_data = self.transform_data(data)
        return {'transformed_data': transformed_data}
    
    def transform_data(self, data: Any) -> Any:
        """转换数据（子类实现）"""
        raise NotImplementedError("子类必须实现 transform_data 方法")

class RockXQlibValidatorPlugin(RockXQlibPlugin):
    """数据验证器插件基类"""
    
    def _execute_specific(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据验证"""
        data = inputs.get('data')
        if data is None:
            raise ValueError("输入数据不能为空")
        
        is_valid, error_message = self.validate_data(data)
        return {
            'is_valid': is_valid,
            'error_message': error_message
        }
    
    def validate_data(self, data: Any) -> tuple[bool, Optional[str]]:
        """验证数据（子类实现）"""
        raise NotImplementedError("子类必须实现 validate_data 方法")

class RockXQlibPluginManager:
    """插件管理器"""
    
    def __init__(self, plugin_directory: Optional[str] = None):
        self.plugin_directory = plugin_directory or "plugins"
        self.plugins = {}  # plugin_id -> plugin_instance
        self.plugin_info = {}  # plugin_id -> plugin_info
        self.plugin_types = {}  # plugin_type -> [plugin_ids]
        self.lock = threading.Lock()
        
        # 统计信息
        self.total_plugins = 0
        self.loaded_plugins = 0
        self.failed_plugins = 0
        self.start_time = time.time()
        
        # 创建插件目录
        self._create_plugin_directory()
    
    def _create_plugin_directory(self):
        """创建插件目录"""
        try:
            Path(self.plugin_directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"插件目录已创建: {self.plugin_directory}")
        except Exception as e:
            logger.error(f"创建插件目录失败: {e}")
    
    def load_plugin(self, plugin_path: str) -> bool:
        """加载插件"""
        try:
            plugin_id = str(uuid.uuid4())[:8]
            
            # 加载插件模块
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", plugin_path)
            if spec is None:
                raise ImportError(f"无法加载插件文件: {plugin_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 获取插件信息
            plugin_info = self._extract_plugin_info(module, plugin_id)
            
            # 创建插件实例
            plugin_class = getattr(module, 'PluginClass', None)
            if not plugin_class:
                raise ValueError("插件文件必须定义 PluginClass")
            
            plugin_instance = plugin_class(plugin_id, plugin_info.config_schema)
            
            # 注册插件
            with self.lock:
                self.plugins[plugin_id] = plugin_instance
                self.plugin_info[plugin_id] = plugin_info
                
                # 添加到类型索引
                plugin_type = plugin_info.plugin_type
                if plugin_type not in self.plugin_types:
                    self.plugin_types[plugin_type] = []
                self.plugin_types[plugin_type].append(plugin_id)
                
                self.total_plugins += 1
            
            logger.info(f"插件 {plugin_id} 加载成功")
            return True
            
        except Exception as e:
            logger.error(f"加载插件失败: {e}")
            self.failed_plugins += 1
            return False
    
    def _extract_plugin_info(self, module, plugin_id: str) -> RockXQlibPluginInfo:
        """提取插件信息"""
        return RockXQlibPluginInfo(
            plugin_id=plugin_id,
            name=getattr(module, 'PLUGIN_NAME', f"Plugin_{plugin_id}"),
            version=getattr(module, 'PLUGIN_VERSION', '1.0.0'),
            plugin_type=RockXQlibPluginType(getattr(module, 'PLUGIN_TYPE', 'custom')),
            description=getattr(module, 'PLUGIN_DESCRIPTION', ''),
            author=getattr(module, 'PLUGIN_AUTHOR', 'Unknown'),
            dependencies=getattr(module, 'PLUGIN_DEPENDENCIES', []),
            config_schema=getattr(module, 'PLUGIN_CONFIG_SCHEMA', {})
        )
    
    def register_plugin(self, plugin: RockXQlibPlugin, plugin_info: RockXQlibPluginInfo):
        """注册插件"""
        try:
            with self.lock:
                plugin_id = plugin_info.plugin_id
                self.plugins[plugin_id] = plugin
                self.plugin_info[plugin_id] = plugin_info
                
                # 添加到类型索引
                plugin_type = plugin_info.plugin_type
                if plugin_type not in self.plugin_types:
                    self.plugin_types[plugin_type] = []
                self.plugin_types[plugin_type].append(plugin_id)
                
                self.total_plugins += 1
            
            logger.info(f"插件 {plugin_id} 注册成功")
            
        except Exception as e:
            logger.error(f"注册插件失败: {e}")
    
    def get_plugin(self, plugin_id: str) -> Optional[RockXQlibPlugin]:
        """获取插件"""
        with self.lock:
            return self.plugins.get(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: RockXQlibPluginType) -> List[RockXQlibPlugin]:
        """根据类型获取插件"""
        with self.lock:
            plugin_ids = self.plugin_types.get(plugin_type, [])
            return [self.plugins[pid] for pid in plugin_ids if pid in self.plugins]
    
    def initialize_plugin(self, plugin_id: str) -> bool:
        """初始化插件"""
        try:
            plugin = self.get_plugin(plugin_id)
            if not plugin:
                raise ValueError(f"插件 {plugin_id} 不存在")
            
            success = plugin.initialize()
            if success:
                self.plugin_info[plugin_id].status = RockXQlibPluginStatus.LOADED
                self.plugin_info[plugin_id].load_time = time.time()
                self.loaded_plugins += 1
            else:
                self.plugin_info[plugin_id].status = RockXQlibPluginStatus.ERROR
                self.failed_plugins += 1
            
            return success
            
        except Exception as e:
            logger.error(f"初始化插件 {plugin_id} 失败: {e}")
            self.plugin_info[plugin_id].status = RockXQlibPluginStatus.ERROR
            self.plugin_info[plugin_id].error_message = str(e)
            return False
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        try:
            plugin = self.get_plugin(plugin_id)
            if not plugin:
                return False
            
            # 清理插件
            plugin.cleanup()
            
            # 从注册表中移除
            with self.lock:
                if plugin_id in self.plugins:
                    del self.plugins[plugin_id]
                
                if plugin_id in self.plugin_info:
                    plugin_info = self.plugin_info[plugin_id]
                    plugin_type = plugin_info.plugin_type
                    if plugin_type in self.plugin_types:
                        if plugin_id in self.plugin_types[plugin_type]:
                            self.plugin_types[plugin_type].remove(plugin_id)
                    del self.plugin_info[plugin_id]
                
                self.loaded_plugins -= 1
            
            logger.info(f"插件 {plugin_id} 卸载成功")
            return True
            
        except Exception as e:
            logger.error(f"卸载插件 {plugin_id} 失败: {e}")
            return False
    
    def execute_plugin(self, plugin_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行插件"""
        try:
            plugin = self.get_plugin(plugin_id)
            if not plugin:
                raise ValueError(f"插件 {plugin_id} 不存在")
            
            if not plugin.is_initialized:
                raise RuntimeError(f"插件 {plugin_id} 未初始化")
            
            return plugin.execute(inputs)
            
        except Exception as e:
            logger.error(f"执行插件 {plugin_id} 失败: {e}")
            raise
    
    def get_plugin_info(self, plugin_id: str) -> Optional[RockXQlibPluginInfo]:
        """获取插件信息"""
        with self.lock:
            return self.plugin_info.get(plugin_id)
    
    def get_all_plugin_info(self) -> List[RockXQlibPluginInfo]:
        """获取所有插件信息"""
        with self.lock:
            return list(self.plugin_info.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'uptime': uptime,
                'total_plugins': self.total_plugins,
                'loaded_plugins': self.loaded_plugins,
                'failed_plugins': self.failed_plugins,
                'plugin_types': {pt.value: len(pids) for pt, pids in self.plugin_types.items()},
                'success_rate': self.loaded_plugins / max(self.total_plugins, 1)
            }
    
    def cleanup(self):
        """清理所有插件"""
        try:
            with self.lock:
                for plugin in self.plugins.values():
                    try:
                        plugin.cleanup()
                    except Exception as e:
                        logger.error(f"清理插件失败: {e}")
                
                self.plugins.clear()
                self.plugin_info.clear()
                self.plugin_types.clear()
            
            logger.info("插件管理器清理完成")
            
        except Exception as e:
            logger.error(f"插件管理器清理失败: {e}")

# 导入时间模块
import time
