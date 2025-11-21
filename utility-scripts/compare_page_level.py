#!/usr/bin/env python3
"""
Deep analysis of page-level differences between PlatformIO and our builds.

SPIFFS error -10025 is mount failure due to metadata validation.
Let's examine where the actual file data is stored and how checksums are computed.
"""

import os
import hashlib

def compare_regions(name1, file1, name2, file2):
    """Compare specific regions of two files"""
    
    with open(file1, 'rb') as f:
        data1 = f.read()
    with open(file2, 'rb') as f:
        data2 = f.read()
    
    print(f"\nComparing {name1} vs {name2}:")
    print("=" * 70)
    
    # Find first difference
    first_diff = None
    for i in range(min(len(data1), len(data2))):
        if data1[i] != data2[i]:
            first_diff = i
            break
    
    if first_diff is None:
        print("✓ Files are IDENTICAL")
        return
    
    print(f"✗ First difference at offset 0x{first_diff:X}")
    print(f"  {name1}[0x{first_diff:X}] = 0x{data1[first_diff]:02X}")
    print(f"  {name2}[0x{first_diff:X}] = 0x{data2[first_diff]:02X}")
    
    # Show context
    start = max(0, first_diff - 32)
    end = min(min(len(data1), len(data2)), first_diff + 32)
    
    print(f"\n  Context around difference:")
    print(f"  {name1}: {' '.join(f'{b:02X}' for b in data1[start:end])}")
    print(f"  {name2}: {' '.join(f'{b:02X}' for b in data2[start:end])}")
    
    # Check page boundaries (256 bytes)
    page_boundary_diffs = []
    for offset in range(256, min(len(data1), len(data2)), 256):
        # Check 4 bytes before page boundary (usually checksum)
        for i in range(offset-4, offset):
            if data1[i] != data2[i]:
                page_boundary_diffs.append((offset, i))
                break
    
    if page_boundary_diffs:
        print(f"\n  Differences near page boundaries:")
        for page_offset, byte_offset in page_boundary_diffs[:5]:
            print(f"    Page 0x{page_offset:X}: diff at 0x{byte_offset:X}")
    
    # Count total differences
    diff_count = sum(1 for i in range(min(len(data1), len(data2))) if data1[i] != data2[i])
    print(f"\n  Total differences: {diff_count} bytes ({100*diff_count/min(len(data1), len(data2)):.2f}%)")
    
    # Check where actual file data is
    # Certificate files in data/ : 4086 bytes total
    # They should appear consecutively in SPIFFS
    print(f"\n  Looking for certificate data...")
    
    # Search for cert file headers
    if b'-----BEGIN' in data1 and b'-----BEGIN' in data2:
        pos1 = data1.find(b'-----BEGIN')
        pos2 = data2.find(b'-----BEGIN')
        print(f"    {name1}: First cert at 0x{pos1:X}")
        print(f"    {name2}: First cert at 0x{pos2:X}")
        
        if pos1 != pos2:
            print(f"    ⚠ Certificate positions differ by {abs(pos2-pos1)} bytes!")
        
        # Compare cert sections
        if pos1 > 0 and pos2 > 0:
            cert_start = min(pos1, pos2)
            cert_end = min(len(data1), len(data2))
            
            # Find how many certs match
            cert_match_bytes = sum(1 for i in range(cert_start, min(pos1 + 4086, pos2 + 4086, cert_end)) 
                                  if i - pos1 + pos1 >= 0 and i - pos2 + pos2 >= 0 and 
                                  data1[i] == data2[i])
            print(f"    Certificate section: {cert_match_bytes} matching bytes")


# Compare images
compare_regions(
    "Fresh (ours)", "spiffs.bin",
    "PlatformIO (works)", "spiffs _dummy.bin"
)

compare_regions(
    "Pre-built", "spiffs_with_correct_names.bin",
    "PlatformIO (works)", "spiffs _dummy.bin"
)

print("\n" + "=" * 70)
print("[KEY INSIGHT]")
print("If certificate data is identical but metadata differs,")
print("the issue is in page/block checksums or SPIFFS metadata headers,")
print("not in the actual file content.")
