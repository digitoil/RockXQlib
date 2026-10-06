# -*- coding: utf-8 -*-
"""参数扫描：对同一条流水线跑网格，每个组合是一条独立、可复现的运行记录。

    python -m pipeline sweep p.yaml --grid start=2018-01-01,2019-01-01 --grid n4.model_class=LGBModel,XGBModel
"""
from __future__ import annotations

import csv
import itertools
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .runner import DEFAULT_RUNS_DIR, run_pipeline
from .runs import _flat_metrics, table


def parse_grid(items: Sequence[str]) -> Dict[str, List[Any]]:
    grid: Dict[str, List[Any]] = {}
    for it in items:
        if "=" not in it:
            raise ValueError("grid 项格式应为 key=v1,v2,...：%r" % it)
        k, vs = it.split("=", 1)
        vals: List[Any] = []
        for v in vs.split(","):
            try:
                vals.append(json.loads(v))
            except ValueError:
                vals.append(v)
        grid[k.strip()] = vals
    return grid


def expand(grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    if not grid:
        return [{}]
    keys = list(grid)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(grid[k] for k in keys))]


def run_sweep(source: Any, grid: Dict[str, List[Any]], *, base_overrides=None,
              backend: str = "qt", runs_dir=None, stop_on_error: bool = False,
              **kw: Any) -> List[Dict[str, Any]]:
    results = []
    for i, combo in enumerate(expand(grid), 1):
        ov = dict(base_overrides or {})
        ov.update(combo)
        rec = run_pipeline(source, overrides=ov, backend=backend, runs_dir=runs_dir,
                           tag="s%02d" % i, **kw)
        rec["sweep_point"] = combo
        results.append(rec)
        if stop_on_error and rec["status"] not in ("success",):
            break
    root = Path(runs_dir or DEFAULT_RUNS_DIR)
    root.mkdir(parents=True, exist_ok=True)
    _write_csv(root / ("sweep_%s.csv" % results[0]["config_hash"] if results else "sweep.csv"),
               results)
    return results


def _write_csv(path: Path, results: List[Dict[str, Any]]) -> None:
    pkeys = list(dict.fromkeys(k for r in results for k in r.get("sweep_point", {})))
    mkeys = list(dict.fromkeys(k for r in results for k in _flat_metrics(r)))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "status"] + pkeys + mkeys)
        for r in results:
            m = _flat_metrics(r)
            w.writerow([r["run_id"], r["status"]]
                       + [r["sweep_point"].get(k, "") for k in pkeys]
                       + [m.get(k, "") for k in mkeys])


def summary(results: List[Dict[str, Any]]) -> str:
    return table(results)
