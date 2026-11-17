@echo off
setlocal
set "GF_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%GF_PYTHON%" set "GF_PYTHON=%~dp0..\SolidWorks-MCP\.venv\Scripts\python.exe"
if not exist "%GF_PYTHON%" set "GF_PYTHON=python"
"%GF_PYTHON%" %*
exit /b %errorlevel%
