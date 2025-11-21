#!/usr/bin/env python3
"""
Build SPIFFS image from data/ folder with EXACT configuration matching PlatformIO.

Configuration:
  - blockSize: 4096 bytes
  - pageSize: 256 bytes
  - objectNameLen: 32 chars
  - metaLength: 4 bytes
  - useMagic: true
  - useMagicLength: 2 bytes

These are the ESP32 defaults and match PlatformIO's configuration.
"""

import os
import sys
import subprocess
from pathlib import Path


def build_spiffs_image(mkspiffs_path, data_folder, output_file, size):
    """
    Build SPIFFS image using mkspiffs with exact parameters.
    
    Args:
        mkspiffs_path: Path to mkspiffs binary
        data_folder: Path to data/ folder
        output_file: Path to output SPIFFS image
        size: Size of SPIFFS partition (must be exact)
        
    Returns:
        True if successful, False otherwise
    """
    
    # These are the EXACT parameters for ESP32
    PAGE_SIZE = 256       # -p
    BLOCK_SIZE = 4096     # -b
    
    print("[INFO] Building SPIFFS image with standard ESP32 parameters")
    print(f"       mkspiffs: {mkspiffs_path}")
    print(f"       input:    {data_folder}")
    print(f"       output:   {output_file}")
    print(f"       size:     {size} bytes (0x{size:X})")
    print(f"       blockSize: {BLOCK_SIZE} bytes")
    print(f"       pageSize:  {PAGE_SIZE} bytes")
    
    # Build command - order matters!
    # mkspiffs -c <data_folder> -b 4096 -p 256 -s <size> <output_file>
    cmd = [
        mkspiffs_path,
        "-c", data_folder,
        "-b", str(BLOCK_SIZE),
        "-p", str(PAGE_SIZE),
        "-s", str(size),
        output_file
    ]
    
    print(f"\n[EXECUTE]")
    print(f"       Command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"[ERROR] mkspiffs failed with code {result.returncode}")
            if result.stderr:
                print(f"[STDERR] {result.stderr}")
            if result.stdout:
                print(f"[STDOUT] {result.stdout}")
            return False
        
        # Verify output file
        if not os.path.exists(output_file):
            print(f"[ERROR] Output file not created: {output_file}")
            return False
        
        actual_size = os.path.getsize(output_file)
        if actual_size != size:
            print(f"[ERROR] Size mismatch!")
            print(f"        Expected: {size} bytes")
            print(f"        Got:      {actual_size} bytes")
            return False
        
        print(f"[SUCCESS] SPIFFS image created: {output_file}")
        print(f"          Size: {actual_size} bytes")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"[ERROR] mkspiffs timeout (>60s)")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(script_dir, "data")
    output_file = os.path.join(script_dir, "spiffs.bin")
    
    # SPIFFS partition size (from device partition table)
    SPIFFS_SIZE = 0x128000  # 1,212,416 bytes
    
    # Find mkspiffs
    mkspiffs = r'C:\Users\escob\.platformio\packages\tool-mkspiffs@1.200.0\mkspiffs.exe'
    
    if not os.path.exists(mkspiffs):
        print(f"[ERROR] mkspiffs not found: {mkspiffs}")
        return 1
    
    print("\n" + "="*70)
    print("BUILDING SPIFFS IMAGE FROM data/ FOLDER")
    print("="*70)
    print()
    
    # Check data folder
    if not os.path.exists(data_folder):
        print(f"[ERROR] Data folder not found: {data_folder}")
        return 1
    
    files = [f for f in os.listdir(data_folder) if os.path.isfile(os.path.join(data_folder, f))]
    if not files:
        print(f"[ERROR] Data folder is empty: {data_folder}")
        return 1
    
    print(f"[INFO] Data folder: {data_folder}")
    print(f"[INFO] Files found: {len(files)}")
    for f in files:
        fpath = os.path.join(data_folder, f)
        size = os.path.getsize(fpath)
        print(f"       • {f} ({size} bytes)")
    print()
    
    # Build image
    success = build_spiffs_image(mkspiffs, data_folder, output_file, SPIFFS_SIZE)
    
    if not success:
        print("\n[ERROR] Failed to build SPIFFS image")
        return 1
    
    # Success - show next steps
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print(f"""
The SPIFFS image has been built: {output_file}

To flash it to your device:

  Option 1 - Manual with esptool:
    esptool.py --chip esp32s3 --port COM8 write-flash \\
      --flash-mode dio --flash-freq 40m \\
      0x5F0000 {output_file}

  Option 2 - Using test script:
    python test_spiffs_build.py COM8 --no-flash

  Option 3 - Using flash script:
    python flash_fresh_spiffs.py COM8

  Option 4 - Click "Upload Data Folder" button in GUI

The image is {os.path.getsize(output_file)} bytes (must match partition size of {SPIFFS_SIZE})
""")
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[CANCELLED]")
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
