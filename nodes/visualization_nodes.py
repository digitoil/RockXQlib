#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可视化节点
集成K线图、回测可视化、图表引擎等功能
"""

import os
import sys
import logging
import json
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Union

# 添加路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# NodeGraphQt 是硬依赖，必须显式失败；其余为可选组件，各自独立降级。
# 原实现把它们放在同一个 try 里，任一失败就把 BaseNode 换成空壳占位类，
# 导致节点失去 add_input/add_output 等全部端口 API。
from NodeGraphQt import BaseNode
NODEGRAPH_AVAILABLE = True

try:
    from core.qlib_core_integration import qlib_core
except ImportError as e:
    print(f"qlib_core 不可用: {e}")
    qlib_core = None

try:
    from visualization.kline_viewer import RockXQlibKlineViewer
    from visualization.backtest_visualizer import RockXQlibBacktestVisualizer
    from visualization.chart_engine import RockXQlibChartEngine
    from visualization.dashboard import RockXQlibDashboard
except ImportError as e:
    print(f"可视化组件不可用，相关节点将降级: {e}")
    RockXQlibKlineViewer = None
    RockXQlibBacktestVisualizer = None
    RockXQlibChartEngine = None
    RockXQlibDashboard = None

logger = logging.getLogger(__name__)

class QlibCoreBaseNode(BaseNode):
    """基于Qlib核心的基节点"""
    
    def __init__(self):
        super().__init__()
        self.qlib_core = qlib_core
        self._execution_result = None
        self._error_message = None
    
    def execute_qlib_operation(self, operation: str, **kwargs) -> Any:
        """执行Qlib操作"""
        try:
            if not self.qlib_core or not self.qlib_core.qlib_available:
                raise Exception("Qlib不可用")
            
            if operation == "initialize":
                return self.qlib_core.initialize_qlib(**kwargs)
            elif operation == "get_data":
                return self.qlib_core.get_qlib_data(**kwargs)
            elif operation == "create_dataset":
                return self.qlib_core.create_dataset(**kwargs)
            elif operation == "create_model":
                return self.qlib_core.create_model(**kwargs)
            elif operation == "create_strategy":
                return self.qlib_core.create_strategy(**kwargs)
            elif operation == "run_backtest":
                return self.qlib_core.run_backtest(**kwargs)
            else:
                raise Exception(f"未知的Qlib操作: {operation}")
                
        except Exception as e:
            logger.error(f"Qlib操作失败: {e}")
            self._error_message = str(e)
            return None
    
    def get_execution_result(self) -> Any:
        """获取执行结果"""
        return self._execution_result
    
    def get_error_message(self) -> Optional[str]:
        """获取错误信息"""
        return self._error_message

class QlibKlineViewerNode(QlibCoreBaseNode):
    """Qlib K线图可视化节点"""
    
    __identifier__ = 'qlib.viz.kline'
    NODE_NAME = 'K线图查看器'
    type_ = 'qlib.viz.kline'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('market_data')
        self.add_output('kline_chart')
        
        # 添加属性
        self.add_text_input('symbol', '股票代码', '000001.SZ')
        self.add_text_input('start_date', '开始日期', '2023-01-01')
        self.add_text_input('end_date', '结束日期', '2023-12-31')
        self.add_text_input('chart_type', '图表类型', 'candlestick')
        self.add_checkbox('show_volume', '显示成交量', '显示成交量', True)
        self.add_checkbox('show_indicators', '显示技术指标', '显示技术指标', True)
        self.add_text_input('indicators', '技术指标', 'MA5,MA10,MA20')
        self.add_text_input('output_format', '输出格式', 'html')
    
    def execute(self) -> bool:
        """执行K线图可视化"""
        try:
            # 检查输入
            market_data = self.get_input('market_data')
            
            symbol = self.get_property('symbol')
            start_date = self.get_property('start_date')
            end_date = self.get_property('end_date')
            chart_type = self.get_property('chart_type')
            show_volume = self.get_property('show_volume')
            show_indicators = self.get_property('show_indicators')
            indicators = self.get_property('indicators')
            output_format = self.get_property('output_format')
            
            # 使用K线图查看器
            if RockXQlibKlineViewer:
                kline_viewer = RockXQlibKlineViewer()
                
                # 准备数据
                if market_data is None:
                    # 如果没有输入数据，尝试获取数据
                    if self.qlib_core and self.qlib_core.qlib_available:
                        market_data = self.qlib_core.get_qlib_data(
                            instruments=symbol,
                            start_time=start_date,
                            end_time=end_date
                        )
                    else:
                        # 生成模拟数据
                        market_data = self._generate_mock_data(symbol, start_date, end_date)
                
                # 创建K线图
                chart_result = kline_viewer.create_kline_chart(
                    data=market_data,
                    symbol=symbol,
                    chart_type=chart_type,
                    show_volume=show_volume,
                    show_indicators=show_indicators,
                    indicators=indicators.split(',') if indicators else [],
                    output_format=output_format
                )
                
                self._execution_result = {
                    'status': 'success',
                    'symbol': symbol,
                    'chart_type': chart_type,
                    'chart_result': chart_result,
                    'output_format': output_format
                }
                self.set_output('kline_chart', self._execution_result)
                logger.info(f"✅ K线图创建完成: {symbol}")
                return True
            else:
                # 模拟K线图创建
                mock_chart = f"模拟K线图: {symbol} ({start_date} - {end_date})"
                
                self._execution_result = {
                    'status': 'success',
                    'symbol': symbol,
                    'chart_type': chart_type,
                    'chart_result': mock_chart,
                    'output_format': output_format
                }
                self.set_output('kline_chart', self._execution_result)
                logger.info(f"✅ 模拟K线图创建完成: {symbol}")
                return True
                
        except Exception as e:
            logger.error(f"K线图节点执行失败: {e}")
            return False
    
    def _generate_mock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """生成模拟数据"""
        dates = pd.date_range(start_date, end_date, freq='D')
        n_days = len(dates)
        
        # 生成模拟价格数据
        base_price = 100.0
        price_changes = np.random.randn(n_days) * 0.02
        prices = base_price * np.exp(np.cumsum(price_changes))
        
        data = pd.DataFrame({
            'open': prices * (1 + np.random.randn(n_days) * 0.01),
            'high': prices * (1 + np.abs(np.random.randn(n_days)) * 0.02),
            'low': prices * (1 - np.abs(np.random.randn(n_days)) * 0.02),
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, n_days)
        }, index=dates)
        
        return data

class QlibBacktestVisualizerNode(QlibCoreBaseNode):
    """Qlib回测可视化节点"""
    
    __identifier__ = 'qlib.viz.backtest'
    NODE_NAME = '回测可视化'
    type_ = 'qlib.viz.backtest'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('backtest_results')
        self.add_output('backtest_charts')
        
        # 添加属性
        self.add_text_input('chart_types', '图表类型', 'equity_curve,drawdown,returns')
        self.add_checkbox('show_benchmark', '显示基准', '显示基准', True)
        self.add_text_input('benchmark_symbol', '基准代码', 'SH000300')
        self.add_checkbox('show_metrics', '显示指标', '显示指标', True)
        self.add_text_input('output_format', '输出格式', 'html')
        self.add_text_input('save_path', '保存路径', './backtest_charts/')
    
    def execute(self) -> bool:
        """执行回测可视化"""
        try:
            # 检查输入
            backtest_results = self.get_input('backtest_results')
            if not backtest_results:
                raise Exception("回测结果为空")
            
            chart_types = self.get_property('chart_types')
            show_benchmark = self.get_property('show_benchmark')
            benchmark_symbol = self.get_property('benchmark_symbol')
            show_metrics = self.get_property('show_metrics')
            output_format = self.get_property('output_format')
            save_path = self.get_property('save_path')
            
            # 使用回测可视化器
            if RockXQlibBacktestVisualizer:
                backtest_viz = RockXQlibBacktestVisualizer()
                
                # 创建回测图表
                charts_result = backtest_viz.create_backtest_charts(
                    backtest_results=backtest_results,
                    chart_types=chart_types.split(',') if chart_types else ['equity_curve'],
                    show_benchmark=show_benchmark,
                    benchmark_symbol=benchmark_symbol,
                    show_metrics=show_metrics,
                    output_format=output_format,
                    save_path=save_path
                )
                
                self._execution_result = {
                    'status': 'success',
                    'chart_types': chart_types,
                    'charts_result': charts_result,
                    'output_format': output_format,
                    'save_path': save_path
                }
                self.set_output('backtest_charts', self._execution_result)
                logger.info(f"✅ 回测图表创建完成: {chart_types}")
                return True
            else:
                # 模拟回测可视化
                mock_charts = f"模拟回测图表: {chart_types}"
                
                self._execution_result = {
                    'status': 'success',
                    'chart_types': chart_types,
                    'charts_result': mock_charts,
                    'output_format': output_format,
                    'save_path': save_path
                }
                self.set_output('backtest_charts', self._execution_result)
                logger.info(f"✅ 模拟回测图表创建完成: {chart_types}")
                return True
                
        except Exception as e:
            logger.error(f"回测可视化节点执行失败: {e}")
            return False

class QlibChartEngineNode(QlibCoreBaseNode):
    """Qlib图表引擎节点"""
    
    __identifier__ = 'qlib.viz.chart_engine'
    NODE_NAME = '图表引擎'
    type_ = 'qlib.viz.chart_engine'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('data_input')
        self.add_output('chart_output')
        
        # 添加属性
        self.add_text_input('chart_type', '图表类型', 'line')
        self.add_text_input('title', '图表标题', '数据图表')
        self.add_text_input('x_axis', 'X轴', 'date')
        self.add_text_input('y_axis', 'Y轴', 'value')
        self.add_text_input('color_scheme', '配色方案', 'default')
        self.add_text_input('output_format', '输出格式', 'html')
        # 注意：'width' / 'height' 是 NodeGraphQt 的保留属性（控制节点视觉尺寸），
        # 用作自定义属性会抛 NodePropertyError，故加 chart_ 前缀
        self.add_text_input('chart_width', '宽度', '800')
        self.add_text_input('chart_height', '高度', '600')
    
    def execute(self) -> bool:
        """执行图表引擎"""
        try:
            # 检查输入
            data_input = self.get_input('data_input')
            if not data_input:
                raise Exception("输入数据为空")
            
            chart_type = self.get_property('chart_type')
            title = self.get_property('title')
            x_axis = self.get_property('x_axis')
            y_axis = self.get_property('y_axis')
            color_scheme = self.get_property('color_scheme')
            output_format = self.get_property('output_format')
            width = int(self.get_property('chart_width'))
            height = int(self.get_property('chart_height'))
            
            # 使用图表引擎
            if RockXQlibChartEngine:
                chart_engine = RockXQlibChartEngine()
                
                # 创建图表
                chart_result = chart_engine.create_chart(
                    data=data_input,
                    chart_type=chart_type,
                    title=title,
                    x_axis=x_axis,
                    y_axis=y_axis,
                    color_scheme=color_scheme,
                    output_format=output_format,
                    width=width,
                    height=height
                )
                
                self._execution_result = {
                    'status': 'success',
                    'chart_type': chart_type,
                    'title': title,
                    'chart_result': chart_result,
                    'output_format': output_format,
                    'dimensions': {'width': width, 'height': height}
                }
                self.set_output('chart_output', self._execution_result)
                logger.info(f"✅ 图表创建完成: {chart_type}")
                return True
            else:
                # 模拟图表创建
                mock_chart = f"模拟图表: {title} ({chart_type})"
                
                self._execution_result = {
                    'status': 'success',
                    'chart_type': chart_type,
                    'title': title,
                    'chart_result': mock_chart,
                    'output_format': output_format,
                    'dimensions': {'width': width, 'height': height}
                }
                self.set_output('chart_output', self._execution_result)
                logger.info(f"✅ 模拟图表创建完成: {chart_type}")
                return True
                
        except Exception as e:
            logger.error(f"图表引擎节点执行失败: {e}")
            return False

class QlibDashboardNode(QlibCoreBaseNode):
    """Qlib仪表板节点"""
    
    __identifier__ = 'qlib.viz.dashboard'
    NODE_NAME = '仪表板'
    type_ = 'qlib.viz.dashboard'
    
    def __init__(self):
        super().__init__()
        
        # 添加输入输出端口
        self.add_input('multiple_inputs')
        self.add_output('dashboard_output')
        
        # 添加属性
        self.add_text_input('dashboard_title', '仪表板标题', '量化分析仪表板')
        self.add_text_input('layout_type', '布局类型', 'grid')
        self.add_text_input('grid_columns', '网格列数', '2')
        self.add_text_input('grid_rows', '网格行数', '2')
        self.add_checkbox('auto_refresh', '自动刷新', '自动刷新', True)
        self.add_text_input('refresh_interval', '刷新间隔(秒)', '60')
        self.add_text_input('output_format', '输出格式', 'html')
        self.add_text_input('save_path', '保存路径', './dashboard/')
    
    def execute(self) -> bool:
        """执行仪表板创建"""
        try:
            # 检查输入
            multiple_inputs = self.get_input('multiple_inputs')
            
            dashboard_title = self.get_property('dashboard_title')
            layout_type = self.get_property('layout_type')
            grid_columns = int(self.get_property('grid_columns'))
            grid_rows = int(self.get_property('grid_rows'))
            auto_refresh = self.get_property('auto_refresh')
            refresh_interval = int(self.get_property('refresh_interval'))
            output_format = self.get_property('output_format')
            save_path = self.get_property('save_path')
            
            # 使用仪表板
            if RockXQlibDashboard:
                dashboard = RockXQlibDashboard()
                
                # 创建仪表板
                dashboard_result = dashboard.create_dashboard(
                    title=dashboard_title,
                    layout_type=layout_type,
                    grid_columns=grid_columns,
                    grid_rows=grid_rows,
                    auto_refresh=auto_refresh,
                    refresh_interval=refresh_interval,
                    output_format=output_format,
                    save_path=save_path,
                    data_inputs=multiple_inputs
                )
                
                self._execution_result = {
                    'status': 'success',
                    'dashboard_title': dashboard_title,
                    'layout_type': layout_type,
                    'dashboard_result': dashboard_result,
                    'output_format': output_format,
                    'save_path': save_path
                }
                self.set_output('dashboard_output', self._execution_result)
                logger.info(f"✅ 仪表板创建完成: {dashboard_title}")
                return True
            else:
                # 模拟仪表板创建
                mock_dashboard = f"模拟仪表板: {dashboard_title} ({layout_type})"
                
                self._execution_result = {
                    'status': 'success',
                    'dashboard_title': dashboard_title,
                    'layout_type': layout_type,
                    'dashboard_result': mock_dashboard,
                    'output_format': output_format,
                    'save_path': save_path
                }
                self.set_output('dashboard_output', self._execution_result)
                logger.info(f"✅ 模拟仪表板创建完成: {dashboard_title}")
                return True
                
        except Exception as e:
            logger.error(f"仪表板节点执行失败: {e}")
            return False

# 导出所有节点类
__all__ = [
    'QlibCoreBaseNode',
    'QlibKlineViewerNode',
    'QlibBacktestVisualizerNode',
    'QlibChartEngineNode',
    'QlibDashboardNode'
]
