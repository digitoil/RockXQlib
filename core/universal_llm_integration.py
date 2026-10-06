#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockX Universal LLM集成模块
支持多种LLM提供商，包括Ollama、OpenAI、Claude等
设计为中性化和通用性，支持所有RockX项目
"""

import os
import json
import time
import logging
import requests
import threading
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """LLM提供商枚举"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    CLAUDE = "claude"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    CUSTOM = "custom"

class LLMModelType(Enum):
    """LLM模型类型"""
    CHAT = "chat"
    EMBEDDING = "embedding"
    CODE = "code"
    QUANT = "quant"
    GENERAL = "general"

@dataclass
class LLMModel:
    """LLM模型信息"""
    name: str
    provider: LLMProvider
    model_type: LLMModelType
    model_id: str
    size: str = ""
    description: str = ""
    capabilities: List[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True
    created_time: float = 0.0
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.created_time == 0.0:
            self.created_time = time.time()

@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    response_time: float = 0.0
    success: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class OllamaLLMProvider:
    """Ollama LLM提供商"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.available_models = []
        self.model_info_cache = {}
        self.last_refresh = 0
        self.cache_ttl = 300  # 5分钟缓存
        
        # 统计信息
        self.total_requests = 0
        self.total_tokens = 0
        self.start_time = time.time()
        
        logger.info("Ollama LLM提供商初始化完成")
    
    def refresh_models(self) -> List[LLMModel]:
        """刷新可用模型列表"""
        try:
            # 检查缓存
            if time.time() - self.last_refresh < self.cache_ttl and self.available_models:
                return self.available_models
            
            # 获取模型列表
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code != 200:
                logger.error(f"获取Ollama模型列表失败: {response.status_code}")
                return self.available_models
            
            data = response.json()
            models = []
            
            for model_data in data.get("models", []):
                model_name = model_data.get("name", "")
                model_id = model_data.get("id", "")
                size = model_data.get("size", 0)
                
                # 根据模型名称判断类型
                model_type = self._detect_model_type(model_name)
                
                # 获取模型详细信息
                model_info = self._get_model_info(model_name)
                
                model = LLMModel(
                    name=model_name,
                    provider=LLMProvider.OLLAMA,
                    model_type=model_type,
                    model_id=model_id,
                    size=f"{size / (1024**3):.1f}GB" if size > 0 else "未知",
                    description=model_info.get("description", ""),
                    capabilities=model_info.get("capabilities", []),
                    max_tokens=model_info.get("max_tokens", 4096),
                    temperature=model_info.get("temperature", 0.7)
                )
                models.append(model)
            
            self.available_models = models
            self.last_refresh = time.time()
            
            logger.info(f"刷新Ollama模型列表完成，共 {len(models)} 个模型")
            return models
            
        except Exception as e:
            logger.error(f"刷新Ollama模型列表失败: {e}")
            return self.available_models
    
    def _detect_model_type(self, model_name: str) -> LLMModelType:
        """检测模型类型"""
        model_name_lower = model_name.lower()
        
        if "embed" in model_name_lower:
            return LLMModelType.EMBEDDING
        elif "code" in model_name_lower or "coder" in model_name_lower:
            return LLMModelType.CODE
        elif "qwen" in model_name_lower:
            return LLMModelType.QUANT
        elif "deepseek" in model_name_lower:
            return LLMModelType.QUANT
        else:
            return LLMModelType.GENERAL
    
    def _get_model_info(self, model_name: str) -> Dict[str, Any]:
        """获取模型详细信息"""
        if model_name in self.model_info_cache:
            return self.model_info_cache[model_name]
        
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                info = {
                    "description": data.get("details", {}).get("description", ""),
                    "capabilities": self._extract_capabilities(data),
                    "max_tokens": data.get("details", {}).get("context_length", 4096),
                    "temperature": 0.7
                }
                self.model_info_cache[model_name] = info
                return info
        except Exception as e:
            logger.warning(f"获取模型 {model_name} 信息失败: {e}")
        
        return {
            "description": f"Ollama模型: {model_name}",
            "capabilities": ["text_generation", "chat"],
            "max_tokens": 4096,
            "temperature": 0.7
        }
    
    def _extract_capabilities(self, model_data: Dict[str, Any]) -> List[str]:
        """提取模型能力"""
        capabilities = ["text_generation", "chat"]
        
        details = model_data.get("details", {})
        if details.get("embedding", False):
            capabilities.append("embedding")
        
        if "code" in model_data.get("name", "").lower():
            capabilities.append("code_generation")
        
        if "quant" in model_data.get("name", "").lower():
            capabilities.append("quantitative_analysis")
        
        return capabilities
    
    def generate_text(self, prompt: str, model_name: str, **kwargs) -> LLMResponse:
        """生成文本"""
        try:
            start_time = time.time()
            
            # 构建请求参数
            request_data = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "top_p": kwargs.get("top_p", 0.9),
                    "max_tokens": kwargs.get("max_tokens", 4096)
                }
            }
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=request_data,
                timeout=kwargs.get("timeout", 60)
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    content="",
                    model=model_name,
                    provider="ollama",
                    success=False,
                    error_message=f"API请求失败: {response.status_code}"
                )
            
            data = response.json()
            content = data.get("response", "")
            tokens_used = data.get("eval_count", 0)
            
            # 更新统计信息
            self.total_requests += 1
            self.total_tokens += tokens_used
            
            return LLMResponse(
                content=content,
                model=model_name,
                provider="ollama",
                tokens_used=tokens_used,
                response_time=time.time() - start_time,
                success=True,
                metadata=data
            )
            
        except Exception as e:
            logger.error(f"Ollama文本生成失败: {e}")
            return LLMResponse(
                content="",
                model=model_name,
                provider="ollama",
                success=False,
                error_message=str(e)
            )
    
    def generate_chat(self, messages: List[Dict[str, str]], model_name: str, **kwargs) -> LLMResponse:
        """生成聊天对话"""
        try:
            start_time = time.time()
            
            # 构建请求参数
            request_data = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "top_p": kwargs.get("top_p", 0.9),
                    "max_tokens": kwargs.get("max_tokens", 4096)
                }
            }
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                timeout=kwargs.get("timeout", 60)
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    content="",
                    model=model_name,
                    provider="ollama",
                    success=False,
                    error_message=f"API请求失败: {response.status_code}"
                )
            
            data = response.json()
            content = data.get("message", {}).get("content", "")
            tokens_used = data.get("eval_count", 0)
            
            # 更新统计信息
            self.total_requests += 1
            self.total_tokens += tokens_used
            
            return LLMResponse(
                content=content,
                model=model_name,
                provider="ollama",
                tokens_used=tokens_used,
                response_time=time.time() - start_time,
                success=True,
                metadata=data
            )
            
        except Exception as e:
            logger.error(f"Ollama聊天生成失败: {e}")
            return LLMResponse(
                content="",
                model=model_name,
                provider="ollama",
                success=False,
                error_message=str(e)
            )
    
    def generate_embedding(self, text: str, model_name: str, **kwargs) -> List[float]:
        """生成文本嵌入"""
        try:
            request_data = {
                "model": model_name,
                "prompt": text
            }
            
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json=request_data,
                timeout=kwargs.get("timeout", 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])
            else:
                logger.error(f"Ollama嵌入生成失败: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ollama嵌入生成失败: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        return {
            "provider": "ollama",
            "base_url": self.base_url,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "uptime": uptime,
            "available_models": len(self.available_models),
            "requests_per_minute": self.total_requests / max(uptime / 60, 1)
        }

class UniversalLLMManager:
    """通用LLM管理器"""
    
    def __init__(self, config_path: str = "config/llm_config.yaml"):
        self.config_path = config_path
        self.providers = {}
        self.models = {}
        self.default_model = None
        
        # 加载配置
        self.config = self._load_config()
        
        # 初始化提供商
        self._initialize_providers()
        
        # 统计信息
        self.total_requests = 0
        self.total_tokens = 0
        self.start_time = time.time()
        
        logger.info("通用LLM管理器初始化完成")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            "providers": {
                "ollama": {
                    "enabled": True,
                    "base_url": "http://localhost:11434",
                    "timeout": 60,
                    "max_retries": 3
                },
                "openai": {
                    "enabled": False,
                    "api_key": "",
                    "base_url": "https://api.openai.com/v1",
                    "timeout": 60
                },
                "claude": {
                    "enabled": False,
                    "api_key": "",
                    "base_url": "https://api.anthropic.com",
                    "timeout": 60
                }
            },
            "default_provider": "ollama",
            "default_model": "qwen3:latest",
            "quant_models": {
                "primary": "qwen3:latest",
                "secondary": "deepseek-r1:8b",
                "embedding": "nomic-embed-text:latest"
            },
            "performance": {
                "cache_enabled": True,
                "cache_ttl": 300,
                "max_concurrent_requests": 5
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            else:
                # 创建默认配置文件
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
                return default_config
        except Exception as e:
            logger.error(f"加载LLM配置失败: {e}")
            return default_config
    
    def _initialize_providers(self):
        """初始化提供商"""
        try:
            # 初始化Ollama
            if self.config.get("providers", {}).get("ollama", {}).get("enabled", True):
                ollama_config = self.config["providers"]["ollama"]
                self.providers["ollama"] = OllamaLLMProvider(
                    base_url=ollama_config.get("base_url", "http://localhost:11434")
                )
                
                # 刷新模型列表
                models = self.providers["ollama"].refresh_models()
                for model in models:
                    self.models[model.name] = model
                
                logger.info(f"Ollama提供商初始化完成，发现 {len(models)} 个模型")
            
            # 设置默认模型
            default_model_name = self.config.get("default_model", "qwen3:latest")
            if default_model_name in self.models:
                self.default_model = self.models[default_model_name]
                logger.info(f"默认模型设置为: {default_model_name}")
            
        except Exception as e:
            logger.error(f"初始化LLM提供商失败: {e}")
    
    def get_available_models(self, provider: Optional[str] = None) -> List[LLMModel]:
        """获取可用模型"""
        if provider:
            if provider in self.providers:
                return self.providers[provider].refresh_models()
            return []
        
        models = []
        for prov in self.providers.values():
            models.extend(prov.refresh_models())
        return models
    
    def get_quant_models(self) -> Dict[str, LLMModel]:
        """获取量化分析专用模型"""
        quant_models = {}
        quant_config = self.config.get("quant_models", {})
        
        for role, model_name in quant_config.items():
            if model_name in self.models:
                quant_models[role] = self.models[model_name]
        
        return quant_models
    
    def generate_text(self, prompt: str, model_name: Optional[str] = None, **kwargs) -> LLMResponse:
        """生成文本"""
        try:
            # 确定使用的模型
            if not model_name:
                model_name = self.default_model.name if self.default_model else None
            
            if not model_name or model_name not in self.models:
                return LLMResponse(
                    content="",
                    model=model_name or "unknown",
                    provider="unknown",
                    success=False,
                    error_message="模型不存在或未指定"
                )
            
            model = self.models[model_name]
            provider = self.providers.get(model.provider.value)
            
            if not provider:
                return LLMResponse(
                    content="",
                    model=model_name,
                    provider=model.provider.value,
                    success=False,
                    error_message=f"提供商 {model.provider.value} 不可用"
                )
            
            # 生成文本
            if model.provider == LLMProvider.OLLAMA:
                response = provider.generate_text(prompt, model_name, **kwargs)
            else:
                # 其他提供商的实现
                response = LLMResponse(
                    content="",
                    model=model_name,
                    provider=model.provider.value,
                    success=False,
                    error_message=f"提供商 {model.provider.value} 暂未实现"
                )
            
            # 更新统计信息
            if response.success:
                self.total_requests += 1
                self.total_tokens += response.tokens_used
            
            return response
            
        except Exception as e:
            logger.error(f"生成文本失败: {e}")
            return LLMResponse(
                content="",
                model=model_name or "unknown",
                provider="unknown",
                success=False,
                error_message=str(e)
            )
    
    def generate_chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, **kwargs) -> LLMResponse:
        """生成聊天对话"""
        try:
            # 确定使用的模型
            if not model_name:
                model_name = self.default_model.name if self.default_model else None
            
            if not model_name or model_name not in self.models:
                return LLMResponse(
                    content="",
                    model=model_name or "unknown",
                    provider="unknown",
                    success=False,
                    error_message="模型不存在或未指定"
                )
            
            model = self.models[model_name]
            provider = self.providers.get(model.provider.value)
            
            if not provider:
                return LLMResponse(
                    content="",
                    model=model_name,
                    provider=model.provider.value,
                    success=False,
                    error_message=f"提供商 {model.provider.value} 不可用"
                )
            
            # 生成聊天
            if model.provider == LLMProvider.OLLAMA:
                response = provider.generate_chat(messages, model_name, **kwargs)
            else:
                response = LLMResponse(
                    content="",
                    model=model_name,
                    provider=model.provider.value,
                    success=False,
                    error_message=f"提供商 {model.provider.value} 暂未实现"
                )
            
            # 更新统计信息
            if response.success:
                self.total_requests += 1
                self.total_tokens += response.tokens_used
            
            return response
            
        except Exception as e:
            logger.error(f"生成聊天失败: {e}")
            return LLMResponse(
                content="",
                model=model_name or "unknown",
                provider="unknown",
                success=False,
                error_message=str(e)
            )
    
    def generate_quant_analysis(self, query: str, analysis_type: str = "general") -> LLMResponse:
        """生成量化分析"""
        try:
            # 根据分析类型选择模型
            quant_models = self.get_quant_models()
            
            if analysis_type == "embedding" and "embedding" in quant_models:
                model_name = quant_models["embedding"].name
            elif analysis_type == "code" and "secondary" in quant_models:
                model_name = quant_models["secondary"].name
            else:
                model_name = quant_models.get("primary", {}).name if quant_models.get("primary") else None
            
            if not model_name:
                model_name = self.default_model.name if self.default_model else None
            
            # 构建量化分析专用提示词
            quant_prompt = self._build_quant_prompt(query, analysis_type)
            
            # 生成响应
            return self.generate_text(quant_prompt, model_name, temperature=0.3)
            
        except Exception as e:
            logger.error(f"生成量化分析失败: {e}")
            return LLMResponse(
                content="",
                model="unknown",
                provider="unknown",
                success=False,
                error_message=str(e)
            )
    
    def _build_quant_prompt(self, query: str, analysis_type: str) -> str:
        """构建量化分析提示词"""
        base_prompt = f"""
你是一个专业的量化分析AI助手，专门帮助用户进行金融数据分析和量化交易策略开发。

用户查询: {query}

请提供专业、准确的量化分析建议，包括：
1. 数据分析方法
2. 技术指标计算
3. 风险评估
4. 策略建议
5. 代码实现（如需要）

请用中文回答，保持专业性和实用性。
"""
        
        if analysis_type == "code":
            base_prompt += "\n\n请重点提供代码实现和具体的技术细节。"
        elif analysis_type == "strategy":
            base_prompt += "\n\n请重点提供交易策略和风险管理建议。"
        elif analysis_type == "risk":
            base_prompt += "\n\n请重点提供风险评估和风险控制方法。"
        
        return base_prompt
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        provider_stats = {}
        
        for name, provider in self.providers.items():
            provider_stats[name] = provider.get_stats()
        
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "uptime": uptime,
            "available_models": len(self.models),
            "providers": provider_stats,
            "default_model": self.default_model.name if self.default_model else None
        }
    
    def save_config(self):
        """保存配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            logger.info("LLM配置保存成功")
        except Exception as e:
            logger.error(f"保存LLM配置失败: {e}")
