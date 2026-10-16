param([ValidateSet('qt','tauri')][string]$UI='qt',[string]$Sample='',[switch]$Auto)
$ProjectRoot=Split-Path $PSScriptRoot -Parent
$env:SHOWPSISI_ROOT=$ProjectRoot
$env:SHOWPSISI_CORE=Join-Path $ProjectRoot 'build\bin\showpsisi-core.exe'
$env:PATH="$ProjectRoot\.deps\Qt\6.7.3\msvc2019_64\bin;$env:PATH"
$env:QT_QPA_PLATFORM_PLUGIN_PATH="$ProjectRoot\.deps\Qt\6.7.3\msvc2019_64\plugins\platforms"
if($Sample){$env:SHOWPSISI_SAMPLE=if([IO.Path]::IsPathRooted($Sample)){[IO.Path]::GetFullPath($Sample)}else{[IO.Path]::GetFullPath((Join-Path $ProjectRoot $Sample))}}else{$env:SHOWPSISI_SAMPLE="$ProjectRoot\samples\generated\lab.ts"}
$env:SHOWPSISI_AUTO=if($Auto){'1'}else{'0'}
$appPath=if($UI -eq 'qt'){Join-Path $ProjectRoot 'build\bin\showpsisi-qt.exe'}else{Join-Path $ProjectRoot 'ui\tauri\src-tauri\target\release\showpsisi-tauri.exe'}
Start-Process -FilePath $appPath -WorkingDirectory $ProjectRoot -WindowStyle Hidden
