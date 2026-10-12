# 对真实构建步骤注入隔离命令替身；不安装依赖、不打包、不复制或删除文件。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$source = Get-Content -LiteralPath (Join-Path $projectRoot 'python-sidecar\build_sidecar.ps1') -Raw -Encoding UTF8
$steps = $source.Substring($source.IndexOf('# 3) Install dependencies'))
$steps = $steps.Replace('& $pythonExe', 'Invoke-TestPython')
function Push-Location { }
function Pop-Location { }
function Test-Path { return $true }
function New-Item { }
function Copy-Item { $script:copied = $true }
function rustc { 'host: x86_64-pc-windows-msvc'; $global:LASTEXITCODE = 0 }
function Invoke-TestPython {
    $script:calls++
    $global:LASTEXITCODE = if ($script:calls -eq $script:failAt) { 17 } else { 0 }
}
foreach ($failure in 1..4) {
    $script:failAt = $failure
    $script:calls = 0
    $script:copied = $false
    $caught = $false
    try { & ([scriptblock]::Create($steps)) }
    catch { $caught = $true }
    if (-not $caught -or $script:copied -or $script:calls -ne $failure) {
        throw "Failed build stage $failure did not stop before copying the old executable"
    }
}
Write-Host 'Sidecar failure guards: 4 passed, 0 failed'
exit 0
