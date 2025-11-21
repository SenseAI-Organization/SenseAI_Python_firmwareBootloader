@echo off
echo ========================================
echo ESP32 Flasher - Generador de EXE (app_generation)
echo ========================================
echo.

echo [1/4] Instalando dependencias (en entorno virtual)...
pushd %~dp0
call install_dependencies.bat
if %errorlevel% neq 0 (
    echo Error al instalar dependencias
    pause
    exit /b 1
)
echo.

echo [2/4] Creando ejecutable con PyInstaller (via PowerShell)...
powershell -ExecutionPolicy Bypass -File build_app.ps1
if %errorlevel% neq 0 (
    echo Error al crear el ejecutable
    pause
    popd
    exit /b 1
)
echo.

echo [3/4] Copiando spiffs.bin a salida (por si acaso)...
if exist "..\app_generation_output\spiffs.bin" (
    echo spiffs.bin already present in output
) else (
    if exist "..\data\spiffs.bin" copy "..\data\spiffs.bin" "..\app_generation_output\spiffs.bin"
)

echo [4/4] Finalizando
echo ========================================
echo ¡COMPLETADO CON EXITO!
echo Tu ejecutable esta en: ..\app_generation_output\ESP32_Flasher.exe
echo Si faltan archivos de datos, revisa la carpeta: ..\app_generation_output\data
echo.
pause
popd
