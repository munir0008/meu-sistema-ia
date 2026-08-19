@echo off
REM Wrapper fino para run_app.py — inicia backend + frontend + navegador.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python nao encontrado no PATH. Instale em https://www.python.org/downloads/
    pause
    exit /b 1
)

python run_app.py %*
if errorlevel 1 pause
