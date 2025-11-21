#!/usr/bin/env python3
"""
Copied utility: build_fresh_spiffs.py
"""
import os
import sys
from spiffs_utils import SPIFFSManager

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.join(script_dir, "..")
    data_folder = os.path.join(repo_root, "data")
    output_file = os.path.join(repo_root, "app_generation_output", "spiffs_fresh_build.bin")
    SPIFFS_SIZE = 0x128000

    def logger(msg, level='info'):
        print(msg)

    spiffs = SPIFFSManager(script_dir=repo_root, logger=logger)
    files = spiffs.validate_data_folder(data_folder)
    if not files:
        print("No files to build")
        return 1
    mkspiffs = spiffs.find_mkspiffs()
    if not mkspiffs:
        print("mkspiffs not found")
        return 1
    success = spiffs.build_spiffs_image_from_mkspiffs(data_folder=data_folder, output_file=output_file, size=SPIFFS_SIZE)
    return 0 if success else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(e)
        sys.exit(1)
