#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI功能节点
集成LLM模型、知识库、智能分析等功能
"""

import os
import sys
import logging
import json
from typing import Dict, Any, Optional, List, Union

# 添加路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from core.qlib_core_integration import qlib_core
    from core.ai_integration import RockXQlibAIIntegrationManager
    from core.ollama_integration import RockXQlibOllamaInterface
    from NodeGraphQt import BaseNode
    NODEGRAPH_AVAILABLE = True
except ImportError as e:
    print(f"导入失败: {e}")
    # 创建占位符
    class BaseNode:
        def __init__(self):
            pass
    qlib_core = None
    RockXQlibAIIntegrationManager = None
    RockXQlibOllamaInterface = None
    NODEGRAPH_AVAILABLE = False

logger = logging.getLogger(__name__)

class QlibCoreBaseNode(BaseNode):
    """基于Qlib核心的基节点"""
    
    def __init__(self):
        super().__init__()
        self.qlib_core = qlib_core
        self._execution_result = None
        self._error_message = None
    
    def execute_qlib_operation(self, operation: str, **kwargs) -> Any:
        """执行Qlib操作"""
        try:
            if not self.qlib_core or not self.qlib_core.qlib_available:
                raise Exception("Qlib不可用")
            
            if operation == "initialize":
                return self.qlib_core.initialize_qlib(**kwargs)
            elif operation == "get_data":
                return self.qlib_core.get_qlib_data(**kwargs)
            elif operation == "create_dataset":
                return self.qlib_core.create_dataset(**kwargs)
            elif operation == "create_model":
                return self.qlib_core.create_model(**kwargs)
            elif operation == "create_strategy":
                return self.qlib_core.create_strategy(**kwargs)
            elif operation == "run_backtest":
                return self.qlib_core.run_backtest(**kwargs)
            else:
                raise Exception(f"未知的Qlib操作: {operation}")
                
        except Exception as e:
            logger.error(f"Qlib操作失败: {e}")
            self._error_message = str(e)
            return None
    
    def get_execution_result(self) -> Any:
        """获取执行结果"""
        return self._execution_result
    
    def get_error_message(self) -> Optional[str]:
        """获取错误信息"""
        return self._error_message

class QlibLLMNode(QlibCoreBaseNode):
    """Qlib LLM分析节点"""
    
    __identifier__ = 'qlib.ai.llm'
    NODE_NAME = 'LLM分析'
    type_ = 'qlib.ai.llm'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('data_input')
        self.add_output('analysis_result')
        
        # 添加属性
        self.add_text_input('model_name', '模型名称', 'qwen3:latest')
        self.add_text_input('analysis_type', '分析类型', 'insight')
        self.add_text_input('prompt_template', '提示模板', '请分析以下数据：{data}')
        self.add_checkbox('use_ollama', '使用Ollama', '使用Ollama', True)
        self.add_text_input('temperature', '温度', '0.7')
        self.add_text_input('max_tokens', '最大令牌', '1000')
    
    def execute(self) -> bool:
        """执行LLM分析"""
        try:
            # 检查输入
            data_input = self.get_input('data_input')
            if not data_input:
                raise Exception("输入数据为空")
            
            model_name = self.get_property('model_name')
            analysis_type = self.get_property('analysis_type')
            prompt_template = self.get_property('prompt_template')
            use_ollama = self.get_property('use_ollama')
            temperature = float(self.get_property('temperature'))
            max_tokens = int(self.get_property('max_tokens'))
            
            # 构建提示
            prompt = prompt_template.format(data=str(data_input))
            
            # 使用AI集成管理器
            if RockXQlibAIIntegrationManager:
                ai_manager = RockXQlibAIIntegrationManager()
                
                if use_ollama and RockXQlibOllamaInterface:
                    # 使用Ollama
                    ollama = RockXQlibOllamaInterface()
                    response = ollama.generate_text(
                        prompt=prompt,
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                else:
                    # 使用其他AI模型
                    response = ai_manager.generate_analysis(
                        query=prompt,
                        analysis_type=analysis_type
                    )
                
                self._execution_result = {
                    'status': 'success',
                    'analysis_type': analysis_type,
                    'model_name': model_name,
                    'response': response,
                    'input_data': data_input
                }
                self.set_output('analysis_result', self._execution_result)
                logger.info(f"✅ LLM分析完成: {analysis_type}")
                return True
            else:
                # 模拟AI分析
                self._execution_result = {
                    'status': 'success',
                    'analysis_type': analysis_type,
                    'model_name': model_name,
                    'response': f"模拟AI分析结果: {analysis_type} - {str(data_input)[:100]}...",
                    'input_data': data_input
                }
                self.set_output('analysis_result', self._execution_result)
                logger.info(f"✅ 模拟LLM分析完成: {analysis_type}")
                return True
                
        except Exception as e:
            logger.error(f"LLM分析节点执行失败: {e}")
            return False

class QlibKnowledgeBaseNode(QlibCoreBaseNode):
    """Qlib知识库节点"""
    
    __identifier__ = 'qlib.ai.knowledge'
    NODE_NAME = '知识库查询'
    type_ = 'qlib.ai.knowledge'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('query_input')
        self.add_output('knowledge_result')
        
        # 添加属性
        self.add_text_input('query', '查询内容', '')
        self.add_text_input('search_type', '搜索类型', 'semantic')
        self.add_text_input('max_results', '最大结果数', '5')
        self.add_checkbox('use_vector_db', '使用向量数据库', '使用向量数据库', True)
    
    def execute(self) -> bool:
        """执行知识库查询"""
        try:
            # 获取查询内容
            query_input = self.get_input('query_input')
            query = self.get_property('query') or str(query_input) if query_input else ""
            
            if not query:
                raise Exception("查询内容为空")
            
            search_type = self.get_property('search_type')
            max_results = int(self.get_property('max_results'))
            use_vector_db = self.get_property('use_vector_db')
            
            # 使用AI集成管理器
            if RockXQlibAIIntegrationManager:
                ai_manager = RockXQlibAIIntegrationManager()
                
                if use_vector_db:
                    # 使用向量数据库搜索
                    results = ai_manager.search_knowledge_base(
                        query=query,
                        search_type=search_type,
                        max_results=max_results
                    )
                else:
                    # 使用传统搜索
                    results = ai_manager.search_knowledge_base(
                        query=query,
                        search_type="keyword",
                        max_results=max_results
                    )
                
                self._execution_result = {
                    'status': 'success',
                    'query': query,
                    'search_type': search_type,
                    'results': results,
                    'result_count': len(results) if results else 0
                }
                self.set_output('knowledge_result', self._execution_result)
                logger.info(f"✅ 知识库查询完成: {len(results) if results else 0} 个结果")
                return True
            else:
                # 模拟知识库查询
                mock_results = [
                    {"title": f"相关文档 {i+1}", "content": f"这是关于'{query}'的相关内容 {i+1}", "score": 0.9 - i*0.1}
                    for i in range(min(max_results, 3))
                ]
                
                self._execution_result = {
                    'status': 'success',
                    'query': query,
                    'search_type': search_type,
                    'results': mock_results,
                    'result_count': len(mock_results)
                }
                self.set_output('knowledge_result', self._execution_result)
                logger.info(f"✅ 模拟知识库查询完成: {len(mock_results)} 个结果")
                return True
                
        except Exception as e:
            logger.error(f"知识库节点执行失败: {e}")
            return False

class QlibSmartAnalysisNode(QlibCoreBaseNode):
    """Qlib智能分析节点"""
    
    __identifier__ = 'qlib.ai.smart_analysis'
    NODE_NAME = '智能分析'
    type_ = 'qlib.ai.smart_analysis'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('market_data')
        self.add_input('model_predictions')
        self.add_output('smart_insights')
        
        # 添加属性
        self.add_text_input('analysis_focus', '分析重点', 'trend')
        self.add_text_input('time_horizon', '时间范围', 'short_term')
        self.add_checkbox('include_risk_analysis', '包含风险分析', '包含风险分析', True)
        self.add_checkbox('include_sentiment', '包含情绪分析', '包含情绪分析', True)
        self.add_text_input('confidence_threshold', '置信度阈值', '0.7')
    
    def execute(self) -> bool:
        """执行智能分析"""
        try:
            # 检查输入
            market_data = self.get_input('market_data')
            model_predictions = self.get_input('model_predictions')
            
            if not market_data and not model_predictions:
                raise Exception("输入数据为空")
            
            analysis_focus = self.get_property('analysis_focus')
            time_horizon = self.get_property('time_horizon')
            include_risk_analysis = self.get_property('include_risk_analysis')
            include_sentiment = self.get_property('include_sentiment')
            confidence_threshold = float(self.get_property('confidence_threshold'))
            
            # 构建分析请求
            analysis_request = {
                'market_data': market_data,
                'model_predictions': model_predictions,
                'analysis_focus': analysis_focus,
                'time_horizon': time_horizon,
                'include_risk_analysis': include_risk_analysis,
                'include_sentiment': include_sentiment,
                'confidence_threshold': confidence_threshold
            }
            
            # 使用AI集成管理器
            if RockXQlibAIIntegrationManager:
                ai_manager = RockXQlibAIIntegrationManager()
                
                insights = ai_manager.generate_smart_analysis(analysis_request)
                
                self._execution_result = {
                    'status': 'success',
                    'analysis_focus': analysis_focus,
                    'time_horizon': time_horizon,
                    'insights': insights,
                    'confidence_threshold': confidence_threshold
                }
                self.set_output('smart_insights', self._execution_result)
                logger.info(f"✅ 智能分析完成: {analysis_focus}")
                return True
            else:
                # 模拟智能分析
                mock_insights = {
                    'trend_analysis': f"基于{analysis_focus}的{time_horizon}趋势分析",
                    'risk_assessment': "风险分析结果" if include_risk_analysis else None,
                    'sentiment_analysis': "情绪分析结果" if include_sentiment else None,
                    'recommendations': ["建议1", "建议2", "建议3"],
                    'confidence_score': 0.85
                }
                
                self._execution_result = {
                    'status': 'success',
                    'analysis_focus': analysis_focus,
                    'time_horizon': time_horizon,
                    'insights': mock_insights,
                    'confidence_threshold': confidence_threshold
                }
                self.set_output('smart_insights', self._execution_result)
                logger.info(f"✅ 模拟智能分析完成: {analysis_focus}")
                return True
                
        except Exception as e:
            logger.error(f"智能分析节点执行失败: {e}")
            return False

class QlibOllamaNode(QlibCoreBaseNode):
    """Qlib Ollama本地模型节点"""
    
    __identifier__ = 'qlib.ai.ollama'
    NODE_NAME = 'Ollama本地模型'
    type_ = 'qlib.ai.ollama'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('prompt_input')
        self.add_output('ollama_response')
        
        # 添加属性
        self.add_text_input('model_name', '模型名称', 'qwen3:latest')
        self.add_text_input('prompt', '提示内容', '')
        self.add_text_input('temperature', '温度', '0.7')
        self.add_text_input('max_tokens', '最大令牌', '1000')
        self.add_text_input('ollama_url', 'Ollama地址', 'http://localhost:11434')
    
    def execute(self) -> bool:
        """执行Ollama模型调用"""
        try:
            # 获取提示内容
            prompt_input = self.get_input('prompt_input')
            prompt = self.get_property('prompt') or str(prompt_input) if prompt_input else ""
            
            if not prompt:
                raise Exception("提示内容为空")
            
            model_name = self.get_property('model_name')
            temperature = float(self.get_property('temperature'))
            max_tokens = int(self.get_property('max_tokens'))
            ollama_url = self.get_property('ollama_url')
            
            # 使用Ollama接口
            if RockXQlibOllamaInterface:
                ollama = RockXQlibOllamaInterface(base_url=ollama_url)
                
                response = ollama.generate_text(
                    prompt=prompt,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                self._execution_result = {
                    'status': 'success',
                    'model_name': model_name,
                    'prompt': prompt,
                    'response': response,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                }
                self.set_output('ollama_response', self._execution_result)
                logger.info(f"✅ Ollama模型调用完成: {model_name}")
                return True
            else:
                # 模拟Ollama响应
                mock_response = f"模拟Ollama响应 (模型: {model_name}): {prompt[:50]}..."
                
                self._execution_result = {
                    'status': 'success',
                    'model_name': model_name,
                    'prompt': prompt,
                    'response': mock_response,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                }
                self.set_output('ollama_response', self._execution_result)
                logger.info(f"✅ 模拟Ollama模型调用完成: {model_name}")
                return True
                
        except Exception as e:
            logger.error(f"Ollama节点执行失败: {e}")
            return False

# 导出所有节点类
__all__ = [
    'QlibCoreBaseNode',
    'QlibLLMNode',
    'QlibKnowledgeBaseNode',
    'QlibSmartAnalysisNode',
    'QlibOllamaNode'
]
