#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 主窗口
基于NodeGraphQt的主界面
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

try:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QSplitter, QMenuBar, QMenu, QAction, QToolBar,
        QStatusBar, QMessageBox, QFileDialog, QTextEdit,
        QTabWidget, QTreeWidget, QTreeWidgetItem, QPushButton
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QIcon, QKeySequence
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    # 如果导入失败，尝试直接导入
    try:
        from PySide6.QtWidgets import QMainWindow
        PYSIDE6_AVAILABLE = True
    except ImportError:
        PYSIDE6_AVAILABLE = False

try:
    from NodeGraphQt import NodeGraph
    NODEGRAPH_AVAILABLE = True
except ImportError:
    NODEGRAPH_AVAILABLE = False

logger = logging.getLogger(__name__)

class RockXQlibMainWindow(QMainWindow):
    """RockXQlib主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 检查依赖项
        if not PYSIDE6_AVAILABLE:
            raise ImportError("PySide6 not available. Please install PySide6.")
        
        if not NODEGRAPH_AVAILABLE:
            raise ImportError("NodeGraphQt not available. Please install NodeGraphQt.")
        
        self.setWindowTitle("RockXQlib - 量化交易节点系统")
        self.setGeometry(100, 100, 1400, 900)
        
        # 初始化组件
        self.graph = None
        self.node_tree = None
        self.property_editor = None
        self.log_viewer = None
        
        # 设置界面
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_status_bar()
        
        # 设置定时器
        self.setup_timer()
        
        logger.info("✅ RockXQlib主窗口初始化成功")
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧面板 - 节点树
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 中间面板 - 图形编辑器
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)
        
        # 右侧面板 - 属性编辑器
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割器比例
        splitter.setSizes([200, 800, 300])
    
    def create_left_panel(self):
        """创建左侧面板 - 节点树"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 节点树
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderLabel("节点库")
        self.setup_node_tree()
        layout.addWidget(self.node_tree)
        
        # 添加节点按钮
        add_node_btn = QPushButton("添加节点")
        add_node_btn.clicked.connect(self.add_selected_node)
        layout.addWidget(add_node_btn)
        
        return panel
    
    def create_center_panel(self):
        """创建中间面板 - 图形编辑器"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建NodeGraphQt图形编辑器
        try:
            from .rockxqlib_graph import RockXQlibGraph
            self.graph = RockXQlibGraph()
            graph_widget = self.graph.get_graph_widget()
            layout.addWidget(graph_widget)
        except Exception as e:
            logger.error(f"图形编辑器创建失败: {e}")
            # 创建占位符
            placeholder = QTextEdit()
            placeholder.setText("图形编辑器加载失败")
            layout.addWidget(placeholder)
        
        return panel
    
    def create_right_panel(self):
        """创建右侧面板 - 属性编辑器"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 属性编辑器标签页
        self.property_editor = QTextEdit()
        self.property_editor.setPlaceholderText("选择节点查看属性")
        tab_widget.addTab(self.property_editor, "属性")
        
        # 日志查看器标签页
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setPlaceholderText("系统日志将显示在这里")
        tab_widget.addTab(self.log_viewer, "日志")
        
        # 帮助标签页
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h3>RockXQlib 使用帮助</h3>
        <p><b>基本操作：</b></p>
        <ul>
        <li>从左侧节点树拖拽节点到画布</li>
        <li>连接节点：拖拽输出端口到输入端口</li>
        <li>右键节点查看属性</li>
        <li>双击节点执行</li>
        </ul>
        <p><b>快捷键：</b></p>
        <ul>
        <li>Ctrl+N: 新建工作流</li>
        <li>Ctrl+O: 打开工作流</li>
        <li>Ctrl+S: 保存工作流</li>
        <li>F5: 执行工作流</li>
        </ul>
        """)
        tab_widget.addTab(help_text, "帮助")
        
        layout.addWidget(tab_widget)
        
        return panel
    
    def setup_node_tree(self):
        """设置节点树"""
        # 数据节点
        data_category = QTreeWidgetItem(self.node_tree, ["数据节点"])
        data_category.addChild(QTreeWidgetItem(["基础数据节点"]))
        data_category.addChild(QTreeWidgetItem(["Alpha因子节点"]))
        data_category.addChild(QTreeWidgetItem(["高频数据节点"]))
        data_category.addChild(QTreeWidgetItem(["自定义数据节点"]))
        
        # 模型节点
        model_category = QTreeWidgetItem(self.node_tree, ["模型节点"])
        model_category.addChild(QTreeWidgetItem(["线性模型节点"]))
        model_category.addChild(QTreeWidgetItem(["树模型节点"]))
        model_category.addChild(QTreeWidgetItem(["LSTM模型节点"]))
        model_category.addChild(QTreeWidgetItem(["Transformer节点"]))
        model_category.addChild(QTreeWidgetItem(["深度神经网络节点"]))
        model_category.addChild(QTreeWidgetItem(["TabNet节点"]))
        
        # 策略节点
        strategy_category = QTreeWidgetItem(self.node_tree, ["策略节点"])
        strategy_category.addChild(QTreeWidgetItem(["信号生成节点"]))
        strategy_category.addChild(QTreeWidgetItem(["组合管理节点"]))
        strategy_category.addChild(QTreeWidgetItem(["风险管理节点"]))
        
        # 回测节点
        backtest_category = QTreeWidgetItem(self.node_tree, ["回测节点"])
        backtest_category.addChild(QTreeWidgetItem(["回测执行节点"]))
        backtest_category.addChild(QTreeWidgetItem(["模拟器节点"]))
        backtest_category.addChild(QTreeWidgetItem(["结果分析节点"]))
        
        # 展开所有节点
        self.node_tree.expandAll()
    
    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        new_action = QAction("新建", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_workflow)
        file_menu.addAction(new_action)
        
        open_action = QAction("打开", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_workflow)
        file_menu.addAction(open_action)
        
        save_action = QAction("保存", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_workflow)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        
        undo_action = QAction("撤销", self)
        undo_action.setShortcut(QKeySequence.Undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("重做", self)
        redo_action.setShortcut(QKeySequence.Redo)
        edit_menu.addAction(redo_action)
        
        # 执行菜单
        execute_menu = menubar.addMenu("执行")
        
        run_action = QAction("运行工作流", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_workflow)
        execute_menu.addAction(run_action)
        
        stop_action = QAction("停止执行", self)
        stop_action.setShortcut("Escape")
        execute_menu.addAction(stop_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_toolbar(self):
        """设置工具栏"""
        toolbar = self.addToolBar("主工具栏")
        
        # 新建按钮
        new_btn = toolbar.addAction("新建")
        new_btn.triggered.connect(self.new_workflow)
        
        # 打开按钮
        open_btn = toolbar.addAction("打开")
        open_btn.triggered.connect(self.open_workflow)
        
        # 保存按钮
        save_btn = toolbar.addAction("保存")
        save_btn.triggered.connect(self.save_workflow)
        
        toolbar.addSeparator()
        
        # 运行按钮
        run_btn = toolbar.addAction("运行")
        run_btn.triggered.connect(self.run_workflow)
        
        # 停止按钮
        stop_btn = toolbar.addAction("停止")
        stop_btn.triggered.connect(self.stop_workflow)
    
    def setup_status_bar(self):
        """设置状态栏"""
        self.statusBar().showMessage("就绪")
    
    def setup_timer(self):
        """设置定时器"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)  # 每秒更新一次
    
    def update_status(self):
        """更新状态"""
        # 这里可以添加状态更新逻辑
        pass
    
    def add_selected_node(self):
        """添加选中的节点"""
        current_item = self.node_tree.currentItem()
        if current_item and current_item.parent():
            node_name = current_item.text(0)
            self.add_node_to_graph(node_name)
    
    def add_node_to_graph(self, node_name):
        """添加节点到图形编辑器"""
        if self.graph:
            # 根据节点名称创建对应的节点
            node_type = self.get_node_type_by_name(node_name)
            if node_type:
                self.graph.add_node(node_type)
                self.log_message(f"添加节点: {node_name}")
    
    def get_node_type_by_name(self, node_name):
        """根据名称获取节点类型"""
        # 节点名称到类型的映射
        node_mapping = {
            "基础数据节点": "RockXQlib.DataNode",
            "Alpha因子节点": "RockXQlib.AlphaNode",
            "高频数据节点": "RockXQlib.HighFreqNode",
            "自定义数据节点": "RockXQlib.CustomDataNode",
            "线性模型节点": "RockXQlib.LinearNode",
            "树模型节点": "RockXQlib.TreeNode",
            "LSTM模型节点": "RockXQlib.LSTMNode",
            "Transformer节点": "RockXQlib.TransformerNode",
            "深度神经网络节点": "RockXQlib.DNNNode",
            "TabNet节点": "RockXQlib.TabNetNode",
            "信号生成节点": "RockXQlib.SignalNode",
            "组合管理节点": "RockXQlib.PortfolioNode",
            "风险管理节点": "RockXQlib.RiskNode",
            "回测执行节点": "RockXQlib.BacktestNode",
            "模拟器节点": "RockXQlib.SimulatorNode",
            "结果分析节点": "RockXQlib.AnalysisNode"
        }
        return node_mapping.get(node_name)
    
    def new_workflow(self):
        """新建工作流"""
        if self.graph:
            self.graph.graph.clear()
            self.log_message("新建工作流")
    
    def open_workflow(self):
        """打开工作流"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开工作流", "", "JSON文件 (*.json)"
        )
        if file_path and self.graph:
            if self.graph.load_workflow(file_path):
                self.log_message(f"打开工作流: {file_path}")
            else:
                QMessageBox.warning(self, "错误", "工作流打开失败")
    
    def save_workflow(self):
        """保存工作流"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存工作流", "", "JSON文件 (*.json)"
        )
        if file_path and self.graph:
            if self.graph.save_workflow(file_path):
                self.log_message(f"保存工作流: {file_path}")
            else:
                QMessageBox.warning(self, "错误", "工作流保存失败")
    
    def run_workflow(self):
        """运行工作流"""
        if self.graph:
            self.log_message("开始执行工作流...")
            results = self.graph.execute_workflow()
            self.log_message(f"工作流执行完成，结果: {len(results)} 个节点")
    
    def stop_workflow(self):
        """停止工作流执行"""
        self.log_message("停止工作流执行")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于RockXQlib", 
                         "RockXQlib v1.0.0\n"
                         "基于Qlib的量化交易节点系统\n"
                         "支持可视化工作流设计")
    
    def log_message(self, message):
        """记录日志消息"""
        if self.log_viewer:
            self.log_viewer.append(f"[{self.get_current_time()}] {message}")
    
    def get_current_time(self):
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
