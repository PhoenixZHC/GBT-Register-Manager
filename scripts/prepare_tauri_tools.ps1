$ErrorActionPreference = "Stop"

$tauriCache = Join-Path $env:LOCALAPPDATA "tauri"

$wixRoot = Join-Path $tauriCache "WixTools314"
$candle = Join-Path $wixRoot "candle.exe"

$nsisRoot = Join-Path $tauriCache "NSIS"
$makensis = Join-Path $nsisRoot "makensis.exe"

Write-Host "[tauri-tools] Ensuring WiX (MSI) and NSIS (EXE) caches are ready..."

$missing = @()

if (Test-Path $candle) {
  Write-Host "[tauri-tools] WiX cache found: $wixRoot"
} else {
  $missing += "WiX 3.11 (expected at '$candle')"
}

if (Test-Path $makensis) {
  Write-Host "[tauri-tools] NSIS cache found: $nsisRoot"
} else {
  $missing += "NSIS 3 (expected at '$makensis')"
}

if ($missing.Count -gt 0) {
  $details = $missing -join "; "
  throw "[tauri-tools] Missing: $details. Run: npm run tauri:download-wix-nsis (installs WiX/NSIS into %LOCALAPPDATA%\tauri)"
}

Write-Host "[tauri-tools] All bundler tools are ready."
