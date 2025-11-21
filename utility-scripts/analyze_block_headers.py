#!/usr/bin/env python3
"""
Check SPIFFS block headers for magic numbers.

SPIFFS layout per block:
  [Block Header (magic + metadata)] [Lookup Table] [Data Pages]

Block header contains the magic number at a specific offset.
"""

import os

# SPIFFS constants
SPIFFS_MAGIC = 0x20140529
BLOCK_SIZE = 4096
PAGE_SIZE = 256
OBJ_NAME_LEN = 32

# Calculate magic
magic = SPIFFS_MAGIC ^ (BLOCK_SIZE << 18) ^ (PAGE_SIZE << 8) ^ OBJ_NAME_LEN

print("[SPIFFS BLOCK HEADER ANALYSIS]")
print("=" * 70)
print(f"Expected magic (LE): {' '.join(f'{(magic >> (i*8)) & 0xFF:02X}' for i in range(4))}")
print(f"Block size: {BLOCK_SIZE} bytes")
print(f"Page size: {PAGE_SIZE} bytes")
print()


def analyze_block_headers(filename):
    """Analyze SPIFFS block headers in file"""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    print(f"\n{filename}:")
    print(f"  Size: {len(data)} bytes")
    
    # Analyze first few blocks
    num_blocks = min(5, len(data) // BLOCK_SIZE)
    
    for block_idx in range(num_blocks):
        offset = block_idx * BLOCK_SIZE
        print(f"\n  Block {block_idx} (offset 0x{offset:05X}):")
        
        # Read block header (first 64 bytes usually contain magic)
        block_header = data[offset:offset+128]
        
        # Print first 32 bytes of header
        print(f"    First 32 bytes:")
        for i in range(0, 32, 16):
            hex_str = ' '.join(f'{b:02X}' for b in block_header[i:i+16])
            print(f"      +{i:02X}: {hex_str}")
        
        # Check for magic number at common offsets
        print(f"    Magic search:")
        magic_bytes_le = bytes([(magic >> (j*8)) & 0xFF for j in range(4)])
        
        for search_offset in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
            if search_offset + 4 <= len(block_header):
                found_bytes = block_header[search_offset:search_offset+4]
                if found_bytes == magic_bytes_le:
                    print(f"      ✓ Found at offset +{search_offset}: {' '.join(f'{b:02X}' for b in found_bytes)}")
        
        # Check for SPIFFS formatted marker (0x91 0x3B pattern)
        for search_offset in range(0, 32, 4):
            if search_offset + 2 <= len(block_header):
                potential_marker = block_header[search_offset:search_offset+2]
                if potential_marker in [bytes([0x91, 0x3B]), bytes([0x3B, 0x91])]:
                    print(f"      ? Potential SPIFFS marker at +{search_offset}: {' '.join(f'{b:02X}' for b in potential_marker)}")


# Analyze images
analyze_block_headers('spiffs_with_correct_names.bin')
analyze_block_headers('spiffs.bin')
analyze_block_headers('spiffs _dummy.bin')

print("\n" + "=" * 70)
print("[NEXT]")
print("Look at block structure and find where checksums differ")
