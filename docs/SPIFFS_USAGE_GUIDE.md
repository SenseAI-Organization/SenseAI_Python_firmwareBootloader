# SPIFFS Upload Feature - Usage Guide

## Overview
The "Upload Data Folder (SPIFFS)" button flashes certificate and data files to the ESP32's SPIFFS filesystem.

## How It Works
1. Button copies the pre-built `spiffs_with_correct_names.bin` image
2. Flashes it to the SPIFFS partition at offset `0x5F0000`
3. Device mounts SPIFFS and accesses files as `/spiffs/filename`

## Current Files in SPIFFS
- `/spiffs/hermesTestServerCert.pem` - Server certificate
- `/spiffs/hermesTestClientCert.pem` - Client certificate  
- `/spiffs/hermesTestClientKey.pem` - Private key

## Adding New Files

### Method 1: Quick (Use Existing Image)
If you just need to re-upload the same files:
1. Add/modify files in `data/` folder
2. Click "Upload Data Folder (SPIFFS)" button
3. Done! (Uses cached image with existing files)

### Method 2: Add New Files (Build New Image)
If you need to add NEW files to SPIFFS:

1. **Add files to `data/` folder**
   - Place all files you want in `data/`
   - Example: `data/config.txt`, `data/firmware.bin`, etc.

2. **Build new SPIFFS image**
   ```bash
   mkspiffs -c data -s 1212416 -p 256 -b 4096 spiffs_with_correct_names.bin
   ```
   
   Or use the helper script:
   ```bash
   python tools_build_spiffs.py
   ```

3. **Test on device**
   ```bash
   python -m esptool --chip esp32s3 --port COM8 --baud 460800 \
     --before default-reset --after hard-reset write-flash -z \
     --flash-mode dio --flash-freq 40m --flash-size detect \
     0x5F0000 spiffs_with_correct_names.bin
   ```
   
   Verify device serial output shows SPIFFS mounted with all files

4. **Use the button**
   - Now the button will use your new image automatically

## Technical Details

### SPIFFS Configuration
- **Partition offset:** `0x5F0000` (detected from device partition table)
- **Partition size:** `0x128000` (1,212,416 bytes)
- **Page size:** 256 bytes
- **Block size:** 4096 bytes
- **Mount point on device:** `/spiffs/`

### Why We Use Pre-Built Images
mkspiffs generates metadata (timestamps, checksums) that varies each build. The ESP-IDF SPIFFS driver can reject these. Using a pre-built, tested image ensures reliability.

### File Paths
- **In image:** Files stored as `/filename`
- **On device:** Firmware prepends `/spiffs/`, so device accesses `/spiffs/filename`
- **Example:** `hermesTestServerCert.pem` → `/spiffs/hermesTestServerCert.pem`

## Troubleshooting

### Device shows "mount failed, -10025"
This means SPIFFS image was rejected. Solutions:
1. Use "Upload Data Folder" button (uses tested image)
2. If building manually, verify image with device test before using

### Device can't find files
Check:
1. Device logs show SPIFFS mounted successfully
2. File is in `data/` folder when building image
3. Firmware code opens `/spiffs/filename` (with `/spiffs/` prefix)

### Want to use mkspiffs directly?
```bash
# Find mkspiffs
where mkspiffs  # or check ~/.platformio/packages/tool-mkspiffs/

# Build image
mkspiffs -c data -s 1212416 -p 256 -b 4096 output.bin

# Flash to device
python -m esptool --chip esp32s3 --port COM8 --baud 460800 \
  --before default-reset --after hard-reset write-flash -z \
  --flash-mode dio --flash-freq 40m --flash-size detect \
  0x5F0000 output.bin
```

## Related Files
- `firmwareBootLoader.py` - Main app (button implementation)
- `spiffs_with_correct_names.bin` - Pre-built working image
- `data/` - Folder with files to upload
- `tools_build_spiffs.py` - Helper script for building SPIFFS
