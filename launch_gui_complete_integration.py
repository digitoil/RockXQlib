#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 完整集成图形界面
集成所有开发的功能：Qlib核心、AI功能、可视化、Kronos模型、核心集成等
"""

# 设置Unicode支持
import os
import sys
if sys.platform.startswith('win'):
    # Windows系统设置UTF-8编码
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # 设置控制台代码页为UTF-8
    try:
        import subprocess
        subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
    except:
        pass
import logging
import json
import time
import yaml
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# 导入深色主题样式
from dark_theme_styles import DarkThemeStyles
from node_styles_config import NodeStylesConfig

# 导入数据库管理模块
try:
    from gui.database_management_widgets import DatabaseManagementWidget
    from core.database_manager import RockXQlibDatabaseManager
    DATABASE_MANAGEMENT_AVAILABLE = True
    print("数据库管理模块可用")
except ImportError as e:
    DATABASE_MANAGEMENT_AVAILABLE = False
    print(f"数据库管理模块不可用: {e}")

# 导入通用配置和Chat2DB适配器
try:
    from core.rockx_universal_config import RockXUniversalConfigManager, RockXSystemType
    from core.rockx_chat2db_adapter import RockXChat2DBAdapter
    from core.universal_llm_integration import UniversalLLMManager
    UNIVERSAL_CONFIG_AVAILABLE = True
    print("OK 通用配置模块可用")
except ImportError as e:
    UNIVERSAL_CONFIG_AVAILABLE = False
    print(f"WARNING 通用配置模块不可用: {e}")

# 导入AI管理组件
try:
    from gui.ai_management_widgets import AIManagementDialog
    AI_MANAGEMENT_AVAILABLE = True
    print("OK AI管理组件可用")
except ImportError as e:
    AI_MANAGEMENT_AVAILABLE = False
    print(f"⚠️ AI管理组件不可用: {e}")

# 导入可视化组件
try:
    from gui.visualization_widgets import VisualizationToolsDialog
    VISUALIZATION_AVAILABLE = True
    print("✅ 可视化组件可用")
except ImportError as e:
    VISUALIZATION_AVAILABLE = False
    print(f"⚠️ 可视化组件不可用: {e}")

# 导入Kronos管理组件
try:
    from gui.kronos_management_widgets import KronosManagerDialog
    KRONOS_MANAGEMENT_AVAILABLE = True
    print("✅ Kronos管理组件可用")
except ImportError as e:
    KRONOS_MANAGEMENT_AVAILABLE = False
    print(f"⚠️ Kronos管理组件不可用: {e}")

# 导入内存监控和安全运行器
try:
    from memory_monitor import SafeQlibRunner
    SAFE_RUNNER_AVAILABLE = True
    print("✅ 安全运行器可用")
except ImportError:
    SAFE_RUNNER_AVAILABLE = False
    print("⚠️ 安全运行器不可用")

# 设置环境变量
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8.dev6'
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB'] = '0.9.8.dev6'
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_QLIB'] = '0.9.0'

# 设置qlib相关环境变量
os.environ['QLIB_DATA_PATH'] = os.path.expanduser('~/.qlib/qlib_data/cn_data')
os.environ['QLIB_LOG_LEVEL'] = 'INFO'

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入NodeGraphQt
try:
    from NodeGraphQt import NodeGraph, BaseNode, NodesTreeWidget, PropertiesBinWidget
    NODEGRAPH_AVAILABLE = True
    print("✅ NodeGraphQt 导入成功")
except ImportError:
    NODEGRAPH_AVAILABLE = False
    print("❌ NodeGraphQt 导入失败")

# 移除CustomNodesTreeWidget类，直接使用原生NodesTreeWidget

# 对话框类定义
class KronosManagerDialog(QDialog):
    """Kronos模型管理对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kronos模型管理")
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout()

        # 标题
        title = QLabel("Kronos模型管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)

        # 内容区域
        content = QLabel("Kronos模型管理功能正在开发中...")
        content.setStyleSheet("color: #7f8c8d; font-size: 14px; margin: 20px;")
        content.setAlignment(Qt.AlignCenter)
        layout.addWidget(content)

        # 按钮
        button_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

class AIManagerDialog(QDialog):
    """AI功能管理对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI功能管理")
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout()

        # 标题
        title = QLabel("AI功能管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)

        # 内容区域
        content = QLabel("AI功能管理功能正在开发中...")
        content.setStyleSheet("color: #7f8c8d; font-size: 14px; margin: 20px;")
        content.setAlignment(Qt.AlignCenter)
        layout.addWidget(content)

        # 按钮
        button_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

class VisualizationToolsDialog(QDialog):
    """可视化工具对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("可视化工具")
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout()

        # 标题
        title = QLabel("可视化工具")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)

        # 内容区域
        content = QLabel("可视化工具功能正在开发中...")
        content.setStyleSheet("color: #7f8c8d; font-size: 14px; margin: 20px;")
        content.setAlignment(Qt.AlignCenter)
        layout.addWidget(content)

        # 按钮
        button_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

# 确保当前目录在sys.path中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 工作流执行线程
class WorkflowExecutionThread(QThread):
    """工作流执行线程"""
    progress_updated = Signal(str, str)  # message, level
    execution_completed = Signal(dict)   # results
    execution_error = Signal(str)        # error_message

    def __init__(self, nodes, parent=None):
        super().__init__(parent)
        self.nodes = nodes
        self.results = {}
        self._should_stop = False

    def run(self):
        """执行工作流"""
        import time
        start_time = time.time()
        max_execution_time = 300  # 5分钟超时

        try:
            # 按拓扑顺序排序节点
            sorted_nodes = self._topological_sort()
            self.progress_updated.emit(f"开始执行工作流，共 {len(sorted_nodes)} 个节点", "INFO")

            for i, node in enumerate(sorted_nodes):
                # 检查是否应该停止
                if self._should_stop or self.isInterruptionRequested():
                    self.progress_updated.emit("工作流执行被中断", "WARNING")
                    break

                # 检查超时
                if time.time() - start_time > max_execution_time:
                    self.progress_updated.emit(f"工作流执行超时 ({max_execution_time}秒)，停止执行", "ERROR")
                    break

                node_name = getattr(node, 'name', lambda: 'Unknown')()
                self.progress_updated.emit(f"执行节点 {i+1}/{len(sorted_nodes)}: {node_name}", "INFO")

                # 执行节点
                if hasattr(node, 'execute'):
                    try:
                        node_start_time = time.time()
                        node_timeout = 60  # 每个节点最多60秒

                        # 使用超时机制执行节点
                        result = self._execute_node_with_timeout(node, node_timeout)
                        node_execution_time = time.time() - node_start_time

                        if result:
                            self.results[node_name] = "执行成功"
                            self.progress_updated.emit(f"OK {node_name} 执行成功 (耗时: {node_execution_time:.2f}秒)", "SUCCESS")

                            # 检查是否需要处理信号占位符
                            if hasattr(node, 'id') and node.id == 'model' and hasattr(node, 'predictions'):
                                self._handle_signal_placeholder(node.predictions)
                        else:
                            self.results[node_name] = "执行失败"
                            self.progress_updated.emit(f"ERROR {node_name} 执行失败", "ERROR")
                    except Exception as e:
                        self.results[node_name] = f"执行异常: {e}"
                        self.progress_updated.emit(f"ERROR {node_name} 执行异常: {e}", "ERROR")
                else:
                    self.results[node_name] = "无执行方法"
                    self.progress_updated.emit(f"WARNING {node_name} 无执行方法", "WARNING")

                # 检查是否应该停止
                if self._should_stop or self.isInterruptionRequested():
                    self.progress_updated.emit("工作流执行被中断", "WARNING")
                    break

                # 短暂延迟，避免CPU占用过高
                self.msleep(100)

            total_time = time.time() - start_time
            self.progress_updated.emit(f"工作流执行完成，总耗时: {total_time:.2f}秒", "INFO")
            self.execution_completed.emit(self.results)

        except Exception as e:
            self.progress_updated.emit(f"工作流执行异常: {e}", "ERROR")
            self.execution_error.emit(str(e))

    def _execute_node_with_timeout(self, node, timeout_seconds):
        """带超时的节点执行"""
        import threading
        import queue
        import psutil

        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        process = psutil.Process()

        def execute_node():
            try:
                # 监控资源使用
                start_cpu = process.cpu_percent()
                start_memory = process.memory_info().rss / 1024 / 1024  # MB

                result = node.execute()

                # 检查资源使用情况
                end_cpu = process.cpu_percent()
                end_memory = process.memory_info().rss / 1024 / 1024  # MB

                if end_cpu > 90:  # CPU使用率过高
                    self.progress_updated.emit(f"警告: 节点执行后CPU使用率过高 {end_cpu:.1f}%", "WARNING")

                if end_memory - start_memory > 500:  # 内存增长超过500MB
                    self.progress_updated.emit(f"警告: 节点执行后内存增长过多 {end_memory - start_memory:.1f}MB", "WARNING")

                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)

        # 启动执行线程
        thread = threading.Thread(target=execute_node)
        thread.daemon = True
        thread.start()

        # 等待结果或超时
        thread.join(timeout_seconds)

        if thread.is_alive():
            # 超时了
            self.progress_updated.emit(f"节点执行超时 ({timeout_seconds}秒)，强制终止", "ERROR")
            # 尝试强制终止线程（Python中无法直接终止线程，但可以设置标志）
            return False

        # 检查是否有异常
        if not exception_queue.empty():
            raise exception_queue.get()

        # 检查是否有结果
        if not result_queue.empty():
            return result_queue.get()

        return False

    def stop_execution(self):
        """停止工作流执行"""
        self._should_stop = True
        self.progress_updated.emit("正在停止工作流执行...", "WARNING")

    def _handle_signal_placeholder(self, predictions):
        """处理信号占位符替换"""
        try:
            # 查找策略节点
            strategy_node = None
            for node in self.nodes:
                if hasattr(node, 'id') and node.id == 'strategy':
                    strategy_node = node
                    break

            if not strategy_node:
                return

            # 检查策略节点是否有信号占位符
            has_placeholder = strategy_node.get_property('_has_signal_placeholder')
            if not has_placeholder:
                return

            # 替换信号占位符
            signal_placeholder = strategy_node.get_property('_signal_placeholder')
            if signal_placeholder == '<PRED>':
                # 将预测结果设置为信号
                strategy_node.set_property('signal', predictions)
                self.progress_updated.emit(f"✅ 将<PRED>占位符替换为预测结果", "INFO")

        except Exception as e:
            self.progress_updated.emit(f"❌ 处理信号占位符失败: {e}", "ERROR")

    def _topological_sort(self):
        """拓扑排序节点"""
        try:
            # 基于节点ID进行拓扑排序
            # 定义执行顺序：init -> dataset -> model -> strategy -> backtest
            execution_order = ['qlib_init', 'dataset', 'model', 'strategy', 'backtest']

            sorted_nodes = []
            node_dict = {}

            # 创建节点字典
            for node in self.nodes:
                if hasattr(node, 'id'):
                    node_dict[node.id] = node
                elif hasattr(node, 'name'):
                    node_name = getattr(node, 'name', lambda: 'Unknown')()
                    # 根据名称映射到ID
                    if '初始化' in node_name or 'init' in node_name.lower():
                        node_dict['qlib_init'] = node
                    elif '数据' in node_name or 'dataset' in node_name.lower():
                        node_dict['dataset'] = node
                    elif '模型' in node_name or 'model' in node_name.lower():
                        node_dict['model'] = node
                    elif '策略' in node_name or 'strategy' in node_name.lower():
                        node_dict['strategy'] = node
                    elif '回测' in node_name or 'backtest' in node_name.lower():
                        node_dict['backtest'] = node

            # 按执行顺序添加节点
            for node_id in execution_order:
                if node_id in node_dict:
                    sorted_nodes.append(node_dict[node_id])

            # 添加未识别的节点
            for node in self.nodes:
                if node not in sorted_nodes:
                    sorted_nodes.append(node)

            return sorted_nodes

        except Exception as e:
            # 如果排序失败，返回原始顺序
            print(f"拓扑排序失败: {e}，使用原始顺序")
            return self.nodes

# 导入统一节点管理器
try:
    from core.unified_node_manager import UnifiedNodeManager
    from core.config_manager import config_manager
    UNIFIED_MANAGER_AVAILABLE = True
    print("✅ 统一节点管理器导入成功")
except ImportError as e:
    UNIFIED_MANAGER_AVAILABLE = False
    print(f"❌ 统一节点管理器导入失败: {e}")

class RockXQlibMainWindow(QMainWindow):
    """RockXQlib主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RockXAIStudio v2.1 - AI工作流建模平台(统一架构)")
        self.setGeometry(100, 100, 1400, 900)

        # 初始化统一节点管理器
        if UNIFIED_MANAGER_AVAILABLE:
            self.unified_manager = UnifiedNodeManager()
            print(f"✅ 统一节点管理器初始化完成，共 {len(self.unified_manager.registry.get_all_nodes())} 个节点")
        else:
            self.unified_manager = None
            print("⚠️ 统一节点管理器不可用，使用基础功能")

        # 初始化安全Qlib运行器
        if SAFE_RUNNER_AVAILABLE:
            self.safe_runner = SafeQlibRunner()
            print("✅ 安全Qlib运行器初始化完成")
        else:
            self.safe_runner = None
            print("⚠️ 安全Qlib运行器不可用")

        # 初始化NodeGraph
        if NODEGRAPH_AVAILABLE:
            self.graph = NodeGraph()
            # 使用节点样式配置设置图形样式
            NodeStylesConfig.setup_graph_styles(self.graph)

            # 确保factory正确初始化
            if not hasattr(self.graph, 'factory') or self.graph.factory is None:
                print("🔧 初始化NodeGraphQt factory...")
                try:
                    from NodeGraphQt import NodeFactory
                    self.graph.factory = NodeFactory()
                    print("✅ Factory初始化成功")
                except Exception as e:
                    print(f"❌ Factory初始化失败: {e}")
        else:
            self.graph = None
            print("❌ NodeGraphQt不可用")

        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_status_bar()
        self.register_nodes()

        # 设置深色主题样式
        self.set_dark_theme()

        # 连接信号
        self.connect_signals()

        print("🚀 RockXQlib完整集成GUI启动完成")

    def set_dark_theme(self):
        """设置深色主题样式"""
        try:
            # 应用完整的深色主题样式
            self.setStyleSheet(DarkThemeStyles.get_complete_style())
            print("✅ 深色主题样式应用成功")
        except Exception as e:
            print(f"❌ 深色主题样式应用失败: {e}")
            # 使用基础深色样式作为备用
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1a1a1a;
                    color: #ffffff;
                }
                QMenuBar {
                    background-color: #2c2c2c;
                    color: #ffffff;
                }
                QToolBar {
                    background-color: #2c2c2c;
                    border: none;
                }
                QStatusBar {
                    background-color: #2c2c2c;
                    color: #e0e0e0;
                }
            """)

    def setup_ui(self):
        """设置用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局（垂直布局）
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 创建上部面板（原来的左右中布局）
        upper_panel = QWidget()
        upper_layout = QHBoxLayout(upper_panel)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(5)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        upper_layout.addWidget(splitter)

        # 左侧面板 - 节点树
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # 中间面板 - 画布
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)

        # 右侧面板 - 属性编辑器
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # 设置分割器比例
        splitter.setSizes([250, 800, 300])

        # 将上部面板添加到主布局
        main_layout.addWidget(upper_panel, 4)

        # 创建底部日志面板
        log_panel = self.create_log_panel()
        main_layout.addWidget(log_panel, 1)

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

        # 节点树 - 使用原生NodesTreeWidget
        if NODEGRAPH_AVAILABLE and self.graph:
            # 先注册所有节点，确保factory有内容
            self.register_all_nodes_to_graph()
            # 使用原生NodesTreeWidget
            self.node_tree = NodesTreeWidget(node_graph=self.graph)
            self.node_tree.setStyleSheet(DarkThemeStyles.get_left_sidebar_style())
            layout.addWidget(self.node_tree)
        else:
            # 备用节点列表
            self.node_list = QListWidget()
            self.node_list.setStyleSheet(DarkThemeStyles.get_left_sidebar_style())
            layout.addWidget(self.node_list)

        return panel

    def create_log_panel(self):
        """创建底部日志面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # 日志标题
        log_title = QLabel("运行日志")
        log_title.setProperty("class", "sidebar_title")
        log_title.setStyleSheet(DarkThemeStyles.get_log_panel_style())
        layout.addWidget(log_title)

        # 创建日志文本区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setProperty("class", "log_panel")
        self.log_text.setStyleSheet(DarkThemeStyles.get_log_panel_style())
        layout.addWidget(self.log_text)

        # 日志控制按钮
        button_layout = QHBoxLayout()

        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.clear_log)
        clear_log_btn.setProperty("class", "clear_log")
        clear_log_btn.setStyleSheet(DarkThemeStyles.get_log_panel_style())

        save_log_btn = QPushButton("保存日志")
        save_log_btn.clicked.connect(self.save_log)
        save_log_btn.setProperty("class", "save_log")
        save_log_btn.setStyleSheet(DarkThemeStyles.get_log_panel_style())

        button_layout.addWidget(clear_log_btn)
        button_layout.addWidget(save_log_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 初始化日志
        self.log_message("🚀 RockXQlib系统启动完成")
        self.log_message("📋 节点系统初始化完成，共注册 22 个节点")
        self.log_message("✅ 界面初始化完成，等待用户操作...")

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

        # 画布
        if NODEGRAPH_AVAILABLE and self.graph:
            self.canvas = self.graph.widget
            self.canvas.setStyleSheet(DarkThemeStyles.get_canvas_style())

            # 设置网格背景
            try:
                # 尝试设置网格模式
                if hasattr(self.graph, 'set_grid_mode'):
                    self.graph.set_grid_mode(True)
                if hasattr(self.graph, 'set_grid_color'):
                    self.graph.set_grid_color([0.9, 0.9, 0.9, 1.0])  # 浅灰色网格
                if hasattr(self.graph, 'set_grid_size'):
                    self.graph.set_grid_size(20)  # 网格大小
            except Exception as e:
                print(f"设置网格失败: {e}")

            layout.addWidget(self.canvas)
        else:
            # 备用画布
            self.canvas = QLabel("NodeGraphQt不可用\n请安装NodeGraphQt以使用完整功能")
            self.canvas.setAlignment(Qt.AlignCenter)
            self.canvas.setProperty("class", "canvas_placeholder")
            self.canvas.setStyleSheet(DarkThemeStyles.get_canvas_style())
            layout.addWidget(self.canvas)

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

        # 属性编辑器 - 使用NodeGraphQt原生方法
        if NODEGRAPH_AVAILABLE and self.graph:
            self.property_editor = PropertiesBinWidget(node_graph=self.graph)
            self.property_editor.setProperty("class", "property_editor")
            self.property_editor.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
            layout.addWidget(self.property_editor)
        else:
            # 备用属性编辑器
            self.property_editor = QTextEdit()
            self.property_editor.setPlaceholderText("属性编辑器\nNodeGraphQt不可用时显示")
            self.property_editor.setProperty("class", "property_editor")
            self.property_editor.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
            layout.addWidget(self.property_editor)

        return panel

    def log_message(self, message, level="INFO"):
        """添加日志消息"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        # 根据级别设置颜色
        if level == "ERROR":
            color = "#e74c3c"  # 红色
            prefix = "❌"
        elif level == "WARNING":
            color = "#f39c12"  # 橙色
            prefix = "⚠️"
        elif level == "SUCCESS":
            color = "#27ae60"  # 绿色
            prefix = "✅"
        else:
            color = "#3498db"  # 蓝色
            prefix = "ℹ️"

        # 格式化消息
        formatted_message = f"[{timestamp}] {prefix} {message}"

        # 添加到日志文本区域
        if hasattr(self, 'log_text'):
            self.log_text.append(formatted_message)
            # 自动滚动到底部
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )

        # 同时输出到控制台
        print(formatted_message)

    def clear_log(self):
        """清空日志"""
        if hasattr(self, 'log_text'):
            self.log_text.clear()
            self.log_message("📝 日志已清空")

    def save_log(self):
        """保存日志到文件"""
        if not hasattr(self, 'log_text'):
            return

        import datetime
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存日志", f"rockxqlib_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt);;所有文件 (*)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self.log_message(f"📁 日志已保存到: {filename}", "SUCCESS")
            except Exception as e:
                self.log_message(f"保存日志失败: {e}", "ERROR")

    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件')

        new_action = QAction('新建工作流', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_workflow)
        file_menu.addAction(new_action)

        open_action = QAction('打开工作流', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_workflow)
        file_menu.addAction(open_action)

        save_action = QAction('保存工作流', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_workflow)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        import_yaml_action = QAction('导入YAML工作流', self)
        import_yaml_action.triggered.connect(self.import_yaml_workflow)
        file_menu.addAction(import_yaml_action)

        export_action = QAction('导出图像', self)
        export_action.triggered.connect(self.export_image)
        file_menu.addAction(export_action)

        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')

        undo_action = QAction('撤销', self)
        undo_action.setShortcut('Ctrl+Z')
        edit_menu.addAction(undo_action)

        redo_action = QAction('重做', self)
        redo_action.setShortcut('Ctrl+Y')
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        select_all_action = QAction('全选', self)
        select_all_action.setShortcut('Ctrl+A')
        select_all_action.triggered.connect(self.select_all_nodes)
        edit_menu.addAction(select_all_action)

        clear_action = QAction('清空画布', self)
        clear_action.triggered.connect(self.clear_canvas)
        edit_menu.addAction(clear_action)

        # 视图菜单
        view_menu = menubar.addMenu('视图')

        zoom_in_action = QAction('放大', self)
        zoom_in_action.setShortcut('Ctrl+=')
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction('缩小', self)
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)

        fit_view_action = QAction('适应视图', self)
        fit_view_action.setShortcut('Ctrl+0')
        fit_view_action.triggered.connect(self.fit_to_view)
        view_menu.addAction(fit_view_action)

        # 工作流菜单
        workflow_menu = menubar.addMenu('工作流')

        run_action = QAction('运行工作流', self)
        run_action.setShortcut('F5')
        run_action.triggered.connect(self.run_workflow)
        workflow_menu.addAction(run_action)

        stop_action = QAction('停止工作流', self)
        stop_action.setShortcut('F6')
        workflow_menu.addAction(stop_action)

        workflow_menu.addSeparator()

        validate_action = QAction('验证工作流', self)
        validate_action.triggered.connect(self.validate_workflow)
        workflow_menu.addAction(validate_action)

        # 工具菜单
        tools_menu = menubar.addMenu('工具')

        kronos_action = QAction('Kronos模型管理', self)
        kronos_action.triggered.connect(self.open_kronos_manager)
        tools_menu.addAction(kronos_action)

        ai_action = QAction('AI功能管理', self)
        ai_action.triggered.connect(self.open_ai_manager)
        tools_menu.addAction(ai_action)

        # 数据库管理菜单
        if DATABASE_MANAGEMENT_AVAILABLE:
            tools_menu.addSeparator()

            db_management_action = QAction('数据库管理', self)
            db_management_action.triggered.connect(self.open_database_management)
            tools_menu.addAction(db_management_action)

            chat2db_action = QAction('启动Chat2DB', self)
            chat2db_action.triggered.connect(self.launch_chat2db)
            tools_menu.addAction(chat2db_action)

        # 通用配置菜单
        if UNIVERSAL_CONFIG_AVAILABLE:
            tools_menu.addSeparator()

            universal_config_action = QAction('通用配置管理', self)
            universal_config_action.triggered.connect(self.open_universal_config)
            tools_menu.addAction(universal_config_action)

            system_switch_action = QAction('切换系统类型', self)
            system_switch_action.triggered.connect(self.switch_system_type)
            tools_menu.addAction(system_switch_action)

        visualization_action = QAction('可视化工具', self)
        visualization_action.triggered.connect(self.open_visualization_tools)
        tools_menu.addAction(visualization_action)

        # 帮助菜单
        help_menu = menubar.addMenu('帮助')

        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_toolbar(self):
        """设置工具栏"""
        toolbar = self.addToolBar('主工具栏')
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 设置工具栏样式 - 使用深色主题
        toolbar.setStyleSheet(DarkThemeStyles.get_toolbar_style())

        # 新建
        new_action = QAction('新建', self)
        new_action.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        new_action.triggered.connect(self.new_workflow)
        toolbar.addAction(new_action)

        # 打开
        open_action = QAction('打开', self)
        open_action.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        open_action.triggered.connect(self.open_workflow)
        toolbar.addAction(open_action)

        # 保存
        save_action = QAction('保存', self)
        save_action.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_action.triggered.connect(self.save_workflow)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        # 运行工作流
        run_action = QAction('运行', self)
        run_action.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        run_action.triggered.connect(self.run_workflow)
        toolbar.addAction(run_action)

        # 停止工作流
        stop_action = QAction('停止', self)
        stop_action.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        toolbar.addAction(stop_action)

        toolbar.addSeparator()

        # 放大
        zoom_in_action = QAction('放大', self)
        zoom_in_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        zoom_in_action.triggered.connect(self.zoom_in)
        toolbar.addAction(zoom_in_action)

        # 缩小
        zoom_out_action = QAction('缩小', self)
        zoom_out_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addAction(zoom_out_action)

        # 适应视图
        fit_action = QAction('适应', self)
        fit_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        fit_action.triggered.connect(self.fit_to_view)
        toolbar.addAction(fit_action)

        toolbar.addSeparator()

        # 清空画布
        clear_action = QAction('清空', self)
        clear_action.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        clear_action.triggered.connect(self.clear_canvas)
        toolbar.addAction(clear_action)

    def setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = self.statusBar()

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)

        # 节点计数
        self.node_count_label = QLabel("节点: 0")
        self.status_bar.addPermanentWidget(self.node_count_label)

        # 连接计数
        self.connection_count_label = QLabel("连接: 0")
        self.status_bar.addPermanentWidget(self.connection_count_label)

        # 系统状态
        self.system_status_label = QLabel("系统: 正常")
        self.status_bar.addPermanentWidget(self.system_status_label)

    def register_basic_nodes(self):
        """注册基础节点到graph，确保factory有内容"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            return

        # 注册一些基础节点类型，确保factory不为空
        try:
            from NodeGraphQt import BaseNode

            # 创建一个简单的测试节点类
            class TestNode(BaseNode):
                __identifier__ = 'test.node'
                NODE_NAME = '测试节点'

                def __init__(self):
                    super(TestNode, self).__init__()
                    self.add_input('input')
                    self.add_output('output')

            # 注册测试节点
            self.graph.register_node(TestNode)
            print("✅ 基础节点注册完成")
        except Exception as e:
            print(f"⚠️ 基础节点注册失败: {e}")

    def register_nodes(self):
        """注册节点"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            return

        # 使用统一节点管理器注册节点
        if self.unified_manager:
            all_nodes = self.unified_manager.registry.get_all_nodes()
            all_categories = self.unified_manager.registry.get_all_categories()
            print(f"📋 开始注册 {len(all_nodes)} 个节点到GUI")

            for identifier, node_class in all_nodes.items():
                try:
                    # 获取节点元数据
                    metadata = self.unified_manager.registry.get_node_metadata(identifier)

                    # 获取节点名称
                    node_name = getattr(node_class, 'NODE_NAME', node_class.__name__)

                    # 找到节点所属的类别
                    category = "Default"
                    for cat in all_categories:
                        if identifier in self.unified_manager.registry.get_nodes_by_category(cat):
                            category = cat
                            break

                    # 节点已经在register_all_nodes_to_graph中注册过了，这里只需要记录
                    print(f"✅ 节点已注册: {node_name} ({identifier}) -> {category}")

                except Exception as e:
                    print(f"❌ 注册节点失败: {identifier} - {e}")

            print(f"🎉 节点注册完成，共注册 {len(all_nodes)} 个节点")
        else:
            # 注册基础节点
            self.register_basic_nodes()

    def register_all_nodes_to_graph(self):
        """注册所有节点到NodeGraphQt"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            return

        # 使用统一节点管理器注册节点
        if self.unified_manager:
            all_nodes = self.unified_manager.registry.get_all_nodes()
            print(f"📋 开始注册 {len(all_nodes)} 个节点到NodeGraphQt")

            for identifier, node_class in all_nodes.items():
                try:
                    # 注册节点到NodeGraphQt
                    self.graph.register_node(node_class)

                    # 获取节点名称
                    node_name = getattr(node_class, 'NODE_NAME', node_class.__name__)
                    print(f"✅ 注册节点到Graph: {node_name} ({identifier})")

                except Exception as e:
                    print(f"❌ 注册节点到Graph失败: {identifier} - {e}")

            print(f"🎉 节点注册到Graph完成，共注册 {len(all_nodes)} 个节点")

            # 验证factory状态
            if hasattr(self.graph, 'factory'):
                print(f"🔍 Factory状态: {type(self.graph.factory)}")
                if hasattr(self.graph.factory, 'names'):
                    print(f"🔍 Factory names: {self.graph.factory.names}")
                else:
                    print("❌ Factory没有names属性")
                    # 手动设置factory的names属性
                    self._setup_factory_names()
            else:
                print("❌ Graph没有factory属性")
        else:
            # 注册基础节点
            self.register_basic_nodes()

    def _setup_factory_names(self):
        """手动设置factory的names属性"""
        if not hasattr(self.graph, 'factory'):
            print("❌ Graph没有factory属性，尝试创建factory")
            # 尝试创建factory
            try:
                from NodeGraphQt import NodeFactory
                self.graph.factory = NodeFactory()
                print("✅ 创建了新的factory")
            except Exception as e:
                print(f"❌ 创建factory失败: {e}")
                return

        try:
            # 获取所有注册的节点
            all_nodes = self.unified_manager.registry.get_all_nodes()
            all_categories = self.unified_manager.registry.get_all_categories()

            # 创建names字典
            names = {}
            for identifier, node_class in all_nodes.items():
                # 获取节点名称
                node_name = getattr(node_class, 'NODE_NAME', node_class.__name__)

                # 找到节点所属的类别
                category = "Default"
                for cat in all_categories:
                    if identifier in self.unified_manager.registry.get_nodes_by_category(cat):
                        category = cat
                        break

                # 添加到names字典
                if category not in names:
                    names[category] = []
                names[category].append(node_name)

            # 设置factory的names属性
            self.graph.factory.names = names
            print(f"✅ 手动设置Factory names: {names}")

            # 验证设置是否成功
            if hasattr(self.graph.factory, 'names'):
                print(f"✅ 验证Factory names: {self.graph.factory.names}")
            else:
                print("❌ Factory仍然没有names属性")

        except Exception as e:
            print(f"❌ 设置Factory names失败: {e}")

    def register_basic_nodes(self):
        """注册基础节点"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            return

        # 创建基础节点类
        class BasicNode(BaseNode):
            def __init__(self, name, identifier):
                super().__init__()
                self.set_name(name)
                self.__identifier__ = identifier

        # 注册基础节点
        basic_nodes = [
            ("数据节点", "basic.data"),
            ("模型节点", "basic.model"),
            ("策略节点", "basic.strategy"),
            ("回测节点", "basic.backtest")
        ]

        for name, identifier in basic_nodes:
            node_class = type(f"{name}Class", (BasicNode,), {
                '__init__': lambda self, n=name, i=identifier: BasicNode.__init__(self, n, i)
            })
            self.graph.register_node(node_class)
            print(f"✅ 注册基础节点: {name}")

    def connect_signals(self):
        """连接信号"""
        if NODEGRAPH_AVAILABLE and self.graph:
            # 连接节点变化信号
            try:
                self.graph.node_created.connect(self.on_node_created)
                self.graph.node_deleted.connect(self.on_node_deleted)
                self.graph.connection_created.connect(self.on_connection_created)
                self.graph.connection_deleted.connect(self.on_connection_deleted)
            except AttributeError:
                # 如果信号不可用，使用定时器更新
                self.update_timer = QTimer()
                self.update_timer.timeout.connect(self.update_status)
                self.update_timer.start(1000)

    def on_node_created(self, node):
        """节点创建事件"""
        self.update_status()
        self.status_label.setText(f"创建节点: {node.name()}")

    def on_node_deleted(self, node):
        """节点删除事件"""
        self.update_status()
        self.status_label.setText(f"删除节点: {node.name()}")

    def on_connection_created(self, connection):
        """连接创建事件"""
        self.update_status()
        self.status_label.setText("创建连接")

    def on_connection_deleted(self, connection):
        """连接删除事件"""
        self.update_status()
        self.status_label.setText("删除连接")

    def update_status(self):
        """更新状态"""
        if NODEGRAPH_AVAILABLE and self.graph:
            try:
                nodes = self.graph.all_nodes()
                node_count = len(nodes)

                # 计算连接数
                connection_count = 0
                for node in nodes:
                    for port in node.inputs().values():
                        connection_count += len(port.connected_ports())

                self.node_count_label.setText(f"节点: {node_count}")
                self.connection_count_label.setText(f"连接: {connection_count}")

            except Exception as e:
                print(f"更新状态失败: {e}")

    # 菜单和工具栏动作
    def new_workflow(self):
        """新建工作流"""
        if NODEGRAPH_AVAILABLE and self.graph:
            self.graph.clear_all()
            self.status_label.setText("新建工作流")

    def open_workflow(self):
        """打开工作流"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            QMessageBox.warning(self, "警告", "NodeGraphQt不可用")
            return

        filename, _ = QFileDialog.getOpenFileName(
            self, "打开工作流", "", "JSON文件 (*.json);;所有文件 (*)"
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                    data = json.loads(content)

                # 检查是否是NodeGraphQt格式
                if 'nodes' in data and isinstance(data['nodes'], dict):
                    # NodeGraphQt原生格式
                    self.graph.load_session(filename)
                    self.status_label.setText(f"打开工作流: {os.path.basename(filename)}")
                else:
                    # 自定义格式
                    self._load_custom_workflow(data)
                    self.status_label.setText(f"打开自定义工作流: {os.path.basename(filename)}")

            except UnicodeDecodeError:
                QMessageBox.critical(self, "错误", "文件编码错误，请确保文件为UTF-8编码")
            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "错误", f"JSON格式错误: {e}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"打开工作流失败: {e}")

    def save_workflow(self):
        """保存工作流"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            QMessageBox.warning(self, "警告", "NodeGraphQt不可用")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "保存工作流", "", "JSON文件 (*.json);;所有文件 (*)"
        )

        if filename:
            try:
                self.graph.save_session(filename)
                self.status_label.setText(f"保存工作流: {os.path.basename(filename)}")
                QMessageBox.information(self, "成功", "工作流保存成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存工作流失败: {e}")

    def import_yaml_workflow(self):
        """导入YAML工作流"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "导入YAML工作流", "", "YAML文件 (*.yaml *.yml);;所有文件 (*)"
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f)

                self._create_workflow_from_yaml(yaml_data)
                self.status_label.setText(f"导入YAML工作流: {os.path.basename(filename)}")
                QMessageBox.information(self, "成功", "YAML工作流导入成功")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入YAML工作流失败: {e}")

    def export_image(self):
        """导出图像"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            QMessageBox.warning(self, "警告", "NodeGraphQt不可用")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "导出图像", "", "PNG文件 (*.png);;JPG文件 (*.jpg);;所有文件 (*)"
        )

        if filename:
            try:
                # 获取画布视图
                view = self.graph.widget.view
                if view:
                    # 创建图像
                    pixmap = view.grab()
                    pixmap.save(filename)
                    self.status_label.setText(f"导出图像: {os.path.basename(filename)}")
                    QMessageBox.information(self, "成功", "图像导出成功")
                else:
                    QMessageBox.warning(self, "警告", "无法获取画布视图")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出图像失败: {e}")

    def run_workflow(self):
        """运行工作流"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            self.log_message("NodeGraphQt不可用", "ERROR")
            QMessageBox.warning(self, "警告", "NodeGraphQt不可用")
            return

        try:
            nodes = self.graph.all_nodes()
            if not nodes:
                self.log_message("画布中没有节点", "WARNING")
                QMessageBox.information(self, "提示", "画布中没有节点")
                return

            self.log_message("🚀 开始执行工作流...", "INFO")
            self.status_label.setText("正在运行工作流...")
            self.system_status_label.setText("系统: 运行中")

            # 创建工作流执行线程
            self.workflow_thread = WorkflowExecutionThread(nodes, self)
            self.workflow_thread.progress_updated.connect(self.update_workflow_progress)
            self.workflow_thread.execution_completed.connect(self._workflow_execution_complete)
            self.workflow_thread.execution_error.connect(self._workflow_execution_error)
            self.workflow_thread.finished.connect(self.workflow_thread.deleteLater)  # 确保线程正确销毁
            self.workflow_thread.start()

        except Exception as e:
            self.log_message(f"运行工作流失败: {e}", "ERROR")
            QMessageBox.critical(self, "错误", f"运行工作流失败: {e}")
            self.status_label.setText("工作流运行失败")

    def update_workflow_progress(self, message, level="INFO"):
        """更新工作流执行进度"""
        self.log_message(message, level)

    def _workflow_execution_complete(self, results):
        """工作流执行完成"""
        self.log_message("🎉 工作流执行完成", "SUCCESS")
        self.status_label.setText("工作流执行完成")
        self.system_status_label.setText("系统: 正常")

        # 显示执行结果
        if results:
            result_text = "\n".join([f"• {k}: {v}" for k, v in results.items()])
            self.log_message(f"执行结果:\n{result_text}", "SUCCESS")

        QMessageBox.information(self, "完成", "工作流执行完成")

    def _workflow_execution_error(self, error_message):
        """工作流执行错误"""
        self.log_message(f"工作流执行失败: {error_message}", "ERROR")
        self.status_label.setText("工作流执行失败")
        self.system_status_label.setText("系统: 正常")
        QMessageBox.critical(self, "错误", f"工作流执行失败: {error_message}")

    def clear_canvas(self):
        """清空画布"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            QMessageBox.warning(self, "警告", "NodeGraphQt不可用")
            return

        reply = QMessageBox.question(
            self, "确认", "确定要清空画布吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 使用NodeGraphQt原生方法清空画布
            try:
                # 获取所有节点并删除
                nodes = self.graph.all_nodes()
                for node in nodes:
                    self.graph.delete_node(node)
                self.update_status()
                self.status_label.setText("画布已清空")
            except Exception as e:
                print(f"清空画布失败: {e}")
                self.status_label.setText(f"清空画布失败: {e}")

    def zoom_in(self):
        """放大"""
        if NODEGRAPH_AVAILABLE and self.graph:
            try:
                # 尝试多种缩放方法
                if hasattr(self.graph.widget, 'view'):
                    view = self.graph.widget.view
                    if hasattr(view, 'zoom_in'):
                        view.zoom_in()
                        return
                    elif hasattr(view, 'scale_up'):
                        view.scale_up()
                        return

                # 尝试通过scene进行缩放
                if hasattr(self.graph.widget, 'scene'):
                    scene = self.graph.widget.scene()
                    if hasattr(scene, 'zoom_in'):
                        scene.zoom_in()
                        return

                # 尝试直接调用widget的缩放方法
                if hasattr(self.graph.widget, 'zoom_in'):
                    self.graph.widget.zoom_in()
                    return
                elif hasattr(self.graph.widget, 'scale_up'):
                    self.graph.widget.scale_up()
                    return

                print("⚠️ 未找到可用的放大方法")
            except Exception as e:
                print(f"放大失败: {e}")

    def zoom_out(self):
        """缩小"""
        if NODEGRAPH_AVAILABLE and self.graph:
            try:
                # 尝试多种缩放方法
                if hasattr(self.graph.widget, 'view'):
                    view = self.graph.widget.view
                    if hasattr(view, 'zoom_out'):
                        view.zoom_out()
                        return
                    elif hasattr(view, 'scale_down'):
                        view.scale_down()
                        return

                # 尝试通过scene进行缩放
                if hasattr(self.graph.widget, 'scene'):
                    scene = self.graph.widget.scene()
                    if hasattr(scene, 'zoom_out'):
                        scene.zoom_out()
                        return

                # 尝试直接调用widget的缩放方法
                if hasattr(self.graph.widget, 'zoom_out'):
                    self.graph.widget.zoom_out()
                    return
                elif hasattr(self.graph.widget, 'scale_down'):
                    self.graph.widget.scale_down()
                    return

                print("⚠️ 未找到可用的缩小方法")
            except Exception as e:
                print(f"缩小失败: {e}")

    def fit_to_view(self):
        """适应视图"""
        if NODEGRAPH_AVAILABLE and self.graph:
            try:
                # 使用NodeGraphQt原生方法适应视图
                if hasattr(self.graph.widget, 'view'):
                    view = self.graph.widget.view
                    if hasattr(view, 'auto_fit'):
                        view.auto_fit()
                    elif hasattr(view, 'fit_in_view'):
                        view.fit_in_view()
                    else:
                        # 备用方法
                        self.graph.widget.auto_fit()
                else:
                    # 直接使用widget的方法
                    if hasattr(self.graph.widget, 'auto_fit'):
                        self.graph.widget.auto_fit()
                    elif hasattr(self.graph.widget, 'fit_in_view'):
                        self.graph.widget.fit_in_view()
            except Exception as e:
                print(f"适应视图失败: {e}")

    def select_all_nodes(self):
        """全选节点"""
        if NODEGRAPH_AVAILABLE and self.graph:
            try:
                nodes = self.graph.all_nodes()
                for node in nodes:
                    node.set_selected(True)
            except Exception as e:
                print(f"全选失败: {e}")

    def validate_workflow(self):
        """验证工作流"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            QMessageBox.warning(self, "警告", "NodeGraphQt不可用")
            return

        try:
            nodes = self.graph.all_nodes()
            if not nodes:
                QMessageBox.information(self, "验证结果", "画布中没有节点")
                return

            # 简单的验证逻辑
            validation_results = []
            for node in nodes:
                # 检查输入端口
                inputs = node.inputs()
                for port_name, port in inputs.items():
                    if not port.connected_ports():
                        validation_results.append(f"节点 {node.name()} 的输入端口 {port_name} 未连接")

            if validation_results:
                QMessageBox.warning(self, "验证结果", "发现以下问题:\n" + "\n".join(validation_results))
            else:
                QMessageBox.information(self, "验证结果", "工作流验证通过")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"验证工作流失败: {e}")

    def open_kronos_manager(self):
        """打开Kronos模型管理"""
        if KRONOS_MANAGEMENT_AVAILABLE:
            dialog = KronosManagerDialog(self)
            dialog.exec()
        else:
            # 使用原来的简单对话框作为备用
            dialog = KronosManagerDialog(self)
            dialog.exec()

    def open_ai_manager(self):
        """打开AI功能管理"""
        if AI_MANAGEMENT_AVAILABLE:
            dialog = AIManagementDialog(self)
            dialog.exec()
        else:
            # 使用原来的简单对话框作为备用
            dialog = AIManagerDialog(self)
            dialog.exec()

    def open_visualization_tools(self):
        """打开可视化工具"""
        if VISUALIZATION_AVAILABLE:
            dialog = VisualizationToolsDialog(self)
            dialog.exec()
        else:
            # 使用原来的简单对话框作为备用
            dialog = VisualizationToolsDialog(self)
            dialog.exec()

    def open_database_management(self):
        """打开数据库管理"""
        if not DATABASE_MANAGEMENT_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "数据库管理模块未安装或初始化失败")
            return

        try:
            # 创建数据库管理对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("数据库管理")
            dialog.setModal(True)
            dialog.resize(1000, 700)

            # 创建布局
            layout = QVBoxLayout(dialog)

            # 添加数据库管理组件
            db_widget = DatabaseManagementWidget(dialog)
            layout.addWidget(db_widget)

            # 显示对话框
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开数据库管理失败: {e}")

    def launch_chat2db(self):
        """启动Chat2DB"""
        if not DATABASE_MANAGEMENT_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "数据库管理模块未安装或初始化失败")
            return

        try:
            # 创建数据库管理器
            db_manager = RockXQlibDatabaseManager()

            # 启动Chat2DB
            if db_manager.start_chat2db():
                QMessageBox.information(self, "启动成功", "Chat2DB已成功启动")
            else:
                QMessageBox.critical(self, "启动失败", "Chat2DB启动失败，请检查安装和配置")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动Chat2DB失败: {e}")

    def open_universal_config(self):
        """打开通用配置管理"""
        if not UNIVERSAL_CONFIG_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "通用配置模块未安装或初始化失败")
            return

        try:
            # 创建通用配置管理对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("RockX通用配置管理")
            dialog.setModal(True)
            dialog.resize(800, 600)

            # 创建布局
            layout = QVBoxLayout(dialog)

            # 添加配置管理组件
            config_widget = self._create_universal_config_widget(dialog)
            layout.addWidget(config_widget)

            # 显示对话框
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开通用配置管理失败: {e}")

    def switch_system_type(self):
        """切换系统类型"""
        if not UNIVERSAL_CONFIG_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "通用配置模块未安装或初始化失败")
            return

        try:
            # 创建系统选择对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("切换系统类型")
            dialog.setModal(True)
            dialog.resize(400, 300)

            layout = QVBoxLayout(dialog)

            # 标题
            title = QLabel("选择RockX系统类型")
            title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
            layout.addWidget(title)

            # 系统列表
            config_manager = RockXUniversalConfigManager()
            available_systems = config_manager.get_available_systems()

            system_list = QListWidget()
            for system in available_systems:
                system_config = config_manager.get_system_config(system)
                system_type = system_config.system_type.value if hasattr(system_config.system_type, 'value') else str(system_config.system_type)
                item_text = f"{system} ({system_type}) - {system_config.description}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, system)
                system_list.addItem(item)

            layout.addWidget(system_list)

            # 按钮
            button_layout = QHBoxLayout()

            switch_button = QPushButton("切换")
            switch_button.clicked.connect(lambda: self._perform_system_switch(system_list, dialog))
            button_layout.addWidget(switch_button)

            cancel_button = QPushButton("取消")
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_button)

            layout.addLayout(button_layout)

            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换系统类型失败: {e}")

    def _create_universal_config_widget(self, parent):
        """创建通用配置管理组件"""
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)

        # 标题
        title = QLabel("RockX通用配置管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)

        # 创建标签页
        tab_widget = QTabWidget()

        # 系统配置标签页
        systems_tab = self._create_systems_config_tab()
        tab_widget.addTab(systems_tab, "系统配置")

        # SQL模板标签页
        templates_tab = self._create_templates_config_tab()
        tab_widget.addTab(templates_tab, "SQL模板")

        # LLM配置标签页
        llm_tab = self._create_llm_config_tab()
        tab_widget.addTab(llm_tab, "LLM配置")

        layout.addWidget(tab_widget)

        return widget

    def _create_systems_config_tab(self):
        """创建系统配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 系统列表
        config_manager = RockXUniversalConfigManager()
        available_systems = config_manager.get_available_systems()

        systems_list = QListWidget()
        for system in available_systems:
            system_config = config_manager.get_system_config(system)
            system_type = system_config.system_type.value if hasattr(system_config.system_type, 'value') else str(system_config.system_type)
            item_text = f"{system} ({system_type})"
            systems_list.addItem(item_text)

        layout.addWidget(QLabel("可用系统:"))
        layout.addWidget(systems_list)

        # 系统信息显示
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(200)
        layout.addWidget(QLabel("系统信息:"))
        layout.addWidget(info_text)

        # 连接选择事件
        systems_list.itemSelectionChanged.connect(
            lambda: self._update_system_info(systems_list, info_text, config_manager)
        )

        return widget

    def _create_templates_config_tab(self):
        """创建SQL模板配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 模板列表
        config_manager = RockXUniversalConfigManager()
        templates = list(config_manager.sql_templates.values())

        templates_list = QListWidget()
        for template in templates:
            item_text = f"{template.name} ({template.category})"
            templates_list.addItem(item_text)

        layout.addWidget(QLabel("SQL模板:"))
        layout.addWidget(templates_list)

        return widget

    def _create_llm_config_tab(self):
        """创建LLM配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # LLM状态信息
        if UNIVERSAL_CONFIG_AVAILABLE:
            try:
                llm_manager = UniversalLLMManager()
                models = llm_manager.get_available_models()

                models_list = QListWidget()
                for model in models:
                    provider = model.provider.value if hasattr(model.provider, 'value') else str(model.provider)
                    model_type = model.model_type.value if hasattr(model.model_type, 'value') else str(model.model_type)
                    item_text = f"{model.name} ({provider}) - {model_type}"
                    models_list.addItem(item_text)

                layout.addWidget(QLabel("可用LLM模型:"))
                layout.addWidget(models_list)

                # 统计信息
                stats = llm_manager.get_stats()
                stats_text = QTextEdit()
                stats_text.setReadOnly(True)
                stats_text.setMaximumHeight(150)
                stats_text.setPlainText(f"总请求数: {stats['total_requests']}\n总Token数: {stats['total_tokens']}\n可用模型数: {stats['available_models']}")
                layout.addWidget(QLabel("LLM统计信息:"))
                layout.addWidget(stats_text)

            except Exception as e:
                error_label = QLabel(f"LLM配置加载失败: {e}")
                error_label.setStyleSheet("color: red;")
                layout.addWidget(error_label)

        return widget

    def _update_system_info(self, systems_list, info_text, config_manager):
        """更新系统信息显示"""
        current_item = systems_list.currentItem()
        if current_item:
            system_name = current_item.text().split(' ')[0]
            system_config = config_manager.get_system_config(system_name)

            if system_config:
                system_type = system_config.system_type.value if hasattr(system_config.system_type, 'value') else str(system_config.system_type)
                info = f"""
系统名称: {system_config.system_name}
系统类型: {system_type}
版本: {system_config.version}
描述: {system_config.description}
数据库连接数: {len(system_config.database_config)}
SQL模板数: {len(system_config.sql_templates)}
启用状态: {'是' if system_config.enabled else '否'}
"""
                info_text.setPlainText(info)

    def _perform_system_switch(self, system_list, dialog):
        """执行系统切换"""
        current_item = system_list.currentItem()
        if current_item:
            system_name = current_item.data(Qt.UserRole)
            QMessageBox.information(self, "系统切换", f"已切换到系统: {system_name}\n\n注意: 系统切换功能正在开发中...")
            dialog.accept()
        else:
            QMessageBox.warning(self, "警告", "请选择一个系统")

    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h3>RockXQlib 完整集成量化分析平台</h3>
        <p>版本: 1.0.0</p>
        <p>基于Qlib核心架构的统一节点管理系统</p>
        <p>集成功能:</p>
        <ul>
        <li>Qlib核心节点</li>
        <li>AI功能和LLM模型</li>
        <li>可视化工具</li>
        <li>Kronos金融K线大模型</li>
        <li>核心集成功能</li>
        </ul>
        <p>© 2025 RockXQlib Team</p>
        """
        QMessageBox.about(self, "关于", about_text)

    def _load_custom_workflow(self, data):
        """加载自定义工作流"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            return

        try:
            # 清空画布 - 使用NodeGraphQt原生方法
            nodes = self.graph.all_nodes()
            for node in nodes:
                self.graph.delete_node(node)

            # 创建节点
            node_map = {}
            if 'nodes' in data:
                for node_data in data['nodes']:
                    node_id = node_data.get('id')
                    node_type = node_data.get('type')
                    node_name = node_data.get('name', node_type)
                    position = node_data.get('position', [0, 0])

                    # 创建节点
                    node = self.graph.create_node(node_type, name=node_name)
                    if node:
                        node.set_pos(position[0], position[1])
                        node_map[node_id] = node

            # 创建连接
            if 'connections' in data:
                for conn_data in data['connections']:
                    from_node_id = conn_data.get('from')
                    to_node_id = conn_data.get('to')
                    from_port = conn_data.get('from_port')
                    to_port = conn_data.get('to_port')

                    if from_node_id in node_map and to_node_id in node_map:
                        from_node = node_map[from_node_id]
                        to_node = node_map[to_node_id]

                        # 创建连接
                        try:
                            if hasattr(from_node, 'outputs') and hasattr(to_node, 'inputs'):
                                from_output = from_node.outputs().get(from_port)
                                to_input = to_node.inputs().get(to_port)
                                if from_output and to_input:
                                    from_output.connect_to(to_input)
                        except Exception as e:
                            print(f"创建连接失败: {e}")

        except Exception as e:
            print(f"加载自定义工作流失败: {e}")

    def _create_workflow_from_yaml(self, yaml_data):
        """从YAML创建工作流"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            return

        try:
            # 清空画布 - 使用NodeGraphQt原生方法
            try:
                # 获取所有节点并删除
                nodes = self.graph.all_nodes()
                for node in nodes:
                    self.graph.delete_node(node)
                print("✅ 画布已清空")
            except Exception as e:
                print(f"清空画布失败: {e}")

            # 解析YAML配置
            workflow_config = self._parse_yaml_config(yaml_data)
            print(f"🔍 解析YAML配置: {len(workflow_config.get('nodes', []))} 个节点")

            # 创建节点
            node_map = {}
            for node_config in workflow_config.get('nodes', []):
                print(f"🔧 创建节点: {node_config.get('type')} - {node_config.get('name')}")
                node = self._create_node_from_config(node_config)
                if node:
                    node_map[node_config['id']] = node
                    print(f"✅ 节点创建成功: {node_config.get('name')}")
                else:
                    print(f"❌ 节点创建失败: {node_config.get('name')}")

            # 创建连接
            for conn_config in workflow_config.get('connections', []):
                print(f"🔗 创建连接: {conn_config.get('from')} -> {conn_config.get('to')}")
                self._create_connection_from_config(conn_config, node_map)

            print(f"🎉 YAML工作流创建完成，共创建 {len(node_map)} 个节点")

        except Exception as e:
            print(f"从YAML创建工作流失败: {e}")
            import traceback
            traceback.print_exc()

    def _parse_yaml_config(self, yaml_data):
        """解析YAML配置"""
        workflow_config = {
            'nodes': [],
            'connections': []
        }

        print(f"🔍 解析YAML数据: {list(yaml_data.keys())}")

        # 解析Qlib初始化
        if 'qlib_init' in yaml_data:
            workflow_config['nodes'].append({
                'id': 'qlib_init',
                'type': 'qlib.core.init',
                'name': 'Qlib初始化',
                'position': [0, 0],
                'properties': yaml_data['qlib_init']
            })
            print("✅ 添加Qlib初始化节点")

        # 解析数据集配置
        if 'task' in yaml_data and 'dataset' in yaml_data['task']:
            dataset_config = yaml_data['task']['dataset']

            # 如果数据集配置包含TSDatasetH，需要正确解析handler配置
            if dataset_config.get('class') == 'TSDatasetH' and 'handler' in dataset_config.get('kwargs', {}):
                handler_config = dataset_config['kwargs']['handler']
                # 创建正确的数据集配置
                processed_config = {
                    'handler_class': handler_config.get('class', 'Alpha158'),
                    'module_path': handler_config.get('module_path', 'qlib.contrib.data.handler'),
                    'handler_kwargs': handler_config.get('kwargs', {}),
                    'segments': dataset_config['kwargs'].get('segments', {}),
                    'step_len': dataset_config['kwargs'].get('step_len', 20)
                }
            else:
                # 使用原始配置
                processed_config = dataset_config

            workflow_config['nodes'].append({
                'id': 'dataset',
                'type': 'qlib.core.dataset',
                'name': '数据集',
                'position': [200, 0],
                'properties': processed_config
            })
            print("✅ 添加数据集节点")

        # 解析模型配置
        if 'task' in yaml_data and 'model' in yaml_data['task']:
            model_config = yaml_data['task']['model']
            workflow_config['nodes'].append({
                'id': 'model',
                'type': 'qlib.core.model',
                'name': 'LSTM模型',
                'position': [400, 0],
                'properties': model_config
            })
            print("✅ 添加LSTM模型节点")

        # 解析策略配置
        if 'port_analysis_config' in yaml_data and 'strategy' in yaml_data['port_analysis_config']:
            strategy_config = yaml_data['port_analysis_config']['strategy'].copy()

            # 确保策略配置包含正确的模块路径
            if 'module_path' not in strategy_config:
                strategy_config['module_path'] = 'qlib.contrib.strategy.signal_strategy'

            # 处理signal参数：如果signal在kwargs中，提取到顶层
            if 'kwargs' in strategy_config and 'signal' in strategy_config['kwargs']:
                signal_value = strategy_config['kwargs'].pop('signal')
                strategy_config['signal'] = signal_value
                print(f"✅ 将signal从kwargs提取到顶层: {signal_value}")

            # 添加信号占位符处理标记
            strategy_config['_has_signal_placeholder'] = True
            strategy_config['_signal_placeholder'] = '<PRED>'

            workflow_config['nodes'].append({
                'id': 'strategy',
                'type': 'qlib.core.strategy',
                'name': 'TopK策略',
                'position': [600, 0],
                'properties': strategy_config
            })
            print("✅ 添加TopK策略节点")

        # 解析回测配置
        if 'port_analysis_config' in yaml_data and 'backtest' in yaml_data['port_analysis_config']:
            backtest_config = yaml_data['port_analysis_config']['backtest']
            # 添加策略配置到回测配置中
            if 'strategy' in yaml_data['port_analysis_config']:
                backtest_config['strategy'] = yaml_data['port_analysis_config']['strategy']
            workflow_config['nodes'].append({
                'id': 'backtest',
                'type': 'qlib.core.backtest',
                'name': '回测',
                'position': [800, 0],
                'properties': backtest_config
            })
            print("✅ 添加回测节点")

        # 创建智能连接
        node_ids = [node['id'] for node in workflow_config['nodes']]
        print(f"🔗 创建连接: {node_ids}")

        # 根据节点类型创建合适的连接
        for i in range(len(node_ids) - 1):
            from_node_id = node_ids[i]
            to_node_id = node_ids[i + 1]

            # 根据节点类型确定端口名称
            if from_node_id == 'qlib_init':
                from_port = 'initialized_qlib'
            elif from_node_id == 'dataset':
                from_port = 'dataset'
            elif from_node_id == 'model':
                from_port = 'predictions'
            elif from_node_id == 'strategy':
                from_port = 'signals'
            else:
                from_port = 'output'

            if to_node_id == 'dataset':
                to_port = 'qlib_data'
            elif to_node_id == 'model':
                to_port = 'dataset'
            elif to_node_id == 'strategy':
                to_port = 'predictions'
            elif to_node_id == 'backtest':
                to_port = 'strategy'
            else:
                to_port = 'input'

            workflow_config['connections'].append({
                'from': from_node_id,
                'to': to_node_id,
                'from_port': from_port,
                'to_port': to_port
            })
            print(f"🔗 连接: {from_node_id}.{from_port} -> {to_node_id}.{to_port}")

        return workflow_config

    def _create_node_from_config(self, node_config):
        """从配置创建节点"""
        try:
            node_type = node_config.get('type')
            node_name = node_config.get('name', node_type)
            position = node_config.get('position', [0, 0])

            print(f"🔧 尝试创建节点: type={node_type}, name={node_name}, position={position}")

            # 检查节点类型是否已注册
            if hasattr(self.graph, 'factory') and self.graph.factory:
                if hasattr(self.graph.factory, '_nodes'):
                    available_types = list(self.graph.factory._nodes.keys())
                    print(f"🔍 可用节点类型: {available_types}")
                    if node_type not in available_types:
                        print(f"❌ 节点类型 {node_type} 未注册")
                        return None

            # 创建节点
            node = self.graph.create_node(node_type, name=node_name)
            if node:
                print(f"✅ 节点创建成功: {node_name}")
                node.set_pos(position[0], position[1])
                print(f"✅ 节点位置设置: {position}")

                # 设置属性 - 根据节点类型处理不同的属性
                properties = node_config.get('properties', {})
                self._set_node_properties(node, node_type, properties)
            else:
                print(f"❌ 节点创建失败: {node_name}")

            return node
        except Exception as e:
            print(f"❌ 创建节点失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _set_node_properties(self, node, node_type, properties):
        """根据节点类型设置属性"""
        try:
            if node_type == 'qlib.core.init':
                # Qlib初始化节点属性
                if 'provider_uri' in properties:
                    node.set_property('provider_uri', str(properties['provider_uri']))
                if 'region' in properties:
                    node.set_property('region', str(properties['region']))
                print(f"✅ 设置Qlib初始化节点属性")

            elif node_type == 'qlib.core.dataset':
                # 数据集节点属性
                if 'class' in properties:
                    node.set_property('handler_class', str(properties['class']))
                if 'kwargs' in properties and 'handler' in properties['kwargs']:
                    handler_config = properties['kwargs']['handler']
                    if 'kwargs' in handler_config:
                        handler_kwargs = handler_config['kwargs']
                        if 'start_time' in handler_kwargs:
                            node.set_property('train_start', str(handler_kwargs['start_time']))
                        if 'end_time' in handler_kwargs:
                            node.set_property('train_end', str(handler_kwargs['end_time']))
                        if 'instruments' in handler_kwargs:
                            node.set_property('instruments', str(handler_kwargs['instruments']))
                print(f"✅ 设置数据集节点属性")

            elif node_type == 'qlib.core.model':
                # 模型节点属性
                if 'class' in properties:
                    node.set_property('model_class', str(properties['class']))
                if 'kwargs' in properties:
                    model_kwargs = properties['kwargs']
                    # 将模型参数转换为JSON字符串
                    import json
                    node.set_property('model_params', json.dumps(model_kwargs))
                print(f"✅ 设置模型节点属性")

            elif node_type == 'qlib.core.strategy':
                # 策略节点属性
                if 'class' in properties:
                    node.set_property('strategy_class', str(properties['class']))
                if 'module_path' in properties:
                    node.set_property('module_path', str(properties['module_path']))
                if 'signal' in properties:
                    node.set_property('signal', str(properties['signal']))
                if 'kwargs' in properties:
                    strategy_kwargs = properties['kwargs']
                    import json
                    node.set_property('strategy_params', json.dumps(strategy_kwargs))
                    node.set_property('strategy_kwargs', json.dumps(strategy_kwargs))
                print(f"✅ 设置策略节点属性")

            elif node_type == 'qlib.core.backtest':
                # 回测节点属性
                if 'start_time' in properties:
                    node.set_property('start_time', str(properties['start_time']))
                if 'end_time' in properties:
                    node.set_property('end_time', str(properties['end_time']))
                if 'account' in properties:
                    node.set_property('initial_capital', str(properties['account']))
                if 'benchmark' in properties:
                    node.set_property('benchmark', str(properties['benchmark']))
                if 'strategy' in properties:
                    strategy_config = properties['strategy']
                    import json
                    node.set_property('strategy_config', json.dumps(strategy_config))
                print(f"✅ 设置回测节点属性")

        except Exception as e:
            print(f"❌ 设置节点属性失败: {e}")

    def _create_connection_from_config(self, conn_config, node_map):
        """从配置创建连接"""
        try:
            from_node_id = conn_config.get('from')
            to_node_id = conn_config.get('to')
            from_port = conn_config.get('from_port', 'output')
            to_port = conn_config.get('to_port', 'input')

            print(f"🔗 尝试创建连接: {from_node_id}.{from_port} -> {to_node_id}.{to_port}")

            if from_node_id in node_map and to_node_id in node_map:
                from_node = node_map[from_node_id]
                to_node = node_map[to_node_id]

                print(f"✅ 找到节点: {from_node.name()} -> {to_node.name()}")

                # 获取端口
                from_outputs = from_node.outputs()
                to_inputs = to_node.inputs()

                print(f"🔍 源节点输出端口: {list(from_outputs.keys())}")
                print(f"🔍 目标节点输入端口: {list(to_inputs.keys())}")

                # 尝试找到匹配的端口
                from_output = None
                to_input = None

                # 如果指定的端口名存在，使用它
                if from_port in from_outputs:
                    from_output = from_outputs[from_port]
                else:
                    # 否则使用第一个可用的输出端口
                    if from_outputs:
                        from_output = list(from_outputs.values())[0]
                        from_port = list(from_outputs.keys())[0]

                if to_port in to_inputs:
                    to_input = to_inputs[to_port]
                else:
                    # 否则使用第一个可用的输入端口
                    if to_inputs:
                        to_input = list(to_inputs.values())[0]
                        to_port = list(to_inputs.keys())[0]

                if from_output and to_input:
                    # 创建连接
                    from_output.connect_to(to_input)
                    print(f"✅ 连接创建成功: {from_node.name()}.{from_port} -> {to_node.name()}.{to_port}")
                else:
                    print(f"❌ 无法找到匹配的端口进行连接")
            else:
                print(f"❌ 节点未找到: {from_node_id} 或 {to_node_id}")

        except Exception as e:
            print(f"❌ 创建连接失败: {e}")
            import traceback
            traceback.print_exc()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("RockXQlib")
    app.setApplicationVersion("1.0.0")

    # 设置应用图标
    app.setWindowIcon(app.style().standardIcon(QStyle.SP_ComputerIcon))

    # 创建主窗口
    window = RockXQlibMainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
