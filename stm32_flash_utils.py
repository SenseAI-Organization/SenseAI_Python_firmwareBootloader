"""
Flash Utilities for STM32WLE5
Handles STM32CubeProgrammer CLI interaction for firmware flashing via SWD.
"""

import subprocess
import os
import re
import shutil
import hashlib
import struct


class STM32FlashManager:
    """Manages STM32 firmware flashing via STM32CubeProgrammer CLI (SWD)."""

    # Default flash parameters for STM32WLE5JCI6
    FLASH_START = 0x08000000
    FLASH_END = 0x0803FFFF
    FLASH_SIZE = 256 * 1024  # 256KB
    SECTOR_SIZE = 2048
    UID_ADDRESS = 0x1FFF7590
    UID_SIZE = 12  # 96-bit = 12 bytes

    def __init__(self, logger=None, cube_programmer_path=None):
        self.logger = logger or self._default_logger
        self.cube_programmer_path = cube_programmer_path or self._find_cube_programmer()

    @staticmethod
    def _default_logger(message, level='info'):
        prefix = {'info': '[I]', 'success': '[OK]', 'error': '[ERR]',
                  'warning': '[WARN]', 'debug': '[DBG]'}.get(level, '[*]')
        print(f"{prefix} {message}")

    def log(self, message, level='info'):
        self.logger(message, level)

    # ------------------------------------------------------------------
    # STM32CubeProgrammer discovery
    # ------------------------------------------------------------------
    def _find_cube_programmer(self):
        """Locate STM32_Programmer_CLI on the system."""
        # Check PATH first
        which = shutil.which("STM32_Programmer_CLI") or shutil.which("STM32_Programmer_CLI.exe")
        if which:
            return which

        # Common install locations on Windows
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                         "STMicroelectronics", "STM32Cube", "STM32CubeProgrammer", "bin",
                         "STM32_Programmer_CLI.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"),
                         "STMicroelectronics", "STM32Cube", "STM32CubeProgrammer", "bin",
                         "STM32_Programmer_CLI.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

        return None

    def is_programmer_available(self):
        """Return True if STM32_Programmer_CLI is found."""
        return self.cube_programmer_path is not None and os.path.isfile(self.cube_programmer_path)

    def set_programmer_path(self, path):
        """Manually set the path to STM32_Programmer_CLI."""
        if os.path.isfile(path):
            self.cube_programmer_path = path
            return True
        return False

    # ------------------------------------------------------------------
    # Low-level CLI helpers
    # ------------------------------------------------------------------
    def _run_cli(self, args, timeout=60):
        """Run STM32_Programmer_CLI with given arguments.
        Returns (returncode, stdout, stderr).
        """
        if not self.is_programmer_available():
            return (1, "", "STM32_Programmer_CLI not found")

        cmd = [self.cube_programmer_path] + list(args)
        self.log(f"CMD: {' '.join(cmd)}", "debug")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return (proc.returncode, proc.stdout or "", proc.stderr or "")
        except subprocess.TimeoutExpired:
            return (1, "", "Command timed out")
        except Exception as e:
            return (1, "", str(e))

    # ------------------------------------------------------------------
    # Device detection & UID
    # ------------------------------------------------------------------
    def connect_and_detect(self):
        """Connect via SWD and detect the target MCU.
        Returns dict with keys: connected, chip_id, description, error
        """
        rc, out, err = self._run_cli([
            "--connect", "port=SWD", "mode=NORMAL", "reset=HWrst",
            "--list"
        ], timeout=20)

        result = {"connected": False, "chip_id": "", "description": "", "error": ""}

        if rc != 0:
            result["error"] = err or out
            return result

        combined = out + err
        # Look for device ID line
        for line in combined.splitlines():
            if "Device ID" in line or "device ID" in line:
                result["chip_id"] = line.strip()
                result["connected"] = True
            if "Device name" in line or "device name" in line:
                result["description"] = line.strip()
                result["connected"] = True

        if not result["connected"]:
            # Check for any connected indicator
            if "ST-LINK" in combined or "Connected" in combined:
                result["connected"] = True
                result["description"] = "STM32 device detected"

        return result

    def read_device_uid(self):
        """Read the 96-bit unique device ID from address 0x1FFF7590.
        Returns hex string like '1A2B3C4D5E6F7890ABCDEF12' or None on error.
        """
        rc, out, err = self._run_cli([
            "--connect", "port=SWD", "mode=NORMAL", "reset=HWrst",
            "--read", hex(self.UID_ADDRESS), str(self.UID_SIZE)
        ], timeout=15)

        if rc != 0:
            self.log(f"Failed to read UID: {err}", "error")
            return None

        # Parse hex dump from output
        uid_bytes = self._parse_hex_dump(out, self.UID_ADDRESS, self.UID_SIZE)
        if uid_bytes and len(uid_bytes) >= self.UID_SIZE:
            return uid_bytes[:self.UID_SIZE].hex().upper()
        return None

    def _parse_hex_dump(self, output, start_addr, size):
        """Parse STM32CubeProgrammer hex dump output into bytes."""
        result = bytearray()
        for line in output.splitlines():
            line = line.strip()
            # Lines look like: 0x1FFF7590 : 4D3C2B1A 6F5E4D3C ...
            match = re.match(r'0x([0-9A-Fa-f]+)\s*:\s*(.*)', line)
            if match:
                addr = int(match.group(1), 16)
                if addr >= start_addr and addr < start_addr + size + 16:
                    hex_data = match.group(2).strip()
                    # Remove any non-hex characters (ASCII dump portion)
                    hex_words = re.findall(r'[0-9A-Fa-f]{8}', hex_data)
                    for word in hex_words:
                        # STM32CubeProgrammer outputs words in big-endian display
                        # but the actual memory is little-endian
                        result.extend(bytes.fromhex(word))
        return bytes(result)

    # ------------------------------------------------------------------
    # Flash operations
    # ------------------------------------------------------------------
    def erase_flash(self, full_chip=True, progress_callback=None):
        """Erase flash memory.
        If full_chip=True, erases entire flash. Otherwise erases sectors for app area only.
        """
        if progress_callback:
            progress_callback(0, "Erasing flash...")

        if full_chip:
            rc, out, err = self._run_cli([
                "--connect", "port=SWD", "mode=NORMAL", "reset=HWrst",
                "--erase", "all"
            ], timeout=30)
        else:
            # Erase only app sectors (not the last sectors reserved for LoRaWAN NVM/SE)
            rc, out, err = self._run_cli([
                "--connect", "port=SWD", "mode=NORMAL", "reset=HWrst",
                "--erase", "0x08000000", "0x0803DFFF"
            ], timeout=30)

        if progress_callback:
            progress_callback(100 if rc == 0 else 0,
                              "Erase complete" if rc == 0 else "Erase failed")

        if rc != 0:
            self.log(f"Erase failed: {err or out}", "error")
            return False

        self.log("Flash erased successfully", "success")
        return True

    def program_firmware(self, firmware_path, verify=True, progress_callback=None):
        """Program firmware file (.hex or .bin) to flash.
        Returns dict: {success, file, size_bytes, checksum_crc32, duration_text}
        """
        if not os.path.isfile(firmware_path):
            self.log(f"Firmware file not found: {firmware_path}", "error")
            return {"success": False, "error": "File not found"}

        file_size = os.path.getsize(firmware_path)
        crc32 = self._file_crc32(firmware_path)

        if progress_callback:
            progress_callback(0, "Programming flash...")

        args = [
            "--connect", "port=SWD", "mode=NORMAL", "reset=HWrst",
            "--download", firmware_path
        ]

        # For .bin files, specify the start address
        if firmware_path.lower().endswith('.bin'):
            args.extend([hex(self.FLASH_START)])

        if verify:
            args.append("--verify")

        args.extend(["--start", hex(self.FLASH_START)])

        import time
        t0 = time.time()
        rc, out, err = self._run_cli(args, timeout=120)
        duration = time.time() - t0

        if progress_callback:
            progress_callback(100 if rc == 0 else 0,
                              "Programming complete" if rc == 0 else "Programming failed")

        result = {
            "success": rc == 0,
            "file": os.path.basename(firmware_path),
            "size_bytes": file_size,
            "checksum_crc32": f"0x{crc32:08X}",
            "duration_seconds": round(duration, 1),
            "output": out,
        }

        if rc != 0:
            result["error"] = err or out
            self.log(f"Programming failed: {result['error']}", "error")
        else:
            self.log(f"Programmed {file_size} bytes in {duration:.1f}s (CRC32: 0x{crc32:08X})", "success")

        return result

    def verify_flash(self, firmware_path):
        """Verify flash contents against firmware file."""
        args = [
            "--connect", "port=SWD", "mode=NORMAL", "reset=HWrst",
            "--verify", firmware_path,
        ]
        if firmware_path.lower().endswith('.bin'):
            args.append(hex(self.FLASH_START))

        rc, out, err = self._run_cli(args, timeout=60)

        if rc == 0 and ("verified" in out.lower() or "File is verified" in out):
            self.log("Flash verification PASSED", "success")
            return True
        else:
            self.log(f"Flash verification FAILED: {err or out}", "error")
            return False

    def reset_device(self):
        """Reset the target MCU."""
        rc, out, err = self._run_cli([
            "--connect", "port=SWD", "mode=NORMAL",
            "--start", hex(self.FLASH_START)
        ], timeout=10)
        return rc == 0

    # ------------------------------------------------------------------
    # ST-Link detection
    # ------------------------------------------------------------------
    def list_stlinks(self):
        """List connected ST-Link debuggers.
        Returns list of dicts with 'serial' and 'description'.
        """
        rc, out, err = self._run_cli(["--list"], timeout=10)
        stlinks = []

        if rc != 0:
            return stlinks

        for line in out.splitlines():
            line = line.strip()
            # Look for serial number lines
            if "Serial number" in line or "SN" in line:
                match = re.search(r'(?:Serial number|SN)\s*[:=]\s*(\S+)', line, re.IGNORECASE)
                if match:
                    stlinks.append({
                        "serial": match.group(1),
                        "description": "ST-Link"
                    })

        return stlinks

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def _file_crc32(filepath):
        """Calculate CRC32 of a file."""
        import zlib
        crc = 0
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                crc = zlib.crc32(chunk, crc)
        return crc & 0xFFFFFFFF

    @staticmethod
    def derive_deveui_from_uid(uid_hex, prefix="70B3D57ED8"):
        """Derive a DevEUI from the 96-bit UID.
        Takes last bytes of UID and combines with OUI prefix.
        Returns 16-char hex string (8 bytes).
        """
        # Use hash of UID to derive unique 3 bytes
        uid_hash = hashlib.sha256(bytes.fromhex(uid_hex)).digest()
        suffix = uid_hash[:3].hex().upper()
        deveui = prefix + suffix
        return deveui[:16]  # Ensure exactly 8 bytes = 16 hex chars
