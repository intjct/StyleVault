; Inno Setup script — builds StyleVault-Setup-x.y.z.exe from dist\StyleVault
; Installs for the current user only (no admin password needed). Installing over an old version keeps
; the settings and the library (they live in %APPDATA% and Documents, not in the program folder).

#ifndef MyAppVersion
  #define MyAppVersion "0.5.0"
#endif

[Setup]
AppId={{5B7D3F0A-2C61-4E8B-9A44-7E1C3D5F8B20}
AppName=StyleVault
AppVersion={#MyAppVersion}
AppPublisher=StyleVault
DefaultDirName={localappdata}\Programs\StyleVault
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=StyleVault-Setup-{#MyAppVersion}
SetupIconFile=..\assets\stylevault.ico
UninstallDisplayIcon={app}\StyleVault.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\StyleVault\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\StyleVault"; Filename: "{app}\StyleVault.exe"
Name: "{userdesktop}\StyleVault"; Filename: "{app}\StyleVault.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StyleVault.exe"; Description: "Open StyleVault now"; Flags: nowait postinstall skipifsilent
; Update from inside the program runs this installer quietly with /RELAUNCH=1: open the program again afterwards.
Filename: "{app}\StyleVault.exe"; Flags: nowait runasoriginaluser; Check: Relaunch

[Code]
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM StyleVault.exe"; Flags: runhidden; RunOnceId: "StopStyleVault"
