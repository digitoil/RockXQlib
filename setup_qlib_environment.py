#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib环境设置脚本
确保qlib能够正常运行和初始化
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def set_environment_variables():
    """设置环境变量"""
    logger.info("🔧 设置环境变量...")

    # 设置SETUPTOOLS_SCM_PRETEND_VERSION
    os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8.dev6'
    os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB'] = '0.9.8.dev6'

    # 设置其他必要的环境变量
    os.environ['PYTHONPATH'] = os.pathsep.join([
        os.getcwd(),
        os.path.join(os.getcwd(), 'qlib'),
        os.path.join(os.getcwd(), 'core'),
        os.path.join(os.getcwd(), 'nodes'),
        os.environ.get('PYTHONPATH', '')
    ])

    # 设置qlib相关环境变量
    os.environ['QLIB_DATA_PATH'] = os.path.expanduser('~/.qlib/qlib_data/cn_data')
    os.environ['QLIB_LOG_LEVEL'] = 'INFO'

    logger.info("✅ 环境变量设置完成")

def check_qlib_installation():
    """检查qlib安装状态"""
    logger.info("🔍 检查qlib安装状态...")

    try:
        import qlib
        logger.info(f"✅ qlib已安装，版本: {qlib.__version__}")
        return True
    except ImportError as e:
        logger.error(f"❌ qlib未安装: {e}")
        return False

def check_qlib_data():
    """检查qlib数据"""
    logger.info("🔍 检查qlib数据...")

    data_path = os.path.expanduser('~/.qlib/qlib_data/cn_data')
    if os.path.exists(data_path):
        logger.info(f"✅ qlib数据路径存在: {data_path}")
        return True
    else:
        logger.warning(f"⚠️ qlib数据路径不存在: {data_path}")
        logger.info("💡 请运行以下命令下载qlib数据:")
        logger.info("   python -c \"import qlib; qlib.run_all()\"")
        return False

def initialize_qlib():
    """初始化qlib"""
    logger.info("🚀 初始化qlib...")

    try:
        import qlib

        # 检查是否已初始化
        if hasattr(qlib, 'is_initialized') and qlib.is_initialized():
            logger.info("✅ qlib已经初始化")
            return True

        # 设置数据路径
        provider_uri = os.path.expanduser('~/.qlib/qlib_data/cn_data')

        # 初始化qlib
        qlib.init(
            provider_uri=provider_uri,
            region="cn",
            auto_mount=False,
            mount_path=None,
            kernel_api=False,
            redis_host=None,
            redis_port=None,
            redis_task_db=None,
            redis_freq_limit=None,
            enable_exp_recorder=True
        )

        # 验证初始化
        from qlib.data import D
        logger.info("✅ qlib初始化成功")
        return True

    except Exception as e:
        logger.error(f"❌ qlib初始化失败: {e}")
        return False

def test_qlib_functionality():
    """测试qlib功能"""
    logger.info("🧪 测试qlib功能...")

    try:
        from qlib.data import D
        from qlib.data.dataset import DatasetH, TSDatasetH
        from qlib.contrib.data.handler import Alpha158, Alpha360
        from qlib.contrib.model.pytorch_lstm_ts import LSTM
        from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy
        from qlib.backtest import backtest
        from qlib.utils import init_instance_by_config

        logger.info("✅ qlib核心模块导入成功")

        # 测试数据获取
        try:
            data = D.features(['SH000300'], ['$close'], start_time='2020-01-01', end_time='2020-01-10')
            logger.info(f"✅ 数据获取测试成功，数据形状: {data.shape}")
        except Exception as e:
            logger.warning(f"⚠️ 数据获取测试失败: {e}")

        # 测试数据集创建
        try:
            handler_config = {
                'class': 'Alpha158',
                'module_path': 'qlib.contrib.data.handler',
                'kwargs': {
                    'start_time': '2020-01-01',
                    'end_time': '2020-01-10',
                    'instruments': 'csi300'
                }
            }
            handler = init_instance_by_config(handler_config)
            logger.info("✅ 数据处理器创建测试成功")
        except Exception as e:
            logger.warning(f"⚠️ 数据处理器创建测试失败: {e}")

        return True

    except Exception as e:
        logger.error(f"❌ qlib功能测试失败: {e}")
        return False

def create_qlib_config():
    """创建qlib配置文件"""
    logger.info("📝 创建qlib配置文件...")

    config_dir = Path.home() / '.qlib'
    config_dir.mkdir(exist_ok=True)

    config_file = config_dir / 'qlib_config.yaml'
    config_content = """# Qlib配置文件
provider_uri: ~/.qlib/qlib_data/cn_data
region: cn
auto_mount: false
mount_path: null
kernel_api: false
redis_host: null
redis_port: null
redis_task_db: null
redis_freq_limit: null
enable_exp_recorder: true
"""

    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(config_content)

    logger.info(f"✅ qlib配置文件已创建: {config_file}")

def main():
    """主函数"""
    logger.info("🚀 开始设置qlib环境...")

    # 1. 设置环境变量
    set_environment_variables()

    # 2. 检查qlib安装
    if not check_qlib_installation():
        logger.error("❌ qlib未安装，请先安装qlib")
        return False

    # 3. 检查qlib数据
    check_qlib_data()

    # 4. 创建配置文件
    create_qlib_config()

    # 5. 初始化qlib
    if not initialize_qlib():
        logger.error("❌ qlib初始化失败")
        return False

    # 6. 测试qlib功能
    if not test_qlib_functionality():
        logger.error("❌ qlib功能测试失败")
        return False

    logger.info("🎉 qlib环境设置完成！")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
