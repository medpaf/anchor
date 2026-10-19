; Inno Setup script for anchor-win.exe (run by build.ps1, or open it in Inno Setup and press Build).
; Installs for the current user only, so no administrator password is needed.

; Windows needs a version number for its Apps list; Anchor doesn't show one anywhere else.
#define AppVersion "1.0"

[Setup]
AppId={{455A0C32-C5C0-4E98-9073-BF83A4BBC3CD}
AppName=Anchor
AppVersion={#AppVersion}
AppVerName=Anchor Free
AppPublisher=Paulo Medeiros
AppPublisherURL=https://github.com/medpaf/anchor
AppSupportURL=https://github.com/medpaf/anchor
DefaultDirName={autopf}\Anchor
DefaultGroupName=Anchor
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=anchor-win
SetupIconFile=desktop\icons\anchor.ico
UninstallDisplayIcon={app}\Anchor.exe
UninstallDisplayName=Anchor Free
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\Anchor\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Anchor"; Filename: "{app}\Anchor.exe"; AppUserModelID: "app.anchor.Desktop"
Name: "{autodesktop}\Anchor"; Filename: "{app}\Anchor.exe"; AppUserModelID: "app.anchor.Desktop"; Tasks: desktopicon

[Run]
Filename: "{app}\Anchor.exe"; Description: "Open Anchor"; Flags: nowait postinstall skipifsilent
; Check for updates… → Update runs this installer silently with /UPDATE=1, after closing Anchor:
; open the new version once it's installed.
Filename: "{app}\Anchor.exe"; Flags: nowait; Check: IsUpdate

; Uninstalling also deletes the backup key and settings in %APPDATA%\Anchor (updates install over Anchor
; without uninstalling, so they keep it). InitializeUninstall below warns first.
[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\Anchor"

[Code]
// True when Anchor's own update started this installer (with /UPDATE=1).
function IsUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

// adb keeps running after Anchor closes (it's a background server) and holds its files in
// {app}\platform-tools open, so they couldn't be replaced or removed. Stop Anchor's own adb first:
// politely, then any adb.exe still running from Anchor's folder. Other copies of adb are left alone.
procedure StopAnchorsAdb;
var
  Adb, Dir: String;
  Code: Integer;
begin
  Adb := ExpandConstant('{app}\platform-tools\adb.exe');
  if not FileExists(Adb) then
    Exit;
  Exec(Adb, 'kill-server', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Dir := ExpandConstant('{app}');
  StringChangeEx(Dir, '''', '''''', True);  // PowerShell quoting
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -Command "Get-Process adb -ErrorAction SilentlyContinue | ' +
    'Where-Object { $_.Path -like ''' + Dir + '\*'' } | Stop-Process -Force"',
    '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopAnchorsAdb;
  Result := '';
end;

// Uninstalling deletes the backup key: say so first, with a way out (not for silent uninstalls).
function InitializeUninstall: Boolean;
begin
  Result := UninstallSilent or (MsgBox(
    'Uninstalling also deletes Anchor''s backup key from this computer.' + #13#10#13#10 +
    'If a phone is still anchored to this computer, cancel and remove Anchor from the phone first, ' +
    'or save the key (Menu > Backup key > Save as PDF). Without the key, that phone can only be ' +
    'recovered with a factory reset.' + #13#10#13#10 + 'Uninstall Anchor?',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopAnchorsAdb;
end;

