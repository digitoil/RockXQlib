#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib AI SQL生成器
基于Chat2DB的AI功能，为量化分析提供智能SQL生成
"""

import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re

logger = logging.getLogger(__name__)

class SQLQueryType(Enum):
    """SQL查询类型"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    ANALYZE = "ANALYZE"

@dataclass
class QuantAnalysisTemplate:
    """量化分析模板"""
    name: str
    category: str
    description: str
    template: str
    parameters: List[str]
    example: str

class RockXQlibAISQLGenerator:
    """RockXQlib AI SQL生成器"""
    
    def __init__(self, chat2db_api_url: str = "http://localhost:10824"):
        self.api_url = chat2db_api_url
        self.templates = self._load_quant_templates()
        self.query_history = []
        self.total_generated = 0
        
        logger.info("AI SQL生成器初始化完成")
    
    def _load_quant_templates(self) -> List[QuantAnalysisTemplate]:
        """加载量化分析模板"""
        templates = [
            # 市场数据查询模板
            QuantAnalysisTemplate(
                name="股票行情查询",
                category="market_data",
                description="查询指定股票的行情数据",
                template="SELECT * FROM market_data WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}' ORDER BY datetime",
                parameters=["symbol", "start_date", "end_date"],
                example="查询平安银行(000001)最近30天的行情数据"
            ),
            QuantAnalysisTemplate(
                name="获取最新价格",
                category="market_data",
                description="获取股票最新价格",
                template="SELECT symbol, close, volume, datetime FROM market_data WHERE datetime = (SELECT MAX(datetime) FROM market_data WHERE symbol = '{symbol}')",
                parameters=["symbol"],
                example="获取平安银行最新价格"
            ),
            QuantAnalysisTemplate(
                name="价格统计",
                category="market_data",
                description="计算价格统计信息",
                template="SELECT symbol, MIN(low) as min_price, MAX(high) as max_price, AVG(close) as avg_price, COUNT(*) as data_count FROM market_data WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'",
                parameters=["symbol", "start_date", "end_date"],
                example="计算平安银行最近一年的价格统计"
            ),
            
            # 技术指标计算模板
            QuantAnalysisTemplate(
                name="移动平均线",
                category="technical_indicators",
                description="计算移动平均线",
                template="SELECT symbol, datetime, close, AVG(close) OVER (PARTITION BY symbol ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as ma_{window} FROM market_data WHERE symbol = '{symbol}' ORDER BY datetime",
                parameters=["symbol", "window"],
                example="计算平安银行20日移动平均线"
            ),
            QuantAnalysisTemplate(
                name="相对强弱指数(RSI)",
                category="technical_indicators",
                description="计算RSI指标",
                template="""WITH price_changes AS (
                    SELECT symbol, datetime, close,
                           close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as price_change
                    FROM market_data WHERE symbol = '{symbol}'
                ),
                rsi_calculation AS (
                    SELECT symbol, datetime, close,
                           AVG(CASE WHEN price_change > 0 THEN price_change ELSE 0 END) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as avg_gain,
                           AVG(CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as avg_loss
                    FROM price_changes
                )
                SELECT symbol, datetime, close,
                       CASE WHEN avg_loss = 0 THEN 100
                            ELSE 100 - (100 / (1 + avg_gain / avg_loss))
                       END as rsi_{period}
                FROM rsi_calculation ORDER BY datetime""",
                parameters=["symbol", "period"],
                example="计算平安银行14日RSI"
            ),
            QuantAnalysisTemplate(
                name="布林带",
                category="technical_indicators",
                description="计算布林带指标",
                template="""SELECT symbol, datetime, close,
                       AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as middle_band,
                       AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) + 
                       {std_dev} * STDDEV(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as upper_band,
                       AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) - 
                       {std_dev} * STDDEV(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as lower_band
                FROM market_data WHERE symbol = '{symbol}' ORDER BY datetime""",
                parameters=["symbol", "period", "std_dev"],
                example="计算平安银行20日布林带"
            ),
            
            # 策略分析模板
            QuantAnalysisTemplate(
                name="策略回测结果",
                category="strategy",
                description="查询策略回测结果",
                template="SELECT * FROM backtest_result WHERE strategy_name = '{strategy_name}' ORDER BY created_time DESC LIMIT {limit}",
                parameters=["strategy_name", "limit"],
                example="查询双均线策略的回测结果"
            ),
            QuantAnalysisTemplate(
                name="策略配置",
                category="strategy",
                description="查询策略配置信息",
                template="SELECT * FROM strategy_config WHERE strategy_name = '{strategy_name}'",
                parameters=["strategy_name"],
                example="查询MACD策略的配置参数"
            ),
            QuantAnalysisTemplate(
                name="策略性能统计",
                category="strategy",
                description="统计策略性能指标",
                template="SELECT strategy_name, COUNT(*) as backtest_count, AVG(total_return) as avg_return, AVG(max_drawdown) as avg_drawdown, AVG(sharpe_ratio) as avg_sharpe FROM backtest_result WHERE created_time >= '{start_date}' GROUP BY strategy_name ORDER BY avg_return DESC",
                parameters=["start_date"],
                example="统计最近一年的策略性能"
            ),
            
            # 风险分析模板
            QuantAnalysisTemplate(
                name="收益率分析",
                category="risk_analysis",
                description="计算股票收益率",
                template="SELECT symbol, datetime, close, (close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as return_rate FROM market_data WHERE symbol = '{symbol}' ORDER BY datetime",
                parameters=["symbol"],
                example="计算平安银行的日收益率"
            ),
            QuantAnalysisTemplate(
                name="波动率计算",
                category="risk_analysis",
                description="计算股票波动率",
                template="""WITH returns AS (
                    SELECT symbol, datetime, close,
                           (close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as return_rate
                    FROM market_data WHERE symbol = '{symbol}'
                )
                SELECT symbol, datetime, close, return_rate,
                       STDDEV(return_rate) OVER (ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as volatility_{window}
                FROM returns ORDER BY datetime""",
                parameters=["symbol", "window"],
                example="计算平安银行20日波动率"
            ),
            QuantAnalysisTemplate(
                name="最大回撤",
                category="risk_analysis",
                description="计算最大回撤",
                template="""WITH cumulative_returns AS (
                    SELECT symbol, datetime, close,
                           (close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as return_rate
                    FROM market_data WHERE symbol = '{symbol}'
                ),
                cumulative_products AS (
                    SELECT symbol, datetime, close, return_rate,
                           EXP(SUM(LN(1 + COALESCE(return_rate, 0))) OVER (PARTITION BY symbol ORDER BY datetime)) as cumulative_return
                    FROM cumulative_returns
                ),
                running_max AS (
                    SELECT symbol, datetime, close, return_rate, cumulative_return,
                           MAX(cumulative_return) OVER (PARTITION BY symbol ORDER BY datetime) as running_max_return
                    FROM cumulative_products
                )
                SELECT symbol, datetime, close, return_rate, cumulative_return, running_max_return,
                       (cumulative_return - running_max_return) / running_max_return as drawdown
                FROM running_max ORDER BY datetime""",
                parameters=["symbol"],
                example="计算平安银行的最大回撤"
            )
        ]
        
        return templates
    
    def generate_sql_from_natural_language(self, query: str, database: str = "sqlite") -> Dict[str, Any]:
        """从自然语言生成SQL"""
        try:
            # 首先尝试使用模板匹配
            template_result = self._try_template_matching(query)
            if template_result:
                return template_result
            
            # 如果模板匹配失败，使用AI生成
            return self._generate_with_ai(query, database)
            
        except Exception as e:
            logger.error(f"生成SQL失败: {e}")
            return {"error": str(e), "sql": "", "explanation": ""}
    
    def _try_template_matching(self, query: str) -> Optional[Dict[str, Any]]:
        """尝试使用模板匹配"""
        query_lower = query.lower()
        
        for template in self.templates:
            # 简单的关键词匹配
            if any(keyword in query_lower for keyword in template.name.lower().split()):
                # 尝试提取参数
                params = self._extract_parameters(query, template.parameters)
                if params:
                    sql = template.template.format(**params)
                    return {
                        "sql": sql,
                        "explanation": f"使用模板: {template.name}",
                        "template": template.name,
                        "parameters": params,
                        "category": template.category
                    }
        
        return None
    
    def _extract_parameters(self, query: str, parameters: List[str]) -> Dict[str, str]:
        """从查询中提取参数"""
        params = {}
        
        # 简单的参数提取逻辑
        for param in parameters:
            if param == "symbol":
                # 提取股票代码
                symbol_match = re.search(r'([0-9]{6})', query)
                if symbol_match:
                    params[param] = symbol_match.group(1)
                else:
                    # 尝试提取股票名称
                    name_match = re.search(r'([\u4e00-\u9fa5]+)', query)
                    if name_match:
                        params[param] = name_match.group(1)
            
            elif param == "start_date":
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', query)
                if date_match:
                    params[param] = date_match.group(1)
                else:
                    params[param] = "2023-01-01"  # 默认值
            
            elif param == "end_date":
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', query)
                if date_match:
                    params[param] = date_match.group(1)
                else:
                    params[param] = "2024-12-31"  # 默认值
            
            elif param == "window":
                window_match = re.search(r'(\d+)日', query)
                if window_match:
                    params[param] = window_match.group(1)
                else:
                    params[param] = "20"  # 默认值
            
            elif param == "period":
                period_match = re.search(r'(\d+)日', query)
                if period_match:
                    params[param] = period_match.group(1)
                else:
                    params[param] = "14"  # 默认值
            
            elif param == "std_dev":
                params[param] = "2"  # 默认值
            
            elif param == "strategy_name":
                strategy_match = re.search(r'([\u4e00-\u9fa5]+策略)', query)
                if strategy_match:
                    params[param] = strategy_match.group(1)
                else:
                    params[param] = "默认策略"
            
            elif param == "limit":
                limit_match = re.search(r'(\d+)条', query)
                if limit_match:
                    params[param] = limit_match.group(1)
                else:
                    params[param] = "10"  # 默认值
        
        return params
    
    def _generate_with_ai(self, query: str, database: str) -> Dict[str, Any]:
        """使用AI生成SQL"""
        try:
            # 构建AI提示词
            prompt = self._build_ai_prompt(query, database)
            
            # 调用Chat2DB API
            payload = {
                "query": prompt,
                "database": database,
                "ai_enabled": True
            }
            
            response = requests.post(
                f"{self.api_url}/api/ai/sql",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.total_generated += 1
                self.query_history.append({
                    "query": query,
                    "sql": result.get("sql", ""),
                    "timestamp": time.time()
                })
                
                return {
                    "sql": result.get("sql", ""),
                    "explanation": result.get("explanation", ""),
                    "ai_generated": True,
                    "confidence": result.get("confidence", 0.8)
                }
            else:
                return {"error": f"AI API请求失败: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"AI生成SQL失败: {e}")
            return {"error": str(e), "sql": "", "explanation": ""}
    
    def _build_ai_prompt(self, query: str, database: str) -> str:
        """构建AI提示词"""
        schema_info = self._get_database_schema_info(database)
        
        prompt = f"""
你是一个专业的量化分析SQL专家。请根据用户的需求生成SQL查询语句。

数据库类型: {database}
数据库架构:
{schema_info}

用户需求: {query}

请生成相应的SQL查询语句，并简要解释查询的目的和逻辑。

要求:
1. SQL语句必须符合{database}的语法规范
2. 查询应该高效且准确
3. 包含适当的注释
4. 如果是量化分析相关的查询，请考虑性能优化

请以JSON格式返回结果:
{{
    "sql": "生成的SQL语句",
    "explanation": "查询说明",
    "confidence": 0.9
}}
"""
        return prompt
    
    def _get_database_schema_info(self, database: str) -> str:
        """获取数据库架构信息"""
        if database == "sqlite":
            return """
主要表结构:
- market_data: 行情数据表
  - symbol: 股票代码 (TEXT)
  - datetime: 时间 (TEXT)
  - open: 开盘价 (REAL)
  - high: 最高价 (REAL)
  - low: 最低价 (REAL)
  - close: 收盘价 (REAL)
  - volume: 成交量 (REAL)
  - amount: 成交额 (REAL)

- strategy_config: 策略配置表
  - strategy_name: 策略名称 (TEXT)
  - parameters: 参数配置 (TEXT)
  - created_time: 创建时间 (REAL)

- backtest_result: 回测结果表
  - strategy_name: 策略名称 (TEXT)
  - total_return: 总收益率 (REAL)
  - max_drawdown: 最大回撤 (REAL)
  - sharpe_ratio: 夏普比率 (REAL)
  - created_time: 创建时间 (REAL)
"""
        else:
            return f"数据库 {database} 的架构信息"
    
    def get_templates_by_category(self, category: str) -> List[QuantAnalysisTemplate]:
        """根据类别获取模板"""
        return [t for t in self.templates if t.category == category]
    
    def get_all_categories(self) -> List[str]:
        """获取所有模板类别"""
        return list(set(t.category for t in self.templates))
    
    def validate_sql(self, sql: str) -> Dict[str, Any]:
        """验证SQL语句"""
        try:
            # 基本的SQL语法检查
            sql_upper = sql.upper().strip()
            
            # 检查是否以SELECT开头
            if not sql_upper.startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                return {"valid": False, "error": "SQL语句必须以SELECT、INSERT、UPDATE、DELETE、CREATE、DROP或ALTER开头"}
            
            # 检查括号匹配
            if sql.count('(') != sql.count(')'):
                return {"valid": False, "error": "括号不匹配"}
            
            # 检查引号匹配
            single_quotes = sql.count("'")
            if single_quotes % 2 != 0:
                return {"valid": False, "error": "单引号不匹配"}
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def optimize_sql(self, sql: str) -> Dict[str, Any]:
        """优化SQL语句"""
        try:
            # 基本的SQL优化建议
            suggestions = []
            
            # 检查是否有LIMIT
            if "SELECT" in sql.upper() and "LIMIT" not in sql.upper():
                suggestions.append("建议添加LIMIT子句以限制结果数量")
            
            # 检查是否有WHERE条件
            if "SELECT" in sql.upper() and "WHERE" not in sql.upper():
                suggestions.append("建议添加WHERE条件以提高查询效率")
            
            # 检查是否有ORDER BY
            if "SELECT" in sql.upper() and "ORDER BY" not in sql.upper():
                suggestions.append("建议添加ORDER BY子句以确保结果顺序")
            
            return {
                "optimized": True,
                "suggestions": suggestions,
                "original_sql": sql
            }
            
        except Exception as e:
            return {"optimized": False, "error": str(e)}
    
    def get_query_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取查询历史"""
        return self.query_history[-limit:]
    
    def clear_history(self):
        """清空查询历史"""
        self.query_history.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_generated": self.total_generated,
            "template_count": len(self.templates),
            "category_count": len(self.get_all_categories()),
            "history_count": len(self.query_history)
        }
