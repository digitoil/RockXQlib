#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一节点管理系统
融合现有节点和新的Qlib核心节点，提供统一的接口和管理
"""

import os
import sys
import logging
import importlib
from typing import Dict, List, Any, Optional, Type, Union
from abc import ABC, abstractmethod

# 添加路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.config_manager import config_manager

logger = logging.getLogger(__name__)

class NodeRegistry:
    """节点注册表"""

    def __init__(self):
        self._nodes = {}
        self._categories = {}
        self._node_metadata = {}

    def register_node(self, node_class: Type, category: str = "Default",
                     metadata: Dict[str, Any] = None):
        """注册节点类"""
        node_name = getattr(node_class, 'NODE_NAME', node_class.__name__)
        node_identifier = getattr(node_class, '__identifier__', f"{category.lower()}.{node_name.lower()}")

        self._nodes[node_identifier] = node_class
        self._node_metadata[node_identifier] = metadata or {}

        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(node_identifier)

        logger.info(f"✅ 注册节点: {node_name} ({node_identifier}) -> {category}")

    def get_node_class(self, identifier: str) -> Optional[Type]:
        """获取节点类"""
        return self._nodes.get(identifier)

    def get_all_nodes(self) -> Dict[str, Type]:
        """获取所有节点"""
        return self._nodes.copy()

    def get_nodes_by_category(self, category: str) -> List[str]:
        """按类别获取节点"""
        return self._categories.get(category, [])

    def get_all_categories(self) -> List[str]:
        """获取所有类别"""
        return list(self._categories.keys())

    def get_node_metadata(self, identifier: str) -> Dict[str, Any]:
        """获取节点元数据"""
        return self._node_metadata.get(identifier, {})

class UnifiedNodeManager:
    """统一节点管理器"""

    def __init__(self):
        self.registry = NodeRegistry()
        self._loaded_modules = set()
        self._initialize_nodes()

    def _initialize_nodes(self):
        """初始化所有节点"""
        logger.info("🚀 开始初始化统一节点管理系统...")

        # 根据配置加载启用的节点系统
        enabled_systems = config_manager.get_enabled_node_systems()
        logger.info(f"📋 启用的节点系统: {enabled_systems}")

        for system_name in enabled_systems:
            system_config = config_manager.get_node_system_config(system_name)
            if system_config:
                self._load_node_system(system_name, system_config)

        logger.info(f"✅ 节点系统初始化完成，共注册 {len(self.registry.get_all_nodes())} 个节点")

    def _load_node_system(self, system_name: str, system_config: Dict[str, Any]):
        """根据配置加载节点系统"""
        try:
            if system_name == "qlib_core":
                self._load_qlib_core_nodes()
            elif system_name == "existing_nodes":
                self._load_existing_nodes()
            elif system_name == "ai_features":
                self._load_ai_nodes()
            elif system_name == "visualization":
                self._load_visualization_nodes()
            elif system_name == "feature_engineering":
                self._load_feature_engineering_nodes()
            elif system_name == "kronos_model":
                self._load_kronos_nodes()
            elif system_name == "core_integration":
                self._load_core_integration_nodes()
            else:
                logger.warning(f"⚠️ 未知的节点系统: {system_name}")
        except Exception as e:
            logger.error(f"❌ 加载节点系统失败: {system_name} - {e}")

    def _load_qlib_core_nodes(self):
        """加载Qlib核心节点"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            from qlib_core_nodes import (
                QlibInitNode, QlibDataNode, QlibHandlerNode, QlibDatasetNode,
                QlibModelNode, QlibStrategyNode, QlibBacktestNode
            )

            # 注册Qlib核心节点
            self.registry.register_node(
                QlibInitNode,
                "Qlib核心",
                {"description": "Qlib初始化节点，基于Qlib核心API", "priority": 1}
            )
            self.registry.register_node(
                QlibDataNode,
                "Qlib核心",
                {"description": "Qlib数据获取节点，基于D.features", "priority": 2}
            )
            self.registry.register_node(
                QlibHandlerNode,
                "Qlib核心",
                {"description": "Qlib数据处理器节点，支持Alpha158、Alpha360等", "priority": 3}
            )
            self.registry.register_node(
                QlibDatasetNode,
                "Qlib核心",
                {"description": "Qlib数据集节点，基于DatasetH", "priority": 4}
            )
            self.registry.register_node(
                QlibModelNode,
                "Qlib核心",
                {"description": "Qlib模型节点，支持所有Qlib模型", "priority": 5}
            )
            self.registry.register_node(
                QlibStrategyNode,
                "Qlib核心",
                {"description": "Qlib策略节点，基于Qlib策略框架", "priority": 6}
            )
            self.registry.register_node(
                QlibBacktestNode,
                "Qlib核心",
                {"description": "Qlib回测节点，基于Qlib回测引擎", "priority": 7}
            )

            logger.info("✅ Qlib核心节点加载完成")

        except ImportError as e:
            logger.warning(f"⚠️ Qlib核心节点加载失败: {e}")

    def _load_existing_nodes(self):
        """加载现有节点系统（已优化，只加载必要的节点）"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            # 只加载必要的兼容节点，避免与Qlib核心节点重复
            try:
                from data_nodes import RockXQlibCustomDataNode

                # 只保留自定义数据节点，其他数据节点由Qlib核心节点替代
                self.registry.register_node(
                    RockXQlibCustomDataNode,
                    "数据节点",
                    {"description": "自定义数据节点（兼容版本）", "priority": 1}
                )
                logger.info("✅ 数据节点加载完成（已优化）")
            except ImportError as e:
                logger.warning(f"⚠️ 数据节点加载失败: {e}")

            # 加载模型节点（已优化，只加载特殊模型）
            try:
                from model_nodes import (
                    QlibLSTMNode, QlibTransformerNode
                )

                # 只保留特殊的深度学习模型，其他模型由Qlib核心节点替代
                self.registry.register_node(
                    QlibLSTMNode,
                    "模型节点",
                    {"description": "LSTM模型节点（特殊深度学习模型）", "priority": 1}
                )
                self.registry.register_node(
                    QlibTransformerNode,
                    "模型节点",
                    {"description": "Transformer模型节点（特殊深度学习模型）", "priority": 2}
                )
                logger.info("✅ 模型节点加载完成（已优化）")
            except ImportError as e:
                logger.warning(f"⚠️ 模型节点加载失败: {e}")

            # 加载策略节点（已优化，只加载常用策略）
            try:
                from strategy_nodes import (
                    QlibTopKNode, QlibLongShortNode
                )

                # 只保留常用的策略节点，其他策略由Qlib核心节点替代
                self.registry.register_node(
                    QlibTopKNode,
                    "策略节点",
                    {"description": "TopK策略节点（常用策略）", "priority": 1}
                )
                self.registry.register_node(
                    QlibLongShortNode,
                    "策略节点",
                    {"description": "多空策略节点（常用策略）", "priority": 2}
                )
                logger.info("✅ 策略节点加载完成（已优化）")
            except ImportError as e:
                logger.warning(f"⚠️ 策略节点加载失败: {e}")

            # 加载回测节点（已优化，只加载模拟器节点）
            try:
                from backtest_nodes import QlibSimulatorNode

                # 只保留模拟器节点，回测节点由Qlib核心节点替代
                self.registry.register_node(
                    QlibSimulatorNode,
                    "回测节点",
                    {"description": "模拟器节点（特殊回测功能）", "priority": 1}
                )
                logger.info("✅ 回测节点加载完成（已优化）")
            except ImportError as e:
                logger.warning(f"⚠️ 回测节点加载失败: {e}")

            logger.info("✅ 现有节点系统加载完成")

        except ImportError as e:
            logger.warning(f"⚠️ 现有节点系统加载失败: {e}")

    def _load_additional_nodes(self):
        """加载其他节点模块"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            # 加载AI节点
            try:
                from ai_nodes import (
                    QlibLLMNode, QlibKnowledgeBaseNode,
                    QlibSmartAnalysisNode, QlibOllamaNode
                )

                self.registry.register_node(
                    QlibLLMNode,
                    "AI功能",
                    {"description": "LLM分析节点", "priority": 1}
                )
                self.registry.register_node(
                    QlibKnowledgeBaseNode,
                    "AI功能",
                    {"description": "知识库查询节点", "priority": 2}
                )
                self.registry.register_node(
                    QlibSmartAnalysisNode,
                    "AI功能",
                    {"description": "智能分析节点", "priority": 3}
                )
                self.registry.register_node(
                    QlibOllamaNode,
                    "AI功能",
                    {"description": "Ollama本地模型节点", "priority": 4}
                )
                logger.info("✅ AI节点加载完成")
            except ImportError as e:
                logger.warning(f"⚠️ AI节点加载失败: {e}")

            # 加载可视化节点
            try:
                from visualization_nodes import (
                    QlibKlineViewerNode, QlibBacktestVisualizerNode,
                    QlibChartEngineNode, QlibDashboardNode
                )

                self.registry.register_node(
                    QlibKlineViewerNode,
                    "可视化",
                    {"description": "K线图可视化节点", "priority": 1}
                )
                self.registry.register_node(
                    QlibBacktestVisualizerNode,
                    "可视化",
                    {"description": "回测可视化节点", "priority": 2}
                )
                self.registry.register_node(
                    QlibChartEngineNode,
                    "可视化",
                    {"description": "图表引擎节点", "priority": 3}
                )
                self.registry.register_node(
                    QlibDashboardNode,
                    "可视化",
                    {"description": "仪表板节点", "priority": 4}
                )
                logger.info("✅ 可视化节点加载完成")
            except ImportError as e:
                logger.warning(f"⚠️ 可视化节点加载失败: {e}")

            # 检查qlib_data_nodes.py是否存在
            qlib_data_nodes_path = os.path.join(nodes_path, 'qlib_data_nodes.py')
            if os.path.exists(qlib_data_nodes_path):
                try:
                    from qlib_data_nodes import (
                        QlibAlphaNode, QlibFeatureNode
                    )

                    self.registry.register_node(
                        QlibAlphaNode,
                        "特征工程",
                        {"description": "Alpha因子节点", "priority": 1}
                    )
                    self.registry.register_node(
                        QlibFeatureNode,
                        "特征工程",
                        {"description": "特征工程节点", "priority": 2}
                    )
                    logger.info("✅ 特征工程节点加载完成")
                except ImportError as e:
                    logger.warning(f"⚠️ 特征工程节点加载失败: {e}")
            else:
                logger.info("⚠️ qlib_data_nodes.py 不存在，跳过加载")

            logger.info("✅ 其他节点模块加载完成")

        except ImportError as e:
            logger.warning(f"⚠️ 其他节点模块加载失败: {e}")

    def _load_ai_nodes(self):
        """加载AI节点"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            from ai_nodes import (
                QlibLLMNode, QlibKnowledgeBaseNode,
                QlibSmartAnalysisNode, QlibOllamaNode
            )

            self.registry.register_node(
                QlibLLMNode,
                "AI功能",
                {"description": "LLM分析节点", "priority": 1}
            )
            self.registry.register_node(
                QlibKnowledgeBaseNode,
                "AI功能",
                {"description": "知识库查询节点", "priority": 2}
            )
            self.registry.register_node(
                QlibSmartAnalysisNode,
                "AI功能",
                {"description": "智能分析节点", "priority": 3}
            )
            self.registry.register_node(
                QlibOllamaNode,
                "AI功能",
                {"description": "Ollama本地模型节点", "priority": 4}
            )
            logger.info("✅ AI节点加载完成")

        except ImportError as e:
            logger.warning(f"⚠️ AI节点加载失败: {e}")

    def _load_visualization_nodes(self):
        """加载可视化节点"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            from visualization_nodes import (
                QlibKlineViewerNode, QlibBacktestVisualizerNode,
                QlibChartEngineNode, QlibDashboardNode
            )

            self.registry.register_node(
                QlibKlineViewerNode,
                "可视化",
                {"description": "K线图可视化节点", "priority": 1}
            )
            self.registry.register_node(
                QlibBacktestVisualizerNode,
                "可视化",
                {"description": "回测可视化节点", "priority": 2}
            )
            self.registry.register_node(
                QlibChartEngineNode,
                "可视化",
                {"description": "图表引擎节点", "priority": 3}
            )
            self.registry.register_node(
                QlibDashboardNode,
                "可视化",
                {"description": "仪表板节点", "priority": 4}
            )
            logger.info("✅ 可视化节点加载完成")

        except ImportError as e:
            logger.warning(f"⚠️ 可视化节点加载失败: {e}")

    def _load_feature_engineering_nodes(self):
        """加载特征工程节点"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            # 检查qlib_data_nodes.py是否存在
            qlib_data_nodes_path = os.path.join(nodes_path, 'qlib_data_nodes.py')
            if os.path.exists(qlib_data_nodes_path):
                from qlib_data_nodes import (
                    QlibAlphaNode, QlibFeatureNode
                )

                self.registry.register_node(
                    QlibAlphaNode,
                    "特征工程",
                    {"description": "Alpha因子节点", "priority": 1}
                )
                self.registry.register_node(
                    QlibFeatureNode,
                    "特征工程",
                    {"description": "特征工程节点", "priority": 2}
                )
                logger.info("✅ 特征工程节点加载完成")
            else:
                logger.info("⚠️ qlib_data_nodes.py 不存在，跳过加载")

        except ImportError as e:
            logger.warning(f"⚠️ 特征工程节点加载失败: {e}")

    def _load_kronos_nodes(self):
        """加载Kronos金融K线大模型节点"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            from kronos_nodes import (
                KronosKlinePredictorNode, KronosQuantitativeAnalysisNode,
                KronosStrategyNode
            )

            self.registry.register_node(
                KronosKlinePredictorNode,
                "Kronos模型",
                {"description": "Kronos K线预测节点", "priority": 1}
            )
            self.registry.register_node(
                KronosQuantitativeAnalysisNode,
                "Kronos模型",
                {"description": "Kronos量化分析节点", "priority": 2}
            )
            self.registry.register_node(
                KronosStrategyNode,
                "Kronos模型",
                {"description": "Kronos策略节点", "priority": 3}
            )
            logger.info("✅ Kronos节点加载完成")

        except ImportError as e:
            logger.warning(f"⚠️ Kronos节点加载失败: {e}")

    def _load_core_integration_nodes(self):
        """加载核心集成节点"""
        try:
            # 添加nodes目录到路径
            nodes_path = os.path.join(os.path.dirname(__file__), '..', 'nodes')
            if nodes_path not in sys.path:
                sys.path.insert(0, nodes_path)

            from core_integration_nodes import (
                DataFlowManagerNode, MessageBusNode, CacheManagerNode,
                ExperimentManagerNode, ParallelExecutorNode
            )

            self.registry.register_node(
                DataFlowManagerNode,
                "核心集成",
                {"description": "数据流管理节点", "priority": 1}
            )
            self.registry.register_node(
                MessageBusNode,
                "核心集成",
                {"description": "消息总线节点", "priority": 2}
            )
            self.registry.register_node(
                CacheManagerNode,
                "核心集成",
                {"description": "缓存管理节点", "priority": 3}
            )
            self.registry.register_node(
                ExperimentManagerNode,
                "核心集成",
                {"description": "实验管理节点", "priority": 4}
            )
            self.registry.register_node(
                ParallelExecutorNode,
                "核心集成",
                {"description": "并行执行器节点", "priority": 5}
            )
            logger.info("✅ 核心集成节点加载完成")

        except ImportError as e:
            logger.warning(f"⚠️ 核心集成节点加载失败: {e}")

    def create_node(self, identifier: str, **kwargs) -> Optional[Any]:
        """创建节点实例"""
        node_class = self.registry.get_node_class(identifier)
        if node_class:
            try:
                node = node_class(**kwargs)
                logger.info(f"✅ 成功创建节点: {identifier}")
                return node
            except Exception as e:
                logger.error(f"❌ 创建节点失败: {identifier} - {e}")
                return None
        else:
            logger.error(f"❌ 未找到节点类: {identifier}")
            return None

    def get_node_info(self, identifier: str) -> Dict[str, Any]:
        """获取节点信息"""
        node_class = self.registry.get_node_class(identifier)
        metadata = self.registry.get_node_metadata(identifier)

        if node_class:
            return {
                'identifier': identifier,
                'class_name': node_class.__name__,
                'node_name': getattr(node_class, 'NODE_NAME', node_class.__name__),
                'category': self._get_category_by_identifier(identifier),
                'metadata': metadata,
                'available': True
            }
        else:
            return {
                'identifier': identifier,
                'available': False
            }

    def _get_category_by_identifier(self, identifier: str) -> str:
        """根据标识符获取类别"""
        for category, nodes in self.registry._categories.items():
            if identifier in nodes:
                return category
        return "Unknown"

    def get_workflow_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取工作流模板"""
        return config_manager.get_workflow_templates_config()

    def validate_workflow(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """验证工作流配置"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }

        nodes = workflow_config.get('nodes', [])
        connections = workflow_config.get('connections', [])

        # 验证节点
        for node in nodes:
            node_type = node.get('type')
            if not self.registry.get_node_class(node_type):
                validation_result['valid'] = False
                validation_result['errors'].append(f"未找到节点类型: {node_type}")

        # 验证连接
        node_ids = [node.get('id') for node in nodes]
        for conn in connections:
            from_id = conn.get('from')
            to_id = conn.get('to')

            if from_id not in node_ids:
                validation_result['valid'] = False
                validation_result['errors'].append(f"连接源节点不存在: {from_id}")

            if to_id not in node_ids:
                validation_result['valid'] = False
                validation_result['errors'].append(f"连接目标节点不存在: {to_id}")

        return validation_result

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'total_nodes': len(self.registry.get_all_nodes()),
            'categories': self.registry.get_all_categories(),
            'loaded_modules': list(self._loaded_modules),
            'qlib_core_available': self._check_qlib_core_availability(),
            'node_distribution': {
                category: len(nodes)
                for category, nodes in self.registry._categories.items()
            }
        }

    def _check_qlib_core_availability(self) -> bool:
        """检查Qlib核心可用性"""
        try:
            from core.qlib_core_integration import qlib_core
            return qlib_core.qlib_available
        except:
            return False

# 全局统一节点管理器实例
unified_node_manager = UnifiedNodeManager()
