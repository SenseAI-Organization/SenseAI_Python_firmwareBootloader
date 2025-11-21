#!/usr/bin/env python3
"""
Build a fresh SPIFFS image from data folder using mkspiffs.
Tests the approach of building from scratch with proven parameters.

Usage:
    python build_fresh_spiffs.py
    python build_fresh_spiffs.py --output custom_name.bin
    python build_fresh_spiffs.py --output custom_name.bin --verbose
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Import the utilities
from spiffs_utils import SPIFFSManager


def main():
    """Build a fresh SPIFFS image from data folder"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Build fresh SPIFFS image from data folder using mkspiffs"
    )
    parser.add_argument('--output', default='spiffs_fresh_build.bin', 
                       help='Output filename (default: spiffs_fresh_build.bin)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(script_dir, "data")
    output_file = os.path.join(script_dir, args.output)
    
    # SPIFFS parameters (proven to work)
    SPIFFS_SIZE = 0x128000  # 1,212,416 bytes (auto-detected partition size)
    PAGE_SIZE = 256
    BLOCK_SIZE = 4096
    
    print("\n" + "="*70)
    print("🔨 BUILDING FRESH SPIFFS IMAGE FROM DATA FOLDER")
    print("="*70)
    print(f"Script dir: {script_dir}")
    print(f"Data folder: {data_folder}")
    print(f"Output file: {output_file}")
    print(f"SPIFFS size: {SPIFFS_SIZE} bytes (0x{SPIFFS_SIZE:X})")
    print(f"Page size: {PAGE_SIZE} bytes (-p {PAGE_SIZE})")
    print(f"Block size: {BLOCK_SIZE} bytes (-b {BLOCK_SIZE})")
    print("="*70 + "\n")
    
    # Create manager with custom logger
    def logger(msg, level='info'):
        prefix = {
            'info': '📝',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'debug': '🔍'
        }.get(level, '•')
        print(f"{prefix} {msg}")
    
    spiffs = SPIFFSManager(script_dir=script_dir, logger=logger)
    
    # Step 1: Validate data folder
    print("📋 STEP 1: VALIDATING DATA FOLDER")
    print("-" * 70)
    files = spiffs.validate_data_folder(data_folder)
    if not files:
        print("\n❌ Data folder is empty or not found. Exiting.")
        return 1
    
    # Step 2: Find mkspiffs
    print("\n\n🔍 STEP 2: FINDING MKSPIFFS")
    print("-" * 70)
    mkspiffs = spiffs.find_mkspiffs()
    if not mkspiffs:
        print("\n❌ mkspiffs not found. Please install it:")
        print("   Option 1: pip install mkspiffs")
        print("   Option 2: PlatformIO will install it at ~/.platformio/packages/")
        return 1
    
    # Step 3: Build fresh image with mkspiffs
    print("\n\n🔨 STEP 3: BUILDING FRESH IMAGE")
    print("-" * 70)
    
    success = spiffs.build_spiffs_image_from_mkspiffs(
        data_folder=data_folder,
        output_file=output_file,
        size=SPIFFS_SIZE
    )
    
    if not success:
        print("\n❌ Failed to build SPIFFS image. Exiting.")
        return 1
    
    # Step 4: Verify the output
    print("\n\n✅ STEP 4: VERIFICATION")
    print("-" * 70)
    
    if not os.path.exists(output_file):
        print(f"\n❌ Output file not created: {output_file}")
        return 1
    
    output_size = os.path.getsize(output_file)
    print(f"\n✅ Fresh SPIFFS image created successfully!")
    print(f"   File: {output_file}")
    print(f"   Size: {output_size} bytes (expected: {SPIFFS_SIZE})")
    
    if output_size != SPIFFS_SIZE:
        print(f"\n⚠️  WARNING: Size mismatch!")
        print(f"   Expected: {SPIFFS_SIZE} bytes")
        print(f"   Got: {output_size} bytes")
        print(f"   Difference: {output_size - SPIFFS_SIZE} bytes")
    
    # Step 5: Show comparison with pre-built image
    print("\n\n📊 STEP 5: COMPARISON WITH PRE-BUILT IMAGE")
    print("-" * 70)
    
    known_good = os.path.join(script_dir, "spiffs_with_correct_names.bin")
    if os.path.exists(known_good):
        good_size = os.path.getsize(known_good)
        print(f"\nPre-built image (spiffs_with_correct_names.bin):")
        print(f"   Size: {good_size} bytes")
        
        # Compare file contents
        with open(output_file, 'rb') as f1:
            fresh_content = f1.read()
        with open(known_good, 'rb') as f2:
            good_content = f2.read()
        
        if fresh_content == good_content:
            print(f"\n🎉 PERFECT MATCH! Fresh build is identical to pre-built image")
            print(f"   Both files are byte-for-byte identical")
            print(f"\n✨ This fresh build can now be used as the new known-good image!")
        else:
            print(f"\n⚠️  Files differ")
            # Find where they differ
            min_len = min(len(fresh_content), len(good_content))
            diff_count = 0
            first_diff = None
            for i in range(min_len):
                if fresh_content[i] != good_content[i]:
                    diff_count += 1
                    if first_diff is None:
                        first_diff = i
            
            if len(fresh_content) != len(good_content):
                print(f"   Size difference: {len(fresh_content)} vs {len(good_content)} bytes")
            else:
                print(f"   Content differences: {diff_count} byte(s) differ")
                if first_diff is not None:
                    print(f"   First difference at offset: 0x{first_diff:X}")
                    print(f"   Fresh: 0x{fresh_content[first_diff]:02X}")
                    print(f"   Pre-built: 0x{good_content[first_diff]:02X}")
    else:
        print(f"\nNo pre-built image found for comparison")
    
    # Final instructions
    print("\n\n📋 NEXT STEPS")
    print("-" * 70)
    print(f"\n1. Test the fresh image on your device:")
    print(f"   esptool.py --chip esp32s3 --port COM3 --baud 115200 \\")
    print(f"     write-flash --flash-mode dio --flash-freq 40m \\")
    print(f"     0x5F0000 {output_file}")
    
    print(f"\n2. If it works on the device, you can:")
    print(f"   • Replace the pre-built image:")
    print(f"     copy {output_file} spiffs_with_correct_names.bin")
    print(f"   • Or keep this as a backup")
    
    print(f"\n3. Use with the test script:")
    print(f"   python test_spiffs_build.py COM3 --no-flash --mkspiffs")
    
    print("\n" + "="*70 + "\n")
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Build cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
