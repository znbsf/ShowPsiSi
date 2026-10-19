# CI/build-time PowerShell only. The generated GUI package has no script runtime prerequisite.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BuildBin,
    [Parameter(Mandatory)][string]$Qt,
    [Parameter(Mandatory)][string]$Sdk,
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][string]$LicenseBundle,
    [Parameter(Mandatory)][string]$SourceCommit,
    [Parameter(Mandatory)][string]$Python,
    [ValidateSet('Prerequisite', 'AppLocal')][string]$CrtMode = 'Prerequisite'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false
if (-not $IsWindows) { throw 'Windows x64 packaging is required.' }
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
function Require-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required package input missing: $Path" }
}
function Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed: $LASTEXITCODE" }
}
if ($SourceCommit -notmatch '^[0-9a-f]{40}$') { throw 'SourceCommit must be a full Git commit ID.' }
$ActualCommit = (& git -C $Root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $ActualCommit -ne $SourceCommit) { throw 'Source commit does not match the checkout.' }
if (Test-Path -LiteralPath $Output) { throw "Output must not exist; refusing to reuse stale staging: $Output" }
$Output = [IO.Path]::GetFullPath($Output)
$Bin = Join-Path $Output 'bin'
foreach ($File in @('showpsisi-core.exe', 'showpsisi-qt.exe')) { Require-File (Join-Path $BuildBin $File) }
Require-File (Join-Path $BuildBin 'showpsisi-build.json')
$Record = Get-Content -LiteralPath (Join-Path $BuildBin 'showpsisi-build.json') -Raw | ConvertFrom-Json
Checked $Python @((Join-Path $PSScriptRoot 'ci/static_dependencies.py'), '--root', $Root, '--record', (Join-Path $BuildBin 'showpsisi-build.json'))
if ($Record.source_commit -ne $SourceCommit -or $Record.source_root -ne $Root) { throw 'Production build record does not match source checkout.' }
foreach ($File in @('showpsisi-core.exe', 'showpsisi-qt.exe')) {
    if ((Get-FileHash -LiteralPath (Join-Path $BuildBin $File) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Record.production.$File) { throw "Production input changed after build: $File" }
}
& (Join-Path $PSScriptRoot 'setup-tsduck.ps1') -Sdk $Sdk -ValidateOnly
Require-File (Join-Path $Qt 'bin/windeployqt.exe')
New-Item -ItemType Directory -Path $Bin -Force | Out-Null
# Explicit allowlist: never copy the build tree or the cancellation-test core.
foreach ($File in @('showpsisi-core.exe', 'showpsisi-qt.exe')) { Copy-Item -LiteralPath (Join-Path $BuildBin $File) -Destination $Bin }
foreach ($File in @('tsduck.dll', 'tscore.dll')) { Copy-Item -LiteralPath (Join-Path $Sdk "bin/$File") -Destination $Bin }
$RuntimeData = @(Get-ChildItem -Path "$Sdk/bin/ts*.xml", "$Sdk/bin/ts*.names" -File)
foreach ($File in $RuntimeData) { Copy-Item -LiteralPath $File.FullName -Destination $Bin }
foreach ($File in @('tsduck.tables.model.xml', 'tsduck.dtv.names', 'tscore.time.xml', 'tscore.ip.names')) { Require-File (Join-Path $Bin $File) }
Checked (Join-Path $Qt 'bin/windeployqt.exe') @('--release', '--no-translations', '--no-compiler-runtime', '--no-system-d3d-compiler', '--skip-plugin-types', 'qmltooling', '--qmldir', (Join-Path $Root 'ui/qt'), '--dir', $Bin, (Join-Path $Bin 'showpsisi-qt.exe'))
Require-File (Join-Path $Bin 'platforms/qwindows.dll')
# Some kit scanners include offscreen by default; it belongs only in the test copy.
$Offscreen = Join-Path $Bin 'platforms/qoffscreen.dll'
if (Test-Path -LiteralPath $Offscreen) { Remove-Item -LiteralPath $Offscreen }
# The default avoids redistributing Microsoft's runtime until distributor rights
# are reviewed. The user installs the official x64 VC Redistributable separately.
$CrtIdentity = 'Microsoft Visual C++ 2015-2022 x64 Redistributable prerequisite'
if ($CrtMode -eq 'AppLocal') {
    $VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    Require-File $VsWhere
    $Vs = (& $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
    $Crt = Get-ChildItem -Path "$Vs/VC/Redist/MSVC/*/x64/Microsoft.VC143.CRT" -Directory | Sort-Object FullName | Select-Object -Last 1
    if (-not $Crt) { throw 'VS 2022 release x64 CRT redistributables unavailable.' }
    Copy-Item -Path "$($Crt.FullName)/*.dll" -Destination $Bin
    foreach ($Name in @('MSVCP140.dll', 'MSVCP140_1.dll', 'VCRUNTIME140.dll', 'VCRUNTIME140_1.dll')) { Require-File (Join-Path $Bin $Name) }
    $CrtIdentity = "$($Crt.Parent.Parent.Name)/x64/$($Crt.Name)"
}
'{"schema_version":1,"resource_root":"..","scope":"qt-core"}' | Set-Content -LiteralPath (Join-Path $Bin 'showpsisi-portable.json') -Encoding utf8NoBOM
@'
[Paths]
Prefix=.
Plugins=.
QmlImports=qml
'@ | Set-Content -LiteralPath (Join-Path $Bin 'qt.conf') -Encoding utf8NoBOM
foreach ($File in @('api/tools.json', 'extensions/demo.json', 'references/standards.json', 'references/satellites.json', 'samples/generated/lab.ts', 'samples/generated/lab.manifest.json', 'assets/icons/showpsisi.svg', 'assets/icons/showpsisi-256.png', 'assets/icons/showpsisi.ico')) {
    $Source = Join-Path $Root $File
    Require-File $Source
    $Target = Join-Path $Output $File
    New-Item -ItemType Directory -Force (Split-Path $Target) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target
}
Copy-Item -LiteralPath (Join-Path $Root 'LICENSE') -Destination $Output
Copy-Item -Path (Join-Path $PSScriptRoot 'portable/*') -Destination $Output
# A license bundle is deliberately explicit. A green compile is not clearance.
foreach ($File in @('THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt', 'redistribution-review.json')) { Require-File (Join-Path $LicenseBundle $File); Copy-Item -LiteralPath (Join-Path $LicenseBundle $File) -Destination $Output }
if (-not (Test-Path -LiteralPath (Join-Path $LicenseBundle 'licenses') -PathType Container)) { throw 'License texts directory missing.' }
Copy-Item -LiteralPath (Join-Path $LicenseBundle 'licenses') -Destination $Output -Recurse
if (Test-Path -LiteralPath (Join-Path $LicenseBundle 'source-index.json') -PathType Leaf) { Copy-Item -LiteralPath (Join-Path $LicenseBundle 'source-index.json') -Destination $Output }
if (Test-Path -LiteralPath (Join-Path $LicenseBundle 'sources') -PathType Container) { Copy-Item -LiteralPath (Join-Path $LicenseBundle 'sources') -Destination $Output -Recurse }
& (Join-Path $PSScriptRoot 'prepare-portable-sources.ps1') -LicenseBundle $LicenseBundle -Cache (Join-Path $Root '.deps/portable-sources') -Output (Join-Path $Output 'sources')
$SourceIndex = Get-Content -LiteralPath (Join-Path $LicenseBundle 'source-index.json') -Raw | ConvertFrom-Json
$QtArchives = @()
foreach ($Archive in @(Get-ChildItem -LiteralPath (Join-Path $Root '.deps/qt-archives') -File)) {
    $QtArchives += @{ name = $Archive.Name; sha256 = (Get-FileHash -LiteralPath $Archive.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
}
if ($QtArchives.Count -eq 0) { throw 'Original Qt download archive identities missing; use CI dependency setup with --keep.' }
$QtConfiguration = @{}
foreach ($Relative in @('mkspecs/qconfig.pri', 'mkspecs/qmodule.pri', 'include/QtCore/qconfig.h')) {
    $ConfigPath = Join-Path $Qt $Relative
    Require-File $ConfigPath
    $QtConfiguration[$Relative] = @{
        sha256 = (Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash.ToLowerInvariant()
        content = Get-Content -LiteralPath $ConfigPath -Raw
    }
}
$QtCoreRelocation = @{
    installed_kit_sha256 = (Get-FileHash -LiteralPath (Join-Path $Qt 'bin/Qt6Core.dll') -Algorithm SHA256).Hash.ToLowerInvariant()
    deployed_sha256 = (Get-FileHash -LiteralPath (Join-Path $Bin 'Qt6Core.dll') -Algorithm SHA256).Hash.ToLowerInvariant()
}
$Metadata = @{
    source_commit = $SourceCommit
    application_version = $Record.application_version
    static_dependencies = $Record.static_dependencies
    qt_version = '6.7.3'; qt_kit = 'win64_msvc2019_64'
    qt_origin = 'https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_673/'
    tsduck_version = '3.45-4798'
    tsduck_origin = 'https://github.com/tsduck/tsduck/releases/download/v3.45-4798/TSDuck-Win64-3.45-4798.exe'
    tsduck_archive_sha256 = 'd1d1dae29e82d9c9dde8380fd562d2995e6cb702706031fa9574ebc06092bc57'
    crt_mode = $CrtMode; crt_identity = $CrtIdentity
    crt_minimum_version = '14.51.36231.0'
    crt_minimum_evidence = 'https://github.com/tsduck/tsduck/actions/runs/34712521690/job/103603758775'
    cmake_version = ((& cmake --version) | Select-Object -First 1)
    toolchain = 'Visual Studio 2022, MSVC x64 Release'
    application_compiler_version = $Record.compiler_version
    tsduck_upstream_linker_toolset = '14.51.36231'
    crt_support_rule = 'https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170'
    qt_download_archives = $QtArchives
    qt_source_archives = $SourceIndex.qt_source_archives
    qt_build_configuration = $QtConfiguration
    qt_core_relocation = $QtCoreRelocation
    windows_prerequisite = 'Windows 10 version 1809 (build 17763) or newer / Windows 11, native x64, system D3Dcompiler_47.dll'
    native_windows_desktop_verified = $false
}
$Metadata | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Output 'build-information.json') -Encoding utf8NoBOM
Checked $Python @((Join-Path $PSScriptRoot 'ci/portable_checks.py'), 'manifest', '--package', $Output)
Write-Host "Staged candidate: $Output. Validation and license review must pass before archive upload."
