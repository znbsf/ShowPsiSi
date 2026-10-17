# Build-time source provision only: fixed official Qt archives, no execution.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$LicenseBundle,
    [Parameter(Mandatory)][string]$Cache,
    [Parameter(Mandatory)][string]$Output
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Pins = @{
    qtbase = '8ccbb9ab055205ac76632c9eeddd1ed6fc66936fc56afc2ed0fd5d9e23da3097'
    qtdeclarative = '937b70e441abf5bc4e50d44d26610e2714a28514acf3885cd36116cd610b9875'
    qtsvg = '40142cb71fb1e07ad612bc361b67f5d54cd9367f9979ae6b86124a064deda06b'
}
$Index = Get-Content -LiteralPath (Join-Path $LicenseBundle 'source-index.json') -Raw | ConvertFrom-Json
$Archives = @($Index.qt_source_archives)
if ($Archives.Count -ne 3 -or @($Archives.module | Sort-Object -Unique).Count -ne 3) { throw 'Expected exactly the three reviewed Qt source archives.' }
# Validate the complete set before any download or copy. URLs cannot be redirected
# by an arbitrary manifest entry; source changes require explicit pin updates.
foreach ($Archive in $Archives) {
    $Name = "$($Archive.module)-everywhere-src-6.7.3.tar.xz"
    $Url = "https://download.qt.io/archive/qt/6.7/6.7.3/submodules/$Name"
    if (-not $Pins.ContainsKey($Archive.module) -or $Archive.filename -cne $Name -or
        $Archive.url -cne $Url -or $Archive.sha256 -cne $Pins[$Archive.module]) {
        throw "Qt source identity differs from reviewed pins: $($Archive.module)"
    }
}
New-Item -ItemType Directory -Force $Cache, $Output | Out-Null
foreach ($Archive in $Archives) {
    $Cached = Join-Path $Cache $Archive.filename
    if (-not (Test-Path -LiteralPath $Cached -PathType Leaf)) {
        Invoke-WebRequest -Uri $Archive.url -OutFile "$Cached.part" -MaximumRetryCount 3 -RetryIntervalSec 5
        if ((Get-FileHash -LiteralPath "$Cached.part" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Archive.sha256) {
            throw "Qt source download SHA-256 mismatch: $($Archive.filename)"
        }
        Move-Item -LiteralPath "$Cached.part" -Destination $Cached
    }
    if ((Get-FileHash -LiteralPath $Cached -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Archive.sha256) {
        throw "Qt source cache SHA-256 mismatch: $($Archive.filename). Remove the corrupt cache file and retry."
    }
    $Target = Join-Path $Output $Archive.filename
    if (Test-Path -LiteralPath $Target) { throw "Refusing to overwrite staged source archive: $Target" }
    Copy-Item -LiteralPath $Cached -Destination $Target
    if ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Archive.sha256) {
        throw "Staged Qt source SHA-256 mismatch: $($Archive.filename)"
    }
}
Write-Host 'Three pinned Qt source archives verified and staged; this does not complete runtime inventory review.'
