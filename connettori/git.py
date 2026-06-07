"""
ARGO - connettori/git.py
Connettore SOLA LETTURA per repository Git locali.

Usa il comando `git` via subprocess (libreria standard) per leggere:
  - stato del repository (git status --porcelain)
  - log degli ultimi N commit (git log --oneline)
  - branch corrente (git rev-parse --abbrev-ref HEAD)

Non esegue mai push, commit, pull o altre operazioni di scrittura.
`disponibile()` = git è presente nel PATH.
"""

import os
import json
import shutil
import subprocess
import sys

# Import difensivo: funziona sia come modulo del pacchetto sia come script diretto
try:
    from .base import Connettore
except ImportError:
    # Eseguito come script diretto (python connettori/git.py)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from connettori.base import Connettore

# --- percorso config ---
_DIR_ARGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILE_CONFIG = os.path.join(_DIR_ARGO, "config", "connettori.json")


def _carica_config_git() -> dict:
    """Legge la sezione git dal file di configurazione connettori."""
    try:
        with open(_FILE_CONFIG, "r", encoding="utf-8") as f:
            dati = json.load(f)
        return dati.get("git", {})
    except Exception:
        return {}


def _esegui_git(args: list[str], cwd: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Esegue un comando git in sola lettura nella cartella `cwd`.

    Ritorna (successo: bool, output: str).
    Non solleva eccezioni: le cattura e le restituisce come errore.
    """
    try:
        risultato = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            # Nessun shell=True per sicurezza
        )
        if risultato.returncode == 0:
            return True, risultato.stdout.strip()
        else:
            errore = risultato.stderr.strip() or f"Codice di uscita: {risultato.returncode}"
            return False, errore
    except FileNotFoundError:
        return False, "Comando 'git' non trovato nel PATH."
    except subprocess.TimeoutExpired:
        return False, "Timeout: il comando git ha impiegato troppo tempo."
    except Exception as e:
        return False, f"Errore imprevisto: {e}"


class ConnettoreGit(Connettore):
    """
    Connettore Git in sola lettura.

    Legge stato, log e informazioni sul branch corrente di un repository locale.

    Parametri accettati in leggi():
      - repo        : str — percorso del repository (default da config)
      - max_commit  : int — numero di commit da leggere nel log (default da config, max 100)
      - operazioni  : list[str] — lista di operazioni da eseguire tra:
                      'stato', 'log', 'branch' (default: tutte e tre)
    """

    @property
    def nome(self) -> str:
        return "git"

    @property
    def descrizione(self) -> str:
        return (
            "Legge stato, log e branch di un repository Git locale in sola lettura. "
            "Richiede che il comando 'git' sia disponibile nel PATH."
        )

    def disponibile(self) -> bool:
        """Ritorna True se il comando 'git' è presente nel PATH di sistema."""
        return shutil.which("git") is not None

    def leggi(self, parametri: dict | None = None) -> list | dict:
        """
        Ritorna un dizionario con le informazioni richieste sul repository.

        Struttura del risultato:
        {
          "repo": "/percorso/repo",
          "branch": "main",
          "stato": [{"simbolo": "M", "file": "..."}],
          "log": [{"hash": "abc1234", "messaggio": "..."}]
        }
        """
        if not self.disponibile():
            return {
                "errore": (
                    "Il comando 'git' non è disponibile nel PATH. "
                    "Installare Git da https://git-scm.com/"
                )
            }

        cfg = _carica_config_git()
        p = parametri or {}

        # --- determina il repository ---
        repo_default = cfg.get("repo_default", "").strip()
        repo = p.get("repo", repo_default)

        if not repo:
            return {"errore": "Nessun repository specificato. Passa 'repo' nei parametri."}

        if not os.path.isdir(repo):
            return {"errore": f"La cartella del repository non esiste: {repo}"}

        max_commit: int = min(int(p.get("max_commit", cfg.get("max_commit", 20))), 100)
        operazioni: list = p.get("operazioni", ["stato", "log", "branch"])

        risultato: dict = {"repo": repo}

        # --- lettura branch corrente ---
        if "branch" in operazioni:
            ok, output = _esegui_git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
            if ok:
                risultato["branch"] = output
            else:
                risultato["branch_errore"] = output

        # --- lettura stato (file modificati, aggiunti, non tracciati) ---
        if "stato" in operazioni:
            ok, output = _esegui_git(["status", "--porcelain"], repo)
            if ok:
                voci_stato = []
                for riga in output.splitlines():
                    if len(riga) >= 3:
                        simbolo = riga[:2].strip()
                        nome_file = riga[3:].strip()
                        voci_stato.append({"simbolo": simbolo, "file": nome_file})
                risultato["stato"] = voci_stato
                risultato["file_modificati"] = len(voci_stato)
            else:
                risultato["stato_errore"] = output

        # --- lettura log commit ---
        if "log" in operazioni:
            ok, output = _esegui_git(
                ["log", f"--max-count={max_commit}", "--oneline", "--no-color"],
                repo,
            )
            if ok:
                voci_log = []
                for riga in output.splitlines():
                    if " " in riga:
                        hash_breve, _, messaggio = riga.partition(" ")
                        voci_log.append({"hash": hash_breve, "messaggio": messaggio})
                risultato["log"] = voci_log
                risultato["commit_letti"] = len(voci_log)
            else:
                risultato["log_errore"] = output

        return risultato


# ---------------------------------------------------------------------------
# Smoke-test: funziona senza credenziali; usa la cartella Argo stessa se
# è un repo git, altrimenti crea un repo temporaneo per il test.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Bootstrap sys.path per esecuzione diretta (python connettori\git.py)
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    import tempfile

    conn = ConnettoreGit()
    print(f"Connettore: {conn}")

    # Verifica disponibile()
    disp = conn.disponibile()
    assert isinstance(disp, bool), "disponibile() deve ritornare bool"

    if not disp:
        print("  git non trovato nel PATH: smoke-test di degradazione.")
        risultato = conn.leggi({"repo": "."})
        assert "errore" in risultato, "Senza git deve ritornare {'errore': ...}"
        print(f"  Degradazione corretta -> {risultato['errore']}")
        print("OK")
    else:
        # Controlla se la cartella Argo è già un repo git
        repo_argo = _DIR_ARGO
        ok_argo, _ = _esegui_git(["rev-parse", "--git-dir"], repo_argo)

        if ok_argo:
            # Usa il repo Argo esistente
            risultato = conn.leggi({"repo": repo_argo, "max_commit": 5})
        else:
            # Crea un repo git temporaneo di prova
            with tempfile.TemporaryDirectory() as tmpdir:
                _esegui_git(["init"], tmpdir)
                _esegui_git(["config", "user.email", "test@argo.local"], tmpdir)
                _esegui_git(["config", "user.name", "ARGO Test"], tmpdir)
                # Crea un file e un commit di prova
                test_file = os.path.join(tmpdir, "prova.txt")
                with open(test_file, "w") as f:
                    f.write("smoke test ARGO")
                _esegui_git(["add", "."], tmpdir)
                _esegui_git(["commit", "-m", "commit di prova smoke test"], tmpdir)
                risultato = conn.leggi({"repo": tmpdir, "max_commit": 5})

        assert isinstance(risultato, dict), "leggi() deve ritornare un dict"
        assert "errore" not in risultato, f"Errore inatteso: {risultato.get('errore')}"

        # Stampa un riepilogo leggibile
        print(f"  Branch: {risultato.get('branch', 'n/d')}")
        print(f"  File modificati: {risultato.get('file_modificati', 0)}")
        print(f"  Commit letti: {risultato.get('commit_letti', 0)}")
        if risultato.get("log"):
            print(f"  Ultimo commit: {risultato['log'][0]['messaggio']}")

        print("OK")
