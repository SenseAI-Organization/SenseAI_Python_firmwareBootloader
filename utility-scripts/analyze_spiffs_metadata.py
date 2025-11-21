#!/usr/bin/env python3
"""
Deep analysis of what changes between mkspiffs builds.
Analyzes the metadata structure to understand if changes are in:
- SPIFFS superblock header (validated by bootloader)
- File entry metadata (validated by SPIFFS driver)
- Timestamps/sequence numbers (may not be validated)
"""

import os
import struct
import sys
from pathlib import Path


def analyze_spiffs_header(filepath):
    """Analyze SPIFFS superblock structure"""
    print(f"\n[HEADER ANALYSIS] {filepath}")
    print("-" * 70)
    
    with open(filepath, 'rb') as f:
        data = f.read()
    
    if len(data) < 256:
        print("[ERROR] File too small to contain SPIFFS header")
        return None
    
    # SPIFFS superblock is at the beginning
    # Magic: 0x53 0x50 0x49 0x46 ('SPIF')
    magic = data[0:4]
    print(f"[INFO] Magic bytes (0x00-0x03): {magic.hex()} = '{magic.decode('utf-8', errors='ignore')}'")
    
    # Extract what we can about the structure
    print(f"[INFO] First 256 bytes (potential superblock):")
    for i in range(0, min(256, len(data)), 16):
        hex_str = ' '.join(f'{b:02x}' for b in data[i:i+16])
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
        print(f"       0x{i:04X}: {hex_str:<48} {ascii_str}")
    
    return data


def compare_spiffs_structures(data1, data2, name1, name2):
    """Compare two SPIFFS images and identify what's different"""
    print(f"\n[STRUCTURE COMPARISON]")
    print("-" * 70)
    
    # Find all differences
    diffs = []
    min_len = min(len(data1), len(data2))
    
    for i in range(min_len):
        if data1[i] != data2[i]:
            diffs.append((i, data1[i], data2[i]))
    
    print(f"[INFO] Total differences: {len(diffs)} bytes")
    
    # Group consecutive differences
    ranges = []
    if diffs:
        current_range = [diffs[0][0], diffs[0][0]]
        for offset, _, _ in diffs[1:]:
            if offset == current_range[1] + 1:
                current_range[1] = offset
            else:
                ranges.append(current_range)
                current_range = [offset, offset]
        ranges.append(current_range)
    
    print(f"[INFO] Different ranges: {len(ranges)}")
    for start, end in ranges:
        print(f"[INFO]   0x{start:04X} - 0x{end:04X} ({end-start+1} bytes)")
    
    # Analyze specific ranges
    print(f"\n[DETAILED ANALYSIS]")
    
    # Check if differences are in the first block (superblock area)
    first_block_size = 4096
    diffs_in_superblock = [d for d in diffs if d[0] < first_block_size]
    diffs_in_data = [d for d in diffs if d[0] >= first_block_size]
    
    print(f"[INFO] Differences in superblock (0x0000-0x0FFF): {len(diffs_in_superblock)}")
    print(f"[INFO] Differences in data blocks (0x1000+): {len(diffs_in_data)}")
    
    # Show actual byte values at diff points
    print(f"\n[BYTE COMPARISONS]")
    for offset, byte1, byte2 in diffs[:20]:  # First 20 differences
        context1 = data1[max(0, offset-2):min(len(data1), offset+3)].hex()
        context2 = data2[max(0, offset-2):min(len(data2), offset+3)].hex()
        print(f"[INFO] Offset 0x{offset:04X}:")
        print(f"       {name1}: ...{context1}...")
        print(f"       {name2}: ...{context2}...")
    
    if len(diffs) > 20:
        print(f"[INFO] ... and {len(diffs) - 20} more differences")


def analyze_platformio_behavior():
    """Analyze what PlatformIO might be doing"""
    print(f"\n[PLATFORMIO ANALYSIS]")
    print("-" * 70)
    print("""
[THEORY] PlatformIO might be doing one of these things:

1. CACHING: PlatformIO caches SPIFFS images and only rebuilds when
   data/ folder contents change (not timestamps). This means:
   - First build: mkspiffs creates image with timestamp T1
   - Second build (no data changes): Use cached image from disk
   - Third build (data changed): mkspiffs creates new image with timestamp T2
   
2. TIMESTAMP MASKING: PlatformIO might strip timestamps before flashing
   or use a build flag to make mkspiffs deterministic
   
3. BOOTLOADER IGNORING METADATA: The bootloader/SPIFFS driver might
   only validate the file entries, not the superblock timestamps
   
4. DETERMINISTIC MODE: Newer mkspiffs might support --no-timestamps
   or similar flag for deterministic builds

[EVIDENCE FROM YOUR TESTING]
- Button works reliably with pre-built image
- Pre-built image has specific metadata
- Fresh builds have different metadata but same file content
- Button uses pre-built, not mkspiffs rebuild
""")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    build1 = os.path.join(script_dir, "test_build1.bin")
    build2 = os.path.join(script_dir, "test_build2.bin")
    prebuilt = os.path.join(script_dir, "spiffs_with_correct_names.bin")
    
    print("\n" + "="*70)
    print("DEEP ANALYSIS: What's changing in mkspiffs builds?")
    print("="*70)
    
    # Analyze each file
    if os.path.exists(build1):
        data1 = analyze_spiffs_header(build1)
    else:
        print(f"[ERROR] {build1} not found")
        data1 = None
    
    if os.path.exists(build2):
        data2 = analyze_spiffs_header(build2)
    else:
        print(f"[ERROR] {build2} not found")
        data2 = None
    
    if os.path.exists(prebuilt):
        data_pre = analyze_spiffs_header(prebuilt)
    else:
        print(f"[ERROR] {prebuilt} not found")
        data_pre = None
    
    # Compare structures
    if data1 and data2:
        compare_spiffs_structures(data1, data2, "build1", "build2")
    
    if data1 and data_pre:
        compare_spiffs_structures(data1, data_pre, "fresh_build", "prebuilt")
    
    # Analyze PlatformIO behavior
    analyze_platformio_behavior()
    
    # Key question
    print(f"\n[KEY QUESTION]")
    print("-" * 70)
    print("""
Can we modify ONLY the file data (after the metadata) without
rebuilding the entire SPIFFS image?

Possible approach:
1. Use pre-built image as base (keep validated metadata)
2. Calculate file offsets from SPIFFS directory entries
3. Patch file contents directly
4. Keep all metadata unchanged

This would preserve metadata that device has validated while
allowing file content updates!
""")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
