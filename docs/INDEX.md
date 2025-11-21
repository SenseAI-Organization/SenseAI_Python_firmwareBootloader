# Documentación - SenseAI Firmware Bootloader

## 📚 Tabla de Contenidos

### Para Empezar
- **README.md** (en raíz) - Inicio rápido y características principales

### Guías Principales
1. **[SPIFFS_GUIDE.md](SPIFFS_GUIDE.md)** - Cómo usar SPIFFS y subir archivos
2. **[SPIFFS_TROUBLESHOOTING.md](SPIFFS_TROUBLESHOOTING.md)** - Solución de problemas comunes
3. **[TECHNICAL_DETAILS.md](TECHNICAL_DETAILS.md)** - Detalles técnicos y arquitectura

---

## 🎯 Guía Rápida por Caso de Uso

### "Quiero subir certificados al ESP32"
→ Lee [SPIFFS_GUIDE.md](SPIFFS_GUIDE.md)

### "Mi SPIFFS no funciona / no encuentra archivos"
→ Lee [SPIFFS_TROUBLESHOOTING.md](SPIFFS_TROUBLESHOOTING.md)

### "Quiero entender cómo funciona internamente"
→ Lee [TECHNICAL_DETAILS.md](TECHNICAL_DETAILS.md)

---

## 📁 Estructura de Carpetas

```
docs/
├── INDEX.md                         ← Este archivo
├── SPIFFS_GUIDE.md                  # Guía práctica
├── SPIFFS_TROUBLESHOOTING.md        # Solución de problemas
└── TECHNICAL_DETAILS.md             # Detalles internos
```

---

## 🔑 Puntos Clave

- **spiffs.bin** en la carpeta `data/` es la imagen del filesystem que se flashea
- Los archivos en `data/` son parte de esta imagen
- El script `firmwareBootLoader.py` maneja todo automáticamente
- Ver la documentación específica para detalles

---

**Última actualización**: Noviembre 2025
