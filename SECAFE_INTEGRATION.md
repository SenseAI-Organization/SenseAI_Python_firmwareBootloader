# Secafé Project Integration Guide
## For: SenseAI_Python_firmwareBootloader

**Date:** April 28, 2026  
**Status:** Handoff for implementation  
**Target:** Add support for Secafé project (ESP32-S3 with OTA + SPIFFS)

---

## Quick Summary

The bootloader app currently supports generic ESP32 firmware flashing with Simple Mode (firmware-only at `0x10000`) and Complete Mode (full reflash). To support Secafé, we need to:

1. **Add a project selector** to choose between existing projects (flowmeter, Hermes_sender) and **new Secafé project**
2. **Fix Simple Mode address** for OTA-based projects (Secafé uses `0x50000`, not `0x10000`)
3. **Create `proyect_firmware/secafe/` folder structure** with pre-built binaries
4. **Ensure SPIFFS upload works** for Secafé (already functional if spiffs.bin exists)

---

## Technical Context: Secafé Flash Map

| Component | Address | Size | File |
|-----------|---------|------|------|
| Bootloader (2nd stage) | `0x0` | 20.5 KB | `bootloader.bin` |
| Partition Table | `0x8000` | 3 KB | `partitions.bin` |
| OTA Data (marks app0 active) | `0x49000` | 8 KB | `ota_data_initial.bin` |
| **Firmware (app0/ota_0)** | **`0x50000`** | 1870 KB | **`firmware.bin`** |
| SPIFFS (certs + data) | `0x5F0000` | 1184 KB | **`spiffs.bin`** |
| CoreDump | `0x720000` | 512 KB | — |

**Key difference from generic ESP32:** OTA firmware at `0x50000` (not `0x10000`)

**Partition Table:**
```
nvs,     data, nvs,      0x9000,   256K
otadata, data, ota,      0x49000,  8K
phy,     data, phy,      0x4B000,  4K
app0,    app,  ota_0,    0x50000,  2700K      ← Secafé firmware here
app1,    app,  ota_1,    0x320000, 2700K
spiffs,  data, spiffs,   0x5F0000, 1184K
coredump,data, coredump, 0x720000, 512K
```

---

## Required Code Changes

### 1. **Add Project Selector to UI** (`setup_main_content` method)

Add a new dropdown/selector **above** the current "Modo de Flasheo" section:

```python
# === PROJECT SELECTOR === (NEW - add near line 250)
project_frame = ttk.LabelFrame(main_frame, text="Proyecto", padding="5")
project_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=3, padx=5)
project_frame.columnconfigure(1, weight=1)

ttk.Label(project_frame, text="Seleccionar Proyecto:", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)

self.selected_project = tk.StringVar(value="generic")
self.project_combo = ttk.Combobox(project_frame, textvariable=self.selected_project, 
                                   state="readonly", width=30)
self.project_combo['values'] = ['generic', 'flowmeter', 'hermes_sender', 'secafe']
self.project_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
self.project_combo.bind('<<ComboboxSelected>>', self.on_project_change)

ttk.Label(project_frame, text="   📁 Carga automáticamente archivos del proyecto seleccionado", 
         foreground="gray", font=('Arial', 8)).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=20)
```

**In `__init__`**, add the project selector variable:
```python
self.selected_project = tk.StringVar(value="generic")
```

---

### 2. **Add Project Change Handler** (NEW method)

Add this method to the `ESP32Flasher` class:

```python
def on_project_change(self):
    """Handle project selection change - auto-load project files"""
    project = self.selected_project.get()
    
    if project == "generic":
        # Generic mode - user selects files manually
        self.log("Modo genérico - selecciona archivos manualmente", "info")
        self.firmware_path = None
        self.bootloader_path = None
        self.partitions_path = None
        self.firmware_label.config(text="No seleccionado", foreground="gray")
        self.bootloader_label.config(text="No requerido (Simple Mode)", foreground="gray")
        self.partitions_label.config(text="No requerido (Simple Mode)", foreground="gray")
        
    else:
        # Project-specific folder
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.join(script_dir, "proyect_firmware", project)
        
        if not os.path.exists(project_dir):
            messagebox.showwarning("Proyecto no encontrado", 
                f"Carpeta de proyecto no existe:\n{project_dir}")
            self.selected_project.set("generic")
            return
        
        # Try to load project files
        fw = os.path.join(project_dir, "firmware.bin")
        bl = os.path.join(project_dir, "bootloader.bin")
        pt = os.path.join(project_dir, "partitions.bin")
        
        if os.path.exists(fw):
            self.firmware_path = fw
            self.firmware_label.config(text=f"✓ {project} firmware", foreground="green")
            self.log(f"Firmware del proyecto '{project}' cargado", "success")
        
        if os.path.exists(bl):
            self.bootloader_path = bl
            self.bootloader_label.config(text=f"✓ {project} bootloader", foreground="green")
        
        if os.path.exists(pt):
            self.partitions_path = pt
            self.partitions_label.config(text=f"✓ {project} partitions", foreground="green")
        
        # Log project info
        self.log(f"Proyecto '{project}' cargado desde: {project_dir}", "info")
        
        # Hint for Secafé
        if project == "secafe":
            self.log("ℹ️ Secafé usa OTA (firmware @ 0x50000) - se detectará automáticamente", "info")
            self.log("ℹ️ Se recomienda usar Complete Mode para full flash", "info")
```

---

### 3. **Fix Simple Mode Address for OTA Projects**

**Current issue:** `get_firmware_address_simple()` returns hardcoded `"0x10000"`, which breaks Secafé.

**Solution:** Make Simple Mode read from partition table if available, or use project-aware logic.

```python
def get_firmware_address_simple(self):
    """Determine firmware flash address for simple mode"""
    project = self.selected_project.get()
    
    # Project-specific addresses
    project_addresses = {
        "secafe": "0x50000",       # OTA app0
        "flowmeter": "0x10000",    # Legacy
        "hermes_sender": "0x10000" # Legacy
    }
    
    if project in project_addresses:
        addr = project_addresses[project]
        self.log(f"💡 Simple Mode: Usando dirección {addr} para {project}", "info")
        return addr
    
    # For generic mode, try to detect from partition table
    if self.partitions_path and os.path.exists(self.partitions_path):
        try:
            app_addr, _ = self.parse_partition_table_file(self.partitions_path)
            if app_addr and app_addr != "0x10000":
                self.log(f"💡 Simple Mode: Dirección detectada desde tabla: {app_addr}", "info")
                return app_addr
        except:
            pass
    
    # Default fallback
    self.log("💡 Simple Mode: Usando dirección por defecto 0x10000", "info")
    return "0x10000"
```

---

### 4. **Create `proyect_firmware/secafe/` Folder Structure**

**Directory layout:**
```
proyect_firmware/
├── flowmeter/
│   ├── firmware.bin
│   ├── bootloader.bin
│   ├── partitions.bin
│   ├── partitions.csv
│   ├── ota_data_initial.bin
│   └── data/
│       └── (data files if any)
│
├── hermes_sender/
│   └── (similar structure)
│
└── secafe/                    ← NEW
    ├── firmware.bin           (1870 KB)
    ├── bootloader.bin         (20.5 KB)
    ├── partitions.bin         (3 KB)
    ├── partitions.csv         (metadata)
    ├── ota_data_initial.bin   (8 KB)
    └── data/
        └── spiffs.bin         (1184 KB) ← Contains Client.pem, KEY1.pem, Server1.pem
```

**Files to copy from Secafé firmware project:**
- Source: `Innovakit_SecafeIDF/.pio/build/esp32-s3-devkitc-1/`
- Files: `firmware.bin`, `bootloader.bin`, `partitions.bin`, `ota_data_initial.bin`, `spiffs.bin`
- Also: `Innovakit_SecafeIDF/partitions/partitions.csv`

**Data folder note:** The `data/spiffs.bin` contains the pre-built SPIFFS image with all certificates embedded. No need to store individual `.pem` files.

---

### 5. **SPIFFS Upload (Already Works - No Changes Needed)**

The existing `_upload_data_thread()` method already:
- ✅ Reads `data/spiffs.bin` (pre-built)
- ✅ Auto-detects SPIFFS partition offset from device partition table
- ✅ Flashes to correct address (`0x5F0000` for Secafé)

Just verify that when user selects "secafe" project, the `data/spiffs.bin` exists.

---

## Implementation Workflow for Secafé

### Recommended Flash Procedure (for users):

1. **Select Project:** Dropdown → choose "secafe"
2. **Select Mode:** Complete Mode (required for OTA support)
3. **Connect device:** ESP32-S3 via USB
4. **Flash:** Click "FLASHEAR FIRMWARE"
   - Bootloader → `0x0`
   - Partitions → `0x8000`
   - OTA Data → `0x49000`
   - Firmware → `0x50000` ✓ (auto-detected from partition table)
5. **Upload SPIFFS:** Click "📤 Upload Data Folder (SPIFFS)"
   - Auto-detects SPIFFS at `0x5F0000`
   - Flashes `data/spiffs.bin`
   - Verifies data is present

**Simple Mode (NOT recommended for Secafé, but if user insists):**
- Will use `0x50000` (correct address)
- Preserves bootloader + partitions + NVS
- ⚠️ Only updates firmware, leaves SPIFFS as-is

---

## Migration Notes

### Existing Projects (flowmeter, Hermes_sender):
- No changes needed — they use legacy `0x10000` address
- Will continue to work in both Simple and Complete Mode

### New Secafé Project:
- Uses OTA at `0x50000`
- **Must use Complete Mode for initial flash** (needs all components)
- Simple Mode works for firmware-only updates (preserves everything)
- SPIFFS upload handled separately

### Address Mapping Summary:
| Project | Simple Mode | Complete Mode | OTA? |
|---------|-----------|---------------|------|
| generic | `0x10000` | Auto-detect | No |
| flowmeter | `0x10000` | `0x10000` | No |
| hermes_sender | `0x10000` | `0x10000` | No |
| **secafe** | **`0x50000`** | **`0x50000`** ✓ | **Yes** |

---

## Testing Checklist

- [ ] Project dropdown appears above "Modo de Flasheo"
- [ ] Selecting "secafe" loads firmware/bootloader/partitions from `proyect_firmware/secafe/`
- [ ] Simple Mode shows "💡 Simple Mode: Usando dirección 0x50000 para secafe"
- [ ] Complete Mode reads partition table and detects firmware at `0x50000`
- [ ] SPIFFS upload detects SPIFFS partition at `0x5F0000`
- [ ] Initial Complete Mode flash completes successfully
- [ ] Firmware updates via Simple Mode preserve everything
- [ ] SPIFFS data uploads and verifies correctly

---

## Files to Update

1. **firmwareBootLoader.py** (main app)
   - Add project selector UI (row 0)
   - Shift existing rows down
   - Add `on_project_change()` method
   - Update `get_firmware_address_simple()` method
   - Add `self.selected_project` in `__init__`

2. **proyect_firmware/secafe/** (NEW FOLDER)
   - Copy all 5 binaries + spiffs.bin + partitions.csv

3. **README.md** (optional, user-facing docs)
   - Document Secafé project, flash procedure, OTA support

---

## Questions for Implementation

- Should Simple Mode warn user if they select Secafé but try to flash at `0x10000`?
- Should "Secafe" project auto-enable Complete Mode (disable Simple Mode)?
- Do you want a "⚠️ OTA Project" label to warn users about addressing?

---

**Generated:** 2026-04-28  
**For:** SenseAI_Python_firmwareBootloader Agent  
**Ready for:** Implementation in `firmwareBootLoader.py`
