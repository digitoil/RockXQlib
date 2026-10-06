#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RockXQlib 回测结果面板：指标卡片 + 资金曲线 + 回撤曲线。

设计说明
--------
回测跑完后，``QlibBacktestNode`` 的输出里有两个关键字段：

- ``metrics``：年化收益 / 最大回撤 / 夏普 / 超额收益等（由
  ``QlibCoreIntegration._attach_metrics()`` 算好）
- ``backtest_result``：qlib 的 ``(portfolio_dict, indicator_dict)`` 原始结构

本模块做两件事：

1. **适配**（``adapt_qlib_backtest_result``）
   把 qlib 的 ``portfolio_metrics`` DataFrame 转成绘图需要的时间序列。
   qlib 的列名是 ``account`` / ``return`` / ``bench`` / ``turnover`` / ``cost``，
   直接丢给通用可视化组件（``visualization/backtest_visualizer.py``）会因为
   字段名对不上而画不出来 —— 这层适配就是补这个缺口。

2. **渲染**
   顶部指标卡片（数值一眼可见），下方用 plotly 画资金曲线与回撤曲线，
   通过 ``QWebEngineView`` 嵌进 Qt。

配色遵循 A 股习惯：**涨红跌绿**。整体深色，与主程序暗色主题一致。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = ["adapt_qlib_backtest_result", "BacktestResultPanel", "HAS_WEBENGINE"]

# ---- 可选依赖探测（缺失时降级为纯文本摘要，不让整个 GUI 起不来）----
try:
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                   QFrame, QScrollArea, QSizePolicy, QTabWidget,
                                   QTextEdit, QGridLayout)
    from PySide6.QtCore import Qt
    QT_OK = True
except Exception:  # pragma: no cover
    QT_OK = False

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:
    HAS_WEBENGINE = False

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except Exception:
    HAS_PANDAS = False


# ---- 暗色主题（与 dark_theme_styles.py 保持一致）----
_BG = "#1e1e1e"
_PANEL = "#2a2a2a"
_GRID = "#3a3a3a"
_TEXT = "#e0e0e0"
_MUTED = "#b0b0b0"
_BLUE = "#3498db"
_ORANGE = "#f39c12"
_UP = "#e74c3c"      # 涨 = 红（A 股习惯）
_DOWN = "#27ae60"    # 跌 = 绿
_GRAY = "#888888"


# ==========================================================================
# 1. 适配层：qlib 回测结果 → 绘图数据
# ==========================================================================

def _pick_daily_freq(portfolio_dict: Dict[str, Any]) -> Optional[str]:
    """从 portfolio_dict 里挑日频键。

    ⚠️ qlib 的频率键是 ``'1day'`` / ``'1min'``，**不是** 裸 ``'day'``。
    """
    if not isinstance(portfolio_dict, dict) or not portfolio_dict:
        return None
    for k in portfolio_dict:
        if "day" in str(k):
            return k
    return next(iter(portfolio_dict))


def adapt_qlib_backtest_result(result: Any) -> Dict[str, Any]:
    """把 qlib 回测结果转成绘图友好的结构。

    Args:
        result: qlib ``backtest()`` 的返回值，即
            ``(portfolio_dict, indicator_dict)``；
            也接受已经解包好的 ``portfolio_dict``。

    Returns:
        ``{ok, reason, portfolio_metrics, dates, equity, returns,
           cum_return, drawdown, benchmark_equity, benchmark_cum,
           turnover, cost, freq}``

        取不到数据时 ``ok=False``，``reason`` 说明原因。
    """
    empty = {
        "ok": False, "reason": "", "portfolio_metrics": None, "dates": [],
        "equity": [], "returns": [], "cum_return": [], "drawdown": [],
        "benchmark_equity": [], "benchmark_cum": [], "turnover": [], "cost": [],
        "freq": None,
    }

    if not HAS_PANDAS:
        empty["reason"] = "pandas 不可用"
        return empty
    if result is None:
        empty["reason"] = "回测结果为空"
        return empty

    # ---- 解包 ----
    pm = None
    freq = None
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict):
        freq = _pick_daily_freq(result[0])
        if freq is not None:
            entry = result[0][freq]
            if isinstance(entry, (list, tuple)) and entry:
                pm = entry[0]
            elif isinstance(entry, pd.DataFrame):
                pm = entry
    elif isinstance(result, dict):
        # 已经是 portfolio_dict
        freq = _pick_daily_freq(result)
        if freq is not None:
            entry = result[freq]
            if isinstance(entry, (list, tuple)) and entry:
                pm = entry[0]
            elif isinstance(entry, pd.DataFrame):
                pm = entry
    elif isinstance(result, pd.DataFrame):
        pm = result

    if not isinstance(pm, pd.DataFrame) or pm.empty:
        empty["reason"] = f"未取到 portfolio_metrics（类型 {type(pm).__name__}）"
        return empty
    if "return" not in pm.columns:
        empty["reason"] = f"portfolio_metrics 缺少 'return' 列，现有列: {list(pm.columns)}"
        return empty

    out = dict(empty)
    out["ok"] = True
    out["portfolio_metrics"] = pm
    out["freq"] = freq

    ret = pd.to_numeric(pm["return"], errors="coerce").fillna(0.0)
    out["dates"] = [str(d) for d in ret.index]
    out["returns"] = [float(x) for x in ret.values]

    cum = (1.0 + ret).cumprod()
    out["cum_return"] = [float(x) for x in cum.values]
    out["drawdown"] = [float(x) for x in (cum / cum.cummax() - 1.0).values]

    # 账户净值优先用 qlib 的 account 列；没有就用累计收益 × 1
    if "account" in pm.columns:
        acc = pd.to_numeric(pm["account"], errors="coerce").ffill()
        out["equity"] = [float(x) for x in acc.values]
    else:
        out["equity"] = [float(x) for x in cum.values]

    # 基准
    if "bench" in pm.columns:
        bench = pd.to_numeric(pm["bench"], errors="coerce").fillna(0.0)
        bench_cum = (1.0 + bench).cumprod()
        out["benchmark_cum"] = [float(x) for x in bench_cum.values]
        if "account" in pm.columns and len(pm) > 0:
            first_acc = float(pd.to_numeric(pm["account"], errors="coerce").dropna().iloc[0]) \
                if pd.to_numeric(pm["account"], errors="coerce").notna().any() else 1.0
            out["benchmark_equity"] = [float(first_acc * x) for x in bench_cum.values]

    if "turnover" in pm.columns:
        out["turnover"] = [float(x) for x in
                           pd.to_numeric(pm["turnover"], errors="coerce").fillna(0.0).values]
    if "cost" in pm.columns:
        out["cost"] = [float(x) for x in
                       pd.to_numeric(pm["cost"], errors="coerce").fillna(0.0).values]

    return out


# ==========================================================================
# 2. 图表构建
# ==========================================================================

def _base_layout(title: str, height: int = 260) -> Dict[str, Any]:
    """统一的 plotly 深色布局。"""
    return dict(
        title=dict(text=title, font=dict(color=_TEXT, size=13), x=0.01, xanchor="left"),
        height=height,
        margin=dict(l=52, r=18, t=38, b=36),
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=dict(color=_MUTED, size=11),
        xaxis=dict(gridcolor=_GRID, zeroline=False, showline=False),
        yaxis=dict(gridcolor=_GRID, zeroline=False, showline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="right", x=1.0, font=dict(size=11)),
        hovermode="x unified",
    )


def build_equity_figure(data: Dict[str, Any]) -> Optional[Any]:
    """资金曲线（策略 vs 基准）。"""
    if not HAS_PLOTLY or not data.get("ok"):
        return None
    dates = data["dates"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=data["equity"], name="策略净值", mode="lines",
        line=dict(color=_BLUE, width=1.8)))
    if data.get("benchmark_equity"):
        fig.add_trace(go.Scatter(
            x=dates, y=data["benchmark_equity"], name="基准（沪深300）", mode="lines",
            line=dict(color=_GRAY, width=1.4, dash="dot")))
    fig.update_layout(**_base_layout("资金曲线"))
    return fig


def build_drawdown_figure(data: Dict[str, Any]) -> Optional[Any]:
    """回撤曲线（面积图）。"""
    if not HAS_PLOTLY or not data.get("ok"):
        return None
    dd = [x * 100 for x in data["drawdown"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["dates"], y=dd, name="回撤", mode="lines",
        line=dict(color=_UP, width=1.2), fill="tozeroy",
        fillcolor="rgba(231,76,60,0.22)"))
    fig.update_layout(**_base_layout("回撤曲线（%）"))
    fig.update_yaxes(ticksuffix="%")
    return fig


def build_returns_figure(data: Dict[str, Any]) -> Optional[Any]:
    """每日收益柱状图（涨红跌绿，A 股习惯）。"""
    if not HAS_PLOTLY or not data.get("ok"):
        return None
    rets = data["returns"]
    colors = [_UP if r >= 0 else _DOWN for r in rets]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=data["dates"], y=[r * 100 for r in rets],
        name="日收益", marker=dict(color=colors, line=dict(width=0))))
    fig.update_layout(**_base_layout("每日收益（%）", height=220))
    fig.update_yaxes(ticksuffix="%")
    return fig


def figure_to_html(fig: Any) -> str:
    """把单个 plotly 图转成独立 HTML 片段（内联 plotly.js）。

    仅在需要单图导出时使用。面板里请用 ``build_dashboard_html()`` ——
    它对多个图只内联**一次** plotly.js。
    """
    try:
        return fig.to_html(
            full_html=False,
            include_plotlyjs=True,
            config={"displayModeBar": False, "responsive": True},
        )
    except Exception as e:
        logger.error(f"生成图表 HTML 失败: {e}")
        return f"<p style='color:{_MUTED}'>图表渲染失败: {e}</p>"


def _plotly_js_source() -> str:
    """取 plotly.js 源码文本（用于在单页里内联一次）。

    ⚠️ 为什么不给每个图各自 ``include_plotlyjs=True``：
    那样 N 个图会内联 N 份 plotly.js（每份约 3MB）。3 个图就是 ~9MB
    HTML，还要开 3 个 QWebEngineView（每个都是独立 Chromium 渲染进程）。
    本机此前已经出现过页面文件耗尽，这里改成**单页 + 单次内联**。
    """
    try:
        from plotly.offline import get_plotlyjs
        return get_plotlyjs()
    except Exception as e:
        logger.warning(f"获取 plotly.js 失败，图表将无法离线渲染: {e}")
        return ""


def build_dashboard_html(figures: Dict[str, Any],
                         titles: Optional[Dict[str, str]] = None) -> str:
    """把多张图合成**单个** HTML 页面（plotly.js 只内联一次）。

    Args:
        figures: ``{key: plotly Figure}``，None 的图会被跳过。
        titles: ``{key: 显示标题}``。

    Returns:
        可直接喂给 ``QWebEngineView.setHtml()`` 的完整 HTML。
    """
    titles = titles or {}
    js = _plotly_js_source()

    blocks = []
    scripts = []
    for i, (key, fig) in enumerate(figures.items()):
        if fig is None:
            continue
        div_id = f"chart_{key}"
        title = titles.get(key, key)
        blocks.append(
            f'<div class="chart-card">'
            f'<div class="chart-title">{title}</div>'
            f'<div id="{div_id}" class="chart"></div>'
            f'</div>')
        try:
            fig_json = fig.to_json()
        except Exception as e:
            logger.warning(f"图 {key} 序列化失败: {e}")
            continue
        scripts.append(
            f"(function(){{var f={fig_json};"
            f"Plotly.newPlot('{div_id}', f.data, f.layout, "
            f"{{displayModeBar:false, responsive:true}});}})();")

    if not blocks:
        blocks = [f'<div class="empty">没有可展示的图表</div>']

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html, body {{
    margin: 0; padding: 0; background: {_BG};
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  }}
  body {{ padding: 8px; }}
  .chart-card {{
    background: {_PANEL}; border: 1px solid {_GRID};
    border-radius: 6px; margin-bottom: 10px; padding: 6px 4px 2px 4px;
  }}
  .chart-title {{
    color: {_TEXT}; font-size: 12px; font-weight: 600;
    padding: 2px 8px 4px 8px;
  }}
  .chart {{ width: 100%; }}
  .empty {{ color: {_MUTED}; font-size: 12px; padding: 24px; text-align: center; }}
  ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
  ::-webkit-scrollbar-track {{ background: {_BG}; }}
  ::-webkit-scrollbar-thumb {{ background: {_GRID}; border-radius: 4px; }}
</style>
<script>{js}</script>
</head>
<body>
{''.join(blocks)}
<script>
{''.join(scripts)}
</script>
</body></html>"""


# ==========================================================================
# 3. 面板控件
# ==========================================================================

# 指标卡片的展示配置：(metrics 里的键, 显示名, 单位, 是否"越大越好")
_METRIC_CARDS: List[Tuple[str, str, str, Optional[bool]]] = [
    ("total_return", "总收益", "%", True),
    ("annualized_return", "年化收益", "%", True),
    ("max_drawdown", "最大回撤", "%", True),
    ("sharpe", "夏普比率", "", True),
    ("excess_annualized_return", "超额年化", "%", True),
    ("avg_turnover", "平均换手", "%", None),
]


def _fmt_metric(value: Any, unit: str) -> str:
    """格式化指标数值。"""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "%":
        return f"{v * 100:.2f}%"
    return f"{v:.3f}"


if QT_OK:

    class _MetricCard(QFrame):
        """单个指标卡片。"""

        def __init__(self, label: str, parent=None):
            super().__init__(parent)
            self.setFrameShape(QFrame.StyledPanel)
            self.setStyleSheet(
                f"QFrame {{ background-color: {_PANEL}; border: 1px solid {_GRID};"
                f" border-radius: 6px; }}")
            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(2)

            self.value_label = QLabel("—")
            self.value_label.setStyleSheet(
                f"color: {_TEXT}; font-size: 17px; font-weight: 600; border: none;")
            self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            self.name_label = QLabel(label)
            self.name_label.setStyleSheet(
                f"color: {_MUTED}; font-size: 11px; border: none;")

            lay.addWidget(self.value_label)
            lay.addWidget(self.name_label)
            self.setMinimumWidth(96)

        def set_value(self, text: str, color: str = _TEXT):
            self.value_label.setText(text)
            self.value_label.setStyleSheet(
                f"color: {color}; font-size: 17px; font-weight: 600; border: none;")

    class BacktestResultPanel(QWidget):
        """回测结果面板：指标卡片 + 图表页签。

        用法::

            panel = BacktestResultPanel()
            panel.show_backtest_result(backtest_result, metrics)   # 两者都可为 None
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self._cards: Dict[str, _MetricCard] = {}
            self._data: Optional[Dict[str, Any]] = None
            self._build_ui()
            self.clear()

        # ---- UI ----

        def _build_ui(self):
            root = QVBoxLayout(self)
            root.setContentsMargins(6, 6, 6, 6)
            root.setSpacing(8)

            # 标题
            self.title_label = QLabel("回测结果")
            self.title_label.setStyleSheet(
                f"color: {_TEXT}; font-size: 13px; font-weight: 600;")
            root.addWidget(self.title_label)

            # 指标卡片区（两行网格）
            cards_wrap = QWidget()
            grid = QGridLayout(cards_wrap)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(6)
            for i, (key, label, unit, _better) in enumerate(_METRIC_CARDS):
                card = _MetricCard(label)
                self._cards[key] = card
                grid.addWidget(card, i // 3, i % 3)
            root.addWidget(cards_wrap)

            # 图表区
            if HAS_WEBENGINE and HAS_PLOTLY:
                # 单个 QWebEngineView 承载全部图表（内部纵向排列 + 滚动）。
                # 不用 QTabWidget + 多视图：那样每个视图都是独立 Chromium
                # 渲染进程，且各自内联一份 plotly.js，内存开销大得多。
                self.chart_view = QWebEngineView()
                self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.chart_view.setMinimumHeight(240)
                self.chart_view.setHtml(self._placeholder_html())
                self.tabs = None
                root.addWidget(self.chart_view, 1)
            else:
                # 没有 WebEngine：不创建 chart_view，走文本兜底分支
                self.tabs = None
                self.chart_view = None
                self.fallback = QTextEdit()
                self.fallback.setReadOnly(True)
                self.fallback.setStyleSheet(
                    f"background: {_PANEL}; color: {_MUTED}; border: 1px solid {_GRID};")
                miss = []
                if not HAS_WEBENGINE:
                    miss.append("PySide6.QtWebEngineWidgets")
                if not HAS_PLOTLY:
                    miss.append("plotly")
                self.fallback.setPlainText(
                    "图表组件不可用，缺失依赖: " + "、".join(miss) +
                    "\n（指标卡片仍可正常显示）")
                root.addWidget(self.fallback, 1)

            # 状态提示
            self.status_label = QLabel("")
            self.status_label.setWordWrap(True)
            self.status_label.setStyleSheet(f"color: {_MUTED}; font-size: 11px;")
            root.addWidget(self.status_label)

        @staticmethod
        def _placeholder_html() -> str:
            return (f"<html><body style='background:{_BG};color:{_MUTED};"
                    f"font-family:sans-serif;font-size:12px;"
                    f"display:flex;align-items:center;justify-content:center;"
                    f"height:100%;margin:0'>尚未运行回测</body></html>")

        # ---- 数据入口 ----

        def clear(self):
            """清空所有展示。"""
            for card in self._cards.values():
                card.set_value("—", _TEXT)
            self._data = None
            if getattr(self, "chart_view", None) is not None:
                self.chart_view.setHtml(self._placeholder_html())
            self.status_label.setText("尚未运行回测")

        def show_backtest_result(self, backtest_result: Any = None,
                                 metrics: Optional[Dict[str, Any]] = None) -> bool:
            """展示回测结果。

            Args:
                backtest_result: qlib 的 ``(portfolio_dict, indicator_dict)``。
                metrics: 绩效指标字典；为 None 时尝试从 ``backtest_result``
                    自行计算。

            Returns:
                是否成功渲染出图表。
            """
            data = adapt_qlib_backtest_result(backtest_result)
            self._data = data

            # ---- 指标卡片 ----
            if metrics is None and data.get("ok"):
                metrics = self._metrics_from_data(data)
            if metrics:
                self._fill_cards(metrics)
            else:
                for card in self._cards.values():
                    card.set_value("—", _TEXT)

            # ---- 图表 ----
            if not data.get("ok"):
                reason = data.get("reason") or "没有可用的回测数据"
                self.status_label.setText(f"⚠️ 无法绘制图表：{reason}")
                if getattr(self, "chart_view", None) is not None:
                    self.chart_view.setHtml(
                        f"<html><body style='background:{_BG};color:{_MUTED};"
                        f"font-family:sans-serif;font-size:12px;padding:16px'>"
                        f"{reason}</body></html>")
                return False

            if getattr(self, "chart_view", None) is None:
                # 无 WebEngine：用文本兜底
                if hasattr(self, "fallback"):
                    lines = [f"回测区间: {data['dates'][0]} ~ {data['dates'][-1]}",
                             f"交易日数: {len(data['dates'])}"]
                    if metrics:
                        lines += ["", "绩效指标:"]
                        for k, label, unit, _ in _METRIC_CARDS:
                            lines.append(f"  {label}: {_fmt_metric(metrics.get(k), unit)}")
                    self.fallback.setPlainText("\n".join(lines))
                self.status_label.setText(
                    f"回测区间 {data['dates'][0]} ~ {data['dates'][-1]}"
                    f"（{len(data['dates'])} 个交易日）")
                return False

            figures = {
                "equity": build_equity_figure(data),
                "drawdown": build_drawdown_figure(data),
                "returns": build_returns_figure(data),
            }
            titles = {"equity": "资金曲线（策略 vs 基准）",
                      "drawdown": "回撤曲线",
                      "returns": "每日收益"}
            html = build_dashboard_html(figures, titles)
            self.chart_view.setHtml(html)

            self.status_label.setText(
                f"回测区间 {data['dates'][0]} ~ {data['dates'][-1]}"
                f"（{len(data['dates'])} 个交易日）")
            return True

        def _fill_cards(self, metrics: Dict[str, Any]):
            for key, _label, unit, better in _METRIC_CARDS:
                if key not in metrics:
                    self._cards[key].set_value("—", _TEXT)
                    continue
                text = _fmt_metric(metrics.get(key), unit)
                color = _TEXT
                try:
                    v = float(metrics[key])
                    if better is True:
                        color = _UP if v >= 0 else _DOWN
                    elif key == "max_drawdown":
                        # 回撤是负数，越接近 0 越好 → 用橙色提示
                        color = _ORANGE
                except (TypeError, ValueError):
                    pass
                self._cards[key].set_value(text, color)

        @staticmethod
        def _metrics_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
            """没有现成 metrics 时，从序列现算一份（保证卡片不为空）。"""
            try:
                import numpy as np
                rets = np.asarray(data["returns"], dtype=float)
                if rets.size == 0:
                    return {}
                cum = np.cumprod(1.0 + rets)
                n = rets.size
                ann = 252
                m = {
                    "total_return": float(cum[-1] - 1.0),
                    "annualized_return": float(cum[-1] ** (ann / n) - 1.0),
                    "max_drawdown": float((cum / np.maximum.accumulate(cum) - 1.0).min()),
                }
                std = float(np.std(rets))
                m["sharpe"] = float(np.mean(rets) / std * np.sqrt(ann)) if std > 0 else 0.0
                return m
            except Exception:
                return {}

else:  # pragma: no cover

    class BacktestResultPanel:  # type: ignore[no-redef]
        """PySide6 不可用时的占位实现。"""

        def __init__(self, *a, **k):
            raise RuntimeError("PySide6 不可用，无法创建回测结果面板")

        def clear(self):
            pass

        def show_backtest_result(self, *a, **k) -> bool:
            return False
