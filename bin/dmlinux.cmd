@echo off
rem ------------------------------------------------------------------
rem  dmlinux - Windows launcher for the Windows-to-Linux project
rem  Usage: dmlinux <command> [args...]
rem
rem  The project root is derived from this script's own location
rem  (%~dp0..), so the whole bin folder can be moved anywhere.
rem
rem  Keep this file ASCII-only: cmd.exe reads batch files with the
rem  console OEM code page, so non-ASCII text here would be garbled.
rem ------------------------------------------------------------------
setlocal
set "DMLINUX_HOME=%~dp0.."
set "DMLINUX=1"

python -c "import sys" >nul 2>&1
if not errorlevel 1 goto run_python
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 goto run_py

echo [dmlinux] No usable Python interpreter found. 1>&2
echo [dmlinux] Install Python 3.10+ and make sure "python" or "py" is on PATH. 1>&2
exit /b 2

:run_python
python "%DMLINUX_HOME%\main.py" %*
exit /b %ERRORLEVEL%

:run_py
py -3 "%DMLINUX_HOME%\main.py" %*
exit /b %ERRORLEVEL%
