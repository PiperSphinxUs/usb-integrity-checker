@echo off
setlocal
title USB Integrity Checker
cd /d "%~dp0src"

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
    echo.
    echo  =======================================================
    echo   Python was not found on this computer.
    echo   Please install Python from https://www.python.org/downloads/
    echo   During setup, make sure to check "Add python.exe to PATH".
    echo   ^(If you already installed Python 3.13+ and still see this,
    echo    try running "py --version" manually in this window.^)
    echo  =======================================================
    echo.
    pause
    exit /b 1
)

echo Using Python command: %PYCMD%

%PYCMD% -c "import customtkinter, PIL" >nul 2>nul
if errorlevel 1 (
    echo.
    echo  =======================================================
    echo   Some required packages are missing. Installing now...
    echo  =======================================================
    echo.
    %PYCMD% -m pip install -r requirements.txt
    %PYCMD% -c "import customtkinter, PIL" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo  =======================================================
        echo   Install failed, or a different Python install is being
        echo   used than the one that ran pip. Try running this manually:
        echo     %PYCMD% -m pip install -r requirements.txt
        echo  =======================================================
        echo.
        pause
        exit /b 1
    )
)

%PYCMD% gui_ctk.py
if errorlevel 1 (
    echo.
    echo  The program closed with an error. See the message above.
    pause
)
