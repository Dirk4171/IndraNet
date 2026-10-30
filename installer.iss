; ===========================================================================
;  IndraNet — Windows-Installationsprogramm
;
;  Erzeugt mit Inno Setup 6 (https://jrsoftware.org/isdl.php)
;
;  Voraussetzung: build_windows.bat wurde bereits ausgefuehrt,
;                 dist\IndraNet\ existiert.
;
;  Aufruf: Diese Datei mit Inno Setup oeffnen, auf "Compile" klicken.
;  Ergebnis: Ausgabe\IndraNet-Setup-2.0.exe
; ===========================================================================

#define AppName      "IndraNet"
#define AppVersion   "2.0"
#define AppPublisher "VELVIUM Technologies UG (haftungsbeschraenkt)"
#define AppExeName   "IndraNet.exe"

[Setup]
AppId={{7C4E1A92-3B5D-4F18-9A6E-2D8C1F4B7E03}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Ausgabe
OutputBaseFilename=IndraNet-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Installation ohne Administratorrechte moeglich: Redaktionsrechner sind
; oft verwaltet, und ein Werkzeug fuer Quellenmaterial sollte nicht
; zwingend durch die IT-Abteilung laufen muessen.
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=LICENSE
InfoBeforeFile=HINWEIS_VOR_INSTALLATION.txt
UninstallDisplayName={#AppName} {#AppVersion}
; SetupIconFile=indranet.ico

[Languages]
Name: "deutsch"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
deutsch.CreateDesktopIcon=Verkn&uepfung auf dem Desktop erstellen
deutsch.LaunchApp=IndraNet jetzt starten
deutsch.OpenManual=Handbuch oeffnen
english.CreateDesktopIcon=Create a &desktop shortcut
english.LaunchApp=Launch IndraNet now
english.OpenManual=Open the manual

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
      GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\IndraNet\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\IndraNet\_internal\*"; DestDir: "{app}\_internal"; \
        Flags: ignoreversion recursesubdirs createallsubdirs
; Tor (optional): Tor Expert Bundle im Ordner "tor" neben dieser Datei
Source: "tor\*"; DestDir: "{app}\tor"; \
        Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; Dokumentation liegt flach im Projektordner, nicht in einem Unterordner —
; ein Unterordner ist eine Fehlerquelle beim Zusammenstellen der Dateien.
Source: "README.md";          DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "LIESMICH_V2.md";     DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "MANUAL.de.md";       DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "MANUAL.en.md";       DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "WHITEPAPER.de.md";   DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "WHITEPAPER.en.md";   DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "LIZENZHINWEIS.md";   DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "HINWEIS_VOR_INSTALLATION.txt"; DestDir: "{app}\Dokumentation"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:OpenManual}"; Filename: "{app}\Dokumentation\MANUAL.de.md"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
      Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchApp}"; \
          Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Die Pods im Benutzerprofil werden NICHT geloescht. Wer das Programm
; entfernt, will seine Recherchen nicht verlieren — und ein Deinstallations-
; programm, das Quellenmaterial vernichtet, waere ein schwerer Fehler.
Type: files; Name: "{app}\*.log"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  DatenOrdner: String;
begin
  if CurStep = ssPostInstall then
  begin
    DatenOrdner := ExpandConstant('{userappdata}\IndraNet');
    if not DirExists(DatenOrdner) then
      CreateDir(DatenOrdner);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := MsgBox(
    'IndraNet wird entfernt.' + #13#10 + #13#10 +
    'Ihre Projekte (.indra-Dateien) bleiben erhalten unter:' + #13#10 +
    ExpandConstant('{userappdata}\IndraNet') + #13#10 + #13#10 +
    'Fortfahren?',
    mbConfirmation, MB_YESNO) = IDYES;
end;
