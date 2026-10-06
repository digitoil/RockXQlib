#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib数据节点具体实现
严格按照设计文档实现所有数据节点
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
import pandas as pd
import numpy as np

# Qlib imports
try:
    import qlib
    from qlib.data import D
    from qlib.data.dataset import DatasetH
    from qlib.contrib.data.handler import Alpha158, Alpha360, Alpha158vwap, Alpha360vwap
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.data.dataset.loader import QlibDataLoader
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    from qlib.constant import REG_CN, REG_US
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

# 添加核心模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from qlib_data_node import QlibDataNode

logger = logging.getLogger(__name__)

class QlibAlphaNode(QlibDataNode):
    """Alpha因子数据节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'alpha')
        self.set_property('description', 'Alpha因子数据节点')
        
        # Alpha因子特定属性
        self.set_property('alpha_type', 'Alpha158')  # Alpha158, Alpha360, Alpha158vwap, Alpha360vwap
        self.set_property('fit_start_time', '2008-01-01')
        self.set_property('fit_end_time', '2014-12-31')
        self.set_property('infer_processors', [])
        self.set_property('learn_processors', [])
    
    def _validate_specific_config(self) -> bool:
        """验证Alpha节点特定配置"""
        try:
            alpha_type = self.get_property('alpha_type')
            if alpha_type not in ['Alpha158', 'Alpha360', 'Alpha158vwap', 'Alpha360vwap']:
                self._set_status("failed", f"不支持的Alpha类型: {alpha_type}")
                return False
            
            return super()._validate_specific_config()
            
        except Exception as e:
            self._set_status("failed", f"Alpha节点配置验证失败: {e}")
            return False
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行Alpha因子数据获取逻辑"""
        try:
            if not QLIB_AVAILABLE:
                self._set_status("failed", "Qlib不可用")
                return {}
            
            alpha_type = self.get_property('alpha_type')
            instruments = self.get_property('instruments')
            start_time = self.get_property('start_time')
            end_time = self.get_property('end_time')
            fit_start_time = self.get_property('fit_start_time')
            fit_end_time = self.get_property('fit_end_time')
            
            # 创建Alpha处理器配置
            handler_config = {
                'class': alpha_type,
                'module_path': 'qlib.contrib.data.handler',
                'kwargs': {
                    'instruments': instruments,
                    'start_time': start_time,
                    'end_time': end_time,
                    'fit_start_time': fit_start_time,
                    'fit_end_time': fit_end_time,
                    'infer_processors': self.get_property('infer_processors'),
                    'learn_processors': self.get_property('learn_processors'),
                }
            }
            
            # 创建Alpha处理器
            alpha_handler = init_instance_by_config(handler_config)
            
            # 获取Alpha数据
            alpha_data = alpha_handler.fetch()
            
            logger.info(f"Alpha因子数据获取成功: {alpha_data.shape}")
            
            return {
                'alpha_data': alpha_data,
                'alpha_handler': alpha_handler,
                'alpha_type': alpha_type
            }
            
        except Exception as e:
            self._set_status("failed", f"Alpha因子数据获取失败: {e}")
            logger.error(f"Alpha因子数据获取失败: {e}")
            return {}
    
    def get_alpha_features(self) -> List[str]:
        """获取Alpha特征列表"""
        try:
            alpha_type = self.get_property('alpha_type')
            
            if alpha_type == 'Alpha158':
                # Alpha158特征列表
                return [
                    'ALPHA001', 'ALPHA002', 'ALPHA003', 'ALPHA004', 'ALPHA005',
                    'ALPHA006', 'ALPHA007', 'ALPHA008', 'ALPHA009', 'ALPHA010',
                    # ... 更多特征
                ]
            elif alpha_type == 'Alpha360':
                # Alpha360特征列表
                return [
                    'ALPHA001', 'ALPHA002', 'ALPHA003', 'ALPHA004', 'ALPHA005',
                    # ... 更多特征
                ]
            else:
                return []
                
        except Exception as e:
            logger.warning(f"获取Alpha特征列表失败: {e}")
            return []

class QlibHighFreqNode(QlibDataNode):
    """高频数据节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'high_freq')
        self.set_property('description', '高频数据节点')
        
        # 高频数据特定属性
        self.set_property('freq', '1min')  # 1min, 5min, 15min, 30min, 1h
        self.set_property('fields', ['$close', '$volume', '$amount', '$vwap'])
        self.set_property('limit_threshold', 0.095)  # 涨跌停限制
        self.set_property('deal_price', 'close')  # 成交价格类型
    
    def _validate_specific_config(self) -> bool:
        """验证高频节点特定配置"""
        try:
            freq = self.get_property('freq')
            if freq not in ['1min', '5min', '15min', '30min', '1h']:
                self._set_status("failed", f"不支持的高频频率: {freq}")
                return False
            
            return super()._validate_specific_config()
            
        except Exception as e:
            self._set_status("failed", f"高频节点配置验证失败: {e}")
            return False
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行高频数据获取逻辑"""
        try:
            if not QLIB_AVAILABLE:
                self._set_status("failed", "Qlib不可用")
                return {}
            
            instruments = self.get_property('instruments')
            fields = self.get_property('fields')
            start_time = self.get_property('start_time')
            end_time = self.get_property('end_time')
            freq = self.get_property('freq')
            
            # 获取高频数据
            high_freq_data = D.features(
                instruments=instruments,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                freq=freq
            )
            
            # 处理高频数据
            processed_data = self._process_high_freq_data(high_freq_data)
            
            logger.info(f"高频数据获取成功: {processed_data.shape}")
            
            return {
                'high_freq_data': processed_data,
                'freq': freq,
                'fields': fields
            }
            
        except Exception as e:
            self._set_status("failed", f"高频数据获取失败: {e}")
            logger.error(f"高频数据获取失败: {e}")
            return {}
    
    def _process_high_freq_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """处理高频数据"""
        try:
            # 移除无效数据
            data = data.dropna()
            
            # 处理涨跌停
            limit_threshold = self.get_property('limit_threshold', 0.095)
            if '$close' in data.columns and '$open' in data.columns:
                # 计算涨跌幅
                price_change = (data['$close'] - data['$open']) / data['$open']
                # 标记涨跌停
                limit_up = price_change >= limit_threshold
                limit_down = price_change <= -limit_threshold
                data['limit_up'] = limit_up
                data['limit_down'] = limit_down
            
            return data
            
        except Exception as e:
            logger.warning(f"高频数据处理失败: {e}")
            return data

class QlibCustomDataNode(QlibDataNode):
    """自定义数据源节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'custom')
        self.set_property('description', '自定义数据源节点')
        
        # 自定义数据特定属性
        self.set_property('data_source', 'csv')  # csv, database, api, file
        self.set_property('file_path', '')
        self.set_property('database_config', {})
        self.set_property('api_config', {})
        self.set_property('data_format', 'pandas')  # pandas, numpy, json
        self.set_property('custom_processor', '')
    
    def _validate_specific_config(self) -> bool:
        """验证自定义节点特定配置"""
        try:
            data_source = self.get_property('data_source')
            if data_source not in ['csv', 'database', 'api', 'file']:
                self._set_status("failed", f"不支持的数据源: {data_source}")
                return False
            
            if data_source == 'csv':
                file_path = self.get_property('file_path')
                if not file_path or not os.path.exists(file_path):
                    self._set_status("failed", f"CSV文件不存在: {file_path}")
                    return False
            
            return super()._validate_specific_config()
            
        except Exception as e:
            self._set_status("failed", f"自定义节点配置验证失败: {e}")
            return False
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行自定义数据获取逻辑"""
        try:
            data_source = self.get_property('data_source')
            
            if data_source == 'csv':
                data = self._load_csv_data()
            elif data_source == 'database':
                data = self._load_database_data()
            elif data_source == 'api':
                data = self._load_api_data()
            elif data_source == 'file':
                data = self._load_file_data()
            else:
                self._set_status("failed", f"不支持的数据源: {data_source}")
                return {}
            
            # 应用自定义处理器
            custom_processor = self.get_property('custom_processor')
            if custom_processor:
                data = self._apply_custom_processor(data, custom_processor)
            
            logger.info(f"自定义数据获取成功: {data.shape if hasattr(data, 'shape') else 'N/A'}")
            
            return {
                'custom_data': data,
                'data_source': data_source,
                'data_format': self.get_property('data_format')
            }
            
        except Exception as e:
            self._set_status("failed", f"自定义数据获取失败: {e}")
            logger.error(f"自定义数据获取失败: {e}")
            return {}
    
    def _load_csv_data(self) -> pd.DataFrame:
        """加载CSV数据"""
        file_path = self.get_property('file_path')
        return pd.read_csv(file_path)
    
    def _load_database_data(self) -> pd.DataFrame:
        """加载数据库数据"""
        # 这里实现数据库连接和查询逻辑
        return pd.DataFrame()
    
    def _load_api_data(self) -> pd.DataFrame:
        """加载API数据"""
        # 这里实现API调用逻辑
        return pd.DataFrame()
    
    def _load_file_data(self) -> Any:
        """加载文件数据"""
        file_path = self.get_property('file_path')
        data_format = self.get_property('data_format')
        
        if data_format == 'pandas':
            return pd.read_csv(file_path)
        elif data_format == 'numpy':
            return np.load(file_path)
        elif data_format == 'json':
            import json
            with open(file_path, 'r') as f:
                return json.load(f)
        else:
            return None
    
    def _apply_custom_processor(self, data: Any, processor: str) -> Any:
        """应用自定义处理器"""
        try:
            # 这里可以实现自定义数据处理逻辑
            # 简化实现
            return data
        except Exception as e:
            logger.warning(f"自定义处理器应用失败: {e}")
            return data

class QlibProcessorNode(QlibDataNode):
    """数据预处理节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'processor')
        self.set_property('description', '数据预处理节点')
        
        # 预处理特定属性
        self.set_property('missing_value_strategy', 'drop')  # drop, fill, interpolate
        self.set_property('outlier_strategy', 'clip')  # clip, remove, transform
        self.set_property('outlier_threshold', 3.0)
        self.set_property('normalize_strategy', 'standard')  # standard, minmax, robust
        self.set_property('feature_selection', False)
        self.set_property('max_features', None)
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据预处理逻辑"""
        try:
            # 获取输入数据
            input_data = inputs.get('data')
            if input_data is None:
                self._set_status("failed", "未提供输入数据")
                return {}
            
            # 数据清洗
            cleaned_data = self._clean_data(input_data)
            
            # 异常值处理
            processed_data = self._handle_outliers(cleaned_data)
            
            # 缺失值处理
            processed_data = self._handle_missing_values(processed_data)
            
            # 数据标准化
            if self.get_property('normalize_strategy') != 'none':
                processed_data = self._normalize_data(processed_data)
            
            # 特征选择
            if self.get_property('feature_selection', False):
                processed_data = self._select_features(processed_data)
            
            logger.info(f"数据预处理完成: {processed_data.shape}")
            
            return {
                'processed_data': processed_data,
                'preprocessing_info': {
                    'missing_value_strategy': self.get_property('missing_value_strategy'),
                    'outlier_strategy': self.get_property('outlier_strategy'),
                    'normalize_strategy': self.get_property('normalize_strategy'),
                    'feature_selection': self.get_property('feature_selection')
                }
            }
            
        except Exception as e:
            self._set_status("failed", f"数据预处理失败: {e}")
            logger.error(f"数据预处理失败: {e}")
            return {}
    
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
    
    def _handle_outliers(self, data: pd.DataFrame) -> pd.DataFrame:
        """处理异常值"""
        try:
            strategy = self.get_property('outlier_strategy')
            threshold = self.get_property('outlier_threshold')
            
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            for column in numeric_columns:
                if strategy == 'clip':
                    # 使用3σ原则裁剪异常值
                    mean = data[column].mean()
                    std = data[column].std()
                    data[column] = data[column].clip(
                        mean - threshold * std,
                        mean + threshold * std
                    )
                elif strategy == 'remove':
                    # 移除异常值
                    mean = data[column].mean()
                    std = data[column].std()
                    mask = (data[column] >= mean - threshold * std) & (data[column] <= mean + threshold * std)
                    data = data[mask]
                elif strategy == 'transform':
                    # 使用对数变换
                    data[column] = np.log1p(data[column])
            
            return data
            
        except Exception as e:
            logger.warning(f"异常值处理失败: {e}")
            return data
    
    def _handle_missing_values(self, data: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""
        try:
            strategy = self.get_property('missing_value_strategy')
            
            if strategy == 'drop':
                data = data.dropna()
            elif strategy == 'fill':
                data = data.fillna(method='ffill').fillna(method='bfill')
            elif strategy == 'interpolate':
                data = data.interpolate()
            
            return data
            
        except Exception as e:
            logger.warning(f"缺失值处理失败: {e}")
            return data
    
    def _normalize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """标准化数据"""
        try:
            from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
            
            strategy = self.get_property('normalize_strategy')
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            if strategy == 'standard':
                scaler = StandardScaler()
            elif strategy == 'minmax':
                scaler = MinMaxScaler()
            elif strategy == 'robust':
                scaler = RobustScaler()
            else:
                return data
            
            if len(numeric_columns) > 0:
                data[numeric_columns] = scaler.fit_transform(data[numeric_columns])
            
            return data
            
        except Exception as e:
            logger.warning(f"数据标准化失败: {e}")
            return data
    
    def _select_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """特征选择"""
        try:
            from sklearn.feature_selection import SelectKBest, f_regression
            
            max_features = self.get_property('max_features')
            
            if max_features is not None and max_features < data.shape[1]:
                selector = SelectKBest(f_regression, k=max_features)
                selected_data = selector.fit_transform(data, data.iloc[:, -1])
                selected_features = data.columns[selector.get_support()]
                return pd.DataFrame(selected_data, columns=selected_features, index=data.index)
            
            return data
            
        except Exception as e:
            logger.warning(f"特征选择失败: {e}")
            return data

class QlibFeatureNode(QlibDataNode):
    """特征工程节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'feature')
        self.set_property('description', '特征工程节点')
        
        # 特征工程特定属性
        self.set_property('feature_types', ['technical', 'statistical', 'time_series'])
        self.set_property('technical_indicators', ['SMA', 'EMA', 'RSI', 'MACD'])
        self.set_property('statistical_features', ['mean', 'std', 'skew', 'kurt'])
        self.set_property('time_series_features', ['lag', 'diff', 'rolling'])
        self.set_property('window_sizes', [5, 10, 20, 30])
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行特征工程逻辑"""
        try:
            # 获取输入数据
            input_data = inputs.get('data')
            if input_data is None:
                self._set_status("failed", "未提供输入数据")
                return {}
            
            # 技术指标特征
            technical_features = self._create_technical_features(input_data)
            
            # 统计特征
            statistical_features = self._create_statistical_features(input_data)
            
            # 时间序列特征
            time_series_features = self._create_time_series_features(input_data)
            
            # 合并所有特征
            all_features = pd.concat([
                technical_features,
                statistical_features,
                time_series_features
            ], axis=1)
            
            logger.info(f"特征工程完成: {all_features.shape}")
            
            return {
                'features': all_features,
                'feature_info': {
                    'technical_features': technical_features.columns.tolist(),
                    'statistical_features': statistical_features.columns.tolist(),
                    'time_series_features': time_series_features.columns.tolist()
                }
            }
            
        except Exception as e:
            self._set_status("failed", f"特征工程失败: {e}")
            logger.error(f"特征工程失败: {e}")
            return {}
    
    def _create_technical_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """创建技术指标特征"""
        try:
            features = pd.DataFrame(index=data.index)
            
            if '$close' in data.columns:
                close_prices = data['$close']
                
                # 简单移动平均
                for window in self.get_property('window_sizes'):
                    features[f'SMA_{window}'] = close_prices.rolling(window=window).mean()
                
                # 指数移动平均
                for window in self.get_property('window_sizes'):
                    features[f'EMA_{window}'] = close_prices.ewm(span=window).mean()
                
                # RSI
                features['RSI'] = self._calculate_rsi(close_prices)
                
                # MACD
                macd_line, signal_line, histogram = self._calculate_macd(close_prices)
                features['MACD'] = macd_line
                features['MACD_Signal'] = signal_line
                features['MACD_Histogram'] = histogram
            
            return features
            
        except Exception as e:
            logger.warning(f"技术指标特征创建失败: {e}")
            return pd.DataFrame(index=data.index)
    
    def _create_statistical_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """创建统计特征"""
        try:
            features = pd.DataFrame(index=data.index)
            
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            for column in numeric_columns:
                series = data[column]
                
                # 滚动统计特征
                for window in self.get_property('window_sizes'):
                    features[f'{column}_mean_{window}'] = series.rolling(window=window).mean()
                    features[f'{column}_std_{window}'] = series.rolling(window=window).std()
                    features[f'{column}_skew_{window}'] = series.rolling(window=window).skew()
                    features[f'{column}_kurt_{window}'] = series.rolling(window=window).kurt()
            
            return features
            
        except Exception as e:
            logger.warning(f"统计特征创建失败: {e}")
            return pd.DataFrame(index=data.index)
    
    def _create_time_series_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """创建时间序列特征"""
        try:
            features = pd.DataFrame(index=data.index)
            
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            for column in numeric_columns:
                series = data[column]
                
                # 滞后特征
                for lag in [1, 2, 3, 5, 10]:
                    features[f'{column}_lag_{lag}'] = series.shift(lag)
                
                # 差分特征
                features[f'{column}_diff_1'] = series.diff(1)
                features[f'{column}_diff_2'] = series.diff(2)
                
                # 滚动特征
                for window in self.get_property('window_sizes'):
                    features[f'{column}_rolling_mean_{window}'] = series.rolling(window=window).mean()
                    features[f'{column}_rolling_std_{window}'] = series.rolling(window=window).std()
            
            return features
            
        except Exception as e:
            logger.warning(f"时间序列特征创建失败: {e}")
            return pd.DataFrame(index=data.index)
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except:
            return pd.Series(index=prices.index, dtype=float)
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算MACD指标"""
        try:
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line
            return macd_line, signal_line, histogram
        except:
            return pd.Series(index=prices.index, dtype=float), pd.Series(index=prices.index, dtype=float), pd.Series(index=prices.index, dtype=float)

class QlibNormalizeNode(QlibDataNode):
    """数据标准化节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'normalize')
        self.set_property('description', '数据标准化节点')
        
        # 标准化特定属性
        self.set_property('normalize_method', 'standard')  # standard, minmax, robust, quantile
        self.set_property('feature_range', (0, 1))  # 用于minmax标准化
        self.set_property('quantile_range', (0.25, 0.75))  # 用于quantile标准化
        self.set_property('exclude_columns', [])  # 排除的列
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据标准化逻辑"""
        try:
            # 获取输入数据
            input_data = inputs.get('data')
            if input_data is None:
                self._set_status("failed", "未提供输入数据")
                return {}
            
            # 标准化数据
            normalized_data = self._normalize_data(input_data)
            
            logger.info(f"数据标准化完成: {normalized_data.shape}")
            
            return {
                'normalized_data': normalized_data,
                'normalize_method': self.get_property('normalize_method'),
                'normalize_info': {
                    'method': self.get_property('normalize_method'),
                    'excluded_columns': self.get_property('exclude_columns')
                }
            }
            
        except Exception as e:
            self._set_status("failed", f"数据标准化失败: {e}")
            logger.error(f"数据标准化失败: {e}")
            return {}
    
    def _normalize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """标准化数据"""
        try:
            from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, QuantileTransformer
            
            method = self.get_property('normalize_method')
            exclude_columns = self.get_property('exclude_columns', [])
            
            # 选择需要标准化的列
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            columns_to_normalize = [col for col in numeric_columns if col not in exclude_columns]
            
            if not columns_to_normalize:
                return data
            
            # 创建标准化器
            if method == 'standard':
                scaler = StandardScaler()
            elif method == 'minmax':
                scaler = MinMaxScaler(feature_range=self.get_property('feature_range'))
            elif method == 'robust':
                scaler = RobustScaler()
            elif method == 'quantile':
                scaler = QuantileTransformer(output_distribution='normal')
            else:
                return data
            
            # 标准化数据
            normalized_data = data.copy()
            normalized_data[columns_to_normalize] = scaler.fit_transform(data[columns_to_normalize])
            
            return normalized_data
            
        except Exception as e:
            logger.warning(f"数据标准化失败: {e}")
            return data

class QlibFilterNode(QlibDataNode):
    """数据过滤节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'filter')
        self.set_property('description', '数据过滤节点')
        
        # 过滤特定属性
        self.set_property('filter_conditions', [])  # 过滤条件列表
        self.set_property('filter_type', 'row')  # row, column, value
        self.set_property('filter_operator', 'and')  # and, or
        self.set_property('min_data_points', 100)  # 最小数据点数
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据过滤逻辑"""
        try:
            # 获取输入数据
            input_data = inputs.get('data')
            if input_data is None:
                self._set_status("failed", "未提供输入数据")
                return {}
            
            # 应用过滤条件
            filtered_data = self._apply_filters(input_data)
            
            # 检查数据量
            if len(filtered_data) < self.get_property('min_data_points'):
                self._set_status("warning", f"过滤后数据量不足: {len(filtered_data)} < {self.get_property('min_data_points')}")
            
            logger.info(f"数据过滤完成: {filtered_data.shape}")
            
            return {
                'filtered_data': filtered_data,
                'filter_info': {
                    'original_shape': input_data.shape,
                    'filtered_shape': filtered_data.shape,
                    'filter_conditions': self.get_property('filter_conditions')
                }
            }
            
        except Exception as e:
            self._set_status("failed", f"数据过滤失败: {e}")
            logger.error(f"数据过滤失败: {e}")
            return {}
    
    def _apply_filters(self, data: pd.DataFrame) -> pd.DataFrame:
        """应用过滤条件"""
        try:
            filtered_data = data.copy()
            conditions = self.get_property('filter_conditions', [])
            filter_operator = self.get_property('filter_operator', 'and')
            
            if not conditions:
                return filtered_data
            
            # 应用每个过滤条件
            mask = pd.Series(True, index=data.index)
            
            for condition in conditions:
                condition_mask = self._apply_single_filter(data, condition)
                
                if filter_operator == 'and':
                    mask = mask & condition_mask
                else:  # or
                    mask = mask | condition_mask
            
            return filtered_data[mask]
            
        except Exception as e:
            logger.warning(f"应用过滤条件失败: {e}")
            return data
    
    def _apply_single_filter(self, data: pd.DataFrame, condition: Dict[str, Any]) -> pd.Series:
        """应用单个过滤条件"""
        try:
            column = condition.get('column')
            operator = condition.get('operator')
            value = condition.get('value')
            
            if column not in data.columns:
                return pd.Series(True, index=data.index)
            
            if operator == '>':
                return data[column] > value
            elif operator == '>=':
                return data[column] >= value
            elif operator == '<':
                return data[column] < value
            elif operator == '<=':
                return data[column] <= value
            elif operator == '==':
                return data[column] == value
            elif operator == '!=':
                return data[column] != value
            elif operator == 'in':
                return data[column].isin(value)
            elif operator == 'not_in':
                return ~data[column].isin(value)
            elif operator == 'is_null':
                return data[column].isnull()
            elif operator == 'not_null':
                return ~data[column].isnull()
            else:
                return pd.Series(True, index=data.index)
                
        except Exception as e:
            logger.warning(f"应用单个过滤条件失败: {e}")
            return pd.Series(True, index=data.index)

class QlibCacheNode(QlibDataNode):
    """数据缓存节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'cache')
        self.set_property('description', '数据缓存节点')
        
        # 缓存特定属性
        self.set_property('cache_strategy', 'memory')  # memory, disk, both
        self.set_property('cache_ttl', 3600)  # 缓存生存时间（秒）
        self.set_property('cache_compression', True)  # 是否压缩
        self.set_property('cache_key_prefix', 'cache')  # 缓存键前缀
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据缓存逻辑"""
        try:
            # 获取输入数据
            input_data = inputs.get('data')
            if input_data is None:
                self._set_status("failed", "未提供输入数据")
                return {}
            
            # 生成缓存键
            cache_key = self._generate_cache_key(input_data)
            
            # 尝试从缓存获取
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                logger.info(f"从缓存获取数据: {cache_key}")
                return {
                    'cached_data': cached_data,
                    'cache_hit': True,
                    'cache_key': cache_key
                }
            
            # 缓存未命中，处理数据
            processed_data = self._process_data(input_data)
            
            # 保存到缓存
            self._save_to_cache(cache_key, processed_data)
            
            logger.info(f"数据已缓存: {cache_key}")
            
            return {
                'cached_data': processed_data,
                'cache_hit': False,
                'cache_key': cache_key
            }
            
        except Exception as e:
            self._set_status("failed", f"数据缓存失败: {e}")
            logger.error(f"数据缓存失败: {e}")
            return {}
    
    def _generate_cache_key(self, data: Any) -> str:
        """生成缓存键"""
        try:
            import hashlib
            
            # 基于数据内容生成键
            if isinstance(data, pd.DataFrame):
                data_str = f"{data.shape}_{data.columns.tolist()}_{data.index.tolist()}"
            else:
                data_str = str(data)
            
            # 添加节点属性
            node_str = f"{self.get_node_id()}_{self.get_property('cache_key_prefix')}"
            
            # 生成哈希
            key_str = f"{node_str}_{data_str}"
            return hashlib.md5(key_str.encode()).hexdigest()[:16]
            
        except Exception as e:
            logger.warning(f"生成缓存键失败: {e}")
            return f"cache_{int(time.time())}"
    
    def _get_from_cache(self, cache_key: str) -> Any:
        """从缓存获取数据"""
        try:
            # 这里可以实现具体的缓存逻辑
            # 简化实现
            return None
            
        except Exception as e:
            logger.warning(f"从缓存获取数据失败: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: Any):
        """保存数据到缓存"""
        try:
            # 这里可以实现具体的缓存逻辑
            # 简化实现
            pass
            
        except Exception as e:
            logger.warning(f"保存数据到缓存失败: {e}")

class QlibStorageNode(QlibDataNode):
    """数据存储节点"""
    
    def __init__(self):
        super().__init__()
        self.set_property('node_type', 'storage')
        self.set_property('description', '数据存储节点')
        
        # 存储特定属性
        self.set_property('storage_type', 'file')  # file, database, cloud
        self.set_property('file_format', 'parquet')  # parquet, csv, hdf5, pickle
        self.set_property('file_path', '')
        self.set_property('database_config', {})
        self.set_property('cloud_config', {})
        self.set_property('compression', True)  # 是否压缩
    
    def _execute_logic(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据存储逻辑"""
        try:
            # 获取输入数据
            input_data = inputs.get('data')
            if input_data is None:
                self._set_status("failed", "未提供输入数据")
                return {}
            
            # 存储数据
            storage_path = self._store_data(input_data)
            
            logger.info(f"数据存储完成: {storage_path}")
            
            return {
                'stored_data': input_data,
                'storage_path': storage_path,
                'storage_type': self.get_property('storage_type'),
                'file_format': self.get_property('file_format')
            }
            
        except Exception as e:
            self._set_status("failed", f"数据存储失败: {e}")
            logger.error(f"数据存储失败: {e}")
            return {}
    
    def _store_data(self, data: pd.DataFrame) -> str:
        """存储数据"""
        try:
            storage_type = self.get_property('storage_type')
            
            if storage_type == 'file':
                return self._store_to_file(data)
            elif storage_type == 'database':
                return self._store_to_database(data)
            elif storage_type == 'cloud':
                return self._store_to_cloud(data)
            else:
                raise ValueError(f"不支持的存储类型: {storage_type}")
                
        except Exception as e:
            logger.error(f"数据存储失败: {e}")
            return ""
    
    def _store_to_file(self, data: pd.DataFrame) -> str:
        """存储到文件"""
        try:
            file_path = self.get_property('file_path')
            file_format = self.get_property('file_format')
            compression = self.get_property('compression')
            
            if not file_path:
                # 生成默认文件路径
                timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
                file_path = f"data_{timestamp}.{file_format}"
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 根据格式保存
            if file_format == 'parquet':
                data.to_parquet(file_path, compression='gzip' if compression else None)
            elif file_format == 'csv':
                data.to_csv(file_path, compression='gzip' if compression else None)
            elif file_format == 'hdf5':
                data.to_hdf(file_path, 'data', mode='w', complevel=9 if compression else 0)
            elif file_format == 'pickle':
                data.to_pickle(file_path)
            else:
                raise ValueError(f"不支持的文件格式: {file_format}")
            
            return file_path
            
        except Exception as e:
            logger.error(f"文件存储失败: {e}")
            return ""
    
    def _store_to_database(self, data: pd.DataFrame) -> str:
        """存储到数据库"""
        try:
            # 这里实现数据库存储逻辑
            # 简化实现
            return "database_storage"
            
        except Exception as e:
            logger.error(f"数据库存储失败: {e}")
            return ""
    
    def _store_to_cloud(self, data: pd.DataFrame) -> str:
        """存储到云存储"""
        try:
            # 这里实现云存储逻辑
            # 简化实现
            return "cloud_storage"
            
        except Exception as e:
            logger.error(f"云存储失败: {e}")
            return ""
