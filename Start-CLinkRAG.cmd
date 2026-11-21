@echo off
setlocal
cd /d "%~dp0"
set "CLINKRAG_PYTHON=runtime\python.exe"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -I -c "import requests,yaml" >nul 2>nul
    if not errorlevel 1 set "CLINKRAG_PYTHON=.venv\Scripts\python.exe"
)
if not exist "%CLINKRAG_PYTHON%" (
    echo Download and extract the portable Windows release, or run install-local.ps1.
    pause
    exit /b 1
)
"%CLINKRAG_PYTHON%" -I -X utf8 -B "tools\launch.py" %*
set "CLINKRAG_EXIT=%ERRORLEVEL%"
if not "%CLINKRAG_EXIT%"=="0" if not defined CLINKRAG_UNATTENDED pause
exit /b %CLINKRAG_EXIT%
