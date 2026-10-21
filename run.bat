@echo off
REM Windows shortcut: starts FastAPI (:8000) and Vite (:5173).
py -3.12 "%~dp0dev.py" run %*
