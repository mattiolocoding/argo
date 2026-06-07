; =============================================================================
; ARGO - Inno Setup 6 installer
; Genera "ARGO Setup.exe": installa l'app, crea collegamento nel menu Start
; e nell'Esecuzione automatica (Startup), lancia l'app a fine installazione.
;
; PREREQUISITI:
;   1) Inno Setup 6   -> https://jrsoftware.org/isinfo.php
;   2) Costruisci prima l'app:
;        pyinstaller produzione\build\argo.spec
;      Questo produce  produzione\build\dist\ARGO\  con  ARGO.exe + _internal\
;   3) Apri questo file con Inno Setup e premi "Compile"  (oppure iscc installer.iss)
;
; OUTPUT: produzione\build\Output\ARGO Setup.exe
; =============================================================================

#define MyApp       "ARGO"
#define MyVer       "1.0"
#define MyPublisher "Davide Tufilli"
#define MyExeName   "ARGO.exe"
#define MyIconName  "logo.ico"

; Percorso relativo a questo .iss (produzione\build\)
; La cartella dist viene prodotta da PyInstaller nella stessa posizione.
#define DistDir     "dist\ARGO"

[Setup]
; --- Identita' ---
AppName={#MyApp}
AppVersion={#MyVer}
AppPublisher={#MyPublisher}
AppId={{A7B3C2D1-4E5F-6789-ABCD-EF0123456789}

; --- Cartella di installazione ---
; {autopf} = Program Files o Program Files (x86) in base all'architettura
DefaultDirName={autopf}\{#MyApp}
DefaultGroupName={#MyApp}
DisableProgramGroupPage=yes

; --- Output installer ---
OutputDir=Output
OutputBaseFilename=ARGO Setup

; --- Aspetto ---
; Richiede logo.ico nella stessa cartella di questo .iss (generato da fai_icona.py)
SetupIconFile=dist\ARGO\assets\{#MyIconName}
WizardStyle=modern
WizardSmallImageFile=dist\ARGO\assets\{#MyIconName}

; --- Requisiti di sistema ---
; Solo Windows 64-bit (Qt WebEngine richiede x64)
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0

; --- Permessi: installa senza admin (per default in Program Files locale) ---
; Cambia in "admin" se vuoi installare in Program Files condiviso
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; --- Compressione ---
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Dirs]
; Crea le cartelle dati utente (la memoria di ARGO) con permessi in scrittura
Name: "{localappdata}\ARGO\memoria"
Name: "{localappdata}\ARGO\config"

[Files]
; Tutto il bundle prodotto da PyInstaller (ARGO.exe + _internal\ + ui\ + assets\ + config\)
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; (Opzionale) installer di Ollama da includere nell'installer:
; Scarica da https://ollama.com/download/windows e decommentare le righe seguenti.
; Source: "OllamaSetup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
; Collegamento nel menu Start
Name: "{group}\{#MyApp}"; \
      Filename: "{app}\{#MyExeName}"; \
      IconFilename: "{app}\assets\{#MyIconName}"; \
      Comment: "Avvia ARGO — il tuo assistente personale"

; Collegamento sul Desktop (opzionale — l'utente puo' scegliere)
Name: "{userdesktop}\{#MyApp}"; \
      Filename: "{app}\{#MyExeName}"; \
      IconFilename: "{app}\assets\{#MyIconName}"; \
      Tasks: desktopicon

; Esecuzione automatica all'avvio di Windows (HKCU, nessun admin richiesto)
; Punta direttamente a ARGO.exe: all'avvio apre il server su 127.0.0.1:8773
; e la finestra Qt (argo_app.py bundlato).
Name: "{userstartup}\{#MyApp}"; \
      Filename: "{app}\{#MyExeName}"; \
      IconFilename: "{app}\assets\{#MyIconName}"; \
      Comment: "ARGO parte all'avvio di Windows"

[Tasks]
Name: "desktopicon"; Description: "Crea collegamento sul Desktop"; \
      GroupDescription: "Opzioni aggiuntive:"; Flags: unchecked

[Registry]
; Aggiunge anche la chiave Run nel registro (doppio meccanismo di avvio automatico)
Root: HKCU; \
      Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
      ValueType: string; ValueName: "{#MyApp}"; \
      ValueData: """{app}\{#MyExeName}"""; \
      Flags: uninsdeletevalue

[Run]
; (Opzionale) installa Ollama in silenzio se incluso sopra:
; Filename: "{tmp}\OllamaSetup.exe"; \
;           Parameters: "/VERYSILENT /NORESTART"; \
;           StatusMsg: "Installo Ollama (motore AI)…"; \
;           Flags: waituntilterminated

; Avvia ARGO a fine installazione (nowait = non blocca il wizard)
; ARGO.exe bundlato esegue la stessa logica di primo_avvio:
;   - accende Ollama se spento
;   - scarica il modello se mancante
;   - apre la finestra Qt su 127.0.0.1:8773
Filename: "{app}\{#MyExeName}"; \
          Description: "Avvia ARGO ora"; \
          Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Rimuove i file generati a runtime (log, cache) ma NON la memoria dell'utente
Type: filesandordirs; Name: "{app}\__pycache__"
