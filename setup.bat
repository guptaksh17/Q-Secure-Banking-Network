@echo off
REM Windows shortcut: creates backend\.venv and installs everything.
py -3.12 "%~dp0dev.py" setup %*
