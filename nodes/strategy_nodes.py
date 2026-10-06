#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib策略节点实现
严格按照设计文档实现
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List, Union
import pandas as pd
import numpy as np
import warnings

# Qlib imports
try:
    import qlib
    from qlib.contrib.strategy import TopkDropoutStrategy, LongShortStrategy
    from qlib.contrib.strategy import PortfolioStrategy, RiskStrategy
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    QLIB_AVAILABLE = True
except ImportError as e:
    QLIB_AVAILABLE = False
    warnings.warn(f"Qlib not available, some features will be limited. Error: {e}")

# 添加核心模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from qlib_base_node import QlibBaseNode

logger = logging.getLogger(__name__)

class QlibSignalNode(QlibBaseNode):
    """信号生成节点"""
    NODE_NAME = "Qlib Signal Node"
    NODE_CATEGORY = "Qlib/Strategy"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("predictions", "dataframe")
        self.add_input_port("market_data", "dataframe")
        self.add_output_port("signals", "dataframe")
        self.add_output_port("signal_strength", "dataframe")
        
        self.add_rockx_property("signal_type", str, "long_short", "信号类型", "信号类型: long_short, long_only, short_only")
        self.add_rockx_property("threshold", float, 0.5, "信号阈值", "信号生成阈值")
        self.add_rockx_property("signal_strength", bool, True, "信号强度", "是否计算信号强度")
        self.add_rockx_property("normalize", bool, True, "标准化", "是否标准化信号")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        predictions = inputs.get("predictions")
        market_data = inputs.get("market_data")
        
        if predictions is None:
            self.set_status("failed", "No predictions provided")
            return False
        
        try:
            signal_type = self.get_rockx_property("signal_type")
            threshold = self.get_rockx_property("threshold")
            signal_strength = self.get_rockx_property("signal_strength")
            normalize = self.get_rockx_property("normalize")
            
            # 生成信号
            if signal_type == "long_short":
                signals = self._generate_long_short_signals(predictions, threshold)
            elif signal_type == "long_only":
                signals = self._generate_long_only_signals(predictions, threshold)
            elif signal_type == "short_only":
                signals = self._generate_short_only_signals(predictions, threshold)
            else:
                raise ValueError(f"Unsupported signal type: {signal_type}")
            
            # 标准化信号
            if normalize:
                signals = self._normalize_signals(signals)
            
            # 计算信号强度
            signal_strength_df = None
            if signal_strength:
                signal_strength_df = self._calculate_signal_strength(predictions, signals)
            
            self.set_output("signals", signals)
            self.set_output("signal_strength", signal_strength_df)
            
            self.set_status("completed", f"Signal generation completed: {signal_type}")
            return True
            
        except Exception as e:
            logger.error(f"Signal generation failed: {e}")
            self.set_status("failed", f"Signal generation failed: {e}")
            return False
    
    def _generate_long_short_signals(self, predictions, threshold):
        """生成多空信号"""
        signals = predictions.copy()
        signals[predictions > threshold] = 1  # 多头信号
        signals[predictions < -threshold] = -1  # 空头信号
        signals[(predictions >= -threshold) & (predictions <= threshold)] = 0  # 中性信号
        return signals
    
    def _generate_long_only_signals(self, predictions, threshold):
        """生成多头信号"""
        signals = predictions.copy()
        signals[predictions > threshold] = 1  # 多头信号
        signals[predictions <= threshold] = 0  # 中性信号
        return signals
    
    def _generate_short_only_signals(self, predictions, threshold):
        """生成空头信号"""
        signals = predictions.copy()
        signals[predictions < -threshold] = -1  # 空头信号
        signals[predictions >= -threshold] = 0  # 中性信号
        return signals
    
    def _normalize_signals(self, signals):
        """标准化信号"""
        return signals / signals.abs().max()
    
    def _calculate_signal_strength(self, predictions, signals):
        """计算信号强度"""
        strength = np.abs(predictions) * np.abs(signals)
        return strength

class QlibTopKNode(QlibBaseNode):
    """TopK策略节点"""
    NODE_NAME = "Qlib TopK Strategy"
    NODE_CATEGORY = "Qlib/Strategy"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("predictions", "dataframe")
        self.add_input_port("market_data", "dataframe")
        self.add_output_port("strategy", "strategy")
        self.add_output_port("positions", "dataframe")
        
        self.add_rockx_property("topk", int, 30, "TopK数量", "选择前K只股票")
        self.add_rockx_property("dropout", float, 0.1, "丢弃比例", "丢弃比例")
        self.add_rockx_property("rebalance_freq", str, "day", "调仓频率", "调仓频率: day, week, month")
        self.add_rockx_property("weight_method", str, "equal", "权重方法", "权重分配方法: equal, market_cap, volume")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        predictions = inputs.get("predictions")
        market_data = inputs.get("market_data")
        
        if predictions is None:
            self.set_status("failed", "No predictions provided")
            return False
        
        try:
            topk = self.get_rockx_property("topk")
            dropout = self.get_rockx_property("dropout")
            rebalance_freq = self.get_rockx_property("rebalance_freq")
            weight_method = self.get_rockx_property("weight_method")
            
            # 创建TopK策略配置
            strategy_config = {
                "class": "TopkDropoutStrategy",
                "module_path": "qlib.contrib.strategy",
                "kwargs": {
                    "topk": topk,
                    "dropout": dropout,
                    "rebalance_freq": rebalance_freq,
                    "weight_method": weight_method
                }
            }
            
            # 初始化策略
            strategy = init_instance_by_config(strategy_config)
            
            # 生成持仓
            positions = strategy.generate_positions(predictions, market_data)
            
            self.set_output("strategy", strategy)
            self.set_output("positions", positions)
            
            self.set_status("completed", f"TopK strategy created: topk={topk}")
            return True
            
        except Exception as e:
            logger.error(f"TopK strategy creation failed: {e}")
            self.set_status("failed", f"TopK strategy creation failed: {e}")
            return False

class QlibLongShortNode(QlibBaseNode):
    """多空策略节点"""
    NODE_NAME = "Qlib Long-Short Strategy"
    NODE_CATEGORY = "Qlib/Strategy"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("predictions", "dataframe")
        self.add_input_port("market_data", "dataframe")
        self.add_output_port("strategy", "strategy")
        self.add_output_port("positions", "dataframe")
        
        self.add_rockx_property("long_threshold", float, 0.6, "多头阈值", "多头信号阈值")
        self.add_rockx_property("short_threshold", float, 0.4, "空头阈值", "空头信号阈值")
        self.add_rockx_property("max_long_weight", float, 0.1, "最大多头权重", "单只股票最大多头权重")
        self.add_rockx_property("max_short_weight", float, 0.1, "最大空头权重", "单只股票最大空头权重")
        self.add_rockx_property("rebalance_freq", str, "day", "调仓频率", "调仓频率: day, week, month")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        predictions = inputs.get("predictions")
        market_data = inputs.get("market_data")
        
        if predictions is None:
            self.set_status("failed", "No predictions provided")
            return False
        
        try:
            long_threshold = self.get_rockx_property("long_threshold")
            short_threshold = self.get_rockx_property("short_threshold")
            max_long_weight = self.get_rockx_property("max_long_weight")
            max_short_weight = self.get_rockx_property("max_short_weight")
            rebalance_freq = self.get_rockx_property("rebalance_freq")
            
            # 创建多空策略配置
            strategy_config = {
                "class": "LongShortStrategy",
                "module_path": "qlib.contrib.strategy",
                "kwargs": {
                    "long_threshold": long_threshold,
                    "short_threshold": short_threshold,
                    "max_long_weight": max_long_weight,
                    "max_short_weight": max_short_weight,
                    "rebalance_freq": rebalance_freq
                }
            }
            
            # 初始化策略
            strategy = init_instance_by_config(strategy_config)
            
            # 生成持仓
            positions = strategy.generate_positions(predictions, market_data)
            
            self.set_output("strategy", strategy)
            self.set_output("positions", positions)
            
            self.set_status("completed", f"Long-Short strategy created")
            return True
            
        except Exception as e:
            logger.error(f"Long-Short strategy creation failed: {e}")
            self.set_status("failed", f"Long-Short strategy creation failed: {e}")
            return False

class QlibPortfolioNode(QlibBaseNode):
    """投资组合策略节点"""
    NODE_NAME = "Qlib Portfolio Strategy"
    NODE_CATEGORY = "Qlib/Strategy"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("predictions", "dataframe")
        self.add_input_port("market_data", "dataframe")
        self.add_output_port("strategy", "strategy")
        self.add_output_port("positions", "dataframe")
        
        self.add_rockx_property("portfolio_method", str, "equal_weight", "投资组合方法", "投资组合方法: equal_weight, market_cap, risk_parity")
        self.add_rockx_property("max_weight", float, 0.1, "最大权重", "单只股票最大权重")
        self.add_rockx_property("min_weight", float, 0.0, "最小权重", "单只股票最小权重")
        self.add_rockx_property("rebalance_freq", str, "day", "调仓频率", "调仓频率: day, week, month")
        self.add_rockx_property("transaction_cost", float, 0.001, "交易成本", "交易成本比例")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        predictions = inputs.get("predictions")
        market_data = inputs.get("market_data")
        
        if predictions is None:
            self.set_status("failed", "No predictions provided")
            return False
        
        try:
            portfolio_method = self.get_rockx_property("portfolio_method")
            max_weight = self.get_rockx_property("max_weight")
            min_weight = self.get_rockx_property("min_weight")
            rebalance_freq = self.get_rockx_property("rebalance_freq")
            transaction_cost = self.get_rockx_property("transaction_cost")
            
            # 创建投资组合策略配置
            strategy_config = {
                "class": "PortfolioStrategy",
                "module_path": "qlib.contrib.strategy",
                "kwargs": {
                    "portfolio_method": portfolio_method,
                    "max_weight": max_weight,
                    "min_weight": min_weight,
                    "rebalance_freq": rebalance_freq,
                    "transaction_cost": transaction_cost
                }
            }
            
            # 初始化策略
            strategy = init_instance_by_config(strategy_config)
            
            # 生成持仓
            positions = strategy.generate_positions(predictions, market_data)
            
            self.set_output("strategy", strategy)
            self.set_output("positions", positions)
            
            self.set_status("completed", f"Portfolio strategy created: {portfolio_method}")
            return True
            
        except Exception as e:
            logger.error(f"Portfolio strategy creation failed: {e}")
            self.set_status("failed", f"Portfolio strategy creation failed: {e}")
            return False

class QlibRiskNode(QlibBaseNode):
    """风险管理节点"""
    NODE_NAME = "Qlib Risk Management"
    NODE_CATEGORY = "Qlib/Strategy"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("positions", "dataframe")
        self.add_input_port("market_data", "dataframe")
        self.add_output_port("risk_metrics", "dict")
        self.add_output_port("risk_adjusted_positions", "dataframe")
        
        self.add_rockx_property("risk_model", str, "var", "风险模型", "风险模型: var, cvar, volatility")
        self.add_rockx_property("confidence_level", float, 0.95, "置信水平", "VaR置信水平")
        self.add_rockx_property("max_var", float, 0.05, "最大VaR", "最大VaR限制")
        self.add_rockx_property("max_volatility", float, 0.2, "最大波动率", "最大波动率限制")
        self.add_rockx_property("risk_budget", float, 1.0, "风险预算", "风险预算")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        positions = inputs.get("positions")
        market_data = inputs.get("market_data")
        
        if positions is None:
            self.set_status("failed", "No positions provided")
            return False
        
        try:
            risk_model = self.get_rockx_property("risk_model")
            confidence_level = self.get_rockx_property("confidence_level")
            max_var = self.get_rockx_property("max_var")
            max_volatility = self.get_rockx_property("max_volatility")
            risk_budget = self.get_rockx_property("risk_budget")
            
            # 计算风险指标
            risk_metrics = self._calculate_risk_metrics(positions, market_data, risk_model, confidence_level)
            
            # 风险调整
            risk_adjusted_positions = self._adjust_positions_for_risk(
                positions, risk_metrics, max_var, max_volatility, risk_budget
            )
            
            self.set_output("risk_metrics", risk_metrics)
            self.set_output("risk_adjusted_positions", risk_adjusted_positions)
            
            self.set_status("completed", f"Risk management completed: {risk_model}")
            return True
            
        except Exception as e:
            logger.error(f"Risk management failed: {e}")
            self.set_status("failed", f"Risk management failed: {e}")
            return False
    
    def _calculate_risk_metrics(self, positions, market_data, risk_model, confidence_level):
        """计算风险指标"""
        risk_metrics = {}
        
        if risk_model == "var":
            # 计算VaR
            returns = market_data.pct_change().dropna()
            portfolio_returns = (positions * returns).sum(axis=1)
            var = np.percentile(portfolio_returns, (1 - confidence_level) * 100)
            risk_metrics["var"] = var
        
        elif risk_model == "cvar":
            # 计算CVaR
            returns = market_data.pct_change().dropna()
            portfolio_returns = (positions * returns).sum(axis=1)
            var = np.percentile(portfolio_returns, (1 - confidence_level) * 100)
            cvar = portfolio_returns[portfolio_returns <= var].mean()
            risk_metrics["cvar"] = cvar
        
        elif risk_model == "volatility":
            # 计算波动率
            returns = market_data.pct_change().dropna()
            portfolio_returns = (positions * returns).sum(axis=1)
            volatility = portfolio_returns.std() * np.sqrt(252)
            risk_metrics["volatility"] = volatility
        
        return risk_metrics
    
    def _adjust_positions_for_risk(self, positions, risk_metrics, max_var, max_volatility, risk_budget):
        """根据风险调整持仓"""
        adjusted_positions = positions.copy()
        
        # 根据VaR调整
        if "var" in risk_metrics and risk_metrics["var"] < -max_var:
            scale_factor = -max_var / risk_metrics["var"]
            adjusted_positions = adjusted_positions * scale_factor
        
        # 根据波动率调整
        if "volatility" in risk_metrics and risk_metrics["volatility"] > max_volatility:
            scale_factor = max_volatility / risk_metrics["volatility"]
            adjusted_positions = adjusted_positions * scale_factor
        
        # 应用风险预算
        adjusted_positions = adjusted_positions * risk_budget
        
        return adjusted_positions

class QlibRebalanceNode(QlibBaseNode):
    """调仓节点"""
    NODE_NAME = "Qlib Rebalance Strategy"
    NODE_CATEGORY = "Qlib/Strategy"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("current_positions", "dataframe")
        self.add_input_port("target_positions", "dataframe")
        self.add_input_port("market_data", "dataframe")
        self.add_output_port("rebalance_orders", "dataframe")
        self.add_output_port("transaction_cost", "float")
        
        self.add_rockx_property("rebalance_freq", str, "day", "调仓频率", "调仓频率: day, week, month")
        self.add_rockx_property("transaction_cost", float, 0.001, "交易成本", "交易成本比例")
        self.add_rockx_property("min_trade_size", float, 0.001, "最小交易规模", "最小交易规模")
        self.add_rockx_property("max_turnover", float, 1.0, "最大换手率", "最大换手率限制")
        self.add_rockx_property("rebalance_method", str, "full", "调仓方法", "调仓方法: full, partial, threshold")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        current_positions = inputs.get("current_positions")
        target_positions = inputs.get("target_positions")
        market_data = inputs.get("market_data")
        
        if current_positions is None or target_positions is None:
            self.set_status("failed", "No positions provided")
            return False
        
        try:
            rebalance_freq = self.get_rockx_property("rebalance_freq")
            transaction_cost = self.get_rockx_property("transaction_cost")
            min_trade_size = self.get_rockx_property("min_trade_size")
            max_turnover = self.get_rockx_property("max_turnover")
            rebalance_method = self.get_rockx_property("rebalance_method")
            
            # 计算调仓订单
            rebalance_orders = self._calculate_rebalance_orders(
                current_positions, target_positions, rebalance_method, min_trade_size
            )
            
            # 计算交易成本
            total_transaction_cost = self._calculate_transaction_cost(
                rebalance_orders, transaction_cost, market_data
            )
            
            # 检查换手率限制
            if self._check_turnover_limit(rebalance_orders, max_turnover):
                rebalance_orders = self._adjust_for_turnover_limit(
                    rebalance_orders, max_turnover
                )
            
            self.set_output("rebalance_orders", rebalance_orders)
            self.set_output("transaction_cost", total_transaction_cost)
            
            self.set_status("completed", f"Rebalance completed: {rebalance_method}")
            return True
            
        except Exception as e:
            logger.error(f"Rebalance failed: {e}")
            self.set_status("failed", f"Rebalance failed: {e}")
            return False
    
    def _calculate_rebalance_orders(self, current_positions, target_positions, method, min_trade_size):
        """计算调仓订单"""
        if method == "full":
            # 完全调仓
            orders = target_positions - current_positions
        elif method == "partial":
            # 部分调仓
            orders = (target_positions - current_positions) * 0.5
        elif method == "threshold":
            # 阈值调仓
            threshold = 0.01
            orders = target_positions - current_positions
            orders[np.abs(orders) < threshold] = 0
        else:
            raise ValueError(f"Unsupported rebalance method: {method}")
        
        # 过滤最小交易规模
        orders[np.abs(orders) < min_trade_size] = 0
        
        return orders
    
    def _calculate_transaction_cost(self, orders, transaction_cost, market_data):
        """计算交易成本"""
        if market_data is not None:
            # 基于市值的交易成本
            market_values = market_data.iloc[-1] if len(market_data) > 0 else 1.0
            cost = np.abs(orders * market_values).sum() * transaction_cost
        else:
            # 基于权重的交易成本
            cost = np.abs(orders).sum() * transaction_cost
        
        return cost
    
    def _check_turnover_limit(self, orders, max_turnover):
        """检查换手率限制"""
        turnover = np.abs(orders).sum()
        return turnover > max_turnover
    
    def _adjust_for_turnover_limit(self, orders, max_turnover):
        """根据换手率限制调整订单"""
        current_turnover = np.abs(orders).sum()
        if current_turnover > max_turnover:
            scale_factor = max_turnover / current_turnover
            orders = orders * scale_factor
        return orders