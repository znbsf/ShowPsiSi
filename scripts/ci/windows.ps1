# CI-only Windows SDK setup and native regression route. Run with PowerShell 7.
# Uses the hosted runner's VS 2022 toolchain, not scripts/env.ps1's owner-PC paths.
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Dependencies', 'Build', 'EngineTests', 'QtTests', 'Diagnostics')]
    [string]$Phase
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false
if (-not $IsWindows) { throw 'This script requires a Windows x64 runner with Visual Studio 2022.' }

$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$Artifacts = Join-Path $Root 'artifacts/windows-native'
$Sdk = Join-Path $Root '.deps/TSDuck-3.39-3956'
$Qt = Join-Path $Root '.deps/Qt/6.7.3/msvc2019_64'
$Build = Join-Path $Root 'build/windows'
$Bin = Join-Path $Build 'bin/Release'
New-Item -ItemType Directory -Force $Artifacts | Out-Null
Start-Transcript -Path (Join-Path $Artifacts "$Phase.log") -Force | Out-Null

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    Write-Host "> $Program $($Arguments -join ' ')"
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required file missing: $Path" }
}

function Set-NativeEnvironment {
    $env:SHOWPSISI_ROOT = $Root
    $env:SHOWPSISI_CORE = Join-Path $Bin 'showpsisi-core.exe'
    $env:SHOWPSISI_QT = Join-Path $Bin 'showpsisi-qt.exe'
    $env:TSPLUGINS_PATH = Join-Path $Sdk 'bin'
    $env:PATH = "$Bin;$Qt/bin;$Sdk/bin;$env:PATH"
    $env:PYTHONUTF8 = '1'
    $env:QT_QPA_PLATFORM = 'offscreen'
    $env:QT_QUICK_BACKEND = 'software'
    # A GUI-subsystem executable otherwise writes diagnostics to the debugger.
    $env:QT_FORCE_STDERR_LOGGING = '1'
}

Push-Location $Root
try {
    Write-Host "Phase: $Phase; OS: $([Environment]::OSVersion); PowerShell: $($PSVersionTable.PSVersion)"
    Write-Host "Runner image: $env:ImageOS $env:ImageVersion"
    Set-NativeEnvironment
    switch ($Phase) {
        'Dependencies' {
            # The portable ZIP is runtime-only in this release. The NSIS EXE has
            # include/ and lib/Release-Win64/. /S /all=true would install the SDK,
            # but also writes registry/PATH. Extract payload only; never run it.
            # https://github.com/tsduck/tsduck/blob/v3.39-3956/pkg/nsis/tsduck.nsi
            # https://github.com/tsduck/tsduck/blob/v3.39-3956/pkg/nsis/build-installer.ps1
            $Url = 'https://github.com/tsduck/tsduck/releases/download/v3.39-3956/TSDuck-Win64-3.39-3956.exe'
            # Identity recorded from the official release asset; not a publisher signature.
            $ExpectedHash = '8694ac1301904ca7e978cfe42a540f29e876f10d68c668ed1bc5d3d25ea2c9c0'
            $Downloads = Join-Path $Root '.deps/downloads'
            New-Item -ItemType Directory -Force $Downloads, $Sdk | Out-Null
            $Installer = Join-Path $Downloads 'TSDuck-Win64-3.39-3956.exe'
            Invoke-WebRequest -Uri $Url -OutFile $Installer -MaximumRetryCount 3 -RetryIntervalSec 5
            $Hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
            @{ url = $Url; sha256 = $Hash; expected_sha256 = $ExpectedHash } |
                ConvertTo-Json | Set-Content (Join-Path $Artifacts 'tsduck-source.json') -Encoding utf8
            if ($Hash -ne $ExpectedHash) { throw "Official TSDuck asset SHA-256 mismatch: $Hash" }
            $SevenZip = (Get-Command 7z.exe -ErrorAction Stop).Source
            Invoke-Checked $SevenZip @('l', $Installer)
            Invoke-Checked $SevenZip @('x', '-y', "-o$Sdk", $Installer, 'bin/*', 'include/*', 'lib/Release-Win64/*', 'LICENSE.txt', 'OTHERS.txt')
            foreach ($Name in @('include/tsduck.h', 'include/tsVersion.h', 'lib/Release-Win64/tsduck.lib', 'bin/tsduck.dll', 'bin/tsp.exe', 'bin/tsduck.tables.model.xml', 'bin/tsduck.dtv.names')) {
                Assert-File (Join-Path $Sdk $Name)
            }
            $VersionHeader = Get-Content (Join-Path $Sdk 'include/tsVersion.h') -Raw
            foreach ($Define in @('TS_VERSION_MAJOR\s+3\b', 'TS_VERSION_MINOR\s+39\b', 'TS_COMMIT\s+3956\b')) {
                if ($VersionHeader -notmatch $Define) { throw "Unexpected TSDuck SDK version: $Define missing" }
            }
            Invoke-Checked (Join-Path $Sdk 'bin/tsp.exe') @('--version')

            # Qt's published 6.7.3 package is named win64_msvc2019_64. VS 2022
            # consumes its older import libraries using Microsoft's supported
            # MSVC 2015+ binary compatibility (the newer linker is required).
            # https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_673/Updates.xml
            # https://learn.microsoft.com/cpp/porting/binary-compat-2015-2017
            Invoke-Checked 'python' @('-m', 'pip', 'install', 'aqtinstall==3.3.0')
            Invoke-Checked 'python' @('-m', 'aqt', 'install-qt', 'windows', 'desktop', '6.7.3', 'win64_msvc2019_64', '--outputdir', (Join-Path $Root '.deps/Qt'), '--archives', 'qtbase', 'qtdeclarative', 'qtsvg', 'qttools')
            Assert-File (Join-Path $Qt 'bin/qmake.exe')
            Assert-File (Join-Path $Qt 'bin/windeployqt.exe')
            Invoke-Checked (Join-Path $Qt 'bin/qmake.exe') @('-query')
            Invoke-Checked 'python' @('-m', 'pip', 'freeze')
        }
        'Build' {
            Assert-File (Join-Path $Sdk 'include/tsduck.h')
            Assert-File (Join-Path $Qt 'lib/cmake/Qt6/Qt6Config.cmake')
            Invoke-Checked 'cmake' @('--version')
            Invoke-Checked 'cmake' @('-S', $Root, '-B', $Build, '-G', 'Visual Studio 17 2022', '-A', 'x64', '-DBUILD_QT_UI=ON', "-DTSDUCK_ROOT=$Sdk", "-DCMAKE_PREFIX_PATH=$Qt")
            Invoke-Checked 'cmake' @('--build', $Build, '--config', 'Release', '--parallel', '2', '--verbose')
            Assert-File $env:SHOWPSISI_CORE
            Assert-File $env:SHOWPSISI_QT
            # Preserve the SDK's lookup files beside the copied TSDuck DLL. A DLL
            # alone can start successfully while native XML/name decoding fails.
            Copy-Item -Path "$Sdk/bin/ts*.xml", "$Sdk/bin/ts*.names" -Destination $Bin
            Invoke-Checked (Join-Path $Qt 'bin/windeployqt.exe') @('--release', '--no-translations', '--no-compiler-runtime', '--include-plugins', 'qoffscreen', '--qmldir', (Join-Path $Root 'ui/qt'), '--dir', $Bin, $env:SHOWPSISI_QT)
            Assert-File (Join-Path $Bin 'platforms/qoffscreen.dll')
            Invoke-Checked 'python' @('scripts/make_fixture.py')
        }
        'EngineTests' {
            Invoke-Checked 'python' @('scripts/ci/windows_native_checks.py', '--artifacts', $Artifacts, '--engine')
        }
        'QtTests' {
            Invoke-Checked 'python' @('scripts/ci/windows_native_checks.py', '--artifacts', $Artifacts, '--qt')
        }
        'Diagnostics' {
            # Deliberately log selected tool paths only, never the full CI environment.
            foreach ($Command in @('python.exe', 'cmake.exe', '7z.exe')) {
                Get-Command $Command -ErrorAction SilentlyContinue | Select-Object Name, Source | Format-Table | Out-String | Write-Host
            }
            foreach ($Directory in @($Bin, "$Sdk/bin", "$Sdk/lib/Release-Win64", "$Qt/bin", "$Qt/plugins/platforms")) {
                Write-Host "Contents: $Directory"
                if (Test-Path -LiteralPath $Directory) {
                    Get-ChildItem -LiteralPath $Directory -File | Select-Object Name, Length | Format-Table -AutoSize | Out-String -Width 240 | Write-Host
                }
            }
            $VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
            if (Test-Path -LiteralPath $VsWhere) {
                & $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json
                $Vs = & $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
                if ($Vs) {
                    $Dumpbin = Get-ChildItem "$Vs/VC/Tools/MSVC/*/bin/Hostx64/x64/dumpbin.exe" -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1
                    if ($Dumpbin) {
                        foreach ($File in @($env:SHOWPSISI_CORE, $env:SHOWPSISI_QT, "$Bin/tsduck.dll", "$Bin/Qt6Core.dll", "$Bin/platforms/qoffscreen.dll", "$Sdk/bin/tsduck.dll", "$Sdk/bin/tsp.exe", "$Qt/bin/Qt6Core.dll", "$Qt/bin/qmake.exe")) {
                            if (Test-Path -LiteralPath $File) { & $Dumpbin.FullName /DEPENDENTS $File }
                        }
                    }
                }
            }
        }
    }
} finally {
    Pop-Location
    Stop-Transcript | Out-Null
}
