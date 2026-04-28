<#
PowerShell build script to create a Windows executable using PyInstaller.

Usage (PowerShell):
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\app_generation\build_app.ps1

What it does:
 - Creates (or repairs) a virtual environment in `app_generation\.venv`
 - Installs dependencies from `requirements.txt` (repo root)
 - Runs PyInstaller to create a single-file windowed executable
 - Places output in `app_generation_output` (repo root)

Options:
  -ConsoleTest   Build with a visible console window (useful for debugging crashes)
#>
param(
    [switch]$ConsoleTest
)

$ErrorActionPreference = 'Stop'

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot   = (Resolve-Path (Join-Path $scriptDir "..")).Path
$outputDir  = Join-Path $repoRoot "app_generation_output"
$venvDir    = Join-Path $scriptDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

$exeName    = "Sense-esp32_flasher"
$iconPath   = Join-Path $scriptDir "IsotipoSense.ico"
$mainScript = Join-Path $repoRoot "firmwareBootLoader.py"
$spiffsSrc  = Join-Path $repoRoot "data\spiffs.bin"

Write-Host "Repo root:  $repoRoot"
Write-Host "Output dir: $outputDir"

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if (-not (Test-Path $mainScript)) {
    Write-Error "Main script not found: $mainScript"
    exit 1
}

# --- Venv: create or repair ---
# Check if pip is functional; rebuild the venv if it is broken.
$needRebuild = $false
if (-not (Test-Path $venvPython)) {
    $needRebuild = $true
    Write-Host "Virtual environment not found - creating..."
} else {
    & $venvPython -m pip --version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $needRebuild = $true
        Write-Host "Virtual environment is broken - rebuilding..."
        Remove-Item -Recurse -Force $venvDir
    }
}

if ($needRebuild) {
    python -m venv $venvDir
}

# --- Install / upgrade dependencies ---
Write-Host "Installing dependencies..."
& $venvPython -m pip install --upgrade pip -q
& $venvPython -m pip install -r (Join-Path $repoRoot "requirements.txt") pyinstaller pillow -q
Write-Host "Dependencies installed."

# --- Convert PNG icon to ICO if needed ---
if (-not (Test-Path $iconPath)) {
    $pngPath = Join-Path $scriptDir "IsotipoSense.png"
    if (Test-Path $pngPath) {
        Write-Host "Converting PNG icon to ICO..."
        & $venvPython -c "
from PIL import Image
img = Image.open(r'$pngPath').convert('RGBA')
img.save(r'$iconPath', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('ICO created.')
"
    } else {
        Write-Warning "Icon not found at $iconPath - building without icon."
        $iconPath = $null
    }
}

# --- Build PyInstaller args ---
Write-Host "Running PyInstaller (this may take a while)..."

$pyArgs = @(
    '--noconfirm',
    '--onefile',
    "--name=$exeName"
)

if (-not $ConsoleTest) {
    $pyArgs += '--windowed'
} else {
    Write-Host "ConsoleTest mode: building with console window."
}

if ($iconPath -and (Test-Path $iconPath)) {
    $pyArgs += "--icon=$iconPath"
}

if (Test-Path $spiffsSrc) {
    $pyArgs += "--add-data=$spiffsSrc;data"
} else {
    Write-Warning "data\spiffs.bin not found - EXE will not bundle a SPIFFS image."
}

$pyArgs += "--distpath=$outputDir"
$pyArgs += "--workpath=$(Join-Path $outputDir 'build')"
$pyArgs += "--specpath=$(Join-Path $outputDir 'specs')"
$pyArgs += $mainScript

& $venvPython -m PyInstaller @pyArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Build complete! EXE located at:"
Write-Host "  $outputDir\$exeName.exe"
