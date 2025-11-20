@echo off
echo ========================================
echo ESP32 Firmware Flasher - Instalador
echo ========================================
echo.
echo Este script instalara las dependencias necesarias:
echo   - pyserial (comunicacion serial)
echo   - esptool (herramienta de flasheo ESP32)
echo.
pause

echo.
echo Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ========================================
if %errorlevel% equ 0 (
    echo Instalacion completada exitosamente!
    echo Ahora puedes ejecutar: python firmwareBootLoader.py
) else (
    echo Error durante la instalacion.
    echo Intenta manualmente: pip install -r requirements.txt
)
echo ========================================
echo.
pause
