# -*- coding: utf-8 -*-
"""无界面的 qlib 研究实验：初始化 → 训练 → 记录预测 →（配置里有的话）回测。

这是微软 qlib ``qrun`` 的同一条链路（``qlib.model.trainer.task_train``）：

    DatasetH / 自定义 handler → 模型.fit → R.save_objects → SignalRecord / SigAnaRecord / PortAnaRecord

和画布节点不是两套算法。节点负责交互式拼装；这里把一份 qlib 工作流 YAML
交给 qlib 自己的 trainer 和 recorder。没有数据、qlib 没装上、或者 recorder
里没有预测时，抛 ``QlibResearchError``，不写成功摘要。
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.qlib_file_exp import RockXFileExpManager

_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class QlibResearchError(RuntimeError):
    """实验没有真正跑完。调用方应把这段文字给用户，不要改写成成功。"""


def load_workflow_config(source: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    """读 qlib 工作流 YAML，或直接接收已经解析的 dict。展开 ``${ENV}``。"""
    if isinstance(source, dict):
        return copy.deepcopy(source)
    path = Path(source)
    if not path.is_file():
        raise QlibResearchError("找不到工作流配置: %s" % path)
    text = path.read_text(encoding="utf-8")

    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key not in os.environ:
            return match.group(0)
        return os.environ[key]

    text = _ENV.sub(repl, text)
    try:
        import yaml
    except ImportError as exc:
        raise QlibResearchError("读取 YAML 需要 pyyaml（pip install pyyaml）") from exc
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise QlibResearchError("%s 顶层不是映射" % path)
    return doc


def validate_workflow_config(config: Dict[str, Any]) -> str:
    """检查这份配置能不能真跑。返回展开后的数据目录。

    缺 provider、目录不是 qlib 数据、或缺 model/dataset 时抛错。
    不在这里创建模型，也不返回空结果冒充成功。
    """
    qinit = config.get("qlib_init") or {}
    provider = qinit.get("provider_uri")
    if not provider or "${" in str(provider):
        raise QlibResearchError(
            "qlib_init.provider_uri 未设置。"
            "小样本可先 `python -m pipeline data-import prices.csv --out ./qlib_data --instrument-list pool`，"
            "再 `--provider-uri ./qlib_data`。"
            "Alpha158 / CSI300 需要官方日频数据："
            "`python -m qlib.cli.data qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn`。"
        )
    provider = os.path.abspath(os.path.expanduser(str(provider)))
    from core.qlib_paths import is_qlib_data_dir
    if not is_qlib_data_dir(provider):
        raise QlibResearchError(
            "数据目录不可用: %s（需要同时有 calendars/、features/、instruments/）。"
            "没有行情就不会开始训练，也不会写成功记录。" % provider
        )
    task = config.get("task") or {}
    for name in ("model", "dataset"):
        block = task.get(name)
        if not isinstance(block, dict) or not block.get("class") or not block.get("module_path"):
            raise QlibResearchError(
                "task.%s 必须包含 class 与 module_path，才能交给 qlib.init_instance_by_config。" % name
            )
    records = task.get("record") or []
    if isinstance(records, dict):
        records = [records]
    classes = [r.get("class") for r in records if isinstance(r, dict)]
    if "SignalRecord" not in classes:
        raise QlibResearchError(
            "task.record 里没有 SignalRecord，训练完也无法从 recorder 读回预测。"
            "请加上 qlib.workflow.record_temp.SignalRecord。"
        )
    return provider


def run_qlib_experiment(
    source: Union[str, Path, Dict[str, Any]],
    *,
    experiment_name: Optional[str] = None,
    uri_folder: Optional[Union[str, Path]] = None,
    recorder_name: Optional[str] = None,
    provider_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """跑完一条 qlib 实验并返回从 recorder **读回**的摘要。

    成功的唯一标准：``task_train`` 没抛错，且 recorder 里的 ``pred.pkl``
    能被另一个管理器实例重新加载、行数大于 0。指标字典只含 recorder 里
    实际 ``log_metrics`` 过的最后一次取值。
    """
    config = load_workflow_config(source)
    if provider_uri:
        config.setdefault("qlib_init", {})["provider_uri"] = provider_uri
    provider = validate_workflow_config(config)

    try:
        import qlib
        from qlib.model.trainer import task_train
    except ImportError as exc:
        raise QlibResearchError(
            "未安装 qlib，无法训练。pip install pyqlib lightgbm"
        ) from exc

    exp_name = experiment_name or config.get("experiment_name") or "workflow"
    uri_dir = Path(uri_folder).resolve() if uri_folder else (Path.cwd().resolve() / "mlruns")
    uri_dir.mkdir(parents=True, exist_ok=True)
    uri = "file:" + str(uri_dir)

    qinit = dict(config.get("qlib_init") or {})
    qinit["provider_uri"] = provider
    qinit["region"] = qinit.get("region") or "cn"
    qinit.setdefault("auto_mount", False)
    # 用户没指定 exp_manager 时用本地文件记录器，这样不依赖 mlflow 也能读回预测。
    # 配置里写了 exp_manager 则尊重（例如要落到 MLflow）。
    if "exp_manager" not in (config.get("qlib_init") or {}):
        qinit["exp_manager"] = {
            "class": "RockXFileExpManager",
            "module_path": "core.qlib_file_exp",
            "kwargs": {"uri": uri, "default_exp_name": exp_name},
        }

    try:
        qlib.init(**qinit)
    except Exception as exc:
        raise QlibResearchError("qlib.init 失败: %s: %s" % (type(exc).__name__, exc)) from exc

    try:
        recorder = task_train(config["task"], experiment_name=exp_name, recorder_name=recorder_name)
    except Exception as exc:
        raise QlibResearchError(
            "训练或记录失败，qlib 没有完成这次实验: %s: %s" % (type(exc).__name__, exc)
        ) from exc

    summary = _summarize(recorder, experiment_name=exp_name, uri=uri, provider_uri=provider)
    if not summary.get("prediction"):
        raise QlibResearchError(
            "task_train 返回了，但 recorder 里没有可重新加载的预测（pred.pkl）。"
            "不会把这次运行记成成功。目录: %s" % summary.get("recorder_dir")
        )
    # 再开一个管理器，确认预测是从磁盘读出来的，而不是还拿着内存对象。
    reloaded = _reload_prediction(uri, exp_name, summary["recorder_id"])
    if reloaded is None or int(reloaded) <= 0:
        raise QlibResearchError("pred.pkl 无法从记录目录重新加载，结果不可复查。")
    summary["prediction"]["reloaded_rows"] = int(reloaded)
    summary["status"] = "success"
    out = Path(summary["recorder_dir"]) / "summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def format_summary(summary: Dict[str, Any]) -> str:
    """给人看的短报告。数字都来自 summary，不另算收益。"""
    pred = summary.get("prediction") or {}
    lines = [
        "状态: %s" % summary.get("status"),
        "实验: %s    recorder: %s" % (summary.get("experiment_name"), summary.get("recorder_id")),
        "数据: %s" % summary.get("provider_uri"),
        "记录目录: %s" % summary.get("recorder_dir"),
        "预测: %s 行, %s 只标的, %s ~ %s" % (
            pred.get("rows"), pred.get("n_instruments"), pred.get("start"), pred.get("end")),
        "产物: %s" % ", ".join(summary.get("artifacts") or []),
    ]
    metrics = summary.get("metrics") or {}
    if metrics:
        shown = []
        for key, value in metrics.items():
            if value is None:
                continue
            # 训练过程的逐轮 loss 很多，摘要里只留分析类指标；轮次指标记个数。
            if _is_analysis_metric(key):
                shown.append("%s=%s" % (key, value))
        epoch_keys = [k for k in metrics if not _is_analysis_metric(k)]
        if shown:
            lines.append("记录到的分析指标: " + ", ".join(shown))
        if epoch_keys:
            lines.append("另有 %d 个训练过程指标（在 metrics.json，末值已保留）" % len(epoch_keys))
    else:
        lines.append("recorder 没有 log_metrics 记录。")
    return "\n".join(lines)


def _is_analysis_metric(key: str) -> bool:
    text = key.lower()
    needles = ("ic", "sharpe", "return", "max_drawdown", "information_ratio", "annualized")
    return any(n in text for n in needles)


def _summarize(recorder: Any, *, experiment_name: str, uri: str, provider_uri: str) -> Dict[str, Any]:
    artifacts = list(recorder.list_artifacts() or [])
    prediction = None
    if "pred.pkl" in artifacts:
        frame = recorder.load_object("pred.pkl")
        prediction = _describe_prediction(frame)
    metrics = {}
    try:
        raw = recorder.list_metrics() or {}
        metrics = {str(k): _jsonable(v) for k, v in raw.items()}
    except Exception:
        metrics = {}
    return {
        "experiment_name": experiment_name,
        "experiment_id": getattr(recorder, "experiment_id", None),
        "recorder_id": recorder.id,
        "recorder_dir": str(getattr(recorder, "run_dir", "")),
        "uri": uri,
        "provider_uri": provider_uri,
        "artifacts": artifacts,
        "prediction": prediction,
        "metrics": metrics,
    }


def _describe_prediction(frame: Any) -> Optional[Dict[str, Any]]:
    try:
        import pandas as pd
    except ImportError:
        return None
    if not isinstance(frame, (pd.Series, pd.DataFrame)) or len(frame) == 0:
        return None
    columns = list(map(str, frame.columns)) if isinstance(frame, pd.DataFrame) else ["score"]
    info: Dict[str, Any] = {"rows": int(len(frame)), "columns": columns}
    index = frame.index
    if isinstance(index, pd.MultiIndex):
        names = list(index.names)
        if "datetime" in names:
            dates = index.get_level_values("datetime")
            info["start"] = str(pd.Timestamp(dates.min()).date())
            info["end"] = str(pd.Timestamp(dates.max()).date())
        if "instrument" in names:
            info["n_instruments"] = int(index.get_level_values("instrument").nunique())
    return info


def _reload_prediction(uri: str, experiment_name: str, recorder_id: str) -> Optional[int]:
    manager = RockXFileExpManager(uri=uri, default_exp_name=experiment_name)
    try:
        exp = manager.get_exp(experiment_name=experiment_name, create=False)
        rec = exp.get_recorder(recorder_id=recorder_id, create=False)
        frame = rec.load_object("pred.pkl")
    except Exception:
        return None
    try:
        return len(frame)
    except TypeError:
        return None


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
        except Exception:
            return str(value)
    return str(value)
