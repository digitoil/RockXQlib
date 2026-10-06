#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 回测可视化系统
提供回测结果分析、性能指标展示、风险分析等功能
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
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

class RockXQlibBacktestChartType(Enum):
    """回测图表类型枚举"""
    EQUITY_CURVE = "equity_curve"
    DRAWDOWN = "drawdown"
    RETURNS = "returns"
    VOLATILITY = "volatility"
    SHARPE_RATIO = "sharpe_ratio"
    MONTHLY_RETURNS = "monthly_returns"
    RISK_METRICS = "risk_metrics"
    TRADE_ANALYSIS = "trade_analysis"

@dataclass
class RockXQlibBacktestMetrics:
    """回测指标"""
    total_return: float
    annual_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_duration: float

class RockXQlibBacktestVisualizer:
    """回测可视化器"""
    
    def __init__(self):
        self.backtest_data = pd.DataFrame()
        self.equity_curve = pd.Series()
        self.returns = pd.Series()
        self.trades = pd.DataFrame()
        self.benchmark_data = pd.DataFrame()
        
        # 配置
        self.config = {
            'equity_color': '#1f77b4',
            'drawdown_color': '#ff7f0e',
            'returns_color': '#2ca02c',
            'benchmark_color': '#d62728',
            'background_color': '#ffffff',
            'grid_color': '#cccccc'
        }
        
        # 统计信息
        self.visualization_count = 0
        self.start_time = time.time()
    
    def load_backtest_data(self, data: Dict[str, Any]) -> bool:
        """加载回测数据"""
        try:
            # 解析回测数据
            if 'equity_curve' in data:
                self.equity_curve = pd.Series(data['equity_curve'])
                if isinstance(self.equity_curve.index, str):
                    self.equity_curve.index = pd.to_datetime(self.equity_curve.index)
            
            if 'returns' in data:
                self.returns = pd.Series(data['returns'])
                if isinstance(self.returns.index, str):
                    self.returns.index = pd.to_datetime(self.returns.index)
            
            if 'trades' in data:
                self.trades = pd.DataFrame(data['trades'])
                if 'datetime' in self.trades.columns:
                    self.trades['datetime'] = pd.to_datetime(self.trades['datetime'])
            
            if 'benchmark' in data:
                self.benchmark_data = pd.DataFrame(data['benchmark'])
                if 'datetime' in self.benchmark_data.columns:
                    self.benchmark_data['datetime'] = pd.to_datetime(self.benchmark_data['datetime'])
                    self.benchmark_data = self.benchmark_data.set_index('datetime')
            
            self.visualization_count += 1
            logger.info("回测数据加载成功")
            return True
            
        except Exception as e:
            logger.error(f"加载回测数据失败: {e}")
            return False
    
    def calculate_metrics(self) -> RockXQlibBacktestMetrics:
        """计算回测指标"""
        try:
            if self.equity_curve.empty:
                return RockXQlibBacktestMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            
            # 总收益率
            total_return = (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0]) - 1
            
            # 年化收益率
            days = (self.equity_curve.index[-1] - self.equity_curve.index[0]).days
            annual_return = (1 + total_return) ** (365 / days) - 1
            
            # 计算日收益率
            if self.returns.empty:
                returns = self.equity_curve.pct_change().dropna()
            else:
                returns = self.returns
            
            # 波动率
            volatility = returns.std() * np.sqrt(252)
            
            # 夏普比率
            risk_free_rate = 0.03  # 假设无风险利率3%
            sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0
            
            # 最大回撤
            max_drawdown = self._calculate_max_drawdown()
            
            # 卡玛比率
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # 胜率
            win_rate = (returns > 0).mean() if not returns.empty else 0
            
            # 盈亏比
            positive_returns = returns[returns > 0]
            negative_returns = returns[returns < 0]
            profit_factor = abs(positive_returns.sum() / negative_returns.sum()) if negative_returns.sum() != 0 else 0
            
            # 交易统计
            total_trades = len(self.trades) if not self.trades.empty else 0
            avg_trade_duration = 0
            if not self.trades.empty and 'duration' in self.trades.columns:
                avg_trade_duration = self.trades['duration'].mean()
            
            return RockXQlibBacktestMetrics(
                total_return=total_return,
                annual_return=annual_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                calmar_ratio=calmar_ratio,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=total_trades,
                avg_trade_duration=avg_trade_duration
            )
            
        except Exception as e:
            logger.error(f"计算回测指标失败: {e}")
            return RockXQlibBacktestMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        try:
            if self.equity_curve.empty:
                return 0
            
            # 计算累计最高点
            cumulative_max = self.equity_curve.expanding().max()
            
            # 计算回撤
            drawdown = (self.equity_curve - cumulative_max) / cumulative_max
            
            return drawdown.min()
            
        except Exception as e:
            logger.error(f"计算最大回撤失败: {e}")
            return 0
    
    def create_equity_curve_chart(self, include_benchmark: bool = True) -> Optional[go.Figure]:
        """创建净值曲线图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            if self.equity_curve.empty:
                logger.warning("没有净值数据")
                return None
            
            fig = go.Figure()
            
            # 净值曲线
            fig.add_trace(
                go.Scatter(
                    x=self.equity_curve.index,
                    y=self.equity_curve.values,
                    name="策略净值",
                    line=dict(color=self.config['equity_color'], width=2)
                )
            )
            
            # 基准曲线
            if include_benchmark and not self.benchmark_data.empty:
                if 'close' in self.benchmark_data.columns:
                    benchmark_normalized = self.benchmark_data['close'] / self.benchmark_data['close'].iloc[0]
                    fig.add_trace(
                        go.Scatter(
                            x=benchmark_normalized.index,
                            y=benchmark_normalized.values,
                            name="基准净值",
                            line=dict(color=self.config['benchmark_color'], width=2, dash='dash')
                        )
                    )
            
            # 更新布局
            fig.update_layout(
                title="净值曲线",
                xaxis_title="时间",
                yaxis_title="净值",
                height=400,
                showlegend=True,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建净值曲线图失败: {e}")
            return None
    
    def create_drawdown_chart(self) -> Optional[go.Figure]:
        """创建回撤图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            if self.equity_curve.empty:
                logger.warning("没有净值数据")
                return None
            
            # 计算回撤
            cumulative_max = self.equity_curve.expanding().max()
            drawdown = (self.equity_curve - cumulative_max) / cumulative_max * 100
            
            fig = go.Figure()
            
            # 回撤曲线
            fig.add_trace(
                go.Scatter(
                    x=drawdown.index,
                    y=drawdown.values,
                    name="回撤",
                    fill='tonexty',
                    fillcolor='rgba(255, 127, 14, 0.3)',
                    line=dict(color=self.config['drawdown_color'], width=1)
                )
            )
            
            # 零线
            fig.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5)
            
            # 更新布局
            fig.update_layout(
                title="回撤分析",
                xaxis_title="时间",
                yaxis_title="回撤 (%)",
                height=300,
                showlegend=True,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建回撤图失败: {e}")
            return None
    
    def create_returns_chart(self) -> Optional[go.Figure]:
        """创建收益率图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            if self.returns.empty:
                logger.warning("没有收益率数据")
                return None
            
            fig = go.Figure()
            
            # 收益率柱状图
            colors = ['green' if x > 0 else 'red' for x in self.returns.values]
            fig.add_trace(
                go.Bar(
                    x=self.returns.index,
                    y=self.returns.values * 100,
                    name="日收益率",
                    marker_color=colors
                )
            )
            
            # 零线
            fig.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5)
            
            # 更新布局
            fig.update_layout(
                title="日收益率",
                xaxis_title="时间",
                yaxis_title="收益率 (%)",
                height=300,
                showlegend=True,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建收益率图失败: {e}")
            return None
    
    def create_monthly_returns_heatmap(self) -> Optional[go.Figure]:
        """创建月度收益热力图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            if self.returns.empty:
                logger.warning("没有收益率数据")
                return None
            
            # 计算月度收益率
            monthly_returns = self.returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
            
            # 创建年月矩阵
            monthly_returns.index = pd.to_datetime(monthly_returns.index)
            monthly_returns_df = monthly_returns.to_frame('returns')
            monthly_returns_df['year'] = monthly_returns_df.index.year
            monthly_returns_df['month'] = monthly_returns_df.index.month
            
            # 透视表
            pivot_table = monthly_returns_df.pivot_table(
                values='returns', 
                index='year', 
                columns='month', 
                fill_value=0
            )
            
            # 创建热力图
            fig = go.Figure(data=go.Heatmap(
                z=pivot_table.values * 100,
                x=pivot_table.columns,
                y=pivot_table.index,
                colorscale='RdYlGn',
                zmid=0,
                text=np.round(pivot_table.values * 100, 2),
                texttemplate="%{text}%",
                textfont={"size": 10},
                hoverongaps=False
            ))
            
            # 更新布局
            fig.update_layout(
                title="月度收益率热力图",
                xaxis_title="月份",
                yaxis_title="年份",
                height=400,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建月度收益热力图失败: {e}")
            return None
    
    def create_risk_metrics_chart(self) -> Optional[go.Figure]:
        """创建风险指标图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            metrics = self.calculate_metrics()
            
            # 创建子图
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('夏普比率', '最大回撤', '年化收益率', '波动率'),
                specs=[[{"type": "indicator"}, {"type": "indicator"}],
                       [{"type": "indicator"}, {"type": "indicator"}]]
            )
            
            # 夏普比率
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=metrics.sharpe_ratio,
                    title={'text': "夏普比率"},
                    gauge={'axis': {'range': [-2, 4]},
                           'bar': {'color': "darkblue"},
                           'steps': [{'range': [-2, 0], 'color': "lightgray"},
                                    {'range': [0, 1], 'color': "yellow"},
                                    {'range': [1, 2], 'color': "lightgreen"},
                                    {'range': [2, 4], 'color': "green"}]}
                ),
                row=1, col=1
            )
            
            # 最大回撤
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=abs(metrics.max_drawdown) * 100,
                    title={'text': "最大回撤 (%)"},
                    gauge={'axis': {'range': [0, 50]},
                           'bar': {'color': "darkred"},
                           'steps': [{'range': [0, 10], 'color': "lightgreen"},
                                    {'range': [10, 20], 'color': "yellow"},
                                    {'range': [20, 30], 'color': "orange"},
                                    {'range': [30, 50], 'color': "red"}]}
                ),
                row=1, col=2
            )
            
            # 年化收益率
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=metrics.annual_return * 100,
                    title={'text': "年化收益率 (%)"},
                    gauge={'axis': {'range': [-50, 100]},
                           'bar': {'color': "darkgreen"},
                           'steps': [{'range': [-50, 0], 'color': "red"},
                                    {'range': [0, 10], 'color': "yellow"},
                                    {'range': [10, 20], 'color': "lightgreen"},
                                    {'range': [20, 100], 'color': "green"}]}
                ),
                row=2, col=1
            )
            
            # 波动率
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=metrics.volatility * 100,
                    title={'text': "年化波动率 (%)"},
                    gauge={'axis': {'range': [0, 100]},
                           'bar': {'color': "darkorange"},
                           'steps': [{'range': [0, 20], 'color': "lightgreen"},
                                    {'range': [20, 40], 'color': "yellow"},
                                    {'range': [40, 60], 'color': "orange"},
                                    {'range': [60, 100], 'color': "red"}]}
                ),
                row=2, col=2
            )
            
            # 更新布局
            fig.update_layout(
                title="风险指标仪表盘",
                height=600,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建风险指标图失败: {e}")
            return None
    
    def create_trade_analysis_chart(self) -> Optional[go.Figure]:
        """创建交易分析图"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            if self.trades.empty:
                logger.warning("没有交易数据")
                return None
            
            # 创建子图
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('交易盈亏分布', '交易频率', '持仓时间分布', '累计盈亏'),
                specs=[[{"type": "histogram"}, {"type": "bar"}],
                       [{"type": "histogram"}, {"type": "scatter"}]]
            )
            
            # 交易盈亏分布
            if 'pnl' in self.trades.columns:
                fig.add_trace(
                    go.Histogram(
                        x=self.trades['pnl'],
                        name="盈亏分布",
                        nbinsx=20
                    ),
                    row=1, col=1
                )
            
            # 交易频率（按月份）
            if 'datetime' in self.trades.columns:
                trades_by_month = self.trades.set_index('datetime').resample('M').size()
                fig.add_trace(
                    go.Bar(
                        x=trades_by_month.index,
                        y=trades_by_month.values,
                        name="月度交易次数"
                    ),
                    row=1, col=2
                )
            
            # 持仓时间分布
            if 'duration' in self.trades.columns:
                fig.add_trace(
                    go.Histogram(
                        x=self.trades['duration'],
                        name="持仓时间分布",
                        nbinsx=20
                    ),
                    row=2, col=1
                )
            
            # 累计盈亏
            if 'pnl' in self.trades.columns:
                cumulative_pnl = self.trades['pnl'].cumsum()
                fig.add_trace(
                    go.Scatter(
                        x=self.trades.index,
                        y=cumulative_pnl,
                        name="累计盈亏",
                        mode='lines'
                    ),
                    row=2, col=2
                )
            
            # 更新布局
            fig.update_layout(
                title="交易分析",
                height=600,
                showlegend=True,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建交易分析图失败: {e}")
            return None
    
    def create_comprehensive_dashboard(self) -> Optional[go.Figure]:
        """创建综合仪表盘"""
        try:
            if not PLOTLY_AVAILABLE:
                logger.error("Plotly不可用")
                return None
            
            # 创建子图
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=('净值曲线', '回撤分析', '日收益率', '月度收益热力图', '风险指标', '交易分析'),
                specs=[[{"type": "scatter"}, {"type": "scatter"}],
                       [{"type": "bar"}, {"type": "heatmap"}],
                       [{"type": "indicator"}, {"type": "histogram"}]]
            )
            
            # 净值曲线
            if not self.equity_curve.empty:
                fig.add_trace(
                    go.Scatter(
                        x=self.equity_curve.index,
                        y=self.equity_curve.values,
                        name="净值曲线",
                        line=dict(color=self.config['equity_color'], width=2)
                    ),
                    row=1, col=1
                )
            
            # 回撤分析
            if not self.equity_curve.empty:
                cumulative_max = self.equity_curve.expanding().max()
                drawdown = (self.equity_curve - cumulative_max) / cumulative_max * 100
                fig.add_trace(
                    go.Scatter(
                        x=drawdown.index,
                        y=drawdown.values,
                        name="回撤",
                        fill='tonexty',
                        fillcolor='rgba(255, 127, 14, 0.3)',
                        line=dict(color=self.config['drawdown_color'], width=1)
                    ),
                    row=1, col=2
                )
            
            # 日收益率
            if not self.returns.empty:
                colors = ['green' if x > 0 else 'red' for x in self.returns.values]
                fig.add_trace(
                    go.Bar(
                        x=self.returns.index,
                        y=self.returns.values * 100,
                        name="日收益率",
                        marker_color=colors
                    ),
                    row=2, col=1
                )
            
            # 月度收益热力图
            if not self.returns.empty:
                monthly_returns = self.returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
                monthly_returns.index = pd.to_datetime(monthly_returns.index)
                monthly_returns_df = monthly_returns.to_frame('returns')
                monthly_returns_df['year'] = monthly_returns_df.index.year
                monthly_returns_df['month'] = monthly_returns_df.index.month
                pivot_table = monthly_returns_df.pivot_table(
                    values='returns', 
                    index='year', 
                    columns='month', 
                    fill_value=0
                )
                
                fig.add_trace(
                    go.Heatmap(
                        z=pivot_table.values * 100,
                        x=pivot_table.columns,
                        y=pivot_table.index,
                        colorscale='RdYlGn',
                        zmid=0,
                        name="月度收益"
                    ),
                    row=2, col=2
                )
            
            # 风险指标
            metrics = self.calculate_metrics()
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=metrics.sharpe_ratio,
                    title={'text': "夏普比率"},
                    gauge={'axis': {'range': [-2, 4]},
                           'bar': {'color': "darkblue"}}
                ),
                row=3, col=1
            )
            
            # 交易分析
            if not self.trades.empty and 'pnl' in self.trades.columns:
                fig.add_trace(
                    go.Histogram(
                        x=self.trades['pnl'],
                        name="盈亏分布",
                        nbinsx=20
                    ),
                    row=3, col=2
                )
            
            # 更新布局
            fig.update_layout(
                title="回测分析综合仪表盘",
                height=1200,
                showlegend=True,
                template="plotly_white"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"创建综合仪表盘失败: {e}")
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
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        return {
            'uptime': uptime,
            'visualization_count': self.visualization_count,
            'has_equity_data': not self.equity_curve.empty,
            'has_returns_data': not self.returns.empty,
            'has_trades_data': not self.trades.empty,
            'data_points': len(self.equity_curve)
        }
