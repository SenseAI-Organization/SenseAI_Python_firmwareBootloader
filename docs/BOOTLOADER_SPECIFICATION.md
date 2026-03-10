# Corona SmartFlux - Firmware Bootloader Specification

## Overview

This document specifies the requirements for a firmware bootloader/flasher tool that logs all flashed devices for the Corona SmartFlux project. The tool should maintain a complete audit trail of all devices programmed with firmware, including device identity, configuration, and flash history.

---

## 1. Bootloader Core Functions

### Primary Responsibilities

1. **Device Detection & Identification**
   - Detect connected STM32WLE5 device via ST-Link/J-Link debugger
   - Read device unique ID (96-bit UID stored at address `0x1FFF7590`)
   - Verify device signature matches STM32WLE5JCIx
   - Check current firmware version (if present)

2. **Firmware Flashing**
   - Erase flash memory (full chip or sector-specific)
   - Program binary/hex file to flash memory starting at `0x08000000`
   - Verify written data (CRC32 checksum)
   - Program LoRaWAN credentials to secure element region

3. **Device Provisioning**
   - Generate or assign unique LoRaWAN credentials:
     - **DevEUI** (Device EUI - 64-bit unique identifier)
     - **JoinEUI/AppEUI** (Application/Join Server identifier)
     - **AppKey** (128-bit root encryption key)
     - **NwkKey** (128-bit network root key)
   - Optional: Read DIP switch configuration for product class
   - Optional: Program custom calibration data (flow sensor calibration, ultrasonic offset)

4. **Logging & Tracking**
   - Record every flash operation to persistent JSON database
   - Generate unique device serial number (e.g., `CORONA-FLUX-00001`)
   - Track firmware versions deployed to each device
   - Maintain flash history with timestamps
   - Export reports for production/deployment tracking

5. **Verification & Testing**
   - Perform post-flash verification
   - Optional: Run built-in self-test (BIST) routine
   - Verify LoRaWAN credentials written correctly
   - Check GPIO functionality (LED blink test)

---

## 2. Hardware & Board Configuration

### Target Board Specifications

```json
{
  "board": {
    "name": "Corona SmartFlux",
    "project_name": "Corona_SmartUrinal_LoRaWAN",
    "manufacturer": "Sense AI / Corona",
    "version": "1.2",
    "product_type": "Smart Urinal Controller"
  },
  
  "mcu": {
    "family": "STM32WL",
    "part_number": "STM32WLE5JCI6",
    "full_name": "STM32WLE5JCIx",
    "package": "UFBGA73 (7x7mm, 73-pin BGA)",
    "core": "ARM Cortex-M4",
    "frequency": "48 MHz",
    "flash_size": "256 KB (0x40000)",
    "ram_size": "64 KB (Main) + 32 KB (RAM2)",
    "features": [
      "Sub-GHz Radio (LoRa/FSK)",
      "Built-in LoRaWAN stack",
      "AES-256 encryption",
      "Low-power modes",
      "12-bit ADC",
      "Multiple timers (TIM2, TIM17)"
    ]
  },
  
  "memory_map": {
    "flash_start": "0x08000000",
    "flash_end": "0x0803FFFF",
    "flash_size_bytes": 262144,
    "ram_start": "0x20000000",
    "ram_size_bytes": 65536,
    "ram2_start": "0x10000000",
    "ram2_size_bytes": 32768,
    "lorawan_nvm_address": "0x0803F000",
    "secure_element_region": "0x0803E000 - 0x0803FFFF",
    "unique_id_address": "0x1FFF7590",
    "device_signature_address": "0x1FFF7500"
  },
  
  "clock_configuration": {
    "system_clock": "48 MHz (MSI)",
    "hclk": "48 MHz",
    "apb1": "48 MHz",
    "apb2": "48 MHz",
    "lse": "32.768 kHz (Low Speed External for RTC)",
    "rtc_source": "LSE",
    "radio_clock": "32 MHz TCXO"
  }
}
```

### Debugger Connection

| Interface | Protocol | Pins Required |
|-----------|---------|---------------|
| **ST-Link V2/V3** | SWD (Serial Wire Debug) | SWDIO, SWCLK, GND, VCC (optional) |
| **J-Link** | SWD | SWDIO, SWCLK, GND, RESET, VCC |
| **UART Bootloader** | USART1 | PA9 (TX), PA10 (RX), BOOT0=HIGH |

**Recommended**: ST-Link V3 for production (faster, supports boundary scan)

---

## 3. Flash Configuration Requirements

### Flash Tool Chain

#### Option 1: STM32CubeProgrammer (Recommended)
```bash
# Command-line interface
STM32_Programmer_CLI.exe \
  --connect port=SWD \
  --download Corona_SmartUrinal_LoRaWAN.hex \
  --verify \
  --start 0x08000000
```

**Configuration File**: `flash_config.stldr`
- Interface: SWD
- Speed: 4 MHz (max 8 MHz for STM32WL)
- Reset mode: Hardware reset
- Erase type: Full chip erase (for initial programming)

#### Option 2: OpenOCD
```bash
openocd -f interface/stlink.cfg \
        -f target/stm32wlx.cfg \
        -c "program Corona_SmartUrinal_LoRaWAN.elf verify reset exit"
```

**OpenOCD Config** (`stm32wle5.cfg`):
```tcl
source [find interface/stlink.cfg]
transport select hla_swd
source [find target/stm32wlx.cfg]

# Flash configuration
flash bank $_FLASHNAME stm32l4x 0x08000000 0x40000 0 0 $_TARGETNAME
# Adapter speed
adapter speed 4000

# Reset configuration
reset_config srst_only srst_nogate
```

#### Option 3: Custom Python Script (pyOCD)
```python
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer

# Connect to target
with ConnectHelper.session_with_chosen_probe() as session:
    board = session.board
    target = board.target
    flash = target.memory_map.get_boot_memory()
    
    # Program firmware
    FileProgrammer(session).program("Corona_SmartUrinal_LoRaWAN.hex")
    
    # Read unique ID
    uid = target.read_memory_block8(0x1FFF7590, 12)
    device_id = ':'.join([f'{b:02X}' for b in uid])
    
    # Verify
    target.reset_and_halt()
```

### Flash Parameters

```json
{
  "flash_settings": {
    "algorithm": "STM32WLxx_256.FLM",
    "verify_after_program": true,
    "erase_before_program": true,
    "reset_after_program": true,
    "start_address": "0x08000000",
    "sector_size": 2048,
    "total_sectors": 128,
    "programming_timeout_ms": 30000,
    "connection_speed_khz": 4000,
    "voltage_range": "2.7V - 3.6V"
  }
}
```

---

## 4. Device Logging Structure (JSON Database)

### Device Log Entry Format

Each flashed device must be logged with the following structure:

```json
{
  "device_serial": "CORONA-FLUX-00042",
  "device_uid": "0x1A2B3C4D5E6F7890ABCD",
  "chip_id": "STM32WLE5JCI6",
  "flash_events": [
    {
      "event_id": "FL-00042-001",
      "timestamp": "2026-03-09T14:32:15Z",
      "event_type": "INITIAL_PROGRAMMING",
      "firmware_version": "1.2.0",
      "firmware_file": "Corona_SmartUrinal_LoRaWAN_v1.2.0.hex",
      "firmware_checksum": "CRC32: 0xABCD1234",
      "flash_size_bytes": 245760,
      "flash_duration_seconds": 12.4,
      "programmer_id": "ST-Link-V3-003F00123456",
      "operator": "Juan Perez",
      "status": "SUCCESS",
      "verification": {
        "crc_match": true,
        "memory_test": "PASS",
        "boot_test": "PASS"
      }
    }
  ],
  "lorawan_config": {
    "deveui": "70B3D57ED8004E5B",
    "joineui": "24E124C0002A0001",
    "appkey": "ED1DC3BFBEEFC91EDABE077AC3E460F",
    "nwkkey": "ED1DC3BFBEEFC91EDABE077AC3E460F",
    "region": "US915",
    "class": "A",
    "activation": "OTAA",
    "network_server": "The Things Network",
    "application_name": "corona-smartflux-prod"
  },
  "hardware_config": {
    "product_class": "PURPLE_CLASS",
    "dip_switch_setting": "0b00",
    "flow_sensor_calibration": 450.0,
    "ultrasonic_trimmer_distance_cm": 25,
    "battery_type": "Li-Ion 18650 3.7V",
    "pcb_version": "v2.1",
    "assembly_date": "2026-03-01"
  },
  "production_data": {
    "batch_number": "BATCH-2026-03-001",
    "production_line": "LINE-A",
    "qc_inspector": "Maria Rodriguez",
    "qc_status": "APPROVED",
    "deployment_location": "Hospital Central - Floor 3",
    "deployment_date": "2026-03-15",
    "warranty_expiry": "2028-03-15"
  },
  "device_metadata": {
    "created_at": "2026-03-09T14:32:15Z",
    "updated_at": "2026-03-09T14:45:30Z",
    "first_join_timestamp": "2026-03-09T15:10:22Z",
    "last_seen_timestamp": "2026-03-09T18:30:45Z",
    "total_flash_count": 1,
    "notes": "Initial production unit for Hospital Central deployment"
  }
}
```

### Database File Structure

**Main Database**: `device_flash_log.json`
```json
{
  "database_version": "1.0",
  "created_at": "2026-01-01T00:00:00Z",
  "last_updated": "2026-03-09T18:30:45Z",
  "total_devices": 42,
  "devices": [
    { /* Device entry as shown above */ },
    { /* Device entry 2 */ },
    { /* ... */ }
  ],
  "statistics": {
    "total_flash_events": 47,
    "success_rate": 97.87,
    "average_flash_time_seconds": 13.2,
    "firmware_versions": {
      "1.0.0": 5,
      "1.1.0": 12,
      "1.2.0": 25
    },
    "production_batches": 3,
    "deployment_sites": 8
  }
}
```

**Backup Files**:
- `device_flash_log_backup_YYYY-MM-DD.json` (Daily backups)
- `flash_events_YYYY-MM.json` (Monthly event logs)
- `device_inventory.csv` (CSV export for Excel)

---

## 5. Bootloader Workflow

### Standard Flashing Procedure

```
┌─────────────────────────────────────────────────────────────────┐
│                   BOOTLOADER WORKFLOW                            │
└─────────────────────────────────────────────────────────────────┘

1. DEVICE CONNECTION
   ├─ Detect ST-Link debugger
   ├─ Connect to STM32WLE5 target (SWD protocol)
   ├─ Read chip ID and verify compatibility
   └─ Read 96-bit unique device ID (UID)

2. PRE-FLASH CHECKS
   ├─ Check if device already programmed (read UID from database)
   ├─ If reprogramming: Prompt user for reason
   ├─ Load firmware binary/hex file
   ├─ Verify firmware checksum
   └─ Prompt for LoRaWAN credentials (or auto-generate)

3. DEVICE PROVISIONING
   ├─ Generate/assign Device Serial Number (e.g., CORONA-FLUX-00043)
   ├─ Assign LoRaWAN credentials:
   │  ├─ DevEUI (from UID or custom range)
   │  ├─ JoinEUI/AppEUI (common for all devices or per batch)
   │  ├─ AppKey (randomly generated or from secure key vault)
   │  └─ NwkKey (same as AppKey for LoRaWAN 1.0.x)
   └─ Record DIP switch configuration (if readable)

4. FLASH PROGRAMMING
   ├─ Erase flash sectors (0x08000000 - 0x0803FFFF)
   ├─ Program firmware binary
   ├─ Program LoRaWAN NVM context (0x0803F000)
   ├─ Write secure element keys (se-identity region)
   └─ Progress bar: [██████░░░░] 60% (15.2s elapsed)

5. VERIFICATION
   ├─ Read back flash memory (CRC32 checksum)
   ├─ Compare with original firmware file
   ├─ Verify LoRaWAN credentials readable
   └─ Optional: Perform LED blink test (GPIO test)

6. POST-FLASH ACTIONS
   ├─ Reset MCU and halt
   ├─ Read reset vector and verify boot
   ├─ Optional: Connect UART console for debug output
   └─ Optional: Trigger first LoRaWAN join attempt

7. DATABASE LOGGING
   ├─ Create/update device entry in JSON database
   ├─ Add flash event record with timestamp
   ├─ Backup database to dated file
   ├─ Export CSV report for batch
   └─ Print QR code label (contains DevEUI + Serial Number)

8. COMPLETION
   ├─ Display summary:
   │  ├─ Device Serial: CORONA-FLUX-00043
   │  ├─ DevEUI: 70B3D57ED8004E5B
   │  ├─ Firmware: v1.2.0
   │  ├─ Flash Time: 12.8 seconds
   │  └─ Status: ✓ SUCCESS
   ├─ Disconnect debugger
   └─ Ready for next device
```

---

## 6. Configuration Files Needed

### 1. `bootloader_config.json`
```json
{
  "bootloader_version": "2.0.1",
  "target_board": "STM32WLE5JCIx",
  "debugger": {
    "type": "ST-Link",
    "interface": "SWD",
    "speed_khz": 4000,
    "reset_mode": "hardware"
  },
  "firmware": {
    "default_path": "./firmware/Corona_SmartUrinal_LoRaWAN.hex",
    "verify_checksum": true,
    "backup_old_firmware": true
  },
  "lorawan": {
    "network_server": "The Things Network",
    "region": "US915",
    "join_eui": "24E124C0002A0001",
    "deveui_mode": "auto_from_uid",
    "appkey_mode": "generate_random",
    "key_vault_path": "./keys/secure_vault.enc"
  },
  "logging": {
    "database_path": "./logs/device_flash_log.json",
    "backup_enabled": true,
    "backup_interval_hours": 24,
    "csv_export_enabled": true,
    "verbose_logging": true
  },
  "production": {
    "serial_number_prefix": "CORONA-FLUX-",
    "starting_serial": 1,
    "batch_mode": true,
    "qr_code_generation": true,
    "quality_check_required": true
  }
}
```

### 2. `flash_template.json` (Per-device template)
```json
{
  "device_serial": "",
  "device_uid": "",
  "chip_id": "STM32WLE5JCI6",
  "flash_events": [],
  "lorawan_config": {
    "deveui": "",
    "joineui": "24E124C0002A0001",
    "appkey": "",
    "nwkkey": "",
    "region": "US915",
    "class": "A",
    "activation": "OTAA"
  },
  "hardware_config": {
    "product_class": "",
    "flow_sensor_calibration": 450.0,
    "ultrasonic_trimmer_distance_cm": 25
  },
  "production_data": {
    "batch_number": "",
    "production_line": "",
    "qc_status": "PENDING"
  }
}
```

### 3. `se-identity_template.h` (Generated per device)
```c
// Auto-generated by bootloader for device: CORONA-FLUX-00043
// Generated: 2026-03-09 14:32:15 UTC

#define LORAWAN_DEVICE_EUI    70,B3,D5,7E,D8,00,4E,5B
#define LORAWAN_JOIN_EUI      24,E1,24,C0,00,2A,00,01
#define LORAWAN_APP_KEY       ED,1D,C3,BF,BE,EE,FC,91,ED,AB,E0,77,AC,3E,46,0F
#define LORAWAN_NWK_KEY       ED,1D,C3,BF,BE,EE,FC,91,ED,AB,E0,77,AC,3E,46,0F
#define LORAWAN_DEVICE_ADDRESS   27,00,CE,B8
#define LORAWAN_NWK_S_KEY     ED,1D,C3,BF,BE,EE,FC,91,ED,AB,E0,77,AC,3E,46,0F
#define LORAWAN_APP_S_KEY     ED,1D,C3,BF,BE,EE,FC,91,ED,AB,E0,77,AC,3E,46,0F
```

---

## 7. Implementation Recommendations

### Technology Stack

**Desktop Application** (Recommended):
- **Language**: Python 3.9+
- **GUI Framework**: PyQt5 or Tkinter
- **Flash Library**: pyOCD or stlink-python
- **Database**: JSON files (lightweight, human-readable)
- **Barcode/QR**: python-qrcode, python-barcode

**Alternative: Web-Based**:
- **Frontend**: React + Electron (for local hardware access)
- **Backend**: Node.js + Express
- **Flash Bridge**: Custom USB bridge via serialport

### Key Libraries

```python
# requirements.txt
pyocd>=0.35.1          # Programming interface
pyserial>=3.5          # Serial communication
pyyaml>=6.0            # Config file parsing
qrcode>=7.4            # QR code generation
reportlab>=4.0         # PDF report generation
pandas>=2.0            # CSV export
cryptography>=41.0     # Key encryption
```

### Security Considerations

1. **Key Storage**: Encrypt AppKey/NwkKey in key vault (AES-256)
2. **Access Control**: Require operator authentication
3. **Audit Trail**: Log all flash operations (who, when, what)
4. **Backup**: Automatic daily backups to network drive
5. **Key Rotation**: Support for key rotation policies

---

## 8. Example Bootloader UI Design

```
╔════════════════════════════════════════════════════════════════╗
║      Corona SmartFlux - Production Bootloader v2.0.1          ║
╚════════════════════════════════════════════════════════════════╝

┌────────────────────────────────────────────────────────────────┐
│ DEVICE STATUS                                                  │
├────────────────────────────────────────────────────────────────┤
│ Debugger:  [●] ST-Link V3 Connected (Serial: 003F00123456)   │
│ Target:    [●] STM32WLE5JCI6 Detected                        │
│ UID:       0x1A2B3C4D5E6F7890ABCD                            │
│ Status:    Ready for programming                              │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ FIRMWARE CONFIGURATION                                         │
├────────────────────────────────────────────────────────────────┤
│ Firmware:  [Corona_SmartUrinal_v1.2.0.hex ▼] [Browse...]     │
│ Version:   1.2.0                     Size: 240 KB             │
│ Checksum:  CRC32: 0xABCD1234         Date: 2026-03-09         │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ LORAWAN PROVISIONING                                           │
├────────────────────────────────────────────────────────────────┤
│ Serial #:  CORONA-FLUX-00043                                   │
│ DevEUI:    [Auto-generate from UID    ▼]                      │
│            70-B3-D5-7E-D8-00-4E-5B                             │
│ JoinEUI:   24-E1-24-C0-00-2A-00-01                             │
│ AppKey:    [Generate Random            ▼] [Show Key]          │
│ Region:    [US915 ▼]  Class: [A ▼]  Mode: [OTAA ▼]           │
│                                                                 │
│ Product:   [Purple Class (450 cal) ▼]                          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ PRODUCTION DATA                                                │
├────────────────────────────────────────────────────────────────┤
│ Batch:     BATCH-2026-03-001                                   │
│ Operator:  [Juan Perez              ▼]                         │
│ Line:      [LINE-A ▼]    Date: 2026-03-09                     │
│ Notes:     [Initial production run for Hospital Central...]    │
└────────────────────────────────────────────────────────────────┘

          [  🔥 PROGRAM DEVICE  ]    [  📋 VIEW LOG  ]

┌────────────────────────────────────────────────────────────────┐
│ PROGRESS                                                       │
├────────────────────────────────────────────────────────────────┤
│ [████████████████████████████░░] 87% - Verifying (11.2s)      │
│                                                                 │
│ ✓ Device connected                                             │
│ ✓ Firmware loaded and verified                                │
│ ✓ Flash erased                                                 │
│ ✓ Programming complete (210,432 bytes)                        │
│ ⏳ Verifying flash contents...                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 9. Quality Control Checklist

After each flash operation, the bootloader should verify:

- [ ] Device UID read successfully
- [ ] Firmware checksum matches expected value
- [ ] Flash verification passed (CRC match)
- [ ] LoRaWAN credentials written and readable
- [ ] Device boots successfully (reset vector valid)
- [ ] Unique serial number assigned
- [ ] Database entry created/updated
- [ ] QR code label generated
- [ ] LED blink test passed (optional)
- [ ] UART console output valid (optional)

---

## 10. Export & Reporting

### Batch Production Report (CSV)

```csv
Serial,UID,DevEUI,FirmwareVersion,FlashDate,FlashTime,Operator,Batch,QC_Status,Notes
CORONA-FLUX-00041,1A2B3C4D5E6F7890ABCD,70B3D57ED8004E5B,1.2.0,2026-03-09T14:30:12Z,12.8s,Juan Perez,BATCH-2026-03-001,PASS,Initial unit
CORONA-FLUX-00042,2B3C4D5E6F7890ABCD12,70B3D57ED8004E5C,1.2.0,2026-03-09T14:35:45Z,13.1s,Juan Perez,BATCH-2026-03-001,PASS,
CORONA-FLUX-00043,3C4D5E6F7890ABCD1234,70B3D57ED8004E5D,1.2.0,2026-03-09T14:40:22Z,12.7s,Juan Perez,BATCH-2026-03-001,PASS,
```

### QR Code Label Content

```
CORONA-FLUX-00043
DevEUI: 70B3D57ED8004E5B
FW: v1.2.0
Date: 2026-03-09
[QR CODE IMAGE]
```

---

## Summary

The firmware bootloader must provide:

1. **Automated device programming** with verification
2. **Complete audit trail** in JSON format
3. **LoRaWAN credential management** (generation/assignment)
4. **Production-ready workflow** (batch mode, QC checks)
5. **Reporting and exports** (CSV, PDF, QR codes)
6. **Security** (encrypted key storage, access control)
7. **Traceability** (unique serial numbers, deployment tracking)

All flashed devices are tracked from production through deployment with complete history.
