# -*- coding: utf-8 -*-
"""把 qlib 的实验记录落到本地目录。

``qlib.model.trainer.task_train`` 只跟 ``R``（Recorder）说话：``log_params``、
``log_metrics``、``save_objects``、``load_object``。默认后端是 MLflow。
环境里如果只有 ``mlflow-tracing``，``MlflowClient`` 不存在，训练会在记指标
那一步失败；原先的空实现把这些调用直接丢掉，预测和回测结果无处可查。

本模块实现同一套接口，目录结构如下::

    <uri>/
      experiments.json
      <experiment_id>/
        meta.json
        <recorder_id>/
          meta.json params.json metrics.json tags.json
          artifacts/pred.pkl ...

读回的数字只来自这些文件，不在内存里另造一份“成功结果”。
"""
from __future__ import annotations

import json
import pickle
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def uri_to_path(uri: str) -> Path:
    """``file:/abs/path``、``file:///abs/path`` 或普通路径 → 目录。

    ``file:/tmp/x`` 不能交给 ``urlparse`` 再补成 ``file://tmp/x``，否则 ``tmp``
    会被当成主机名，目录变成 ``/x``。
    """
    text = str(uri)
    if text.startswith("file:"):
        rest = text[5:]
        if rest.startswith("//"):
            return Path(urlparse(text).path)
        return Path(rest)
    return Path(text)


def default_tracking_uri() -> str:
    """项目内 ``mlruns/``（已在 .gitignore）。"""
    root = Path(__file__).resolve().parent.parent / "mlruns"
    return "file:" + str(root)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _metric_value(value: Any) -> Optional[float]:
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _dump_obj(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from qlib.utils.serial import Serializable
    except ImportError:
        Serializable = None  # type: ignore
    if Serializable is not None:
        Serializable.general_dump(obj, path)
        return
    with path.open("wb") as handle:
        pickle.dump(obj, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _load_obj(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


def _safe_rel(name: str) -> Path:
    rel = Path(str(name))
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("非法 artifact 名: %s" % name)
    return rel


def _missing(name: str) -> Exception:
    try:
        from qlib.utils.exceptions import LoadObjectError
    except ImportError:
        return FileNotFoundError(name)
    return LoadObjectError("artifact 不存在: %s" % name)


class RockXFileRecorder:
    """一个实验运行。接口对齐 ``qlib.workflow.recorder.Recorder`` 里 task 会调用的部分。"""

    STATUS_S = "SCHEDULED"
    STATUS_R = "RUNNING"
    STATUS_FI = "FINISHED"
    STATUS_FA = "FAILED"

    def __init__(self, experiment: "RockXFileExperiment", name: str,
                 recorder_id: Optional[str] = None) -> None:
        self.experiment = experiment
        self.experiment_id = experiment.id
        self.name = name or "recorder"
        self.id = recorder_id or uuid.uuid4().hex
        self.start_time: Optional[str] = None
        self.end_time: Optional[str] = None
        self.status = self.STATUS_S
        self.run_dir = experiment.exp_dir / self.id
        self.artifact_dir = self.run_dir / "artifacts"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._params: Dict[str, str] = _read_json(self.run_dir / "params.json", {})
        self._metrics: Dict[str, List[Dict[str, Any]]] = _read_json(self.run_dir / "metrics.json", {})
        self._tags: Dict[str, str] = _read_json(self.run_dir / "tags.json", {})
        meta = _read_json(self.run_dir / "meta.json", {})
        if meta:
            self.status = meta.get("status") or self.status
            self.start_time = meta.get("start_time")
            self.end_time = meta.get("end_time")
            self.name = meta.get("name") or self.name

    @property
    def info(self) -> Dict[str, Any]:
        return {
            "class": "Recorder",
            "id": self.id,
            "name": self.name,
            "experiment_id": self.experiment_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
        }

    def _flush_meta(self) -> None:
        _write_json(self.run_dir / "meta.json", self.info)

    def start_run(self) -> "RockXFileRecorder":
        self.status = self.STATUS_R
        self.start_time = self.start_time or _now()
        self._flush_meta()
        return self

    def end_run(self, status: str = STATUS_S) -> None:
        self.status = status
        self.end_time = _now()
        self._flush_meta()

    def log_params(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            self._params[str(key)] = str(value)[:2000]
        _write_json(self.run_dir / "params.json", self._params)

    def log_metrics(self, step: Optional[int] = None, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            point = {"step": step, "value": _metric_value(value)}
            self._metrics.setdefault(str(key), []).append(point)
        _write_json(self.run_dir / "metrics.json", self._metrics)

    def set_tags(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            self._tags[str(key)] = str(value)[:500]
        _write_json(self.run_dir / "tags.json", self._tags)

    def delete_tags(self, *keys: str) -> None:
        for key in keys:
            self._tags.pop(str(key), None)
        _write_json(self.run_dir / "tags.json", self._tags)

    def save_objects(self, local_path: Optional[str] = None, artifact_path: Optional[str] = None,
                     **kwargs: Any) -> None:
        dest = self.artifact_dir
        if artifact_path:
            dest = dest / _safe_rel(artifact_path)
        dest.mkdir(parents=True, exist_ok=True)
        if local_path is not None:
            src = Path(local_path)
            target = dest / src.name
            if src.is_dir():
                import shutil
                shutil.copytree(src, target, dirs_exist_ok=True)
            else:
                import shutil
                shutil.copy2(src, target)
            return
        for name, obj in kwargs.items():
            _dump_obj(obj, dest / _safe_rel(name))

    def load_object(self, name: str, unpickler: Any = None, trusted: bool = False, **kwargs: Any) -> Any:
        # 文件是本记录器刚写的。SigAnaRecord 默认 trusted=False 也会来读 pred.pkl，
        # 所以这里按我们自己的 pickle 读回，而不是再套一层会拒绝 pandas 的限制解包。
        del trusted, kwargs
        path = self.artifact_dir / _safe_rel(name)
        if not path.is_file():
            raise _missing(name)
        if unpickler is not None:
            with path.open("rb") as handle:
                return unpickler(handle).load()
        return _load_obj(path)

    def list_artifacts(self, artifact_path: Optional[str] = None) -> List[str]:
        root = self.artifact_dir
        if not root.is_dir():
            return []
        base = root / _safe_rel(artifact_path) if artifact_path else root
        if not base.exists():
            return []
        if base.is_file():
            return [base.relative_to(root).as_posix()]
        found = [p.relative_to(root).as_posix() for p in base.rglob("*") if p.is_file()]
        return sorted(found)

    def list_metrics(self) -> Dict[str, Optional[float]]:
        latest: Dict[str, Optional[float]] = {}
        for key, points in self._metrics.items():
            if points:
                latest[key] = points[-1].get("value")
        return latest

    def list_params(self) -> Dict[str, str]:
        return dict(self._params)

    def list_tags(self) -> Dict[str, str]:
        return dict(self._tags)

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None) -> None:
        self.save_objects(local_path=local_path, artifact_path=artifact_path)


class RockXFileExperiment:
    def __init__(self, manager: "RockXFileExpManager", experiment_id: str, name: str) -> None:
        self.manager = manager
        self.id = experiment_id
        self.name = name
        self.active_recorder: Optional[RockXFileRecorder] = None
        self._default_rec_name = "recorder"
        self.exp_dir = manager.root / experiment_id
        self.exp_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.exp_dir / "meta.json", {"id": self.id, "name": self.name})
        self._recorders: Dict[str, RockXFileRecorder] = {}

    def load_recorders(self) -> None:
        if not self.exp_dir.is_dir():
            return
        for child in sorted(self.exp_dir.iterdir()):
            meta = child / "meta.json"
            if child.is_dir() and meta.is_file():
                info = _read_json(meta, {})
                rec = RockXFileRecorder(self, info.get("name") or "recorder", recorder_id=child.name)
                self._recorders[rec.id] = rec

    def _find(self, recorder_id: Optional[str], recorder_name: Optional[str]) -> Optional[RockXFileRecorder]:
        if recorder_id:
            return self._recorders.get(recorder_id)
        if recorder_name:
            matched = [rec for rec in self._recorders.values() if rec.name == recorder_name]
            return matched[-1] if matched else None
        return None

    def create_recorder(self, recorder_name: Optional[str] = None) -> RockXFileRecorder:
        rec = RockXFileRecorder(self, recorder_name or self._default_rec_name)
        self._recorders[rec.id] = rec
        rec._flush_meta()
        return rec

    def start(self, *, recorder_id: Optional[str] = None, recorder_name: Optional[str] = None,
              resume: bool = False) -> RockXFileRecorder:
        if resume:
            rec = self._find(recorder_id, recorder_name)
            if rec is None:
                raise ValueError("找不到要恢复的 recorder")
        else:
            rec = self.create_recorder(recorder_name or self._default_rec_name)
        self.active_recorder = rec
        rec.start_run()
        return rec

    def end(self, recorder_status: str = RockXFileRecorder.STATUS_FI) -> None:
        if self.active_recorder is not None:
            self.active_recorder.end_run(recorder_status)
            self.active_recorder = None

    def get_recorder(self, recorder_id: Optional[str] = None, recorder_name: Optional[str] = None,
                     create: bool = True, start: bool = False) -> RockXFileRecorder:
        if recorder_id is None and recorder_name is None:
            if self.active_recorder is not None:
                return self.active_recorder
            recorder_name = self._default_rec_name
        rec = self._find(recorder_id, recorder_name)
        created = False
        if rec is None:
            if not create:
                raise ValueError("找不到 recorder")
            rec = self.create_recorder(recorder_name or self._default_rec_name)
            created = True
        if created and start:
            self.active_recorder = rec
            rec.start_run()
        return rec

    def list_recorders(self, rtype: str = "dict", **kwargs: Any) -> Any:
        status = kwargs.get("status")
        items = [rec for rec in self._recorders.values()
                 if status is None or rec.status == status]
        if rtype == "list":
            return items
        return {rec.id: rec for rec in items}


class RockXFileExpManager:
    """qlib ``R`` 使用的实验管理器。不继承 MLflow 实现，因此不导入 mlflow。"""

    def __init__(self, uri: str, default_exp_name: Optional[str] = None) -> None:
        self._uri = str(uri)
        self.default_exp_name = default_exp_name or "workflow"
        self._active_exp_uri: Optional[str] = None
        self.active_experiment: Optional[RockXFileExperiment] = None
        self.root = uri_to_path(self._uri)
        self.root.mkdir(parents=True, exist_ok=True)
        self._experiments: Dict[str, RockXFileExperiment] = {}
        self._load()

    @property
    def uri(self) -> str:
        return self._active_exp_uri or self._uri

    def _load(self) -> None:
        for item in _read_json(self.root / "experiments.json", []):
            exp = RockXFileExperiment(self, item["id"], item["name"])
            exp.load_recorders()
            self._experiments[exp.id] = exp

    def _save_index(self) -> None:
        payload = [{"id": exp.id, "name": exp.name} for exp in self._experiments.values()]
        _write_json(self.root / "experiments.json", payload)

    def _find(self, experiment_id: Optional[str], experiment_name: Optional[str]) -> Optional[RockXFileExperiment]:
        if experiment_id and experiment_id in self._experiments:
            return self._experiments[experiment_id]
        if experiment_name:
            matched = [exp for exp in self._experiments.values() if exp.name == experiment_name]
            return matched[-1] if matched else None
        return None

    def _create(self, name: str) -> RockXFileExperiment:
        exp = RockXFileExperiment(self, uuid.uuid4().hex, name)
        self._experiments[exp.id] = exp
        self._save_index()
        return exp

    def start_exp(self, *, experiment_id: Optional[str] = None, experiment_name: Optional[str] = None,
                  recorder_id: Optional[str] = None, recorder_name: Optional[str] = None,
                  uri: Optional[str] = None, resume: bool = False, **kwargs: Any) -> RockXFileExperiment:
        del kwargs
        self._active_exp_uri = uri
        name = experiment_name or self.default_exp_name
        exp = self._find(experiment_id, name)
        if exp is None:
            exp = self._create(name)
        self.active_experiment = exp
        exp.start(recorder_id=recorder_id, recorder_name=recorder_name, resume=resume)
        return exp

    def end_exp(self, recorder_status: str = RockXFileRecorder.STATUS_FI, **kwargs: Any) -> None:
        del kwargs
        self._active_exp_uri = None
        if self.active_experiment is not None:
            self.active_experiment.end(recorder_status)
            self.active_experiment = None

    def get_exp(self, *, experiment_id: Optional[str] = None, experiment_name: Optional[str] = None,
                create: bool = True, start: bool = False) -> RockXFileExperiment:
        if experiment_id is None and experiment_name is None:
            if self.active_experiment is not None:
                return self.active_experiment
            experiment_name = self.default_exp_name
        exp = self._find(experiment_id, experiment_name)
        if exp is None:
            if not create:
                raise ValueError("找不到实验: id=%s name=%s" % (experiment_id, experiment_name))
            exp = self._create(experiment_name or self.default_exp_name)
        if start and self.active_experiment is None:
            self.active_experiment = exp
            if exp.active_recorder is None:
                exp.start()
        return exp

    def list_experiments(self) -> Dict[str, RockXFileExperiment]:
        return {exp.name: exp for exp in self._experiments.values()}

    def create_exp(self, experiment_name: Optional[str] = None) -> RockXFileExperiment:
        return self._create(experiment_name or self.default_exp_name)

    def search_records(self, experiment_ids: Any = None, **kwargs: Any) -> List[Dict[str, Any]]:
        del kwargs
        wanted = set(experiment_ids or [])
        rows = []
        for exp in self._experiments.values():
            if wanted and exp.id not in wanted:
                continue
            for rec in exp.list_recorders(rtype="list"):
                rows.append({"experiment_id": exp.id, "recorder_id": rec.id, **rec.info})
        return rows

    def delete_exp(self, experiment_id: Optional[str] = None, experiment_name: Optional[str] = None) -> None:
        exp = self._find(experiment_id, experiment_name)
        if exp is None:
            raise ValueError("找不到要删除的实验")
        import shutil
        shutil.rmtree(exp.exp_dir, ignore_errors=True)
        self._experiments.pop(exp.id, None)
        self._save_index()
