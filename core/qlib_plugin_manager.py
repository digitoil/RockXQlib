#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib插件管理器
严格按照设计文档实现
"""

import os
import sys
import logging
import importlib
import inspect
from typing import Dict, Any, Optional, List, Type, Callable
import json
from datetime import datetime

from .qlib_base_node import QlibBaseNode

logger = logging.getLogger(__name__)

class QlibPlugin:
    """Qlib插件基类"""
    
    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.author = ""
        self.created_time = datetime.now().isoformat()
        self.dependencies = []
        self.node_classes = []
        self.functions = []
        self.is_loaded = False
        
    def get_info(self) -> Dict[str, Any]:
        """获取插件信息"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'created_time': self.created_time,
            'dependencies': self.dependencies,
            'node_classes': [cls.__name__ for cls in self.node_classes],
            'functions': [func.__name__ for func in self.functions],
            'is_loaded': self.is_loaded
        }
    
    def load(self) -> bool:
        """加载插件"""
        try:
            self.is_loaded = True
            logger.info(f"插件加载成功: {self.name}")
            return True
        except Exception as e:
            logger.error(f"插件加载失败: {e}")
            return False
    
    def unload(self) -> bool:
        """卸载插件"""
        try:
            self.is_loaded = False
            logger.info(f"插件卸载成功: {self.name}")
            return True
        except Exception as e:
            logger.error(f"插件卸载失败: {e}")
            return False

class QlibPluginManager:
    """插件管理器"""
    
    def __init__(self, plugin_dir: str = "./plugins"):
        self.plugin_dir = plugin_dir
        self.plugins = {}
        self.loaded_plugins = {}
        self.node_registry = {}
        self.function_registry = {}
        
        # 创建插件目录
        os.makedirs(plugin_dir, exist_ok=True)
        
        # 加载现有插件
        self._load_existing_plugins()
        
        logger.info(f"插件管理器初始化完成: {plugin_dir}")
    
    def _load_existing_plugins(self):
        """加载现有插件"""
        try:
            # 扫描插件目录
            for filename in os.listdir(self.plugin_dir):
                if filename.endswith('.py') and not filename.startswith('__'):
                    plugin_name = filename[:-3]
                    self._load_plugin_from_file(plugin_name)
            
            logger.info(f"加载了 {len(self.plugins)} 个插件")
            
        except Exception as e:
            logger.error(f"加载现有插件失败: {e}")
    
    def _load_plugin_from_file(self, plugin_name: str) -> bool:
        """从文件加载插件"""
        try:
            plugin_file = os.path.join(self.plugin_dir, f"{plugin_name}.py")
            
            if not os.path.exists(plugin_file):
                logger.error(f"插件文件不存在: {plugin_file}")
                return False
            
            # 动态导入插件模块
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, QlibPlugin) and 
                    obj != QlibPlugin):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                logger.error(f"插件文件中未找到插件类: {plugin_file}")
                return False
            
            # 创建插件实例
            plugin = plugin_class()
            
            # 注册插件
            self.plugins[plugin.name] = plugin
            
            logger.info(f"插件加载成功: {plugin.name}")
            return True
            
        except Exception as e:
            logger.error(f"从文件加载插件失败: {e}")
            return False
    
    def load_plugin(self, plugin_path: str) -> bool:
        """加载插件"""
        try:
            if not os.path.exists(plugin_path):
                logger.error(f"插件路径不存在: {plugin_path}")
                return False
            
            # 获取插件名称
            plugin_name = os.path.splitext(os.path.basename(plugin_path))[0]
            
            # 动态导入插件
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, QlibPlugin) and 
                    obj != QlibPlugin):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                logger.error(f"插件文件中未找到插件类: {plugin_path}")
                return False
            
            # 创建插件实例
            plugin = plugin_class()
            
            # 检查依赖
            if not self._check_dependencies(plugin):
                logger.error(f"插件依赖检查失败: {plugin.name}")
                return False
            
            # 加载插件
            if not plugin.load():
                logger.error(f"插件加载失败: {plugin.name}")
                return False
            
            # 注册插件
            self.plugins[plugin.name] = plugin
            self.loaded_plugins[plugin.name] = plugin
            
            # 注册节点类
            self._register_plugin_nodes(plugin)
            
            # 注册函数
            self._register_plugin_functions(plugin)
            
            logger.info(f"插件加载成功: {plugin.name}")
            return True
            
        except Exception as e:
            logger.error(f"加载插件失败: {e}")
            return False
    
    def _check_dependencies(self, plugin: QlibPlugin) -> bool:
        """检查插件依赖"""
        try:
            for dependency in plugin.dependencies:
                if dependency not in self.loaded_plugins:
                    logger.error(f"缺少依赖插件: {dependency}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查插件依赖失败: {e}")
            return False
    
    def _register_plugin_nodes(self, plugin: QlibPlugin):
        """注册插件节点"""
        try:
            for node_class in plugin.node_classes:
                if issubclass(node_class, QlibBaseNode):
                    self.node_registry[node_class.__name__] = {
                        'class': node_class,
                        'plugin': plugin.name,
                        'description': node_class.__doc__ or ''
                    }
                    logger.info(f"节点类注册成功: {node_class.__name__}")
            
        except Exception as e:
            logger.error(f"注册插件节点失败: {e}")
    
    def _register_plugin_functions(self, plugin: QlibPlugin):
        """注册插件函数"""
        try:
            for func in plugin.functions:
                if callable(func):
                    self.function_registry[func.__name__] = {
                        'function': func,
                        'plugin': plugin.name,
                        'description': func.__doc__ or ''
                    }
                    logger.info(f"函数注册成功: {func.__name__}")
            
        except Exception as e:
            logger.error(f"注册插件函数失败: {e}")
    
    def register_custom_node(self, node_class: Type[QlibBaseNode]) -> bool:
        """注册自定义节点"""
        try:
            if not issubclass(node_class, QlibBaseNode):
                logger.error(f"节点类必须继承自QlibBaseNode: {node_class}")
                return False
            
            # 注册节点类
            self.node_registry[node_class.__name__] = {
                'class': node_class,
                'plugin': 'custom',
                'description': node_class.__doc__ or ''
            }
            
            logger.info(f"自定义节点注册成功: {node_class.__name__}")
            return True
            
        except Exception as e:
            logger.error(f"注册自定义节点失败: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        try:
            if plugin_name not in self.loaded_plugins:
                logger.error(f"插件未加载: {plugin_name}")
                return False
            
            plugin = self.loaded_plugins[plugin_name]
            
            # 卸载插件
            if not plugin.unload():
                logger.error(f"插件卸载失败: {plugin_name}")
                return False
            
            # 从注册表中移除节点类
            for node_name, node_info in list(self.node_registry.items()):
                if node_info['plugin'] == plugin_name:
                    del self.node_registry[node_name]
            
            # 从注册表中移除函数
            for func_name, func_info in list(self.function_registry.items()):
                if func_info['plugin'] == plugin_name:
                    del self.function_registry[func_name]
            
            # 从加载列表中移除
            del self.loaded_plugins[plugin_name]
            
            logger.info(f"插件卸载成功: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"卸载插件失败: {e}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[QlibPlugin]:
        """获取插件"""
        return self.loaded_plugins.get(plugin_name)
    
    def get_loaded_plugins(self) -> Dict[str, QlibPlugin]:
        """获取已加载的插件"""
        return self.loaded_plugins.copy()
    
    def get_available_plugins(self) -> Dict[str, QlibPlugin]:
        """获取可用插件"""
        return self.plugins.copy()
    
    def get_registered_nodes(self) -> Dict[str, Dict[str, Any]]:
        """获取注册的节点"""
        return self.node_registry.copy()
    
    def get_registered_functions(self) -> Dict[str, Dict[str, Any]]:
        """获取注册的函数"""
        return self.function_registry.copy()
    
    def create_node(self, node_name: str, **kwargs) -> Optional[QlibBaseNode]:
        """创建节点实例"""
        try:
            if node_name not in self.node_registry:
                logger.error(f"节点类未注册: {node_name}")
                return None
            
            node_info = self.node_registry[node_name]
            node_class = node_info['class']
            
            # 创建节点实例
            node = node_class(**kwargs)
            
            logger.info(f"节点实例创建成功: {node_name}")
            return node
            
        except Exception as e:
            logger.error(f"创建节点实例失败: {e}")
            return None
    
    def call_function(self, function_name: str, *args, **kwargs) -> Any:
        """调用注册的函数"""
        try:
            if function_name not in self.function_registry:
                logger.error(f"函数未注册: {function_name}")
                return None
            
            func_info = self.function_registry[function_name]
            func = func_info['function']
            
            # 调用函数
            result = func(*args, **kwargs)
            
            logger.info(f"函数调用成功: {function_name}")
            return result
            
        except Exception as e:
            logger.error(f"调用函数失败: {e}")
            return None
    
    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件信息"""
        try:
            if plugin_name not in self.loaded_plugins:
                logger.error(f"插件未加载: {plugin_name}")
                return {}
            
            plugin = self.loaded_plugins[plugin_name]
            return plugin.get_info()
            
        except Exception as e:
            logger.error(f"获取插件信息失败: {e}")
            return {}
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            return {
                'plugin_dir': self.plugin_dir,
                'total_plugins': len(self.plugins),
                'loaded_plugins': len(self.loaded_plugins),
                'registered_nodes': len(self.node_registry),
                'registered_functions': len(self.function_registry),
                'loaded_plugin_names': list(self.loaded_plugins.keys()),
                'available_plugin_names': list(self.plugins.keys()),
                'registered_node_names': list(self.node_registry.keys()),
                'registered_function_names': list(self.function_registry.keys())
            }
            
        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {}
    
    def save_plugin_config(self, config_path: str) -> bool:
        """保存插件配置"""
        try:
            config = {
                'plugin_dir': self.plugin_dir,
                'loaded_plugins': list(self.loaded_plugins.keys()),
                'plugins': {}
            }
            
            # 保存插件信息
            for plugin_name, plugin in self.plugins.items():
                config['plugins'][plugin_name] = plugin.get_info()
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"插件配置保存成功: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存插件配置失败: {e}")
            return False
    
    def load_plugin_config(self, config_path: str) -> bool:
        """加载插件配置"""
        try:
            if not os.path.exists(config_path):
                logger.error(f"配置文件不存在: {config_path}")
                return False
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 加载插件
            for plugin_name in config.get('loaded_plugins', []):
                if plugin_name in self.plugins:
                    plugin = self.plugins[plugin_name]
                    if plugin.load():
                        self.loaded_plugins[plugin_name] = plugin
                        self._register_plugin_nodes(plugin)
                        self._register_plugin_functions(plugin)
            
            logger.info(f"插件配置加载成功: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"加载插件配置失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            # 卸载所有插件
            for plugin_name in list(self.loaded_plugins.keys()):
                self.unload_plugin(plugin_name)
            
            # 清空注册表
            self.node_registry.clear()
            self.function_registry.clear()
            self.plugins.clear()
            
            logger.info("插件管理器清理完成")
            
        except Exception as e:
            logger.error(f"插件管理器清理失败: {e}")
