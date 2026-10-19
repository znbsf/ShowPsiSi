# Build-time only. Wrap the exact cleared Qt/core payload in a per-user installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Package,
    [Parameter(Mandatory)][string]$Validation,
    [Parameter(Mandatory)][string]$PrerequisiteDirectory,
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][string]$Work,
    [Parameter(Mandatory)][string]$Python,
    [string]$InnoCompiler,
    [switch]$CreateUpgradeFixture
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false
if (-not $IsWindows) { throw 'Windows installer compilation requires Windows.' }
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Output = [IO.Path]::GetFullPath($Output)
$Work = [IO.Path]::GetFullPath($Work)
$Package = [IO.Path]::GetFullPath($Package)
if (Test-Path -LiteralPath $Output) { throw "Refusing stale installer output: $Output" }
if (Test-Path -LiteralPath $Work) { throw "Refusing stale installer work directory: $Work" }
if (-not $InnoCompiler) { $InnoCompiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe' }
if (-not (Test-Path -LiteralPath $InnoCompiler -PathType Leaf)) { throw 'Install official Inno Setup 6.3+ or pass -InnoCompiler. CI uses the hosted image tool.' }
$CompilerInfo = [Diagnostics.FileVersionInfo]::GetVersionInfo($InnoCompiler)
$CompilerVersion = '{0}.{1}.{2}.{3}' -f $CompilerInfo.FileMajorPart, $CompilerInfo.FileMinorPart, $CompilerInfo.FileBuildPart, $CompilerInfo.FilePrivatePart
if ([Version]$CompilerVersion -lt [Version]'6.3.0.0' -or [Version]$CompilerVersion -ge [Version]'7.0.0.0') { throw "Unverified Inno compiler version: $CompilerVersion" }
$Project = Get-Content -LiteralPath (Join-Path $Root 'CMakeLists.txt') -Raw
$Match = [regex]::Match($Project, 'project\(ShowPsiSi VERSION ([0-9]+\.[0-9]+\.[0-9]+) ')
if (-not $Match.Success) { throw 'Unable to read canonical CMake project version.' }
$Version = $Match.Groups[1].Value
$SourceCommit = (& git -C $Root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $SourceCommit -notmatch '^[a-f0-9]{40}$') { throw 'Current checkout commit is unavailable.' }
& git -C $Root diff --quiet HEAD --
if ($LASTEXITCODE -ne 0) { throw 'Installer wrapping requires a clean tracked checkout matching the staged source commit.' }
$RuntimeMetadata = Join-Path $PrerequisiteDirectory 'vc-runtime.json'
$Runtime = Get-Content -LiteralPath $RuntimeMetadata -Raw | ConvertFrom-Json
$RuntimeFile = Join-Path $PrerequisiteDirectory 'vc_redist.x64.exe'
if ((Get-FileHash -LiteralPath $RuntimeFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Runtime.sha256) { throw 'Microsoft prerequisite bytes changed after verification.' }
$Signature = Get-AuthenticodeSignature -LiteralPath $RuntimeFile
if ($Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
    $Signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)' -or
    $Signature.SignerCertificate.Thumbprint -ne $Runtime.signer_thumbprint) { throw 'Microsoft prerequisite Authenticode identity is not verified.' }
$Info = [Diagnostics.FileVersionInfo]::GetVersionInfo($RuntimeFile)
$RuntimeVersion = '{0}.{1}.{2}.{3}' -f $Info.FileMajorPart, $Info.FileMinorPart, $Info.FileBuildPart, $Info.FilePrivatePart
if ($RuntimeVersion -ne $Runtime.version -or [Version]$RuntimeVersion -lt [Version]'14.51.36231.0') { throw 'Microsoft prerequisite version is not verified.' }
New-Item -ItemType Directory -Path $Output, $Work | Out-Null
function Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed: $LASTEXITCODE" }
}
$Checker = Join-Path $PSScriptRoot 'ci/installer_checks.py'
$Generated = Join-Path $Work 'release'
Checked $Python @($Checker, 'prepare', '--package', $Package, '--artifacts', $Validation, '--prerequisite', $RuntimeMetadata, '--version', $Version, '--source-commit', $SourceCommit, '--generated', $Generated, '--output', $Output)
Checked $InnoCompiler @('/Qp', (Join-Path $Generated 'ShowPsiSi.iss'))
$Installer = Join-Path $Output "ShowPsiSi-$Version-windows-x64-setup.exe"
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { throw 'Inno did not produce the exact required installer asset.' }
$Hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $([IO.Path]::GetFileName($Installer))" | Set-Content -LiteralPath (Join-Path $Output 'SHA256SUMS') -Encoding ascii
$Record = Get-Content -LiteralPath (Join-Path $Generated 'installer-inputs.json') -Raw | ConvertFrom-Json -AsHashtable
$Record['installer_sha256'] = $Hash
$Record['installer_bytes'] = (Get-Item -LiteralPath $Installer).Length
$Record['inno_setup_version'] = $CompilerVersion
$Record['inno_compiler_sha256'] = (Get-FileHash -LiteralPath $InnoCompiler -Algorithm SHA256).Hash.ToLowerInvariant()
$Record['installer_source_sha256'] = (Get-FileHash -LiteralPath (Join-Path $Generated 'ShowPsiSi.iss') -Algorithm SHA256).Hash.ToLowerInvariant()
$Record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Output 'installer-build.json') -Encoding utf8NoBOM
if ($CreateUpgradeFixture) {
    $FixtureGenerated = Join-Path $Work 'previous'
    $FixtureOutput = Join-Path $Work 'test-only'
    New-Item -ItemType Directory -Path $FixtureOutput | Out-Null
    Checked $Python @($Checker, 'prepare', '--package', $Package, '--artifacts', $Validation, '--prerequisite', $RuntimeMetadata, '--version', $Version, '--source-commit', $SourceCommit, '--generated', $FixtureGenerated, '--output', $FixtureOutput, '--upgrade-fixture')
    Checked $InnoCompiler @('/Qp', (Join-Path $FixtureGenerated 'ShowPsiSi.iss'))
}
Write-Host "Built unsigned installer candidate: $Installer. Install/upgrade/uninstall smoke is still required."
