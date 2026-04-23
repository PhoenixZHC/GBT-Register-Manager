#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$bundleRoot = Join-Path $projectRoot "src-tauri\target\release\bundle"

if (-not (Test-Path $bundleRoot)) {
  Write-Host "[rename-bundles] bundle directory not found: $bundleRoot (skip)"
  exit 0
}

function Rename-BundleFile {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$NewName
  )
  $dir = Split-Path -Parent $Path
  $target = Join-Path $dir $NewName
  if ((Resolve-Path -LiteralPath $Path).Path -ieq $target) {
    Write-Host "[rename-bundles] already named: $NewName"
    return
  }
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Force
  }
  Move-Item -LiteralPath $Path -Destination $target -Force
  Write-Host "[rename-bundles] $(Split-Path -Leaf $Path)  ->  $NewName"
}

# MSI: {productName}_{version}_x64_{lang}.msi  ->  {productName}_{version}.msi
$msiDir = Join-Path $bundleRoot "msi"
if (Test-Path $msiDir) {
  Get-ChildItem -LiteralPath $msiDir -File -Filter *.msi | ForEach-Object {
    $new = $_.Name -replace "_x64_[A-Za-z\-]+(?=\.msi$)", ""
    Rename-BundleFile -Path $_.FullName -NewName $new
  }
  Get-ChildItem -LiteralPath $msiDir -File -Filter *.msi.zip | ForEach-Object {
    $new = $_.Name -replace "_x64_[A-Za-z\-]+(?=\.msi\.zip$)", ""
    Rename-BundleFile -Path $_.FullName -NewName $new
  }
  Get-ChildItem -LiteralPath $msiDir -File -Filter *.msi.zip.sig | ForEach-Object {
    $new = $_.Name -replace "_x64_[A-Za-z\-]+(?=\.msi\.zip\.sig$)", ""
    Rename-BundleFile -Path $_.FullName -NewName $new
  }
}

# NSIS: {productName}_{version}_x64-setup.exe  ->  {productName}_{version}-setup.exe
$nsisDir = Join-Path $bundleRoot "nsis"
if (Test-Path $nsisDir) {
  Get-ChildItem -LiteralPath $nsisDir -File -Filter *.exe | ForEach-Object {
    $new = $_.Name -replace "_x64(?=-setup\.exe$)", ""
    Rename-BundleFile -Path $_.FullName -NewName $new
  }
  Get-ChildItem -LiteralPath $nsisDir -File -Filter *.nsis.zip | ForEach-Object {
    $new = $_.Name -replace "_x64(?=-setup\.nsis\.zip$)", ""
    Rename-BundleFile -Path $_.FullName -NewName $new
  }
  Get-ChildItem -LiteralPath $nsisDir -File -Filter *.nsis.zip.sig | ForEach-Object {
    $new = $_.Name -replace "_x64(?=-setup\.nsis\.zip\.sig$)", ""
    Rename-BundleFile -Path $_.FullName -NewName $new
  }
}

Write-Host "[rename-bundles] done."
