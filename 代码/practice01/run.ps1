$OutputEncoding = [System.Console]::OutputEncoding = [System.Console]::InputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

Write-Host "============================================================"
Write-Host "正在启动 LLM 客户端..."
Write-Host "============================================================"

Set-Location $PSScriptRoot
py -3.12 llm_client.py

Write-Host ""
Write-Host "按 Enter 键退出..."
Read-Host
