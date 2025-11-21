@echo off
echo ========================================
echo ESP32 Firmware Flasher - Instalador (app_generation)
echo ========================================
echo.
echo Este script instalara las dependencias necesarias usando el Python del sistema o la venv creada por build_app.ps1
echo.
echo Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r ..\requirements.txt

if %errorlevel% equ 0 (
    echo Instalacion completada exitosamente!
    exit /b 0
) else (
    echo Error durante la instalacion.
    exit /b 1
)
