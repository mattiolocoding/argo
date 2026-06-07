# ARGO — installer one-command (Windows / PowerShell)
#
#   irm https://raw.githubusercontent.com/mattiolocoding/argo/main/install.ps1 | iex
#
# Clona ARGO, prepara un ambiente isolato, controlla Ollama (scarica i modelli),
# crea il comando `argo` e avvia l'app desktop. Idempotente: rilanciarlo aggiorna.

$ErrorActionPreference = "Stop"
$Repo = "https://github.com/mattiolocoding/argo.git"
$Dest = Join-Path $env:USERPROFILE "argo"

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }

Step "ARGO installer"

# --- prerequisiti ---
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git non trovato. Installa Git (https://git-scm.com) e riprova."
}
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py -or $py -like "*WindowsApps*") {
  throw "Python 3.11+ non trovato (lo stub di Microsoft Store non basta). Installalo da https://python.org o 'winget install Python.Python.3.11'."
}

# --- codice ---
if (Test-Path (Join-Path $Dest ".git")) {
  Step "Aggiorno ARGO in $Dest"
  git -C $Dest pull --ff-only
} else {
  Step "Clono ARGO in $Dest"
  git clone --depth 1 $Repo $Dest
}
Set-Location $Dest

# --- ambiente isolato ---
Step "Creo l'ambiente Python (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & python -m venv .venv }
$venv = ".\.venv\Scripts\python.exe"
& $venv -m pip install --quiet --upgrade pip
Step "Installo i componenti opzionali (finestra nativa, cifratura)"
& $venv -m pip install --quiet -r requirements.txt

# --- Ollama (il cervello locale) ---
if (Get-Command ollama -ErrorAction SilentlyContinue) {
  Step "Ollama trovato: scarico i modelli (se mancano)"
  ollama pull qwen2.5:7b-instruct
  ollama pull nomic-embed-text
} else {
  Write-Host "!  Ollama non trovato: installalo da https://ollama.com per il cervello locale. ARGO parte comunque." -ForegroundColor Yellow
}

# --- comando `argo` ---
Step "Creo il comando 'argo'"
$bin = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
$shim = Join-Path $bin "argo.cmd"
"@echo off`r`n`"$Dest\.venv\Scripts\python.exe`" `"$Dest\cli.py`" %*" | Set-Content -Path $shim -Encoding ascii
Write-Host "   creato $shim (gia' nel PATH)" -ForegroundColor DarkGray

Step "Fatto. Avvio ARGO..."
Write-Host "   In futuro: digita  argo   (desktop) ·  argo engine  (headless) ·  argo fleet" -ForegroundColor DarkGray
& $venv "$Dest\argo_app.py"
