# RockXQlib - 基于Qlib的高级量化分析系统

基于 Qlib 的研究工作台：可视化节点流，也可无界面跑实验。仓库在 [GitHub](https://github.com/digitoil/RockXQlib)，觉得有用欢迎点一颗 Star。无界面训练与记录见 [PR #3](https://github.com/digitoil/RockXQlib/pull/3)（`docs/QLIB_RESEARCH.md`）。

A Qlib-based research workbench: visual node workflows, and headless experiment runs. The repo is on [GitHub](https://github.com/digitoil/RockXQlib); a star is welcome if it is useful. Headless training and records: [PR #3](https://github.com/digitoil/RockXQlib/pull/3) (`docs/QLIB_RESEARCH.md`).

## 🚀 系统概述

RockXQlib 是一个基于 Qlib 的高级量化分析系统，提供了完整的节点化工作流、可视化分析、实验管理和插件扩展功能。系统采用NodeGraphQt原生方法实现拖拽节点创建、节点树工具箱等核心功能。

## ✨ 核心特性

### 🎯 统一节点管理系统（已优化）
- **15个精选节点**：去除重复功能，保留核心节点
- **6个节点类别**：Qlib核心、AI功能、可视化、Kronos模型、核心集成、兼容节点
- **动态节点注册**：支持插件化扩展和自定义节点
- **功能去重优化**：消除重复节点，提升用户体验

### 🖥️ 原生GUI界面
- **NodeGraphQt原生拖拽**：支持从节点树拖拽到画布创建节点
- **属性编辑器**：实时编辑节点属性和参数
- **工作流画布**：可视化构建和编辑量化分析工作流
- **工具栏和菜单**：完整的操作界面

### 🤖 AI功能集成
- **LLM分析节点**：支持本地和云端LLM模型
- **知识库查询**：向量数据库集成
- **智能分析**：结合LLM和知识库的智能分析
- **Ollama集成**：本地模型接口

### 📊 可视化工具
- **K线图查看器**：专业的K线图可视化
- **回测可视化**：回测结果图表展示
- **图表引擎**：多种图表类型支持
- **仪表板**：综合分析仪表板

### 🕰️ Kronos模型集成
- **K线预测**：基于Kronos金融K线大模型
- **量化分析**：趋势、波动率、动量、风险分析
- **策略生成**：基于预测结果的交易策略

## 🏗️ 系统架构

### 核心组件
```
RockXQlib/
├── core/                          # 核心框架
│   ├── qlib_core_integration.py   # Qlib核心集成
│   ├── unified_node_manager.py    # 统一节点管理
│   ├── config_manager.py          # 配置管理
│   └── qlib_base_node.py          # 基础节点类
├── nodes/                         # 节点实现
│   ├── qlib_core_nodes.py         # Qlib核心节点
│   ├── data_nodes.py              # 数据节点
│   ├── model_nodes.py             # 模型节点
│   ├── strategy_nodes.py          # 策略节点
│   ├── backtest_nodes.py          # 回测节点
│   ├── ai_nodes.py                # AI功能节点
│   ├── visualization_nodes.py     # 可视化节点
│   └── kronos_nodes.py            # Kronos模型节点
├── config/                        # 配置文件
│   └── node_fusion_config.yaml    # 节点系统配置
├── launch_gui_complete_integration.py  # 主GUI程序
└── start_rockxqlib.bat            # 启动脚本
```

### 节点系统（已优化）
- **Qlib核心节点** (6个)：基于Qlib核心API的节点
- **AI功能** (4个)：AI和LLM模型节点
- **可视化** (4个)：可视化工具节点
- **Kronos模型** (3个)：Kronos金融模型节点
- **核心集成** (5个)：系统集成功能节点
- **兼容节点** (3个)：特殊功能兼容节点（自定义数据、LSTM模型、TopK策略等）

**优化说明**：已去除重复的数据、模型、策略、回测节点，统一使用Qlib核心节点，保留必要的特殊功能节点。

## 🚀 快速开始

### Windows用户
双击运行 `start_rockxqlib.bat` 或在命令行中执行：
```cmd
start_rockxqlib.bat
```

### Linux/Mac用户
在终端中执行：
```bash
chmod +x start_rockxqlib.sh
./start_rockxqlib.sh
```

### 手动启动
```bash
python launch_gui_complete_integration.py
```

## 🎮 使用指南

### 基本操作
1. **添加节点**：从左侧节点树拖拽节点到画布
2. **连接节点**：拖拽输出端口到输入端口创建连接
3. **编辑属性**：选择节点后在右侧属性编辑器中修改参数
4. **运行工作流**：点击"运行工作流"按钮执行整个工作流
5. **保存工作流**：点击"保存工作流"按钮保存当前工作流

### 节点类别说明

#### 📊 Qlib核心节点
- **QlibInitNode**：Qlib初始化节点
- **QlibDataNode**：数据获取节点
- **QlibDatasetNode**：数据集节点
- **QlibModelNode**：模型节点
- **QlibStrategyNode**：策略节点
- **QlibBacktestNode**：回测节点

#### 🤖 AI功能节点
- **QlibLLMNode**：LLM分析节点
- **QlibKnowledgeBaseNode**：知识库查询节点
- **QlibSmartAnalysisNode**：智能分析节点
- **QlibOllamaNode**：Ollama本地模型节点

#### 📊 可视化节点
- **QlibKlineViewerNode**：K线图查看器
- **QlibBacktestVisualizerNode**：回测可视化节点
- **QlibChartEngineNode**：图表引擎节点
- **QlibDashboardNode**：仪表板节点

#### 🕰️ Kronos模型节点
- **KronosKlinePredictorNode**：K线预测节点
- **KronosQuantitativeAnalysisNode**：量化分析节点
- **KronosStrategyNode**：策略节点

## 🔧 系统要求

### 环境要求
- **Python**: 3.8+
- **内存**: 8GB+ 推荐
- **存储**: 10GB+ 可用空间
- **操作系统**: Windows, macOS, Linux

### 依赖包
```bash
pip install PySide6 NodeGraphQt qlib pandas numpy scipy scikit-learn lightgbm matplotlib seaborn
```

## 📚 技术实现

### NodeGraphQt原生方法
系统严格使用NodeGraphQt的原生方法实现所有GUI功能：

1. **节点树创建**：
   ```python
   self.node_tree = NodesTreeWidget(node_graph=self.graph)
   ```

2. **属性编辑器创建**：
   ```python
   self.property_editor = PropertiesBinWidget(node_graph=self.graph)
   ```

3. **节点注册**：
   ```python
   self.graph.register_node(node_class)
   ```

4. **分类标签设置**：
   ```python
   self.node_tree.set_category_label(identifier, category)
   ```

### 统一节点管理
- **配置驱动**：通过YAML配置文件管理节点系统
- **动态加载**：支持动态加载和注册节点
- **错误处理**：完善的异常处理和日志记录
- **模块化设计**：清晰的模块分离和接口定义

## 🎯 工作流示例

### 基本量化分析工作流
1. **QlibInitNode** → 初始化Qlib
2. **QlibDataNode** → 获取市场数据
3. **QlibFeatureNode** → 特征工程
4. **QlibModelNode** → 模型训练
5. **QlibStrategyNode** → 策略生成
6. **QlibBacktestNode** → 回测分析
7. **QlibVisualizationNode** → 结果可视化

### AI增强工作流
1. **QlibDataNode** → 获取数据
2. **QlibLLMNode** → LLM分析
3. **QlibKnowledgeBaseNode** → 知识库查询
4. **QlibSmartAnalysisNode** → 智能分析
5. **KronosKlinePredictorNode** → K线预测
6. **QlibBacktestNode** → 回测验证

## 🆘 故障排除

### 常见问题
1. **PySide6导入失败**：安装PySide6 `pip install PySide6`
2. **NodeGraphQt导入失败**：安装NodeGraphQt `pip install NodeGraphQt`
3. **节点无法拖拽**：确保从节点树拖拽到画布区域
4. **工作流无法运行**：检查节点连接是否正确

### 系统状态检查
运行测试脚本检查系统状态：
```bash
python test_unified_system_simple.py
```

## 📈 系统优势

### 1. 完整性
- 覆盖了量化分析的全流程
- 从数据获取到结果可视化的完整支持
- 支持多种分析场景

### 2. 可扩展性
- 插件化架构，支持自定义节点
- 模块化设计，便于功能扩展
- 标准化的接口，便于集成

### 3. 易用性
- 图形化界面支持
- 丰富的模板和示例
- 详细的文档和帮助

### 4. 性能
- 智能缓存机制
- 并行执行支持
- 内存优化设计

### 5. 专业性
- 基于Qlib的专业量化分析框架
- 支持多种机器学习模型
- 完整的回测和分析功能

## 🎉 开始使用

现在您已经了解了RockXQlib的基本使用方法，可以开始构建您的量化分析工作流了！

**祝您使用愉快！** 🚀

---

## 📞 技术支持

如有问题或建议，请查看系统日志了解详细错误信息，或参考相关文档和示例代码。

## 📄 许可证

本项目基于MIT许可证开源。

## 流水线开发
见 [docs/PIPELINE.md](docs/PIPELINE.md)：模板库、AI 生成、运行记录、命令行批量与 CI。
