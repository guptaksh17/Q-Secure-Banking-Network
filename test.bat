@echo off
REM Windows shortcut: runs the backend test suite in backend\.venv.
py -3.12 "%~dp0dev.py" test %*
