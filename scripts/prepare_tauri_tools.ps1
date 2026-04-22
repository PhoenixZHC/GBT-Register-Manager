$ErrorActionPreference = "Stop"



$wixRoot = Join-Path $env:LOCALAPPDATA "tauri\WixTools314"

$candle = Join-Path $wixRoot "candle.exe"



Write-Host "[tauri-tools] Ensuring WiX (MSI) cache is ready..."



if (Test-Path $candle) {

  Write-Host "[tauri-tools] WiX cache already available: $wixRoot"

  exit 0

}



throw "[tauri-tools] WiX 3.11 not found at '$candle'. Run: npm run tauri:download-wix-nsis (installs WiX into %LOCALAPPDATA%\tauri\WixTools314)"

