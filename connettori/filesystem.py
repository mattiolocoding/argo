"""
ARGO - connettori/filesystem.py
Connettore SOLA LETTURA per il filesystem locale.

Elenca e cerca file in una cartella specificata, con filtro opzionale
per estensione e stringa nel nome. Non esegue mai scritture.
"""

import os
import json
import sys
from datetime import datetime

# Import difensivo: funziona sia come modulo del pacchetto sia come script diretto
try:
    from .base import Connettore
except ImportError:
    # Eseguito come script diretto (python connettori/filesystem.py)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from connettori.base import Connettore

# Modulo sicurezza (difensivo): protegge da cartelle/file sensibili
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import sicurezza as _sec
except Exception:
    _sec = None

# --- percorso config ---
_DIR_ARGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILE_CONFIG = os.path.join(_DIR_ARGO, "config", "connettori.json")

_CARTELLE_SISTEMA = tuple(
    os.path.abspath(p).lower()
    for p in (
        os.environ.get("SystemRoot", r"C:\Windows"),
        os.path.join(os.environ.get("SystemDrive", "C:"), "Program Files"),
        os.path.join(os.environ.get("SystemDrive", "C:"), "Program Files (x86)"),
        "/etc",
        "/proc",
        "/sys",
        "/boot",
    )
    if p
)


def _carica_config() -> dict:
    """Legge il file di configurazione connettori, ritorna {} se assente."""
    try:
        with open(_FILE_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class ConnettoreFilesystem(Connettore):
    """
    Connettore filesystem in sola lettura.

    Parametri accettati in leggi():
      - cartella   : str  — percorso della cartella da esplorare
                            (se assente usa filesystem.cartella_default da config)
      - ricorsivo  : bool — se True esplora anche le sottocartelle (default False)
      - estensione : str  — filtra per estensione, es. ".py" (default: tutte)
      - cerca      : str  — filtra i nomi che contengono questa stringa (case-insensitive)
      - max_risultati : int — numero massimo di voci restituite (default 100)
    """

    @property
    def nome(self) -> str:
        return "filesystem"

    @property
    def descrizione(self) -> str:
        return (
            "Elenca e cerca file in una cartella locale in sola lettura. "
            "Supporta filtri per estensione, nome e navigazione ricorsiva."
        )

    def disponibile(self) -> bool:
        """Sempre disponibile: il filesystem è sempre accessibile."""
        return True

    def leggi(self, parametri: dict | None = None) -> list | dict:
        """
        Ritorna una lista di dizionari con informazioni sui file trovati.

        Ogni voce contiene: percorso, nome, estensione, dimensione_bytes, modificato.
        """
        p = parametri or {}

        # --- determina la cartella da esplorare ---
        config = _carica_config()
        cartella_default = config.get("filesystem", {}).get("cartella_default", "")
        cartella = p.get("cartella", cartella_default)

        if not cartella:
            return {"errore": "Nessuna cartella specificata. Passa 'cartella' nei parametri."}

        if cartella_default and _sec and not _sec.percorso_sicuro(cartella_default, cartella):
            return {
                "errore": (
                    f"Accesso negato: '{cartella}' non e' dentro la radice configurata "
                    f"'{cartella_default}'. Modifica config/connettori.json per ampliare l'accesso."
                )
            }

        cartella_abs = os.path.abspath(cartella).lower()
        if any(cartella_abs == c or cartella_abs.startswith(c + os.sep) for c in _CARTELLE_SISTEMA):
            return {"errore": f"Accesso a cartella di sistema non consentito: '{cartella}'"}

        if not os.path.isdir(cartella):
            return {"errore": f"La cartella non esiste o non è accessibile: {cartella}"}

        # SICUREZZA: non esplorare aree sensibili (.ssh, credenziali, ecc.)
        if _sec and _sec.file_sensibile(cartella):
            return {"errore": "Cartella sensibile: accesso negato per sicurezza."}

        # --- parametri di filtro ---
        ricorsivo: bool = bool(p.get("ricorsivo", False))
        estensione: str = p.get("estensione", "").lower()
        cerca: str = p.get("cerca", "").lower()
        max_risultati: int = int(p.get("max_risultati", 100))

        risultati = []

        try:
            if ricorsivo:
                # os.walk non solleva eccezioni: gestisce gli errori internamente
                generatore = (
                    (radice, f)
                    for radice, _, files in os.walk(cartella)
                    for f in files
                )
            else:
                generatore = (
                    (cartella, f)
                    for f in os.listdir(cartella)
                    if os.path.isfile(os.path.join(cartella, f))
                )

            for radice, nome_file in generatore:
                if len(risultati) >= max_risultati:
                    break

                # --- applicazione filtri ---
                nome_lower = nome_file.lower()
                _, ext = os.path.splitext(nome_file)
                ext_lower = ext.lower()

                if estensione and ext_lower != estensione:
                    continue
                if cerca and cerca not in nome_lower:
                    continue

                percorso_completo = os.path.join(radice, nome_file)
                # SICUREZZA: non elencare file sensibili (password, chiavi…)
                if _sec and _sec.file_sensibile(percorso_completo):
                    continue
                try:
                    stat = os.stat(percorso_completo)
                    risultati.append({
                        "percorso": percorso_completo,
                        "nome": nome_file,
                        "estensione": ext_lower,
                        "dimensione_bytes": stat.st_size,
                        "modificato": datetime.fromtimestamp(stat.st_mtime).isoformat(
                            timespec="seconds"
                        ),
                    })
                except OSError:
                    # file non accessibile: lo saltiamo silenziosamente
                    continue

        except Exception as e:
            return {"errore": f"Errore durante la lettura della cartella: {e}"}

        return risultati


# ---------------------------------------------------------------------------
# Smoke-test: eseguibile senza credenziali reali
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Bootstrap sys.path per esecuzione diretta (python connettori\filesystem.py)
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    import tempfile

    conn = ConnettoreFilesystem()
    print(f"Connettore: {conn}")

    # Crea una cartella temporanea con file di prova
    with tempfile.TemporaryDirectory() as tmpdir:
        # Crea 3 file di prova
        for nome in ["alpha.txt", "beta.py", "gamma.txt"]:
            with open(os.path.join(tmpdir, nome), "w") as f:
                f.write(f"contenuto di {nome}")

        # Test 1: lista completa
        risultati = conn.leggi({"cartella": tmpdir})
        assert isinstance(risultati, list), "Atteso una lista"
        assert len(risultati) == 3, f"Attesi 3 file, trovati {len(risultati)}"

        # Test 2: filtro per estensione
        risultati_py = conn.leggi({"cartella": tmpdir, "estensione": ".py"})
        assert len(risultati_py) == 1, f"Atteso 1 file .py, trovati {len(risultati_py)}"

        # Test 3: filtro per nome
        risultati_cerca = conn.leggi({"cartella": tmpdir, "cerca": "alpha"})
        assert len(risultati_cerca) == 1, f"Atteso 1 file con 'alpha', trovati {len(risultati_cerca)}"

        # Test 4: cartella inesistente
        errore = conn.leggi({"cartella": "/percorso/inesistente/xyz"})
        assert "errore" in errore, "Atteso un dizionario con 'errore'"

    print("OK")
