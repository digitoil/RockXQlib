#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib核心集成模块
基于Qlib的架构和核心组件进行深度集成
"""

# 设置Unicode支持
import os
import sys
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
import logging
import json
import re
import traceback
from typing import Dict, Any, Optional, List, Union
from abc import ABC, abstractmethod

# 设置环境变量
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8.dev6'
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB'] = '0.9.8.dev6'

# mlflow 2.9.x 内部还在用 pkg_resources，import 时会打一条弃用警告。
# qlib 的 DataHandler 会 spawn 大量子进程，每个子进程都重复打这条，
# 日志会被刷屏。这里统一压制（只压这一条，不影响其他告警）。
import warnings as _warnings
_warnings.filterwarnings('ignore', message='pkg_resources is deprecated as an API')
_warnings.filterwarnings('ignore', category=UserWarning, module='mlflow')
_warnings.filterwarnings('ignore', category=UserWarning, module='pkg_resources')


logger = logging.getLogger(__name__)

class QlibCoreIntegration:
    """Qlib核心集成类"""

    def __init__(self):
        self.qlib_available = False
        self.qlib_initialized = False
        # 最近一次模型节点产出的预测（Series，MultiIndex=datetime×instrument）。
        # 策略节点的 signal='<PRED>' 会从这里取，避免再伪造假信号。
        self._last_prediction = None
        # 各模型类的可用性（由 _check_qlib_availability 填充）
        self.available_models = {}
        self._check_qlib_availability()

    def _check_qlib_availability(self):
        """检查Qlib可用性。

        注意：这里只校验「核心链路必需」的组件。此前把 ``LSTM`` 也放进
        必检列表，但 ``qlib.contrib.model.__init__`` 里 LSTM/Transformer 等
        PyTorch 模型是包在同一个 try 里的，只要缺 pytorch 就整体导入失败，
        进而把整个 ``qlib_available`` 误判为 False —— 实际上 LGBModel 等
        非神经网络模型完全可用。改为分级校验。
        """
        try:
            import qlib
            from qlib.data import D
            from qlib.data.dataset import DatasetH
            from qlib.contrib.data.handler import Alpha158, Alpha360
            from qlib.contrib.strategy import TopkDropoutStrategy
            from qlib.backtest import backtest
            from qlib.utils import init_instance_by_config

            self.qlib_available = True
            logger.info("✅ Qlib核心组件导入成功")

        except ImportError as e:
            self.qlib_available = False
            logger.warning(f"❌ Qlib核心组件导入失败: {e}")
            return

        # 模型是可选的：逐个探测，缺哪个记哪个，不影响核心可用性
        self.available_models = {}
        for cls_name, mod in (
            ('LinearModel', 'qlib.contrib.model.linear'),
            ('LGBModel', 'qlib.contrib.model.gbdt'),
            ('XGBModel', 'qlib.contrib.model.xgboost'),
            ('CatBoostModel', 'qlib.contrib.model.catboost_model'),
        ):
            try:
                __import__(mod, fromlist=[cls_name])
                self.available_models[cls_name] = True
            except Exception:
                self.available_models[cls_name] = False
        # 神经网络模型（依赖 pytorch），单独标记
        try:
            from qlib.contrib.model.pytorch_lstm import LSTM  # noqa: F401
            self.available_models['LSTM'] = True
        except Exception:
            self.available_models['LSTM'] = False
        avail = [k for k, v in self.available_models.items() if v]
        logger.info(f"可用模型: {avail if avail else '（仅基础模型）'}")

    @staticmethod
    def _mlflow_client_available() -> bool:
        """探测环境里是否有「完整版」mlflow（即 mlflow.tracking.MlflowClient 可用）。

        容易踩的坑：``pip install mlflow`` 在部分源/版本下会装到
        ``mlflow-tracing``（只有 tracing 子集）。此时
        ``from mlflow.version import IS_TRACING_SDK_ONLY`` 为 True，
        ``mlflow.tracking`` 模块虽然存在，但里面**没有** MlflowClient，
        qlib 的 MLflowExpManager 一 new 就抛 AttributeError。
        """
        try:
            import mlflow.tracking as _mt
            if not hasattr(_mt, "MlflowClient"):
                return False
            # 再确认能真正实例化（有些环境 import 成功但内部依赖缺失）
            from mlflow.client import MlflowClient  # noqa: F401
            return True
        except Exception:
            return False

    def initialize_qlib(self, provider_uri: str = None, region: str = "cn",
                       enable_exp_recorder: bool = True) -> bool:
        """初始化Qlib"""
        if not self.qlib_available:
            logger.error("Qlib不可用，无法初始化")
            return False

        try:
            import qlib

            # 设置环境变量
            os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8.dev6'
            os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB'] = '0.9.8.dev6'

            # 检查 Qlib 是否已初始化，并核对数据路径是否与本次请求一致。
            #
            # 原实现用「能否 from qlib.data import D」来判断是否已初始化，
            # 但该导入在 qlib 未初始化时同样会成功，于是被误判为“已初始化”，
            # 真正的 qlib.init() 被跳过 —— 结果数据节点拿到的是 qlib 默认路径
            # (~/.qlib/qlib_data/cn_data)，而不是节点属性里配的 provider_uri，
            # 报 "Please run qlib.init() first"。
            # 改为直接读取 qlib 当前生效的 provider_uri 做比对。
            current_provider = ""
            try:
                from qlib.config import C as _QlibC
                _cur = getattr(_QlibC, "provider_uri", None)
                if isinstance(_cur, dict):
                    _cur = _cur.get("__DEFAULT_FREQ") or next(iter(_cur.values()), "")
                current_provider = str(_cur or "")
            except Exception:
                current_provider = ""

            if provider_uri is None:
                provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")

            def _norm(p):
                return os.path.normcase(os.path.normpath(str(p)))

            is_initialized = bool(current_provider)
            need_init = (not is_initialized) or (_norm(provider_uri) != _norm(current_provider))

            if need_init:
                logger.info(f"🚀 正在初始化Qlib，数据路径: {provider_uri} "
                            f"(当前: {current_provider or '未初始化'})")

                # 初始化Qlib
                #
                # 注意 ``enable_exp_recorder`` / ``kernel_api`` 等并不是 qlib 认识
                # 的参数（qlib 只会打印 "Unrecognized config" 警告）。真正决定
                # 实验记录器的是 ``exp_manager`` 这一段配置：qlib.init() 会执行
                #   exp_manager = init_instance_by_config(self["exp_manager"])
                # 默认是 MLflowExpManager，它会 new 一个 MlflowClient。
                # 如果环境里装的是 mlflow-tracing（只有 tracing 子集，没有
                # MlflowClient），模型 fit 到最后一步 R.log_metrics 就会崩，
                # 表现为「模型训练成功了但拿不到预测」。
                # 这里探测 mlflow 是否真正可用，不可用就把 exp_manager 换成
                # 轻量的本地实现，让整条链路不依赖 mlflow 也能跑通。
                qlib_init_kwargs = dict(
                    provider_uri=provider_uri,
                    region=region,
                    auto_mount=False,
                    mount_path=None,
                    kernel_api=False,
                    redis_host=None,
                    redis_port=None,
                    redis_task_db=None,
                    redis_freq_limit=None,
                )
                if not self._mlflow_client_available():
                    qlib_init_kwargs["exp_manager"] = {
                        "class": "RockXNullExpManager",
                        "module_path": "core.qlib_exp_shim",
                        "kwargs": {},
                    }
                    logger.warning(
                        "⚠️ 未检测到完整的 mlflow（缺少 MlflowClient），"
                        "已切换到本地空实现实验管理器，训练/回测不受影响，"
                        "但不落盘实验记录。安装完整版 mlflow 可恢复该功能："
                        "pip install mlflow==2.9.2")

                qlib.init(**qlib_init_kwargs)

                # 验证初始化是否成功
                try:
                    from qlib.data import D
                    # 如果能导入D模块，说明初始化成功
                    self.qlib_initialized = True
                    logger.info(f"✅ Qlib初始化成功: {provider_uri}")

                    # 测试基本功能
                    try:
                        # 测试数据获取
                        test_data = D.features(['SH000300'], ['$close'],
                                             start_time='2020-01-01',
                                             end_time='2020-01-02')
                        logger.info("✅ Qlib数据获取测试成功")
                    except Exception as e:
                        logger.warning(f"⚠️ Qlib数据获取测试失败: {e}")

                    return True
                except Exception as e:
                    logger.error(f"❌ Qlib初始化验证失败: {e}")
                    return False
            else:
                self.qlib_initialized = True
                logger.info("✅ Qlib已经初始化")
                return True

        except Exception as e:
            logger.error(f"❌ Qlib初始化失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False

    def get_qlib_data(self, instruments: str = "csi300",
                     start_time: str = "2008-01-01",
                     end_time: str = "2020-08-01",
                     fields: List[str] = None) -> Optional[Any]:
        """获取Qlib数据"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法获取数据")
            return None

        try:
            from qlib.data import D

            if fields is None:
                fields = ["$close", "$volume", "$amount"]

            # qlib 的 D.features 不接受 'csi300' 这样的裸市场名，
            # 必须经 D.instruments(market=...) 转成 Instrument 配置；
            # 传股票代码时则要包成列表。原实现直接透传字符串，
            # 报 "Unsupported input type for param `instrument`"。
            resolved = instruments
            try:
                if isinstance(instruments, str):
                    s = instruments.strip()
                    if s.startswith('[') or s.startswith('{'):
                        resolved = json.loads(s)
                    elif ',' in s:
                        resolved = [x.strip() for x in s.split(',') if x.strip()]
                    elif re.fullmatch(r'[A-Za-z]{2}\d{6}', s):
                        resolved = [s]
                    else:
                        resolved = D.instruments(market=s)
                elif isinstance(instruments, (list, tuple)):
                    resolved = list(instruments)
            except Exception as e:
                logger.warning(f"instrument 参数解析失败，按原值透传: {e}")
                resolved = instruments

            data = D.features(
                instruments=resolved,
                fields=fields,
                start_time=start_time,
                end_time=end_time
            )

            logger.info(f"✅ 成功获取Qlib数据: {instruments}, {start_time} - {end_time}")
            return data

        except Exception as e:
            logger.error(f"❌ 获取Qlib数据失败: {e}")
            return None

    def create_dataset(self, handler_config: Dict[str, Any],
                      segments: Dict[str, List[str]] = None,
                      dataset_class: str = "DatasetH",
                      step_len: int = 20) -> Optional[Any]:
        """创建Qlib数据集"""
        if not self.qlib_available:
            logger.error("Qlib不可用，无法创建数据集")
            return None

        # 确保Qlib已初始化
        try:
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
                logger.info("Qlib未初始化，正在重新初始化...")
                self.initialize_qlib()
        except Exception as e:
            logger.error(f"检查Qlib初始化状态失败: {e}")
            return None

        try:
            from qlib.data.dataset import DatasetH, TSDatasetH
            from qlib.utils import init_instance_by_config

            # 确保handler_config包含module_path
            if 'module_path' not in handler_config:
                handler_config['module_path'] = 'qlib.contrib.data.handler'

            # 注意：不要给 handler 注入 num_workers。
            # qlib 的 Alpha158 / Alpha360 的 __init__ 并没有这个参数，
            # 注入会直接抛
            #   DataHandler.__init__() got an unexpected keyword argument 'num_workers'
            # 让数据集节点必然失败。控制并行度应通过 D.features(n_jobs=...) 或
            # OMP_NUM_THREADS / OPENBLAS_NUM_THREADS 等环境变量，而不是 handler 参数。
            kwargs = handler_config.setdefault('kwargs', {})
            kwargs.pop('num_workers', None)

            # 创建数据处理器
            handler = init_instance_by_config(handler_config)

            # 设置默认分段
            if segments is None:
                segments = {
                    "train": ["2008-01-01", "2014-12-31"],
                    "valid": ["2015-01-01", "2016-12-31"],
                    "test": ["2017-01-01", "2020-08-01"]
                }

            # 根据数据集类型创建数据集
            if dataset_class == "TSDatasetH":
                dataset = TSDatasetH(handler=handler, segments=segments, step_len=step_len)
            else:
                dataset = DatasetH(handler=handler, segments=segments)

            logger.info("✅ 成功创建Qlib数据集")
            return dataset

        except Exception as e:
            logger.error(f"❌ 创建Qlib数据集失败: {e}")
            return None

    def create_handler(self, handler_config: Dict[str, Any]) -> Optional[Any]:
        """创建Qlib数据处理器"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法创建数据处理器")
            return None

        try:
            from qlib.utils import init_instance_by_config

            # 确保handler_config包含module_path
            if 'module_path' not in handler_config:
                handler_config['module_path'] = 'qlib.contrib.data.handler'

            # 创建数据处理器
            handler = init_instance_by_config(handler_config)

            logger.info("✅ 成功创建Qlib数据处理器")
            return handler

        except Exception as e:
            logger.error(f"❌ 创建Qlib数据处理器失败: {e}")
            return None

    def create_model(self, model_config: Dict[str, Any]) -> Optional[Any]:
        """创建Qlib模型"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法创建模型")
            return None

        try:
            from qlib.utils import init_instance_by_config

            # 导入错误修复器
            try:
                from fix_workflow_errors import WorkflowErrorFixer

                # 如果是LSTM模型，修复参数类型问题
                model_class = model_config.get('class', '')
                if model_class == 'LSTM' and 'kwargs' in model_config:
                    logger.info("🔧 检测到LSTM模型，修复参数类型...")
                    fixed_params = WorkflowErrorFixer.fix_lstm_model_params(model_config['kwargs'])
                    model_config['kwargs'] = fixed_params
                    logger.info("✅ LSTM模型参数修复完成")

                # 确保model_config包含module_path
                if 'module_path' not in model_config:
                    fixed_config = WorkflowErrorFixer.fix_model_config(
                        model_config.get('class', 'LGBModel'),
                        model_config.get('kwargs', {})
                    )
                    model_config.update(fixed_config)

            except ImportError:
                # 如果无法导入修复器，使用默认配置
                if 'module_path' not in model_config:
                    model_config['module_path'] = 'qlib.contrib.model'

            model = init_instance_by_config(model_config)

            logger.info(f"✅ 成功创建Qlib模型: {model_config.get('class', 'Unknown')}")
            return model

        except Exception as e:
            logger.error(f"❌ 创建Qlib模型失败: {e}")
            return None

    def create_strategy(self, strategy_config: Dict[str, Any]) -> Optional[Any]:
        """创建Qlib策略"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法创建策略")
            return None

        try:
            from qlib.utils import init_instance_by_config

            # 导入错误修复器
            try:
                from fix_workflow_errors import WorkflowErrorFixer

                # 确保strategy_config包含module_path
                if 'module_path' not in strategy_config:
                    fixed_config = WorkflowErrorFixer.fix_strategy_config(
                        strategy_config.get('class', 'TopkDropoutStrategy'),
                        strategy_config.get('kwargs', {})
                    )
                    strategy_config.update(fixed_config)

            except ImportError:
                # 如果无法导入修复器，使用默认配置
                if 'module_path' not in strategy_config:
                    strategy_config['module_path'] = 'qlib.contrib.strategy'

            # 处理signal参数：将signal移动到kwargs中并转换为信号对象
            if 'signal' in strategy_config:
                signal = strategy_config.pop('signal')  # 从顶层移除signal
                if 'kwargs' not in strategy_config:
                    strategy_config['kwargs'] = {}

                if signal is None:
                    logger.warning("signal 为空，跳过")
                else:
                    signal_obj = self._normalize_signal(signal)
                    if signal_obj is not None:
                        strategy_config['kwargs']['signal'] = signal_obj
                        logger.info(f"signal 已归一化为: {type(signal_obj).__name__}")
                    else:
                        logger.warning("无法归一化 signal，移除该参数")

            logger.info(f"最终策略配置: {strategy_config}")
            strategy = init_instance_by_config(strategy_config)

            logger.info(f"✅ 成功创建Qlib策略: {strategy_config.get('class', 'Unknown')}")
            return strategy

        except Exception as e:
            logger.error(f"❌ 创建Qlib策略失败: {e}")
            return None

    @staticmethod
    def _normalize_backtest_config(backtest_config: Dict[str, Any]) -> Dict[str, Any]:
        """把回测配置归一化，保证 start_time / account 等落在**顶层**。

        ⚠️ 踩过的坑：``WorkflowErrorFixer.fix_backtest_config()`` 返回的结构是::

            {'class': 'Backtest', 'module_path': 'qlib.backtest',
             'kwargs': {'start_time': ..., 'account': ...}}   # ← 埋在 kwargs 里

        而 ``run_backtest`` 是从**顶层**读的::

            backtest_config.get('start_time', '2017-01-01')

        结果用户在「Qlib回测」节点里配的 start_time / end_time / account /
        benchmark / exchange_kwargs **全部被静默忽略**，一律退回默认值 ——
        表现为回测区间永远是 2017-01-01 起（实测 911 个交易日），
        手续费配置也被丢弃。因为默认值和用户配置常常接近，很容易一直不被发现。

        这里做一次归一化：顶层缺失的键，从 ``kwargs`` 里取。
        """
        if not isinstance(backtest_config, dict):
            return {}
        cfg = dict(backtest_config)
        inner = cfg.get("kwargs")
        if isinstance(inner, dict):
            for k, v in inner.items():
                # 顶层已有（且非 None）就不覆盖
                if k not in cfg or cfg[k] is None:
                    cfg[k] = v
        return cfg

    def run_backtest(self, backtest_config: Dict[str, Any]) -> Optional[Any]:
        """运行Qlib回测"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法运行回测")
            return None

        # 归一化：把可能埋在 kwargs 里的 start_time / account 等提到顶层
        backtest_config = self._normalize_backtest_config(backtest_config)

        try:
            from qlib.backtest import backtest
            from qlib.utils import init_instance_by_config

            # 导入错误修复器
            try:
                from fix_workflow_errors import WorkflowErrorFixer

                # 确保backtest_config包含正确的配置
                if 'module_path' not in backtest_config:
                    # 构建回测参数
                    backtest_params = {
                        'start_time': backtest_config.get('start_time', '2017-01-01'),
                        'end_time': backtest_config.get('end_time', '2020-08-01'),
                        'account': backtest_config.get('account', 1000000),
                        'benchmark': backtest_config.get('benchmark', 'SH000300'),
                        'exchange_kwargs': backtest_config.get('exchange_kwargs', {
                            'freq': 'day',
                            'limit_threshold': 0.095,
                            'deal_price': 'close',
                            'open_cost': 0.0005,
                            'close_cost': 0.0015,
                            'min_cost': 5
                        })
                    }

                    fixed_config = WorkflowErrorFixer.fix_backtest_config(backtest_params)
                    backtest_config.update(fixed_config)

            except ImportError:
                # 如果无法导入修复器，使用默认配置
                pass

            # 创建回测配置
            strategy_config = backtest_config.get('strategy', {})
            logger.info(f"回测策略配置: {strategy_config}")

            # 优先复用上游策略节点已经建好的实例（它内部已经持有真实 signal）；
            # 重新 init_instance_by_config 会把 signal 丢掉，导致回测无信号。
            strategy = strategy_config.pop('_strategy_instance', None)

            # 检查策略配置中是否包含信号对象
            if strategy is None and 'kwargs' in strategy_config and 'signal' in strategy_config['kwargs']:
                signal_obj = strategy_config['kwargs']['signal']
                logger.info(f"策略信号对象类型: {type(signal_obj)}")
                if hasattr(signal_obj, 'signal'):
                    logger.info(f"信号DataFrame形状: {signal_obj.signal.shape}")

                    # 检查信号数据是否有效
                    signal_df = signal_obj.signal
                    if signal_df.empty:
                        logger.error(
                            "❌ 信号 DataFrame 为空，无法回测。"
                            "原实现会伪造随机信号继续跑，但那样的回测结果毫无意义；"
                            "这里直接失败，让上游把预测链路修好。")
                        return None

            if strategy is None:
                strategy = init_instance_by_config(strategy_config)

            # 创建执行器
            executor_config = {
                'class': 'SimulatorExecutor',
                'module_path': 'qlib.backtest.executor',
                'kwargs': {
                    'time_per_step': 'day',
                    'generate_portfolio_metrics': True
                }
            }
            executor = init_instance_by_config(executor_config)

            # 把实际生效的参数打出来 —— 这类"配置被静默忽略"的 bug
            # 只有对比"配置值 vs 生效值"才能发现
            _eff_start = backtest_config.get('start_time', '2017-01-01')
            _eff_end = backtest_config.get('end_time', '2020-12-31')
            _eff_acct = backtest_config.get('account', 1000000)
            _eff_bench = backtest_config.get('benchmark', 'SH000300')
            _eff_ex = backtest_config.get('exchange_kwargs') or {}
            logger.info(
                "回测参数(实际生效): %s ~ %s | 初始资金 %s | 基准 %s | 手续费 %s",
                _eff_start, _eff_end, _eff_acct, _eff_bench,
                {k: _eff_ex.get(k) for k in
                 ('open_cost', 'close_cost', 'min_cost', 'limit_threshold')
                 if k in _eff_ex} or "（qlib 默认）")

            # 运行回测
            result = backtest(
                strategy=strategy,
                executor=executor,
                start_time=_eff_start,
                end_time=_eff_end,
                account=_eff_acct,
                benchmark=_eff_bench,
                exchange_kwargs=_eff_ex
            )

            logger.info("✅ 成功运行Qlib回测")

            # 回测返回的是 [(portfolio_metrics, indicator), ...] 结构。
            # 之前直接把原始对象丢给上层，界面上什么指标都看不到。
            # 这里算出常用的年化收益 / 最大回撤 / 信息比率等，方便节点展示。
            result = self._attach_metrics(result)
            return result

        except Exception as e:
            logger.error(f"❌ 运行Qlib回测失败: {e}")
            # 打印完整堆栈：回测报错往往在 qlib 内部深层，只有消息
            # （如 "index 4943 is out of bounds for axis 0 with size 4943"）
            # 无法定位，必须看调用链。
            logger.error("回测异常堆栈:\n%s", traceback.format_exc())
            return None

    @staticmethod
    def _attach_metrics(result: Any) -> Any:
        """从 qlib 回测结果里提取并附加常用绩效指标。

        qlib ``backtest`` 的真实返回结构是::

            (portfolio_dict, indicator_dict)

        两者都是 **按频率索引的 dict**，形如
        ``{"day": (portfolio_metrics_DataFrame, indicator_obj)}``。
        注意不是 list-of-tuples —— 这里必须按 dict 取值，
        否则会踩 ``KeyError: 0``。

        ``portfolio_metrics`` 的列通常包含
        ``return / cost / turnover / account / bench``。
        """
        try:
            import numpy as np
            import pandas as pd
        except Exception:
            return result

        try:
            pm = None
            freq_used = None

            # 形态 A：标准二元组 (portfolio_dict, indicator_dict)
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict):
                portfolio_dict = result[0]
                if portfolio_dict:
                    # 频率键实际是 '1min' / '1day' 这类（不是裸 'day'）。
                    # 优先选日频，找不到就取第一个可用频率。
                    freq_used = next(
                        (k for k in portfolio_dict if 'day' in str(k)),
                        next(iter(portfolio_dict)))
                    entry = portfolio_dict[freq_used]
                    if isinstance(entry, (list, tuple)) and len(entry) > 0:
                        pm = entry[0]
                    elif isinstance(entry, pd.DataFrame):
                        pm = entry

            # 形态 B：list-of-tuples（旧版本 / 其他调用方）
            elif isinstance(result, (list, tuple)) and len(result) > 0:
                first = result[0]
                if isinstance(first, (list, tuple)) and len(first) > 0:
                    pm = first[0]
                elif isinstance(first, pd.DataFrame):
                    pm = first

            if not isinstance(pm, pd.DataFrame) or pm.empty:
                logger.warning(
                    "回测已完成，但未取到 portfolio_metrics（类型 %s）—— 跳过绩效指标计算",
                    type(pm).__name__)
                return result
            if 'return' not in pm.columns:
                logger.warning("portfolio_metrics 缺少 'return' 列，可用列: %s", list(pm.columns))
                return result

            ret = pm['return'].dropna()
            if ret.empty:
                logger.warning("portfolio_metrics 的 return 全为 NaN，无法计算绩效")
                return result

            n = len(ret)
            ann = 252
            cum = (1 + ret).cumprod()
            metrics = {
                'freq': freq_used,
                'start': str(ret.index[0]),
                'end': str(ret.index[-1]),
                'n_days': int(n),
                'total_return': float(cum.iloc[-1] - 1),
                'annualized_return': float(cum.iloc[-1] ** (ann / n) - 1),
                'mean_daily_return': float(ret.mean()),
                'std_daily_return': float(ret.std()),
                'max_drawdown': float((cum / cum.cummax() - 1).min()),
                'sharpe': float(
                    (ret.mean() / ret.std() * np.sqrt(ann)) if ret.std() and ret.std() > 0 else 0.0
                ),
            }
            if 'turnover' in pm.columns:
                metrics['avg_turnover'] = float(pm['turnover'].dropna().mean())
            if 'cost' in pm.columns:
                metrics['total_cost'] = float(pm['cost'].dropna().sum())
            if 'account' in pm.columns:
                acc = pm['account'].dropna()
                if not acc.empty:
                    metrics['final_account'] = float(acc.iloc[-1])
            # 超额收益（相对基准）
            if 'bench' in pm.columns:
                bench = pm['bench'].dropna()
                if not bench.empty:
                    n_b = len(bench)
                    metrics['bench_total_return'] = float((1 + bench).prod() - 1)
                    metrics['bench_annualized_return'] = float(
                        (1 + bench).prod() ** (ann / n_b) - 1)
                    metrics['excess_annualized_return'] = (
                        metrics['annualized_return'] - metrics['bench_annualized_return'])

            logger.info(
                "📊 回测绩效[%s]: 总收益 %.2f%% | 年化 %.2f%% | 最大回撤 %.2f%% | 夏普 %.2f | %s ~ %s",
                freq_used,
                metrics['total_return'] * 100,
                metrics['annualized_return'] * 100,
                metrics['max_drawdown'] * 100,
                metrics['sharpe'],
                metrics['start'], metrics['end'])
            return (result, metrics)
        except Exception as e:
            logger.warning(f"绩效指标计算失败(不影响回测本身): {e}")
            logger.debug("指标计算堆栈:\n%s", traceback.format_exc())
            return result

    def parse_yaml_config(self, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析Qlib YAML配置"""
        try:
            config = {
                'qlib_init': yaml_data.get('qlib_init', {}),
                'data_handler_config': yaml_data.get('data_handler_config', {}),
                'port_analysis_config': yaml_data.get('port_analysis_config', {}),
                'task': yaml_data.get('task', {})
            }

            logger.info("✅ 成功解析Qlib YAML配置")
            return config

        except Exception as e:
            logger.error(f"❌ 解析Qlib YAML配置失败: {e}")
            return {}

    def execute_workflow(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """执行完整的Qlib工作流"""
        if not self.qlib_available or not self.qlib_initialized:
            logger.error("Qlib未初始化，无法执行工作流")
            return {}

        try:
            results = {}

            # 1. 初始化Qlib
            qlib_init = config.get('qlib_init', {})
            if qlib_init:
                self.initialize_qlib(
                    provider_uri=qlib_init.get('provider_uri'),
                    region=qlib_init.get('region', 'cn'),
                    enable_exp_recorder=qlib_init.get('enable_exp_recorder', True)
                )

            # 2. 创建数据集
            data_handler_config = config.get('data_handler_config', {})
            if data_handler_config:
                dataset = self.create_dataset(data_handler_config)
                results['dataset'] = dataset

            # 3. 创建模型
            task_config = config.get('task', {})
            if 'model' in task_config:
                model = self.create_model(task_config['model'])
                results['model'] = model

            # 4. 创建策略
            port_analysis_config = config.get('port_analysis_config', {})
            if 'strategy' in port_analysis_config:
                strategy = self.create_strategy(port_analysis_config['strategy'])
                results['strategy'] = strategy

            # 5. 运行回测
            if 'backtest' in port_analysis_config:
                backtest_result = self.run_backtest(port_analysis_config['backtest'])
                results['backtest'] = backtest_result

            logger.info("✅ 成功执行Qlib工作流")
            return results

        except Exception as e:
            logger.error(f"❌ 执行Qlib工作流失败: {e}")
            return {}

    def _normalize_signal(self, signal: Any) -> Optional[Any]:
        """把各种形态的 signal 统一成 qlib 可用的 Signal 对象。

        qlib 的 ``SignalStrategy`` 内部会对传入的 ``signal`` 调用
        ``create_signal_from``。而 ``create_signal_from`` 只认这几种输入：

            - 已经是 ``Signal`` 实例 → 原样返回
            - ``tuple`` / ``list``  → ``ModelSignal(*obj)``（即 ``(model, dataset)``）
            - ``dict`` / ``str``    → ``init_instance_by_config``（配置字典）
            - ``pd.DataFrame`` / ``pd.Series`` → ``SignalWCache(signal=obj)``
            - 其他                  → ``NotImplementedError("This type of signal is not supported")``

        所以「不是 qlib 信号」这个报错的真正来源只有一个：传进来的东西
        不在上面这五种里（例如 numpy 数组、或者是 ``<PRED>`` 这类占位字符串
        但上游没给出真实预测）。

        本方法负责把它转成合法的 ``pd.Series/DataFrame`` 或 ``Signal``：
        ``<PRED>`` 占位符会取上游缓存的真实预测；取不到就返回 ``None``，
        让调用方明确报错，而不是伪造数据把回测带偏。
        """
        from qlib.backtest.signal import Signal, create_signal_from
        import pandas as pd
        import numpy as np

        # 1) 已经是 Signal 对象
        if isinstance(signal, Signal):
            return signal

        # 2) <PRED> 占位符 → 取上游模型预测
        if isinstance(signal, str) and signal.strip() == '<PRED>':
            cached = self.get_cached_prediction()
            if cached is None:
                logger.warning(
                    "⚠️ signal='<PRED>' 但上游没有可用预测（模型未训练或未连线）。"
                    "回测缺少信号，已放弃本次策略创建。")
                return None
            signal = cached

        # 3) pandas 对象 → 直接交给 SignalWCache；这里做一次索引校验
        if isinstance(signal, (pd.Series, pd.DataFrame)):
            if signal.empty:
                logger.warning("signal 为空 DataFrame/Series")
                return None
            # SignalWCache 要求索引含 (datetime, instrument)。
            # 预测结果通常是 MultiIndex；若上游给的是宽表（日期×股票），
            # 这里 stack 成长表，否则回测取不到数值。
            if isinstance(signal, pd.DataFrame):
                idx_names = list(signal.index.names)
                if 'datetime' not in idx_names:
                    signal = signal.stack()
                    signal.index = signal.index.set_names(['datetime', 'instrument'])
                if signal.index.nlevels < 2:
                    logger.warning(f"signal 索引层级不足({signal.index.nlevels})，可能无法回测")
                signal = signal.astype('float64')
                if isinstance(signal, pd.DataFrame):
                    signal = signal.iloc[:, 0]
            return create_signal_from(signal)

        # 4) numpy 数组 → 包成 Series（需要外部提供索引，风险较高，仅兜底）
        if isinstance(signal, np.ndarray):
            logger.warning("signal 是裸 ndarray，缺少 datetime/instrument 索引，无法可靠回测")
            return None

        # 5) dict / str 配置 → 交给 qlib
        if isinstance(signal, (dict, str, list, tuple)):
            try:
                return create_signal_from(signal)
            except Exception as e:
                logger.warning(f"按配置创建 signal 失败: {e}")
                return None

        logger.warning(f"signal 形态无法识别: {type(signal)}")
        return None

    def get_cached_prediction(self) -> Optional[Any]:
        """取最近一次模型节点产出的预测（供策略节点复用）。"""
        return self._last_prediction

    def set_cached_prediction(self, predictions: Any) -> None:
        """记录模型节点产出的预测，供 <PRED> 信号使用。"""
        self._last_prediction = predictions


# 全局Qlib核心集成实例
qlib_core = QlibCoreIntegration()
