#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib Ollama集成模块
支持本地Ollama模型集成
"""

import json
import logging
import requests
import numpy as np
from typing import Dict, Any, List, Optional, Union
import warnings

logger = logging.getLogger(__name__)

class RockXQlibOllamaInterface:
    """Ollama本地模型接口"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.available_models = []
        self._check_ollama_connection()
    
    def _check_ollama_connection(self):
        """检查Ollama连接状态"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                self.available_models = [model['name'] for model in models_data.get('models', [])]
                logger.info(f"✅ Ollama连接成功，可用模型: {self.available_models}")
            else:
                logger.warning(f"⚠️ Ollama连接失败，状态码: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Ollama连接失败: {e}")
            self.available_models = []
    
    def generate_text(self, 
                     prompt: str, 
                     model: str = "qwen3:latest",
                     temperature: float = 0.7,
                     max_tokens: int = 1000) -> str:
        """生成文本"""
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                logger.error(f"文本生成失败，状态码: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"文本生成异常: {e}")
            return ""
    
    def generate_embedding(self, 
                          text: str, 
                          model: str = "nomic-embed-text:latest") -> List[float]:
        """生成文本嵌入向量"""
        try:
            payload = {
                "model": model,
                "prompt": text
            }
            
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('embedding', [])
            else:
                logger.error(f"嵌入生成失败，状态码: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"嵌入生成异常: {e}")
            return []
    
    def chat_completion(self,
                       messages: List[Dict[str, str]],
                       model: str = "qwen3:latest",
                       temperature: float = 0.7) -> str:
        """聊天完成"""
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', '')
            else:
                logger.error(f"聊天完成失败，状态码: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"聊天完成异常: {e}")
            return ""

class RockXQlibOllamaKnowledgeBase:
    """基于Ollama的知识库"""
    
    def __init__(self, 
                 ollama_interface: RockXQlibOllamaInterface,
                 embedding_model: str = "nomic-embed-text:latest",
                 llm_model: str = "qwen3:latest"):
        self.ollama = ollama_interface
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.knowledge_items = []
        self.embeddings = []
    
    def add_knowledge(self, 
                     knowledge_type: str,
                     content: str,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加知识"""
        try:
            # 生成嵌入向量
            embedding = self.ollama.generate_embedding(content, self.embedding_model)
            if not embedding:
                logger.warning("无法生成嵌入向量，跳过知识添加")
                return None
            
            # 创建知识项
            knowledge_id = f"kb_{len(self.knowledge_items)}"
            knowledge_item = {
                "id": knowledge_id,
                "type": knowledge_type,
                "content": content,
                "metadata": metadata or {},
                "embedding": embedding
            }
            
            self.knowledge_items.append(knowledge_item)
            self.embeddings.append(embedding)
            
            logger.info(f"✅ 知识添加成功: {knowledge_id}")
            return knowledge_id
            
        except Exception as e:
            logger.error(f"知识添加失败: {e}")
            return None
    
    def search_knowledge(self, 
                        query: str, 
                        top_k: int = 5,
                        knowledge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索知识"""
        try:
            # 生成查询向量
            query_embedding = self.ollama.generate_embedding(query, self.embedding_model)
            if not query_embedding:
                logger.warning("无法生成查询向量")
                return []
            
            # 计算相似度
            similarities = []
            for i, item in enumerate(self.knowledge_items):
                if knowledge_type and item['type'] != knowledge_type:
                    continue
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(query_embedding, item['embedding'])
                similarities.append((i, similarity, item))
            
            # 排序并返回top_k结果
            similarities.sort(key=lambda x: x[1], reverse=True)
            results = [item for _, _, item in similarities[:top_k]]
            
            logger.info(f"✅ 知识搜索完成，找到 {len(results)} 条结果")
            return results
            
        except Exception as e:
            logger.error(f"知识搜索失败: {e}")
            return []
    
    def query_with_context(self, 
                          question: str,
                          context_knowledge: Optional[List[Dict[str, Any]]] = None) -> str:
        """基于上下文回答问题"""
        try:
            # 如果没有提供上下文，先搜索相关知识
            if not context_knowledge:
                context_knowledge = self.search_knowledge(question, top_k=3)
            
            # 构建上下文
            context_text = ""
            for item in context_knowledge:
                context_text += f"[{item['type']}] {item['content']}\n"
            
            # 构建提示词
            prompt = f"""基于以下上下文信息回答问题：

上下文信息：
{context_text}

问题：{question}

请基于上下文信息提供准确、详细的回答："""
            
            # 生成回答
            answer = self.ollama.generate_text(
                prompt=prompt,
                model=self.llm_model,
                temperature=0.3
            )
            
            logger.info("✅ 上下文查询完成")
            return answer
            
        except Exception as e:
            logger.error(f"上下文查询失败: {e}")
            return ""
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.error(f"余弦相似度计算失败: {e}")
            return 0.0

class RockXQlibOllamaQuantitativeAssistant:
    """基于Ollama的量化交易助手"""
    
    def __init__(self, 
                 ollama_interface: RockXQlibOllamaInterface,
                 knowledge_base: RockXQlibOllamaKnowledgeBase):
        self.ollama = ollama_interface
        self.kb = knowledge_base
        self._initialize_quantitative_knowledge()
    
    def _initialize_quantitative_knowledge(self):
        """初始化量化交易知识"""
        quantitative_knowledge = [
            {
                "type": "strategy",
                "content": "Alpha158因子包含158个技术指标，包括价格、成交量、波动率等多个维度的特征。",
                "metadata": {"category": "factor", "source": "qlib"}
            },
            {
                "type": "model",
                "content": "LightGBM是梯度提升决策树模型，在量化交易中常用于特征选择和预测。",
                "metadata": {"category": "ml_model", "source": "qlib"}
            },
            {
                "type": "backtest",
                "content": "回测是验证策略有效性的重要方法，需要考虑交易成本、滑点、市场冲击等因素。",
                "metadata": {"category": "methodology", "source": "qlib"}
            },
            {
                "type": "risk",
                "content": "风险管理包括仓位管理、止损设置、最大回撤控制等关键要素。",
                "metadata": {"category": "risk_management", "source": "qlib"}
            }
        ]
        
        for knowledge in quantitative_knowledge:
            self.kb.add_knowledge(
                knowledge_type=knowledge["type"],
                content=knowledge["content"],
                metadata=knowledge["metadata"]
            )
    
    def analyze_strategy(self, strategy_description: str) -> str:
        """分析策略"""
        prompt = f"""作为量化交易专家，请分析以下策略：

策略描述：{strategy_description}

请从以下角度进行分析：
1. 策略逻辑和原理
2. 适用市场环境
3. 潜在风险和限制
4. 优化建议
5. 实施要点

请提供详细的分析报告："""
        
        return self.ollama.generate_text(prompt, temperature=0.3)
    
    def suggest_improvements(self, 
                           strategy_performance: Dict[str, Any],
                           current_issues: List[str]) -> str:
        """建议策略改进"""
        context = self.kb.search_knowledge("strategy optimization", top_k=3)
        
        prompt = f"""基于以下策略表现和问题，请提供改进建议：

策略表现：{json.dumps(strategy_performance, indent=2, ensure_ascii=False)}
当前问题：{', '.join(current_issues)}

请提供具体的改进建议和实施方案："""
        
        return self.kb.query_with_context(prompt, context)
    
    def explain_factor(self, factor_name: str) -> str:
        """解释因子"""
        context = self.kb.search_knowledge(factor_name, top_k=5)
        
        if not context:
            # 如果没有找到相关知识，使用通用解释
            prompt = f"""请解释量化交易中的 {factor_name} 因子：

1. 因子的定义和计算方法
2. 因子的经济含义
3. 因子的使用场景
4. 因子的注意事项

请提供详细的解释："""
        else:
            prompt = f"""请基于相关知识解释 {factor_name} 因子："""
        
        return self.kb.query_with_context(prompt, context)
    
    def generate_trading_signal(self, 
                              market_data: Dict[str, Any],
                              model_predictions: Dict[str, Any]) -> str:
        """生成交易信号"""
        prompt = f"""基于以下市场数据和模型预测，生成交易信号：

市场数据：{json.dumps(market_data, indent=2, ensure_ascii=False)}
模型预测：{json.dumps(model_predictions, indent=2, ensure_ascii=False)}

请提供：
1. 交易信号（买入/卖出/持有）
2. 信号强度
3. 风险等级
4. 操作建议

请生成详细的交易信号报告："""
        
        return self.ollama.generate_text(prompt, temperature=0.2)
