param(
    [switch]$CoreOnly,
    [switch]$SkipTauri,
    [string]$BuildDirectory = 'build'
)
# Tauri's packaging route currently expects the native engine in build/bin.
if ($BuildDirectory -ne 'build' -and -not ($CoreOnly -or $SkipTauri)) {
    throw 'A custom BuildDirectory requires -CoreOnly or -SkipTauri.'
}
. "$PSScriptRoot\env.ps1"
Push-Location $ProjectRoot
try {
    $BuildDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($BuildDirectory)
    $qtFlag = if ($CoreOnly) { 'OFF' } else { 'ON' }
    cmake --fresh -S . -B "$BuildDirectory" -G Ninja '-DCMAKE_CXX_COMPILER=cl.exe' -DCMAKE_BUILD_TYPE=Release "-DCMAKE_PREFIX_PATH=$env:QT_ROOT" "-DTSDUCK_ROOT=$env:TSDUCK_ROOT" "-DBUILD_QT_UI=$qtFlag"
    if ($LASTEXITCODE) { throw 'CMake configure failed' }
    cmake --build "$BuildDirectory" --parallel 4
    if ($LASTEXITCODE) { throw 'C++ build failed' }
    # XML models and name databases are part of native decoding, not optional
    # documentation. Keep both TSCore and TSDuck data beside the two copied DLLs.
    Copy-Item -Path "$env:TSDUCK_ROOT/bin/ts*.xml", "$env:TSDUCK_ROOT/bin/ts*.names" -Destination (Join-Path $BuildDirectory 'bin')
    if (-not $CoreOnly -and -not $SkipTauri) {
        cargo build --release --manifest-path ui/tauri/src-tauri/Cargo.toml -j 4
        if ($LASTEXITCODE) { throw 'Tauri build failed' }
    }
} finally { Pop-Location }
