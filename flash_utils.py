"""
Flash Utilities for ESP32
Handles esptool interaction and firmware flashing
"""

import subprocess
import sys
import re
import os


class FlashManager:
    """Manages ESP32 firmware and SPIFFS flashing"""
    
    def __init__(self, logger=None):
        """
        Initialize flash manager
        
        Args:
            logger: Optional logger callback function(message, level='info')
        """
        self.logger = logger or self._default_logger
    
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
    
    def flash_binary(self, port, chip, baud, binary_path, offset, 
                     flash_mode='dio', flash_freq='40m', 
                     progress_callback=None):
        """
        Flash a binary image to ESP32
        
        Args:
            port: COM port (e.g., 'COM3')
            chip: Chip type (e.g., 'esp32s3')
            baud: Baud rate (e.g., 115200)
            binary_path: Path to binary file to flash
            offset: Flash offset as 0xABCD format or integer
            flash_mode: Flash mode ('dio', 'dout', 'qio', 'qout')
            flash_freq: Flash frequency ('40m', '80m')
            progress_callback: Optional callback(percent, message) for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(binary_path):
            self.log(f"Binary file not found: {binary_path}", "error")
            return False
        
        try:
            python_exe = sys.executable
            
            # Convert offset if needed
            if isinstance(offset, int):
                offset_str = f"0x{offset:X}"
            else:
                offset_str = str(offset)
            
            binary_size = os.path.getsize(binary_path)
            self.log(f"Flashing {binary_path} ({binary_size} bytes) to 0x{offset_str}...", "info")
            
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", str(baud),
                "--before", "default-reset",
                "--after", "hard-reset",
                "write-flash",
                "-z",
                "--flash-mode", flash_mode,
                "--flash-freq", flash_freq,
                "--flash-size", "detect",
                offset_str, binary_path
            ]
            
            self.log(f"Command: {' '.join(cmd)}", "debug")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output
            for line in iter(process.stdout.readline, ''):
                if line:
                    line = line.strip()
                    
                    # Extract progress percentage
                    match = re.search(r'(\d+\.\d+)%', line)
                    if match and progress_callback:
                        percent = float(match.group(1))
                        progress_callback(percent, line)
                    
                    # Log important lines
                    if any(x in line for x in ['Connecting', 'Erasing', 'Writing', 'Hash', 'Uploading']):
                        self.log(line, "debug")
                        if progress_callback:
                            progress_callback(None, line)
            
            process.wait()
            
            if process.returncode == 0:
                self.log(f"Flash successful: {binary_path}", "success")
                return True
            else:
                self.log(f"Flash failed with code {process.returncode}", "error")
                return False
        
        except Exception as e:
            self.log(f"Error flashing binary: {e}", "error")
            return False
    
    def flash_spiffs(self, port, chip, baud, spiffs_image, offset, 
                     flash_freq='40m', progress_callback=None):
        """
        Flash a SPIFFS image
        Convenience wrapper for flash_binary with SPIFFS-specific defaults
        
        Args:
            port: COM port (e.g., 'COM3')
            chip: Chip type (e.g., 'esp32s3')
            baud: Baud rate (e.g., 115200)
            spiffs_image: Path to SPIFFS image
            offset: SPIFFS partition offset
            flash_freq: Flash frequency (default '40m' - important for stability)
            progress_callback: Optional callback(percent, message) for progress
            
        Returns:
            True if successful, False otherwise
        """
        return self.flash_binary(
            port=port,
            chip=chip,
            baud=baud,
            binary_path=spiffs_image,
            offset=offset,
            flash_mode='dio',
            flash_freq=flash_freq,
            progress_callback=progress_callback
        )
