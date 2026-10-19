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
$Sdk = Join-Path $Root '.deps/TSDuck-3.45-4798'
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
    $env:SHOWPSISI_TEST_CORE = Join-Path $Bin 'showpsisi-core-test.exe'
    $env:SHOWPSISI_QT = Join-Path $Bin 'showpsisi-qt.exe'
    $env:TSPLUGINS_PATH = Join-Path $Sdk 'bin'
    $env:PATH = "$Bin;$Qt/bin;$Sdk/bin;$env:PATH"
    $env:PYTHONUTF8 = '1'
    $env:QT_QPA_PLATFORM = 'offscreen'
    $env:QT_QUICK_BACKEND = 'software'
    # Windows qoffscreen uses FreeType, not qwindows' system font database.
    # Point it at the runner's existing fonts instead of Qt's empty lib/fonts.
    # https://github.com/qt/qtbase/blob/v6.7.3/src/gui/text/freetype/qfreetypefontdatabase.cpp
    $env:QT_QPA_FONTDIR = Join-Path $env:WINDIR 'Fonts'
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
            # Verify and extract the official NSIS payload into this workspace;
            # the setup helper never executes the installer or writes registry/PATH.
            & (Join-Path $Root 'scripts/setup-tsduck.ps1') -Sdk $Sdk -Artifacts $Artifacts
            Invoke-Checked (Join-Path $Sdk 'bin/tsp.exe') @('--version')

            # Qt's published 6.7.3 package is named win64_msvc2019_64. VS 2022
            # consumes its older import libraries using Microsoft's supported
            # MSVC 2015+ binary compatibility (the newer linker is required).
            # https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_673/Updates.xml
            # https://learn.microsoft.com/cpp/porting/binary-compat-2015-2017
            Invoke-Checked 'python' @('-m', 'pip', 'install', 'aqtinstall==3.3.0')
            Invoke-Checked 'python' @('-m', 'aqt', 'install-qt', 'windows', 'desktop', '6.7.3', 'win64_msvc2019_64', '--outputdir', (Join-Path $Root '.deps/Qt'), '--archives', 'qtbase', 'qtdeclarative', 'qtsvg', 'qttools', '--keep', '--archive-dest', (Join-Path $Root '.deps/qt-archives'))
            Assert-File (Join-Path $Qt 'bin/qmake.exe')
            Assert-File (Join-Path $Qt 'bin/windeployqt.exe')
            Invoke-Checked (Join-Path $Qt 'bin/qmake.exe') @('-query')
            Invoke-Checked 'python' @('-m', 'pip', 'freeze')
        }
        'Build' {
            & (Join-Path $Root 'scripts/setup-tsduck.ps1') -Sdk $Sdk -ValidateOnly
            Assert-File (Join-Path $Qt 'lib/cmake/Qt6/Qt6Config.cmake')
            Invoke-Checked 'cmake' @('--version')
            Invoke-Checked 'cmake' @('-S', $Root, '-B', $Build, '-G', 'Visual Studio 17 2022', '-A', 'x64', '-DBUILD_QT_UI=ON', '-DSHOWPSISI_BUILD_CANCELLATION_TESTS=ON', '-DSHOWPSISI_BUILD_UPDATER_TESTS=ON', "-DTSDUCK_ROOT=$Sdk", "-DCMAKE_PREFIX_PATH=$Qt")
            Invoke-Checked 'cmake' @('--build', $Build, '--config', 'Release', '--parallel', '2', '--verbose')
            Assert-File $env:SHOWPSISI_CORE
            Assert-File $env:SHOWPSISI_TEST_CORE
            Assert-File $env:SHOWPSISI_QT
            # Preserve both SDKs' lookup files beside the copied TSDuck/TSCore DLLs.
            # A DLL alone can start while native XML/name decoding still fails.
            Copy-Item -Path "$Sdk/bin/ts*.xml", "$Sdk/bin/ts*.names" -Destination $Bin
            foreach ($Name in @('tsduck.dll', 'tscore.dll', 'tsduck.tables.model.xml', 'tsduck.dtv.names', 'tscore.time.xml', 'tscore.ip.names')) {
                Assert-File (Join-Path $Bin $Name)
                $SourceHash = (Get-FileHash -LiteralPath (Join-Path $Sdk "bin/$Name") -Algorithm SHA256).Hash
                $StagedHash = (Get-FileHash -LiteralPath (Join-Path $Bin $Name) -Algorithm SHA256).Hash
                if ($SourceHash -ne $StagedHash) { throw "Staged TSDuck/TSCore runtime mismatch: $Name" }
            }
            Invoke-Checked (Join-Path $Qt 'bin/windeployqt.exe') @('--release', '--no-translations', '--no-compiler-runtime', '--include-plugins', 'qoffscreen', '--qmldir', (Join-Path $Root 'ui/qt'), '--dir', $Bin, $env:SHOWPSISI_QT)
            Assert-File (Join-Path $Bin 'platforms/qoffscreen.dll')
            Invoke-Checked 'python' @('scripts/make_fixture.py')
            # Bind explicit production inputs to this build's checkout identity.
            $CompilerInfo = Get-ChildItem -Path "$Build/CMakeFiles/*/CMakeCXXCompiler.cmake" -File | Select-Object -Last 1
            if (-not $CompilerInfo) { throw 'CMake compiler identity unavailable.' }
            $CompilerVersion = Select-String -LiteralPath $CompilerInfo.FullName -Pattern '^set\(CMAKE_CXX_COMPILER_VERSION "([^"]+)"\)'
            if (-not $CompilerVersion) { throw 'CMake compiler version unavailable.' }
            $ProjectVersion = [regex]::Match((Get-Content -LiteralPath (Join-Path $Root 'CMakeLists.txt') -Raw), 'project\(ShowPsiSi VERSION ([0-9]+\.[0-9]+\.[0-9]+) ')
            if (-not $ProjectVersion.Success) { throw 'Canonical application version unavailable.' }
            $BuildRecord = @{
                source_commit = (& git rev-parse HEAD).Trim()
                application_version = $ProjectVersion.Groups[1].Value
                source_root = $Root
                compiler_version = $CompilerVersion.Matches[0].Groups[1].Value
                production = @{}
            }
            foreach ($Name in @('showpsisi-core.exe', 'showpsisi-qt.exe')) {
                $BuildRecord.production[$Name] = (Get-FileHash -LiteralPath (Join-Path $Bin $Name) -Algorithm SHA256).Hash.ToLowerInvariant()
            }
            $BuildRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Bin 'showpsisi-build.json') -Encoding utf8NoBOM
        }
        'EngineTests' {
            Invoke-Checked 'python' @('scripts/ci/windows_native_checks.py', '--artifacts', $Artifacts, '--engine')
        }
        'QtTests' {
            Assert-File (Join-Path $env:QT_QPA_FONTDIR 'segoeui.ttf')
            Write-Host "Offscreen FreeType fonts: $env:QT_QPA_FONTDIR"
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
                        foreach ($File in @($env:SHOWPSISI_CORE, $env:SHOWPSISI_TEST_CORE, $env:SHOWPSISI_QT, "$Bin/tsduck.dll", "$Bin/tscore.dll", "$Bin/Qt6Core.dll", "$Bin/platforms/qoffscreen.dll", "$Sdk/bin/tsduck.dll", "$Sdk/bin/tscore.dll", "$Sdk/bin/tsp.exe", "$Qt/bin/Qt6Core.dll", "$Qt/bin/qmake.exe")) {
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
