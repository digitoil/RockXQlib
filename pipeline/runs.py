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
                except (ValueError, OSError):
                    continue
                if not isinstance(rec, dict):
                    continue
                rec.setdefault("run_id", d.name)   # 损坏/手写的记录也要能列出来
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
        rows.append([r["run_id"], r.get("status", "?"), "%.1f" % (r.get("elapsed") or 0)]
                    + [("%.4f" % m[k]) if k in m else "-" for k in keys])
    w = [max(len(str(row[i])) for row in rows) for i in range(len(header))]
    return "\n".join("  ".join(str(c).ljust(w[i]) for i, c in enumerate(row)) for row in rows)


def load_workflow_of(rec: Dict[str, Any]) -> Dict[str, Any]:
    p = Path(rec["run_dir"]) / "workflow.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def diff_props(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """各运行之间**取值不同**的节点属性：``[{"key": "n3.train_end", "values": [...]}]``。

    这是回答「两次结果为什么不一样」的第一步 —— 先看改了哪些参数。
    """
    flat = []
    for r in runs:
        d: Dict[str, Any] = {}
        for n in load_workflow_of(r).get("nodes", []):
            for k, v in (n.get("props") or {}).items():
                d["%s.%s" % (n["id"], k)] = v
        flat.append(d)
    keys = list(dict.fromkeys(k for d in flat for k in d))
    out = []
    for k in keys:
        vals = [d.get(k) for d in flat]
        if len({json.dumps(v, sort_keys=True, default=str) for v in vals}) > 1:
            out.append({"key": k, "values": vals})
    return out


# 越大越好 / 越小越好，用于对比时标出最优
_LOWER_IS_BETTER = ("drawdown", "turnover", "cost", "loss", "mdd")


def best_of(runs: List[Dict[str, Any]]) -> Dict[str, int]:
    """每个指标取最优那次运行的下标。回撤/换手/成本类按"绝对值越小越好"。"""
    best: Dict[str, int] = {}
    keys = list(dict.fromkeys(k for r in runs for k in _flat_metrics(r)))
    for k in keys:
        cand = [(i, _flat_metrics(r)[k]) for i, r in enumerate(runs) if k in _flat_metrics(r)]
        if len(cand) < 2:
            continue
        lower = any(t in k.lower() for t in _LOWER_IS_BETTER)
        best[k] = (min if lower else max)(cand, key=lambda x: abs(x[1]) if lower else x[1])[0]
    return best


def compare_text(runs: List[Dict[str, Any]]) -> str:
    """指标表 + 参数差异 + 各指标最优者。"""
    out = [table(runs), ""]
    diffs = diff_props(runs)
    if diffs:
        out.append("参数差异：")
        for d in diffs:
            out.append("  %s: %s" % (d["key"], "  |  ".join(str(v) for v in d["values"])))
    else:
        out.append("参数差异：无（配置相同）")
    b = best_of(runs)
    if b:
        out.append("")
        out.append("各指标最优：" + "；".join("%s → %s" % (k, runs[i]["run_id"][-14:])
                                          for k, i in b.items()))
    return "\n".join(out)
