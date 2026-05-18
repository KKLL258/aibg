$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ScriptDir\.."
py -3.12 practice02/tool_chat.py
Read-Host "按 Enter 键退出"
