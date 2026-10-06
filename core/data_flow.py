#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 统一数据流系统
提供统一的数据格式、传输协议、缓存机制
"""

import time
import hashlib
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import queue
import pickle
import gzip
from pathlib import Path

logger = logging.getLogger(__name__)

class RockXQlibDataFormat(Enum):
    """数据格式枚举"""
    JSON = "json"
    PICKLE = "pickle"
    PARQUET = "parquet"
    CSV = "csv"
    HDF5 = "hdf5"
    NUMPY = "numpy"

class RockXQlibDataQuality(Enum):
    """数据质量枚举"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"

@dataclass
class RockXQlibDataMetadata:
    """数据元数据"""
    data_id: str
    data_type: str
    format: RockXQlibDataFormat
    size_bytes: int
    quality: RockXQlibDataQuality
    source: str
    timestamp: float
    version: str
    tags: List[str] = None
    description: str = ""
    schema: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.schema is None:
            self.schema = {}

class RockXQlibDataPacket:
    """统一数据包格式"""
    
    def __init__(self, data: Any, metadata: Optional[RockXQlibDataMetadata] = None, 
                 format_type: RockXQlibDataFormat = RockXQlibDataFormat.JSON):
        self.data = data
        self.format_type = format_type
        self.timestamp = time.time()
        self.data_id = self._generate_data_id()
        self.version = "1.0"
        
        # 创建元数据
        if metadata is None:
            self.metadata = RockXQlibDataMetadata(
                data_id=self.data_id,
                data_type=type(data).__name__,
                format=format_type,
                size_bytes=self._calculate_size(),
                quality=RockXQlibDataQuality.UNKNOWN,
                source="unknown",
                timestamp=self.timestamp,
                version=self.version
            )
        else:
            self.metadata = metadata
        
        # 数据验证
        self._validate_data()
    
    def _generate_data_id(self) -> str:
        """生成数据ID"""
        timestamp = str(self.timestamp)
        data_str = str(self.data)[:100]  # 只取前100个字符
        return hashlib.md5(f"{timestamp}_{data_str}_{id(self.data)}".encode()).hexdigest()[:16]
    
    def _calculate_size(self) -> int:
        """计算数据大小"""
        try:
            if self.format_type == RockXQlibDataFormat.JSON:
                return len(json.dumps(self.data, default=str).encode('utf-8'))
            elif self.format_type == RockXQlibDataFormat.PICKLE:
                return len(pickle.dumps(self.data))
            else:
                return len(str(self.data).encode('utf-8'))
        except:
            return 0
    
    def _validate_data(self):
        """验证数据"""
        try:
            # 基本验证
            if self.data is None:
                self.metadata.quality = RockXQlibDataQuality.POOR
                return
            
            # 根据数据类型进行验证
            if isinstance(self.data, dict):
                if not self.data:
                    self.metadata.quality = RockXQlibDataQuality.POOR
                else:
                    self.metadata.quality = RockXQlibDataQuality.GOOD
            elif isinstance(self.data, list):
                if not self.data:
                    self.metadata.quality = RockXQlibDataQuality.POOR
                else:
                    self.metadata.quality = RockXQlibDataQuality.GOOD
            else:
                self.metadata.quality = RockXQlibDataQuality.GOOD
                
        except Exception as e:
            logger.warning(f"数据验证失败: {e}")
            self.metadata.quality = RockXQlibDataQuality.POOR
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'data_id': self.data_id,
            'data': self.data,
            'metadata': asdict(self.metadata),
            'format_type': self.format_type.value,
            'timestamp': self.timestamp,
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]) -> 'RockXQlibDataPacket':
        """从字典创建数据包"""
        metadata_dict = data_dict.get('metadata', {})
        metadata = RockXQlibDataMetadata(**metadata_dict)
        
        packet = cls(
            data=data_dict['data'],
            metadata=metadata,
            format_type=RockXQlibDataFormat(data_dict.get('format_type', 'json'))
        )
        packet.data_id = data_dict['data_id']
        packet.timestamp = data_dict['timestamp']
        packet.version = data_dict['version']
        return packet
    
    def serialize(self) -> bytes:
        """序列化数据包"""
        try:
            if self.format_type == RockXQlibDataFormat.JSON:
                return json.dumps(self.to_dict(), default=str).encode('utf-8')
            elif self.format_type == RockXQlibDataFormat.PICKLE:
                return pickle.dumps(self.to_dict())
            else:
                return json.dumps(self.to_dict(), default=str).encode('utf-8')
        except Exception as e:
            logger.error(f"数据包序列化失败: {e}")
            return b""
    
    @classmethod
    def deserialize(cls, data_bytes: bytes, format_type: RockXQlibDataFormat = RockXQlibDataFormat.JSON) -> 'RockXQlibDataPacket':
        """反序列化数据包"""
        try:
            if format_type == RockXQlibDataFormat.JSON:
                data_dict = json.loads(data_bytes.decode('utf-8'))
            elif format_type == RockXQlibDataFormat.PICKLE:
                data_dict = pickle.loads(data_bytes)
            else:
                data_dict = json.loads(data_bytes.decode('utf-8'))
            
            return cls.from_dict(data_dict)
        except Exception as e:
            logger.error(f"数据包反序列化失败: {e}")
            return None
    
    def compress(self) -> bytes:
        """压缩数据包"""
        try:
            serialized_data = self.serialize()
            return gzip.compress(serialized_data)
        except Exception as e:
            logger.error(f"数据包压缩失败: {e}")
            return b""
    
    @classmethod
    def decompress(cls, compressed_data: bytes, format_type: RockXQlibDataFormat = RockXQlibDataFormat.JSON) -> 'RockXQlibDataPacket':
        """解压缩数据包"""
        try:
            decompressed_data = gzip.decompress(compressed_data)
            return cls.deserialize(decompressed_data, format_type)
        except Exception as e:
            logger.error(f"数据包解压缩失败: {e}")
            return None

class RockXQlibDataValidator:
    """数据验证器"""
    
    def __init__(self):
        self.validation_rules = {}
        self.custom_validators = {}
    
    def add_validation_rule(self, data_type: str, rule: Callable[[Any], bool]):
        """添加验证规则"""
        if data_type not in self.validation_rules:
            self.validation_rules[data_type] = []
        self.validation_rules[data_type].append(rule)
    
    def add_custom_validator(self, name: str, validator: Callable[[RockXQlibDataPacket], bool]):
        """添加自定义验证器"""
        self.custom_validators[name] = validator
    
    def validate(self, data_packet: RockXQlibDataPacket) -> bool:
        """验证数据包"""
        try:
            # 基础验证
            if data_packet.data is None:
                return False
            
            # 类型验证
            data_type = type(data_packet.data).__name__
            if data_type in self.validation_rules:
                for rule in self.validation_rules[data_type]:
                    if not rule(data_packet.data):
                        return False
            
            # 自定义验证
            for validator in self.custom_validators.values():
                if not validator(data_packet):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"数据验证失败: {e}")
            return False

class RockXQlibDataTransformer:
    """数据转换器"""
    
    def __init__(self):
        self.transformers = {}
        self.custom_transformers = {}
    
    def add_transformer(self, from_format: RockXQlibDataFormat, to_format: RockXQlibDataFormat, 
                       transformer: Callable[[Any], Any]):
        """添加转换器"""
        key = (from_format, to_format)
        if key not in self.transformers:
            self.transformers[key] = []
        self.transformers[key].append(transformer)
    
    def add_custom_transformer(self, name: str, transformer: Callable[[RockXQlibDataPacket], RockXQlibDataPacket]):
        """添加自定义转换器"""
        self.custom_transformers[name] = transformer
    
    def transform(self, data_packet: RockXQlibDataPacket, target_format: RockXQlibDataFormat) -> RockXQlibDataPacket:
        """转换数据包"""
        try:
            if data_packet.format_type == target_format:
                return data_packet
            
            # 查找转换器
            key = (data_packet.format_type, target_format)
            if key in self.transformers:
                transformed_data = data_packet.data
                for transformer in self.transformers[key]:
                    transformed_data = transformer(transformed_data)
                
                # 创建新的数据包
                new_metadata = RockXQlibDataMetadata(
                    data_id=data_packet.data_id,
                    data_type=type(transformed_data).__name__,
                    format=target_format,
                    size_bytes=0,  # 将在构造函数中计算
                    quality=data_packet.metadata.quality,
                    source=data_packet.metadata.source,
                    timestamp=time.time(),
                    version=data_packet.version,
                    tags=data_packet.metadata.tags.copy(),
                    description=f"Transformed from {data_packet.format_type.value}",
                    schema=data_packet.metadata.schema.copy()
                )
                
                return RockXQlibDataPacket(transformed_data, new_metadata, target_format)
            else:
                logger.warning(f"未找到从 {data_packet.format_type.value} 到 {target_format.value} 的转换器")
                return data_packet
                
        except Exception as e:
            logger.error(f"数据转换失败: {e}")
            return data_packet

class RockXQlibDataStream:
    """数据流"""
    
    def __init__(self, stream_id: str, stream_type: str):
        self.stream_id = stream_id
        self.stream_type = stream_type
        self.data_queue = queue.Queue()
        self.subscribers = []
        self.is_active = False
        self.thread = None
        self.lock = threading.Lock()
    
    def add_data(self, data_packet: RockXQlibDataPacket):
        """添加数据到流"""
        try:
            with self.lock:
                self.data_queue.put(data_packet)
                # 通知订阅者
                for callback in self.subscribers:
                    try:
                        callback(data_packet)
                    except Exception as e:
                        logger.error(f"通知订阅者失败: {e}")
        except Exception as e:
            logger.error(f"添加数据到流失败: {e}")
    
    def get_data(self, timeout: float = 1.0) -> Optional[RockXQlibDataPacket]:
        """从流获取数据"""
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def subscribe(self, callback: Callable[[RockXQlibDataPacket], None]):
        """订阅数据流"""
        with self.lock:
            self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[RockXQlibDataPacket], None]):
        """取消订阅数据流"""
        with self.lock:
            if callback in self.subscribers:
                self.subscribers.remove(callback)
    
    def start(self):
        """启动数据流"""
        with self.lock:
            if not self.is_active:
                self.is_active = True
                self.thread = threading.Thread(target=self._process_data)
                self.thread.start()
    
    def stop(self):
        """停止数据流"""
        with self.lock:
            if self.is_active:
                self.is_active = False
                if self.thread:
                    self.thread.join()
    
    def _process_data(self):
        """处理数据（子类可重写）"""
        while self.is_active:
            try:
                data_packet = self.get_data(timeout=0.1)
                if data_packet:
                    # 处理数据
                    self._handle_data(data_packet)
            except Exception as e:
                logger.error(f"处理数据失败: {e}")
    
    def _handle_data(self, data_packet: RockXQlibDataPacket):
        """处理数据（子类可重写）"""
        pass

class RockXQlibDataFlowManager:
    """统一数据流管理器"""
    
    def __init__(self):
        self.data_streams = {}
        self.data_validator = RockXQlibDataValidator()
        self.data_transformer = RockXQlibDataTransformer()
        self.cache_manager = None
        self.lock = threading.Lock()
        
        # 初始化默认转换器
        self._initialize_default_transformers()
    
    def _initialize_default_transformers(self):
        """初始化默认转换器"""
        # JSON到字典的转换
        self.data_transformer.add_transformer(
            RockXQlibDataFormat.JSON, RockXQlibDataFormat.PICKLE,
            lambda x: x  # JSON数据可以直接用于pickle
        )
        
        # 字典到JSON的转换
        self.data_transformer.add_transformer(
            RockXQlibDataFormat.PICKLE, RockXQlibDataFormat.JSON,
            lambda x: x  # 字典数据可以直接用于JSON
        )
    
    def create_stream(self, stream_id: str, stream_type: str) -> RockXQlibDataStream:
        """创建数据流"""
        try:
            with self.lock:
                if stream_id in self.data_streams:
                    logger.warning(f"数据流 {stream_id} 已存在")
                    return self.data_streams[stream_id]
                
                stream = RockXQlibDataStream(stream_id, stream_type)
                self.data_streams[stream_id] = stream
                logger.info(f"数据流 {stream_id} 创建成功")
                return stream
        except Exception as e:
            logger.error(f"创建数据流失败: {e}")
            return None
    
    def get_stream(self, stream_id: str) -> Optional[RockXQlibDataStream]:
        """获取数据流"""
        with self.lock:
            return self.data_streams.get(stream_id)
    
    def remove_stream(self, stream_id: str) -> bool:
        """移除数据流"""
        try:
            with self.lock:
                if stream_id in self.data_streams:
                    stream = self.data_streams[stream_id]
                    stream.stop()
                    del self.data_streams[stream_id]
                    logger.info(f"数据流 {stream_id} 移除成功")
                    return True
                return False
        except Exception as e:
            logger.error(f"移除数据流失败: {e}")
            return False
    
    def validate_data(self, data_packet: RockXQlibDataPacket) -> bool:
        """验证数据"""
        return self.data_validator.validate(data_packet)
    
    def transform_data(self, data_packet: RockXQlibDataPacket, 
                      target_format: RockXQlibDataFormat) -> RockXQlibDataPacket:
        """转换数据"""
        return self.data_transformer.transform(data_packet, target_format)
    
    def add_validation_rule(self, data_type: str, rule: Callable[[Any], bool]):
        """添加验证规则"""
        self.data_validator.add_validation_rule(data_type, rule)
    
    def add_custom_validator(self, name: str, validator: Callable[[RockXQlibDataPacket], bool]):
        """添加自定义验证器"""
        self.data_validator.add_custom_validator(name, validator)
    
    def add_transformer(self, from_format: RockXQlibDataFormat, to_format: RockXQlibDataFormat, 
                       transformer: Callable[[Any], Any]):
        """添加转换器"""
        self.data_transformer.add_transformer(from_format, to_format, transformer)
    
    def add_custom_transformer(self, name: str, transformer: Callable[[RockXQlibDataPacket], RockXQlibDataPacket]):
        """添加自定义转换器"""
        self.data_transformer.add_custom_transformer(name, transformer)
    
    def get_stream_info(self) -> Dict[str, Any]:
        """获取数据流信息"""
        with self.lock:
            return {
                stream_id: {
                    'stream_type': stream.stream_type,
                    'is_active': stream.is_active,
                    'queue_size': stream.data_queue.qsize(),
                    'subscriber_count': len(stream.subscribers)
                }
                for stream_id, stream in self.data_streams.items()
            }
    
    def cleanup(self):
        """清理资源"""
        try:
            with self.lock:
                for stream in self.data_streams.values():
                    stream.stop()
                self.data_streams.clear()
            logger.info("数据流管理器清理完成")
        except Exception as e:
            logger.error(f"数据流管理器清理失败: {e}")
