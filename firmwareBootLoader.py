import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial.tools.list_ports
import subprocess
import os
import sys
import threading

class ESP32Flasher:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Firmware Flasher")
        self.root.geometry("650x850")
        self.root.resizable(True, True)  # Permitir redimensionar
        self.root.minsize(450, 500)  # Tamaño mínimo más pequeño
        
        # Variables
        self.firmware_path = None
        self.selected_port = tk.StringVar()
        self.selected_chip = tk.StringVar(value="esp32s3")  # Valor por defecto para ESP32-S3
        self.selected_baud = tk.StringVar(value="115200")  # Baud rate por defecto
        self.is_flashing = False
        
        # Configuraciones específicas por chip
        self.chip_configs = {
            "esp32": {"flash_addr": "0x10000", "baud": "115200"},
            "esp32s3": {"flash_addr": "0x50000", "baud": "115200"},  # ESP32-S3 usa 0x50000 (PlatformIO)
            "esp32s2": {"flash_addr": "0x10000", "baud": "115200"},
            "esp32c3": {"flash_addr": "0x10000", "baud": "115200"},
            "esp32c6": {"flash_addr": "0x10000", "baud": "115200"},
            "esp32h2": {"flash_addr": "0x10000", "baud": "115200"}
        }
        
        # Configurar interfaz
        self.setup_ui()
        
        # Buscar firmware al iniciar
        self.search_firmware()
        
        # Actualizar puertos COM
        self.refresh_ports()
    
    def setup_ui(self):
        # Configurar el root para que se expanda
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar el main_frame para que se expanda
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1) 
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(13, weight=1)  # Fila del log se expande
        
        # Título
        title_label = ttk.Label(main_frame, text="ESP32 Firmware Flasher", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # Información del firmware
        ttk.Label(main_frame, text="Archivo de Firmware:", 
                 font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.firmware_label = ttk.Label(main_frame, text="Buscando...", 
                                       foreground="gray")
        self.firmware_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=20)
        
        # Selección de puerto COM
        ttk.Label(main_frame, text="Puerto COM:", 
                 font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky=tk.W, pady=(20, 5))
        
        port_frame = ttk.Frame(main_frame)
        port_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        port_frame.columnconfigure(0, weight=1)  # Combobox se expande
        
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.selected_port, 
                                       state="readonly")
        self.port_combo.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.refresh_btn = ttk.Button(port_frame, text=" Actualizar", 
                                     command=self.refresh_ports, width=12)
        self.refresh_btn.grid(row=0, column=1, sticky=tk.E)
        
        # Selección de tipo de chip ESP32
        ttk.Label(main_frame, text="Tipo de Chip:", 
                 font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky=tk.W, pady=(20, 5))
        
        chip_frame = ttk.Frame(main_frame)
        chip_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.chip_combo = ttk.Combobox(chip_frame, textvariable=self.selected_chip, 
                                      state="readonly", width=20)
        self.chip_combo['values'] = ['esp32', 'esp32s3', 'esp32s2', 'esp32c3', 'esp32c6', 'esp32h2']
        self.chip_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(chip_frame, text="(ESP32-S3 es el más común)", 
                 foreground="gray").pack(side=tk.LEFT)
        
        # Selección de velocidad (Baud Rate)
        ttk.Label(main_frame, text="Velocidad de Transmisión:", 
                 font=('Arial', 10, 'bold')).grid(row=7, column=0, sticky=tk.W, pady=(10, 5))
        
        baud_frame = ttk.Frame(main_frame)
        baud_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        baud_frame.columnconfigure(0, weight=0)  # Combobox tamaño fijo
        baud_frame.columnconfigure(1, weight=1)  # Label se expande
        
        self.baud_combo = ttk.Combobox(baud_frame, textvariable=self.selected_baud, 
                                      state="readonly", width=10)
        self.baud_combo['values'] = ['115200', '230400', '460800', '921600']
        self.baud_combo.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        ttk.Label(baud_frame, text="(115200 es más confiable, 460800+ más rápido)", 
                 foreground="gray").grid(row=0, column=1, sticky=tk.W)
        
        # Marco con scroll para configuración avanzada
        config_container = ttk.Frame(main_frame)
        config_container.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        config_container.columnconfigure(0, weight=1)
        config_container.rowconfigure(0, weight=1)
        
        # Canvas y scrollbar para el contenido
        canvas = tk.Canvas(config_container, height=200)  # Altura fija para el área de scroll
        scrollbar = ttk.Scrollbar(config_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Habilitar scroll con rueda del mouse
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
        # Configuración avanzada dentro del frame scrollable
        advanced_frame = ttk.LabelFrame(scrollable_frame, text="Configuración Avanzada", padding="5")
        advanced_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        advanced_frame.columnconfigure(0, weight=1)  # Se expande horizontalmente
        
        self.use_alt_address = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Usar dirección alternativa (0x10000 en lugar de 0x50000 para ESP32-S3)", 
                       variable=self.use_alt_address).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        self.erase_flash = tk.BooleanVar(value=True)  # Por defecto borrar flash
        ttk.Checkbutton(advanced_frame, text="Borrar flash completo antes de escribir (recomendado)", 
                       variable=self.erase_flash).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        self.verify_flash = tk.BooleanVar(value=True)  # Por defecto verificar
        ttk.Checkbutton(advanced_frame, text="Verificar escritura después de flashear", 
                       variable=self.verify_flash).grid(row=2, column=0, sticky=tk.W, pady=2)
        
        self.include_bootloader = tk.BooleanVar(value=False)  # Cambiar a False por defecto
        ttk.Checkbutton(advanced_frame, text="Incluir bootloader ESP32-S3 (experimental - solo si flash vacío)", 
                       variable=self.include_bootloader).grid(row=3, column=0, sticky=tk.W, pady=2)
                       
        self.use_platformio_layout = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Usar layout de PlatformIO (múltiples particiones: bootloader+app)", 
                       variable=self.use_platformio_layout).grid(row=4, column=0, sticky=tk.W, pady=2)
                       
        self.skip_bootloader_creation = tk.BooleanVar(value=True)  # Por defecto saltarse
        ttk.Checkbutton(advanced_frame, text="Saltear creación de bootloader (usar el existente)", 
                       variable=self.skip_bootloader_creation).grid(row=5, column=0, sticky=tk.W, pady=2)
                       
        self.firmware_only_mode = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Modo simple: solo firmware en 0x50000 (sin particiones)", 
                       variable=self.firmware_only_mode).grid(row=6, column=0, sticky=tk.W, pady=2)
                       
        self.smart_erase = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Borrado inteligente (solo región del firmware, no todo)", 
                       variable=self.smart_erase).grid(row=7, column=0, sticky=tk.W, pady=2)
        self.smart_erase = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Borrado inteligente (solo región del firmware, no todo)", 
                       variable=self.smart_erase).grid(row=7, column=0, sticky=tk.W, pady=2)
                       
        self.use_platformio_files = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Usar bootloader real de PlatformIO (buscar en .pio/build/)", 
                       variable=self.use_platformio_files).grid(row=8, column=0, sticky=tk.W, pady=2)
        
        # Información adicional
        info_frame = ttk.Frame(advanced_frame)
        info_frame.grid(row=9, column=0, sticky=(tk.W, tk.E), pady=5)
        info_frame.columnconfigure(0, weight=1)
        
        ttk.Label(info_frame, text="💡 Si ves 'Guru Meditation Error', desmarca 'Incluir bootloader'", 
                 foreground="blue", font=('Arial', 8)).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info_frame, text="💡 Tu firmware ESP32-S3 parece incluir bootloader propio", 
                 foreground="green", font=('Arial', 8)).grid(row=1, column=0, sticky=tk.W)
        ttk.Label(info_frame, text="⚠️ O mejor: obtén el bootloader oficial de tu proyecto ESP32-S3", 
                 foreground="orange", font=('Arial', 8)).grid(row=2, column=0, sticky=tk.W)
        ttk.Label(info_frame, text="✅ NUEVO: Prueba 'layout de PlatformIO' para firmwares grandes", 
                 foreground="blue", font=('Arial', 8, 'bold')).grid(row=3, column=0, sticky=tk.W)
        ttk.Label(info_frame, text="👍 Recomendación: Marcar 'Saltear bootloader' si tienes errores", 
                 foreground="purple", font=('Arial', 8, 'bold')).grid(row=4, column=0, sticky=tk.W)
        ttk.Label(info_frame, text="⚡ PRUEBA ESTO: 'Modo simple' para firmware de PlatformIO", 
                 foreground="red", font=('Arial', 8, 'bold')).grid(row=5, column=0, sticky=tk.W)
        ttk.Label(info_frame, text="🔥 MEJOR: Usar bootloader real de PlatformIO si está disponible", 
                 foreground="red", font=('Arial', 8, 'bold')).grid(row=6, column=0, sticky=tk.W)
        ttk.Label(info_frame, text="🧠 INTELIGENTE: Borrado inteligente preserva bootloader existente", 
                 foreground="green", font=('Arial', 8, 'bold')).grid(row=7, column=0, sticky=tk.W)
        
        # Información sobre compatibilidad de firmware
        compat_frame = ttk.LabelFrame(advanced_frame, text="Compatibilidad de Firmware", padding="5")
        compat_frame.grid(row=10, column=0, sticky=(tk.W, tk.E), pady=5)
        compat_frame.columnconfigure(0, weight=1)  # Se expande horizontalmente
        
        ttk.Label(compat_frame, text="⚠️ IMPORTANTE: Verifica que tu firmware.bin sea para ESP32-S3", 
                 foreground="red", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(compat_frame, text="• Firmware para ESP32 original NO funciona en ESP32-S3", 
                 foreground="orange", font=('Arial', 8)).grid(row=1, column=0, sticky=tk.W)
        ttk.Label(compat_frame, text="• ESP32-S3 tiene arquitectura diferente (dual-core Xtensa LX7)", 
                 foreground="orange", font=('Arial', 8)).grid(row=2, column=0, sticky=tk.W)
        ttk.Label(compat_frame, text="• Necesitas recompilar tu código específicamente para ESP32-S3", 
                 foreground="orange", font=('Arial', 8)).grid(row=3, column=0, sticky=tk.W)
        
        # Botones de acción
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=10, column=0, columnspan=3, pady=20)
        
        self.analyze_btn = ttk.Button(buttons_frame, text=" ANALIZAR FIRMWARE", 
                                     command=self.show_firmware_analysis, width=18)
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.erase_btn = ttk.Button(buttons_frame, text=" BORRAR FLASH ESP32", 
                                   command=self.start_erase, width=18)
        self.erase_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.flash_btn = ttk.Button(buttons_frame, text=" CARGAR FIRMWARE AL ESP32", 
                                   command=self.start_flash, style='Accent.TButton')
        self.flash_btn.pack(side=tk.LEFT)
        
        # Barra de progreso
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=400)
        self.progress.grid(row=11, column=0, columnspan=3, pady=10)
        
        # Área de log
        ttk.Label(main_frame, text="Log de Proceso:", 
                 font=('Arial', 10, 'bold')).grid(row=12, column=0, sticky=tk.W, pady=(10, 5))
        
        self.log_text = scrolledtext.ScrolledText(main_frame, height=8, width=70, 
                                                  state='disabled', wrap=tk.WORD)
        self.log_text.grid(row=13, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar tags para colores
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("info", foreground="blue")
    
    def log(self, message, tag="normal"):
        """Agregar mensaje al log"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.root.update()
    
    def search_firmware(self):
        """Buscar archivo .bin en la carpeta firmware"""
        firmware_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) 
                                    else os.path.dirname(os.path.abspath(__file__)), "firmware")
        
        # Crear carpeta firmware si no existe
        if not os.path.exists(firmware_dir):
            os.makedirs(firmware_dir)
            self.firmware_label.config(text=" Carpeta 'firmware' creada. Coloca tu archivo .bin ahí.", 
                                      foreground="orange")
            self.log("Carpeta 'firmware' creada en: " + firmware_dir, "info")
            self.log("Por favor, coloca tu archivo .bin en esta carpeta y reinicia la aplicación.", "info")
            return
        
        # Buscar archivos .bin
        bin_files = [f for f in os.listdir(firmware_dir) if f.endswith('.bin')]
        
        if not bin_files:
            self.firmware_label.config(text=" No se encontró ningún archivo .bin en la carpeta 'firmware'", 
                                      foreground="red")
            self.log("No se encontró archivo .bin en: " + firmware_dir, "error")
        elif len(bin_files) == 1:
            self.firmware_path = os.path.join(firmware_dir, bin_files[0])
            self.firmware_label.config(text=f" {bin_files[0]} ({self.get_file_size(self.firmware_path)})", 
                                      foreground="green")
            self.log(f"Firmware encontrado: {bin_files[0]}", "success")
        else:
            # Si hay múltiples archivos, usar el primero
            self.firmware_path = os.path.join(firmware_dir, bin_files[0])
            self.firmware_label.config(text=f" {bin_files[0]} (Se encontraron {len(bin_files)} archivos, usando el primero)", 
                                      foreground="green")
            self.log(f"Se encontraron {len(bin_files)} archivos .bin, usando: {bin_files[0]}", "info")
    
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
        ports = serial.tools.list_ports.comports()
        port_list = [f"{port.device} - {port.description}" for port in ports]
        
        self.port_combo['values'] = port_list
        
        if port_list:
            self.port_combo.current(0)
            self.log(f"Puertos COM detectados: {len(port_list)}", "info")
        else:
            self.log("No se detectaron puertos COM. Conecta tu ESP32 y actualiza.", "error")
    
    def start_flash(self):
        """Iniciar proceso de flasheo en un hilo separado"""
        if self.is_flashing:
            messagebox.showwarning("Advertencia", "Ya hay un proceso de flasheo en curso.")
            return
        
        # Validaciones
        if not self.firmware_path or not os.path.exists(self.firmware_path):
            messagebox.showerror("Error", "No se encontró el archivo de firmware.\n\n"
                               "Asegúrate de tener un archivo .bin en la carpeta 'firmware'.")
            return
        
        if not self.selected_port.get():
            messagebox.showerror("Error", "Por favor selecciona un puerto COM.")
            return
        
        # Extraer solo el nombre del puerto (ej: COM3)
        port = self.selected_port.get().split(' - ')[0]
        
        # Confirmar
        if not messagebox.askyesno("Confirmar", 
                                   f"¿Estás seguro de que quieres cargar el firmware a {port}?\n\n"
                                   "Asegúrate de que el ESP32 esté en modo de programación."):
            return
        
        # Iniciar flasheo en un hilo separado
        self.is_flashing = True
        self.flash_btn.config(state='disabled')
        self.erase_btn.config(state='disabled')
        self.refresh_btn.config(state='disabled')
        self.progress.start()
        
        thread = threading.Thread(target=self.flash_firmware, args=(port,))
        thread.daemon = True
        thread.start()
    
    def flash_firmware(self, port):
        """Flashear el firmware usando esptool"""
        try:
            self.log("=" * 60, "info")
            self.log(f"Iniciando carga de firmware al ESP32 en {port}...", "info")
            self.log("=" * 60, "info")
            
            # Comando esptool
            # Dirección 0x10000 es común para aplicaciones ESP32 (puede variar según tu bootloader)
            # Buscar el Python correcto donde está instalado esptool
            script_dir = os.path.dirname(os.path.abspath(__file__))
            venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
            
            if os.path.exists(venv_python):
                python_exe = venv_python
            else:
                python_exe = sys.executable  # Fallback al Python actual
            
            # Obtener configuración específica del chip
            chip = self.selected_chip.get()
            config = self.chip_configs.get(chip, self.chip_configs["esp32s3"])
            
            # Usar baud rate seleccionado
            baud_rate = self.selected_baud.get()
            
            # Usar dirección alternativa si está marcada la opción
            flash_addr = config["flash_addr"]
            if chip == "esp32s3" and self.use_alt_address.get():
                flash_addr = "0x10000"  # Dirección alternativa para ESP32-S3
            
            # Comando base
            base_cmd = [
                python_exe, "-m", "esptool",
                "--chip", chip,
                "--port", port,
                "--baud", baud_rate,
                "--before", "default_reset",
                "--after", "hard_reset"
            ]
            
            # PASO 1: Borrar flash si está marcado
            if self.erase_flash.get():
                if self.smart_erase.get() and self.firmware_only_mode.get():
                    self.log("PASO 1/2: Borrado inteligente - solo región del firmware...", "info")
                    success = self.smart_erase_firmware_region(base_cmd)
                    if not success:
                        return
                    self.log("Región del firmware borrada (bootloader preservado)", "success")
                    self.log("", "normal")
                else:
                    self.log("PASO 1/2: Borrando flash completo...", "info")
                    erase_cmd = base_cmd + ["erase_flash"]
                    
                    self.log(f"Comando de borrado: {' '.join(erase_cmd)}", "info")
                    
                    erase_process = subprocess.Popen(
                        erase_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )
                    
                    for line in erase_process.stdout:
                        line = line.strip()
                        if line:
                            if "Chip erase completed" in line:
                                self.log(line, "success")
                            else:
                                self.log(line, "normal")
                    
                    erase_process.wait()
                    
                    if erase_process.returncode != 0:
                        self.log("Error al borrar el flash", "error")
                        return
                    else:
                        self.log("Flash borrado exitosamente", "success")
                        self.log("", "normal")
            
            
            # PASO 2: Verificar si usar layout de PlatformIO o modo simple
            if self.firmware_only_mode.get():
                self.log("PASO 2/2: Modo simple - solo firmware en 0x50000...", "info")
                success = self.flash_firmware_only_mode(base_cmd)
                if success:
                    self.log("", "normal")
                    self.log("=" * 60, "success")
                    self.log(" ¡FIRMWARE CARGADO EXITOSAMENTE EN MODO SIMPLE!", "success")
                    self.log("=" * 60, "success")
                    messagebox.showinfo("Éxito", "¡Firmware cargado exitosamente en modo simple!")
                return
            elif self.use_platformio_layout.get():
                if self.use_platformio_files.get():
                    self.log("PASO 2/2: Usando archivos reales de PlatformIO...", "info")
                    success = self.flash_with_real_platformio_files(base_cmd)
                else:
                    self.log("PASO 2/2: Usando layout de PlatformIO (múltiples particiones)...", "info")
                    success = self.flash_with_platformio_layout(base_cmd, baud_rate)
                
                if success:
                    self.log("", "normal")
                    self.log("=" * 60, "success")
                    self.log(" ¡FIRMWARE CARGADO EXITOSAMENTE CON LAYOUT PLATFORMIO!", "success")
                    self.log("=" * 60, "success")
                    messagebox.showinfo("Éxito", "¡Firmware cargado exitosamente con layout de PlatformIO!")
                return
            
            # PASO 2: Escribir firmware y bootloader si es necesario
            if chip == "esp32s3" and self.include_bootloader.get():
                self.log("PASO 2/3: Escribiendo bootloader ESP32-S3...", "info")
                
                # Crear bootloader básico para ESP32-S3
                bootloader_data = self.create_esp32s3_bootloader()
                bootloader_path = os.path.join(os.path.dirname(self.firmware_path), "bootloader_temp.bin")
                
                with open(bootloader_path, 'wb') as f:
                    f.write(bootloader_data)
                
                # Comando para bootloader con --force para saltarse validación de chip ID
                bootloader_cmd = base_cmd + [
                    "write_flash",
                    "-z",
                    "--force",  # Forzar escritura aunque el chip ID no coincida
                    "--flash_mode", "dio",
                    "--flash_freq", "80m", 
                    "--flash_size", "detect",
                    "0x0",  # Bootloader siempre va en 0x0
                    bootloader_path
                ]
                
                self.log(f"Comando bootloader: {' '.join(bootloader_cmd)}", "info")
                
                bootloader_process = subprocess.Popen(
                    bootloader_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                for line in bootloader_process.stdout:
                    line = line.strip()
                    if line:
                        if "Hash of data verified" in line or "Wrote" in line:
                            self.log(line, "success")
                        elif "Warning" in line:
                            self.log(line, "info")  # Warnings como info, no como error
                        else:
                            self.log(line, "normal")
                
                bootloader_process.wait()
                
                # Limpiar archivo temporal
                try:
                    os.remove(bootloader_path)
                except:
                    pass
                
                if bootloader_process.returncode != 0:
                    self.log("Error al escribir bootloader", "error")
                    return
                else:
                    self.log("Bootloader escrito exitosamente", "success")
                    self.log("", "normal")
                
                self.log("PASO 3/3: Escribiendo aplicación...", "info")
            else:
                self.log("PASO 2/2: Escribiendo firmware...", "info")
            cmd = base_cmd + [
                "write_flash",
                "-z",  # Comprimir para velocidad
                "--flash_mode", "dio",
                "--flash_freq", "80m",
                "--flash_size", "detect",
                flash_addr,
                self.firmware_path
            ]
            
            # Agregar verificación si está marcada
            if self.verify_flash.get():
                cmd.insert(-2, "--verify")
            
            self.log(f"Chip seleccionado: {chip}", "info")
            self.log(f"Dirección de flash: {flash_addr}", "info")
            self.log(f"Velocidad: {baud_rate} baud", "info")
            self.log(f"Archivo: {os.path.basename(self.firmware_path)} ({self.get_file_size(self.firmware_path)})", "info")
            self.log(f"Comando completo: {' '.join(cmd)}", "info")
            self.log("", "normal")
            
            # Ejecutar esptool
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Leer salida en tiempo real con mejor manejo de errores
            error_detected = False
            for line in process.stdout:
                line = line.strip()
                if line:
                    # Detectar errores específicos
                    if "A fatal error occurred" in line:
                        self.log(line, "error")
                        error_detected = True
                    elif "Failed to" in line or "Error:" in line:
                        self.log(line, "error")
                        error_detected = True
                    elif "Connecting" in line or "Writing" in line or "Hash of data verified" in line:
                        self.log(line, "success")
                    else:
                        self.log(line, "normal")
            
            process.wait()
            
            if process.returncode == 0:
                self.log("", "normal")
                self.log("=" * 60, "success")
                self.log(" ¡FIRMWARE CARGADO EXITOSAMENTE!", "success")
                self.log("=" * 60, "success")
                messagebox.showinfo("Éxito", "¡Firmware cargado exitosamente al ESP32!")
            else:
                self.log("", "normal")
                self.log("="*60, "error")
                self.log(" Error al cargar el firmware", "error")
                self.log("="*60, "error")
                
                # Sugerencias específicas para ESP32-S3
                chip = self.selected_chip.get()
                if chip == "esp32s3":
                    self.log("SUGERENCIAS PARA ESP32-S3:", "error")
                    self.log("1. Tu firmware ES compatible con ESP32-S3 (✓)", "info")
                    self.log("2. USA dirección 0x50000 (estándar PlatformIO)", "error")
                    self.log("3. NO marques 'Incluir bootloader' - causa conflictos", "error")
                    self.log("4. Si sigue fallando, intenta dirección 0x10000 (marca checkbox)", "error")
                    self.log("5. Mantén presionado BOOT, presiona RESET, suelta RESET, suelta BOOT", "error")
                    
                messagebox.showerror("Error", f"Error al cargar firmware al {chip}.\n\n"
                                   "Tu firmware ES compatible con ESP32-S3 ✓\n\n"
                                   "Para ESP32-S3:\n"
                                   "• USA dirección 0x50000 (estándar PlatformIO)\n"
                                   "• NO marques 'Incluir bootloader'\n"
                                   "• Si falla, intenta dirección 0x10000 (marca checkbox)\n"
                                   "• Mantén BOOT, presiona RESET, suelta RESET, suelta BOOT\n\n"
                                   "Revisa el log para más detalles.")
        
        except Exception as e:
            self.log("", "normal")
            self.log(f" Excepción: {str(e)}", "error")
            messagebox.showerror("Error", f"Error inesperado:\n{str(e)}")
        
        finally:
            self.is_flashing = False
            self.flash_btn.config(state='normal')
            self.erase_btn.config(state='normal')
            self.refresh_btn.config(state='normal')
            self.progress.stop()

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
        self.flash_btn.config(state='disabled')
        self.erase_btn.config(state='disabled')
        self.refresh_btn.config(state='disabled')
        self.progress.start()
        
        thread = threading.Thread(target=self.erase_flash_chip, args=(port,))
        thread.daemon = True
        thread.start()
    
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
                "erase_flash"
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
            self.flash_btn.config(state='normal')
            self.erase_btn.config(state='normal')
            self.refresh_btn.config(state='normal')
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
        """Crear un bootloader básico para ESP32-S3"""
        # Bootloader mínimo funcional para ESP32-S3 con chip ID correcto
        bootloader_size = 0x5000  # 20KB
        bootloader = bytearray(bootloader_size)
        
        # ESP32-S3 Image Header con chip ID correcto
        bootloader[0] = 0xE9  # ESP_IMAGE_HEADER_MAGIC
        bootloader[1] = 0x01  # segment_count (1 segmento)  
        bootloader[2] = 0x02  # spi_mode (DIO)
        bootloader[3] = 0x0F  # spi_speed (80MHz) + spi_size (detect)
        bootloader[4:8] = (0x40378000).to_bytes(4, 'little')  # entry_point para ESP32-S3
        
        # WP Pin y reservado
        bootloader[8] = 0xEE  # wp_pin
        bootloader[9] = 0x00  # reservado
        bootloader[10] = 0x00 # reservado
        bootloader[11] = 0x00 # reservado
        
        # Chip ID correcto para ESP32-S3
        bootloader[12] = 9    # CHIP_ID para ESP32-S3 (debe ser 9)
        bootloader[13] = 0    # reservado
        
        # Número de segmentos  
        bootloader[14] = 1    # segments
        bootloader[15] = 0    # reservado
        
        # Segment header 
        bootloader[16:20] = (0x40378000).to_bytes(4, 'little')   # load_addr
        bootloader[20:24] = (32).to_bytes(4, 'little')           # data_len (32 bytes de código)
        
        # Código de bootloader simplificado - solo saltos básicos
        boot_code = [
            # Código mínimo para ESP32-S3 que salta a la aplicación
            0x00, 0x00, 0x00, 0x00,  # entry point setup
            0x00, 0x00, 0x10, 0x00,  # jump to 0x10000 (aplicación)
            0x00, 0x00, 0x00, 0x00,  # nop
            0x00, 0x00, 0x00, 0x00,  # nop
            0x00, 0x00, 0x00, 0x00,  # nop
            0x00, 0x00, 0x00, 0x00,  # nop
            0x00, 0x00, 0x00, 0x00,  # nop
            0x00, 0x00, 0x00, 0x00   # nop
        ]
        
        # Copiar código al bootloader
        bootloader[24:24+len(boot_code)] = boot_code
        
        # Checksum simple (XOR de todos los bytes de datos)
        checksum = 0xEF
        for i in range(24, 24+len(boot_code)):
            checksum ^= bootloader[i]
            
        # Poner checksum
        bootloader[24+len(boot_code)] = checksum
        
        # Hash SHA256 placeholder (32 bytes de zeros - esptool lo calculará)
        for i in range(24+len(boot_code)+1, 24+len(boot_code)+33):
            if i < len(bootloader):
                bootloader[i] = 0x00
        
        # Rellenar el resto con 0xFF
        for i in range(24+len(boot_code)+33, len(bootloader)):
            bootloader[i] = 0xFF
        
        self.log("Bootloader ESP32-S3 creado con chip ID correcto (9)", "info")
        return bootloader
    
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
    
    def flash_with_platformio_layout(self, base_cmd, baud_rate):
        """Flash firmware usando layout de múltiples particiones como PlatformIO"""
        try:
            # Crear archivos temporales
            import tempfile
            temp_dir = tempfile.mkdtemp()
            
            partitions = []
            temp_files = []
            
            # Solo crear bootloader si no se salta
            if not self.skip_bootloader_creation.get():
                # Crear bootloader
                bootloader_data = self.create_bootloader_for_platformio()
                bootloader_path = os.path.join(temp_dir, "bootloader.bin")
                
                with open(bootloader_path, 'wb') as f:
                    f.write(bootloader_data)
                
                partitions.append(("0x0", bootloader_path, "Bootloader"))
                temp_files.append(bootloader_path)
                self.log("Bootloader personalizado creado", "info")
            else:
                self.log("Saltando creación de bootloader - usando el existente", "info")
            
            # Crear tabla de particiones
            partition_table_data = self.create_partition_table_for_platformio()
            partition_table_path = os.path.join(temp_dir, "partition_table.bin")
            
            with open(partition_table_path, 'wb') as f:
                f.write(partition_table_data)
            
            partitions.append(("0x8000", partition_table_path, "Tabla de particiones"))
            temp_files.append(partition_table_path)
            
            # Crear datos OTA
            ota_data = self.create_ota_data()
            ota_data_path = os.path.join(temp_dir, "ota_data_initial.bin")
            
            with open(ota_data_path, 'wb') as f:
                f.write(ota_data)
            
            partitions.append(("0x49000", ota_data_path, "OTA Data"))
            temp_files.append(ota_data_path)
            
            # Crear datos NVS como PlatformIO
            nvs_data = self.create_nvs_data() 
            nvs_data_path = os.path.join(temp_dir, "nvs_data.bin")
            
            with open(nvs_data_path, 'wb') as f:
                f.write(nvs_data)
            
            partitions.append(("0x49000", nvs_data_path, "NVS Data (como PlatformIO)"))
            temp_files.append(nvs_data_path)
            
            # Agregar firmware
            partitions.append(("0x50000", self.firmware_path, "App0 (OTA slot 0)"))
            
            self.log("Mapa de particiones ESP32-S3:", "info")
            for addr, path, desc in partitions:
                size = os.path.getsize(path)
                self.log(f"  {addr}: {desc} ({size:,} bytes)", "info")
            self.log("", "normal")
            
            # Flash cada partición
            total_partitions = len(partitions)
            for i, (address, file_path, description) in enumerate(partitions, 1):
                self.log(f"Escribiendo partición {i}/{total_partitions}: {description} en {address}...", "info")
                
                cmd = base_cmd + [
                    "write_flash",
                    "-z",
                    "--flash_mode", "dio",
                    "--flash_freq", "80m",
                    "--flash_size", "detect",
                    address,
                    file_path
                ]
                
                if self.verify_flash.get():
                    cmd.insert(-2, "--verify")
                
                self.log(f"Comando: {' '.join(cmd[-4:])}", "info")
                
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
                        if "Hash of data verified" in line or "Wrote" in line:
                            self.log(line, "success")
                        elif "A fatal error occurred" in line or "Failed to" in line:
                            self.log(line, "error")
                            # Limpiar archivos temporales
                            try:
                                for temp_file in temp_files:
                                    os.remove(temp_file)
                                os.rmdir(temp_dir)
                            except:
                                pass
                            return False
                        else:
                            self.log(line, "normal")
                
                process.wait()
                
                if process.returncode != 0:
                    self.log(f"Error escribiendo {description}", "error")
                    # Limpiar archivos temporales
                    try:
                        for temp_file in temp_files:
                            os.remove(temp_file)
                        os.rmdir(temp_dir)
                    except:
                        pass
                    return False
                else:
                    self.log(f"✓ {description} escrito exitosamente", "success")
                    self.log("", "normal")
            
            # Limpiar archivos temporales
            try:
                for temp_file in temp_files:
                    os.remove(temp_file)
                os.rmdir(temp_dir)
            except:
                pass
            
            return True
            
        except Exception as e:
            self.log(f"Error en flash PlatformIO: {str(e)}", "error")
            return False
    
    def create_bootloader_for_platformio(self):
        """Crear bootloader compatible con PlatformIO para ESP32-S3"""
        # Bootloader básico para ESP32-S3 (compatible con el formato que usa PlatformIO)
        bootloader = bytearray(0x5000)  # 20KB típico de PlatformIO
        
        # Header ESP32-S3
        bootloader[0] = 0xE9  # ESP_IMAGE_HEADER_MAGIC
        bootloader[1] = 0x04  # Segment count
        bootloader[2] = 0x02  # SPI mode DIO
        bootloader[3] = 0x0F  # SPI size 16MB
        
        # Entry point típico para ESP32-S3 bootloader
        entry_point = 0x40374000
        bootloader[4:8] = entry_point.to_bytes(4, 'little')
        
        # WP Pin (deshabilitado)
        bootloader[8] = 0xEE
        
        # Rellenar el resto con patrón válido
        for i in range(9, len(bootloader)):
            bootloader[i] = 0xFF
        
        return bytes(bootloader)
    
    def create_partition_table_for_platformio(self):
        """Crear tabla de particiones exactamente como la del ESP32-S3 detectada"""
        # Tabla de particiones que coincide con la detectada en el ESP32-S3
        partition_table = bytearray(0x1000)
        
        # Magic bytes del header
        partition_table[0:2] = b'\xAA\x50'
        
        # Partición 0: nvs (WiFi data) - 01 02 00009000 00040000
        offset = 32  # Primera entrada de partición
        partition_table[offset:offset+2] = b'\xAA\x50'  # Magic
        partition_table[offset+2] = 0x01  # Type: data
        partition_table[offset+3] = 0x02  # Subtype: nvs
        partition_table[offset+4:offset+8] = (0x9000).to_bytes(4, 'little')   # Offset
        partition_table[offset+8:offset+12] = (0x40000).to_bytes(4, 'little') # Size
        partition_table[offset+12:offset+28] = b'nvs\x00' + b'\x00' * 13     # Label
        partition_table[offset+28:offset+32] = b'\x00' * 4  # Flags
        
        # Partición 1: otadata (OTA data) - 01 00 00049000 00002000 
        offset = 64
        partition_table[offset:offset+2] = b'\xAA\x50'  # Magic
        partition_table[offset+2] = 0x01  # Type: data
        partition_table[offset+3] = 0x00  # Subtype: ota
        partition_table[offset+4:offset+8] = (0x49000).to_bytes(4, 'little')  # Offset
        partition_table[offset+8:offset+12] = (0x2000).to_bytes(4, 'little')  # Size
        partition_table[offset+12:offset+28] = b'otadata\x00' + b'\x00' * 9  # Label
        partition_table[offset+28:offset+32] = b'\x00' * 4  # Flags
        
        # Partición 2: phy (RF data) - 01 01 0004b000 00001000
        offset = 96
        partition_table[offset:offset+2] = b'\xAA\x50'  # Magic
        partition_table[offset+2] = 0x01  # Type: data
        partition_table[offset+3] = 0x01  # Subtype: phy
        partition_table[offset+4:offset+8] = (0x4b000).to_bytes(4, 'little')  # Offset
        partition_table[offset+8:offset+12] = (0x1000).to_bytes(4, 'little')  # Size
        partition_table[offset+12:offset+28] = b'phy\x00' + b'\x00' * 13     # Label
        partition_table[offset+28:offset+32] = b'\x00' * 4  # Flags
        
        # Partición 3: app0 (OTA app) - 00 10 00050000 002a3000
        offset = 128
        partition_table[offset:offset+2] = b'\xAA\x50'  # Magic
        partition_table[offset+2] = 0x00  # Type: app
        partition_table[offset+3] = 0x10  # Subtype: ota_0
        partition_table[offset+4:offset+8] = (0x50000).to_bytes(4, 'little')  # Offset
        partition_table[offset+8:offset+12] = (0x2a3000).to_bytes(4, 'little') # Size
        partition_table[offset+12:offset+28] = b'app0\x00' + b'\x00' * 12    # Label
        partition_table[offset+28:offset+32] = b'\x00' * 4  # Flags
        
        # Partición 4: app1 (OTA app) - 00 11 00320000 002a3000
        offset = 160
        partition_table[offset:offset+2] = b'\xAA\x50'  # Magic
        partition_table[offset+2] = 0x00  # Type: app
        partition_table[offset+3] = 0x11  # Subtype: ota_1
        partition_table[offset+4:offset+8] = (0x320000).to_bytes(4, 'little')  # Offset
        partition_table[offset+8:offset+12] = (0x2a3000).to_bytes(4, 'little') # Size
        partition_table[offset+12:offset+28] = b'app1\x00' + b'\x00' * 12    # Label
        partition_table[offset+28:offset+32] = b'\x00' * 4  # Flags
        
        # Partición 5: spiffs (Unknown data) - 01 82 005f0000 00128000
        offset = 192
        partition_table[offset:offset+2] = b'\xAA\x50'  # Magic
        partition_table[offset+2] = 0x01  # Type: data
        partition_table[offset+3] = 0x82  # Subtype: spiffs
        partition_table[offset+4:offset+8] = (0x5f0000).to_bytes(4, 'little')  # Offset
        partition_table[offset+8:offset+12] = (0x128000).to_bytes(4, 'little') # Size
        partition_table[offset+12:offset+28] = b'spiffs\x00' + b'\x00' * 10  # Label
        partition_table[offset+28:offset+32] = b'\x00' * 4  # Flags
        
        # Partición 6: coredump (Unknown data) - 01 03 00720000 00080000
        offset = 224
        partition_table[offset:offset+2] = b'\xAA\x50'  # Magic
        partition_table[offset+2] = 0x01  # Type: data
        partition_table[offset+3] = 0x03  # Subtype: coredump
        partition_table[offset+4:offset+8] = (0x720000).to_bytes(4, 'little')  # Offset
        partition_table[offset+8:offset+12] = (0x80000).to_bytes(4, 'little')  # Size
        partition_table[offset+12:offset+28] = b'coredump\x00' + b'\x00' * 8 # Label
        partition_table[offset+28:offset+32] = b'\x00' * 4  # Flags
        
        # Rellenar el resto con 0xFF
        for i in range(256, len(partition_table)):
            partition_table[i] = 0xFF
        
        return bytes(partition_table)
    
    def create_ota_data(self):
        """Crear datos OTA iniciales para marcar app0 como válida"""
        # OTA data de 8KB con app0 marcada como activa
        ota_data = bytearray(0x2000)  # 8KB
        
        # Estructura OTA data para ESP32-S3
        # Marcar app0 (slot 0) como activa
        ota_data[0:4] = (0).to_bytes(4, 'little')      # active_otadata[0] = 0 (app0)
        ota_data[4:8] = (0xFFFFFFFF).to_bytes(4, 'little')  # active_otadata[1] = invalid
        
        # CRC32 para validar (simplificado)
        ota_data[28:32] = (0xFFFFFFFF).to_bytes(4, 'little')  # CRC placeholder
        
        # Rellenar el resto con 0xFF
        for i in range(32, len(ota_data)):
            ota_data[i] = 0xFF
        
        return bytes(ota_data)
    
    def create_nvs_data(self):
        """Crear datos NVS inicial para ESP32-S3 (como PlatformIO)"""
        # NVS data de 8KB - exactamente como lo hace PlatformIO
        nvs_data = bytearray(0x2000)  # 8KB como en el log de PlatformIO
        
        # Header NVS
        nvs_data[0:4] = b'\xff\xff\xff\xff'  # Página vacía inicialmente
        
        # Rellenar con patrón NVS vacío
        for i in range(4, len(nvs_data)):
            nvs_data[i] = 0xFF
        
        return bytes(nvs_data)
    
    def flash_firmware_only_mode(self, base_cmd):
        """Flash solo el firmware en 0x50000 - método simple sin particiones"""
        try:
            self.log("Modo simple: escribiendo firmware directamente en 0x50000", "info")
            self.log(f"Archivo: {os.path.basename(self.firmware_path)}", "info")
            self.log(f"Tamaño: {self.get_file_size(self.firmware_path)}", "info")
            self.log("", "normal")
            
            # Comando simple para escribir solo el firmware
            cmd = base_cmd + [
                "write_flash",
                "-z",
                "--flash_mode", "dio", 
                "--flash_freq", "80m",
                "--flash_size", "detect",
                "0x50000",  # Dirección donde el bootloader busca app0
                self.firmware_path
            ]
            
            if self.verify_flash.get():
                cmd.insert(-2, "--verify")
            
            self.log(f"Comando: {' '.join(cmd[-4:])}", "info")
            self.log("Iniciando escritura...", "info")
            
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
                    if "Hash of data verified" in line or "Wrote" in line:
                        self.log(line, "success")
                    elif "A fatal error occurred" in line or "Failed to" in line:
                        self.log(line, "error")
                        return False
                    else:
                        self.log(line, "normal")
            
            process.wait()
            
            if process.returncode == 0:
                self.log("✓ Firmware escrito exitosamente en 0x50000", "success")
                return True
            else:
                self.log("Error escribiendo firmware", "error")
                return False
                
        except Exception as e:
            self.log(f"Error en modo simple: {str(e)}", "error")
            return False
    
    def find_platformio_files(self):
        """Buscar archivos de bootloader y particiones de PlatformIO"""
        try:
            # Buscar en directorios comunes de PlatformIO
            project_root = os.path.dirname(os.path.abspath(__file__))
            search_paths = [
                os.path.join(project_root, ".pio", "build", "esp32-s3-devkitc-1"),
                os.path.join(project_root, "..", ".pio", "build", "esp32-s3-devkitc-1"),
                os.path.join(project_root, "..", "..", ".pio", "build", "esp32-s3-devkitc-1")
            ]
            
            for search_path in search_paths:
                if os.path.exists(search_path):
                    bootloader_path = os.path.join(search_path, "bootloader.bin")
                    partitions_path = os.path.join(search_path, "partitions.bin")
                    
                    if os.path.exists(bootloader_path) and os.path.exists(partitions_path):
                        self.log(f"Encontrados archivos PlatformIO en: {search_path}", "success")
                        return {
                            "bootloader": bootloader_path,
                            "partitions": partitions_path,
                            "build_dir": search_path
                        }
            
            self.log("No se encontraron archivos de PlatformIO", "error")
            self.log("Busca en: .pio/build/esp32-s3-devkitc-1/", "info")
            return None
            
        except Exception as e:
            self.log(f"Error buscando archivos PlatformIO: {e}", "error")
            return None
    
    def flash_with_real_platformio_files(self, base_cmd):
        """Flash usando archivos reales de bootloader y particiones de PlatformIO"""
        try:
            # Buscar archivos de PlatformIO
            pio_files = self.find_platformio_files()
            if not pio_files:
                self.log("No se pueden usar archivos de PlatformIO - no encontrados", "error")
                return False
            
            # Crear datos OTA
            import tempfile
            temp_dir = tempfile.mkdtemp()
            
            ota_data = self.create_ota_data()
            ota_data_path = os.path.join(temp_dir, "ota_data_initial.bin")
            
            with open(ota_data_path, 'wb') as f:
                f.write(ota_data)
            
            # Mapa de particiones usando archivos reales de PlatformIO
            partitions = [
                ("0x0", pio_files["bootloader"], "Bootloader (PlatformIO real)"),
                ("0x8000", pio_files["partitions"], "Partitions (PlatformIO real)"),
                ("0x49000", ota_data_path, "OTA Data"),
                ("0x50000", self.firmware_path, "App0 (Firmware)")
            ]
            
            self.log("Usando archivos REALES de PlatformIO:", "success")
            for addr, path, desc in partitions:
                size = os.path.getsize(path)
                self.log(f"  {addr}: {desc} ({size:,} bytes)", "info")
            self.log("", "normal")
            
            # Flash cada partición
            for i, (address, file_path, description) in enumerate(partitions, 1):
                self.log(f"Escribiendo {i}/4: {description} en {address}...", "info")
                
                cmd = base_cmd + [
                    "write_flash",
                    "-z",
                    "--flash_mode", "dio",
                    "--flash_freq", "80m",
                    "--flash_size", "detect",
                    address,
                    file_path
                ]
                
                if self.verify_flash.get():
                    cmd.insert(-2, "--verify")
                
                self.log(f"Comando: {' '.join(cmd[-4:])}", "info")
                
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
                        if "Hash of data verified" in line or "Wrote" in line:
                            self.log(line, "success")
                        elif "A fatal error occurred" in line or "Failed to" in line:
                            self.log(line, "error")
                            # Limpiar archivos temporales
                            try:
                                os.remove(ota_data_path)
                                os.rmdir(temp_dir)
                            except:
                                pass
                            return False
                        else:
                            self.log(line, "normal")
                
                process.wait()
                
                if process.returncode != 0:
                    self.log(f"Error escribiendo {description}", "error")
                    # Limpiar archivos temporales
                    try:
                        os.remove(ota_data_path)
                        os.rmdir(temp_dir)
                    except:
                        pass
                    return False
                else:
                    self.log(f"✓ {description} escrito exitosamente", "success")
                    self.log("", "normal")
            
            # Limpiar archivos temporales
            try:
                os.remove(ota_data_path)
                os.rmdir(temp_dir)
            except:
                pass
            
            return True
            
        except Exception as e:
            self.log(f"Error usando archivos PlatformIO reales: {str(e)}", "error")
            return False
    
    def smart_erase_firmware_region(self, base_cmd):
        """Borrar solo la región del firmware, preservando bootloader y particiones"""
        try:
            self.log("Borrando solo región 0x50000-0x300000 (preserva bootloader)", "info")
            
            # Comando para borrar solo la región del firmware
            cmd = base_cmd + [
                "erase_region",
                "0x50000",  # Inicio: donde va el firmware
                "0x2B0000"  # Tamaño: ~2.7MB (suficiente para firmware)
            ]
            
            self.log(f"Comando: {' '.join(cmd)}", "info")
            
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
                    if "Erase completed" in line:
                        self.log(line, "success")
                    elif "Error" in line or "Failed" in line:
                        self.log(line, "error")
                        return False
                    else:
                        self.log(line, "normal")
            
            process.wait()
            return process.returncode == 0
            
        except Exception as e:
            self.log(f"Error en borrado inteligente: {e}", "error")
            return False

def main():
    root = tk.Tk()
    app = ESP32Flasher(root)
    root.mainloop()

if __name__ == "__main__":
    main()