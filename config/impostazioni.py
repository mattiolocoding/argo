"""
ARGO - config/impostazioni.py
Le impostazioni di Argo, leggibili e modificabili (file config.json).

MODELLO DI AUTONOMIA a 3 livelli:
  - "osserva"  -> guarda e basta, non propone azioni
  - "chiede"   -> propone, serve conferma di Davide   (DEFAULT sicuro)
  - "agisce"   -> fa da solo e avvisa dopo
"""

import os
import json

_DIR = os.path.dirname(os.path.abspath(__file__))
_FILE = os.path.join(_DIR, "config.json")

LIVELLI_VALIDI = ("osserva", "chiede", "agisce")
REGOLE_VALIDE = ("tipo", "data", "progetto")

_DEFAULT = {
    "cartelle_sorvegliate": ["sorvegliata"],
    "occhi_tutto_pc": True,
    "regola_ordine": "tipo",
    "soglia_accumulo": 10,
    "cartelle_protette": [
        "Windows", "Program Files", "Program Files (x86)",
        "ProgramData", "System32", "AppData",
    ],
    "autonomia": {
        "default": "chiede",
        "crea_cartella": "agisce",
        "archivia": "chiede",
        "sposta": "chiede",
        "rinomina": "chiede",
        "elimina": "osserva",
    },
}


class Impostazioni:
    def __init__(self, percorso=None):
        self.percorso = percorso or _FILE
        self.dati = self._carica()

    def _carica(self):
        if os.path.exists(self.percorso):
            try:
                with open(self.percorso, "r", encoding="utf-8") as f:
                    dati = json.load(f)
                # completa le chiavi mancanti con i default (robustezza)
                for k, v in _DEFAULT.items():
                    dati.setdefault(k, v)
                return dati
            except Exception:
                pass
        self._scrivi(_DEFAULT)
        return json.loads(json.dumps(_DEFAULT))

    def _scrivi(self, dati):
        os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
        with open(self.percorso, "w", encoding="utf-8") as f:
            json.dump(dati, f, indent=2, ensure_ascii=False)

    def salva(self):
        self._scrivi(self.dati)

    # ---- autonomia ----
    def autonomia(self, azione):
        a = self.dati.get("autonomia", {})
        return a.get(azione, a.get("default", "chiede"))

    def imposta_autonomia(self, azione, livello):
        if livello not in LIVELLI_VALIDI:
            raise ValueError(f"livello non valido: {livello}")
        self.dati.setdefault("autonomia", {})[azione] = livello
        self.salva()

    # ---- cartelle ----
    def cartelle_protette(self):
        return list(self.dati.get("cartelle_protette", []))

    def cartelle_sorvegliate(self):
        return list(self.dati.get("cartelle_sorvegliate", ["sorvegliata"]))

    def occhi_tutto_pc(self):
        return bool(self.dati.get("occhi_tutto_pc", True))

    # ---- regole ----
    def regola_ordine(self):
        r = self.dati.get("regola_ordine", "tipo")
        return r if r in REGOLE_VALIDE else "tipo"

    def soglia_accumulo(self):
        try:
            return int(self.dati.get("soglia_accumulo", 10))
        except Exception:
            return 10


if __name__ == "__main__":
    imp = Impostazioni()
    print("sorvegliate:", imp.cartelle_sorvegliate())
    print("regola:", imp.regola_ordine(), "| soglia:", imp.soglia_accumulo())
    print("autonomia archivia:", imp.autonomia("archivia"))
