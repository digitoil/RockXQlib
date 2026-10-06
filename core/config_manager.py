#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器
管理节点融合配置和系统设置
"""

import os
import sys
import yaml
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


def _detect_provider_uri() -> str:
    """探测可用的 qlib 数据目录，作为配置默认值。

    原来默认写死 'D:\\\\qlib_data'，本机并不存在（真实数据在
    <项目>/../RockXFWV21/qlib_data/cn_data）。
    """
    try:
        from .qlib_paths import get_default_provider_uri
        return get_default_provider_uri()
    except ImportError:
        try:
            from qlib_paths import get_default_provider_uri
            return get_default_provider_uri()
        except ImportError:
            return "~/.qlib/qlib_data/cn_data"


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or self._get_default_config_file()
        self.config = {}
        self._load_config()
    
    def _get_default_config_file(self) -> str:
        """获取默认配置文件路径"""
        current_dir = os.path.dirname(__file__)
        config_dir = os.path.join(current_dir, '..', 'config')
        return os.path.join(config_dir, 'node_fusion_config.yaml')
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                logger.info(f"✅ 配置文件加载成功: {self.config_file}")
            else:
                logger.warning(f"⚠️ 配置文件不存在: {self.config_file}")
                self.config = self._get_default_config()
        except Exception as e:
            logger.error(f"❌ 配置文件加载失败: {e}")
            self.config = self._get_default_config()

        # 加载后修正无效路径
        self._fix_invalid_paths()

    def _fix_invalid_paths(self):
        """把配置里指向不存在目录的 provider_uri 换成自动探测到的真实路径。

        YAML 里写的是 ``D:\\qlib_data``（本机并不存在），而且它**会覆盖**
        代码里的默认值 —— 只在代码里改默认值是没用的。
        这里做一次运行时校验：配置里的路径不可用就替换成探测结果。
        这样配置文本保持可移植，实际生效的却是本机真实路径。
        """
        try:
            from .qlib_paths import is_qlib_data_dir, get_default_provider_uri
        except ImportError:
            try:
                from qlib_paths import is_qlib_data_dir, get_default_provider_uri
            except ImportError:
                return

        if not isinstance(self.config, dict):
            return

        fixed = []

        def _check(container, key, where):
            cur = container.get(key) if isinstance(container, dict) else None
            if isinstance(cur, str) and cur and not is_qlib_data_dir(cur):
                container[key] = get_default_provider_uri()
                fixed.append("%s (%s -> %s)" % (where, cur, container[key]))

        # 1) integration.qlib.provider_uri
        integ = self.config.get("integration")
        if isinstance(integ, dict) and isinstance(integ.get("qlib"), dict):
            _check(integ["qlib"], "provider_uri", "integration.qlib")

        # 2) 工作流模板里各节点的 provider_uri
        tpls = self.config.get("workflow_templates")
        if isinstance(tpls, dict):
            for tname, tpl in tpls.items():
                for node in (tpl or {}).get("nodes", []) or []:
                    props = node.get("properties")
                    if isinstance(props, dict) and "provider_uri" in props:
                        _check(props, "provider_uri",
                               "workflow_templates.%s" % tname)

        if fixed:
            logger.info("🔧 已修正配置中无效的 provider_uri: %s", "; ".join(fixed))
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'system': {
                'name': 'RockXQlib统一节点管理系统',
                'version': '1.0.0',
                'description': '基于Qlib核心的量化分析节点系统'
            },
            'node_systems': {
                'qlib_core': {
                    'enabled': True,
                    'priority': 1,
                    'description': '基于Qlib核心API的节点系统'
                }
            },
            'categories': {
                'Qlib核心': {
                    'description': '基于Qlib核心API的节点',
                    'icon': '🔧',
                    'color': '#0078d4',
                    'priority': 1
                }
            },
            'workflow_templates': {},
            'node_properties': {},
            'integration': {
                'qlib': {
                    'auto_init': True,
                    # 自动探测真实数据目录（原来写死 'D:\\qlib_data'，本机不存在）
                    'provider_uri': _detect_provider_uri(),
                    'region': 'cn',
                    'enable_exp_recorder': True
                }
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(levelname)s - %(message)s'
            }
        }
    
    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return self.config.get('system', {})
    
    def get_node_systems_config(self) -> Dict[str, Any]:
        """获取节点系统配置"""
        return self.config.get('node_systems', {})
    
    def get_categories_config(self) -> Dict[str, Any]:
        """获取类别配置"""
        return self.config.get('categories', {})
    
    def get_workflow_templates_config(self) -> Dict[str, Any]:
        """获取工作流模板配置"""
        return self.config.get('workflow_templates', {})
    
    def get_node_properties_config(self) -> Dict[str, Any]:
        """获取节点属性配置"""
        return self.config.get('node_properties', {})
    
    def get_integration_config(self) -> Dict[str, Any]:
        """获取集成配置"""
        return self.config.get('integration', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config.get('logging', {})
    
    def get_enabled_node_systems(self) -> List[str]:
        """获取启用的节点系统"""
        node_systems = self.get_node_systems_config()
        enabled_systems = []
        
        for system_name, system_config in node_systems.items():
            if system_config.get('enabled', False):
                enabled_systems.append(system_name)
        
        # 按优先级排序
        enabled_systems.sort(key=lambda x: node_systems[x].get('priority', 999))
        return enabled_systems
    
    def get_node_system_config(self, system_name: str) -> Optional[Dict[str, Any]]:
        """获取特定节点系统配置"""
        node_systems = self.get_node_systems_config()
        return node_systems.get(system_name)
    
    def get_category_config(self, category_name: str) -> Optional[Dict[str, Any]]:
        """获取特定类别配置"""
        categories = self.get_categories_config()
        return categories.get(category_name)
    
    def get_workflow_template_config(self, template_name: str) -> Optional[Dict[str, Any]]:
        """获取特定工作流模板配置"""
        templates = self.get_workflow_templates_config()
        return templates.get(template_name)
    
    def get_node_property_config(self, node_type: str, property_name: str) -> Optional[Dict[str, Any]]:
        """获取特定节点属性配置"""
        node_properties = self.get_node_properties_config()
        node_config = node_properties.get(node_type, {})
        return node_config.get(property_name)
    
    def get_qlib_config(self) -> Dict[str, Any]:
        """获取Qlib集成配置"""
        integration = self.get_integration_config()
        return integration.get('qlib', {})
    
    def get_nodegraphqt_config(self) -> Dict[str, Any]:
        """获取NodeGraphQt集成配置"""
        integration = self.get_integration_config()
        return integration.get('nodegraphqt', {})
    
    def get_data_flow_config(self) -> Dict[str, Any]:
        """获取数据流配置"""
        integration = self.get_integration_config()
        return integration.get('data_flow', {})
    
    def save_config(self, config: Dict[str, Any] = None):
        """保存配置"""
        try:
            if config:
                self.config = config
            
            # 确保配置目录存在
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            logger.info(f"✅ 配置文件保存成功: {self.config_file}")
            
        except Exception as e:
            logger.error(f"❌ 配置文件保存失败: {e}")
    
    def update_config(self, section: str, key: str, value: Any):
        """更新配置"""
        try:
            if section not in self.config:
                self.config[section] = {}
            
            if key is None:
                self.config[section] = value
            else:
                self.config[section][key] = value
            
            logger.info(f"✅ 配置更新成功: {section}.{key} = {value}")
            
        except Exception as e:
            logger.error(f"❌ 配置更新失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        self._load_config()
        logger.info("✅ 配置重新加载完成")
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        try:
            # 验证系统配置
            system_config = self.get_system_config()
            if not system_config.get('name'):
                validation_result['warnings'].append("系统名称未设置")
            
            # 验证节点系统配置
            node_systems = self.get_node_systems_config()
            if not node_systems:
                validation_result['warnings'].append("未配置任何节点系统")
            
            # 验证类别配置
            categories = self.get_categories_config()
            if not categories:
                validation_result['warnings'].append("未配置任何节点类别")
            
            # 验证集成配置
            integration = self.get_integration_config()
            qlib_config = integration.get('qlib', {})
            if not qlib_config.get('provider_uri'):
                validation_result['warnings'].append("Qlib数据源URI未设置")
            
            logger.info("✅ 配置验证完成")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"配置验证失败: {e}")
            logger.error(f"❌ 配置验证失败: {e}")
        
        return validation_result
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'config_file': self.config_file,
            'system_name': self.get_system_config().get('name', 'Unknown'),
            'system_version': self.get_system_config().get('version', 'Unknown'),
            'enabled_node_systems': len(self.get_enabled_node_systems()),
            'total_categories': len(self.get_categories_config()),
            'total_templates': len(self.get_workflow_templates_config()),
            'qlib_auto_init': self.get_qlib_config().get('auto_init', False),
            'config_valid': self.validate_config()['valid']
        }

# 全局配置管理器实例
config_manager = ConfigManager()
