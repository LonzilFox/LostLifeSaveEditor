@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHON=python"
where py >nul 2>nul
if not errorlevel 1 set "PYTHON=py -3"
%PYTHON% -m venv ".venv-build"
if errorlevel 1 goto :error
call ".venv-build\Scripts\activate.bat"
if errorlevel 1 goto :error
python -m pip install --upgrade pip pyinstaller
if errorlevel 1 goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "SOLSaveEditor" --paths "." main.py
if errorlevel 1 goto :error
echo.
echo BUILD SUCCEEDED: dist\SOLSaveEditor.exe
exit /b 0
:error
echo.
echo BUILD FAILED. Check Python installation, network connection, and messages above.
pause
exit /b 1
