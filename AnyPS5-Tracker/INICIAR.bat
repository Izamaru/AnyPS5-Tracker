@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  AnyPS5 Tracker - Progresso + GitHub
echo ============================================
where py >nul 2>nul
if not errorlevel 1 (
  py -3 tracker.py --once
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 nao encontrado. Instale Python 3.10 ou superior.
    pause
    exit /b 1
  )
  python tracker.py --once
)
if exist painel.html start "" "%~dp0painel.html"
pause
