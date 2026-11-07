@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
title FloodSystem - Simulador interativo
pushd "%~dp0"
cls
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado nesta pasta.
    echo Consulte docs\simulator.md para preparar o projeto.
    pause
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -m tools.simulator menu %*
set "floodExitCode=%errorlevel%"
if not "%floodExitCode%"=="0" pause
popd
exit /b %floodExitCode%
