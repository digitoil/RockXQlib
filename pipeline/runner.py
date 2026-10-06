# -*- coding: utf-8 -*-
"""运行一条流水线并落盘可复现的运行记录（run record）。

一次运行 = ``runs/<时间>_<名称>_<配置哈希>/``：

    workflow.json   实际执行的、已解析参数的工作流（可直接导入 GUI 画布）
    manifest.json   状态、耗时、逐节点记录、git 版本、后端、配置哈希
    metrics.json    回测绩效（有则写；没有就不写，绝不造假）
    run.log         运行日志
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.workflow_runner import NodeGraphWorkflowRunner
from core.workflow_schema import deserialize_graph, validate_workflow

from .backends import make_graph
from .definition import compile_pipeline, dangling_inputs, load_pipeline_file, parse_overrides

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs"


def _jsonable(o: Any) -> Any:
    """指标里可能混有 numpy / pandas 标量，统一转成 JSON 友好类型。"""
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    if hasattr(o, "item"):
        try:
            return _jsonable(o.item())
        except Exception:
            pass
    return str(o)


def config_hash(workflow: Dict[str, Any]) -> str:
    core = {"nodes": [{k: n[k] for k in ("id", "type", "props")} for n in workflow["nodes"]],
            "links": workflow["links"]}
    blob = json.dumps(core, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]


def _git_sha() -> Optional[str]:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(PROJECT_ROOT),
            stderr=subprocess.DEVNULL, text=True).strip() or None
    except Exception:
        return None


def prepare(source: Any, overrides: Optional[Dict[str, Any]] = None,
            specs: Optional[Dict[str, Dict[str, Any]]] = None):
    """文件路径或 dict -> 已校验的 workflow。返回 ``(workflow, errors, warnings)``。"""
    from .specs import extract_specs
    specs = specs or extract_specs()
    doc = load_pipeline_file(source) if isinstance(source, (str, Path)) else source
    wf, errs = compile_pipeline(doc, specs, overrides)
    if errs:
        return wf, errs, []
    ok, msgs = validate_workflow(wf, specs=specs)
    errors = [m for m in msgs if not m.startswith("[警告]")]
    warnings = [m for m in msgs if m.startswith("[警告]")]
    warnings += ["[警告] " + m for m in dangling_inputs(wf, specs)]
    return wf, errors, warnings


def run_pipeline(source: Any, *, overrides: Optional[Dict[str, Any]] = None,
                 backend: str = "qt", runs_dir: Optional[Path] = None,
                 tag: str = "", node_timeout: Optional[float] = None,
                 total_timeout: Optional[float] = None,
                 graph_and_specs: Any = None) -> Dict[str, Any]:
    """校验 -> 建图 -> 执行 -> 落盘。永不抛业务异常，失败体现在 ``status``。"""
    t0 = time.time()
    graph, specs = graph_and_specs or make_graph(backend)
    wf, errors, warnings = prepare(source, overrides, specs)

    name = re.sub(r"[^\w\-]+", "_", wf.get("name") or "pipeline") if wf else "pipeline"
    h = config_hash(wf) if wf and wf.get("nodes") else "invalid"
    run_id = "%s_%s_%s%s" % (datetime.now().strftime("%Y%m%d-%H%M%S"), name, h,
                             "_" + tag if tag else "")
    run_dir = Path(runs_dir or DEFAULT_RUNS_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_lines: List[str] = []

    def log(msg: str, level: str = "INFO") -> None:
        line = "%s [%s] %s" % (datetime.now().strftime("%H:%M:%S"), level, msg)
        log_lines.append(line)
        print(line, flush=True)

    manifest: Dict[str, Any] = {
        "run_id": run_id, "name": wf.get("name", "") if wf else "", "config_hash": h,
        "backend": backend, "git": _git_sha(), "python": platform.python_version(),
        "started": datetime.now().isoformat(timespec="seconds"),
        "overrides": _jsonable(overrides or {}), "warnings": warnings, "tag": tag,
    }

    def finish(status: str, **extra: Any) -> Dict[str, Any]:
        manifest.update(status=status, elapsed=round(time.time() - t0, 3), **extra)
        (run_dir / "manifest.json").write_text(
            json.dumps(_jsonable(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        manifest["run_dir"] = str(run_dir)
        return manifest

    if errors:
        for e in errors:
            log(e, "ERROR")
        return finish("invalid", errors=errors)
    for w in warnings:
        log(w, "WARNING")

    (run_dir / "workflow.json").write_text(
        json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")

    ok, derrs = deserialize_graph(wf, graph, clear=True, specs=specs)
    if not ok:
        for e in derrs:
            log(e, "ERROR")
        return finish("invalid", errors=derrs)

    kw: Dict[str, Any] = {}
    if node_timeout is not None:
        kw["node_timeout"] = node_timeout
    if total_timeout is not None:
        kw["total_timeout"] = total_timeout
    runner = NodeGraphWorkflowRunner(graph.all_nodes(), on_progress=log, **kw)
    try:
        summary = runner.run()
    except Exception as e:  # runner 自身的异常
        log("执行器异常: %s: %s" % (type(e).__name__, e), "ERROR")
        return finish("error", errors=[str(e)])

    metrics = summary.get("metrics")
    if metrics:
        (run_dir / "metrics.json").write_text(
            json.dumps(_jsonable(metrics), ensure_ascii=False, indent=2), encoding="utf-8")
    return finish(summary["status"], ok_count=summary["ok_count"], total=summary["total"],
                  records=summary["records"], metrics=metrics)


def record_run(workflow: Dict[str, Any], summary: Dict[str, Any], *,
               backend: str = "gui", runs_dir: Optional[Path] = None,
               tag: str = "") -> Path:
    """把一次**已经跑完**的运行（如 GUI 一键运行）落盘成与 CLI 相同的运行记录。"""
    h = config_hash(workflow) if workflow.get("nodes") else "empty"
    name = re.sub(r"[^\w\-]+", "_", workflow.get("name") or "canvas")
    run_id = "%s_%s_%s%s" % (datetime.now().strftime("%Y%m%d-%H%M%S"), name, h,
                             "_" + tag if tag else "")
    run_dir = Path(runs_dir or DEFAULT_RUNS_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "workflow.json").write_text(
        json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics = summary.get("metrics")
    if metrics:
        (run_dir / "metrics.json").write_text(
            json.dumps(_jsonable(metrics), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "run_id": run_id, "name": workflow.get("name", ""), "config_hash": h,
        "backend": backend, "git": _git_sha(), "python": platform.python_version(),
        "started": datetime.now().isoformat(timespec="seconds"), "tag": tag,
        "status": summary.get("status", "?"), "elapsed": round(summary.get("elapsed", 0.0), 3),
        "ok_count": summary.get("ok_count"), "total": summary.get("total"),
        "records": summary.get("records"), "metrics": metrics,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(_jsonable(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir
