@echo off
setlocal
title USB Integrity Checker - Run Tests
cd /d "%~dp0"

set PYCMD=

where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 set PYCMD=python
)

if "%PYCMD%"=="" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py --version >nul 2>nul
        if not errorlevel 1 set PYCMD=py
    )
)

if "%PYCMD%"=="" (
    echo Python was not found. Install it first, then run this script again.
    pause
    exit /b 1
)

echo Using Python command: %PYCMD%
echo.
%PYCMD% -m unittest discover -s tests -p "test_*.py" -v

echo.
pause
