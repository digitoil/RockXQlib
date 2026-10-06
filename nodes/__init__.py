#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 节点包

================== 包边界约定（请勿破坏） ==================

本文件**不自动导入**任何子模块。三个原因：

1. **依赖重**：各节点模块会拉起 qlib / torch / plotly 等重依赖。
   一旦在这里自动导入，任意 `import nodes.xxx` 都要付出全部加载代价。

2. **原实现是坏的**：原先的自动导入引用了一批**旧类名** ——
   RockXQlibDataNode / RockXQlibModelNode / RockXQlibLinearNode /
   RockXQlibStrategyNode / RockXQlibBacktestNode …
   但当前各模块里的实际类名是 `QlibXxx`（无 RockXQlib 前缀），
   这些名字**一个都不存在**。结果是 `import nodes` 直接 ImportError，
   并且连带让所有 `from nodes.xxx import ...` 一并失败 ——
   而报错信息指向 `nodes/__init__.py`，与真正想导入的模块毫无关系，
   极难定位。（本次清理删掉 data_nodes.py 后，这个隐藏问题才暴露出来。）

3. **一致性**：与 core/__init__.py 的边界原则相同 ——
   包入口只做声明，不主动拉起重依赖。

请**直接导入具体子模块**：

    from nodes.qlib_core_nodes import QlibInitNode, QlibDataNode
    from nodes.qlib_data_nodes import QlibAlphaNode, QlibFeatureNode
    from nodes.model_nodes import QlibLSTMNode

节点注册走 config/node_fusion_config.yaml 的 node_systems 配置，
由 core/unified_node_manager.py 按需加载（默认只开 qlib_core 与
feature_engineering）。

守门测试：tests/test_core_purity.py
============================================================
"""

__all__ = []
