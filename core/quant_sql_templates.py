#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 量化分析SQL模板
提供专业的量化分析SQL查询模板和AI提示词
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class QuantAnalysisType(Enum):
    """量化分析类型"""
    MARKET_DATA = "market_data"
    TECHNICAL_INDICATORS = "technical_indicators"
    STRATEGY_ANALYSIS = "strategy_analysis"
    RISK_ANALYSIS = "risk_analysis"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    BACKTEST_ANALYSIS = "backtest_analysis"

@dataclass
class QuantSQLTemplate:
    """量化SQL模板"""
    name: str
    category: QuantAnalysisType
    description: str
    template: str
    parameters: List[str]
    example: str
    difficulty: str  # easy, medium, hard
    performance_tips: List[str]
    related_indicators: List[str]

class RockXQlibQuantSQLTemplates:
    """RockXQlib量化SQL模板管理器"""
    
    def __init__(self):
        self.templates = self._load_quant_templates()
        self.ai_prompts = self._load_ai_prompts()
        self.performance_tips = self._load_performance_tips()
        
        logger.info(f"量化SQL模板加载完成，共 {len(self.templates)} 个模板")
    
    def _load_quant_templates(self) -> List[QuantSQLTemplate]:
        """加载量化分析模板"""
        templates = [
            # 市场数据查询模板
            QuantSQLTemplate(
                name="基础行情查询",
                category=QuantAnalysisType.MARKET_DATA,
                description="查询股票基础行情数据",
                template="SELECT symbol, datetime, open, high, low, close, volume FROM market_data WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}' ORDER BY datetime",
                parameters=["symbol", "start_date", "end_date"],
                example="查询平安银行(000001)最近30天的行情数据",
                difficulty="easy",
                performance_tips=["添加索引: CREATE INDEX idx_symbol_datetime ON market_data(symbol, datetime)"],
                related_indicators=["价格", "成交量"]
            ),
            
            QuantSQLTemplate(
                name="多股票行情对比",
                category=QuantAnalysisType.MARKET_DATA,
                description="对比多只股票的行情数据",
                template="""SELECT symbol, datetime, close, 
                       AVG(close) OVER (PARTITION BY symbol ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as ma_{window}
                FROM market_data 
                WHERE symbol IN ({symbols}) AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY symbol, datetime""",
                parameters=["symbols", "start_date", "end_date", "window"],
                example="对比平安银行、招商银行、工商银行的20日均线",
                difficulty="medium",
                performance_tips=["使用IN查询时限制股票数量", "考虑分页查询"],
                related_indicators=["移动平均线", "价格对比"]
            ),
            
            QuantSQLTemplate(
                name="成交量分析",
                category=QuantAnalysisType.MARKET_DATA,
                description="分析股票成交量特征",
                template="""SELECT symbol, datetime, volume, close,
                       AVG(volume) OVER (PARTITION BY symbol ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as avg_volume,
                       volume / AVG(volume) OVER (PARTITION BY symbol ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as volume_ratio
                FROM market_data 
                WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "window"],
                example="分析平安银行成交量与20日均量的比值",
                difficulty="medium",
                performance_tips=["对volume字段建立索引", "使用窗口函数优化"],
                related_indicators=["成交量", "量比"]
            ),
            
            # 技术指标计算模板
            QuantSQLTemplate(
                name="简单移动平均线(SMA)",
                category=QuantAnalysisType.TECHNICAL_INDICATORS,
                description="计算简单移动平均线",
                template="""SELECT symbol, datetime, close,
                       AVG(close) OVER (PARTITION BY symbol ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as sma_{window}
                FROM market_data 
                WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "window"],
                example="计算平安银行20日简单移动平均线",
                difficulty="easy",
                performance_tips=["使用窗口函数提高性能", "考虑数据量大的情况"],
                related_indicators=["SMA", "移动平均线"]
            ),
            
            QuantSQLTemplate(
                name="指数移动平均线(EMA)",
                category=QuantAnalysisType.TECHNICAL_INDICATORS,
                description="计算指数移动平均线",
                template="""WITH ema_calc AS (
                    SELECT symbol, datetime, close,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY datetime) as rn
                    FROM market_data 
                    WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ),
                ema_recursive AS (
                    SELECT symbol, datetime, close, rn,
                           CASE WHEN rn = 1 THEN close
                                ELSE {alpha} * close + (1 - {alpha}) * LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)
                           END as ema_{window}
                    FROM ema_calc
                )
                SELECT symbol, datetime, close, ema_{window}
                FROM ema_recursive
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "window", "alpha"],
                example="计算平安银行20日指数移动平均线",
                difficulty="hard",
                performance_tips=["使用递归CTE", "alpha参数通常为2/(window+1)"],
                related_indicators=["EMA", "指数移动平均线"]
            ),
            
            QuantSQLTemplate(
                name="相对强弱指数(RSI)",
                category=QuantAnalysisType.TECHNICAL_INDICATORS,
                description="计算RSI指标",
                template="""WITH price_changes AS (
                    SELECT symbol, datetime, close,
                           close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as price_change
                    FROM market_data WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ),
                rsi_calculation AS (
                    SELECT symbol, datetime, close, price_change,
                           AVG(CASE WHEN price_change > 0 THEN price_change ELSE 0 END) 
                               OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as avg_gain,
                           AVG(CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END) 
                               OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as avg_loss
                    FROM price_changes
                )
                SELECT symbol, datetime, close,
                       CASE WHEN avg_loss = 0 THEN 100
                            ELSE 100 - (100 / (1 + avg_gain / avg_loss))
                       END as rsi_{period}
                FROM rsi_calculation 
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "period"],
                example="计算平安银行14日RSI指标",
                difficulty="hard",
                performance_tips=["使用窗口函数优化", "考虑NULL值处理"],
                related_indicators=["RSI", "相对强弱指数"]
            ),
            
            QuantSQLTemplate(
                name="布林带(Bollinger Bands)",
                category=QuantAnalysisType.TECHNICAL_INDICATORS,
                description="计算布林带指标",
                template="""SELECT symbol, datetime, close,
                       AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as middle_band,
                       AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) + 
                       {std_dev} * STDDEV(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as upper_band,
                       AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) - 
                       {std_dev} * STDDEV(close) OVER (ORDER BY datetime ROWS BETWEEN {period-1} PRECEDING AND CURRENT ROW) as lower_band
                FROM market_data 
                WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "period", "std_dev"],
                example="计算平安银行20日布林带",
                difficulty="medium",
                performance_tips=["使用窗口函数", "std_dev通常为2"],
                related_indicators=["布林带", "Bollinger Bands"]
            ),
            
            QuantSQLTemplate(
                name="MACD指标",
                category=QuantAnalysisType.TECHNICAL_INDICATORS,
                description="计算MACD指标",
                template="""WITH ema_data AS (
                    SELECT symbol, datetime, close,
                           AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {fast_period-1} PRECEDING AND CURRENT ROW) as ema_{fast_period},
                           AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {slow_period-1} PRECEDING AND CURRENT ROW) as ema_{slow_period}
                    FROM market_data 
                    WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                )
                SELECT symbol, datetime, close, ema_{fast_period}, ema_{slow_period},
                       ema_{fast_period} - ema_{slow_period} as macd_line,
                       AVG(ema_{fast_period} - ema_{slow_period}) OVER (ORDER BY datetime ROWS BETWEEN {signal_period-1} PRECEDING AND CURRENT ROW) as signal_line
                FROM ema_data
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "fast_period", "slow_period", "signal_period"],
                example="计算平安银行MACD指标(12,26,9)",
                difficulty="hard",
                performance_tips=["使用多层窗口函数", "考虑计算复杂度"],
                related_indicators=["MACD", "移动平均收敛发散"]
            ),
            
            # 策略分析模板
            QuantSQLTemplate(
                name="双均线策略信号",
                category=QuantAnalysisType.STRATEGY_ANALYSIS,
                description="生成双均线策略交易信号",
                template="""WITH ma_data AS (
                    SELECT symbol, datetime, close,
                           AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {short_period-1} PRECEDING AND CURRENT ROW) as ma_short,
                           AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {long_period-1} PRECEDING AND CURRENT ROW) as ma_long
                    FROM market_data 
                    WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ),
                signals AS (
                    SELECT symbol, datetime, close, ma_short, ma_long,
                           CASE WHEN ma_short > ma_long AND LAG(ma_short) OVER (ORDER BY datetime) <= LAG(ma_long) OVER (ORDER BY datetime) THEN 'BUY'
                                WHEN ma_short < ma_long AND LAG(ma_short) OVER (ORDER BY datetime) >= LAG(ma_long) OVER (ORDER BY datetime) THEN 'SELL'
                                ELSE 'HOLD'
                           END as signal
                    FROM ma_data
                )
                SELECT * FROM signals WHERE signal != 'HOLD'
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "short_period", "long_period"],
                example="生成平安银行双均线策略(5,20)交易信号",
                difficulty="medium",
                performance_tips=["使用LAG函数检测交叉", "过滤HOLD信号"],
                related_indicators=["双均线", "交易信号"]
            ),
            
            QuantSQLTemplate(
                name="策略回测结果分析",
                category=QuantAnalysisType.BACKTEST_ANALYSIS,
                description="分析策略回测结果",
                template="""SELECT strategy_name,
                       COUNT(*) as total_trades,
                       AVG(total_return) as avg_return,
                       MAX(total_return) as max_return,
                       MIN(total_return) as min_return,
                       AVG(max_drawdown) as avg_drawdown,
                       MAX(max_drawdown) as max_drawdown,
                       AVG(sharpe_ratio) as avg_sharpe,
                       AVG(win_rate) as avg_win_rate
                FROM backtest_result 
                WHERE created_time >= '{start_date}' AND created_time <= '{end_date}'
                GROUP BY strategy_name
                ORDER BY avg_return DESC""",
                parameters=["start_date", "end_date"],
                example="分析最近一年的策略回测结果",
                difficulty="easy",
                performance_tips=["添加时间索引", "使用聚合函数"],
                related_indicators=["回测结果", "策略分析"]
            ),
            
            # 风险分析模板
            QuantSQLTemplate(
                name="收益率分析",
                category=QuantAnalysisType.RISK_ANALYSIS,
                description="计算股票收益率",
                template="""SELECT symbol, datetime, close,
                       (close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as daily_return,
                       LN(close / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) as log_return
                FROM market_data 
                WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date"],
                example="计算平安银行的日收益率",
                difficulty="easy",
                performance_tips=["使用LAG函数", "处理除零错误"],
                related_indicators=["收益率", "对数收益率"]
            ),
            
            QuantSQLTemplate(
                name="波动率计算",
                category=QuantAnalysisType.RISK_ANALYSIS,
                description="计算股票波动率",
                template="""WITH returns AS (
                    SELECT symbol, datetime, close,
                           (close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as return_rate
                    FROM market_data WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
                )
                SELECT symbol, datetime, close, return_rate,
                       STDDEV(return_rate) OVER (ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as volatility_{window},
                       STDDEV(return_rate) OVER (ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) * SQRT(252) as annualized_volatility
                FROM returns 
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date", "window"],
                example="计算平安银行20日波动率",
                difficulty="medium",
                performance_tips=["使用STDDEV函数", "年化波动率=日波动率*√252"],
                related_indicators=["波动率", "年化波动率"]
            ),
            
            QuantSQLTemplate(
                name="最大回撤计算",
                category=QuantAnalysisType.RISK_ANALYSIS,
                description="计算最大回撤",
                template="""WITH cumulative_returns AS (
                    SELECT symbol, datetime, close,
                           (close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime) as return_rate
                    FROM market_data WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}'
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
                       (cumulative_return - running_max_return) / running_max_return as drawdown,
                       MAX((cumulative_return - running_max_return) / running_max_return) OVER (PARTITION BY symbol) as max_drawdown
                FROM running_max 
                ORDER BY datetime""",
                parameters=["symbol", "start_date", "end_date"],
                example="计算平安银行的最大回撤",
                difficulty="hard",
                performance_tips=["使用多层窗口函数", "处理NULL值"],
                related_indicators=["最大回撤", "回撤分析"]
            ),
            
            # 投资组合分析模板
            QuantSQLTemplate(
                name="投资组合收益率",
                category=QuantAnalysisType.PORTFOLIO_ANALYSIS,
                description="计算投资组合收益率",
                template="""WITH portfolio_returns AS (
                    SELECT datetime,
                           SUM(weight * (close - LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) / LAG(close) OVER (PARTITION BY symbol ORDER BY datetime)) as portfolio_return
                    FROM market_data m
                    JOIN portfolio_weights p ON m.symbol = p.symbol
                    WHERE m.datetime BETWEEN '{start_date}' AND '{end_date}'
                    GROUP BY datetime
                )
                SELECT datetime, portfolio_return,
                       EXP(SUM(LN(1 + COALESCE(portfolio_return, 0))) OVER (ORDER BY datetime)) as cumulative_return
                FROM portfolio_returns
                ORDER BY datetime""",
                parameters=["start_date", "end_date"],
                example="计算投资组合的收益率",
                difficulty="hard",
                performance_tips=["使用JOIN连接权重表", "处理权重变化"],
                related_indicators=["投资组合收益率", "累计收益率"]
            )
        ]
        
        return templates
    
    def _load_ai_prompts(self) -> Dict[str, List[str]]:
        """加载AI提示词"""
        return {
            "quant_analysis": [
                "请为量化分析生成SQL查询语句",
                "请优化这个技术指标计算查询",
                "请生成风险分析相关的SQL语句",
                "请解释这个回测结果查询的含义",
                "请为投资组合分析生成SQL查询"
            ],
            "technical_indicators": [
                "请生成移动平均线计算的SQL",
                "请计算RSI指标的SQL查询",
                "请生成MACD指标的SQL语句",
                "请计算布林带的SQL查询",
                "请生成KDJ指标的SQL语句"
            ],
            "strategy_analysis": [
                "请生成双均线策略的SQL查询",
                "请计算策略回测结果的SQL",
                "请生成交易信号识别的SQL",
                "请分析策略性能的SQL查询",
                "请计算策略收益率的SQL语句"
            ],
            "risk_management": [
                "请计算股票波动率的SQL查询",
                "请生成最大回撤计算的SQL",
                "请分析风险指标的SQL语句",
                "请计算VaR的SQL查询",
                "请生成压力测试的SQL语句"
            ]
        }
    
    def _load_performance_tips(self) -> Dict[str, List[str]]:
        """加载性能优化提示"""
        return {
            "indexing": [
                "为常用查询字段创建复合索引",
                "使用覆盖索引减少回表查询",
                "定期分析查询执行计划",
                "考虑分区表提高查询性能"
            ],
            "query_optimization": [
                "使用窗口函数替代子查询",
                "避免在WHERE子句中使用函数",
                "使用LIMIT限制结果集大小",
                "考虑使用EXISTS替代IN"
            ],
            "data_management": [
                "定期清理历史数据",
                "使用适当的数据类型",
                "考虑数据压缩存储",
                "建立数据归档策略"
            ]
        }
    
    def get_templates_by_category(self, category: QuantAnalysisType) -> List[QuantSQLTemplate]:
        """根据类别获取模板"""
        return [t for t in self.templates if t.category == category]
    
    def get_template_by_name(self, name: str) -> Optional[QuantSQLTemplate]:
        """根据名称获取模板"""
        for template in self.templates:
            if template.name == name:
                return template
        return None
    
    def get_templates_by_difficulty(self, difficulty: str) -> List[QuantSQLTemplate]:
        """根据难度获取模板"""
        return [t for t in self.templates if t.difficulty == difficulty]
    
    def search_templates(self, keyword: str) -> List[QuantSQLTemplate]:
        """搜索模板"""
        keyword_lower = keyword.lower()
        results = []
        
        for template in self.templates:
            if (keyword_lower in template.name.lower() or 
                keyword_lower in template.description.lower() or
                keyword_lower in template.example.lower()):
                results.append(template)
        
        return results
    
    def get_ai_prompts_by_category(self, category: str) -> List[str]:
        """根据类别获取AI提示词"""
        return self.ai_prompts.get(category, [])
    
    def get_performance_tips_by_category(self, category: str) -> List[str]:
        """根据类别获取性能优化提示"""
        return self.performance_tips.get(category, [])
    
    def generate_sql_from_template(self, template_name: str, parameters: Dict[str, str]) -> Optional[str]:
        """从模板生成SQL"""
        template = self.get_template_by_name(template_name)
        if not template:
            return None
        
        try:
            return template.template.format(**parameters)
        except KeyError as e:
            logger.error(f"模板参数缺失: {e}")
            return None
    
    def validate_parameters(self, template_name: str, parameters: Dict[str, str]) -> Tuple[bool, List[str]]:
        """验证模板参数"""
        template = self.get_template_by_name(template_name)
        if not template:
            return False, ["模板不存在"]
        
        missing_params = []
        for param in template.parameters:
            if param not in parameters:
                missing_params.append(param)
        
        return len(missing_params) == 0, missing_params
    
    def get_all_categories(self) -> List[QuantAnalysisType]:
        """获取所有类别"""
        return list(set(t.category for t in self.templates))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        category_count = {}
        difficulty_count = {}
        
        for template in self.templates:
            category = template.category.value
            difficulty = template.difficulty
            
            category_count[category] = category_count.get(category, 0) + 1
            difficulty_count[difficulty] = difficulty_count.get(difficulty, 0) + 1
        
        return {
            "total_templates": len(self.templates),
            "category_count": category_count,
            "difficulty_count": difficulty_count,
            "ai_prompt_categories": len(self.ai_prompts),
            "performance_tip_categories": len(self.performance_tips)
        }
