#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 数据节点
实现各种数据获取、处理、存储节点，与Qlib无缝集成
"""

import time
import logging
from typing import Dict, Any, Optional, List, Union
import pandas as pd
import numpy as np
import warnings

# Qlib imports
try:
    import qlib
    from qlib.data import D
    from qlib.data.dataset import DatasetH
    from qlib.contrib.data.handler import Alpha158, Alpha360
    from qlib.contrib.data.handler import Alpha158vwap, Alpha360vwap
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.data.dataset.loader import QlibDataLoader
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    from qlib.constant import REG_CN, REG_US
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False
    warnings.warn("Qlib not available, some features will be limited")

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from base_node import RockXQlibBaseNode, RockXQlibDataType

logger = logging.getLogger(__name__)

class RockXQlibDataNode(RockXQlibBaseNode):
    """基础数据节点 - 与Qlib D接口集成"""
    
    def __init__(self):
        super().__init__()
        self.set_name("Qlib数据节点")
        self.set_color(100, 150, 200)
        
        # 添加端口
        self.add_output_port("market_data", RockXQlibDataType.DATA_FRAME, "市场数据")
        self.add_output_port("features", RockXQlibDataType.DATA_FRAME, "特征数据")
        self.add_output_port("handler", RockXQlibDataType.HANDLER, "数据处理器")
        
        # 添加属性
        self.add_text_input("instruments", "股票池", "csi300")
        self.add_text_input("start_time", "开始时间", "2020-01-01")
        self.add_text_input("end_time", "结束时间", "2023-12-31")
        self.add_text_input("fields", "数据字段", "open,high,low,close,volume")
        self.add_text_input("freq", "数据频率", "day")
        self.add_checkbox("use_qlib", "使用Qlib", "使用Qlib数据接口", True)
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Any:
        """执行数据获取逻辑"""
        try:
            if not QLIB_AVAILABLE:
                logger.warning("Qlib不可用，使用模拟数据")
                return self._generate_mock_data()
            
            instruments = self.get_rockx_property("instruments", "csi300")
            start_time = self.get_rockx_property("start_time", "2020-01-01")
            end_time = self.get_rockx_property("end_time", "2023-12-31")
            fields = self.get_rockx_property("fields", "open,high,low,close,volume")
            freq = self.get_rockx_property("freq", "day")
            use_qlib = self.get_rockx_property("use_qlib", True)
            
            if use_qlib:
                # 使用Qlib D接口获取数据
                field_list = [f.strip() for f in fields.split(',')]
                
                # 获取市场数据
                market_data = D.features(
                    instruments=instruments,
                    fields=field_list,
                    start_time=start_time,
                    end_time=end_time,
                    freq=freq
                )
                
                logger.info(f"通过Qlib获取了 {len(market_data)} 条数据")
                
                return {
                    'market_data': market_data,
                    'features': market_data,
                    'handler': None
                }
            else:
                return self._generate_mock_data()
                
        except Exception as e:
            logger.error(f"数据获取失败: {e}")
            return self._generate_mock_data()
    
    def _generate_mock_data(self) -> Dict[str, Any]:
        """生成模拟数据"""
        start_time = self.get_rockx_property("start_time", "2020-01-01")
        end_time = self.get_rockx_property("end_time", "2023-12-31")
        fields = self.get_rockx_property("fields", "open,high,low,close,volume")
        
        dates = pd.date_range(start_time, end_time, freq='D')
        n_days = len(dates)
        
        # 生成模拟价格数据
        base_price = 100.0
        price_changes = np.random.randn(n_days) * 0.02
        prices = base_price * np.exp(np.cumsum(price_changes))
        
        # 创建OHLCV数据
        data = pd.DataFrame({
            'open': prices * (1 + np.random.randn(n_days) * 0.01),
            'high': prices * (1 + np.abs(np.random.randn(n_days)) * 0.02),
            'low': prices * (1 - np.abs(np.random.randn(n_days)) * 0.02),
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, n_days)
        }, index=dates)
        
        # 确保high >= max(open, close), low <= min(open, close)
        data['high'] = np.maximum(data['high'], np.maximum(data['open'], data['close']))
        data['low'] = np.minimum(data['low'], np.minimum(data['open'], data['close']))
        
        field_list = [f.strip() for f in fields.split(',')]
        features = data[field_list] if field_list else data
        
        return {
            'market_data': data,
            'features': features,
            'handler': None
        }

class RockXQlibAlphaNode(RockXQlibBaseNode):
    """Alpha因子数据节点 - 基于Qlib Alpha158/Alpha360"""
    
    def __init__(self):
        super().__init__()
        self.set_name("Alpha因子节点")
        self.set_color(150, 100, 200)
        
        # 添加端口
        self.add_output_port("dataset", RockXQlibDataType.DATASET, "数据集")
        self.add_output_port("handler", RockXQlibDataType.HANDLER, "数据处理器")
        self.add_output_port("features", RockXQlibDataType.DATA_FRAME, "特征数据")
        self.add_output_port("labels", RockXQlibDataType.DATA_FRAME, "标签数据")
        
        # 添加属性
        self.add_combo_menu("alpha_type", "Alpha类型", ["Alpha158", "Alpha360", "Alpha158vwap", "Alpha360vwap"], "Alpha158")
        self.add_text_input("instruments", "股票池", "csi300")
        self.add_text_input("start_time", "开始时间", "2008-01-01")
        self.add_text_input("end_time", "结束时间", "2020-08-01")
        self.add_text_input("fit_start_time", "训练开始时间", "2008-01-01")
        self.add_text_input("fit_end_time", "训练结束时间", "2014-12-31")
        self.add_text_input("freq", "数据频率", "day")
        self.add_checkbox("use_qlib", "使用Qlib", "使用Qlib Alpha处理器", True)
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Any:
        """执行Alpha因子计算"""
        try:
            if not QLIB_AVAILABLE:
                logger.warning("Qlib不可用，使用模拟Alpha数据")
                return self._generate_mock_alpha_data()
            
            alpha_type = self.get_rockx_property("alpha_type", "Alpha158")
            instruments = self.get_rockx_property("instruments", "csi300")
            start_time = self.get_rockx_property("start_time", "2008-01-01")
            end_time = self.get_rockx_property("end_time", "2020-08-01")
            fit_start_time = self.get_rockx_property("fit_start_time", "2008-01-01")
            fit_end_time = self.get_rockx_property("fit_end_time", "2014-12-31")
            freq = self.get_rockx_property("freq", "day")
            use_qlib = self.get_rockx_property("use_qlib", True)
            
            if use_qlib:
                # 创建Alpha处理器
                alpha_class = {
                    "Alpha158": Alpha158,
                    "Alpha360": Alpha360,
                    "Alpha158vwap": Alpha158vwap,
                    "Alpha360vwap": Alpha360vwap
                }.get(alpha_type, Alpha158)
                
                handler = alpha_class(
                    instruments=instruments,
                    start_time=start_time,
                    end_time=end_time,
                    freq=freq,
                    fit_start_time=fit_start_time,
                    fit_end_time=fit_end_time
                )
                
                # 创建数据集
                dataset = DatasetH(handler=handler)
                
                # 准备数据
                data = dataset.prepare("train")
                
                # 分离特征和标签
                feature_cols = [col for col in data.columns if not col.startswith('LABEL')]
                label_cols = [col for col in data.columns if col.startswith('LABEL')]
                
                features = data[feature_cols] if feature_cols else data
                labels = data[label_cols] if label_cols else pd.DataFrame()
                
                logger.info(f"使用{alpha_type}生成了 {len(data)} 条数据，特征数: {len(feature_cols)}")
                
                return {
                    'dataset': dataset,
                    'handler': handler,
                    'features': features,
                    'labels': labels
                }
            else:
                return self._generate_mock_alpha_data()
                
        except Exception as e:
            logger.error(f"Alpha因子计算失败: {e}")
            return self._generate_mock_alpha_data()
    
    def _generate_mock_alpha_data(self) -> Dict[str, Any]:
        """生成模拟Alpha数据"""
        start_time = self.get_rockx_property("start_time", "2008-01-01")
        end_time = self.get_rockx_property("end_time", "2020-08-01")
        
        dates = pd.date_range(start_time, end_time, freq='D')
        n_days = len(dates)
        
        # 生成158个特征（模拟Alpha158）
        n_features = 158
        features = pd.DataFrame(
            np.random.randn(n_days, n_features),
            index=dates,
            columns=[f"ALPHA_{i:03d}" for i in range(n_features)]
        )
        
        # 生成标签（未来收益率）
        labels = pd.DataFrame(
            np.random.randn(n_days, 1),
            index=dates,
            columns=["LABEL0"]
        )
        
        return {
            'dataset': None,
            'handler': None,
            'features': features,
            'labels': labels
        }

class RockXQlibHighFreqNode(RockXQlibBaseNode):
    """高频数据节点 - 支持Tick数据和订单簿数据"""
    
    def __init__(self):
        super().__init__()
        self.set_name("高频数据节点")
        self.set_color(200, 100, 150)
        
        # 添加端口
        self.add_output_port("tick_data", RockXQlibDataType.DATA_FRAME, "Tick数据")
        self.add_output_port("orderbook_data", RockXQlibDataType.DATA_FRAME, "订单簿数据")
        self.add_output_port("features", RockXQlibDataType.DATA_FRAME, "特征数据")
        
        # 添加属性
        self.add_text_input("symbol", "股票代码", "AAPL")
        self.add_text_input("frequency", "数据频率", "1min")
        self.add_text_input("start_time", "开始时间", "2024-01-01 09:30:00")
        self.add_text_input("end_time", "结束时间", "2024-01-01 15:00:00")
        self.add_text_input("tick_fields", "Tick字段", "bid,ask,last,volume")
        self.add_checkbox("include_orderbook", "包含订单簿", "包含订单簿数据", False)
        self.add_checkbox("use_qlib", "使用Qlib", "使用Qlib高频数据", True)
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Any:
        """执行高频数据获取"""
        try:
            if not QLIB_AVAILABLE:
                logger.warning("Qlib不可用，使用模拟高频数据")
                return self._generate_mock_highfreq_data()
            
            symbol = self.get_rockx_property("symbol", "AAPL")
            frequency = self.get_rockx_property("frequency", "1min")
            start_time = self.get_rockx_property("start_time", "2024-01-01 09:30:00")
            end_time = self.get_rockx_property("end_time", "2024-01-01 15:00:00")
            tick_fields = self.get_rockx_property("tick_fields", "bid,ask,last,volume")
            include_orderbook = self.get_rockx_property("include_orderbook", False)
            use_qlib = self.get_rockx_property("use_qlib", True)
            
            if use_qlib:
                # 使用Qlib获取高频数据
                field_list = [f.strip() for f in tick_fields.split(',')]
                
                # 获取Tick数据
                tick_data = D.features(
                    instruments=[symbol],
                    fields=field_list,
                    start_time=start_time,
                    end_time=end_time,
                    freq=frequency
                )
                
                result = {
                    'tick_data': tick_data,
                    'features': tick_data,
                    'orderbook_data': pd.DataFrame()
                }
                
                # 获取订单簿数据
                if include_orderbook:
                    orderbook_data = self._get_orderbook_data(symbol, start_time, end_time, frequency)
                    result['orderbook_data'] = orderbook_data
                
                logger.info(f"获取了 {len(tick_data)} 条高频数据")
                
                return result
            else:
                return self._generate_mock_highfreq_data()
                
        except Exception as e:
            logger.error(f"高频数据获取失败: {e}")
            return self._generate_mock_highfreq_data()
    
    def _get_orderbook_data(self, symbol: str, start_time: str, end_time: str, frequency: str) -> pd.DataFrame:
        """获取订单簿数据"""
        try:
            # 这里应该实现真正的订单簿数据获取
            # 目前返回空DataFrame
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"订单簿数据获取失败: {e}")
            return pd.DataFrame()
    
    def _generate_mock_highfreq_data(self) -> Dict[str, Any]:
        """生成模拟高频数据"""
        symbol = self.get_rockx_property("symbol", "AAPL")
        frequency = self.get_rockx_property("frequency", "1min")
        start_time = self.get_rockx_property("start_time", "2024-01-01 09:30:00")
        end_time = self.get_rockx_property("end_time", "2024-01-01 15:00:00")
        tick_fields = self.get_rockx_property("tick_fields", "bid,ask,last,volume")
        include_orderbook = self.get_rockx_property("include_orderbook", False)
        
        # 生成时间序列
        if frequency == "1min":
            freq = "1T"
        elif frequency == "5min":
            freq = "5T"
        elif frequency == "1sec":
            freq = "1S"
        else:
            freq = "1T"
        
        timestamps = pd.date_range(start_time, end_time, freq=freq)
        
        # 生成Tick数据
        base_price = 100.0
        tick_data = pd.DataFrame({
            'bid': base_price + np.random.randn(len(timestamps)) * 0.1,
            'ask': base_price + np.random.randn(len(timestamps)) * 0.1 + 0.05,
            'last': base_price + np.random.randn(len(timestamps)) * 0.1,
            'volume': np.random.randint(100, 1000, len(timestamps))
        }, index=timestamps)
        
        # 确保bid < ask
        tick_data['ask'] = np.maximum(tick_data['ask'], tick_data['bid'] + 0.01)
        
        result = {
            'tick_data': tick_data,
            'features': tick_data,
            'orderbook_data': pd.DataFrame()
        }
        
        # 生成订单簿数据
        if include_orderbook:
            orderbook_data = self._generate_mock_orderbook_data(timestamps, base_price)
            result['orderbook_data'] = orderbook_data
        
        return result
    
    def _generate_mock_orderbook_data(self, timestamps: pd.DatetimeIndex, base_price: float) -> pd.DataFrame:
        """生成模拟订单簿数据"""
        orderbook_data = []
        for ts in timestamps:
            for level in range(1, 6):  # 5档行情
                orderbook_data.append({
                    'timestamp': ts,
                    'level': level,
                    'bid_price': base_price - level * 0.01 + np.random.randn() * 0.005,
                    'bid_size': np.random.randint(100, 1000),
                    'ask_price': base_price + level * 0.01 + np.random.randn() * 0.005,
                    'ask_size': np.random.randint(100, 1000)
                })
        
        return pd.DataFrame(orderbook_data)

class RockXQlibCustomDataNode(RockXQlibBaseNode):
    """自定义数据节点 - 支持多种数据源"""
    
    def __init__(self):
        super().__init__()
        self.set_name("自定义数据节点")
        self.set_color(200, 200, 100)
        
        # 添加端口
        self.add_output_port("market_data", RockXQlibDataType.DATA_FRAME, "市场数据")
        self.add_output_port("features", RockXQlibDataType.DATA_FRAME, "特征数据")
        self.add_output_port("custom_data", RockXQlibDataType.DATA_FRAME, "自定义数据")
        
        # 添加属性
        self.add_combo_menu("data_source", "数据源", ["csv", "api", "database", "qlib"], "csv")
        self.add_text_input("file_path", "文件路径", "")
        self.add_text_input("api_url", "API地址", "")
        self.add_text_input("api_key", "API密钥", "")
        self.add_text_input("database_url", "数据库连接", "")
        self.add_text_input("custom_fields", "自定义字段", "")
        self.add_text_input("instruments", "股票池", "csi300")
        self.add_text_input("start_time", "开始时间", "2020-01-01")
        self.add_text_input("end_time", "结束时间", "2023-12-31")
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Any:
        """执行自定义数据获取"""
        try:
            data_source = self.get_rockx_property("data_source", "csv")
            file_path = self.get_rockx_property("file_path", "")
            api_url = self.get_rockx_property("api_url", "")
            api_key = self.get_rockx_property("api_key", "")
            database_url = self.get_rockx_property("database_url", "")
            custom_fields = self.get_rockx_property("custom_fields", "")
            instruments = self.get_rockx_property("instruments", "csi300")
            start_time = self.get_rockx_property("start_time", "2020-01-01")
            end_time = self.get_rockx_property("end_time", "2023-12-31")
            
            if data_source == "csv" and file_path:
                # 从CSV文件读取
                data = pd.read_csv(file_path)
                if 'datetime' in data.columns:
                    data['datetime'] = pd.to_datetime(data['datetime'])
                    data = data.set_index('datetime')
            elif data_source == "api" and api_url:
                # 从API获取数据
                data = self._fetch_from_api(api_url, api_key)
            elif data_source == "database" and database_url:
                # 从数据库获取数据
                data = self._fetch_from_database(database_url, instruments, start_time, end_time)
            elif data_source == "qlib" and QLIB_AVAILABLE:
                # 使用Qlib获取数据
                data = D.features(
                    instruments=instruments,
                    fields=["open", "high", "low", "close", "volume"],
                    start_time=start_time,
                    end_time=end_time
                )
            else:
                # 使用默认模拟数据
                data = self._generate_mock_data()
            
            # 处理自定义字段
            if custom_fields:
                field_list = [f.strip() for f in custom_fields.split(',')]
                available_fields = [f for f in field_list if f in data.columns]
                if available_fields:
                    features = data[available_fields]
                else:
                    features = data
            else:
                features = data
            
            logger.info(f"从 {data_source} 获取了 {len(data)} 条自定义数据")
            
            return {
                'market_data': data,
                'features': features,
                'custom_data': data
            }
            
        except Exception as e:
            logger.error(f"自定义数据获取失败: {e}")
            return self._generate_mock_data()
    
    def _fetch_from_api(self, api_url: str, api_key: str = "") -> pd.DataFrame:
        """从API获取数据"""
        try:
            import requests
            
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict) and 'data' in data:
                return pd.DataFrame(data['data'])
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"API数据获取失败: {e}")
            return pd.DataFrame()
    
    def _fetch_from_database(self, database_url: str, instruments: str, start_time: str, end_time: str) -> pd.DataFrame:
        """从数据库获取数据"""
        try:
            # 这里应该实现真正的数据库查询
            # 目前返回空DataFrame
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"数据库数据获取失败: {e}")
            return pd.DataFrame()
    
    def _generate_mock_data(self) -> pd.DataFrame:
        """生成模拟数据"""
        start_time = self.get_rockx_property("start_time", "2020-01-01")
        end_time = self.get_rockx_property("end_time", "2023-12-31")
        
        dates = pd.date_range(start_time, end_time, freq='D')
        n_days = len(dates)
        
        # 生成模拟价格数据
        base_price = 100.0
        price_changes = np.random.randn(n_days) * 0.02
        prices = base_price * np.exp(np.cumsum(price_changes))
        
        data = pd.DataFrame({
            'open': prices * (1 + np.random.randn(n_days) * 0.01),
            'high': prices * (1 + np.abs(np.random.randn(n_days)) * 0.02),
            'low': prices * (1 - np.abs(np.random.randn(n_days)) * 0.02),
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, n_days)
        }, index=dates)
        
        return data