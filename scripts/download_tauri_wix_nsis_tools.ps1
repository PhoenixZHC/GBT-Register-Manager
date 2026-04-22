#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# ghproxy 等镜像前缀；不需要时改为 "" 即可直连 GitHub
$ghproxy = "https://ghproxy.net/"

$wix311_binaries = $ghproxy + "https://github.com/wixtoolset/wix3/releases/download/wix3112rtm/wix311-binaries.zip"
$nsis_3 = $ghproxy + "https://github.com/tauri-apps/binary-releases/releases/download/nsis-3/nsis-3.zip"
$NSIS_ApplicationID = $ghproxy + "https://github.com/tauri-apps/binary-releases/releases/download/nsis-plugins-v0/NSIS-ApplicationID.zip"
$nsis_tauri_utils = $ghproxy + "https://github.com/tauri-apps/nsis-tauri-utils/releases/download/nsis_tauri_utils-v0.1.1/nsis_tauri_utils.dll"

function Invoke-FileDownload([string] $Uri, [string] $OutFile) {
  Write-Host "Downloading: $Uri"
  Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$temp = Join-Path $projectRoot "temp"
$tauriCache = Join-Path $env:LOCALAPPDATA "tauri"

if (Test-Path $temp) {
  Remove-Item -LiteralPath $temp -Recurse -Force
}
New-Item -ItemType Directory -Path $temp -Force | Out-Null
Push-Location $temp

try {
  Invoke-FileDownload -Uri $wix311_binaries -OutFile ".\wix311-binaries.zip"
  New-Item -ItemType Directory -Path ".\WixTools314" -Force | Out-Null
  Expand-Archive -Path ".\wix311-binaries.zip" -DestinationPath ".\WixTools314" -Force

  Invoke-FileDownload -Uri $nsis_3 -OutFile ".\nsis-3.zip"
  New-Item -ItemType Directory -Path ".\NSIS" -Force | Out-Null
  Expand-Archive -Path ".\nsis-3.zip" -DestinationPath ".\NSIS" -Force

  $nested = Get-ChildItem ".\NSIS" -Directory | Where-Object { $_.Name -like "nsis-3*" }
  foreach ($d in $nested) {
    Get-ChildItem -LiteralPath $d.FullName | ForEach-Object {
      Move-Item -LiteralPath $_.FullName -Destination (Join-Path ".\NSIS" $_.Name) -Force
    }
    Remove-Item -LiteralPath $d.FullName -Recurse -Force
  }

  Invoke-FileDownload -Uri $NSIS_ApplicationID -OutFile ".\NSIS-ApplicationID.zip"
  New-Item -ItemType Directory -Path ".\NSIS-ApplicationID" -Force | Out-Null
  Expand-Archive -Path ".\NSIS-ApplicationID.zip" -DestinationPath ".\NSIS-ApplicationID" -Force

  $pluginsUnicode = Join-Path ".\NSIS" "Plugins\x86-unicode"
  New-Item -ItemType Directory -Path $pluginsUnicode -Force | Out-Null
  $releaseDir = Join-Path ".\NSIS-ApplicationID" "Release"
  if (-not (Test-Path $releaseDir)) {
    throw "解压后未找到目录: $releaseDir"
  }
  Get-ChildItem -LiteralPath $releaseDir | ForEach-Object {
    Move-Item -LiteralPath $_.FullName -Destination (Join-Path $pluginsUnicode $_.Name) -Force
  }

  Invoke-FileDownload -Uri $nsis_tauri_utils -OutFile ".\nsis_tauri_utils.dll"
  Move-Item -LiteralPath ".\nsis_tauri_utils.dll" -Destination (Join-Path $pluginsUnicode "nsis_tauri_utils.dll") -Force

  New-Item -ItemType Directory -Path $tauriCache -Force | Out-Null
  $destNsis = Join-Path $tauriCache "NSIS"
  $destWix = Join-Path $tauriCache "WixTools314"
  if (Test-Path $destNsis) { Remove-Item -LiteralPath $destNsis -Recurse -Force }
  if (Test-Path $destWix) { Remove-Item -LiteralPath $destWix -Recurse -Force }

  Move-Item -LiteralPath ".\NSIS" -Destination $destNsis
  Move-Item -LiteralPath ".\WixTools314" -Destination $destWix

  Write-Host "rm temp dir"
}
finally {
  Pop-Location
  if (Test-Path $temp) {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "done"
Write-Host "NSIS: $(Join-Path $tauriCache 'NSIS')"
Write-Host "WiX:  $(Join-Path $tauriCache 'WixTools314')"
