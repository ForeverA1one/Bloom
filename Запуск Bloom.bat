@echo off
chcp 65001 >nul
title Bloom — управление яркостью мониторов
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0bloom.py"
) else (
    python "%~dp0bloom.py"
)
