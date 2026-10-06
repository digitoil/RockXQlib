#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXAIStudio 深色主题样式配置
基于界面描述的完整配色方案
"""

class DarkThemeStyles:
    """深色主题样式配置类"""
    
    # 主要颜色定义
    COLORS = {
        # 背景色系
        'bg_primary': '#1a1a1a',        # 主背景 - 接近黑色
        'bg_secondary': '#2c2c2c',      # 次背景 - 深灰色
        'bg_tertiary': '#3a3a3a',       # 第三级背景 - 稍亮的灰色
        'bg_panel': '#2a2a2a',          # 面板背景
        'bg_hover': '#404040',          # 悬停背景
        
        # 文本色系
        'text_primary': '#ffffff',      # 主文本 - 白色
        'text_secondary': '#e0e0e0',    # 次文本 - 浅灰色
        'text_muted': '#b0b0b0',        # 弱化文本 - 中灰色
        'text_disabled': '#808080',     # 禁用文本 - 深灰色
        
        # 边框色系
        'border_primary': '#4a4a4a',    # 主边框
        'border_secondary': '#3a3a3a',  # 次边框
        'border_selected': '#e0e0e0',   # 选中边框 - 浅灰色
        
        # 强调色系
        'accent_blue': '#3498db',       # 蓝色强调 - 选中项
        'accent_blue_hover': '#2980b9', # 蓝色悬停
        'accent_green': '#27ae60',      # 绿色强调 - 执行按钮
        'accent_green_hover': '#229954', # 绿色悬停
        'accent_orange': '#f39c12',     # 橙色强调 - 连接线
        'accent_red': '#e74c3c',        # 红色强调 - 错误/删除
        'accent_red_hover': '#c0392b',  # 红色悬停
        
        # 节点颜色
        'node_bg': '#2c2c2c',          # 节点背景
        'node_border': '#4a4a4a',       # 节点边框
        'node_selected_border': '#e0e0e0', # 选中节点边框
        'node_text': '#ffffff',         # 节点文本
        
        # 连接线颜色
        'connection_line': '#f39c12',   # 连接线 - 橙色
        'connection_hover': '#e67e22',  # 连接线悬停
    }
    
    @classmethod
    def get_main_window_style(cls):
        """主窗口样式"""
        return f"""
        QMainWindow {{
            background-color: {cls.COLORS['bg_primary']};
            color: {cls.COLORS['text_primary']};
        }}
        
        QMenuBar {{
            background-color: {cls.COLORS['bg_secondary']};
            color: {cls.COLORS['text_primary']};
            border-bottom: 1px solid {cls.COLORS['border_primary']};
            padding: 4px;
        }}
        
        QMenuBar::item {{
            background-color: transparent;
            padding: 8px 12px;
            border-radius: 4px;
        }}
        
        QMenuBar::item:selected {{
            background-color: {cls.COLORS['accent_blue']};
        }}
        
        QMenu {{
            background-color: {cls.COLORS['bg_secondary']};
            color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 4px;
        }}
        
        QMenu::item {{
            padding: 8px 16px;
            border-radius: 2px;
        }}
        
        QMenu::item:selected {{
            background-color: {cls.COLORS['accent_blue']};
        }}
        
        QStatusBar {{
            background-color: {cls.COLORS['bg_secondary']};
            color: {cls.COLORS['text_secondary']};
            border-top: 1px solid {cls.COLORS['border_primary']};
            padding: 4px;
        }}
        """
    
    @classmethod
    def get_toolbar_style(cls):
        """工具栏样式"""
        return f"""
        QToolBar {{
            background-color: {cls.COLORS['bg_secondary']};
            border: none;
            spacing: 3px;
            padding: 4px;
        }}
        
        QToolBar QToolButton {{
            background-color: {cls.COLORS['bg_tertiary']};
            color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 4px;
            padding: 8px 12px;
            margin: 2px;
            min-width: 60px;
        }}
        
        QToolBar QToolButton:hover {{
            background-color: {cls.COLORS['accent_blue']};
            color: {cls.COLORS['text_primary']};
            border-color: {cls.COLORS['accent_blue_hover']};
        }}
        
        QToolBar QToolButton:pressed {{
            background-color: {cls.COLORS['accent_blue_hover']};
            color: {cls.COLORS['text_primary']};
        }}
        
        QToolBar QToolButton[class="execute"] {{
            background-color: {cls.COLORS['accent_green']};
            color: {cls.COLORS['text_primary']};
            font-weight: bold;
        }}
        
        QToolBar QToolButton[class="execute"]:hover {{
            background-color: {cls.COLORS['accent_green_hover']};
        }}
        """
    
    @classmethod
    def get_left_sidebar_style(cls):
        """左侧边栏样式"""
        return f"""
        QWidget[class="left_sidebar"] {{
            background-color: {cls.COLORS['bg_panel']};
            border-right: 1px solid {cls.COLORS['border_primary']};
        }}
        
        QLabel[class="sidebar_title"] {{
            background-color: {cls.COLORS['bg_secondary']};
            color: {cls.COLORS['text_primary']};
            font-size: 16px;
            font-weight: bold;
            padding: 12px;
            border-bottom: 1px solid {cls.COLORS['border_primary']};
        }}
        
        QTreeWidget {{
            background-color: {cls.COLORS['bg_panel']};
            color: {cls.COLORS['text_primary']};
            border: none;
            outline: none;
            font-size: 13px;
        }}
        
        QTreeWidget::item {{
            padding: 8px 12px;
            border: none;
            border-radius: 4px;
            margin: 1px 4px;
        }}
        
        QTreeWidget::item:hover {{
            background-color: {cls.COLORS['bg_hover']};
        }}
        
        QTreeWidget::item:selected {{
            background-color: {cls.COLORS['accent_blue']};
            color: {cls.COLORS['text_primary']};
        }}
        
        QTreeWidget::branch {{
            background-color: transparent;
        }}
        
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings {{
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuNSA2TDcuNSA5TDEwLjUgNiIgc3Ryb2tlPSIjZTBmMGYxIiBzdHJva2Utd2lkdGg9IjEuNSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
        }}
        
        QTreeWidget::branch:open:has-children:!has-siblings,
        QTreeWidget::branch:open:has-children:has-siblings {{
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTYgNC41TDkgNy41TDYgMTAuNSIgc3Ryb2tlPSIjZTBmMGYxIiBzdHJva2Utd2lkdGg9IjEuNSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
        }}
        """
    
    @classmethod
    def get_canvas_style(cls):
        """画布区域样式"""
        return f"""
        QGraphicsView {{
            background-color: {cls.COLORS['bg_primary']};
            border: none;
            outline: none;
        }}
        
        QGraphicsView::item {{
            selection-background-color: {cls.COLORS['accent_blue']};
        }}
        
        QLabel[class="canvas_placeholder"] {{
            background-color: {cls.COLORS['bg_secondary']};
            border: 2px dashed {cls.COLORS['border_primary']};
            border-radius: 8px;
            color: {cls.COLORS['text_secondary']};
            font-size: 16px;
            padding: 50px;
        }}
        
        QWidget[class="canvas_controls"] {{
            background-color: {cls.COLORS['bg_secondary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 4px;
            padding: 8px;
        }}
        
        QPushButton[class="canvas_control"] {{
            background-color: {cls.COLORS['bg_tertiary']};
            color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 4px;
            padding: 8px;
            margin: 2px;
            min-width: 32px;
            min-height: 32px;
        }}
        
        QPushButton[class="canvas_control"]:hover {{
            background-color: {cls.COLORS['bg_hover']};
        }}
        
        QPushButton[class="canvas_control"]:checked {{
            background-color: {cls.COLORS['accent_blue']};
            border-color: {cls.COLORS['accent_blue_hover']};
        }}
        """
    
    @classmethod
    def get_right_sidebar_style(cls):
        """右侧边栏样式"""
        return f"""
        QWidget[class="right_sidebar"] {{
            background-color: {cls.COLORS['bg_panel']};
            border-left: 1px solid {cls.COLORS['border_primary']};
        }}
        
        QLabel[class="sidebar_title"] {{
            background-color: {cls.COLORS['bg_secondary']};
            color: {cls.COLORS['text_primary']};
            font-size: 16px;
            font-weight: bold;
            padding: 12px;
            border-bottom: 1px solid {cls.COLORS['border_primary']};
        }}
        
        QWidget[class="property_editor"] {{
            background-color: {cls.COLORS['bg_panel']};
            color: {cls.COLORS['text_primary']};
            border: none;
        }}
        
        QGroupBox {{
            background-color: {cls.COLORS['bg_secondary']};
            color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: {cls.COLORS['text_primary']};
        }}
        
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {cls.COLORS['bg_tertiary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 3px;
            padding: 6px;
            color: {cls.COLORS['text_primary']};
            font-size: 12px;
        }}
        
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {cls.COLORS['accent_blue']};
        }}
        
        QCheckBox {{
            color: {cls.COLORS['text_primary']};
            spacing: 8px;
        }}
        
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 3px;
            background-color: {cls.COLORS['bg_tertiary']};
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {cls.COLORS['accent_blue']};
            border-color: {cls.COLORS['accent_blue_hover']};
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+Cg==);
        }}
        
        QComboBox {{
            background-color: {cls.COLORS['bg_tertiary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 3px;
            padding: 6px;
            color: {cls.COLORS['text_primary']};
            min-width: 100px;
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        
        QComboBox::down-arrow {{
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTMgNEw2IDdMOSA0IiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS41IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+Cg==);
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {cls.COLORS['bg_secondary']};
            border: 1px solid {cls.COLORS['border_primary']};
            color: {cls.COLORS['text_primary']};
            selection-background-color: {cls.COLORS['accent_blue']};
        }}
        """
    
    @classmethod
    def get_node_style(cls):
        """节点样式"""
        return f"""
        QGraphicsItem[class="node"] {{
            background-color: {cls.COLORS['node_bg']};
            border: 1px solid {cls.COLORS['node_border']};
            border-radius: 6px;
            color: {cls.COLORS['node_text']};
        }}
        
        QGraphicsItem[class="node"]:selected {{
            border: 2px solid {cls.COLORS['node_selected_border']};
        }}
        
        QGraphicsItem[class="node_title"] {{
            color: {cls.COLORS['text_primary']};
            font-weight: bold;
            font-size: 13px;
        }}
        
        QGraphicsItem[class="node_port"] {{
            background-color: {cls.COLORS['bg_tertiary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 8px;
        }}
        
        QGraphicsItem[class="node_port"]:hover {{
            background-color: {cls.COLORS['accent_blue']};
        }}
        """
    
    @classmethod
    def get_log_panel_style(cls):
        """日志面板样式"""
        return f"""
        QTextEdit[class="log_panel"] {{
            background-color: {cls.COLORS['bg_tertiary']};
            color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 4px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 11px;
            padding: 8px;
        }}
        
        QPushButton[class="clear_log"] {{
            background-color: {cls.COLORS['accent_red']};
            color: {cls.COLORS['text_primary']};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }}
        
        QPushButton[class="clear_log"]:hover {{
            background-color: {cls.COLORS['accent_red_hover']};
        }}
        """
    
    @classmethod
    def get_scrollbar_style(cls):
        """滚动条样式"""
        return f"""
        QScrollBar:vertical {{
            background-color: {cls.COLORS['bg_secondary']};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {cls.COLORS['bg_hover']};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {cls.COLORS['accent_blue']};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QScrollBar:horizontal {{
            background-color: {cls.COLORS['bg_secondary']};
            height: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:horizontal {{
            background-color: {cls.COLORS['bg_hover']};
            border-radius: 6px;
            min-width: 20px;
        }}
        
        QScrollBar::handle:horizontal:hover {{
            background-color: {cls.COLORS['accent_blue']};
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        """
    
    @classmethod
    def get_complete_style(cls):
        """完整的样式表"""
        return (
            cls.get_main_window_style() +
            cls.get_toolbar_style() +
            cls.get_left_sidebar_style() +
            cls.get_canvas_style() +
            cls.get_right_sidebar_style() +
            cls.get_node_style() +
            cls.get_log_panel_style() +
            cls.get_scrollbar_style()
        )


# 导出样式类
__all__ = ['DarkThemeStyles']
