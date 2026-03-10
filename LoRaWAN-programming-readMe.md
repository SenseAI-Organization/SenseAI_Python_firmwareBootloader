# LoRaWAN Device Programming Guide

Production tool for flashing STM32WLE5JCI6 (Corona SmartFlux) devices via SWD, capturing LoRaWAN credentials over serial, and exporting them for batch LNS registration.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.10+ |
| **STM32CubeProgrammer** | Installed and on PATH (`STM32_Programmer_CLI`) |
| **ST-Link V3** | Connected via USB with SWD wiring to the target board |
| **Serial adapter** | ST-Link VCP or USB-UART on USART2 TX (PA2), 115200 baud |
| **Firmware file** | `.hex`, `.bin`, or `.elf` placed in the `firmware/` folder |

## 1 — Install Dependencies

```bash
# Activate the virtual environment (recommended)
cd app_generation
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell

# Install packages
pip install -r requirements.txt
```

Required packages: `pyserial`, `pyinstaller`, `qrcode`, `reportlab`, `pandas`, `cryptography`.

## 2 — Hardware Setup

1. Connect the **ST-Link V3** to the target STM32WLE5 board via SWD (SWDIO, SWCLK, GND, 3V3).
2. Connect the **serial/VCP adapter** to USART2 TX (PA2) at **115200 8N1**. This is the line the device uses to print its credentials after boot.
3. Power the target board (ST-Link can supply 3.3 V if jumpered).

## 3 — Launch the App

```bash
python stm32_bootloader.py
```

The GUI opens with three main areas:

- **Left panel** — Firmware selection, COM port / baud rate, product class, inspector dropdown.
- **Center panel** — Programming log and progress bar.
- **Right panel** — Last-programmed device info (DevEUI, AppKey, serial number).

## 4 — Programming Workflow (per device)

1. **Select firmware** — Browse or use the default `firmware/Corona_SmartUrinal_LoRaWAN.hex`.
2. **Select COM port** — Pick the serial port connected to USART2. Click ↻ to refresh the list.
3. **Select product class** — PURPLE / GREEN / BLUE / WHITE (sets calibration factor).
4. **Click "Program Device"** — The tool runs these steps automatically:

| Step | Action |
|---|---|
| 1 | Connect to ST-Link via SWD, read 96-bit UID |
| 2 | Check device database for duplicates |
| 3 | Erase flash (full chip) |
| 4 | Program firmware + verify |
| 5 | Reset device → capture serial output (DevEUI, JoinEUI, AppKey, DevAddr, FW version) |
| 6 | Build LoRaWAN config from captured data |
| 7 | Log device to JSON database |

5. **Verify on-screen** — DevEUI and AppKey are displayed on the right panel. The log shows all captured credentials.

## 5 — Serial Credential Capture

After programming and reset, the firmware prints its credentials 3× over USART2:

```
DEVEUI:70B3D57ED8004E5B
JOINEUI:24E124C0002A0001
APPKEY:ED1DC3BFBEEFC91EDABE077AC3E460F0
DEVADDR:00000000
FW:1.2
---
```

The tool captures the first complete block (terminated by `---`) and extracts DevEUI, JoinEUI, AppKey, DevAddr, and firmware version. If serial capture fails, DevEUI falls back to a UID-derived value and AppKey is marked as missing.

## 6 — Device Database

Every programmed device is saved to `logs/device_flash_log.json` with:

- **Device UID** (96-bit from STM32)
- **Serial number** (auto-incrementing: `CORONA-FLUX-00001`, `00002`, …)
- **LoRaWAN credentials** (DevEUI, JoinEUI, AppKey, DevAddr)
- **Product class** and calibration factor
- **Flash events** (timestamp, firmware file, firmware version, inspector, result)

Re-flashing the same device appends a new flash event to the existing record — credentials are preserved.

## 7 — Export for LNS Registration

Use **File → Export** in the GUI to generate batch-import files:

| Format | File | Use |
|---|---|---|
| TTN JSON | `exports/ttn_devices.json` | The Things Network bulk import |
| TTN CSV | `exports/ttn_devices.csv` | TTN spreadsheet import |
| ChirpStack JSON | `exports/chirpstack_devices.json` | ChirpStack bulk import |
| Inventory CSV | `exports/inventory.csv` | Internal tracking (serial, UID, class, all credentials) |

All exports pull from the device database so they always reflect the latest data.

## 8 — Configuration

Runtime settings are in `bootloader_config.json`:

- `flash_settings` — SWD speed, erase type, verify, retry count
- `serial_capture` — baud rate, timeout, regex patterns for parsing
- `lorawan` — JoinEUI, region (US915), network server
- `serial_number` — prefix and starting number
- `product_classes` — calibration factors per DIP switch setting
- `production` — batch size, inspector list, post-flash tests

## Quick Checklist (per batch)

- [ ] ST-Link connected and powered
- [ ] Serial/VCP cable on USART2 TX
- [ ] Correct firmware `.hex` selected
- [ ] Correct product class selected
- [ ] Inspector name chosen
- [ ] Program each device → green checkmark in log
- [ ] After batch: **File → Export** → upload to TTN / ChirpStack
