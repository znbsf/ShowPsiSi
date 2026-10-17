# Pinned workspace-only Windows SDK extraction. Requires PowerShell 7 and 7-Zip.
# The official NSIS installer is an archive input only; it is never executed.
[CmdletBinding()]
param(
    [string]$Sdk = (Join-Path (Split-Path $PSScriptRoot -Parent) '.deps/TSDuck-3.45-4798'),
    [string]$Artifacts = '',
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false
$Root = Split-Path $PSScriptRoot -Parent
$Url = 'https://github.com/tsduck/tsduck/releases/download/v3.45-4798/TSDuck-Win64-3.45-4798.exe'
# Identity from the official release asset, not a publisher signature.
$ExpectedHash = 'd1d1dae29e82d9c9dde8380fd562d2995e6cb702706031fa9574ebc06092bc57'

function Assert-Sdk {
    foreach ($Name in @('include/tsduck/tsduck.h', 'include/tscore/tscore.h', 'include/tscore/tsVersion.h',
                       'lib/Release-Win64/tsduck.lib', 'lib/Release-Win64/tscore.lib',
                       'lib/Release-Win64/tsduck.dll', 'lib/Release-Win64/tscore.dll',
                       'bin/tsduck.dll', 'bin/tscore.dll', 'bin/tsp.exe',
                       'bin/tsduck.tables.model.xml', 'bin/tsduck.dtv.names',
                       'bin/tscore.time.xml', 'bin/tscore.ip.names')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Sdk $Name) -PathType Leaf)) {
            throw "TSDuck 3.45-4798 developer SDK incomplete: $Name missing under $Sdk. Run scripts/setup-tsduck.ps1; do not mix old headers or runtime files."
        }
    }
    $VersionHeader = Get-Content (Join-Path $Sdk 'include/tscore/tsVersion.h') -Raw
    foreach ($Define in @('TS_VERSION_MAJOR\s+3\b', 'TS_VERSION_MINOR\s+45\b', 'TS_COMMIT\s+4798\b')) {
        if ($VersionHeader -notmatch $Define) { throw "TSDuck SDK version mismatch under ${Sdk}: expected 3.45-4798 ($Define missing)." }
    }
    foreach ($Name in @('tsduck.dll', 'tscore.dll')) {
        $RuntimeHash = (Get-FileHash -LiteralPath (Join-Path $Sdk "bin/$Name") -Algorithm SHA256).Hash
        $LibraryHash = (Get-FileHash -LiteralPath (Join-Path $Sdk "lib/Release-Win64/$Name") -Algorithm SHA256).Hash
        if ($RuntimeHash -ne $LibraryHash) { throw "TSDuck SDK/runtime mismatch: bin/$Name differs from lib/Release-Win64/$Name under $Sdk." }
    }
}

if (-not $ValidateOnly) {
    if (-not $IsWindows) { throw 'SDK extraction requires a Windows x64 development environment with 7-Zip.' }
    $Downloads = Join-Path $Root '.deps/downloads'
    New-Item -ItemType Directory -Force $Downloads, $Sdk | Out-Null
    $Installer = Join-Path $Downloads 'TSDuck-Win64-3.45-4798.exe'
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
        Invoke-WebRequest -Uri $Url -OutFile "$Installer.part" -MaximumRetryCount 3 -RetryIntervalSec 5
        $DownloadedHash = (Get-FileHash -LiteralPath "$Installer.part" -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($DownloadedHash -ne $ExpectedHash) { throw "Official TSDuck download SHA-256 mismatch: $DownloadedHash" }
        Move-Item -LiteralPath "$Installer.part" -Destination $Installer -Force
    }
    $Hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Artifacts) {
        New-Item -ItemType Directory -Force $Artifacts | Out-Null
        @{ url = $Url; sha256 = $Hash; expected_sha256 = $ExpectedHash } |
            ConvertTo-Json | Set-Content (Join-Path $Artifacts 'tsduck-source.json') -Encoding utf8
    }
    if ($Hash -ne $ExpectedHash) { throw "Official TSDuck asset SHA-256 mismatch: $Hash. Remove the cached download and retry." }
    $SevenZip = (Get-Command 7z.exe -ErrorAction Stop).Source
    # The portable ZIP is runtime-only. NSIS includes the split include/tsduck,
    # include/tscore and lib/Release-Win64 trees needed by C++ applications.
    # https://github.com/tsduck/tsduck/blob/v3.45-4798/pkg/nsis/tsduck.nsi
    & $SevenZip l $Installer
    if ($LASTEXITCODE -ne 0) { throw "7-Zip list failed: $LASTEXITCODE" }
    & $SevenZip x -y "-o$Sdk" $Installer 'bin/*' 'include/*' 'lib/Release-Win64/*' 'LICENSE.txt' 'OTHERS.txt'
    if ($LASTEXITCODE -ne 0) { throw "7-Zip extraction failed: $LASTEXITCODE" }
}
Assert-Sdk
