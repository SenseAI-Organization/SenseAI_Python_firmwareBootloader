# Detalles Técnicos - SPIFFS en ESP32

## 🏗️ Arquitectura de SPIFFS

### Qué es SPIFFS

**SPIFFS** (Spiffs Flash File System) es un sistema de archivos embebido diseñado por Spiffs creator (Peter Andersson) para:
- Microcontroladores con poco RAM
- Almacenamiento en SPI Flash
- Sistemas con power-loss recovery
- Operaciones POSIX-like (open, read, write, close)

**Características:**
- Log-structured filesystem
- Wear leveling (distribución de escrituras)
- Bad block handling
- CRC checking en cada página

---

## 📍 Configuración en ESP32-S3

### Parámetros SPIFFS Estándar

```
Block Size:        4096 bytes    (0x1000)
Page Size:         256 bytes     (0x100)
Object Name Len:   32 chars
Meta Length:       4 bytes
Use Magic:         true
Magic Value:       0x20140529
Magic Len:         0x20150115
```

### Cálculo de Magic Number

El magic number se calcula como:

```c
magic = SPIFFS_MAGIC
        ^ (block_size << 18)
        ^ (page_size  << 8)
        ^ (obj_name_len)
      = 0x20140529
        ^ 0x40000000  // 4096 << 18
        ^ 0x00010000  // 256 << 8
        ^ 0x00000020  // 32
      = 0x60150509
```

Este magic number se almacena en cada bloque para validar que los parámetros coinciden.

---

## 💾 Disposición en Flash

### Partición SPIFFS en tu ESP32

```
Address     Size        Purpose
─────────────────────────────────────
0x5F0000    0x128000    SPIFFS Partition (1.2 MB)
            (1,212,416 bytes total)
```

### Estructura Interna

```
0x5F0000 ┌─────────────────────────┐
         │ Block 0 (4096 bytes)    │
         │  ├─ Header + Magic      │
         │  ├─ Lookup Table        │
         │  └─ Data Pages          │
0x5F1000 ├─────────────────────────┤
         │ Block 1 (4096 bytes)    │
0x5F2000 ├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
         │ ...                     │
0x717FFF └─────────────────────────┘
         Total: 296 blocks
```

### Estructura de Block

```
Block Layout (4096 bytes):
┌─────────────────────────────────────┐
│ Block Header (first 4 bytes)        │  Offset 0x000
│ - Magic number + flags              │
├─────────────────────────────────────┤
│ Object Index/Lookup Table           │  Offset 0x004
│ - 16 entries × 8 bytes each         │
│ - Points to file objects            │
├─────────────────────────────────────┤
│ Page 0 (256 bytes)                  │  Offset 0x000
├─────────────────────────────────────┤
│ Page 1 (256 bytes)                  │  Offset 0x100
├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ Page 15 (256 bytes)                 │  Offset 0xF00
├─────────────────────────────────────┤
│ CRC-32 (4 bytes) at page end        │  Offset 0xFC
└─────────────────────────────────────┘
```

---

## 📄 Estructura de Archivo en SPIFFS

### File Object Entry

```
Entry Size: Variable
─────────────────────────
Offset  Size  Field
─────────────────────────
0x00    2     Flags
0x02    4     File Size
0x06    4     Block/Page Pointers
0x0A    32    Filename (null-terminated)
0x2A    ...   Metadata (timestamps, etc.)
```

### Estados de Archivo

- **ALLOCATED**: Archivo activo, listo para usar
- **DELETED**: Marcado para eliminación
- **INDEX**: Entrada de índice (parte de SPIFFS metadata)

---

## 🔄 Ciclo de Vida SPIFFS en tu Dispositivo

### 1. Primera Vez: Flash de Imagen

```
1. Bootloader detecta partición SPIFFS @ 0x5F0000
2. Kernel intenta montar SPIFFS
3. SPIFFS driver valida magic numbers
4. Si fallan: SPIFFS entra en recovery
5. Reformatea la partición
6. Indexa archivos desde image
```

### 2. Montaje Exitoso

```
I (25506) awsHandler: Initializing SPIFFS
W (25506) SPIFFS: mount failed, -10025. formatting...
I (25700) SPIFFS: format done...
I (31806) awsHandler: SPIFFS mounted successfully
```

### 3. Acceso a Archivos

Tu código puede:
```c
FILE* f = fopen("/spiffs/archivo.pem", "r");
size_t bytes = fread(buffer, 1, size, f);
fclose(f);
```

---

## 🧪 Proceso de Construcción de Image

### cómo mkspiffs Construye `spiffs.bin`

```bash
# Comando ejecutado internamente
mkspiffs -c data -b 4096 -p 256 -s 1212416 spiffs.bin
```

**Pasos:**

1. **Scan**: Lee todos los archivos en `data/`
2. **Organize**: Distribuye archivos en páginas (256 bytes c/u)
3. **Index**: Construye tabla de lookup con posiciones
4. **Checksum**: Calcula CRC-32 para cada página
5. **Pack**: Empaqueta en imagen de 1,212,416 bytes

**Archivo + Metadatos:**

```
Entrada de índice (32 bytes):
├─ Filename: /hermesTestClientCert.pem
├─ Size: 1220 bytes (0x4C4)
├─ Block: 0x0001
├─ Page: 0x0008
└─ CRC-32: 0x5A3F1B2C

Contenido (1220 bytes):
├─ Almacenado en páginas 8-13
├─ Distribuido: 256+256+256+256+196 bytes
└─ CRC calculado para cada página
```

---

## ⚠️ Problemas Conocidos y Soluciones

### 1. mkspiffs Non-Determinism

**Problema**: Cada run de mkspiffs produce checksums diferentes
**Razón**: Timestamps del filesystem, secuencia de operaciones
**Solución**: Usar pre-built image (spiffs.bin in data/)

### 2. Format Mismatch

**Problema**: Device rechaza imagen con código `-10025`
**Razón**: Magic numbers no coinciden con parámetros
**Solución**: Usar parámetros exactos: `-b 4096 -p 256`

### 3. File Indexing

**Problema**: Archivos existen pero no se encuentran
**Razón**: Lookup table corrupta o mal reconstruida
**Solución**: Esperar a que device complete formateo (5-10 segundos)

---

## 🔐 Validación de Checksums

### Cómo Funciona CRC-32

```
Por cada página (256 bytes):
1. Calcula CRC-32 de los 252 primeros bytes
2. Almacena CRC en bytes 252-256
3. Al leer: recalcula CRC y verifica
4. Si no coincide: página corrupta
```

### Magic Number Validation

```
Al montar SPIFFS:
1. Lee magic number de bloque 0
2. Computa magic esperado con parámetros del sistema
3. Si no coinciden: rechaza como invalid format
4. Device luego reformatea si es primera vez
```

---

## 📊 Estadísticas de Partición

Para tu ESP32-S3 estándar:

```
Total Size:           1,212,416 bytes (0x128000)
Block Size:           4,096 bytes
Number of Blocks:     296

Per Block:
  - Header:           4 bytes
  - Data:             4,092 bytes
  
Total Data Capacity:  ~1.2 MB (minus ~10KB overhead)
Usable for Files:     ~1.19 MB
```

---

## 🛠️ Herramientas para Debugging

### Leer SPIFFS de Dispositivo

```bash
esptool.py -p COM8 read_flash 0x5F0000 0x128000 spiffs_backup.bin
hexdump -C spiffs_backup.bin | head -50
```

### Verificar Estructura

```bash
# Contar bloques
ls -la spiffs.bin
# Size: 1212416 = 296 blocks × 4096

# Verificar magic numbers
hexdump -C spiffs.bin | head -20
# Buscar patrón de magic
```

### Monitor Actividad

En el firmware ESP32:
```c
#include "esp_spiffs.h"

void check_spiffs() {
    esp_spiffs_info(NULL, &total, &used);
    printf("SPIFFS: %d / %d bytes\n", used, total);
}
```

---

## 📚 Referencias

- **SPIFFS Repo**: https://github.com/pellepl/spiffs
- **ESP-IDF SPIFFS**: https://docs.espressif.com/projects/esp-idf/
- **mkspiffs**: https://github.com/igrr/mkspiffs

---

**Última actualización**: Noviembre 2025
