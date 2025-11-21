# Solución de Problemas SPIFFS

## 🔴 Problemas Comunes y Soluciones

### 1. "SPIFFS: mount failed, -10025. formatting..."

**Síntomas:**
```
W (25506) SPIFFS: mount failed, -10025. formatting...
I (31806) awsHandler: SPIFFS mounted successfully
```

**Causa**: Primera vez que se flashea una imagen SPIFFS o formato diferente
**Solución**: ✅ Es NORMAL - El dispositivo detecta la nueva imagen, la reformatea, y la acepta
**Acción**: Espera a que complete el formateo (2-5 segundos) - Los archivos estarán disponibles después

---

### 2. "Failed to open file: /spiffs/..."

**Síntomas:**
```
E (31866) SPIFFS: Failed to open file: /spiffs/hermesTestServerCert.pem
E (31866) awsHandler: Failed to read certificate: hermesTestServerCert.pem
```

**Causa**: El archivo no está en la imagen SPIFFS que se flasheó
**Diagnóstico:**
1. Verifica que el archivo existe en `data/`
2. Verifica el nombre exacto (SPIFFS es case-sensitive)
3. Verifica que el archivo no está vacío

**Soluciones:**
```bash
# Verificar qué archivos hay en data/
dir data/

# Verificar tamaño del archivo
ls -la data/hermesTestServerCert.pem

# Si falta: copiar archivo
cp ruta/al/certificado.pem data/hermesTestServerCert.pem
```

**Después de agregar archivos:**
1. Re-ejecuta `firmwareBootLoader.py`
2. Click "Upload Data Folder (SPIFFS)"
3. Espera a que termine
4. Reinicia el ESP32

---

### 3. "No se pudo detectar la partición SPIFFS"

**Síntomas:**
```
❌ No se pudo detectar la partición SPIFFS en el dispositivo
```

**Causa**: El ESP32 no tiene una partición SPIFFS configurada o no responde
**Soluciones:**

1. **Verifica conexión USB**
   ```bash
   # En Windows
   mode COM8:
   # Debería mostrar configuración del puerto
   ```

2. **Verifica que el ESP32 esté en modo boot**
   - Desconecta y vuelve a conectar el USB
   - Algunos chips necesitan pulsar BOOT + RESET

3. **Flashea tabla de particiones**
   - Asegúrate de que el firmware incluya la partición SPIFFS
   - La partición debería estar en `0x5F0000` con tamaño `0x128000`

4. **Reinicia el dispositivo**
   ```bash
   # Presiona reset en el ESP32
   # O desconecta y reconecta USB
   ```

---

### 4. Archivos Visibles pero Contenido Incorrecto

**Síntomas:**
- El archivo se abre correctamente
- Pero el contenido está corrupto o vacío

**Causa**: 
- Archivo en `data/` está incompleto o corrupto
- Formato de archivo incompatible

**Soluciones:**

1. **Verifica el archivo original**
   ```bash
   # Ver tamaño y contenido
   ls -la data/archivo.pem
   file data/archivo.pem
   
   # Para certificados PEM
   openssl x509 -in data/archivo.pem -text -noout
   ```

2. **Re-copia el archivo**
   ```bash
   # Elimina el corrupto
   rm data/archivo.pem
   
   # Copia nuevo desde fuente
   cp ruta_correcta/archivo.pem data/
   ```

3. **Re-flashea SPIFFS**

---

### 5. "SPIFFS: filesystem seems corrupted"

**Síntomas:**
```
E (25506) SPIFFS: filesystem seems corrupted
W (25506) SPIFFS: mount failed, -10025. formatting...
```

**Causa**: Imagen SPIFFS flasheada es inválida o se corrompió en flash

**Soluciones:**

1. **Borra SPIFFS completamente**
   ```bash
   # Flashea zeros
   python -m esptool --chip esp32s3 --port COM8 \
     write-flash 0x5F0000 /dev/zero --size 0x128000
   ```

2. **Re-flashea SPIFFS**
   ```bash
   # Ejecuta el flasher nuevamente
   python firmwareBootLoader.py
   # Click "Upload Data Folder (SPIFFS)"
   ```

3. **Verifica integridad de archivo binario**
   ```bash
   # Ver tamaño exacto
   ls -la data/spiffs.bin
   # Debería ser exactamente 1212416 bytes
   ```

---

### 6. SPIFFS Monta pero Luego Falla

**Síntomas:**
```
I (31806) awsHandler: SPIFFS mounted successfully
E (31866) SPIFFS: Failed to open file: ...
```

**Causa**: Archivos no se indexaron correctamente tras formateo
**Soluciones:**

1. **Espera más tiempo**
   - El formateo puede tardar 5-10 segundos
   - Espera antes de intentar leer archivos

2. **Reinicia el dispositivo**
   ```bash
   # Pulsa reset en el ESP32
   ```

3. **Re-flashea con espera**
   ```bash
   python firmwareBootLoader.py
   # Espera a que muestre [OK] Flash successful
   # Luego espera 30 segundos antes de acceder a archivos
   ```

---

## 📊 Tabla de Referencia Rápida

| Error | Causa Probable | Solución Rápida |
|-------|---|---|
| `-10025 formatting` | Formato nuevo | Esperar, es normal |
| `Failed to open file` | Archivo no existe | Verificar en `data/`, re-flashear |
| `No se pudo detectar SPIFFS` | Puerto/conexión | Reconectar USB, verificar tabla particiones |
| `filesystem seems corrupted` | Imagen inválida | Borrar SPIFFS, re-flashear |
| Contenido incorrecto | Archivo corrupto | Verificar original, re-copiar |

---

## 🔧 Diagnóstico Avanzado

### Verificar Tamaño Exacto de SPIFFS

```bash
dir data\spiffs.bin
REM Debería mostrar exactamente 1,212,416 bytes

# En macOS/Linux
ls -la data/spiffs.bin
# Size: 1212416 bytes
```

### Verificar Archivos en Imagen

```bash
# Ver estructura de partición
esptool.py -p COM8 read_partition_table
```

### Leer SPIFFS Directamente del Dispositivo

```bash
# Extraer SPIFFS a archivo
esptool.py -p COM8 read_flash 0x5F0000 0x128000 spiffs_backup.bin

# Analizar
ls -la spiffs_backup.bin
# Debería ser 1212416 bytes
```

---

## 📞 Obtener Ayuda

### Información a Proporcionar

Si necesitas soporte, incluye:

1. **Modelo de ESP32**: ESP32-S3, ESP32, ESP32-C3, etc.
2. **IDF Version**: Se muestra en boot messages
3. **Tamaño de SPIFFS**: `ls -la data/spiffs.bin`
4. **Mensajes de error completos**
5. **Pasos que realizaste**

### Logs Útiles

Copia los logs del monitor serial:
```
[INFO] Detectando partición SPIFFS...
[OK] Found SPIFFS partition: spiffs @ 0x5F0000, size 0x128000
[INFO] Flasheando SPIFFS...
I (25506) awsHandler: Initializing SPIFFS
W (25506) SPIFFS: mount failed, -10025. formatting...
I (31806) awsHandler: SPIFFS mounted successfully
```

---

## 💡 Consejos

1. **Siempre verifica nombres** de archivo (case-sensitive en SPIFFS)
2. **Espera después de flashear** antes de acceder a archivos
3. **Mantén backups** de certificados originales
4. **Usa archivos pequeños** para probar primero
5. **Verifica tamaño de spiffs.bin** siempre es 1,212,416 bytes

---

**Última actualización**: Noviembre 2025
