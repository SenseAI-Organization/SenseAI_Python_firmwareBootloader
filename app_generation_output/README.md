# Sense ESP32 Flasher

GUI tool for flashing ESP32 firmware, uploading SPIFFS, and debugging devices via UART — no Python installation required.

---

## Running the App

Double-click **`Sense-esp32_flasher.exe`**.

No installation needed. Windows may show a SmartScreen warning on first run — click "More info" → "Run anyway".

---

## Required File Structure

The EXE is self-contained for firmware flashing. For **SPIFFS upload** or **project-specific firmware**, the EXE looks for folders placed **next to it**:

```
Sense-esp32_flasher.exe       ← the app
data/                         ← generic SPIFFS data folder (for "Upload Data Folder")
    spiffs.bin                    (pre-built image, used if mkspiffs is not installed)
    <any other files>             (config files, certs, etc.)
proyect_firmware/             ← project firmware bundles (optional)
    secafe/
        firmware.bin
        bootloader.bin
        partitions.bin
        ota_data_initial.bin
        data/
            spiffs.bin
    flowmeter/
        firmware.bin
        bootloader.bin
        partitions.bin
        data/
    Hermes_sender/
        firmware.bin
        bootloader.bin
        partitions.bin
        data/
```

> The `data/spiffs.bin` bundled inside the EXE is the generic default. If you place a `data/` folder next to the EXE, it takes precedence.

---

## Flashing Firmware

### 1. Connect the ESP32
Plug in via USB. The COM port will appear in the **Port** dropdown. Hit **Refresh** if it doesn't show.

### 2. Select chip type
Default is **ESP32-S3**. Change in the dropdown if using a different variant (ESP32, ESP32-C3, etc.).

### 3. Choose flash mode

| Mode | What it flashes | Use when |
|---|---|---|
| **Simple Mode** | `firmware.bin` only | Quick update, keep bootloader/partitions |
| **Complete Mode** | Bootloader + Partitions + Firmware | First flash or full wipe |

### 4. Select files
Click **Browse** next to each field to pick the `.bin` files.

### 5. Options (Complete Mode)
- **Preserve NVS/WiFi** — skips erasing the NVS partition (keeps saved WiFi credentials)
- **Preserve Bootloader** — skips re-flashing the bootloader

### 6. Flash baud rate
Default is **460800**. Lower it (e.g. 115200) if you get connection errors.

### 7. Click Flash
Progress and esptool output appear in the log panel on the left.

---

## Uploading SPIFFS (Data Folder)

SPIFFS holds the filesystem used by the firmware (config files, web assets, certs, etc.).

1. Place the EXE next to a `data/` folder containing the files you want to upload.
2. Connect to the device and select the port/chip as above.
3. Click **Upload Data Folder (SPIFFS)**.

The app uses a pre-built `spiffs.bin` if present in `data/`. If not found, it will attempt to build one using **mkspiffs** (install via the *Install mkspiffs* button in the tools section).

To **verify** what's on the device's SPIFFS, click **Verificar SPIFFS**.

---

## Serial Monitor & UART Debugger

The right panel provides a live serial terminal and a command sender for debugging devices over UART.

### Connecting
1. Select the **COM port** and **Baud rate** (default 115200) in the Serial Monitor header.
2. Click **Conectar**. Incoming device output appears in the terminal window.

### Sending Commands

The **"Enviar Comando UART"** section (below the terminal) lets you send text commands to the device:

| Control | Description |
|---|---|
| Text field | Type any command and press **Enter** or click **Enviar** |
| **↑ / ↓ arrow keys** | Navigate command history (last sent commands) |
| **Line ending selector** | Choose CRLF, LF, CR, or None — must match what your firmware expects |
| **restart** button | Sends `restart` command |
| **help** button | Sends `help` command |
| **status** button | Sends `status` command |
| **version** button | Sends `version` command |

Sent commands appear in **blue** in the terminal (`> command`). Received data appears in white.

> The serial monitor and the flasher share the same COM port — disconnect the monitor before flashing, or the app will handle it automatically.

---

## Tips

- If the port doesn't appear, check Device Manager — some boards need a CP210x or CH340 driver installed.
- Hold the **BOOT** button on the ESP32 while clicking Flash if the chip doesn't enter download mode automatically.
- Use **Complete Mode** for the first flash on a new board.
- The log panel saves the full session output — scroll up to review past messages.
