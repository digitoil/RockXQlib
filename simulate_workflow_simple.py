#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版工作流模拟程序
使用LSTM Alpha360配置作为示例，展示完整的节点执行流程
使用RockXQlib的真实节点进行模拟
"""

import os
import sys
import yaml
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 设置环境变量
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8.dev6'
os.environ['QLIB_DATA_PATH'] = '~/.qlib/qlib_data/cn_data'
os.environ['QLIB_LOG_LEVEL'] = 'INFO'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('workflow_simulation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 导入RockXQlib节点
try:
    from nodes.qlib_core_nodes import (
        QlibInitNode, QlibDataNode, QlibDatasetNode,
        QlibModelNode, QlibStrategyNode, QlibBacktestNode
    )
    from core.qlib_core_integration import QlibCoreIntegration
    ROCKXQLIB_NODES_AVAILABLE = True
    print("RockXQlib节点导入成功")
except ImportError as e:
    ROCKXQLIB_NODES_AVAILABLE = False
    print(f"RockXQlib节点导入失败: {e}")

@dataclass
class NodeExecutionResult:
    """节点执行结果"""
    node_id: str
    node_type: str
    success: bool
    execution_time: float
    outputs: Dict[str, Any] = None
    error_message: str = ""

    def __post_init__(self):
        if self.outputs is None:
            self.outputs = {}

class WorkflowSimulator:
    """工作流模拟器"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
        self.execution_order = []
        self.node_results = {}
        self.signal_placeholders = {}
        self.qlib_core = None
        self.nodes = {}  # 存储创建的节点实例

        # 加载配置
        self.load_config()

        # 初始化Qlib核心
        if ROCKXQLIB_NODES_AVAILABLE:
            self.qlib_core = QlibCoreIntegration()

    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            print(f"配置文件加载成功: {self.config_path}")
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            raise

    def create_rockxqlib_nodes(self) -> Dict[str, Any]:
        """创建RockXQlib节点实例"""
        try:
            if not ROCKXQLIB_NODES_AVAILABLE:
                print("RockXQlib节点不可用")
                return {}

            nodes = {}

            # 1. 创建Qlib初始化节点
            if 'qlib_init' in self.config:
                qlib_config = self.config['qlib_init']
                init_node = QlibInitNode()
                init_node.qlib_core = self.qlib_core
                # 设置属性
                for key, value in qlib_config.items():
                    init_node.set_property(key, str(value))
                nodes['qlib_init'] = init_node
                print("创建Qlib初始化节点")

            # 2. 创建数据处理器节点
            if 'data_handler_config' in self.config:
                handler_config = self.config['data_handler_config']
                data_node = QlibDataNode()
                data_node.qlib_core = self.qlib_core
                # 设置属性
                data_node.set_property('handler_class', 'Alpha360')
                data_node.set_property('module_path', 'qlib.contrib.data.handler')
                data_node.set_property('handler_kwargs', str(handler_config))
                nodes['data_handler'] = data_node
                print("创建Alpha360数据处理器节点")

            # 3. 创建数据集节点
            if 'task' in self.config and 'dataset' in self.config['task']:
                dataset_config = self.config['task']['dataset']
                dataset_node = QlibDatasetNode()
                dataset_node.qlib_core = self.qlib_core
                # 设置属性
                dataset_node.set_property('dataset_class', dataset_config.get('class', 'DatasetH'))
                dataset_node.set_property('module_path', dataset_config.get('module_path', 'qlib.data.dataset'))
                dataset_node.set_property('handler_class', dataset_config['kwargs']['handler']['class'])
                dataset_node.set_property('handler_module_path', dataset_config['kwargs']['handler']['module_path'])
                dataset_node.set_property('handler_kwargs', str(dataset_config['kwargs']['handler']['kwargs']))
                dataset_node.set_property('segments', str(dataset_config['kwargs']['segments']))
                nodes['dataset'] = dataset_node
                print("创建数据集节点")

            # 4. 创建模型节点
            if 'task' in self.config and 'model' in self.config['task']:
                model_config = self.config['task']['model']
                model_node = QlibModelNode()
                model_node.qlib_core = self.qlib_core
                # 设置属性
                model_node.set_property('model_class', model_config.get('class', 'LSTM'))
                model_node.set_property('module_path', model_config.get('module_path', 'qlib.contrib.model.pytorch_lstm'))
                model_node.set_property('model_params', str(model_config.get('kwargs', {})))
                nodes['model'] = model_node
                print("创建LSTM模型节点")

            # 5. 创建策略节点
            if 'port_analysis_config' in self.config and 'strategy' in self.config['port_analysis_config']:
                strategy_config = self.config['port_analysis_config']['strategy'].copy()

                # 处理signal参数：如果signal在kwargs中，提取到顶层
                if 'kwargs' in strategy_config and 'signal' in strategy_config['kwargs']:
                    signal_value = strategy_config['kwargs'].pop('signal')
                    strategy_config['signal'] = signal_value
                    print(f"将signal从kwargs提取到顶层: {signal_value}")

                # 添加信号占位符处理标记
                strategy_config['_has_signal_placeholder'] = True
                strategy_config['_signal_placeholder'] = '<PRED>'

                strategy_node = QlibStrategyNode()
                strategy_node.qlib_core = self.qlib_core
                # 设置属性
                strategy_node.set_property('strategy_class', strategy_config.get('class', 'TopkDropoutStrategy'))
                strategy_node.set_property('module_path', strategy_config.get('module_path', 'qlib.contrib.strategy'))
                strategy_node.set_property('signal', strategy_config.get('signal', '<PRED>'))
                strategy_node.set_property('strategy_params', str(strategy_config.get('kwargs', {})))
                strategy_node.set_property('_has_signal_placeholder', 'True')
                strategy_node.set_property('_signal_placeholder', '<PRED>')
                nodes['strategy'] = strategy_node
                print("创建TopK策略节点")

            # 6. 创建回测节点
            if 'port_analysis_config' in self.config and 'backtest' in self.config['port_analysis_config']:
                backtest_config = self.config['port_analysis_config']['backtest']
                # 添加策略配置到回测配置中
                if 'strategy' in self.config['port_analysis_config']:
                    backtest_config['strategy_config'] = self.config['port_analysis_config']['strategy']

                backtest_node = QlibBacktestNode()
                backtest_node.qlib_core = self.qlib_core
                # 设置属性
                backtest_node.set_property('start_time', backtest_config.get('start_time', '2017-01-01'))
                backtest_node.set_property('end_time', backtest_config.get('end_time', '2020-08-01'))
                backtest_node.set_property('account', str(backtest_config.get('account', 100000000)))
                backtest_node.set_property('benchmark', backtest_config.get('benchmark', 'SH000300'))
                backtest_node.set_property('strategy_config', str(backtest_config.get('strategy_config', {})))
                nodes['backtest'] = backtest_node
                print("创建回测节点")

            return nodes

        except Exception as e:
            print(f"创建RockXQlib节点失败: {e}")
            raise

    def execute_rockxqlib_node(self, node_id: str, node: Any) -> NodeExecutionResult:
        """执行RockXQlib节点"""
        node_name = node.__class__.__name__
        print(f"开始执行节点: {node_name} ({node_id})")
        start_time = time.time()

        try:
            # 执行节点
            success = node.execute()
            execution_time = time.time() - start_time

            if success:
                print(f"{node_name} 执行成功 (耗时: {execution_time:.2f}s)")

                # 获取节点输出
                outputs = self._get_node_outputs(node, node_id)

                return NodeExecutionResult(
                    node_id=node_id,
                    node_type=node_name,
                    success=True,
                    execution_time=execution_time,
                    outputs=outputs
                )
            else:
                print(f"{node_name} 执行失败")
                return NodeExecutionResult(
                    node_id=node_id,
                    node_type=node_name,
                    success=False,
                    execution_time=execution_time,
                    error_message="节点执行返回False"
                )

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"{node_name} 执行异常: {e}")
            return NodeExecutionResult(
                node_id=node_id,
                node_type=node_name,
                success=False,
                execution_time=execution_time,
                error_message=str(e)
            )

    def _get_node_outputs(self, node: Any, node_id: str) -> Dict[str, Any]:
        """获取节点输出"""
        try:
            outputs = {}

            # 根据节点类型获取不同的输出
            if hasattr(node, 'qlib_data') and node.qlib_data:
                outputs['qlib_data'] = node.qlib_data

            if hasattr(node, 'dataset') and node.dataset:
                outputs['dataset'] = node.dataset

            if hasattr(node, 'model') and node.model:
                outputs['model'] = node.model

            if hasattr(node, 'predictions') and node.predictions is not None:
                outputs['predictions'] = node.predictions

            if hasattr(node, 'strategy') and node.strategy:
                outputs['strategy'] = node.strategy

            if hasattr(node, 'signal') and node.signal:
                outputs['signal'] = node.signal

            if hasattr(node, 'backtest_result') and node.backtest_result:
                outputs['backtest_result'] = node.backtest_result

            # 特殊处理：模型节点生成预测结果
            if node_id == 'model' and hasattr(node, 'model') and node.model:
                # 生成模拟预测结果用于演示
                predictions = self._generate_mock_predictions()
                outputs['predictions'] = predictions
                # 将预测结果存储到节点中
                node.predictions = predictions

            return outputs

        except Exception as e:
            print(f"获取节点输出失败: {e}")
            return {}

    def _generate_mock_predictions(self) -> pd.DataFrame:
        """生成模拟预测结果"""
        try:
            # 生成模拟的预测数据
            dates = pd.date_range('2017-01-01', '2020-08-01', freq='D')
            instruments = [f'SH60000{i:03d}' for i in range(1, 301)]  # 模拟300只股票

            # 创建多级索引
            index = pd.MultiIndex.from_product([dates, instruments], names=['datetime', 'instrument'])

            # 生成模拟预测分数
            np.random.seed(42)  # 固定随机种子以便复现
            predictions = pd.DataFrame({
                'score': np.random.randn(len(index))
            }, index=index)

            print(f"生成了 {len(predictions)} 条预测记录")
            return predictions

        except Exception as e:
            print(f"生成模拟预测结果失败: {e}")
            return pd.DataFrame()

    def execute_workflow(self) -> Dict[str, Any]:
        """执行完整工作流"""
        try:
            print("开始执行LSTM Alpha360工作流模拟")
            print("=" * 60)

            if not ROCKXQLIB_NODES_AVAILABLE:
                print("RockXQlib节点不可用，无法执行工作流")
                return {'success': False, 'error': 'RockXQlib节点不可用'}

            # 创建RockXQlib节点
            self.nodes = self.create_rockxqlib_nodes()

            # 按依赖顺序执行节点
            execution_order = ['qlib_init', 'data_handler', 'dataset', 'model', 'strategy', 'backtest']

            for node_id in execution_order:
                if node_id not in self.nodes:
                    print(f"未找到节点: {node_id}")
                    continue

                node = self.nodes[node_id]

                # 执行节点
                result = self.execute_rockxqlib_node(node_id, node)
                self.node_results[node_id] = result

                # 处理信号占位符
                if node_id == 'model' and result.success:
                    self._handle_signal_placeholder_replacement()

                if not result.success:
                    print(f"节点 {node_id} 执行失败，工作流终止")
                    break

            # 生成执行报告
            return self._generate_execution_report()

        except Exception as e:
            print(f"工作流执行失败: {e}")
            return {'success': False, 'error': str(e)}

    def _handle_signal_placeholder_replacement(self):
        """处理信号占位符替换"""
        try:
            # 获取模型预测结果
            model_result = self.node_results.get('model')
            if not model_result or not model_result.success:
                return

            predictions = model_result.outputs.get('predictions')
            if predictions is not None:
                print("执行信号占位符替换...")
                print(f"将<PRED>替换为 {len(predictions)} 条预测记录")

                # 查找策略节点并替换信号
                if 'strategy' in self.nodes:
                    strategy_node = self.nodes['strategy']
                    if hasattr(strategy_node, 'set_property'):
                        # 检查是否有信号占位符标记
                        has_placeholder = strategy_node.get_property('_has_signal_placeholder')
                        if has_placeholder == 'True':
                            # 替换信号占位符
                            strategy_node.set_property('signal', predictions)
                            print("策略节点信号占位符已替换")

                print("信号占位符替换完成")

        except Exception as e:
            print(f"处理信号占位符替换失败: {e}")

    def _generate_execution_report(self) -> Dict[str, Any]:
        """生成执行报告"""
        try:
            total_time = sum(result.execution_time for result in self.node_results.values())
            success_count = sum(1 for result in self.node_results.values() if result.success)
            total_count = len(self.node_results)

            report = {
                'success': success_count == total_count,
                'workflow_id': 'lstm_alpha360_simulation',
                'total_execution_time': total_time,
                'node_count': total_count,
                'success_count': success_count,
                'failure_count': total_count - success_count,
                'node_results': {}
            }

            for node_id, result in self.node_results.items():
                report['node_results'][node_id] = {
                    'success': result.success,
                    'execution_time': result.execution_time,
                    'error_message': result.error_message,
                    'outputs': result.outputs
                }

            return report

        except Exception as e:
            print(f"生成执行报告失败: {e}")
            return {'success': False, 'error': str(e)}

    def print_execution_report(self, report: Dict[str, Any]):
        """打印执行报告"""
        print("\n" + "=" * 60)
        print("工作流执行报告")
        print("=" * 60)

        if report['success']:
            print("工作流执行成功")
        else:
            print("工作流执行失败")

        print(f"总执行时间: {report['total_execution_time']:.2f}秒")
        print(f"节点统计: {report['success_count']}/{report['node_count']} 成功")

        print("\n节点执行详情:")
        for node_id, result in report['node_results'].items():
            status = "成功" if result['success'] else "失败"
            print(f"   {status} {node_id}: {result['execution_time']:.2f}s")
            if not result['success'] and result['error_message']:
                print(f"      错误: {result['error_message']}")

        print("=" * 60)

def main():
    """主函数"""
    try:
        # 配置文件路径
        config_path = "examples/benchmarks/LSTM/workflow_config_lstm_Alpha360.yaml"

        if not os.path.exists(config_path):
            print(f"配置文件不存在: {config_path}")
            return

        # 创建工作流模拟器
        simulator = WorkflowSimulator(config_path)

        # 执行工作流
        report = simulator.execute_workflow()

        # 打印报告
        simulator.print_execution_report(report)

    except Exception as e:
        print(f"程序执行失败: {e}")

if __name__ == "__main__":
    main()
