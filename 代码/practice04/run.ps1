$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
python chat_client.py
Read-Host "按 Enter 键继续..."
