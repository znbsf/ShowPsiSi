$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
if (-not $IsWindows) { throw 'This environment script requires PowerShell 7 on Windows.' }
$VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
if (-not (Test-Path -LiteralPath $VsWhere -PathType Leaf)) { throw 'Visual Studio 2022 Build Tools with the C++ x64 tools and Windows SDK are required for TSDuck 3.45 (C++20).' }
$Vs = & $VsWhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $Vs) { throw 'No Visual Studio 2022 C++ x64 toolchain found. TSDuck 3.45 does not support the old VS 2019 build route.' }
$devBatch = Join-Path $Vs 'VC/Auxiliary/Build/vcvars64.bat'
if (-not (Test-Path -LiteralPath $devBatch -PathType Leaf)) { throw "MSVC x64 environment script missing: $devBatch" }
$CompilerEnvironment = cmd.exe /d /s /c "`"$devBatch`" >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Visual Studio 2022 x64 environment initialization failed.' }
$CompilerEnvironment | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
$env:RUSTUP_HOME = Join-Path $ProjectRoot '.deps\rustup'
$env:CARGO_HOME = Join-Path $ProjectRoot '.deps\cargo'
# Qt's official 6.7.3 kit keeps this name; VS 2022 consumes its compatible ABI.
if (-not $env:QT_ROOT) { $env:QT_ROOT = Join-Path $ProjectRoot '.deps\Qt\6.7.3\msvc2019_64' }
if (-not $env:TSDUCK_ROOT) { $env:TSDUCK_ROOT = Join-Path $ProjectRoot '.deps\TSDuck-3.45-4798' }
& "$PSScriptRoot/setup-tsduck.ps1" -Sdk $env:TSDUCK_ROOT -ValidateOnly
$env:TSPLUGINS_PATH = Join-Path $env:TSDUCK_ROOT 'bin'
$env:PATH = "$env:CARGO_HOME\bin;$env:QT_ROOT\bin;$env:TSDUCK_ROOT\bin;$env:PATH"
$env:SHOWPSISI_ROOT = $ProjectRoot
$env:VSLANG = '1033'
$env:SHOWPSISI_CORE = Join-Path $ProjectRoot 'build\bin\showpsisi-core.exe'
