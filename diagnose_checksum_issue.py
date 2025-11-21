#!/usr/bin/env python3
"""
Final diagnostic: Why device mounts but can't find files.

Device successfully formatted and mounted the image.
This means the SPIFFS block structure is valid.

But files aren't accessible from /spiffs/filename
This suggests the object index isn't being read correctly.

This can happen if:
1. The object index (lookup table) is corrupted
2. The index points to wrong offsets
3. The page checksums don't match expected format
"""

import os

with open('spiffs_with_correct_names.bin', 'rb') as f:
    prebuilt = f.read()

with open('spiffs_pio.bin', 'rb') as f:
    pio = f.read()

print('[SPIFFS OBJECT INDEX DIAGNOSTIC]')
print('=' * 70)

# The object index is in the first pages of the SPIFFS partition
# For ESP32: PAGE_SIZE = 256 bytes
# Pages 0-N contain the object lookup table

# The key difference is at offset 0xFC (checksum of the page)
# This offset is (PAGE_SIZE - 4) = 256 - 4 = 252 = 0xFC

print('\n[PAGE CHECKSUMS - The problem area]')
print('=' * 70)

PAGE_SIZE = 256

# Check page 0 checksum
print('\nPage 0 (offset 0x000-0x0FF):')
print(f'  Prebuilt checksum (at 0xFC): {\" \".join(f\"{b:02X}\" for b in prebuilt[0xFC:0x100])}')
print(f'  PlatformIO checksum (at 0xFC): {\" \".join(f\"{b:02X}\" for b in pio[0xFC:0x100])}')

if prebuilt[0xFC:0x100] == pio[0xFC:0x100]:
    print('  ✓ Checksums match')
else:
    print('  ✗ Checksums differ!')
    print()
    print('  This explains why device cant find files:')
    print('  - Device reads page 0 (object index)')
    print('  - Device validates checksum at 0xFC')
    print('  - Checksums dont match')
    print('  - Device rejects index as corrupted')

# Count total checksum differences
print('\n[PAGE CHECKSUM MISMATCHES]')
print('=' * 70)

mismatch_count = 0
mismatch_pages = []

for page_idx in range(0, min(len(prebuilt), len(pio)) // PAGE_SIZE):
    offset = page_idx * PAGE_SIZE + (PAGE_SIZE - 4)  # Last 4 bytes of page
    
    if offset + 4 <= len(prebuilt) and offset + 4 <= len(pio):
        pre_checksum = prebuilt[offset:offset+4]
        pio_checksum = pio[offset:offset+4]
        
        if pre_checksum != pio_checksum:
            mismatch_count += 1
            if len(mismatch_pages) < 10:  # Show first 10
                mismatch_pages.append((page_idx, pre_checksum, pio_checksum))

print(f'Total page mismatches: {mismatch_count}')
if mismatch_pages:
    print('\nFirst 10 mismatches:')
    for page_idx, pre_cs, pio_cs in mismatch_pages:
        print(f'  Page {page_idx}: {\" \".join(f\"{b:02X}\" for b in pre_cs)} → {\" \".join(f\"{b:02X}\" for b in pio_cs)}')

print('\n' + '=' * 70)
print('[ROOT CAUSE]')
print()
print('mkspiffs computes page checksums differently than how they were')
print('computed in the pre-built image.')
print()
print('Since the device device FORMATS the image when mounting,')
print('it recalculates all checksums from scratch.')
print()
print('But the OBJECT INDEX (page 0) might not be properly rebuilt,')
print('causing the device to fail to enumerate files.')
print()
print('[SOLUTION]')
print()
print('The device DID accept the format, which is good!')
print('Now we need to ensure the object index is built correctly.')
print()
print('Options:')
print('1. Flash the image again (device may retry and succeed)')
print('2. Use mkspiffs -u to unpack files and verify')
print('3. Rebuild using tool-mkspiffs@2.230.0 (newer version)')
print('4. Stick with pre-built image (guaranteed to work)')
