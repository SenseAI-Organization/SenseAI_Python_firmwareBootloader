# Guía SPIFFS - Cómo Subir Archivos al ESP32

## 📋 Resumen Rápido

1. **Añade archivos** a la carpeta `data/`
2. **Ejecuta** `firmwareBootLoader.py`
3. **Click** en "Upload Data Folder (SPIFFS)"
4. **Espera** a que termine
5. ✅ **Archivos disponibles** en `/spiffs/filename` en tu ESP32

---

## 🔍 ¿Qué es SPIFFS?

**SPIFFS** (Spiffs Flash File System) es un sistema de archivos ligero diseñado para microcontroladores y dispositivos embebidos. Permite:

- Almacenar archivos en la memoria flash del ESP32
- Organizarlos en directorios
- Acceder a ellos como en un filesystem normal
- Usar espacio de flash no ocupado por firmware

### En tu ESP32
- Partición dedicada: `0x5F0000` a `0x717FFF` (~1.2 MB)
- Los archivos se montan en `/spiffs/`
- Tu código puede leerlos con funciones estándar de archivo

---

## 📁 Carpeta `data/`

Esta carpeta contiene los archivos que se suben al ESP32:

```
data/
├── spiffs.bin                    # Imagen SPIFFS (prebuilt, no modificar)
├── hermesTestClientCert.pem      # Certificado cliente (ejemplo)
├── hermesTestClientKey.pem       # Clave privada (ejemplo)
└── hermesTestServerCert.pem      # Certificado servidor (ejemplo)
```

### Añadir Nuevos Archivos

1. **Coloca tu archivo** en la carpeta `data/`
2. **Ejecuta el flasher**
3. El archivo se incluirá automáticamente en SPIFFS

### Ejemplos de Archivos que Puedes Añadir

- **Certificados**: `.pem`, `.crt`, `.der`
- **Configuración**: `.json`, `.txt`, `.conf`
- **Datos**: `.bin`, `.dat`
- **Recursos**: Cualquier archivo binario

---

## 🚀 Proceso Paso a Paso

### 1. Preparar Archivos

```bash
# Copiar un archivo a data/
cp mi_certificado.pem data/mi_certificado.pem

# O simplemente arrastra el archivo en el explorador
```

### 2. Ejecutar el Flasher

```bash
python firmwareBootLoader.py
```

### 3. Seleccionar Modo

En la interfaz gráfica:
1. **Selecciona el puerto COM** donde está tu ESP32
2. **Click en "Upload Data Folder (SPIFFS)"**

### 4. Esperar a que Termine

El programa:
- Auto-detecta la partición SPIFFS del ESP32
- Prepara la imagen SPIFFS con tus archivos
- Flashea la imagen al dispositivo
- Verifica que todo esté correcto

### 5. Verificar en el Dispositivo

Tu código ESP32 puede acceder a los archivos:

```cpp
// En tu firmware ESP32 (pseudocódigo)
FILE* f = fopen("/spiffs/mi_certificado.pem", "r");
if (f) {
    // Leer certificado
    fclose(f);
}
```

---

## 📊 Estructura Resultante

Cuando se flashea `spiffs.bin`, tu ESP32 montará:

```
ESP32 Flash Memory
├── Firmware (0x50000)
├── ...
├── SPIFFS Partition (0x5F0000)
│   ├── spiffs.bin (contenido)
│   └── Archivos montados como:
│       ├── /spiffs/hermesTestClientCert.pem
│       ├── /spiffs/hermesTestClientKey.pem
│       ├── /spiffs/hermesTestServerCert.pem
│       └── /spiffs/tus_archivos.pem
└── ...
```

---

## ✅ Verificar que Funcionó

### Opción 1: Monitor Serial

Observa la salida serial del ESP32:

```
I (31806) awsHandler: SPIFFS mounted successfully
I (31806) SPIFFS: Listing files in SPIFFS...
I (31866) SPIFFS: Found file: /spiffs/hermesTestClientCert.pem
I (31876) SPIFFS: Found file: /spiffs/hermesTestClientKey.pem
```

### Opción 2: En tu Código

```cpp
#include "esp_spiffs.h"
#include <dirent.h>

void list_spiffs_files() {
    DIR* dir = opendir("/spiffs");
    if (dir) {
        struct dirent* entry;
        while ((entry = readdir(dir))) {
            printf("Archivo: %s\n", entry->d_name);
        }
        closedir(dir);
    }
}
```

---

## 🔧 Solucionar Problemas

### "SPIFFS: mount failed -10025"

**Causa**: El formato SPIFFS no se reconoce en el primer intento
**Solución**: Es normal, el dispositivo lo reformatea automáticamente en el segundo intento

### "Failed to open file: /spiffs/..."

**Causa**: El archivo no está en la imagen SPIFFS
**Solución**: 
1. Verifica que el archivo esté en `data/`
2. Verifica el nombre exacto (sensible a mayúsculas/minúsculas)
3. Re-flashea SPIFFS

### El archivo aparece pero está vacío

**Causa**: El archivo en `data/` está vacío
**Solución**: Verifica el contenido del archivo original

---

## 📈 Más Información

Para detalles técnicos sobre SPIFFS:
→ Lee [TECHNICAL_DETAILS.md](TECHNICAL_DETAILS.md)

Para problemas avanzados:
→ Lee [SPIFFS_TROUBLESHOOTING.md](SPIFFS_TROUBLESHOOTING.md)

---

**Última actualización**: Noviembre 2025
