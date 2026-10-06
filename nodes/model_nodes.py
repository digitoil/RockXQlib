#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib模型节点实现
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
    from qlib.contrib.model import LinearModel, LGBModel, XGBModel, CatBoostModel
    # 注意类名与本 qlib 版本一致：SFM -> SFM_Model、TabnetModel、TCN
    from qlib.contrib.model import GRU, LSTM, ALSTM, GATs, SFM_Model, TabnetModel, TCN
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    QLIB_AVAILABLE = True
except ImportError as e:
    QLIB_AVAILABLE = False
    warnings.warn(f"Qlib not available, some features will be limited. Error: {e}")

# Transformer 并非所有 qlib 版本都提供，单独探测，缺失时置 None
try:
    from qlib.contrib.model import Transformer
except ImportError:
    Transformer = None

# 添加核心模块路径（同时兼容包内导入与顶层模块导入）
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
try:
    from .qlib_base_node import QlibBaseNode
    from .qlib_model_node import QlibModelNode
except ImportError:
    from qlib_base_node import QlibBaseNode
    from qlib_model_node import QlibModelNode

logger = logging.getLogger(__name__)

class QlibLinearNode(QlibModelNode):
    """线性模型节点"""

    __identifier__ = 'qlib.model.linear'
    NODE_NAME = "Qlib Linear Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("fit_intercept", bool, True, "拟合截距", "是否拟合截距项")
        self.add_rockx_property("normalize", bool, False, "标准化", "是否标准化特征")
        self.add_rockx_property("random_state", int, 42, "随机种子", "随机数种子")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            # 创建线性模型配置
            model_config = {
                "class": "LinearModel",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "fit_intercept": self.get_rockx_property("fit_intercept"),
                    "normalize": self.get_rockx_property("normalize"),
                    "random_state": self.get_rockx_property("random_state")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", "Linear model training completed")
            return True
            
        except Exception as e:
            logger.error(f"Linear model training failed: {e}")
            self.set_status("failed", f"Linear model training failed: {e}")
            return False

class QlibTreeNode(QlibModelNode):
    """树模型节点"""

    __identifier__ = 'qlib.model.tree'
    NODE_NAME = "Qlib Tree Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("model_type", str, "lgb", "模型类型", "树模型类型: lgb, xgb, catboost")
        self.add_rockx_property("n_estimators", int, 100, "树的数量", "树的数量")
        self.add_rockx_property("max_depth", int, 6, "最大深度", "树的最大深度")
        self.add_rockx_property("learning_rate", float, 0.1, "学习率", "学习率")
        self.add_rockx_property("random_state", int, 42, "随机种子", "随机数种子")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            model_type = self.get_rockx_property("model_type")
            
            # 根据模型类型创建配置
            if model_type == "lgb":
                model_config = {
                    "class": "LGBModel",
                    "module_path": "qlib.contrib.model",
                    "kwargs": {
                        "n_estimators": self.get_rockx_property("n_estimators"),
                        "max_depth": self.get_rockx_property("max_depth"),
                        "learning_rate": self.get_rockx_property("learning_rate"),
                        "random_state": self.get_rockx_property("random_state")
                    }
                }
            elif model_type == "xgb":
                model_config = {
                    "class": "XGBModel",
                    "module_path": "qlib.contrib.model",
                    "kwargs": {
                        "n_estimators": self.get_rockx_property("n_estimators"),
                        "max_depth": self.get_rockx_property("max_depth"),
                        "learning_rate": self.get_rockx_property("learning_rate"),
                        "random_state": self.get_rockx_property("random_state")
                    }
                }
            elif model_type == "catboost":
                model_config = {
                    "class": "CatBoostModel",
                    "module_path": "qlib.contrib.model",
                    "kwargs": {
                        "n_estimators": self.get_rockx_property("n_estimators"),
                        "max_depth": self.get_rockx_property("max_depth"),
                        "learning_rate": self.get_rockx_property("learning_rate"),
                        "random_state": self.get_rockx_property("random_state")
                    }
                }
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", f"{model_type.upper()} model training completed")
            return True
            
        except Exception as e:
            logger.error(f"Tree model training failed: {e}")
            self.set_status("failed", f"Tree model training failed: {e}")
            return False

class QlibEnsembleNode(QlibModelNode):
    """集成模型节点"""

    __identifier__ = 'qlib.model.ensemble'
    NODE_NAME = "Qlib Ensemble Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("base_models", List[str], ["lgb", "xgb"], "基础模型", "基础模型列表")
        self.add_rockx_property("ensemble_method", str, "voting", "集成方法", "集成方法: voting, stacking, bagging")
        self.add_rockx_property("n_estimators", int, 100, "树的数量", "每个基础模型的树数量")
        self.add_rockx_property("random_state", int, 42, "随机种子", "随机数种子")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            base_models = self.get_rockx_property("base_models")
            ensemble_method = self.get_rockx_property("ensemble_method")
            
            # 创建基础模型
            base_model_configs = []
            for model_type in base_models:
                if model_type == "lgb":
                    config = {
                        "class": "LGBModel",
                        "module_path": "qlib.contrib.model",
                        "kwargs": {
                            "n_estimators": self.get_rockx_property("n_estimators"),
                            "random_state": self.get_rockx_property("random_state")
                        }
                    }
                elif model_type == "xgb":
                    config = {
                        "class": "XGBModel",
                        "module_path": "qlib.contrib.model",
                        "kwargs": {
                            "n_estimators": self.get_rockx_property("n_estimators"),
                            "random_state": self.get_rockx_property("random_state")
                        }
                    }
                else:
                    continue
                base_model_configs.append(config)
            
            # 创建集成模型
            if ensemble_method == "voting":
                # 简单投票集成
                models = []
                for config in base_model_configs:
                    model = init_instance_by_config(config)
                    model.fit(train_data)
                    models.append(model)
                
                # 预测
                predictions = None
                if test_data is not None:
                    pred_list = []
                    for model in models:
                        pred = model.predict(test_data)
                        pred_list.append(pred)
                    predictions = np.mean(pred_list, axis=0)
                
                # 评估模型
                metrics = self._evaluate_ensemble_model(models, train_data, test_data)
                
                self.set_output("model", models)
                self.set_output("predictions", predictions)
                self.set_output("metrics", metrics)
            
            self.set_status("completed", f"Ensemble model training completed")
            return True
            
        except Exception as e:
            logger.error(f"Ensemble model training failed: {e}")
            self.set_status("failed", f"Ensemble model training failed: {e}")
            return False

class QlibLSTMNode(QlibModelNode):
    """LSTM模型节点"""

    __identifier__ = 'qlib.model.lstm'
    NODE_NAME = "Qlib LSTM Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("hidden_size", int, 64, "隐藏层大小", "LSTM隐藏层大小")
        self.add_rockx_property("num_layers", int, 2, "层数", "LSTM层数")
        self.add_rockx_property("dropout", float, 0.1, "Dropout", "Dropout比例")
        self.add_rockx_property("learning_rate", float, 0.001, "学习率", "学习率")
        self.add_rockx_property("epochs", int, 100, "训练轮数", "训练轮数")
        self.add_rockx_property("batch_size", int, 32, "批次大小", "批次大小")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            # 创建LSTM模型配置
            model_config = {
                "class": "LSTM",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "hidden_size": self.get_rockx_property("hidden_size"),
                    "num_layers": self.get_rockx_property("num_layers"),
                    "dropout": self.get_rockx_property("dropout"),
                    "learning_rate": self.get_rockx_property("learning_rate"),
                    "epochs": self.get_rockx_property("epochs"),
                    "batch_size": self.get_rockx_property("batch_size")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", "LSTM model training completed")
            return True
            
        except Exception as e:
            logger.error(f"LSTM model training failed: {e}")
            self.set_status("failed", f"LSTM model training failed: {e}")
            return False

class QlibGRUNode(QlibModelNode):
    """GRU模型节点"""

    __identifier__ = 'qlib.model.gru'
    NODE_NAME = "Qlib GRU Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("hidden_size", int, 64, "隐藏层大小", "GRU隐藏层大小")
        self.add_rockx_property("num_layers", int, 2, "层数", "GRU层数")
        self.add_rockx_property("dropout", float, 0.1, "Dropout", "Dropout比例")
        self.add_rockx_property("learning_rate", float, 0.001, "学习率", "学习率")
        self.add_rockx_property("epochs", int, 100, "训练轮数", "训练轮数")
        self.add_rockx_property("batch_size", int, 32, "批次大小", "批次大小")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            # 创建GRU模型配置
            model_config = {
                "class": "GRU",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "hidden_size": self.get_rockx_property("hidden_size"),
                    "num_layers": self.get_rockx_property("num_layers"),
                    "dropout": self.get_rockx_property("dropout"),
                    "learning_rate": self.get_rockx_property("learning_rate"),
                    "epochs": self.get_rockx_property("epochs"),
                    "batch_size": self.get_rockx_property("batch_size")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", "GRU model training completed")
            return True
            
        except Exception as e:
            logger.error(f"GRU model training failed: {e}")
            self.set_status("failed", f"GRU model training failed: {e}")
            return False

class QlibTransformerNode(QlibModelNode):
    """Transformer模型节点"""

    __identifier__ = 'qlib.model.transformer'
    NODE_NAME = "Qlib Transformer Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("d_model", int, 64, "模型维度", "Transformer模型维度")
        self.add_rockx_property("n_heads", int, 8, "注意力头数", "多头注意力的头数")
        self.add_rockx_property("n_layers", int, 6, "层数", "Transformer层数")
        self.add_rockx_property("dropout", float, 0.1, "Dropout", "Dropout比例")
        self.add_rockx_property("learning_rate", float, 0.001, "学习率", "学习率")
        self.add_rockx_property("epochs", int, 100, "训练轮数", "训练轮数")
        self.add_rockx_property("batch_size", int, 32, "批次大小", "批次大小")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            # 创建Transformer模型配置
            model_config = {
                "class": "Transformer",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "d_model": self.get_rockx_property("d_model"),
                    "n_heads": self.get_rockx_property("n_heads"),
                    "n_layers": self.get_rockx_property("n_layers"),
                    "dropout": self.get_rockx_property("dropout"),
                    "learning_rate": self.get_rockx_property("learning_rate"),
                    "epochs": self.get_rockx_property("epochs"),
                    "batch_size": self.get_rockx_property("batch_size")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", "Transformer model training completed")
            return True
            
        except Exception as e:
            logger.error(f"Transformer model training failed: {e}")
            self.set_status("failed", f"Transformer model training failed: {e}")
            return False

class QlibCNNNode(QlibModelNode):
    """CNN模型节点"""

    __identifier__ = 'qlib.model.cnn'
    NODE_NAME = "Qlib CNN Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("input_channels", int, 1, "输入通道数", "输入数据的通道数")
        self.add_rockx_property("hidden_channels", List[int], [32, 64], "隐藏通道数", "隐藏层通道数列表")
        self.add_rockx_property("kernel_size", int, 3, "卷积核大小", "卷积核大小")
        self.add_rockx_property("dropout", float, 0.1, "Dropout", "Dropout比例")
        self.add_rockx_property("learning_rate", float, 0.001, "学习率", "学习率")
        self.add_rockx_property("epochs", int, 100, "训练轮数", "训练轮数")
        self.add_rockx_property("batch_size", int, 32, "批次大小", "批次大小")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            # 创建CNN模型配置
            model_config = {
                "class": "CNNModel",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "input_channels": self.get_rockx_property("input_channels"),
                    "hidden_channels": self.get_rockx_property("hidden_channels"),
                    "kernel_size": self.get_rockx_property("kernel_size"),
                    "dropout": self.get_rockx_property("dropout"),
                    "learning_rate": self.get_rockx_property("learning_rate"),
                    "epochs": self.get_rockx_property("epochs"),
                    "batch_size": self.get_rockx_property("batch_size")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", "CNN model training completed")
            return True
            
        except Exception as e:
            logger.error(f"CNN model training failed: {e}")
            self.set_status("failed", f"CNN model training failed: {e}")
            return False

class QlibRLNode(QlibModelNode):
    """强化学习模型节点"""

    __identifier__ = 'qlib.model.rl'
    NODE_NAME = "Qlib RL Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("rl_algorithm", str, "dqn", "强化学习算法", "强化学习算法: dqn, ppo, a2c")
        self.add_rockx_property("state_dim", int, 10, "状态维度", "状态空间维度")
        self.add_rockx_property("action_dim", int, 3, "动作维度", "动作空间维度")
        self.add_rockx_property("learning_rate", float, 0.001, "学习率", "学习率")
        self.add_rockx_property("episodes", int, 1000, "训练轮数", "训练轮数")
        self.add_rockx_property("batch_size", int, 32, "批次大小", "批次大小")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            rl_algorithm = self.get_rockx_property("rl_algorithm")
            
            # 创建强化学习模型配置
            model_config = {
                "class": f"{rl_algorithm.upper()}Model",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "state_dim": self.get_rockx_property("state_dim"),
                    "action_dim": self.get_rockx_property("action_dim"),
                    "learning_rate": self.get_rockx_property("learning_rate"),
                    "episodes": self.get_rockx_property("episodes"),
                    "batch_size": self.get_rockx_property("batch_size")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", f"{rl_algorithm.upper()} model training completed")
            return True
            
        except Exception as e:
            logger.error(f"RL model training failed: {e}")
            self.set_status("failed", f"RL model training failed: {e}")
            return False

class QlibDQNNode(QlibModelNode):
    """DQN模型节点"""

    __identifier__ = 'qlib.model.dqn'
    NODE_NAME = "Qlib DQN Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("state_dim", int, 10, "状态维度", "状态空间维度")
        self.add_rockx_property("action_dim", int, 3, "动作维度", "动作空间维度")
        self.add_rockx_property("hidden_size", int, 64, "隐藏层大小", "隐藏层大小")
        self.add_rockx_property("learning_rate", float, 0.001, "学习率", "学习率")
        self.add_rockx_property("episodes", int, 1000, "训练轮数", "训练轮数")
        self.add_rockx_property("epsilon", float, 0.1, "探索率", "探索率")
        self.add_rockx_property("gamma", float, 0.99, "折扣因子", "折扣因子")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            # 创建DQN模型配置
            model_config = {
                "class": "DQNModel",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "state_dim": self.get_rockx_property("state_dim"),
                    "action_dim": self.get_rockx_property("action_dim"),
                    "hidden_size": self.get_rockx_property("hidden_size"),
                    "learning_rate": self.get_rockx_property("learning_rate"),
                    "episodes": self.get_rockx_property("episodes"),
                    "epsilon": self.get_rockx_property("epsilon"),
                    "gamma": self.get_rockx_property("gamma")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", "DQN model training completed")
            return True
            
        except Exception as e:
            logger.error(f"DQN model training failed: {e}")
            self.set_status("failed", f"DQN model training failed: {e}")
            return False

class QlibPPONode(QlibModelNode):
    """PPO模型节点"""

    __identifier__ = 'qlib.model.ppo'
    NODE_NAME = "Qlib PPO Model"
    NODE_CATEGORY = "Qlib/Model"
    
    def __init__(self):
        super().__init__()
        self.add_input_port("train_data", "dataframe")
        self.add_input_port("test_data", "dataframe")
        self.add_output_port("model", "model")
        self.add_output_port("predictions", "dataframe")
        self.add_output_port("metrics", "dict")
        
        self.add_rockx_property("state_dim", int, 10, "状态维度", "状态空间维度")
        self.add_rockx_property("action_dim", int, 3, "动作维度", "动作空间维度")
        self.add_rockx_property("hidden_size", int, 64, "隐藏层大小", "隐藏层大小")
        self.add_rockx_property("learning_rate", float, 0.001, "学习率", "学习率")
        self.add_rockx_property("episodes", int, 1000, "训练轮数", "训练轮数")
        self.add_rockx_property("clip_ratio", float, 0.2, "裁剪比例", "PPO裁剪比例")
        self.add_rockx_property("gamma", float, 0.99, "折扣因子", "折扣因子")
    
    def _execute_logic(self, inputs):
        if not QLIB_AVAILABLE:
            self.set_status("failed", "Qlib not available")
            return False
        
        train_data = inputs.get("train_data")
        test_data = inputs.get("test_data")
        
        if train_data is None:
            self.set_status("failed", "No training data provided")
            return False
        
        try:
            # 创建PPO模型配置
            model_config = {
                "class": "PPOModel",
                "module_path": "qlib.contrib.model",
                "kwargs": {
                    "state_dim": self.get_rockx_property("state_dim"),
                    "action_dim": self.get_rockx_property("action_dim"),
                    "hidden_size": self.get_rockx_property("hidden_size"),
                    "learning_rate": self.get_rockx_property("learning_rate"),
                    "episodes": self.get_rockx_property("episodes"),
                    "clip_ratio": self.get_rockx_property("clip_ratio"),
                    "gamma": self.get_rockx_property("gamma")
                }
            }
            
            # 初始化模型
            model = init_instance_by_config(model_config)
            
            # 训练模型
            model.fit(train_data)
            
            # 预测
            predictions = None
            if test_data is not None:
                predictions = model.predict(test_data)
            
            # 评估模型
            metrics = self._evaluate_model(model, train_data, test_data)
            
            self.set_output("model", model)
            self.set_output("predictions", predictions)
            self.set_output("metrics", metrics)
            
            self.set_status("completed", "PPO model training completed")
            return True
            
        except Exception as e:
            logger.error(f"PPO model training failed: {e}")
            self.set_status("failed", f"PPO model training failed: {e}")
            return False