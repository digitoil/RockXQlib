# RockXQlib启动脚本
Write-Host "🚀 启动RockXQlib系统..." -ForegroundColor Green

# 设置环境变量
$env:SETUPTOOLS_SCM_PRETEND_VERSION = "0.9.8.dev6"
$env:SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ROCKXQLIB = "0.9.8.dev6"
$env:SETUPTOOLS_SCM_PRETEND_VERSION_FOR_QLIB = "0.9.0"

# 设置Python路径
$currentDir = Get-Location
$env:PYTHONPATH = "$currentDir;$currentDir\qlib;$currentDir\core;$currentDir\nodes;$env:PYTHONPATH"

# 设置qlib相关环境变量
$env:QLIB_DATA_PATH = "$env:USERPROFILE\.qlib\qlib_data\cn_data"
$env:QLIB_LOG_LEVEL = "INFO"

Write-Host "✅ 环境变量设置完成" -ForegroundColor Green
Write-Host "📁 数据路径: $env:QLIB_DATA_PATH" -ForegroundColor Yellow

# 运行qlib环境设置脚本
Write-Host "🔧 设置qlib环境..." -ForegroundColor Blue
python setup_qlib_environment.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ qlib环境设置成功" -ForegroundColor Green

    # 运行主程序
    Write-Host "🚀 启动RockXQlib GUI..." -ForegroundColor Green
    python launch_gui_complete_integration.py
} else {
    Write-Host "❌ qlib环境设置失败" -ForegroundColor Red
}

Read-Host "按任意键退出"
