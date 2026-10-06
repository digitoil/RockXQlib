#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 数据库连接管理器
管理多种数据库连接，支持连接池和自动重连
"""

import os
import time
import logging
import threading
import sqlite3
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import queue
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class ConnectionStatus(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class ConnectionInfo:
    """连接信息"""
    name: str
    db_type: str
    status: ConnectionStatus
    created_time: float
    last_used: float
    error_message: str = ""
    connection_count: int = 0

class DatabaseConnectionPool:
    """数据库连接池"""
    
    def __init__(self, max_connections: int = 10, min_connections: int = 2):
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.connections = queue.Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()
        
        # 初始化最小连接数
        self._initialize_min_connections()
    
    def _initialize_min_connections(self):
        """初始化最小连接数"""
        for _ in range(self.min_connections):
            try:
                conn = self._create_connection()
                if conn:
                    self.connections.put(conn)
                    self.active_connections += 1
            except Exception as e:
                logger.error(f"初始化连接失败: {e}")
    
    def _create_connection(self) -> Optional[Any]:
        """创建新连接"""
        # 这里应该根据数据库类型创建相应的连接
        # 目前只实现SQLite连接
        try:
            conn = sqlite3.connect("rockxqlib.db", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"创建连接失败: {e}")
            return None
    
    def get_connection(self, timeout: int = 30) -> Optional[Any]:
        """获取连接"""
        try:
            # 尝试从池中获取连接
            conn = self.connections.get(timeout=timeout)
            return conn
        except queue.Empty:
            # 如果池中没有连接，尝试创建新连接
            with self.lock:
                if self.active_connections < self.max_connections:
                    conn = self._create_connection()
                    if conn:
                        self.active_connections += 1
                        return conn
            return None
    
    def return_connection(self, conn: Any):
        """归还连接"""
        try:
            if conn:
                self.connections.put(conn)
        except queue.Full:
            # 如果池已满，关闭连接
            conn.close()
            with self.lock:
                self.active_connections -= 1
    
    def close_all(self):
        """关闭所有连接"""
        while not self.connections.empty():
            try:
                conn = self.connections.get_nowait()
                conn.close()
            except queue.Empty:
                break
        self.active_connections = 0

class RockXQlibDatabaseConnectionManager:
    """RockXQlib数据库连接管理器"""
    
    def __init__(self, config_path: str = "config/database_config.yaml"):
        self.config_path = config_path
        self.connections: Dict[str, Any] = {}
        self.connection_info: Dict[str, ConnectionInfo] = {}
        self.connection_pools: Dict[str, DatabaseConnectionPool] = {}
        
        # 加载配置
        self.config = self._load_config()
        
        # 统计信息
        self.total_connections = 0
        self.successful_connections = 0
        self.failed_connections = 0
        self.start_time = time.time()
        
        logger.info("数据库连接管理器初始化完成")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            "connection_pool": {
                "max_connections": 10,
                "min_connections": 2,
                "connection_timeout": 30,
                "idle_timeout": 300
            },
            "databases": {
                "sqlite": {
                    "name": "RockXQlib SQLite",
                    "type": "sqlite",
                    "file_path": "rockxqlib.db",
                    "enabled": True
                }
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                import yaml
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            else:
                return default_config
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return default_config
    
    def connect_database(self, name: str, connection_config: Dict[str, Any]) -> bool:
        """连接数据库"""
        try:
            self.connection_info[name] = ConnectionInfo(
                name=name,
                db_type=connection_config.get("type", "sqlite"),
                status=ConnectionStatus.CONNECTING,
                created_time=time.time(),
                last_used=time.time()
            )
            
            # 根据数据库类型创建连接
            if connection_config.get("type") == "sqlite":
                success = self._connect_sqlite(name, connection_config)
            elif connection_config.get("type") == "mysql":
                success = self._connect_mysql(name, connection_config)
            elif connection_config.get("type") == "postgresql":
                success = self._connect_postgresql(name, connection_config)
            elif connection_config.get("type") == "mongodb":
                success = self._connect_mongodb(name, connection_config)
            else:
                success = False
                self.connection_info[name].error_message = f"不支持的数据库类型: {connection_config.get('type')}"
            
            if success:
                self.connection_info[name].status = ConnectionStatus.CONNECTED
                self.successful_connections += 1
                logger.info(f"数据库连接成功: {name}")
            else:
                self.connection_info[name].status = ConnectionStatus.ERROR
                self.failed_connections += 1
                logger.error(f"数据库连接失败: {name}")
            
            self.total_connections += 1
            return success
            
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            if name in self.connection_info:
                self.connection_info[name].status = ConnectionStatus.ERROR
                self.connection_info[name].error_message = str(e)
            self.failed_connections += 1
            return False
    
    def _connect_sqlite(self, name: str, config: Dict[str, Any]) -> bool:
        """连接SQLite数据库"""
        try:
            file_path = config.get("file_path", "rockxqlib.db")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 创建连接
            conn = sqlite3.connect(file_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            
            # 测试连接
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            self.connections[name] = conn
            
            # 创建连接池
            self.connection_pools[name] = DatabaseConnectionPool(
                max_connections=self.config.get("connection_pool", {}).get("max_connections", 10),
                min_connections=self.config.get("connection_pool", {}).get("min_connections", 2)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"连接SQLite失败: {e}")
            return False
    
    def _connect_mysql(self, name: str, config: Dict[str, Any]) -> bool:
        """连接MySQL数据库"""
        try:
            import pymysql
            
            conn = pymysql.connect(
                host=config.get("host", "localhost"),
                port=config.get("port", 3306),
                user=config.get("username", ""),
                password=config.get("password", ""),
                database=config.get("database", ""),
                charset='utf8mb4'
            )
            
            # 测试连接
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            self.connections[name] = conn
            return True
            
        except ImportError:
            logger.error("PyMySQL未安装，无法连接MySQL")
            return False
        except Exception as e:
            logger.error(f"连接MySQL失败: {e}")
            return False
    
    def _connect_postgresql(self, name: str, config: Dict[str, Any]) -> bool:
        """连接PostgreSQL数据库"""
        try:
            import psycopg2
            
            conn = psycopg2.connect(
                host=config.get("host", "localhost"),
                port=config.get("port", 5432),
                user=config.get("username", ""),
                password=config.get("password", ""),
                database=config.get("database", "")
            )
            
            # 测试连接
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            self.connections[name] = conn
            return True
            
        except ImportError:
            logger.error("psycopg2未安装，无法连接PostgreSQL")
            return False
        except Exception as e:
            logger.error(f"连接PostgreSQL失败: {e}")
            return False
    
    def _connect_mongodb(self, name: str, config: Dict[str, Any]) -> bool:
        """连接MongoDB数据库"""
        try:
            import pymongo
            
            client = pymongo.MongoClient(
                host=config.get("host", "localhost"),
                port=config.get("port", 27017),
                username=config.get("username", ""),
                password=config.get("password", ""),
                serverSelectionTimeoutMS=5000
            )
            
            # 测试连接
            client.admin.command('ping')
            
            self.connections[name] = client
            return True
            
        except ImportError:
            logger.error("pymongo未安装，无法连接MongoDB")
            return False
        except Exception as e:
            logger.error(f"连接MongoDB失败: {e}")
            return False
    
    def disconnect_database(self, name: str) -> bool:
        """断开数据库连接"""
        try:
            if name in self.connections:
                conn = self.connections[name]
                if hasattr(conn, 'close'):
                    conn.close()
                del self.connections[name]
            
            if name in self.connection_pools:
                self.connection_pools[name].close_all()
                del self.connection_pools[name]
            
            if name in self.connection_info:
                self.connection_info[name].status = ConnectionStatus.DISCONNECTED
            
            logger.info(f"数据库连接已断开: {name}")
            return True
            
        except Exception as e:
            logger.error(f"断开数据库连接失败: {e}")
            return False
    
    def get_connection(self, name: str) -> Optional[Any]:
        """获取数据库连接"""
        if name in self.connections:
            self.connection_info[name].last_used = time.time()
            self.connection_info[name].connection_count += 1
            return self.connections[name]
        return None
    
    def get_connection_from_pool(self, name: str) -> Optional[Any]:
        """从连接池获取连接"""
        if name in self.connection_pools:
            return self.connection_pools[name].get_connection()
        return None
    
    def return_connection_to_pool(self, name: str, conn: Any):
        """归还连接到连接池"""
        if name in self.connection_pools:
            self.connection_pools[name].return_connection(conn)
    
    def test_connection(self, name: str) -> bool:
        """测试数据库连接"""
        try:
            if name not in self.connections:
                return False
            
            conn = self.connections[name]
            
            if self.connection_info[name].db_type == "sqlite":
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            elif self.connection_info[name].db_type == "mysql":
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            elif self.connection_info[name].db_type == "postgresql":
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            elif self.connection_info[name].db_type == "mongodb":
                conn.admin.command('ping')
            
            return True
            
        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            if name in self.connection_info:
                self.connection_info[name].status = ConnectionStatus.ERROR
                self.connection_info[name].error_message = str(e)
            return False
    
    def get_connection_status(self, name: str) -> Optional[ConnectionInfo]:
        """获取连接状态"""
        return self.connection_info.get(name)
    
    def get_all_connections(self) -> Dict[str, ConnectionInfo]:
        """获取所有连接信息"""
        return self.connection_info.copy()
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        uptime = time.time() - self.start_time
        active_connections = sum(1 for info in self.connection_info.values() 
                               if info.status == ConnectionStatus.CONNECTED)
        
        return {
            "total_connections": self.total_connections,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "active_connections": active_connections,
            "uptime": uptime,
            "success_rate": (self.successful_connections / max(self.total_connections, 1)) * 100
        }
    
    def close_all_connections(self):
        """关闭所有连接"""
        for name in list(self.connections.keys()):
            self.disconnect_database(name)
        
        logger.info("所有数据库连接已关闭")
    
    def __del__(self):
        """析构函数"""
        self.close_all_connections()
