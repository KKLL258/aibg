$OutputEncoding = [System.Console]::OutputEncoding = [System.Console]::InputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

Write-Host "============================================================"
Write-Host "正在启动 - 聊天记忆系统 + 5W信息提取"
Write-Host "提示: 每5轮自动提取关键信息，支持/search检索历史"
Write-Host "============================================================"
Write-Host ""

Set-Location $PSScriptRoot
py -3.12 chat_memory.py

Write-Host ""
Write-Host "按 Enter 键退出..."
Read-Host
