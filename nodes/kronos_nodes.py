#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kronos金融K线大模型节点
集成Kronos金融K线大模型，提供K线预测、量化分析等功能
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


# ---------------------------------------------------------------------------
# 定位 Kronos 库
#
# 原实现只试一个硬编码的相对路径：
#     <RockXQlib>/nodes/../../../PanShiBaseLib/Kronos
# 即 E:\2025\PanShiBaseLib\Kronos —— 这个目录**根本不存在**，
# 而真实的库在 E:\2025\PanShiAIQuant\PanShiBaseLib\Kronos 等位置，
# 结果 Kronos 节点一直静默降级成占位实现（不会报错，只是功能是假的）。
#
# 这里改成按候选列表逐个探测，并且**校验候选里真的有 model/kronos.py**，
# 避免把同名但无关的目录当成果。也支持用环境变量 KRONOS_PATH 显式指定。
# ---------------------------------------------------------------------------
def _resolve_kronos_path():
    here = os.path.dirname(os.path.abspath(__file__))
    proj = os.path.dirname(here)                      # <RockXQlib>
    root = os.path.dirname(proj)                      # E:\2025\RockX20251003

    candidates = []
    # 1) 环境变量显式指定（优先级最高）
    env_p = os.environ.get("KRONOS_PATH")
    if env_p:
        candidates.append(env_p)
    # 2) 相对本项目的常见位置
    candidates += [
        os.path.join(root, "PanShiBaseLib", "Kronos"),
        os.path.join(proj, "PanShiBaseLib", "Kronos"),
        os.path.join(root, "Kronos"),
    ]
    # 3) 同盘其他项目下的 PanShiBaseLib/Kronos（本机实际布局）
    drive = os.path.splitdrive(root)[0] + os.sep
    for sub in ("2025", ""):
        for proj_name in ("PanShiAIQuant", "0915AIQuantPyTorch", "AIQuantTF",
                          "09131505备份AIQuantPyTorch"):
            candidates.append(os.path.join(drive, sub, proj_name,
                                           "PanShiBaseLib", "Kronos"))

    for cand in candidates:
        if not cand:
            continue
        cand = os.path.abspath(cand)
        # 必须真的有 model/kronos.py，否则是同名无关目录
        if os.path.isfile(os.path.join(cand, "model", "kronos.py")):
            return cand
    return None


_kronos_path = _resolve_kronos_path()
if _kronos_path:
    if _kronos_path not in sys.path:
        sys.path.insert(0, _kronos_path)
    print(f"✅ 已定位 Kronos 库: {_kronos_path}")
else:
    print("⚠️ 未找到 Kronos 库（可用环境变量 KRONOS_PATH 指定），"
          "Kronos 节点将使用占位实现")


# NodeGraphQt 是硬依赖，必须显式失败；qlib_core 与 Kronos 模型各自独立降级。
# 原实现把三者放在同一个 try 里，任一导入失败就把 BaseNode 换成空壳占位类，
# 导致节点失去 add_input/add_output 等全部端口 API。
from NodeGraphQt import BaseNode
NODEGRAPH_AVAILABLE = True

try:
    from core.qlib_core_integration import qlib_core
except ImportError as _e:
    print(f"qlib_core 不可用: {_e}")
    qlib_core = None

# 尝试导入Kronos模型（缺失时用占位实现，保证节点仍可创建）
try:
    from model import Kronos, KronosTokenizer, KronosPredictor
    KRONOS_AVAILABLE = True
    print("✅ Kronos 模型导入成功（真实实现）")
except ImportError as e:
    KRONOS_AVAILABLE = False
    # 区分"库没找到"和"依赖缺失"，否则用户看到
    # "No module named 'einops'" 根本不知道要装什么
    if _kronos_path is None:
        print("⚠️ Kronos 库未找到，Kronos 节点使用占位实现。"
              "可用环境变量 KRONOS_PATH 指向库根目录。")
    else:
        print(f"⚠️ Kronos 库已找到（{_kronos_path}）但导入失败: {e}")
        print("   多半是缺依赖，尝试: pip install einops huggingface_hub safetensors")
    print("   Kronos 节点将使用占位实现（功能不可用，但不会报错）")

    class Kronos:
        @staticmethod
        def from_pretrained(model_name):
            return None

    class KronosTokenizer:
        @staticmethod
        def from_pretrained(tokenizer_name):
            return None

    class KronosPredictor:
        def __init__(self, model, tokenizer, device="cpu", max_context=512):
            self.model = model
            self.tokenizer = tokenizer
            self.device = device
            self.max_context = max_context

        def predict(self, df, x_timestamp, y_timestamp, pred_len, T=1.0, top_p=0.9, sample_count=1, verbose=True):
            # 模拟预测结果
            return pd.DataFrame({
                'open': np.random.randn(pred_len) * 0.01 + 100,
                'high': np.random.randn(pred_len) * 0.01 + 100,
                'low': np.random.randn(pred_len) * 0.01 + 100,
                'close': np.random.randn(pred_len) * 0.01 + 100,
                'volume': np.random.randint(1000000, 5000000, pred_len),
                'amount': np.random.randint(10000000, 50000000, pred_len)
            })

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

class KronosKlinePredictorNode(QlibCoreBaseNode):
    """Kronos K线预测节点"""
    
    __identifier__ = 'kronos.kline_predictor'
    NODE_NAME = 'Kronos K线预测'
    type_ = 'kronos.kline_predictor'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('kline_data')
        self.add_output('prediction_result')
        
        # 添加属性
        self.add_text_input('model_name', '模型名称', 'NeoQuasar/Kronos-small')
        self.add_text_input('tokenizer_name', '分词器名称', 'NeoQuasar/Kronos-Tokenizer-base')
        self.add_text_input('device', '设备', 'cpu')
        self.add_text_input('max_context', '最大上下文', '512')
        self.add_text_input('lookback', '回望长度', '400')
        self.add_text_input('pred_len', '预测长度', '120')
        self.add_text_input('temperature', '温度', '1.0')
        self.add_text_input('top_p', 'Top-p', '0.9')
        self.add_text_input('sample_count', '采样次数', '1')
        self.add_checkbox('verbose', '详细输出', '详细输出', True)
    
    def execute(self) -> bool:
        """执行Kronos K线预测"""
        try:
            # 检查输入
            kline_data = self.get_input('kline_data')
            if kline_data is None:
                raise Exception("K线数据为空")
            
            model_name = self.get_property('model_name')
            tokenizer_name = self.get_property('tokenizer_name')
            device = self.get_property('device')
            max_context = int(self.get_property('max_context'))
            lookback = int(self.get_property('lookback'))
            pred_len = int(self.get_property('pred_len'))
            temperature = float(self.get_property('temperature'))
            top_p = float(self.get_property('top_p'))
            sample_count = int(self.get_property('sample_count'))
            verbose = self.get_property('verbose')
            
            # 准备数据
            if isinstance(kline_data, pd.DataFrame):
                df = kline_data.copy()
            else:
                # 如果是其他格式，尝试转换
                df = pd.DataFrame(kline_data)
            
            # 确保数据包含必要的列
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                raise Exception(f"数据缺少必要列: {required_columns}")
            
            # 添加amount列（如果没有）
            if 'amount' not in df.columns:
                df['amount'] = df['close'] * df['volume']
            
            # 准备时间戳
            if 'timestamps' in df.columns:
                x_timestamp = df['timestamps'].iloc[:lookback]
                y_timestamp = pd.date_range(
                    start=df['timestamps'].iloc[lookback-1], 
                    periods=pred_len+1, 
                    freq='5min'
                )[1:]
            else:
                # 生成默认时间戳
                x_timestamp = pd.date_range(start='2023-01-01', periods=lookback, freq='5min')
                y_timestamp = pd.date_range(start='2023-01-01', periods=pred_len, freq='5min')
            
            # 准备输入数据
            x_df = df.loc[:lookback-1, ['open', 'high', 'low', 'close', 'volume', 'amount']]
            
            # 使用Kronos进行预测
            if KRONOS_AVAILABLE:
                # 加载模型和分词器
                tokenizer = KronosTokenizer.from_pretrained(tokenizer_name)
                model = Kronos.from_pretrained(model_name)
                
                # 创建预测器
                predictor = KronosPredictor(
                    model=model, 
                    tokenizer=tokenizer, 
                    device=device, 
                    max_context=max_context
                )
                
                # 执行预测
                pred_df = predictor.predict(
                    df=x_df,
                    x_timestamp=x_timestamp,
                    y_timestamp=y_timestamp,
                    pred_len=pred_len,
                    T=temperature,
                    top_p=top_p,
                    sample_count=sample_count,
                    verbose=verbose
                )
                
                self._execution_result = {
                    'status': 'success',
                    'model_name': model_name,
                    'prediction_length': pred_len,
                    'prediction_data': pred_df,
                    'input_data_shape': x_df.shape,
                    'kronos_available': True
                }
                self.set_output('prediction_result', self._execution_result)
                logger.info(f"✅ Kronos K线预测完成: {pred_len} 个预测点")
                return True
            else:
                # 模拟预测结果
                pred_df = pd.DataFrame({
                    'open': np.random.randn(pred_len) * 0.01 + x_df['close'].iloc[-1],
                    'high': np.random.randn(pred_len) * 0.01 + x_df['close'].iloc[-1],
                    'low': np.random.randn(pred_len) * 0.01 + x_df['close'].iloc[-1],
                    'close': np.random.randn(pred_len) * 0.01 + x_df['close'].iloc[-1],
                    'volume': np.random.randint(1000000, 5000000, pred_len),
                    'amount': np.random.randint(10000000, 50000000, pred_len)
                })
                
                self._execution_result = {
                    'status': 'success',
                    'model_name': model_name,
                    'prediction_length': pred_len,
                    'prediction_data': pred_df,
                    'input_data_shape': x_df.shape,
                    'kronos_available': False,
                    'note': '使用模拟数据，Kronos模型不可用'
                }
                self.set_output('prediction_result', self._execution_result)
                logger.info(f"✅ 模拟Kronos K线预测完成: {pred_len} 个预测点")
                return True
                
        except Exception as e:
            logger.error(f"Kronos K线预测节点执行失败: {e}")
            return False

class KronosQuantitativeAnalysisNode(QlibCoreBaseNode):
    """Kronos量化分析节点"""
    
    __identifier__ = 'kronos.quantitative_analysis'
    NODE_NAME = 'Kronos量化分析'
    type_ = 'kronos.quantitative_analysis'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('market_data')
        self.add_input('prediction_data')
        self.add_output('analysis_result')
        
        # 添加属性
        self.add_text_input('analysis_type', '分析类型', 'trend_analysis')
        self.add_text_input('time_horizon', '时间范围', 'short_term')
        self.add_checkbox('include_risk_metrics', '包含风险指标', '包含风险指标', True)
        self.add_checkbox('include_volatility', '包含波动率分析', '包含波动率分析', True)
        self.add_text_input('confidence_level', '置信水平', '0.95')
        self.add_text_input('lookback_period', '回望周期', '30')
    
    def execute(self) -> bool:
        """执行Kronos量化分析"""
        try:
            # 检查输入
            market_data = self.get_input('market_data')
            prediction_data = self.get_input('prediction_data')
            
            if market_data is None and prediction_data is None:
                raise Exception("输入数据为空")
            
            analysis_type = self.get_property('analysis_type')
            time_horizon = self.get_property('time_horizon')
            include_risk_metrics = self.get_property('include_risk_metrics')
            include_volatility = self.get_property('include_volatility')
            confidence_level = float(self.get_property('confidence_level'))
            lookback_period = int(self.get_property('lookback_period'))
            
            # 准备分析数据
            analysis_data = {}
            if market_data is not None:
                analysis_data['market_data'] = market_data
            if prediction_data is not None:
                analysis_data['prediction_data'] = prediction_data
            
            # 执行量化分析
            analysis_result = self._perform_quantitative_analysis(
                analysis_data=analysis_data,
                analysis_type=analysis_type,
                time_horizon=time_horizon,
                include_risk_metrics=include_risk_metrics,
                include_volatility=include_volatility,
                confidence_level=confidence_level,
                lookback_period=lookback_period
            )
            
            self._execution_result = {
                'status': 'success',
                'analysis_type': analysis_type,
                'time_horizon': time_horizon,
                'analysis_result': analysis_result,
                'confidence_level': confidence_level,
                'kronos_available': KRONOS_AVAILABLE
            }
            self.set_output('analysis_result', self._execution_result)
            logger.info(f"✅ Kronos量化分析完成: {analysis_type}")
            return True
                
        except Exception as e:
            logger.error(f"Kronos量化分析节点执行失败: {e}")
            return False
    
    def _perform_quantitative_analysis(self, analysis_data: Dict, analysis_type: str, 
                                     time_horizon: str, include_risk_metrics: bool,
                                     include_volatility: bool, confidence_level: float,
                                     lookback_period: int) -> Dict:
        """执行量化分析"""
        result = {
            'analysis_type': analysis_type,
            'time_horizon': time_horizon,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        
        # 趋势分析
        if analysis_type == 'trend_analysis':
            result['trend_analysis'] = self._analyze_trend(analysis_data, lookback_period)
        
        # 风险指标
        if include_risk_metrics:
            result['risk_metrics'] = self._calculate_risk_metrics(analysis_data, confidence_level)
        
        # 波动率分析
        if include_volatility:
            result['volatility_analysis'] = self._analyze_volatility(analysis_data, lookback_period)
        
        # 预测准确性评估
        if 'prediction_data' in analysis_data and 'market_data' in analysis_data:
            result['prediction_accuracy'] = self._evaluate_prediction_accuracy(
                analysis_data['market_data'], 
                analysis_data['prediction_data']
            )
        
        return result
    
    def _analyze_trend(self, analysis_data: Dict, lookback_period: int) -> Dict:
        """分析趋势"""
        # 模拟趋势分析
        return {
            'trend_direction': 'upward',
            'trend_strength': 0.75,
            'trend_confidence': 0.85,
            'support_level': 100.0,
            'resistance_level': 110.0
        }
    
    def _calculate_risk_metrics(self, analysis_data: Dict, confidence_level: float) -> Dict:
        """计算风险指标"""
        # 模拟风险指标计算
        return {
            'var': 0.05,  # Value at Risk
            'cvar': 0.07,  # Conditional Value at Risk
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.08,
            'volatility': 0.15
        }
    
    def _analyze_volatility(self, analysis_data: Dict, lookback_period: int) -> Dict:
        """分析波动率"""
        # 模拟波动率分析
        return {
            'current_volatility': 0.15,
            'historical_volatility': 0.18,
            'volatility_trend': 'decreasing',
            'volatility_forecast': 0.14
        }
    
    def _evaluate_prediction_accuracy(self, market_data: Any, prediction_data: Any) -> Dict:
        """评估预测准确性"""
        # 模拟预测准确性评估
        return {
            'mae': 0.02,  # Mean Absolute Error
            'rmse': 0.03,  # Root Mean Square Error
            'mape': 0.05,  # Mean Absolute Percentage Error
            'accuracy_score': 0.85
        }

class KronosStrategyNode(QlibCoreBaseNode):
    """Kronos策略节点"""
    
    __identifier__ = 'kronos.strategy'
    NODE_NAME = 'Kronos策略'
    type_ = 'kronos.strategy'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('prediction_data')
        self.add_input('market_data')
        self.add_output('strategy_signals')
        
        # 添加属性
        self.add_text_input('strategy_type', '策略类型', 'momentum')
        self.add_text_input('entry_threshold', '入场阈值', '0.02')
        self.add_text_input('exit_threshold', '出场阈值', '0.01')
        self.add_text_input('position_size', '仓位大小', '0.1')
        self.add_checkbox('use_stop_loss', '使用止损', '使用止损', True)
        self.add_text_input('stop_loss_pct', '止损百分比', '0.05')
        self.add_checkbox('use_take_profit', '使用止盈', '使用止盈', True)
        self.add_text_input('take_profit_pct', '止盈百分比', '0.1')
    
    def execute(self) -> bool:
        """执行Kronos策略"""
        try:
            # 检查输入
            prediction_data = self.get_input('prediction_data')
            market_data = self.get_input('market_data')
            
            if prediction_data is None:
                raise Exception("预测数据为空")
            
            strategy_type = self.get_property('strategy_type')
            entry_threshold = float(self.get_property('entry_threshold'))
            exit_threshold = float(self.get_property('exit_threshold'))
            position_size = float(self.get_property('position_size'))
            use_stop_loss = self.get_property('use_stop_loss')
            stop_loss_pct = float(self.get_property('stop_loss_pct'))
            use_take_profit = self.get_property('use_take_profit')
            take_profit_pct = float(self.get_property('take_profit_pct'))
            
            # 生成策略信号
            strategy_signals = self._generate_strategy_signals(
                prediction_data=prediction_data,
                market_data=market_data,
                strategy_type=strategy_type,
                entry_threshold=entry_threshold,
                exit_threshold=exit_threshold,
                position_size=position_size,
                use_stop_loss=use_stop_loss,
                stop_loss_pct=stop_loss_pct,
                use_take_profit=use_take_profit,
                take_profit_pct=take_profit_pct
            )
            
            self._execution_result = {
                'status': 'success',
                'strategy_type': strategy_type,
                'strategy_signals': strategy_signals,
                'position_size': position_size,
                'risk_management': {
                    'stop_loss': use_stop_loss,
                    'stop_loss_pct': stop_loss_pct,
                    'take_profit': use_take_profit,
                    'take_profit_pct': take_profit_pct
                },
                'kronos_available': KRONOS_AVAILABLE
            }
            self.set_output('strategy_signals', self._execution_result)
            logger.info(f"✅ Kronos策略生成完成: {strategy_type}")
            return True
                
        except Exception as e:
            logger.error(f"Kronos策略节点执行失败: {e}")
            return False
    
    def _generate_strategy_signals(self, prediction_data: Any, market_data: Any,
                                 strategy_type: str, entry_threshold: float,
                                 exit_threshold: float, position_size: float,
                                 use_stop_loss: bool, stop_loss_pct: float,
                                 use_take_profit: bool, take_profit_pct: float) -> Dict:
        """生成策略信号"""
        signals = {
            'strategy_type': strategy_type,
            'signals': [],
            'positions': [],
            'risk_metrics': {}
        }
        
        # 模拟策略信号生成
        if isinstance(prediction_data, dict) and 'prediction_data' in prediction_data:
            pred_df = prediction_data['prediction_data']
        elif isinstance(prediction_data, pd.DataFrame):
            pred_df = prediction_data
        else:
            # 生成模拟数据
            pred_df = pd.DataFrame({
                'close': np.random.randn(10) * 0.01 + 100,
                'volume': np.random.randint(1000000, 5000000, 10)
            })
        
        # 生成交易信号
        for i in range(len(pred_df)):
            signal = {
                'timestamp': pd.Timestamp.now() + pd.Timedelta(minutes=i*5),
                'action': 'buy' if i % 3 == 0 else 'hold',
                'price': pred_df['close'].iloc[i] if i < len(pred_df) else 100,
                'position_size': position_size,
                'confidence': 0.8
            }
            signals['signals'].append(signal)
        
        # 风险指标
        signals['risk_metrics'] = {
            'max_position_size': position_size,
            'stop_loss_pct': stop_loss_pct if use_stop_loss else None,
            'take_profit_pct': take_profit_pct if use_take_profit else None,
            'expected_return': 0.05,
            'expected_volatility': 0.15
        }
        
        return signals

# 导出所有节点类
__all__ = [
    'QlibCoreBaseNode',
    'KronosKlinePredictorNode',
    'KronosQuantitativeAnalysisNode',
    'KronosStrategyNode'
]
