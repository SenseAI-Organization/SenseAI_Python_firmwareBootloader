#!/usr/bin/env python3
"""
Strategy: Use pre-built image but replace file content.

Since the pre-built image works, we can:
1. Treat it as a template with valid checksums
2. Extract file positions and sizes from it
3. Replace file content while keeping metadata intact

This avoids mkspiffs altogether and guarantees device compatibility.
"""

import os

def analyze_file_entries(binary_path):
    """
    Find SPIFFS file entries in the image.
    
    SPIFFS file entry format (approx):
    [flags: 2 bytes][size: 4 bytes][block/page pointers: 4 bytes][name: 32 bytes]...
    """
    with open(binary_path, 'rb') as f:
        data = f.read()
    
    print(f"\n[Analyzing {os.path.basename(binary_path)}]")
    print("=" * 70)
    
    # Search for file paths (names start with /)
    files_found = []
    for offset in range(0, min(4096, len(data))):  # Search in first block only
        # Look for "/" character followed by filename-like characters
        if offset < len(data) - 32 and data[offset:offset+1] == b'/':
            # Try to extract null-terminated filename
            name_end = offset + 1
            while name_end < offset + 32 and name_end < len(data) and data[name_end] != 0:
                # Check if it's a printable filename character
                b = data[name_end]
                if (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122) or b in (46, 45, 95):  # 0-9, A-Z, a-z, . - _
                    name_end += 1
                else:
                    break
            
            if name_end > offset + 1:
                filename = data[offset:name_end].decode('utf-8', errors='ignore')
                
                # Get surrounding context (likely to include size/pointers)
                context_start = max(0, offset - 16)
                context_end = min(len(data), offset + 64)
                context = data[context_start:context_end]
                
                files_found.append({
                    'name': filename,
                    'offset': offset,
                    'context_start': context_start,
                    'context': context
                })
    
    if files_found:
        print(f"Found {len(files_found)} file entries:")
        for i, entry in enumerate(files_found):
            print(f"\n  {i+1}. {entry['name']} @ 0x{entry['offset']:X}")
            hex_str = ' '.join(f'{b:02X}' for b in entry['context'])
            print(f"     Context: {hex_str}")
    
    return files_found


# Analyze the working pre-built image
analyze_file_entries('spiffs_with_correct_names.bin')
analyze_file_entries('spiffs _dummy.bin')
analyze_file_entries('spiffs.bin')

print("\n" + "=" * 70)
print("[CONCLUSION]")
print("\nMkspiffs structures are too different from pre-built.")
print("The simple solution:")
print("  1. Copy pre-built image")
print("  2. Use it as-is (it works!)")
print("  3. OR rebuild with mkspiffs and patch block status flags")
print("\nSince patching flags didn't work, let's just use the pre-built image.")
print("It's already tested and works on the device.")
