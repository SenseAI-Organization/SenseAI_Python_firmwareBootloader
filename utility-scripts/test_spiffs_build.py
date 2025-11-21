#!/usr/bin/env python3
"""
Standalone SPIFFS Build & Flash Test Script
Demonstrates how the Upload Data Folder button works.
Calls the exact same functions used by the main application.

Usage:
    python test_spiffs_build.py <port> [chip] [data_folder]

Examples:
    python test_spiffs_build.py COM3
    python test_spiffs_build.py COM3 esp32s3 ./data
"""

import os
import sys
import argparse
from pathlib import Path

# Import the utilities we just created
from spiffs_utils import SPIFFSManager
from flash_utils import FlashManager


def main():
    """Main test function"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Test SPIFFS build and flash (mimics Upload Data Folder button)",
        epilog="Example: python test_spiffs_build.py COM3 esp32s3"
    )
    
    parser.add_argument('port', help='COM port (e.g., COM3)')
    parser.add_argument('--chip', default='esp32s3', help='Chip type (default: esp32s3)')
    parser.add_argument('--data', default=None, help='Data folder (default: ./data)')
    parser.add_argument('--baud', default=115200, type=int, help='Baud rate (default: 115200)')
    parser.add_argument('--no-flash', action='store_true', help='Skip flashing, just build image')
    parser.add_argument('--mkspiffs', action='store_true', help='Use mkspiffs to build (not pre-built image)')
    parser.add_argument('--flash-freq', default='40m', help='Flash frequency (default: 40m)')
    
    args = parser.parse_args()
    
    # Determine data folder
    if args.data:
        data_folder = os.path.abspath(args.data)
    else:
        data_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("\n" + "="*70)
    print("🔧 SPIFFS BUILD & FLASH TEST")
    print("="*70)
    print(f"Script directory: {script_dir}")
    print(f"Data folder: {data_folder}")
    print(f"Port: {args.port}")
    print(f"Chip: {args.chip}")
    print(f"Baud: {args.baud}")
    print(f"Flash frequency: {args.flash_freq}")
    print("="*70 + "\n")
    
    # Initialize managers
    spiffs = SPIFFSManager(script_dir=script_dir)
    flash = FlashManager()
    
    # Step 1: Validate data folder
    print("\n📋 STEP 1: VALIDATING DATA FOLDER")
    print("-" * 70)
    files = spiffs.validate_data_folder(data_folder)
    if not files:
        print("\n❌ No files found in data folder. Exiting.")
        return 1
    
    # Step 2: Detect SPIFFS partition
    print("\n\n🔍 STEP 2: DETECTING SPIFFS PARTITION")
    print("-" * 70)
    spiffs_info = spiffs.detect_spiffs_partition(args.port, args.chip)
    if not spiffs_info:
        print("\n❌ Failed to detect SPIFFS partition. Exiting.")
        return 1
    
    spiffs_offset, spiffs_size = spiffs_info
    print(f"\n✅ SPIFFS Partition Found:")
    print(f"   Offset: 0x{spiffs_offset:X} ({spiffs_offset} bytes)")
    print(f"   Size: 0x{spiffs_size:X} ({spiffs_size} bytes)")
    
    # Step 3: Build SPIFFS image
    print("\n\n🔨 STEP 3: BUILDING SPIFFS IMAGE")
    print("-" * 70)
    
    spiffs_image = os.path.join(script_dir, "test_spiffs_output.bin")
    
    if args.mkspiffs:
        # Use mkspiffs to build
        print(f"\nBuilding with mkspiffs...")
        success = spiffs.build_spiffs_image_from_mkspiffs(
            data_folder=data_folder,
            output_file=spiffs_image,
            size=spiffs_size
        )
    else:
        # Use pre-built image (recommended)
        print(f"\nBuilding from pre-built image...")
        success = spiffs.build_spiffs_image_with_prebuilt(
            data_folder=data_folder,
            output_file=spiffs_image,
            size=spiffs_size
        )
    
    if not success:
        print("\n❌ Failed to build SPIFFS image. Exiting.")
        return 1
    
    print(f"\n✅ SPIFFS Image Ready: {spiffs_image}")
    print(f"   Size: {os.path.getsize(spiffs_image)} bytes")
    
    # Step 4: Flash (optional)
    if args.no_flash:
        print("\n\n⏭️  Skipping flash (--no-flash specified)")
        print("\nTo flash manually:")
        print(f"  esptool.py --chip {args.chip} --port {args.port} --baud {args.baud} \\")
        print(f"    write-flash --flash-mode dio --flash-freq {args.flash_freq} \\")
        print(f"    0x{spiffs_offset:X} {spiffs_image}")
        return 0
    
    print("\n\n📤 STEP 4: FLASHING SPIFFS")
    print("-" * 70)
    
    def progress_callback(percent, message):
        """Progress callback for flashing"""
        if percent is not None:
            print(f"  {percent:.1f}% - {message}")
    
    success = flash.flash_spiffs(
        port=args.port,
        chip=args.chip,
        baud=args.baud,
        spiffs_image=spiffs_image,
        offset=spiffs_offset,
        flash_freq=args.flash_freq,
        progress_callback=progress_callback
    )
    
    # Final result
    print("\n" + "="*70)
    if success:
        print("✅ SUCCESS! SPIFFS uploaded and flashed successfully")
        print("="*70)
        print("\nThe ESP32 should now have access to files in /spiffs/")
        print("Expected files on device:")
        for f in files:
            print(f"  /spiffs/{f}")
        print("\n")
        return 0
    else:
        print("❌ FAILED! Flash operation did not complete")
        print("="*70 + "\n")
        return 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
