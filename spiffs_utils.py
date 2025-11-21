"""
SPIFFS Utilities for ESP32
Handles partition detection, image building, and file management
"""

import os
import subprocess
import struct
import tempfile
import shutil
import sys


class SPIFFSManager:
    """Manages SPIFFS partition detection, image building, and flashing"""
    
    def __init__(self, script_dir=None, logger=None):
        """
        Initialize SPIFFS manager
        
        Args:
            script_dir: Directory where the app is running (for locating tools/images)
            logger: Optional logger callback function(message, level='info')
        """
        self.script_dir = script_dir or os.path.dirname(os.path.abspath(__file__))
        self.logger = logger or self._default_logger
        
        # SPIFFS parameters - MUST match ESP-IDF defaults exactly
        # These are from the official ESP32 SPIFFS configuration
        # Reference: https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/storage/spiffs.html
        self.PAGE_SIZE = 256           # bytes - page size for SPIFFS
        self.BLOCK_SIZE = 4096         # bytes - erase block size
        self.OBJECT_NAME_LEN = 32      # characters - max filename length
        self.META_LENGTH = 4           # bytes - metadata length per object
        self.USE_MAGIC = True          # use magic numbers for validation
        self.USE_MAGIC_LENGTH = 2      # length of magic bytes
    
    @staticmethod
    def _default_logger(message, level='info'):
        """Default logger - just prints to console"""
        prefix = {
            'info': '📝',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'debug': '🔍'
        }.get(level, '•')
        print(f"{prefix} {message}")
    
    def log(self, message, level='info'):
        """Log a message"""
        self.logger(message, level)
    
    def detect_spiffs_partition(self, port, chip):
        """
        Detect SPIFFS partition address and size from device
        
        Reads the partition table from device at offset 0x8000 (4KB)
        and finds the SPIFFS partition (type=1, subtype=0x82)
        
        Args:
            port: COM port (e.g., 'COM3')
            chip: Chip type (e.g., 'esp32s3')
            
        Returns:
            Tuple of (offset, size) in bytes, or None if not found
        """
        try:
            python_exe = shutil.which('pythonw') or shutil.which('python') or sys.executable
            temp_file = os.path.join(self.script_dir, "temp_partitions.bin")
            
            self.log(f"Reading partition table from {port}...", "debug")
            
            # Read partition table from device at 0x8000
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", "115200",
                "read-flash",
                "0x8000", "0x1000",  # Read 4KB partition table
                temp_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0 or not os.path.exists(temp_file):
                self.log(f"Failed to read partition table: {result.stderr}", "error")
                return None
            
            # Parse partition table to find SPIFFS
            with open(temp_file, 'rb') as f:
                data = f.read()
            
            # Clean up temp file
            try:
                os.remove(temp_file)
            except:
                pass
            
            # Check magic bytes
            if len(data) < 32 or data[0:2] != b'\xAA\x50':
                self.log("Invalid partition table magic bytes", "error")
                return None
            
            # Parse entries (32 bytes each)
            offset = 0
            while offset + 32 <= len(data):
                if data[offset:offset+2] != b'\xAA\x50':
                    break
                
                ptype = data[offset+2]
                subtype = data[offset+3]
                p_offset = struct.unpack('<I', data[offset+4:offset+8])[0]
                p_size = struct.unpack('<I', data[offset+8:offset+12])[0]
                label = data[offset+12:offset+28].decode('utf-8', errors='ignore').rstrip('\x00')
                
                # SPIFFS is type 1 (data), subtype 0x82
                if ptype == 1 and subtype == 0x82:
                    self.log(f"Found SPIFFS partition: {label} @ 0x{p_offset:X}, size 0x{p_size:X}", "success")
                    return (p_offset, p_size)
                
                offset += 32
            
            self.log("No SPIFFS partition found in partition table", "error")
            return None
            
        except Exception as e:
            self.log(f"Error detecting SPIFFS partition: {e}", "error")
            return None
    
    def should_rebuild_spiffs(self, data_folder, output_file):
        """
        Check if SPIFFS image needs rebuilding.
        Only rebuild if data folder contents changed (matches PlatformIO behavior).
        This prevents non-deterministic metadata changes that can cause device issues.
        
        Args:
            data_folder: Path to data/ folder with files
            output_file: Path to SPIFFS image output
            
        Returns:
            True if rebuild needed, False if cached image is valid
        """
        if not os.path.exists(output_file):
            self.log("No existing SPIFFS image, will rebuild", "debug")
            return True
        
        try:
            # Get the latest modification time from all files in data folder
            latest_data_mtime = 0
            for root, dirs, files in os.walk(data_folder):
                for f in files:
                    file_path = os.path.join(root, f)
                    mtime = os.path.getmtime(file_path)
                    latest_data_mtime = max(latest_data_mtime, mtime)
            
            # Get the modification time of the output image
            output_mtime = os.path.getmtime(output_file)
            
            # Rebuild only if data is newer than image
            should_rebuild = latest_data_mtime > output_mtime
            if not should_rebuild:
                self.log("SPIFFS image is up-to-date (data unchanged), skipping rebuild", "debug")
            else:
                self.log("Data folder modified, will rebuild SPIFFS image", "debug")
            
            return should_rebuild
        except Exception as e:
            self.log(f"Error checking SPIFFS cache: {e}, will rebuild", "debug")
            return True
    
    def find_mkspiffs(self):
        """
        Find mkspiffs binary from multiple sources:
        1. Repository tools/ folder
        2. PATH environment variable
        3. PlatformIO packages
        
        Returns:
            Path to mkspiffs binary, or None if not found
        """
        candidates = []
        
        # Helper: search repository 'tools' folder
        def repo_tools_candidates(name):
            tools_dir = os.path.join(self.script_dir, 'tools')
            candidates_list = []
            if os.path.exists(tools_dir):
                for root, _, files in os.walk(tools_dir):
                    for f in files:
                        if f.lower() == name.lower() or f.lower().startswith(name.lower()):
                            candidates_list.append(os.path.join(root, f))
            return candidates_list
        
        # Check repo tools folder
        candidates.extend(repo_tools_candidates('mkspiffs.exe'))
        candidates.extend(repo_tools_candidates('mkspiffs'))
        
        # Check PATH
        which_path = shutil.which('mkspiffs')
        if which_path:
            candidates.append(which_path)
        
        # Check PlatformIO packages
        try:
            pio_base = os.path.join(os.path.expanduser('~'), '.platformio', 'packages')
            if os.path.exists(pio_base):
                for root, dirs, files in os.walk(pio_base):
                    for d in dirs:
                        if d.lower().startswith('tool-mkspiffs') or d.lower().startswith('mkspiffs'):
                            candidate = os.path.join(root, d)
                            for sub in ('bin', ''):
                                cand = os.path.join(candidate, sub, 'mkspiffs.exe')
                                if os.path.exists(cand):
                                    candidates.append(cand)
                                cand = os.path.join(candidate, sub, 'mkspiffs')
                                if os.path.exists(cand):
                                    candidates.append(cand)
        except Exception as e:
            self.log(f"Error searching PlatformIO packages: {e}", "debug")
        
        # Use first valid candidate
        for cand in candidates:
            if os.path.exists(cand) and os.path.isfile(cand):
                self.log(f"Found mkspiffs at: {cand}", "success")
                return cand
        
        self.log("mkspiffs not found", "warning")
        return None
    
    def build_spiffs_image_from_mkspiffs(self, data_folder, output_file, size):
        """
        Build SPIFFS image using mkspiffs binary.
        
        Files from data/ are stored as /filename in SPIFFS.
        When mounted at /spiffs, they become /spiffs/filename (matching firmware expectations).
        
        Args:
            data_folder: Path to data/ folder with files
            output_file: Path to output SPIFFS image
            size: Size of SPIFFS partition in bytes
            
        Returns:
            True if successful, False otherwise
        """
        mkspiffs = self.find_mkspiffs()
        if not mkspiffs:
            self.log("mkspiffs binary not found", "error")
            self.log("Install via: pip install mkspiffs", "info")
            return False
        
        try:
            self.log(f"Building SPIFFS image with mkspiffs...", "info")
            self.log(f"  Input: {data_folder}", "debug")
            self.log(f"  Output: {output_file}", "debug")
            self.log(f"  Size: {size} bytes", "debug")
            self.log(f"  Page size: {self.PAGE_SIZE} bytes (-p {self.PAGE_SIZE})", "debug")
            self.log(f"  Block size: {self.BLOCK_SIZE} bytes (-b {self.BLOCK_SIZE})", "debug")
            
            cmd = [
                mkspiffs,
                "-c", data_folder,
                "-s", str(size),
                "-p", str(self.PAGE_SIZE),
                "-b", str(self.BLOCK_SIZE),
                output_file
            ]
            
            self.log(f"Command: {' '.join(cmd)}", "debug")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.log(f"mkspiffs error: {result.stderr}", "error")
                return False
            
            if os.path.exists(output_file):
                size_actual = os.path.getsize(output_file)
                self.log(f"SPIFFS image created successfully: {size_actual} bytes", "success")
                return True
            else:
                self.log("SPIFFS image file not created", "error")
                return False
        
        except Exception as e:
            self.log(f"Error building SPIFFS image: {e}", "error")
            return False
    
    def build_spiffs_image_with_prebuilt(self, data_folder, output_file, size, known_good_image=None):
        """
        Build SPIFFS image by copying a known-good pre-built image.
        This is the most reliable approach because:
        - mkspiffs generates non-deterministic metadata each run
        - Device SPIFFS driver validates metadata and can reject "new" images
        - Using a pre-built tested image ensures device always accepts it
        
        Args:
            data_folder: Path to data/ folder (checked for modification)
            output_file: Path to output SPIFFS image
            size: Expected size of SPIFFS partition (validation only)
            known_good_image: Path to pre-built image (default: spiffs_with_correct_names.bin)
            
        Returns:
            True if successful, False otherwise
        """
        if known_good_image is None:
            known_good_image = os.path.join(self.script_dir, "spiffs_with_correct_names.bin")
        
        # Check if rebuild is needed
        if not self.should_rebuild_spiffs(data_folder, output_file):
            self.log(f"Using cached SPIFFS image: {output_file}", "debug")
            return True
        
        if not os.path.exists(known_good_image):
            self.log(f"Known-good SPIFFS image not found: {known_good_image}", "error")
            self.log("To create one:", "info")
            self.log("  1. Build with mkspiffs: mkspiffs -c data -s 1212416 -p 256 -b 4096 spiffs_with_correct_names.bin", "info")
            self.log("  2. Test on device to verify it mounts", "info")
            self.log("  3. Once working, use it as known-good image", "info")
            return False
        
        try:
            self.log(f"Preparing SPIFFS image (using known-good template)...", "info")
            shutil.copy2(known_good_image, output_file)
            
            actual_size = os.path.getsize(output_file)
            self.log(f"✅ SPIFFS image prepared: {actual_size} bytes", "success")
            
            if actual_size != size:
                self.log(f"⚠️  Image size ({actual_size}) differs from partition size ({size})", "warning")
                self.log(f"    This may cause issues. Expected size: {size} bytes", "warning")
                return False
            
            return True
        
        except Exception as e:
            self.log(f"Error copying SPIFFS image: {e}", "error")
            return False
    
    def validate_data_folder(self, data_folder):
        """
        Validate that data folder exists and has files.
        
        Args:
            data_folder: Path to data/ folder
            
        Returns:
            List of files if valid, None otherwise
        """
        if not os.path.exists(data_folder):
            self.log(f"Data folder not found: {data_folder}", "error")
            return None
        
        if not os.path.isdir(data_folder):
            self.log(f"Not a directory: {data_folder}", "error")
            return None
        
        files = [f for f in os.listdir(data_folder) if os.path.isfile(os.path.join(data_folder, f))]
        
        if not files:
            self.log(f"Data folder is empty: {data_folder}", "warning")
            return None
        
        self.log(f"Found {len(files)} file(s) in data folder:", "info")
        for f in files:
            filepath = os.path.join(data_folder, f)
            size = os.path.getsize(filepath)
            self.log(f"  • {f} ({size} bytes)", "info")
        
        return files
    
    def build_spiffs_with_smart_caching(self, data_folder, output_file, size):
        """
        Build SPIFFS image with intelligent caching strategy (matches PlatformIO behavior).
        
        This implements the key insight discovered through testing:
        - Device validates SPIFFS metadata ONCE when first flashed
        - Subsequent flashes with SAME metadata work fine
        - Fresh mkspiffs builds with NEW metadata may fail initially
        - BUT if device accepts new metadata, it can be used again
        
        Strategy:
        1. Check if data folder is NEWER than output image
        2. If NOT: use cached image (device already knows this metadata)
        3. If YES: rebuild with mkspiffs (will generate new metadata)
        4. First flash of new metadata: device validates it
        5. Future flashes: reuse same image (caching)
        
        Args:
            data_folder: Path to data/ folder
            output_file: Path to output SPIFFS image
            size: Size of SPIFFS partition
            
        Returns:
            Tuple (success: bool, image_path: str, reason: str)
        """
        # Check if rebuild is needed
        if not self.should_rebuild_spiffs(data_folder, output_file):
            self.log(f"SPIFFS cache valid - using cached image", "info")
            self.log(f"  Cache: {output_file}", "debug")
            self.log(f"  (Data folder unchanged since last build)", "debug")
            return (True, output_file, "Using cached image (data unchanged)")
        
        self.log(f"Data folder changed - rebuilding SPIFFS image", "info")
        self.log(f"  Data folder newer than cached image", "debug")
        self.log(f"  Will generate new image with fresh metadata", "debug")
        
        # Rebuild with mkspiffs
        success = self.build_spiffs_image_from_mkspiffs(
            data_folder=data_folder,
            output_file=output_file,
            size=size
        )
        
        if not success:
            self.log(f"Failed to rebuild SPIFFS image", "error")
            # Fallback to cached if it exists
            if os.path.exists(output_file):
                self.log(f"Falling back to cached image", "warning")
                return (True, output_file, "Build failed, using cached image")
            return (False, None, "Failed to build and no cache available")
        
        self.log(f"New SPIFFS image built successfully", "success")
        self.log(f"  First flash will validate metadata", "info")
        self.log(f"  Future flashes will reuse this image", "info")
        
        return (True, output_file, "New image built (fresh metadata)")
