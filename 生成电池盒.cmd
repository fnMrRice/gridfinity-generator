@echo off
call "%~dp0run_python.cmd" "%~dp0battery_cli.py" %*
exit /b %errorlevel%
