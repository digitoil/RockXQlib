#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib - 基于Qlib的高级量化分析平台
集成AI大模型、知识库、统一数据流和消息系统

Author: RockX Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "RockX Team"
__email__ = "rockx@example.com"

# 核心组件导入
from .core.base_node import RockXQlibBaseNode
from .core.data_flow import RockXQlibDataFlowManager, RockXQlibDataPacket
from .core.message_system import RockXQlibMessageBus, RockXQlibEventSystem
from .core.ai_integration import RockXQlibAIModelInterface, RockXQlibKnowledgeBase
# from .core.plugin_system import RockXQlibPluginManager, RockXQlibPlugin
from .core.workflow_engine import RockXQlibWorkflowEngine

# 节点类型导入
from .nodes.data_nodes import (
    RockXQlibDataNode,
    RockXQlibAlphaNode,
    RockXQlibHighFreqNode,
    RockXQlibCustomDataNode
)

from .nodes.model_nodes import (
    RockXQlibModelNode,
    RockXQlibLinearNode,
    RockXQlibTreeNode,
    RockXQlibLSTMNode,
    RockXQlibTransformerNode
)

from .nodes.strategy_nodes import (
    RockXQlibStrategyNode,
    RockXQlibSignalNode,
    RockXQlibPortfolioNode,
    RockXQlibRiskNode
)

from .nodes.backtest_nodes import (
    RockXQlibBacktestNode,
    RockXQlibSimulatorNode,
    RockXQlibAnalysisNode
)

# 工具类导入
from .utils.config_manager import RockXQlibConfigManager
from .utils.logger import RockXQlibLogger
from .utils.monitor import RockXQlibMonitor

__all__ = [
    # 核心组件
    'RockXQlibBaseNode',
    'RockXQlibDataFlowManager',
    'RockXQlibDataPacket',
    'RockXQlibMessageBus',
    'RockXQlibEventSystem',
    'RockXQlibAIModelInterface',
    'RockXQlibKnowledgeBase',
    'RockXQlibPluginManager',
    'RockXQlibPlugin',
    'RockXQlibWorkflowEngine',
    
    # 数据节点
    'RockXQlibDataNode',
    'RockXQlibAlphaNode',
    'RockXQlibHighFreqNode',
    'RockXQlibCustomDataNode',
    
    # 模型节点
    'RockXQlibModelNode',
    'RockXQlibLinearNode',
    'RockXQlibTreeNode',
    'RockXQlibLSTMNode',
    'RockXQlibTransformerNode',
    
    # 策略节点
    'RockXQlibStrategyNode',
    'RockXQlibSignalNode',
    'RockXQlibPortfolioNode',
    'RockXQlibRiskNode',
    
    # 回测节点
    'RockXQlibBacktestNode',
    'RockXQlibSimulatorNode',
    'RockXQlibAnalysisNode',
    
    # 工具类
    'RockXQlibConfigManager',
    'RockXQlibLogger',
    'RockXQlibMonitor'
]
