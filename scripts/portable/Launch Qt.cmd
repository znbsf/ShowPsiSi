@echo off
setlocal DisableDelayedExpansion
rem Only the complete app-local package is used. No PowerShell or SDK required.
for /f "delims==" %%V in ('set SHOWPSISI_ 2^>nul') do set "%%V="
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
set "QML_IMPORT_PATH="
set "QML2_IMPORT_PATH="
set "QT_QPA_PLATFORM="
set "TSPLUGINS_PATH="
set "TSDUCK="
start "" /wait "%~dp0bin\showpsisi-qt.exe"
endlocal
