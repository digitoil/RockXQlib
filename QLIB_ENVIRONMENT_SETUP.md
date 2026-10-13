# Qlib环境设置指南

本指南将帮助您正确设置qlib环境，确保RockXQlib系统能够正常运行。

## 🚀 快速启动

### 方法1：使用批处理脚本（推荐）
```bash
# Windows
run_rockxqlib.bat
```

### 方法2：使用PowerShell脚本
```powershell
# Windows PowerShell
.\run_rockxqlib.ps1
```

### 方法3：手动设置环境变量
```bash
# 设置环境变量
set SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8.dev6
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB=0.9.8.dev6
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_QLIB=0.9.0

# 运行环境设置脚本
python setup_qlib_environment.py

# 运行主程序
python launch_gui_complete_integration.py
```

## 🔧 环境设置脚本

### 1. setup_qlib_environment.py
完整的qlib环境设置脚本，包括：
- 设置环境变量
- 检查qlib安装状态
- 检查qlib数据
- 初始化qlib
- 测试qlib功能

### 2. test_qlib_environment.py
快速测试脚本，验证qlib环境是否正常：
- 测试qlib导入
- 测试qlib初始化
- 测试数据访问
- 测试组件创建

## 📁 环境变量说明

| 变量名 | 值 | 说明 |
|--------|-----|------|
| SETUPTOOLS_SCM_PRETEND_VERSION | 0.9.8.dev6 | 设置setuptools版本 |
| SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB | 0.9.8.dev6 | RockXQlib专用版本 |
| SETUPTOOLS_SCM_PRETEND_VERSION_FOR_QLIB | 0.9.0 | Qlib专用版本 |
| QLIB_DATA_PATH | ~/.qlib/qlib_data/cn_data | qlib数据路径 |
| QLIB_LOG_LEVEL | INFO | qlib日志级别 |

## 🗂️ 目录结构

```
RockXQlib/
├── setup_qlib_environment.py    # qlib环境设置脚本
├── test_qlib_environment.py     # qlib环境测试脚本
├── run_rockxqlib.bat           # Windows批处理启动脚本
├── run_rockxqlib.ps1           # PowerShell启动脚本
├── launch_gui_complete_integration.py  # 主程序
└── QLIB_ENVIRONMENT_SETUP.md   # 本文件
```

## 🛠️ 故障排除

### 1. qlib未安装
```bash
pip install qlib
```

### 2. qlib数据未下载

官方日频 A 股数据（Alpha158、仓库根目录的 LSTM workflow 需要它）：

```bash
python -m qlib.cli.data qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn
```

没有这份数据时，`python -m pipeline qrun workflows/lgb_alpha158.yaml` 会在训练开始前失败，不会写成功记录。

只想先跑通「训练 → recorder 里的预测 → 回测」时，不必下全市场。把 CSV 收成 qlib 目录再跑最小配置，见 [docs/QLIB_RESEARCH.md](docs/QLIB_RESEARCH.md)。

### 3. 环境变量未设置
确保运行启动脚本前设置了正确的环境变量。

### 4. 权限问题
在Windows上，可能需要以管理员身份运行PowerShell脚本。

## 📊 测试环境

运行测试脚本验证环境：
```bash
python test_qlib_environment.py
```

如果测试通过，您应该看到：
- ✅ qlib导入成功
- ✅ qlib初始化成功
- ✅ 数据访问成功（如果数据已下载）
- ✅ 组件创建成功

## 🎯 下一步

环境设置完成后，您可以：
1. 运行主程序：`python launch_gui_complete_integration.py`
2. 使用GUI界面创建量化工作流
3. 运行LSTM模型和回测

## 📞 支持

如果遇到问题，请检查：
1. Python版本（推荐3.8+）
2. qlib版本（推荐最新版本）
3. 环境变量设置
4. 数据路径权限

---

**注意**：首次运行可能需要下载qlib数据，请确保网络连接正常。
