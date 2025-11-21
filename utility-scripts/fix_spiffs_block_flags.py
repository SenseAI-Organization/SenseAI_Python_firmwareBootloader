#!/usr/bin/env python3
"""
Fix SPIFFS block status flags in generated image.

PlatformIO builds have the block status flag set (0x01 0x80).
Our mkspiffs builds don't.

We can patch our fresh build to match PlatformIO's format.
"""

import os
import shutil

def fix_spiffs_block_flags(input_file, output_file):
    """
    Patch SPIFFS block flags to match PlatformIO format.
    
    Block 0 should start with 0x01 0x80 (ALLOCATED | DELETED flags).
    """
    
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return False
    
    print(f"[FIX SPIFFS BLOCK FLAGS]")
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print()
    
    # Read entire image
    with open(input_file, 'rb') as f:
        data = bytearray(f.read())
    
    print(f"Original size: {len(data)} bytes")
    print(f"Block 0 header (before): {' '.join(f'{b:02X}' for b in data[0:16])}")
    
    # Patch block 0 flags
    # Change first byte from 0x00 to 0x01 (ALLOCATED flag)
    # Change second byte from 0x00 to 0x80 (DELETED flag)
    if data[0] == 0x00 and data[1] == 0x00:
        data[0] = 0x01
        data[1] = 0x80
        print(f"\n✓ Patched Block 0 flags")
    else:
        print(f"\n⚠ Block 0 already has flags: {data[0]:02X} {data[1]:02X}")
    
    print(f"Block 0 header (after):  {' '.join(f'{b:02X}' for b in data[0:16])}")
    
    # Write patched image
    with open(output_file, 'wb') as f:
        f.write(data)
    
    print(f"\nPatched file written: {output_file}")
    print(f"New size: {os.path.getsize(output_file)} bytes")
    
    return True


# Patch our fresh build
if fix_spiffs_block_flags('spiffs.bin', 'spiffs_patched.bin'):
    print("\n" + "=" * 70)
    print("[NEXT STEPS]")
    print("1. Flash spiffs_patched.bin to device")
    print("2. Check if device mounts SPIFFS successfully")
    print("3. This should match PlatformIO's working format")
