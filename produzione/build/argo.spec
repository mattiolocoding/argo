# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# ARGO - PyInstaller spec (app desktop Qt, PySide6 + QWebEngine)
# Entry point: primo_avvio.py  (prepara Ollama/modello, poi apre argo_app.py)
#
# COME USARE:
#   Dalla cartella  produzione\build:
#       pyinstaller argo.spec
#   Oppure da qualsiasi cartella con percorso assoluto:
#       pyinstaller produzione\build\argo.spec
#
# RISULTATO: dist\ARGO\  con  ARGO.exe  (window mode, niente console)
#
# AVVERTENZA QtWebEngine:
#   PySide6.QtWebEngineWidgets e' un componente PESANTE (300-500 MB nel dist).
#   collect_all('PySide6') include il DLL di Chromium (QtWebEngineProcess.exe)
#   e le risorse ICU. Senza di esso la WebView non si apre.
#   Non rimuovere la chiamata collect_all qui sotto.
# =============================================================================

import os
from PyInstaller.utils.hooks import collect_all

# --- Percorsi di progetto (relativi a questo spec) --------------------------
# Questo spec si trova in  produzione/build/argo.spec
# La cartella radice del progetto e' due livelli su.
_SPEC_DIR = os.path.abspath(SPECPATH)   # SPECPATH è GIÀ la cartella del .spec (produzione/build)
_ARGO     = os.path.abspath(os.path.join(_SPEC_DIR, "..", ".."))  # Argo/

# Scorciatoie ai percorsi di dati da includere
_UI      = os.path.join(_ARGO, "ui")
_ASSETS  = os.path.join(_ARGO, "assets")
_CONFIG  = os.path.join(_ARGO, "config")
_HOOKS   = os.path.join(_SPEC_DIR, "hooks")

# --- Raccolta completa PySide6 (incluso QtWebEngineWidgets + risorse) -------
# collect_all restituisce (datas, binaries, hiddenimports) per il pacchetto
# indicato.  E' necessario per QtWebEngineProcess.exe e i file ICU/pak.
pyside6_datas, pyside6_binaries, pyside6_hidden = collect_all("PySide6")

# --- Dati aggiuntivi del progetto -------------------------------------------
# Formato: (sorgente, destinazione_nel_bundle)
# La cartella ui/ contiene index.html; assets/ ha il logo; config/ ha i JSON.
extra_datas = [
    (_UI,     "ui"),
    (_ASSETS, "assets"),
    (_CONFIG, "config"),
]

# Unione datas
all_datas = pyside6_datas + extra_datas

# --- Hidden imports del progetto --------------------------------------------
# PyInstaller non riesce a vedere gli import dinamici (importlib, try/except).
# Elenchiamo qui tutti i moduli del progetto che vengono importati a runtime.
progetto_hidden = [
    # core
    "cervello",
    "motore_web",
    "argo_app",
    "sistema",
    "sicurezza",
    "comprensione",
    "sensi",
    "modelli",
    "workflow",
    # memoria (pacchetto)
    "memoria",
    "memoria.memoria",
    "memoria.grafo",
    "memoria.semantica",
    # mani (pacchetto)
    "mani",
    "mani.mani",
    # config (pacchetto)
    "config",
    "config.impostazioni",
    # governo (pacchetto + tutti i sottomoduli)
    "governo",
    "governo.policy",
    "governo.ruoli",
    "governo.rollback",
    "governo.metriche",
    "governo.consolidamento",
    "governo.agenti",
    "governo.lacune",
    "governo.skill_registry",
    "governo.skill_writer",
    "governo.sonno",
    "governo.sandbox_skill",
    # connettori (pacchetto + tutti i sottomoduli)
    "connettori",
    "connettori.base",
    "connettori.email_imap",
    "connettori.filesystem",
    "connettori.git",
    # dipendenze di terze parti usate dai moduli del progetto
    "sqlite3",
    "cryptography",
    "cryptography.fernet",
    "cryptography.hazmat.primitives",
    "sentence_transformers",
    "sklearn",
    "sklearn.metrics.pairwise",
    "numpy",
    "imaplib",
    "email",
    "email.mime.text",
    "email.mime.multipart",
    "git",        # gitpython (connettori/git.py)
]

all_hidden = pyside6_hidden + progetto_hidden

block_cipher = None

# =============================================================================
# Analysis: raccogli tutto cio' che serve
# =============================================================================
a = Analysis(
    # Entry point: wrapper di primo avvio nella cartella build.
    # Controlla Ollama/modello e poi importa argo_app nel bundle.
    [os.path.join(_SPEC_DIR, "primo_avvio.py")],

    # pathex: dove cercare i moduli del progetto durante l'analisi
    pathex=[_ARGO],

    binaries=pyside6_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,

    hookspath=[_HOOKS],
    hooksconfig={},
    runtime_hooks=[],

    # Escludi Tkinter dall'exe finale (e' usato solo nella logica
    # "primo avvio installa PySide6", che non serve nel bundle distribuito)
    excludes=["tkinter", "_tkinter"],

    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# =============================================================================
# EXE: modalita' onefile=False (onedir), nessuna console (windowed)
# =============================================================================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # i binari stanno nel COLLECT, non nell'EXE
    name="ARGO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                   # comprime i binari con UPX se disponibile
    console=False,              # --noconsole: niente finestra nera

    # Icona dell'eseguibile (file .ico generato da fai_icona.py)
    # Se logo.ico non esiste, PyInstaller ignora il parametro senza errori.
    icon=os.path.join(_ASSETS, "logo.ico"),

    # Metadati visibili in Proprieta' file (Windows)
    version_file=None,
)

# =============================================================================
# COLLECT: raduna EXE + binari + dati in dist/ARGO/
# =============================================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ARGO",    # -> dist/ARGO/
)
