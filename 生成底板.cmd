@echo off
call "%~dp0run_python.cmd" "%~dp0baseplate_cli.py" %*
exit /b %errorlevel%
