@echo off
title Factorio 2.0 Video to Blueprint Generator

if "%1"=="--web" goto run_web
if "%1"=="-w" goto run_web

if exist "%~dp0dist\VideoToFactorioBlueprint.exe" (
    start "" "%~dp0dist\VideoToFactorioBlueprint.exe"
    exit /b 0
) else if exist "%~dp0publish\VideoToFactorioBlueprint.exe" (
    start "" "%~dp0publish\VideoToFactorioBlueprint.exe"
    exit /b 0
) else if exist "%~dp0dist\FactorioVideoToBlueprint.exe" (
    start "" "%~dp0dist\FactorioVideoToBlueprint.exe"
    exit /b 0
) else if exist "%~dp0publish\FactorioVideoToBlueprint.exe" (
    start "" "%~dp0publish\FactorioVideoToBlueprint.exe"
    exit /b 0
)

where dotnet >nul 2>nul
if %errorlevel% equ 0 (
    if exist "%~dp0VideoToFactorioBlueprint" (
        dotnet run --project "%~dp0VideoToFactorioBlueprint"
        exit /b 0
    ) else (
        dotnet run --project "%~dp0FactorioVideoToBlueprint"
        exit /b 0
    )
)

:run_web
echo [INFO] Starting cross-platform Web UI...
python "%~dp0server.py" %*