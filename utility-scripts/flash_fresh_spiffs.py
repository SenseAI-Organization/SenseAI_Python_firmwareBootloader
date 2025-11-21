#!/usr/bin/env python3
"""
Flash fresh SPIFFS image to device and test if it works.
This will definitively answer: does the device validate metadata checksums?
"""

import os
import sys
import argparse
from pathlib import Path

# Import the utilities
from spiffs_utils import SPIFFSManager
from flash_utils import FlashManager


def main():
    parser = argparse.ArgumentParser(
        description="Flash fresh SPIFFS image to device for testing"
    )
    parser.add_argument('port', help='COM port (e.g., COM3)')
    parser.add_argument('--chip', default='esp32s3', help='Chip type (default: esp32s3)')
    parser.add_argument('--baud', default=115200, type=int, help='Baud rate')
    parser.add_argument('--image', default=None, help='Image to flash (default: spiffs_fresh_build.bin)')
    
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine which image to flash
    if args.image:
        spiffs_image = os.path.join(script_dir, args.image)
    else:
        spiffs_image = os.path.join(script_dir, "spiffs_fresh_build.bin")
    
    print("\n" + "="*70)
    print("FLASHING FRESH SPIFFS IMAGE TO DEVICE")
    print("="*70)
    print(f"Image: {spiffs_image}")
    print(f"Port: {args.port}")
    print(f"Chip: {args.chip}")
    print(f"Baud: {args.baud}")
    
    # Check image exists
    if not os.path.exists(spiffs_image):
        print(f"[ERROR] Image not found: {spiffs_image}")
        return 1
    
    image_size = os.path.getsize(spiffs_image)
    print(f"Image size: {image_size} bytes (0x{image_size:X})")
    print("="*70 + "\n")
    
    # Create managers
    def logger(msg, level='info'):
        prefix = {
            'info': '[INFO]',
            'success': '[OK]',
            'error': '[ERROR]',
            'warning': '[WARN]',
            'debug': '[DEBUG]'
        }.get(level, '[*]')
        print(f"{prefix} {msg}")
    
    spiffs = SPIFFSManager(script_dir=script_dir, logger=logger)
    flash = FlashManager(logger=logger)
    
    # Detect SPIFFS partition
    print("[*] Detecting SPIFFS partition from device...")
    spiffs_info = spiffs.detect_spiffs_partition(args.port, args.chip)
    if not spiffs_info:
        print("[ERROR] Could not detect SPIFFS partition")
        return 1
    
    spiffs_offset, spiffs_size = spiffs_info
    print(f"[OK] SPIFFS partition: 0x{spiffs_offset:X} ({spiffs_size} bytes)\n")
    
    # Verify image size matches partition
    if image_size != spiffs_size:
        print(f"[WARN] Image size ({image_size}) != partition size ({spiffs_size})")
        response = input("Continue anyway? (y/n): ").lower()
        if response != 'y':
            return 1
    
    # Flash the image
    print("[*] Flashing SPIFFS image...")
    print("-" * 70)
    
    def progress_callback(percent, message):
        if percent is not None:
            print(f"    {percent:.1f}% {message}")
    
    success = flash.flash_spiffs(
        port=args.port,
        chip=args.chip,
        baud=args.baud,
        spiffs_image=spiffs_image,
        offset=spiffs_offset,
        flash_freq='40m',
        progress_callback=progress_callback
    )
    
    print("-" * 70)
    
    if not success:
        print("[ERROR] Flash failed")
        return 1
    
    # Success!
    print("\n" + "="*70)
    print("[OK] SPIFFS image flashed successfully!")
    print("="*70)
    print("\nTEST RESULTS:")
    print("-" * 70)
    print("""
If your device boots and can read the certificate files, then:
  -> The metadata checksums are NOT strictly validated
  -> We CAN use dynamically built SPIFFS images!
  -> Your theory about modifying files in-place is viable!

If your device fails to mount SPIFFS or read files, then:
  -> The metadata checksums ARE validated
  -> We must use the pre-built image approach
  -> Files can only be updated by rebuilding with mkspiffs

Check your device serial output for:
  1. "SPIFFS mounted" or similar message (indicates mount success)
  2. Certificate parsing errors or success
  3. Any "invalid" or "CRC" error messages
""")
    print("="*70 + "\n")
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[WARN] Cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
