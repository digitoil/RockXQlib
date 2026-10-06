#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib AI集成系统
提供大模型接口、知识库系统、智能推荐、自然语言处理
"""

import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

class RockXQlibAIModelType(Enum):
    """AI模型类型枚举"""
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_OPUS = "claude-3-opus"
    LOCAL_LLM = "local-llm"
    CUSTOM = "custom"

class RockXQlibAnalysisType(Enum):
    """分析类型枚举"""
    INSIGHT = "insight"
    PREDICTION = "prediction"
    STRATEGY = "strategy"
    RISK = "risk"
    OPTIMIZATION = "optimization"
    EXPLANATION = "explanation"

@dataclass
class RockXQlibAIResponse:
    """AI响应结构"""
    response_id: str
    model_type: RockXQlibAIModelType
    query: str
    response: str
    confidence: float
    tokens_used: int
    processing_time: float
    timestamp: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class RockXQlibAIModelInterface:
    """AI大模型接口"""
    
    def __init__(self, model_type: RockXQlibAIModelType, model_config: Dict[str, Any]):
        self.model_type = model_type
        self.model_config = model_config
        self.model = None
        self.is_initialized = False
        self.lock = threading.Lock()
        
        # 统计信息
        self.total_queries = 0
        self.total_tokens = 0
        self.total_processing_time = 0.0
        self.start_time = time.time()
        
        # 初始化模型
        self._initialize_model()
    
    def _initialize_model(self):
        """初始化模型"""
        try:
            if self.model_type == RockXQlibAIModelType.GPT_3_5_TURBO or self.model_type == RockXQlibAIModelType.GPT_4:
                self._initialize_openai_model()
            elif self.model_type in [RockXQlibAIModelType.CLAUDE_3_SONNET, RockXQlibAIModelType.CLAUDE_3_OPUS]:
                self._initialize_claude_model()
            elif self.model_type == RockXQlibAIModelType.LOCAL_LLM:
                self._initialize_local_model()
            else:
                self._initialize_custom_model()
            
            self.is_initialized = True
            logger.info(f"AI模型 {self.model_type.value} 初始化成功")
            
        except Exception as e:
            logger.error(f"AI模型初始化失败: {e}")
            self.is_initialized = False
    
    def _initialize_openai_model(self):
        """初始化OpenAI模型"""
        try:
            import openai
            openai.api_key = self.model_config.get('api_key')
            self.model = openai
            logger.info("OpenAI模型初始化成功")
        except ImportError:
            logger.error("OpenAI库未安装")
            raise
        except Exception as e:
            logger.error(f"OpenAI模型初始化失败: {e}")
            raise
    
    def _initialize_claude_model(self):
        """初始化Claude模型"""
        try:
            import anthropic
            self.model = anthropic.Anthropic(api_key=self.model_config.get('api_key'))
            logger.info("Claude模型初始化成功")
        except ImportError:
            logger.error("Anthropic库未安装")
            raise
        except Exception as e:
            logger.error(f"Claude模型初始化失败: {e}")
            raise
    
    def _initialize_local_model(self):
        """初始化本地模型"""
        try:
            # 这里可以集成各种本地LLM，如Ollama、Transformers等
            model_path = self.model_config.get('model_path')
            if not model_path:
                raise ValueError("本地模型路径未配置")
            
            # 示例：使用transformers加载本地模型
            from transformers import AutoTokenizer, AutoModelForCausalLM
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForCausalLM.from_pretrained(model_path)
            logger.info(f"本地模型 {model_path} 初始化成功")
        except Exception as e:
            logger.error(f"本地模型初始化失败: {e}")
            raise
    
    def _initialize_custom_model(self):
        """初始化自定义模型"""
        try:
            # 自定义模型初始化逻辑
            model_class = self.model_config.get('model_class')
            if not model_class:
                raise ValueError("自定义模型类未配置")
            
            # 动态导入和实例化
            module_name, class_name = model_class.rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            model_class_obj = getattr(module, class_name)
            self.model = model_class_obj(**self.model_config.get('model_kwargs', {}))
            logger.info("自定义模型初始化成功")
        except Exception as e:
            logger.error(f"自定义模型初始化失败: {e}")
            raise
    
    def generate_text(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        try:
            if not self.is_initialized:
                raise RuntimeError("模型未初始化")
            
            start_time = time.time()
            
            with self.lock:
                if self.model_type in [RockXQlibAIModelType.GPT_3_5_TURBO, RockXQlibAIModelType.GPT_4]:
                    response = self._generate_openai_text(prompt, **kwargs)
                elif self.model_type in [RockXQlibAIModelType.CLAUDE_3_SONNET, RockXQlibAIModelType.CLAUDE_3_OPUS]:
                    response = self._generate_claude_text(prompt, **kwargs)
                elif self.model_type == RockXQlibAIModelType.LOCAL_LLM:
                    response = self._generate_local_text(prompt, **kwargs)
                else:
                    response = self._generate_custom_text(prompt, **kwargs)
                
                # 更新统计
                processing_time = time.time() - start_time
                self.total_queries += 1
                self.total_processing_time += processing_time
                
                return response
                
        except Exception as e:
            logger.error(f"生成文本失败: {e}")
            raise
    
    def _generate_openai_text(self, prompt: str, **kwargs) -> str:
        """使用OpenAI生成文本"""
        try:
            response = self.model.ChatCompletion.create(
                model=self.model_type.value,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI文本生成失败: {e}")
            raise
    
    def _generate_claude_text(self, prompt: str, **kwargs) -> str:
        """使用Claude生成文本"""
        try:
            response = self.model.messages.create(
                model=self.model_type.value,
                max_tokens=kwargs.get('max_tokens', 1000),
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude文本生成失败: {e}")
            raise
    
    def _generate_local_text(self, prompt: str, **kwargs) -> str:
        """使用本地模型生成文本"""
        try:
            inputs = self.tokenizer.encode(prompt, return_tensors="pt")
            with self.model.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_length=kwargs.get('max_length', 512),
                    num_return_sequences=1,
                    temperature=kwargs.get('temperature', 0.7),
                    do_sample=True
                )
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return response[len(prompt):].strip()
        except Exception as e:
            logger.error(f"本地模型文本生成失败: {e}")
            raise
    
    def _generate_custom_text(self, prompt: str, **kwargs) -> str:
        """使用自定义模型生成文本"""
        try:
            return self.model.generate(prompt, **kwargs)
        except Exception as e:
            logger.error(f"自定义模型文本生成失败: {e}")
            raise
    
    def analyze_data(self, data: Any, analysis_type: RockXQlibAnalysisType) -> Dict[str, Any]:
        """分析数据"""
        try:
            # 构建分析提示
            prompt = self._build_analysis_prompt(data, analysis_type)
            
            # 生成分析
            analysis = self.generate_text(prompt)
            
            # 解析分析结果
            result = self._parse_analysis_result(analysis, analysis_type)
            
            return result
            
        except Exception as e:
            logger.error(f"数据分析失败: {e}")
            return {"error": str(e)}
    
    def _build_analysis_prompt(self, data: Any, analysis_type: RockXQlibAnalysisType) -> str:
        """构建分析提示"""
        data_str = str(data)[:2000]  # 限制数据长度
        
        prompts = {
            RockXQlibAnalysisType.INSIGHT: f"""
请分析以下量化数据并提供洞察：
数据: {data_str}

请从以下角度分析：
1. 数据趋势和模式
2. 异常值和异常情况
3. 潜在的投资机会
4. 风险因素
5. 建议的后续行动

请用简洁明了的语言回答。
""",
            RockXQlibAnalysisType.PREDICTION: f"""
请基于以下数据预测未来趋势：
数据: {data_str}

请提供：
1. 短期预测（1-7天）
2. 中期预测（1-4周）
3. 长期预测（1-3个月）
4. 预测的置信度
5. 影响预测的关键因素

请用数据支撑你的预测。
""",
            RockXQlibAnalysisType.STRATEGY: f"""
请基于以下数据设计量化策略：
数据: {data_str}

请提供：
1. 策略概述
2. 入场条件
3. 出场条件
4. 风险控制措施
5. 预期收益和风险
6. 实施建议

请确保策略具有可操作性。
""",
            RockXQlibAnalysisType.RISK: f"""
请评估以下数据的风险：
数据: {data_str}

请分析：
1. 市场风险
2. 流动性风险
3. 信用风险
4. 操作风险
5. 风险等级评估
6. 风险缓解建议

请提供具体的风险指标。
""",
            RockXQlibAnalysisType.OPTIMIZATION: f"""
请优化以下量化策略：
数据: {data_str}

请提供：
1. 当前策略的问题
2. 优化建议
3. 参数调整方案
4. 性能提升预期
5. 实施步骤
6. 监控指标

请确保优化方案具有可操作性。
""",
            RockXQlibAnalysisType.EXPLANATION: f"""
请解释以下量化概念或结果：
数据: {data_str}

请提供：
1. 概念解释
2. 计算过程
3. 实际意义
4. 应用场景
5. 注意事项
6. 相关概念

请用通俗易懂的语言解释。
"""
        }
        
        return prompts.get(analysis_type, f"请分析以下数据：{data_str}")
    
    def _parse_analysis_result(self, analysis: str, analysis_type: RockXQlibAnalysisType) -> Dict[str, Any]:
        """解析分析结果"""
        try:
            # 尝试解析JSON格式的结果
            if analysis.strip().startswith('{'):
                return json.loads(analysis)
            
            # 否则返回文本结果
            return {
                "analysis_type": analysis_type.value,
                "result": analysis,
                "timestamp": time.time(),
                "model_type": self.model_type.value
            }
            
        except Exception as e:
            logger.warning(f"解析分析结果失败: {e}")
            return {
                "analysis_type": analysis_type.value,
                "result": analysis,
                "timestamp": time.time(),
                "model_type": self.model_type.value,
                "parse_error": str(e)
            }
    
    def generate_strategy(self, requirements: Dict[str, Any]) -> str:
        """生成策略"""
        try:
            prompt = f"""
请基于以下要求生成量化策略：

要求：
{json.dumps(requirements, indent=2, ensure_ascii=False)}

请提供：
1. 策略名称和描述
2. 策略逻辑
3. 参数设置
4. 风险控制
5. 实施步骤
6. 预期效果

请确保策略具有可操作性和实用性。
"""
            
            return self.generate_text(prompt)
            
        except Exception as e:
            logger.error(f"生成策略失败: {e}")
            return f"策略生成失败: {e}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        return {
            'model_type': self.model_type.value,
            'is_initialized': self.is_initialized,
            'uptime': uptime,
            'total_queries': self.total_queries,
            'total_tokens': self.total_tokens,
            'total_processing_time': self.total_processing_time,
            'average_processing_time': self.total_processing_time / max(self.total_queries, 1),
            'queries_per_minute': self.total_queries / max(uptime / 60, 1)
        }

class RockXQlibKnowledgeBase:
    """知识库系统"""
    
    def __init__(self, knowledge_base_path: Optional[str] = None, 
                 vector_db_path: Optional[str] = None):
        self.knowledge_base_path = knowledge_base_path or "knowledge_base.json"
        self.vector_db_path = vector_db_path or "vector_kb"
        
        # 传统知识库
        self.knowledge_graph = {}
        self.strategy_knowledge = {}
        self.market_knowledge = {}
        self.technical_knowledge = {}
        
        # 向量数据库
        self.vector_db = None
        self.text_vectorizer = None
        
        self.lock = threading.Lock()
        
        # 统计信息
        self.total_queries = 0
        self.total_additions = 0
        self.start_time = time.time()
        
        # 初始化向量数据库
        self._initialize_vector_database()
        
        # 加载知识库
        self._load_knowledge_base()
    
    def _initialize_vector_database(self):
        """初始化向量数据库"""
        try:
            from .vector_database import RockXQlibVectorDatabase, RockXQlibTextVectorizer
            
            # 初始化向量数据库
            self.vector_db = RockXQlibVectorDatabase(
                dimension=384,  # sentence-transformers默认维度
                persist_path=self.vector_db_path
            )
            
            # 初始化文本向量化器
            self.text_vectorizer = RockXQlibTextVectorizer()
            
            logger.info("向量数据库初始化成功")
            
        except Exception as e:
            logger.warning(f"向量数据库初始化失败: {e}")
            self.vector_db = None
            self.text_vectorizer = None
    
    def _load_knowledge_base(self):
        """加载知识库"""
        try:
            if Path(self.knowledge_base_path).exists():
                with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.knowledge_graph = data.get('knowledge_graph', {})
                    self.strategy_knowledge = data.get('strategy_knowledge', {})
                    self.market_knowledge = data.get('market_knowledge', {})
                    self.technical_knowledge = data.get('technical_knowledge', {})
                logger.info("知识库加载成功")
            else:
                logger.info("知识库文件不存在，将创建新的知识库")
        except Exception as e:
            logger.error(f"加载知识库失败: {e}")
    
    def _save_knowledge_base(self):
        """保存知识库"""
        try:
            with self.lock:
                data = {
                    'knowledge_graph': self.knowledge_graph,
                    'strategy_knowledge': self.strategy_knowledge,
                    'market_knowledge': self.market_knowledge,
                    'technical_knowledge': self.technical_knowledge,
                    'last_updated': time.time()
                }
                
                with open(self.knowledge_base_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                logger.debug("知识库保存成功")
        except Exception as e:
            logger.error(f"保存知识库失败: {e}")
    
    def add_knowledge(self, knowledge_type: str, knowledge: Any, metadata: Optional[Dict[str, Any]] = None):
        """添加知识"""
        try:
            with self.lock:
                knowledge_id = str(hashlib.md5(f"{knowledge_type}_{time.time()}_{id(knowledge)}".encode()).hexdigest()[:12])
                
                knowledge_item = {
                    'id': knowledge_id,
                    'type': knowledge_type,
                    'content': knowledge,
                    'metadata': metadata or {},
                    'timestamp': time.time()
                }
                
                # 添加到传统知识库
                if knowledge_type == 'strategy':
                    self.strategy_knowledge[knowledge_id] = knowledge_item
                elif knowledge_type == 'market':
                    self.market_knowledge[knowledge_id] = knowledge_item
                elif knowledge_type == 'technical':
                    self.technical_knowledge[knowledge_id] = knowledge_item
                else:
                    self.knowledge_graph[knowledge_id] = knowledge_item
                
                # 添加到向量数据库
                if self.vector_db and self.text_vectorizer:
                    try:
                        # 将知识转换为文本
                        knowledge_text = str(knowledge)
                        if isinstance(knowledge, dict):
                            knowledge_text = json.dumps(knowledge, ensure_ascii=False)
                        
                        # 向量化
                        vector = self.text_vectorizer.encode_text(knowledge_text)
                        
                        # 添加到向量数据库
                        vector_metadata = {
                            'knowledge_id': knowledge_id,
                            'knowledge_type': knowledge_type,
                            'original_metadata': metadata or {}
                        }
                        
                        self.vector_db.add_vector(
                            vector=vector,
                            text=knowledge_text,
                            metadata=vector_metadata,
                            vector_id=knowledge_id
                        )
                        
                    except Exception as e:
                        logger.warning(f"添加知识到向量数据库失败: {e}")
                
                self.total_additions += 1
                self._save_knowledge_base()
                
                logger.info(f"知识 {knowledge_id} 已添加到 {knowledge_type} 知识库")
                
        except Exception as e:
            logger.error(f"添加知识失败: {e}")
    
    def query_knowledge(self, query: str, knowledge_type: Optional[str] = None, 
                       use_vector_search: bool = True, top_k: int = 10) -> List[Any]:
        """查询知识"""
        try:
            with self.lock:
                self.total_queries += 1
                results = []
                
                # 向量搜索
                if use_vector_search and self.vector_db and self.text_vectorizer:
                    try:
                        # 将查询向量化
                        query_vector = self.text_vectorizer.encode_text(query)
                        
                        # 向量搜索
                        vector_results = self.vector_db.search(query_vector, k=top_k)
                        
                        # 转换为知识库格式
                        for result in vector_results:
                            knowledge_item = {
                                'id': result['vector_id'],
                                'type': result['metadata'].get('knowledge_type', 'unknown'),
                                'content': result['text'],
                                'metadata': result['metadata'].get('original_metadata', {}),
                                'timestamp': result['timestamp'],
                                'similarity_score': result['score']
                            }
                            
                            # 类型过滤
                            if knowledge_type is None or knowledge_item['type'] == knowledge_type:
                                results.append(knowledge_item)
                        
                        # 按相似度排序
                        results.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
                        
                    except Exception as e:
                        logger.warning(f"向量搜索失败，回退到传统搜索: {e}")
                        use_vector_search = False
                
                # 传统搜索（作为补充或回退）
                if not use_vector_search or len(results) < top_k:
                    traditional_results = []
                    
                    # 根据类型查询
                    if knowledge_type == 'strategy':
                        traditional_results.extend(self._search_knowledge(self.strategy_knowledge, query))
                    elif knowledge_type == 'market':
                        traditional_results.extend(self._search_knowledge(self.market_knowledge, query))
                    elif knowledge_type == 'technical':
                        traditional_results.extend(self._search_knowledge(self.technical_knowledge, query))
                    else:
                        # 查询所有类型
                        traditional_results.extend(self._search_knowledge(self.knowledge_graph, query))
                        traditional_results.extend(self._search_knowledge(self.strategy_knowledge, query))
                        traditional_results.extend(self._search_knowledge(self.market_knowledge, query))
                        traditional_results.extend(self._search_knowledge(self.technical_knowledge, query))
                    
                    # 合并结果
                    existing_ids = {r.get('id') for r in results}
                    for result in traditional_results:
                        if result.get('id') not in existing_ids:
                            results.append(result)
                
                # 去重和排序
                seen_ids = set()
                unique_results = []
                for result in results:
                    result_id = result.get('id')
                    if result_id and result_id not in seen_ids:
                        seen_ids.add(result_id)
                        unique_results.append(result)
                
                # 按时间戳排序（如果没有相似度分数）
                unique_results.sort(key=lambda x: x.get('similarity_score', x.get('timestamp', 0)), reverse=True)
                
                return unique_results[:top_k]
                
        except Exception as e:
            logger.error(f"查询知识失败: {e}")
            return []
    
    def _search_knowledge(self, knowledge_dict: Dict[str, Any], query: str) -> List[Any]:
        """搜索知识"""
        results = []
        query_lower = query.lower()
        
        for knowledge_id, knowledge_item in knowledge_dict.items():
            content = str(knowledge_item.get('content', '')).lower()
            if query_lower in content:
                results.append(knowledge_item)
        
        return results
    
    def get_recommendations(self, context: Dict[str, Any]) -> List[Any]:
        """获取推荐"""
        try:
            recommendations = []
            
            # 基于上下文推荐策略
            if 'strategy_type' in context:
                strategy_type = context['strategy_type']
                for knowledge_id, knowledge_item in self.strategy_knowledge.items():
                    if strategy_type.lower() in str(knowledge_item.get('content', '')).lower():
                        recommendations.append(knowledge_item)
            
            # 基于市场条件推荐
            if 'market_condition' in context:
                market_condition = context['market_condition']
                for knowledge_id, knowledge_item in self.market_knowledge.items():
                    if market_condition.lower() in str(knowledge_item.get('content', '')).lower():
                        recommendations.append(knowledge_item)
            
            # 基于技术指标推荐
            if 'technical_indicator' in context:
                technical_indicator = context['technical_indicator']
                for knowledge_id, knowledge_item in self.technical_knowledge.items():
                    if technical_indicator.lower() in str(knowledge_item.get('content', '')).lower():
                        recommendations.append(knowledge_item)
            
            # 去重和排序
            recommendations = list(set(recommendations))
            recommendations.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            return recommendations[:10]  # 返回前10个推荐
            
        except Exception as e:
            logger.error(f"获取推荐失败: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'uptime': uptime,
                'total_queries': self.total_queries,
                'total_additions': self.total_additions,
                'knowledge_graph_size': len(self.knowledge_graph),
                'strategy_knowledge_size': len(self.strategy_knowledge),
                'market_knowledge_size': len(self.market_knowledge),
                'technical_knowledge_size': len(self.technical_knowledge),
                'queries_per_minute': self.total_queries / max(uptime / 60, 1)
            }
    
    def cleanup(self):
        """清理资源"""
        try:
            self._save_knowledge_base()
            logger.info("知识库清理完成")
        except Exception as e:
            logger.error(f"知识库清理失败: {e}")


class RockXQlibAIIntegrationManager:
    """AI 功能集成管理器（门面类）

    把「大模型分析」「知识库检索」「智能分析」三类能力聚合到一个无参可构造的
    入口上，供节点层直接调用（节点里写的是 RockXQlibAIIntegrationManager()）。

    设计要点：
    - 后端全部惰性创建，构造管理器本身不触发任何网络请求或模型加载；
    - 任何一个后端不可用（未装依赖、没配 API Key、Ollama 没启动）时，
      对应能力降级为本地启发式实现并记 warning，**不抛异常**，
      保证工作流执行链路不会因为 AI 组件缺失而中断。
    """

    def __init__(self,
                 knowledge_base_path: Optional[str] = None,
                 model_type: Optional[RockXQlibAIModelType] = None,
                 model_config: Optional[Dict[str, Any]] = None):
        self.knowledge_base_path = knowledge_base_path
        self._model_type = model_type or RockXQlibAIModelType.LOCAL_LLM
        self._model_config = dict(model_config or {})
        self._model_interface = None
        self._knowledge_base = None
        self._init_lock = threading.Lock()
        self.total_analysis = 0
        self.total_searches = 0
        self.start_time = time.time()

    # ------------------------------------------------------------------
    # 惰性后端
    # ------------------------------------------------------------------
    def _get_model_interface(self):
        """惰性创建大模型接口；失败时缓存 False，避免反复重试。"""
        if self._model_interface is None:
            with self._init_lock:
                if self._model_interface is None:
                    try:
                        self._model_interface = RockXQlibAIModelInterface(
                            self._model_type, dict(self._model_config))
                    except Exception as e:
                        logger.warning(f"大模型接口不可用，将使用本地分析: {e}")
                        self._model_interface = False
        return self._model_interface or None

    def _get_knowledge_base(self):
        """惰性创建知识库；失败时缓存 False。"""
        if self._knowledge_base is None:
            with self._init_lock:
                if self._knowledge_base is None:
                    try:
                        self._knowledge_base = RockXQlibKnowledgeBase(
                            self.knowledge_base_path)
                    except Exception as e:
                        logger.warning(f"知识库不可用，将返回空检索结果: {e}")
                        self._knowledge_base = False
        return self._knowledge_base or None

    # ------------------------------------------------------------------
    # 对外能力
    # ------------------------------------------------------------------
    def generate_analysis(self, query: str, analysis_type: str = "insight",
                          **kwargs) -> str:
        """大模型分析，返回分析文本。

        节点 QlibLLMNode 调用方式：
            generate_analysis(query=prompt, analysis_type=analysis_type)
        """
        self.total_analysis += 1
        iface = self._get_model_interface()
        if iface is not None:
            try:
                text = iface.generate_text(query, **kwargs)
                if text:
                    return text
            except Exception as e:
                logger.warning(f"大模型分析失败，降级为本地分析: {e}")
        return self._local_analysis(query, analysis_type)

    def _local_analysis(self, query: str, analysis_type: str) -> str:
        """本地启发式分析：不依赖任何外部服务，保证链路始终可用。"""
        preview = (query or "").strip().replace("\n", " ")
        if len(preview) > 300:
            preview = preview[:300] + "..."
        hints = {
            "insight": "已对输入做结构化解读：关注数值分布、极值位置与异常点。",
            "prediction": "已做趋势外推：请结合模型的 IC/RankIC 判断预测可信度。",
            "strategy": "已生成策略建议：注意仓位上限、换手成本与回撤约束。",
            "risk": "已完成风险扫描：关注最大回撤、波动率与集中度。",
            "optimization": "已完成参数优化建议：注意过拟合，建议样本外验证。",
            "explanation": "已生成解释：特征贡献度可用于归因分析。",
        }
        hint = hints.get(str(analysis_type).lower(), hints["insight"])
        return (f"[本地分析 · 未接入外部大模型]\n"
                f"分析类型: {analysis_type}\n"
                f"结论: {hint}\n"
                f"输入摘要: {preview}")

    def search_knowledge_base(self, query: str, search_type: str = "semantic",
                              max_results: int = 10) -> List[Dict[str, Any]]:
        """知识库检索。

        节点 QlibKnowledgeBaseNode 调用方式：
            search_knowledge_base(query=..., search_type=..., max_results=...)
        """
        self.total_searches += 1
        kb = self._get_knowledge_base()
        if kb is None:
            return []
        try:
            use_vector = str(search_type).lower() in ("semantic", "vector", "hybrid")
            raw = kb.query_knowledge(query,
                                     use_vector_search=use_vector,
                                     top_k=max_results)
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")
            return []

        results = []
        for item in raw or []:
            if isinstance(item, dict):
                results.append(item)
            else:
                results.append({
                    "content": getattr(item, "content", str(item)),
                    "score": getattr(item, "score", None),
                    "type": getattr(item, "knowledge_type", None),
                })
        return results[:max_results]

    def generate_smart_analysis(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """智能分析：结合行情数据、模型预测与知识库检索给出综合结论。

        节点 QlibSmartAnalysisNode 传入的 request 结构：
            {market_data, model_predictions, analysis_focus, time_horizon,
             include_risk_analysis, include_sentiment, confidence_threshold}
        """
        request = request or {}
        focus = request.get("analysis_focus", "综合")
        horizon = request.get("time_horizon", "中期")
        confidence_threshold = request.get("confidence_threshold", 0.6)

        market_data = request.get("market_data")
        predictions = request.get("model_predictions")

        findings = []
        if market_data is not None:
            findings.append(self._summarize_frame("行情数据", market_data))
        if predictions is not None:
            findings.append(self._summarize_frame("模型预测", predictions))

        kb_hits = []
        if request.get("include_sentiment"):
            kb_hits = self.search_knowledge_base(f"{focus} 市场情绪", max_results=3)

        risk_note = None
        if request.get("include_risk_analysis"):
            risk_note = self._risk_note(market_data)

        return {
            "focus": focus,
            "time_horizon": horizon,
            "confidence_threshold": confidence_threshold,
            "findings": findings,
            "risk_analysis": risk_note,
            "knowledge_hits": len(kb_hits),
            "knowledge": kb_hits,
            "backend": "llm" if self._get_model_interface() else "local",
        }

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _summarize_frame(label: str, data: Any) -> Dict[str, Any]:
        """对 DataFrame / dict 做轻量统计摘要，避免依赖具体数据结构。"""
        summary: Dict[str, Any] = {"label": label}
        try:
            import pandas as pd
            if isinstance(data, pd.DataFrame):
                summary["rows"] = int(len(data))
                summary["columns"] = list(map(str, data.columns))[:20]
                num = data.select_dtypes("number")
                if not num.empty:
                    last = num.iloc[-1]
                    summary["last"] = {str(k): float(v) for k, v in last.items()
                                       if pd.notna(v)}
                    summary["mean"] = {str(k): float(v) for k, v in num.mean().items()
                                       if pd.notna(v)}
                return summary
            if isinstance(data, pd.Series):
                summary["rows"] = int(len(data))
                if len(data):
                    summary["last"] = float(data.iloc[-1])
                    summary["mean"] = float(data.mean())
                return summary
        except Exception:
            pass
        summary["type"] = type(data).__name__
        if isinstance(data, dict):
            summary["keys"] = list(map(str, data.keys()))[:20]
        else:
            summary["preview"] = str(data)[:200]
        return summary

    @staticmethod
    def _risk_note(market_data: Any) -> Dict[str, Any]:
        """从行情数据提取基础风险指标（波动率、最大回撤）。"""
        note: Dict[str, Any] = {"available": False}
        try:
            import numpy as np
            import pandas as pd
            series = None
            if isinstance(market_data, pd.DataFrame):
                for col in ("$close", "close", "Close"):
                    if col in market_data.columns:
                        series = market_data[col]
                        break
                if series is None and not market_data.empty:
                    series = market_data.iloc[:, 0]
            elif isinstance(market_data, pd.Series):
                series = market_data
            if series is None or len(series) < 2:
                return note

            s = pd.Series(series).astype(float).dropna()
            if len(s) < 2:
                return note
            returns = s.pct_change().dropna()
            note["available"] = True
            note["observations"] = int(len(s))
            note["volatility"] = float(returns.std() * np.sqrt(252)) if len(returns) else 0.0
            cum = (1 + returns).cumprod()
            note["max_drawdown"] = float((cum / cum.cummax() - 1).min()) if len(cum) else 0.0
            note["total_return"] = float(cum.iloc[-1] - 1) if len(cum) else 0.0
        except Exception as e:
            note["error"] = str(e)[:120]
        return note

    def get_stats(self) -> Dict[str, Any]:
        """运行统计"""
        uptime = time.time() - self.start_time
        return {
            "uptime": uptime,
            "total_analysis": self.total_analysis,
            "total_searches": self.total_searches,
            "model_backend": "available" if self._get_model_interface() else "local-fallback",
            "knowledge_base": "available" if self._get_knowledge_base() else "unavailable",
        }

