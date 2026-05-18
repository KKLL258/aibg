$OutputEncoding = [System.Console]::OutputEncoding = [System.Console]::InputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

Write-Host "============================================================"
Write-Host "正在启动 - 聊天历史自动总结压缩"
Write-Host "提示: 超过5轮对话或3000字符自动触发总结"
Write-Host "============================================================"
Write-Host ""

Set-Location $PSScriptRoot
py -3.12 chat_compression.py

Write-Host ""
Write-Host "按 Enter 键退出..."
Read-Host
