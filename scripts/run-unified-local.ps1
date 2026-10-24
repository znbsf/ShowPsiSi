param([string]$Sample='')
$ErrorActionPreference='Stop'
$repoRoot=Split-Path $PSScriptRoot -Parent
$sdk='C:\Users\hentai\Documents\ShowPsiSi\.deps\Qt\6.7.3\msvc2019_64'
$env:PATH="$sdk\bin;$env:PATH"
$env:QT_QPA_PLATFORM_PLUGIN_PATH="$sdk\plugins\platforms"
$env:QML_IMPORT_PATH="$sdk\qml"
$env:SHOWPSISI_ROOT=$repoRoot
$env:SHOWPSISI_CORE="$repoRoot\build\bin\showpsisi-core.exe"
$env:SHOWPSISI_SETTINGS_PATH="$repoRoot\artifacts\unified-inspector\comparison-settings.ini"
$env:SHOWPSISI_SAMPLE=if($Sample){(Resolve-Path -LiteralPath $Sample).Path}else{"$repoRoot\artifacts\unified-inspector\fixture.ts"}
$env:SHOWPSISI_AUTO='1'
$env:SHOWPSISI_SCRIPT=''
$env:SHOWPSISI_ADVANCED='0'
$env:SHOWPSISI_THEME='light'
$env:SHOWPSISI_AGENT_DIR=''
& "$repoRoot\build\bin\showpsisi-qt.exe"
