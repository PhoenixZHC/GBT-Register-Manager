$ErrorActionPreference = 'Stop'

# 1) Locate project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

Write-Host ("gbt-bridge project root = {0}" -f $projectRoot) -ForegroundColor Cyan

# 2) Detect Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
  Write-Error 'Python 3.9+ not found. Please install and add to PATH.'
  exit 1
}

$pythonExe = $python.Source
Write-Host ("gbt-bridge using python = {0}" -f $pythonExe)

# 3) Install dependencies
Write-Host 'gbt-bridge installing runtime + build dependencies ...' -ForegroundColor Cyan
& $pythonExe -m pip install --upgrade pip | Out-Host
& $pythonExe -m pip install -r 'python-sidecar\requirements.txt' | Out-Host
& $pythonExe -m pip install -r 'python-sidecar\requirements-build.txt' | Out-Host

# 4) Build sidecar via PyInstaller
Write-Host 'gbt-bridge running PyInstaller ...' -ForegroundColor Cyan
Push-Location 'python-sidecar'
try {
  & $pythonExe -m PyInstaller --noconfirm --clean 'gbt_bridge.spec'
} finally {
  Pop-Location
}

$builtExe = Join-Path $projectRoot 'python-sidecar\dist\gbt-bridge.exe'
if (-not (Test-Path $builtExe)) {
  Write-Error ("Build failed: file not found: {0}" -f $builtExe)
  exit 1
}

# 5) Resolve Rust target triple
$targetTriple = (& rustc -vV | Select-String 'host:' | ForEach-Object { ($_ -split ':')[1].Trim() })
if (-not $targetTriple) {
  Write-Warning 'rustc not detected. Fallback to x86_64-pc-windows-msvc.'
  $targetTriple = 'x86_64-pc-windows-msvc'
}

Write-Host ("gbt-bridge target triple = {0}" -f $targetTriple)

# 6) Copy binary to Tauri externalBin folder
$binDir = Join-Path $projectRoot 'src-tauri\binaries'
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

$dest = Join-Path $binDir ("gbt-bridge-{0}.exe" -f $targetTriple)
Copy-Item $builtExe $dest -Force
Write-Host ("gbt-bridge copied -> {0}" -f $dest) -ForegroundColor Green

Write-Host 'gbt-bridge done. You can now run npm run tauri:build .' -ForegroundColor Green
