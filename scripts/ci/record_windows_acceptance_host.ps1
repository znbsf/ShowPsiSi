# Read-only host evidence for a disposable Windows VM. Windows PowerShell 5.1+.
# This does not install/uninstall software, alter networking, launch the app, or
# establish application acceptance. Keep this helper outside the release payload.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Output,
    [ValidateSet('Observe', 'CleanNoSharedVc')][string]$Profile = 'Observe',
    [string[]]$Artifact = @()
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Output = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw "Refusing stale evidence: $Output" }
$Parent = [IO.Path]::GetDirectoryName($Output)
if (-not (Test-Path -LiteralPath $Parent -PathType Container)) {
    throw 'Create the evidence directory first; the report must be outside the package.'
}
$Record = [ordered]@{
    schema_version = 1
    captured_utc = [DateTime]::UtcNow.ToString('o')
    profile = $Profile
    collection_complete = $false
    profile_satisfied = $false
    native_windows_desktop_verified = $false
    offline_verified = $false
    no_runtime_installer_verified = $false
    artifact_sha256 = @()
    errors = @()
    limitations = @(
        'Host snapshot only; does not start or validate the application.',
        'Network-interface state is not proof of Internet isolation.',
        'No process audit is collected; absence of runtime installation is unverified.',
        'No installed-software inventory is inferred from missing System32 VC DLLs.',
        'Read errors fail collection; missing files are recorded separately.'
    )
}
$Failure = $null
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Native Windows is required.' }
    if ([IntPtr]::Size -ne 8) { throw 'Run native x64 Windows PowerShell, not 32-bit PowerShell.' }
    # IsWow64Process2 distinguishes native AMD64 from ARM64 emulation. It
    # uses Windows/.NET only; no VS, SDK, Python, or downloaded executable needed.
    if (-not ('ShowPsiSiAcceptanceHost.Native' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace ShowPsiSiAcceptanceHost {
    public static class Native {
        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool IsWow64Process2(IntPtr process, out ushort processMachine, out ushort nativeMachine);
    }
}
'@
    }
    [UInt16]$ProcessMachine = 0
    [UInt16]$NativeMachine = 0
    $CurrentProcess = [Diagnostics.Process]::GetCurrentProcess()
    try {
        if (-not [ShowPsiSiAcceptanceHost.Native]::IsWow64Process2($CurrentProcess.Handle, [ref]$ProcessMachine, [ref]$NativeMachine)) {
            throw (New-Object ComponentModel.Win32Exception([Runtime.InteropServices.Marshal]::GetLastWin32Error()))
        }
    } finally { $CurrentProcess.Dispose() }
    $Version = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $Record.os = [ordered]@{
        build = [int]$Version.CurrentBuildNumber
        revision = $Version.UBR
        installation_type = $Version.InstallationType
        native_machine = ('0x{0:X4}' -f $NativeMachine)
        process_machine = ('0x{0:X4}' -f $ProcessMachine)
        powershell_version = $PSVersionTable.PSVersion.ToString()
        process_bits = [IntPtr]::Size * 8
    }
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $Identity.IsAuthenticated -or $null -eq $Identity.Groups) {
        throw 'Could not establish an authenticated Windows user token and group list.'
    }
    $Principal = New-Object Security.Principal.WindowsPrincipal($Identity)
    # A filtered administrator is not an actual standard account. Groups still
    # includes the deny-only Administrators SID, so test both facts explicitly.
    $AdminGroup = @($Identity.Groups | Where-Object { $_.Value -eq 'S-1-5-32-544' }).Count -gt 0
    $AdminEffective = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    $Interactive = @($Identity.Groups | Where-Object { $_.Value -eq 'S-1-5-4' }).Count -gt 0
    $Record.token = [ordered]@{
        administrators_sid_present = $AdminGroup
        administrator_effective = $AdminEffective
        interactive = $Interactive
        system_account = $Identity.IsSystem
        standard_user = ($Interactive -and -not $Identity.IsSystem -and -not $AdminGroup -and -not $AdminEffective)
    }
    function Get-Sha256([string]$Path) {
        # Use inbox .NET directly. A PowerShell 5.1 child may inherit a module
        # search path from pwsh where the Get-FileHash script cmdlet is absent.
        # Hash/read errors still fail collection and retain the failure record.
        $Hasher = [Security.Cryptography.SHA256]::Create()
        try {
            $InputStream = [IO.File]::OpenRead($Path)
            try { $Digest = $Hasher.ComputeHash($InputStream) }
            finally { $InputStream.Dispose() }
            return [BitConverter]::ToString($Digest).Replace('-', '').ToLowerInvariant()
        } finally { $Hasher.Dispose() }
    }
    function Get-FileEvidence([string]$Path) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            return [ordered]@{ path = $Path; exists = $false }
        }
        $File = Get-Item -LiteralPath $Path
        $Info = [Diagnostics.FileVersionInfo]::GetVersionInfo($File.FullName)
        return [ordered]@{
            path = $File.FullName
            exists = $true
            bytes = $File.Length
            sha256 = Get-Sha256 $File.FullName
            file_version = ('{0}.{1}.{2}.{3}' -f $Info.FileMajorPart, $Info.FileMinorPart, $Info.FileBuildPart, $Info.FilePrivatePart)
        }
    }
    $System = Join-Path $env:SystemRoot 'System32'
    $Names = @('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')
    $Record.shared_required_vc = @($Names | ForEach-Object { Get-FileEvidence (Join-Path $System $_) })
    # Capture additional v14-family files rather than treating an incomplete
    # installation as a pristine no-runtime image. Windows msvcrt/msvcp_win/UCRT
    # components are intentionally outside this application-runtime family.
    $Record.shared_other_vc14 = @(Get-ChildItem -LiteralPath $System -File |
        Where-Object { $_.Name -match '^(msvcp140|vcruntime140|concrt140|vcomp140|vcamp140|vccorlib140).*\.dll$' -and $_.Name -notin $Names } |
        ForEach-Object { Get-FileEvidence $_.FullName })
    $Record.windows_components = @('ucrtbase.dll', 'D3Dcompiler_47.dll') |
        ForEach-Object { Get-FileEvidence (Join-Path $System $_) }
    $Record.network_interfaces = @([Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
        ForEach-Object { [ordered]@{ type = $_.NetworkInterfaceType.ToString(); status = $_.OperationalStatus.ToString() } })
    foreach ($Path in $Artifact) {
        $Item = Get-FileEvidence ([IO.Path]::GetFullPath($Path))
        $Record.artifact_sha256 += $Item
        if (-not $Item.exists) { throw "Acceptance input missing: $Path" }
    }
    $Record.collection_complete = $true
    if ($Profile -eq 'CleanNoSharedVc') {
        if ($NativeMachine -ne 0x8664 -or $ProcessMachine -ne 0) { $Record.errors += 'Native AMD64 is required; ARM64 emulation is outside acceptance.' }
        if ($Record.os.build -lt 17763 -or $Record.os.installation_type -ne 'Client') {
            $Record.errors += 'Windows 10 1809+ / Windows 11 client is required.'
        }
        if (-not $Record.token.standard_user) { $Record.errors += 'Use an interactive non-administrator account, not a service or administrator with a filtered token.' }
        if (@($Record.shared_required_vc | Where-Object { $_.exists }).Count -or @($Record.shared_other_vc14).Count) {
            $Record.errors += 'Shared v14 CRT files exist. Do not remove them; choose a fresh disposable image.'
        }
        if (@($Record.windows_components | Where-Object { -not $_.exists }).Count) {
            $Record.errors += 'Required Windows UCRT/D3Dcompiler components are missing.'
        }
    }
    $Record.profile_satisfied = $Record.errors.Count -eq 0
    if (-not $Record.profile_satisfied) { throw ($Record.errors -join ' ') }
} catch {
    $Failure = $_
    $Record.profile_satisfied = $false
    if ($Record.errors -notcontains $_.Exception.Message) { $Record.errors += $_.Exception.Message }
} finally {
    # CreateNew prevents races/stale success overwrites; failure records remain.
    $Json = $Record | ConvertTo-Json -Depth 8
    $Stream = [IO.File]::Open($Output, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $Bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($Json + [Environment]::NewLine)
        $Stream.Write($Bytes, 0, $Bytes.Length)
    } finally { $Stream.Dispose() }
}
if ($Failure) { throw $Failure }
Write-Host "Host evidence recorded: $Output (profile: $Profile). Application acceptance is still unverified."
