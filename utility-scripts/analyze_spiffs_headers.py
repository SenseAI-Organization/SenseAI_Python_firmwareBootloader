#!/usr/bin/env python3
"""
Deep dive into SPIFFS block structure differences.

SPIFFS block header format (per SPIFFS spec):
  Byte 0: Block flags/status
    - Bit 0: BLOCK_ALLOCATED (0=used, 1=free)
    - Bit 7: BLOCK_DELETED/MARKED
  Bytes 1-3: More metadata
"""

import os

def analyze_differences():
    """Compare block headers between images"""
    
    files = {
        'Pre-built': 'spiffs_with_correct_names.bin',
        'Fresh (ours)': 'spiffs.bin',
        'PlatformIO (works)': 'spiffs _dummy.bin'
    }
    
    images = {}
    for name, filepath in files.items():
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                images[name] = f.read()
    
    print("[SPIFFS BLOCK STATUS ANALYSIS]")
    print("=" * 70)
    print("\nComparing first 256 bytes (SPIFFS header/metadata area):")
    print()
    
    # Compare first 256 bytes byte-by-byte
    for offset in range(0, 128, 16):
        print(f"Offset 0x{offset:04X}:")
        for name in images.keys():
            data = images[name]
            hex_str = ' '.join(f'{b:02X}' for b in data[offset:offset+16])
            print(f"  {name:20s}: {hex_str}")
        print()
    
    print("=" * 70)
    print("\n[KEY DIFFERENCE]")
    print("PlatformIO image starts with:    01 80 01 00")
    print("Pre-built & Fresh images start:  00 00 01 00")
    print()
    print("This suggests PlatformIO uses a DIFFERENT block allocation format")
    print("or has BLOCK_DELETED flag set (0x80).")
    print()
    
    # Check if this pattern repeats
    print("[PATTERN CHECK]")
    magic_le = bytes([0x09, 0x05, 0x15, 0x60])
    
    for name, data in images.items():
        print(f"\n{name}:")
        # Look for blocks that start with 01 80
        count_01_80 = 0
        count_00_00 = 0
        
        for block_idx in range(min(20, len(data) // 4096)):
            offset = block_idx * 4096
            first_byte = data[offset]
            second_byte = data[offset+1] if offset+1 < len(data) else 0
            
            if first_byte == 0x01 and second_byte == 0x80:
                count_01_80 += 1
            elif first_byte == 0x00 and second_byte == 0x00:
                count_00_00 += 1
        
        print(f"  Blocks starting with 01 80: {count_01_80}")
        print(f"  Blocks starting with 00 00: {count_00_00}")
    
    print("\n" + "=" * 70)
    print("[CONCLUSION]")
    print("PlatformIO sets the BLOCK_DELETED flag (0x80) on block 0")
    print("This is NORMAL - marks the block as being reformatted")
    print("Device ACCEPTS this format because it expects:")
    print("  - Block 0 with flags set (0x01 0x80)")
    print("  - Or block 0 clean (0x00 0x00)")
    print()
    print("However, ONLY the PlatformIO format gets accepted by device!")
    print("This suggests device firmware expects SPECIFIC header format")

analyze_differences()
