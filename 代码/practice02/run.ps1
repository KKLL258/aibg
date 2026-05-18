$OutputEncoding = [System.Console]::OutputEncoding = [System.Console]::InputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

Write-Host "============================================================"
Write-Host "正在启动流式对话客户端..."
Write-Host "提示: 输入内容聊天，按 Ctrl+C 退出"
Write-Host "============================================================"
Write-Host ""

Set-Location $PSScriptRoot
py -3.12 chat_stream.py

Write-Host ""
Write-Host "按 Enter 键退出..."
Read-Host
