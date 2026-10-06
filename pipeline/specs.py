# -*- coding: utf-8 -*-
"""节点规格的静态提取（不导入 NodeGraphQt / qlib / Qt）。

校验、LLM 说明书、CLI 的 ``describe`` 都需要「有哪些节点、端口、属性」。
``core.workflow_schema.collect_specs_from_graph`` 要实例化节点，必须有 Qt。
流水线要在 CI / 服务器上跑，所以这里用 AST 直接读节点源码里的
``__identifier__`` / ``NODE_NAME`` 和 ``add_input / add_output / add_*_input /
add_checkbox`` 调用，得到与实例化一致的规格，且零依赖。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 默认只认核心节点；扩展节点（kronos/ai/...）按需传入
DEFAULT_NODE_FILES: Sequence[str] = ("nodes/qlib_core_nodes.py",)

# 属性声明方法 -> 默认值所在的位置参数下标（name, label, value / text ...）
_PROP_METHODS = {
    "add_text_input": 2,
    "add_checkbox": 3,
    "add_combo_menu": 3,
}

_cache: Dict[tuple, Dict[str, Dict[str, Any]]] = {}


def _const(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _class_info(cls: ast.ClassDef) -> Optional[Dict[str, Any]]:
    ident = name = None
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            key = stmt.targets[0].id
            if key == "__identifier__":
                ident = _const(stmt.value)
            elif key == "NODE_NAME":
                name = _const(stmt.value)
    if not ident:
        return None

    inputs, outputs, props, defaults = [], [], [], {}
    for sub in ast.walk(cls):
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)):
            continue
        m = sub.func.attr
        if m in ("add_input", "add_output") and sub.args:
            port = _const(sub.args[0])
            if isinstance(port, str):
                (inputs if m == "add_input" else outputs).append(port)
        elif m in _PROP_METHODS and sub.args:
            pname = _const(sub.args[0])
            if not isinstance(pname, str):
                continue
            props.append(pname)
            idx = _PROP_METHODS[m]
            if len(sub.args) > idx:
                defaults[pname] = _const(sub.args[idx])
    return {
        "identifier": ident,
        "name": name or cls.name,
        "inputs": sorted(set(inputs)),
        "outputs": sorted(set(outputs)),
        "props": sorted(set(props)),
        "defaults": defaults,
    }


def extract_specs(files: Iterable[str] = DEFAULT_NODE_FILES,
                  root: Path = PROJECT_ROOT) -> Dict[str, Dict[str, Any]]:
    """扫描节点源码，返回 ``{type: {name, inputs, outputs, props, defaults}}``。"""
    key = (tuple(files), str(root))
    if key in _cache:
        return _cache[key]
    specs: Dict[str, Dict[str, Any]] = {}
    for rel in files:
        path = Path(root) / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                info = _class_info(node)
                if info:
                    specs[info.pop("identifier")] = info
    _cache[key] = specs
    return specs


def short_aliases(specs: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """``init -> qlib.core.init`` 这类短名，供 chain 写法使用。"""
    return {t.rsplit(".", 1)[-1]: t for t in specs}


def specs_json(specs: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
    return json.dumps(specs or extract_specs(), ensure_ascii=False, indent=2)
