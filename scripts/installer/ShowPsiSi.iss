; Compiled only through package-installer.ps1 after exact payload review/validation.
; No Microsoft runtime binary is embedded or redistributed by this installer.
#include "generated.iss"

[Setup]
AppId={{13C6E0A2-B226-4BAA-A218-8DD167D78D4C}
AppName=ShowPsiSi
AppVersion={#AppVersion}
AppPublisher=ShowPsiSi contributors
AppPublisherURL=https://github.com/znbsf/ShowPsiSi
AppSupportURL=https://github.com/znbsf/ShowPsiSi/issues
AppUpdatesURL=https://github.com/znbsf/ShowPsiSi/releases
DefaultDirName={localappdata}\Programs\ShowPsiSi
DefaultGroupName=ShowPsiSi
PrivilegesRequired=lowest
; System32 runtime checks are validated for native x64 Windows only.
; ARM64 emulation needs its own runtime/load-path acceptance before enabling it.
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
UsePreviousAppDir=yes
UsePreviousTasks=yes
DisableProgramGroupPage=yes
DisableDirPage=no
UninstallDisplayIcon={app}\bin\showpsisi-qt.exe
UninstallDisplayName=ShowPsiSi {#AppVersion}
SetupIconFile={#PackageRoot}\assets\icons\showpsisi.ico
OutputDir={#InstallerOutput}
OutputBaseFilename={#InstallerBaseName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=Local\ShowPsiSi.ApplicationLifetime
CloseApplications=no
RestartApplications=no
AllowNoIcons=yes
; Preserve all per-user Qt settings and user-created exports on upgrade/uninstall.
; No registry deletion, profile cleanup, global PATH change or file associations.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
#include "payload-files.iss"

[Icons]
Name: "{group}\ShowPsiSi"; Filename: "{app}\bin\showpsisi-qt.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\ShowPsiSi"; Filename: "{app}\bin\showpsisi-qt.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\bin\showpsisi-qt.exe"; WorkingDir: "{app}"; Description: "Open ShowPsiSi"; Flags: nowait postinstall skipifsilent unchecked

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{13C6E0A2-B226-4BAA-A218-8DD167D78D4C}_is1';
var
  DownloadPage: TDownloadWizardPage;

function VersionAtLeast(const Actual, Required: String): Boolean;
var
  ActualVersion, RequiredVersion: Int64;
begin
  Result := StrToVersion(Actual, ActualVersion) and StrToVersion(Required, RequiredVersion);
  if Result then
    Result := ComparePackedVersion(ActualVersion, RequiredVersion) >= 0;
end;

function RuntimeFileReady(const Name: String): Boolean;
var
  Version: String;
begin
  Result := GetVersionNumbersString(ExpandConstant('{sys}\') + Name, Version);
  if Result then
    Result := VersionAtLeast(Version, '{#VcMinimum}');
end;

function RuntimeReady: Boolean;
begin
  Result := RuntimeFileReady('vcruntime140.dll') and
    RuntimeFileReady('vcruntime140_1.dll') and RuntimeFileReady('msvcp140.dll') and
    RuntimeFileReady('msvcp140_1.dll');
end;

function IsUpdate: Boolean;
var
  Index: Integer;
begin
  Result := False;
  for Index := 1 to ParamCount do
    if CompareText(ParamStr(Index), '/UPDATE') = 0 then Result := True;
end;

function DirectoryHasFiles(const Directory: String): Boolean;
var
  FindRec: TFindRec;
begin
  Result := False;
  if FindFirst(AddBackslash(Directory) + '*', FindRec) then begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then Result := True;
      until Result or not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage('Microsoft Visual C++ runtime',
    'Downloading the verified prerequisite directly from Microsoft.', nil);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingVersion, ExistingLocation: String;
  ResultCode: Integer;
begin
  Result := '';
  if IsUpdate and not FileExists(ExpandConstant('{app}\showpsisi-installation.json')) then begin
    Result := 'The update destination is not an installed ShowPsiSi folder. Run Setup normally to choose a new installation.';
    exit;
  end;
  if DirectoryHasFiles(ExpandConstant('{app}')) and
      not FileExists(ExpandConstant('{app}\showpsisi-installation.json')) then begin
    Result := 'Choose an empty folder or an existing ShowPsiSi installation. Setup will not overwrite an unrelated folder.';
    exit;
  end;
  if RegQueryStringValue(HKCU64, UninstallKey, 'DisplayVersion', ExistingVersion) then begin
    if not VersionAtLeast('{#AppVersion}', ExistingVersion) then begin
      Result := 'A newer ShowPsiSi version is already installed. Downgrades are blocked; uninstall it first if you really need an older version.';
      exit;
    end;
    if RegQueryStringValue(HKCU64, UninstallKey, 'InstallLocation', ExistingLocation) then
      if CompareText(RemoveBackslashUnlessRoot(ExistingLocation),
          RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0 then begin
        Result := 'An existing ShowPsiSi installation uses a different folder. Upgrade that folder, or uninstall it before choosing another location.';
        exit;
      end;
  end;
  if RuntimeReady then exit;
  // Never download, elevate or accept Microsoft terms during a silent install.
  if WizardSilent then begin
    Result := 'Microsoft Visual C++ x64 runtime {#VcMinimum} or newer is required. Run Setup interactively to review and install the official prerequisite.';
    exit;
  end;
  if MsgBox('ShowPsiSi needs Microsoft Visual C++ x64 runtime {#VcMinimum} or newer.' + #13#10 + #13#10 +
      'Download the verified runtime directly from Microsoft now and open its installer?' + #13#10 +
      'This needs internet access and may ask for administrator permission. Review and accept Microsoft''s terms in its own installer. ShowPsiSi will not be installed until the runtime is ready.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) <> IDYES then begin
    Result := 'The runtime installation was declined. No ShowPsiSi application files or registration have been changed.';
    exit;
  end;
  DownloadPage.Clear;
  DownloadPage.Add('{#VcUrl}', 'vc_redist.x64.exe', '{#VcSha256}');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
    except
      if DownloadPage.AbortedByUser then
        Result := 'The runtime download was cancelled. No ShowPsiSi application files or registration have been changed.'
      else
        Result := 'The Microsoft runtime could not be downloaded or verified. Check your connection and retry. ' + GetExceptionMessage;
      exit;
    end;
  finally
    DownloadPage.Hide;
  end;
  // Hash was pinned only after valid Microsoft Authenticode + version checks at build time.
  // The visible Microsoft wizard retains its license acceptance and UAC prompts.
  if not ShellExec('runas', ExpandConstant('{tmp}\vc_redist.x64.exe'), '/install /norestart',
      '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then begin
    Result := 'The Microsoft runtime installer was not started (permission may have been declined). No ShowPsiSi application files or registration have been changed.';
    exit;
  end;
  if (ResultCode = 3010) or (ResultCode = 1641) then begin
    NeedsRestart := True;
    Result := 'Microsoft reports a restart is required. Restart Windows, then run ShowPsiSi Setup again.';
    exit;
  end;
  if (ResultCode <> 0) or not RuntimeReady then
    Result := 'Microsoft runtime installation was cancelled, failed, or did not satisfy the minimum version. No ShowPsiSi application files or registration have been changed. Setup code: ' + IntToStr(ResultCode);
end;
