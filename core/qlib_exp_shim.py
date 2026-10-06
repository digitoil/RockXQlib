# -*- coding: utf-8 -*-
"""QLib 实验管理器空实现（mlflow 缺失时的降级方案）。

背景
----
``qlib.init()`` 内部会执行::

    exp_manager = init_instance_by_config(self["exp_manager"])

``exp_manager`` 默认指向 ``qlib.workflow.expm.MLflowExpManager``，它会在
构造时 new 一个 ``mlflow.tracking.MlflowClient``。

如果环境里装的是 ``mlflow-tracing``（tracing 子集，没有 MlflowClient），
这个构造就会抛 ``AttributeError: module 'mlflow.tracking' has no attribute
'MlflowClient'``。而 qlib 的模型 ``fit()`` 收尾时会调用
``R.log_metrics(...)``，于是出现很迷惑的现象：

    lightgbm 明明打印了 "Early stopping, best iteration is: [25]"，
    紧接着却报错 —— 模型训练其实成功了，只是记录指标那一步炸了，
    导致节点拿不到预测，回测因为没信号而失败。

本模块提供一个不依赖 mlflow 的 ``RockXNullExpManager``：接口与
``MLflowExpManager`` 对齐（继承它以保证类型兼容），但把落盘相关操作
变成空操作，从而让「训练 → 预测 → 策略 → 回测」整条链路在纯 qlib 环境
下也能跑通。

装好完整版 mlflow 后，本 shim 会自动不再被使用（见
``QlibCoreIntegration._mlflow_client_available``）。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["RockXNullExpManager", "RockXNullRecorder"]


class RockXNullRecorder:
    """空实现 Recorder：所有写入操作静默丢弃。

    只实现 qlib 调用链路上会用到的方法，未知属性一律返回一个
    「吞掉一切调用」的哑对象，避免因为缺方法再报错。
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.id = "rockx-null-recorder"
        self.name = "rockx-null"
        self.info: dict = {}

    # --- 生命周期 ---
    def start_run(self, *a: Any, **k: Any) -> "RockXNullRecorder":
        return self

    def end_run(self, *a: Any, **k: Any) -> None:
        return None

    def __enter__(self) -> "RockXNullRecorder":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    # --- 记录类操作（全部静默） ---
    def log_params(self, *a: Any, **k: Any) -> None:
        return None

    def log_metrics(self, *a: Any, **k: Any) -> None:
        # qlib 的 LGBModel.fit 会逐 epoch 调用这里
        return None

    def log_artifact(self, *a: Any, **k: Any) -> None:
        return None

    def log_text(self, *a: Any, **k: Any) -> None:
        return None

    def set_tags(self, *a: Any, **k: Any) -> None:
        return None

    def delete(self, *a: Any, **k: Any) -> None:
        return None

    def save_objects(self, *a: Any, **k: Any) -> None:
        return None

    def load_object(self, *a: Any, **k: Any) -> Any:
        return None

    def list_artifacts(self, *a: Any, **k: Any) -> list:
        return []

    def download_artifact(self, *a: Any, **k: Any) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        # 兜底：任何未实现的方法都变成空操作，避免 qlib 内部换实现时炸链
        def _noop(*a: Any, **k: Any) -> None:
            logger.debug("RockXNullRecorder 忽略调用: %s", name)
            return None

        return _noop


class RockXNullExpManager:
    """空实现 Experiment Manager。

    不继承 MLflowExpManager —— 因为父类构造本身就会去 new MlflowClient，
    正是我们要绕开的东西。这里只实现 QlibRecorder 会用到的最小接口。
    """

    def __init__(self, uri: Optional[str] = None, default_exp_name: Optional[str] = None,
                 *args: Any, **kwargs: Any) -> None:
        self.uri = uri
        self.default_exp_name = default_exp_name or "rockx-null"
        self._experiments: dict = {}
        logger.info("RockXNullExpManager 已启用（不落盘实验记录）")

    # --- 实验 ---
    def create_exp(self, name: Optional[str] = None, *a: Any, **k: Any):
        exp = self.get_exp(name or self.default_exp_name)
        return exp

    def get_exp(self, experiment_name: Optional[str] = None,
                create: bool = True, *a: Any, **k: Any):
        name = experiment_name or self.default_exp_name
        if name not in self._experiments:
            self._experiments[name] = _NullExperiment(name)
        return self._experiments[name]

    def _get_exp(self, experiment_id: Optional[str] = None,
                 experiment_name: Optional[str] = None):
        return self.get_exp(experiment_name)

    def delete_exp(self, *a: Any, **k: Any) -> None:
        return None

    def list_experiments(self) -> list:
        return list(self._experiments.values())

    def search_records(self, *a: Any, **k: Any) -> list:
        return []

    def __getattr__(self, name: str) -> Any:
        def _noop(*a: Any, **k: Any) -> None:
            logger.debug("RockXNullExpManager 忽略调用: %s", name)
            return None

        return _noop


class _NullExperiment:
    """空实现 Experiment，持有若干空 Recorder。"""

    def __init__(self, name: str) -> None:
        self.id = f"rockx-null-{name}"
        self.name = name

    def get_recorder(self, *a: Any, **k: Any) -> RockXNullRecorder:
        return RockXNullRecorder()

    def list_recorders(self, *a: Any, **k: Any) -> list:
        return []

    def delete(self, *a: Any, **k: Any) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        def _noop(*a: Any, **k: Any) -> None:
            return None

        return _noop
