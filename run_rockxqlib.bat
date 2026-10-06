@echo off
echo 🚀 启动RockXQlib系统...

REM 设置环境变量
set SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8.dev6
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB=0.9.8.dev6
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_QLIB=0.9.0

REM 设置Python路径
set PYTHONPATH=%CD%;%CD%\qlib;%CD%\core;%CD%\nodes;%PYTHONPATH%

REM 设置qlib相关环境变量
set QLIB_DATA_PATH=%USERPROFILE%\.qlib\qlib_data\cn_data
set QLIB_LOG_LEVEL=INFO

echo ✅ 环境变量设置完成
echo 📁 数据路径: %QLIB_DATA_PATH%

REM 运行qlib环境设置脚本
echo 🔧 设置qlib环境...
python setup_qlib_environment.py

REM 运行主程序
echo 🚀 启动RockXQlib GUI...
python launch_gui_complete_integration.py

pause
