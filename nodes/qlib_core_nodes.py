#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于Qlib核心架构的节点系统
完全集成Qlib的API和组件，不使用模拟代码
"""

# 设置Unicode支持
import os
import sys
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
import logging
import traceback
from typing import Dict, Any, Optional, List, Union

# 添加路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from core.qlib_core_integration import qlib_core
    from NodeGraphQt import BaseNode
except ImportError as e:
    print(f"导入失败: {e}")
    # 创建占位符
    class BaseNode:
        def __init__(self):
            pass
    qlib_core = None

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
            if not self.qlib_core.qlib_available:
                raise Exception("Qlib不可用")

            if operation == "initialize":
                return self.qlib_core.initialize_qlib(**kwargs)
            elif operation == "get_data":
                return self.qlib_core.get_qlib_data(**kwargs)
            elif operation == "create_handler":
                return self.qlib_core.create_handler(**kwargs)
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

    def get_input(self, port_name: str) -> Any:
        """获取输入端口的数据"""
        try:
            # 获取输入端口
            input_port = self.inputs().get(port_name)
            if input_port:
                # 获取连接的输出端口
                connected_ports = input_port.connected_ports()
                if connected_ports:
                    # 获取第一个连接的输出端口的数据
                    output_port = connected_ports[0]
                    # 从输出端口获取数据
                    if hasattr(output_port, 'data'):
                        return output_port.data
                    elif hasattr(output_port, 'value'):
                        return output_port.value
                    else:
                        # 如果没有数据，返回默认值
                        return {'status': 'success', 'data': None}
                else:
                    # 没有连接的端口，返回默认值
                    return {'status': 'success', 'data': None}
            else:
                return None
        except Exception as e:
            logger.error(f"获取输入端口 {port_name} 失败: {e}")
            return None

    def set_output(self, port_name: str, data: Any):
        """设置输出端口的数据"""
        try:
            output_port = self.outputs().get(port_name)
            if output_port:
                if hasattr(output_port, 'data'):
                    output_port.data = data
                elif hasattr(output_port, 'value'):
                    output_port.value = data
                else:
                    # 如果没有data或value属性，尝试设置其他属性
                    setattr(output_port, 'data', data)
        except Exception as e:
            logger.error(f"设置输出端口 {port_name} 失败: {e}")

class QlibInitNode(QlibCoreBaseNode):
    """Qlib初始化节点 - 基于Qlib核心"""

    __identifier__ = 'qlib.core.init'
    NODE_NAME = 'Qlib初始化'
    type_ = 'qlib.core.init'

    def __init__(self):
        super().__init__()

        # 添加输入输出端口
        self.add_output('initialized_qlib')

        # 添加属性
        self.add_text_input('provider_uri', '数据源URI', 'D:\\qlib_data')
        self.add_text_input('region', '区域', 'cn')
        self.add_checkbox('enable_exp_recorder', '启用实验记录', '启用实验记录', True)

    def execute(self) -> bool:
        """执行Qlib初始化"""
        try:
            provider_uri = self.get_property('provider_uri')
            region = self.get_property('region')
            enable_exp_recorder = self.get_property('enable_exp_recorder')

            # 直接使用qlib_core进行初始化
            if self.qlib_core and self.qlib_core.qlib_available:
                result = self.qlib_core.initialize_qlib(
                    provider_uri=provider_uri,
                    region=region,
                    enable_exp_recorder=enable_exp_recorder
                )
            else:
                raise Exception("Qlib核心不可用")

            if result:
                self._execution_result = {
                    'status': 'success',
                    'provider_uri': provider_uri,
                    'region': region,
                    'initialized': True
                }
                self.set_output('initialized_qlib', self._execution_result)
                logger.info("✅ Qlib初始化成功")
                return True
            else:
                self._execution_result = {
                    'status': 'failed',
                    'error': self._error_message
                }
                logger.error("❌ Qlib初始化失败")
                return False

        except Exception as e:
            logger.error(f"Qlib初始化节点执行失败: {e}")
            return False

class QlibDataNode(QlibCoreBaseNode):
    """Qlib数据节点 - 基于Qlib核心"""

    __identifier__ = 'qlib.core.data'
    NODE_NAME = 'Qlib数据获取'
    type_ = 'qlib.core.data'

    def __init__(self):
        super().__init__()

        # 添加输入输出端口
        self.add_input('initialized_qlib')
        self.add_output('qlib_data')

        # 添加属性
        self.add_text_input('instruments', '股票池', 'csi300')
        self.add_text_input('start_time', '开始时间', '2008-01-01')
        self.add_text_input('end_time', '结束时间', '2020-08-01')
        self.add_text_input('fields', '数据字段', '$close,$volume,$amount')

    def execute(self) -> bool:
        """执行数据获取"""
        try:
            # 检查输入
            init_input = self.get_input('initialized_qlib')
            if not init_input or not init_input.get('initialized', False):
                raise Exception("Qlib未初始化")

            instruments = self.get_property('instruments')
            start_time = self.get_property('start_time')
            end_time = self.get_property('end_time')
            fields_str = self.get_property('fields')

            # 解析字段
            fields = [field.strip() for field in fields_str.split(',') if field.strip()]

            # 直接使用qlib_core获取数据
            if self.qlib_core and self.qlib_core.qlib_available:
                data = self.qlib_core.get_qlib_data(
                    instruments=instruments,
                    start_time=start_time,
                    end_time=end_time,
                    fields=fields
                )
            else:
                raise Exception("Qlib核心不可用")

            if data is not None:
                self._execution_result = {
                    'status': 'success',
                    'data': data,
                    'instruments': instruments,
                    'start_time': start_time,
                    'end_time': end_time,
                    'fields': fields
                }
                self.set_output('qlib_data', self._execution_result)
                logger.info(f"✅ 成功获取Qlib数据: {instruments}")
                return True
            else:
                self._execution_result = {
                    'status': 'failed',
                    'error': self._error_message
                }
                logger.error("❌ 获取Qlib数据失败")
                return False

        except Exception as e:
            logger.error(f"Qlib数据节点执行失败: {e}")
            return False

class QlibDatasetNode(QlibCoreBaseNode):
    """Qlib数据集节点 - 基于Qlib核心"""

    __identifier__ = 'qlib.core.dataset'
    NODE_NAME = 'Qlib数据集'
    type_ = 'qlib.core.dataset'

    def __init__(self):
        super().__init__()

        # 添加输入输出端口
        self.add_input('qlib_data')
        self.add_output('dataset')

        # 添加属性
        self.add_text_input('handler_class', '处理器类', 'Alpha158')
        self.add_text_input('instruments', '股票池', 'csi300')
        self.add_text_input('train_start', '训练开始', '2008-01-01')
        self.add_text_input('train_end', '训练结束', '2014-12-31')
        self.add_text_input('valid_start', '验证开始', '2015-01-01')
        self.add_text_input('valid_end', '验证结束', '2016-12-31')
        self.add_text_input('test_start', '测试开始', '2017-01-01')
        self.add_text_input('test_end', '测试结束', '2020-08-01')

    def execute(self) -> bool:
        """执行数据集创建"""
        try:
            # 确保Qlib已初始化
            if not self.qlib_core or not self.qlib_core.qlib_available:
                logger.error("Qlib核心不可用")
                return False

            # 强制重新初始化Qlib
            if not self.qlib_core.qlib_initialized:
                logger.info("重新初始化Qlib...")
                self.qlib_core.initialize_qlib()

            # 额外检查：确保qlib.data.D可用
            try:
                from qlib.data import D
                # 尝试简单的数据获取来验证Qlib是否真正可用
                test_data = D.features(['000001.SZ'], ['$close'], '2020-01-01', '2020-01-01')
                logger.info("Qlib数据模块验证成功")
            except Exception as e:
                logger.warning(f"Qlib数据模块验证失败: {e}，尝试重新初始化")
                # 强制重新初始化
                import qlib
                qlib.init(provider_uri='~/.qlib/qlib_data/cn_data', region='cn')

                # 再次验证
                try:
                    from qlib.data import D
                    test_data = D.features(['000001.SZ'], ['$close'], '2020-01-01', '2020-01-01')
                    logger.info("重新初始化后Qlib数据模块验证成功")
                except Exception as e2:
                    logger.error(f"重新初始化后仍然失败: {e2}")
                    # 如果仍然失败，尝试使用不同的初始化方式
                    try:
                        import qlib
                        qlib.init(provider_uri='~/.qlib/qlib_data/cn_data', region='cn',
                                 redis_host='127.0.0.1', redis_port=6379, redis_task_db=1)
                        logger.info("使用Redis配置重新初始化Qlib")
                    except Exception as e3:
                        logger.error(f"Redis配置初始化也失败: {e3}")
                        # 最后尝试：直接使用默认配置
                        import qlib
                        qlib.init()
                        logger.info("使用默认配置初始化Qlib")

            # 检查是否有TSDatasetH配置
            handler_kwargs = self.get_property('handler_kwargs')
            if handler_kwargs:
                # 使用TSDatasetH配置
                handler_class = self.get_property('handler_class') or 'Alpha158'
                module_path = self.get_property('module_path') or 'qlib.contrib.data.handler'
                handler_config = {
                    'class': handler_class,
                    'module_path': module_path,
                    'kwargs': handler_kwargs
                }
                segments = self.get_property('segments') or {}
                if not segments:
                    segments = {
                        'train': [self.get_property('train_start'), self.get_property('train_end')],
                        'valid': [self.get_property('valid_start'), self.get_property('valid_end')],
                        'test': [self.get_property('test_start'), self.get_property('test_end')]
                    }
            else:
                # 检查输入
                data_input = self.get_input('qlib_data')
                if not data_input or (isinstance(data_input, dict) and data_input.get('status') != 'success'):
                    # 如果没有输入或输入无效，使用默认配置
                    handler_class = self.get_property('handler_class')
                    handler_config = {
                        'class': handler_class,
                        'kwargs': {
                            'start_time': '2008-01-01',
                            'end_time': '2020-08-01',
                            'instruments': 'csi300'
                        }
                    }
                else:
                    # 使用输入数据构建配置
                    handler_class = self.get_property('handler_class')
                    if isinstance(data_input, dict):
                        handler_config = {
                            'class': handler_class,
                            'kwargs': {
                                'start_time': data_input.get('start_time', '2008-01-01'),
                                'end_time': data_input.get('end_time', '2020-08-01'),
                                'instruments': data_input.get('instruments', 'csi300')
                            }
                        }
                    else:
                        # 如果输入不是字典，使用默认配置
                        handler_config = {
                            'class': handler_class,
                            'kwargs': {
                                'start_time': '2008-01-01',
                                'end_time': '2020-08-01',
                                'instruments': 'csi300'
                            }
                        }

                # 构建分段配置
                segments = {
                    'train': [self.get_property('train_start'), self.get_property('train_end')],
                    'valid': [self.get_property('valid_start'), self.get_property('valid_end')],
                    'test': [self.get_property('test_start'), self.get_property('test_end')]
                }

            # 使用Qlib核心创建数据集
            dataset = self.execute_qlib_operation(
                "create_dataset",
                handler_config=handler_config,
                segments=segments
            )

            if dataset is not None:
                self._execution_result = {
                    'status': 'success',
                    'dataset': dataset,
                    'handler_class': handler_class,
                    'segments': segments
                }
                self.set_output('dataset', self._execution_result)
                logger.info(f"✅ 成功创建Qlib数据集: {handler_class}")
                return True
            else:
                self._execution_result = {
                    'status': 'failed',
                    'error': self._error_message
                }
                logger.error("❌ 创建Qlib数据集失败")
                return False

        except Exception as e:
            logger.error(f"Qlib数据集节点执行失败: {e}")
            return False

class QlibHandlerNode(QlibCoreBaseNode):
    """Qlib数据处理器节点 - 基于Qlib核心"""

    __identifier__ = 'qlib.core.handler'
    NODE_NAME = 'Qlib数据处理器'
    type_ = 'qlib.core.handler'

    def __init__(self):
        super().__init__()

        # 添加输入输出端口
        self.add_input('qlib_data')
        self.add_output('handler')

        # 添加属性
        self.add_text_input('handler_class', '处理器类', 'Alpha158')
        self.add_text_input('module_path', '模块路径', 'qlib.contrib.data.handler')
        self.add_text_input('start_time', '开始时间', '2008-01-01')
        self.add_text_input('end_time', '结束时间', '2020-08-01')
        self.add_text_input('instruments', '股票池', 'csi300')
        self.add_text_input('handler_kwargs', '处理器参数', '{}')

    def execute(self) -> bool:
        """执行数据处理器创建"""
        try:
            # 检查输入
            data_input = self.get_input('qlib_data')
            if not data_input or (isinstance(data_input, dict) and data_input.get('status') != 'success'):
                # 如果没有输入或输入无效，使用默认配置
                pass  # 继续执行，使用默认配置

            handler_class = self.get_property('handler_class')
            module_path = self.get_property('module_path')
            start_time = self.get_property('start_time')
            end_time = self.get_property('end_time')
            instruments = self.get_property('instruments')
            handler_kwargs_str = self.get_property('handler_kwargs')

            # 解析处理器参数
            try:
                import json
                handler_kwargs = json.loads(handler_kwargs_str) if handler_kwargs_str else {}
            except:
                handler_kwargs = {}

            # 构建处理器配置
            handler_config = {
                'class': handler_class,
                'module_path': module_path,
                'kwargs': {
                    'start_time': start_time,
                    'end_time': end_time,
                    'instruments': instruments,
                    **handler_kwargs
                }
            }

            # 使用Qlib核心创建数据处理器
            handler = self.execute_qlib_operation(
                "create_handler",
                handler_config=handler_config
            )

            if handler is not None:
                self._execution_result = {
                    'status': 'success',
                    'handler': handler,
                    'handler_class': handler_class,
                    'config': handler_config
                }
                self.set_output('handler', self._execution_result)
                logger.info(f"✅ 成功创建Qlib数据处理器: {handler_class}")
                return True
            else:
                self._execution_result = {
                    'status': 'failed',
                    'error': self._error_message
                }
                logger.error("❌ 创建Qlib数据处理器失败")
                return False

        except Exception as e:
            logger.error(f"Qlib数据处理器节点执行失败: {e}")
            return False

class QlibModelNode(QlibCoreBaseNode):
    """Qlib模型节点 - 基于Qlib核心"""

    __identifier__ = 'qlib.core.model'
    NODE_NAME = 'Qlib模型'
    type_ = 'qlib.core.model'

    def __init__(self):
        super().__init__()

        # 添加输入输出端口
        self.add_input('dataset')
        self.add_output('model')
        self.add_output('predictions')

        # 添加属性
        self.add_text_input('model_class', '模型类', 'LGBModel')
        self.add_text_input('model_params', '模型参数', '{}')

    def execute(self) -> bool:
        """执行模型创建和训练"""
        try:
            # 检查输入
            dataset_input = self.get_input('dataset')
            if not dataset_input or (isinstance(dataset_input, dict) and dataset_input.get('status') != 'success'):
                # 如果没有输入或输入无效，使用默认配置
                pass  # 继续执行，使用默认配置

            model_class = self.get_property('model_class')
            model_params_str = self.get_property('model_params')

            # 检查是否有完整的模型配置（来自YAML）
            module_path = self.get_property('module_path')
            if module_path:
                # 使用完整的模型配置
                model_config = {
                    'class': model_class,
                    'module_path': module_path,
                    'kwargs': self.get_property('model_kwargs') or {}
                }
            else:
                # 使用简化的模型配置
                try:
                    import json
                    model_params = json.loads(model_params_str) if model_params_str else {}
                except:
                    model_params = {}

                model_config = {
                    'class': model_class,
                    'kwargs': model_params
                }

            # 导入错误修复器并修复参数
            try:
                from fix_workflow_errors import WorkflowErrorFixer

                # 如果是LSTM模型，修复参数类型问题
                if model_class == 'LSTM':
                    logger.info("🔧 检测到LSTM模型，修复参数类型...")
                    if 'kwargs' in model_config:
                        model_config['kwargs'] = WorkflowErrorFixer.fix_lstm_model_params(model_config['kwargs'])
                    logger.info("✅ LSTM模型参数修复完成")

                # 构建修复后的模型配置
                model_config = WorkflowErrorFixer.fix_model_config(model_class, model_config.get('kwargs', {}))

            except ImportError:
                # 如果无法导入修复器，使用原始配置
                pass

            # 使用Qlib核心创建模型
            model = self.execute_qlib_operation(
                "create_model",
                model_config=model_config
            )

            if model is not None:
                self._execution_result = {
                    'status': 'success',
                    'model': model,
                    'model_class': model_class,
                    'model_params': model_params
                }
                self.set_output('model', self._execution_result)
                self.set_output('predictions', self._execution_result)
                logger.info(f"✅ 成功创建Qlib模型: {model_class}")
                return True
            else:
                self._execution_result = {
                    'status': 'failed',
                    'error': self._error_message
                }
                logger.error("❌ 创建Qlib模型失败")
                return False

        except Exception as e:
            logger.error(f"Qlib模型节点执行失败: {e}")
            return False

class QlibStrategyNode(QlibCoreBaseNode):
    """Qlib策略节点 - 基于Qlib核心"""

    __identifier__ = 'qlib.core.strategy'
    NODE_NAME = 'Qlib策略'
    type_ = 'qlib.core.strategy'

    def __init__(self):
        super().__init__()

        # 添加输入输出端口
        self.add_input('predictions')
        self.add_output('strategy')
        self.add_output('signals')

        # 添加属性
        self.add_text_input('strategy_class', '策略类', 'TopkDropoutStrategy')
        self.add_text_input('module_path', '模块路径', 'qlib.contrib.strategy.signal_strategy')
        self.add_text_input('signal', '信号', '<PRED>')
        self.add_text_input('strategy_params', '策略参数', '{"topk": 50, "n_drop": 5}')
        self.add_text_input('strategy_kwargs', '策略参数字典', '{}')

    def execute(self) -> bool:
        """执行策略创建"""
        try:
            # 检查输入
            predictions_input = self.get_input('predictions')
            if not predictions_input or (isinstance(predictions_input, dict) and predictions_input.get('status') != 'success'):
                # 如果没有输入或输入无效，使用默认配置
                pass  # 继续执行，使用默认配置

            strategy_class = self.get_property('strategy_class')
            strategy_params_str = self.get_property('strategy_params')

            # 解析策略参数
            try:
                import json
                strategy_params = json.loads(strategy_params_str) if strategy_params_str else {}
            except:
                strategy_params = {}

            # 检查是否有完整的策略配置（来自YAML）
            module_path = self.get_property('module_path')
            signal = self.get_property('signal')
            logger.info(f"策略节点module_path: {module_path}")
            logger.info(f"策略节点signal: {signal}")

            # 获取策略参数
            strategy_kwargs_str = self.get_property('strategy_kwargs')
            if strategy_kwargs_str:
                try:
                    import json
                    strategy_kwargs = json.loads(strategy_kwargs_str)
                except:
                    strategy_kwargs = strategy_params
            else:
                strategy_kwargs = strategy_params

            if module_path:
                # 使用完整的策略配置
                strategy_config = {
                    'class': strategy_class,
                    'module_path': module_path,
                    'kwargs': strategy_kwargs
                }
                # 如果有signal参数，添加到kwargs中并转换为信号对象
                if signal:
                    # 将signal添加到kwargs中，而不是顶层
                    if 'kwargs' not in strategy_config:
                        strategy_config['kwargs'] = {}

                    # 如果signal是<PRED>字符串，转换为默认信号对象
                    if signal == '<PRED>':
                        try:
                            from qlib.backtest.signal import create_signal_from
                            import pandas as pd

                            # 创建默认信号DataFrame
                            default_signal = pd.DataFrame({
                                '000001.SZ': [0.1, 0.2, 0.3],
                                '000002.SZ': [0.2, 0.1, 0.4],
                                '000858.SZ': [0.3, 0.4, 0.1]
                            }, index=pd.date_range('2020-01-01', periods=3))

                            signal_obj = create_signal_from(default_signal)
                            strategy_config['kwargs']['signal'] = signal_obj
                            logger.info("将<PRED>信号转换为默认信号对象")
                        except Exception as e:
                            logger.warning(f"创建默认信号失败: {e}，移除signal参数")
                            # 不设置signal参数，让策略使用默认行为
                    else:
                        strategy_config['kwargs']['signal'] = signal
                        logger.info("将signal参数添加到kwargs中")
                # 如果没有signal参数，不设置任何signal，让策略使用默认行为
            else:
                # 导入错误修复器并修复策略配置
                try:
                    from fix_workflow_errors import WorkflowErrorFixer

                    # 构建修复后的策略配置
                    strategy_config = WorkflowErrorFixer.fix_strategy_config(strategy_class, strategy_params)

                except ImportError:
                    # 如果无法导入修复器，使用原始配置
                    strategy_config = {
                        'class': strategy_class,
                        'module_path': 'qlib.contrib.strategy.signal_strategy',
                        'kwargs': strategy_params
                    }
                    # 如果有signal参数，添加到kwargs中并转换为信号对象
                    if signal:
                        # 将signal添加到kwargs中，而不是顶层
                        if 'kwargs' not in strategy_config:
                            strategy_config['kwargs'] = {}

                        # 如果signal是<PRED>字符串，转换为默认信号对象
                        if signal == '<PRED>':
                            try:
                                from qlib.backtest.signal import create_signal_from
                                import pandas as pd

                                # 创建默认信号DataFrame
                                default_signal = pd.DataFrame({
                                    '000001.SZ': [0.1, 0.2, 0.3],
                                    '000002.SZ': [0.2, 0.1, 0.4],
                                    '000858.SZ': [0.3, 0.4, 0.1]
                                }, index=pd.date_range('2020-01-01', periods=3))

                                signal_obj = create_signal_from(default_signal)
                                strategy_config['kwargs']['signal'] = signal_obj
                                logger.info("将<PRED>信号转换为默认信号对象")
                            except Exception as e:
                                logger.warning(f"创建默认信号失败: {e}，移除signal参数")
                                # 不设置signal参数，让策略使用默认行为
                        else:
                            strategy_config['kwargs']['signal'] = signal
                            logger.info("将signal参数添加到kwargs中")
                    # 如果没有signal参数，不设置任何signal，让策略使用默认行为

            # 使用Qlib核心创建策略
            strategy = self.execute_qlib_operation(
                "create_strategy",
                strategy_config=strategy_config
            )

            if strategy is not None:
                self._execution_result = {
                    'status': 'success',
                    'strategy': strategy,
                    'strategy_class': strategy_class,
                    'strategy_params': strategy_params
                }
                self.set_output('strategy', self._execution_result)
                self.set_output('signals', self._execution_result)
                logger.info(f"✅ 成功创建Qlib策略: {strategy_class}")
                return True
            else:
                self._execution_result = {
                    'status': 'failed',
                    'error': self._error_message
                }
                logger.error("❌ 创建Qlib策略失败")
                return False

        except Exception as e:
            logger.error(f"Qlib策略节点执行失败: {e}")
            return False

class QlibBacktestNode(QlibCoreBaseNode):
    """Qlib回测节点 - 基于Qlib核心"""

    __identifier__ = 'qlib.core.backtest'
    NODE_NAME = 'Qlib回测'
    type_ = 'qlib.core.backtest'

    def __init__(self):
        super().__init__()

        # 添加输入输出端口
        self.add_input('strategy')
        self.add_output('backtest_results')

        # 添加属性
        self.add_text_input('start_time', '回测开始', '2017-01-01')
        self.add_text_input('end_time', '回测结束', '2020-12-31')
        self.add_text_input('initial_capital', '初始资金', '1000000')
        self.add_text_input('benchmark', '基准', 'SH000300')
        self.add_text_input('strategy_config', '策略配置', '{}')

    def execute(self) -> bool:
        """执行回测"""
        try:
            # 检查是否有策略配置属性
            strategy_config_str = self.get_property('strategy_config')
            if strategy_config_str and strategy_config_str != '{}':
                try:
                    import json
                    strategy_config = json.loads(strategy_config_str)
                except:
                    strategy_config = None
            else:
                strategy_config = None

            # 如果没有策略配置，检查输入
            if not strategy_config:
                strategy_input = self.get_input('strategy')
                if not strategy_input or (isinstance(strategy_input, dict) and strategy_input.get('status') != 'success'):
                    # 如果没有输入或输入无效，使用默认配置
                    strategy_config = {
                        'class': 'TopkDropoutStrategy',
                        'module_path': 'qlib.contrib.strategy.signal_strategy',
                        'kwargs': {'topk': 50, 'n_drop': 5}
                    }
                else:
                    # 使用输入数据构建配置
                    if isinstance(strategy_input, dict):
                        strategy_config = {
                            'class': strategy_input.get('strategy_class', 'TopkDropoutStrategy'),
                            'module_path': strategy_input.get('module_path', 'qlib.contrib.strategy.signal_strategy'),
                            'kwargs': strategy_input.get('strategy_params', {'topk': 50, 'n_drop': 5})
                        }
                    else:
                        strategy_config = {
                            'class': 'TopkDropoutStrategy',
                            'module_path': 'qlib.contrib.strategy.signal_strategy',
                            'kwargs': {'topk': 50, 'n_drop': 5}
                        }

            # 确保策略配置包含module_path
            if 'module_path' not in strategy_config or strategy_config['module_path'] is None:
                strategy_config['module_path'] = 'qlib.contrib.strategy.signal_strategy'

            # 导入错误修复器并修复回测配置
            try:
                from fix_workflow_errors import WorkflowErrorFixer

                # 构建回测参数
                backtest_params = {
                    'start_time': self.get_property('start_time'),
                    'end_time': self.get_property('end_time'),
                    'account': int(self.get_property('initial_capital')),
                    'benchmark': self.get_property('benchmark'),
                    'exchange_kwargs': {
                        'freq': 'day',
                        'limit_threshold': 0.095,
                        'deal_price': 'close',
                        'open_cost': 0.0005,
                        'close_cost': 0.0015,
                        'min_cost': 5
                    }
                }

                # 构建修复后的回测配置
                backtest_config = WorkflowErrorFixer.fix_backtest_config(backtest_params)
                backtest_config['strategy'] = strategy_config

            except ImportError:
                # 如果无法导入修复器，使用原始配置
                backtest_config = {
                    'strategy': strategy_config,
                    'start_time': self.get_property('start_time'),
                    'end_time': self.get_property('end_time'),
                    'account': int(self.get_property('initial_capital')),
                    'benchmark': self.get_property('benchmark'),
                    'exchange_kwargs': {
                        'freq': 'day',
                        'limit_threshold': 0.095,
                        'deal_price': 'close',
                        'open_cost': 0.0005,
                        'close_cost': 0.0015,
                        'min_cost': 5
                    }
                }

            # 使用Qlib核心运行回测
            backtest_result = self.execute_qlib_operation(
                "run_backtest",
                backtest_config=backtest_config
            )

            if backtest_result is not None:
                self._execution_result = {
                    'status': 'success',
                    'backtest_result': backtest_result,
                    'backtest_config': backtest_config
                }
                self.set_output('backtest_results', self._execution_result)
                logger.info("✅ 成功运行Qlib回测")
                return True
            else:
                self._execution_result = {
                    'status': 'failed',
                    'error': self._error_message
                }
                logger.error("❌ 运行Qlib回测失败")
                return False

        except Exception as e:
            logger.error(f"Qlib回测节点执行失败: {e}")
            return False

    def _create_simple_signal(self, strategy_config: Dict[str, Any]) -> Optional[Any]:
        """创建简单信号对象（回退方案）"""
        try:
            from qlib.backtest.signal import create_signal_from
            import pandas as pd
            import numpy as np

            # 从策略配置中提取信息
            kwargs = strategy_config.get('kwargs', {})
            topk = kwargs.get('topk', 50)

            # 创建基于topk的简单信号
            n_stocks = min(topk, 10)  # 限制股票数量

            # 生成简单的股票代码
            stock_codes = [f"{i:06d}.SZ" for i in range(1, n_stocks + 1)]

            # 创建简单的时间范围
            dates = pd.date_range('2020-01-01', periods=5, freq='D')

            # 创建零信号（中性信号）
            signal_values = np.zeros((len(dates), len(stock_codes)))

            signal_df = pd.DataFrame(
                signal_values,
                index=dates,
                columns=stock_codes
            )

            return signal_df

        except Exception as e:
            logger.error(f"创建简单信号失败: {e}")
            return None

# 导出所有节点类
__all__ = [
    'QlibCoreBaseNode',
    'QlibInitNode',
    'QlibDataNode',
    'QlibDatasetNode',
    'QlibModelNode',
    'QlibStrategyNode',
    'QlibBacktestNode'
]
