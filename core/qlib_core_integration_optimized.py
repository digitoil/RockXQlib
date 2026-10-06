#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能优化的Qlib核心集成模块
避免死机和卡机问题
"""

import os
import sys
import logging
import traceback
import time
import signal
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager

# 设置环境变量
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.0'
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_QLIB'] = '0.9.0'

logger = logging.getLogger(__name__)

@contextmanager
def timeout(seconds):
    """超时上下文管理器"""
    def signal_handler(signum, frame):
        raise TimeoutError(f"操作超时 ({seconds}秒)")
    
    # 设置信号处理器
    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # 恢复原来的信号处理器
        signal.signal(signal.SIGALRM, old_handler)
        signal.alarm(0)

class QlibCoreIntegrationOptimized:
    """性能优化的Qlib核心集成类"""
    
    def __init__(self):
        self.qlib_available = False
        self.qlib_initialized = False
        self._check_qlib_availability()
    
    def _check_qlib_availability(self):
        """检查Qlib可用性（带超时）"""
        try:
            with timeout(10):  # 10秒超时
                import qlib
                from qlib.data import D
                from qlib.data.dataset import DatasetH
                from qlib.contrib.data.handler import Alpha158, Alpha360
                from qlib.contrib.model import LinearModel, LGBModel
                from qlib.contrib.strategy import TopkDropoutStrategy
                from qlib.backtest import backtest
                from qlib.utils import init_instance_by_config
                
                self.qlib_available = True
                logger.info("✅ Qlib核心组件导入成功")
                
        except TimeoutError:
            self.qlib_available = False
            logger.warning("❌ Qlib核心组件导入超时")
        except ImportError as e:
            self.qlib_available = False
            logger.warning(f"❌ Qlib核心组件导入失败: {e}")
    
    def initialize_qlib(self, provider_uri: str = None, region: str = "cn", 
                       enable_exp_recorder: bool = True, timeout_seconds: int = 30) -> bool:
        """初始化Qlib（带超时）"""
        if not self.qlib_available:
            logger.error("Qlib不可用，无法初始化")
            return False
        
        try:
            with timeout(timeout_seconds):
                import qlib
                
                # 检查Qlib是否已初始化
                is_initialized = False
                try:
                    if hasattr(qlib, 'is_initialized'):
                        is_initialized = qlib.is_initialized()
                    else:
                        # 如果没有is_initialized方法，尝试导入D模块
                        from qlib.data import D
                        is_initialized = True
                except Exception:
                    is_initialized = False
                
                if not is_initialized:
                    # 设置默认数据路径（自动探测，避免写死不存在的目录）
                    if provider_uri is None:
                        try:
                            from .qlib_paths import get_default_provider_uri
                            provider_uri = get_default_provider_uri()
                        except ImportError:
                            try:
                                from qlib_paths import get_default_provider_uri
                                provider_uri = get_default_provider_uri()
                            except ImportError:
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
                        enable_exp_recorder=enable_exp_recorder
                    )
                    
                    # 验证初始化是否成功
                    try:
                        from qlib.data import D
                        self.qlib_initialized = True
                        logger.info(f"✅ Qlib初始化成功: {provider_uri}")
                        return True
                    except Exception as e:
                        logger.error(f"❌ Qlib初始化验证失败: {e}")
                        return False
                else:
                    self.qlib_initialized = True
                    logger.info("✅ Qlib已经初始化")
                    return True
                    
        except TimeoutError:
            logger.error(f"❌ Qlib初始化超时 ({timeout_seconds}秒)")
            return False
        except Exception as e:
            logger.error(f"❌ Qlib初始化失败: {e}")
            return False
    
    def get_qlib_data(self, instruments: str = "csi300", 
                     start_time: str = "2008-01-01", 
                     end_time: str = "2020-08-01",
                     fields: List[str] = None, 
                     timeout_seconds: int = 60) -> Optional[Any]:
        """获取Qlib数据（带超时）"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法获取数据")
            return None
        
        try:
            with timeout(timeout_seconds):
                from qlib.data import D
                
                if fields is None:
                    fields = ["$close", "$volume", "$amount"]
                
                data = D.features(
                    instruments=instruments,
                    fields=fields,
                    start_time=start_time,
                    end_time=end_time
                )
                
                logger.info(f"✅ 成功获取Qlib数据: {instruments}, {start_time} - {end_time}")
                return data
                
        except TimeoutError:
            logger.error(f"❌ 获取Qlib数据超时 ({timeout_seconds}秒)")
            return None
        except Exception as e:
            logger.error(f"❌ 获取Qlib数据失败: {e}")
            return None
    
    def create_dataset(self, handler_config: Dict[str, Any], 
                      segments: Dict[str, List[str]] = None,
                      timeout_seconds: int = 30) -> Optional[Any]:
        """创建Qlib数据集（带超时）"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法创建数据集")
            return None
        
        try:
            with timeout(timeout_seconds):
                from qlib.data.dataset import DatasetH
                from qlib.utils import init_instance_by_config
                
                # 确保handler_config包含module_path
                if 'module_path' not in handler_config:
                    handler_config['module_path'] = 'qlib.contrib.data.handler'
                
                # 创建数据处理器
                handler = init_instance_by_config(handler_config)
                
                # 设置默认分段
                if segments is None:
                    segments = {
                        "train": ["2008-01-01", "2014-12-31"],
                        "valid": ["2015-01-01", "2016-12-31"],
                        "test": ["2017-01-01", "2020-08-01"]
                    }
                
                # 创建数据集
                dataset = DatasetH(handler=handler, segments=segments)
                
                logger.info("✅ 成功创建Qlib数据集")
                return dataset
                
        except TimeoutError:
            logger.error(f"❌ 创建Qlib数据集超时 ({timeout_seconds}秒)")
            return None
        except Exception as e:
            logger.error(f"❌ 创建Qlib数据集失败: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any], 
                    timeout_seconds: int = 30) -> Optional[Any]:
        """创建Qlib模型（带超时）"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法创建模型")
            return None
        
        try:
            with timeout(timeout_seconds):
                from qlib.utils import init_instance_by_config
                
                # 确保model_config包含module_path
                if 'module_path' not in model_config:
                    model_config['module_path'] = 'qlib.contrib.model'
                
                model = init_instance_by_config(model_config)
                
                logger.info(f"✅ 成功创建Qlib模型: {model_config.get('class', 'Unknown')}")
                return model
                
        except TimeoutError:
            logger.error(f"❌ 创建Qlib模型超时 ({timeout_seconds}秒)")
            return None
        except Exception as e:
            logger.error(f"❌ 创建Qlib模型失败: {e}")
            return None
    
    def create_strategy(self, strategy_config: Dict[str, Any], 
                       timeout_seconds: int = 30) -> Optional[Any]:
        """创建Qlib策略（带超时）"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法创建策略")
            return None
        
        try:
            with timeout(timeout_seconds):
                from qlib.utils import init_instance_by_config
                
                # 确保strategy_config包含module_path
                if 'module_path' not in strategy_config:
                    strategy_config['module_path'] = 'qlib.contrib.strategy'
                
                strategy = init_instance_by_config(strategy_config)
                
                logger.info(f"✅ 成功创建Qlib策略: {strategy_config.get('class', 'Unknown')}")
                return strategy
                
        except TimeoutError:
            logger.error(f"❌ 创建Qlib策略超时 ({timeout_seconds}秒)")
            return None
        except Exception as e:
            logger.error(f"❌ 创建Qlib策略失败: {e}")
            return None
    
    def run_backtest(self, backtest_config: Dict[str, Any], 
                    timeout_seconds: int = 120) -> Optional[Any]:
        """运行Qlib回测（带超时）"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法运行回测")
            return None
        
        try:
            with timeout(timeout_seconds):
                from qlib.backtest import backtest
                
                # 运行回测
                result = backtest(**backtest_config)
                
                logger.info("✅ 成功运行Qlib回测")
                return result
                
        except TimeoutError:
            logger.error(f"❌ 运行Qlib回测超时 ({timeout_seconds}秒)")
            return None
        except Exception as e:
            logger.error(f"❌ 运行Qlib回测失败: {e}")
            return None

# 创建全局实例
qlib_core_optimized = QlibCoreIntegrationOptimized()
