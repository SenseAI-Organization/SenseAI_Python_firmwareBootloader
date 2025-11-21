App generation and packaging

This folder contains helper scripts to produce a Windows executable for the GUI
and to keep packaging-related tools in one place.

Files included:
- `build_app.ps1`  : PowerShell script that creates a venv, installs deps and runs PyInstaller
- `crear_exe.bat`  : Simple batch wrapper for users who prefer double-click
- `install_dependencies.bat` : Installs requirements using pip
- `build_spiffs.py` : (copied) utility to build spiffs image with mkspiffs
- `build_fresh_spiffs.py` : (copied) higher-level script to build a fresh spiffs image
- `flash_fresh_spiffs.py` : (copied) script to flash freshly-built SPIFFS image

Output:
- All built artifacts (the executable) will be placed in `..\app_generation_output` when using the provided scripts.

Notes:
- We intentionally include the pre-built `data/spiffs.bin` via PyInstaller's `--add-data`.
- If `mkspiffs` is unavailable, the build scripts will skip attempts to build a fresh SPIFFS image.
