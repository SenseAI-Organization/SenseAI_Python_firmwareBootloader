# ESP32 Firmware Flasher - Refactoring Complete ✅

## Summary
Complete refactoring of the ESP32 firmware flasher following ESP-IDF best practices and PlatformIO patterns.

## Changes Implemented

### 1. ✅ Two Clear Flash Modes (Instead of 11 Confusing Checkboxes)

**Simple Mode:**
- Flash firmware only (firmware.bin)
- Assumes bootloader already exists on chip
- Uses 0x50000 for ESP32-S3 (OTA layout) or 0x10000 for ESP32 classic
- Quick updates - typical use case

**Complete Mode:**
- Flash bootloader.bin (0x1000) + partitions.bin (0x8000) + firmware.bin
- Exactly like PlatformIO's upload process
- For new chips or complete re-flash
- Automatically detects app address from partition table

### 2. ✅ Removed Synthetic Bootloader Generation (Security Risk)

**REMOVED (Dangerous):**
- `create_bootloader_for_platformio()` - generated fake bootloaders
- `create_esp32s3_bootloader()` - unreliable synthetic bootloader
- `create_partition_table_for_platformio()` - hardcoded partition tables

**NOW USES:**
- Real bootloader.bin from PlatformIO builds
- Real partitions.bin from PlatformIO builds
- Auto-detection of companion files from `.pio/build/<board>/` directory

### 3. ✅ Proper Partition Table Handling

**NEW FEATURES:**
- Binary partition table parser using `struct` module
- Reads partition table from device at 0x8000
- Parses partition entries to find actual app address
- Detects OTA support automatically
- Creates proper OTA data initial file if needed

**Methods Added:**
- `parse_partition_table()` - Read from device
- `parse_partition_table_file()` - Parse .bin file
- `detect_device_partitions()` - Read partitions from connected ESP32
- `create_ota_data_initial_file()` - Create proper OTA selector

### 4. ✅ ESP-IDF Style Architecture

**New Structure:**
```python
flasher_args = {
    "write_flash_args": ["--flash_mode", "dio", "--flash_freq", "80m", "--flash_size", "detect"],
    "flash_files": [
        ("0x1000", "bootloader.bin", "Bootloader (2nd stage)"),
        ("0x8000", "partitions.bin", "Partition Table"),
        ("0x49000", "ota_data_initial.bin", "OTA Data Initial"),
        ("0x50000", "firmware.bin", "Firmware (app)")
    ],
    "extra_args": {...}
}
```

**Benefits:**
- Clear, organized flash planning
- Easy to debug - shows exactly what will be flashed where
- Systematic two-phase operation: erase → flash components
- Each component flashed individually with progress tracking

### 5. ✅ Smart Erase Options

**Three Options:**
1. **Full Erase** (default) - Erase entire chip before flashing
2. **Smart Erase** (preserve NVS) - Erase only app regions, keep NVS/WiFi settings
3. **No Erase** - Write directly (not recommended)

### 6. ✅ File Auto-Detection

**Automatic Discovery:**
- When you select `firmware.bin`, the app automatically searches for:
  - `bootloader.bin` in same directory
  - `partitions.bin` in same directory
  - PlatformIO build folders: `.pio/build/<board>/`
- Button to manually trigger PlatformIO file detection

### 7. ✅ Device Partition Detection

**New Feature:**
- "🔍 Detectar Particiones" button
- Reads partition table from connected device at 0x8000
- Shows what partitions exist on the chip
- Helps diagnose flashing issues

## UI Improvements

**Before:** 11 overlapping checkboxes (confusing)
**After:** 2 clear radio buttons (Simple vs Complete mode)

**New Elements:**
- File picker buttons with auto-detection
- Device partition detection button
- Clean 3-checkbox options (erase, verify, preserve NVS)
- Color-coded status labels (green=selected, gray=not needed, orange=missing)

## ESP-IDF Standard Addresses Used

```
0x1000  - Bootloader (2nd stage)
0x8000  - Partition Table
0x49000 - OTA Data (if OTA enabled)
0x10000 - App (no OTA)
0x50000 - App (with OTA, typical ESP32-S3)
```

## Methods Added

1. `on_mode_change()` - Handle Simple/Complete mode switching
2. `select_firmware_file()` - File picker for firmware
3. `select_bootloader_file()` - File picker for bootloader
4. `select_partitions_file()` - File picker for partitions
5. `auto_detect_companion_files()` - Auto-find bootloader/partitions
6. `auto_detect_pio_files()` - Find PlatformIO build files
7. `detect_device_partitions()` - Read partitions from device
8. `_detect_partitions_thread()` - Thread for partition reading
9. `parse_partition_table()` - Parse device partition table
10. `parse_partition_table_file()` - Parse partition .bin file
11. `build_flasher_args()` - Create ESP-IDF style flash plan
12. `get_firmware_address_simple()` - Determine app address for Simple mode
13. `create_ota_data_initial_file()` - Generate OTA selector file
14. `execute_erase()` - Full chip erase
15. `smart_erase()` - Erase only app regions
16. `flash_component()` - Flash single component with progress

## Methods Removed

1. ❌ `create_bootloader_for_platformio()` - Synthetic bootloader (unreliable)
2. ❌ `create_esp32s3_bootloader()` - Fake bootloader generation
3. ❌ `create_partition_table_for_platformio()` - Hardcoded partitions
4. ❌ `create_ota_data()` - Replaced with proper OTA data generation
5. ❌ `create_nvs_data()` - Not needed (NVS initialized by app)
6. ❌ `flash_with_platformio_layout()` - Complex overlapping logic
7. ❌ `flash_firmware_only_mode()` - Merged into main logic
8. ❌ `flash_with_real_platformio_files()` - Merged into main logic
9. ❌ `smart_erase_firmware_region()` - Replaced with `smart_erase()`

## Testing Recommendations

### Test 1: Simple Mode (Firmware Only)
1. Select "Simple Mode"
2. Choose `firmware.bin`
3. Connect ESP32-S3 with existing bootloader
4. Click "⚡ FLASHEAR FIRMWARE"
5. Should flash only to 0x50000 (or 0x10000 depending on chip/partitions)

### Test 2: Complete Mode (Full Flash)
1. Select "Complete Mode"
2. Choose `firmware.bin` (auto-detection should find bootloader/partitions)
3. Or manually select all three files
4. Connect fresh ESP32-S3
5. Click "⚡ FLASHEAR FIRMWARE"
6. Should flash:
   - Bootloader → 0x1000
   - Partitions → 0x8000
   - OTA Data → 0x49000 (if OTA detected)
   - Firmware → 0x50000 (or address from partition table)

### Test 3: Partition Detection
1. Connect ESP32 with existing firmware
2. Click "🔍 Detectar Particiones"
3. Should read and display partition table from device

### Test 4: Auto-Detection
1. Click "📁 Seleccionar" for firmware
2. Navigate to PlatformIO build folder
3. Select `firmware.bin`
4. Should automatically find and select `bootloader.bin` and `partitions.bin`

### Test 5: Smart Erase
1. Enable "Preservar NVS/WiFi data"
2. Flash firmware
3. NVS settings should survive (WiFi credentials, etc.)

## Configuration

**Default Settings:**
- Baud Rate: 460800 (faster, recommended)
- Flash Mode: Simple
- Erase: Enabled
- Verify: Enabled
- Preserve NVS: Disabled

**Recommended Baud Rates:**
- 460800 (default) - Fast and reliable
- 921600 - Fastest, may be unstable on some USB adapters
- 230400 - Slower but more compatible
- 115200 - Slowest but most reliable

## File Structure

```
SenseAI_Python_firmwareBootloader/
├── firmwareBootLoader.py          (1222 lines - cleaned and refactored)
├── requirements.txt               (dependencies)
├── crear_exe.bat                  (build script)
├── firmware/                      (firmware directory)
└── REFACTORING_COMPLETE.md       (this file)
```

## Dependencies

```
pyserial >= 3.5
esptool >= 4.7
```

## Known Limitations

1. **Partition Detection requires connected device** - Can't detect partitions without hardware
2. **OTA address hardcoded to 0x49000** - Standard ESP-IDF value, should work for most cases
3. **Simple mode assumes standard addresses** - 0x50000 for ESP32-S3 OTA, 0x10000 for no-OTA
4. **No support for custom partition schemes** - Uses standard ESP-IDF layouts

## Future Enhancements (Optional)

1. **Partition Table Editor** - Create/edit partition tables in the GUI
2. **Firmware Comparison** - Compare two firmware files
3. **Batch Flashing** - Flash multiple devices simultaneously
4. **Templates** - Save common configurations as templates
5. **Log Export** - Export flashing logs to file
6. **Update Check** - Check for firmware updates from server
7. **Chip Auto-Detection** - Auto-detect connected chip type

## Conclusion

The refactoring is complete! The app now:
- ✅ Uses real bootloaders (not synthetic/fake ones)
- ✅ Has clear Simple/Complete modes (not confusing checkboxes)
- ✅ Properly parses partition tables (not hardcoded guesses)
- ✅ Follows ESP-IDF standards
- ✅ Auto-detects PlatformIO build files
- ✅ Provides device partition inspection
- ✅ Has smart erase options

The architecture is now clean, maintainable, and follows industry best practices.
