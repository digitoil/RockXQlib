# RockXQlib 快速开始指南

## 🚀 快速启动

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
python launch_gui_simple_nodegraphqt.py
```

## 🎯 界面说明

### 左侧节点工具箱
包含31个专业节点，分为4个类别：

#### 📊 数据节点 (9个)
- **QlibAlphaNode** - Alpha因子数据
- **QlibHighFreqNode** - 高频数据
- **QlibCustomDataNode** - 自定义数据
- **QlibProcessorNode** - 数据处理器
- **QlibFeatureNode** - 特征工程
- **QlibNormalizeNode** - 数据标准化
- **QlibFilterNode** - 数据过滤
- **QlibCacheNode** - 数据缓存
- **QlibStorageNode** - 数据存储

#### 🤖 模型节点 (10个)
- **QlibLinearNode** - 线性模型
- **QlibTreeNode** - 树模型
- **QlibEnsembleNode** - 集成模型
- **QlibLSTMNode** - LSTM模型
- **QlibGRUNode** - GRU模型
- **QlibTransformerNode** - Transformer模型
- **QlibCNNNode** - CNN模型
- **QlibRLNode** - 强化学习模型
- **QlibDQNNode** - DQN模型
- **QlibPPONode** - PPO模型

#### 📈 策略节点 (6个)
- **QlibSignalNode** - 信号生成
- **QlibTopKNode** - TopK策略
- **QlibLongShortNode** - 多空策略
- **QlibPortfolioNode** - 投资组合
- **QlibRiskNode** - 风险管理
- **QlibRebalanceNode** - 再平衡

#### 📊 回测节点 (6个)
- **QlibBacktestNode** - 回测引擎
- **QlibSimulatorNode** - 模拟器
- **QlibRealTimeNode** - 实时交易
- **QlibAnalysisNode** - 结果分析
- **QlibReportNode** - 报告生成
- **QlibVisualizationNode** - 结果可视化

### 中央工作流画布
- 拖拽节点到画布构建工作流
- 连接节点：拖拽输出端口到输入端口
- 右键节点查看菜单
- 双击节点执行单个节点

### 右侧属性编辑器
- 选择节点查看和编辑属性
- 配置节点参数
- 查看节点状态和端口信息

## 🎮 操作指南

### 基本操作
1. **添加节点**: 从左侧节点树拖拽节点到画布 (✅ 已实现)
2. **移动节点**: 在画布上直接拖拽节点调整位置 (✅ 已实现)
3. **编辑属性**: 选择节点后在右侧属性编辑器中修改参数 (✅ 已实现)
4. **执行节点**: 双击节点执行单个节点
5. **运行工作流**: 点击"运行工作流"按钮执行整个工作流 (✅ 已实现)

### 高级操作
1. **保存工作流**: 点击"保存工作流"按钮保存当前工作流
2. **清空画布**: 点击"清空画布"按钮清除所有节点
3. **节点复制**: 右键节点选择复制
4. **节点删除**: 右键节点选择删除

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

## 📚 更多资源

### 文档
- `USAGE_EXAMPLES.md` - 详细使用示例
- `INSTALLATION_GUIDE.md` - 安装和配置指南
- `FINAL_SYSTEM_STATUS.md` - 系统状态报告

### 测试
- `test_system_core.py` - 核心系统测试
- `test_gui_simple.py` - GUI功能测试
- `test_ai_simple.py` - AI集成测试

### 示例工作流
1. **数据获取** → **特征工程** → **模型训练** → **策略生成** → **回测分析**
2. **Alpha因子** → **数据标准化** → **线性模型** → **TopK策略** → **回测引擎**
3. **高频数据** → **特征工程** → **LSTM模型** → **风险管理** → **结果可视化**

## 🆘 故障排除

### 常见问题
1. **PySide6导入失败**: 安装PySide6 `pip install PySide6`
2. **NodeGraphQt导入失败**: 安装NodeGraphQt `pip install NodeGraphQt`
3. **节点无法拖拽**: 确保从节点树拖拽到画布区域
4. **工作流无法运行**: 检查节点连接是否正确

### 获取帮助
- 查看系统日志了解详细错误信息
- 检查依赖包是否正确安装
- 参考文档和示例代码

## 🎉 开始使用

现在您已经了解了RockXQlib的基本使用方法，可以开始构建您的量化分析工作流了！

**祝您使用愉快！** 🚀
