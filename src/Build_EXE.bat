@echo off
setlocal
title Build USB Integrity Checker .exe
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
echo Installing/updating build dependencies...
%PYCMD% -m pip install --upgrade -r requirements.txt pyinstaller

echo.
echo Building the standalone .exe (this can take a minute or two)...
%PYCMD% -m PyInstaller --noconfirm --clean build_exe.spec

if errorlevel 1 (
    echo.
    echo Build failed. See the error above.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo   Build finished successfully.
echo   Your standalone program is in:
echo   %~dp0dist\USB Integrity Checker\
echo   Double-click "USB Integrity Checker.exe" inside that folder to run it -
echo   no Python installation required on the machine you copy it to.
echo =======================================================
pause
