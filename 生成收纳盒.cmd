@echo off
call "%~dp0run_python.cmd" "%~dp0bin_cli.py" %*
exit /b %errorlevel%
