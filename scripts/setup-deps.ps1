# Reproduce local SDK setup. The pre-existing TSDuck and MSVC developer installs are prerequisites.
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path $PSScriptRoot -Parent
Push-Location $ProjectRoot
try {
    if(-not (Test-Path .deps\py\Scripts\python.exe)) { python -m venv .deps\py }
    & .deps\py\Scripts\python.exe -m pip install 'aqtinstall==3.3.0' 'psutil==7.2.2'
    if($LASTEXITCODE){throw 'Python dependency install failed'}
    if(-not (Test-Path .deps\Qt\6.7.3\msvc2019_64\bin\qmake.exe)) {
        & .deps\py\Scripts\python.exe -m aqt install-qt windows desktop 6.7.3 win64_msvc2019_64 --archives qtbase qtdeclarative qtshadertools --outputdir .deps\Qt
        if($LASTEXITCODE){throw 'Qt SDK install failed'}
    }
    $env:RUSTUP_HOME="$ProjectRoot\.deps\rustup";$env:CARGO_HOME="$ProjectRoot\.deps\cargo"
    if(-not (Test-Path .deps\cargo\bin\cargo.exe)) {
        New-Item -ItemType Directory -Force .deps\downloads | Out-Null
        $url='https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe'
        $digest=(Invoke-WebRequest "$url.sha256").Content.Split(' ')[0].Trim()
        Invoke-WebRequest $url -OutFile .deps\downloads\rustup-init.exe.part
        if((Get-FileHash .deps\downloads\rustup-init.exe.part -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest){throw 'Rust bootstrap SHA-256 mismatch'}
        Move-Item -LiteralPath .deps\downloads\rustup-init.exe.part -Destination .deps\downloads\rustup-init.exe -Force
        & .deps\downloads\rustup-init.exe -y --no-modify-path --profile minimal --default-toolchain 1.99.1
        if($LASTEXITCODE){throw 'Rust install failed'}
    }
} finally { Pop-Location }
