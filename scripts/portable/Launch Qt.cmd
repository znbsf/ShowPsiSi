@echo off
setlocal DisableDelayedExpansion
rem Uses inbox Windows PowerShell for a read-only runtime check; no policy changes.
for /f "delims==" %%V in ('set SHOWPSISI_ 2^>nul') do set "%%V="
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
set "QML_IMPORT_PATH="
set "QML2_IMPORT_PATH="
set "QT_QPA_PLATFORM="
set "TSPLUGINS_PATH="
set "TSDUCK="
if not exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" goto runtime_check_unavailable
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; try { if ([Environment]::OSVersion.Version -lt [version]'10.0.17763.0') { throw 'Windows 10 version 1809 (build 17763) or newer is required.' }; if ([IntPtr]::Size -ne 8) { throw 'Use the 64-bit Windows Command Prompt and inbox PowerShell for this x64 package.' }; $minimum=[version]'14.51.36231.0'; foreach($name in @('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','msvcp140_1.dll')) { $path=Join-Path $env:SystemRoot ('System32\'+$name); if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Missing runtime: '+$name) }; $info=[Diagnostics.FileVersionInfo]::GetVersionInfo($path); $version=[version]::new($info.FileMajorPart,$info.FileMinorPart,$info.FileBuildPart,$info.FilePrivatePart); if ($version -lt $minimum) { throw ('Runtime too old: '+$name+' '+$version) } }; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
if errorlevel 1 goto runtime_not_ready
start "" /wait "%~dp0bin\showpsisi-qt.exe"
exit /b %errorlevel%

:runtime_check_unavailable
echo The read-only prerequisite check needs inbox Windows PowerShell.
echo It is unavailable. ShowPsiSi has not been started.
goto runtime_help

:runtime_not_ready
echo ShowPsiSi portable needs Microsoft Visual C++ x64 runtime 14.51.36231.0 or newer.
echo A required DLL is missing, too old, or could not be checked. See the error above.

:runtime_help
echo Official Microsoft prerequisite information and download:
echo https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
echo Nothing was downloaded or installed by this launcher.
echo After installing the official x64 prerequisite yourself, run Launch Qt.cmd again.
echo See README-portable.txt. Directly opening bin\showpsisi-qt.exe bypasses this check.
pause
exit /b 1
