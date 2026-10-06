#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib数据节点基类
严格按照设计文档实现
"""

import os
import sys
import logging
import hashlib
import pickle
from typing import Dict, Any, Optional, List, Union, Tuple
import pandas as pd
import numpy as np

# Qlib imports
try:
    import qlib
    from qlib.data import D
    from qlib.data.dataset import DatasetH
    from qlib.contrib.data.handler import Alpha158, Alpha360
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.data.dataset.loader import QlibDataLoader
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    from qlib.constant import REG_CN, REG_US
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

from .qlib_base_node import QlibBaseNode

logger = logging.getLogger(__name__)

class QlibDataNode(QlibBaseNode):
    """数据节点基类"""
    
    def __init__(self):
        super().__init__()
        self._data_cache = {}
        self._data_loader = None
        self._data_handler = None
        self._setup_data_properties()
    
    def _setup_data_properties(self):
        """设置数据相关属性"""
        # 数据源配置
        self.set_property('data_source', 'qlib')  # qlib, csv, database, api
        self.set_property('data_path', '~/.qlib/qlib_data/cn_data')
        self.set_property('region', 'cn')  # cn, us
        self.set_property('instruments', 'csi300')
        self.set_property('start_time', '2020-01-01')
        self.set_property('end_time', '2023-12-31')
        self.set_property('freq', 'day')
        self.set_property('fields', ['$close', '$volume', '$open', '$high', '$low'])
        
        # 数据处理配置
        self.set_property('normalize', True)
        self.set_property('fill_method', 'ffill')  # ffill, bfill, interpolate, drop
        self.set_property('outlier_method', 'clip')  # clip, remove, transform
        self.set_property('outlier_threshold', 3.0)
        
        # 缓存配置
        self.set_property('cache_data', True)
        self.set_property('cache_ttl', 3600)  # 1小时
        self.set_property('cache_compression', True)
        
        # 内存配置
        self.set_property('chunk_size', 10000)
        self.set_property('max_memory_usage', 0.8)  # 80%内存使用率
    
    def _validate_specific_config(self) -> bool:
        """验证数据节点特定配置"""
        try:
            # 验证数据源
            data_source = self.get_property('data_source')
            if data_source not in ['qlib', 'csv', 'database', 'api']:
                self._set_status("failed", f"不支持的数据源: {data_source}")
                return False
            
            # 验证时间范围
            start_time = self.get_property('start_time')
            end_time = self.get_property('end_time')
            if not self._validate_time_range(start_time, end_time):
                return False
            
            # 验证字段
            fields = self.get_property('fields')
            if not isinstance(fields, list) or len(fields) == 0:
                self._set_status("failed", "字段列表不能为空")
                return False
            
            # 验证Qlib配置
            if data_source == 'qlib' and not QLIB_AVAILABLE:
                self._set_status("failed", "Qlib不可用，无法使用qlib数据源")
                return False
            
            return True
            
        except Exception as e:
            self._set_status("failed", f"数据节点配置验证失败: {e}")
            return False
    
    def _validate_time_range(self, start_time: str, end_time: str) -> bool:
        """验证时间范围"""
        try:
            from datetime import datetime
            
            start_dt = datetime.strptime(start_time, '%Y-%m-%d')
            end_dt = datetime.strptime(end_time, '%Y-%m-%d')
            
            if start_dt >= end_dt:
                self._set_status("failed", "开始时间必须早于结束时间")
                return False
            
            # 检查时间范围是否合理（不超过10年）
            if (end_dt - start_dt).days > 3650:
                self._set_status("warning", "时间范围超过10年，可能影响性能")
            
            return True
            
        except ValueError:
            self._set_status("failed", "时间格式错误，请使用YYYY-MM-DD格式")
            return False
    
    def _prepare_specific_execution(self) -> bool:
        """准备数据节点特定执行环境"""
        try:
            # 初始化数据加载器
            if not self._initialize_data_loader():
                return False
            
            # 检查内存使用
            if not self._check_memory_usage():
                return False
            
            return True
            
        except Exception as e:
            self._set_status("failed", f"数据节点执行准备失败: {e}")
            return False
    
    def _initialize_data_loader(self) -> bool:
        """初始化数据加载器"""
        try:
            data_source = self.get_property('data_source')
            
            if data_source == 'qlib':
                return self._initialize_qlib_loader()
            elif data_source == 'csv':
                return self._initialize_csv_loader()
            elif data_source == 'database':
                return self._initialize_database_loader()
            elif data_source == 'api':
                return self._initialize_api_loader()
            else:
                self._set_status("failed", f"不支持的数据源: {data_source}")
                return False
                
        except Exception as e:
            self._set_status("failed", f"数据加载器初始化失败: {e}")
            return False
    
    def _initialize_qlib_loader(self) -> bool:
        """初始化Qlib数据加载器"""
        try:
            if not QLIB_AVAILABLE:
                self._set_status("failed", "Qlib不可用")
                return False
            
            # 初始化Qlib
            data_path = os.path.expanduser(self.get_property('data_path'))
            region = self.get_property('region')
            
            if not qlib.is_initialized():
                qlib.init(provider_uri=data_path, region=region)
            
            # 创建数据加载器
            self._data_loader = QlibDataLoader()
            
            logger.info(f"Qlib数据加载器初始化成功: {data_path}, {region}")
            return True
            
        except Exception as e:
            self._set_status("failed", f"Qlib数据加载器初始化失败: {e}")
            return False
    
    def _initialize_csv_loader(self) -> bool:
        """初始化CSV数据加载器"""
        try:
            data_path = self.get_property('data_path')
            if not os.path.exists(data_path):
                self._set_status("failed", f"CSV文件不存在: {data_path}")
                return False
            
            self._data_loader = 'csv'  # 标记为CSV加载器
            logger.info(f"CSV数据加载器初始化成功: {data_path}")
            return True
            
        except Exception as e:
            self._set_status("failed", f"CSV数据加载器初始化失败: {e}")
            return False
    
    def _initialize_database_loader(self) -> bool:
        """初始化数据库数据加载器"""
        try:
            # 这里可以实现数据库连接
            self._data_loader = 'database'
            logger.info("数据库数据加载器初始化成功")
            return True
            
        except Exception as e:
            self._set_status("failed", f"数据库数据加载器初始化失败: {e}")
            return False
    
    def _initialize_api_loader(self) -> bool:
        """初始化API数据加载器"""
        try:
            # 这里可以实现API连接
            self._data_loader = 'api'
            logger.info("API数据加载器初始化成功")
            return True
            
        except Exception as e:
            self._set_status("failed", f"API数据加载器初始化失败: {e}")
            return False
    
    def _check_memory_usage(self) -> bool:
        """检查内存使用情况"""
        try:
            import psutil
            
            # 获取当前内存使用情况
            memory_info = psutil.virtual_memory()
            memory_usage = memory_info.percent / 100.0
            
            max_usage = self.get_property('max_memory_usage', 0.8)
            if memory_usage > max_usage:
                self._set_status("warning", f"内存使用率过高: {memory_usage:.1%}")
                return False
            
            return True
            
        except ImportError:
            # 如果没有psutil，跳过内存检查
            logger.warning("psutil不可用，跳过内存检查")
            return True
        except Exception as e:
            logger.warning(f"内存检查失败: {e}")
            return True
    
    def get_data(self, config: Dict) -> Any:
        """获取数据"""
        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(config)
            
            # 检查缓存
            if self.get_property('cache_data', True):
                cached_data = self._get_cached_data(cache_key)
                if cached_data is not None:
                    logger.info(f"从缓存获取数据: {cache_key}")
                    return cached_data
            
            # 从数据源获取数据
            data = self._load_data_from_source(config)
            
            # 处理数据
            processed_data = self.process_data(data)
            
            # 缓存数据
            if self.get_property('cache_data', True):
                self.cache_data(processed_data, cache_key)
            
            return processed_data
            
        except Exception as e:
            self._set_status("failed", f"数据获取失败: {e}")
            logger.error(f"数据获取失败: {e}")
            return None
    
    def _load_data_from_source(self, config: Dict) -> Any:
        """从数据源加载数据"""
        data_source = self.get_property('data_source')
        
        if data_source == 'qlib':
            return self._load_qlib_data(config)
        elif data_source == 'csv':
            return self._load_csv_data(config)
        elif data_source == 'database':
            return self._load_database_data(config)
        elif data_source == 'api':
            return self._load_api_data(config)
        else:
            raise ValueError(f"不支持的数据源: {data_source}")
    
    def _load_qlib_data(self, config: Dict) -> pd.DataFrame:
        """加载Qlib数据"""
        try:
            instruments = config.get('instruments', self.get_property('instruments'))
            fields = config.get('fields', self.get_property('fields'))
            start_time = config.get('start_time', self.get_property('start_time'))
            end_time = config.get('end_time', self.get_property('end_time'))
            freq = config.get('freq', self.get_property('freq'))
            
            # 使用Qlib D.features获取数据
            data = D.features(
                instruments=instruments,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                freq=freq
            )
            
            logger.info(f"Qlib数据加载成功: {data.shape}")
            return data
            
        except Exception as e:
            raise Exception(f"Qlib数据加载失败: {e}")
    
    def _load_csv_data(self, config: Dict) -> pd.DataFrame:
        """加载CSV数据"""
        try:
            file_path = config.get('file_path', self.get_property('data_path'))
            
            # 读取CSV文件
            data = pd.read_csv(file_path)
            
            # 处理时间列
            if 'datetime' in data.columns:
                data['datetime'] = pd.to_datetime(data['datetime'])
                data.set_index('datetime', inplace=True)
            
            logger.info(f"CSV数据加载成功: {data.shape}")
            return data
            
        except Exception as e:
            raise Exception(f"CSV数据加载失败: {e}")
    
    def _load_database_data(self, config: Dict) -> pd.DataFrame:
        """加载数据库数据"""
        try:
            # 这里实现数据库查询逻辑
            # 示例实现
            query = config.get('query', 'SELECT * FROM market_data')
            # data = pd.read_sql(query, connection)
            # 临时返回空DataFrame
            data = pd.DataFrame()
            
            logger.info(f"数据库数据加载成功: {data.shape}")
            return data
            
        except Exception as e:
            raise Exception(f"数据库数据加载失败: {e}")
    
    def _load_api_data(self, config: Dict) -> pd.DataFrame:
        """加载API数据"""
        try:
            # 这里实现API调用逻辑
            # 示例实现
            url = config.get('url', '')
            # response = requests.get(url)
            # data = pd.DataFrame(response.json())
            # 临时返回空DataFrame
            data = pd.DataFrame()
            
            logger.info(f"API数据加载成功: {data.shape}")
            return data
            
        except Exception as e:
            raise Exception(f"API数据加载失败: {e}")
    
    def process_data(self, data: Any) -> Any:
        """处理数据"""
        try:
            if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                self._set_status("warning", "输入数据为空")
                return data
            
            # 数据清洗
            processed_data = self._clean_data(data)
            
            # 数据标准化
            if self.get_property('normalize', True):
                processed_data = self._normalize_data(processed_data)
            
            # 异常值处理
            processed_data = self._handle_outliers(processed_data)
            
            # 缺失值处理
            processed_data = self._handle_missing_values(processed_data)
            
            logger.info(f"数据处理完成: {processed_data.shape if hasattr(processed_data, 'shape') else 'N/A'}")
            return processed_data
            
        except Exception as e:
            self._set_status("failed", f"数据处理失败: {e}")
            logger.error(f"数据处理失败: {e}")
            return data
    
    def _clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        try:
            # 移除重复行
            data = data.drop_duplicates()
            
            # 移除全为NaN的行
            data = data.dropna(how='all')
            
            # 移除全为NaN的列
            data = data.dropna(axis=1, how='all')
            
            return data
            
        except Exception as e:
            logger.warning(f"数据清洗失败: {e}")
            return data
    
    def _normalize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """标准化数据"""
        try:
            from sklearn.preprocessing import StandardScaler
            
            # 只对数值列进行标准化
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            if len(numeric_columns) > 0:
                scaler = StandardScaler()
                data[numeric_columns] = scaler.fit_transform(data[numeric_columns])
            
            return data
            
        except Exception as e:
            logger.warning(f"数据标准化失败: {e}")
            return data
    
    def _handle_outliers(self, data: pd.DataFrame) -> pd.DataFrame:
        """处理异常值"""
        try:
            outlier_method = self.get_property('outlier_method', 'clip')
            threshold = self.get_property('outlier_threshold', 3.0)
            
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            for column in numeric_columns:
                if outlier_method == 'clip':
                    # 使用3σ原则裁剪异常值
                    mean = data[column].mean()
                    std = data[column].std()
                    data[column] = data[column].clip(
                        mean - threshold * std,
                        mean + threshold * std
                    )
                elif outlier_method == 'remove':
                    # 移除异常值
                    mean = data[column].mean()
                    std = data[column].std()
                    mask = (data[column] >= mean - threshold * std) & (data[column] <= mean + threshold * std)
                    data = data[mask]
                elif outlier_method == 'transform':
                    # 使用对数变换
                    data[column] = np.log1p(data[column])
            
            return data
            
        except Exception as e:
            logger.warning(f"异常值处理失败: {e}")
            return data
    
    def _handle_missing_values(self, data: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""
        try:
            fill_method = self.get_property('fill_method', 'ffill')
            
            if fill_method == 'ffill':
                data = data.fillna(method='ffill')
            elif fill_method == 'bfill':
                data = data.fillna(method='bfill')
            elif fill_method == 'interpolate':
                data = data.interpolate()
            elif fill_method == 'drop':
                data = data.dropna()
            
            return data
            
        except Exception as e:
            logger.warning(f"缺失值处理失败: {e}")
            return data
    
    def cache_data(self, data: Any, key: str):
        """缓存数据"""
        try:
            if not self.get_property('cache_data', True):
                return
            
            # 检查缓存大小限制
            if self._check_cache_size(data):
                # 压缩数据
                if self.get_property('cache_compression', True):
                    data = self._compress_data(data)
                
                # 存储到缓存
                self._data_cache[key] = {
                    'data': data,
                    'timestamp': pd.Timestamp.now(),
                    'ttl': self.get_property('cache_ttl', 3600)
                }
                
                logger.debug(f"数据已缓存: {key}")
            
        except Exception as e:
            logger.warning(f"数据缓存失败: {e}")
    
    def _check_cache_size(self, data: Any) -> bool:
        """检查缓存大小"""
        try:
            # 估算数据大小
            if isinstance(data, pd.DataFrame):
                data_size = data.memory_usage(deep=True).sum()
            else:
                data_size = sys.getsizeof(data)
            
            # 检查是否超过内存限制
            max_memory = self.get_property('memory_limit', 1024 * 1024 * 1024)
            if data_size > max_memory * 0.1:  # 不超过10%内存
                logger.warning(f"数据过大，跳过缓存: {data_size / 1024 / 1024:.1f}MB")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"缓存大小检查失败: {e}")
            return True
    
    def _compress_data(self, data: Any) -> bytes:
        """压缩数据"""
        try:
            return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.warning(f"数据压缩失败: {e}")
            return data
    
    def _decompress_data(self, compressed_data: bytes) -> Any:
        """解压数据"""
        try:
            return pickle.loads(compressed_data)
        except Exception as e:
            logger.warning(f"数据解压失败: {e}")
            return compressed_data
    
    def _get_cached_data(self, key: str) -> Any:
        """获取缓存数据"""
        try:
            if key not in self._data_cache:
                return None
            
            cache_entry = self._data_cache[key]
            
            # 检查TTL
            ttl = cache_entry['ttl']
            timestamp = cache_entry['timestamp']
            if (pd.Timestamp.now() - timestamp).total_seconds() > ttl:
                # 缓存过期，删除
                del self._data_cache[key]
                return None
            
            # 解压数据
            data = cache_entry['data']
            if isinstance(data, bytes):
                data = self._decompress_data(data)
            
            return data
            
        except Exception as e:
            logger.warning(f"获取缓存数据失败: {e}")
            return None
    
    def _generate_cache_key(self, config: Dict) -> str:
        """生成缓存键"""
        try:
            # 创建配置字符串
            config_str = str(sorted(config.items()))
            
            # 生成哈希值
            hash_obj = hashlib.md5()
            hash_obj.update(config_str.encode('utf-8'))
            hash_obj.update(self._node_id.encode('utf-8'))
            
            return f"{self.__class__.__name__}_{hash_obj.hexdigest()[:16]}"
            
        except Exception as e:
            logger.warning(f"生成缓存键失败: {e}")
            return f"{self.__class__.__name__}_{id(config)}"
    
    def _cleanup_specific(self):
        """清理数据节点特定资源"""
        try:
            # 清理缓存
            self._data_cache.clear()
            
            # 清理数据加载器
            self._data_loader = None
            self._data_handler = None
            
        except Exception as e:
            logger.warning(f"数据节点清理失败: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            'cache_size': len(self._data_cache),
            'cache_keys': list(self._data_cache.keys()),
            'memory_usage': sum(sys.getsizeof(entry) for entry in self._data_cache.values())
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._data_cache.clear()
        logger.info("数据缓存已清空")
