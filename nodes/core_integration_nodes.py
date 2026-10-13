#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心集成节点
集成数据流、消息系统、缓存管理、实验管理等核心功能
"""

import os
import sys
import logging
import json
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Union

# 添加路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# NodeGraphQt 是硬依赖，必须显式失败；核心集成组件各自独立降级。
# 原实现共用一个 try，任一导入失败就把 BaseNode 换成空壳占位类，
# 导致节点失去 add_input/add_output 等全部端口 API。
from NodeGraphQt import BaseNode
NODEGRAPH_AVAILABLE = True

try:
    from core.qlib_core_integration import qlib_core
except ImportError as e:
    print(f"qlib_core 不可用: {e}")
    qlib_core = None

try:
    from core.data_flow import RockXQlibDataFlowManager, RockXQlibDataPacket
    from core.message_system import RockXQlibMessageBus
    from core.qlib_cache_manager import QlibCacheManager
    from core.qlib_experiment_manager import QlibExperimentManager
    from core.qlib_parallel_executor import QlibParallelExecutor
except ImportError as e:
    print(f"核心集成组件不可用，相关节点将降级: {e}")
    RockXQlibDataFlowManager = None
    RockXQlibDataPacket = None
    RockXQlibMessageBus = None
    QlibCacheManager = None
    QlibExperimentManager = None
    QlibParallelExecutor = None

logger = logging.getLogger(__name__)

class QlibCoreBaseNode(BaseNode):
    """基于Qlib核心的基节点"""
    
    def __init__(self):
        super().__init__()
        self.qlib_core = qlib_core
        self._execution_result = None
        self._error_message = None
    
    def execute_qlib_operation(self, operation: str, **kwargs) -> Any:
        """执行Qlib操作"""
        try:
            if not self.qlib_core or not self.qlib_core.qlib_available:
                raise Exception("Qlib不可用")
            
            if operation == "initialize":
                return self.qlib_core.initialize_qlib(**kwargs)
            elif operation == "get_data":
                return self.qlib_core.get_qlib_data(**kwargs)
            elif operation == "create_dataset":
                return self.qlib_core.create_dataset(**kwargs)
            elif operation == "create_model":
                return self.qlib_core.create_model(**kwargs)
            elif operation == "create_strategy":
                return self.qlib_core.create_strategy(**kwargs)
            elif operation == "run_backtest":
                return self.qlib_core.run_backtest(**kwargs)
            else:
                raise Exception(f"未知的Qlib操作: {operation}")
                
        except Exception as e:
            logger.error(f"Qlib操作失败: {e}")
            self._error_message = str(e)
            return None
    
    def get_execution_result(self) -> Any:
        """获取执行结果"""
        return self._execution_result
    
    def get_error_message(self) -> Optional[str]:
        """获取错误信息"""
        return self._error_message

class DataFlowManagerNode(QlibCoreBaseNode):
    """数据流管理节点"""
    
    __identifier__ = 'core.data_flow_manager'
    NODE_NAME = '数据流管理'
    type_ = 'core.data_flow_manager'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('data_input')
        self.add_output('data_output')
        
        # 添加属性
        self.add_text_input('data_format', '数据格式', 'json')
        self.add_text_input('compression', '压缩方式', 'none')
        self.add_checkbox('enable_caching', '启用缓存', '启用缓存', True)
        self.add_text_input('cache_ttl', '缓存TTL(秒)', '3600')
        self.add_text_input('quality_threshold', '质量阈值', '0.8')
    
    def execute(self) -> bool:
        """执行数据流管理"""
        try:
            # 检查输入
            data_input = self.get_input('data_input')
            if data_input is None:
                raise Exception("输入数据为空")
            
            data_format = self.get_property('data_format')
            compression = self.get_property('compression')
            enable_caching = self.get_property('enable_caching')
            cache_ttl = int(self.get_property('cache_ttl'))
            quality_threshold = float(self.get_property('quality_threshold'))
            
            # 使用数据流管理器
            if RockXQlibDataFlowManager:
                data_flow_manager = RockXQlibDataFlowManager()
                
                # 创建数据包
                data_packet = data_flow_manager.create_data_packet(
                    data=data_input,
                    data_type="market_data",
                    format=data_format,
                    compression=compression,
                    quality_threshold=quality_threshold
                )
                
                # 处理数据流
                processed_packet = data_flow_manager.process_data_packet(
                    packet=data_packet,
                    enable_caching=enable_caching,
                    cache_ttl=cache_ttl
                )
                
                self._execution_result = {
                    'status': 'success',
                    'data_format': data_format,
                    'compression': compression,
                    'processed_data': processed_packet.data if processed_packet else data_input,
                    'metadata': processed_packet.metadata if processed_packet else {},
                    'quality_score': processed_packet.metadata.quality if processed_packet and processed_packet.metadata else 1.0
                }
                self.set_output('data_output', self._execution_result)
                logger.info("✅ 数据流管理完成")
                return True
            else:
                # 模拟数据流处理
                self._execution_result = {
                    'status': 'success',
                    'data_format': data_format,
                    'compression': compression,
                    'processed_data': data_input,
                    'metadata': {'quality': 1.0, 'size': len(str(data_input))},
                    'quality_score': 1.0,
                    'note': '使用模拟数据流处理'
                }
                self.set_output('data_output', self._execution_result)
                logger.info("✅ 模拟数据流管理完成")
                return True
                
        except Exception as e:
            logger.error(f"数据流管理节点执行失败: {e}")
            return False

class MessageBusNode(QlibCoreBaseNode):
    """消息总线节点"""
    
    __identifier__ = 'core.message_bus'
    NODE_NAME = '消息总线'
    type_ = 'core.message_bus'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('message_input')
        self.add_output('message_output')
        
        # 添加属性
        self.add_text_input('topic', '主题', 'default')
        self.add_text_input('message_type', '消息类型', 'info')
        self.add_text_input('priority', '优先级', 'normal')
        self.add_checkbox('enable_persistence', '启用持久化', '启用持久化', True)
        self.add_text_input('ttl', '生存时间(秒)', '3600')
    
    def execute(self) -> bool:
        """执行消息总线操作"""
        try:
            # 检查输入
            message_input = self.get_input('message_input')
            if message_input is None:
                raise Exception("输入消息为空")
            
            topic = self.get_property('topic')
            message_type = self.get_property('message_type')
            priority = self.get_property('priority')
            enable_persistence = self.get_property('enable_persistence')
            ttl = int(self.get_property('ttl'))
            
            # 使用消息总线
            if RockXQlibMessageBus:
                message_bus = RockXQlibMessageBus()
                
                # 发布消息
                message_id = message_bus.publish(
                    topic=topic,
                    message_type=message_type,
                    priority=priority,
                    content=message_input,
                    sender="DataFlowManagerNode",
                    ttl=ttl
                )
                
                # 订阅消息
                received_messages = message_bus.subscribe(topic, max_messages=10)
                
                self._execution_result = {
                    'status': 'success',
                    'topic': topic,
                    'message_type': message_type,
                    'message_id': message_id,
                    'published_content': message_input,
                    'received_messages': [msg.content for msg in received_messages],
                    'message_count': len(received_messages)
                }
                self.set_output('message_output', self._execution_result)
                logger.info(f"✅ 消息总线操作完成: {topic}")
                return True
            else:
                # 模拟消息总线操作
                self._execution_result = {
                    'status': 'success',
                    'topic': topic,
                    'message_type': message_type,
                    'message_id': f"mock_{topic}_{pd.Timestamp.now().timestamp()}",
                    'published_content': message_input,
                    'received_messages': [message_input],
                    'message_count': 1,
                    'note': '使用模拟消息总线'
                }
                self.set_output('message_output', self._execution_result)
                logger.info(f"✅ 模拟消息总线操作完成: {topic}")
                return True
                
        except Exception as e:
            logger.error(f"消息总线节点执行失败: {e}")
            return False

class CacheManagerNode(QlibCoreBaseNode):
    """缓存管理节点"""
    
    __identifier__ = 'core.cache_manager'
    NODE_NAME = '缓存管理'
    type_ = 'core.cache_manager'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('data_input')
        self.add_output('cached_output')
        
        # 添加属性
        self.add_text_input('cache_key', '缓存键', '')
        self.add_text_input('cache_ttl', '缓存TTL(秒)', '3600')
        self.add_text_input('cache_size', '缓存大小(MB)', '100')
        self.add_checkbox('enable_compression', '启用压缩', '启用压缩', True)
        self.add_text_input('eviction_policy', '淘汰策略', 'lru')
    
    def execute(self) -> bool:
        """执行缓存管理"""
        try:
            # 检查输入
            data_input = self.get_input('data_input')
            if data_input is None:
                raise Exception("输入数据为空")
            
            cache_key = self.get_property('cache_key') or f"cache_{pd.Timestamp.now().timestamp()}"
            cache_ttl = int(self.get_property('cache_ttl'))
            cache_size = int(self.get_property('cache_size'))
            enable_compression = self.get_property('enable_compression')
            eviction_policy = self.get_property('eviction_policy')
            
            # 使用缓存管理器
            if QlibCacheManager:
                cache_manager = QlibCacheManager(
                    max_size_mb=cache_size,
                    enable_compression=enable_compression,
                    eviction_policy=eviction_policy
                )
                
                # 存储到缓存
                cache_manager.set(cache_key, data_input, ttl=cache_ttl)
                
                # 从缓存获取
                cached_data = cache_manager.get(cache_key)
                
                # 获取缓存统计
                cache_stats = cache_manager.get_cache_stats()
                
                self._execution_result = {
                    'status': 'success',
                    'cache_key': cache_key,
                    'cached_data': cached_data,
                    'cache_stats': cache_stats,
                    'ttl': cache_ttl,
                    'compression_enabled': enable_compression
                }
                self.set_output('cached_output', self._execution_result)
                logger.info(f"✅ 缓存管理完成: {cache_key}")
                return True
            else:
                # 模拟缓存管理
                self._execution_result = {
                    'status': 'success',
                    'cache_key': cache_key,
                    'cached_data': data_input,
                    'cache_stats': {'size': len(str(data_input)), 'hits': 1, 'misses': 0},
                    'ttl': cache_ttl,
                    'compression_enabled': enable_compression,
                    'note': '使用模拟缓存管理'
                }
                self.set_output('cached_output', self._execution_result)
                logger.info(f"✅ 模拟缓存管理完成: {cache_key}")
                return True
                
        except Exception as e:
            logger.error(f"缓存管理节点执行失败: {e}")
            return False

class ExperimentManagerNode(QlibCoreBaseNode):
    """实验管理节点"""
    
    __identifier__ = 'core.experiment_manager'
    NODE_NAME = '实验管理'
    type_ = 'core.experiment_manager'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('experiment_data')
        self.add_output('experiment_result')
        
        # 添加属性
        self.add_text_input('experiment_name', '实验名称', 'default_experiment')
        self.add_text_input('experiment_type', '实验类型', 'backtest')
        self.add_checkbox('enable_logging', '启用日志', '启用日志', True)
        self.add_checkbox('enable_metrics', '启用指标', '启用指标', True)
        self.add_text_input('output_dir', '输出目录', './experiments/')
    
    def execute(self) -> bool:
        """把上游传来的真实指标写入实验目录。没有指标就失败，不填占位分数。"""
        try:
            experiment_data = self.get_input('experiment_data')
            experiment_name = self.get_property('experiment_name')
            experiment_type = self.get_property('experiment_type')
            output_dir = self.get_property('output_dir') or './experiments/'

            if QlibExperimentManager is None:
                self._error_message = "QlibExperimentManager 不可用，不会用模拟分数冒充实验记录"
                self._execution_result = {'status': 'failed', 'error': self._error_message}
                logger.error(self._error_message)
                return False

            metrics = None
            params = None
            if isinstance(experiment_data, dict):
                if isinstance(experiment_data.get('metrics'), dict):
                    metrics = experiment_data['metrics']
                params = experiment_data.get('params') or experiment_data.get('parameters')
            if not metrics:
                self._error_message = (
                    "没有可记录的指标。请把上游结果里的 metrics 接到本节点；"
                    "不会写入 accuracy=0.85 这类占位值。"
                )
                self._execution_result = {'status': 'failed', 'error': self._error_message}
                logger.error(self._error_message)
                return False

            manager = QlibExperimentManager(experiments_dir=output_dir)
            experiment_id = manager.create_experiment(
                experiment_name, {'description': experiment_type or ''})
            if not experiment_id:
                self._error_message = "创建实验失败"
                self._execution_result = {'status': 'failed', 'error': self._error_message}
                return False
            run_id = manager.start_run(experiment_id, experiment_name)
            if isinstance(params, dict) and params:
                manager.log_parameters(run_id, params)
            manager.log_metrics(run_id, metrics)
            manager.end_run(run_id)
            stored = manager.get_run(run_id) or {}

            self._execution_result = {
                'status': 'success',
                'experiment_name': experiment_name,
                'experiment_type': experiment_type,
                'experiment_id': experiment_id,
                'run_id': run_id,
                'experiment_results': stored,
                'output_dir': output_dir,
            }
            self.set_output('experiment_result', self._execution_result)
            logger.info("✅ 已记录实验 %s / %s", experiment_name, run_id)
            return True
        except Exception as e:
            logger.error(f"实验管理节点执行失败: {e}")
            self._error_message = str(e)
            self._execution_result = {'status': 'failed', 'error': self._error_message}
            return False

class ParallelExecutorNode(QlibCoreBaseNode):
    """并行执行器节点"""
    
    __identifier__ = 'core.parallel_executor'
    NODE_NAME = '并行执行器'
    type_ = 'core.parallel_executor'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('task_list')
        self.add_output('execution_result')
        
        # 添加属性
        self.add_text_input('max_workers', '最大工作线程', '4')
        self.add_text_input('execution_mode', '执行模式', 'parallel')
        self.add_checkbox('enable_progress', '启用进度显示', '启用进度显示', True)
        self.add_text_input('timeout', '超时时间(秒)', '300')
    
    def execute(self) -> bool:
        """执行并行任务"""
        try:
            # 检查输入
            task_list = self.get_input('task_list')
            if task_list is None:
                raise Exception("任务列表为空")
            
            max_workers = int(self.get_property('max_workers'))
            execution_mode = self.get_property('execution_mode')
            enable_progress = self.get_property('enable_progress')
            timeout = int(self.get_property('timeout'))
            
            # 使用并行执行器
            if QlibParallelExecutor:
                parallel_executor = QlibParallelExecutor(
                    max_workers=max_workers,
                    enable_progress=enable_progress,
                    timeout=timeout
                )
                
                # 执行任务
                if execution_mode == 'parallel':
                    results = parallel_executor.execute_parallel(task_list)
                else:
                    results = parallel_executor.execute_sequential(task_list)
                
                # 获取执行统计
                execution_stats = parallel_executor.get_execution_stats()
                
                self._execution_result = {
                    'status': 'success',
                    'execution_mode': execution_mode,
                    'max_workers': max_workers,
                    'results': results,
                    'execution_stats': execution_stats,
                    'task_count': len(task_list) if isinstance(task_list, list) else 1
                }
                self.set_output('execution_result', self._execution_result)
                logger.info(f"✅ 并行执行完成: {execution_mode}")
                return True
            else:
                # 模拟并行执行
                mock_results = [f"result_{i}" for i in range(len(task_list) if isinstance(task_list, list) else 1)]
                
                self._execution_result = {
                    'status': 'success',
                    'execution_mode': execution_mode,
                    'max_workers': max_workers,
                    'results': mock_results,
                    'execution_stats': {'total_time': 1.5, 'success_count': len(mock_results)},
                    'task_count': len(task_list) if isinstance(task_list, list) else 1,
                    'note': '使用模拟并行执行'
                }
                self.set_output('execution_result', self._execution_result)
                logger.info(f"✅ 模拟并行执行完成: {execution_mode}")
                return True
                
        except Exception as e:
            logger.error(f"并行执行器节点执行失败: {e}")
            return False

# 导出所有节点类
__all__ = [
    'QlibCoreBaseNode',
    'DataFlowManagerNode',
    'MessageBusNode',
    'CacheManagerNode',
    'ExperimentManagerNode',
    'ParallelExecutorNode'
]
