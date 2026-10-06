# -*- coding: utf-8 -*-
"""流水线定义文件 -> 标准工作流 dict。

流水线文件（YAML / JSON）有两种写法，可混用：

链式（推荐，人和 LLM 都好写；端口按同名自动连线）::

    name: lgb_csi300
    params: {universe: csi300, start: "2019-01-01"}
    steps:
      - init
      - {type: data,    props: {instruments: "${universe}", start_time: "${start}"}}
      - dataset
      - {type: model,   props: {model_class: LGBModel, model_params: {num_leaves: 64}}}
      - strategy
      - backtest

完整写法：直接给 ``nodes`` / ``links``（即 core.workflow_schema 的格式）。

``${name}`` 引用 ``params``；整串就是 ``${x}`` 时保留原类型。
命令行覆盖：``--set universe=csi500``（改参数）或 ``--set n3.train_end=2015-12-31``（改节点属性）。
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .specs import extract_specs, short_aliases

_VAR = re.compile(r"\$\{(\w+)\}")


def load_pipeline_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("读取 YAML 需要 PyYAML：pip install pyyaml") from e
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("流水线文件顶层必须是对象")
    return data


def parse_overrides(items: Optional[Sequence[str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for it in items or ():
        if "=" not in it:
            raise ValueError("覆盖项格式应为 key=value：%r" % it)
        k, v = it.split("=", 1)
        try:
            val = json.loads(v)
        except ValueError:
            val = v
        out[k.strip()] = val
    return out


def _subst(value: Any, params: Dict[str, Any], errors: List[str], where: str) -> Any:
    if isinstance(value, str):
        m = _VAR.fullmatch(value)
        if m:
            if m.group(1) not in params:
                errors.append("%s 引用了未定义参数 ${%s}" % (where, m.group(1)))
                return value
            return params[m.group(1)]

        def rep(mm):
            if mm.group(1) not in params:
                errors.append("%s 引用了未定义参数 ${%s}" % (where, mm.group(1)))
                return mm.group(0)
            return str(params[mm.group(1)])
        return _VAR.sub(rep, value)
    if isinstance(value, dict):
        return {k: _subst(v, params, errors, where) for k, v in value.items()}
    if isinstance(value, list):
        return [_subst(v, params, errors, where) for v in value]
    return value


def _as_prop(value: Any, default: Any) -> Any:
    """节点的文本属性存的是字符串；dict/list（如模型参数）转成 JSON 文本。"""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(default, str) and not isinstance(value, str) and value is not None \
            and not isinstance(value, bool):
        return str(value)
    return value


def compile_pipeline(doc: Dict[str, Any],
                     specs: Optional[Dict[str, Dict[str, Any]]] = None,
                     overrides: Optional[Dict[str, Any]] = None
                     ) -> Tuple[Dict[str, Any], List[str]]:
    """编译并返回 ``(workflow, errors)``。errors 非空时 workflow 不可用。"""
    specs = specs or extract_specs()
    aliases = short_aliases(specs)
    errors: List[str] = []
    doc = copy.deepcopy(doc)

    params = dict(doc.get("params") or {})
    node_overrides: Dict[str, Any] = {}
    for k, v in (overrides or {}).items():
        if "." in k:
            node_overrides[k] = v
        else:
            if k not in params:
                errors.append("覆盖了未声明的参数 %r（已声明: %s）"
                              % (k, ", ".join(sorted(params)) or "无"))
            params[k] = v

    # ---- 取得节点列表 ----
    if "nodes" in doc:
        raw_nodes = doc["nodes"]
        chain = False
    else:
        raw_nodes = doc.get("steps") or []
        chain = True
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return {}, ["流水线没有 steps / nodes"]

    nodes: List[Dict[str, Any]] = []
    for i, st in enumerate(raw_nodes):
        if isinstance(st, str):
            st = {"type": st}
        if not isinstance(st, dict) or "type" not in st:
            errors.append("第 %d 步格式错误（需要字符串或带 type 的对象）" % (i + 1))
            continue
        t = aliases.get(st["type"], st["type"])
        nid = st.get("id") or "n%d" % (i + 1)
        defaults = (specs.get(t) or {}).get("defaults", {})
        props = {k: _as_prop(_subst(v, params, errors, "%s.%s" % (nid, k)),
                             defaults.get(k))
                 for k, v in (st.get("props") or {}).items()}
        nodes.append({"id": nid, "type": t,
                      "name": st.get("name") or (specs.get(t) or {}).get("name", t),
                      "pos": st.get("pos") or [100 + 260 * i, 100],
                      "props": props})

    ids = {n["id"] for n in nodes}
    for k, v in node_overrides.items():
        nid, prop = k.split(".", 1)
        target = [n for n in nodes if n["id"] == nid]
        if not target:
            errors.append("覆盖项 %s 指向不存在的节点 %s（可用: %s）"
                          % (k, nid, ", ".join(sorted(ids))))
            continue
        d = (specs.get(target[0]["type"]) or {}).get("defaults", {})
        target[0]["props"][prop] = _as_prop(v, d.get(prop))

    # ---- 连线 ----
    links: List[Dict[str, str]] = []
    if chain:
        for j, n in enumerate(nodes):
            for port in (specs.get(n["type"]) or {}).get("inputs", []):
                for up in reversed(nodes[:j]):
                    if port in (specs.get(up["type"]) or {}).get("outputs", []):
                        links.append({"from": "%s.%s" % (up["id"], port),
                                      "to": "%s.%s" % (n["id"], port)})
                        break
    for l in doc.get("links") or []:
        if l not in links:
            links.append(l)

    wf = {"version": "1.0", "name": doc.get("name", ""), "nodes": nodes, "links": links}
    if doc.get("params"):
        wf["params"] = params
    return wf, errors


def dangling_inputs(workflow: Dict[str, Any],
                    specs: Optional[Dict[str, Dict[str, Any]]] = None) -> List[str]:
    """已声明输入端口却没有上游的节点（运行时会拿到空数据）。"""
    specs = specs or extract_specs()
    linked = {l["to"] for l in workflow.get("links", [])}
    out = []
    for n in workflow.get("nodes", []):
        for port in (specs.get(n["type"]) or {}).get("inputs", []):
            if "%s.%s" % (n["id"], port) not in linked:
                out.append("%s(%s) 的输入端口 %s 没有上游" % (n["id"], n["type"], port))
    return out
