#!/usr/bin/env python3
"""
Test mkspiffs non-determinism by building multiple images.
If mkspiffs is non-deterministic, each build should produce different metadata.
"""

import os
import sys
import subprocess
from pathlib import Path

# Import the utilities
from spiffs_utils import SPIFFSManager


def build_image(script_dir, data_folder, output_file):
    """Build a SPIFFS image and return success status"""
    SPIFFS_SIZE = 0x128000
    
    def logger(msg, level='info'):
        print(f"[{level.upper()}] {msg}")
    
    spiffs = SPIFFSManager(script_dir=script_dir, logger=logger)
    
    success = spiffs.build_spiffs_image_from_mkspiffs(
        data_folder=data_folder,
        output_file=output_file,
        size=SPIFFS_SIZE
    )
    
    return success


def compare_files(file1, file2):
    """Compare two binary files and report differences"""
    with open(file1, 'rb') as f:
        content1 = f.read()
    with open(file2, 'rb') as f:
        content2 = f.read()
    
    print(f"\n[INFO] Comparing files:")
    print(f"[INFO]   File 1: {file1}")
    print(f"[INFO]   Size 1: {len(content1)} bytes")
    print(f"[INFO]   File 2: {file2}")
    print(f"[INFO]   Size 2: {len(content2)} bytes")
    
    if len(content1) != len(content2):
        print(f"[ERROR] Different sizes: {len(content1)} vs {len(content2)}")
        return False
    
    if content1 == content2:
        print(f"[SUCCESS] FILES ARE IDENTICAL (100% match)")
        return True
    else:
        # Find differences
        diff_count = 0
        diff_ranges = []
        in_diff = False
        start = None
        
        for i in range(len(content1)):
            if content1[i] != content2[i]:
                diff_count += 1
                if not in_diff:
                    start = i
                    in_diff = True
            else:
                if in_diff:
                    diff_ranges.append((start, i-1))
                    in_diff = False
        
        if in_diff:
            diff_ranges.append((start, len(content1)-1))
        
        print(f"[WARNING] FILES DIFFER")
        print(f"[INFO] Total different bytes: {diff_count}")
        print(f"[INFO] Different ranges: {len(diff_ranges)}")
        
        for start, end in diff_ranges[:5]:  # Show first 5 ranges
            print(f"[INFO]   Range 0x{start:X} - 0x{end:X} ({end-start+1} bytes)")
            if start < 20:
                print(f"[INFO]     File1[{start}:{end+1}]: {content1[start:end+1].hex()}")
                print(f"[INFO]     File2[{start}:{end+1}]: {content2[start:end+1].hex()}")
        
        if len(diff_ranges) > 5:
            print(f"[INFO]   ... and {len(diff_ranges)-5} more ranges")
        
        return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(script_dir, "data")
    
    build1 = os.path.join(script_dir, "test_build1.bin")
    build2 = os.path.join(script_dir, "test_build2.bin")
    build3 = os.path.join(script_dir, "test_build3.bin")
    
    print("\n" + "="*70)
    print("TESTING MKSPIFFS NON-DETERMINISM")
    print("Building 3 fresh images from same data folder")
    print("="*70)
    
    # Build three images
    print("\n[INFO] Building image 1...")
    if not build_image(script_dir, data_folder, build1):
        print("[ERROR] Failed to build image 1")
        return 1
    
    print("\n[INFO] Building image 2...")
    if not build_image(script_dir, data_folder, build2):
        print("[ERROR] Failed to build image 2")
        return 1
    
    print("\n[INFO] Building image 3...")
    if not build_image(script_dir, data_folder, build3):
        print("[ERROR] Failed to build image 3")
        return 1
    
    # Compare them
    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)
    
    print("\n--- Build 1 vs Build 2 ---")
    result12 = compare_files(build1, build2)
    
    print("\n--- Build 2 vs Build 3 ---")
    result23 = compare_files(build2, build3)
    
    print("\n--- Build 1 vs Build 3 ---")
    result13 = compare_files(build1, build3)
    
    # Final verdict
    print("\n" + "="*70)
    if result12 and result23 and result13:
        print("RESULT: mkspiffs IS DETERMINISTIC")
        print("All three builds are identical. The tool produces same metadata.")
        print("This means we CAN dynamically build and rely on the results!")
    else:
        print("RESULT: mkspiffs IS NON-DETERMINISTIC")
        print("The builds differ - metadata changes each run.")
        print("This confirms why pre-built images are more reliable.")
    print("="*70 + "\n")
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
