@echo off
echo ========================================
echo ESP32 Flasher - Generador de EXE
echo ========================================
echo.

echo [1/3] Instalando dependencias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error al instalar dependencias
    pause
    exit /b 1
)
echo.

echo [2/3] Creando ejecutable con PyInstaller...
pyinstaller --onefile --windowed --name "ESP32_Flasher" --icon=NONE esp32_flasher.py
if %errorlevel% neq 0 (
    echo Error al crear el ejecutable
    pause
    exit /b 1
)
echo.

echo [3/3] Creando carpeta firmware en dist...
if not exist "dist\firmware" mkdir "dist\firmware"
echo.

echo ========================================
echo ¡COMPLETADO CON EXITO!
echo ========================================
echo.
echo Tu ejecutable esta en: dist\ESP32_Flasher.exe
echo.
echo IMPORTANTE: Copia la carpeta 'firmware' junto al .exe
echo y coloca tu archivo .bin dentro de ella.
echo.
pause