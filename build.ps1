# Скрипт сборки StreamGrab для Windows (PowerShell)
# Создает как папку с файлами, так и портативную onefile версию

param(
    [switch]$Clean,
    [switch]$OneFile,
    [switch]$All
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  StreamGrab - Build Script (Windows)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = $PSScriptRoot
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
$ResourcesDir = Join-Path $ProjectRoot "resources"
$OutputDir = Join-Path $ProjectRoot "output"

if ($Clean) {
    Write-Host "[CLEAN] Removing previous builds..." -ForegroundColor Yellow
    if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
    if (Test-Path $DistDir) { Remove-Item $DistDir -Recurse -Force }
    if (Test-Path $OutputDir) { Remove-Item $OutputDir -Recurse -Force }
}

if (-not (Test-Path $BuildDir)) { New-Item -ItemType Directory -Path $BuildDir | Out-Null }
if (-not (Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir | Out-Null }
if (-not (Test-Path $ResourcesDir)) { New-Item -ItemType Directory -Path $ResourcesDir | Out-Null }
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }

Write-Host "[1/6] Checking Python..." -ForegroundColor Green
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}
Write-Host "    Using: $($pythonCmd.Source)" -ForegroundColor Gray

Write-Host "[2/6] Checking dependencies..." -ForegroundColor Green
$deps = @("pyinstaller", "requests", "yt-dlp", "mutagen")
foreach ($dep in $deps) {
    $installed = & python -m pip show $dep 2>$null
    if (-not $installed) {
        Write-Host "    Installing $dep..." -ForegroundColor Yellow
        & python -m pip install $dep --quiet
    }
}

Write-Host "[3/6] Installing project dependencies..." -ForegroundColor Green
& python -m pip install -q requests yt-dlp mutagen plyer 2>$null

Write-Host "[4/6] Generating icon..." -ForegroundColor Green
$iconScript = Join-Path $ProjectRoot "scripts" "generate_icon.py"
if (Test-Path $iconScript) {
    & python $iconScript 2>$null
    Write-Host "    Icon generated in resources/" -ForegroundColor Gray
} else {
    Write-Host "    Icon script not found, skipping..." -ForegroundColor Gray
}

Write-Host "[5/6] Building with PyInstaller..." -ForegroundColor Green

$specFile = Join-Path $ProjectRoot "StreamGrab.spec"
$onefileSpec = Join-Path $ProjectRoot "StreamGrab-onefile.spec"

if ($All -or (-not $OneFile)) {
    Write-Host "    Building folder version..." -ForegroundColor Gray
    & python -m PyInstaller $specFile --clean --noconfirm --log-level=INFO
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Build failed" -ForegroundColor Red
        exit 1
    }
    
    if (Test-Path (Join-Path $DistDir "StreamGrab")) {
        Copy-Item -Path (Join-Path $DistDir "StreamGrab") -Destination (Join-Path $OutputDir "StreamGrab") -Recurse -Force
        Write-Host "    Folder version: output/StreamGrab/" -ForegroundColor Gray
    }
}

if ($OneFile -or $All) {
    Write-Host "    Building onefile version..." -ForegroundColor Gray
    
    $onefileArgs = @($onefileSpec, "--onefile", "--noconfirm", "--log-level=INFO")
    & python -m PyInstaller @onefileArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] OneFile build failed" -ForegroundColor Red
        exit 1
    }
    
    if (Test-Path (Join-Path $DistDir "StreamGrab.exe")) {
        Copy-Item -Path (Join-Path $DistDir "StreamGrab.exe") -Destination $OutputDir -Force
        Write-Host "    OneFile: output/StreamGrab.exe" -ForegroundColor Gray
    }
}

Write-Host "[6/6] Verifying build..." -ForegroundColor Green

$exeInOutput = Get-ChildItem $OutputDir -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue
if ($exeInOutput) {
    foreach ($exe in $exeInOutput) {
        $sizeMB = [math]::Round($exe.Length / 1MB, 2)
        Write-Host "    $($exe.Name): $sizeMB MB" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Build completed successfully!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Output directory: $OutputDir" -ForegroundColor White
Write-Host ""

if (Test-Path (Join-Path $OutputDir "StreamGrab.exe")) {
    Write-Host "Portable EXE: $OutputDir\StreamGrab.exe" -ForegroundColor Yellow
    Write-Host "  -> Double-click to run" -ForegroundColor Gray
}
if (Test-Path (Join-Path $OutputDir "StreamGrab")) {
    Write-Host "Folder version: $OutputDir\StreamGrab\" -ForegroundColor Yellow
    Write-Host "  -> Run StreamGrab.exe inside the folder" -ForegroundColor Gray
}
Write-Host ""
