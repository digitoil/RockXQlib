#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib智能缓存管理器
严格按照设计文档实现
"""

import os
import sys
import logging
import hashlib
import pickle
import json
import time
import threading
from typing import Dict, Any, Optional, List, Union, Tuple
from collections import OrderedDict
import pandas as pd
import numpy as np

from .qlib_base_node import QlibBaseNode

logger = logging.getLogger(__name__)

class QlibCacheManager:
    """智能缓存管理器"""
    
    def __init__(self, cache_dir: str = "./cache", max_memory_size: int = 1024 * 1024 * 1024):
        self.cache_dir = cache_dir
        self.max_memory_size = max_memory_size
        self.memory_cache = OrderedDict()  # LRU缓存
        self.disk_cache = {}  # 磁盘缓存索引
        self.cache_policies = {}  # 缓存策略
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'memory_usage': 0,
            'disk_usage': 0
        }
        self.lock = threading.RLock()  # 线程安全锁
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        # 加载磁盘缓存索引
        self._load_disk_cache_index()
        
        logger.info(f"缓存管理器初始化完成: {cache_dir}, 最大内存: {max_memory_size / 1024 / 1024:.1f}MB")
    
    def get_cache_key(self, node: QlibBaseNode, inputs: Dict) -> str:
        """生成缓存键"""
        try:
            # 获取节点信息
            node_id = node.get_node_id()
            node_class = node.__class__.__name__
            node_properties = node.get_all_properties()
            
            # 创建输入数据的哈希
            inputs_hash = self._hash_data(inputs)
            
            # 创建节点配置的哈希
            config_hash = self._hash_data(node_properties)
            
            # 组合缓存键
            cache_key = f"{node_class}_{node_id}_{config_hash}_{inputs_hash}"
            
            # 限制键长度
            if len(cache_key) > 255:
                cache_key = hashlib.md5(cache_key.encode()).hexdigest()
            
            return cache_key
            
        except Exception as e:
            logger.error(f"生成缓存键失败: {e}")
            return f"error_{int(time.time())}"
    
    def _hash_data(self, data: Any) -> str:
        """计算数据哈希值"""
        try:
            if isinstance(data, (dict, list, tuple)):
                # 对复杂数据结构进行JSON序列化后哈希
                data_str = json.dumps(data, sort_keys=True, default=str)
            elif isinstance(data, pd.DataFrame):
                # 对DataFrame进行特殊处理
                data_str = f"{data.shape}_{data.columns.tolist()}_{data.index.tolist()}"
            elif isinstance(data, np.ndarray):
                # 对NumPy数组进行特殊处理
                data_str = f"{data.shape}_{data.dtype}_{data.tobytes()}"
            else:
                data_str = str(data)
            
            # 计算MD5哈希
            return hashlib.md5(data_str.encode('utf-8')).hexdigest()[:16]
            
        except Exception as e:
            logger.warning(f"数据哈希计算失败: {e}")
            return str(hash(str(data)))[:16]
    
    def get_cached_result(self, key: str) -> Any:
        """获取缓存结果"""
        try:
            with self.lock:
                # 首先检查内存缓存
                if key in self.memory_cache:
                    # 更新LRU顺序
                    result = self.memory_cache.pop(key)
                    self.memory_cache[key] = result
                    self.cache_stats['hits'] += 1
                    logger.debug(f"内存缓存命中: {key}")
                    return result
                
                # 检查磁盘缓存
                if key in self.disk_cache:
                    result = self._load_from_disk(key)
                    if result is not None:
                        # 加载到内存缓存
                        self._add_to_memory_cache(key, result)
                        self.cache_stats['hits'] += 1
                        logger.debug(f"磁盘缓存命中: {key}")
                        return result
                
                # 缓存未命中
                self.cache_stats['misses'] += 1
                logger.debug(f"缓存未命中: {key}")
                return None
                
        except Exception as e:
            logger.error(f"获取缓存结果失败: {e}")
            self.cache_stats['misses'] += 1
            return None
    
    def cache_result(self, key: str, result: Any):
        """缓存结果"""
        try:
            with self.lock:
                # 检查结果是否可缓存
                if not self._is_cacheable(result):
                    logger.debug(f"结果不可缓存: {key}")
                    return
                
                # 添加到内存缓存
                self._add_to_memory_cache(key, result)
                
                # 添加到磁盘缓存
                self._add_to_disk_cache(key, result)
                
                logger.debug(f"结果已缓存: {key}")
                
        except Exception as e:
            logger.error(f"缓存结果失败: {e}")
    
    def _is_cacheable(self, result: Any) -> bool:
        """检查结果是否可缓存"""
        try:
            if result is None:
                return False
            
            # 检查数据类型
            if isinstance(result, (str, int, float, bool)):
                return True
            
            if isinstance(result, (list, tuple, dict)):
                return len(str(result)) < 1024 * 1024  # 小于1MB
            
            if isinstance(result, pd.DataFrame):
                return result.memory_usage(deep=True).sum() < 100 * 1024 * 1024  # 小于100MB
            
            if isinstance(result, np.ndarray):
                return result.nbytes < 100 * 1024 * 1024  # 小于100MB
            
            # 其他类型检查大小
            try:
                size = sys.getsizeof(result)
                return size < 100 * 1024 * 1024  # 小于100MB
            except:
                return False
                
        except Exception as e:
            logger.warning(f"缓存性检查失败: {e}")
            return False
    
    def _add_to_memory_cache(self, key: str, result: Any):
        """添加到内存缓存"""
        try:
            # 计算结果大小
            result_size = self._calculate_size(result)
            
            # 检查内存限制
            while (self.cache_stats['memory_usage'] + result_size > self.max_memory_size and 
                   self.memory_cache):
                self._evict_from_memory()
            
            # 添加到内存缓存
            self.memory_cache[key] = result
            self.cache_stats['memory_usage'] += result_size
            
        except Exception as e:
            logger.warning(f"添加到内存缓存失败: {e}")
    
    def _add_to_disk_cache(self, key: str, result: Any):
        """添加到磁盘缓存"""
        try:
            # 生成磁盘文件路径
            file_path = os.path.join(self.cache_dir, f"{key}.pkl")
            
            # 保存到磁盘
            with open(file_path, 'wb') as f:
                pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # 更新磁盘缓存索引
            file_size = os.path.getsize(file_path)
            self.disk_cache[key] = {
                'file_path': file_path,
                'size': file_size,
                'timestamp': time.time()
            }
            
            self.cache_stats['disk_usage'] += file_size
            
        except Exception as e:
            logger.warning(f"添加到磁盘缓存失败: {e}")
    
    def _load_from_disk(self, key: str) -> Any:
        """从磁盘加载缓存"""
        try:
            if key not in self.disk_cache:
                return None
            
            file_path = self.disk_cache[key]['file_path']
            
            if not os.path.exists(file_path):
                # 文件不存在，清理索引
                del self.disk_cache[key]
                return None
            
            # 加载文件
            with open(file_path, 'rb') as f:
                result = pickle.load(f)
            
            return result
            
        except Exception as e:
            logger.warning(f"从磁盘加载缓存失败: {e}")
            return None
    
    def _calculate_size(self, data: Any) -> int:
        """计算数据大小"""
        try:
            if isinstance(data, pd.DataFrame):
                return data.memory_usage(deep=True).sum()
            elif isinstance(data, np.ndarray):
                return data.nbytes
            else:
                return sys.getsizeof(data)
                
        except Exception as e:
            logger.warning(f"计算数据大小失败: {e}")
            return 1024  # 默认1KB
    
    def _evict_from_memory(self):
        """从内存缓存中淘汰数据"""
        try:
            if not self.memory_cache:
                return
            
            # 使用LRU策略淘汰
            key, result = self.memory_cache.popitem(last=False)
            
            # 更新统计信息
            result_size = self._calculate_size(result)
            self.cache_stats['memory_usage'] -= result_size
            self.cache_stats['evictions'] += 1
            
            logger.debug(f"内存缓存淘汰: {key}")
            
        except Exception as e:
            logger.warning(f"内存缓存淘汰失败: {e}")
    
    def invalidate_cache(self, pattern: str):
        """失效缓存"""
        try:
            with self.lock:
                # 失效内存缓存
                keys_to_remove = []
                for key in self.memory_cache:
                    if pattern in key:
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    result = self.memory_cache.pop(key)
                    result_size = self._calculate_size(result)
                    self.cache_stats['memory_usage'] -= result_size
                
                # 失效磁盘缓存
                disk_keys_to_remove = []
                for key, cache_info in self.disk_cache.items():
                    if pattern in key:
                        disk_keys_to_remove.append(key)
                        # 删除文件
                        try:
                            os.remove(cache_info['file_path'])
                            self.cache_stats['disk_usage'] -= cache_info['size']
                        except:
                            pass
                
                for key in disk_keys_to_remove:
                    del self.disk_cache[key]
                
                logger.info(f"缓存失效完成: {pattern}, 清理了 {len(keys_to_remove)} 个内存缓存, {len(disk_keys_to_remove)} 个磁盘缓存")
                
        except Exception as e:
            logger.error(f"缓存失效失败: {e}")
    
    def clear_cache(self):
        """清空所有缓存"""
        try:
            with self.lock:
                # 清空内存缓存
                self.memory_cache.clear()
                self.cache_stats['memory_usage'] = 0
                
                # 清空磁盘缓存
                for key, cache_info in self.disk_cache.items():
                    try:
                        os.remove(cache_info['file_path'])
                    except:
                        pass
                
                self.disk_cache.clear()
                self.cache_stats['disk_usage'] = 0
                
                # 重置统计信息
                self.cache_stats['hits'] = 0
                self.cache_stats['misses'] = 0
                self.cache_stats['evictions'] = 0
                
                logger.info("所有缓存已清空")
                
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
    
    def _load_disk_cache_index(self):
        """加载磁盘缓存索引"""
        try:
            index_file = os.path.join(self.cache_dir, "cache_index.json")
            
            if os.path.exists(index_file):
                with open(index_file, 'r', encoding='utf-8') as f:
                    self.disk_cache = json.load(f)
                
                # 验证文件是否存在
                valid_cache = {}
                for key, cache_info in self.disk_cache.items():
                    if os.path.exists(cache_info['file_path']):
                        valid_cache[key] = cache_info
                    else:
                        logger.warning(f"磁盘缓存文件不存在: {cache_info['file_path']}")
                
                self.disk_cache = valid_cache
                logger.info(f"磁盘缓存索引加载完成: {len(self.disk_cache)} 个文件")
            
        except Exception as e:
            logger.warning(f"加载磁盘缓存索引失败: {e}")
    
    def _save_disk_cache_index(self):
        """保存磁盘缓存索引"""
        try:
            index_file = os.path.join(self.cache_dir, "cache_index.json")
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(self.disk_cache, f, indent=2, ensure_ascii=False)
            
            logger.debug("磁盘缓存索引已保存")
            
        except Exception as e:
            logger.warning(f"保存磁盘缓存索引失败: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
            hit_rate = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                'hits': self.cache_stats['hits'],
                'misses': self.cache_stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self.cache_stats['evictions'],
                'memory_usage': self.cache_stats['memory_usage'],
                'memory_usage_mb': self.cache_stats['memory_usage'] / 1024 / 1024,
                'disk_usage': self.cache_stats['disk_usage'],
                'disk_usage_mb': self.cache_stats['disk_usage'] / 1024 / 1024,
                'memory_cache_size': len(self.memory_cache),
                'disk_cache_size': len(self.disk_cache),
                'max_memory_size': self.max_memory_size,
                'max_memory_size_mb': self.max_memory_size / 1024 / 1024
            }
    
    def cleanup_expired_cache(self, max_age: int = 3600):
        """清理过期缓存"""
        try:
            current_time = time.time()
            expired_keys = []
            
            # 检查磁盘缓存
            for key, cache_info in self.disk_cache.items():
                if current_time - cache_info['timestamp'] > max_age:
                    expired_keys.append(key)
            
            # 清理过期缓存
            for key in expired_keys:
                try:
                    os.remove(self.disk_cache[key]['file_path'])
                    del self.disk_cache[key]
                except:
                    pass
            
            if expired_keys:
                logger.info(f"清理了 {len(expired_keys)} 个过期缓存")
            
        except Exception as e:
            logger.warning(f"清理过期缓存失败: {e}")
    
    def optimize_cache(self):
        """优化缓存"""
        try:
            # 清理过期缓存
            self.cleanup_expired_cache()
            
            # 保存磁盘缓存索引
            self._save_disk_cache_index()
            
            # 压缩内存缓存
            if len(self.memory_cache) > 1000:  # 如果缓存项过多
                # 保留最近使用的50%
                items = list(self.memory_cache.items())
                keep_count = len(items) // 2
                self.memory_cache.clear()
                self.memory_cache.update(items[-keep_count:])
                
                logger.info(f"内存缓存优化完成，保留 {keep_count} 个最近使用的项")
            
        except Exception as e:
            logger.warning(f"缓存优化失败: {e}")
    
    def __del__(self):
        """析构函数"""
        try:
            self._save_disk_cache_index()
        except:
            pass
