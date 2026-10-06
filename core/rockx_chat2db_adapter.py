#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockX Chat2DB Universal Adapter
通用Chat2DB集成适配器，支持不同RockX系统产品的配置和模板
"""

import os
import json
import time
import logging
import requests
import threading
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

# 导入通用配置管理器
from .rockx_universal_config import RockXUniversalConfigManager, RockXSystemType, SQLTemplate
from .universal_llm_integration import UniversalLLMManager

logger = logging.getLogger(__name__)

class Chat2DBIntegrationMode(Enum):
    """Chat2DB集成模式"""
    EMBEDDED = "embedded"      # 嵌入式集成
    STANDALONE = "standalone"  # 独立运行
    API_ONLY = "api_only"      # 仅API调用

@dataclass
class Chat2DBSystemProfile:
    """Chat2DB系统配置文件"""
    system_name: str
    system_type: RockXSystemType
    integration_mode: Chat2DBIntegrationMode
    database_connections: Dict[str, Any]
    sql_templates: List[str]
    ai_prompts: Dict[str, List[str]]
    custom_ui_config: Dict[str, Any]
    enabled_features: List[str]

class RockXChat2DBAdapter:
    """RockX Chat2DB通用适配器"""
    
    def __init__(self, system_name: str = "RockXQlib", config_dir: str = "config/rockx_systems"):
        self.system_name = system_name
        self.config_dir = config_dir
        
        # 初始化配置管理器
        self.config_manager = RockXUniversalConfigManager(config_dir)
        
        # 初始化LLM管理器
        self.llm_manager = UniversalLLMManager()
        
        # 获取系统配置
        self.system_config = self.config_manager.get_system_config(system_name)
        if not self.system_config:
            raise ValueError(f"系统配置不存在: {system_name}")
        
        # 创建系统配置文件
        self.system_profile = self._create_system_profile()
        
        # Chat2DB相关
        self.chat2db_process = None
        self.api_url = "http://localhost:10824"
        self.is_running = False
        
        # 统计信息
        self.total_queries = 0
        self.total_ai_queries = 0
        self.start_time = time.time()
        
        logger.info(f"RockX Chat2DB适配器初始化完成: {system_name}")
    
    def _create_system_profile(self) -> Chat2DBSystemProfile:
        """创建系统配置文件"""
        return Chat2DBSystemProfile(
            system_name=self.system_name,
            system_type=self.system_config.system_type,
            integration_mode=Chat2DBIntegrationMode.EMBEDDED,
            database_connections=self.system_config.database_config,
            sql_templates=self.system_config.sql_templates,
            ai_prompts=self.system_config.ai_prompts,
            custom_ui_config={
                "theme": "dark",
                "language": "zh-CN",
                "show_quant_templates": True,
                "enable_ai_features": True
            },
            enabled_features=[
                "sql_generation",
                "ai_analysis",
                "template_management",
                "database_management",
                "visualization"
            ]
        )
    
    def start_chat2db(self) -> bool:
        """启动Chat2DB"""
        try:
            if self.is_running:
                logger.info("Chat2DB已在运行")
                return True
            
            # 根据系统类型配置Chat2DB
            self._configure_chat2db_for_system()
            
            # 启动Chat2DB进程
            success = self._launch_chat2db_process()
            
            if success:
                self.is_running = True
                self.start_time = time.time()
                logger.info(f"Chat2DB已为 {self.system_name} 系统启动")
            
            return success
            
        except Exception as e:
            logger.error(f"启动Chat2DB失败: {e}")
            return False
    
    def _configure_chat2db_for_system(self):
        """根据系统类型配置Chat2DB"""
        try:
            # 创建系统专用的Chat2DB配置
            chat2db_config = {
                "system": {
                    "name": self.system_name,
                    "type": self.system_config.system_type.value,
                    "version": self.system_config.version
                },
                "database": self.system_config.database_config,
                "templates": self._prepare_sql_templates(),
                "ai": {
                    "enabled": True,
                    "provider": "ollama",
                    "models": self._get_ai_models_for_system(),
                    "prompts": self.system_config.ai_prompts
                },
                "ui": self.system_profile.custom_ui_config,
                "features": self.system_profile.enabled_features
            }
            
            # 保存配置到Chat2DB配置目录
            config_path = os.path.join(self.config_dir, f"{self.system_name.lower()}_chat2db_config.json")
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(chat2db_config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Chat2DB配置已保存: {config_path}")
            
        except Exception as e:
            logger.error(f"配置Chat2DB失败: {e}")
    
    def _prepare_sql_templates(self) -> List[Dict[str, Any]]:
        """准备SQL模板"""
        templates = []
        
        for template_name in self.system_config.sql_templates:
            template = self.config_manager.sql_templates.get(template_name)
            if template:
                templates.append({
                    "name": template.name,
                    "category": template.category,
                    "description": template.description,
                    "template": template.template,
                    "parameters": template.parameters,
                    "example": template.example,
                    "difficulty": template.difficulty,
                    "tags": template.tags
                })
        
        return templates
    
    def _get_ai_models_for_system(self) -> Dict[str, str]:
        """获取系统专用的AI模型"""
        quant_models = self.llm_manager.get_quant_models()
        
        models = {}
        for role, model in quant_models.items():
            models[role] = model.name
        
        return models
    
    def _launch_chat2db_process(self) -> bool:
        """启动Chat2DB进程"""
        try:
            import subprocess
            
            # 查找Chat2DB可执行文件
            chat2db_path = self._find_chat2db_executable()
            if not chat2db_path:
                logger.error("未找到Chat2DB可执行文件")
                return False
            
            # 构建启动命令
            cmd = [chat2db_path]
            
            # 添加系统专用配置
            config_path = os.path.join(self.config_dir, f"{self.system_name.lower()}_chat2db_config.json")
            if os.path.exists(config_path):
                cmd.extend(["--config", config_path])
            
            # 启动进程
            self.chat2db_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # 等待启动
            time.sleep(3)
            
            # 检查是否启动成功
            if self._check_chat2db_status():
                return True
            else:
                logger.error("Chat2DB启动失败")
                return False
                
        except Exception as e:
            logger.error(f"启动Chat2DB进程失败: {e}")
            return False
    
    def _find_chat2db_executable(self) -> Optional[str]:
        """查找Chat2DB可执行文件"""
        possible_paths = [
            # Windows路径
            "C:\\Program Files\\Chat2DB\\Chat2DB.exe",
            "C:\\Program Files (x86)\\Chat2DB\\Chat2DB.exe",
            os.path.expanduser("~\\AppData\\Local\\Programs\\Chat2DB\\Chat2DB.exe"),
            # 当前目录
            "./Chat2DB/Chat2DB.exe",
            "./chat2db.exe",
            # 系统PATH
            "chat2db.exe",
            "Chat2DB.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _check_chat2db_status(self) -> bool:
        """检查Chat2DB运行状态"""
        try:
            response = requests.get(f"{self.api_url}/api/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def stop_chat2db(self) -> bool:
        """停止Chat2DB"""
        try:
            if self.chat2db_process and self.chat2db_process.poll() is None:
                self.chat2db_process.terminate()
                self.chat2db_process.wait(timeout=10)
            
            self.is_running = False
            logger.info("Chat2DB已停止")
            return True
        except Exception as e:
            logger.error(f"停止Chat2DB失败: {e}")
            return False
    
    def generate_sql_for_system(self, natural_language: str, category: str = "general") -> Dict[str, Any]:
        """为系统生成SQL"""
        try:
            if not self.is_running:
                return {"error": "Chat2DB未运行"}
            
            # 获取系统专用的AI提示词
            system_prompts = self.system_config.ai_prompts.get(category, [])
            
            # 构建系统专用的提示词
            system_prompt = self._build_system_prompt(natural_language, category, system_prompts)
            
            # 使用LLM生成SQL
            response = self.llm_manager.generate_text(system_prompt)
            
            if response.success:
                self.total_ai_queries += 1
                return {
                    "sql": self._extract_sql_from_response(response.content),
                    "explanation": response.content,
                    "model": response.model,
                    "system": self.system_name,
                    "category": category
                }
            else:
                return {"error": response.error_message}
                
        except Exception as e:
            logger.error(f"生成SQL失败: {e}")
            return {"error": str(e)}
    
    def _build_system_prompt(self, query: str, category: str, system_prompts: List[str]) -> str:
        """构建系统专用提示词"""
        base_prompt = f"""
你是一个专业的{self.system_name}系统AI助手，专门为{self.system_config.system_type.value}系统提供SQL查询生成服务。

系统信息:
- 系统名称: {self.system_name}
- 系统类型: {self.system_config.system_type.value}
- 系统版本: {self.system_config.version}
- 系统描述: {self.system_config.description}

用户查询: {query}

请根据系统特点生成相应的SQL查询语句。
"""
        
        if system_prompts:
            base_prompt += f"\n系统专用提示词:\n" + "\n".join(f"- {prompt}" for prompt in system_prompts)
        
        # 添加可用的SQL模板信息
        templates = self.config_manager.get_sql_templates_for_system(self.system_name)
        if templates:
            base_prompt += f"\n\n可用的SQL模板:\n"
            for template in templates[:5]:  # 只显示前5个模板
                base_prompt += f"- {template.name}: {template.description}\n"
        
        base_prompt += "\n\n请生成相应的SQL查询语句，并简要解释查询的目的。"
        
        return base_prompt
    
    def _extract_sql_from_response(self, response: str) -> str:
        """从响应中提取SQL"""
        # 简单的SQL提取逻辑
        lines = response.split('\n')
        sql_lines = []
        in_sql_block = False
        
        for line in lines:
            line = line.strip()
            if line.upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                in_sql_block = True
                sql_lines.append(line)
            elif in_sql_block and line and not line.startswith('--'):
                sql_lines.append(line)
            elif in_sql_block and not line:
                break
        
        return '\n'.join(sql_lines)
    
    def execute_sql(self, sql: str, database: str = "default") -> Dict[str, Any]:
        """执行SQL查询"""
        try:
            if not self.is_running:
                return {"error": "Chat2DB未运行"}
            
            payload = {
                "sql": sql,
                "database": database,
                "system": self.system_name
            }
            
            response = requests.post(
                f"{self.api_url}/api/sql/execute",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.total_queries += 1
                return response.json()
            else:
                return {"error": f"API请求失败: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"执行SQL失败: {e}")
            return {"error": str(e)}
    
    def get_system_templates(self) -> List[SQLTemplate]:
        """获取系统专用模板"""
        return self.config_manager.get_sql_templates_for_system(self.system_name)
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "system_name": self.system_name,
            "system_type": self.system_config.system_type.value,
            "version": self.system_config.version,
            "description": self.system_config.description,
            "chat2db_status": {
                "is_running": self.is_running,
                "uptime": time.time() - self.start_time if self.is_running else 0,
                "total_queries": self.total_queries,
                "total_ai_queries": self.total_ai_queries
            },
            "available_templates": len(self.get_system_templates()),
            "database_connections": len(self.system_config.database_config),
            "enabled_features": self.system_profile.enabled_features
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        return {
            "system": self.system_name,
            "total_queries": self.total_queries,
            "total_ai_queries": self.total_ai_queries,
            "uptime": uptime,
            "queries_per_minute": self.total_queries / max(uptime / 60, 1),
            "ai_queries_per_minute": self.total_ai_queries / max(uptime / 60, 1),
            "chat2db_running": self.is_running
        }

