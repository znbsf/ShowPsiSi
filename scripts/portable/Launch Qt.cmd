@echo off
setlocal DisableDelayedExpansion
rem Inbox Windows PowerShell and local WMI only: read-only platform/package checks.
rem Win32_Processor.Architecture: https://learn.microsoft.com/windows/win32/cimwin32prov/win32-processor
for /f "delims==" %%V in ('set SHOWPSISI_ 2^>nul') do set "%%V="
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
set "QML_IMPORT_PATH="
set "QML2_IMPORT_PATH="
set "QT_QPA_PLATFORM="
set "TSPLUGINS_PATH="
set "TSDUCK="
set "SHOWPSISI_PACKAGE_ROOT=%~dp0"
if not exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" goto runtime_check_unavailable
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; try { if ([Environment]::OSVersion.Version -lt [version]'10.0.17763.0') { throw 'Windows 10 version 1809 (build 17763) or newer is required.' }; if ([IntPtr]::Size -ne 8) { throw 'Use the 64-bit Windows Command Prompt and inbox PowerShell for this x64 package.' }; try { $processors=@(Get-CimInstance -ClassName Win32_Processor -Property Architecture -OperationTimeoutSec 5) } catch { throw ('Native x64 platform check needs local Windows WMI; query unavailable: '+$_.Exception.Message) }; if ($processors.Count -eq 0 -or @($processors | Where-Object { $_.Architecture -ne 9 }).Count -ne 0) { throw 'Native x64 Windows is required; ARM64 emulation or unknown processor architecture is not supported.' }; $bin=Join-Path $env:SHOWPSISI_PACKAGE_ROOT 'bin'; $minimum=[version]'14.51.36231.0'; $pinned=[version]'14.51.36247.0'; $names=@('msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','vcruntime140.dll','vcruntime140_1.dll'); $metadata=Join-Path $bin 'showpsisi-vc-runtime.json'; if (-not (Test-Path -LiteralPath $metadata -PathType Leaf)) { throw 'Missing bundled runtime metadata: bin\showpsisi-vc-runtime.json' }; $record=Get-Content -LiteralPath $metadata -Raw -Encoding UTF8 | ConvertFrom-Json; if (($record.schema_version -isnot [int] -and $record.schema_version -isnot [long]) -or $record.schema_version -ne 1 -or $record.mode -cne 'AppLocal' -or $record.version -cne $pinned.ToString() -or $record.minimum_version -cne $minimum.ToString()) { throw 'Invalid bundled runtime metadata or unsupported runtime mode.' }; $keys=@($record.files.PSObject.Properties.Name); if ($keys.Count -ne $names.Count -or @($keys | Where-Object { $_ -cnotin $names }).Count -ne 0) { throw 'Bundled runtime metadata must identify exactly the five reviewed DLLs.' }; foreach($name in $names) { $path=Join-Path $bin $name; if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Missing bundled runtime: bin\'+$name) }; $data=[IO.File]::ReadAllBytes($path); if ($data.Length -lt 64 -or $data[0] -ne 77 -or $data[1] -ne 90) { throw ('Corrupt bundled runtime (invalid PE header): '+$name) }; $pe=[BitConverter]::ToInt32($data,60); if ($pe -lt 64 -or $pe -gt ($data.Length-26) -or [BitConverter]::ToUInt32($data,$pe) -ne 17744) { throw ('Corrupt bundled runtime (invalid PE header): '+$name) }; if ([BitConverter]::ToUInt16($data,$pe+4) -ne 34404 -or [BitConverter]::ToUInt16($data,$pe+24) -ne 523 -or ([BitConverter]::ToUInt16($data,$pe+22) -band 8192) -eq 0) { throw ('Bundled runtime is not an x64 DLL: '+$name) }; $info=[Diagnostics.FileVersionInfo]::GetVersionInfo($path); $version=[version]::new($info.FileMajorPart,$info.FileMinorPart,$info.FileBuildPart,$info.FilePrivatePart); if ($version -lt $minimum) { throw ('Bundled runtime too old: '+$name+' '+$version+'; required '+$minimum) }; $entry=$record.files.$name; if (($entry.bytes -isnot [int] -and $entry.bytes -isnot [long]) -or $entry.machine -cne 'AMD64' -or $entry.version -cne $pinned.ToString() -or $version -ne $pinned -or $entry.bytes -ne $data.Length -or $entry.sha256 -cnotmatch '^[0-9a-f]{64}$') { throw ('Bundled runtime identity mismatch: '+$name) }; $hasher=[Security.Cryptography.SHA256]::Create(); try { $actual=[BitConverter]::ToString($hasher.ComputeHash($data)).Replace('-','').ToLowerInvariant() } finally { $hasher.Dispose() }; if ($actual -cne $entry.sha256) { throw ('Corrupt bundled runtime (SHA-256 mismatch): '+$name) } }; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
if errorlevel 1 goto runtime_not_ready
if not errorlevel 0 goto runtime_not_ready
set "SHOWPSISI_PACKAGE_ROOT="
start "" /wait "%~dp0bin\showpsisi-qt.exe"
exit /b %errorlevel%

:runtime_check_unavailable
echo The read-only platform/package check needs inbox Windows PowerShell and local WMI.
echo It is unavailable. ShowPsiSi has not been started.
goto runtime_help

:runtime_not_ready
echo ShowPsiSi could not verify its bundled Microsoft Visual C++ x64 runtime.
echo A package file is missing, too old, damaged, or could not be checked.
echo See the exact error above. System-installed runtimes are not a fallback.

:runtime_help
echo Extract the complete original ShowPsiSi ZIP into a new folder and try again.
echo Do not copy DLLs from other applications or DLL-download websites.
echo Nothing was downloaded, installed, elevated, or changed by this launcher.
echo Microsoft runtime information:
echo https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
echo See README-portable.txt. Directly opening bin\showpsisi-qt.exe bypasses this check.
pause
exit /b 1
