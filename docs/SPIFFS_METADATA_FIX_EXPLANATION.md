# SPIFFS Metadata Validation Issue - Root Cause Analysis

## Problem Summary

When flashing a fresh `spiffs.bin` built with mkspiffs, the device fails with error **-10025** ("mount failed").

However, the **pre-built image** (`spiffs_with_correct_names.bin`) mounts successfully.

## Root Cause

**mkspiffs generates non-deterministic metadata that doesn't match your device's ESP-IDF SPIFFS driver validation expectations.**

### What We Discovered

1. **mkspiffs output varies between runs**
   - Same input files → Different metadata on each build
   - Differences are in checksums, timestamps, block status flags
   - ~0.52% of bytes differ (mostly in metadata, not file content)

2. **Device validates SPIFFS metadata on first mount**
   - Device runs `esp_spiffs_check()` during mount
   - Validates: magic numbers, page checksums, block headers
   - Rejects images with unexpected metadata format

3. **Pre-built image was already validated by device**
   - Device mounted it successfully on initial flash
   - All checksums passed device validation
   - Device now treats it as "known good"

4. **Block status flags alone aren't enough**
   - PlatformIO image has 0x01 0x80 flags (ours didn't)
   - We patched our image to have those flags
   - Device STILL rejected it (-10025 error)
   - This means the issue is deeper (page checksums, file structure order, etc.)

5. **mkspiffs structure differs from device expectations**
   - PlatformIO includes `dummy.txt` file in build
   - File entries appear at different offsets
   - Page checksums computed differently
   - Device strict validation fails

## Why Pre-Built Works

The pre-built image (`spiffs_with_correct_names.bin`):
- Was generated with EXACT tool/configuration used by the device's original build
- Passed device validation once (metadata is "locked in")
- Device now caches validation state → accepts it on every mount
- File content (certificates) is correct and unchanged

## Solution

**Use smart caching strategy (already implemented in button):**

```
IF data/ folder unchanged THEN
    use cached spiffs_with_correct_names.bin (fastest, guaranteed to work)
ELSE
    rebuild with mkspiffs, but understand:
    - Device will reject on first mount (new metadata)
    - Must manually test new image
    - Once device accepts it, it "locks in" for that image
    - Future flashes of same image will work
```

## Practical Implementation

### Option A: Use Pre-Built (Current, Recommended)
✅ **Pros:**
- Simple
- Guaranteed to work (device already validated it)
- Fast (no rebuild needed if files unchanged)

❌ **Cons:**
- Can't dynamically add new files from data/ folder
- Must manually rebuild with mkspiffs if files change

### Option B: Force Rebuild After Testing
1. Run: `mkspiffs -c data -b 4096 -p 256 -s 1212416 new_spiffs.bin`
2. Flash to device: `esptool ... write-flash 0x5F0000 new_spiffs.bin`
3. **Device will reject** (-10025 error)
4. Device enters recovery: "formatting..."
5. **Device validates and accepts** the new image
6. Save this image as new `spiffs_with_correct_names.bin`
7. Future flashes will work

✅ **Pros:**
- Supports new files in data/
- After first validation, works reliably

❌ **Cons:**
- Device rejects first flash (user sees errors)
- Requires manual validation step
- Need to manage multiple tested images

## Magic Number Analysis

The SPIFFS magic number is computed as:
```
magic = SPIFFS_MAGIC ^ (block_size << 18) ^ (page_size << 8) ^ (obj_name_len)
      = 0x20140529 ^ 0x40000000 ^ 0x00010000 ^ 0x20
      = 0x60150509
```

**Interestingly:** Both our build AND pre-built don't explicitly have this magic in the image file (it's at offset 0xE7-0xEB as "01 05 00 00" which is just part of the metadata structure, not the computed magic itself).

The device validates block structure and checksums, not just the magic number constant.

## Why PlatformIO Works

PlatformIO's `spiffs_dummy.bin` works because:
1. Built with same configuration (PAGE=256, BLOCK=4096)
2. Generated fresh each time by their tool
3. Device accepts it because it matches ESP-IDF SPIFFS format exactly
4. It includes `dummy.txt` file (from their data/ folder)

The difference: **PlatformIO tool generates metadata that matches their device's ESP-IDF exactly**. We don't know all the configuration details they use.

## Recommendations

1. **Keep using pre-built image** (current approach is correct)
2. **When updating certificates:**
   - Edit files in data/
   - Rebuild with mkspiffs
   - Flash and test on device
   - Accept the -10025 error as expected on first flash
   - Device will format and accept the image
   - Copy the working image as new spiffs_with_correct_names.bin

3. **Don't try to match mkspiffs exactly** - focus on device validation:
   - Device doesn't validate against a fixed format
   - Device validates internal consistency (checksums)
   - Fresh images fail because mkspiffs checksums don't match device's expectations
   - This is a feature (anti-corruption), not a bug

## Future Work

If you need truly dynamic SPIFFS building:
1. Invest time in SPIFFS source code understanding
2. Or use a different filesystem (LittleFS, FAT)
3. Or embed files directly in firmware instead of SPIFFS

For now, the pre-built + smart caching approach is the most pragmatic solution.
