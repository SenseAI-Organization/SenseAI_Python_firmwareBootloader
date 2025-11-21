# Quick Reference: How to Add Files to SPIFFS

## TL;DR - 3 Steps

1. **Put files in `data/` folder**
   ```
   data/
   ├── hermesTestClientCert.pem
   ├── hermesTestClientKey.pem
   ├── hermesTestServerCert.pem
   └── your_file.pem  ← Add here
   ```

2. **Start the app**
   ```bash
   python firmwareBootLoader.py
   ```

3. **Click "Upload Data Folder (SPIFFS)"**
   - Select COM port first
   - Click the button
   - Device gets your files

---

## File Location Reference

| ❌ Wrong | ✅ Correct |
|---------|-----------|
| `C:\...\firmware\file.pem` | `C:\...\data\file.pem` |
| `C:\...\test_data\file.pem` | `C:\...\data\file.pem` |
| `C:\...\Data\file.pem` | `C:\...\data\file.pem` (lowercase!) |

## On Device

After upload, your files appear as:
```
/spiffs/your_file.pem      ← Full path
/your_file.pem             ← Path in SPIFFS image
```

Your firmware code accesses them with `/spiffs/` prefix:
```cpp
fopen("/spiffs/your_file.pem", "r")  // Correct
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Button grayed out | Select COM port first |
| Can't find button | Scroll down in app window |
| Device shows error | Check file is in `data/` folder |
| Device can't mount | Try again - device may need reboot |

## For More Details
- See `DATA_FOLDER_GUIDE.md` for comprehensive guide
- See `README.md` for app overview
- See `SPIFFS_USAGE_GUIDE.md` for technical details

---
**File Location:** `data/` folder (same level as README.md)
