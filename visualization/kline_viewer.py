#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib K线浏览器
提供交互式K线图浏览、技术指标分析、数据导出等功能
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 尝试导入绘图库
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QLineEdit, QDateEdit, QTableWidget,
        QTableWidgetItem, QTabWidget, QSplitter, QScrollArea, QFrame,
        QGroupBox, QCheckBox, QSpinBox, QSlider, QProgressBar, QStatusBar,
        QMenuBar, QMenu, QToolBar, QAction, QFileDialog, QMessageBox
    )
    from PySide6.QtCore import Qt, QTimer, QThread, Signal, QDate, QDateTime
    from PySide6.QtGui import QFont, QIcon, QPixmap, QPalette, QColor
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

class RockXQlibChartType(Enum):
    """图表类型枚举"""
    CANDLESTICK = "candlestick"
    LINE = "line"
    BAR = "bar"
    VOLUME = "volume"
    MACD = "macd"
    RSI = "rsi"
    BOLLINGER = "bollinger"

@dataclass
class RockXQlibTechnicalIndicator:
    """技术指标"""
    name: str
    data: pd.Series
    color: str = "blue"
    line_width: int = 1
    visible: bool = True

class RockXQlibKlineViewer:
    """K线浏览器"""
    
    def __init__(self, data_source=None):
        self.data_source = data_source
        self.current_data = pd.DataFrame()
        self.indicators = {}
        self.chart_type = RockXQlibChartType.CANDLESTICK
        self.time_range = None
        self.selected_symbols = []
        
        # 配置
        self.config = {
            'candlestick_color_up': '#00ff00',
            'candlestick_color_down': '#ff0000',
            'volume_color': '#888888',
            'background_color': '#ffffff',
            'grid_color': '#cccccc',
            'text_color': '#000000'
        }
        
        # 统计信息
        self.view_count = 0
        self.start_time = time.time()
    
    def load_data(self, data: pd.DataFrame, symbol: str = "") -> bool:
        """加载数据"""
        try:
            if data.empty:
                logger.warning("数据为空")
                return False
            
            # 验证数据格式
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in data.columns for col in required_columns):
                logger.error(f"数据缺少必要列: {required_columns}")
                return False
            
            # 确保有日期索引
            if not isinstance(data.index, pd.DatetimeIndex):
                if 'datetime' in data.columns:
                    data = data.set_index('datetime')
                else:
                    logger.error("数据没有日期索引")
                    return False
            
            self.current_data = data.sort_index()
            self.view_count += 1
            
            logger.info(f"加载了 {len(data)} 条K线数据")
            return True
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return False
    
    def add_technical_indicator(self, name: str, indicator_data: pd.Series, 
                              color: str = "blue", line_width: int = 1) -> bool:
        """添加技术指标"""
        try:
            indicator = RockXQlibTechnicalIndicator(
                name=name,
                data=indicator_data,
                color=color,
                line_width=line_width
            )
            
            self.indicators[name] = indicator
            logger.info(f"添加技术指标: {name}")
            return True
            
        except Exception as e:
            logger.error(f"添加技术指标失败: {e}")
            return False
    
    def calculate_ma(self, period: int) -> pd.Series:
        """计算移动平均线"""
        try:
            if self.current_data.empty:
                return pd.Series()
            
            return self.current_data['close'].rolling(window=period).mean()
        except Exception as e:
            logger.error(f"计算MA{period}失败: {e}")
            return pd.Series()
    
    def calculate_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """计算MACD指标"""
        try:
            if self.current_data.empty:
                return {}
            
            close = self.current_data['close']
            
            # 计算EMA
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            
            # MACD线
            macd_line = ema_fast - ema_slow
            
            # 信号线
            signal_line = macd_line.ewm(span=signal).mean()
            
            # 柱状图
            histogram = macd_line - signal_line
            
            return {
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            }
            
        except Exception as e:
            logger.error(f"计算MACD失败: {e}")
            return {}
    
    def calculate_rsi(self, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        try:
            if self.current_data.empty:
                return pd.Series()
            
            close = self.current_data['close']
            delta = close.diff()
            
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"计算RSI失败: {e}")
            return pd.Series()
    
    def calculate_bollinger_bands(self, period: int = 20, std_dev: float = 2) -> Dict[str, pd.Series]:
        """计算布林带"""
        try:
            if self.current_data.empty:
                return {}
            
            close = self.current_data['close']
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            return {
                'upper': upper_band,
                'middle': sma,
                'lower': lower_band
            }
            
        except Exception as e:
            logger.error(f"计算布林带失败: {e}")
            return {}
    
    def create_candlestick_chart(self, data: Optional[pd.DataFrame] = None, 
                               title: str = "K线图") -> Optional[go.Figure]:
        """创建K线图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            chart_data = data if data is not None else self.current_data
            if chart_data.empty:
                logger.warning("没有数据可显示")
                return None
            
            # 创建子图
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                subplot_titles=(title, '成交量'),
                row_width=[0.7, 0.3]
            )
            
            # K线图
            fig.add_trace(
                go.Candlestick(
                    x=chart_data.index,
                    open=chart_data['open'],
                    high=chart_data['high'],
                    low=chart_data['low'],
                    close=chart_data['close'],
                    name="K线",
                    increasing_line_color=self.config['candlestick_color_up'],
                    decreasing_line_color=self.config['candlestick_color_down']
                ),
                row=1, col=1
            )
            
            # 成交量
            fig.add_trace(
                go.Bar(
                    x=chart_data.index,
                    y=chart_data['volume'],
                    name="成交量",
                    marker_color=self.config['volume_color']
                ),
                row=2, col=1
            )
            
            # 添加技术指标
            for name, indicator in self.indicators.items():
                if indicator.visible:
                    fig.add_trace(
                        go.Scatter(
                            x=chart_data.index,
                            y=indicator.data,
                            name=name,
                            line=dict(color=indicator.color, width=indicator.line_width)
                        ),
                        row=1, col=1
                    )
            
            # 更新布局
            fig.update_layout(
                title=title,
                xaxis_rangeslider_visible=False,
                height=600,
                showlegend=True,
                template="plotly_white"
            )
            
            # 更新x轴
            fig.update_xaxes(type="date")
            
            return fig
            
        except Exception as e:
            logger.error(f"创建K线图失败: {e}")
            return None
    
    def create_line_chart(self, data: Optional[pd.DataFrame] = None, 
                         column: str = "close", title: str = "价格走势") -> Optional[go.Figure]:
        """创建线图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            chart_data = data if data is not None else self.current_data
            if chart_data.empty:
                logger.warning("没有数据可显示")
                return None
            
            fig = go.Figure()
            
            # 主价格线
            fig.add_trace(
                go.Scatter(
                    x=chart_data.index,
                    y=chart_data[column],
                    name=column,
                    line=dict(color='blue', width=2)
                )
            )
            
            # 添加技术指标
            for name, indicator in self.indicators.items():
                if indicator.visible:
                    fig.add_trace(
                        go.Scatter(
                            x=chart_data.index,
                            y=indicator.data,
                            name=name,
                            line=dict(color=indicator.color, width=indicator.line_width)
                        )
                    )
            
            # 更新布局
            fig.update_layout(
                title=title,
                xaxis_title="时间",
                yaxis_title="价格",
                height=400,
                showlegend=True,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建线图失败: {e}")
            return None
    
    def create_volume_chart(self, data: Optional[pd.DataFrame] = None, 
                          title: str = "成交量") -> Optional[go.Figure]:
        """创建成交量图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            chart_data = data if data is not None else self.current_data
            if chart_data.empty:
                logger.warning("没有数据可显示")
                return None
            
            fig = go.Figure()
            
            # 成交量柱状图
            fig.add_trace(
                go.Bar(
                    x=chart_data.index,
                    y=chart_data['volume'],
                    name="成交量",
                    marker_color=self.config['volume_color']
                )
            )
            
            # 更新布局
            fig.update_layout(
                title=title,
                xaxis_title="时间",
                yaxis_title="成交量",
                height=300,
                showlegend=True,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建成交量图失败: {e}")
            return None
    
    def export_chart(self, fig: go.Figure, filename: str, format: str = "html") -> bool:
        """导出图表"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return False
            
            if format == "html":
                fig.write_html(filename)
            elif format == "png":
                fig.write_image(filename)
            elif format == "pdf":
                fig.write_image(filename)
            else:
                logger.error(f"不支持的格式: {format}")
                return False
            
            logger.info(f"图表已导出: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"导出图表失败: {e}")
            return False
    
    def export_data(self, filename: str, format: str = "csv") -> bool:
        """导出数据"""
        try:
            if self.current_data.empty:
                logger.warning("没有数据可导出")
                return False
            
            if format == "csv":
                self.current_data.to_csv(filename, encoding='utf-8-sig')
            elif format == "excel":
                self.current_data.to_excel(filename)
            elif format == "json":
                self.current_data.to_json(filename, orient='index', date_format='iso')
            else:
                logger.error(f"不支持的格式: {format}")
                return False
            
            logger.info(f"数据已导出: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return False
    
    def get_data_summary(self) -> Dict[str, Any]:
        """获取数据摘要"""
        try:
            if self.current_data.empty:
                return {}
            
            summary = {
                'symbol_count': len(self.current_data),
                'date_range': {
                    'start': self.current_data.index.min().strftime('%Y-%m-%d'),
                    'end': self.current_data.index.max().strftime('%Y-%m-%d')
                },
                'price_range': {
                    'min': self.current_data['low'].min(),
                    'max': self.current_data['high'].max(),
                    'current': self.current_data['close'].iloc[-1] if len(self.current_data) > 0 else 0
                },
                'volume_stats': {
                    'total': self.current_data['volume'].sum(),
                    'avg': self.current_data['volume'].mean(),
                    'max': self.current_data['volume'].max()
                },
                'indicators_count': len(self.indicators)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取数据摘要失败: {e}")
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        return {
            'uptime': uptime,
            'view_count': self.view_count,
            'data_points': len(self.current_data),
            'indicators_count': len(self.indicators),
            'chart_type': self.chart_type.value
        }
