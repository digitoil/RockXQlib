# -*- coding: utf-8 -*-
"""运行记录的查询与对比。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .runner import DEFAULT_RUNS_DIR


def list_runs(runs_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    root = Path(runs_dir or DEFAULT_RUNS_DIR)
    out = []
    if root.is_dir():
        for d in sorted(root.iterdir()):
            m = d / "manifest.json"
            if m.is_file():
                try:
                    rec = json.loads(m.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                rec["run_dir"] = str(d)
                out.append(rec)
    return out


def find_run(key: str, runs_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """按完整 run_id、前缀/子串（取最新）或 ``latest`` 查找。"""
    runs = list_runs(runs_dir)
    if key == "latest":
        return runs[-1] if runs else None
    hits = [r for r in runs if key in r["run_id"]]
    return hits[-1] if hits else None


def _flat_metrics(rec: Dict[str, Any]) -> Dict[str, float]:
    out = {}
    for k, v in (rec.get("metrics") or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = v
    return out


def table(runs: List[Dict[str, Any]]) -> str:
    """把若干运行渲染成对齐文本表（指标列取各运行的并集）。"""
    keys: List[str] = []
    for r in runs:
        for k in _flat_metrics(r):
            if k not in keys:
                keys.append(k)
    header = ["run_id", "status", "secs"] + keys
    rows = [header]
    for r in runs:
        m = _flat_metrics(r)
        rows.append([r["run_id"], r.get("status", "?"), "%.1f" % r.get("elapsed", 0)]
                    + [("%.4f" % m[k]) if k in m else "-" for k in keys])
    w = [max(len(str(row[i])) for row in rows) for i in range(len(header))]
    return "\n".join("  ".join(str(c).ljust(w[i]) for i, c in enumerate(row)) for row in rows)
