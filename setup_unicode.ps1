# PowerShell Unicode Setup Script
# 设置PowerShell支持Unicode

Write-Host "Setting up Unicode support for PowerShell..." -ForegroundColor Green

# 设置控制台代码页为UTF-8
chcp 65001

# 设置环境变量
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $PWD

Write-Host "Unicode support configured!" -ForegroundColor Green
Write-Host "Current code page: $(chcp)" -ForegroundColor Yellow
Write-Host "PYTHONIOENCODING: $env:PYTHONIOENCODING" -ForegroundColor Yellow
Write-Host "PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Yellow

# 测试Unicode输出
Write-Host "`nTesting Unicode output:" -ForegroundColor Cyan
Write-Host "✅ Success" -ForegroundColor Green
Write-Host "❌ Error" -ForegroundColor Red
Write-Host "⚠️ Warning" -ForegroundColor Yellow
Write-Host "🚀 Rocket" -ForegroundColor Magenta
Write-Host "🎉 Celebration" -ForegroundColor Cyan

Write-Host "`nUnicode setup complete! You can now use Unicode characters in your Python scripts." -ForegroundColor Green

