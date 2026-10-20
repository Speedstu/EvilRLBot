@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\v5\python.exe" (
    echo Missing runtime. Extract the entire ZIP package first.
    pause
    exit /b 1
)
"runtime\v5\python.exe" "ui\classic.py"
echo Evil RLBot exit code: %ERRORLEVEL%
pause
