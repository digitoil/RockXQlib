# -*- coding: utf-8 -*-
"""RockXQlib 流水线命令行。

    python -m pipeline nodes                      # 可用节点、端口、属性
    python -m pipeline validate pipelines/x.yaml  # 只校验，不执行
    python -m pipeline run pipelines/x.yaml --set universe=csi500 [--backend dry]
    python -m pipeline sweep x.yaml --grid n4.model_class=LGBModel,XGBModel
    python -m pipeline runs [--compare ID ID ...]  # 运行记录
    python -m pipeline new my_strategy [--template lgb_alpha158]
    python -m pipeline generate "用 CSI500 训练 LGB，2019 年起回测"   # LLM 起草
    python -m pipeline accept pipelines/drafts/x.json
    python -m pipeline export x.yaml out.json     # 导出给 GUI 画布导入
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from core.workflow_schema import describe_schema, dump_workflow

from .definition import parse_overrides
from .runner import PROJECT_ROOT, prepare, run_pipeline
from .runs import find_run, list_runs, table
from .specs import extract_specs

TEMPLATES_DIR = PROJECT_ROOT / "pipelines"


def _common_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("pipeline")
    p.add_argument("--set", dest="sets", action="append", default=[],
                   metavar="K=V", help="覆盖参数（k=v）或节点属性（n3.train_end=v），可重复")
    p.add_argument("--backend", choices=["qt", "dry"], default="qt",
                   help="qt=真实 qlib 节点；dry=只验证接线与数据流（无需 Qt/qlib）")
    p.add_argument("--runs-dir", default=None)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pipeline", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("nodes", help="列出可用节点")

    p = sub.add_parser("validate", help="校验流水线")
    p.add_argument("pipeline")
    p.add_argument("--set", dest="sets", action="append", default=[])

    p = sub.add_parser("run", help="运行流水线")
    _common_run_args(p)
    p.add_argument("--tag", default="")

    p = sub.add_parser("sweep", help="参数扫描")
    _common_run_args(p)
    p.add_argument("--grid", action="append", required=True, metavar="K=V1,V2")
    p.add_argument("--stop-on-error", action="store_true")

    p = sub.add_parser("runs", help="查看/对比运行记录")
    p.add_argument("--runs-dir", default=None)
    p.add_argument("--compare", nargs="+", metavar="RUN")

    p = sub.add_parser("new", help="从模板新建流水线")
    p.add_argument("name")
    p.add_argument("--template", default="lgb_alpha158")

    p = sub.add_parser("export", help="导出标准工作流 JSON（GUI 可导入）")
    p.add_argument("pipeline")
    p.add_argument("out")
    p.add_argument("--set", dest="sets", action="append", default=[])

    p = sub.add_parser("generate", help="LLM 根据需求起草流水线（只生成草稿）")
    p.add_argument("request")
    p.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"))
    p.add_argument("--model", default=os.environ.get("LLM_MODEL", ""))
    p.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", ""))
    p.add_argument("--max-rounds", type=int, default=3)

    p = sub.add_parser("accept", help="确认草稿，转入 pipelines/")
    p.add_argument("draft")
    return ap


def _prepare_or_exit(path: str, sets: List[str]):
    wf, errors, warnings = prepare(path, parse_overrides(sets))
    for w in warnings:
        print(w)
    if errors:
        print("校验未通过：")
        for e in errors:
            print("  ✗", e)
        sys.exit(2)
    return wf


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "nodes":
        print(describe_schema(extract_specs()))
        return 0

    if args.cmd == "validate":
        wf = _prepare_or_exit(args.pipeline, args.sets)
        print("✓ 通过：%d 节点 / %d 连线" % (len(wf["nodes"]), len(wf["links"])))
        return 0

    if args.cmd == "run":
        rec = run_pipeline(args.pipeline, overrides=parse_overrides(args.sets),
                           backend=args.backend, runs_dir=args.runs_dir, tag=args.tag)
        print("\n状态: %s  记录: %s" % (rec["status"], rec["run_dir"]))
        return 0 if rec["status"] == "success" else 1

    if args.cmd == "sweep":
        from .sweep import parse_grid, run_sweep, summary
        res = run_sweep(args.pipeline, parse_grid(args.grid),
                        base_overrides=parse_overrides(args.sets), backend=args.backend,
                        runs_dir=args.runs_dir, stop_on_error=args.stop_on_error)
        print("\n" + summary(res))
        return 0 if all(r["status"] == "success" for r in res) else 1

    if args.cmd == "runs":
        if args.compare:
            recs = [find_run(k, args.runs_dir) for k in args.compare]
            missing = [k for k, r in zip(args.compare, recs) if r is None]
            if missing:
                print("找不到运行记录:", ", ".join(missing))
                return 1
            print(table(recs))
        else:
            runs = list_runs(args.runs_dir)
            print(table(runs) if runs else "（暂无运行记录）")
        return 0

    if args.cmd == "new":
        src = TEMPLATES_DIR / ("%s.yaml" % args.template)
        if not src.exists():
            names = sorted(p.stem for p in TEMPLATES_DIR.glob("*.yaml"))
            print("模板不存在: %s（可用: %s）" % (args.template, ", ".join(names)))
            return 1
        dst = TEMPLATES_DIR / ("%s.yaml" % args.name)
        if dst.exists():
            print("已存在，不覆盖:", dst)
            return 1
        shutil.copy(src, dst)
        print("已创建:", dst)
        return 0

    if args.cmd == "export":
        wf = _prepare_or_exit(args.pipeline, args.sets)
        wf.pop("params", None)
        dump_workflow(wf, args.out)
        print("已导出:", args.out)
        return 0

    if args.cmd == "generate":
        from .llm import generate_pipeline, openai_compatible_chat, save_draft
        if not args.model:
            print("请用 --model 或环境变量 LLM_MODEL 指定模型（Ollama 需先启动服务并拉取模型）")
            return 1
        chat = openai_compatible_chat(args.base_url, args.model, args.api_key)
        doc, trail = generate_pipeline(args.request, chat, max_rounds=args.max_rounds)
        print("\n".join(trail))
        if doc is None:
            print("未能生成通过校验的流水线，未写入草稿。")
            return 1
        path = save_draft(doc)
        print("草稿已写入（尚未生效）:", path)
        print("预览/校验: python -m pipeline validate %s；确认: python -m pipeline accept %s"
              % (path, path))
        return 0

    if args.cmd == "accept":
        from .llm import accept_draft
        _prepare_or_exit(args.draft, [])
        print("已转正:", accept_draft(Path(args.draft)))
        return 0
    return 1
