# Build-time provenance only: downloads but never executes Microsoft's installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Output,
    [string]$MinimumVersion = '14.51.36231.0',
    [string]$Metadata,
    [ValidateSet('Prerequisite', 'AppLocal')][string]$Purpose = 'Prerequisite'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $IsWindows) { throw 'Microsoft Authenticode verification requires Windows.' }
$Output = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw "Refusing stale prerequisite output: $Output" }
New-Item -ItemType Directory -Path $Output | Out-Null
$Official = 'https://aka.ms/vc14/vc_redist.x64.exe'
$Pinned = $null
if ($Metadata) { $Pinned = Get-Content -LiteralPath $Metadata -Raw | ConvertFrom-Json }
$Url = if ($Pinned) { [string]$Pinned.url } else { $Official }
function Assert-MicrosoftUrl([string]$Value) {
    $Uri = [Uri]$Value
    if ($Uri.Scheme -ne 'https' -or $Uri.UserInfo -or $Uri.Port -ne 443 -or
        $Uri.Host -notin @('download.visualstudio.microsoft.com', 'download.microsoft.com')) {
        throw "Unexpected Microsoft prerequisite download destination: $Value"
    }
}
if ($Pinned) { Assert-MicrosoftUrl $Url }
$Target = Join-Path $Output 'vc_redist.x64.exe'
$Response = Invoke-WebRequest -Uri $Url -OutFile $Target -PassThru -MaximumRedirection 5
$FinalUrl = $Response.BaseResponse.RequestMessage.RequestUri.AbsoluteUri
Assert-MicrosoftUrl $FinalUrl
$Hash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Pinned -and $Hash -ne $Pinned.sha256) { throw 'Pinned Microsoft prerequisite SHA-256 changed.' }
$Signature = Get-AuthenticodeSignature -LiteralPath $Target
if ($Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
    $Signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') {
    throw 'The prerequisite must have a valid Microsoft Corporation Authenticode signature.'
}
$Info = [Diagnostics.FileVersionInfo]::GetVersionInfo($Target)
$Version = '{0}.{1}.{2}.{3}' -f $Info.FileMajorPart, $Info.FileMinorPart, $Info.FileBuildPart, $Info.FilePrivatePart
if ([Version]$Version -lt [Version]$MinimumVersion) { throw "Official runtime $Version is older than required $MinimumVersion." }
if ($Pinned -and $Version -ne $Pinned.version) { throw 'Pinned Microsoft prerequisite version changed.' }
$Record = [ordered]@{
    schema_version = 1
    official_source = $Official
    documentation = 'https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist'
    url = $FinalUrl
    sha256 = $Hash
    bytes = (Get-Item -LiteralPath $Target).Length
    version = $Version
    minimum_version = $MinimumVersion
    signature_status = [string]$Signature.Status
    signer_subject = $Signature.SignerCertificate.Subject
    signer_thumbprint = $Signature.SignerCertificate.Thumbprint
    retrieved_at_utc = [DateTime]::UtcNow.ToString('o')
    redistribution = if ($Purpose -eq 'AppLocal') { 'Original EXE is a build-time verified source and is not shipped. The five exact derived release DLLs are packaged app-locally subject to their separate reviewed distribution terms.' } else { 'Not embedded or redistributed. Target downloads these exact Microsoft bytes only after explicit consent.' }
}
$Record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Output 'vc-runtime.json') -Encoding utf8NoBOM
Write-Host "Verified Microsoft prerequisite $Version; SHA-256 $Hash. No installer executed."
