#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXAIStudio 深色主题演示
展示完整的深色主题界面效果
"""

import sys
import os
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# 导入深色主题样式
from dark_theme_styles import DarkThemeStyles
from node_styles_config import NodeStylesConfig

class DarkThemeDemo(QMainWindow):
    """深色主题演示窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RockXAIStudio v2.1 - 深色主题演示")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置深色主题
        self.setup_dark_theme()
        
        # 创建界面
        self.create_demo_ui()
        
        print("🎨 深色主题演示界面启动完成")
    
    def setup_dark_theme(self):
        """设置深色主题"""
        try:
            # 应用完整的深色主题样式
            self.setStyleSheet(DarkThemeStyles.get_complete_style())
            print("✅ 深色主题样式应用成功")
        except Exception as e:
            print(f"❌ 深色主题样式应用失败: {e}")
    
    def create_demo_ui(self):
        """创建演示界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 左侧面板 - 节点工具箱
        left_panel = self.create_left_panel()
        left_panel.setProperty("class", "left_sidebar")
        left_panel.setStyleSheet(DarkThemeStyles.get_left_sidebar_style())
        main_layout.addWidget(left_panel, 1)
        
        # 中间面板 - 画布区域
        center_panel = self.create_center_panel()
        main_layout.addWidget(center_panel, 3)
        
        # 右侧面板 - 属性编辑器
        right_panel = self.create_right_panel()
        right_panel.setProperty("class", "right_sidebar")
        right_panel.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        main_layout.addWidget(right_panel, 1)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建状态栏
        self.create_status_bar()
    
    def create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title = QLabel("人工智能工具箱")
        title.setProperty("class", "sidebar_title")
        title.setStyleSheet(DarkThemeStyles.get_left_sidebar_style())
        layout.addWidget(title)
        
        # 节点分类树
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setStyleSheet(DarkThemeStyles.get_left_sidebar_style())
        
        # 添加节点分类
        categories = {
            "AI节点工具箱": ["数据编码", "分类算法", "回归算法", "聚类算法"],
            "machine_learning (9)": ["线性回归", "决策树", "随机森林", "支持向量机"],
            "deep_learning (3)": ["LSTM网络", "CNN网络", "Transformer"],
            "workflow_control (7)": ["条件判断", "循环控制", "并行执行", "数据合并"]
        }
        
        for category, nodes in categories.items():
            category_item = QTreeWidgetItem(tree)
            category_item.setText(0, category)
            category_item.setExpanded(True)
            
            for node in nodes:
                node_item = QTreeWidgetItem(category_item)
                node_item.setText(0, node)
        
        layout.addWidget(tree)
        
        return panel
    
    def create_center_panel(self):
        """创建中间面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 画布标题
        canvas_title = QLabel("工作流画布")
        canvas_title.setProperty("class", "sidebar_title")
        canvas_title.setStyleSheet(DarkThemeStyles.get_canvas_style())
        layout.addWidget(canvas_title)
        
        # 画布区域
        canvas = QLabel("深色主题画布区域\n\n这里将显示节点和工作流\n\n支持拖拽创建节点\n支持连接线绘制")
        canvas.setProperty("class", "canvas_placeholder")
        canvas.setStyleSheet(DarkThemeStyles.get_canvas_style())
        canvas.setAlignment(Qt.AlignCenter)
        layout.addWidget(canvas)
        
        return panel
    
    def create_right_panel(self):
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title = QLabel("属性编辑器")
        title.setProperty("class", "sidebar_title")
        title.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        layout.addWidget(title)
        
        # 属性编辑区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(DarkThemeStyles.get_scrollbar_style())
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 节点属性组
        node_group = QGroupBox("节点属性")
        node_group.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout = QFormLayout(node_group)
        
        # 添加属性控件
        name_edit = QLineEdit("LSTM网络")
        name_edit.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("名称:", name_edit)
        
        type_combo = QComboBox()
        type_combo.addItems(["rockx_lstm_node.RockXLstm", "rockx_cnn_node.RockXCnn"])
        type_combo.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("类型:", type_combo)
        
        color_edit = QLineEdit("(100, 100, 100)")
        color_edit.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("颜色:", color_edit)
        
        border_color_edit = QLineEdit("(200, 200, 200)")
        border_color_edit.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("边框色:", border_color_edit)
        
        text_color_edit = QLineEdit("(255, 255, 255)")
        text_color_edit.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("文本色:", text_color_edit)
        
        selected_check = QCheckBox("已选中")
        selected_check.setChecked(True)
        selected_check.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("状态:", selected_check)
        
        visible_check = QCheckBox("可见")
        visible_check.setChecked(True)
        visible_check.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("可见性:", visible_check)
        
        width_spin = QSpinBox()
        width_spin.setRange(50, 500)
        width_spin.setValue(271)
        width_spin.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("宽度:", width_spin)
        
        height_spin = QSpinBox()
        height_spin.setRange(30, 300)
        height_spin.setValue(72)
        height_spin.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
        node_layout.addRow("高度:", height_spin)
        
        content_layout.addWidget(node_group)
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        return panel
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        file_menu.addAction('新建')
        file_menu.addAction('打开')
        file_menu.addAction('保存')
        file_menu.addSeparator()
        file_menu.addAction('退出')
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')
        edit_menu.addAction('撤销')
        edit_menu.addAction('重做')
        edit_menu.addSeparator()
        edit_menu.addAction('复制')
        edit_menu.addAction('粘贴')
        
        # 工作流菜单
        workflow_menu = menubar.addMenu('工作流')
        workflow_menu.addAction('执行')
        workflow_menu.addAction('停止')
        workflow_menu.addAction('暂停')
        workflow_menu.addSeparator()
        workflow_menu.addAction('清空')
        
        # 视图菜单
        view_menu = menubar.addMenu('视图')
        view_menu.addAction('放大')
        view_menu.addAction('缩小')
        view_menu.addAction('适应窗口')
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        help_menu.addAction('关于')
        help_menu.addAction('使用说明')
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar('主工具栏')
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setStyleSheet(DarkThemeStyles.get_toolbar_style())
        
        # 添加工具栏按钮
        actions = [
            ('新建', 'SP_FileIcon'),
            ('打开', 'SP_DirOpenIcon'),
            ('保存', 'SP_DialogSaveButton'),
            ('执行', 'SP_MediaPlay'),
            ('停止', 'SP_MediaStop'),
            ('暂停', 'SP_MediaPause'),
            ('清空', 'SP_TrashIcon')
        ]
        
        for text, icon_name in actions:
            action = QAction(text, self)
            action.setIcon(self.style().standardIcon(getattr(QStyle, icon_name)))
            if text == '执行':
                action.setProperty("class", "execute")
            toolbar.addAction(action)
    
    def create_status_bar(self):
        """创建状态栏"""
        status_bar = self.statusBar()
        status_bar.setStyleSheet(DarkThemeStyles.get_main_window_style())
        
        # 添加状态信息
        status_bar.showMessage("深色主题演示 - 就绪")
        
        # 添加永久部件
        node_count_label = QLabel("节点: 0")
        connection_count_label = QLabel("连接: 0")
        
        status_bar.addPermanentWidget(node_count_label)
        status_bar.addPermanentWidget(connection_count_label)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("RockXAIStudio")
    app.setApplicationVersion("v2.1")
    app.setOrganizationName("RockX")
    
    # 创建演示窗口
    demo_window = DarkThemeDemo()
    demo_window.show()
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
