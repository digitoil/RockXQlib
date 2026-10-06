#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存和性能监控工具
防止Qlib运行时的死机问题
"""

import os
import sys
import time
import psutil
import threading
import logging
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, 
                 memory_threshold_mb: int = 2048,  # 2GB内存阈值
                 cpu_threshold: float = 80.0,      # 80% CPU阈值
                 check_interval: float = 1.0):     # 1秒检查间隔
        self.memory_threshold = memory_threshold_mb * 1024 * 1024  # 转换为字节
        self.cpu_threshold = cpu_threshold
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread = None
        self.callbacks = []
        self.alert_count = 0
        self.max_alerts = 5  # 最大警告次数
        
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加监控回调函数"""
        self.callbacks.append(callback)
    
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.alert_count = 0
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("内存监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("内存监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 获取系统信息
                memory_info = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=0.1)
                process = psutil.Process()
                process_memory = process.memory_info().rss
                
                # 检查阈值
                alerts = []
                
                if memory_info.percent > 90:
                    alerts.append(f"系统内存使用率过高: {memory_info.percent:.1f}%")
                
                if cpu_percent > self.cpu_threshold:
                    alerts.append(f"CPU使用率过高: {cpu_percent:.1f}%")
                
                if process_memory > self.memory_threshold:
                    alerts.append(f"进程内存使用过大: {process_memory / 1024 / 1024:.1f}MB")
                
                # 如果有警告且未超过最大警告次数
                if alerts and self.alert_count < self.max_alerts:
                    self.alert_count += 1
                    alert_info = {
                        'timestamp': time.time(),
                        'alerts': alerts,
                        'memory_percent': memory_info.percent,
                        'memory_used_mb': memory_info.used / 1024 / 1024,
                        'cpu_percent': cpu_percent,
                        'process_memory_mb': process_memory / 1024 / 1024,
                        'alert_count': self.alert_count
                    }
                    
                    # 调用回调函数
                    for callback in self.callbacks:
                        try:
                            callback(alert_info)
                        except Exception as e:
                            logger.error(f"回调函数执行失败: {e}")
                    
                    # 记录警告
                    for alert in alerts:
                        logger.warning(alert)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(self.check_interval)
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前系统状态"""
        try:
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            process = psutil.Process()
            process_memory = process.memory_info().rss
            
            return {
                'timestamp': time.time(),
                'memory': {
                    'total_mb': memory_info.total / 1024 / 1024,
                    'available_mb': memory_info.available / 1024 / 1024,
                    'used_mb': memory_info.used / 1024 / 1024,
                    'percent': memory_info.percent
                },
                'cpu': {
                    'percent': cpu_percent
                },
                'process': {
                    'memory_mb': process_memory / 1024 / 1024,
                    'cpu_percent': process.cpu_percent()
                },
                'thresholds': {
                    'memory_threshold_mb': self.memory_threshold / 1024 / 1024,
                    'cpu_threshold': self.cpu_threshold
                }
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {}


class SafeQlibRunner:
    """安全的Qlib运行器"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
        self.qlib_available = False
        self.qlib_initialized = False
        
        # 设置监控回调
        self.monitor.add_callback(self._handle_alert)
        
        # 检查Qlib可用性
        self._check_qlib()
    
    def _check_qlib(self):
        """检查Qlib可用性"""
        try:
            import qlib
            self.qlib_available = True
            logger.info("Qlib可用")
        except ImportError as e:
            self.qlib_available = False
            logger.warning(f"Qlib不可用: {e}")
    
    def _handle_alert(self, alert_info: Dict[str, Any]):
        """处理监控警告"""
        logger.warning(f"系统资源警告: {alert_info['alerts']}")
        
        # 如果警告次数过多，可以考虑终止操作
        if alert_info['alert_count'] >= self.monitor.max_alerts:
            logger.error("警告次数过多，建议停止当前操作")
    
    @contextmanager
    def safe_operation(self, operation_name: str = "操作"):
        """安全操作上下文管理器"""
        logger.info(f"开始执行: {operation_name}")
        
        # 开始监控
        self.monitor.start_monitoring()
        
        try:
            # 记录开始状态
            start_status = self.monitor.get_current_status()
            logger.info(f"开始状态 - 内存: {start_status.get('memory', {}).get('percent', 0):.1f}%, "
                       f"CPU: {start_status.get('cpu', {}).get('percent', 0):.1f}%")
            
            yield
            
            # 记录结束状态
            end_status = self.monitor.get_current_status()
            logger.info(f"结束状态 - 内存: {end_status.get('memory', {}).get('percent', 0):.1f}%, "
                       f"CPU: {end_status.get('cpu', {}).get('percent', 0):.1f}%")
            
        except Exception as e:
            logger.error(f"操作失败: {e}")
            raise
        finally:
            # 停止监控
            self.monitor.stop_monitoring()
    
    def safe_init_qlib(self, provider_uri: str = None, region: str = "cn") -> bool:
        """安全初始化Qlib"""
        if not self.qlib_available:
            logger.error("Qlib不可用，无法初始化")
            return False
        
        try:
            with self.safe_operation("Qlib初始化"):
                import qlib
                
                # 检查是否已初始化
                if hasattr(qlib, 'is_initialized') and qlib.is_initialized():
                    self.qlib_initialized = True
                    logger.info("Qlib已经初始化")
                    return True
                
                # 设置默认配置
                if provider_uri is None:
                    provider_uri = "~/.qlib/qlib_data/cn_data"
                
                # 初始化Qlib
                qlib.init(
                    provider_uri=provider_uri,
                    region=region,
                    auto_mount=False,
                    mount_path=None,
                    kernel_api=False,
                    redis_host=None,
                    redis_port=None,
                    redis_task_db=None,
                    redis_freq_limit=None,
                    enable_exp_recorder=False  # 禁用实验记录器
                )
                
                self.qlib_initialized = True
                logger.info("Qlib初始化成功")
                return True
                
        except Exception as e:
            logger.error(f"Qlib初始化失败: {e}")
            return False
    
    def safe_get_data(self, instruments: str = "csi300", 
                     start_time: str = "2020-01-01", 
                     end_time: str = "2020-01-31",
                     fields: list = None) -> Optional[Any]:
        """安全获取数据"""
        if not self.qlib_initialized:
            logger.error("Qlib未初始化，无法获取数据")
            return None
        
        if fields is None:
            fields = ['$close', '$volume', '$amount']
        
        try:
            with self.safe_operation("数据获取"):
                from qlib.data import D
                
                data = D.features(
                    instruments=instruments,
                    start_time=start_time,
                    end_time=end_time,
                    fields=fields
                )
                
                logger.info(f"数据获取成功: {data.shape}")
                return data
                
        except Exception as e:
            logger.error(f"数据获取失败: {e}")
            return None
    
    def safe_create_model(self, model_class: str = "LGBModel", 
                         model_params: Dict[str, Any] = None) -> Optional[Any]:
        """安全创建模型"""
        if not self.qlib_initialized:
            logger.error("Qlib未初始化，无法创建模型")
            return None
        
        if model_params is None:
            model_params = {}
        
        try:
            with self.safe_operation("模型创建"):
                from qlib.utils import init_instance_by_config
                
                model_config = {
                    'class': model_class,
                    'module_path': 'qlib.contrib.model',
                    'kwargs': model_params
                }
                
                model = init_instance_by_config(model_config)
                logger.info(f"模型创建成功: {model_class}")
                return model
                
        except Exception as e:
            logger.error(f"模型创建失败: {e}")
            return None


def test_memory_monitor():
    """测试内存监控器"""
    print("测试内存监控器...")
    
    monitor = MemoryMonitor()
    
    # 添加测试回调
    def test_callback(alert_info):
        print(f"收到警告: {alert_info['alerts']}")
    
    monitor.add_callback(test_callback)
    
    # 开始监控
    monitor.start_monitoring()
    
    # 获取当前状态
    status = monitor.get_current_status()
    print(f"当前状态: {status}")
    
    # 监控5秒
    time.sleep(5)
    
    # 停止监控
    monitor.stop_monitoring()
    print("监控测试完成")


def test_safe_qlib_runner():
    """测试安全Qlib运行器"""
    print("测试安全Qlib运行器...")
    
    runner = SafeQlibRunner()
    
    # 测试初始化
    if runner.safe_init_qlib():
        print("Qlib初始化成功")
        
        # 测试数据获取
        data = runner.safe_get_data(
            instruments="csi300",
            start_time="2020-01-01",
            end_time="2020-01-31"
        )
        
        if data is not None:
            print(f"数据获取成功: {data.shape}")
        else:
            print("数据获取失败")
        
        # 测试模型创建
        model = runner.safe_create_model(
            model_class="LGBModel",
            model_params={'n_estimators': 10}
        )
        
        if model is not None:
            print("模型创建成功")
        else:
            print("模型创建失败")
    else:
        print("Qlib初始化失败")


if __name__ == "__main__":
    test_memory_monitor()
    test_safe_qlib_runner()
