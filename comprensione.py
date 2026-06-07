"""
ARGO - comprensione.py  (Fase 4 - memoria profonda, parte 1: il contenuto)
Argo non guarda solo il TIPO di file, ma ne capisce il CONTENUTO.
Per i file testuali (txt, md, csv, log, json, codice) legge il testo e usa il
cervello (Ollama) per: un riassunto in una riga + una categoria/nome sensato.

Robusto: legge al massimo pochi KB, niente crash se il file e' binario o grande.
Nessuna libreria da installare.

Prova:  python comprensione.py percorso\\del\\file.txt
"""

import os
from cervello import Cervello

# estensioni di cui possiamo leggere il testo in modo sicuro
TESTUALI = {".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".ts",
            ".html", ".css", ".ini", ".cfg", ".xml", ".yaml", ".yml", ".sql"}

MAX_BYTES = 8000   # leggiamo solo l'inizio: basta per capire di cosa parla


def leggibile(file_path):
    return os.path.splitext(file_path)[1].lower() in TESTUALI


def _estrai_testo(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(MAX_BYTES)
    except Exception:
        return ""


class Comprensione:
    def __init__(self, cervello=None):
        self.cervello = cervello or Cervello()

    def capisci(self, file_path):
        """Ritorna {'riassunto':..., 'categoria':...} o None se non possibile."""
        if not os.path.isfile(file_path) or not leggibile(file_path):
            return None
        if not self.cervello.vivo():
            return None
        testo = _estrai_testo(file_path)
        if not testo.strip():
            return None
        nome = os.path.basename(file_path)
        prompt = (
            f"Questo e' l'inizio del file «{nome}»:\n\n{testo}\n\n"
            "In UNA sola riga dimmi di cosa parla. "
            "Poi, su una seconda riga, scrivi: CATEGORIA: <una parola>."
        )
        risposta = self.cervello.pensa(prompt)
        riassunto, categoria = risposta, None
        for riga in risposta.splitlines():
            if riga.upper().startswith("CATEGORIA:"):
                categoria = riga.split(":", 1)[1].strip()
                riassunto = risposta.replace(riga, "").strip()
                break
        return {"riassunto": riassunto.strip(), "categoria": categoria}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python comprensione.py <percorso_file>")
        raise SystemExit(0)
    c = Comprensione()
    r = c.capisci(sys.argv[1])
    if r is None:
        print("Non riesco a leggerne il contenuto (non testuale, vuoto o cervello offline).")
    else:
        print("Riassunto:", r["riassunto"])
        print("Categoria:", r["categoria"])
