#!/usr/bin/env python3
"""
Check SPIFFS magic numbers in generated images.

SPIFFS magic is computed as:
  magic = SPIFFS_MAGIC ^ (block_size << 18) ^ (page_size << 8) ^ (name_length)

Where:
  SPIFFS_MAGIC = 0x20140529
  SPIFFS_MAGIC_LEN = 0x20150115
"""

import os

# SPIFFS constants from source
SPIFFS_MAGIC = 0x20140529
SPIFFS_MAGIC_LEN = 0x20150115

# ESP32 parameters
BLOCK_SIZE = 4096
PAGE_SIZE = 256
OBJ_NAME_LEN = 32

# Calculate magic number
magic = SPIFFS_MAGIC ^ (BLOCK_SIZE << 18) ^ (PAGE_SIZE << 8) ^ OBJ_NAME_LEN

print("[SPIFFS MAGIC NUMBER CALCULATION]")
print("=" * 70)
print(f"SPIFFS_MAGIC:     0x{SPIFFS_MAGIC:08X}")
print(f"SPIFFS_MAGIC_LEN: 0x{SPIFFS_MAGIC_LEN:08X}")
print()
print("[CONFIGURATION]")
print(f"block_size:       {BLOCK_SIZE} (0x{BLOCK_SIZE:X})")
print(f"page_size:        {PAGE_SIZE} (0x{PAGE_SIZE:X})")
print(f"obj_name_length:  {OBJ_NAME_LEN} (0x{OBJ_NAME_LEN:X})")
print()
print("[FORMULA]")
print(f"magic = SPIFFS_MAGIC")
print(f"      ^ (block_size << 18)")
print(f"      ^ (page_size << 8)")
print(f"      ^ (obj_name_len)")
print()
print(f"magic = 0x{SPIFFS_MAGIC:08X}")
print(f"      ^ (0x{BLOCK_SIZE:X} << 18) = 0x{(BLOCK_SIZE << 18):08X}")
print(f"      ^ (0x{PAGE_SIZE:X} << 8)  = 0x{(PAGE_SIZE << 8):08X}")
print(f"      ^ 0x{OBJ_NAME_LEN:02X}")
print()
print("[RESULT]")
print(f"Computed magic:   0x{magic:08X}")
print(f"As 4 bytes (LE):  {' '.join(f'{(magic >> (i*8)) & 0xFF:02X}' for i in range(4))}")
print(f"As 4 bytes (BE):  {' '.join(f'{(magic >> ((3-i)*8)) & 0xFF:02X}' for i in range(4))}")
print()

# Now check our images for this magic number
print("[CHECKING IMAGES FOR MAGIC NUMBERS]")
print("=" * 70)


def find_magic_in_file(filename, magic_value):
    """Find all occurrences of magic number in file"""
    if not os.path.exists(filename):
        print(f"\nFile not found: {filename}")
        return None, None
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    # Convert magic to bytes (little-endian and big-endian)
    magic_bytes_le = bytes([(magic_value >> (i*8)) & 0xFF for i in range(4)])
    magic_bytes_be = bytes([(magic_value >> ((3-i)*8)) & 0xFF for i in range(4)])
    
    offsets_le = []
    offsets_be = []
    
    # Search for magic (little-endian and big-endian)
    for i in range(len(data) - 3):
        if data[i:i+4] == magic_bytes_le:
            offsets_le.append(i)
        if data[i:i+4] == magic_bytes_be:
            offsets_be.append(i)
    
    print(f"\n{filename}:")
    print(f"  Size: {len(data)} bytes (0x{len(data):X})")
    print(f"  Magic (LE): Found {len(offsets_le)} times")
    if offsets_le:
        print(f"    Offsets: {offsets_le[:10]}")
        # Check if they're at block boundaries (0x1000 = 4096)
        at_boundaries = [o for o in offsets_le if (o + 4) % BLOCK_SIZE == 0 or o % BLOCK_SIZE == 0]
        print(f"    At block boundaries: {len(at_boundaries)}")
    print(f"  Magic (BE): Found {len(offsets_be)} times")
    if offsets_be:
        print(f"    Offsets: {offsets_be[:10]}")
    
    # Check end of file
    print(f"\n  Last 16 bytes:")
    print(f"    {' '.join(f'{b:02X}' for b in data[-16:])}")
    
    return offsets_le, offsets_be


# Check all our SPIFFS images
find_magic_in_file('spiffs_with_correct_names.bin', magic)
find_magic_in_file('spiffs.bin', magic)
find_magic_in_file('spiffs _dummy.bin', magic)

print("\n" + "=" * 70)
print("[ANALYSIS]")
print("\nIf magic numbers are NOT found in our build but ARE in pre-built:")
print("  -> mkspiffs may not be calculating magic correctly")
print("  -> OR mkspiffs version differs from PlatformIO's")
print("  -> OR our parameters don't match what mkspiffs expects")
print("\nNext step: Compare actual magic bytes between working and failing images")
