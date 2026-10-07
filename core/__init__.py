#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 核心包

================== 核心边界约定（请勿破坏） ==================

本包只承载 qlib 量化链路的**内核**，依赖限于：

    qlib / PySide6 / pandas / numpy / 标准库

⚠️ 禁止在本文件里**直接**导入扩展模块（AI 集成 / 数据流 / 消息系统 /
   插件系统 / 工作流引擎）。

原因：Python 在导入 `core.xxx` 时会**先执行本文件**。一旦这里直接
导入扩展，任何只想用某个核心模块的调用方都会被强制拉起整条扩展
依赖链（openai / langchain / chromadb / torch …）。

实测（改之前）：`import core.qlib_paths` 会连带加载 5 个扩展模块 ——
    core.ai_integration  core.data_flow  core.message_system
    core.plugin_system   core.workflow_engine

扩展组件改为通过 PEP 562 的模块级 ``__getattr__`` **延迟导入**：
用法完全不变（`from core import RockXQlibAIModelInterface` 照样可用），
但只在真正访问该名字时才加载对应模块。

⚠️ 已移除的死代码（零引用，2026-10-07 清理）：
    plugin_system.py（插件系统，从未接线）
    workflow_engine.py（旧工作流引擎，节点契约与真实节点不兼容，从未跑通）
    qlib_workflow.py / qlib_node_editor.py（同上）
    现役执行器是 workflow_runner.py。

新增扩展请放到 extensions/ 目录，不要往本文件加导入语句。
守门测试：tests/test_core_purity.py
============================================================
"""

from .base_node import RockXQlibBaseNode

__all__ = [
    'RockXQlibBaseNode',
    # 以下为扩展组件，延迟导入（见 _LAZY_ATTRS）
    'RockXQlibDataFlowManager',
    'RockXQlibDataPacket',
    'RockXQlibMessageBus',
    'RockXQlibEventSystem',
    'RockXQlibAIModelInterface',
    'RockXQlibKnowledgeBase',
]

# 扩展组件映射：导出名 -> (相对模块名, 模块内属性名)
# 这些模块**不属于核心**，只在使用时才加载。
_LAZY_ATTRS = {
    'RockXQlibDataFlowManager': ('.data_flow', 'RockXQlibDataFlowManager'),
    'RockXQlibDataPacket': ('.data_flow', 'RockXQlibDataPacket'),
    'RockXQlibMessageBus': ('.message_system', 'RockXQlibMessageBus'),
    'RockXQlibEventSystem': ('.message_system', 'RockXQlibEventSystem'),
    'RockXQlibAIModelInterface': ('.ai_integration', 'RockXQlibAIModelInterface'),
    'RockXQlibKnowledgeBase': ('.ai_integration', 'RockXQlibKnowledgeBase'),
}


def __getattr__(name: str):
    """PEP 562 延迟导入扩展组件。

    保持 ``from core import X`` 的向后兼容，同时避免 ``import core``
    连带拉起整条扩展依赖链。
    """
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    import importlib

    module_name, attr_name = target
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    # 缓存进模块命名空间，后续访问不再走 __getattr__
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY_ATTRS))
