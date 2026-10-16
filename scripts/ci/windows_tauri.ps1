# Compile/test evidence only: this does not launch WebView2, a browser, or an installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Setup', 'Test', 'Build', 'Diagnostics')]
    [string]$Phase
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false
if (-not $IsWindows) { throw 'This script requires a Windows x64 runner with Visual Studio 2022.' }

$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$Artifacts = Join-Path $Root 'artifacts/windows-tauri'
$Target = Join-Path $Root 'build/tauri-windows'
$Manifest = Join-Path $Root 'ui/tauri/src-tauri/Cargo.toml'
$Toolchain = '1.99.1-x86_64-pc-windows-msvc'
$Binary = Join-Path $Target 'release/showpsisi-tauri.exe'
$env:CARGO_TERM_COLOR = 'never'
$env:RUST_BACKTRACE = '1'
New-Item -ItemType Directory -Force $Artifacts | Out-Null
Start-Transcript -Path (Join-Path $Artifacts "$Phase.log") -Force | Out-Null

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments, [string]$Log = '')
    Write-Host "> $Program $($Arguments -join ' ')"
    if ($Log) {
        & $Program @Arguments 2>&1 | Tee-Object -FilePath $Log | ForEach-Object { Write-Host $_ }
    } else {
        & $Program @Arguments | ForEach-Object { Write-Host $_ }
    }
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required file missing: $Path" }
}

function Read-TestSummary([string]$Text) {
    # A green cargo invocation with zero tests/ignored tests is not regression proof.
    $MatchesFound = [regex]::Matches($Text, 'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out;')
    if ($MatchesFound.Count -ne 1) { throw 'Expected exactly one complete Rust unit-test summary.' }
    $Counts = $MatchesFound[0].Groups
    if ([int]$Counts[1].Value -lt 1 -or [int]$Counts[2].Value -ne 0 -or
        [int]$Counts[3].Value -ne 0 -or [int]$Counts[4].Value -ne 0 -or [int]$Counts[5].Value -ne 0) {
        throw 'Rust tests must execute at least one case, with no failed, ignored, measured, or filtered cases.'
    }
    return [int]$Counts[1].Value
}

Push-Location $Root
try {
    Write-Host "Phase: $Phase; OS: $([Environment]::OSVersion); PowerShell: $($PSVersionTable.PSVersion)"
    Write-Host "Runner image: $env:ImageOS $env:ImageVersion"
    switch ($Phase) {
        'Setup' {
            # Both are tracked repository assets. tauri-build needs the ICO even
            # with bundle.active=false; its Windows resource step invokes rc.exe.
            foreach ($Name in @('Cargo.toml', 'Cargo.lock', 'icons/icon.ico', 'icons/icon.png')) {
                Assert-File (Join-Path $Root "ui/tauri/src-tauri/$Name")
            }
            $VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
            Assert-File $VsWhere
            $Vs = & $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
            if ($LASTEXITCODE -ne 0 -or -not $Vs) { throw 'Hosted runner is missing the Visual Studio C++ toolchain.' }
            Invoke-Checked $VsWhere @('-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-format', 'json')
            # Use rustup's official versioned distribution, without changing its default.
            Invoke-Checked 'rustup' @('toolchain', 'install', $Toolchain, '--profile', 'minimal')
            Invoke-Checked 'rustc' @("+$Toolchain", '--version', '--verbose')
            Invoke-Checked 'cargo' @("+$Toolchain", '--version', '--verbose')
        }
        'Test' {
            $Log = Join-Path $Artifacts 'cargo-test.log'
            Invoke-Checked 'cargo' @("+$Toolchain", 'test', '--locked', '--release', '--manifest-path', $Manifest, '--target-dir', $Target, '--bin', 'showpsisi-tauri', '--', '--nocapture') $Log
            $Passed = Read-TestSummary (Get-Content -LiteralPath $Log -Raw)
            @{ passed = $Passed; failed = 0; ignored = 0; filtered = 0; scope = 'Rust unit tests; no GUI or real browser launch' } |
                ConvertTo-Json | Set-Content (Join-Path $Artifacts 'test-result.json') -Encoding utf8
        }
        'Build' {
            Invoke-Checked 'cargo' @("+$Toolchain", 'build', '--locked', '--release', '--manifest-path', $Manifest, '--target-dir', $Target, '--bin', 'showpsisi-tauri') (Join-Path $Artifacts 'cargo-build.log')
            Assert-File $Binary
            Copy-Item -LiteralPath $Binary -Destination (Join-Path $Artifacts 'showpsisi-tauri.exe')
            $Commit = & git rev-parse HEAD
            if ($LASTEXITCODE -ne 0) { throw 'Could not record the checked-out source commit.' }
            $Inputs = @{}
            foreach ($Name in @('ui/tauri/src-tauri/Cargo.lock', 'ui/tauri/src-tauri/src/main.rs', 'ui/tauri/web/app.js', 'ui/tauri/web/style.css', 'ui/tauri/src-tauri/icons/icon.ico')) {
                $Inputs[$Name] = (Get-FileHash -LiteralPath (Join-Path $Root $Name) -Algorithm SHA256).Hash.ToLowerInvariant()
            }
            @{
                checked_out_commit = $Commit; source_head_sha = $env:SOURCE_HEAD_SHA
                toolchain = $Toolchain; profile = 'release'; locked_dependencies = $true
                binary = 'showpsisi-tauri.exe'; bytes = (Get-Item -LiteralPath $Binary).Length
                sha256 = (Get-FileHash -LiteralPath $Binary -Algorithm SHA256).Hash.ToLowerInvariant()
                inputs_sha256 = $Inputs
                scope = 'Windows compilation and Rust unit tests only; not a standalone distribution, WebView2 interaction, OS browser launch, or installer validation'
            } | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Artifacts 'build-evidence.json') -Encoding utf8
        }
        'Diagnostics' {
            # Keep targeted tool/resource/dependency diagnostics, never the whole environment.
            foreach ($Command in @('rustup.exe', 'rustc.exe', 'cargo.exe')) {
                Get-Command $Command -ErrorAction SilentlyContinue | Select-Object Name, Source | Format-Table | Out-String | Write-Host
            }
            $VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
            if (Test-Path -LiteralPath $VsWhere) {
                $Vs = & $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
                if ($Vs -and (Test-Path -LiteralPath $Binary)) {
                    $Dumpbin = Get-ChildItem "$Vs/VC/Tools/MSVC/*/bin/Hostx64/x64/dumpbin.exe" -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1
                    if ($Dumpbin) { Invoke-Checked $Dumpbin.FullName @('/HEADERS', '/DEPENDENTS', $Binary) }
                }
            }
            Get-ChildItem -Path "$Target/release/build/showpsisi-tauri-*/output" -ErrorAction SilentlyContinue | ForEach-Object {
                Write-Host "Tauri build-script output: $($_.FullName)"
                Get-Content -LiteralPath $_.FullName | Write-Host
            }
        }
    }
} finally {
    Pop-Location
    Stop-Transcript | Out-Null
}
