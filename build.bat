@echo off
REM Build script for MultiTool application using PyInstaller
REM This script packages the application into a standalone executable

echo Building MultiTool application...
echo.

REM Run PyInstaller with the package structure
pyinstaller --onefile --windowed --noconsole --clean ^
    --icon=Assets/icon.ico ^
    --add-data "Assets/icon.ico;." ^
    --hidden-import=multitool ^
    --hidden-import=multitool.widgets ^
    --hidden-import=multitool.helpers ^
    MultiTool.py

echo.
echo Build complete!
echo The executable is located in: dist/MultiTool.exe
echo.
pause
