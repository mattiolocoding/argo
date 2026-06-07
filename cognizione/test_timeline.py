"""
Test standalone:
    python cognizione\\test_timeline.py
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from cognizione import TimelineCognitiva, normalizza_evento


def _db_temp():
    fd, path = tempfile.mkstemp(prefix="argo_cognizione_", suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


def test_normalizza():
    e = normalizza_evento(
        "file_aggiunto",
        riferimento=r"C:\Users\Davide\Desktop\ProgettoX\report.pdf",
        quando="2026-06-06T10:00:00",
    )
    assert e.tipo == "file_visto"
    assert e.giorno == "2026-06-06"
    assert e.progetto == "ProgettoX"


def test_storage_timeline_inferenze():
    db = _db_temp()
    try:
        c = TimelineCognitiva(db)
        giorno = "2026-06-06"
        c.registra_file(r"C:\Users\Davide\Desktop\ClienteA\offerta.pdf", quando=f"{giorno}T09:00:00")
        c.registra_file(r"C:\Users\Davide\Desktop\ClienteA\foto.jpg", quando=f"{giorno}T09:01:00")
        c.registra_finestra("ClienteA - preventivo - Visual Studio Code", quando=f"{giorno}T09:02:00")
        c.registra_chat("cosa devo fare sul cliente A?", quando=f"{giorno}T09:03:00")
        c.registra_azione("proposta archiviazione", riferimento=r"C:\Users\Davide\Desktop\ClienteA\offerta.pdf", quando=f"{giorno}T09:04:00")
        c.registra_azione("proposta archiviazione", riferimento=r"C:\Users\Davide\Desktop\ClienteA\foto.jpg", quando=f"{giorno}T09:05:00")
        c.registra_rischio("password rilevata e ignorata", livello="alto", riferimento=r"C:\Users\Davide\Desktop\ClienteA\password.txt", quando=f"{giorno}T09:06:00")

        timeline = c.timeline_giorno(giorno)
        assert len(timeline) == 7
        assert timeline[0]["tipo"] == "file_visto"

        riepilogo = c.riepilogo_giorno(giorno)
        assert riepilogo["conteggi"]["file_visto"] == 2
        assert riepilogo["conteggi"]["azione"] == 2
        assert riepilogo["conteggi"]["rischio"] == 1
        assert riepilogo["progetti"][0]["nome"] == "ClienteA"
        assert any(p["tipo"] == "azione_ripetuta" for p in riepilogo["pattern"])
        assert riepilogo["suggerimenti"]

        trovati = c.cerca("offerta")
        assert trovati and trovati[0]["tipo"] in {"azione", "file_visto"}
        c.chiudi()
    finally:
        if os.path.exists(db):
            os.remove(db)


def main():
    test_normalizza()
    test_storage_timeline_inferenze()
    print("OK cognizione timeline")


if __name__ == "__main__":
    main()
