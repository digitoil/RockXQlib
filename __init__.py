#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RockXQlib —— 基于 qlib 的可视化量化分析平台（顶层包）。

============================================================
本文件是**包入口**，刻意保持最小。
============================================================

⚠️ 为什么这里不做任何 ``from .core.xxx import ...``：

1. **会连带拉起重依赖**。原先这里急切导入了 ``core.ai_integration``，
   于是 ``import RockXQlib`` 会一并加载 openai / langchain / chromadb，
   哪怕调用方只想用 ``core.qlib_paths`` 里一个函数。
   （同样的坑在 ``core/__init__.py`` 已经修过一次，见该文件顶部说明。）

2. **模块路径极易失效**。原先还导入了 ``nodes.data_nodes`` 与
   ``core.workflow_engine`` —— 两者都已作为死代码删除，
   导致 ``import RockXQlib`` 直接 ``ModuleNotFoundError``。
   顶层包一旦被删掉的模块名拖住，整个包就不可导入了。

3. **它不是使用入口**。项目里没有任何代码 ``import RockXQlib``；
   实际入口是 ``launch_gui_complete_integration.py``（GUI）与
   ``python -m pipeline``（命令行），二者都直接使用 ``core.*`` / ``nodes.*``。

⚠️ 本文件**不要删除**：项目顶层包保留 ``__init__.py`` 可避免
「命名空间包被同名常规包覆盖」的问题（本项目在 core / nodes / tests
上各踩过一次，详见技能文档中的同名包遮蔽陷阱）。

需要什么就直接从子模块导入::

    from core.qlib_core_integration import QlibCoreIntegration
    from core.workflow_runner import NodeGraphWorkflowRunner
    from nodes.qlib_core_nodes import QlibInitNode
"""

__version__ = "1.0.0"
__author__ = "RockX Team"

__all__ = ["__version__", "__author__"]
