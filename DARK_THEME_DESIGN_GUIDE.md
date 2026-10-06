# RockXAIStudio 深色主题设计指南

## 🎨 设计概述

本指南详细介绍了RockXAIStudio v2.1的深色主题设计，完全匹配您展示的界面风格。该主题采用现代化的深色配色方案，提供专业的AI工作流建模体验。

## 🌈 配色方案

### 主要颜色定义

#### 背景色系
- **主背景**: `#1a1a1a` - 接近黑色的深色背景
- **次背景**: `#2c2c2c` - 深灰色，用于面板和容器
- **第三级背景**: `#3a3a3a` - 稍亮的灰色，用于输入框等
- **面板背景**: `#2a2a2a` - 侧边栏面板背景
- **悬停背景**: `#404040` - 鼠标悬停时的背景色

#### 文本色系
- **主文本**: `#ffffff` - 白色，用于主要文本内容
- **次文本**: `#e0e0e0` - 浅灰色，用于次要文本
- **弱化文本**: `#b0b0b0` - 中灰色，用于提示文本
- **禁用文本**: `#808080` - 深灰色，用于禁用状态

#### 边框色系
- **主边框**: `#4a4a4a` - 主要边框颜色
- **次边框**: `#3a3a3a` - 次要边框颜色
- **选中边框**: `#e0e0e0` - 选中状态的浅灰色边框

#### 强调色系
- **蓝色强调**: `#3498db` - 用于选中项和交互元素
- **蓝色悬停**: `#2980b9` - 蓝色悬停状态
- **绿色强调**: `#27ae60` - 用于执行按钮等积极操作
- **绿色悬停**: `#229954` - 绿色悬停状态
- **橙色强调**: `#f39c12` - 用于连接线和警告
- **红色强调**: `#e74c3c` - 用于错误和删除操作

## 🏗️ 界面组件样式

### 1. 主窗口样式
```css
QMainWindow {
    background-color: #1a1a1a;
    color: #ffffff;
}
```

### 2. 菜单栏样式
- 背景色: `#2c2c2c`
- 文本色: `#ffffff`
- 悬停色: `#3498db`
- 边框: 底部1px实线 `#4a4a4a`

### 3. 工具栏样式
- 背景色: `#2c2c2c`
- 按钮背景: `#3a3a3a`
- 按钮悬停: `#3498db`
- 执行按钮: `#27ae60` (绿色)

### 4. 侧边栏样式

#### 左侧工具箱
- 背景色: `#2a2a2a`
- 标题背景: `#2c2c2c`
- 树形控件背景: `#2a2a2a`
- 选中项背景: `#3498db`

#### 右侧属性编辑器
- 背景色: `#2a2a2a`
- 输入框背景: `#3a3a3a`
- 复选框选中: `#3498db`
- 下拉框背景: `#3a3a3a`

### 5. 画布区域样式
- 背景色: `#1a1a1a` (主背景)
- 网格色: `#404040` (深灰色网格)
- 占位符边框: 2px虚线 `#4a4a4a`

### 6. 节点样式

#### 基础节点
- 背景色: `#2c2c2c`
- 边框色: `#4a4a4a`
- 文本色: `#ffffff`
- 选中边框: `#e0e0e0`

#### 分类节点颜色
- **Qlib核心节点**: 深蓝灰色 `#34495e`
- **AI功能节点**: 深绿色 `#2e7d32`
- **可视化节点**: 紫色 `#9c27b0`
- **Kronos模型节点**: 橙色 `#ff5722`
- **核心集成节点**: 靛蓝色 `#3f51b5`
- **工作流控制节点**: 蓝灰色 `#607d8b`

### 7. 连接线样式
- 默认连接: 橙色 `#f39c12`
- 数据连接: 橙色 `#f39c12`
- 控制连接: 紫色 `#9b59b6`
- 连接线宽度: 2px

## 📁 文件结构

```
RockXQlib/
├── dark_theme_styles.py          # 深色主题样式定义
├── node_styles_config.py         # 节点样式配置
├── demo_dark_theme.py            # 深色主题演示
├── launch_gui_complete_integration.py  # 主程序（已更新）
└── DARK_THEME_DESIGN_GUIDE.md    # 本设计指南
```

## 🚀 使用方法

### 1. 基本使用
```python
from dark_theme_styles import DarkThemeStyles

# 应用完整深色主题
window.setStyleSheet(DarkThemeStyles.get_complete_style())
```

### 2. 组件特定样式
```python
# 应用侧边栏样式
sidebar.setStyleSheet(DarkThemeStyles.get_left_sidebar_style())

# 应用工具栏样式
toolbar.setStyleSheet(DarkThemeStyles.get_toolbar_style())

# 应用画布样式
canvas.setStyleSheet(DarkThemeStyles.get_canvas_style())
```

### 3. 节点样式配置
```python
from node_styles_config import NodeStylesConfig

# 设置图形样式
NodeStylesConfig.setup_graph_styles(graph)

# 应用节点样式
NodeStylesConfig.apply_node_style(node, 'qlib_core')
```

## 🎯 设计特点

### 1. 视觉层次
- 使用不同深度的灰色创建清晰的视觉层次
- 通过颜色对比突出重要元素
- 保持整体色调的一致性

### 2. 交互反馈
- 悬停状态使用蓝色强调
- 选中状态使用浅灰色边框
- 执行操作使用绿色强调

### 3. 可读性
- 高对比度的文本颜色确保可读性
- 合理的字体大小和间距
- 清晰的图标和符号

### 4. 专业性
- 深色主题减少眼部疲劳
- 现代化的设计语言
- 符合AI/ML工具的专业形象

## 🔧 自定义配置

### 修改颜色
在 `dark_theme_styles.py` 中的 `COLORS` 字典中修改颜色值：

```python
COLORS = {
    'bg_primary': '#1a1a1a',        # 修改主背景色
    'accent_blue': '#3498db',       # 修改强调色
    # ... 其他颜色
}
```

### 添加新组件样式
在 `DarkThemeStyles` 类中添加新的样式方法：

```python
@classmethod
def get_custom_component_style(cls):
    """自定义组件样式"""
    return f"""
    QCustomWidget {{
        background-color: {cls.COLORS['bg_secondary']};
        color: {cls.COLORS['text_primary']};
    }}
    """
```

## 📱 响应式设计

主题支持不同窗口大小的响应式布局：
- 侧边栏宽度自适应
- 画布区域自动调整
- 工具栏按钮大小适配

## 🎨 演示运行

运行演示程序查看完整效果：

```bash
cd RockXQlib
python demo_dark_theme.py
```

演示程序展示了：
- 完整的深色主题界面
- 所有组件的样式效果
- 节点分类和属性编辑
- 菜单栏和工具栏样式

## 📝 注意事项

1. **兼容性**: 确保PySide6版本兼容
2. **性能**: 大量节点时注意样式渲染性能
3. **自定义**: 修改样式后需要重新应用
4. **测试**: 在不同操作系统上测试显示效果

## 🔄 更新日志

- **v1.0**: 初始深色主题设计
- **v1.1**: 添加节点分类颜色
- **v1.2**: 优化交互反馈效果
- **v1.3**: 完善响应式布局

---

*本设计指南将随着界面更新持续维护和完善。*
