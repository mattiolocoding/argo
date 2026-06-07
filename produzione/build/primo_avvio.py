"""
ARGO - produzione/build/primo_avvio.py
Punto di ingresso dell'app installata (usato da Inno Setup e dall'avvio automatico).

Sequenza:
  1) Aggiunge la cartella di installazione al sys.path (trova i moduli ARGO).
  2) Assicura Ollama acceso usando Cervello.assicura_acceso() (lo avvia se spento).
  3) Se il modello preferito non e' ancora scaricato, esegue  ollama pull  (primo avvio).
  4) Avvia argo_app.py in-process (stessa finestra, zero processi extra).

Uso in sviluppo (dalla radice del progetto):
    python produzione\\build\\primo_avvio.py

Uso da installazione (chiamato da Inno Setup o dalla voce di avvio automatico):
    ARGO_PrimoAvvio.exe   (oppure: pythonw.exe primo_avvio.py)
"""

import os
import sys
import shutil
import subprocess

# ---------------------------------------------------------------------------
# Percorsi: questo file vive in  produzione/build/
#           argo_app.py vive nella radice del progetto (due livelli su)
# ---------------------------------------------------------------------------
_QUI  = os.path.dirname(os.path.abspath(__file__))   # produzione/build
_PROD = os.path.dirname(_QUI)                         # produzione
_ARGO = os.path.dirname(_PROD)                        # radice Argo/

# Quando viene lanciato come exe installato, la struttura e':
#   C:\Program Files\ARGO\
#       ARGO.exe           <- entry point principale (argo_app.py bundlato)
#       _internal\         <- moduli Python inclusi da PyInstaller (onedir)
# In quel caso sys.executable punta a ARGO.exe e _MEIPASS contiene i moduli.
# In sviluppo invece aggiungiamo _ARGO al path cosi' i moduli sono raggiungibili.
if _ARGO not in sys.path:
    sys.path.insert(0, _ARGO)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _stampa(msg: str):
    """Stampa con flush immediato (utile anche senza console)."""
    print(msg, flush=True)


def _ollama_exe() -> str | None:
    """Restituisce il percorso dell'eseguibile ollama, o None se non trovato."""
    # Cerca prima nel PATH di sistema
    exe = shutil.which("ollama")
    if exe:
        return exe
    # Posizioni di installazione standard di Ollama su Windows
    candidate = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]
    for p in candidate:
        if os.path.isfile(p):
            return p
    return None


# ---------------------------------------------------------------------------
# Passo 1 — Assicura Ollama acceso + modello presente
# ---------------------------------------------------------------------------

def assicura_ollama_e_modello() -> bool:
    """
    Usa Cervello.assicura_acceso() per avviare Ollama se spento,
    poi verifica/scarica il modello preferito.
    Ritorna True se tutto e' pronto.
    """
    try:
        from cervello import Cervello, MODELLO_PREFERITO
    except ImportError as e:
        _stampa(f"[primo_avvio] Impossibile importare cervello.py: {e}")
        _stampa("  Assicurati di trovarti nella cartella giusta o di aver installato ARGO.")
        return False

    c = Cervello()

    # Accende Ollama se spento (usa il metodo ufficiale del modulo cervello)
    _stampa("[primo_avvio] Controllo Ollama…")
    acceso = c.assicura_acceso(timeout=60, passo=2)
    if not acceso:
        _stampa("[primo_avvio] ATTENZIONE: Ollama non risponde.")
        _stampa("  Installalo da https://ollama.com/ e riprova.")
        return False

    _stampa(f"[primo_avvio] Ollama attivo. Modello preferito: {MODELLO_PREFERITO}")

    # Verifica se il modello e' gia' scaricato
    modelli_presenti = c.modelli()
    modello_ok = any(
        m == MODELLO_PREFERITO or m.startswith(MODELLO_PREFERITO + ":")
        for m in modelli_presenti
    )

    if not modello_ok:
        _stampa(f"[primo_avvio] Modello «{MODELLO_PREFERITO}» non trovato.")
        _stampa("[primo_avvio] Scarico il modello (una volta sola, potrebbe richiedere qualche minuto)…")
        exe = _ollama_exe()
        if not exe:
            _stampa("[primo_avvio] Eseguibile ollama non trovato nel PATH.")
            _stampa("  Esegui manualmente:  ollama pull " + MODELLO_PREFERITO)
            return False
        try:
            ret = subprocess.run([exe, "pull", MODELLO_PREFERITO], check=False)
            if ret.returncode != 0:
                _stampa(f"[primo_avvio] ollama pull ha restituito codice {ret.returncode}.")
                return False
        except Exception as e:
            _stampa(f"[primo_avvio] Errore durante ollama pull: {e}")
            return False
        _stampa(f"[primo_avvio] Modello «{MODELLO_PREFERITO}» scaricato con successo.")
    else:
        _stampa(f"[primo_avvio] Modello presente: {MODELLO_PREFERITO}")

    return True


# ---------------------------------------------------------------------------
# Passo 2 — Avvia la nuova app desktop (argo_app.py)
# ---------------------------------------------------------------------------

def avvia_app():
    """
    Avvia la nuova app desktop Qt (argo_app.py).

    Modalita':
      - In sviluppo:  lancia  python argo_app.py  come sottoprocesso separato.
      - Se lo script e' gia' incluso nel bundle PyInstaller (sys.frozen),
        importa direttamente il main() di argo_app per evitare un secondo processo.
    """
    # Bundle PyInstaller: argo_app e' gia' incluso, lo importiamo direttamente
    if getattr(sys, "frozen", False):
        try:
            import argo_app
            argo_app.main()
            return
        except Exception as e:
            _stampa(f"[primo_avvio] Errore avvio argo_app (bundle): {e}")
            return

    # Sviluppo: avvia come processo separato (niente console su Windows)
    app_py = os.path.join(_ARGO, "argo_app.py")
    if not os.path.isfile(app_py):
        _stampa(f"[primo_avvio] argo_app.py non trovato in: {app_py}")
        return

    # Su Windows usa pythonw.exe per non mostrare la console
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    interprete = pythonw if os.path.isfile(pythonw) else sys.executable

    flags = 0
    if os.name == "nt":
        flags = 0x08000000   # CREATE_NO_WINDOW

    _stampa(f"[primo_avvio] Avvio: {interprete} {app_py}")
    subprocess.Popen([interprete, app_py], creationflags=flags)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _stampa("=== ARGO - Primo avvio ===")

    tutto_ok = assicura_ollama_e_modello()

    if tutto_ok:
        avvia_app()
        _stampa("[primo_avvio] ARGO avviato.")
    else:
        _stampa("[primo_avvio] Avvio interrotto: risolvi i problemi indicati sopra e riprova.")
        sys.exit(1)
