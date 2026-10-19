# Build time only. Treat signed Microsoft EXE/CABs as data; never run the installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$PrerequisiteDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false
if (-not $IsWindows) { throw 'Official runtime signature verification and CAB expansion require Windows.' }
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Output = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw 'Refusing stale app-local runtime stage.' }
$Pin = Get-Content (Join-Path $PSScriptRoot 'portable-licenses/vc-runtime-pin.json') -Raw | ConvertFrom-Json
$Work = "$Output-work"
if (Test-Path -LiteralPath $Work) { throw 'Refusing stale app-local runtime work directory.' }
New-Item -ItemType Directory -Path $Work | Out-Null
$Metadata = Join-Path $Work 'download-pin.json'
$Pin.package_metadata.source | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Metadata -Encoding utf8NoBOM
& (Join-Path $PSScriptRoot 'prepare-windows-prerequisite.ps1') -Output $PrerequisiteDirectory -Metadata $Metadata -MinimumVersion $Pin.package_metadata.minimum_version -Purpose AppLocal
$Verifier = Join-Path $PSScriptRoot 'ci/vc_runtime.py'
function Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed: $LASTEXITCODE" }
}
$Cabinet = Join-Path $Work 'payload.cab'
Checked $Python @($Verifier, 'cabinet', '--input', (Join-Path $PrerequisiteDirectory 'vc_redist.x64.exe'), '--output', $Cabinet)
$Expand = Join-Path $env:SystemRoot 'System32/expand.exe'
if (-not (Test-Path -LiteralPath $Expand -PathType Leaf)) { throw 'Inbox Windows CAB expansion tool missing.' }
$Inner = Join-Path $Work 'inner'
New-Item -ItemType Directory -Path $Inner | Out-Null
# Exact named members only: no wildcard extraction and no executable/MSI actions.
Checked $Expand @('-F:a4', $Cabinet, $Inner)
$RuntimeCab = Join-Path $Inner 'a4'
Checked $Python @($Verifier, 'inner', '--input', $RuntimeCab)
$Dlls = Join-Path $Work 'dlls'
New-Item -ItemType Directory -Path $Dlls | Out-Null
$SignatureEvidence = @()
$Signing = Join-Path $Work 'signature-inputs'
New-Item -ItemType Directory -Path $Signing | Out-Null
foreach ($Entry in $Pin.package_metadata.files.PSObject.Properties) {
    $Name = $Entry.Name
    if ($Name -notmatch '^(msvcp140(_[12])?|vcruntime140(_1)?)\.dll$') { throw 'Unreviewed runtime member name.' }
    Checked $Expand @("-F:$($Name)_amd64", $RuntimeCab, $Dlls)
    $File = Join-Path $Dlls "$($Name)_amd64"
    # Give the SIP dispatcher a conventional .dll extension; bytes remain unchanged.
    $SignatureInput = Join-Path $Signing $Name
    Copy-Item -LiteralPath $File -Destination $SignatureInput
    $Signature = Get-AuthenticodeSignature -LiteralPath $SignatureInput
    if ($Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
        $Signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') {
        throw "Extracted runtime signature is not valid Microsoft code: $Name"
    }
    $SignatureEvidence += @{ name = $Name; sha256 = (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash.ToLowerInvariant(); signature_status = [string]$Signature.Status; signer_subject = $Signature.SignerCertificate.Subject; signer_thumbprint = $Signature.SignerCertificate.Thumbprint }
}
$SignatureEvidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Work 'runtime-signatures.json') -Encoding utf8NoBOM
Checked $Python @($Verifier, 'stage', '--input', $Dlls, '--output', $Output)
Copy-Item -LiteralPath (Join-Path $PrerequisiteDirectory 'vc-runtime.json') -Destination (Join-Path $Work 'vc-runtime.json')
Write-Host 'Pinned release x64 DLLs verified and staged as data. Distribution still requires the applicable license-basis and exact inventory review.'
