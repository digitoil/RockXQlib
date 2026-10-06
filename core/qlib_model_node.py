#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib模型节点基类
严格按照设计文档实现
"""

import os
import sys
import logging
import pickle
import joblib
from typing import Dict, Any, Optional, List, Union, Tuple
import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import cross_val_score

# Qlib imports
try:
    import qlib
    from qlib.data.dataset import DatasetH
    from qlib.model.base import Model
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

# 本模块既可能作为包内模块导入（core.qlib_model_node），
# 也可能被 nodes/* 以顶层模块方式导入（qlib_model_node），两种都要兼容。
try:
    from .qlib_base_node import QlibBaseNode
except ImportError:
    from qlib_base_node import QlibBaseNode

logger = logging.getLogger(__name__)

class QlibModelNode(QlibBaseNode):
    """模型节点基类"""
    
    def __init__(self):
        super().__init__()
        self._ml_model = None
        self._model_config = {}
        self._training_data = None
        self._test_data = None
        self._predictions = None
        self._evaluation_metrics = {}
        self._setup_model_properties()
    
    def _setup_model_properties(self):
        """设置模型相关属性"""
        # 模型配置
        self.set_property('model_type', 'linear')  # linear, tree, neural, ensemble
        self.set_property('model_name', 'LinearModel')
        self.set_property('model_params', {})
        self.set_property('random_state', 42)
        
        # 训练配置
        self.set_property('train_ratio', 0.7)
        self.set_property('validation_ratio', 0.15)
        self.set_property('test_ratio', 0.15)
        self.set_property('cross_validation', False)
        self.set_property('cv_folds', 5)
        
        # 特征配置
        self.set_property('feature_selection', False)
        self.set_property('feature_importance_threshold', 0.01)
        self.set_property('max_features', None)
        
        # 性能配置
        self.set_property('early_stopping', False)
        self.set_property('early_stopping_patience', 10)
        self.set_property('max_iterations', 1000)
        self.set_property('learning_rate', 0.01)
        
        # 评估配置
        self.set_property('evaluation_metrics', ['mse', 'mae', 'r2'])
        self.set_property('save_model', True)
        self.set_property('model_path', './models')
    
    def _validate_specific_config(self) -> bool:
        """验证模型节点特定配置"""
        try:
            # 验证模型类型
            model_type = self.get_property('model_type')
            if model_type not in ['linear', 'tree', 'neural', 'ensemble']:
                self._set_status("failed", f"不支持的模型类型: {model_type}")
                return False
            
            # 验证训练比例
            train_ratio = self.get_property('train_ratio', 0.7)
            val_ratio = self.get_property('validation_ratio', 0.15)
            test_ratio = self.get_property('test_ratio', 0.15)
            
            if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
                self._set_status("failed", "训练、验证、测试比例之和必须为1")
                return False
            
            if not (0 < train_ratio < 1 and 0 <= val_ratio < 1 and 0 <= test_ratio < 1):
                self._set_status("failed", "训练、验证、测试比例必须在(0,1)范围内")
                return False
            
            # 验证交叉验证配置
            if self.get_property('cross_validation', False):
                cv_folds = self.get_property('cv_folds', 5)
                if not isinstance(cv_folds, int) or cv_folds < 2:
                    self._set_status("failed", "交叉验证折数必须大于等于2")
                    return False
            
            # 验证学习率
            learning_rate = self.get_property('learning_rate', 0.01)
            if not isinstance(learning_rate, (int, float)) or learning_rate <= 0:
                self._set_status("failed", "学习率必须大于0")
                return False
            
            # 验证最大迭代次数
            max_iterations = self.get_property('max_iterations', 1000)
            if not isinstance(max_iterations, int) or max_iterations <= 0:
                self._set_status("failed", "最大迭代次数必须大于0")
                return False
            
            return True
            
        except Exception as e:
            self._set_status("failed", f"模型节点配置验证失败: {e}")
            return False
    
    def _prepare_specific_execution(self) -> bool:
        """准备模型节点特定执行环境"""
        try:
            # 创建模型目录
            model_path = self.get_property('model_path', './models')
            os.makedirs(model_path, exist_ok=True)
            
            # 初始化模型
            if not self._initialize_model():
                return False
            
            return True
            
        except Exception as e:
            self._set_status("failed", f"模型节点执行准备失败: {e}")
            return False
    
    def _initialize_model(self) -> bool:
        """初始化模型"""
        try:
            model_type = self.get_property('model_type')
            model_name = self.get_property('model_name')
            model_params = self.get_property('model_params', {})
            
            if model_type == 'linear':
                self._ml_model = self._create_linear_model(model_name, model_params)
            elif model_type == 'tree':
                self._ml_model = self._create_tree_model(model_name, model_params)
            elif model_type == 'neural':
                self._ml_model = self._create_neural_model(model_name, model_params)
            elif model_type == 'ensemble':
                self._ml_model = self._create_ensemble_model(model_name, model_params)
            else:
                self._set_status("failed", f"不支持的模型类型: {model_type}")
                return False
            
            if self._ml_model is None:
                self._set_status("failed", "模型初始化失败")
                return False
            
            logger.info(f"模型初始化成功: {model_name}")
            return True
            
        except Exception as e:
            self._set_status("failed", f"模型初始化失败: {e}")
            return False
    
    def _create_linear_model(self, model_name: str, params: Dict) -> Any:
        """创建线性模型"""
        try:
            if QLIB_AVAILABLE and model_name in ['LinearModel', 'RidgeModel', 'LassoModel']:
                # 使用Qlib的线性模型
                from qlib.contrib.model.linear import LinearModel
                
                model_config = {
                    'class': model_name,
                    'module_path': 'qlib.contrib.model.linear',
                    'kwargs': params
                }
                
                return init_instance_by_config(model_config)
            else:
                # 使用sklearn的线性模型
                from sklearn.linear_model import LinearRegression, Ridge, Lasso
                
                if model_name == 'LinearModel' or model_name == 'LinearRegression':
                    return LinearRegression(**params)
                elif model_name == 'RidgeModel' or model_name == 'Ridge':
                    return Ridge(**params)
                elif model_name == 'LassoModel' or model_name == 'Lasso':
                    return Lasso(**params)
                else:
                    return LinearRegression(**params)
                    
        except Exception as e:
            logger.error(f"线性模型创建失败: {e}")
            return None
    
    def _create_tree_model(self, model_name: str, params: Dict) -> Any:
        """创建树模型"""
        try:
            if QLIB_AVAILABLE and model_name in ['LGBModel', 'XGBModel', 'CatBoostModel']:
                # 使用Qlib的树模型
                if model_name == 'LGBModel':
                    from qlib.contrib.model.gbdt import LGBModel
                    model_config = {
                        'class': 'LGBModel',
                        'module_path': 'qlib.contrib.model.gbdt',
                        'kwargs': params
                    }
                elif model_name == 'XGBModel':
                    from qlib.contrib.model.xgboost import XGBModel
                    model_config = {
                        'class': 'XGBModel',
                        'module_path': 'qlib.contrib.model.xgboost',
                        'kwargs': params
                    }
                elif model_name == 'CatBoostModel':
                    from qlib.contrib.model.catboost_model import CatBoostModel
                    model_config = {
                        'class': 'CatBoostModel',
                        'module_path': 'qlib.contrib.model.catboost_model',
                        'kwargs': params
                    }
                
                return init_instance_by_config(model_config)
            else:
                # 使用sklearn的树模型
                from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
                from sklearn.tree import DecisionTreeRegressor
                
                if model_name == 'RandomForest':
                    return RandomForestRegressor(**params)
                elif model_name == 'GradientBoosting':
                    return GradientBoostingRegressor(**params)
                elif model_name == 'DecisionTree':
                    return DecisionTreeRegressor(**params)
                else:
                    return RandomForestRegressor(**params)
                    
        except Exception as e:
            logger.error(f"树模型创建失败: {e}")
            return None
    
    def _create_neural_model(self, model_name: str, params: Dict) -> Any:
        """创建神经网络模型"""
        try:
            # 使用sklearn的神经网络模型
            from sklearn.neural_network import MLPRegressor
            
            if model_name == 'MLPRegressor':
                return MLPRegressor(**params)
            else:
                return MLPRegressor(**params)
                
        except Exception as e:
            logger.error(f"神经网络模型创建失败: {e}")
            return None
    
    def _create_ensemble_model(self, model_name: str, params: Dict) -> Any:
        """创建集成模型"""
        try:
            from sklearn.ensemble import VotingRegressor, BaggingRegressor, AdaBoostRegressor
            
            if model_name == 'VotingRegressor':
                return VotingRegressor(**params)
            elif model_name == 'BaggingRegressor':
                return BaggingRegressor(**params)
            elif model_name == 'AdaBoostRegressor':
                return AdaBoostRegressor(**params)
            else:
                return VotingRegressor(**params)
                
        except Exception as e:
            logger.error(f"集成模型创建失败: {e}")
            return None
    
    def train(self, train_data: Any, config: Dict) -> Any:
        """训练模型"""
        try:
            if self._ml_model is None:
                self._set_status("failed", "模型未初始化")
                return None
            
            # 准备训练数据
            X_train, y_train = self._prepare_training_data(train_data)
            
            if X_train is None or y_train is None:
                self._set_status("failed", "训练数据准备失败")
                return None
            
            # 特征选择
            if self.get_property('feature_selection', False):
                X_train = self._select_features(X_train, y_train)
            
            # 训练模型
            if hasattr(self._ml_model, 'fit'):
                # sklearn模型
                self._ml_model.fit(X_train, y_train)
            elif QLIB_AVAILABLE and hasattr(self._ml_model, 'fit'):
                # Qlib模型
                if isinstance(train_data, DatasetH):
                    self._ml_model.fit(train_data)
                else:
                    # 创建临时数据集
                    dataset = self._create_dataset(X_train, y_train)
                    self._ml_model.fit(dataset)
            else:
                self._set_status("failed", "模型不支持训练")
                return None
            
            # 保存训练数据
            self._training_data = train_data
            
            # 交叉验证
            if self.get_property('cross_validation', False):
                self._perform_cross_validation(X_train, y_train)
            
            self._set_status("success", "模型训练完成")
            return self._ml_model
            
        except Exception as e:
            self._set_status("failed", f"模型训练失败: {e}")
            logger.error(f"模型训练失败: {e}")
            return None
    
    def _prepare_training_data(self, data: Any) -> Tuple[Any, Any]:
        """准备训练数据"""
        try:
            if isinstance(data, pd.DataFrame):
                # 假设最后一列是目标变量
                X = data.iloc[:, :-1]
                y = data.iloc[:, -1]
                return X, y
            elif isinstance(data, tuple) and len(data) == 2:
                # 已经是(X, y)格式
                return data
            elif QLIB_AVAILABLE and isinstance(data, DatasetH):
                # Qlib数据集
                return data, None
            else:
                self._set_status("failed", f"不支持的数据格式: {type(data)}")
                return None, None
                
        except Exception as e:
            self._set_status("failed", f"训练数据准备失败: {e}")
            return None, None
    
    def _select_features(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """特征选择"""
        try:
            from sklearn.feature_selection import SelectKBest, f_regression
            
            max_features = self.get_property('max_features')
            threshold = self.get_property('feature_importance_threshold', 0.01)
            
            if max_features is not None:
                selector = SelectKBest(f_regression, k=min(max_features, X.shape[1]))
                X_selected = selector.fit_transform(X, y)
                selected_features = X.columns[selector.get_support()]
                return pd.DataFrame(X_selected, columns=selected_features, index=X.index)
            else:
                # 基于重要性阈值选择特征
                selector = SelectKBest(f_regression, k='all')
                selector.fit(X, y)
                scores = selector.scores_
                selected_mask = scores > threshold
                return X.loc[:, selected_mask]
                
        except Exception as e:
            logger.warning(f"特征选择失败: {e}")
            return X
    
    def _create_dataset(self, X: pd.DataFrame, y: pd.Series) -> Any:
        """创建Qlib数据集"""
        try:
            if not QLIB_AVAILABLE:
                return None
            
            # 这里需要根据Qlib的要求创建数据集
            # 简化实现，实际需要更复杂的逻辑
            return None
            
        except Exception as e:
            logger.warning(f"创建Qlib数据集失败: {e}")
            return None
    
    def _perform_cross_validation(self, X: pd.DataFrame, y: pd.Series):
        """执行交叉验证"""
        try:
            cv_folds = self.get_property('cv_folds', 5)
            scoring = 'neg_mean_squared_error'
            
            scores = cross_val_score(self._ml_model, X, y, cv=cv_folds, scoring=scoring)
            
            self._evaluation_metrics['cv_scores'] = scores.tolist()
            self._evaluation_metrics['cv_mean'] = scores.mean()
            self._evaluation_metrics['cv_std'] = scores.std()
            
            logger.info(f"交叉验证完成: {scores.mean():.4f} (+/- {scores.std() * 2:.4f})")
            
        except Exception as e:
            logger.warning(f"交叉验证失败: {e}")
    
    def predict(self, model: Any, data: Any) -> Any:
        """模型预测"""
        try:
            if model is None:
                model = self._ml_model
            
            if model is None:
                self._set_status("failed", "模型未初始化")
                return None
            
            # 准备预测数据
            X_pred = self._prepare_prediction_data(data)
            
            if X_pred is None:
                self._set_status("failed", "预测数据准备失败")
                return None
            
            # 执行预测
            if hasattr(model, 'predict'):
                predictions = model.predict(X_pred)
            elif QLIB_AVAILABLE and hasattr(model, 'predict'):
                # Qlib模型预测
                if isinstance(data, DatasetH):
                    predictions = model.predict(data)
                else:
                    predictions = model.predict(X_pred)
            else:
                self._set_status("failed", "模型不支持预测")
                return None
            
            # 保存预测结果
            self._predictions = predictions
            self._test_data = data
            
            self._set_status("success", f"预测完成: {len(predictions)} 个样本")
            return predictions
            
        except Exception as e:
            self._set_status("failed", f"模型预测失败: {e}")
            logger.error(f"模型预测失败: {e}")
            return None
    
    def _prepare_prediction_data(self, data: Any) -> Any:
        """准备预测数据"""
        try:
            if isinstance(data, pd.DataFrame):
                return data
            elif isinstance(data, tuple) and len(data) == 2:
                return data[0]  # 返回X部分
            elif QLIB_AVAILABLE and isinstance(data, DatasetH):
                return data
            else:
                self._set_status("failed", f"不支持的预测数据格式: {type(data)}")
                return None
                
        except Exception as e:
            self._set_status("failed", f"预测数据准备失败: {e}")
            return None
    
    def evaluate(self, model: Any, test_data: Any) -> Dict:
        """模型评估"""
        try:
            if model is None:
                model = self._ml_model
            
            if model is None:
                self._set_status("failed", "模型未初始化")
                return {}
            
            # 获取预测结果
            if self._predictions is not None:
                predictions = self._predictions
            else:
                predictions = self.predict(model, test_data)
                if predictions is None:
                    return {}
            
            # 获取真实标签
            if isinstance(test_data, pd.DataFrame):
                y_true = test_data.iloc[:, -1]
            elif isinstance(test_data, tuple) and len(test_data) == 2:
                y_true = test_data[1]
            else:
                self._set_status("failed", "无法获取真实标签")
                return {}
            
            # 计算评估指标
            metrics = {}
            evaluation_metrics = self.get_property('evaluation_metrics', ['mse', 'mae', 'r2'])
            
            if 'mse' in evaluation_metrics:
                metrics['mse'] = mean_squared_error(y_true, predictions)
            
            if 'mae' in evaluation_metrics:
                metrics['mae'] = mean_absolute_error(y_true, predictions)
            
            if 'r2' in evaluation_metrics:
                metrics['r2'] = r2_score(y_true, predictions)
            
            if 'rmse' in evaluation_metrics:
                metrics['rmse'] = np.sqrt(metrics.get('mse', 0))
            
            # 保存评估结果
            self._evaluation_metrics.update(metrics)
            
            # 保存模型
            if self.get_property('save_model', True):
                self._save_model(model)
            
            self._set_status("success", f"模型评估完成: {metrics}")
            return metrics
            
        except Exception as e:
            self._set_status("failed", f"模型评估失败: {e}")
            logger.error(f"模型评估失败: {e}")
            return {}
    
    def _save_model(self, model: Any):
        """保存模型"""
        try:
            model_path = self.get_property('model_path', './models')
            model_name = f"{self.__class__.__name__}_{self._node_id}.pkl"
            full_path = os.path.join(model_path, model_name)
            
            # 保存模型
            joblib.dump(model, full_path)
            
            # 保存元数据
            metadata = {
                'node_id': self._node_id,
                'model_type': self.get_property('model_type'),
                'model_name': self.get_property('model_name'),
                'model_params': self.get_property('model_params'),
                'evaluation_metrics': self._evaluation_metrics,
                'training_time': self._execution_time
            }
            
            metadata_path = full_path.replace('.pkl', '_metadata.json')
            import json
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"模型已保存: {full_path}")
            
        except Exception as e:
            logger.warning(f"模型保存失败: {e}")
    
    def load_model(self, model_path: str) -> Any:
        """加载模型"""
        try:
            if not os.path.exists(model_path):
                self._set_status("failed", f"模型文件不存在: {model_path}")
                return None
            
            # 加载模型
            model = joblib.load(model_path)
            self._ml_model = model
            
            # 加载元数据
            metadata_path = model_path.replace('.pkl', '_metadata.json')
            if os.path.exists(metadata_path):
                import json
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    self._evaluation_metrics = metadata.get('evaluation_metrics', {})
            
            self._set_status("success", f"模型加载成功: {model_path}")
            return model
            
        except Exception as e:
            self._set_status("failed", f"模型加载失败: {e}")
            logger.error(f"模型加载失败: {e}")
            return None
    
    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        try:
            if self._ml_model is None:
                return {}
            
            if hasattr(self._ml_model, 'feature_importances_'):
                # 树模型的特征重要性
                if hasattr(self._ml_model, 'feature_names_in_'):
                    feature_names = self._ml_model.feature_names_in_
                else:
                    feature_names = [f'feature_{i}' for i in range(len(self._ml_model.feature_importances_))]
                
                return dict(zip(feature_names, self._ml_model.feature_importances_))
            elif hasattr(self._ml_model, 'coef_'):
                # 线性模型的系数
                if hasattr(self._ml_model, 'feature_names_in_'):
                    feature_names = self._ml_model.feature_names_in_
                else:
                    feature_names = [f'feature_{i}' for i in range(len(self._ml_model.coef_))]
                
                return dict(zip(feature_names, abs(self._ml_model.coef_)))
            else:
                logger.warning("模型不支持特征重要性")
                return {}
                
        except Exception as e:
            logger.warning(f"获取特征重要性失败: {e}")
            return {}
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            'model_type': self.get_property('model_type'),
            'model_name': self.get_property('model_name'),
            'model_params': self.get_property('model_params'),
            'evaluation_metrics': self._evaluation_metrics,
            'feature_importance': self.get_feature_importance(),
            'training_time': self._execution_time,
            'is_trained': self._ml_model is not None
        }
    
    def _cleanup_specific(self):
        """清理模型节点特定资源"""
        try:
            # 清理模型
            self._ml_model = None
            
            # 清理数据
            self._training_data = None
            self._test_data = None
            self._predictions = None
            
            # 清理评估指标
            self._evaluation_metrics.clear()
            
        except Exception as e:
            logger.warning(f"模型节点清理失败: {e}")
