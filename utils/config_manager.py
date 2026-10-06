#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 配置管理器
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class RockXQlibConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "rockxqlib_config.json"):
        self.config_file = config_file
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self._get_default_config()
                self.save_config()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = self._get_default_config()
    
    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "database": {
                "sqlite_path": "rockxqlib.db",
                "vector_db_path": "vector_kb"
            },
            "ai": {
                "model_type": "local",
                "api_key": ""
            },
            "visualization": {
                "theme": "plotly_white",
                "colors": {
                    "primary": "#1f77b4",
                    "secondary": "#ff7f0e"
                }
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
