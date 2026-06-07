"""
Demo standalone:
    python cognizione\\demo_timeline.py

Crea una timeline cognitiva in memoria temporanea e stampa un riepilogo.
"""

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from cognizione import TimelineCognitiva


def main():
    giorno = "2026-06-06"
    db = os.path.join(tempfile.gettempdir(), "argo_demo_cognizione.db")
    if os.path.exists(db):
        os.remove(db)

    c = TimelineCognitiva(db)
    c.registra_file(r"C:\Users\Davide\Desktop\Argo\docs\visione.pdf", quando=f"{giorno}T09:00:00")
    c.registra_finestra("ARGO_VISIONE_ENTERPRISE.md - Visual Studio Code", quando=f"{giorno}T09:04:00")
    c.registra_chat("cosa manca rispetto alla visione enterprise?", quando=f"{giorno}T09:08:00")
    c.registra_azione(
        "proposta archiviazione",
        riferimento=r"C:\Users\Davide\Desktop\Argo\docs\visione.pdf",
        esito="confermata",
        quando=f"{giorno}T09:12:00",
    )
    c.registra_rischio(
        "file sensibile non toccato",
        livello="alto",
        riferimento=r"C:\Users\Davide\Desktop\Argo\sorvegliata\password.txt",
        quando=f"{giorno}T09:20:00",
    )

    print(json.dumps(c.riepilogo_giorno(giorno), indent=2, ensure_ascii=False))
    c.chiudi()


if __name__ == "__main__":
    main()
