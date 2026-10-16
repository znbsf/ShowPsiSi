param([switch]$CoreOnly, [switch]$SkipTauri)
. "$PSScriptRoot\env.ps1"
Push-Location $ProjectRoot
try {
    $qtFlag = if ($CoreOnly) { 'OFF' } else { 'ON' }
    cmake --fresh -S . -B build -G Ninja '-DCMAKE_CXX_COMPILER=cl.exe' -DCMAKE_BUILD_TYPE=Release "-DCMAKE_PREFIX_PATH=$env:QT_ROOT" "-DBUILD_QT_UI=$qtFlag"
    if ($LASTEXITCODE) { throw 'CMake configure failed' }
    cmake --build build --parallel 4
    if ($LASTEXITCODE) { throw 'C++ build failed' }
    if (-not $CoreOnly -and -not $SkipTauri) {
        cargo build --release --manifest-path ui/tauri/src-tauri/Cargo.toml -j 4
        if ($LASTEXITCODE) { throw 'Tauri build failed' }
    }
} finally { Pop-Location }
