@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 main.py %*
  goto :end
)
where python >nul 2>nul
if not errorlevel 1 (
  python main.py %*
  goto :end
)
echo Python 3.10 or later is required. Install Python for Windows, then retry.
exit /b 1
:end
if errorlevel 1 (
  echo.
  echo Launch failed. Check the messages above.
  pause
)
endlocal
