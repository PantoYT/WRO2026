@echo off
rem Espero-bot launcher - works regardless of PowerShell ExecutionPolicy.
rem Usage: run.bat [-Test] [-SetupOnly] [-Reinstall]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
