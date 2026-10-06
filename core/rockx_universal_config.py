#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockX Universal Configuration Manager
通用配置管理器，支持不同RockX系统产品的配置和SQL模板
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import importlib.util

logger = logging.getLogger(__name__)

class RockXSystemType(Enum):
    """RockX系统类型"""
    QLIB = "qlib"                    # 量化分析系统
    TRADING = "trading"              # 交易系统
    RISK = "risk"                    # 风险管理系统
    PORTFOLIO = "portfolio"          # 投资组合系统
    RESEARCH = "research"            # 研究分析系统
    BACKTEST = "backtest"            # 回测系统
    DATA = "data"                    # 数据管理系统
    CUSTOM = "custom"                # 自定义系统

class DatabaseType(Enum):
    """数据库类型"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    CLICKHOUSE = "clickhouse"
    INFLUXDB = "influxdb"
    TIMESCALEDB = "timescaledb"

@dataclass
class SQLTemplate:
    """SQL模板"""
    name: str
    category: str
    description: str
    template: str
    parameters: List[str]
    example: str
    system_types: List[RockXSystemType]
    database_types: List[DatabaseType]
    difficulty: str = "medium"
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

@dataclass
class SystemConfig:
    """系统配置"""
    system_name: str
    system_type: RockXSystemType
    version: str
    description: str
    database_config: Dict[str, Any]
    sql_templates: List[str]
    ai_prompts: Dict[str, List[str]]
    custom_features: Dict[str, Any]
    enabled: bool = True

class RockXUniversalConfigManager:
    """RockX通用配置管理器"""
    
    def __init__(self, config_dir: str = "config/rockx_systems"):
        self.config_dir = config_dir
        self.system_configs = {}
        self.sql_templates = {}
        self.current_system = None
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 加载所有配置
        self._load_all_configs()
        
        logger.info(f"RockX通用配置管理器初始化完成，支持 {len(self.system_configs)} 个系统")
    
    def _load_all_configs(self):
        """加载所有系统配置"""
        try:
            # 加载系统配置
            self._load_system_configs()
            
            # 加载SQL模板
            self._load_sql_templates()
            
            # 加载默认配置
            self._create_default_configs()
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
    
    def _load_system_configs(self):
        """加载系统配置"""
        systems_dir = os.path.join(self.config_dir, "systems")
        os.makedirs(systems_dir, exist_ok=True)
        
        for config_file in os.listdir(systems_dir):
            if config_file.endswith('.yaml'):
                try:
                    config_path = os.path.join(systems_dir, config_file)
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
                    
                    # 转换字符串为枚举类型
                    if 'system_type' in config_data and isinstance(config_data['system_type'], str):
                        config_data['system_type'] = RockXSystemType(config_data['system_type'])
                    
                    system_config = SystemConfig(**config_data)
                    self.system_configs[system_config.system_name] = system_config
                    
                except Exception as e:
                    logger.error(f"加载系统配置 {config_file} 失败: {e}")
    
    def _load_sql_templates(self):
        """加载SQL模板"""
        templates_dir = os.path.join(self.config_dir, "sql_templates")
        os.makedirs(templates_dir, exist_ok=True)
        
        for template_file in os.listdir(templates_dir):
            if template_file.endswith('.yaml'):
                try:
                    template_path = os.path.join(templates_dir, template_file)
                    with open(template_path, 'r', encoding='utf-8') as f:
                        templates_data = yaml.safe_load(f)
                    
                    for template_data in templates_data.get('templates', []):
                        # 转换字符串为枚举类型
                        if 'system_types' in template_data and isinstance(template_data['system_types'], list):
                            template_data['system_types'] = [RockXSystemType(t) if isinstance(t, str) else t for t in template_data['system_types']]
                        
                        if 'database_types' in template_data and isinstance(template_data['database_types'], list):
                            template_data['database_types'] = [DatabaseType(t) if isinstance(t, str) else t for t in template_data['database_types']]
                        
                        template = SQLTemplate(**template_data)
                        self.sql_templates[template.name] = template
                        
                except Exception as e:
                    logger.error(f"加载SQL模板 {template_file} 失败: {e}")
    
    def _create_default_configs(self):
        """创建默认配置"""
        # 创建默认的RockXQlib配置
        if "RockXQlib" not in self.system_configs:
            self._create_qlib_config()
        
        # 创建默认的SQL模板
        if not self.sql_templates:
            self._create_default_sql_templates()
    
    def _create_qlib_config(self):
        """创建RockXQlib默认配置"""
        qlib_config = SystemConfig(
            system_name="RockXQlib",
            system_type=RockXSystemType.QLIB,
            version="2.1",
            description="基于Qlib的高级量化分析系统",
            database_config={
                "primary": {
                    "type": "sqlite",
                    "path": "rockxqlib.db",
                    "tables": ["market_data", "strategy_config", "backtest_result", "user_config"]
                },
                "vector": {
                    "type": "vector",
                    "path": "vector_kb",
                    "enabled": True
                },
                "mongodb": {
                    "type": "mongodb",
                    "host": "localhost",
                    "port": 27017,
                    "database": "qlib_tasks",
                    "enabled": True
                }
            },
            sql_templates=[
                "基础行情查询", "技术指标计算", "策略回测分析", "风险分析", "投资组合分析"
            ],
            ai_prompts={
                "quant_analysis": [
                    "请为量化分析生成SQL查询语句",
                    "请优化这个技术指标计算查询",
                    "请生成风险分析相关的SQL语句"
                ],
                "strategy_development": [
                    "请生成双均线策略的SQL查询",
                    "请计算策略回测结果的SQL",
                    "请分析策略性能的SQL查询"
                ]
            },
            custom_features={
                "node_workflow": True,
                "ai_integration": True,
                "visualization": True,
                "kronos_model": True
            }
        )
        
        self.system_configs["RockXQlib"] = qlib_config
        self._save_system_config("RockXQlib", qlib_config)
    
    def _create_default_sql_templates(self):
        """创建默认SQL模板"""
        default_templates = [
            # 通用模板
            SQLTemplate(
                name="基础数据查询",
                category="data_query",
                description="基础数据查询模板",
                template="SELECT * FROM {table_name} WHERE {condition} ORDER BY {order_field} LIMIT {limit}",
                parameters=["table_name", "condition", "order_field", "limit"],
                example="查询用户表中的前10条记录",
                system_types=[RockXSystemType.QLIB, RockXSystemType.TRADING, RockXSystemType.DATA],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="easy",
                tags=["基础", "查询"]
            ),
            
            # 量化分析专用模板
            SQLTemplate(
                name="股票行情查询",
                category="market_data",
                description="查询股票行情数据",
                template="SELECT symbol, datetime, open, high, low, close, volume FROM market_data WHERE symbol = '{symbol}' AND datetime BETWEEN '{start_date}' AND '{end_date}' ORDER BY datetime",
                parameters=["symbol", "start_date", "end_date"],
                example="查询平安银行最近30天的行情数据",
                system_types=[RockXSystemType.QLIB, RockXSystemType.TRADING, RockXSystemType.RESEARCH],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="easy",
                tags=["量化", "行情", "股票"]
            ),
            
            SQLTemplate(
                name="技术指标计算",
                category="technical_analysis",
                description="计算技术指标",
                template="SELECT symbol, datetime, close, AVG(close) OVER (ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as ma_{window} FROM market_data WHERE symbol = '{symbol}' ORDER BY datetime",
                parameters=["symbol", "window"],
                example="计算平安银行20日移动平均线",
                system_types=[RockXSystemType.QLIB, RockXSystemType.TRADING, RockXSystemType.RESEARCH],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="medium",
                tags=["技术指标", "移动平均", "量化"]
            ),
            
            # 交易系统专用模板
            SQLTemplate(
                name="交易记录查询",
                category="trading_records",
                description="查询交易记录",
                template="SELECT trade_id, symbol, side, quantity, price, timestamp, status FROM trades WHERE symbol = '{symbol}' AND timestamp BETWEEN '{start_time}' AND '{end_time}' ORDER BY timestamp DESC",
                parameters=["symbol", "start_time", "end_time"],
                example="查询平安银行最近一周的交易记录",
                system_types=[RockXSystemType.TRADING, RockXSystemType.BACKTEST],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="easy",
                tags=["交易", "记录", "查询"]
            ),
            
            SQLTemplate(
                name="持仓分析",
                category="position_analysis",
                description="分析持仓情况",
                template="SELECT symbol, SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) as net_position, AVG(price) as avg_price FROM trades WHERE account_id = '{account_id}' GROUP BY symbol HAVING net_position != 0",
                parameters=["account_id"],
                example="分析账户的持仓情况",
                system_types=[RockXSystemType.TRADING, RockXSystemType.PORTFOLIO],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="medium",
                tags=["持仓", "分析", "交易"]
            ),
            
            # 风险管理系统专用模板
            SQLTemplate(
                name="风险指标计算",
                category="risk_metrics",
                description="计算风险指标",
                template="SELECT symbol, datetime, close, STDDEV(close) OVER (ORDER BY datetime ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW) as volatility FROM market_data WHERE symbol = '{symbol}' ORDER BY datetime",
                parameters=["symbol", "window"],
                example="计算股票波动率",
                system_types=[RockXSystemType.RISK, RockXSystemType.PORTFOLIO, RockXSystemType.QLIB],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="medium",
                tags=["风险", "波动率", "指标"]
            ),
            
            SQLTemplate(
                name="VaR计算",
                category="risk_metrics",
                description="计算风险价值(VaR)",
                template="WITH returns AS (SELECT symbol, datetime, (close - LAG(close) OVER (ORDER BY datetime)) / LAG(close) OVER (ORDER BY datetime) as return_rate FROM market_data WHERE symbol = '{symbol}') SELECT PERCENTILE_CONT({confidence_level}) WITHIN GROUP (ORDER BY return_rate) as var FROM returns",
                parameters=["symbol", "confidence_level"],
                example="计算95%置信度的VaR",
                system_types=[RockXSystemType.RISK, RockXSystemType.PORTFOLIO],
                database_types=[DatabaseType.POSTGRESQL, DatabaseType.MYSQL],
                difficulty="hard",
                tags=["VaR", "风险", "统计"]
            ),
            
            # 投资组合系统专用模板
            SQLTemplate(
                name="投资组合收益率",
                category="portfolio_analysis",
                description="计算投资组合收益率",
                template="SELECT date, SUM(weight * return_rate) as portfolio_return FROM portfolio_returns WHERE date BETWEEN '{start_date}' AND '{end_date}' GROUP BY date ORDER BY date",
                parameters=["start_date", "end_date"],
                example="计算投资组合的日收益率",
                system_types=[RockXSystemType.PORTFOLIO, RockXSystemType.BACKTEST],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="medium",
                tags=["投资组合", "收益率", "分析"]
            ),
            
            # 数据管理系统专用模板
            SQLTemplate(
                name="数据质量检查",
                category="data_quality",
                description="检查数据质量",
                template="SELECT COUNT(*) as total_records, COUNT(DISTINCT symbol) as unique_symbols, MIN(datetime) as earliest_date, MAX(datetime) as latest_date FROM market_data WHERE datetime BETWEEN '{start_date}' AND '{end_date}'",
                parameters=["start_date", "end_date"],
                example="检查市场数据的质量",
                system_types=[RockXSystemType.DATA, RockXSystemType.QLIB],
                database_types=[DatabaseType.SQLITE, DatabaseType.MYSQL, DatabaseType.POSTGRESQL],
                difficulty="easy",
                tags=["数据质量", "检查", "统计"]
            ),
            
            # 研究分析系统专用模板
            SQLTemplate(
                name="相关性分析",
                category="correlation_analysis",
                description="分析股票相关性",
                template="SELECT a.symbol as symbol1, b.symbol as symbol2, CORR(a.close, b.close) as correlation FROM market_data a JOIN market_data b ON a.datetime = b.datetime WHERE a.symbol = '{symbol1}' AND b.symbol = '{symbol2}' AND a.datetime BETWEEN '{start_date}' AND '{end_date}'",
                parameters=["symbol1", "symbol2", "start_date", "end_date"],
                example="分析两只股票的相关性",
                system_types=[RockXSystemType.RESEARCH, RockXSystemType.PORTFOLIO, RockXSystemType.QLIB],
                database_types=[DatabaseType.POSTGRESQL, DatabaseType.MYSQL],
                difficulty="medium",
                tags=["相关性", "分析", "统计"]
            )
        ]
        
        for template in default_templates:
            self.sql_templates[template.name] = template
        
        self._save_sql_templates()
    
    def get_system_config(self, system_name: str) -> Optional[SystemConfig]:
        """获取系统配置"""
        return self.system_configs.get(system_name)
    
    def get_available_systems(self) -> List[str]:
        """获取可用系统列表"""
        return list(self.system_configs.keys())
    
    def get_sql_templates_for_system(self, system_name: str) -> List[SQLTemplate]:
        """获取系统专用的SQL模板"""
        system_config = self.get_system_config(system_name)
        if not system_config:
            return []
        
        templates = []
        for template_name in system_config.sql_templates:
            if template_name in self.sql_templates:
                templates.append(self.sql_templates[template_name])
        
        return templates
    
    def get_templates_by_category(self, category: str) -> List[SQLTemplate]:
        """根据类别获取模板"""
        return [t for t in self.sql_templates.values() if t.category == category]
    
    def get_templates_by_system_type(self, system_type: RockXSystemType) -> List[SQLTemplate]:
        """根据系统类型获取模板"""
        return [t for t in self.sql_templates.values() if system_type in t.system_types]
    
    def search_templates(self, keyword: str, system_name: Optional[str] = None) -> List[SQLTemplate]:
        """搜索模板"""
        keyword_lower = keyword.lower()
        results = []
        
        templates_to_search = []
        if system_name:
            templates_to_search = self.get_sql_templates_for_system(system_name)
        else:
            templates_to_search = list(self.sql_templates.values())
        
        for template in templates_to_search:
            if (keyword_lower in template.name.lower() or 
                keyword_lower in template.description.lower() or
                keyword_lower in template.example.lower() or
                any(keyword_lower in tag.lower() for tag in template.tags)):
                results.append(template)
        
        return results
    
    def create_custom_system_config(self, system_name: str, system_type: RockXSystemType, 
                                  description: str, database_config: Dict[str, Any],
                                  sql_templates: List[str], **kwargs) -> SystemConfig:
        """创建自定义系统配置"""
        system_config = SystemConfig(
            system_name=system_name,
            system_type=system_type,
            version=kwargs.get("version", "1.0"),
            description=description,
            database_config=database_config,
            sql_templates=sql_templates,
            ai_prompts=kwargs.get("ai_prompts", {}),
            custom_features=kwargs.get("custom_features", {}),
            enabled=kwargs.get("enabled", True)
        )
        
        self.system_configs[system_name] = system_config
        self._save_system_config(system_name, system_config)
        
        logger.info(f"创建自定义系统配置: {system_name}")
        return system_config
    
    def add_custom_sql_template(self, template: SQLTemplate):
        """添加自定义SQL模板"""
        self.sql_templates[template.name] = template
        self._save_sql_templates()
        logger.info(f"添加自定义SQL模板: {template.name}")
    
    def _save_system_config(self, system_name: str, config: SystemConfig):
        """保存系统配置"""
        try:
            systems_dir = os.path.join(self.config_dir, "systems")
            os.makedirs(systems_dir, exist_ok=True)
            
            config_path = os.path.join(systems_dir, f"{system_name.lower()}.yaml")
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(asdict(config), f, default_flow_style=False, allow_unicode=True)
                
        except Exception as e:
            logger.error(f"保存系统配置失败: {e}")
    
    def _save_sql_templates(self):
        """保存SQL模板"""
        try:
            templates_dir = os.path.join(self.config_dir, "sql_templates")
            os.makedirs(templates_dir, exist_ok=True)
            
            # 按类别分组保存
            categories = {}
            for template in self.sql_templates.values():
                if template.category not in categories:
                    categories[template.category] = []
                categories[template.category].append(asdict(template))
            
            for category, templates in categories.items():
                template_path = os.path.join(templates_dir, f"{category}.yaml")
                with open(template_path, 'w', encoding='utf-8') as f:
                    yaml.dump({"templates": templates}, f, default_flow_style=False, allow_unicode=True)
                    
        except Exception as e:
            logger.error(f"保存SQL模板失败: {e}")
    
    def export_system_config(self, system_name: str, export_path: str):
        """导出系统配置"""
        try:
            config = self.get_system_config(system_name)
            if not config:
                raise ValueError(f"系统配置不存在: {system_name}")
            
            with open(export_path, 'w', encoding='utf-8') as f:
                yaml.dump(asdict(config), f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"系统配置已导出到: {export_path}")
            
        except Exception as e:
            logger.error(f"导出系统配置失败: {e}")
    
    def import_system_config(self, import_path: str):
        """导入系统配置"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            config = SystemConfig(**config_data)
            self.system_configs[config.system_name] = config
            self._save_system_config(config.system_name, config)
            
            logger.info(f"系统配置已导入: {config.system_name}")
            
        except Exception as e:
            logger.error(f"导入系统配置失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_systems": len(self.system_configs),
            "total_templates": len(self.sql_templates),
            "system_types": list(set(config.system_type.value for config in self.system_configs.values())),
            "template_categories": list(set(template.category for template in self.sql_templates.values())),
            "available_systems": list(self.system_configs.keys())
        }
