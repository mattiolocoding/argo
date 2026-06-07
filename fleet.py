"""
ARGO — Flotta (scaling orizzontale).

Aggrega lo stato di piu' istanze ARGO che girano su porte o macchine diverse.
Ogni istanza espone l'endpoint `/identita`; la flotta le interroga in parallelo
e somma lo stato (ricordi, azioni, istanze online). E' la fondazione di una
"console centrale" che vede tutta la flotta.

Principi del progetto rispettati:
  - 100% standard library (nessuna dipendenza esterna).
  - Locale per default; gli endpoint restano su 127.0.0.1 a meno che TU non
    elenchi esplicitamente altri host.
  - Degrada con grazia: un'istanza che non risponde non rompe la panoramica.

Come si elencano le istanze (in ordine di priorita'):
  1. argomento `peers=[...]` al costruttore;
  2. variabile d'ambiente  ARGO_FLOTTA="http://127.0.0.1:8773,http://127.0.0.1:8774";
  3. file  config/flotta.json  ->  {"istanze": ["http://127.0.0.1:8773", ...]}.
"""

import os
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG = os.path.join(_DIR, "config", "flotta.json")

TIMEOUT = 3          # secondi per istanza
MAX_PARALLELE = 16   # quante istanze interrogare insieme


def _normalizza(base: str) -> str:
    base = (base or "").strip().rstrip("/")
    if base and not base.startswith(("http://", "https://")):
        base = "http://" + base
    return base


def _peers_da_ambiente() -> list:
    raw = os.environ.get("ARGO_FLOTTA", "")
    return [b for b in (_normalizza(p) for p in raw.split(",")) if b]


def _peers_da_file(percorso: str = _CONFIG) -> list:
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            dati = json.load(f)
        return [b for b in (_normalizza(p) for p in dati.get("istanze", [])) if b]
    except Exception:
        return []


def interroga(base: str) -> dict:
    """Interroga /identita di una singola istanza. Non solleva mai."""
    base = _normalizza(base)
    try:
        req = urllib.request.Request(base + "/identita", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            dati = json.loads(r.read().decode("utf-8"))
        if not isinstance(dati, dict):
            dati = {}
        dati["_base"] = base
        dati["_online"] = True
        return dati
    except Exception as e:
        return {"_base": base, "_online": False, "errore": str(e)[:140]}


class Flotta:
    """Registro di istanze ARGO + panoramica aggregata."""

    def __init__(self, peers=None):
        peers = peers if peers is not None else (_peers_da_ambiente() or _peers_da_file())
        # dedup mantenendo l'ordine
        viste, ordinate = set(), []
        for b in (_normalizza(p) for p in peers):
            if b and b not in viste:
                viste.add(b)
                ordinate.append(b)
        self.peers = ordinate

    def aggiungi(self, base: str):
        base = _normalizza(base)
        if base and base not in self.peers:
            self.peers.append(base)
        return self.peers

    def panoramica(self) -> dict:
        if not self.peers:
            return {"totale": 0, "online": 0, "ricordi_totali": 0,
                    "azioni_totali": 0, "istanze": []}
        n = min(MAX_PARALLELE, len(self.peers))
        with ThreadPoolExecutor(max_workers=n) as ex:
            istanze = list(ex.map(interroga, self.peers))
        online = [i for i in istanze if i.get("_online")]
        return {
            "totale": len(istanze),
            "online": len(online),
            "offline": len(istanze) - len(online),
            "ricordi_totali": sum(int(i.get("ricordi", 0) or 0) for i in online),
            "azioni_totali": sum(int(i.get("azioni", 0) or 0) for i in online),
            "versioni": sorted({i.get("versione", "?") for i in online}),
            "istanze": istanze,
        }


if __name__ == "__main__":
    # Self-test: se non c'e' nessun peer configurato, prova l'istanza locale.
    f = Flotta()
    if not f.peers:
        f.aggiungi("http://127.0.0.1:8773")
        print("(nessun peer configurato: provo l'istanza locale)")
    print("Peers:", f.peers)
    pan = f.panoramica()
    print(json.dumps(pan, indent=2, ensure_ascii=False))
    print("OK")
