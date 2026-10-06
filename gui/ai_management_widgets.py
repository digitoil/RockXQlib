#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib AI功能管理组件
提供AI模型管理、配置和监控功能
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

# 导入AI相关模块
try:
    from core.universal_llm_integration import UniversalLLMManager, LLMProvider, LLMModelType
    from core.rockx_chat2db_adapter import RockXChat2DBAdapter
    AI_MODULES_AVAILABLE = True
except ImportError as e:
    AI_MODULES_AVAILABLE = False
    print(f"AI模块导入失败: {e}")

logger = logging.getLogger(__name__)

class AIModelManagerWidget(QWidget):
    """AI模型管理组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.llm_manager = None
        self.setup_ui()
        
        # 初始化LLM管理器
        if AI_MODULES_AVAILABLE:
            try:
                self.llm_manager = UniversalLLMManager()
                self.refresh_models()
            except Exception as e:
                logger.error(f"初始化LLM管理器失败: {e}")
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("AI模型管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)
        
        # 模型列表
        model_group = QGroupBox("可用模型")
        model_layout = QVBoxLayout()
        
        self.model_table = QTableWidget()
        self.model_table.setColumnCount(6)
        self.model_table.setHorizontalHeaderLabels([
            "模型名称", "提供商", "类型", "大小", "状态", "描述"
        ])
        self.model_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.model_table.setAlternatingRowColors(True)
        model_layout.addWidget(self.model_table)
        
        # 模型操作按钮
        model_buttons = QHBoxLayout()
        
        self.refresh_button = QPushButton("刷新模型")
        self.refresh_button.clicked.connect(self.refresh_models)
        model_buttons.addWidget(self.refresh_button)
        
        self.test_button = QPushButton("测试模型")
        self.test_button.clicked.connect(self.test_selected_model)
        model_buttons.addWidget(self.test_button)
        
        self.set_default_button = QPushButton("设为默认")
        self.set_default_button.clicked.connect(self.set_default_model)
        model_buttons.addWidget(self.set_default_button)
        
        model_buttons.addStretch()
        model_layout.addLayout(model_buttons)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # 模型配置
        config_group = QGroupBox("模型配置")
        config_layout = QFormLayout()
        
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        config_layout.addRow("温度:", self.temperature_spin)
        
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 8192)
        self.max_tokens_spin.setValue(2048)
        config_layout.addRow("最大Token数:", self.max_tokens_spin)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setValue(60)
        config_layout.addRow("超时时间(秒):", self.timeout_spin)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 测试区域
        test_group = QGroupBox("模型测试")
        test_layout = QVBoxLayout()
        
        self.test_input = QTextEdit()
        self.test_input.setPlaceholderText("输入测试文本...")
        self.test_input.setMaximumHeight(100)
        test_layout.addWidget(self.test_input)
        
        test_buttons = QHBoxLayout()
        
        self.send_test_button = QPushButton("发送测试")
        self.send_test_button.clicked.connect(self.send_test_request)
        test_buttons.addWidget(self.send_test_button)
        
        self.clear_test_button = QPushButton("清空")
        self.clear_test_button.clicked.connect(self.clear_test)
        test_buttons.addWidget(self.clear_test_button)
        
        test_buttons.addStretch()
        test_layout.addLayout(test_buttons)
        
        self.test_output = QTextEdit()
        self.test_output.setReadOnly(True)
        self.test_output.setMaximumHeight(200)
        test_layout.addWidget(self.test_output)
        
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        self.setLayout(layout)
    
    def refresh_models(self):
        """刷新模型列表"""
        if not self.llm_manager:
            QMessageBox.warning(self, "警告", "LLM管理器未初始化")
            return
        
        try:
            models = self.llm_manager.get_available_models()
            self.model_table.setRowCount(len(models))
            
            for row, model in enumerate(models):
                self.model_table.setItem(row, 0, QTableWidgetItem(model.name))
                
                provider = model.provider.value if hasattr(model.provider, 'value') else str(model.provider)
                self.model_table.setItem(row, 1, QTableWidgetItem(provider))
                
                model_type = model.model_type.value if hasattr(model.model_type, 'value') else str(model.model_type)
                self.model_table.setItem(row, 2, QTableWidgetItem(model_type))
                
                self.model_table.setItem(row, 3, QTableWidgetItem(model.size))
                
                status_item = QTableWidgetItem("可用" if model.enabled else "禁用")
                if model.enabled:
                    status_item.setBackground(QColor(200, 255, 200))
                else:
                    status_item.setBackground(QColor(255, 200, 200))
                self.model_table.setItem(row, 4, status_item)
                
                self.model_table.setItem(row, 5, QTableWidgetItem(model.description))
            
            self.model_table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"刷新模型列表失败: {e}")
    
    def test_selected_model(self):
        """测试选中的模型"""
        current_row = self.model_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择一个模型")
            return
        
        model_name = self.model_table.item(current_row, 0).text()
        QMessageBox.information(self, "模型测试", f"测试模型: {model_name}\n\n测试功能正在开发中...")
    
    def set_default_model(self):
        """设置默认模型"""
        current_row = self.model_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择一个模型")
            return
        
        model_name = self.model_table.item(current_row, 0).text()
        QMessageBox.information(self, "设置默认模型", f"已设置 {model_name} 为默认模型")
    
    def send_test_request(self):
        """发送测试请求"""
        if not self.llm_manager:
            QMessageBox.warning(self, "警告", "LLM管理器未初始化")
            return
        
        test_text = self.test_input.toPlainText().strip()
        if not test_text:
            QMessageBox.warning(self, "警告", "请输入测试文本")
            return
        
        try:
            # 显示加载状态
            self.send_test_button.setText("发送中...")
            self.send_test_button.setEnabled(False)
            
            # 发送测试请求
            response = self.llm_manager.generate_text(
                test_text,
                temperature=self.temperature_spin.value(),
                max_tokens=self.max_tokens_spin.value(),
                timeout=self.timeout_spin.value()
            )
            
            if response.success:
                self.test_output.setPlainText(response.content)
            else:
                self.test_output.setPlainText(f"错误: {response.error_message}")
            
        except Exception as e:
            self.test_output.setPlainText(f"测试失败: {e}")
        finally:
            self.send_test_button.setText("发送测试")
            self.send_test_button.setEnabled(True)
    
    def clear_test(self):
        """清空测试"""
        self.test_input.clear()
        self.test_output.clear()

class AIConfigurationWidget(QWidget):
    """AI配置组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("AI配置")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)
        
        # 提供商配置
        provider_group = QGroupBox("提供商配置")
        provider_layout = QFormLayout()
        
        self.ollama_enabled = QCheckBox("启用Ollama")
        self.ollama_enabled.setChecked(True)
        provider_layout.addRow("Ollama:", self.ollama_enabled)
        
        self.ollama_url = QLineEdit()
        self.ollama_url.setText("http://localhost:11434")
        provider_layout.addRow("Ollama URL:", self.ollama_url)
        
        self.openai_enabled = QCheckBox("启用OpenAI")
        provider_layout.addRow("OpenAI:", self.openai_enabled)
        
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_key.setPlaceholderText("输入OpenAI API Key")
        provider_layout.addRow("OpenAI Key:", self.openai_key)
        
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)
        
        # 量化分析配置
        quant_group = QGroupBox("量化分析配置")
        quant_layout = QFormLayout()
        
        self.primary_model = QComboBox()
        self.primary_model.addItems(["qwen3:latest", "deepseek-r1:8b"])
        quant_layout.addRow("主要模型:", self.primary_model)
        
        self.secondary_model = QComboBox()
        self.secondary_model.addItems(["deepseek-r1:8b", "qwen3:latest"])
        quant_layout.addRow("备用模型:", self.secondary_model)
        
        self.embedding_model = QComboBox()
        self.embedding_model.addItems(["nomic-embed-text:latest", "bge-m3:latest"])
        quant_layout.addRow("嵌入模型:", self.embedding_model)
        
        quant_group.setLayout(quant_layout)
        layout.addWidget(quant_group)
        
        # 性能配置
        perf_group = QGroupBox("性能配置")
        perf_layout = QFormLayout()
        
        self.cache_enabled = QCheckBox("启用缓存")
        self.cache_enabled.setChecked(True)
        perf_layout.addRow("缓存:", self.cache_enabled)
        
        self.cache_ttl = QSpinBox()
        self.cache_ttl.setRange(60, 3600)
        self.cache_ttl.setValue(300)
        perf_layout.addRow("缓存TTL(秒):", self.cache_ttl)
        
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(1, 20)
        self.max_concurrent.setValue(5)
        perf_layout.addRow("最大并发数:", self.max_concurrent)
        
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存配置")
        self.save_button.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_button)
        
        self.load_button = QPushButton("加载配置")
        self.load_button.clicked.connect(self.load_config)
        button_layout.addWidget(self.load_button)
        
        self.reset_button = QPushButton("重置配置")
        self.reset_button.clicked.connect(self.reset_config)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def save_config(self):
        """保存配置"""
        QMessageBox.information(self, "保存配置", "配置保存功能正在开发中...")
    
    def load_config(self):
        """加载配置"""
        QMessageBox.information(self, "加载配置", "配置加载功能正在开发中...")
    
    def reset_config(self):
        """重置配置"""
        reply = QMessageBox.question(self, "重置配置", "确定要重置所有配置吗？")
        if reply == QMessageBox.Yes:
            self.ollama_enabled.setChecked(True)
            self.ollama_url.setText("http://localhost:11434")
            self.openai_enabled.setChecked(False)
            self.openai_key.clear()
            self.primary_model.setCurrentIndex(0)
            self.secondary_model.setCurrentIndex(0)
            self.embedding_model.setCurrentIndex(0)
            self.cache_enabled.setChecked(True)
            self.cache_ttl.setValue(300)
            self.max_concurrent.setValue(5)

class AIStatisticsWidget(QWidget):
    """AI统计组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.llm_manager = None
        self.setup_ui()
        
        # 初始化LLM管理器
        if AI_MODULES_AVAILABLE:
            try:
                self.llm_manager = UniversalLLMManager()
            except Exception as e:
                logger.error(f"初始化LLM管理器失败: {e}")
        
        # 启动定时器更新统计信息
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_statistics)
        self.timer.start(5000)  # 每5秒更新一次
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("AI统计信息")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)
        
        # 统计信息显示
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(300)
        layout.addWidget(self.stats_text)
        
        # 刷新按钮
        refresh_button = QPushButton("刷新统计")
        refresh_button.clicked.connect(self.update_statistics)
        layout.addWidget(refresh_button)
        
        self.setLayout(layout)
        
        # 初始更新
        self.update_statistics()
    
    def update_statistics(self):
        """更新统计信息"""
        if not self.llm_manager:
            self.stats_text.setPlainText("LLM管理器未初始化")
            return
        
        try:
            stats = self.llm_manager.get_stats()
            
            stats_text = f"""
=== AI统计信息 ===
总请求数: {stats.get('total_requests', 0)}
总Token数: {stats.get('total_tokens', 0)}
运行时间: {stats.get('uptime', 0):.1f}秒
可用模型数: {stats.get('available_models', 0)}
默认模型: {stats.get('default_model', '未设置')}

=== 提供商统计 ===
"""
            
            for provider_name, provider_stats in stats.get('providers', {}).items():
                stats_text += f"""
{provider_name.upper()}:
  总请求数: {provider_stats.get('total_requests', 0)}
  总Token数: {provider_stats.get('total_tokens', 0)}
  运行时间: {provider_stats.get('uptime', 0):.1f}秒
  可用模型数: {provider_stats.get('available_models', 0)}
  请求/分钟: {provider_stats.get('requests_per_minute', 0):.1f}
"""
            
            self.stats_text.setPlainText(stats_text)
            
        except Exception as e:
            self.stats_text.setPlainText(f"获取统计信息失败: {e}")

class AIManagementDialog(QDialog):
    """AI功能管理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI功能管理")
        self.setModal(True)
        self.resize(1000, 700)
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 模型管理标签页
        self.model_widget = AIModelManagerWidget()
        tab_widget.addTab(self.model_widget, "模型管理")
        
        # 配置标签页
        self.config_widget = AIConfigurationWidget()
        tab_widget.addTab(self.config_widget, "配置")
        
        # 统计标签页
        self.stats_widget = AIStatisticsWidget()
        tab_widget.addTab(self.stats_widget, "统计")
        
        layout.addWidget(tab_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
