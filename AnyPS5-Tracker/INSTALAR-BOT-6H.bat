@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_agendamento.ps1" -IntervaloMinutos 360
pause
