@echo off
setlocal
set "GF_PYTHON=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%GF_PYTHON%" set "GF_PYTHON=%~dp0..\SolidWorks-MCP\.venv\Scripts\pythonw.exe"
if not exist "%GF_PYTHON%" set "GF_PYTHON=pythonw"
start "" "%GF_PYTHON%" "%~dp0app_scad.py"
