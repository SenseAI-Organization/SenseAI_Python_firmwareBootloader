# ESP32 Firmware Flasher

Aplicación GUI para flashear firmware en ESP32/ESP32-S3 con modos Simple y Completo.

## 🚀 Instalación Rápida

### Opción 1: Script Automático (Recomendado)
1. Ejecuta `install_dependencies.bat`
2. Ejecuta `python firmwareBootLoader.py`

### Opción 2: Manual
```bash
pip install -r requirements.txt
python firmwareBootLoader.py
```

## 📦 Dependencias

- **pyserial** - Comunicación serial con dispositivos
- **esptool** - Herramienta oficial de Espressif para flasheo ESP32

## ✨ Características

### Modos de Flasheo
- **Simple Mode**: Solo firmware (actualización rápida)
- **Complete Mode**: Bootloader + Partitions + Firmware (flasheo completo)

### Paneles de Debug
- **Debug Messages**: Mensajes detallados de depuración
- **Serial Monitor**: Monitor TX/RX de comunicación serial
- **Session Info**: Estadísticas y MACs de dispositivos flasheados

### Funciones
- ✅ Auto-detección de archivos PlatformIO
- ✅ Lectura de particiones desde dispositivo
- ✅ Smart Erase (preserva NVS/WiFi)
- ✅ Análisis de firmware
- ✅ Tracking de sesión con MACs

## 🔧 Uso

1. **Conecta tu ESP32** al puerto USB
2. **Selecciona el modo**:
   - Simple: Solo firmware.bin
   - Complete: Bootloader + Partitions + Firmware
3. **Selecciona archivos** (o usa auto-detección)
4. **Haz clic en "FLASHEAR FIRMWARE"**

## 📝 Estructura de Archivos

```
SenseAI_Python_firmwareBootloader/
├── firmwareBootLoader.py          # Aplicación principal
├── requirements.txt               # Dependencias Python
├── install_dependencies.bat       # Instalador automático
├── crear_exe.bat                  # Compilar a .exe
└── firmware/                      # Carpeta para archivos .bin
```

## 🐛 Troubleshooting

### "esptool no está instalado"
**Solución**: Ejecuta `install_dependencies.bat` o `pip install esptool`

### "No module named serial"
**Solución**: Ejecuta `pip install pyserial`

### No detecta puertos COM
**Solución**: 
- Verifica que el ESP32 esté conectado
- Instala drivers USB-Serial (CH340/CP2102)
- Haz clic en "🔄 Actualizar"

### Error de flasheo
**Solución**:
- Mantén presionado BOOT mientras conectas el ESP32
- Verifica el tipo de chip correcto (ESP32-S3, ESP32, etc.)
- Reduce el Baud Rate a 115200
- Activa "Modo Verbose" para ver detalles

## 📊 Panel de Sesión

- **Total Flasheos**: Intentos totales
- **Exitosos**: Flasheos completados
- **Dispositivos únicos**: Número de MACs diferentes
- **MACs Flasheadas**: Lista de direcciones MAC

## ⚙️ Configuración Recomendada

- **Baud Rate**: 460800 (rápido y confiable)
- **Chip**: ESP32-S3 (más común)
- **Borrar flash**: ✅ Activado
- **Verificar**: ✅ Activado
- **Preservar NVS**: ❌ Desactivado (a menos que necesites mantener WiFi)

## 🔗 Direcciones de Flash Estándar

```
0x1000  - Bootloader (2nd stage)
0x8000  - Partition Table
0x49000 - OTA Data (si hay OTA)
0x10000 - App (sin OTA)
0x50000 - App (con OTA)
```

## 📄 Licencia

Desarrollado por SenseAI Organization
