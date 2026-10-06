#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复工作流运行错误
解决LSTM模型、策略和回测的参数问题
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class WorkflowErrorFixer:
    """工作流错误修复器"""

    @staticmethod
    def fix_lstm_model_params(model_params_str: str) -> Dict[str, Any]:
        """修复LSTM模型参数类型问题"""
        try:
            # 解析原始参数
            if isinstance(model_params_str, str):
                model_params = json.loads(model_params_str)
            else:
                model_params = model_params_str or {}

            # 修复参数类型
            fixed_params = {}

            # 数值参数 - 确保是数字类型
            numeric_params = {
                'd_feat': int,
                'hidden_size': int,
                'num_layers': int,
                'dropout': float,
                'n_epochs': int,
                'lr': float,
                'early_stop': int,
                'batch_size': int,
                'n_jobs': int,
                'GPU': int
            }

            for param_name, param_type in numeric_params.items():
                if param_name in model_params:
                    value = model_params[param_name]
                    try:
                        if param_type == int:
                            fixed_params[param_name] = int(float(value))
                        else:
                            fixed_params[param_name] = param_type(value)
                    except (ValueError, TypeError):
                        # 使用默认值
                        defaults = {
                            'd_feat': 20,
                            'hidden_size': 64,
                            'num_layers': 2,
                            'dropout': 0.0,
                            'n_epochs': 200,
                            'lr': 0.001,
                            'early_stop': 10,
                            'batch_size': 800,
                            'n_jobs': 20,
                            'GPU': 0
                        }
                        fixed_params[param_name] = defaults.get(param_name, 0)
                        logger.warning(f"参数 {param_name} 类型转换失败，使用默认值: {fixed_params[param_name]}")

            # 字符串参数
            string_params = ['metric', 'loss', 'optimizer', 'loss_type']
            for param_name in string_params:
                if param_name in model_params:
                    fixed_params[param_name] = str(model_params[param_name])

            # 布尔参数
            bool_params = ['use_GPU']
            for param_name in bool_params:
                if param_name in model_params:
                    value = model_params[param_name]
                    if isinstance(value, str):
                        fixed_params[param_name] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        fixed_params[param_name] = bool(value)

            # 特殊处理
            if 'visible_GPU' in model_params:
                fixed_params['visible_GPU'] = int(model_params['visible_GPU']) if model_params['visible_GPU'] is not None else 0

            if 'seed' in model_params:
                seed_value = model_params['seed']
                if seed_value is None or seed_value == 'None':
                    fixed_params['seed'] = None
                else:
                    fixed_params['seed'] = int(seed_value)

            logger.info(f"✅ LSTM模型参数修复完成: {fixed_params}")
            return fixed_params

        except Exception as e:
            logger.error(f"❌ 修复LSTM模型参数失败: {e}")
            # 返回默认参数
            return {
                'd_feat': 20,
                'hidden_size': 64,
                'num_layers': 2,
                'dropout': 0.0,
                'n_epochs': 200,
                'lr': 0.001,
                'early_stop': 10,
                'batch_size': 800,
                'metric': 'loss',
                'loss': 'mse',
                'optimizer': 'adam',
                'loss_type': 'mse',
                'visible_GPU': 0,
                'use_GPU': True,
                'seed': None,
                'n_jobs': 20,
                'GPU': 0
            }

    @staticmethod
    def fix_model_config(model_class: str, model_params: Dict[str, Any]) -> Dict[str, Any]:
        """修复模型配置，添加必要的模块路径"""
        try:
            # 根据模型类型确定模块路径
            module_paths = {
                'LSTM': 'qlib.contrib.model.pytorch_lstm_ts',
                'LGBModel': 'qlib.contrib.model.gbdt',
                'XGBModel': 'qlib.contrib.model.gbdt',
                'CatBoostModel': 'qlib.contrib.model.gbdt',
                'LinearModel': 'qlib.contrib.model.linear',
                'GRU': 'qlib.contrib.model.rnn',
                'ALSTM': 'qlib.contrib.model.pytorch_alstm',
                'SFM': 'qlib.contrib.model.pytorch_sfm',
                'GATs': 'qlib.contrib.model.pytorch_gats',
                'Transformer': 'qlib.contrib.model.pytorch_transformer'
            }

            module_path = module_paths.get(model_class, 'qlib.contrib.model')

            # 构建完整的模型配置
            model_config = {
                'class': model_class,
                'module_path': module_path,
                'kwargs': model_params
            }

            logger.info(f"✅ 模型配置修复完成: {model_class} -> {module_path}")
            return model_config

        except Exception as e:
            logger.error(f"❌ 修复模型配置失败: {e}")
            return {
                'class': model_class,
                'module_path': 'qlib.contrib.model',
                'kwargs': model_params
            }

    @staticmethod
    def fix_strategy_config(strategy_class: str, strategy_params: Dict[str, Any]) -> Dict[str, Any]:
        """修复策略配置，添加必要的模块路径"""
        try:
            # 根据策略类型确定模块路径
            module_paths = {
                'TopkDropoutStrategy': 'qlib.contrib.strategy.signal_strategy',
                'TopkStrategy': 'qlib.contrib.strategy.signal_strategy',
                'WeightStrategy': 'qlib.contrib.strategy.weight_strategy',
                'TWAPStrategy': 'qlib.contrib.strategy.twap_strategy',
                'VWAPStrategy': 'qlib.contrib.strategy.vwap_strategy'
            }

            module_path = module_paths.get(strategy_class, 'qlib.contrib.strategy')

            # 构建完整的策略配置
            strategy_config = {
                'class': strategy_class,
                'module_path': module_path,
                'kwargs': strategy_params
            }

            logger.info(f"✅ 策略配置修复完成: {strategy_class} -> {module_path}")
            return strategy_config

        except Exception as e:
            logger.error(f"❌ 修复策略配置失败: {e}")
            return {
                'class': strategy_class,
                'module_path': 'qlib.contrib.strategy',
                'kwargs': strategy_params
            }

    @staticmethod
    def fix_backtest_config(backtest_params: Dict[str, Any]) -> Dict[str, Any]:
        """修复回测配置，添加必要的模块路径"""
        try:
            # 构建完整的回测配置
            backtest_config = {
                'class': 'Backtest',
                'module_path': 'qlib.backtest',
                'kwargs': backtest_params
            }

            logger.info(f"✅ 回测配置修复完成")
            return backtest_config

        except Exception as e:
            logger.error(f"❌ 修复回测配置失败: {e}")
            return {
                'class': 'Backtest',
                'module_path': 'qlib.backtest',
                'kwargs': backtest_params
            }

    @staticmethod
    def fix_workflow_node_data(node_data: Dict[str, Any]) -> Dict[str, Any]:
        """修复工作流节点数据"""
        try:
            node_type = node_data.get('type_', '')
            custom_data = node_data.get('custom', {})

            if node_type == 'qlib.core.model':
                # 修复模型节点
                model_class = custom_data.get('model_class', 'LGBModel')
                model_params_str = custom_data.get('model_params', '{}')

                # 修复参数
                fixed_params = WorkflowErrorFixer.fix_lstm_model_params(model_params_str)

                # 构建修复后的配置
                fixed_config = WorkflowErrorFixer.fix_model_config(model_class, fixed_params)

                # 更新节点数据
                node_data['custom']['model_class'] = model_class
                node_data['custom']['model_params'] = json.dumps(fixed_params)
                node_data['custom']['model_config'] = json.dumps(fixed_config)

                logger.info(f"✅ 模型节点修复完成: {model_class}")

            elif node_type == 'qlib.core.strategy':
                # 修复策略节点
                strategy_class = custom_data.get('strategy_class', 'TopkDropoutStrategy')
                strategy_params_str = custom_data.get('strategy_params', '{}')

                try:
                    strategy_params = json.loads(strategy_params_str) if strategy_params_str else {}
                except:
                    strategy_params = {}

                # 构建修复后的配置
                fixed_config = WorkflowErrorFixer.fix_strategy_config(strategy_class, strategy_params)

                # 更新节点数据
                node_data['custom']['strategy_class'] = strategy_class
                node_data['custom']['strategy_params'] = json.dumps(strategy_params)
                node_data['custom']['strategy_config'] = json.dumps(fixed_config)

                logger.info(f"✅ 策略节点修复完成: {strategy_class}")

            elif node_type == 'qlib.core.backtest':
                # 修复回测节点
                backtest_params = {
                    'start_time': custom_data.get('start_time', '2017-01-01'),
                    'end_time': custom_data.get('end_time', '2020-08-01'),
                    'account': custom_data.get('initial_capital', 1000000),
                    'benchmark': custom_data.get('benchmark', 'SH000300'),
                    'exchange_kwargs': {
                        'freq': 'day',
                        'limit_threshold': 0.095,
                        'deal_price': 'close',
                        'open_cost': 0.0005,
                        'close_cost': 0.0015,
                        'min_cost': 5
                    }
                }

                # 构建修复后的配置
                fixed_config = WorkflowErrorFixer.fix_backtest_config(backtest_params)

                # 更新节点数据
                node_data['custom']['backtest_config'] = json.dumps(fixed_config)

                logger.info(f"✅ 回测节点修复完成")

            return node_data

        except Exception as e:
            logger.error(f"❌ 修复工作流节点数据失败: {e}")
            return node_data


def test_error_fixes():
    """测试错误修复功能"""
    print("测试工作流错误修复功能...")

    # 测试LSTM模型参数修复
    print("\n1. 测试LSTM模型参数修复...")
    lstm_params_str = '{"d_feat": 20, "hidden_size": 64, "num_layers": 2, "dropout": 0.0, "n_epochs": 200, "lr": "1e-3", "early_stop": 10, "batch_size": 800, "metric": "loss", "loss": "mse", "n_jobs": 20, "GPU": 0}'
    fixed_params = WorkflowErrorFixer.fix_lstm_model_params(lstm_params_str)
    print(f"   原始参数: {lstm_params_str}")
    print(f"   修复后参数: {fixed_params}")

    # 测试模型配置修复
    print("\n2. 测试模型配置修复...")
    model_config = WorkflowErrorFixer.fix_model_config('LSTM', fixed_params)
    print(f"   模型配置: {model_config}")

    # 测试策略配置修复
    print("\n3. 测试策略配置修复...")
    strategy_params = {"signal": "<PRED>", "topk": 50, "n_drop": 5}
    strategy_config = WorkflowErrorFixer.fix_strategy_config('TopkDropoutStrategy', strategy_params)
    print(f"   策略配置: {strategy_config}")

    # 测试回测配置修复
    print("\n4. 测试回测配置修复...")
    backtest_params = {
        'start_time': '2017-01-01',
        'end_time': '2020-08-01',
        'account': 1000000,
        'benchmark': 'SH000300'
    }
    backtest_config = WorkflowErrorFixer.fix_backtest_config(backtest_params)
    print(f"   回测配置: {backtest_config}")

    print("\n错误修复功能测试完成")


if __name__ == "__main__":
    test_error_fixes()
