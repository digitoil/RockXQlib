# RockXQlib 安装和使用指南

## 系统要求

### 硬件要求
- **CPU**: 4核心以上推荐
- **内存**: 8GB以上推荐
- **存储**: 10GB以上可用空间
- **显卡**: 可选，用于深度学习模型加速

### 软件要求
- **操作系统**: Windows 10/11, macOS 10.14+, Ubuntu 18.04+
- **Python**: 3.8或更高版本
- **Git**: 用于版本控制

## 安装步骤

### 1. 环境准备

#### 创建虚拟环境（推荐）
```bash
# 使用conda
conda create -n rockxqlib python=3.8
conda activate rockxqlib

# 或使用venv
python -m venv rockxqlib_env
source rockxqlib_env/bin/activate  # Linux/macOS
# 或
rockxqlib_env\Scripts\activate  # Windows
```

#### 设置环境变量
```bash
# Windows (PowerShell)
$env:SETUPTOOLS_SCM_PRETEND_VERSION="1.0.0"
$env:SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB="1.0.0"

# Linux/macOS
export SETUPTOOLS_SCM_PRETEND_VERSION="1.0.0"
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB="1.0.0"
```

### 2. 安装依赖

#### 基础依赖
```bash
# 安装Qlib
pip install qlib

# 安装数据处理库
pip install pandas numpy scipy

# 安装机器学习库
pip install scikit-learn lightgbm xgboost catboost

# 安装深度学习库（可选）
pip install torch torchvision
pip install tensorflow

# 安装可视化库
pip install matplotlib seaborn plotly

# 安装其他依赖
pip install pyyaml tqdm
```

#### 图形界面依赖（可选）
```bash
# 安装Qt相关库
pip install PySide6

# 安装NodeGraphQt
pip install NodeGraphQt
```

#### 完整安装命令
```bash
# 一键安装所有依赖
pip install qlib pandas numpy scipy scikit-learn lightgbm xgboost catboost matplotlib seaborn plotly pyyaml tqdm PySide6 NodeGraphQt
```

### 3. 下载和安装RockXQlib

#### 方法1：直接使用（推荐）
```bash
# 克隆或下载项目到本地
git clone <repository_url>
cd RockXQlib

# 设置Python路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 或使用sys.path
python -c "import sys; sys.path.append('.')"
```

#### 方法2：安装为包
```bash
# 在项目根目录下
pip install -e .
```

### 4. 验证安装

#### 运行测试脚本
```bash
# 基础功能测试
python test_simple_final.py

# 完整系统测试
python test_complete_system_final.py
```

#### 检查导入
```python
# 测试核心模块导入
python -c "
import os
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '1.0.0'
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB'] = '1.0.0'

from core.qlib_base_node import QlibBaseNode
from core.qlib_workflow import QlibWorkflow
from core.qlib_core_integration import QlibCoreIntegration
print('✅ 所有核心模块导入成功')
"
```

## 快速开始

### 1. 基本使用

#### 创建工作流
```python
from core.qlib_workflow import QlibWorkflow
from nodes.data_nodes import QlibAlphaNode
from nodes.model_nodes import QlibLinearNode

# 创建工作流
workflow = QlibWorkflow("我的第一个工作流")

# 添加节点
alpha_node = QlibAlphaNode()
model_node = QlibLinearNode()

alpha_id = workflow.add_node(alpha_node)
model_id = workflow.add_node(model_node)

# 连接节点
workflow.connect_nodes(alpha_id, model_id, "alpha_data", "train_data")

# 验证和执行
if workflow.validate_workflow():
    print("工作流验证通过")
```

#### 运行实验
```python
from core.qlib_experiment_manager import QlibExperimentManager

# 创建实验管理器
exp_manager = QlibExperimentManager("./experiments")

# 创建实验
experiment_id = exp_manager.create_experiment("测试实验")
run_id = exp_manager.start_run(experiment_id)

# 记录结果
exp_manager.log_metrics(run_id, {"accuracy": 0.95})
exp_manager.end_run(run_id)
```

### 2. 图形界面使用

#### 启动图形界面
```bash
# 运行图形界面
python run_gui.py
```

#### 图形界面功能
- 拖拽创建节点
- 连接节点构建工作流
- 编辑节点属性
- 执行工作流
- 查看结果

### 3. 命令行使用

#### 运行工作流
```bash
# 启动 GUI（推荐方式）
python launch_gui_complete_integration.py

# 运行实验管理
python -m core.qlib_experiment_manager experiment_config.yaml
```

## 配置说明

### 1. 系统配置

#### 创建配置文件
```yaml
# config.yaml
system:
  data_path: "./data"
  cache_path: "./cache"
  log_level: "INFO"
  max_workers: 4

qlib:
  provider_uri: "~/.qlib/qlib_data/cn_data"
  region: "cn"
  market: "csi300"

visualization:
  figure_size: [12, 8]
  dpi: 100
  style: "seaborn"
```

#### 加载配置
```python
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 使用配置
print(f"数据路径: {config['system']['data_path']}")
```

### 2. 节点配置

#### 节点属性配置
```python
# 设置节点属性
alpha_node = QlibAlphaNode()
alpha_node.set_rockx_property("instruments", "csi300")
alpha_node.set_rockx_property("start_date", "2020-01-01")
alpha_node.set_rockx_property("end_date", "2023-12-31")
```

#### 工作流配置
```yaml
# workflow.yaml
name: "量化分析工作流"
nodes:
  - type: "QlibAlphaNode"
    id: "alpha_1"
    properties:
      instruments: "csi300"
      start_date: "2020-01-01"
      end_date: "2023-12-31"
  - type: "QlibLinearNode"
    id: "model_1"
    properties:
      fit_intercept: true
      normalize: false

connections:
  - from: "alpha_1"
    to: "model_1"
    from_port: "alpha_data"
    to_port: "train_data"
```

## 常见问题

### 1. 安装问题

#### 问题：setuptools-scm错误
```
LookupError: setuptools-scm was unable to detect version
```

**解决方案**：
```bash
# 设置环境变量
export SETUPTOOLS_SCM_PRETEND_VERSION="1.0.0"
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB="1.0.0"
```

#### 问题：Qt相关错误
```
QWidget: Must construct a QGuiApplication before a QWidget
```

**解决方案**：
```bash
# 安装Qt依赖
pip install PySide6

# 或避免使用图形界面功能
# 只使用核心功能，不导入Qt相关模块
```

#### 问题：Qlib导入错误
```
ImportError: No module named 'qlib'
```

**解决方案**：
```bash
# 安装Qlib
pip install qlib

# 或使用conda
conda install -c conda-forge qlib
```

### 2. 运行问题

#### 问题：内存不足
```
MemoryError: Unable to allocate array
```

**解决方案**：
```python
# 启用缓存
cache_manager = QlibCacheManager("./cache", max_memory_usage=1024*1024*1024)

# 减少数据量
alpha_node.set_rockx_property("instruments", "csi100")  # 使用更小的股票池
```

#### 问题：节点执行失败
```
Node execution failed: No data provided
```

**解决方案**：
```python
# 检查输入数据
if inputs.get("data") is None:
    print("输入数据为空，请检查前置节点")

# 检查节点连接
workflow.validate_workflow()
```

### 3. 性能问题

#### 问题：执行速度慢
**解决方案**：
```python
# 启用并行执行
executor = QlibParallelExecutor(max_workers=4)

# 启用缓存
cache_manager = QlibCacheManager("./cache", enable_disk_cache=True)

# 优化工作流
workflow.optimize_execution()
```

## 开发指南

### 1. 添加新节点

```python
from core.qlib_base_node import QlibBaseNode

class MyCustomNode(QlibBaseNode):
    NODE_NAME = "My Custom Node"
    NODE_CATEGORY = "Custom"
    
    def __init__(self):
        super().__init__()
        # 定义输入输出端口
        self.add_input_port("input_data", "dataframe")
        self.add_output_port("output_data", "dataframe")
        
        # 定义属性
        self.add_rockx_property("param1", str, "default", "参数1", "参数1描述")
    
    def _execute_logic(self, inputs):
        # 实现节点逻辑
        input_data = inputs.get("input_data")
        # 处理数据
        output_data = input_data * 2  # 示例处理
        self.set_output("output_data", output_data)
        return True
```

### 2. 扩展新节点（推荐方式）

新增节点不需要写插件 —— 定义节点类，再在配置里登记即可。

```python
# 1) 定义节点（新契约：execute() 无参，数据走真实端口）
from NodeGraphQt import BaseNode

class MyCustomNode(BaseNode):
    __identifier__ = 'qlib.custom'   # 必须唯一，否则注册时互相覆盖
    NODE_NAME = '我的节点'

    def __init__(self):
        super().__init__()
        self.add_input('input_data')
        self.add_output('output_data')

    def execute(self) -> bool:
        data = self.get_input('input_data')
        self.set_output('output_data', data)
        return True
```

```yaml
# 2) 在 config/node_fusion_config.yaml 的 node_systems 里登记，
#    由 core/unified_node_manager.py 按需加载
```

> ⚠️ 两条契约：新式节点用 `execute(self)`（无参，数据走真实端口）；
> 旧式节点用 `execute(self, inputs)`（传字典）。一键运行的执行器
> （core/workflow_runner.py）会自动识别签名，两者可混在同一条链路里。
>
> 注：早期设计里的 `core/qlib_plugin_manager.py`（插件系统）与
> `core/qlib_execution_engine.py`（执行引擎）**从未接线**，代码中
> 无任何引用，已在核心精简中移除。

### 3. 自定义回测图表

回测结果面板已提供现成的绘图入口，直接复用即可。

```python
from gui.backtest_result_panel import (
    adapt_qlib_backtest_result,   # qlib 回测结果 -> 绘图数据
    build_dashboard_html,         # 多图合成单页（共享一份 plotly.js）
    build_equity_figure,
)

data = adapt_qlib_backtest_result(backtest_result)
fig = build_equity_figure(data)
html = build_dashboard_html({'equity': fig}, {'equity': '资金曲线'})
```

> 注：早期设计里的 `core/qlib_visualization_engine.py` **从未接线**，
> 已在核心精简中移除。现有可视化能力见 `gui/backtest_result_panel.py`
> 与 `visualization/` 目录。

## 部署指南

### 1. 生产环境部署

#### Docker部署
```dockerfile
# Dockerfile
FROM python:3.8-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY . .

# 安装Python依赖
RUN pip install -r requirements.txt

# 设置环境变量
ENV SETUPTOOLS_SCM_PRETEND_VERSION=1.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB=1.0.0

# 运行应用
CMD ["python", "run_gui.py"]
```

#### 构建和运行
```bash
# 构建镜像
docker build -t rockxqlib .

# 运行容器
docker run -p 8080:8080 rockxqlib
```

### 2. 云平台部署

#### AWS部署
```yaml
# cloudformation.yaml
Resources:
  RockXQlibInstance:
    Type: AWS::EC2::Instance
    Properties:
      ImageId: ami-0c55b159cbfafe1d0
      InstanceType: t3.large
      SecurityGroups:
        - !Ref SecurityGroup
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          yum update -y
          yum install -y python3 pip
          pip install qlib pandas numpy
          # 其他安装步骤
```

#### Azure部署
```yaml
# azure-pipelines.yml
trigger:
- main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.8'

- script: |
    pip install -r requirements.txt
    python test_simple_final.py
  displayName: 'Install dependencies and test'
```

## 维护和更新

### 1. 版本管理

#### 检查版本
```python
import rockxqlib
print(f"RockXQlib版本: {rockxqlib.__version__}")
```

#### 更新系统
```bash
# 更新依赖
pip install --upgrade qlib pandas numpy

# 更新代码
git pull origin main

# 重新安装
pip install -e .
```

### 2. 日志和监控

#### 配置日志
```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rockxqlib.log'),
        logging.StreamHandler()
    ]
)
```

#### 监控系统状态
```python
from core.unified_node_manager import UnifiedNodeManager
from core.config_manager import config_manager

# 当前启用的节点系统与已注册节点
print("启用的节点系统:", config_manager.get_enabled_node_systems())
manager = UnifiedNodeManager()
print("已注册节点数:", len(manager.registry.get_all_nodes()))
```

## 支持和帮助

### 1. 获取帮助

#### 查看文档
```bash
# 查看帮助
python -m core.qlib_workflow --help

# 查看节点列表
python -c "from nodes.data_nodes import *; print([cls.__name__ for cls in [QlibAlphaNode, QlibHighFreqNode]])"
```

#### 运行示例
```bash
# 运行示例工作流
python examples/basic_workflow.py

# 运行示例实验
python examples/basic_experiment.py
```

### 2. 报告问题

#### 收集信息
```python
# 收集系统信息
import sys
import platform

print(f"Python版本: {sys.version}")
print(f"操作系统: {platform.system()}")
print(f"架构: {platform.architecture()}")

# 收集错误信息
import traceback
try:
    # 你的代码
    pass
except Exception as e:
    traceback.print_exc()
```

#### 提交问题
1. 检查现有问题
2. 创建新问题
3. 提供详细信息
4. 附上错误日志

这个安装和使用指南提供了完整的RockXQlib系统安装、配置、使用和开发指导，帮助用户快速上手并充分利用系统功能。
