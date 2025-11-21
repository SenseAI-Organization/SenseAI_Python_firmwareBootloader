#!/usr/bin/env python3
"""
Copied utility: flash_fresh_spiffs.py
"""
import os
import sys
from spiffs_utils import SPIFFSManager
from flash_utils import FlashManager

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.join(script_dir, "..")
    spiffs_image = os.path.join(repo_root, "app_generation_output", "spiffs_fresh_build.bin")
    print(f"Will flash: {spiffs_image}")
    if not os.path.exists(spiffs_image):
        print("Image not found")
        return 1
    # Basic stub to reuse existing managers
    spiffs = SPIFFSManager(script_dir=repo_root, logger=print)
    flash = FlashManager(logger=print)
    print("This script is copied into app_generation for convenience.")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(e)
        sys.exit(1)
