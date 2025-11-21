# 📍 WHERE TO PUT YOUR FILES - Visual Guide

## The Answer: `data/` Folder

```
Your Computer
│
└── 📁 SenseAI_Python_firmwareBootloader/
    ├── 📄 firmwareBootLoader.py         ← The app
    ├── 📄 README.md
    ├── 📄 QUICK_START.md
    ├── 📄 DATA_FOLDER_GUIDE.md
    │
    ├── 📁 data/                         ← 👈 YOUR FILES GO HERE
    │   ├── 📄 hermesTestClientCert.pem
    │   ├── 📄 hermesTestClientKey.pem
    │   ├── 📄 hermesTestServerCert.pem
    │   └── 📄 your_file.pem             ← Add your file here
    │
    ├── 📁 firmware/                     ← Not this folder!
    │   └── (firmware .bin files)
    │
    ├── 📁 proyect_firmware/
    ├── 📁 .git/
    └── ... other files
```

## ⚡ How to Add a File

### Step 1: Get Your File
- Save or download your file
- Example: `config.json`, `mycert.pem`, `settings.txt`

### Step 2: Copy to `data/` Folder
- Open Windows Explorer
- Navigate to: `C:\Users\YourName\Desktop\SenseAI\LibreriasSense\SenseAI_Python_firmwareBootloader\`
- Find the `data` folder
- Copy your file inside

### Step 3: File Should Look Like This
```
📁 data
├── 📄 hermesTestClientCert.pem
├── 📄 hermesTestClientKey.pem
├── 📄 hermesTestServerCert.pem
└── 📄 your_file.pem              ← Your file is here now
```

### Step 4: Upload to Device
1. Open app: `python firmwareBootLoader.py`
2. Select COM port
3. Click "Upload Data Folder (SPIFFS)"
4. Done! ✅

## ❌ WRONG Places

```
❌ Do NOT put files here:
   - 📁 firmware/
   - 📁 proyect_firmware/
   - 📁 test_data/
   - Root directory (alongside README.md)

❌ Do NOT put in subfolders:
   - 📁 data/subfolder/file.pem  (wrong!)
   - 📁 data/certs/file.pem      (wrong!)
   - 📁 data/myfiles/file.pem    (wrong!)

   Instead: 📁 data/file.pem     (correct!)
```

## 🎯 The Rule

**All files must be DIRECTLY in the `data/` folder, nowhere else.**

```
✅ CORRECT:    data/file.pem
❌ WRONG:      data/subfolder/file.pem
❌ WRONG:      firmware/file.pem
❌ WRONG:      file.pem (in root)
```

## 📝 Filename Rules

- ✅ `mycert.pem` - good
- ✅ `config_v2.txt` - good
- ✅ `ca_bundle.crt` - good
- ❌ `My Certificate.pem` - spaces not allowed
- ❌ `FILE.PEM` - uppercase OK but use lowercase
- ❌ `file@#$.txt` - special chars not allowed

**Best practice:** Use lowercase, no spaces, no special characters.
Examples: `root_ca.pem`, `device_config.json`, `settings.txt`

## 🔍 How to Verify

Windows Explorer path should show:
```
C:\Users\YourName\Desktop\SenseAI\LibreriasSense\SenseAI_Python_firmwareBootloader\data\your_file.pem
                                                                                      ^^^^
                                                                      This part shows the data folder
```

Or in PowerShell:
```powershell
PS> dir .\data\
    Mode Name
    ---- ----
    -a-- hermesTestClientCert.pem
    -a-- hermesTestClientKey.pem
    -a-- hermesTestServerCert.pem
    -a-- your_file.pem            ← Your file listed here ✅
```

## 🚀 After Upload

Files appear on device at:
```cpp
/spiffs/hermesTestClientCert.pem  ← original file
/spiffs/hermesTestClientKey.pem   ← original file
/spiffs/hermesTestServerCert.pem  ← original file
/spiffs/your_file.pem             ← YOUR FILE ✨
```

Firmware code:
```cpp
FILE* f = fopen("/spiffs/your_file.pem", "r");  // Works! ✅
```

---

## Still Confused?

1. Open the `data/` folder in Windows Explorer
2. Your file should be visible next to the three `.pem` files
3. If not, it's in the wrong place!

**Folder location:** Same level as `README.md` and `firmwareBootLoader.py`
