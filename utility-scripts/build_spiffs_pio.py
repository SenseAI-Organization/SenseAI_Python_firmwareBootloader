#!/usr/bin/env python3
"""
Build SPIFFS using PlatformIO's exact mkspiffs version (1.200.0).

This ensures maximum compatibility with your device since:
1. PlatformIO's builds work on your device
2. Using the same mkspiffs version reduces format differences
3. All configuration is explicit and tested
"""

import os
import subprocess
import sys


def find_pio_mkspiffs():
    """Find PlatformIO's tool-mkspiffs@1.200.0"""
    pio_path = os.path.expanduser('~/.platformio/packages/tool-mkspiffs@1.200.0/mkspiffs.exe')
    if os.path.exists(pio_path):
        return pio_path
    
    # Try without version
    pio_path2 = os.path.expanduser('~/.platformio/packages/tool-mkspiffs/mkspiffs.exe')
    if os.path.exists(pio_path2):
        return pio_path2
    
    return None


def build_with_pio_mkspiffs():
    """Build SPIFFS with PlatformIO's mkspiffs"""
    
    mkspiffs = find_pio_mkspiffs()
    if not mkspiffs:
        print('[ERROR] PlatformIO mkspiffs not found!')
        print('        Expected at: ~/.platformio/packages/tool-mkspiffs@1.200.0/mkspiffs.exe')
        print()
        print('        Install with: platformio platform install espressif32')
        return False
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(script_dir, 'data')
    output_file = os.path.join(script_dir, 'spiffs_pio.bin')
    
    print('[BUILD SPIFFS WITH PLATFORMIO MKSPIFFS]')
    print('=' * 70)
    print(f'mkspiffs version: tool-mkspiffs@1.200.0')
    print(f'mkspiffs path:    {mkspiffs}')
    print(f'data folder:      {data_folder}')
    print(f'output file:      {output_file}')
    print()
    
    # Verify data folder
    if not os.path.exists(data_folder):
        print(f'[ERROR] Data folder not found: {data_folder}')
        return False
    
    files = os.listdir(data_folder)
    total_size = sum(os.path.getsize(os.path.join(data_folder, f)) for f in files if os.path.isfile(os.path.join(data_folder, f)))
    
    print(f'[DATA] {len(files)} files, {total_size} bytes total')
    for f in files:
        path = os.path.join(data_folder, f)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            print(f'       {f:40s} {size:10,d} bytes')
    print()
    
    # Standard ESP32-S3 SPIFFS parameters
    print('[CONFIGURATION]')
    print('  block_size:  4096 bytes  (-b 4096)')
    print('  page_size:   256 bytes   (-p 256)')
    print('  image_size:  1212416 bytes (-s 1212416 = 0x128000)')
    print('  This matches standard ESP-IDF SPIFFS defaults')
    print()
    
    # Build command
    cmd = [
        mkspiffs,
        '-c', data_folder,      # Create from directory
        '-b', '4096',           # Block size
        '-p', '256',            # Page size
        '-s', '1212416',        # Partition size (exact)
        output_file
    ]
    
    print('[EXECUTE]')
    print(f'  {" ".join(cmd)}')
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f'[ERROR] mkspiffs failed with code {result.returncode}')
            if result.stderr:
                print(f'[STDERR] {result.stderr}')
            if result.stdout:
                print(f'[STDOUT] {result.stdout}')
            return False
        
        # Verify output
        if not os.path.exists(output_file):
            print('[ERROR] Output file not created')
            return False
        
        actual_size = os.path.getsize(output_file)
        expected_size = 1212416
        
        if actual_size != expected_size:
            print(f'[ERROR] Size mismatch!')
            print(f'        Expected: {expected_size} bytes')
            print(f'        Got:      {actual_size} bytes')
            return False
        
        print('[SUCCESS] SPIFFS image created!')
        print(f'  File:  {output_file}')
        print(f'  Size:  {actual_size} bytes')
        print()
        print('[NEXT STEPS]')
        print('1. Flash to device:')
        print(f'   esptool write-flash 0x5F0000 {output_file}')
        print()
        print('2. Check device serial output for SPIFFS mount status')
        print('   - If device says "SPIFFS mounted" → SUCCESS!')
        print('   - If device says "mount failed -10025" → Device may format and retry')
        print('   - If device says "mount failed" after format → Check parameters')
        print()
        print('3. If working, copy as official template:')
        print(f'   copy {output_file} spiffs_with_correct_names.bin')
        print()
        
        return True
        
    except subprocess.TimeoutExpired:
        print('[ERROR] mkspiffs timeout')
        return False
    except Exception as e:
        print(f'[ERROR] {e}')
        return False


if __name__ == '__main__':
    success = build_with_pio_mkspiffs()
    sys.exit(0 if success else 1)
