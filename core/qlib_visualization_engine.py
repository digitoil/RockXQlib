#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib可视化引擎
严格按照设计文档实现
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import json

# 设置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

logger = logging.getLogger(__name__)

class QlibVisualizationEngine:
    """可视化引擎"""
    
    def __init__(self, output_dir: str = "./visualizations"):
        self.output_dir = output_dir
        self.chart_engine = None
        self.dashboard = None
        self.chart_config = {
            'figure_size': (12, 8),
            'dpi': 100,
            'style': 'seaborn-v0_8',
            'color_palette': 'husl',
            'font_size': 12,
            'title_size': 16,
            'label_size': 14
        }
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 初始化图表引擎
        self._initialize_chart_engine()
        
        logger.info(f"可视化引擎初始化完成: {output_dir}")
    
    def _initialize_chart_engine(self):
        """初始化图表引擎"""
        try:
            # 设置matplotlib样式
            plt.style.use(self.chart_config['style'])
            
            # 设置颜色调色板
            sns.set_palette(self.chart_config['color_palette'])
            
            logger.info("图表引擎初始化成功")
            
        except Exception as e:
            logger.error(f"图表引擎初始化失败: {e}")
    
    def create_performance_chart(self, results: Dict) -> Dict[str, Any]:
        """创建性能图表"""
        try:
            if not results:
                logger.error("结果数据为空")
                return {}
            
            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=self.chart_config['figure_size'])
            fig.suptitle('性能分析图表', fontsize=self.chart_config['title_size'])
            
            # 1. 收益率曲线
            if 'returns' in results:
                returns = results['returns']
                if isinstance(returns, pd.Series):
                    axes[0, 0].plot(returns.index, returns.values, label='收益率')
                    axes[0, 0].set_title('收益率曲线')
                    axes[0, 0].set_xlabel('时间')
                    axes[0, 0].set_ylabel('收益率')
                    axes[0, 0].legend()
                    axes[0, 0].grid(True)
            
            # 2. 累计收益
            if 'cumulative_returns' in results:
                cum_returns = results['cumulative_returns']
                if isinstance(cum_returns, pd.Series):
                    axes[0, 1].plot(cum_returns.index, cum_returns.values, label='累计收益')
                    axes[0, 1].set_title('累计收益曲线')
                    axes[0, 1].set_xlabel('时间')
                    axes[0, 1].set_ylabel('累计收益')
                    axes[0, 1].legend()
                    axes[0, 1].grid(True)
            
            # 3. 回撤分析
            if 'drawdown' in results:
                drawdown = results['drawdown']
                if isinstance(drawdown, pd.Series):
                    axes[1, 0].fill_between(drawdown.index, drawdown.values, 0, 
                                          alpha=0.3, color='red', label='回撤')
                    axes[1, 0].set_title('回撤分析')
                    axes[1, 0].set_xlabel('时间')
                    axes[1, 0].set_ylabel('回撤')
                    axes[1, 0].legend()
                    axes[1, 0].grid(True)
            
            # 4. 收益分布
            if 'returns' in results:
                returns = results['returns']
                if isinstance(returns, pd.Series):
                    axes[1, 1].hist(returns.values, bins=50, alpha=0.7, label='收益分布')
                    axes[1, 1].set_title('收益分布')
                    axes[1, 1].set_xlabel('收益率')
                    axes[1, 1].set_ylabel('频次')
                    axes[1, 1].legend()
                    axes[1, 1].grid(True)
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            chart_path = os.path.join(self.output_dir, f"performance_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(chart_path, dpi=self.chart_config['dpi'], bbox_inches='tight')
            plt.close()
            
            logger.info(f"性能图表创建成功: {chart_path}")
            
            return {
                'chart_path': chart_path,
                'chart_type': 'performance',
                'created_time': datetime.now().isoformat(),
                'data_points': len(results.get('returns', []))
            }
            
        except Exception as e:
            logger.error(f"创建性能图表失败: {e}")
            return {}
    
    def create_risk_analysis(self, results: Dict) -> Dict[str, Any]:
        """创建风险分析"""
        try:
            if not results:
                logger.error("结果数据为空")
                return {}
            
            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=self.chart_config['figure_size'])
            fig.suptitle('风险分析图表', fontsize=self.chart_config['title_size'])
            
            # 1. 波动率分析
            if 'volatility' in results:
                volatility = results['volatility']
                if isinstance(volatility, pd.Series):
                    axes[0, 0].plot(volatility.index, volatility.values, label='波动率')
                    axes[0, 0].set_title('波动率分析')
                    axes[0, 0].set_xlabel('时间')
                    axes[0, 0].set_ylabel('波动率')
                    axes[0, 0].legend()
                    axes[0, 0].grid(True)
            
            # 2. VaR分析
            if 'var' in results:
                var_data = results['var']
                if isinstance(var_data, dict):
                    var_levels = list(var_data.keys())
                    var_values = list(var_data.values())
                    axes[0, 1].bar(var_levels, var_values, label='VaR')
                    axes[0, 1].set_title('VaR分析')
                    axes[0, 1].set_xlabel('置信水平')
                    axes[0, 1].set_ylabel('VaR值')
                    axes[0, 1].legend()
                    axes[0, 1].grid(True)
            
            # 3. 相关性分析
            if 'correlation' in results:
                corr_matrix = results['correlation']
                if isinstance(corr_matrix, pd.DataFrame):
                    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0, ax=axes[1, 0])
                    axes[1, 0].set_title('相关性矩阵')
            
            # 4. 风险指标
            if 'risk_metrics' in results:
                risk_metrics = results['risk_metrics']
                if isinstance(risk_metrics, dict):
                    metrics_names = list(risk_metrics.keys())
                    metrics_values = list(risk_metrics.values())
                    axes[1, 1].bar(metrics_names, metrics_values, label='风险指标')
                    axes[1, 1].set_title('风险指标')
                    axes[1, 1].set_xlabel('指标名称')
                    axes[1, 1].set_ylabel('指标值')
                    axes[1, 1].legend()
                    axes[1, 1].grid(True)
                    # 旋转x轴标签
                    axes[1, 1].tick_params(axis='x', rotation=45)
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            chart_path = os.path.join(self.output_dir, f"risk_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(chart_path, dpi=self.chart_config['dpi'], bbox_inches='tight')
            plt.close()
            
            logger.info(f"风险分析图表创建成功: {chart_path}")
            
            return {
                'chart_path': chart_path,
                'chart_type': 'risk_analysis',
                'created_time': datetime.now().isoformat(),
                'risk_metrics': results.get('risk_metrics', {})
            }
            
        except Exception as e:
            logger.error(f"创建风险分析失败: {e}")
            return {}
    
    def create_factor_analysis(self, results: Dict) -> Dict[str, Any]:
        """创建因子分析"""
        try:
            if not results:
                logger.error("结果数据为空")
                return {}
            
            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=self.chart_config['figure_size'])
            fig.suptitle('因子分析图表', fontsize=self.chart_config['title_size'])
            
            # 1. 因子收益
            if 'factor_returns' in results:
                factor_returns = results['factor_returns']
                if isinstance(factor_returns, pd.DataFrame):
                    for column in factor_returns.columns:
                        axes[0, 0].plot(factor_returns.index, factor_returns[column], label=column)
                    axes[0, 0].set_title('因子收益')
                    axes[0, 0].set_xlabel('时间')
                    axes[0, 0].set_ylabel('收益')
                    axes[0, 0].legend()
                    axes[0, 0].grid(True)
            
            # 2. 因子暴露
            if 'factor_exposure' in results:
                factor_exposure = results['factor_exposure']
                if isinstance(factor_exposure, pd.DataFrame):
                    # 选择前10个因子
                    top_factors = factor_exposure.mean().nlargest(10)
                    axes[0, 1].bar(range(len(top_factors)), top_factors.values)
                    axes[0, 1].set_title('因子暴露度')
                    axes[0, 1].set_xlabel('因子')
                    axes[0, 1].set_ylabel('暴露度')
                    axes[0, 1].set_xticks(range(len(top_factors)))
                    axes[0, 1].set_xticklabels(top_factors.index, rotation=45)
                    axes[0, 1].grid(True)
            
            # 3. 因子相关性
            if 'factor_correlation' in results:
                factor_corr = results['factor_correlation']
                if isinstance(factor_corr, pd.DataFrame):
                    sns.heatmap(factor_corr, annot=True, cmap='coolwarm', center=0, ax=axes[1, 0])
                    axes[1, 0].set_title('因子相关性')
            
            # 4. 因子重要性
            if 'factor_importance' in results:
                factor_importance = results['factor_importance']
                if isinstance(factor_importance, dict):
                    factors = list(factor_importance.keys())
                    importance = list(factor_importance.values())
                    axes[1, 1].bar(factors, importance)
                    axes[1, 1].set_title('因子重要性')
                    axes[1, 1].set_xlabel('因子')
                    axes[1, 1].set_ylabel('重要性')
                    axes[1, 1].tick_params(axis='x', rotation=45)
                    axes[1, 1].grid(True)
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            chart_path = os.path.join(self.output_dir, f"factor_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(chart_path, dpi=self.chart_config['dpi'], bbox_inches='tight')
            plt.close()
            
            logger.info(f"因子分析图表创建成功: {chart_path}")
            
            return {
                'chart_path': chart_path,
                'chart_type': 'factor_analysis',
                'created_time': datetime.now().isoformat(),
                'factor_count': len(results.get('factor_returns', {}).columns) if 'factor_returns' in results else 0
            }
            
        except Exception as e:
            logger.error(f"创建因子分析失败: {e}")
            return {}
    
    def create_portfolio_analysis(self, results: Dict) -> Dict[str, Any]:
        """创建投资组合分析"""
        try:
            if not results:
                logger.error("结果数据为空")
                return {}
            
            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=self.chart_config['figure_size'])
            fig.suptitle('投资组合分析图表', fontsize=self.chart_config['title_size'])
            
            # 1. 投资组合权重
            if 'portfolio_weights' in results:
                weights = results['portfolio_weights']
                if isinstance(weights, pd.DataFrame):
                    # 选择权重最大的前10个资产
                    top_weights = weights.mean().nlargest(10)
                    axes[0, 0].pie(top_weights.values, labels=top_weights.index, autopct='%1.1f%%')
                    axes[0, 0].set_title('投资组合权重')
            
            # 2. 资产配置变化
            if 'portfolio_weights' in results:
                weights = results['portfolio_weights']
                if isinstance(weights, pd.DataFrame):
                    # 选择前5个资产
                    top_assets = weights.mean().nlargest(5).index
                    for asset in top_assets:
                        axes[0, 1].plot(weights.index, weights[asset], label=asset)
                    axes[0, 1].set_title('资产配置变化')
                    axes[0, 1].set_xlabel('时间')
                    axes[0, 1].set_ylabel('权重')
                    axes[0, 1].legend()
                    axes[0, 1].grid(True)
            
            # 3. 投资组合收益
            if 'portfolio_returns' in results:
                portfolio_returns = results['portfolio_returns']
                if isinstance(portfolio_returns, pd.Series):
                    axes[1, 0].plot(portfolio_returns.index, portfolio_returns.values, label='投资组合收益')
                    axes[1, 0].set_title('投资组合收益')
                    axes[1, 0].set_xlabel('时间')
                    axes[1, 0].set_ylabel('收益')
                    axes[1, 0].legend()
                    axes[1, 0].grid(True)
            
            # 4. 投资组合风险
            if 'portfolio_risk' in results:
                portfolio_risk = results['portfolio_risk']
                if isinstance(portfolio_risk, dict):
                    risk_metrics = list(portfolio_risk.keys())
                    risk_values = list(portfolio_risk.values())
                    axes[1, 1].bar(risk_metrics, risk_values)
                    axes[1, 1].set_title('投资组合风险指标')
                    axes[1, 1].set_xlabel('风险指标')
                    axes[1, 1].set_ylabel('指标值')
                    axes[1, 1].tick_params(axis='x', rotation=45)
                    axes[1, 1].grid(True)
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            chart_path = os.path.join(self.output_dir, f"portfolio_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(chart_path, dpi=self.chart_config['dpi'], bbox_inches='tight')
            plt.close()
            
            logger.info(f"投资组合分析图表创建成功: {chart_path}")
            
            return {
                'chart_path': chart_path,
                'chart_type': 'portfolio_analysis',
                'created_time': datetime.now().isoformat(),
                'asset_count': len(results.get('portfolio_weights', {}).columns) if 'portfolio_weights' in results else 0
            }
            
        except Exception as e:
            logger.error(f"创建投资组合分析失败: {e}")
            return {}
    
    def create_comparison_chart(self, results_list: List[Dict], labels: List[str]) -> Dict[str, Any]:
        """创建对比图表"""
        try:
            if not results_list or not labels:
                logger.error("结果数据或标签为空")
                return {}
            
            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=self.chart_config['figure_size'])
            fig.suptitle('策略对比分析', fontsize=self.chart_config['title_size'])
            
            # 1. 累计收益对比
            for i, (results, label) in enumerate(zip(results_list, labels)):
                if 'cumulative_returns' in results:
                    cum_returns = results['cumulative_returns']
                    if isinstance(cum_returns, pd.Series):
                        axes[0, 0].plot(cum_returns.index, cum_returns.values, label=label)
            
            axes[0, 0].set_title('累计收益对比')
            axes[0, 0].set_xlabel('时间')
            axes[0, 0].set_ylabel('累计收益')
            axes[0, 0].legend()
            axes[0, 0].grid(True)
            
            # 2. 回撤对比
            for i, (results, label) in enumerate(zip(results_list, labels)):
                if 'drawdown' in results:
                    drawdown = results['drawdown']
                    if isinstance(drawdown, pd.Series):
                        axes[0, 1].plot(drawdown.index, drawdown.values, label=label)
            
            axes[0, 1].set_title('回撤对比')
            axes[0, 1].set_xlabel('时间')
            axes[0, 1].set_ylabel('回撤')
            axes[0, 1].legend()
            axes[0, 1].grid(True)
            
            # 3. 收益分布对比
            for i, (results, label) in enumerate(zip(results_list, labels)):
                if 'returns' in results:
                    returns = results['returns']
                    if isinstance(returns, pd.Series):
                        axes[1, 0].hist(returns.values, bins=30, alpha=0.7, label=label)
            
            axes[1, 0].set_title('收益分布对比')
            axes[1, 0].set_xlabel('收益率')
            axes[1, 0].set_ylabel('频次')
            axes[1, 0].legend()
            axes[1, 0].grid(True)
            
            # 4. 风险收益散点图
            risk_return_data = []
            for i, (results, label) in enumerate(zip(results_list, labels)):
                if 'returns' in results and 'volatility' in results:
                    returns = results['returns']
                    volatility = results['volatility']
                    if isinstance(returns, pd.Series) and isinstance(volatility, pd.Series):
                        mean_return = returns.mean()
                        mean_volatility = volatility.mean()
                        risk_return_data.append((mean_volatility, mean_return, label))
            
            if risk_return_data:
                for vol, ret, label in risk_return_data:
                    axes[1, 1].scatter(vol, ret, label=label, s=100)
                
                axes[1, 1].set_title('风险收益对比')
                axes[1, 1].set_xlabel('波动率')
                axes[1, 1].set_ylabel('平均收益')
                axes[1, 1].legend()
                axes[1, 1].grid(True)
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            chart_path = os.path.join(self.output_dir, f"comparison_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(chart_path, dpi=self.chart_config['dpi'], bbox_inches='tight')
            plt.close()
            
            logger.info(f"对比图表创建成功: {chart_path}")
            
            return {
                'chart_path': chart_path,
                'chart_type': 'comparison',
                'created_time': datetime.now().isoformat(),
                'comparison_count': len(results_list)
            }
            
        except Exception as e:
            logger.error(f"创建对比图表失败: {e}")
            return {}
    
    def create_dashboard(self, results: Dict) -> Dict[str, Any]:
        """创建仪表盘"""
        try:
            if not results:
                logger.error("结果数据为空")
                return {}
            
            # 创建仪表盘
            fig = plt.figure(figsize=(16, 12))
            gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
            
            # 1. 主要指标
            ax1 = fig.add_subplot(gs[0, :2])
            if 'key_metrics' in results:
                metrics = results['key_metrics']
                if isinstance(metrics, dict):
                    metric_names = list(metrics.keys())
                    metric_values = list(metrics.values())
                    bars = ax1.bar(metric_names, metric_values)
                    ax1.set_title('主要指标', fontsize=14)
                    ax1.tick_params(axis='x', rotation=45)
                    
                    # 添加数值标签
                    for bar, value in zip(bars, metric_values):
                        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                               f'{value:.2f}', ha='center', va='bottom')
            
            # 2. 收益曲线
            ax2 = fig.add_subplot(gs[0, 2:])
            if 'cumulative_returns' in results:
                cum_returns = results['cumulative_returns']
                if isinstance(cum_returns, pd.Series):
                    ax2.plot(cum_returns.index, cum_returns.values)
                    ax2.set_title('累计收益曲线', fontsize=14)
                    ax2.grid(True)
            
            # 3. 回撤分析
            ax3 = fig.add_subplot(gs[1, :2])
            if 'drawdown' in results:
                drawdown = results['drawdown']
                if isinstance(drawdown, pd.Series):
                    ax3.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
                    ax3.set_title('回撤分析', fontsize=14)
                    ax3.grid(True)
            
            # 4. 风险指标
            ax4 = fig.add_subplot(gs[1, 2:])
            if 'risk_metrics' in results:
                risk_metrics = results['risk_metrics']
                if isinstance(risk_metrics, dict):
                    risk_names = list(risk_metrics.keys())
                    risk_values = list(risk_metrics.values())
                    ax4.bar(risk_names, risk_values)
                    ax4.set_title('风险指标', fontsize=14)
                    ax4.tick_params(axis='x', rotation=45)
            
            # 5. 收益分布
            ax5 = fig.add_subplot(gs[2, :2])
            if 'returns' in results:
                returns = results['returns']
                if isinstance(returns, pd.Series):
                    ax5.hist(returns.values, bins=50, alpha=0.7)
                    ax5.set_title('收益分布', fontsize=14)
                    ax5.grid(True)
            
            # 6. 相关性矩阵
            ax6 = fig.add_subplot(gs[2, 2:])
            if 'correlation' in results:
                corr_matrix = results['correlation']
                if isinstance(corr_matrix, pd.DataFrame):
                    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0, ax=ax6)
                    ax6.set_title('相关性矩阵', fontsize=14)
            
            # 保存仪表盘
            dashboard_path = os.path.join(self.output_dir, f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(dashboard_path, dpi=self.chart_config['dpi'], bbox_inches='tight')
            plt.close()
            
            logger.info(f"仪表盘创建成功: {dashboard_path}")
            
            return {
                'dashboard_path': dashboard_path,
                'chart_type': 'dashboard',
                'created_time': datetime.now().isoformat(),
                'sections': ['主要指标', '收益曲线', '回撤分析', '风险指标', '收益分布', '相关性矩阵']
            }
            
        except Exception as e:
            logger.error(f"创建仪表盘失败: {e}")
            return {}
    
    def export_chart_data(self, chart_path: str, data: Dict) -> bool:
        """导出图表数据"""
        try:
            if not chart_path or not data:
                logger.error("图表路径或数据为空")
                return False
            
            # 生成数据文件路径
            data_path = chart_path.replace('.png', '_data.json')
            
            # 保存数据
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"图表数据导出成功: {data_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出图表数据失败: {e}")
            return False
    
    def get_chart_config(self) -> Dict[str, Any]:
        """获取图表配置"""
        return self.chart_config.copy()
    
    def set_chart_config(self, config: Dict[str, Any]):
        """设置图表配置"""
        try:
            self.chart_config.update(config)
            
            # 更新matplotlib配置
            if 'figure_size' in config:
                plt.rcParams['figure.figsize'] = config['figure_size']
            if 'dpi' in config:
                plt.rcParams['figure.dpi'] = config['dpi']
            if 'style' in config:
                plt.style.use(config['style'])
            if 'color_palette' in config:
                sns.set_palette(config['color_palette'])
            
            logger.info("图表配置更新成功")
            
        except Exception as e:
            logger.error(f"设置图表配置失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理matplotlib缓存
            plt.close('all')
            
            logger.info("可视化引擎清理完成")
            
        except Exception as e:
            logger.error(f"可视化引擎清理失败: {e}")
