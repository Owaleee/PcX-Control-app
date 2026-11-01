; Instalador do agente do PcX Control (Inno Setup 6).
; Uso: iscc /DAppVersion=0.3.0 packaging\installer.iss  (na pasta agent, depois do PyInstaller)

#ifndef AppVersion
  #error Informe a versao: iscc /DAppVersion=X.Y.Z installer.iss
#endif

[Setup]
AppId={{6E0B7C4A-2F1D-4B8E-9C3A-5D7F1E2A9B60}
AppName=PcX Control
AppVersion={#AppVersion}
AppVerName=PcX Control {#AppVersion}
AppPublisher=Alexandre Queiroz
AppPublisherURL=https://github.com/Owaleee/PcX-Control-app
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\PcX Control
DisableProgramGroupPage=yes
DefaultGroupName=PcX Control
AppMutex=Local\PcXControl.Agent
CloseApplications=yes
OutputDir=Output
OutputBaseFilename=PcXControl-Setup-{#AppVersion}
SetupIconFile=..\pcx_agent\assets\icon.ico
UninstallDisplayIcon={app}\PcXControl.exe
UninstallDisplayName=PcX Control
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "autostart"; Description: "Iniciar com o Windows"
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\PcXControl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "firewall.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\PcX Control"; Filename: "{app}\PcXControl.exe"
Name: "{autodesktop}\PcX Control"; Filename: "{app}\PcXControl.exe"; Tasks: desktopicon

[Registry]
; Mesmo valor que o agente grava em "Iniciar com o Windows" (pcx_agent/winsys/autostart.py).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PcXControl"; ValueData: """{app}\PcXControl.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Um unico pedido de administrador, so para a regra de firewall. Se for negado, a instalacao segue.
Filename: "{cmd}"; Parameters: "/c """"{app}\firewall.cmd"" add ""{app}\PcXControl.exe"""""; Verb: runas; Flags: shellexec runhidden waituntilterminated; StatusMsg: "Liberando o PcX Control na rede privada..."
Filename: "{app}\PcXControl.exe"; Description: "Abrir o PcX Control"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c """"{app}\firewall.cmd"" remove"""; Verb: runas; Flags: shellexec runhidden waituntilterminated; RunOnceId: "RemoveFirewall"
