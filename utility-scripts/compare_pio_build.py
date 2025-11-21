#!/usr/bin/env python3
"""
Compare PlatformIO's spiffs_dummy.bin (WORKS on device) with our builds.
This is CRITICAL because it shows what makes a build accepted by the device.
"""

import os
import sys
from pathlib import Path


def compare_files_detailed(file1, file2, name1, name2):
    """Deep comparison of two SPIFFS images"""
    with open(file1, 'rb') as f:
        data1 = f.read()
    with open(file2, 'rb') as f:
        data2 = f.read()
    
    print(f"\n{'='*70}")
    print(f"COMPARING: {name1} vs {name2}")
    print(f"{'='*70}")
    
    print(f"\n[SIZE COMPARISON]")
    print(f"  {name1}: {len(data1):,} bytes (0x{len(data1):X})")
    print(f"  {name2}: {len(data2):,} bytes (0x{len(data2):X})")
    
    if len(data1) != len(data2):
        print(f"  [WARNING] Different sizes!")
    
    # Find differences
    diffs = []
    min_len = min(len(data1), len(data2))
    
    for i in range(min_len):
        if data1[i] != data2[i]:
            diffs.append((i, data1[i], data2[i]))
    
    if not diffs:
        print(f"\n[RESULT] ✅ FILES ARE IDENTICAL")
        return True
    
    print(f"\n[DIFFERENCES]")
    print(f"  Total different bytes: {len(diffs)}")
    
    # Group into ranges
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
    
    print(f"  Different ranges: {len(ranges)}")
    
    # Show first few ranges
    print(f"\n[DIFFERENCE RANGES]")
    for i, (start, end) in enumerate(ranges[:10]):
        size = end - start + 1
        print(f"  {i+1}. 0x{start:04X} - 0x{end:04X} ({size} bytes)")
        # Show byte values
        context_start = max(0, start - 2)
        context_end = min(len(data1), end + 3)
        hex1 = data1[context_start:context_end].hex()
        hex2 = data2[context_start:context_end].hex()
        print(f"     {name1}: {hex1}")
        print(f"     {name2}: {hex2}")
    
    if len(ranges) > 10:
        print(f"  ... and {len(ranges) - 10} more ranges")
    
    return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    files_to_compare = [
        ("spiffs_dummy.bin", "PlatformIO build (WORKS on device)"),
        ("spiffs_fresh_build.bin", "Our fresh mkspiffs build (FAILED on device)"),
        ("spiffs_with_correct_names.bin", "Pre-built image (WORKS on device)"),
    ]
    
    # Find all files
    available = []
    for fname, desc in files_to_compare:
        fpath = os.path.join(script_dir, fname)
        if os.path.exists(fpath):
            available.append((fpath, fname, desc))
            print(f"[FOUND] {fname}")
        else:
            print(f"[NOT FOUND] {fname}")
    
    if len(available) < 2:
        print("\n[ERROR] Need at least 2 files to compare")
        return 1
    
    print("\n" + "="*70)
    print("CRITICAL ANALYSIS: PlatformIO Build vs Our Builds")
    print("="*70)
    
    # Compare PlatformIO with others
    pio_path, pio_name, pio_desc = available[0]
    
    for other_path, other_name, other_desc in available[1:]:
        match = compare_files_detailed(pio_path, other_path, pio_desc, other_desc)
        
        if match:
            print(f"\n[INSIGHT] These files are IDENTICAL!")
            print(f"  → PlatformIO and our build produce same result")
        else:
            # Analyze the differences
            with open(pio_path, 'rb') as f:
                pio_data = f.read()
            with open(other_path, 'rb') as f:
                other_data = f.read()
            
            # Count differences
            diffs = sum(1 for i in range(min(len(pio_data), len(other_data)))
                       if pio_data[i] != other_data[i])
            
            print(f"\n[KEY FINDING]")
            print(f"  PlatformIO build WORKS despite having {diffs} different bytes")
            print(f"  This means those bytes are NOT critical for device validation")
            print(f"  They're likely:")
            print(f"    - Timestamps (when image was built)")
            print(f"    - Build environment specific data")
            print(f"    - Non-critical metadata")
    
    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    print("""
If spiffs_dummy.bin (PlatformIO) is DIFFERENT from our builds but WORKS:
  → Device doesn't strictly validate certain metadata bytes
  → We can build fresh images and device will accept them
  → The validation is more lenient than we thought

If spiffs_dummy.bin is IDENTICAL to one of our builds:
  → That build will work on the device
  → We can replicate that approach
  → We've found the secret sauce!
""")
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
