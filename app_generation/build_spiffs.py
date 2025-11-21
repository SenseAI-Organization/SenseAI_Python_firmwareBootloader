#!/usr/bin/env python3
"""
Copied utility: build_spiffs.py
This script attempts to build a SPIFFS image from `data/` using mkspiffs.
It was copied into `app_generation/` so packaging-related scripts live together.
"""

import os
import sys
import subprocess
from pathlib import Path


def build_spiffs_image(mkspiffs_path, data_folder, output_file, size):
    PAGE_SIZE = 256
    BLOCK_SIZE = 4096
    print("[INFO] Building SPIFFS image with standard ESP32 parameters")
    cmd = [mkspiffs_path, "-c", data_folder, "-b", str(BLOCK_SIZE), "-p", str(PAGE_SIZE), "-s", str(size), output_file]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"[ERROR] mkspiffs failed: {result.stderr}")
            return False
        if not os.path.exists(output_file):
            print(f"[ERROR] Output file not created: {output_file}")
            return False
        actual_size = os.path.getsize(output_file)
        if actual_size != size:
            print(f"[ERROR] Size mismatch: expected {size}, got {actual_size}")
            return False
        print(f"[SUCCESS] SPIFFS image created: {output_file}")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(script_dir, "..", "data")
    output_file = os.path.join(script_dir, "..", "app_generation_output", "spiffs.bin")
    SPIFFS_SIZE = 0x128000
    mkspiffs = r'C:\Users\escob\.platformio\packages\tool-mkspiffs@1.200.0\mkspiffs.exe'
    if not os.path.exists(mkspiffs):
        print(f"[ERROR] mkspiffs not found: {mkspiffs}")
        return 1
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    success = build_spiffs_image(mkspiffs, data_folder, output_file, SPIFFS_SIZE)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
