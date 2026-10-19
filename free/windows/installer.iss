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

; The backup key in %APPDATA%\Anchor is kept on purpose, also when Anchor is uninstalled in Settings:
; without it, a phone that is still anchored can only be recovered with a factory reset.

[Code]
// True when Anchor's own update started this installer (with /UPDATE=1).
function IsUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

