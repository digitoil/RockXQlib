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

# ----------------------------------------------------------------
# sys.path 引导（必须在任何 core./gui./nodes. 导入之前执行）
#
# 本文件用的是包式导入（from core.xxx / from gui.xxx / from nodes.xxx），
# 因此**项目根目录**必须在 sys.path 上。直接双击运行时 sys.path[0] 是
# 脚本所在目录，通常没问题；但通过某些启动器 / 模块方式运行时，
# 根目录可能不在路径里，于是 `from core.xxx import ...` 大面积失败。
# 这类问题的隐蔽之处：若某模块把导入包在 try/except ImportError 里，
# 而类定义处又引用了那个未导入的名字，抛出的会是 **NameError** ——
# 它**不会被 except ImportError 捕获**，直接把整个 GUI 带崩。
#
# ⚠️ 顺序很关键：兄弟目录 RockXFWV21 下**也有一个 core 包**
#    （E:\...\RockXFWV21\core\，属于另一个项目：backtest/base/controllers/...）。
#    如果 RockXFWV21 排在 RockXQlib 前面，`import core` 会解析到**错误的那个**，
#    于是 core.workflow_runner / core.qlib_paths 等统统 "No module named"，
#    而且报错信息完全指不到真正的原因。
#    所以必须保证 RockXQlib 在最前 —— 用**倒序**插入，让 _HERE 最终位于 sys.path[0]。
#
# ⚠️ 绝对不要把 `<项目>/qlib` 加进 sys.path！
#    `RockXQlib/qlib` **本身就是 qlib 包**（含 __init__.py / data / model / ...），
#    并没有嵌套的 qlib/qlib。把它加进路径只会带来两个害处：
#      1. 让 `import qlib` 仍然可用（其实 _HERE 已经在路径上，本来就够用），
#         纯属多余；
#      2. 把 qlib 的**内部子包全部暴露成顶层模块** ——
#         backtest / cli / config / constant / contrib / data / log / model /
#         rl / strategy / tests / typehint / utils / workflow
#         共 14 个名字。任何 `import model` / `import data` / `import utils`
#         都会静默命中 qlib 的内部实现。
#    实测后果：`from model import Kronos`（Kronos 节点）命中的是
#    qlib/model/__init__.py，报
#        ImportError: attempted relative import beyond top-level package
#    —— 报错完全指不到真正原因。去掉这个路径后 Kronos 恢复正常的
#    "模块不存在 → 优雅降级" 行为。
# ----------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (os.path.join(_PARENT, "RockXFWV21"), _HERE):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# 自检：确认 qlib 的内部子包没有被暴露成顶层模块
def _verify_no_qlib_internals_leaked():
    """确保 <项目>/qlib 不在 sys.path 上。

    只要它在，qlib 的内部子包（model / data / utils / workflow / ...）
    就会变成顶层可导入模块，静默遮蔽同名模块。
    """
    leaked = os.path.join(_HERE, "qlib")
    norm = os.path.normcase(os.path.abspath(leaked))
    bad = [p for p in sys.path
           if os.path.normcase(os.path.abspath(p or ".")) == norm]
    if bad:
        for p in bad:
            sys.path.remove(p)
        print("=" * 70)
        print("⚠️ 检测到 <项目>/qlib 被加进了 sys.path，已自动移除。")
        print("    它会让 qlib 的内部子包（model/data/utils/workflow/...）")
        print("    暴露成顶层模块，静默遮蔽同名模块（例如 Kronos 节点的")
        print("    `from model import ...` 会命中 qlib/model）。")
        print("=" * 70)


_verify_no_qlib_internals_leaked()

# 自检：确认 core 解析到的是本项目，而不是 RockXFWV21 的同名包
def _verify_core_package():
    try:
        import core as _core
    except Exception as e:
        print(f"⚠️ core 包导入失败: {e}")
        return
    core_file = getattr(_core, "__file__", "") or ""
    if os.path.normcase(_HERE) not in os.path.normcase(core_file):
        print("=" * 70)
        print("⚠️ 警告：import core 解析到了非本项目的包！")
        print(f"    期望目录: {_HERE}")
        print(f"    实际文件: {core_file}")
        print("    这会导致 core.* 模块大面积导入失败。")
        print("    请检查 PYTHONPATH 顺序，确保 RockXQlib 在 RockXFWV21 之前。")
        print("=" * 70)
        # 尽力纠正：把本项目根提到最前，并清理已缓存的错误 core 包
        if _HERE in sys.path:
            sys.path.remove(_HERE)
        sys.path.insert(0, _HERE)
        for _m in [m for m in list(sys.modules) if m == "core" or m.startswith("core.")]:
            del sys.modules[_m]
        try:
            import core as _core2
            f2 = getattr(_core2, "__file__", "") or ""
            print("    已尝试纠正 -> %s" % ("成功" if os.path.normcase(_HERE) in
                                          os.path.normcase(f2) else "仍失败: " + f2))
        except Exception as e:
            print(f"    纠正失败: {e}")
        print("=" * 70)


_verify_core_package()

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# 导入深色主题样式
from dark_theme_styles import DarkThemeStyles
from node_styles_config import NodeStylesConfig

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
    # 重复注册节点时抛这个异常，注册基础节点处要单独捕获
    try:
        from NodeGraphQt.errors import NodeRegistrationError
    except ImportError:
        from NodeGraphQt.base.factory import NodeRegistrationError  # 兼容旧路径
    NODEGRAPH_AVAILABLE = True
    print("✅ NodeGraphQt 导入成功")
except ImportError as _e:
    NODEGRAPH_AVAILABLE = False
    # 定义一个兜底异常类，保证后面 except 子句不会因未定义而 NameError
    class NodeRegistrationError(Exception):
        pass
    print(f"❌ NodeGraphQt 导入失败: {_e}")

# 移除CustomNodesTreeWidget类，直接使用原生NodesTreeWidget

# 对话框类定义
# 确保当前目录在sys.path中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ============================================================================
# 工作流执行线程
#
# 包装 core.workflow_runner.NodeGraphWorkflowRunner（按真实端口连线做拓扑排序、
# 用正确的节点契约 execute() 执行）。
#
# 替换掉的原实现有三个致命问题：
#   1. node_timeout=60s / max_execution_time=300s —— 实测单个 Alpha158 处理器
#      节点就要 127 秒、整链约 380 秒，必然超时。
#   2. _topological_sort 靠硬编码 node.id == 'qlib_init' 判断顺序 ——
#      NodeGraphQt 的 id 是 '0x24ff7c4b770' 这种十六进制串，永远匹配不上。
#   3. 把 node.execute() 又塞进一层 threading.Thread 来"实现超时" ——
#      qlib 的 DataHandler 会用 multiprocessing spawn 子进程，再套线程会让
#      子进程无法正常 spawn；且 Python 无法真正杀线程，"超时"后后台仍在吃内存。
# ============================================================================
class WorkflowExecutionThread(QThread):
    """工作流执行线程。"""

    progress_updated = Signal(str, str)          # message, level
    node_started = Signal(str, int, int)         # label, index, total
    node_finished = Signal(str, bool, float, str)  # label, ok, elapsed, detail
    execution_completed = Signal(dict)           # 汇总结果
    execution_error = Signal(str)                # 错误信息

    def __init__(self, nodes, node_timeout=None, total_timeout=None, parent=None):
        super().__init__(parent)
        self.nodes = list(nodes) if nodes else []

        # 超时只作为"卡死兜底"；None 表示用 runner 里的默认值
        kwargs = {}
        if node_timeout is not None:
            kwargs["node_timeout"] = node_timeout
        if total_timeout is not None:
            kwargs["total_timeout"] = total_timeout

        self.runner = NodeGraphWorkflowRunner(
            self.nodes,
            on_progress=self._on_progress,
            on_node_start=self._on_node_start,
            on_node_end=self._on_node_end,
            **kwargs,
        )

    # ---- 回调转信号（runner 在工作线程里跑，信号会排队到主线程）----

    def _on_progress(self, message, level="INFO"):
        self.progress_updated.emit(message, level)

    def _on_node_start(self, label, index, total):
        self.node_started.emit(label, index, total)

    def _on_node_end(self, label, ok, elapsed, detail):
        self.node_finished.emit(label, ok, elapsed, detail)

    # ---- 线程主体 ----

    def run(self):
        try:
            summary = self.runner.run()
            self.execution_completed.emit(summary)
        except Exception as e:
            import traceback
            self.progress_updated.emit(
                f"工作流执行异常: {e}\n{traceback.format_exc()}", "ERROR")
            self.execution_error.emit(str(e))

    # ---- 对外控制 ----

    def stop_execution(self):
        """请求停止（协作式：当前节点跑完后生效）。"""
        self.runner.request_stop()


# 导入统一节点管理器
try:
    from core.unified_node_manager import UnifiedNodeManager
    from core.config_manager import config_manager
    UNIFIED_MANAGER_AVAILABLE = True
    print("✅ 统一节点管理器导入成功")
except ImportError as e:
    UNIFIED_MANAGER_AVAILABLE = False
    print(f"❌ 统一节点管理器导入失败: {e}")

# 工作流序列化（图 <-> 简洁 JSON：可校验、人类可读、LLM 友好）
try:
    from core.workflow_schema import (
        serialize_graph,
        deserialize_graph,
        validate_workflow,
        collect_specs_from_graph,
        describe_schema,
        dump_workflow,
        load_workflow,
    )
    WORKFLOW_SCHEMA_AVAILABLE = True
    print("✅ 工作流序列化模块导入成功")
except ImportError as e:
    WORKFLOW_SCHEMA_AVAILABLE = False
    print(f"⚠️ 工作流序列化模块不可用: {e}")

# 工作流执行器（按真实端口连线拓扑排序 + 正确节点契约）
try:
    from core.workflow_runner import (
        NodeGraphWorkflowRunner,
        DEFAULT_NODE_TIMEOUT,
        DEFAULT_TOTAL_TIMEOUT,
    )
    WORKFLOW_RUNNER_AVAILABLE = True
    print("✅ 工作流执行器导入成功")
except ImportError as e:
    WORKFLOW_RUNNER_AVAILABLE = False
    NodeGraphWorkflowRunner = None  # type: ignore
    print(f"❌ 工作流执行器导入失败: {e}")

# 回测结果面板（指标卡片 + 资金曲线/回撤图）
try:
    from gui.backtest_result_panel import BacktestResultPanel
    BACKTEST_PANEL_AVAILABLE = True
    print("✅ 回测结果面板导入成功")
except ImportError as e:
    BACKTEST_PANEL_AVAILABLE = False
    BacktestResultPanel = None  # type: ignore
    print(f"❌ 回测结果面板导入失败: {e}")

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
                    # NodeGraphQt 顶层 **没有** 导出 NodeFactory（新版把它
                    # 移到了 base.factory）。先试正确路径，再退回顶层导入名。
                    try:
                        from NodeGraphQt.base.factory import NodeFactory
                    except ImportError:
                        from NodeGraphQt import NodeFactory  # 兼容旧版
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
        # 右侧要容纳回测图表，适当加宽
        splitter.setSizes([220, 740, 420])

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
            # 把树里的英文标识符类别换成中文（含对 Backdrop 的说明）
            self._apply_tree_category_labels()
            layout.addWidget(self.node_tree)
        else:
            # 备用节点列表
            self.node_list = QListWidget()
            self.node_list.setStyleSheet(DarkThemeStyles.get_left_sidebar_style())
            layout.addWidget(self.node_list)

        return panel

    # 节点树里类别名 -> 中文标签
    # 树的类别是按标识符前缀自动分组的（'.'.join(nid.split('.')[:-1])），
    # 所以显示的是 qlib.core / kronos / core 这类英文标识符。
    # 这里映射成中文，顺带把 NodeGraphQt 自带的装饰节点说明清楚。
    _TREE_CATEGORY_LABELS = {
        "qlib.core": "Qlib 核心",
        "qlib.ai": "AI 功能",
        "qlib.viz": "可视化",
        "qlib.feature": "特征工程",
        "kronos": "Kronos 模型",
        "core": "核心集成",
        # NodeGraphQt 内置的装饰节点：Backdrop 是画布上的分组框/注释框，
        # 有用但**不参与工作流执行**（没有 execute()）。
        # 明确标注，免得被当成工作流节点。
        "nodeGraphQt.nodes": "画布工具（不参与运行）",
    }

    def _apply_tree_category_labels(self):
        """把节点树的英文类别名换成中文。

        注意：``NodesTreeWidget.set_category_label()`` 只对**已存在**的类别
        生效，而类别是在控件构造时按当前 factory 内容生成的，
        所以必须在 ``NodesTreeWidget(...)`` 之后调用。
        """
        tree = getattr(self, "node_tree", None)
        if tree is None or not hasattr(tree, "set_category_label"):
            return
        applied = []
        for cat, label in self._TREE_CATEGORY_LABELS.items():
            try:
                tree.set_category_label(cat, label)
                applied.append(cat)
            except Exception as e:
                print(f"[节点树] 类别 {cat} 标签设置失败（不影响功能）: {e}")
        if applied:
            print(f"[节点树] 已汉化类别: {applied}")

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
        #
        # ⚠️ 节点数必须**动态取**，不要写死 —— 这里原先硬编码 "22 个节点"，
        # 在扩展开关收紧（25 -> 9）后就变成错误信息，误导排查。
        self.log_message("🚀 RockXQlib系统启动完成")
        try:
            _mgr = getattr(self, "unified_manager", None)
            _n = len(_mgr.registry.get_all_nodes()) if _mgr else 0
        except Exception:
            _n = 0
        self.log_message(f"📋 节点系统初始化完成，共注册 {_n} 个节点")
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
                # NodeGraphQt 的真实签名：
                #   set_grid_mode(mode)       mode 是 ViewerEnum 的字符串值
                #   set_grid_color(r, g, b)   **三个独立参数**，不是 list
                # 原实现传 [0.9,0.9,0.9,1.0] 会报
                #   NodeGraph.set_grid_color() missing 2 required positional arguments
                if hasattr(self.graph, 'set_grid_mode'):
                    try:
                        from NodeGraphQt.constants import ViewerEnum
                        self.graph.set_grid_mode(ViewerEnum.GRID_DISPLAY_DOTS.value)
                    except Exception:
                        self.graph.set_grid_mode(True)
                if hasattr(self.graph, 'set_grid_color'):
                    self.graph.set_grid_color(0.9, 0.9, 0.9)  # 浅灰色网格
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
        """创建右侧面板：属性编辑器 / 回测结果 两个页签。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # ---- 属性编辑器 ----
        prop_widget = QWidget()
        prop_layout = QVBoxLayout(prop_widget)
        prop_layout.setContentsMargins(4, 4, 4, 4)

        if NODEGRAPH_AVAILABLE and self.graph:
            self.property_editor = PropertiesBinWidget(node_graph=self.graph)
            self.property_editor.setProperty("class", "property_editor")
            self.property_editor.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
            prop_layout.addWidget(self.property_editor)
        else:
            self.property_editor = QTextEdit()
            self.property_editor.setPlaceholderText("属性编辑器\nNodeGraphQt 不可用时显示")
            self.property_editor.setProperty("class", "property_editor")
            self.property_editor.setStyleSheet(DarkThemeStyles.get_right_sidebar_style())
            prop_layout.addWidget(self.property_editor)

        # ---- 回测结果 ----
        if BACKTEST_PANEL_AVAILABLE:
            self.result_panel = BacktestResultPanel()
        else:
            self.result_panel = None

        # ---- 页签容器 ----
        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #3a3a3a; background: #1e1e1e; }"
            "QTabBar::tab { background: #2a2a2a; color: #b0b0b0; padding: 5px 12px;"
            " border: 1px solid #3a3a3a; }"
            "QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; }")
        self.right_tabs.addTab(prop_widget, "属性编辑器")
        if self.result_panel is not None:
            self.right_tabs.addTab(self.result_panel, "回测结果")
        else:
            hint = QLabel("回测结果面板不可用\n（gui.backtest_result_panel 导入失败）")
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet("color: #b0b0b0;")
            self.right_tabs.addTab(hint, "回测结果")

        layout.addWidget(self.right_tabs)
        return panel

    def show_result_tab(self):
        """切换到「回测结果」页签。"""
        tabs = getattr(self, "right_tabs", None)
        if tabs is None:
            return
        for i in range(tabs.count()):
            if tabs.tabText(i) == "回测结果":
                tabs.setCurrentIndex(i)
                break

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

        file_menu.addSeparator()

        # 简洁 JSON 格式（人类可读、可校验、LLM 友好）—— 与 save_session 并存
        export_json_action = QAction('导出工作流(JSON)', self)
        export_json_action.triggered.connect(self.export_workflow_json)
        file_menu.addAction(export_json_action)

        import_json_action = QAction('导入工作流(JSON)', self)
        import_json_action.triggered.connect(self.import_workflow_json)
        file_menu.addAction(import_json_action)

        file_menu.addSeparator()

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

        # 保存为实例属性：运行期间要禁用"运行"、启用"停止"
        self.run_action = QAction('一键运行工作流', self)
        self.run_action.setShortcut('F5')
        self.run_action.triggered.connect(self.run_workflow)
        workflow_menu.addAction(self.run_action)

        self.stop_action = QAction('停止工作流', self)
        self.stop_action.setShortcut('F6')
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self.stop_workflow)
        workflow_menu.addAction(self.stop_action)

        workflow_menu.addSeparator()

        validate_action = QAction('验证工作流', self)
        validate_action.triggered.connect(self.validate_workflow)
        workflow_menu.addAction(validate_action)

        view_result_action = QAction('查看回测结果', self)
        view_result_action.triggered.connect(self.show_result_tab)
        workflow_menu.addAction(view_result_action)

        reset_color_action = QAction('重置节点配色', self)
        reset_color_action.setToolTip('把执行时标记的绿/红配色还原为原始配色')
        reset_color_action.triggered.connect(self.reset_node_colors)
        workflow_menu.addAction(reset_color_action)

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

        # 一键运行 —— 复用菜单里创建的 action（否则会出现两个"运行"按钮，
        # 且运行期间只有菜单那个会被禁用）。做成绿色醒目样式。
        try:
            self.run_action.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.run_action.setText('▶ 一键运行')
            self.run_action.setToolTip('按数据流顺序执行画布上的全部节点（F5）')
        except Exception:
            pass
        toolbar.addAction(self.run_action)

        # 停止 —— 同样复用
        try:
            self.stop_action.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
            self.stop_action.setText('■ 停止')
            self.stop_action.setToolTip('停止工作流（F6，当前节点跑完后生效）')
        except Exception:
            pass
        toolbar.addAction(self.stop_action)

        # 给运行按钮加醒目样式（工具栏级别的 QToolButton 定制）
        try:
            run_widget = toolbar.widgetForAction(self.run_action)
            if run_widget is not None:
                run_widget.setStyleSheet(
                    "QToolButton { background-color: #27ae60; color: #ffffff;"
                    " font-weight: 600; padding: 4px 12px; border-radius: 4px;"
                    " border: 1px solid #229954; }"
                    "QToolButton:hover { background-color: #2ecc71; }"
                    "QToolButton:disabled { background-color: #3a3a3a;"
                    " color: #808080; border: 1px solid #4a4a4a; }")
        except Exception as e:
            print(f"运行按钮样式设置失败（不影响功能）: {e}")

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
                try:
                    from NodeGraphQt.base.factory import NodeFactory
                except ImportError:
                    from NodeGraphQt import NodeFactory  # 兼容旧版
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
            # 关键：NodeGraphQt 的 type_ 是
            #     cls.__identifier__ + '.' + cls.__name__
            # 两者都在**类层面**求值（注册时立即读取）。
            # 原实现只在 __init__ 里设 __identifier__（实例级），
            # 于是四个类的 __identifier__ 全部继承自 BaseNode，
            # 只有 cls.__name__ 不同 —— 而这里 f"{name}Class" 生成的
            # 类名在不同循环里可能重名（如两次都叫 数据节点Class），
            # 第二次注册就抛 NodeRegistrationError：
            #   node type "nodeGraphQt.nodes.数据节点Class" already registered
            # 修法：把 __identifier__ 作为**类属性**写进 type() 的 dict，
            # 并保证类名唯一（用 identifier 派生）。
            safe_cls_name = "Basic_" + identifier.replace(".", "_") + "Class"
            node_class = type(safe_cls_name, (BasicNode,), {
                '__identifier__': identifier,   # 类级，供 type_ 使用
                'NODE_NAME': name,              # 类级，供 factory 的 name 索引使用
                '__init__': lambda self, n=name, i=identifier: BasicNode.__init__(self, n, i)
            })
            try:
                self.graph.register_node(node_class)
                print(f"✅ 注册基础节点: {name} ({identifier})")
            except NodeRegistrationError as e:
                # 重复注册不算致命，跳过即可，不要中断整个初始化
                print(f"⚠️ 跳过已注册的基础节点: {name} -> {e}")

    def connect_signals(self):
        """连接信号。

        NodeGraphQt 实际暴露的信号（已用 dir() 枚举确认）是：
            node_created(node) / nodes_deleted(list) /
            port_connected(Port, Port) / port_disconnected(Port, Port) /
            property_changed(Node, str, object) / session_changed(str) /
            node_selected(list) / node_selection_changed(list)

        原实现连的是 node_deleted / connection_created / connection_deleted
        —— 这三个信号在 NodeGraphQt 里**不存在**，所以每次都会抛
        AttributeError 掉进 except 分支，状态栏只能靠 1 秒定时器刷新。
        这里改为逐个 try 连接真实信号名，任何一个不可用都不影响其余信号。
        """
        if not (NODEGRAPH_AVAILABLE and self.graph):
            return

        # (信号名, 处理函数)  按可用性逐个挂载
        wanted = [
            ('node_created', self.on_node_created),
            ('nodes_deleted', self.on_nodes_deleted),
            ('port_connected', self.on_port_connected),
            ('port_disconnected', self.on_port_disconnected),
            ('property_changed', self.on_property_changed),
        ]
        connected = []
        for sig_name, slot in wanted:
            try:
                sig = getattr(self.graph, sig_name, None)
                if sig is None:
                    continue
                sig.connect(slot)
                connected.append(sig_name)
            except Exception as e:
                print(f"[信号] {sig_name} 连接失败（不影响使用）: {e}")

        # 兜底：始终挂一个定时器刷新，保证状态栏节点/连线计数不会漏更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)
        self.update_status()

        print(f"[信号] 已连接: {connected if connected else '（无）'}；"
              f"状态栏定时刷新已启用")

    def on_node_created(self, node):
        """节点创建事件"""
        self.update_status()
        try:
            self.status_label.setText(f"创建节点: {node.name()}")
        except Exception:
            pass

    def on_nodes_deleted(self, nodes):
        """节点删除事件（NodeGraphQt 传的是 list）"""
        self.update_status()
        try:
            n = len(nodes) if hasattr(nodes, '__len__') else 1
            self.status_label.setText(f"删除节点: {n} 个")
        except Exception:
            pass

    def on_port_connected(self, port_a, port_b):
        """端口连接事件"""
        self.update_status()
        try:
            self.status_label.setText(
                f"连接: {port_a.node().name()}.{port_a.name()} -> "
                f"{port_b.node().name()}.{port_b.name()}")
        except Exception:
            self.status_label.setText("创建连接")

    def on_port_disconnected(self, port_a, port_b):
        """端口断开事件"""
        self.update_status()
        try:
            self.status_label.setText(
                f"断开: {port_a.node().name()}.{port_a.name()} -/- "
                f"{port_b.node().name()}.{port_b.name()}")
        except Exception:
            self.status_label.setText("断开连接")

    def on_property_changed(self, node, prop_name, prop_value):
        """节点属性变更事件"""
        try:
            self.status_label.setText(
                f"修改属性: {node.name()}.{prop_name} = {prop_value}")
        except Exception:
            pass

    # 兼容旧入口名（避免其他地方仍引用）
    def on_node_deleted(self, node):
        self.update_status()

    def on_connection_created(self, connection):
        self.update_status()

    def on_connection_deleted(self, connection):
        self.update_status()

    def update_status(self):
        """更新状态"""
        if NODEGRAPH_AVAILABLE and self.graph:
            try:
                nodes = self.graph.all_nodes()
                node_count = len(nodes)

                # 计算连接数
                #
                # ⚠️ NodeGraphQt 的 node.inputs() / outputs() 在「该方向没有端口」
                # 时返回 **None**，而不是空 dict。直接 .values() 会抛
                # AttributeError，而本方法由 1 秒定时器驱动，会变成每秒刷一条
                # 错误。必须用 `or {}` 兜住。
                connection_count = 0
                for node in nodes:
                    for port in (node.inputs() or {}).values():
                        connection_count += len(port.connected_ports())

                self.node_count_label.setText(f"节点: {node_count}")
                self.connection_count_label.setText(f"连接: {connection_count}")

            except Exception as e:
                print(f"更新状态失败: {e}")

    # 菜单和工具栏动作
    def new_workflow(self):
        """新建工作流"""
        if NODEGRAPH_AVAILABLE and self.graph:
            self.graph.clear_session()
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

    # ---------------------------------------------------------------
    # 工作流 JSON 导出 / 导入（core/workflow_schema.py）
    #
    # 与上面的 save_session 方式的区别：
    #   save_session -> NodeGraphQt 私有格式（含 UI 状态，人类不可读、无法校验）
    #   本方法       -> 简洁 JSON（人类可读、可校验、LLM 友好）
    # 两者并存，互不影响。
    # ---------------------------------------------------------------
    def export_workflow_json(self):
        """导出工作流为简洁 JSON（人类可读、可校验、LLM 友好）。"""
        if not (NODEGRAPH_AVAILABLE and self.graph):
            QMessageBox.warning(self, "警告", "NodeGraphQt 不可用")
            return
        if not WORKFLOW_SCHEMA_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "工作流序列化模块未加载")
            return

        if not self.graph.all_nodes():
            QMessageBox.information(self, "提示", "画布中没有节点")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "导出工作流(JSON)", "workflow.json",
            "JSON 文件 (*.json);;所有文件 (*)")
        if not filename:
            return

        try:
            base = os.path.splitext(os.path.basename(filename))[0]
            data = serialize_graph(self.graph, name=base)
            dump_workflow(data, filename)
            self.log_message(
                "已导出工作流: %s（%d 节点 / %d 连线）"
                % (os.path.basename(filename), len(data["nodes"]), len(data["links"])),
                "SUCCESS")
            self.status_label.setText("已导出: %s" % os.path.basename(filename))
        except Exception as e:
            QMessageBox.critical(self, "错误", "导出工作流失败: %s" % e)

    def import_workflow_json(self):
        """导入简洁 JSON 工作流。先校验，不通过则画布保持不变。"""
        if not (NODEGRAPH_AVAILABLE and self.graph):
            QMessageBox.warning(self, "警告", "NodeGraphQt 不可用")
            return
        if not WORKFLOW_SCHEMA_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "工作流序列化模块未加载")
            return

        filename, _ = QFileDialog.getOpenFileName(
            self, "导入工作流(JSON)", "", "JSON 文件 (*.json);;所有文件 (*)")
        if not filename:
            return

        try:
            data = load_workflow(filename)
        except Exception as e:
            QMessageBox.critical(self, "错误", "读取文件失败: %s" % e)
            return

        # 用真实节点类收集规格（而不是硬编码表，避免节点变了规格没跟着变）
        try:
            specs = collect_specs_from_graph(self.graph)
        except Exception:
            specs = None

        ok, msgs = validate_workflow(data, specs=specs)
        if not ok:
            detail = "\n".join("• " + m for m in msgs[:12])
            QMessageBox.critical(
                self, "校验未通过",
                "工作流有问题，未导入（画布保持不变）:\n\n" + detail)
            self.log_message("导入被拒绝，共 %d 个问题" % len(msgs), "ERROR")
            return

        rok, rerrs = deserialize_graph(data, self.graph, clear=True, specs=specs)
        if not rok:
            detail = "\n".join("• " + m for m in rerrs[:12])
            QMessageBox.critical(self, "导入失败", detail)
            self.log_message("导入失败", "ERROR")
            return

        self.log_message(
            "已导入工作流: %s（%d 节点 / %d 连线）"
            % (os.path.basename(filename),
               len(data.get("nodes", [])), len(data.get("links", []))),
            "SUCCESS")
        for w in [m for m in msgs if m.startswith("[警告]")]:
            self.log_message(w, "WARNING")
        self.status_label.setText("已导入: %s" % os.path.basename(filename))

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
        """一键运行工作流：按真实端口连线拓扑排序，依次执行所有节点。"""
        if not NODEGRAPH_AVAILABLE or not self.graph:
            self.log_message("NodeGraphQt 不可用", "ERROR")
            QMessageBox.warning(self, "警告", "NodeGraphQt 不可用")
            return

        if not WORKFLOW_RUNNER_AVAILABLE:
            self.log_message("工作流执行器不可用（core.workflow_runner 导入失败）", "ERROR")
            QMessageBox.critical(self, "错误", "工作流执行器不可用")
            return

        # 已有线程在跑就不重复启动
        if getattr(self, "workflow_thread", None) is not None and \
                self.workflow_thread.isRunning():
            QMessageBox.information(self, "提示", "工作流正在运行中，请先等待完成或点击停止。")
            return

        try:
            nodes = self.graph.all_nodes()
            if not nodes:
                self.log_message("画布中没有节点", "WARNING")
                QMessageBox.information(self, "提示", "画布中没有节点")
                return

            # 运行前先做一次校验，把"没连线""有环"等问题提前告诉用户
            warnings = self._preflight_check(nodes)
            if warnings:
                for w in warnings:
                    self.log_message(f"⚠️ {w}", "WARNING")
                msg = "运行前检查发现问题：\n\n" + "\n".join(f"• {w}" for w in warnings) + \
                      "\n\n仍要继续运行吗？"
                if QMessageBox.question(
                        self, "运行前检查", msg,
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No) != QMessageBox.Yes:
                    self.log_message("已取消运行", "WARNING")
                    return

            self.log_message("=" * 56, "INFO")
            self.log_message("🚀 开始执行工作流（一键运行）", "INFO")
            self.status_label.setText("正在运行工作流...")
            self.system_status_label.setText("系统: 运行中")
            self.run_action.setEnabled(False)
            self.stop_action.setEnabled(True)

            # 执行前：还原上一轮留下的绿/红配色，并记录原始配色
            self._restore_node_colors()
            self._remember_node_colors(nodes)

            self.workflow_thread = WorkflowExecutionThread(nodes, parent=self)
            self.workflow_thread.progress_updated.connect(self.update_workflow_progress)
            self.workflow_thread.node_started.connect(self._on_node_started)
            self.workflow_thread.node_finished.connect(self._on_node_finished)
            self.workflow_thread.execution_completed.connect(self._workflow_execution_complete)
            self.workflow_thread.execution_error.connect(self._workflow_execution_error)
            self.workflow_thread.finished.connect(self._on_workflow_thread_finished)
            self.workflow_thread.start()

        except Exception as e:
            import traceback
            self.log_message(f"运行工作流失败: {e}", "ERROR")
            self.log_message(traceback.format_exc(), "ERROR")
            QMessageBox.critical(self, "错误", f"运行工作流失败: {e}")
            self.status_label.setText("工作流运行失败")

    def _preflight_check(self, nodes):
        """运行前静态检查，返回问题列表（不阻断，只提示）。"""
        warnings = []
        try:
            from core.workflow_runner import topological_sort_nodes
            ordered, warns = topological_sort_nodes(nodes)
            warnings.extend(warns)
        except Exception as e:
            warnings.append(f"拓扑排序检查失败: {e}")

        # 检查有没有节点缺 execute
        for n in nodes:
            if not callable(getattr(n, "execute", None)):
                try:
                    name = n.name() if callable(getattr(n, "name", None)) else str(n)
                except Exception:
                    name = str(n)
                warnings.append(f"节点「{name}」没有 execute() 方法，运行时会跳过")
        return warnings

    def stop_workflow(self):
        """停止工作流（协作式：当前节点跑完后生效）。"""
        th = getattr(self, "workflow_thread", None)
        if th is None or not th.isRunning():
            self.log_message("当前没有正在运行的工作流", "WARNING")
            return
        self.log_message("⏹ 已请求停止工作流（将在当前节点执行完后停止）", "WARNING")
        self.status_label.setText("正在停止工作流...")
        th.stop_execution()

    def update_workflow_progress(self, message, level="INFO"):
        """更新工作流执行进度"""
        self.log_message(message, level)

    def _node_by_label(self, label):
        """按显示名在画布上找节点（用于执行时高亮）。"""
        if not (NODEGRAPH_AVAILABLE and self.graph):
            return None
        try:
            for n in self.graph.all_nodes():
                try:
                    nm = n.name() if callable(getattr(n, "name", None)) else str(n)
                except Exception:
                    nm = str(n)
                if nm == label:
                    return n
        except Exception:
            pass
        return None

    def _set_node_color(self, node, rgb):
        """给节点上色（rgb 为 (r,g,b)）。"""
        if node is None:
            return
        try:
            node.set_property("color", (rgb[0], rgb[1], rgb[2], 255), push_undo=False)
        except Exception:
            try:
                node.set_property("color", (rgb[0], rgb[1], rgb[2], 255))
            except Exception:
                pass

    def _remember_node_colors(self, nodes):
        """记录运行前的节点颜色，便于结束后还原。"""
        self._saved_node_colors = {}
        for n in nodes:
            try:
                self._saved_node_colors[id(n)] = n.get_property("color")
            except Exception:
                pass

    def _restore_node_colors(self):
        """还原运行前的节点颜色。"""
        saved = getattr(self, "_saved_node_colors", None) or {}
        if not saved or not (NODEGRAPH_AVAILABLE and self.graph):
            return
        try:
            for n in self.graph.all_nodes():
                col = saved.get(id(n))
                if col:
                    try:
                        n.set_property("color", col, push_undo=False)
                    except Exception:
                        pass
        except Exception:
            pass
        self._saved_node_colors = {}

    def reset_node_colors(self):
        """菜单入口：把执行时标记的绿/红配色还原为原始配色。"""
        saved = getattr(self, "_saved_node_colors", None) or {}
        if not saved:
            self.log_message("没有可还原的节点配色记录", "WARNING")
            return
        self._restore_node_colors()
        self.log_message("🎨 节点配色已还原", "SUCCESS")

    def _on_node_started(self, label, index, total):
        """节点开始执行：高亮为橙色。"""
        self.status_label.setText(f"正在执行 [{index}/{total}] {label} ...")
        self._set_node_color(self._node_by_label(label), (230, 150, 30))

    def _on_node_finished(self, label, ok, elapsed, detail):
        """节点执行结束：成功绿色 / 失败红色，并更新状态栏耗时。"""
        try:
            self._set_node_color(self._node_by_label(label),
                                 (39, 174, 96) if ok else (231, 76, 60))
        except Exception:
            pass
        try:
            if ok:
                self.status_label.setText(f"完成 {label}（{elapsed:.2f}s）")
            else:
                self.status_label.setText(f"失败 {label}：{detail}")
        except Exception:
            pass

    def _on_workflow_thread_finished(self):
        """线程收尾：恢复按钮状态并释放线程对象。"""
        try:
            self.run_action.setEnabled(True)
            self.stop_action.setEnabled(False)
        except Exception:
            pass
        th = getattr(self, "workflow_thread", None)
        if th is not None:
            th.deleteLater()
            self.workflow_thread = None

    def _workflow_execution_complete(self, summary):
        """工作流执行完成：渲染指标 + 图表，并切到回测结果页。"""
        summary = summary or {}
        status = summary.get("status")
        ok_count = summary.get("ok_count", 0)
        total = summary.get("total", 0)
        elapsed = summary.get("elapsed", 0.0)

        if status == "success":
            self.log_message(
                f"🎉 工作流执行完成：{ok_count}/{total} 个节点成功，总耗时 {elapsed:.2f}s",
                "SUCCESS")
            self.status_label.setText("工作流执行完成")
        else:
            self.log_message(
                f"⚠️ 工作流部分完成：{ok_count}/{total} 个节点成功，总耗时 {elapsed:.2f}s",
                "WARNING")
            self.status_label.setText(f"工作流完成（{ok_count}/{total}）")
        self.system_status_label.setText("系统: 正常")

        # 逐节点结果汇总到日志
        records = summary.get("records") or []
        if records:
            lines = []
            for r in records:
                mark = "✅" if r.get("ok") else "❌"
                lines.append(f"   {mark} {r.get('node')}  {r.get('elapsed', 0):.2f}s"
                             + (f"  {r.get('detail')}" if r.get("detail") else ""))
            self.log_message("执行明细:\n" + "\n".join(lines), "INFO")

        # ---- 回测结果渲染 ----
        metrics = summary.get("metrics")
        backtest_result = summary.get("backtest_result")
        self._render_backtest_results(backtest_result, metrics)

        # 成功且有结果时不再弹窗打断（日志和结果页已经足够），
        # 只有失败时才弹窗提示。
        if status != "success":
            QMessageBox.warning(
                self, "工作流完成",
                f"工作流部分完成：{ok_count}/{total} 个节点成功。\n"
                f"请查看日志了解失败原因。")

    def _render_backtest_results(self, backtest_result, metrics):
        """把回测结果送到结果面板并切换过去。"""
        if not BACKTEST_PANEL_AVAILABLE or getattr(self, "result_panel", None) is None:
            if backtest_result is None and not metrics:
                self.log_message("本次运行没有产生回测结果", "WARNING")
            return

        if backtest_result is None and not metrics:
            self.log_message("本次运行没有产生回测结果，跳过图表渲染", "WARNING")
            return

        try:
            rendered = self.result_panel.show_backtest_result(backtest_result, metrics)
            # 切到"回测结果"页签
            if getattr(self, "right_tabs", None) is not None:
                for i in range(self.right_tabs.count()):
                    if self.right_tabs.tabText(i) == "回测结果":
                        self.right_tabs.setCurrentIndex(i)
                        break
            if metrics:
                self.log_message(
                    "📊 回测绩效: 总收益 {:.2f}% | 年化 {:.2f}% | 最大回撤 {:.2f}% | 夏普 {:.2f}".format(
                        float(metrics.get("total_return", 0)) * 100,
                        float(metrics.get("annualized_return", 0)) * 100,
                        float(metrics.get("max_drawdown", 0)) * 100,
                        float(metrics.get("sharpe", 0))),
                    "SUCCESS")
            self.log_message(
                "📈 回测图表已渲染到右侧「回测结果」页签"
                if rendered else
                "⚠️ 指标已显示，但图表未能渲染（详见结果页提示）",
                "SUCCESS" if rendered else "WARNING")
        except Exception as e:
            import traceback
            self.log_message(f"渲染回测结果失败: {e}", "ERROR")
            self.log_message(traceback.format_exc(), "ERROR")

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

    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h3>RockXQlib 完整集成量化分析平台</h3>
        <p>版本: 1.0.0</p>
        <p>基于Qlib核心架构的统一节点管理系统</p>
        <p>核心能力:</p>
        <ul>
        <li>Qlib 核心节点（数据 / 处理器 / 数据集 / 模型 / 策略 / 回测）</li>
        <li>特征工程节点（Alpha因子 / 特征工程）</li>
        <li>一键运行工作流 + 回测结果可视化</li>
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
