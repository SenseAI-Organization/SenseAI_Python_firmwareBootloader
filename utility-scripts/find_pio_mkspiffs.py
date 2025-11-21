#!/usr/bin/env python3
"""
Find PlatformIO mkspiffs version and configuration.
"""

import json
import os

# Check for PlatformIO package info
pio_packages_dir = os.path.expanduser('~/.platformio/packages')
if os.path.exists(pio_packages_dir):
    mkspiffs_dirs = []
    for d in os.listdir(pio_packages_dir):
        if 'mkspiffs' in d.lower():
            mkspiffs_dirs.append(d)
    
    if mkspiffs_dirs:
        print('[PLATFORMIO MKSPIFFS VERSIONS]')
        print('=' * 70)
        for d in mkspiffs_dirs:
            print(f'\n{d}')
            pkg_path = os.path.join(pio_packages_dir, d)
            
            # Check for metadata
            package_json = os.path.join(pkg_path, 'package.json')
            if os.path.exists(package_json):
                with open(package_json, 'r') as f:
                    try:
                        pkg = json.load(f)
                        version = pkg.get('version', 'unknown')
                        print(f'  Version: {version}')
                    except Exception as e:
                        print(f'  Error reading package.json: {e}')
            
            # List executable
            exe = os.path.join(pkg_path, 'mkspiffs.exe')
            if os.path.exists(exe):
                print(f'  Exe: {exe}')
                # Try to get version from executable
                import subprocess
                try:
                    result = subprocess.run([exe, '--help'], capture_output=True, text=True, timeout=5)
                    if result.stdout:
                        # Show first 500 chars of help
                        print(f'  Help output (first 500 chars):')
                        for line in result.stdout.split('\n')[:10]:
                            print(f'    {line}')
                except:
                    pass
    else:
        print('[NO PLATFORMIO MKSPIFFS FOUND]')
        print('Check ~/.platformio/packages/ directly')
else:
    print('[NO PLATFORMIO PACKAGES DIR]')

# Also check platformio.ini if it exists
platformio_ini = 'platformio.ini'
if os.path.exists(platformio_ini):
    print('\n[platformio.ini - SPIFFS related settings]')
    print('=' * 70)
    with open(platformio_ini, 'r') as f:
        for line in f:
            if 'spiffs' in line.lower() or 'mkspiffs' in line.lower():
                print(line.rstrip())
