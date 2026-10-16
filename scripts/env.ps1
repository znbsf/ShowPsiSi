$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$devBatch = 'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path $devBatch)) { throw 'MSVC 2019 Build Tools are required for the pinned Qt SDK' }
cmd.exe /d /s /c "`"$devBatch`" >nul && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
$env:RUSTUP_HOME = Join-Path $ProjectRoot '.deps\rustup'
$env:CARGO_HOME = Join-Path $ProjectRoot '.deps\cargo'
$env:QT_ROOT = Join-Path $ProjectRoot '.deps\Qt\6.7.3\msvc2019_64'
$env:PATH = "$env:CARGO_HOME\bin;$env:QT_ROOT\bin;D:\msys64\ucrt64\bin;$env:PATH"
$env:SHOWPSISI_ROOT = $ProjectRoot
$env:VSLANG = '1033'
$env:SHOWPSISI_CORE = Join-Path $ProjectRoot 'build\bin\showpsisi-core.exe'
