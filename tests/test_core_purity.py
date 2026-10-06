#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心纯净性守门测试  (tests/test_core_purity.py)

================== 目的 ==================

锁死一条架构边界：**核心层不得在"导入时"依赖扩展层**。

================== 背景 ==================

项目曾出现这样的问题：``core/__init__.py`` 在模块级直接导入了
ai_integration / data_flow / message_system，于是任何
``import core.qlib_paths`` 都会连带拉起 5 个扩展模块及其三方依赖
（openai / langchain / chromadb …）。已实测确认过这个副作用。

================== 判定规则 ==================

1. **只检查模块级导入**（导入时即执行）。函数体内的延迟导入**允许** ——
   污染只发生在"导入时"，不在"调用时"。

   例：``core/unified_node_manager.py`` 在 ``_load_kronos_nodes()`` 里
   延迟导入 kronos_nodes，这是**正确做法**，不算违规。

2. 核心文件（``CORE_ENTRY_FILES``）的模块级导入**闭包**中，
   不得出现扩展模块（``FORBIDDEN_MODULES`` / ``FORBIDDEN_PREFIXES``）。

3. 核心也不得在模块级依赖重型三方库（torch / openai / …）。

================== 运行 ==================

    python tests/test_core_purity.py          # 独立运行
    pytest tests/test_core_purity.py -v       # 走 pytest
"""

from __future__ import annotations

import ast
import io
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# 核心文件清单 —— 允许被核心依赖的起点（导入闭包的根）
# --------------------------------------------------------------------------
CORE_ENTRY_FILES: Tuple[str, ...] = (
    "core/__init__.py",
    "core/qlib_core_integration.py",
    "core/qlib_paths.py",
    "core/qlib_exp_shim.py",
    "core/config_manager.py",
    "core/base_node.py",
    "core/qlib_base_node.py",
    "core/workflow_runner.py",
    "core/unified_node_manager.py",
    "nodes/__init__.py",
    "nodes/qlib_core_nodes.py",
    "nodes/qlib_data_nodes.py",
)

# --------------------------------------------------------------------------
# 扩展模块 —— 核心不得在模块级依赖
# 同时收录「全名」与「裸名」：unified_node_manager 会把 nodes/ 加进
# sys.path 后用裸名导入（from kronos_nodes import ...），所以裸名也要拦。
# --------------------------------------------------------------------------
FORBIDDEN_MODULES: Set[str] = {
    # --- AI / LLM ---
    "core.ai_integration",
    "core.ollama_integration",
    "core.universal_llm_integration",
    "core.ai_sql_generator",
    # --- 数据流 / 消息 / 插件 / 未接线引擎 ---
    "core.data_flow",
    "core.message_system",
    "core.plugin_system",
    "core.workflow_engine",
    # --- 数据库 / Chat2DB ---
    "core.database_manager",
    "core.database_connection_manager",
    "core.rockx_chat2db_adapter",
    "core.quant_sql_templates",
    "core.sqlite_database",
    "core.vector_database",
    # --- 高级执行组件 ---
    "core.qlib_cache_manager",
    "core.qlib_experiment_manager",
    "core.qlib_parallel_executor",
    # --- 扩展节点（全名）---
    "nodes.kronos_nodes",
    "nodes.ai_nodes",
    "nodes.visualization_nodes",
    "nodes.core_integration_nodes",
    "nodes.model_nodes",
    "nodes.strategy_nodes",
    "nodes.backtest_nodes",
    # --- 扩展节点（裸名，因 sys.path 注入 nodes/ 后可直接导入）---
    "kronos_nodes",
    "ai_nodes",
    "visualization_nodes",
    "core_integration_nodes",
    "model_nodes",
    "strategy_nodes",
    "backtest_nodes",
    # --- 扩展 GUI ---
    "gui.database_management_widgets",
    "gui.ai_management_widgets",
    "gui.kronos_management_widgets",
    "gui.visualization_widgets",
    "gui.ai_management_widgets",
}

# 前缀匹配（整个子包都算扩展）
FORBIDDEN_PREFIXES: Tuple[str, ...] = ("visualization.",)

# 核心不该在模块级依赖的重型三方库
FORBIDDEN_THIRD_PARTY: Set[str] = {
    "torch", "openai", "ollama", "langchain", "chromadb",
}


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------
def module_name_of(path: Path) -> str:
    """把文件路径转成模块名（相对项目根）。"""
    rel = path.relative_to(PROJECT_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def module_to_path(mod: str) -> Optional[Path]:
    """把模块名转成项目内的文件路径；不在项目内则返回 None。"""
    if not mod:
        return None
    base = PROJECT_ROOT.joinpath(*mod.split("."))
    py = base.with_suffix(".py")
    if py.is_file():
        return py
    init = base / "__init__.py"
    if init.is_file():
        return init
    return None


def resolve_relative(cur_module: str, level: int, rest: str, is_package: bool) -> str:
    """把相对导入（``from .x import y``）转成绝对模块名。"""
    parts = cur_module.split(".")
    if not is_package:
        parts = parts[:-1]
    up = level - 1
    if up > 0:
        parts = parts[:-up] if up <= len(parts) else []
    if rest:
        parts = parts + rest.split(".")
    return ".".join(parts)


def collect_module_level_imports(tree: ast.AST) -> List[Tuple[str, int]]:
    """收集**模块级**（导入时即执行）的 import，跳过函数体内的。

    函数体内是延迟执行，不构成"导入时依赖"，因此允许。
    """
    out: List[Tuple[str, int]] = []

    def walk(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            # 函数体跳过（延迟执行）
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Import):
                for alias in child.names:
                    out.append((alias.name, child.lineno))
                continue
            if isinstance(child, ast.ImportFrom):
                mod = child.module or ""
                if child.level:
                    mod = "." * child.level + mod
                out.append((mod, child.lineno))
                continue
            walk(child)

    walk(tree)
    return out


def parse_module_level_imports(path: Path) -> List[Tuple[str, int]]:
    """解析文件的模块级 import；语法错误时返回空。"""
    try:
        src = io.open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return []
    return collect_module_level_imports(tree)


def collect_closure(entries: Tuple[str, ...]) -> Dict[str, List[Tuple[str, int]]]:
    """从入口文件出发，展开项目内的模块级 import 闭包。

    返回 ``{模块名: [(来源文件, 行号), ...]}``
    """
    found: Dict[str, List[Tuple[str, int]]] = {}
    visited: Set[Path] = set()
    queue: List[Path] = [PROJECT_ROOT / e for e in entries]

    while queue:
        path = queue.pop()
        if path in visited or not path.is_file():
            continue
        visited.add(path)

        cur_module = module_name_of(path)
        is_package = path.name == "__init__.py"

        for mod, lineno in parse_module_level_imports(path):
            if mod.startswith("."):
                level = len(mod) - len(mod.lstrip("."))
                rest = mod.lstrip(".")
                mod = resolve_relative(cur_module, level, rest, is_package)

            rel_src = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            found.setdefault(mod, []).append((rel_src, lineno))

            # 项目内模块 -> 继续展开
            nxt = module_to_path(mod)
            if nxt is not None and nxt not in visited:
                queue.append(nxt)

    return found


def is_forbidden(mod: str) -> Optional[str]:
    """判断模块是否违规；返回违规原因，否则 None。"""
    if mod in FORBIDDEN_MODULES:
        return "扩展模块"
    for pre in FORBIDDEN_PREFIXES:
        if mod.startswith(pre):
            return "扩展模块（前缀匹配）"
    root = mod.split(".")[0]
    if root in FORBIDDEN_THIRD_PARTY:
        return "重型三方库"
    return None


# --------------------------------------------------------------------------
# 测试主体
# --------------------------------------------------------------------------
def run_check(verbose: bool = True) -> int:
    """执行检查，返回违规数量。"""
    if verbose:
        print("=" * 72)
        print("核心纯净性检查 —— 模块级导入闭包中不得出现扩展")
        print("=" * 72)
        print()

    missing = [e for e in CORE_ENTRY_FILES if not (PROJECT_ROOT / e).is_file()]
    if missing:
        print("⚠️ 以下核心文件不存在（清单需更新）:")
        for m in missing:
            print("   - %s" % m)
        print()

    closure = collect_closure(CORE_ENTRY_FILES)

    if verbose:
        print("核心导入闭包共 %d 个模块" % len(closure))
        print()

    violations: List[Tuple[str, str, List[Tuple[str, int]]]] = []
    for mod, sources in sorted(closure.items()):
        reason = is_forbidden(mod)
        if reason:
            violations.append((mod, reason, sources))

    if violations:
        print("❌ 发现 %d 处违规（核心在模块级依赖了扩展）:" % len(violations))
        print()
        for mod, reason, sources in violations:
            print("   %s  [%s]" % (mod, reason))
            for src, lineno in sources:
                print("        %s:%d" % (src, lineno))
        print()
        print("修法：把该导入改为**函数内延迟导入**，或移出核心层。")
        print("      （函数体内的 import 不会被本测试拦截 —— 污染只在导入时发生）")
        return len(violations)

    print("✅ 核心纯净性检查通过：模块级导入闭包中无扩展依赖")
    print()
    if verbose:
        print("   已检查的核心入口:")
        for e in CORE_ENTRY_FILES:
            mark = "✓" if (PROJECT_ROOT / e).is_file() else "✗"
            print("     %s %s" % (mark, e))
    return 0


def test_core_purity() -> None:
    """pytest 入口。"""
    n = run_check(verbose=False)
    assert n == 0, "核心层在模块级依赖了 %d 个扩展模块（详见 stdout）" % n


if __name__ == "__main__":
    sys.exit(1 if run_check(verbose=True) > 0 else 0)
