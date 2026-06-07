# Come costruire l'installer di ARGO (app desktop Qt)

Obiettivo: un solo `ARGO Setup.exe`, come le big tech. L'utente lo installa
e al primo avvio l'app si connette ad Ollama, scarica il modello e si apre
nella finestra Qt (niente terminale, niente browser).

---

## Architettura a runtime

```
ARGO Setup.exe  ──installa──▶  C:\Program Files\ARGO\
                               ├─ ARGO.exe              ← entry point Qt
                               ├─ _internal\            ← moduli Python + Qt DLL
                               │   ├─ PySide6\          ← Qt + QtWebEngineProcess.exe
                               │   ├─ cervello.pyc
                               │   ├─ motore_web.pyc
                               │   └─ ...tutti i moduli ARGO...
                               ├─ ui\index.html         ← interfaccia web
                               ├─ assets\logo.ico       ← icona
                               └─ config\config.json    ← configurazione

Al primo avvio:
  ARGO.exe  →  server HTTP su 127.0.0.1:8773  +  finestra Qt WebView
```

La finestra Qt incorpora un browser Chromium (QtWebEngineWidgets) che carica
`http://127.0.0.1:8773`. **Non si apre nessuna scheda Edge/Chrome**: tutto
vive dentro la finestra `ARGO`.

---

## Prerequisiti di build

| Strumento | Installazione |
|-----------|---------------|
| Python 3.11+ | https://python.org |
| PyInstaller | `pip install pyinstaller` |
| PySide6 (con WebEngine) | `pip install PySide6` |
| Pillow | `pip install pillow` |
| cairosvg (opzionale, per icona) | `pip install cairosvg` |
| Inno Setup 6 | https://jrsoftware.org/isinfo.php |

---

## Passi di build (eseguire nell'ordine)

### 1. Installa le dipendenze Python

```powershell
pip install pyinstaller pillow PySide6 cairosvg
```

> `cairosvg` e' opzionale: se non si installa, `fai_icona.py` usa PySide6
> come fallback per generare il PNG dal SVG.

---

### 2. Genera l'icona (ICO + PNG)

Dalla radice del progetto (`Desktop\Argo\`):

```powershell
python produzione\build\fai_icona.py
```

Produce:
- `assets\logo.png` (256 × 256)
- `assets\logo.ico` (multi-risoluzione: 16, 32, 48, 64, 128, 256)

Se lo script si lamenta di librerie mancanti, segui le istruzioni a schermo.

---

### 3. Costruisci l'eseguibile con PyInstaller

Dalla radice del progetto (`Desktop\Argo\`):

```powershell
pyinstaller produzione\build\argo.spec
```

Oppure dalla cartella `produzione\build\`:

```powershell
cd produzione\build
pyinstaller argo.spec
```

**Risultato atteso**: cartella `produzione\build\dist\ARGO\` contenente:
- `ARGO.exe` — eseguibile principale (niente console)
- `_internal\` — tutti i moduli Python e le DLL Qt
- `ui\`, `assets\`, `config\` — risorse incluse

> **Nota QtWebEngine**: la cartella `dist\ARGO` sara' grande (300-500 MB)
> perche' include il motore Chromium (`QtWebEngineProcess.exe`, file ICU/pak).
> E' normale: e' il costo di avere un browser embedded senza dipendenze esterne.

---

### 4. (Opzionale) Includi Ollama nell'installer

Se vuoi distribuire Ollama insieme ad ARGO:

1. Scarica `OllamaSetup.exe` da https://ollama.com/download/windows
2. Mettilo nella cartella `produzione\build\`
3. Scommenta le righe relative in `installer.iss` (cercate `OllamaSetup`)

---

### 5. Compila l'installer con Inno Setup

Apri `produzione\build\installer.iss` con Inno Setup e premi **Compile**,
oppure da riga di comando:

```powershell
iscc produzione\build\installer.iss
```

**Risultato**: `produzione\build\Output\ARGO Setup.exe`

---

## Come verificare che l'app funzioni

### Test rapido (senza installare)

Avvia direttamente l'exe prodotto da PyInstaller:

```powershell
produzione\build\dist\ARGO\ARGO.exe
```

Attendi 2-3 secondi (il server parte in background), poi:

1. La finestra Qt deve aprirsi con il titolo `ARGO` e l'interfaccia web caricata.
2. Apri il browser e vai su `http://127.0.0.1:8773` — deve rispondere con la
   stessa interfaccia (conferma che il server HTTP e' attivo).
3. Nella chat scrivi qualcosa: se Ollama e' acceso risponde in italiano.

### Cosa controllare se qualcosa non va

| Sintomo | Causa probabile | Soluzione |
|---------|----------------|-----------|
| Finestra bianca / errore di caricamento | Server non ancora pronto | Aspetta 5 s e ricarica |
| `QtWebEngineProcess` non trovato | `collect_all('PySide6')` non ha incluso il componente | Riesegui `pyinstaller argo.spec` |
| `127.0.0.1:8773` non risponde | `motore_web` non parte | Guarda i log nella console (riavvia con `ARGO.exe` da terminale per vedere stdout) |
| App si chiude subito | Errore di import di un modulo | Riesegui da terminale: `cd dist\ARGO && ARGO.exe` |
| Icona generica (niente logo) | `logo.ico` assente | Esegui `fai_icona.py` e riesegui PyInstaller |

---

## Distribuzione

- Carica `ARGO Setup.exe` su GitHub Releases o sul tuo sito.
- L'utente lo installa e ARGO parte automaticamente ad ogni avvio di Windows
  (collegamento in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`
  + chiave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
- Ollama va installato separatamente (o incluso nell'installer come descritto
  al passo 4): senza di esso la chat risponde `[cervello offline]`.
