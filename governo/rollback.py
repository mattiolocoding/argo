"""
ARGO - governo/rollback.py  (ANNULLA: ogni azione reversibile)
Enterprise non accetta "ho spostato e basta". Ogni azione reversibile registra
il suo PIANO INVERSO, così si può sempre annullare.

  sposta/archivia A->B   => inverso: sposta B->A
  rinomina A->B          => inverso: sposta B->A
  crea_cartella X        => inverso: rimuovi X se vuota

SQLite locale. Solo libreria standard.
"""

import os
import json
import sqlite3
import datetime

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def piano_inverso(piano):
    az = piano.get("azione")
    if az in ("sposta", "archivia", "rinomina"):
        return {"azione": "sposta",
                "sorgente": piano.get("destinazione"),
                "destinazione": piano.get("sorgente"),
                "descrizione": "Annullo: " + piano.get("descrizione", "")}
    if az == "crea_cartella":
        return {"azione": "rimuovi_cartella_vuota",
                "destinazione": piano.get("destinazione"),
                "descrizione": "Annullo creazione cartella"}
    return None


class Rollback:
    def __init__(self, percorso=None):
        self.percorso = percorso or os.path.join(_DIR, "memoria", "argo_rollback.db")
        os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS azioni (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                quando      TEXT,
                descrizione TEXT,
                inverso     TEXT,
                annullata   INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def registra(self, piano):
        inv = piano_inverso(piano)
        if not inv:
            return None
        c = self.conn.cursor()
        c.execute("INSERT INTO azioni (quando, descrizione, inverso) VALUES (?,?,?)",
                  (_ora(), piano.get("descrizione", ""), json.dumps(inv)))
        self.conn.commit()
        return c.lastrowid

    def ultima_annullabile(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM azioni WHERE annullata=0 ORDER BY id DESC LIMIT 1")
        r = c.fetchone()
        return dict(r) if r else None

    def annulla_ultima(self, mani):
        """Esegue il piano inverso dell'ultima azione, in sicurezza (via mani)."""
        r = self.ultima_annullabile()
        if not r:
            return {"ok": False, "messaggio": "niente da annullare"}
        inv = json.loads(r["inverso"])
        if inv.get("azione") == "rimuovi_cartella_vuota":
            try:
                d = inv.get("destinazione")
                if d and os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
                    esito = {"ok": True, "messaggio": "cartella rimossa"}
                else:
                    esito = {"ok": False, "messaggio": "cartella non vuota, non rimuovo"}
            except Exception as e:
                esito = {"ok": False, "messaggio": str(e)}
        else:
            esito = mani.esegui(inv)
        if esito.get("ok"):
            self.conn.execute("UPDATE azioni SET annullata=1 WHERE id=?", (r["id"],))
            self.conn.commit()
        return esito

    def lista(self, n=10):
        c = self.conn.cursor()
        c.execute("SELECT quando, descrizione, annullata FROM azioni ORDER BY id DESC LIMIT ?", (n,))
        return [dict(x) for x in c.fetchall()]

    def chiudi(self):
        self.conn.close()
