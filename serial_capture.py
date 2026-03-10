"""
Serial Capture Module — Corona SmartFlux STM32 Bootloader
==========================================================
Listens on a COM/UART port after device programming to capture
the DevEUI, AppKey, and other credentials that the firmware
outputs at boot time.

The firmware on the STM32WLE5 generates its own LoRaWAN credentials
and prints them over UART.  This module captures that output and
parses the values so they can be logged accurately.
"""

import re
import time
import threading
import serial
import serial.tools.list_ports


# ---------------------------------------------------------------------------
# Default regex patterns — matched against the firmware's firstBootPrintDevEUI()
# output.  The device prints (3x for reliability):
#
#     DEVEUI:70B3D57ED8004E5B\r\n
#     JOINEUI:24E124C0002A0001\r\n
#     APPKEY:ED1DC3BFBEEFC91EDABE077AC3E460F0\r\n
#     DEVADDR:00000000\r\n
#     FW:1.2\r\n
#     ---\r\n
#
# ---------------------------------------------------------------------------
DEFAULT_PATTERNS = {
    "deveui":  re.compile(
        r"DEVEUI:(?P<value>[0-9A-Fa-f]{16})", re.IGNORECASE),
    "joineui":  re.compile(
        r"JOINEUI:(?P<value>[0-9A-Fa-f]{16})", re.IGNORECASE),
    "appkey":  re.compile(
        r"APPKEY:(?P<value>[0-9A-Fa-f]{32})", re.IGNORECASE),
    "devaddr": re.compile(
        r"DEVADDR:(?P<value>[0-9A-Fa-f]{8})", re.IGNORECASE),
    "fw_version": re.compile(
        r"FW:(?P<value>\d+\.\d+)", re.IGNORECASE),
}

# The firmware sends "---" after each credential block
END_MARKER = "---"

# Keys that are required for a "complete" capture
REQUIRED_KEYS = {"deveui", "joineui", "appkey"}


class SerialCapture:
    """
    Opens a serial port, reads lines, and parses LoRaWAN credentials
    from the device's boot output.
    """

    def __init__(self, port=None, baudrate=115200, timeout_seconds=15,
                 patterns=None, logger=None):
        """
        Parameters
        ----------
        port : str
            COM port name (e.g. "COM3", "/dev/ttyACM0").
        baudrate : int
            UART baud rate (default 115200).
        timeout_seconds : float
            How long to wait for the expected output before giving up.
        patterns : dict[str, re.Pattern]
            Override the default regex patterns with custom ones.
        logger : callable(message, level)
            Optional callback for log messages.
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout_seconds = timeout_seconds
        self.patterns = patterns or dict(DEFAULT_PATTERNS)
        self._log = logger or (lambda m, l="info": None)

        self._serial = None
        self._captured = {}
        self._raw_lines = []
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Port discovery
    # ------------------------------------------------------------------
    @staticmethod
    def list_com_ports():
        """Return a list of available COM ports as dicts."""
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append({
                "device": p.device,
                "description": p.description,
                "hwid": p.hwid,
                "manufacturer": p.manufacturer or "",
            })
        return sorted(ports, key=lambda x: x["device"])

    @staticmethod
    def find_stlink_vcp():
        """Try to find an ST-Link Virtual COM Port automatically."""
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            mfr = (p.manufacturer or "").lower()
            hwid = (p.hwid or "").lower()
            if any(tag in desc for tag in ("st-link", "stlink", "stm")):
                return p.device
            if "stmicroelectronics" in mfr:
                return p.device
            # ST-Link USB VID
            if "0483" in hwid:
                return p.device
        return None

    # ------------------------------------------------------------------
    # Core capture
    # ------------------------------------------------------------------
    def open(self):
        """Open the serial port."""
        if not self.port:
            raise ValueError("No COM port specified")
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=1,          # read timeout per iteration
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
        # Flush any stale data
        self._serial.reset_input_buffer()
        self._log(f"Serial port {self.port} opened @ {self.baudrate} baud", "info")

    def close(self):
        """Close the serial port."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._log(f"Serial port {self.port} closed", "info")

    def capture(self, reset_callback=None):
        """
        Blocking call: reads serial lines until all expected fields are
        captured or the timeout expires.

        Parameters
        ----------
        reset_callback : callable or None
            If provided, called right after opening the port to trigger
            a device reset (so the firmware re-prints its boot banner).

        Returns
        -------
        dict  with keys:
            "success"  : bool
            "captured" : dict of parsed key→value pairs
            "raw"      : list of raw lines received
            "missing"  : list of required keys not found
            "elapsed"  : float seconds
        """
        self._captured = {}
        self._raw_lines = []
        self._stop_event.clear()

        try:
            self.open()
        except serial.SerialException as e:
            return {
                "success": False,
                "captured": {},
                "raw": [],
                "missing": list(REQUIRED_KEYS),
                "elapsed": 0,
                "error": str(e),
            }

        if reset_callback:
            self._log("Triggering device reset for boot output...", "info")
            reset_callback()
            time.sleep(0.5)  # give MCU time to restart
            self._serial.reset_input_buffer()

        start = time.time()
        try:
            while not self._stop_event.is_set():
                elapsed = time.time() - start
                if elapsed > self.timeout_seconds:
                    self._log("Serial capture timed out", "warning")
                    break

                raw = self._serial.readline()
                if not raw:
                    continue

                try:
                    line = raw.decode("utf-8", errors="replace").strip()
                except Exception:
                    continue

                if not line:
                    continue

                self._raw_lines.append(line)
                self._log(f"[RX] {line}", "debug")

                # The firmware sends "---" after each credential block
                if line.strip() == END_MARKER and REQUIRED_KEYS.issubset(self._captured.keys()):
                    self._log("End marker received — capture complete", "info")
                    break

                self._parse_line(line)

        finally:
            self.close()

        elapsed = time.time() - start
        missing = [k for k in REQUIRED_KEYS if k not in self._captured]

        return {
            "success": len(missing) == 0,
            "captured": dict(self._captured),
            "raw": list(self._raw_lines),
            "missing": missing,
            "elapsed": round(elapsed, 2),
        }

    def stop(self):
        """Signal the capture loop to stop (from another thread)."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Async wrapper (for GUI thread)
    # ------------------------------------------------------------------
    def capture_async(self, callback, reset_callback=None):
        """
        Run capture() in a background thread.

        Parameters
        ----------
        callback : callable(result_dict)
            Called on the background thread when capture finishes.
        reset_callback : callable or None
            Passed through to capture().
        """
        def worker():
            result = self.capture(reset_callback=reset_callback)
            callback(result)
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return t

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _parse_line(self, line):
        """Try every pattern against the line and store matches."""
        for key, pattern in self.patterns.items():
            if key in self._captured:
                continue  # already have this value
            m = pattern.search(line)
            if m:
                value = m.group("value").strip()
                self._captured[key] = value
                self._log(f"Captured {key} = {value}", "info")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def add_pattern(self, key, regex_str, required=False):
        """
        Add a custom parsing pattern at runtime.

        Parameters
        ----------
        key : str       Identifier for the captured value.
        regex_str : str  Regex with a named group ``(?P<value>...)``.
        required : bool  If True, this key must be present for success.
        """
        self.patterns[key] = re.compile(regex_str, re.IGNORECASE)
        if required:
            REQUIRED_KEYS.add(key)

    def get_captured(self):
        """Return the most recently captured values."""
        return dict(self._captured)

    def get_raw_output(self):
        """Return all raw lines from the last capture."""
        return list(self._raw_lines)
