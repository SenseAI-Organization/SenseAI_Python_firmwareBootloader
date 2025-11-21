# 📁 Where to Add Files for SPIFFS Upload

## Quick Start
**Add your files to the `data/` folder, then click "Upload Data Folder (SPIFFS)" button.**

```
data/
├── hermesTestClientCert.pem      ← Your files go here
├── hermesTestClientKey.pem
├── hermesTestServerCert.pem
└── ... (add any other files here)
```

## ✅ File Location Checklist

- [ ] Files are in the **`data/`** folder (not `test_data`, not root)
- [ ] Folder name is exactly **`data`** (lowercase)
- [ ] Files are directly in `data/`, not in subfolders
- [ ] Filenames have no spaces (use `my_file.pem` not `my file.pem`)

## 🚀 How to Add Files

### Step 1: Prepare Your Files
- Get your certificate/data files ready
- Rename if needed (lowercase, no spaces)

### Step 2: Copy to data/ Folder
```
Copy your files to:
📁 SenseAI_Python_firmwareBootloader/data/
```

### Step 3: Upload to Device
1. Start the app: `python firmwareBootLoader.py`
2. Select COM port
3. Click **"Upload Data Folder (SPIFFS)"** button
4. Confirm the upload

### Step 4: Verify on Device
Check device serial monitor for:
```
I (25566) awsHandler: SPIFFS mounted successfully
I (25566) SPIFFS: File: yourfile.pem
```

## 📝 Examples

### Adding a Configuration File
```
data/
├── hermesTestClientCert.pem
├── hermesTestClientKey.pem
├── hermesTestServerCert.pem
└── config.json                    ← Add your config here
```

### Adding Multiple Files
```
data/
├── hermesTestClientCert.pem
├── hermesTestClientKey.pem
├── hermesTestServerCert.pem
├── root_ca.pem
├── custom_cert.pem
└── settings.txt
```

## ⚠️ Common Mistakes

| ❌ Wrong | ✅ Correct |
|---------|----------|
| `test_data/file.pem` | `data/file.pem` |
| `my file.pem` | `my_file.pem` |
| `Data/file.pem` | `data/file.pem` |
| Nested: `data/certs/file.pem` | Flat: `data/file.pem` |

## 🔧 For Advanced Users: Adding New Files

If the simple "Upload" button doesn't work after adding new files:

1. **Build a new SPIFFS image:**
   ```bash
   mkspiffs -c data -s 1212416 -p 256 -b 4096 spiffs_with_correct_names.bin
   ```

2. **Test it manually:**
   ```bash
   python -m esptool --chip esp32s3 --port COM8 --baud 460800 \
     --before default-reset --after hard-reset write-flash -z \
     --flash-mode dio --flash-freq 40m --flash-size detect \
     0x5F0000 spiffs_with_correct_names.bin
   ```

3. **If device mounts successfully**, the button will now use the new image

See `SPIFFS_USAGE_GUIDE.md` for detailed technical info.

## 📚 Related Files
- `SPIFFS_USAGE_GUIDE.md` - Detailed technical documentation
- `SPIFFS_IMPLEMENTATION.md` - Implementation details
- `spiffs_with_correct_names.bin` - The working SPIFFS image (do not delete)

---
**TL;DR:** Put files in `data/` folder, click button, done! 🎉
