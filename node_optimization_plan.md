# 节点功能重复优化方案

## 问题分析

当前系统存在以下节点功能重复：

### 1. 回测节点重复
- **Qlib核心**: `QlibBacktestNode` - 基于Qlib核心API，功能完整
- **现有节点**: `QlibBacktestNode` + `QlibSimulatorNode` - 功能分散

### 2. 策略节点重复
- **Qlib核心**: `QlibStrategyNode` - 统一策略接口，支持所有Qlib策略
- **现有节点**: `QlibSignalNode`, `QlibTopKNode`, `QlibLongShortNode`, `QlibPortfolioNode`, `QlibRiskNode`, `QlibRebalanceNode` - 功能分散

### 3. 数据节点重复
- **Qlib核心**: `QlibDataNode` - 统一数据接口，支持所有Qlib数据源
- **现有节点**: `RockXQlibDataNode`, `RockXQlibAlphaNode`, `RockXQlibHighFreqNode`, `RockXQlibCustomDataNode` - 功能分散

### 4. 模型节点重复
- **Qlib核心**: `QlibModelNode` - 统一模型接口，支持所有Qlib模型
- **现有节点**: `QlibLinearNode`, `QlibTreeNode`, `QlibLSTMNode`, `QlibGRUNode`, `QlibTransformerNode`, `QlibCNNNode`, `QlibRLNode`, `QlibDQNNode`, `QlibPPONode` - 功能分散

## 优化方案

### 方案1：保留Qlib核心节点，移除重复的现有节点
**优点**：
- 基于Qlib核心API，功能更完整
- 代码更简洁，维护成本低
- 统一的接口设计

**缺点**：
- 失去了一些特定功能的节点

### 方案2：保留现有节点，移除Qlib核心节点
**优点**：
- 保留所有现有功能
- 节点功能更细分

**缺点**：
- 代码冗余，维护成本高
- 功能重复，用户困惑

### 方案3：合并优化（推荐）
**优点**：
- 保留核心功能
- 减少重复
- 提供更好的用户体验

## 推荐实施方案

### 1. 数据节点优化
- **保留**: `QlibDataNode` (Qlib核心) - 作为主要数据节点
- **保留**: `RockXQlibCustomDataNode` - 用于自定义数据源
- **移除**: `RockXQlibDataNode`, `RockXQlibAlphaNode`, `RockXQlibHighFreqNode`

### 2. 模型节点优化
- **保留**: `QlibModelNode` (Qlib核心) - 作为主要模型节点
- **保留**: `QlibLSTMNode`, `QlibTransformerNode` - 用于特殊深度学习模型
- **移除**: `QlibLinearNode`, `QlibTreeNode`, `QlibGRUNode`, `QlibCNNNode`, `QlibRLNode`, `QlibDQNNode`, `QlibPPONode`

### 3. 策略节点优化
- **保留**: `QlibStrategyNode` (Qlib核心) - 作为主要策略节点
- **保留**: `QlibTopKNode`, `QlibLongShortNode` - 用于常用策略
- **移除**: `QlibSignalNode`, `QlibPortfolioNode`, `QlibRiskNode`, `QlibRebalanceNode`

### 4. 回测节点优化
- **保留**: `QlibBacktestNode` (Qlib核心) - 作为主要回测节点
- **保留**: `QlibSimulatorNode` - 用于模拟交易
- **移除**: 重复的 `QlibBacktestNode`

## 实施步骤

1. **更新配置文件** - 禁用重复的节点系统
2. **更新统一节点管理器** - 移除重复节点的加载
3. **测试验证** - 确保保留的节点功能正常
4. **更新文档** - 更新节点使用说明

## 预期效果

- 节点数量从24个减少到约15个
- 消除功能重复
- 提高用户体验
- 降低维护成本
