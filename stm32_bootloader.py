"""
Corona SmartFlux — STM32WLE5 Production Bootloader v2.0
=========================================================
GUI tool for programming STM32WLE5JCI6 devices via ST-Link (SWD),
provisioning LoRaWAN credentials, logging every device, and
exporting data for batch LNS registration.

Replaces the previous ESP32-based firmware flasher.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import sys
import threading
import time
from datetime import datetime, timezone

# Local modules
from stm32_flash_utils import STM32FlashManager
from device_log_manager import DeviceLogManager
from lorawan_provisioner import LoRaWANProvisioner
from lns_exporter import LNSExporter
from serial_capture import SerialCapture


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_TITLE = "Corona SmartFlux — STM32 Production Bootloader v2.0"
WINDOW_SIZE = "1200x850"
MIN_SIZE = (1000, 700)

PRODUCT_CLASSES = {
    "PURPLE_CLASS": {"dip": "0b00", "cal": 450.0, "liters": 1.6, "desc": "High flow rate"},
    "GREEN_CLASS":  {"dip": "0b01", "cal": 520.0, "liters": 1.2, "desc": "Medium flow rate"},
    "BLUE_CLASS":   {"dip": "0b10", "cal": 600.0, "liters": 0.8, "desc": "Low flow rate"},
    "WHITE_CLASS":  {"dip": "0b11", "cal": 500.0, "liters": 1.0, "desc": "Standard"},
}

INSPECTORS = ["Maria Rodriguez", "Juan Perez", "Carlos Martinez"]


class STM32Flasher:
    """Main GUI application for STM32WLE5 production programming."""

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(True, True)
        self.root.minsize(*MIN_SIZE)

        # --- Back-end modules ---
        self.flash_mgr = STM32FlashManager(logger=self._backend_log)
        self.log_mgr = DeviceLogManager()
        self.provisioner = LoRaWANProvisioner()
        self.exporter = LNSExporter()
        self.serial_capture = SerialCapture(logger=self._backend_log)

        # --- State ---
        self.firmware_path = None
        self.is_flashing = False

        # UI variables
        self.selected_operator = tk.StringVar(value=INSPECTORS[0] if INSPECTORS else "")
        self.selected_product_class = tk.StringVar(value="PURPLE_CLASS")
        self.firmware_version = tk.StringVar(value="1.0.0")
        self.batch_number = tk.StringVar(value=self._generate_batch_number())
        self.verbose_mode = tk.BooleanVar(value=False)
        self.auto_generate_deveui = tk.BooleanVar(value=True)
        self.notes_text_var = tk.StringVar(value="")
        self.selected_com_port = tk.StringVar(value="")
        self.selected_baud = tk.StringVar(value="115200")
        self.serial_timeout = tk.IntVar(value=15)

        # Session stats
        self.session_total = 0
        self.session_success = 0
        self.session_uids = []

        self._setup_ui()
        self._search_firmware()
        self._check_programmer()
        self._refresh_com_ports()

    # ==================================================================
    # UI SETUP
    # ==================================================================
    def _setup_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=5, pady=5)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Left panel (scrollable)
        left_container = ttk.Frame(main)
        left_container.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(left_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        self.scroll_frame.bind("<Configure>",
                               lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self.scroll_frame.columnconfigure(0, weight=1)
        self._build_left_panel(self.scroll_frame)

        # Right panel
        right_frame = ttk.Frame(main)
        right_frame.grid(row=0, column=1, sticky="nsew")
        self._build_right_panel(right_frame)

    # ------------------------------------------------------------------
    # LEFT PANEL
    # ------------------------------------------------------------------
    def _build_left_panel(self, parent):
        row = 0

        # --- Title ---
        ttk.Label(parent, text="Corona SmartFlux — STM32 Bootloader",
                  font=("Arial", 16, "bold")).grid(row=row, column=0, pady=8, sticky="ew")
        row += 1

        # --- Device Status ---
        status_frame = ttk.LabelFrame(parent, text="Device Status", padding=5)
        status_frame.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        status_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(status_frame, text="ST-Link:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=3)
        self.stlink_label = ttk.Label(status_frame, text="Not detected", foreground="gray")
        self.stlink_label.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(status_frame, text="Detect", command=self._detect_stlink, width=10).grid(row=0, column=2, padx=3)

        ttk.Label(status_frame, text="Target:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", padx=3)
        self.target_label = ttk.Label(status_frame, text="—", foreground="gray")
        self.target_label.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(status_frame, text="UID:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", padx=3)
        self.uid_label = ttk.Label(status_frame, text="—", foreground="gray")
        self.uid_label.grid(row=2, column=1, sticky="w", padx=5)

        # --- Serial Port (for credential capture) ---
        serial_frame = ttk.LabelFrame(parent, text="Serial Port (credential capture)", padding=5)
        serial_frame.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        serial_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(serial_frame, text="COM Port:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=3)
        self.com_combo = ttk.Combobox(serial_frame, textvariable=self.selected_com_port,
                                      state="readonly", width=25)
        self.com_combo.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(serial_frame, text="Refresh", command=self._refresh_com_ports, width=8).grid(row=0, column=2, padx=3)

        ttk.Label(serial_frame, text="Baud:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", padx=3)
        baud_combo = ttk.Combobox(serial_frame, textvariable=self.selected_baud,
                                  values=["9600", "19200", "38400", "57600", "115200", "230400", "460800"],
                                  state="readonly", width=12)
        baud_combo.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(serial_frame, text="Timeout (s):", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", padx=3)
        ttk.Spinbox(serial_frame, from_=5, to=60, textvariable=self.serial_timeout, width=6).grid(row=2, column=1, sticky="w", padx=5)

        # --- Firmware ---
        fw_frame = ttk.LabelFrame(parent, text="Firmware", padding=5)
        fw_frame.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        fw_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(fw_frame, text="File:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=3)
        self.fw_label = ttk.Label(fw_frame, text="No firmware selected", foreground="gray")
        self.fw_label.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(fw_frame, text="Browse", command=self._select_firmware, width=10).grid(row=0, column=2, padx=3)

        ttk.Label(fw_frame, text="Version:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", padx=3)
        ttk.Entry(fw_frame, textvariable=self.firmware_version, width=15).grid(row=1, column=1, sticky="w", padx=5)

        # --- LoRaWAN Provisioning ---
        lora_frame = ttk.LabelFrame(parent, text="LoRaWAN Provisioning", padding=5)
        lora_frame.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        lora_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(lora_frame, text="JoinEUI:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=3)
        self.joineui_label = ttk.Label(lora_frame,
                                       text=LoRaWANProvisioner.format_eui(self.provisioner.join_eui),
                                       foreground="blue")
        self.joineui_label.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(lora_frame, text="DevEUI:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", padx=3)
        self.deveui_label = ttk.Label(lora_frame, text="(captured from serial after flash)", foreground="gray")
        self.deveui_label.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(lora_frame, text="AppKey:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", padx=3)
        self.appkey_label = ttk.Label(lora_frame, text="(captured from serial after flash)", foreground="gray")
        self.appkey_label.grid(row=2, column=1, sticky="w", padx=5)

        ttk.Label(lora_frame, text="Region / Class:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky="w", padx=3)
        ttk.Label(lora_frame, text="US915 / Class A / OTAA", foreground="green").grid(row=3, column=1, sticky="w", padx=5)

        # --- Production Data ---
        prod_frame = ttk.LabelFrame(parent, text="Production Data", padding=5)
        prod_frame.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        prod_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(prod_frame, text="Operator:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=3)
        op_combo = ttk.Combobox(prod_frame, textvariable=self.selected_operator,
                                values=INSPECTORS, state="readonly", width=25)
        op_combo.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(prod_frame, text="Batch:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", padx=3)
        ttk.Entry(prod_frame, textvariable=self.batch_number, width=25).grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(prod_frame, text="Product:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", padx=3)
        pc_combo = ttk.Combobox(prod_frame, textvariable=self.selected_product_class,
                                values=list(PRODUCT_CLASSES.keys()), state="readonly", width=25)
        pc_combo.grid(row=2, column=1, sticky="w", padx=5)

        ttk.Label(prod_frame, text="Notes:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky="nw", padx=3)
        ttk.Entry(prod_frame, textvariable=self.notes_text_var, width=50).grid(row=3, column=1, sticky="ew", padx=5)

        # --- Action Buttons ---
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, pady=8, sticky="ew", padx=5)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        row += 1

        self.flash_btn = ttk.Button(btn_frame, text="PROGRAM DEVICE",
                                    command=self._start_program, width=25)
        self.flash_btn.grid(row=0, column=0, padx=4, sticky="ew")

        self.export_btn = ttk.Button(btn_frame, text="EXPORT FOR LNS",
                                     command=self._show_export_dialog, width=20)
        self.export_btn.grid(row=0, column=1, padx=4, sticky="ew")

        self.log_btn = ttk.Button(btn_frame, text="VIEW LOG",
                                  command=self._show_device_log, width=15)
        self.log_btn.grid(row=0, column=2, padx=4, sticky="ew")

        # --- Progress ---
        self.progress = ttk.Progressbar(parent, mode="determinate", maximum=100)
        self.progress.grid(row=row, column=0, pady=5, sticky="ew", padx=5)
        row += 1

        self.status_label = ttk.Label(parent, text="Ready", font=("Arial", 9, "bold"), foreground="blue")
        self.status_label.grid(row=row, column=0, sticky="w", padx=8)
        row += 1

        # --- Log area ---
        self.log_text = scrolledtext.ScrolledText(parent, height=12, wrap=tk.WORD, state="disabled")
        self.log_text.grid(row=row, column=0, pady=5, sticky="nsew", padx=5)
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("info", foreground="blue")
        self.log_text.tag_config("warning", foreground="orange")
        parent.rowconfigure(row, weight=1)

    # ------------------------------------------------------------------
    # RIGHT PANEL
    # ------------------------------------------------------------------
    def _build_right_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=0)

        # Debug log
        ttk.Label(parent, text="Debug:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.debug_text = scrolledtext.ScrolledText(parent, height=10, width=40, state="disabled",
                                                     wrap=tk.WORD, font=("Consolas", 8))
        self.debug_text.grid(row=1, column=0, sticky="nsew", pady=(0, 5))
        self.debug_text.tag_config("debug", foreground="gray")

        # Session info
        session_frame = ttk.LabelFrame(parent, text="Session", padding=5)
        session_frame.grid(row=2, column=0, sticky="ew", pady=5)
        session_frame.columnconfigure(1, weight=1)

        ttk.Label(session_frame, text="Total:", font=("Arial", 8)).grid(row=0, column=0, sticky="w")
        self.lbl_total = ttk.Label(session_frame, text="0", foreground="blue", font=("Arial", 8))
        self.lbl_total.grid(row=0, column=1, sticky="w")

        ttk.Label(session_frame, text="Success:", font=("Arial", 8)).grid(row=1, column=0, sticky="w")
        self.lbl_success = ttk.Label(session_frame, text="0", foreground="green", font=("Arial", 8))
        self.lbl_success.grid(row=1, column=1, sticky="w")

        ttk.Label(session_frame, text="In DB:", font=("Arial", 8)).grid(row=2, column=0, sticky="w")
        self.lbl_db_count = ttk.Label(session_frame, text=str(self.log_mgr.get_device_count()),
                                       foreground="purple", font=("Arial", 8))
        self.lbl_db_count.grid(row=2, column=1, sticky="w")

        # UID list from this session
        self.uid_list_text = scrolledtext.ScrolledText(session_frame, height=5, width=35, state="disabled",
                                                        wrap=tk.WORD, font=("Consolas", 7))
        self.uid_list_text.grid(row=3, column=0, columnspan=2, sticky="ew", pady=3)

        ttk.Button(session_frame, text="Reset", command=self._reset_session, width=8).grid(
            row=4, column=0, columnspan=2, pady=2)

        # STM32CubeProgrammer path
        prog_frame = ttk.LabelFrame(parent, text="Programmer", padding=5)
        prog_frame.grid(row=3, column=0, sticky="ew", pady=5)
        prog_frame.columnconfigure(0, weight=1)

        self.prog_path_label = ttk.Label(prog_frame, text="...", font=("Consolas", 7), wraplength=250)
        self.prog_path_label.grid(row=0, column=0, sticky="w")
        ttk.Button(prog_frame, text="Set Path", command=self._browse_programmer, width=10).grid(row=1, column=0, pady=2)

    # ==================================================================
    # LOGGING
    # ==================================================================
    def _log(self, message, tag="info"):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _debug(self, message):
        self.debug_text.config(state="normal")
        self.debug_text.insert(tk.END, f"[DBG] {message}\n", "debug")
        self.debug_text.see(tk.END)
        self.debug_text.config(state="disabled")
        self.root.update_idletasks()

    def _backend_log(self, message, level="info"):
        """Callback for backend modules."""
        self._debug(f"[{level.upper()}] {message}")
        if level in ("error", "warning"):
            self._log(message, level)

    # ==================================================================
    # INITIALIZATION HELPERS
    # ==================================================================
    def _check_programmer(self):
        if self.flash_mgr.is_programmer_available():
            path = self.flash_mgr.cube_programmer_path
            self.prog_path_label.config(text=path)
            self._log("STM32_Programmer_CLI found", "success")
        else:
            self.prog_path_label.config(text="NOT FOUND")
            self._log("STM32_Programmer_CLI not found — set path manually or install STM32CubeProgrammer", "warning")

    def _search_firmware(self):
        fw_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware")
        os.makedirs(fw_dir, exist_ok=True)
        candidates = [f for f in os.listdir(fw_dir)
                      if f.lower().endswith((".hex", ".bin", ".elf"))]
        if len(candidates) == 1:
            self.firmware_path = os.path.join(fw_dir, candidates[0])
            size_str = self._file_size_str(self.firmware_path)
            self.fw_label.config(text=f"{candidates[0]} ({size_str})", foreground="green")
            self._log(f"Firmware found: {candidates[0]}", "success")
        elif candidates:
            self.fw_label.config(text=f"{len(candidates)} files — select one", foreground="orange")
        else:
            self.fw_label.config(text="Place .hex/.bin in firmware/ folder", foreground="gray")

    @staticmethod
    def _generate_batch_number():
        return f"BATCH-{datetime.now().strftime('%Y-%m')}-001"

    @staticmethod
    def _file_size_str(path):
        size = os.path.getsize(path)
        for unit in ("B", "KB", "MB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    # ==================================================================
    # UI ACTIONS
    # ==================================================================
    def _select_firmware(self):
        fw_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware")
        path = filedialog.askopenfilename(
            title="Select Firmware",
            initialdir=fw_dir,
            filetypes=[("Firmware", "*.hex *.bin *.elf"), ("All", "*.*")],
        )
        if path:
            self.firmware_path = path
            size_str = self._file_size_str(path)
            self.fw_label.config(text=f"{os.path.basename(path)} ({size_str})", foreground="green")
            self._log(f"Firmware selected: {os.path.basename(path)}", "success")

    def _refresh_com_ports(self):
        """Refresh the COM port dropdown with available ports."""
        ports = SerialCapture.list_com_ports()
        port_names = [p["device"] for p in ports]
        self.com_combo["values"] = port_names
        if port_names:
            # Try to auto-select an ST-Link VCP
            vcp = SerialCapture.find_stlink_vcp()
            if vcp and vcp in port_names:
                self.selected_com_port.set(vcp)
            elif not self.selected_com_port.get():
                self.selected_com_port.set(port_names[0])
            descs = [f"  {p['device']}: {p['description']}" for p in ports]
            self._debug("COM ports:\n" + "\n".join(descs))
        else:
            self._debug("No COM ports found")

    def _browse_programmer(self):
        path = filedialog.askopenfilename(
            title="Locate STM32_Programmer_CLI.exe",
            filetypes=[("Executable", "*.exe"), ("All", "*.*")],
        )
        if path and self.flash_mgr.set_programmer_path(path):
            self.prog_path_label.config(text=path)
            self._log("Programmer path updated", "success")
        elif path:
            messagebox.showerror("Error", "Invalid programmer path")

    def _detect_stlink(self):
        self._log("Detecting ST-Link...", "info")
        self._debug("Running ST-Link detection")

        def worker():
            stlinks = self.flash_mgr.list_stlinks()
            if stlinks:
                sn = stlinks[0]["serial"]
                self.stlink_label.config(text=f"Connected (SN: {sn})", foreground="green")
                self._log(f"ST-Link detected: {sn}", "success")

                # Try to detect target
                info = self.flash_mgr.connect_and_detect()
                if info["connected"]:
                    self.target_label.config(text=info.get("description", "STM32WLE5"),
                                             foreground="green")
                    uid = self.flash_mgr.read_device_uid()
                    if uid:
                        self.uid_label.config(text=f"0x{uid}", foreground="green")
                        # Preview DevEUI
                        deveui = self.provisioner.generate_deveui(uid)
                        self.deveui_label.config(
                            text=LoRaWANProvisioner.format_eui(deveui),
                            foreground="blue")
                        self._log(f"Device UID: 0x{uid}", "success")
                        self._log(f"DevEUI preview: {LoRaWANProvisioner.format_eui(deveui)}", "info")
                    else:
                        self.uid_label.config(text="Could not read", foreground="red")
                else:
                    self.target_label.config(text="No target", foreground="red")
                    self._log(f"Target detection failed: {info.get('error', '')}", "error")
            else:
                self.stlink_label.config(text="Not detected", foreground="red")
                self._log("No ST-Link found. Connect debugger and retry.", "error")

        threading.Thread(target=worker, daemon=True).start()

    def _reset_session(self):
        self.session_total = 0
        self.session_success = 0
        self.session_uids.clear()
        self._update_session_display()

    def _update_session_display(self):
        self.lbl_total.config(text=str(self.session_total))
        self.lbl_success.config(text=str(self.session_success))
        self.lbl_db_count.config(text=str(self.log_mgr.get_device_count()))
        self.uid_list_text.config(state="normal")
        self.uid_list_text.delete("1.0", tk.END)
        for uid in self.session_uids:
            self.uid_list_text.insert(tk.END, uid + "\n")
        self.uid_list_text.config(state="disabled")

    def _set_buttons_state(self, state):
        self.flash_btn.config(state=state)
        self.export_btn.config(state=state)
        self.log_btn.config(state=state)

    # ==================================================================
    # MAIN PROGRAMMING WORKFLOW
    # ==================================================================
    def _start_program(self):
        if self.is_flashing:
            messagebox.showwarning("Busy", "A programming operation is already in progress.")
            return
        if not self.firmware_path or not os.path.isfile(self.firmware_path):
            messagebox.showerror("Error", "Select a valid firmware file first.")
            return
        if not self.flash_mgr.is_programmer_available():
            messagebox.showerror("Error",
                                 "STM32_Programmer_CLI not found.\n\n"
                                 "Install STM32CubeProgrammer or set the path manually.")
            return
        if not self.selected_com_port.get():
            messagebox.showerror("Error",
                                 "Select a COM port for serial credential capture.\n\n"
                                 "The device outputs its DevEUI/AppKey over UART after boot.")
            return

        # Confirm
        msg = (f"Program device?\n\n"
               f"Firmware: {os.path.basename(self.firmware_path)}\n"
               f"Version: {self.firmware_version.get()}\n"
               f"Serial port: {self.selected_com_port.get()} @ {self.selected_baud.get()}\n"
               f"Operator: {self.selected_operator.get()}\n"
               f"Batch: {self.batch_number.get()}\n"
               f"Product: {self.selected_product_class.get()}")
        if not messagebox.askyesno("Confirm Programming", msg):
            return

        self.is_flashing = True
        self._set_buttons_state("disabled")
        self.progress["value"] = 0
        threading.Thread(target=self._program_device_thread, daemon=True).start()

    def _program_device_thread(self):
        """Full programming workflow — runs in background thread."""
        try:
            self.session_total += 1
            self._log("=" * 60, "info")
            self._log("  STARTING DEVICE PROGRAMMING", "info")
            self._log("=" * 60, "info")

            # --- Step 1: Connect via SWD & read UID ---
            self._update_status("Connecting to device (SWD)...")
            self.progress["value"] = 5
            self._log("Step 1/7: Connecting via SWD and reading UID...", "info")

            info = self.flash_mgr.connect_and_detect()
            if not info["connected"]:
                raise RuntimeError(f"Cannot connect to target: {info.get('error', 'unknown')}")

            chip_id = info.get("chip_id", "STM32WLE5JCI6")
            self.target_label.config(text=info.get("description", chip_id), foreground="green")

            uid = self.flash_mgr.read_device_uid()
            if not uid:
                raise RuntimeError("Failed to read device UID")

            self.uid_label.config(text=f"0x{uid}", foreground="green")
            self._log(f"  Device UID: 0x{uid}", "success")
            self._log(f"  Chip: {chip_id}", "info")
            self.progress["value"] = 10

            # --- Step 2: Check if device already in DB ---
            self._update_status("Checking database...")
            self._log("Step 2/7: Checking device history...", "info")

            existing = self.log_mgr.find_device_by_uid(uid)
            event_type = "FIRMWARE_UPDATE" if existing else "INITIAL_PROGRAMMING"
            if existing:
                serial = existing["device_serial"]
                flash_count = existing.get("device_metadata", {}).get("total_flash_count", 0)
                self._log(f"  Device found in DB: {serial} (flashed {flash_count}x before)", "warning")
            else:
                serial = self.log_mgr.next_serial_number()
                self._log(f"  New device — assigned serial: {serial}", "success")
            self.progress["value"] = 20

            # --- Step 3: Erase flash ---
            self._update_status("Erasing flash...")
            self._log("Step 3/7: Erasing flash...", "info")

            if not self.flash_mgr.erase_flash(full_chip=True,
                                               progress_callback=self._progress_cb):
                raise RuntimeError("Flash erase failed")

            self._log("  Flash erased", "success")
            self.progress["value"] = 35

            # --- Step 4: Program firmware ---
            self._update_status("Programming firmware...")
            self._log("Step 4/7: Programming firmware...", "info")

            result = self.flash_mgr.program_firmware(
                self.firmware_path, verify=True,
                progress_callback=self._progress_cb)

            if not result["success"]:
                raise RuntimeError(f"Programming failed: {result.get('error', '')}")

            self._log(f"  Programmed {result['size_bytes']} bytes in {result['duration_seconds']}s", "success")
            self._log(f"  CRC32: {result['checksum_crc32']}", "info")
            self.progress["value"] = 55

            # --- Step 5: Reset device and capture serial output ---
            self._update_status("Capturing credentials from serial...")
            self._log("Step 5/7: Resetting device and reading serial output...", "info")
            self._log(f"  Listening on {self.selected_com_port.get()} @ {self.selected_baud.get()} baud", "info")

            self.serial_capture.port = self.selected_com_port.get()
            self.serial_capture.baudrate = int(self.selected_baud.get())
            self.serial_capture.timeout_seconds = self.serial_timeout.get()

            # Use CubeProgrammer to reset the MCU so it boots and prints credentials
            def trigger_reset():
                self.flash_mgr.reset_device()

            capture_result = self.serial_capture.capture(reset_callback=trigger_reset)

            # Show raw output in debug
            for raw_line in capture_result.get("raw", []):
                self._debug(f"[UART] {raw_line}")

            captured = capture_result.get("captured", {})

            if capture_result["success"]:
                self._log(f"  Serial capture OK ({capture_result['elapsed']}s)", "success")
                self._log(f"  Captured fields: {list(captured.keys())}", "info")
            else:
                missing = capture_result.get("missing", [])
                self._log(f"  WARNING: Serial capture incomplete — missing: {missing}", "warning")
                self._log(f"  Got: {list(captured.keys())}  (timeout {capture_result['elapsed']}s)", "warning")
                if "error" in capture_result:
                    self._log(f"  Serial error: {capture_result['error']}", "error")

            self.progress["value"] = 70

            # --- Step 6: Build LoRaWAN config from captured data ---
            self._update_status("Building LoRaWAN config...")
            self._log("Step 6/7: Building LoRaWAN credentials...", "info")

            # DevEUI, JoinEUI, AppKey all come from serial now
            deveui = captured.get("deveui", "")
            joineui = captured.get("joineui", self.provisioner.join_eui)
            appkey = captured.get("appkey", "")
            devaddr = captured.get("devaddr", "")
            fw_from_device = captured.get("fw_version", "")

            if not deveui:
                # Fallback: derive from UID if serial capture missed it
                deveui = self.provisioner.generate_deveui(uid)
                self._log(f"  DevEUI not captured — using UID-derived fallback: {deveui}", "warning")

            if not appkey:
                if existing:
                    appkey = existing.get("lorawan_config", {}).get("appkey", "")
                    self._log("  AppKey not captured — reusing from database", "warning")
                if not appkey:
                    self._log("  AppKey: MISSING — serial capture failed to read it", "error")

            lora_config = {
                "deveui": deveui.upper(),
                "joineui": joineui.upper(),
                "appkey": appkey.upper(),
                "nwkkey": appkey.upper(),  # LoRaWAN 1.0.x: NwkKey == AppKey
                "devaddr": devaddr.upper(),
                "region": "US915",
                "class": "A",
                "activation": "OTAA",
                "network_server": "The Things Network",
                "application_name": "corona-smartflux-prod",
                "credential_source": "serial_capture" if captured.get("deveui") else "uid_derived",
                "fw_version_reported": fw_from_device,
            }

            # Update UI labels
            self.deveui_label.config(text=LoRaWANProvisioner.format_eui(deveui), foreground="blue")
            self.appkey_label.config(
                text=LoRaWANProvisioner.format_key(appkey[:16]) + "..." if len(appkey) >= 16 else (appkey or "MISSING"),
                foreground="blue" if appkey else "red")

            self._log(f"  DevEUI:  {LoRaWANProvisioner.format_eui(deveui)}", "success")
            self._log(f"  JoinEUI: {LoRaWANProvisioner.format_eui(joineui)}", "info")
            self._log(f"  AppKey:  {appkey[:8]}... (hidden)" if appkey else "  AppKey:  MISSING", "info" if appkey else "error")
            if devaddr:
                self._log(f"  DevAddr: {devaddr}", "info")
            if fw_from_device:
                self._log(f"  FW (device): {fw_from_device}", "info")
            self._log(f"  Source:  {lora_config['credential_source']}", "info")
            self.progress["value"] = 80

            # --- Step 7: Log to database ---
            self._update_status("Logging device...")
            self._log("Step 7/7: Saving to database...", "info")

            # Build programmer ID from ST-Link list
            stlinks = self.flash_mgr.list_stlinks()
            programmer_id = f"ST-Link-{stlinks[0]['serial']}" if stlinks else "unknown"

            flash_event = self.log_mgr.build_flash_event(
                event_type=event_type,
                firmware_version=self.firmware_version.get(),
                firmware_file=os.path.basename(self.firmware_path),
                firmware_checksum=result["checksum_crc32"],
                flash_size_bytes=result["size_bytes"],
                flash_duration_seconds=result["duration_seconds"],
                programmer_id=programmer_id,
                operator=self.selected_operator.get(),
                status="SUCCESS",
            )

            if existing:
                self.log_mgr.add_flash_event(uid, flash_event)
                self._log(f"  Updated existing device: {serial}", "success")
            else:
                pc = self.selected_product_class.get()
                pc_info = PRODUCT_CLASSES.get(pc, {})
                hw_config = {
                    "product_class": pc,
                    "dip_switch_setting": pc_info.get("dip", ""),
                    "flow_sensor_calibration": pc_info.get("cal", 0),
                    "pcb_version": "v2.1",
                }
                prod_data = {
                    "batch_number": self.batch_number.get(),
                    "production_line": "LINE-A",
                    "qc_inspector": self.selected_operator.get(),
                    "qc_status": "PENDING",
                }

                entry = self.log_mgr.build_device_entry(
                    serial=serial,
                    uid=uid,
                    chip_id=chip_id,
                    flash_event=flash_event,
                    lorawan_config=lora_config,
                    hardware_config=hw_config,
                    production_data=prod_data,
                    notes=self.notes_text_var.get(),
                )
                self.log_mgr.add_device(entry)
                self._log(f"  New device registered: {serial}", "success")

            self.progress["value"] = 100
            self.session_success += 1
            self.session_uids.append(f"{serial}  UID:{uid[:12]}..  DevEUI:{deveui}")
            self._update_session_display()

            # --- Done ---
            self._log("=" * 60, "success")
            self._log("  DEVICE PROGRAMMED SUCCESSFULLY", "success")
            self._log(f"  Serial:  {serial}", "success")
            self._log(f"  DevEUI:  {LoRaWANProvisioner.format_eui(deveui)}", "success")
            self._log(f"  FW:      {self.firmware_version.get()}", "success")
            self._log("=" * 60, "success")
            self._update_status("Done — ready for next device")

            messagebox.showinfo("Success",
                                f"Device programmed!\n\n"
                                f"Serial: {serial}\n"
                                f"DevEUI: {LoRaWANProvisioner.format_eui(deveui)}\n"
                                f"Firmware: {self.firmware_version.get()}")

        except Exception as e:
            self._log(f"ERROR: {e}", "error")
            self._update_status("FAILED")
            self.progress["value"] = 0
            messagebox.showerror("Programming Failed", str(e))

        finally:
            self.is_flashing = False
            self._set_buttons_state("normal")

    def _progress_cb(self, percent, message):
        if percent is not None:
            self.progress["value"] = percent
        self._debug(message)

    def _update_status(self, text):
        self.status_label.config(text=text)
        self.root.update_idletasks()

    # ==================================================================
    # EXPORT DIALOG
    # ==================================================================
    def _show_export_dialog(self):
        devices = self.log_mgr.get_all_devices()
        if not devices:
            messagebox.showinfo("No Devices", "No devices in database to export.")
            return

        win = tk.Toplevel(self.root)
        win.title("Export Devices for LNS")
        win.geometry("500x400")
        win.resizable(False, False)

        ttk.Label(win, text="Export Devices for LNS Registration",
                  font=("Arial", 12, "bold")).pack(pady=10)

        ttk.Label(win, text=f"Total devices in database: {len(devices)}").pack(pady=5)

        fmt_var = tk.StringVar(value="ttn_csv")
        fmt_frame = ttk.LabelFrame(win, text="Export Format", padding=10)
        fmt_frame.pack(fill="x", padx=20, pady=5)

        ttk.Radiobutton(fmt_frame, text="TTN CSV (Console bulk import)", variable=fmt_var, value="ttn_csv").pack(anchor="w")
        ttk.Radiobutton(fmt_frame, text="TTN JSON (CLI / API import)", variable=fmt_var, value="ttn_json").pack(anchor="w")
        ttk.Radiobutton(fmt_frame, text="ChirpStack JSON", variable=fmt_var, value="chirpstack_json").pack(anchor="w")
        ttk.Radiobutton(fmt_frame, text="Full Inventory CSV", variable=fmt_var, value="inventory_csv").pack(anchor="w")

        # Batch filter
        batches = set()
        for d in devices:
            b = d.get("production_data", {}).get("batch_number", "")
            if b:
                batches.add(b)
        batch_var = tk.StringVar(value="ALL")
        if batches:
            b_frame = ttk.LabelFrame(win, text="Filter by Batch", padding=10)
            b_frame.pack(fill="x", padx=20, pady=5)
            ttk.Radiobutton(b_frame, text="All devices", variable=batch_var, value="ALL").pack(anchor="w")
            for b in sorted(batches):
                ttk.Radiobutton(b_frame, text=b, variable=batch_var, value=b).pack(anchor="w")

        def do_export():
            fmt = fmt_var.get()
            batch = batch_var.get()
            try:
                if batch != "ALL":
                    path = self.exporter.export_devices_by_batch(devices, batch, fmt)
                else:
                    if fmt == "ttn_csv":
                        path = self.exporter.export_ttn_csv(devices)
                    elif fmt == "ttn_json":
                        path = self.exporter.export_ttn_json(devices)
                    elif fmt == "chirpstack_json":
                        path = self.exporter.export_chirpstack_json(devices)
                    else:
                        path = self.exporter.export_inventory_csv(devices)

                self._log(f"Exported to: {path}", "success")
                messagebox.showinfo("Exported", f"File saved:\n\n{path}")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

        ttk.Button(win, text="Export", command=do_export, width=20).pack(pady=15)

    # ==================================================================
    # DEVICE LOG VIEWER
    # ==================================================================
    def _show_device_log(self):
        devices = self.log_mgr.get_all_devices()
        stats = self.log_mgr.get_statistics()

        win = tk.Toplevel(self.root)
        win.title("Device Flash Log")
        win.geometry("800x600")

        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 9))
        text.pack(fill="both", expand=True, padx=10, pady=10)

        lines = [
            f"{'='*70}",
            f"  DEVICE FLASH LOG — {len(devices)} device(s)",
            f"{'='*70}",
            f"  Total flash events: {stats.get('total_flash_events', 0)}",
            f"  Success rate: {stats.get('success_rate_percent', 0)}%",
            f"  Firmware versions: {stats.get('firmware_versions', {})}",
            f"  Operators: {stats.get('operators', {})}",
            f"{'='*70}",
            "",
        ]

        for dev in devices:
            serial = dev.get("device_serial", "?")
            uid = dev.get("device_uid", "?")
            lora = dev.get("lorawan_config", {})
            events = dev.get("flash_events", [])
            lines.append(f"  {serial}")
            lines.append(f"    UID:    0x{uid}")
            lines.append(f"    DevEUI: {lora.get('deveui', '?')}")
            lines.append(f"    AppKey: {lora.get('appkey', '?')[:16]}...")
            lines.append(f"    Flashes: {len(events)}")
            if events:
                latest = events[-1]
                lines.append(f"    Latest: {latest.get('firmware_version', '?')} @ {latest.get('timestamp', '?')}")
            lines.append("")

        text.insert("1.0", "\n".join(lines))
        text.config(state="disabled")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        def copy_all():
            win.clipboard_clear()
            win.clipboard_append("\n".join(lines))
            messagebox.showinfo("Copied", "Log copied to clipboard", parent=win)

        ttk.Button(btn_frame, text="Copy", command=copy_all).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side="right", padx=5)


# ==================================================================
# ENTRY POINT
# ==================================================================
def main():
    root = tk.Tk()
    app = STM32Flasher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
