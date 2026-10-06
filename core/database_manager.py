#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 数据库管理器
集成Chat2DB桌面客户端，提供AI驱动的数据库管理功能
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
import requests
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseType(Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    CLICKHOUSE = "clickhouse"

@dataclass
class DatabaseConnection:
    """数据库连接配置"""
    name: str
    db_type: DatabaseType
    host: str = "localhost"
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    file_path: str = ""  # 用于SQLite等文件数据库
    connection_string: str = ""
    chat2db_enabled: bool = True
    created_time: float = 0.0
    
    def __post_init__(self):
        if self.created_time == 0.0:
            self.created_time = time.time()

class Chat2DBManager:
    """Chat2DB管理器"""
    
    def __init__(self, config_path: str = "config/chat2db_config.yaml"):
        self.config_path = config_path
        self.process = None
        self.api_url = "http://localhost:10824"
        self.is_running = False
        self.start_time = 0.0
        
        # 加载配置
        self.config = self._load_config()
        
        # 统计信息
        self.total_queries = 0
        self.total_ai_queries = 0
        self.start_time = time.time()
        
        logger.info("Chat2DB管理器初始化完成")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载Chat2DB配置"""
        default_config = {
            "chat2db": {
                "auto_start": True,
                "port": 10824,
                "executable_path": "",  # 自动检测
                "data_dir": "data/chat2db",
                "ai_features": {
                    "enabled": True,
                    "model": "gpt-3.5-turbo",
                    "api_key": "",
                    "max_tokens": 2000
                },
                "security": {
                    "enable_auth": False,
                    "username": "",
                    "password": ""
                }
            },
            "databases": {
                "sqlite": {
                    "type": "sqlite",
                    "path": "rockxqlib.db",
                    "chat2db_enabled": True
                },
                "vector_db": {
                    "type": "vector",
                    "path": "vector_kb",
                    "chat2db_enabled": False
                }
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
            logger.error(f"加载Chat2DB配置失败: {e}")
            return default_config
    
    def save_config(self):
        """保存配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            logger.info("Chat2DB配置保存成功")
        except Exception as e:
            logger.error(f"保存Chat2DB配置失败: {e}")
    
    def find_chat2db_executable(self) -> Optional[str]:
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
                logger.info(f"找到Chat2DB可执行文件: {path}")
                return path
        
        logger.warning("未找到Chat2DB可执行文件，请手动安装")
        return None
    
    def start_chat2db(self) -> bool:
        """启动Chat2DB桌面客户端"""
        try:
            if self.is_running:
                logger.info("Chat2DB已在运行")
                return True
            
            # 查找可执行文件
            executable_path = self.config.get("chat2db", {}).get("executable_path")
            if not executable_path:
                executable_path = self.find_chat2db_executable()
                if not executable_path:
                    logger.error("未找到Chat2DB可执行文件")
                    return False
            
            # 启动Chat2DB
            cmd = [executable_path]
            if self.config.get("chat2db", {}).get("port"):
                cmd.extend(["--port", str(self.config["chat2db"]["port"])])
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            # 等待启动
            time.sleep(3)
            
            # 检查是否启动成功
            if self._check_chat2db_status():
                self.is_running = True
                self.start_time = time.time()
                logger.info("Chat2DB启动成功")
                return True
            else:
                logger.error("Chat2DB启动失败")
                return False
                
        except Exception as e:
            logger.error(f"启动Chat2DB失败: {e}")
            return False
    
    def stop_chat2db(self) -> bool:
        """停止Chat2DB"""
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=10)
            
            self.is_running = False
            logger.info("Chat2DB已停止")
            return True
        except Exception as e:
            logger.error(f"停止Chat2DB失败: {e}")
            return False
    
    def _check_chat2db_status(self) -> bool:
        """检查Chat2DB运行状态"""
        try:
            response = requests.get(f"{self.api_url}/api/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_chat2db_status(self) -> Dict[str, Any]:
        """获取Chat2DB状态"""
        return {
            "is_running": self.is_running,
            "api_url": self.api_url,
            "uptime": time.time() - self.start_time if self.is_running else 0,
            "total_queries": self.total_queries,
            "total_ai_queries": self.total_ai_queries
        }
    
    def execute_ai_sql(self, natural_language: str, database: str = "default") -> Dict[str, Any]:
        """执行AI SQL生成"""
        try:
            if not self.is_running:
                return {"error": "Chat2DB未运行"}
            
            payload = {
                "query": natural_language,
                "database": database,
                "ai_enabled": True
            }
            
            response = requests.post(
                f"{self.api_url}/api/ai/sql",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.total_ai_queries += 1
                return response.json()
            else:
                return {"error": f"API请求失败: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"AI SQL执行失败: {e}")
            return {"error": str(e)}
    
    def execute_sql(self, sql: str, database: str = "default") -> Dict[str, Any]:
        """执行SQL查询"""
        try:
            if not self.is_running:
                return {"error": "Chat2DB未运行"}
            
            payload = {
                "sql": sql,
                "database": database
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
            logger.error(f"SQL执行失败: {e}")
            return {"error": str(e)}

class RockXQlibDatabaseManager:
    """RockXQlib数据库管理器"""
    
    def __init__(self, config_path: str = "config/database_config.yaml"):
        self.config_path = config_path
        self.chat2db_manager = Chat2DBManager()
        self.database_connections: Dict[str, DatabaseConnection] = {}
        self.connection_pool = {}
        
        # 加载配置
        self.config = self._load_config()
        
        # 初始化数据库连接
        self._initialize_connections()
        
        # 统计信息
        self.total_operations = 0
        self.start_time = time.time()
        
        logger.info("RockXQlib数据库管理器初始化完成")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载数据库配置"""
        default_config = {
            "databases": {
                "sqlite": {
                    "name": "RockXQlib SQLite",
                    "type": "sqlite",
                    "file_path": "rockxqlib.db",
                    "chat2db_enabled": True
                },
                "vector_db": {
                    "name": "Vector Database",
                    "type": "vector",
                    "file_path": "vector_kb",
                    "chat2db_enabled": False
                }
            },
            "chat2db": {
                "auto_start": True,
                "port": 10824
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = key
                    return config
            else:
                # 创建默认配置文件
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
                return default_config
        except Exception as e:
            logger.error(f"加载数据库配置失败: {e}")
            return default_config
    
    def _initialize_connections(self):
        """初始化数据库连接"""
        try:
            for db_name, db_config in self.config.get("databases", {}).items():
                connection = DatabaseConnection(
                    name=db_config.get("name", db_name),
                    db_type=DatabaseType(db_config.get("type", "sqlite")),
                    file_path=db_config.get("file_path", ""),
                    host=db_config.get("host", "localhost"),
                    port=db_config.get("port", 0),
                    database=db_config.get("database", ""),
                    username=db_config.get("username", ""),
                    password=db_config.get("password", ""),
                    chat2db_enabled=db_config.get("chat2db_enabled", True)
                )
                self.database_connections[db_name] = connection
            
            logger.info(f"初始化了 {len(self.database_connections)} 个数据库连接")
            
        except Exception as e:
            logger.error(f"初始化数据库连接失败: {e}")
    
    def start_chat2db(self) -> bool:
        """启动Chat2DB"""
        return self.chat2db_manager.start_chat2db()
    
    def stop_chat2db(self) -> bool:
        """停止Chat2DB"""
        return self.chat2db_manager.stop_chat2db()
    
    def get_chat2db_status(self) -> Dict[str, Any]:
        """获取Chat2DB状态"""
        return self.chat2db_manager.get_chat2db_status()
    
    def add_database_connection(self, connection: DatabaseConnection) -> bool:
        """添加数据库连接"""
        try:
            self.database_connections[connection.name] = connection
            self.save_config()
            logger.info(f"添加数据库连接成功: {connection.name}")
            return True
        except Exception as e:
            logger.error(f"添加数据库连接失败: {e}")
            return False
    
    def remove_database_connection(self, name: str) -> bool:
        """移除数据库连接"""
        try:
            if name in self.database_connections:
                del self.database_connections[name]
                self.save_config()
                logger.info(f"移除数据库连接成功: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"移除数据库连接失败: {e}")
            return False
    
    def get_database_connections(self) -> Dict[str, DatabaseConnection]:
        """获取所有数据库连接"""
        return self.database_connections
    
    def execute_ai_sql(self, natural_language: str, database: str = "sqlite") -> Dict[str, Any]:
        """执行AI SQL生成"""
        if database not in self.database_connections:
            return {"error": f"数据库连接不存在: {database}"}
        
        connection = self.database_connections[database]
        if not connection.chat2db_enabled:
            return {"error": f"数据库 {database} 未启用Chat2DB"}
        
        return self.chat2db_manager.execute_ai_sql(natural_language, database)
    
    def execute_sql(self, sql: str, database: str = "sqlite") -> Dict[str, Any]:
        """执行SQL查询"""
        if database not in self.database_connections:
            return {"error": f"数据库连接不存在: {database}"}
        
        connection = self.database_connections[database]
        if not connection.chat2db_enabled:
            return {"error": f"数据库 {database} 未启用Chat2DB"}
        
        return self.chat2db_manager.execute_sql(sql, database)
    
    def get_database_schema(self, database: str = "sqlite") -> Dict[str, Any]:
        """获取数据库架构"""
        try:
            if database == "sqlite":
                return self._get_sqlite_schema()
            else:
                return self.chat2db_manager.execute_sql(f"SHOW TABLES", database)
        except Exception as e:
            logger.error(f"获取数据库架构失败: {e}")
            return {"error": str(e)}
    
    def _get_sqlite_schema(self) -> Dict[str, Any]:
        """获取SQLite数据库架构"""
        try:
            sqlite_path = self.database_connections.get("sqlite", {}).file_path
            if not sqlite_path or not os.path.exists(sqlite_path):
                return {"error": "SQLite数据库文件不存在"}
            
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            schema = {"tables": {}}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                schema["tables"][table] = [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default_value": col[4],
                        "primary_key": bool(col[5])
                    }
                    for col in columns
                ]
            
            conn.close()
            return schema
            
        except Exception as e:
            logger.error(f"获取SQLite架构失败: {e}")
            return {"error": str(e)}
    
    def save_config(self):
        """保存配置"""
        try:
            config = {
                "databases": {},
                "chat2db": self.config.get("chat2db", {})
            }
            
            for name, connection in self.database_connections.items():
                config["databases"][name] = {
                    "name": connection.name,
                    "type": connection.db_type.value,
                    "file_path": connection.file_path,
                    "host": connection.host,
                    "port": connection.port,
                    "database": connection.database,
                    "username": connection.username,
                    "password": connection.password,
                    "chat2db_enabled": connection.chat2db_enabled
                }
            
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info("数据库配置保存成功")
            
        except Exception as e:
            logger.error(f"保存数据库配置失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        return {
            "total_operations": self.total_operations,
            "uptime": uptime,
            "database_count": len(self.database_connections),
            "chat2db_status": self.get_chat2db_status()
        }
