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

logger = logging.getLogger(__name__)

# 交易所参数缺省值（与 qlib 官方基准 LightGBM 配置一致）。
# 之前这几个值是**写死**在回测节点里的，用户改不了；现在改为
# 「节点属性 exchange_kwargs 优先，缺省用这里的值」。
_DEFAULT_EXCHANGE_KWARGS = {
    "freq": "day",
    "limit_threshold": 0.095,
    "deal_price": "close",
    "open_cost": 0.0005,
    "close_cost": 0.0015,
    "min_cost": 5,
}


def _as_json_dict(value, default=None):
    """把节点属性（文本/JSON 字符串/dict）统一转成 dict。

    节点属性用 ``add_text_input`` 声明时存的是**字符串**，而使用方要的是
    dict。原先各处写法不一（有的直接 ``or {}``，于是拿到字符串后
    ``.get()`` 会炸；有的手写 json.loads）。这里统一收口。

    解析失败或为空时返回 ``default``（默认 ``{}``）—— 不抛异常，
    免得一个手写错的 JSON 把整条链路带崩。
    """
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return dict(default) if default else {}
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "{}":
            return dict(default) if default else {}
        try:
            import json as _json
            obj = _json.loads(text)
            return dict(obj) if isinstance(obj, dict) else (dict(default) if default else {})
        except Exception:
            return dict(default) if default else {}
    return dict(default) if default else {}


def _exchange_kwargs(node) -> dict:
    """交易所参数：节点属性优先，缺省用官方基准默认值。"""
    d = dict(_DEFAULT_EXCHANGE_KWARGS)
    d.update(_as_json_dict(node.get_property("exchange_kwargs")))
    return d


def _lookup_module_path(class_name: str, kind: str = "model") -> str:
    """按类名从注册表反查 ``module_path``（AST 扫描，不 import qlib / torch）。

    比 ``fix_workflow_errors`` 里的硬编码表可靠得多 —— 那张表写错过
    （``GRU -> qlib.contrib.model.rnn`` 这个模块根本不存在），
    而且与 qlib 源码的对应关系会随版本漂移。

    注册表不可用时返回空串，调用方保持原有行为。
    """
    try:
        from pipeline.registry import build
        return build().module_of(class_name or "", kind)
    except Exception:
        return ""


def _autofill_module_path(node, setter, kind: str,
                          class_prop: str, module_prop: str) -> None:
    """类名一改就顺手把 ``module_path`` 带出来。

    为什么做在节点里：模型/策略节点只有「类名」「module_path」两个文本框，
    用户改完类名常常忘了改 module_path —— 而这一对填错时的报错
    （``ModuleNotFoundError`` 或取到另一个模块的同名类）离「哪个字段错了」很远。

    三种情况**不**动：
    - 注册表不可用（拿不到 qlib 源码）
    - 类名有歧义（同名类且没有官方基准背书）→ 交给校验如实报告，不猜
    - 当前 module_path 对新类名仍然合法（是用户自己选的，尊重）
    """
    try:
        from pipeline.registry import build
        cls_name = node.get_property(class_prop)
        if not isinstance(cls_name, str) or not cls_name.strip():
            return
        cls_name = cls_name.strip()
        reg = build()
        cur = node.get_property(module_prop)
        cur = cur.strip() if isinstance(cur, str) else ""
        cands = reg.by_name(cls_name, kind)
        if cur and any(cur in c.all_modules for c in cands):
            return
        want = reg.module_of(cls_name, kind)
        if want and want != cur:
            setter(module_prop, want, push_undo=False)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 导入策略：NodeGraphQt 是硬依赖（拿不到就建不出节点），必须显式失败。
# 原先把 qlib_core 与 BaseNode 放在同一个 try 里，任一导入失败就把 BaseNode
# 换成空壳占位类，结果所有核心节点失去 add_input/add_output 等全部端口 API，
# 建节点时报 "object has no attribute 'add_output'"。两者必须分开。
# ---------------------------------------------------------------------------
from NodeGraphQt import BaseNode

try:
    from core.qlib_core_integration import qlib_core
except ImportError as _e:
    logger.warning(f"qlib_core 不可用，Qlib 相关能力将降级: {_e}")
    qlib_core = None


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
        # 默认数据路径用自动探测的结果 —— 原来写死 'D:\qlib_data'，
        # 这个目录在本机并不存在，新建节点后不动这个属性就会取数失败。
        try:
            from core.qlib_paths import get_default_provider_uri
            _default_uri = get_default_provider_uri()
        except Exception:
            _default_uri = "~/.qlib/qlib_data/cn_data"
        self.add_text_input('provider_uri', '数据源URI', _default_uri)
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
        # ⚠️ 下面三个原先**没有声明**，但 execute() 里一直在读 ——
        # 导致「完整 handler 配置」那条分支永远走不到（get_property 返回 None），
        # 导入 qlib 官方基准配置时也会因"属性不存在"校验失败。
        self.add_text_input('module_path', '处理器模块路径', 'qlib.contrib.data.handler')
        self.add_text_input('handler_kwargs', '处理器参数(JSON)',
                            '{"start_time": "2008-01-01", "end_time": "2020-08-01", '
                            '"fit_start_time": "2008-01-01", "fit_end_time": "2014-12-31", '
                            '"instruments": "csi300"}')
        self.add_text_input('segments', '区间覆盖(JSON)', '{}')
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
                test_data = D.features(['SH600000'], ['$close'], '2020-09-24', '2020-09-25')
                logger.info("Qlib数据模块验证成功")
            except Exception as e:
                logger.warning(f"Qlib数据模块验证失败: {e}")
                # 注意：这里不能硬编码 '~/.qlib/qlib_data/cn_data' 或调用无参 qlib.init()，
                # 那会用 qlib 默认路径覆盖用户在「Qlib初始化」节点里配的 provider_uri，
                # 导致后续取数全部落到一个不存在的目录上。
                # 改为沿用当前已生效的 provider_uri 重新初始化。
                cur_uri = None
                try:
                    from qlib.config import C as _C
                    _p = getattr(_C, "provider_uri", None)
                    if isinstance(_p, dict):
                        _p = _p.get("__DEFAULT_FREQ") or next(iter(_p.values()), None)
                    cur_uri = str(_p) if _p else None
                except Exception:
                    cur_uri = None

                if cur_uri:
                    try:
                        self.qlib_core.initialize_qlib(provider_uri=cur_uri, region="cn")
                        from qlib.data import D as _D
                        _D.features(['SH600000'], ['$close'], '2020-09-24', '2020-09-25')
                        logger.info(f"沿用 {cur_uri} 重新初始化成功")
                    except Exception as e2:
                        logger.error(f"沿用当前数据路径重新初始化仍失败: {e2}")
                else:
                    logger.error("未取到有效的 provider_uri，请检查「Qlib初始化」节点的数据源URI设置")

            # 检查是否有TSDatasetH配置
            handler_kwargs = _as_json_dict(self.get_property('handler_kwargs'))
            if handler_kwargs:
                # 使用TSDatasetH配置
                handler_class = self.get_property('handler_class') or 'Alpha158'
                module_path = self.get_property('module_path') or 'qlib.contrib.data.handler'
                handler_config = {
                    'class': handler_class,
                    'module_path': module_path,
                    'kwargs': handler_kwargs
                }
                segments = _as_json_dict(self.get_property('segments'))
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
        # ⚠️ 这两个原先未声明但被 execute() 读取（同上：分支不可达）。
        # 填了 module_path 就走「完整配置」路径，模型参数用 model_kwargs。
        self.add_text_input('module_path', '模型模块路径', '')
        self.add_text_input('model_kwargs', '模型参数(完整配置, JSON)', '{}')

    def set_property(self, name, value, **kwargs):
        """改 ``model_class`` 时自动带出 ``module_path``（见 :func:`_autofill_module_path`）。

        注意必须接受 ``**kwargs``：NodeGraphQt 会以
        ``set_property('selected', False, push_undo=True)`` 这种形式调用。
        """
        super().set_property(name, value, **kwargs)
        if name == 'model_class':
            _autofill_module_path(self, super().set_property, 'model',
                                  'model_class', 'module_path')

    def execute(self) -> bool:
        """执行模型创建和训练"""
        try:
            # 检查输入
            dataset_input = self.get_input('dataset')
            if not dataset_input or (isinstance(dataset_input, dict) and dataset_input.get('status') != 'success'):
                # 如果没有输入或输入无效，使用默认配置
                pass  # 继续执行，使用默认配置

            model_class = self.get_property('model_class')

            # 参数字典 = model_params 打底，model_kwargs 覆盖其上。
            #
            # ⚠️ 原实现是「有 module_path 就**只读 model_kwargs、完全忽略
            # model_params**」。而官方基准模板恰好把论文超参放在
            # model_params、同时写了 module_path —— 于是超参被整体丢弃
            # （静默、不报错），模型用默认值训练。实测 48 个官方模板全部如此。
            # 与策略节点的合并语义保持一致（那边早先修过同一个坑）。
            model_kwargs = _as_json_dict(self.get_property('model_params'))
            model_kwargs.update(_as_json_dict(self.get_property('model_kwargs')))

            module_path = (self.get_property('module_path') or '').strip()
            if not module_path:
                module_path = _lookup_module_path(model_class, 'model')

            model_config = {'class': model_class, 'kwargs': model_kwargs}
            if module_path:
                model_config['module_path'] = module_path

            # LSTM 参数类型规范（只统一取值类型，不增删参数）。
            #
            # 这里刻意**不再调用** WorkflowErrorFixer.fix_model_config ——
            # 那个函数会用一张硬编码表**整个覆盖** model_config，实测把
            # LSTM 换成了 pytorch_lstm_ts（需要 TSDatasetH，普通 DatasetH 会报错）、
            # XGBModel 指向 gbdt（该模块里没有 XGBModel）、TRAModel 指向包。
            try:
                from fix_workflow_errors import WorkflowErrorFixer
                if model_class == 'LSTM':
                    model_config['kwargs'] = WorkflowErrorFixer.fix_lstm_model_params(
                        model_config['kwargs'])
            except ImportError:
                pass
            except Exception as e:
                logger.debug(f"LSTM 参数类型修复跳过（不影响流程）: {e}")

            # 使用Qlib核心创建模型
            model = self.execute_qlib_operation(
                "create_model",
                model_config=model_config
            )

            if model is not None:
                # 关键：不能只创建模型就返回。原实现到这里就结束了，
                # 输出的 'predictions' 其实只是模型对象本身，没有任何预测值，
                # 下游策略节点取不到信号，只能退回硬编码假信号，
                # 回测因此报 "This type of signal is not supported"。
                # 这里补上「训练 + 预测」，把真实的预测 DataFrame 传给策略。
                dataset = None
                if isinstance(dataset_input, dict):
                    dataset = dataset_input.get('dataset') or dataset_input.get('data')
                elif dataset_input is not None:
                    dataset = dataset_input

                predictions = None
                train_error = None
                if dataset is not None:
                    try:
                        logger.info("🚀 开始训练模型...")
                        model.fit(dataset)
                        predictions = model.predict(dataset)
                        n_pred = len(predictions) if predictions is not None else 0
                        logger.info(f"✅ 模型训练完成，预测样本数: {n_pred}")
                        if n_pred == 0:
                            predictions = None
                            train_error = "模型预测结果为空"
                    except Exception as e:
                        train_error = str(e)
                        logger.error(f"❌ 模型训练/预测失败: {e}")
                else:
                    train_error = "上游未提供数据集，无法训练"
                    logger.warning(f"⚠️ {train_error}")

                self._execution_result = {
                    'status': 'success' if predictions is not None else 'partial',
                    'model': model,
                    'model_class': model_class,
                    'predictions': predictions,
                    'trained': predictions is not None,
                    'train_error': train_error,
                }
                self.set_output('model', self._execution_result)
                self.set_output('predictions', self._execution_result)
                if predictions is not None:
                    # 同时缓存到全局 qlib_core：策略节点即便没连线，
                    # 也能通过 signal='<PRED>' 取到这份真实预测。
                    try:
                        from core.qlib_core_integration import qlib_core as _qc
                        if _qc is not None:
                            _qc.set_cached_prediction(predictions)
                    except Exception as _e:
                        logger.debug(f"缓存预测失败(不影响流程): {_e}")
                    logger.info(f"✅ 成功创建并训练Qlib模型: {model_class}")
                else:
                    logger.warning(f"⚠️ 模型已创建但未产出预测: {model_class} ({train_error})")
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

    def set_property(self, name, value, **kwargs):
        """改 ``strategy_class`` 时自动带出 ``module_path``。

        策略节点的 module_path 默认写死 ``signal_strategy``，用户把类名改成
        规则类（如 ``ACStrategy``）却忘了改模块，运行时会
        ``ModuleNotFoundError``。这里在改类名时顺手纠正。
        """
        super().set_property(name, value, **kwargs)
        if name == 'strategy_class':
            _autofill_module_path(self, super().set_property, 'strategy',
                                  'strategy_class', 'module_path')

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

            # 获取策略参数。
            # 注意：strategy_kwargs 的默认值是字符串 '{}'，它是“真值”，
            # 原实现据此进入分支并解析出空字典，把 strategy_params 里的
            # topk / n_drop 覆盖掉，导致 TopkDropoutStrategy 报
            # "missing 2 required keyword-only arguments: 'topk' and 'n_drop'"。
            # 改为以 strategy_params 为基底，strategy_kwargs 作为覆盖项合并。
            strategy_kwargs = dict(strategy_params) if isinstance(strategy_params, dict) else {}
            strategy_kwargs_str = self.get_property('strategy_kwargs')
            if strategy_kwargs_str:
                try:
                    import json
                    extra = json.loads(strategy_kwargs_str)
                    if isinstance(extra, dict):
                        strategy_kwargs.update(extra)
                except Exception:
                    pass

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

                    # <PRED> 表示「用上游模型的预测作为策略信号」。
                    # 原实现无论上游有没有数据，都造一份 3 行硬编码假信号，
                    # 与回测的股票池/日期区间完全不匹配，回测必然报
                    # "This type of signal is not supported"。
                    # 正确做法：从 predictions 输入里取出真实预测 DataFrame。
                    if signal == '<PRED>':
                        pred_frame = None
                        if isinstance(predictions_input, dict):
                            for key in ('predictions', 'prediction', 'pred', 'signal', 'data'):
                                cand = predictions_input.get(key)
                                if cand is not None and hasattr(cand, 'index') and len(cand) > 0:
                                    pred_frame = cand
                                    break
                        elif predictions_input is not None and hasattr(predictions_input, 'index'):
                            if len(predictions_input) > 0:
                                pred_frame = predictions_input

                        if pred_frame is not None:
                            # qlib 的 SignalStrategy 接受 DataFrame，
                            # 内部会用 create_signal_from 包装。
                            # 同时缓存到 qlib_core，供全局 <PRED> 复用。
                            strategy_config['kwargs']['signal'] = pred_frame
                            try:
                                from core.qlib_core_integration import qlib_core as _qc
                                if _qc is not None:
                                    _qc.set_cached_prediction(pred_frame)
                            except Exception:
                                pass
                            logger.info(f"✅ 使用上游模型预测作为策略信号，样本数: {len(pred_frame)}")
                        else:
                            logger.error(
                                "❌ 上游没有可用的预测数据，无法构建策略信号。"
                                "请确认上游模型节点已完成训练与预测（检查模型节点是否报错）。")
                            self._execution_result = {
                                'status': 'failed',
                                'error': '上游无预测数据，策略无法创建',
                            }
                            return False
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
                    # signal 的统一归一化交给 qlib_core._normalize_signal 处理，
                    # 这里不再伪造 3 行假数据（那会让回测完全失真）。
                    if signal:
                        if 'kwargs' not in strategy_config:
                            strategy_config['kwargs'] = {}
                        if signal == '<PRED>':
                            try:
                                from core.qlib_core_integration import qlib_core as _qc
                                cached = _qc.get_cached_prediction() if _qc is not None else None
                            except Exception:
                                cached = None
                            if cached is not None and hasattr(cached, 'index') and len(cached) > 0:
                                strategy_config['kwargs']['signal'] = cached
                                logger.info(f"使用缓存的模型预测作为信号，样本数: {len(cached)}")
                            else:
                                logger.error(
                                    "❌ signal='<PRED>' 但无可用预测（上游模型未训练/未连线），"
                                    "策略无法创建。")
                                self._execution_result = {
                                    'status': 'failed',
                                    'error': '无可用预测数据',
                                }
                                return False
                        else:
                            strategy_config['kwargs']['signal'] = signal
                            logger.info("将signal参数添加到kwargs中")

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
        # 交易所参数（费率/涨跌停/成交价）。原先这几个值是**硬编码**的，
        # 用户无法调整 —— 但 qlib 官方各基准用的费率并不完全相同，
        # 要复现论文结果就得能改。留空则用官方基准默认值。
        self.add_text_input('exchange_kwargs', '交易所参数(JSON)', '{}')

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
                        # 上游策略节点已经建好了策略实例，且里面带着真实 signal。
                        # 直接把实例透传给 run_backtest，避免重新 init 时丢掉 signal。
                        _strat_obj = strategy_input.get('strategy')
                        if _strat_obj is not None:
                            strategy_config = {
                                'class': strategy_input.get('strategy_class', 'TopkDropoutStrategy'),
                                'module_path': 'qlib.contrib.strategy.signal_strategy',
                                'kwargs': strategy_input.get('strategy_params', {}) or {},
                                '_strategy_instance': _strat_obj,
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
                    'exchange_kwargs': _exchange_kwargs(self)
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
                    'exchange_kwargs': _exchange_kwargs(self)
                }

            # 使用Qlib核心运行回测
            backtest_result = self.execute_qlib_operation(
                "run_backtest",
                backtest_config=backtest_config
            )

            if backtest_result is not None:
                # run_backtest 返回 (原始结果, metrics) 二元组；
                # metrics 是年化/回撤/夏普等可直接展示的绩效指标。
                metrics = None
                raw_result = backtest_result
                if (isinstance(backtest_result, tuple) and len(backtest_result) == 2
                        and isinstance(backtest_result[1], dict)):
                    raw_result, metrics = backtest_result

                self._execution_result = {
                    'status': 'success',
                    'backtest_result': raw_result,
                    'metrics': metrics,
                    'backtest_config': backtest_config
                }
                self.set_output('backtest_results', self._execution_result)
                if metrics:
                    logger.info(
                        "✅ 成功运行Qlib回测 | 年化收益 %.2f%% | 最大回撤 %.2f%% | 夏普 %.2f",
                        metrics.get('annualized_return', 0) * 100,
                        metrics.get('max_drawdown', 0) * 100,
                        metrics.get('sharpe', 0))
                else:
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
