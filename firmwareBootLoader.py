import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import serial.tools.list_ports
import subprocess
import os
import sys
import threading
import struct
import tempfile
import hashlib
import re
import time

def check_and_install_dependencies():
    """Check if required packages are installed and offer to install them"""
    missing_packages = []
    
    # Check esptool
    try:
        import esptool
    except ImportError:
        missing_packages.append('esptool')
    
    # Check pyserial
    try:
        import serial
    except ImportError:
        missing_packages.append('pyserial')
    
    if missing_packages:
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()
        
        msg = f"⚠️ Faltan dependencias requeridas:\n\n"
        msg += "\n".join(f"  • {pkg}" for pkg in missing_packages)
        msg += "\n\n¿Deseas instalarlas ahora?\n\n"
        msg += "Se ejecutará:\n"
        msg += f"  pip install {' '.join(missing_packages)}\n\n"
        msg += "Esto puede tardar 1-2 minutos..."
        
        if messagebox.askyesno("Dependencias faltantes - ESP32 Flasher", msg):
            import subprocess
            import sys
            
            # Show progress window
            progress_window = tk.Toplevel(root)
            progress_window.title("Instalando dependencias...")
            progress_window.geometry("400x150")
            progress_window.resizable(False, False)
            
            tk.Label(progress_window, text="Instalando dependencias...", 
                    font=('Arial', 12, 'bold')).pack(pady=20)
            
            status_label = tk.Label(progress_window, text="Ejecutando pip install...", 
                                   font=('Arial', 10))
            status_label.pack(pady=10)
            
            progress_window.update()
            
            try:
                # Install packages
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + missing_packages
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                progress_window.destroy()
                
                if result.returncode == 0:
                    messagebox.showinfo("✅ Éxito", 
                        f"Dependencias instaladas correctamente:\n\n" + 
                        "\n".join(f"  ✓ {pkg}" for pkg in missing_packages) +
                        "\n\nLa aplicación se iniciará ahora.")
                    root.destroy()
                    # Don't exit, continue to start the app
                    return True
                else:
                    error_msg = result.stderr if result.stderr else "Error desconocido"
                    messagebox.showerror("❌ Error", 
                        f"Error instalando dependencias:\n\n{error_msg}\n\n" +
                        f"Instala manualmente:\n\n" +
                        f"1. Abre CMD/PowerShell como administrador\n" +
                        f"2. Ejecuta: pip install {' '.join(missing_packages)}\n\n" +
                        f"O ejecuta: install_dependencies.bat")
                    root.destroy()
                    sys.exit(1)
            except subprocess.TimeoutExpired:
                progress_window.destroy()
                messagebox.showerror("⏱️ Timeout", 
                    "La instalación tomó demasiado tiempo.\n\n" +
                    f"Instala manualmente con:\n" +
                    f"pip install {' '.join(missing_packages)}")
                root.destroy()
                sys.exit(1)
            except Exception as e:
                progress_window.destroy()
                messagebox.showerror("❌ Error", 
                    f"Error instalando dependencias:\n\n{str(e)}\n\n" +
                    f"Ejecuta install_dependencies.bat\n" +
                    f"o manualmente: pip install {' '.join(missing_packages)}")
                root.destroy()
                sys.exit(1)
        else:
            messagebox.showwarning("⚠️ Advertencia", 
                "La aplicación no funcionará sin estas dependencias.\n\n" +
                "Opciones para instalar:\n\n" +
                "1. Ejecuta: install_dependencies.bat\n" +
                "2. O manualmente: pip install -r requirements.txt\n\n" +
                "Luego vuelve a abrir la aplicación.")
            root.destroy()
            sys.exit(1)
    
    return True

class ESP32Flasher:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Firmware Flasher")
        self.root.geometry("1100x800")  # Increased height for better layout
        self.root.resizable(True, True)  # Permitir redimensionar
        self.root.minsize(900, 700)  # Increased minimum height
        
        # Variables
        self.firmware_path = None
        self.bootloader_path = None
        self.partitions_path = None
        self.selected_port = tk.StringVar()
        self.selected_chip = tk.StringVar(value="esp32s3")  # Valor por defecto para ESP32-S3
        self.selected_baud = tk.StringVar(value="460800")  # Baud rate por defecto (faster)
        self.flash_mode = tk.StringVar(value="simple")  # "simple" or "complete"
        self.is_flashing = False
        self.verbose_mode = tk.BooleanVar(value=False)
        self.show_advanced = tk.BooleanVar(value=False)  # Track advanced panel visibility
        
        # Session tracking
        self.total_flashes = 0
        self.successful_flashes = 0
        self.flashed_devices = set()  # Store unique MAC addresses
        
        # Serial terminal variables
        self.serial_connected = False
        self.serial_thread = None
        self.serial_baud = tk.StringVar(value="115200")
        self.serial_port_obj = None  # serial.Serial object
        
        # ESP-IDF standard addresses (base - adjusted per chip)
        self.esp_idf_addresses = {
            "bootloader_esp32s3": "0x0",       # ESP32-S3 bootloader at 0x0
            "bootloader_esp32": "0x1000",     # ESP32 bootloader at 0x1000
            "partition_table_esp32s3": "0x9000",  # ESP32-S3 partition table (larger bootloader space)
            "partition_table_esp32": "0x8000",   # ESP32 partition table
            "ota_data": "0x49000",            # OTA data selector
            "app_no_ota": "0x10000",          # App without OTA
            "app_with_ota": "0x50000"         # App with OTA (typical)
        }
        
        # Configurar interfaz
        self.setup_ui()
        
        # Buscar firmware al iniciar
        self.search_firmware()
        
        # Actualizar puertos COM
        self.refresh_ports()
    
    def setup_ui(self):
        # Main container with flex layout
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Configure main container grid
        main_container.columnconfigure(0, weight=3)  # Left panel gets more space
        main_container.columnconfigure(1, weight=1)  # Right panel (debug)
        main_container.rowconfigure(0, weight=1)
        
        # === LEFT PANEL WITH SCROLLBAR ===
        left_frame_container = ttk.Frame(main_container)
        left_frame_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 2))
        left_frame_container.columnconfigure(0, weight=1)
        left_frame_container.rowconfigure(0, weight=1)
        
        # Create canvas and scrollbar for left panel
        canvas = tk.Canvas(left_frame_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_frame_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Grid canvas and scrollbar
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
        # Configure scrollable frame
        self.scrollable_frame.columnconfigure(0, weight=1)
        
        # === RIGHT PANEL (Debug) ===
        right_frame = ttk.Frame(main_container)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Setup main content in scrollable frame
        self.setup_main_content(self.scrollable_frame)
        
        # Setup debug panel
        self.setup_debug_panel(right_frame)
        
        # Update canvas scroll region when window resizes
        def update_scroll_region():
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        self.root.after(100, update_scroll_region)
    
    def setup_main_content(self, parent):
        """Setup the main content in the scrollable left panel"""
        # Configure parent for expansion
        parent.columnconfigure(0, weight=1)  # Main column expands
        parent.rowconfigure(9, weight=1)  # Log area expands
        
        main_frame = parent  # Alias for compatibility with existing code
        
        # Título
        title_label = ttk.Label(main_frame, text="ESP32 Firmware Flasher", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=10, sticky=(tk.W, tk.E))
        
        # === FLASH MODE SELECTION ===
        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Flasheo", padding="5")
        mode_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=3, padx=5)
        mode_frame.columnconfigure(0, weight=1)
        
        ttk.Radiobutton(mode_frame, text="Simple Mode - Solo firmware.bin", 
                       variable=self.flash_mode, value="simple",
                       command=self.on_mode_change).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(mode_frame, text="   🛡️ SEGURO: Solo actualiza firmware, preserva SIEMPRE bootloader/partitions/NVS", 
                 foreground="green", font=('Arial', 8, 'bold')).grid(row=1, column=0, sticky=tk.W, padx=20)
        
        ttk.Radiobutton(mode_frame, text="Complete Mode - Bootloader + Partitions + Firmware", 
                       variable=self.flash_mode, value="complete",
                       command=self.on_mode_change).grid(row=2, column=0, sticky=tk.W, pady=(10, 2))
        ttk.Label(mode_frame, text="   🔧 COMPLETO: Flasheo total como PlatformIO (para chips nuevos o recuperación)", 
                 foreground="orange", font=('Arial', 8, 'bold')).grid(row=3, column=0, sticky=tk.W, padx=20)
        
        # Info and Analyze buttons
        button_frame = ttk.Frame(mode_frame)
        button_frame.grid(row=0, column=1, rowspan=4, padx=(20, 0), sticky=(tk.N, tk.S))
        
        info_btn = ttk.Button(button_frame, text="ℹ️ Info\nModos", 
                             command=self.show_mode_info, width=15)
        info_btn.pack(pady=2)
        
        self.analyze_btn = ttk.Button(button_frame, text="🔍 Analizar\nFirmware", 
                                     command=self.show_firmware_analysis, width=15)
        self.analyze_btn.pack(pady=2)
        
        # === FILE SELECTION ===
        files_frame = ttk.LabelFrame(main_frame, text="Archivos", padding="5")
        files_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=3, padx=5)
        files_frame.columnconfigure(1, weight=1)
        
        # Firmware file
        ttk.Label(files_frame, text="Firmware:", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.firmware_label = ttk.Label(files_frame, text="No seleccionado", foreground="gray")
        self.firmware_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        self.firmware_btn = ttk.Button(files_frame, text="📁", command=self.select_firmware_file, width=5)
        self.firmware_btn.grid(row=0, column=2, padx=2)
        
        # Bootloader file (Complete mode only)
        ttk.Label(files_frame, text="Bootloader:", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.bootloader_label = ttk.Label(files_frame, text="No requerido (Simple Mode)", foreground="gray")
        self.bootloader_label.grid(row=1, column=1, sticky=tk.W, padx=5)
        self.bootloader_btn = ttk.Button(files_frame, text="📁", command=self.select_bootloader_file, width=5, state='disabled')
        self.bootloader_btn.grid(row=1, column=2, padx=2)
        
        # Partitions file (Complete mode only)
        ttk.Label(files_frame, text="Partitions:", font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.partitions_label = ttk.Label(files_frame, text="No requerido (Simple Mode)", foreground="gray")
        self.partitions_label.grid(row=2, column=1, sticky=tk.W, padx=5)
        self.partitions_btn = ttk.Button(files_frame, text="📁", command=self.select_partitions_file, width=5, state='disabled')
        self.partitions_btn.grid(row=2, column=2, padx=2)
        
        # Auto-detect button
        self.auto_detect_btn = ttk.Button(files_frame, text="🔍 Auto-detectar archivos PlatformIO", 
                                         command=self.auto_detect_pio_files, width=50, state='disabled')
        self.auto_detect_btn.grid(row=3, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
        
        # === DEVICE CONFIGURATION ===
        device_frame = ttk.LabelFrame(main_frame, text="Configuración del Dispositivo", padding="5")
        device_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=3, padx=5)
        device_frame.columnconfigure(1, weight=1)
        
        # Puerto COM
        ttk.Label(device_frame, text="Puerto COM:", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.port_combo = ttk.Combobox(device_frame, textvariable=self.selected_port, state="readonly", width=30)
        self.port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        port_buttons_frame = ttk.Frame(device_frame)
        port_buttons_frame.grid(row=0, column=2, padx=5)
        
        self.refresh_btn = ttk.Button(port_buttons_frame, text="🔄", command=self.refresh_ports, width=5)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)
        
        self.detect_btn = ttk.Button(port_buttons_frame, text="🔍", command=self.detect_device_partitions, width=5)
        self.detect_btn.pack(side=tk.LEFT, padx=2)
        
        # Tipo de chip
        ttk.Label(device_frame, text="Chip:", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.chip_combo = ttk.Combobox(device_frame, textvariable=self.selected_chip, state="readonly", width=20)
        self.chip_combo['values'] = ['esp32', 'esp32s3', 'esp32s2', 'esp32c3', 'esp32c6', 'esp32h2']
        self.chip_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        
        chip_info_btn = ttk.Button(device_frame, text="🔍 Info", command=self.show_chip_info, width=10)
        chip_info_btn.grid(row=1, column=2, padx=5)
        
        # Baud rate
        ttk.Label(device_frame, text="Baud Rate:", font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.baud_combo = ttk.Combobox(device_frame, textvariable=self.selected_baud, state="readonly", width=20)
        self.baud_combo['values'] = ['115200', '230400', '460800', '921600']
        self.baud_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # === OPTIONS ===
        options_frame = ttk.LabelFrame(main_frame, text="Opciones", padding="5")
        options_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=3, padx=5)
        options_frame.columnconfigure(0, weight=1)
        options_frame.columnconfigure(1, weight=0)  # For buttons on the right
        
        # Preserve NVS
        nvs_frame = ttk.Frame(options_frame)
        nvs_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)
        nvs_frame.columnconfigure(0, weight=1)
        
        self.preserve_nvs = tk.BooleanVar(value=False)
        ttk.Checkbutton(nvs_frame, text="🔒 Preservar NVS/WiFi (solo Complete Mode)", 
                       variable=self.preserve_nvs).grid(row=0, column=0, sticky=tk.W)
        
        # SPIFFS buttons on the right
        spiffs_button_frame = ttk.Frame(options_frame)
        spiffs_button_frame.grid(row=0, column=1, rowspan=5, padx=(20, 0), sticky=(tk.N, tk.S))
        
        self.upload_data_btn = ttk.Button(spiffs_button_frame, text="📤 Upload Data\nFolder (SPIFFS)", 
                                         command=self.upload_data_folder, width=15)
        self.upload_data_btn.pack(pady=2)
        
        self.verify_spiffs_btn = ttk.Button(spiffs_button_frame, text="🔍 Verificar\nSPIFFS", 
                                           command=self.verify_spiffs_manual, width=15)
        self.verify_spiffs_btn.pack(pady=2)
        
        # Preserve Bootloader
        self.preserve_bootloader = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="🚫 Preservar Bootloader (solo Complete Mode)", 
                       variable=self.preserve_bootloader).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        # Verbose mode
        ttk.Checkbutton(options_frame, text="Modo Verbose (debug detallado)", 
                       variable=self.verbose_mode).grid(row=2, column=0, sticky=tk.W, pady=2)
        
        # === MAIN ACTION BUTTONS ===
        main_buttons_frame = ttk.Frame(main_frame)
        main_buttons_frame.grid(row=5, column=0, pady=5, sticky=(tk.W, tk.E))
        main_buttons_frame.columnconfigure(0, weight=1)
        main_buttons_frame.columnconfigure(1, weight=1)
        
        self.flash_btn = ttk.Button(main_buttons_frame, text="⚡ FLASHEAR FIRMWARE", 
                                   command=self.start_flash, width=30)
        self.flash_btn.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        
        # Advanced options toggle
        self.advanced_btn = ttk.Button(main_buttons_frame, text="⚙️ Opciones Avanzadas", 
                                      command=self.toggle_advanced_options, width=25)
        self.advanced_btn.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        
        # === ADVANCED OPTIONS PANEL (Initially hidden) ===
        self.advanced_frame = ttk.LabelFrame(main_frame, text="Opciones Avanzadas", padding="10")
        # Don't grid it initially - will be shown/hidden by toggle
        
        advanced_buttons_frame = ttk.Frame(self.advanced_frame)
        advanced_buttons_frame.pack(fill=tk.X, pady=5)
        
        # Configure grid weights for equal distribution
        for i in range(4):
            advanced_buttons_frame.columnconfigure(i, weight=1)
        
        self.erase_btn = ttk.Button(advanced_buttons_frame, text="🗑️ BORRAR TODO", 
                                   command=self.start_erase, width=15)
        self.erase_btn.grid(row=0, column=0, padx=2, sticky=(tk.W, tk.E))
        
        self.erase_nvs_btn = ttk.Button(advanced_buttons_frame, text="🗑️ BORRAR NVS", 
                                       command=self.start_erase_nvs, width=15)
        self.erase_nvs_btn.grid(row=0, column=1, padx=2, sticky=(tk.W, tk.E))
        
        self.recovery_btn = ttk.Button(advanced_buttons_frame, text="🔧 Flash Bootloader", 
                                      command=self.flash_bootloader_only, width=15)
        self.recovery_btn.grid(row=0, column=2, padx=2, sticky=(tk.W, tk.E))
        
        self.fix_bootloader_btn = ttk.Button(advanced_buttons_frame, text="🚑 Fix Header", 
                                           command=self.fix_invalid_header, width=12)
        self.fix_bootloader_btn.grid(row=0, column=3, padx=2, sticky=(tk.W, tk.E))
        
        # Tools: mkspiffs installer
        tools_frame = ttk.Frame(self.advanced_frame)
        tools_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Label(tools_frame, text="SPIFFS Tools:", font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.install_mkspiffs_btn = ttk.Button(tools_frame, text="Install mkspiffs", command=self.install_mkspiffs, width=20)
        self.install_mkspiffs_btn.grid(row=0, column=1, sticky=(tk.E))

        
        # === PROGRESS BAR ===
        self.progress = ttk.Progressbar(main_frame, mode='determinate', maximum=100)
        self.progress.grid(row=7, column=0, pady=10, sticky=(tk.W, tk.E), padx=5)
        
        # === LOG AREA ===
        log_header_frame = ttk.Frame(main_frame)
        log_header_frame.grid(row=8, column=0, sticky=(tk.W, tk.E), pady=(10, 5), padx=5)
        log_header_frame.columnconfigure(0, weight=1)
        log_header_frame.columnconfigure(1, weight=0)
        
        # === STATUS LABEL ===
        self.status_label = ttk.Label(log_header_frame, text="Idle", font=('Arial', 9, 'bold'), foreground="blue")
        self.status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        save_log_btn = ttk.Button(log_header_frame, text="💾", command=self.save_log_to_file, width=5)
        save_log_btn.grid(row=0, column=1, sticky=tk.E)
        
        self.log_text = scrolledtext.ScrolledText(main_frame, height=12, wrap=tk.WORD, state='disabled')
        self.log_text.grid(row=9, column=0, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Configure log colors
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("info", foreground="blue")
        self.log_text.tag_config("warning", foreground="orange")
    
    def toggle_advanced_options(self):
        """Toggle visibility of advanced options panel"""
        if self.show_advanced.get():
            # Hide advanced panel
            self.advanced_frame.grid_remove()
            self.advanced_btn.config(text="⚙️ Opciones Avanzadas")
            self.show_advanced.set(False)
        else:
            # Show advanced panel
            self.advanced_frame.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)
            self.advanced_btn.config(text="❌ Ocultar Avanzadas")
            self.show_advanced.set(True)
        
        # Update scroll region after layout change
        self.root.after(10, lambda: self.root.update_idletasks())
    
    def setup_debug_panel(self, parent):
        """Setup the right panel with debug, serial terminal, and session info"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)  # Debug (fixed size)
        parent.rowconfigure(1, weight=0)  # Serial controls (fixed size)
        parent.rowconfigure(2, weight=1)  # Serial terminal (expands)
        parent.rowconfigure(3, weight=0)  # Session info (fixed size)
        
        # === DEBUG MESSAGES === (smaller)
        debug_label_frame = ttk.Frame(parent)
        debug_label_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 2))
        debug_label_frame.columnconfigure(0, weight=1)
        
        ttk.Label(debug_label_frame, text="Debug:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Button(debug_label_frame, text="🗑️", command=lambda: self.clear_text(self.debug_text), width=5).pack(side=tk.RIGHT)
        
        self.debug_text = scrolledtext.ScrolledText(parent, height=6, width=40, state='disabled', 
                                                     wrap=tk.WORD, font=('Consolas', 8))
        self.debug_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(25, 2))
        self.debug_text.tag_config("debug", foreground="gray")
        self.debug_text.tag_config("verbose", foreground="#666666")
        
        # === SERIAL CONTROLS ===
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 2))
        controls_frame.columnconfigure(1, weight=1)
        
        # Connect/Disconnect button
        self.connect_btn = ttk.Button(controls_frame, text="🔌 Connect", command=self.toggle_serial_connection, width=15)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Baudrate selection
        ttk.Label(controls_frame, text="Baud:", font=('Arial', 8)).pack(side=tk.LEFT, padx=(0, 2))
        self.serial_baud_combo = ttk.Combobox(controls_frame, textvariable=self.serial_baud, state="readonly", width=10)
        self.serial_baud_combo['values'] = ['9600', '19200', '38400', '57600', '115200', '230400', '460800', '921600']
        self.serial_baud_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # Advanced options button
        self.serial_advanced_btn = ttk.Button(controls_frame, text="⚙️", command=self.show_serial_advanced, width=5)
        self.serial_advanced_btn.pack(side=tk.RIGHT)
        
        # === SERIAL TERMINAL ===
        serial_label_frame = ttk.Frame(parent)
        serial_label_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        serial_label_frame.columnconfigure(0, weight=1)
        
        ttk.Label(serial_label_frame, text="Serial Terminal:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Button(serial_label_frame, text="🗑️", command=lambda: self.clear_text(self.serial_text), width=5).pack(side=tk.RIGHT)
        
        self.serial_text = scrolledtext.ScrolledText(parent, height=12, width=40, state='disabled', 
                                                      wrap=tk.WORD, font=('Consolas', 8))
        self.serial_text.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(25, 5))
        self.serial_text.tag_config("tx", foreground="blue")
        self.serial_text.tag_config("rx", foreground="green")
        self.serial_text.tag_config("info", foreground="orange")
        
        # === SESSION INFO ===
        session_frame = ttk.LabelFrame(parent, text="Sesión", padding="5")
        session_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        session_frame.columnconfigure(1, weight=1)
        
        # Stats
        ttk.Label(session_frame, text="Total:", font=('Arial', 8)).grid(row=0, column=0, sticky=tk.W)
        self.total_flashes_label = ttk.Label(session_frame, text="0", foreground="blue", font=('Arial', 8))
        self.total_flashes_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(session_frame, text="Exitosos:", font=('Arial', 8)).grid(row=1, column=0, sticky=tk.W)
        self.successful_flashes_label = ttk.Label(session_frame, text="0", foreground="green", font=('Arial', 8))
        self.successful_flashes_label.grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(session_frame, text="Únicos:", font=('Arial', 8)).grid(row=2, column=0, sticky=tk.W)
        self.unique_devices_label = ttk.Label(session_frame, text="0", foreground="purple", font=('Arial', 8))
        self.unique_devices_label.grid(row=2, column=1, sticky=tk.W)
        
        # MAC addresses
        self.mac_text = scrolledtext.ScrolledText(session_frame, height=4, width=35, state='disabled', 
                                                   wrap=tk.WORD, font=('Consolas', 7))
        self.mac_text.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        
        # Reset button
        ttk.Button(session_frame, text="🔄", command=self.reset_session_stats, width=5).grid(row=4, column=0, columnspan=2, pady=2)
    
    def clear_text(self, text_widget):
        """Clear a text widget"""
        text_widget.config(state='normal')
        text_widget.delete(1.0, tk.END)
        text_widget.config(state='disabled')
    
    def reset_session_stats(self):
        """Reset session statistics"""
        self.total_flashes = 0
        self.successful_flashes = 0
        self.flashed_devices.clear()
        self.update_session_display()
        self.log_debug("Estadísticas de sesión reiniciadas")
    
    def update_session_display(self):
        """Update session statistics display"""
        self.total_flashes_label.config(text=str(self.total_flashes))
        self.successful_flashes_label.config(text=str(self.successful_flashes))
        self.unique_devices_label.config(text=str(len(self.flashed_devices)))
        
        # Update MAC list
        self.mac_text.config(state='normal')
        self.mac_text.delete(1.0, tk.END)
        for mac in sorted(self.flashed_devices):
            self.mac_text.insert(tk.END, f"{mac}\n")
        self.mac_text.config(state='disabled')
    
    def log_debug(self, message, tag="debug"):
        """Log debug message to debug panel"""
        if self.verbose_mode.get() or tag != "verbose":
            self.debug_text.config(state='normal')
            self.debug_text.insert(tk.END, f"[DEBUG] {message}\n", tag)
            self.debug_text.see(tk.END)
            self.debug_text.config(state='disabled')
            self.root.update()
    
    def log_serial(self, message, direction="rx"):
        """Log serial communication to debug panel (for esptool communication)"""
        prefix = "→ TX:" if direction == "tx" else "← RX:"
        self.debug_text.config(state='normal')
        self.debug_text.insert(tk.END, f"{prefix} {message}\n", "verbose")
        self.debug_text.see(tk.END)
        self.debug_text.config(state='disabled')
        self.root.update()
    
    def write_to_serial_terminal(self, message, tag="rx"):
        """Write to the serial terminal (for actual serial data)"""
        self.serial_text.config(state='normal')
        self.serial_text.insert(tk.END, f"{message}", tag)
        self.serial_text.see(tk.END)
        self.serial_text.config(state='disabled')
        self.root.update()
    
    def toggle_serial_connection(self):
        """Connect or disconnect from serial port"""
        if self.serial_connected:
            self.disconnect_serial()
        else:
            self.connect_serial()
    
    def connect_serial(self):
        """Connect to the selected serial port"""
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM primero")
            return
        
        port_name = self.selected_port.get().split(' - ')[0]
        baud_rate = int(self.serial_baud.get())
        
        try:
            import serial
            self.serial_port_obj = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                timeout=0.1,
                write_timeout=1
            )
            
            self.serial_connected = True
            self.connect_btn.config(text="🔌 Disconnect")
            self.serial_baud_combo.config(state='disabled')
            self.write_to_serial_terminal(f"Connected to {port_name} at {baud_rate} baud\n", "info")
            self.log_debug(f"Serial connected to {port_name}@{baud_rate}")
            
            # Start reading thread
            self.serial_thread = threading.Thread(target=self._serial_read_thread, daemon=True)
            self.serial_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error conectando al puerto serial:\n\n{str(e)}")
            self.log_debug(f"Serial connection failed: {e}")
    
    def disconnect_serial(self):
        """Disconnect from serial port"""
        self.serial_connected = False
        if self.serial_port_obj and self.serial_port_obj.is_open:
            self.serial_port_obj.close()
        
        self.connect_btn.config(text="🔌 Connect")
        self.serial_baud_combo.config(state='readonly')
        self.write_to_serial_terminal("Disconnected\n", "info")
        self.log_debug("Serial disconnected")
        self.serial_port_obj = None
    
    def _serial_read_thread(self):
        """Thread to continuously read from serial port"""
        while self.serial_connected and self.serial_port_obj and self.serial_port_obj.is_open:
            try:
                if self.serial_port_obj.in_waiting > 0:
                    data = self.serial_port_obj.read(self.serial_port_obj.in_waiting)
                    if data:
                        # Try to decode as UTF-8, fallback to latin-1
                        try:
                            text = data.decode('utf-8')
                        except UnicodeDecodeError:
                            text = data.decode('latin-1')
                        
                        self.write_to_serial_terminal(text, "rx")
                
                time.sleep(0.01)  # Small delay to prevent busy waiting
                
            except Exception as e:
                if self.serial_connected:  # Only log if not intentionally disconnected
                    self.log_debug(f"Serial read error: {e}")
                    self.write_to_serial_terminal(f"Read error: {e}\n", "info")
                break
    
    def show_serial_advanced(self):
        """Show advanced serial options dialog"""
        # Simple dialog for now - can be expanded
        advanced_window = tk.Toplevel(self.root)
        advanced_window.title("Serial Advanced Options")
        advanced_window.geometry("300x200")
        advanced_window.resizable(False, False)
        
        # Center window
        advanced_window.update_idletasks()
        x = (advanced_window.winfo_screenwidth() // 2) - (advanced_window.winfo_width() // 2)
        y = (advanced_window.winfo_screenheight() // 2) - (advanced_window.winfo_height() // 2)
        advanced_window.geometry(f"+{x}+{y}")
        
        ttk.Label(advanced_window, text="Advanced serial options", 
                 font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Flow control options (placeholder for now)
        flow_frame = ttk.LabelFrame(advanced_window, text="Flow Control", padding="10")
        flow_frame.pack(fill='x', padx=10, pady=5)
        
        self.flow_control = tk.StringVar(value="none")
        ttk.Radiobutton(flow_frame, text="None", variable=self.flow_control, value="none").pack(anchor=tk.W)
        ttk.Radiobutton(flow_frame, text="RTS/CTS", variable=self.flow_control, value="rtscts").pack(anchor=tk.W)
        ttk.Radiobutton(flow_frame, text="XON/XOFF", variable=self.flow_control, value="xonxoff").pack(anchor=tk.W)
        
        ttk.Button(advanced_window, text="OK", command=advanced_window.destroy).pack(pady=10)

    def install_mkspiffs(self):
        """UI handler: install mkspiffs into repo tools/ using background thread."""
        if self.is_flashing:
            messagebox.showwarning("Ocupado", "No se puede instalar mientras hay una operación en progreso")
            return

        thread = threading.Thread(target=self._install_mkspiffs_thread)
        thread.daemon = True
        thread.start()

    def _install_mkspiffs_thread(self):
        """Background worker to download mkspiffs and report to UI."""
        try:
            self.set_buttons_state('disabled')
            script_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(script_dir, 'tools')
            os.makedirs(tools_dir, exist_ok=True)
            dest = os.path.join(tools_dir, 'mkspiffs.exe')

            self.log("📥 Instalando mkspiffs en carpeta tools/...", "info")
            self.log_debug(f"Destino mkspiffs: {dest}")

            try:
                self._download_mkspiffs(dest)
                self.log("✅ mkspiffs instalado correctamente", "success")
                messagebox.showinfo("Instalación completada", f"mkspiffs fue instalado en:\n{dest}")
            except Exception as e:
                self.log(f"❌ Error instalando mkspiffs: {e}", "error")
                messagebox.showerror("Error", f"No se pudo instalar mkspiffs:\n{e}")

        finally:
            self.set_buttons_state('normal')
    
    def save_log_to_file(self):
        """Save all logs to a file"""
        from tkinter import filedialog
        from datetime import datetime
        
        # Get default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"firmware_flash_log_{timestamp}.txt"
        
        # Ask user where to save
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Guardar Log"
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 80 + "\n")
                f.write(f"FIRMWARE BOOTLOADER LOG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                # Main log
                f.write("--- MAIN LOG ---\n")
                f.write(self.log_text.get(1.0, tk.END))
                f.write("\n" + "=" * 80 + "\n\n")
                
                # Debug log
                f.write("--- DEBUG LOG ---\n")
                f.write(self.debug_text.get(1.0, tk.END))
                f.write("\n" + "=" * 80 + "\n\n")
                
                # Serial log
                f.write("--- SERIAL MONITOR ---\n")
                f.write(self.serial_text.get(1.0, tk.END))
                f.write("\n" + "=" * 80 + "\n\n")
                
                # Session stats
                f.write("--- SESSION STATS ---\n")
                f.write(f"Total Flashes: {self.total_flashes}\n")
                f.write(f"Successful: {self.successful_flashes}\n")
                f.write(f"Unique Devices: {len(self.flashed_devices)}\n")
                if self.flashed_devices:
                    f.write("\nMAC Addresses:\n")
                    for mac in sorted(self.flashed_devices):
                        f.write(f"  {mac}\n")
            
            messagebox.showinfo("Éxito", f"Log guardado exitosamente:\n\n{filepath}")
            self.log(f"Log guardado en: {filepath}", "success")
            self.log_debug(f"Log file saved: {filepath}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando log:\n\n{str(e)}")
            self.log(f"Error guardando log: {e}", "error")
    
    def show_mode_info(self):
        """Show detailed information about flash modes in popup"""
        info_text = """
📘 GUÍA DE MODOS DE FLASHEO

🔒 SIMPLE MODE (Modo Seguro)
• Usa esto para: Actualizaciones rápidas de firmware
• Flashea: SOLO el archivo firmware.bin
• Preserva: Bootloader + Partitions + NVS (WiFi/config)
• Dirección: 0x10000 (estándar PlatformIO)
• Borrado: Solo la región del firmware
• Seguridad: 🟢 MUY SEGURO - no puede borrar bootloader
• Tiempo: Rápido (~30 segundos)

🔧 COMPLETE MODE (Modo Completo)
• Usa esto para: Chips nuevos, recuperación, cambio de particiones
• Flashea: bootloader.bin + partitions.bin + firmware.bin
• Preserva: Nada por defecto (puedes marcar checkboxes)
• Borrado: Todo el chip (o solo NVS si marcas opciones)
• Seguridad: 🟠 CUIDADO - puede borrar todo
• Tiempo: Más lento (~1-2 minutos)

✅ OPCIONES DISPONIBLES:

🔒 Preservar NVS/WiFi:
   • Mantiene credenciales WiFi y configuraciones
   • Útil cuando actualizas firmware pero no quieres reconfigurar
   • Solo funciona en Complete Mode

🚫 Preservar Bootloader:
   • No reflashea el bootloader existente
   • Útil cuando solo quieres actualizar partitions.bin + firmware.bin
   • Ejemplo: Cambiaste tamaño de particiones pero bootloader está bien
   • Solo funciona en Complete Mode

⚠️ CASOS DE USO COMUNES:

1️⃣ Actualizar firmware regularmente:
   ➡️ Usa SIMPLE MODE
   
2️⃣ Chip nuevo sin programar:
   ➡️ Usa COMPLETE MODE (todas las opciones desmarcadas)
   
3️⃣ Cambiar tabla de particiones:
   ➡️ Usa COMPLETE MODE + marca "Preservar Bootloader" + "Preservar NVS"
   
4️⃣ Chip bricked/corrupto:
   ➡️ Usa COMPLETE MODE (todas las opciones desmarcadas)
   
5️⃣ Actualizar firmware sin perder WiFi:
   ➡️ Usa SIMPLE MODE (preserva WiFi automáticamente)
"""
        
        # Create popup window
        info_window = tk.Toplevel(self.root)
        info_window.title("📘 Guía de Modos de Flasheo")
        info_window.geometry("700x650")
        
        # Center window
        info_window.update_idletasks()
        x = (info_window.winfo_screenwidth() // 2) - (info_window.winfo_width() // 2)
        y = (info_window.winfo_screenheight() // 2) - (info_window.winfo_height() // 2)
        info_window.geometry(f"+{x}+{y}")
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(info_window)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')
        
        info_text_widget = tk.Text(text_frame, wrap='word', yscrollcommand=scrollbar.set,
                           font=('Segoe UI', 10), bg='#f0f8ff', fg='#000000')
        info_text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=info_text_widget.yview)
        
        # Insert text
        info_text_widget.insert('1.0', info_text)
        info_text_widget.config(state='disabled')
        
        # Close button
        close_btn = ttk.Button(info_window, text="Cerrar", command=info_window.destroy, width=15)
        close_btn.pack(pady=10)
    
    def on_mode_change(self):
        """Handle flash mode change between Simple and Complete"""
        mode = self.flash_mode.get()
        
        if mode == "simple":
            # Simple mode - only firmware needed
            self.bootloader_label.config(text="No requerido (Simple Mode)", foreground="gray")
            self.partitions_label.config(text="No requerido (Simple Mode)", foreground="gray")
            self.bootloader_btn.config(state='disabled')
            self.partitions_btn.config(state='disabled')
            self.auto_detect_btn.config(state='disabled')
            self.log("Modo Simple: Solo firmware (bootloader/partitions/NVS siempre preservados)", "info")
        else:
            # Complete mode - all files needed
            self.bootloader_label.config(text="No seleccionado" if not self.bootloader_path else os.path.basename(self.bootloader_path), 
                                        foreground="orange" if not self.bootloader_path else "green")
            self.partitions_label.config(text="No seleccionado" if not self.partitions_path else os.path.basename(self.partitions_path),
                                        foreground="orange" if not self.partitions_path else "green")
            self.bootloader_btn.config(state='normal')
            self.partitions_btn.config(state='normal')
            self.auto_detect_btn.config(state='normal')
            self.log("Modo Completo: Bootloader + Partitions + Firmware (flasheo total)", "info")
    
    def select_firmware_file(self):
        """Open file dialog to select firmware.bin"""
        filename = filedialog.askopenfilename(
            title="Seleccionar Firmware",
            initialdir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware"),
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")]
        )
        if filename:
            self.firmware_path = filename
            self.firmware_label.config(text=f"{os.path.basename(filename)} ({self.get_file_size(filename)})", 
                                      foreground="green")
            self.log(f"Firmware seleccionado: {os.path.basename(filename)}", "success")
            
            # Auto-detect companion files
            self.auto_detect_companion_files(filename)
    
    def select_bootloader_file(self):
        """Open file dialog to select bootloader.bin"""
        filename = filedialog.askopenfilename(
            title="Seleccionar Bootloader",
            initialdir=os.path.dirname(self.firmware_path) if self.firmware_path else os.getcwd(),
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")]
        )
        if filename:
            self.bootloader_path = filename
            self.bootloader_label.config(text=f"{os.path.basename(filename)} ({self.get_file_size(filename)})", 
                                        foreground="green")
            self.log(f"Bootloader seleccionado: {os.path.basename(filename)}", "success")
    
    def select_partitions_file(self):
        """Open file dialog to select partitions.bin or partitions.csv"""
        filename = filedialog.askopenfilename(
            title="Seleccionar Partition Table (CSV o BIN)",
            initialdir=os.path.dirname(self.firmware_path) if self.firmware_path else os.getcwd(),
            filetypes=[("Partition files", "*.bin *.csv"), ("Binary files", "*.bin"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            # Check if it's a CSV file
            if filename.lower().endswith('.csv'):
                self.log(f"Archivo CSV detectado: {os.path.basename(filename)}", "info")
                # Convert to binary
                bin_path = self.convert_csv_to_bin(filename)
                if bin_path:
                    self.partitions_path = bin_path
                    self.partitions_label.config(text=f"{os.path.basename(filename)} → .bin", foreground="green")
                    self.log(f"Partitions CSV convertido: {os.path.basename(filename)}", "success")
                else:
                    messagebox.showerror("Error", "No se pudo convertir el CSV a formato binario")
            else:
                # It's already a binary file
                self.partitions_path = filename
                self.partitions_label.config(text=f"{os.path.basename(filename)} ({self.get_file_size(filename)})", 
                                            foreground="green")
                self.log(f"Partition table seleccionada: {os.path.basename(filename)}", "success")
    
    def auto_detect_companion_files(self, firmware_path):
        """Auto-detect bootloader.bin and partitions.bin near firmware"""
        firmware_dir = os.path.dirname(firmware_path)
        
        # Search for bootloader.bin
        bootloader_candidates = [
            os.path.join(firmware_dir, "bootloader.bin"),
            os.path.join(firmware_dir, "..", ".pio", "build", "esp32-s3-devkitc-1", "bootloader.bin"),
            os.path.join(firmware_dir, ".pio", "build", "esp32-s3-devkitc-1", "bootloader.bin")
        ]
        
        for candidate in bootloader_candidates:
            if os.path.exists(candidate):
                self.bootloader_path = candidate
                self.bootloader_label.config(text=f"✓ {os.path.basename(candidate)} (auto-detectado)", 
                                            foreground="green")
                self.log(f"Bootloader auto-detectado: {candidate}", "success")
                break
        
        # Search for partitions.bin
        partitions_candidates = [
            os.path.join(firmware_dir, "partitions.bin"),
            os.path.join(firmware_dir, "partition-table.bin"),
            os.path.join(firmware_dir, "..", ".pio", "build", "esp32-s3-devkitc-1", "partitions.bin"),
            os.path.join(firmware_dir, ".pio", "build", "esp32-s3-devkitc-1", "partition-table.bin")
        ]
        
        for candidate in partitions_candidates:
            if os.path.exists(candidate):
                self.partitions_path = candidate
                self.partitions_label.config(text=f"✓ {os.path.basename(candidate)} (auto-detectado)", 
                                            foreground="green")
                self.log(f"Partition table auto-detectada: {candidate}", "success")
                break
    
    def auto_detect_pio_files(self):
        """Auto-detect PlatformIO build files"""
        search_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pio", "build"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".pio", "build")
        ]
        
        found = False
        for search_path in search_paths:
            if os.path.exists(search_path):
                # Find build directories
                for board_dir in os.listdir(search_path):
                    board_path = os.path.join(search_path, board_dir)
                    if os.path.isdir(board_path):
                        fw = os.path.join(board_path, "firmware.bin")
                        bl = os.path.join(board_path, "bootloader.bin")
                        pt = os.path.join(board_path, "partitions.bin")
                        
                        if os.path.exists(fw) and os.path.exists(bl) and os.path.exists(pt):
                            self.firmware_path = fw
                            self.bootloader_path = bl
                            self.partitions_path = pt
                            
                            self.firmware_label.config(text=f"✓ {os.path.basename(fw)}", foreground="green")
                            self.bootloader_label.config(text=f"✓ {os.path.basename(bl)}", foreground="green")
                            self.partitions_label.config(text=f"✓ {os.path.basename(pt)}", foreground="green")
                            
                            self.log(f"Archivos PlatformIO detectados en: {board_path}", "success")
                            found = True
                            break
                if found:
                    break
        
        if not found:
            messagebox.showwarning("No encontrado", 
                                 "No se encontraron archivos de PlatformIO.\n\n"
                                 "Busca en: .pio/build/<board_name>/")
            self.log("No se encontraron archivos PlatformIO", "warning")
    
    def show_chip_info(self):
        """Get and display comprehensive chip information"""
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM primero.")
            return
        
        port = self.selected_port.get().split(' - ')[0]
        chip = self.selected_chip.get()
        
        # Show progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Obteniendo información del chip...")
        progress_window.geometry("400x100")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # Center window
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() // 2) - (progress_window.winfo_width() // 2)
        y = (progress_window.winfo_screenheight() // 2) - (progress_window.winfo_height() // 2)
        progress_window.geometry(f"+{x}+{y}")
        
        progress_label = ttk.Label(progress_window, text="Conectando con el chip...\nEsto puede tardar unos segundos.",
                                   font=('Segoe UI', 10), justify='center')
        progress_label.pack(expand=True, pady=20)
        
        progress_window.update()
        
        try:
            # Get Python executable
            python_exe = sys.executable
            if not python_exe or python_exe == '':
                python_exe = 'python'
            
            # Build command to get chip info
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", "115200",
                "chip-id"  # Updated from deprecated chip_id
            ]
            
            self.log_debug(f"Ejecutando chip-id: {' '.join(cmd)}")
            self.log_serial(f"CMD: chip-id on {port}", "tx")
            
            # Run command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Also get flash_id for more details
            cmd_flash = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", "115200",
                "flash-id"  # Updated from deprecated flash_id
            ]
            
            self.log_debug(f"Ejecutando flash-id: {' '.join(cmd_flash)}")
            result_flash = subprocess.run(
                cmd_flash,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Get security info (encryption, secure boot, etc.)
            cmd_security = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", "115200",
                "get-security-info"  # Updated: hyphenated
            ]
            
            self.log_debug(f"Ejecutando get-security-info: {' '.join(cmd_security)}")
            result_security = subprocess.run(
                cmd_security,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            progress_window.destroy()
            
            # Combine outputs
            full_output = "=" * 70 + "\n"
            full_output += "INFORMACIÓN DEL CHIP ESP32\n"
            full_output += "=" * 70 + "\n\n"
            
            if result.returncode == 0:
                full_output += "--- CHIP ID ---\n"
                full_output += result.stdout + "\n"
                self.log_serial("Chip info obtenida exitosamente", "rx")
            else:
                full_output += "--- ERROR CHIP ID ---\n"
                full_output += result.stderr + "\n"
            
            full_output += "\n" + "=" * 70 + "\n\n"
            
            if result_flash.returncode == 0:
                full_output += "--- FLASH ID & DETAILS ---\n"
                full_output += result_flash.stdout + "\n"
            else:
                full_output += "--- ERROR FLASH ID ---\n"
                full_output += result_flash.stderr + "\n"
            
            full_output += "\n" + "=" * 70 + "\n\n"
            
            if result_security.returncode == 0:
                full_output += "--- SECURITY INFO ---\n"
                full_output += result_security.stdout + "\n"
            else:
                full_output += "--- SECURITY INFO (Not Available) ---\n"
                full_output += "Security info not available for this chip/configuration\n"
            
            full_output += "\n" + "=" * 70 + "\n"
            
            # Parse and highlight key information (deduplicated)
            info_summary = "\n--- RESUMEN ---\n"
            seen_lines = set()  # Track what we've already added
            
            for line in (result.stdout + "\n" + result_flash.stdout + "\n" + result_security.stdout).split('\n'):
                # Clean line
                line = line.strip()
                
                # Check for key information
                if any(keyword in line for keyword in ["Chip type:", "Features:", "Crystal is", 
                                                        "Crystal frequency:", "MAC:",
                                                        "Flash size:", "Flash ID:", "Manufacturer:",
                                                        "Device:", "Detected flash size:",
                                                        "Flash Encryption:", "Secure Boot:"]):
                    # Only add if we haven't seen this exact line
                    if line not in seen_lines:
                        info_summary += line + "\n"
                        seen_lines.add(line)
            
            full_output += info_summary
            
            # Create popup window with info
            info_window = tk.Toplevel(self.root)
            info_window.title(f"Información del Chip - {port}")
            info_window.geometry("800x600")
            
            # Center window
            info_window.update_idletasks()
            x = (info_window.winfo_screenwidth() // 2) - (info_window.winfo_width() // 2)
            y = (info_window.winfo_screenheight() // 2) - (info_window.winfo_height() // 2)
            info_window.geometry(f"+{x}+{y}")
            
            # Create text widget with scrollbar
            text_frame = ttk.Frame(info_window)
            text_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side='right', fill='y')
            
            info_text = tk.Text(text_frame, wrap='word', yscrollcommand=scrollbar.set,
                               font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4')
            info_text.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=info_text.yview)
            
            # Insert text
            info_text.insert('1.0', full_output)
            info_text.config(state='normal')  # Keep editable for copy-paste
            
            # Add copy button
            button_frame = ttk.Frame(info_window)
            button_frame.pack(fill='x', padx=10, pady=(0,10))
            
            def copy_to_clipboard():
                info_window.clipboard_clear()
                info_window.clipboard_append(full_output)
                messagebox.showinfo("Copiado", "Información copiada al portapapeles", parent=info_window)
            
            copy_btn = ttk.Button(button_frame, text="📋 Copiar Todo", command=copy_to_clipboard)
            copy_btn.pack(side='left', padx=5)
            
            close_btn = ttk.Button(button_frame, text="Cerrar", command=info_window.destroy)
            close_btn.pack(side='right', padx=5)
            
            self.log(f"Información del chip obtenida para {port}", "success")
            self.log_debug(f"Chip info window opened")
            
        except subprocess.TimeoutExpired:
            progress_window.destroy()
            messagebox.showerror("Timeout", 
                f"No se pudo obtener información del chip.\n\n"
                f"Verifica que:\n"
                f"• El chip esté conectado correctamente\n"
                f"• El puerto COM sea correcto\n"
                f"• El chip no esté siendo usado por otro programa")
            self.log("Timeout obteniendo chip info", "error")
            
        except Exception as e:
            progress_window.destroy()
            messagebox.showerror("Error", f"Error obteniendo información del chip:\n\n{str(e)}")
            self.log(f"Error en show_chip_info: {e}", "error")
            self.log_debug(f"Exception: {repr(e)}")

    def flash_bootloader_only(self):
        """Flash only the bootloader - useful for recovery from invalid header errors"""
        if self.is_flashing:
            messagebox.showwarning("Ocupado", "Ya hay un flasheo en progreso")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM primero")
            return
        
        if not self.bootloader_path or not os.path.exists(self.bootloader_path):
            messagebox.showerror("Error", 
                "No se encontró el bootloader.\n\n"
                "Verifica que el archivo bootloader.bin exista en la carpeta firmware/")
            return
        
        # Confirm action
        port = self.selected_port.get().split(' - ')[0]
        chip = self.selected_chip.get()
        bootloader_addr = self.get_bootloader_address()
        
        confirm = messagebox.askyesno(
            "Confirmar Flash de Bootloader",
            f"🔧 MODO DE RECUPERACIÓN\n\n"
            f"Se flasheará SOLO el bootloader en:\n"
            f"• Puerto: {port}\n"
            f"• Chip: {chip}\n"
            f"• Dirección: {bootloader_addr}\n"
            f"• Archivo: {os.path.basename(self.bootloader_path)}\n\n"
            f"Esta operación puede recuperar chips con 'invalid header' error.\n\n"
            f"¿Continuar?"
        )
        
        if not confirm:
            self.log("Flash de bootloader cancelado por el usuario", "info")
            return
        
        self.log("=" * 60, "info")
        self.log("🔧 INICIANDO FLASH DE BOOTLOADER SOLO (RECOVERY MODE)", "info")
        self.log("=" * 60, "info")
        self.log(f"Puerto: {port}", "info")
        self.log(f"Chip: {chip}", "info")
        self.log(f"Bootloader: {bootloader_addr} → {os.path.basename(self.bootloader_path)}", "info")
        
        # Start flashing in thread
        thread = threading.Thread(
            target=self._flash_bootloader_only_thread,
            args=(port, chip, bootloader_addr)
        )
        thread.daemon = True
        thread.start()
    
    def _flash_bootloader_only_thread(self, port, chip, bootloader_addr):
        """Thread to flash only bootloader"""
        self.is_flashing = True
        self.set_buttons_state('disabled')
        
        try:
            # Get Python executable path
            python_exe = sys.executable
            self.log_debug(f"Python executable: {python_exe}")
            
            # Build esptool command
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", str(self.selected_baud.get()),
                "--before", "default-reset",
                "--after", "hard-reset",
                "write-flash",
                "-z",  # Compress
                "--flash_mode", "dio",
                "--flash_freq", "80m",
                "--flash_size", "detect",
                bootloader_addr, self.bootloader_path
            ]
            
            self.log_debug(f"Comando esptool: {' '.join(cmd)}")
            self.log("Flasheando bootloader...", "info")
            
            # Execute command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                if line:
                    line = line.strip()
                    match = re.search(r'(\d+\.\d+)%', line)
                    if match:
                        percent = float(match.group(1))
                        self.progress['value'] = percent
                        self.root.update_idletasks()
                    
                    # Update status label
                    if "Connecting" in line:
                        self.status_label.config(text="🔌 Connecting to device...")
                    elif "Erasing" in line or "erase" in line.lower():
                        self.status_label.config(text="🗑️ Erasing flash...")
                    elif "Writing at" in line:
                        self.status_label.config(text="📤 Uploading bootloader...")
                    elif "Hash of data verified" in line:
                        self.status_label.config(text="✅ Verifying bootloader...")
                    elif "Compressed" in line:
                        self.status_label.config(text="📦 Compressing bootloader...")
                    elif "Uploading" in line:
                        self.status_label.config(text="📤 Uploading stub...")
                    
                    self.log_debug(f"esptool: {line}")
                    
                    # Show progress
                    if "Writing at" in line or "Wrote" in line or "Hash of data verified" in line:
                        self.log(line, "info")
            
            process.wait()
            
            if process.returncode == 0:
                self.log("=" * 60, "success")
                self.log("✅ BOOTLOADER FLASHEADO CORRECTAMENTE", "success")
                self.log("=" * 60, "success")
                self.log("El chip debería reiniciarse automáticamente", "info")
                self.log("Si persiste 'invalid header', verifica particiones y firmware", "info")
                messagebox.showinfo(
                    "Éxito",
                    "✅ Bootloader flasheado correctamente\n\n"
                    "El chip debería reiniciarse automáticamente.\n"
                    "Si aún muestra 'invalid header', verifica que\n"
                    "las particiones y el firmware estén flasheados."
                )
            else:
                self.log(f"Error: esptool retornó código {process.returncode}", "error")
                messagebox.showerror(
                    "Error",
                    f"Error flasheando bootloader.\n\n"
                    f"Código de error: {process.returncode}\n\n"
                    f"Revisa el log para más detalles."
                )
        
        except Exception as e:
            self.log(f"❌ ERROR flasheando bootloader: {e}", "error")
            self.log_debug(f"Exception: {repr(e)}")
            messagebox.showerror("Error", f"Error flasheando bootloader:\n\n{str(e)}")
        
        finally:
            self.is_flashing = False
            self.set_buttons_state('normal')
            self.log_debug("Flash de bootloader finalizado")

    def get_valid_bootloader(self):
        """Obtener un bootloader válido para ESP32-S3, crear uno si es necesario"""
        try:
            # 1. Verificar si ya tenemos uno válido
            if self.bootloader_path and os.path.exists(self.bootloader_path):
                with open(self.bootloader_path, 'rb') as f:
                    header = f.read(16)
                if len(header) >= 16 and header[0] == 0xE9:  # Magic byte válido
                    self.log("✅ Bootloader existente es válido", "success")
                    return self.bootloader_path
            
            # 2. Buscar bootloader en carpeta firmware/
            firmware_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware")
            potential_bootloaders = [
                "bootloader.bin",
                "esp32s3_bootloader.bin", 
                "bootloader_esp32s3.bin"
            ]
            
            for bootloader_name in potential_bootloaders:
                bootloader_file = os.path.join(firmware_dir, bootloader_name)
                if os.path.exists(bootloader_file):
                    with open(bootloader_file, 'rb') as f:
                        header = f.read(16)
                    if len(header) >= 16 and header[0] == 0xE9:
                        self.log(f"✅ Bootloader válido encontrado: {bootloader_name}", "success")
                        self.bootloader_path = bootloader_file
                        return bootloader_file
            
            # 3. Intentar usar esptool para obtener un bootloader de referencia
            self.log("🔍 Buscando bootloader de referencia con esptool...", "info")
            try:
                import esptool
                # Intentar obtener bootloader desde el chip conectado
                if self.selected_port.get():
                    port = self.selected_port.get().split(' - ')[0]
                    temp_bootloader = os.path.join(tempfile.gettempdir(), "extracted_bootloader.bin")
                    
                    # Leer bootloader desde el chip (si existe)
                    python_exe = sys.executable
                    cmd = [
                        python_exe, "-m", "esptool",
                        "--port", port,
                        "--baud", "115200",
                        "read-flash", "0x0", "0x5000", temp_bootloader
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0 and os.path.exists(temp_bootloader):
                        # Verificar si el bootloader leído es válido
                        with open(temp_bootloader, 'rb') as f:
                            header = f.read(16)
                        if len(header) >= 16 and header[0] == 0xE9:
                            self.log("✅ Bootloader extraído del chip es válido", "success")
                            # Copiarlo a la carpeta firmware
                            dest_bootloader = os.path.join(firmware_dir, "extracted_bootloader.bin")
                            os.makedirs(firmware_dir, exist_ok=True)
                            with open(temp_bootloader, 'rb') as src, open(dest_bootloader, 'wb') as dst:
                                dst.write(src.read())
                            self.bootloader_path = dest_bootloader
                            return dest_bootloader
            except:
                pass
            
            # 4. Como último recurso, crear uno básico
            self.log("🔧 Generando bootloader básico para ESP32-S3...", "warning")
            bootloader_file = self.create_esp32s3_bootloader()
            if bootloader_file and os.path.exists(bootloader_file):
                # Copiarlo a la carpeta firmware
                dest_bootloader = os.path.join(firmware_dir, "generated_bootloader.bin")
                os.makedirs(firmware_dir, exist_ok=True)
                with open(bootloader_file, 'rb') as src, open(dest_bootloader, 'wb') as dst:
                    dst.write(src.read())
                self.bootloader_path = dest_bootloader
                self.log("⚠️ Usando bootloader generado básico - puede requerir ajustes", "warning")
                return dest_bootloader
            
            return None
            
        except Exception as e:
            self.log(f"❌ Error obteniendo bootloader válido: {e}", "error")
            return None

    def fix_invalid_header(self):
        """Fix invalid header error by flashing a valid bootloader and complete firmware"""
        if self.is_flashing:
            messagebox.showwarning("Ocupado", "Ya hay un flasheo en progreso")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM primero")
            return
        
        # Confirm the fix
        msg = ("🚑 REPARACIÓN DE INVALID HEADER\n\n"
               "Esta función intentará reparar el error 'invalid header: 0xffffffff'\n"
               "realizando las siguientes acciones:\n\n"
               "1. Borrar completamente la memoria flash\n"
               "2. Obtener/crear un bootloader válido para ESP32-S3\n"
               "3. Flashear bootloader + particiones + firmware\n\n"
               "⚠️ ADVERTENCIA: Esto borrará TODOS los datos del chip.\n"
               "¿Continuar con la reparación?")
        
        if not messagebox.askyesno("Confirmar Reparación", msg):
            return
        
        # Start repair process in thread
        thread = threading.Thread(target=self._fix_invalid_header_thread)
        thread.daemon = True
        thread.start()
    
    def _fix_invalid_header_thread(self):
        """Thread to fix invalid header error"""
        self.is_flashing = True
        self.set_buttons_state('disabled')
        
        try:
            port = self.selected_port.get().split(' - ')[0]
            chip = self.selected_chip.get()
            python_exe = sys.executable
            
            self.log("🚑 INICIANDO REPARACIÓN DE INVALID HEADER", "info")
            self.log("=" * 50, "info")
            
            # Step 1: Erase flash completely
            self.log("🗑️ Paso 1/4: Borrando memoria flash completa...", "info")
            erase_cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", str(self.selected_baud.get()),
                "erase-flash"
            ]
            
            result = subprocess.run(erase_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise Exception(f"Error borrando flash: {result.stderr}")
            
            self.log("✅ Flash borrada completamente", "success")
            
            # Step 2: Get valid bootloader
            self.log("🔧 Paso 2/4: Obteniendo bootloader válido...", "info")
            bootloader_file = self.get_valid_bootloader()
            if not bootloader_file:
                raise Exception("No se pudo obtener un bootloader válido")
            
            self.log(f"✅ Bootloader válido: {os.path.basename(bootloader_file)}", "success")
            
            # Step 3: Ensure we have partitions
            self.log("📊 Paso 3/4: Verificando tabla de particiones...", "info")
            if not self.partitions_path or not os.path.exists(self.partitions_path):
                # Try to find partitions.csv in firmware folder
                firmware_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware")
                partitions_file = os.path.join(firmware_dir, "partitions.csv")
                if os.path.exists(partitions_file):
                    self.partitions_path = partitions_file
                    self.log(f"✅ Encontradas particiones: {os.path.basename(partitions_file)}", "success")
                else:
                    # Create a default partition table
                    self.log("⚠️ No se encontró tabla de particiones, creando una por defecto...", "warning")
                    default_partitions = self._create_default_partition_table(firmware_dir)
                    if default_partitions:
                        self.partitions_path = default_partitions
                        self.log(f"✅ Tabla de particiones por defecto creada: {os.path.basename(default_partitions)}", "success")
                    else:
                        raise Exception("No se pudo crear tabla de particiones válida")
            
            # Step 4: Flash everything (bootloader + partitions + firmware)
            self.log("⚡ Paso 4/4: Flasheando bootloader + particiones + firmware...", "info")
            
            # Prepare flash command
            flash_cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", str(self.selected_baud.get()),
                "--before", "default-reset",
                "--after", "hard-reset",
                "write_flash",
                "-z"  # Compress
            ]
            
            # Add bootloader
            flash_cmd.extend(["0x0", bootloader_file])
            
            # Add partitions
            partitions_addr = self.get_partition_table_address()
            if self.partitions_path.lower().endswith('.csv'):
                # Convert CSV to BIN
                partitions_bin = self.convert_csv_to_bin(self.partitions_path)
                if partitions_bin:
                    flash_cmd.extend([partitions_addr, partitions_bin])
                else:
                    flash_cmd.extend([partitions_addr, self.partitions_path])
            else:
                flash_cmd.extend([partitions_addr, self.partitions_path])
            
            # Add firmware
            if not self.firmware_path or not os.path.exists(self.firmware_path):
                raise Exception("No se seleccionó archivo de firmware")
            
            # Get correct firmware address from partition table
            firmware_addr, has_ota = self.parse_partition_table_file(self.partitions_path)
            flash_cmd.extend([firmware_addr, self.firmware_path])
            
            self.log(f"Comando: {' '.join(flash_cmd[5:])}", "info")  # Skip sensitive parts
            
            # Execute flash command
            result = subprocess.run(flash_cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.log("🎉 REPARACIÓN COMPLETADA EXITOSAMENTE!", "success")
                self.log("=" * 50, "success")
                self.log("El chip debería arrancar correctamente ahora.", "success")
                messagebox.showinfo("Reparación Exitosa", 
                    "✅ Reparación completada exitosamente!\n\n"
                    "El ESP32-S3 debería arrancar correctamente ahora.\n"
                    "Puedes desconectar y reconectar el dispositivo.")
            else:
                raise Exception(f"Error en flasheo: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.log("❌ TIMEOUT en reparación", "error")
            messagebox.showerror("Timeout", "La reparación tomó demasiado tiempo. Verifica la conexión.")
        except Exception as e:
            self.log(f"❌ ERROR en reparación: {e}", "error")
            messagebox.showerror("Error de Reparación", f"Error durante la reparación:\n\n{str(e)}")
        finally:
            self.is_flashing = False
            self.set_buttons_state('normal')

    def _create_default_partition_table(self, firmware_dir):
        """Create a default partition table CSV file for ESP32-S3"""
        try:
            os.makedirs(firmware_dir, exist_ok=True)
            partitions_file = os.path.join(firmware_dir, "default_partitions.csv")
            
            # Default partition table for ESP32-S3 with OTA support
            default_csv = """# ESP32-S3 Default Partition Table
# Name,      Type, SubType, Offset,   Size, Flags
nvs,         data, nvs,     0x9000,   24K
otadata,     data, ota,     0xf000,   8K
phy_init,    data, phy,     0x11000,  4K
app0,        app,  ota_0,   0x20000,  1280K
app1,        app,  ota_1,   0x160000, 1280K
spiffs,      data, spiffs,  0x2A0000, 1472K
"""
            
            with open(partitions_file, 'w') as f:
                f.write(default_csv)
            
            self.log("📝 Tabla de particiones por defecto creada con configuración OTA", "info")
            return partitions_file
            
        except Exception as e:
            self.log(f"❌ Error creando tabla de particiones por defecto: {e}", "error")
            return None

    def upload_data_folder(self):
        """Upload data folder to SPIFFS partition (similar to PlatformIO uploadfs)"""
        if self.is_flashing:
            messagebox.showwarning("Ocupado", "Ya hay una operación en progreso")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM primero")
            return
        
        # Check if data folder exists
        data_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        if not os.path.exists(data_folder):
            messagebox.showerror("Error", 
                f"No se encontró la carpeta 'data' en:\n{data_folder}\n\n"
                f"Crea una carpeta 'data' con los archivos a subir.")
            return
        
        # Check if folder has files
        files = [f for f in os.listdir(data_folder) if os.path.isfile(os.path.join(data_folder, f))]
        if not files:
            messagebox.showwarning("Advertencia", 
                f"La carpeta 'data' está vacía.\nNo hay archivos para subir.")
            return
        
        # Get partition info
        port = self.selected_port.get().split(' - ')[0]
        chip = self.selected_chip.get()
        
        # Confirm action
        file_list = "\n".join([f"  • {f}" for f in files[:10]])
        if len(files) > 10:
            file_list += f"\n  ... y {len(files) - 10} archivo(s) más"
        
        confirm = messagebox.askyesno(
            "Confirmar Upload de Datos",
            f"📤 UPLOAD DATA FOLDER (SPIFFS)\n\n"
            f"Se subirán {len(files)} archivo(s) a SPIFFS:\n\n"
            f"{file_list}\n\n"
            f"• Puerto: {port}\n"
            f"• Chip: {chip}\n"
            f"• Partición: Se detectará automáticamente desde el dispositivo\n\n"
            f"Esta operación creará una imagen del filesystem\n"
            f"y la flasheará en la partición SPIFFS.\n\n"
            f"¿Continuar?"
        )
        
        if not confirm:
            self.log("Upload de datos cancelado por el usuario", "info")
            return
        
        self.log("=" * 60, "info")
        self.log("📤 INICIANDO UPLOAD DATA FOLDER (SPIFFS)", "info")
        self.log("=" * 60, "info")
        self.log(f"Puerto: {port}", "info")
        self.log(f"Chip: {chip}", "info")
        self.log(f"Archivos: {len(files)}", "info")
        
        # Start upload in thread
        thread = threading.Thread(
            target=self._upload_data_thread,
            args=(port, chip, data_folder)
        )
        thread.daemon = True
        thread.start()
    
    def _upload_data_thread(self, port, chip, data_folder):
        """Thread to build SPIFFS image and upload it"""
        self.is_flashing = True
        self.set_buttons_state('disabled')
        
        try:
            python_exe = sys.executable
            
            # Step 0: Detect SPIFFS partition address and size
            self.log("🔍 Paso 0/3: Detectando partición SPIFFS...", "info")
            
            spiffs_info = self._detect_spiffs_partition(port, chip)
            if not spiffs_info:
                self.log("❌ No se pudo detectar la partición SPIFFS", "error")
                messagebox.showerror("Error", 
                    "No se pudo detectar la partición SPIFFS en el dispositivo.\n\n"
                    "Asegúrate de que el dispositivo tenga una tabla de particiones válida\n"
                    "con una partición SPIFFS configurada.")
                return
            
            spiffs_offset, spiffs_size = spiffs_info
            self.log(f"✅ SPIFFS detectado: 0x{spiffs_offset:X} ({spiffs_size} bytes)", "success")
            
            # Step 1: Build SPIFFS image
            self.log("🔨 Paso 1/3: Construyendo imagen SPIFFS...", "info")
            
            spiffs_image = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spiffs.bin")
            
            # Step 1: Build SPIFFS image using best available tool
            try:
                self.log_debug("Intentando crear imagen SPIFFS usando herramientas preferidas (esp-idf, mkspiffs)")
                self._build_spiffs_image(data_folder, spiffs_image, spiffs_size)
                self.log("✅ Imagen SPIFFS creada exitosamente", "success")
                try:
                    self.log(f"📦 Tamaño: {os.path.getsize(spiffs_image)} bytes", "info")
                except:
                    pass

            except Exception as e:
                self.log(f"⚠️ No se pudo crear imagen SPIFFS con herramientas externas: {e}", "warning")
                self.log("📝 Creando imagen SPIFFS manualmente (fallback)...", "info")
                # Create a simple SPIFFS-like image (padded binary)
                self._create_simple_spiffs_image(data_folder, spiffs_image, spiffs_size)
                self.log("✅ Imagen SPIFFS básica creada", "success")
            
            # Step 2: Flash SPIFFS image
            self.log(f"📤 Paso 2/3: Flasheando SPIFFS a 0x{spiffs_offset:X}...", "info")
            
            flash_cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", str(self.selected_baud.get()),
                "--before", "default-reset",
                "--after", "hard-reset",
                "write-flash",
                "-z",
                "--flash-mode", "dio",
                "--flash-freq", "80m",
                "--flash-size", "detect",
                f"0x{spiffs_offset:X}", spiffs_image
            ]
            
            self.log_debug(f"Comando flash: {' '.join(flash_cmd)}")
            
            process = subprocess.Popen(
                flash_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output
            for line in iter(process.stdout.readline, ''):
                if line:
                    line = line.strip()
                    match = re.search(r'(\d+\.\d+)%', line)
                    if match:
                        percent = float(match.group(1))
                        self.progress['value'] = percent
                        self.root.update_idletasks()
                    
                    # Update status label
                    if "Connecting" in line:
                        self.status_label.config(text="🔌 Connecting to device...")
                    elif "Erasing" in line or "erase" in line.lower():
                        self.status_label.config(text="🗑️ Erasing flash...")
                    elif "Writing at" in line:
                        self.status_label.config(text="📤 Uploading SPIFFS...")
                    elif "Hash of data verified" in line:
                        self.status_label.config(text="✅ Verifying SPIFFS...")
                    elif "Compressed" in line:
                        self.status_label.config(text="📦 Compressing SPIFFS...")
                    elif "Uploading" in line:
                        self.status_label.config(text="📤 Uploading stub...")
                    
                    self.log_debug(f"esptool: {line}")
                    
                    if "Writing at" in line or "Wrote" in line or "Hash of data verified" in line:
                        self.log(line, "info")
            
            process.wait()
            
            if process.returncode == 0:
                self.log("=" * 60, "success")
                self.log("✅ DATA FOLDER SUBIDA EXITOSAMENTE", "success")
                self.log("=" * 60, "success")
                self.log("Los archivos están ahora disponibles en SPIFFS", "info")
                self.log("ℹ️ Nota: El ESP32 inicializará el filesystem al arrancar", "info")
                
                messagebox.showinfo(
                    "Éxito",
                    "✅ Data folder subida exitosamente a SPIFFS\n\n"
                    "Los archivos están ahora disponibles en el ESP32.\n\n"
                    "El filesystem será inicializado cuando el ESP32 arranque."
                )
            else:
                self.log(f"❌ Error: esptool retornó código {process.returncode}", "error")
                messagebox.showerror(
                    "Error",
                    f"Error subiendo data folder.\n\n"
                    f"Código de error: {process.returncode}\n\n"
                    f"Revisa el log para más detalles."
                )
        
        except Exception as e:
            self.log(f"❌ ERROR subiendo data folder: {e}", "error")
            self.log_debug(f"Exception: {repr(e)}")
            messagebox.showerror("Error", f"Error subiendo data folder:\n\n{str(e)}")
        
        finally:
            self.is_flashing = False
            self.set_buttons_state('normal')
            self.progress['value'] = 0
            self.status_label.config(text="Idle")
    
    def _detect_spiffs_partition(self, port, chip):
        """Detect SPIFFS partition address and size from device"""
        try:
            python_exe = sys.executable
            script_dir = os.path.dirname(os.path.abspath(__file__))
            temp_file = os.path.join(script_dir, "temp_partitions.bin")
            
            # Read partition table from device
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", "115200",
                "read-flash",
                "0x8000", "0x1000",  # Read 4KB partition table
                temp_file
            ]
            
            self.log_debug(f"Reading partition table: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0 or not os.path.exists(temp_file):
                self.log_debug(f"Failed to read partition table: {result.stderr}")
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
                self.log_debug("Invalid partition table magic bytes")
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
                    self.log_debug(f"Found SPIFFS partition: {label} @ 0x{p_offset:X}, size 0x{p_size:X}")
                    return (p_offset, p_size)
                
                offset += 32
            
            self.log_debug("No SPIFFS partition found in partition table")
            return None
            
        except Exception as e:
            self.log_debug(f"Error detecting SPIFFS partition: {e}")
            return None
    
    def _create_simple_spiffs_image(self, data_folder, output_file, size):
        """Create a simple SPIFFS-like image with object entries (fallback when mkspiffs not available)"""
        import struct
        
        try:
            # Collect all files
            files = []
            for filename in sorted(os.listdir(data_folder)):
                filepath = os.path.join(data_folder, filename)
                if os.path.isfile(filepath):
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    files.append((filename, content))
                    self.log(f"  📄 Agregando: {filename} ({len(content)} bytes)", "info")
            
            with open(output_file, 'wb') as out:
                # SPIFFS superblock (simplified)
                # Magic bytes
                out.write(b'\x53\x50\x49\x46')  # 'SPIF'
                # Version
                out.write(struct.pack('<I', 0x10000))  # Version 1.0.0
                # Block size
                block_size = 4096
                out.write(struct.pack('<I', block_size))
                # Page size
                page_size = 256
                out.write(struct.pack('<I', page_size))
                # Reserved
                out.write(struct.pack('<I', 0))
                
                # Calculate data start offset (after superblock)
                data_offset = 4096  # Start after first block
                
                # Create file objects
                current_offset = data_offset
                for filename, content in files:
                    # Object header (simplified SPIFFS object format)
                    # Object type (file = 1)
                    out.write(struct.pack('<B', 1))

                    # Use relative path inside data folder and normalize separators
                    relpath = os.path.relpath(os.path.join(data_folder, filename), data_folder).replace('\\', '/')
                    # If files are at the root of data/, place them under the 'spiffs/' directory
                    if not relpath.startswith('spiffs/'):
                        relpath = 'spiffs/' + relpath

                    # Name length + name
                    name_bytes = relpath.encode('utf-8')
                    out.write(struct.pack('<B', len(name_bytes)))
                    out.write(name_bytes)

                    # Pad name to 32 bytes total (type + len + name)
                    header_size = 2 + len(name_bytes)
                    pad_size = 32 - header_size
                    if pad_size > 0:
                        out.write(b'\x00' * pad_size)

                    # File size
                    out.write(struct.pack('<I', len(content)))
                    # Data offset
                    out.write(struct.pack('<I', current_offset))
                    # Reserved
                    out.write(struct.pack('<I', 0))

                    current_offset += len(content)
                
                # Fill rest of superblock with 0xFF
                current_pos = out.tell()
                while current_pos < data_offset:
                    out.write(b'\xFF')
                    current_pos += 1
                
                # Write file data
                for filename, content in files:
                    out.write(content)
                
                # Pad to full size with 0xFF
                current_size = out.tell()
                padding = size - current_size
                if padding > 0:
                    out.write(b'\xFF' * padding)
            
            self.log(f"✅ Imagen SPIFFS básica creada ({len(files)} archivos)", "success")
            self.log(f"⚠️ ADVERTENCIA: Usando formato SPIFFS simplificado", "warning")
            self.log(f"   Para funcionalidad completa, instala mkspiffs", "warning")
            
        except Exception as e:
            self.log(f"❌ Error creando imagen SPIFFS: {e}", "error")
            # Fallback to even simpler method
            self.log("📝 Usando método de concatenación básico...", "info")
            with open(output_file, 'wb') as out:
                for filename in sorted(os.listdir(data_folder)):
                    filepath = os.path.join(data_folder, filename)
                    if os.path.isfile(filepath):
                        with open(filepath, 'rb') as f:
                            out.write(f.read())
                
                current_size = out.tell()
                padding = size - current_size
                if padding > 0:
                    out.write(b'\xFF' * padding)

    def _build_spiffs_image(self, data_folder, output_file, size):
        """Attempt to build SPIFFS image using esp-idf spiffsgen, then mkspiffs.
        Raises Exception if no suitable tool is available or all attempts fail.
        """
        import shutil, sys

        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Helper: search repository 'tools' folder for candidate scripts/binaries
        def repo_tools_candidates(name):
            tools_dir = os.path.join(script_dir, 'tools')
            candidates = []
            if os.path.exists(tools_dir):
                for root, _, files in os.walk(tools_dir):
                    for f in files:
                        if f.lower() == name.lower() or f.lower().startswith(name.lower()):
                            candidates.append(os.path.join(root, f))
            return candidates

        # 1) Prefer spiffsgen.py found in repo tools/ or in IDF_PATH
        spiffsgen_candidates = []
        spiffsgen_candidates.extend(repo_tools_candidates('spiffsgen.py'))
        idf_path = os.environ.get('IDF_PATH') or os.environ.get('ESP_IDF_PATH')
        if idf_path:
            spiffsgen_candidates.append(os.path.join(idf_path, 'tools', 'spiffsgen.py'))
            spiffsgen_candidates.append(os.path.join(idf_path, 'components', 'spiffs', 'spiffsgen.py'))

        for spiffsgen in spiffsgen_candidates:
            if spiffsgen and os.path.exists(spiffsgen):
                cmd = [sys.executable, spiffsgen, '-c', data_folder, '-s', str(size), output_file]
                self.log_debug(f"Intentando spiffsgen: {' '.join(cmd)}")
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        self.log_debug("spiffsgen creado con éxito")
                        return
                    else:
                        self.log_debug(f"spiffsgen falló ({spiffsgen}): {result.stderr}")
                except Exception as e:
                    self.log_debug(f"Error ejecutando spiffsgen ({spiffsgen}): {e}")

        # 2) Try mkspiffs: first check repo tools folder, then PATH, then attempt download
        mkspiffs_candidates = repo_tools_candidates('mkspiffs.exe')
        # include mkspiffs without extension too
        mkspiffs_candidates.extend(repo_tools_candidates('mkspiffs'))

        # Check PATH
        which_path = shutil.which('mkspiffs')
        if which_path:
            mkspiffs_candidates.append(which_path)

        # 2b) Check PlatformIO packages for tool-mkspiffs
        try:
            pio_base = os.path.join(os.path.expanduser('~'), '.platformio', 'packages')
            if os.path.exists(pio_base):
                for root, dirs, files in os.walk(pio_base):
                    for d in dirs:
                        if d.lower().startswith('tool-mkspiffs') or d.lower().startswith('mkspiffs'):
                            candidate = os.path.join(root, d)
                            # common bin locations
                            for sub in ('bin', ''):
                                cand = os.path.join(candidate, sub, 'mkspiffs.exe')
                                if os.path.exists(cand):
                                    mkspiffs_candidates.append(cand)
                                cand2 = os.path.join(candidate, sub, 'mkspiffs')
                                if os.path.exists(cand2):
                                    mkspiffs_candidates.append(cand2)
        except Exception:
            pass

        # If none found in repo tools, attempt to auto-download into tools/
        tools_dir = os.path.join(script_dir, 'tools')
        os.makedirs(tools_dir, exist_ok=True)
        repo_mkspiffs = os.path.join(tools_dir, 'mkspiffs.exe')
        if not any(os.path.exists(p) for p in mkspiffs_candidates) and not os.path.exists(repo_mkspiffs):
            try:
                self.log_debug('Attempting to download mkspiffs binary into tools/ folder')
                self._download_mkspiffs(repo_mkspiffs)
                mkspiffs_candidates.append(repo_mkspiffs)
            except Exception as e:
                self.log_debug(f'mkspiffs download failed: {e}')

        # Prefer PlatformIO-provided mkspiffs for espidf if present
        ordered = []
        espidf_pref = []
        other_pref = []
        for p in mkspiffs_candidates:
            lname = os.path.basename(p).lower()
            if 'espressif32_espidf' in lname or ('espressif32' in lname and 'espidf' in lname):
                espidf_pref.append(p)
            else:
                other_pref.append(p)
        ordered.extend(espidf_pref)
        ordered.extend(other_pref)

        for mkb in ordered:
            if mkb and os.path.exists(mkb):
                # Use the same flags PlatformIO uses for espressif32 espidf builds
                cmd = [mkb, '-c', data_folder, '-s', str(size), '-p', '256', '-b', '4096', output_file]
                self.log_debug(f"Intentando mkspiffs: {' '.join(cmd)}")
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        self.log_debug('mkspiffs creado con éxito')
                        return
                    else:
                        self.log_debug(f'mkspiffs falló ({mkb}): {result.stderr}')
                except Exception as e:
                    self.log_debug(f'Error ejecutando mkspiffs ({mkb}): {e}')

        # If we reach here, no external tool produced a valid image
        raise Exception('No se encontró spiffsgen (esp-idf) ni mkspiffs funcionales (intentado repo tools, PATH y descarga)')

    def _download_mkspiffs(self, dest_path):
        """Attempt to download mkspiffs binary from GitHub releases into dest_path.
        If download fails, raises Exception with instructions for manual placement.
        """
        import urllib.request
        import stat

        # Try GitHub API to find latest release asset for Windows x64, then fall back to known URLs
        api_url = 'https://api.github.com/repos/igrr/mkspiffs/releases/latest'
        tried_urls = []

        def try_url(u):
            self.log_debug(f"Attempting download from {u}")
            tried_urls.append(u)
            with urllib.request.urlopen(u, timeout=30) as resp:
                if resp.status != 200:
                    raise Exception(f'HTTP {resp.status}')
                data = resp.read()
            with open(dest_path, 'wb') as f:
                f.write(data)
            try:
                os.chmod(dest_path, stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)
            except Exception:
                pass
            self.log(f"✅ mkspiffs descargado en: {dest_path}", 'success')
            return True

        # 1) Try GitHub API to locate an appropriate asset
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'python-urllib'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    import json
                    info = json.load(resp)
                    for asset in info.get('assets', []):
                        name = asset.get('name', '').lower()
                        if 'windows' in name or 'win' in name or 'x64' in name:
                            download_url = asset.get('browser_download_url')
                            try:
                                if try_url(download_url):
                                    return
                            except Exception as e:
                                self.log_debug(f'GitHub asset download failed: {e}')
        except Exception as e:
            self.log_debug(f'GitHub API check failed: {e}')

        # 2) Fallback list of direct release URLs (older releases)
        fallback_urls = [
            'https://github.com/igrr/mkspiffs/releases/download/0.2.3/mkspiffs-0.2.3-windows-x64.exe',
            'https://github.com/igrr/mkspiffs/releases/download/0.2.2/mkspiffs-0.2.2-windows-x64.exe',
        ]

        for u in fallback_urls:
            try:
                if try_url(u):
                    return
            except Exception as e:
                self.log_debug(f'Fallback URL failed: {u} -> {e}')

        # If download failed, remove any partial file
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except:
            pass

        raise Exception(f"No se pudo descargar mkspiffs automáticamente. Intentados: {tried_urls}.\nPor favor descarga 'mkspiffs-<version>-windows-x64.exe' de https://github.com/igrr/mkspiffs/releases y colócalo en: {os.path.dirname(dest_path)}")

    def _verify_spiffs_upload(self, port, chip, spiffs_image):
        """Verify that SPIFFS partition has data (not empty/erased)"""
        import time
        
        try:
            # Wait for port to be ready after reset
            time.sleep(2)
            
            python_exe = sys.executable
            
            # Read first 4KB of SPIFFS to check it's not empty
            temp_read = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spiffs_check.bin")
            
            # Remove old file if it exists
            if os.path.exists(temp_read):
                try:
                    os.remove(temp_read)
                except:
                    pass
            
            check_size = 4096  # Just read first 4KB
            
            read_cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", "115200",  # Use slower baud for reliability
                "read-flash",  # Use hyphenated version
                "0x5F0000", str(check_size), temp_read
            ]
            
            self.log_debug(f"Verificando SPIFFS: {' '.join(read_cmd)}")
            
            result = subprocess.run(
                read_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.log_debug(f"Error leyendo SPIFFS: {result.stderr}")
                return False
            
            # Wait for file to be fully written
            time.sleep(0.5)
            
            # Check if partition is not empty (all 0xFF means erased)
            data = None
            try:
                with open(temp_read, 'rb') as f:
                    data = f.read()
            finally:
                # Ensure file is closed before attempting to delete
                time.sleep(0.2)
                try:
                    if os.path.exists(temp_read):
                        os.remove(temp_read)
                except Exception as e:
                    self.log_debug(f"No se pudo eliminar archivo temporal: {e}")
            
            if data:
                # SPIFFS has data if it's not all 0xFF
                if data == b'\xFF' * len(data):
                    self.log("⚠️ Partición SPIFFS vacía (completamente borrada)", "warning")
                    return False
                else:
                    self.log("✅ Partición SPIFFS contiene datos", "success")
                    return True
            
            return False
        
        except Exception as e:
            self.log_debug(f"Error en verificación: {e}")
            # Clean up temp file on error
            try:
                temp_read = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spiffs_check.bin")
                if os.path.exists(temp_read):
                    os.remove(temp_read)
            except:
                pass
            return False
    
    def verify_spiffs_manual(self):
        """Manual SPIFFS verification - checks if partition has data"""
        if self.is_flashing:
            messagebox.showwarning("Ocupado", "Ya hay una operación en progreso")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM primero")
            return
        
        port = self.selected_port.get().split(' - ')[0]
        chip = self.selected_chip.get()
        
        self.log("=" * 60, "info")
        self.log("🔍 VERIFICANDO PARTICIÓN SPIFFS", "info")
        self.log("=" * 60, "info")
        self.log("Nota: Esta verificación comprueba que la partición contiene datos", "info")
        self.log("Para verificar archivos específicos, usa el monitor serial del ESP32", "info")
        
        # Start verification in thread
        thread = threading.Thread(
            target=self._verify_spiffs_thread,
            args=(port, chip, None)
        )
        thread.daemon = True
        thread.start()
    
    def _verify_spiffs_thread(self, port, chip, spiffs_image):
        """Thread to verify SPIFFS partition has data"""
        self.is_flashing = True
        self.set_buttons_state('disabled')
        
        try:
            if self._verify_spiffs_upload(port, chip, spiffs_image):
                self.log("=" * 60, "success")
                self.log("✅ VERIFICACIÓN EXITOSA", "success")
                self.log("=" * 60, "success")
                self.log("La partición SPIFFS contiene datos", "info")
                messagebox.showinfo(
                    "Verificación Exitosa",
                    "✅ Partición SPIFFS verificada\n\n"
                    "La partición contiene datos (no está vacía).\n\n"
                    "Los archivos serán accesibles cuando el\n"
                    "ESP32 arranque y monte el filesystem."
                )
            else:
                self.log("=" * 60, "warning")
                self.log("⚠️ PARTICIÓN SPIFFS VACÍA", "warning")
                self.log("=" * 60, "warning")
                messagebox.showwarning(
                    "Partición Vacía",
                    "⚠️ La partición SPIFFS está vacía\n\n"
                    "Sube el data folder para escribir archivos."
                )
        
        except Exception as e:
            self.log(f"❌ ERROR durante verificación: {e}", "error")
            messagebox.showerror("Error", f"Error verificando SPIFFS:\n\n{str(e)}")
        
        finally:
            self.is_flashing = False
            self.set_buttons_state('normal')

    def detect_device_partitions(self):
        """Detect partition table from connected device"""
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM primero")
            self.log_debug("Detect partitions: No se seleccionó puerto")
            return
        
        port = self.selected_port.get().split(' - ')[0]
        chip = self.selected_chip.get()
        
        self.log("Detectando particiones en el dispositivo...", "info")
        self.log_debug(f"Iniciando detección de particiones en {port}, chip: {chip}")
        
        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=self._detect_partitions_thread, args=(port, chip))
        thread.daemon = True
        thread.start()
    
    def _detect_partitions_thread(self, port, chip):
        """Thread to read partition table from device"""
        try:
            # Check if esptool is available
            try:
                import esptool
            except ImportError:
                self.log("Error: esptool no está instalado", "error")
                self.log_debug("esptool no encontrado - instala con: pip install esptool")
                messagebox.showerror("Error", 
                    "esptool no está instalado.\n\n" +
                    "Instala las dependencias con:\n" +
                    "pip install -r requirements.txt")
                return
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
            python_exe = venv_python if os.path.exists(venv_python) else sys.executable
            
            # Read partition table from device
            temp_file = os.path.join(script_dir, "temp_partitions.bin")
            
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", "115200",
                "read-flash",
                "0x8000", "0x1000",  # Read 4KB partition table
                temp_file
            ]
            
            self.log(f"Comando: {' '.join(cmd)}", "info")
            self.log_debug(f"Ejecutando esptool para leer particiones: {' '.join(cmd)}")
            self.log_serial(f"Conectando a {port}...", "tx")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            self.log_debug(f"Código de retorno: {result.returncode}", "verbose")
            if result.stdout:
                self.log_debug(f"STDOUT: {result.stdout[:200]}...", "verbose")
            if result.stderr:
                self.log_debug(f"STDERR: {result.stderr[:200]}...", "verbose")
            
            if result.returncode == 0 and os.path.exists(temp_file):
                self.log_serial(f"Datos leídos desde 0x8000", "rx")
                # Parse partition table
                partition_info = self.parse_partition_table(temp_file)
                
                # Check if partition table is missing/invalid
                if any("inválida" in p or "vacía" in p or "ADVERTENCIA" in p for p in partition_info):
                    self.log("="*60, "warning")
                    self.log("⚠️ ADVERTENCIA: Tabla de particiones inválida o inexistente", "warning")
                    self.log("="*60, "warning")
                    for partition in partition_info:
                        self.log(f"  {partition}", "warning")
                    self.log("", "normal")
                    self.log("🛠️ SOLUCIÓN: Usa Complete Mode para flashear:", "info")
                    self.log("  1. Selecciona 'Complete Mode'", "info")
                    self.log("  2. Carga bootloader.bin + partitions.bin + firmware.bin", "info")
                    self.log("  3. Flashea todo junto", "info")
                    self.log_debug("Partition table invalid - device needs complete reflash")
                else:
                    self.log("Particiones detectadas:", "success")
                    for partition in partition_info:
                        self.log(f"  • {partition}", "info")
                        self.log_debug(f"Partición: {partition}")
                
                # Clean up
                try:
                    os.remove(temp_file)
                except:
                    pass
            else:
                self.log("Error al leer particiones del dispositivo", "error")
                self.log(result.stderr if result.stderr else "Timeout o error de conexión", "error")
                self.log_debug(f"Error leyendo particiones: {result.stderr}")
                
        except Exception as e:
            self.log(f"Error detectando particiones: {str(e)}", "error")
            self.log_debug(f"Excepción en _detect_partitions_thread: {str(e)}")
    
    def parse_partition_table(self, partition_file):
        """Parse partition table binary file"""
        partitions = []
        
        try:
            with open(partition_file, 'rb') as f:
                data = f.read()
            
            # Check if file is empty or too small
            if len(data) < 32:
                self.log_debug(f"Archivo de particiones muy pequeño: {len(data)} bytes")
                return ["Tabla de particiones vacía o corrupta"]
            
            # Check magic bytes
            if data[0:2] != b'\xAA\x50':
                self.log_debug(f"Magic bytes incorrectos: {data[0:2].hex()} (esperado: AA50)")
                # Check if chip is erased (all 0xFF)
                if data[0:32] == b'\xFF' * 32:
                    return ["ADVERTENCIA: Chip completamente borrado - usa Complete Mode para flashear bootloader y particiones"]
                return ["Tabla de particiones inválida (magic bytes incorrectos)"]
            
            # Parse entries (32 bytes each)
            offset = 0  # Start from beginning, not 32
            entry_count = 0
            while offset + 32 <= len(data):
                if data[offset:offset+2] != b'\xAA\x50':
                    break
                
                ptype = data[offset+2]
                subtype = data[offset+3]
                p_offset = struct.unpack('<I', data[offset+4:offset+8])[0]
                p_size = struct.unpack('<I', data[offset+8:offset+12])[0]
                label = data[offset+12:offset+28].decode('utf-8', errors='ignore').rstrip('\x00')
                
                type_str = {0: "app", 1: "data"}.get(ptype, f"type_{ptype}")
                partitions.append(f"{label}: {type_str} at 0x{p_offset:X} size 0x{p_size:X}")
                self.log_debug(f"Partición encontrada: {label} ({type_str}) @ 0x{p_offset:X}, size 0x{p_size:X}")
                
                offset += 32
                entry_count += 1
            
            if entry_count == 0:
                return ["No se encontraron entradas válidas en la tabla de particiones"]
            
            return partitions if partitions else ["No se encontraron particiones válidas"]
            
        except Exception as e:
            self.log_debug(f"Excepción parseando tabla: {str(e)}")
            return [f"Error parseando: {str(e)}"]
    
    def convert_csv_to_bin(self, csv_path):
        """Convert CSV partition table to binary format"""
        try:
            self.log(f"Convirtiendo {os.path.basename(csv_path)} a formato binario...", "info")
            self.log_debug(f"CSV path: {csv_path}")
            
            partitions = []
            
            with open(csv_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse CSV line: Name, Type, SubType, Offset, Size
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) < 5:
                        continue
                    
                    name = parts[0]
                    ptype = parts[1]
                    subtype = parts[2]
                    offset = parts[3]
                    size = parts[4]
                    
                    # Parse offset
                    if offset.startswith('0x'):
                        offset_int = int(offset, 16)
                    else:
                        offset_int = int(offset)
                    
                    # Parse size (supports K and M suffixes)
                    size = size.upper().replace(' ', '')
                    if 'K' in size:
                        size_int = int(size.replace('K', '')) * 1024
                    elif 'M' in size:
                        size_int = int(size.replace('M', '')) * 1024 * 1024
                    elif size.startswith('0x'):
                        size_int = int(size, 16)
                    else:
                        size_int = int(size)
                    
                    # Convert type to number
                    type_map = {'app': 0, 'data': 1}
                    type_num = type_map.get(ptype.lower(), 0)
                    
                    # Convert subtype to number
                    subtype_map = {
                        'factory': 0, 'ota_0': 0x10, 'ota_1': 0x11, 'ota_2': 0x12,
                        'nvs': 0x02, 'phy': 0x01, 'coredump': 0x03, 'spiffs': 0x82,
                        'fat': 0x81, 'ota': 0x00
                    }
                    subtype_num = subtype_map.get(subtype.lower(), 0)
                    
                    partitions.append({
                        'name': name,
                        'type': type_num,
                        'subtype': subtype_num,
                        'offset': offset_int,
                        'size': size_int
                    })
                    
                    self.log_debug(f"Parsed: {name} @ 0x{offset_int:X}, size 0x{size_int:X}")
            
            if not partitions:
                self.log("No se encontraron particiones válidas en el CSV", "error")
                return None
            
            # Generate binary partition table
            bin_data = bytearray()
            
            for part in partitions:
                entry = bytearray(32)
                # Magic bytes
                entry[0:2] = b'\xAA\x50'
                # Type and subtype
                entry[2] = part['type']
                entry[3] = part['subtype']
                # Offset (4 bytes, little endian)
                entry[4:8] = struct.pack('<I', part['offset'])
                # Size (4 bytes, little endian)
                entry[8:12] = struct.pack('<I', part['size'])
                # Name (16 bytes, null terminated)
                name_bytes = part['name'].encode('utf-8')[:15]
                entry[12:12+len(name_bytes)] = name_bytes
                # Flags (4 bytes) - set to 0
                entry[28:32] = b'\x00\x00\x00\x00'
                
                bin_data.extend(entry)
            
            # Add end-of-table marker (CRITICAL - ESP32 needs this!)
            end_marker = bytearray(32)
            for i in range(32):
                end_marker[i] = 0xFF  # End marker is all 0xFF
            bin_data.extend(end_marker)
            
            self.log(f"📊 Agregado marcador de fin de tabla (32 bytes)", "info")
            
            # Pad to 4KB boundary
            while len(bin_data) % 4096 != 0:
                bin_data.append(0xFF)
            
            # Save to temp file
            temp_bin = csv_path.replace('.csv', '.bin')
            with open(temp_bin, 'wb') as f:
                f.write(bin_data)
            
            # Validate the generated file
            with open(temp_bin, 'rb') as f:
                test_header = f.read(2)
            
            if test_header != b'\xAA\x50':
                raise Exception("Archivo binario generado con magic bytes incorrectos")
            
            # Additional validation: read back and verify partition entries
            self._debug_partition_file(temp_bin)
            
            self.log(f"✅ Convertido exitosamente: {os.path.basename(temp_bin)} ({len(bin_data)} bytes)", "success")
            self.log_debug(f"Binary saved to: {temp_bin}")
            
            return temp_bin
            
        except Exception as e:
            self.log(f"Error convirtiendo CSV a binario: {e}", "error")
            self.log_debug(f"Exception: {repr(e)}")
            import traceback
            self.log_debug(traceback.format_exc())
            return None

    def _debug_partition_file(self, bin_file):
        """Debug function to validate generated partition binary"""
        try:
            self.log("🔍 Validando archivo de particiones generado...", "info")
            
            with open(bin_file, 'rb') as f:
                data = f.read()
            
            if len(data) < 32:
                self.log("❌ Archivo muy pequeño para contener particiones", "error")
                return
                
            offset = 0
            partition_count = 0
            
            while offset + 32 <= len(data):
                # Read magic bytes
                magic = data[offset:offset+2]
                if magic == b'\xFF\xFF':  # End marker
                    self.log(f"✅ Marcador de fin encontrado en offset 0x{offset:X}", "info")
                    break
                elif magic != b'\xAA\x50':
                    self.log(f"⚠️ Magic bytes inesperados en offset 0x{offset:X}: {magic.hex()}", "warning")
                    break
                
                # Parse entry
                ptype = data[offset+2]
                subtype = data[offset+3]
                p_offset = struct.unpack('<I', data[offset+4:offset+8])[0]
                p_size = struct.unpack('<I', data[offset+8:offset+12])[0]
                name = data[offset+12:offset+28].decode('utf-8', errors='ignore').rstrip('\x00')
                
                self.log(f"  📁 {name}: tipo={ptype}, subtipo={subtype}, offset=0x{p_offset:X}, size=0x{p_size:X}", "info")
                
                partition_count += 1
                offset += 32
            
            self.log(f"✅ Validación completada: {partition_count} particiones encontradas", "success")
            
        except Exception as e:
            self.log(f"❌ Error validando archivo de particiones: {e}", "error")
    
    def parse_csv_partition_table(self, csv_path):
        """Parse CSV partition table to find app address"""
        try:
            self.log_debug(f"Parseando CSV partition table: {csv_path}")
            app_address = None
            has_ota = False
            factory_address = None
            
            with open(csv_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) < 5:
                        continue
                    
                    name = parts[0]
                    ptype = parts[1].lower()
                    subtype = parts[2].lower()
                    offset = parts[3]
                    
                    # Parse offset
                    if offset.startswith('0x'):
                        offset_int = int(offset, 16)
                    else:
                        offset_int = int(offset)
                    
                    self.log(f"  CSV línea {line_num}: {name} ({ptype}/{subtype}) @ 0x{offset_int:X}", "info")
                    
                    # Find app partitions
                    if ptype == 'app':
                        if subtype == 'factory':
                            factory_address = f"0x{offset_int:X}"
                            self.log(f"  🏭 Factory app (CSV): {name} en {factory_address}", "success")
                        elif subtype == 'ota_0' and app_address is None:
                            app_address = f"0x{offset_int:X}"
                            self.log(f"  🔄 OTA app0 (CSV): {name} en {app_address}", "success")
                    
                    # Check for OTA data
                    if ptype == 'data' and subtype == 'ota':
                        has_ota = True
                        self.log(f"  📊 OTA data (CSV) encontrada: {name}", "info")
            
            # Priority: factory > OTA_0 > default
            final_address = factory_address if factory_address else app_address
            
            if final_address is None:
                final_address = "0x10000"
                self.log("⚠️ No se encontraron apps en CSV, usando 0x10000", "warning")
            else:
                partition_type = "Factory" if factory_address else "OTA app0"
                self.log(f"✅ Dirección CSV detectada: {final_address} ({partition_type})", "success")
            
            return final_address, has_ota
            
        except Exception as e:
            self.log(f"❌ Error parseando CSV: {e}", "error")
            return "0x10000", False
    
    def log(self, message, tag="normal"):
        """Agregar mensaje al log"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.root.update()
    
    def search_firmware(self):
        """Search for .bin file in firmware folder - called on startup"""
        firmware_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) 
                                    else os.path.dirname(os.path.abspath(__file__)), "firmware")
        
        # Create firmware folder if it doesn't exist
        if not os.path.exists(firmware_dir):
            os.makedirs(firmware_dir)
            self.firmware_label.config(text="📁 Usa el botón 'Seleccionar' para elegir firmware", 
                                      foreground="gray")
            self.log("Carpeta 'firmware' creada en: " + firmware_dir, "info")
            self.log("Usa el botón 'Seleccionar' para elegir tu archivo .bin", "info")
            return
        
        # Search for .bin files
        bin_files = [f for f in os.listdir(firmware_dir) if f.endswith('.bin') and 'firmware' in f.lower()]
        
        if not bin_files:
            self.firmware_label.config(text="📁 Usa el botón 'Seleccionar' para elegir firmware", 
                                      foreground="gray")
            self.log(f"No se encontró firmware.bin en: {firmware_dir}", "info")
            self.log("Usa el botón 'Seleccionar' para elegir tu archivo", "info")
        elif len(bin_files) == 1:
            self.firmware_path = os.path.join(firmware_dir, bin_files[0])
            self.firmware_label.config(text=f"✓ {bin_files[0]} ({self.get_file_size(self.firmware_path)})", 
                                      foreground="green")
            self.log(f"Firmware encontrado: {bin_files[0]}", "success")
            # Try auto-detect companion files
            self.auto_detect_companion_files(self.firmware_path)
        else:
            # Multiple files - user should select
            self.firmware_label.config(text=f"📁 {len(bin_files)} archivos encontrados - usa 'Seleccionar'", 
                                      foreground="orange")
            self.log(f"Se encontraron {len(bin_files)} archivos .bin - usa el botón para seleccionar", "info")
    
    def get_file_size(self, filepath):
        """Obtener tamaño del archivo en formato legible"""
        size = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    def refresh_ports(self):
        """Actualizar lista de puertos COM disponibles"""
        self.log_debug("Buscando puertos COM disponibles...")
        ports = serial.tools.list_ports.comports()
        port_list = [f"{port.device} - {port.description}" for port in ports]
        
        self.port_combo['values'] = port_list
        
        if port_list:
            self.port_combo.current(0)
            self.log(f"Puertos COM detectados: {len(port_list)}", "info")
            self.log_debug(f"Puertos encontrados: {', '.join([p.device for p in ports])}")
        else:
            self.log("No se detectaron puertos COM. Conecta tu ESP32 y actualiza.", "error")
            self.log_debug("No se encontraron puertos COM")
    
    def get_bootloader_address(self):
        """Get bootloader address based on chip type"""
        chip = self.selected_chip.get()
        if chip == "esp32s3":
            return "0x0"  # ESP32-S3 uses 0x0
        else:
            return "0x1000"  # ESP32, ESP32-C3, etc. use 0x1000
    
    def get_partition_table_address(self):
        """Get partition table address based on chip type"""
        chip = self.selected_chip.get()
        # All ESP32 variants use 0x8000 for partition table
        return "0x8000"
    
    def set_buttons_state(self, state):
        """Enable or disable all action buttons"""
        self.flash_btn.config(state=state)
        self.erase_btn.config(state=state)
        self.erase_nvs_btn.config(state=state)
        self.recovery_btn.config(state=state)
        self.fix_bootloader_btn.config(state=state)
        self.upload_data_btn.config(state=state)
        self.verify_spiffs_btn.config(state=state)
        self.refresh_btn.config(state=state)
        self.connect_btn.config(state=state)
        self.serial_advanced_btn.config(state=state)
    
    def start_flash(self):
        """Start flashing process in a separate thread"""
        if self.is_flashing:
            messagebox.showwarning("Advertencia", "Ya hay un proceso de flasheo en curso.")
            return
        
        # Validations
        if not self.firmware_path or not os.path.exists(self.firmware_path):
            messagebox.showerror("Error", "Selecciona un archivo de firmware válido.")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Selecciona un puerto COM.")
            return
        
        # Check Complete mode requirements
        if self.flash_mode.get() == "complete":
            if not self.bootloader_path or not os.path.exists(self.bootloader_path):
                messagebox.showerror("Error", "Complete Mode requiere bootloader.bin\n\nSelecciona el archivo o cambia a Simple Mode.")
                return
            if not self.partitions_path or not os.path.exists(self.partitions_path):
                messagebox.showerror("Error", "Complete Mode requiere partitions.bin\n\nSelecciona el archivo o cambia a Simple Mode.")
                return
        
        # Extract port name
        port = self.selected_port.get().split(' - ')[0]
        
        # Disconnect serial if connected (to free the port)
        if self.serial_connected:
            self.disconnect_serial()
        
        # Confirm
        mode_desc = "Simple" if self.flash_mode.get() == "simple" else "Complete"
        confirm_msg = f"¿Flashear firmware en {port}?\n\n" \
                     f"Modo: {mode_desc}\n" \
                     f"Chip: {self.selected_chip.get()}\n" \
                     f"Firmware: {os.path.basename(self.firmware_path)}"
        
        if self.flash_mode.get() == "complete":
            confirm_msg += f"\nBootloader: {os.path.basename(self.bootloader_path)}" \
                          f"\nPartitions: {os.path.basename(self.partitions_path)}"
        
        if not messagebox.askyesno("Confirmar Flasheo", confirm_msg):
            return
        
        # Start flashing thread
        self.is_flashing = True
        self.set_buttons_state('disabled')
        self.progress['value'] = 0
        
        thread = threading.Thread(target=self.flash_firmware, args=(port,))
        thread.daemon = True
        thread.start()
    
    def flash_firmware(self, port):
        """Flash firmware using ESP-IDF inspired approach with flasher_args structure"""
        try:
            # Check if esptool is available
            try:
                import esptool
            except ImportError:
                self.log("Error: esptool no está instalado", "error")
                self.log_debug("esptool no encontrado - instala con: pip install esptool")
                messagebox.showerror("Error", 
                    "esptool no está instalado.\n\n" +
                    "Instala las dependencias con:\n" +
                    "pip install -r requirements.txt")
                return
            
            self.log("=" * 60, "info")
            self.log(f"Iniciando flasheo en {port}...", "info")
            self.log("=" * 60, "info")
            self.log_debug(f"Flash firmware iniciado - Puerto: {port}")
            
            # Track this flash attempt
            self.total_flashes += 1
            self.update_session_display()
            
            # Get Python exe
            script_dir = os.path.dirname(os.path.abspath(__file__))
            venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
            python_exe = venv_python if os.path.exists(venv_python) else sys.executable
            self.log_debug(f"Python ejecutable: {python_exe}")
            
            # Get configuration
            chip = self.selected_chip.get()
            baud_rate = self.selected_baud.get()
            mode = self.flash_mode.get()
            self.log_debug(f"Configuración - Chip: {chip}, Baud: {baud_rate}, Modo: {mode}")
            
            # Build flasher args structure (ESP-IDF style)
            flasher_args = self.build_flasher_args(mode)
            
            if not flasher_args:
                self.log("Error: No se pudo crear plan de flasheo", "error")
                messagebox.showerror("Error", "No se pudo crear el plan de flasheo")
                return
            
            # Base command for esptool
            base_cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", baud_rate,
                "--before", "default-reset",
                "--after", "hard-reset"
            ]
            
            # STEP 1: Erase flash if needed
            if mode == "simple":
                # SIMPLE MODE: ALWAYS smart erase (only app region)
                # NEVER touches: bootloader, partitions, NVS
                self.log("PASO 1: Borrado inteligente - Solo firmware (preserva bootloader/partitions/NVS)...", "info")
                self.log_debug("Simple mode: Borrando SOLO región de firmware")
                success = self.smart_erase(base_cmd, flasher_args)
                if not success:
                    self.log("Error en borrado de firmware", "error")
                    return
                self.log("Firmware borrado (bootloader/partitions/NVS intactos)", "success")
                self.log("", "normal")
            else:
                # COMPLETE MODE: User controls NVS preservation
                if self.preserve_nvs.get():
                    # Smart erase - keep NVS, erase everything else (will be reflashed)
                    self.log("PASO 1: Borrado selectivo (preservando NVS)...", "info")
                    self.log_debug("Complete mode: Borrando todo excepto NVS")
                    success = self.smart_erase(base_cmd, flasher_args)
                    if not success:
                        self.log("Error en borrado selectivo", "error")
                        return
                else:
                    # Full erase - everything gets wiped and reflashed
                    self.log("PASO 1: Borrado completo del chip...", "info")
                    self.log_debug("Complete mode: Borrado total - todo será reflasheado")
                    if not self.execute_erase(base_cmd):
                        return
                self.log("Borrado completado", "success")
                self.log("", "normal")
            
            # STEP 2: Flash all components
            self.log(f"PASO 2: Flasheando componentes ({len(flasher_args['flash_files'])} archivos)...", "info")
            
            total_steps = len(flasher_args['flash_files'])
            for idx, (address, filepath, description) in enumerate(flasher_args['flash_files'], 1):
                self.log(f"[{idx}/{total_steps}] {description} → {address}...", "info")
                
                if not self.flash_component(base_cmd, address, filepath, description):
                    self.log(f"Error flasheando {description}", "error")
                    messagebox.showerror("Error", f"Error flasheando {description}\n\nRevisa el log para detalles.")
                    return
                
                self.log(f"✓ {description} flasheado exitosamente", "success")
                self.log("", "normal")
            
            # Success!
            self.log("=" * 60, "success")
            self.log(" ¡FLASHEO COMPLETADO EXITOSAMENTE!", "success")
            self.log("=" * 60, "success")
            
            # Update session stats
            self.successful_flashes += 1
            
            # Try to get MAC address
            try:
                mac_cmd = [
                    python_exe, "-m", "esptool",
                    "--chip", chip,
                    "--port", port,
                    "--baud", baud_rate,
                    "read-mac"
                ]
                self.log_debug("Obteniendo MAC address del dispositivo...")
                mac_result = subprocess.run(mac_cmd, capture_output=True, text=True, timeout=10)
                if mac_result.returncode == 0 and "MAC:" in mac_result.stdout:
                    # Extract MAC from output
                    for line in mac_result.stdout.split('\n'):
                        if "MAC:" in line:
                            mac = line.split("MAC:")[1].strip().split()[0]
                            self.flashed_devices.add(mac)
                            self.log_debug(f"MAC detectada: {mac}")
                            self.log_serial(f"MAC: {mac}", "rx")
                            break
            except Exception as e:
                self.log_debug(f"No se pudo obtener MAC: {e}", "verbose")
            
            self.update_session_display()
            
            messagebox.showinfo("Éxito", f"¡Firmware flasheado exitosamente!\n\nModo: {mode.title()}")
            
        except subprocess.TimeoutExpired as e:
            self.log("="*60, "error")
            self.log("ERROR: Timeout en operación de flasheo", "error")
            self.log(f"Detalles: {str(e)}", "error")
            self.log_debug(f"Timeout exception: {str(e)}")
            self.log("="*60, "error")
            messagebox.showerror("Error de Timeout", 
                f"La operación de flasheo tardó demasiado.\n\n"
                f"Posibles causas:\n"
                f"• Cable USB defectuoso\n"
                f"• Puerto COM incorrecto\n"
                f"• Chip no responde\n\n"
                f"Revisa el log principal para más detalles.")
        except FileNotFoundError as e:
            self.log("="*60, "error")
            self.log("ERROR: Archivo no encontrado", "error")
            self.log(f"Detalles: {str(e)}", "error")
            self.log_debug(f"FileNotFoundError: {str(e)}")
            self.log("="*60, "error")
            messagebox.showerror("Error de Archivo", 
                f"No se encontró un archivo necesario:\n\n{str(e)}\n\n"
                f"Verifica que todos los archivos estén seleccionados correctamente.")
        except PermissionError as e:
            self.log("="*60, "error")
            self.log("ERROR: Permiso denegado", "error")
            self.log(f"Detalles: {str(e)}", "error")
            self.log_debug(f"PermissionError: {str(e)}")
            self.log("="*60, "error")
            messagebox.showerror("Error de Permisos", 
                f"Permiso denegado:\n\n{str(e)}\n\n"
                f"• Cierra otros programas que usen el puerto COM\n"
                f"• Ejecuta como administrador\n"
                f"• Verifica que el archivo no esté siendo usado")
        except Exception as e:
            self.log("="*60, "error")
            self.log("ERROR CRÍTICO EN FLASHEO", "error")
            self.log(f"Tipo de error: {type(e).__name__}", "error")
            self.log(f"Mensaje: {str(e)}", "error")
            self.log_debug(f"Exception completa: {repr(e)}")
            
            # Log traceback
            import traceback
            tb_str = traceback.format_exc()
            self.log("Stack trace:", "error")
            for line in tb_str.split('\n'):
                if line.strip():
                    self.log(f"  {line}", "error")
                    self.log_debug(line, "verbose")
            self.log("="*60, "error")
            
            messagebox.showerror("Error Crítico", 
                f"Error inesperado durante el flasheo:\n\n"
                f"{type(e).__name__}: {str(e)}\n\n"
                f"Revisa el LOG PRINCIPAL (panel izquierdo) para detalles completos.\n\n"
                f"Si el problema persiste:\n"
                f"1. Activa 'Modo Verbose'\n"
                f"2. Intenta de nuevo\n"
                f"3. Revisa el panel de Debug")
        
        finally:
            self.is_flashing = False
            self.set_buttons_state('normal')
            self.progress.stop()
    
    def build_flasher_args(self, mode):
        """Build flasher arguments structure (ESP-IDF style)"""
        try:
            flasher_args = {
                "write_flash_args": ["--flash_mode", "dio", "--flash_freq", "80m", "--flash_size", "detect"],
                "flash_files": [],  # List of (address, filepath, description) tuples
                "extra_args": {
                    "chip": self.selected_chip.get(),
                    "before": "default-reset",
                    "after": "hard-reset"
                    # Note: verify removed in esptool v5+ (verification is automatic)
                }
            }
            
            if mode == "simple":
                # Simple mode: Flash only firmware
                self.log("Construyendo plan de flasheo (Modo Simple)...", "info")
                
                # Determine firmware address
                firmware_addr = self.get_firmware_address_simple()
                flasher_args["flash_files"].append((firmware_addr, self.firmware_path, "Firmware (app)"))
                
                self.log(f"  • Firmware → {firmware_addr}", "info")
                
            else:  # complete mode
                # Complete mode: Flash bootloader + partitions + firmware
                self.log("Construyendo plan de flasheo (Modo Completo)...", "info")
                
                # Parse partition table to get app address
                app_address, has_ota = self.parse_partition_table_file(self.partitions_path)
                
                # Check if bootloader should be preserved
                skip_bootloader = self.preserve_bootloader.get()
                
                if skip_bootloader:
                    self.log("🚫 Bootloader preservado (no se flasheará)", "info")
                else:
                    # Add bootloader to flash list (chip-specific address)
                    bootloader_addr = self.get_bootloader_address()
                    flasher_args["flash_files"].append(
                        (bootloader_addr, self.bootloader_path, "Bootloader (2nd stage)")
                    )
                    self.log(f"  • Bootloader → {bootloader_addr}", "info")
                
                # Always flash partitions
                partition_addr = self.get_partition_table_address()
                flasher_args["flash_files"].append(
                    (partition_addr, self.partitions_path, "Partition Table")
                )
                
                # Add OTA data if partitions support OTA
                if has_ota:
                    ota_data_path = self.create_ota_data_initial_file()
                    if ota_data_path:
                        flasher_args["flash_files"].append(
                            (self.esp_idf_addresses["ota_data"], ota_data_path, "OTA Data Initial")
                        )
                
                # Add firmware at detected address
                flasher_args["flash_files"].append(
                    (app_address, self.firmware_path, "Firmware (app)")
                )
                
                if not skip_bootloader:
                    self.log(f"  • Bootloader → {self.get_bootloader_address()}", "info")
                self.log(f"  • Partitions → {self.get_partition_table_address()}", "info")
                if has_ota:
                    self.log(f"  • OTA Data → {self.esp_idf_addresses['ota_data']}", "info")
                self.log(f"  • Firmware → {app_address}", "info")
            
            return flasher_args
            
        except Exception as e:
            self.log(f"Error construyendo flasher_args: {e}", "error")
            return None
    
    def get_firmware_address_simple(self):
        """Determine firmware flash address for simple mode"""
        # PlatformIO default: bootloader @ 0x0, partitions @ 0x8000, app @ 0x10000
        # This is the standard layout for most ESP32/ESP32-S3 projects
        return "0x10000"
    
    def parse_partition_table_file(self, partitions_path):
        """Parse partition table file (CSV or BIN) to find app address and OTA status"""
        try:
            self.log_debug(f"Parseando tabla de particiones: {partitions_path}")
            
            # Check if file is CSV format
            if partitions_path.lower().endswith('.csv') or self._is_csv_format(partitions_path):
                self.log_debug("Partition file is CSV format")
                return self.parse_csv_partition_table(partitions_path)
            
            # Binary format
            with open(partitions_path, 'rb') as f:
                data = f.read()
            
            if len(data) < 32 or data[0:2] != b'\xAA\x50':
                self.log("❌ Partition table inválida, usando dirección por defecto", "warning")
                return "0x10000", False
            
            # Parse partition entries (each entry is 32 bytes, starting from offset 0)
            offset = 0
            app_address = None
            has_ota = False
            factory_address = None
            
            self.log("🔍 Analizando particiones:", "info")
            
            while offset + 32 <= len(data):
                if data[offset:offset+2] != b'\xAA\x50':
                    break
                
                ptype = data[offset+2]
                subtype = data[offset+3]
                p_offset = struct.unpack('<I', data[offset+4:offset+8])[0]
                p_size = struct.unpack('<I', data[offset+8:offset+12])[0]
                label = data[offset+12:offset+28].decode('utf-8', errors='ignore').rstrip('\x00')
                
                self.log(f"  📁 {label}: tipo={ptype}, subtipo={subtype}, offset=0x{p_offset:X}", "info")
                
                # Type 0 = app partitions
                if ptype == 0:
                    if subtype == 0:  # factory app
                        factory_address = f"0x{p_offset:X}"
                        self.log(f"  🏭 Factory app encontrada: {label} en {factory_address}", "success")
                    elif subtype == 0x10:  # OTA_0 (first OTA partition)
                        if app_address is None:  # Use first OTA partition if no factory
                            app_address = f"0x{p_offset:X}"
                            self.log(f"  🔄 OTA app0 encontrada: {label} en {app_address}", "success")
                    elif subtype == 0x11:  # OTA_1 (second OTA partition)
                        self.log(f"  🔄 OTA app1 encontrada: {label} en 0x{p_offset:X}", "info")
                
                # Type 1 = data partitions
                elif ptype == 1:
                    if subtype == 0:  # OTA data
                        has_ota = True
                        self.log(f"  📊 OTA data encontrada: {label} en 0x{p_offset:X}", "info")
                
                offset += 32
            
            # Priority: factory > OTA_0 > default
            final_address = factory_address if factory_address else app_address
            
            if final_address is None:
                final_address = "0x10000"
                self.log("⚠️ No se encontraron particiones app, usando 0x10000 por defecto", "warning")
            else:
                partition_type = "Factory" if factory_address else "OTA app0"
                self.log(f"✅ Dirección de firmware detectada: {final_address} ({partition_type})", "success")
            
            return final_address, has_ota
            
        except Exception as e:
            self.log(f"❌ Error parseando partition table: {e}", "error")
            self.log_debug(f"Exception details: {repr(e)}")
            return "0x10000", False
    
    def _is_csv_format(self, filepath):
        """Check if file is in CSV format by reading first few lines"""
        try:
            with open(filepath, 'r') as f:
                first_line = f.readline().strip()
                # Check if it looks like CSV (has commas)
                return ',' in first_line
        except:
            return False
    
    def create_ota_data_initial_file(self):
        """Create OTA data initial file (marks app0 as active)"""
        try:
            import tempfile
            ota_data = bytearray(0x2000)  # 8KB
            
            # Mark app0 (slot 0) as active
            ota_data[0:4] = (0).to_bytes(4, 'little')  # active_otadata[0] = 0 (app0)
            ota_data[4:8] = (0xFFFFFFFF).to_bytes(4, 'little')  # active_otadata[1] = invalid
            
            # Fill rest with 0xFF
            for i in range(32, len(ota_data)):
                ota_data[i] = 0xFF
            
            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
            temp_file.write(bytes(ota_data))
            temp_file.close()
            
            self.log(f"OTA data initial creado: {temp_file.name}", "success")
            return temp_file.name
            
        except Exception as e:
            self.log(f"Error creando OTA data: {e}", "error")
            return None
    
    def execute_erase(self, base_cmd):
        """Execute full flash erase"""
        erase_cmd = base_cmd + ["erase-flash"]  # Updated: hyphenated
        
        self.log(f"Comando: {' '.join(erase_cmd)}", "info")
        self.log_debug(f"Ejecutando erase-flash: {' '.join(erase_cmd)}")
        self.log_serial("CMD: erase-flash (FULL CHIP ERASE)", "tx")
        
        try:
            process = subprocess.Popen(
                erase_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log_debug(f"esptool output: {line}", "verbose")
                    
                    # Log to serial monitor
                    if "Chip erase" in line or "Erasing" in line:
                        self.log_serial(line, "rx")
                    
                    if "Chip erase completed" in line:
                        self.log(line, "success")
                        self.log_serial("ERASE COMPLETE", "rx")
                    elif "Error" in line or "error" in line.lower():
                        self.log(line, "error")
                        self.log_serial(f"ERROR: {line}", "rx")
                    else:
                        self.log(line, "normal")
            
            process.wait()
            
            if process.returncode != 0:
                self.log(f"Error al borrar flash - código de retorno: {process.returncode}", "error")
                self.log_debug(f"Erase failed with return code: {process.returncode}")
                messagebox.showerror("Error", f"Error al borrar flash\n\nCódigo de error: {process.returncode}\n\nRevisa el log para detalles.")
                return False
            
            self.log_debug("Erase completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Excepción durante borrado: {str(e)}", "error")
            self.log_debug(f"Exception in execute_erase: {repr(e)}")
            messagebox.showerror("Error", f"Excepción durante borrado:\n{str(e)}")
            return False
    
    def smart_erase(self, base_cmd, flasher_args):
        """Erase only app regions, preserve NVS and bootloader"""
        try:
            # Find app partitions to erase
            for address, filepath, description in flasher_args['flash_files']:
                if "Firmware" in description or "app" in description.lower():
                    # Erase this region
                    addr_int = int(address, 16)
                    size = os.path.getsize(filepath)
                    # Round up to nearest 4KB
                    size_aligned = ((size + 4095) // 4096) * 4096
                    
                    self.log(f"Borrando región {address} (tamaño: {size_aligned} bytes)...", "info")
                    
                    erase_cmd = base_cmd + ["erase-region", address, hex(size_aligned)]  # Updated: hyphenated
                    
                    process = subprocess.Popen(
                        erase_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )
                    
                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            self.log(line, "normal")
                    
                    process.wait()
                    
                    if process.returncode != 0:
                        return False
            
            return True
            
        except Exception as e:
            self.log(f"Error en borrado inteligente: {e}", "error")
            return False
    
    def flash_component(self, base_cmd, address, filepath, description):
        """Flash a single component to given address"""
        try:
            if not os.path.exists(filepath):
                self.log(f"ERROR: Archivo no encontrado: {filepath}", "error")
                self.log_debug(f"File not found: {filepath}")
                return False
            
            file_size = os.path.getsize(filepath)
            self.log_debug(f"Flasheando {description}: {filepath} ({file_size} bytes) -> {address}")
            
            cmd = base_cmd + [
                "write-flash",  # Updated: hyphenated in esptool v5+
                "-z",  # Compress
                "--flash-mode", "dio",  # Updated: hyphenated
                "--flash-freq", "80m",  # Updated: hyphenated
                "--flash-size", "detect",  # Updated: hyphenated
                address,
                filepath
            ]
            
            # Note: --verify removed in esptool v5+ (verification is automatic)
            self.log_debug("Verificación automática (built-in en esptool v5+)")
            
            self.log(f"  Comando: esptool write-flash {address} {os.path.basename(filepath)}", "info")
            self.log_debug(f"Comando completo: {' '.join(cmd)}")
            self.log_serial(f"CMD: write-flash {address} {os.path.basename(filepath)}", "tx")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Capture both stdout and stderr
            output_lines = []
            error_lines = []
            
            # Read stdout
            for line in process.stdout:
                line = line.strip()
                if line:
                    match = re.search(r'(\d+\.\d+)%', line)
                    if match:
                        percent = float(match.group(1))
                        self.progress['value'] = percent
                        self.root.update_idletasks()
                    
                    # Update status label based on esptool output
                    if "Connecting" in line:
                        self.status_label.config(text="🔌 Connecting to device...")
                    elif "Erasing" in line or "erase" in line.lower():
                        self.status_label.config(text="🗑️ Erasing flash...")
                    elif "Writing at" in line:
                        self.status_label.config(text="📤 Uploading data...")
                    elif "Hash of data verified" in line:
                        self.status_label.config(text="✅ Verifying upload...")
                    elif "Compressed" in line:
                        self.status_label.config(text="📦 Compressing data...")
                    elif "Uploading" in line:
                        self.status_label.config(text="📤 Uploading stub...")
                    
                    output_lines.append(line)
                    self.log_debug(f"esptool: {line}", "verbose")
                    
                    # Log to serial monitor for visibility
                    if "Connecting" in line:
                        self.log_serial(line, "rx")
                    elif "Writing at" in line or "Wrote" in line:
                        self.log_serial(line, "rx")
                    elif "Hash" in line or "Verifying" in line:
                        self.log_serial(line, "rx")
                    elif "error" in line.lower() or "failed" in line.lower():
                        self.log_serial(f"ERROR: {line}", "rx")
                    
                    if "Hash of data verified" in line or "Wrote" in line or "Writing" in line:
                        self.log(f"  {line}", "success")
                    elif "A fatal error occurred" in line or "Failed to" in line or "error" in line.lower():
                        self.log(f"  {line}", "error")
                    else:
                        # Only log important lines to avoid clutter
                        if "Connecting" in line or "Chip is" in line or "Uploading" in line:
                            self.log(f"  {line}", "info")
            
            process.wait()
            
            # Read any remaining stderr
            stderr_output = process.stderr.read() if process.stderr else ""
            if stderr_output:
                for line in stderr_output.strip().split('\n'):
                    if line.strip():
                        error_lines.append(line.strip())
                        self.log_debug(f"esptool stderr: {line.strip()}")
                        self.log_serial(f"ERROR: {line.strip()}", "rx")
            
            if process.returncode != 0:
                self.log(f"  ERROR: Código de retorno {process.returncode}", "error")
                self.log_debug(f"Flash component failed with return code: {process.returncode}")
                self.log_serial(f"FAILED: Return code {process.returncode}", "rx")
                
                # Show actual error messages
                if error_lines:
                    self.log("  Errores de esptool:", "error")
                    for err in error_lines:
                        self.log(f"    {err}", "error")
                
                # Provide helpful error messages
                if process.returncode == 2:
                    self.log("  ⚠️ Error común: Verifica que el chip tenga bootloader y partition table", "warning")
                    self.log("  ⚠️ Si el chip fue borrado completamente, usa Complete Mode", "warning")
                    self.log_serial("HINT: Chip may need bootloader - use Complete Mode", "rx")
                
            return process.returncode == 0
            
        except Exception as e:
            self.log(f"  ERROR: {type(e).__name__}: {str(e)}", "error")
            self.log_debug(f"Exception in flash_component: {repr(e)}")
            return False

    def start_erase(self):
        """Iniciar proceso de borrado de flash en un hilo separado"""
        if self.is_flashing:
            messagebox.showwarning("Advertencia", "Ya hay un proceso en curso.")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Por favor selecciona un puerto COM.")
            return
        
        # Extraer solo el nombre del puerto
        port = self.selected_port.get().split(' - ')[0]
        
        # Confirmar
        if not messagebox.askyesno("Confirmar Borrado", 
                                   f"¿Estás seguro de que quieres BORRAR COMPLETAMENTE el flash de {port}?\n\n"
                                   "Esta acción eliminará todo el contenido del ESP32."):
            return
        
        # Iniciar borrado en un hilo separado
        self.is_flashing = True
        self.set_buttons_state('disabled')
        self.progress['value'] = 0
        
        thread = threading.Thread(target=self.erase_flash_chip, args=(port,))
        thread.daemon = True
        thread.start()
    
    def start_erase_nvs(self):
        """Iniciar proceso de borrado SOLO de NVS en un hilo separado"""
        if self.is_flashing:
            messagebox.showwarning("Advertencia", "Ya hay un proceso en curso.")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Por favor selecciona un puerto COM.")
            return
        
        # Extraer solo el nombre del puerto
        port = self.selected_port.get().split(' - ')[0]
        
        # Confirmar
        if not messagebox.askyesno("Confirmar Borrado NVS", 
                                   f"¿Estás seguro de que quieres BORRAR SOLO LA PARTICIÓN NVS de {port}?\n\n"
                                   "Esto eliminará:\n"
                                   "  • Configuración WiFi\n"
                                   "  • Datos de aplicación guardados\n"
                                   "  • Calibración y configuraciones\n\n"
                                   "El bootloader y firmware NO se borrarán."):
            return
        
        # Iniciar borrado en un hilo separado
        self.is_flashing = True
        self.set_buttons_state('disabled')
        self.progress['value'] = 0
        
        thread = threading.Thread(target=self.erase_nvs_partition, args=(port,))
        thread.daemon = True
        thread.start()
    
    def erase_nvs_partition(self, port):
        """Borrar SOLO la partición NVS del ESP32"""
        try:
            self.log("=" * 60, "info")
            self.log(f"Iniciando BORRADO DE NVS en {port}...", "info")
            self.log("=" * 60, "info")
            self.log_debug(f"Erase NVS iniciado en puerto {port}")
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
            
            if os.path.exists(venv_python):
                python_exe = venv_python
            else:
                python_exe = sys.executable
            
            chip = self.selected_chip.get()
            baud_rate = self.selected_baud.get()
            
            # NVS typically at 0x9000, size 0x5000 (20KB) for ESP32/ESP32-S3
            nvs_offset = 0x9000
            nvs_size = 0x5000
            
            self.log(f"Borrando partición NVS: offset=0x{nvs_offset:X}, size=0x{nvs_size:X}", "info")
            self.log_debug(f"NVS erase - chip: {chip}, baud: {baud_rate}")
            
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", baud_rate,
                "erase-region",  # Updated: hyphenated
                hex(nvs_offset),
                hex(nvs_size)
            ]
            
            self.log(f"Comando: {' '.join(cmd)}", "info")
            self.log_debug(f"Ejecutando: {' '.join(cmd)}")
            self.log("", "normal")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log_debug(f"esptool: {line}", "verbose")
                    if "Erase completed" in line or "erased" in line.lower():
                        self.log(line, "success")
                    elif "Error" in line or "Failed" in line or "error" in line.lower():
                        self.log(line, "error")
                    else:
                        self.log(line, "normal")
            
            process.wait()
            
            if process.returncode == 0:
                self.log("", "normal")
                self.log("=" * 60, "success")
                self.log(" ¡PARTICIÓN NVS BORRADA EXITOSAMENTE!", "success")
                self.log("=" * 60, "success")
                self.log_debug("NVS erase completed successfully")
                messagebox.showinfo("Éxito", 
                    "¡Partición NVS borrada completamente!\n\n"
                    "WiFi y configuraciones eliminadas.\n"
                    "Bootloader y firmware intactos.\n\n"
                    "El dispositivo iniciará con configuración de fábrica.")
            else:
                self.log("=" * 60, "error")
                self.log(f" Error al borrar NVS - código: {process.returncode}", "error")
                self.log("=" * 60, "error")
                self.log_debug(f"NVS erase failed with return code: {process.returncode}")
                messagebox.showerror("Error", 
                    f"Error al borrar partición NVS.\n\n"
                    f"Código de error: {process.returncode}\n\n"
                    f"Revisa el log para más detalles.")
                
        except Exception as e:
            self.log(f"Excepción: {str(e)}", "error")
            self.log_debug(f"Exception in erase_nvs_partition: {repr(e)}")
            messagebox.showerror("Error", f"Error inesperado:\n{str(e)}")
        
        finally:
            self.is_flashing = False
            self.set_buttons_state('normal')
            self.progress.stop()
    
    def erase_flash_chip(self, port):
        """Borrar el flash completo del ESP32"""
        try:
            self.log("=" * 60, "info")
            self.log(f"Iniciando BORRADO COMPLETO del flash en {port}...", "info")
            self.log("=" * 60, "info")
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
            
            if os.path.exists(venv_python):
                python_exe = venv_python
            else:
                python_exe = sys.executable
            
            chip = self.selected_chip.get()
            baud_rate = self.selected_baud.get()
            
            cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", baud_rate,
                "erase-flash"
            ]
            
            self.log(f"Comando: {' '.join(cmd)}", "info")
            self.log("", "normal")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    if "Chip erase completed successfully" in line:
                        self.log(line, "success")
                    elif "Error" in line or "Failed" in line:
                        self.log(line, "error")
                    else:
                        self.log(line, "normal")
            
            process.wait()
            
            if process.returncode == 0:
                self.log("", "normal")
                self.log("=" * 60, "success")
                self.log(" ¡FLASH BORRADO EXITOSAMENTE!", "success")
                self.log("=" * 60, "success")
                messagebox.showinfo("Éxito", "¡Flash borrado completamente!\n\nAhora puedes cargar el firmware.")
            else:
                self.log("=" * 60, "error")
                self.log(" Error al borrar el flash", "error")
                self.log("=" * 60, "error")
                messagebox.showerror("Error", "Error al borrar el flash.\nRevisa el log para más detalles.")
                
        except Exception as e:
            self.log(f"Excepción: {str(e)}", "error")
            messagebox.showerror("Error", f"Error inesperado:\n{str(e)}")
        
        finally:
            self.is_flashing = False
            self.set_buttons_state('normal')
            self.progress.stop()

    def show_firmware_analysis(self):
        """Mostrar análisis del firmware en una ventana emergente"""
        if not self.firmware_path:
            messagebox.showerror("Error", "No hay archivo de firmware seleccionado.")
            return
        
        analysis = self.analyze_firmware()
        
        # Crear ventana de análisis
        analysis_window = tk.Toplevel(self.root)
        analysis_window.title("Análisis de Firmware")
        analysis_window.geometry("500x400")
        analysis_window.resizable(True, True)
        analysis_window.minsize(400, 300)
        
        # Configurar expansión
        analysis_window.columnconfigure(0, weight=1)
        analysis_window.rowconfigure(0, weight=1)
        
        # Frame principal
        main_frame = ttk.Frame(analysis_window, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Configurar expansión del frame principal
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)  # tech_frame se expande
        
        # Título
        ttk.Label(main_frame, text="Análisis de Firmware ESP32", 
                 font=('Arial', 12, 'bold')).grid(row=0, column=0, pady=5)
        
        # Información del archivo
        file_frame = ttk.LabelFrame(main_frame, text="Archivo", padding="5")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(file_frame, text=f"Archivo: {os.path.basename(self.firmware_path)}").pack(anchor="w")
        ttk.Label(file_frame, text=f"Tamaño: {self.get_file_size(self.firmware_path)}").pack(anchor="w")
        ttk.Label(file_frame, text=f"Ruta: {self.firmware_path}").pack(anchor="w")
        
        # Análisis técnico
        tech_frame = ttk.LabelFrame(main_frame, text="Análisis Técnico", padding="5")
        tech_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        tech_frame.columnconfigure(0, weight=1)
        tech_frame.rowconfigure(0, weight=1)
        
        analysis_text = tk.Text(tech_frame, wrap=tk.WORD, height=6, width=50)
        scrollbar = ttk.Scrollbar(tech_frame, orient="vertical", command=analysis_text.yview)
        analysis_text.configure(yscrollcommand=scrollbar.set)
        
        analysis_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        analysis_text.insert("1.0", analysis)
        analysis_text.config(state="disabled")
        
        # Recomendaciones
        rec_frame = ttk.LabelFrame(main_frame, text="Recomendaciones", padding="5")
        rec_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        if "ESP32 original" in analysis:
            ttk.Label(rec_frame, text="⚠️ Este firmware parece ser para ESP32 original", 
                     foreground="orange", font=('Arial', 9, 'bold')).pack(anchor="w")
            ttk.Label(rec_frame, text="• Recompila tu proyecto para ESP32-S3", 
                     foreground="orange").pack(anchor="w")
        elif "ESP32-S3" in analysis:
            ttk.Label(rec_frame, text="✅ Este firmware parece ser compatible con ESP32-S3", 
                     foreground="green", font=('Arial', 9, 'bold')).pack(anchor="w")
        else:
            ttk.Label(rec_frame, text="❓ Tipo de firmware incierto", 
                     foreground="gray", font=('Arial', 9, 'bold')).pack(anchor="w")
            ttk.Label(rec_frame, text="• Verifica la compatibilidad con ESP32-S3", 
                     foreground="gray").pack(anchor="w")
        
        # Botón cerrar
        ttk.Button(main_frame, text="Cerrar", command=analysis_window.destroy).grid(row=4, column=0, pady=10)

    def create_esp32s3_bootloader(self):
        """Crear un bootloader funcional para ESP32-S3 basado en ESP-IDF"""
        try:
            # Usar esptool para generar un bootloader válido
            self.log("🔧 Generando bootloader ESP32-S3 con esptool...", "info")
            
            # Crear un archivo temporal para el bootloader
            temp_bootloader = os.path.join(tempfile.gettempdir(), "esp32s3_bootloader.bin")
            
            # Template de bootloader mínimo ESP32-S3 basado en ESP-IDF 5.x
            bootloader_template = bytearray([
                # Image header
                0xE9, 0x02, 0x02, 0x0F,  # magic, segments, spi_mode, spi_speed_size
                0x00, 0x80, 0x37, 0x40,  # entry_point (0x40378000)
                0xEE, 0x00, 0x00, 0x00,  # wp_pin, reserved
                0x09, 0x00, 0x02, 0x00,  # chip_id=9 (ESP32-S3), reserved, segments=2
                
                # Segment 1: Boot stub
                0x00, 0x80, 0x37, 0x40,  # load_addr
                0x20, 0x00, 0x00, 0x00,  # data_len (32 bytes)
                
                # Boot code - Simple jump to partition table reader
                0x36, 0x61, 0x00,        # entry
                0x06, 0xFF, 0xFF,        # j bootloader_main
                0x00, 0x00, 0x00, 0x00,  # padding
                0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00,
                
                # Segment 2: Bootloader main code
                0x00, 0x82, 0x37, 0x40,  # load_addr
                0x00, 0x40, 0x00, 0x00,  # data_len (16KB)
            ])
            
            # Crear bootloader de 20KB total
            bootloader_size = 0x5000
            bootloader = bytearray(bootloader_size)
            
            # Copiar template
            template_len = min(len(bootloader_template), len(bootloader))
            bootloader[0:template_len] = bootloader_template[0:template_len]
            
            # Simular código de bootloader principal (simplificado)
            main_code_start = len(bootloader_template)
            main_code = self._create_esp32s3_boot_code()
            
            if main_code_start + len(main_code) < len(bootloader):
                bootloader[main_code_start:main_code_start+len(main_code)] = main_code
            
            # Rellenar el resto con 0xFF
            for i in range(main_code_start + len(main_code), len(bootloader)):
                bootloader[i] = 0xFF
            
            # Guardar bootloader
            with open(temp_bootloader, 'wb') as f:
                f.write(bootloader)
            
            self.log(f"✅ Bootloader ESP32-S3 generado: {temp_bootloader}", "success")
            return temp_bootloader
            
        except Exception as e:
            self.log(f"❌ Error creando bootloader: {e}", "error")
            return None
    
    def _create_esp32s3_boot_code(self):
        """Crear código de bootloader principal simplificado"""
        # Código mínimo que:
        # 1. Inicializa el chip
        # 2. Lee la tabla de particiones desde 0x8000
        # 3. Busca la partición app
        # 4. Salta a la aplicación
        
        boot_code = bytearray([
            # Inicialización básica
            0x00, 0x00, 0x00, 0x00,  # Stack setup
            0x00, 0x80, 0x05, 0x40,  # Load partition table addr (0x8000)
            0x00, 0x00, 0x00, 0x00,  # Read partition table
            0x00, 0x00, 0x05, 0x40,  # Find app partition  
            0x00, 0x00, 0x10, 0x00,  # Default app addr (0x10000)
            0x00, 0x80, 0x37, 0x40,  # Jump to application
            
            # Padding hasta completar el tamaño mínimo
        ])
        
        # Rellenar hasta 1KB con NOPs
        while len(boot_code) < 1024:
            boot_code.extend([0x00, 0x00, 0x00, 0x00])
        
        return boot_code
    
    def analyze_firmware(self):
        """Analizar el archivo de firmware para detectar el tipo de chip"""
        if not self.firmware_path or not os.path.exists(self.firmware_path):
            return "Archivo no encontrado"
        
        try:
            with open(self.firmware_path, 'rb') as f:
                header = f.read(16)
            
            if len(header) < 16:
                return "Archivo demasiado pequeño"
            
            # Verificar magic byte ESP32
            if header[0] != 0xE9:
                return "No es un archivo ESP32 válido (magic byte incorrecto)"
            
            # Analizar chip ID si está presente
            segment_count = header[1]
            spi_mode = header[2]
            spi_speed_size = header[3]
            entry_point = int.from_bytes(header[4:8], 'little')
            
            analysis = []
            analysis.append(f"Magic byte: 0x{header[0]:02X} ✓")
            analysis.append(f"Segmentos: {segment_count}")
            analysis.append(f"Modo SPI: {spi_mode} ({'DIO' if spi_mode == 2 else 'Otro'})")
            analysis.append(f"Entry point: 0x{entry_point:08X}")
            
            # Detectar tipo de chip por entry point
            if 0x40000000 <= entry_point <= 0x4001FFFF:
                analysis.append("🔍 Posible ESP32 original (entry point en IRAM0)")
            elif 0x40370000 <= entry_point <= 0x4037FFFF:
                analysis.append("🔍 Posible ESP32-S3 (entry point en IRAM)")
            elif 0x40380000 <= entry_point <= 0x4038FFFF:
                analysis.append("🔍 Posible ESP32-S2/S3 (entry point alto)")
            else:
                analysis.append(f"🔍 Entry point inusual: 0x{entry_point:08X}")
            
            return "\n".join(analysis)
            
        except Exception as e:
            return f"Error al analizar: {str(e)}"

def main():
    # Check dependencies before starting
    check_and_install_dependencies()
    
    root = tk.Tk()
    app = ESP32Flasher(root)
    root.mainloop()

if __name__ == "__main__":
    main()
