#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 数据库管理GUI组件
提供数据库连接管理、SQL查询、AI SQL生成等界面
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# 导入数据库管理模块
try:
    from core.database_manager import RockXQlibDatabaseManager, DatabaseConnection, DatabaseType
    from core.ai_sql_generator import RockXQlibAISQLGenerator
    from core.database_connection_manager import RockXQlibDatabaseConnectionManager
    DATABASE_MODULES_AVAILABLE = True
except ImportError as e:
    DATABASE_MODULES_AVAILABLE = False
    print(f"数据库模块导入失败: {e}")

    # ------------------------------------------------------------
    # 降级占位：数据库后端不可用时，仍然要能让本模块**被导入成功**。
    #
    # 原来只设了个 flag，但下面 class 的方法签名/函数体里直接引用了
    # DatabaseConnection / DatabaseType，Python 在**类定义时**就会求值
    # 默认参数注解并抛 NameError；而 NameError 不属于 ImportError，
    # 不会被上面的 except 捕获 —— 结果整个 GUI 起不来。
    # 这里补一组最小可用占位，保证界面能打开，相关功能点再报错提示。
    # ------------------------------------------------------------
    from dataclasses import dataclass as _dataclass
    from enum import Enum as _Enum

    class DatabaseType(_Enum):
        SQLITE = "sqlite"
        MYSQL = "mysql"
        POSTGRESQL = "postgresql"
        OTHER = "other"

    @_dataclass
    class DatabaseConnection:  # type: ignore[no-redef]
        name: str = ""
        db_type: "DatabaseType" = DatabaseType.SQLITE
        host: str = ""
        port: int = 0
        database: str = ""
        username: str = ""
        password: str = ""

    class RockXQlibDatabaseManager:  # type: ignore[no-redef]
        def __init__(self, *a, **k):
            raise RuntimeError("数据库后端模块不可用（core.database_manager 导入失败）")

    class RockXQlibAISQLGenerator:  # type: ignore[no-redef]
        def __init__(self, *a, **k):
            raise RuntimeError("AI SQL 生成模块不可用（core.ai_sql_generator 导入失败）")

    class RockXQlibDatabaseConnectionManager:  # type: ignore[no-redef]
        def __init__(self, *a, **k):
            raise RuntimeError("数据库连接管理模块不可用（core.database_connection_manager 导入失败）")

logger = logging.getLogger(__name__)

class DatabaseConnectionDialog(QDialog):
    """数据库连接配置对话框"""
    
    def __init__(self, parent=None, connection: Optional[DatabaseConnection] = None):
        super().__init__(parent)
        self.connection = connection
        self.setWindowTitle("数据库连接配置" if connection is None else "编辑数据库连接")
        self.setModal(True)
        self.resize(500, 400)
        
        self.setup_ui()
        self.load_connection_data()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        
        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("连接名称")
        basic_layout.addRow("名称:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems([db_type.value for db_type in DatabaseType])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        basic_layout.addRow("类型:", self.type_combo)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 连接配置
        self.config_group = QGroupBox("连接配置")
        self.config_layout = QFormLayout()
        
        # 文件路径（SQLite等文件数据库）
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("数据库文件路径")
        self.file_path_edit.setVisible(False)
        self.config_layout.addRow("文件路径:", self.file_path_edit)
        
        # 网络配置（MySQL、PostgreSQL等）
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("主机地址")
        self.host_edit.setText("localhost")
        self.config_layout.addRow("主机:", self.host_edit)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(3306)
        self.config_layout.addRow("端口:", self.port_spin)
        
        self.database_edit = QLineEdit()
        self.database_edit.setPlaceholderText("数据库名")
        self.config_layout.addRow("数据库:", self.database_edit)
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("用户名")
        self.config_layout.addRow("用户名:", self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("密码")
        self.config_layout.addRow("密码:", self.password_edit)
        
        self.config_group.setLayout(self.config_layout)
        layout.addWidget(self.config_group)
        
        # 高级选项
        advanced_group = QGroupBox("高级选项")
        advanced_layout = QFormLayout()
        
        self.chat2db_checkbox = QCheckBox("启用Chat2DB集成")
        self.chat2db_checkbox.setChecked(True)
        advanced_layout.addRow(self.chat2db_checkbox)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_button)
        
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_type_changed(self, db_type: str):
        """数据库类型改变时的处理"""
        is_file_db = db_type in ["sqlite", "vector"]
        is_network_db = db_type in ["mysql", "postgresql", "mongodb", "oracle", "sqlserver"]
        
        # 显示/隐藏相关字段
        self.file_path_edit.setVisible(is_file_db)
        self.host_edit.setVisible(is_network_db)
        self.port_spin.setVisible(is_network_db)
        self.database_edit.setVisible(is_network_db)
        self.username_edit.setVisible(is_network_db)
        self.password_edit.setVisible(is_network_db)
        
        # 设置默认端口
        port_defaults = {
            "mysql": 3306,
            "postgresql": 5432,
            "mongodb": 27017,
            "oracle": 1521,
            "sqlserver": 1433
        }
        if db_type in port_defaults:
            self.port_spin.setValue(port_defaults[db_type])
    
    def load_connection_data(self):
        """加载连接数据"""
        if self.connection:
            self.name_edit.setText(self.connection.name)
            self.type_combo.setCurrentText(self.connection.db_type.value)
            self.file_path_edit.setText(self.connection.file_path)
            self.host_edit.setText(self.connection.host)
            self.port_spin.setValue(self.connection.port)
            self.database_edit.setText(self.connection.database)
            self.username_edit.setText(self.connection.username)
            self.password_edit.setText(self.connection.password)
            self.chat2db_checkbox.setChecked(self.connection.chat2db_enabled)
    
    def test_connection(self):
        """测试连接"""
        try:
            # 这里应该调用实际的连接测试
            QMessageBox.information(self, "测试连接", "连接测试功能正在开发中...")
        except Exception as e:
            QMessageBox.critical(self, "测试连接", f"连接测试失败: {e}")
    
    def get_connection_data(self) -> DatabaseConnection:
        """获取连接数据"""
        return DatabaseConnection(
            name=self.name_edit.text(),
            db_type=DatabaseType(self.type_combo.currentText()),
            file_path=self.file_path_edit.text(),
            host=self.host_edit.text(),
            port=self.port_spin.value(),
            database=self.database_edit.text(),
            username=self.username_edit.text(),
            password=self.password_edit.text(),
            chat2db_enabled=self.chat2db_checkbox.isChecked()
        )

class AISQLGeneratorWidget(QWidget):
    """AI SQL生成器组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_generator = None
        self.setup_ui()
        
        # 初始化AI生成器
        if DATABASE_MODULES_AVAILABLE:
            self.ai_generator = RockXQlibAISQLGenerator()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("AI SQL生成器")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)
        
        # 自然语言输入
        input_group = QGroupBox("自然语言查询")
        input_layout = QVBoxLayout()
        
        self.query_edit = QTextEdit()
        self.query_edit.setPlaceholderText("请输入您的查询需求，例如：查询平安银行最近30天的行情数据")
        self.query_edit.setMaximumHeight(100)
        input_layout.addWidget(self.query_edit)
        
        # 数据库选择
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("数据库:"))
        self.db_combo = QComboBox()
        self.db_combo.addItems(["sqlite", "mysql", "postgresql"])
        db_layout.addWidget(self.db_combo)
        db_layout.addStretch()
        
        self.generate_button = QPushButton("生成SQL")
        self.generate_button.clicked.connect(self.generate_sql)
        db_layout.addWidget(self.generate_button)
        
        input_layout.addLayout(db_layout)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 生成的SQL
        sql_group = QGroupBox("生成的SQL")
        sql_layout = QVBoxLayout()
        
        self.sql_edit = QTextEdit()
        self.sql_edit.setReadOnly(True)
        self.sql_edit.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New', monospace;")
        sql_layout.addWidget(self.sql_edit)
        
        # SQL操作按钮
        sql_buttons = QHBoxLayout()
        
        self.copy_button = QPushButton("复制SQL")
        self.copy_button.clicked.connect(self.copy_sql)
        sql_buttons.addWidget(self.copy_button)
        
        self.execute_button = QPushButton("执行SQL")
        self.execute_button.clicked.connect(self.execute_sql)
        sql_buttons.addWidget(self.execute_button)
        
        self.optimize_button = QPushButton("优化SQL")
        self.optimize_button.clicked.connect(self.optimize_sql)
        sql_buttons.addWidget(self.optimize_button)
        
        sql_buttons.addStretch()
        sql_layout.addLayout(sql_buttons)
        
        sql_group.setLayout(sql_layout)
        layout.addWidget(sql_group)
        
        # 查询历史
        history_group = QGroupBox("查询历史")
        history_layout = QVBoxLayout()
        
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.load_history_item)
        history_layout.addWidget(self.history_list)
        
        history_buttons = QHBoxLayout()
        
        self.clear_history_button = QPushButton("清空历史")
        self.clear_history_button.clicked.connect(self.clear_history)
        history_buttons.addWidget(self.clear_history_button)
        
        history_buttons.addStretch()
        history_layout.addLayout(history_buttons)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        self.setLayout(layout)
    
    def generate_sql(self):
        """生成SQL"""
        try:
            query = self.query_edit.toPlainText().strip()
            if not query:
                QMessageBox.warning(self, "警告", "请输入查询需求")
                return
            
            if not self.ai_generator:
                QMessageBox.critical(self, "错误", "AI生成器未初始化")
                return
            
            # 显示加载状态
            self.generate_button.setText("生成中...")
            self.generate_button.setEnabled(False)
            
            # 生成SQL
            result = self.ai_generator.generate_sql_from_natural_language(
                query, 
                self.db_combo.currentText()
            )
            
            if "error" in result:
                QMessageBox.critical(self, "生成失败", result["error"])
            else:
                self.sql_edit.setPlainText(result.get("sql", ""))
                
                # 显示解释
                if result.get("explanation"):
                    QMessageBox.information(self, "SQL解释", result["explanation"])
            
            # 更新历史
            self.update_history()
            
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"生成SQL时发生错误: {e}")
        finally:
            self.generate_button.setText("生成SQL")
            self.generate_button.setEnabled(True)
    
    def copy_sql(self):
        """复制SQL"""
        sql = self.sql_edit.toPlainText()
        if sql:
            QApplication.clipboard().setText(sql)
            QMessageBox.information(self, "复制成功", "SQL已复制到剪贴板")
    
    def execute_sql(self):
        """执行SQL"""
        sql = self.sql_edit.toPlainText()
        if not sql:
            QMessageBox.warning(self, "警告", "没有可执行的SQL")
            return
        
        QMessageBox.information(self, "执行SQL", "SQL执行功能正在开发中...")
    
    def optimize_sql(self):
        """优化SQL"""
        sql = self.sql_edit.toPlainText()
        if not sql:
            QMessageBox.warning(self, "警告", "没有可优化的SQL")
            return
        
        if not self.ai_generator:
            QMessageBox.critical(self, "错误", "AI生成器未初始化")
            return
        
        result = self.ai_generator.optimize_sql(sql)
        if result.get("optimized"):
            suggestions = result.get("suggestions", [])
            if suggestions:
                QMessageBox.information(self, "优化建议", "\n".join(suggestions))
            else:
                QMessageBox.information(self, "优化完成", "SQL已优化")
        else:
            QMessageBox.warning(self, "优化失败", result.get("error", "未知错误"))
    
    def update_history(self):
        """更新历史记录"""
        if not self.ai_generator:
            return
        
        history = self.ai_generator.get_query_history(20)
        self.history_list.clear()
        
        for item in history:
            list_item = QListWidgetItem(item.get("query", ""))
            list_item.setData(Qt.UserRole, item)
            self.history_list.addItem(list_item)
    
    def load_history_item(self, item: QListWidgetItem):
        """加载历史项"""
        data = item.data(Qt.UserRole)
        if data:
            self.query_edit.setPlainText(data.get("query", ""))
            self.sql_edit.setPlainText(data.get("sql", ""))
    
    def clear_history(self):
        """清空历史"""
        if self.ai_generator:
            self.ai_generator.clear_history()
            self.history_list.clear()

class DatabaseManagementWidget(QWidget):
    """数据库管理主组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = None
        self.connection_manager = None
        
        # 初始化数据库管理器
        if DATABASE_MODULES_AVAILABLE:
            self.db_manager = RockXQlibDatabaseManager()
            self.connection_manager = RockXQlibDatabaseConnectionManager()
        
        self.setup_ui()
        self.load_connections()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("数据库管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 连接管理标签页
        self.connections_tab = self.create_connections_tab()
        self.tab_widget.addTab(self.connections_tab, "连接管理")
        
        # AI SQL生成标签页
        self.ai_sql_tab = AISQLGeneratorWidget()
        self.tab_widget.addTab(self.ai_sql_tab, "AI SQL生成")
        
        # Chat2DB状态标签页
        self.chat2db_tab = self.create_chat2db_tab()
        self.tab_widget.addTab(self.chat2db_tab, "Chat2DB状态")
        
        layout.addWidget(self.tab_widget)
        
        self.setLayout(layout)
    
    def create_connections_tab(self) -> QWidget:
        """创建连接管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.add_button = QPushButton("添加连接")
        self.add_button.clicked.connect(self.add_connection)
        toolbar.addWidget(self.add_button)
        
        self.edit_button = QPushButton("编辑连接")
        self.edit_button.clicked.connect(self.edit_connection)
        toolbar.addWidget(self.edit_button)
        
        self.delete_button = QPushButton("删除连接")
        self.delete_button.clicked.connect(self.delete_connection)
        toolbar.addWidget(self.delete_button)
        
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_connections)
        toolbar.addWidget(self.refresh_button)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 连接列表
        self.connections_table = QTableWidget()
        self.connections_table.setColumnCount(6)
        self.connections_table.setHorizontalHeaderLabels([
            "名称", "类型", "状态", "最后使用", "连接次数", "错误信息"
        ])
        self.connections_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.connections_table.setAlternatingRowColors(True)
        layout.addWidget(self.connections_table)
        
        widget.setLayout(layout)
        return widget
    
    def create_chat2db_tab(self) -> QWidget:
        """创建Chat2DB状态标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 状态信息
        status_group = QGroupBox("Chat2DB状态")
        status_layout = QFormLayout()
        
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addRow("状态:", self.status_label)
        
        self.uptime_label = QLabel("0秒")
        status_layout.addRow("运行时间:", self.uptime_label)
        
        self.queries_label = QLabel("0")
        status_layout.addRow("总查询数:", self.queries_label)
        
        self.ai_queries_label = QLabel("0")
        status_layout.addRow("AI查询数:", self.ai_queries_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 控制按钮
        control_group = QGroupBox("控制")
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("启动Chat2DB")
        self.start_button.clicked.connect(self.start_chat2db)
        control_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止Chat2DB")
        self.stop_button.clicked.connect(self.stop_chat2db)
        control_layout.addWidget(self.stop_button)
        
        self.status_button = QPushButton("刷新状态")
        self.status_button.clicked.connect(self.refresh_chat2db_status)
        control_layout.addWidget(self.status_button)
        
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 日志显示
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        widget.setLayout(layout)
        return widget
    
    def load_connections(self):
        """加载连接列表"""
        if not self.connection_manager:
            return
        
        connections = self.connection_manager.get_all_connections()
        self.connections_table.setRowCount(len(connections))
        
        for row, (name, info) in enumerate(connections.items()):
            self.connections_table.setItem(row, 0, QTableWidgetItem(name))
            self.connections_table.setItem(row, 1, QTableWidgetItem(info.db_type))
            
            status_item = QTableWidgetItem(info.status.value)
            if info.status.value == "connected":
                status_item.setBackground(QColor(200, 255, 200))
            elif info.status.value == "error":
                status_item.setBackground(QColor(255, 200, 200))
            self.connections_table.setItem(row, 2, status_item)
            
            last_used = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info.last_used))
            self.connections_table.setItem(row, 3, QTableWidgetItem(last_used))
            self.connections_table.setItem(row, 4, QTableWidgetItem(str(info.connection_count)))
            self.connections_table.setItem(row, 5, QTableWidgetItem(info.error_message))
        
        self.connections_table.resizeColumnsToContents()
    
    def add_connection(self):
        """添加连接"""
        dialog = DatabaseConnectionDialog(self)
        if dialog.exec() == QDialog.Accepted:
            connection = dialog.get_connection_data()
            if self.connection_manager:
                # 这里应该调用实际的添加连接方法
                QMessageBox.information(self, "添加连接", "连接添加功能正在开发中...")
                self.load_connections()
    
    def edit_connection(self):
        """编辑连接"""
        current_row = self.connections_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要编辑的连接")
            return
        
        connection_name = self.connections_table.item(current_row, 0).text()
        # 这里应该获取实际的连接对象
        QMessageBox.information(self, "编辑连接", "连接编辑功能正在开发中...")
    
    def delete_connection(self):
        """删除连接"""
        current_row = self.connections_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要删除的连接")
            return
        
        connection_name = self.connections_table.item(current_row, 0).text()
        reply = QMessageBox.question(self, "确认删除", f"确定要删除连接 '{connection_name}' 吗？")
        if reply == QMessageBox.Yes:
            # 这里应该调用实际的删除连接方法
            QMessageBox.information(self, "删除连接", "连接删除功能正在开发中...")
            self.load_connections()
    
    def refresh_connections(self):
        """刷新连接列表"""
        self.load_connections()
    
    def start_chat2db(self):
        """启动Chat2DB"""
        if not self.db_manager:
            QMessageBox.critical(self, "错误", "数据库管理器未初始化")
            return
        
        if self.db_manager.start_chat2db():
            QMessageBox.information(self, "启动成功", "Chat2DB已启动")
            self.refresh_chat2db_status()
        else:
            QMessageBox.critical(self, "启动失败", "Chat2DB启动失败")
    
    def stop_chat2db(self):
        """停止Chat2DB"""
        if not self.db_manager:
            QMessageBox.critical(self, "错误", "数据库管理器未初始化")
            return
        
        if self.db_manager.stop_chat2db():
            QMessageBox.information(self, "停止成功", "Chat2DB已停止")
            self.refresh_chat2db_status()
        else:
            QMessageBox.critical(self, "停止失败", "Chat2DB停止失败")
    
    def refresh_chat2db_status(self):
        """刷新Chat2DB状态"""
        if not self.db_manager:
            return
        
        status = self.db_manager.get_chat2db_status()
        
        if status.get("is_running"):
            self.status_label.setText("运行中")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        else:
            self.status_label.setText("未运行")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
        
        uptime = status.get("uptime", 0)
        self.uptime_label.setText(f"{uptime:.0f}秒")
        self.queries_label.setText(str(status.get("total_queries", 0)))
        self.ai_queries_label.setText(str(status.get("total_ai_queries", 0)))
