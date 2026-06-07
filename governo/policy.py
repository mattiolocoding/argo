"""
ARGO - governo/policy.py  (POLICY ENGINE, standard 2026)
Governo dell'azione a runtime: prima di toccare qualcosa, ARGO chiede al policy
engine cosa può fare. Esiti (come i Policy Gates 2026):

  CONSENTI  -> ok, procedi (poi decide il livello di autonomia)
  ESCALA    -> richiede SEMPRE conferma umana, anche se l'autonomia è "agisce"
  BLOCCA    -> azione vietata, non si esegue
  MODIFICA  -> consentito ma con un aggiustamento (es. destinazione forzata)

Le regole stanno in config/policy.json (modificabili). Prima regola che matcha vince.
Solo libreria standard.
"""

import os
import json

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILE = os.path.join(_DIR, "config", "policy.json")

ESITI = ("consenti", "escala", "blocca", "modifica")

# regole di default (sicure e sensate). Modificabili in config/policy.json.
_DEFAULT = {
    "regole": [
        {"nome": "Mai toccare contratti",
         "se": {"nome_contiene": ["contratto", "contract", "nda", "accordo"]},
         "esito": "blocca",
         "motivo": "I contratti non si spostano automaticamente."},
        {"nome": "Dati HR / buste paga: sempre conferma",
         "se": {"nome_contiene": ["busta", "paga", "payroll", "stipendio", "hr",
                                   "cedolino", "dipendent"]},
         "esito": "escala",
         "motivo": "Dati del personale: serve conferma umana."},
        {"nome": "Documenti fiscali/legali: conferma",
         "se": {"nome_contiene": ["fattura", "f24", "imu", "tasse", "notaio",
                                   "sentenza", "ricorso"]},
         "esito": "escala",
         "motivo": "Documento sensibile: meglio confermare."},
        {"nome": "Eliminazioni: vietate in automatico",
         "se": {"azione": ["elimina"]},
         "esito": "blocca",
         "motivo": "ARGO non elimina file."}
    ]
}


class Policy:
    def __init__(self, percorso=None):
        self.percorso = percorso or _FILE
        self.dati = self._carica()

    def _carica(self):
        if os.path.exists(self.percorso):
            try:
                with open(self.percorso, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        try:
            os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
            with open(self.percorso, "w", encoding="utf-8") as f:
                json.dump(_DEFAULT, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return json.loads(json.dumps(_DEFAULT))

    def regole(self):
        return self.dati.get("regole", [])

    def valuta(self, azione, percorso="", categoria=""):
        """Ritorna {esito, motivo, regola}. Default: consenti."""
        nome = os.path.basename(percorso).lower()
        perc = (percorso or "").lower()
        cat = (categoria or "").lower()
        for r in self.regole():
            se = r.get("se", {})
            if "azione" in se and azione not in se["azione"]:
                continue
            if "categoria" in se and cat not in [x.lower() for x in se["categoria"]]:
                continue
            if "nome_contiene" in se and not any(k.lower() in nome for k in se["nome_contiene"]):
                continue
            if "cartella_contiene" in se and not any(k.lower() in perc for k in se["cartella_contiene"]):
                continue
            # tutte le condizioni presenti sono soddisfatte
            if any(k in se for k in ("azione", "categoria", "nome_contiene", "cartella_contiene")):
                return {"esito": r.get("esito", "consenti"),
                        "motivo": r.get("motivo", ""), "regola": r.get("nome", "")}
        return {"esito": "consenti", "motivo": "", "regola": ""}


if __name__ == "__main__":
    p = Policy()
    print(p.valuta("archivia", "C:/Down/Contratto_2025.pdf", "Documenti"))
    print(p.valuta("archivia", "C:/Down/busta_paga_marzo.pdf", "Documenti"))
    print(p.valuta("archivia", "C:/Down/foto.png", "Immagini"))
