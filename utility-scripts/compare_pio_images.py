#!/usr/bin/env python3
"""
Compare PlatformIO-built image with pre-built to understand file indexing issue.
"""

import os

with open('spiffs_pio.bin', 'rb') as f:
    pio_new = f.read()

with open('spiffs_with_correct_names.bin', 'rb') as f:
    prebuilt = f.read()

print('[COMPARING: spiffs_pio.bin vs spiffs_with_correct_names.bin]')
print('=' * 70)

# Count differences
diffs = sum(1 for i in range(min(len(pio_new), len(prebuilt))) if pio_new[i] != prebuilt[i])

print(f'Size (new):      {len(pio_new)} bytes')
print(f'Size (prebuilt): {len(prebuilt)} bytes')
print(f'Differences:     {diffs} bytes ({100*diffs/len(prebuilt):.2f}%)')

if diffs == 0:
    print('\n✓ IDENTICAL - Perfect match!')
else:
    # Find first difference
    for i in range(min(len(pio_new), len(prebuilt))):
        if pio_new[i] != prebuilt[i]:
            print(f'\nFirst difference at offset 0x{i:X}:')
            print(f'  New:     0x{pio_new[i]:02X}')
            print(f'  Prebuilt: 0x{prebuilt[i]:02X}')
            
            # Show context
            start = max(0, i - 32)
            end = min(min(len(pio_new), len(prebuilt)), i + 32)
            print(f'\n  Context (new):')
            hex_new = ' '.join(f'{b:02X}' for b in pio_new[start:end])
            print(f'    {hex_new}')
            print(f'  Context (prebuilt):')
            hex_pre = ' '.join(f'{b:02X}' for b in prebuilt[start:end])
            print(f'    {hex_pre}')
            break

# Analyze file entries
print('\n' + '=' * 70)
print('[FILE ENTRY ANALYSIS]')

def find_file_entries(data, name):
    """Find SPIFFS file entries (containing /)"""
    entries = []
    for offset in range(0, min(4096, len(data))):
        if data[offset:offset+1] == b'/' and offset > 0:
            # Get null-terminated filename
            name_end = offset + 1
            while name_end < offset + 32 and name_end < len(data) and data[name_end] != 0:
                b = data[name_end]
                if (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122) or b in (46, 45, 95, 46):
                    name_end += 1
                else:
                    break
            
            if name_end > offset + 1:
                filename = data[offset:name_end].decode('utf-8', errors='ignore')
                entries.append((offset, filename))
    
    print(f'\n{name}:')
    if entries:
        for offset, filename in entries:
            print(f'  0x{offset:04X}: {filename}')
    else:
        print(f'  No file entries found!')
    
    return entries

pio_entries = find_file_entries(pio_new, 'spiffs_pio.bin')
pre_entries = find_file_entries(prebuilt, 'spiffs_with_correct_names.bin')

print('\n' + '=' * 70)
print('[HYPOTHESIS]')
print('If new image has different file entry positions,')
print('the device may not properly index them in the lookup table.')
print()
print('Device accepted the format but cant find files →')
print('File entries exist but arent linked in the SPIFFS object table.')
