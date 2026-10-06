#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib SQLite数据库
用于存储行情数据、策略配置、回测结果等
"""

import os
import time
import json
import logging
import sqlite3
import threading
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

class RockXQlibTableType(Enum):
    """表类型枚举"""
    MARKET_DATA = "market_data"
    STRATEGY_CONFIG = "strategy_config"
    BACKTEST_RESULT = "backtest_result"
    USER_CONFIG = "user_config"
    LOG_DATA = "log_data"
    CUSTOM = "custom"

@dataclass
class RockXQlibMarketData:
    """行情数据结构"""
    symbol: str
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None
    adj_factor: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class RockXQlibStrategyConfig:
    """策略配置结构"""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    config: Dict[str, Any]
    created_time: float
    updated_time: float
    is_active: bool = True
    description: str = ""
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = time.time()
        if self.updated_time is None:
            self.updated_time = time.time()

@dataclass
class RockXQlibBacktestResult:
    """回测结果结构"""
    backtest_id: str
    strategy_id: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    result_data: Dict[str, Any]
    created_time: float
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = time.time()

class RockXQlibSQLiteDatabase:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str = "rockxqlib.db"):
        self.db_path = db_path
        self.connection = None
        self.lock = threading.Lock()
        
        # 统计信息
        self.total_queries = 0
        self.total_inserts = 0
        self.start_time = time.time()
        
        # 初始化数据库
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库"""
        try:
            # 确保目录存在
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            # 连接数据库
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self.connection.row_factory = sqlite3.Row
            
            # 创建表
            self._create_tables()
            
            logger.info(f"SQLite数据库初始化成功: {self.db_path}")
            
        except Exception as e:
            logger.error(f"初始化SQLite数据库失败: {e}")
            raise
    
    def _create_tables(self):
        """创建数据表"""
        try:
            cursor = self.connection.cursor()
            
            # 行情数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL,
                    adj_factor REAL,
                    metadata TEXT,
                    created_time REAL DEFAULT (julianday('now')),
                    UNIQUE(symbol, datetime)
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_datetime ON market_data(datetime)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol_datetime ON market_data(symbol, datetime)")
            
            # 策略配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategy_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT UNIQUE NOT NULL,
                    strategy_name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    config TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    description TEXT,
                    created_time REAL NOT NULL,
                    updated_time REAL NOT NULL
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy_config_id ON strategy_config(strategy_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy_config_type ON strategy_config(strategy_type)")
            
            # 回测结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_id TEXT UNIQUE NOT NULL,
                    strategy_id TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    final_capital REAL NOT NULL,
                    total_return REAL NOT NULL,
                    annual_return REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    sharpe_ratio REAL NOT NULL,
                    win_rate REAL NOT NULL,
                    result_data TEXT NOT NULL,
                    created_time REAL NOT NULL
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backtest_result_id ON backtest_result(backtest_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backtest_result_strategy ON backtest_result(strategy_id)")
            
            # 用户配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,
                    config_type TEXT DEFAULT 'string',
                    description TEXT,
                    created_time REAL DEFAULT (julianday('now')),
                    updated_time REAL DEFAULT (julianday('now')),
                    UNIQUE(user_id, config_key)
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_config_user ON user_config(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_config_key ON user_config(config_key)")
            
            # 日志数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    logger_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    module TEXT,
                    function TEXT,
                    line_number INTEGER,
                    thread_id INTEGER,
                    process_id INTEGER,
                    created_time REAL DEFAULT (julianday('now'))
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_data_level ON log_data(level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_data_time ON log_data(created_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_data_logger ON log_data(logger_name)")
            
            # 提交事务
            self.connection.commit()
            
            logger.info("数据表创建完成")
            
        except Exception as e:
            logger.error(f"创建数据表失败: {e}")
            self.connection.rollback()
            raise
    
    def insert_market_data(self, data: Union[RockXQlibMarketData, List[RockXQlibMarketData]]) -> bool:
        """插入行情数据"""
        try:
            if isinstance(data, RockXQlibMarketData):
                data = [data]
            
            cursor = self.connection.cursor()
            
            for item in data:
                cursor.execute("""
                    INSERT OR REPLACE INTO market_data 
                    (symbol, datetime, open, high, low, close, volume, amount, adj_factor, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.symbol,
                    item.datetime,
                    item.open,
                    item.high,
                    item.low,
                    item.close,
                    item.volume,
                    item.amount,
                    item.adj_factor,
                    json.dumps(item.metadata) if item.metadata else None
                ))
            
            self.connection.commit()
            self.total_inserts += len(data)
            
            logger.debug(f"插入了 {len(data)} 条行情数据")
            return True
            
        except Exception as e:
            logger.error(f"插入行情数据失败: {e}")
            self.connection.rollback()
            return False
    
    def query_market_data(self, symbol: str, start_date: Optional[str] = None, 
                         end_date: Optional[str] = None, limit: Optional[int] = None) -> pd.DataFrame:
        """查询行情数据"""
        try:
            cursor = self.connection.cursor()
            
            query = "SELECT * FROM market_data WHERE symbol = ?"
            params = [symbol]
            
            if start_date:
                query += " AND datetime >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND datetime <= ?"
                params.append(end_date)
            
            query += " ORDER BY datetime"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 转换为DataFrame
            if rows:
                df = pd.DataFrame(rows)
                df.columns = [description[0] for description in cursor.description]
                
                # 解析metadata
                if 'metadata' in df.columns:
                    df['metadata'] = df['metadata'].apply(
                        lambda x: json.loads(x) if x else {}
                    )
                
                self.total_queries += 1
                logger.debug(f"查询到 {len(df)} 条行情数据")
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"查询行情数据失败: {e}")
            return pd.DataFrame()
    
    def get_market_data_symbols(self) -> List[str]:
        """获取所有股票代码"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM market_data ORDER BY symbol")
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"获取股票代码失败: {e}")
            return []
    
    def insert_strategy_config(self, config: RockXQlibStrategyConfig) -> bool:
        """插入策略配置"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO strategy_config 
                (strategy_id, strategy_name, strategy_type, config, is_active, description, created_time, updated_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config.strategy_id,
                config.strategy_name,
                config.strategy_type,
                json.dumps(config.config),
                config.is_active,
                config.description,
                config.created_time,
                config.updated_time
            ))
            
            self.connection.commit()
            self.total_inserts += 1
            
            logger.debug(f"插入了策略配置: {config.strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"插入策略配置失败: {e}")
            self.connection.rollback()
            return False
    
    def query_strategy_config(self, strategy_id: Optional[str] = None, 
                             strategy_type: Optional[str] = None) -> List[RockXQlibStrategyConfig]:
        """查询策略配置"""
        try:
            cursor = self.connection.cursor()
            
            query = "SELECT * FROM strategy_config WHERE 1=1"
            params = []
            
            if strategy_id:
                query += " AND strategy_id = ?"
                params.append(strategy_id)
            
            if strategy_type:
                query += " AND strategy_type = ?"
                params.append(strategy_type)
            
            query += " ORDER BY created_time DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            configs = []
            for row in rows:
                config = RockXQlibStrategyConfig(
                    strategy_id=row['strategy_id'],
                    strategy_name=row['strategy_name'],
                    strategy_type=row['strategy_type'],
                    config=json.loads(row['config']),
                    is_active=bool(row['is_active']),
                    description=row['description'] or "",
                    created_time=row['created_time'],
                    updated_time=row['updated_time']
                )
                configs.append(config)
            
            self.total_queries += 1
            logger.debug(f"查询到 {len(configs)} 个策略配置")
            return configs
            
        except Exception as e:
            logger.error(f"查询策略配置失败: {e}")
            return []
    
    def insert_backtest_result(self, result: RockXQlibBacktestResult) -> bool:
        """插入回测结果"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO backtest_result 
                (backtest_id, strategy_id, start_date, end_date, initial_capital, final_capital,
                 total_return, annual_return, max_drawdown, sharpe_ratio, win_rate, result_data, created_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.backtest_id,
                result.strategy_id,
                result.start_date,
                result.end_date,
                result.initial_capital,
                result.final_capital,
                result.total_return,
                result.annual_return,
                result.max_drawdown,
                result.sharpe_ratio,
                result.win_rate,
                json.dumps(result.result_data),
                result.created_time
            ))
            
            self.connection.commit()
            self.total_inserts += 1
            
            logger.debug(f"插入了回测结果: {result.backtest_id}")
            return True
            
        except Exception as e:
            logger.error(f"插入回测结果失败: {e}")
            self.connection.rollback()
            return False
    
    def query_backtest_results(self, strategy_id: Optional[str] = None, 
                              limit: Optional[int] = None) -> List[RockXQlibBacktestResult]:
        """查询回测结果"""
        try:
            cursor = self.connection.cursor()
            
            query = "SELECT * FROM backtest_result WHERE 1=1"
            params = []
            
            if strategy_id:
                query += " AND strategy_id = ?"
                params.append(strategy_id)
            
            query += " ORDER BY created_time DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                result = RockXQlibBacktestResult(
                    backtest_id=row['backtest_id'],
                    strategy_id=row['strategy_id'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    initial_capital=row['initial_capital'],
                    final_capital=row['final_capital'],
                    total_return=row['total_return'],
                    annual_return=row['annual_return'],
                    max_drawdown=row['max_drawdown'],
                    sharpe_ratio=row['sharpe_ratio'],
                    win_rate=row['win_rate'],
                    result_data=json.loads(row['result_data']),
                    created_time=row['created_time']
                )
                results.append(result)
            
            self.total_queries += 1
            logger.debug(f"查询到 {len(results)} 个回测结果")
            return results
            
        except Exception as e:
            logger.error(f"查询回测结果失败: {e}")
            return []
    
    def insert_user_config(self, user_id: str, config_key: str, config_value: Any, 
                          config_type: str = "string", description: str = "") -> bool:
        """插入用户配置"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO user_config 
                (user_id, config_key, config_value, config_type, description, updated_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                config_key,
                json.dumps(config_value) if config_type == "json" else str(config_value),
                config_type,
                description,
                time.time()
            ))
            
            self.connection.commit()
            self.total_inserts += 1
            
            logger.debug(f"插入了用户配置: {user_id}.{config_key}")
            return True
            
        except Exception as e:
            logger.error(f"插入用户配置失败: {e}")
            self.connection.rollback()
            return False
    
    def query_user_config(self, user_id: str, config_key: Optional[str] = None) -> Dict[str, Any]:
        """查询用户配置"""
        try:
            cursor = self.connection.cursor()
            
            query = "SELECT * FROM user_config WHERE user_id = ?"
            params = [user_id]
            
            if config_key:
                query += " AND config_key = ?"
                params.append(config_key)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            configs = {}
            for row in rows:
                key = row['config_key']
                value = row['config_value']
                config_type = row['config_type']
                
                if config_type == "json":
                    configs[key] = json.loads(value)
                elif config_type == "int":
                    configs[key] = int(value)
                elif config_type == "float":
                    configs[key] = float(value)
                elif config_type == "bool":
                    configs[key] = value.lower() == "true"
                else:
                    configs[key] = value
            
            self.total_queries += 1
            logger.debug(f"查询到 {len(configs)} 个用户配置")
            return configs
            
        except Exception as e:
            logger.error(f"查询用户配置失败: {e}")
            return {}
    
    def insert_log_data(self, level: str, logger_name: str, message: str, 
                       module: Optional[str] = None, function: Optional[str] = None,
                       line_number: Optional[int] = None) -> bool:
        """插入日志数据"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT INTO log_data 
                (level, logger_name, message, module, function, line_number, thread_id, process_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                level,
                logger_name,
                message,
                module,
                function,
                line_number,
                threading.get_ident(),
                os.getpid()
            ))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"插入日志数据失败: {e}")
            return False
    
    def query_log_data(self, level: Optional[str] = None, logger_name: Optional[str] = None,
                      start_time: Optional[float] = None, end_time: Optional[float] = None,
                      limit: Optional[int] = None) -> pd.DataFrame:
        """查询日志数据"""
        try:
            cursor = self.connection.cursor()
            
            query = "SELECT * FROM log_data WHERE 1=1"
            params = []
            
            if level:
                query += " AND level = ?"
                params.append(level)
            
            if logger_name:
                query += " AND logger_name = ?"
                params.append(logger_name)
            
            if start_time:
                query += " AND created_time >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND created_time <= ?"
                params.append(end_time)
            
            query += " ORDER BY created_time DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if rows:
                df = pd.DataFrame(rows)
                df.columns = [description[0] for description in cursor.description]
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"查询日志数据失败: {e}")
            return pd.DataFrame()
    
    def execute_custom_query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """执行自定义查询"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params or [])
            rows = cursor.fetchall()
            
            # 转换为字典列表
            results = []
            for row in rows:
                results.append(dict(row))
            
            self.total_queries += 1
            logger.debug(f"执行自定义查询，返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"执行自定义查询失败: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            cursor = self.connection.cursor()
            
            # 获取表统计
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            table_stats = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_stats[table] = count
            
            uptime = time.time() - self.start_time
            
            return {
                'db_path': self.db_path,
                'uptime': uptime,
                'total_queries': self.total_queries,
                'total_inserts': self.total_inserts,
                'table_stats': table_stats,
                'queries_per_minute': self.total_queries / max(uptime / 60, 1)
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def backup_database(self, backup_path: str) -> bool:
        """备份数据库"""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"数据库备份成功: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.connection:
                self.connection.close()
            logger.info("SQLite数据库清理完成")
        except Exception as e:
            logger.error(f"SQLite数据库清理失败: {e}")
