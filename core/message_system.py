#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 消息系统
提供实时消息传递、事件驱动、异步处理
"""

import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import queue
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)

class RockXQlibMessageType(Enum):
    """消息类型枚举"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
    EVENT = "event"
    DATA = "data"
    COMMAND = "command"
    RESPONSE = "response"

class RockXQlibMessagePriority(Enum):
    """消息优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class RockXQlibMessage:
    """消息结构"""
    message_id: str
    topic: str
    message_type: RockXQlibMessageType
    priority: RockXQlibMessagePriority
    content: Any
    sender: str
    timestamp: float
    ttl: Optional[float] = None  # 生存时间（秒）
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'message_id': self.message_id,
            'topic': self.topic,
            'message_type': self.message_type.value,
            'priority': self.priority.value,
            'content': self.content,
            'sender': self.sender,
            'timestamp': self.timestamp,
            'ttl': self.ttl,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RockXQlibMessage':
        """从字典创建消息"""
        return cls(
            message_id=data['message_id'],
            topic=data['topic'],
            message_type=RockXQlibMessageType(data['message_type']),
            priority=RockXQlibMessagePriority(data['priority']),
            content=data['content'],
            sender=data['sender'],
            timestamp=data['timestamp'],
            ttl=data.get('ttl'),
            metadata=data.get('metadata', {})
        )

class RockXQlibMessageHandler:
    """消息处理器"""
    
    def __init__(self, handler_id: str, callback: Callable[[RockXQlibMessage], None], 
                 filter_func: Optional[Callable[[RockXQlibMessage], bool]] = None):
        self.handler_id = handler_id
        self.callback = callback
        self.filter_func = filter_func
        self.message_count = 0
        self.error_count = 0
        self.last_message_time = None
    
    def handle(self, message: RockXQlibMessage) -> bool:
        """处理消息"""
        try:
            # 检查过滤器
            if self.filter_func and not self.filter_func(message):
                return False
            
            # 处理消息
            self.callback(message)
            
            # 更新统计
            self.message_count += 1
            self.last_message_time = time.time()
            
            return True
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"消息处理器 {self.handler_id} 处理消息失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'handler_id': self.handler_id,
            'message_count': self.message_count,
            'error_count': self.error_count,
            'last_message_time': self.last_message_time,
            'error_rate': self.error_count / max(self.message_count, 1)
        }

class RockXQlibMessageBus:
    """消息总线"""
    
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.subscribers = defaultdict(list)  # topic -> [handlers]
        self.message_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.is_running = False
        self.thread = None
        self.lock = threading.Lock()
        self.message_history = []
        self.max_history_size = 1000
        
        # 统计信息
        self.total_messages = 0
        self.processed_messages = 0
        self.failed_messages = 0
        self.start_time = time.time()
    
    def start(self):
        """启动消息总线"""
        with self.lock:
            if not self.is_running:
                self.is_running = True
                self.thread = threading.Thread(target=self._process_messages)
                self.thread.daemon = True
                self.thread.start()
                logger.info("消息总线已启动")
    
    def stop(self):
        """停止消息总线"""
        with self.lock:
            if self.is_running:
                self.is_running = False
                if self.thread:
                    self.thread.join(timeout=5.0)
                logger.info("消息总线已停止")
    
    def subscribe(self, topic: str, callback: Callable[[RockXQlibMessage], None], 
                 handler_id: Optional[str] = None, 
                 filter_func: Optional[Callable[[RockXQlibMessage], bool]] = None) -> str:
        """订阅消息"""
        try:
            if handler_id is None:
                handler_id = f"handler_{uuid.uuid4().hex[:8]}"
            
            handler = RockXQlibMessageHandler(handler_id, callback, filter_func)
            
            with self.lock:
                self.subscribers[topic].append(handler)
            
            logger.info(f"订阅者 {handler_id} 已订阅主题 {topic}")
            return handler_id
            
        except Exception as e:
            logger.error(f"订阅消息失败: {e}")
            return None
    
    def unsubscribe(self, topic: str, handler_id: str) -> bool:
        """取消订阅"""
        try:
            with self.lock:
                if topic in self.subscribers:
                    self.subscribers[topic] = [
                        h for h in self.subscribers[topic] if h.handler_id != handler_id
                    ]
                    if not self.subscribers[topic]:
                        del self.subscribers[topic]
                    logger.info(f"订阅者 {handler_id} 已取消订阅主题 {topic}")
                    return True
            return False
            
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            return False
    
    def publish(self, topic: str, content: Any, message_type: RockXQlibMessageType = RockXQlibMessageType.INFO,
                priority: RockXQlibMessagePriority = RockXQlibMessagePriority.NORMAL,
                sender: str = "system", ttl: Optional[float] = None,
                metadata: Optional[Dict[str, Any]] = None) -> str:
        """发布消息"""
        try:
            message_id = str(uuid.uuid4())
            message = RockXQlibMessage(
                message_id=message_id,
                topic=topic,
                message_type=message_type,
                priority=priority,
                content=content,
                sender=sender,
                timestamp=time.time(),
                ttl=ttl,
                metadata=metadata or {}
            )
            
            # 添加到队列
            priority_value = -priority.value  # 负数，因为PriorityQueue是最小堆
            self.message_queue.put((priority_value, time.time(), message))
            
            # 更新统计
            self.total_messages += 1
            
            logger.debug(f"消息 {message_id} 已发布到主题 {topic}")
            return message_id
            
        except Exception as e:
            logger.error(f"发布消息失败: {e}")
            return None
    
    def send_event(self, event_type: str, event_data: Any, sender: str = "system") -> str:
        """发送事件"""
        return self.publish(
            topic=f"event.{event_type}",
            content=event_data,
            message_type=RockXQlibMessageType.EVENT,
            sender=sender
        )
    
    def send_command(self, command: str, command_data: Any, sender: str = "system") -> str:
        """发送命令"""
        return self.publish(
            topic=f"command.{command}",
            content=command_data,
            message_type=RockXQlibMessageType.COMMAND,
            priority=RockXQlibMessagePriority.HIGH,
            sender=sender
        )
    
    def _process_messages(self):
        """处理消息"""
        while self.is_running:
            try:
                # 获取消息
                priority, timestamp, message = self.message_queue.get(timeout=1.0)
                
                # 检查消息是否过期
                if message.is_expired():
                    logger.debug(f"消息 {message.message_id} 已过期")
                    continue
                
                # 分发消息
                self._distribute_message(message)
                
                # 更新统计
                self.processed_messages += 1
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                self.failed_messages += 1
    
    def _distribute_message(self, message: RockXQlibMessage):
        """分发消息"""
        try:
            # 添加到历史记录
            self._add_to_history(message)
            
            # 查找订阅者
            handlers = []
            with self.lock:
                # 精确匹配
                if message.topic in self.subscribers:
                    handlers.extend(self.subscribers[message.topic])
                
                # 通配符匹配
                for topic_pattern, topic_handlers in self.subscribers.items():
                    if self._match_topic(message.topic, topic_pattern):
                        handlers.extend(topic_handlers)
            
            # 处理消息
            for handler in handlers:
                try:
                    handler.handle(message)
                except Exception as e:
                    logger.error(f"处理器 {handler.handler_id} 处理消息失败: {e}")
                    self.failed_messages += 1
                    
        except Exception as e:
            logger.error(f"分发消息失败: {e}")
            self.failed_messages += 1
    
    def _match_topic(self, topic: str, pattern: str) -> bool:
        """匹配主题模式"""
        if pattern == "*":
            return True
        elif pattern.endswith("*"):
            return topic.startswith(pattern[:-1])
        elif pattern.startswith("*"):
            return topic.endswith(pattern[1:])
        else:
            return topic == pattern
    
    def _add_to_history(self, message: RockXQlibMessage):
        """添加到历史记录"""
        with self.lock:
            self.message_history.append(message)
            if len(self.message_history) > self.max_history_size:
                self.message_history.pop(0)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'is_running': self.is_running,
                'uptime': uptime,
                'total_messages': self.total_messages,
                'processed_messages': self.processed_messages,
                'failed_messages': self.failed_messages,
                'queue_size': self.message_queue.qsize(),
                'subscriber_count': sum(len(handlers) for handlers in self.subscribers.values()),
                'topic_count': len(self.subscribers),
                'message_rate': self.total_messages / max(uptime, 1),
                'error_rate': self.failed_messages / max(self.total_messages, 1)
            }
    
    def get_message_history(self, limit: int = 100) -> List[RockXQlibMessage]:
        """获取消息历史"""
        with self.lock:
            return self.message_history[-limit:]
    
    def get_subscriber_stats(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取订阅者统计"""
        with self.lock:
            result = {}
            for topic, handlers in self.subscribers.items():
                result[topic] = [handler.get_stats() for handler in handlers]
            return result

class RockXQlibEventSystem:
    """事件系统"""
    
    def __init__(self):
        self.event_handlers = defaultdict(list)  # event_type -> [handlers]
        self.event_history = []
        self.max_history_size = 1000
        self.lock = threading.Lock()
        
        # 统计信息
        self.total_events = 0
        self.processed_events = 0
        self.failed_events = 0
        self.start_time = time.time()
    
    def register_handler(self, event_type: str, handler: Callable[[str, Any], None], 
                        handler_id: Optional[str] = None) -> str:
        """注册事件处理器"""
        try:
            if handler_id is None:
                handler_id = f"event_handler_{uuid.uuid4().hex[:8]}"
            
            with self.lock:
                self.event_handlers[event_type].append({
                    'id': handler_id,
                    'handler': handler,
                    'call_count': 0,
                    'error_count': 0
                })
            
            logger.info(f"事件处理器 {handler_id} 已注册事件类型 {event_type}")
            return handler_id
            
        except Exception as e:
            logger.error(f"注册事件处理器失败: {e}")
            return None
    
    def unregister_handler(self, event_type: str, handler_id: str) -> bool:
        """取消注册事件处理器"""
        try:
            with self.lock:
                if event_type in self.event_handlers:
                    self.event_handlers[event_type] = [
                        h for h in self.event_handlers[event_type] if h['id'] != handler_id
                    ]
                    if not self.event_handlers[event_type]:
                        del self.event_handlers[event_type]
                    logger.info(f"事件处理器 {handler_id} 已取消注册事件类型 {event_type}")
                    return True
            return False
            
        except Exception as e:
            logger.error(f"取消注册事件处理器失败: {e}")
            return False
    
    def emit_event(self, event_type: str, event_data: Any, sender: str = "system") -> bool:
        """触发事件"""
        try:
            event_id = str(uuid.uuid4())
            event_info = {
                'event_id': event_id,
                'event_type': event_type,
                'event_data': event_data,
                'sender': sender,
                'timestamp': time.time()
            }
            
            # 添加到历史记录
            with self.lock:
                self.event_history.append(event_info)
                if len(self.event_history) > self.max_history_size:
                    self.event_history.pop(0)
            
            # 更新统计
            self.total_events += 1
            
            # 处理事件
            self._process_event(event_type, event_data, event_id)
            
            logger.debug(f"事件 {event_id} 已触发: {event_type}")
            return True
            
        except Exception as e:
            logger.error(f"触发事件失败: {e}")
            self.failed_events += 1
            return False
    
    def _process_event(self, event_type: str, event_data: Any, event_id: str):
        """处理事件"""
        try:
            handlers = []
            with self.lock:
                if event_type in self.event_handlers:
                    handlers = self.event_handlers[event_type].copy()
            
            # 调用处理器
            for handler_info in handlers:
                try:
                    handler_info['handler'](event_type, event_data)
                    handler_info['call_count'] += 1
                    self.processed_events += 1
                except Exception as e:
                    handler_info['error_count'] += 1
                    logger.error(f"事件处理器 {handler_info['id']} 处理事件失败: {e}")
                    self.failed_events += 1
                    
        except Exception as e:
            logger.error(f"处理事件失败: {e}")
            self.failed_events += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'uptime': uptime,
                'total_events': self.total_events,
                'processed_events': self.processed_events,
                'failed_events': self.failed_events,
                'event_type_count': len(self.event_handlers),
                'total_handlers': sum(len(handlers) for handlers in self.event_handlers.values()),
                'event_rate': self.total_events / max(uptime, 1),
                'error_rate': self.failed_events / max(self.total_events, 1)
            }
    
    def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取事件历史"""
        with self.lock:
            return self.event_history[-limit:]
    
    def get_handler_stats(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取处理器统计"""
        with self.lock:
            result = {}
            for event_type, handlers in self.event_handlers.items():
                result[event_type] = [
                    {
                        'id': h['id'],
                        'call_count': h['call_count'],
                        'error_count': h['error_count'],
                        'error_rate': h['error_count'] / max(h['call_count'], 1)
                    }
                    for h in handlers
                ]
            return result
