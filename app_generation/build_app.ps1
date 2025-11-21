<#
PowerShell build script to create a Windows executable using PyInstaller.

Usage (PowerShell):
  .\build_app.ps1

What it does:
 - Creates a virtual environment in `app_generation\.venv`
 - Installs dependencies from `requirements.txt` (repo root)
 - Runs PyInstaller to create a single-file executable
 - Places output in `app_generation_output` (repo root)
#>
param(
    [switch]$ConsoleTest
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$outputDir = Join-Path $repoRoot "app_generation_output"
$venvDir = Join-Path $scriptDir ".venv"

Write-Host "Repo root: $repoRoot"
Write-Host "Output dir: $outputDir"

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venvDir
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Virtualenv python not found, falling back to system python"
    $venvPython = "python"
}

Write-Host "Installing dependencies into virtualenv..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $repoRoot "requirements.txt")

Write-Host "Ensuring PyInstaller available..."
& $venvPython -m pip install "pyinstaller>=5.0"

# Build args
$mainScript = Join-Path $repoRoot "firmwareBootLoader.py"
$spiffsSrc = Join-Path $repoRoot "data\spiffs.bin"

if (-not (Test-Path $mainScript)) {
    Write-Error "Main script not found: $mainScript"
    exit 1
}

if (-not (Test-Path $spiffsSrc)) {
    Write-Warning "Warning: data/spiffs.bin not found. The generated EXE will not include SPIFFS image."
}

Write-Host "Running PyInstaller (this may take a while)..."

# For Windows the --add-data separator is ;
$addDataArg = $null
if (Test-Path $spiffsSrc) {
    # Format: "<abs_path>;<destination_folder_inside_exe>"
    $addDataArg = "--add-data"
    $addDataValue = """$spiffsSrc;data"""
}

# Prepare argument list for PyInstaller invocation
$pyinstallerArgs = @('--noconfirm','--onefile','--name=ESP32_Flasher')
if (-not $ConsoleTest) {
    # Default: windowed (no console)
    $pyinstallerArgs += '--windowed'
} else {
    Write-Host "ConsoleTest requested - building console EXE for debugging"
}
if ($addDataArg) { $pyinstallerArgs += $addDataArg; $pyinstallerArgs += $addDataValue }
$pyinstallerArgs += @('--distpath', (Resolve-Path $outputDir).Path, '--workpath', (Join-Path $outputDir 'build'), '--specpath', (Join-Path $outputDir 'specs'), (Resolve-Path $mainScript).Path)

Write-Host "pyinstaller args: $pyinstallerArgs"

& $venvPython -m PyInstaller @pyinstallerArgs

Write-Host "PyInstaller finished. Output placed in: $outputDir"

# Also copy the spiffs.bin next to the exe for convenience
if (Test-Path $spiffsSrc) {
    try {
        Copy-Item -Path $spiffsSrc -Destination (Join-Path $outputDir "spiffs.bin") -Force
        Write-Host "Copied spiffs.bin to output folder"
    } catch {
        Write-Warning "Failed to copy spiffs.bin to output folder: $_"
    }
}

Write-Host "Build complete. You can find the EXE at: $outputDir\ESP32_Flasher.exe"
