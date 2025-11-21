#!/usr/bin/env python3
"""
FINAL SOLUTION: Smart SPIFFS Cache Manager

This implements the proven working strategy:
1. Use pre-built image as baseline (guaranteed device compatibility)
2. Check if data/ folder changed
3. If changed: rebuild with mkspiffs but understand device validation will happen
4. If unchanged: use cached image (fast, reliable)
"""

import os
import shutil
import hashlib
import time
from pathlib import Path


class SPIFFSCacheManager:
    """Manages SPIFFS builds with smart caching for device compatibility"""
    
    def __init__(self, script_dir, cache_dir=None):
        self.script_dir = script_dir
        self.cache_dir = cache_dir or script_dir
        self.data_folder = os.path.join(script_dir, 'data')
        self.cache_file = os.path.join(self.cache_dir, '.spiffs_cache')
        
        # Known-good pre-built images (in order of preference)
        self.known_good_images = [
            os.path.join(script_dir, 'spiffs_with_correct_names.bin'),
            os.path.join(script_dir, 'spiffs_with_correct_names_backup.bin'),
        ]
    
    def get_data_fingerprint(self):
        """Get hash of all files in data/ folder"""
        hasher = hashlib.md5()
        
        if not os.path.exists(self.data_folder):
            return None
        
        # Sort files for consistent order
        files = sorted(Path(self.data_folder).glob('*'))
        
        for file_path in files:
            if file_path.is_file():
                # Hash filename and content
                hasher.update(str(file_path.name).encode())
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
                # Hash modification time
                mtime = os.path.getmtime(file_path)
                hasher.update(str(mtime).encode())
        
        return hasher.hexdigest()
    
    def load_cached_fingerprint(self):
        """Load previously cached data fingerprint"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return f.read().strip()
            except:
                return None
        return None
    
    def save_cached_fingerprint(self):
        """Save current data fingerprint to cache"""
        fingerprint = self.get_data_fingerprint()
        if fingerprint:
            try:
                with open(self.cache_file, 'w') as f:
                    f.write(fingerprint)
            except:
                pass
    
    def should_rebuild(self):
        """Check if SPIFFS image needs rebuilding"""
        current = self.get_data_fingerprint()
        cached = self.load_cached_fingerprint()
        
        if current != cached:
            return True
        return False
    
    def get_working_image(self):
        """
        Get a working SPIFFS image.
        
        Strategy:
        1. Check if data/ unchanged → use cached image
        2. If data/ changed → rebuild with mkspiffs
        3. Fallback to known-good pre-built image
        
        Returns:
            (image_path, strategy_used)
        """
        
        # Strategy 1: Check cache
        if not self.should_rebuild():
            # Data unchanged, use pre-built image
            for image_path in self.known_good_images:
                if os.path.exists(image_path):
                    print(f"[CACHE HIT] Using cached image: {image_path}")
                    return image_path, "cache"
        
        # Strategy 2: Rebuild if data changed
        if self.should_rebuild():
            print("[REBUILD] Data folder changed, rebuilding SPIFFS image...")
            rebuild_result = self._rebuild_spiffs_image()
            if rebuild_result:
                self.save_cached_fingerprint()
                return rebuild_result, "rebuilt"
        
        # Strategy 3: Fallback to known-good
        for image_path in self.known_good_images:
            if os.path.exists(image_path):
                print(f"[FALLBACK] Using known-good image: {image_path}")
                return image_path, "fallback"
        
        print("[ERROR] No working SPIFFS image available!")
        return None, "failed"
    
    def _rebuild_spiffs_image(self):
        """Rebuild SPIFFS image with mkspiffs"""
        import subprocess
        
        output_file = os.path.join(self.cache_dir, 'spiffs_rebuilt.bin')
        
        # Try to find mkspiffs
        mkspiffs = self._find_mkspiffs()
        if not mkspiffs:
            print("[WARNING] mkspiffs not found, cannot rebuild")
            return None
        
        try:
            cmd = [
                mkspiffs,
                "-c", self.data_folder,
                "-b", "4096",  # Block size
                "-p", "256",   # Page size
                "-s", "1212416",  # Partition size
                output_file
            ]
            
            print(f"[BUILD] Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_file):
                size = os.path.getsize(output_file)
                if size == 1212416:
                    print(f"[SUCCESS] Built SPIFFS image: {output_file}")
                    return output_file
                else:
                    print(f"[ERROR] Size mismatch: expected 1212416, got {size}")
            else:
                print(f"[ERROR] mkspiffs failed: {result.stderr}")
        except Exception as e:
            print(f"[ERROR] {e}")
        
        return None
    
    def _find_mkspiffs(self):
        """Find mkspiffs binary"""
        import shutil
        
        # Check PATH
        mkspiffs = shutil.which('mkspiffs')
        if mkspiffs:
            return mkspiffs
        
        # Check PlatformIO
        pio_path = os.path.expanduser('~/.platformio/packages/tool-mkspiffs/mkspiffs')
        if os.path.exists(pio_path):
            return pio_path
        
        # Check Windows variant
        pio_path_exe = os.path.expanduser('~/.platformio/packages/tool-mkspiffs/mkspiffs.exe')
        if os.path.exists(pio_path_exe):
            return pio_path_exe
        
        return None


# Example usage
if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    manager = SPIFFSCacheManager(script_dir)
    
    print("[SPIFFS CACHE MANAGER]")
    print("=" * 70)
    
    # Check data status
    current_fp = manager.get_data_fingerprint()
    cached_fp = manager.load_cached_fingerprint()
    
    print(f"\nData fingerprint (current): {current_fp[:16]}...")
    print(f"Data fingerprint (cached):  {cached_fp[:16] if cached_fp else 'None'}...")
    print(f"Need rebuild: {manager.should_rebuild()}")
    
    # Get working image
    print("\nFinding working SPIFFS image...")
    image_path, strategy = manager.get_working_image()
    
    if image_path:
        print(f"\n✅ Using: {os.path.basename(image_path)}")
        print(f"   Strategy: {strategy}")
        print(f"   Size: {os.path.getsize(image_path)} bytes")
        print(f"\nReady to flash with:")
        print(f"   esptool write-flash 0x5F0000 {image_path}")
    else:
        print("\n❌ No working SPIFFS image found!")
        print("   Create one with: mkspiffs -c data -b 4096 -p 256 -s 1212416 spiffs.bin")
