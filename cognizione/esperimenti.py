"""
ARGO - cognizione/esperimenti.py
Registro A/B locale per misurare strategie cognitive senza riaddestrare modelli.
"""

import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "memoria", "argo_esperimenti.db")


def _now():
    return datetime.now().isoformat(timespec="seconds")


class EsperimentiCognitivi:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS esperimenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quando TEXT NOT NULL,
                nome TEXT NOT NULL,
                variabile TEXT,
                variante_a TEXT,
                variante_b TEXT,
                risultato_a TEXT,
                risultato_b TEXT,
                vincitore TEXT,
                nota TEXT
            )
            """
        )
        self.conn.commit()

    def registra(self, nome, variabile="", variante_a="", variante_b="",
                 risultato_a=None, risultato_b=None, vincitore=None, nota=""):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO esperimenti(quando, nome, variabile, variante_a, variante_b,
                                    risultato_a, risultato_b, vincitore, nota)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(), str(nome)[:160], str(variabile)[:160],
                str(variante_a)[:300], str(variante_b)[:300],
                "" if risultato_a is None else str(risultato_a)[:500],
                "" if risultato_b is None else str(risultato_b)[:500],
                "" if vincitore is None else str(vincitore)[:80],
                str(nota or "")[:1000],
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def recenti(self, limite=20):
        limite = max(1, min(int(limite or 20), 100))
        rows = self.conn.execute(
            "SELECT * FROM esperimenti ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def statistiche(self):
        totale = self.conn.execute("SELECT COUNT(*) FROM esperimenti").fetchone()[0]
        winners = self.conn.execute(
            "SELECT vincitore, COUNT(*) AS n FROM esperimenti WHERE vincitore != '' GROUP BY vincitore"
        ).fetchall()
        return {"totale": totale, "vincitori": [{"vincitore": r["vincitore"], "n": r["n"]} for r in winners]}

    def valuta_deliberazione(self, domanda, risposta_diretta, risposta_deliberata, scelta="deliberata"):
        return self.registra(
            "chat_deliberazione",
            "qualita_risposta",
            "diretta",
            "deliberata",
            risposta_diretta,
            risposta_deliberata,
            scelta,
            domanda,
        )

    def _row(self, r):
        return {
            "id": r["id"],
            "quando": r["quando"],
            "nome": r["nome"],
            "variabile": r["variabile"] or "",
            "variante_a": r["variante_a"] or "",
            "variante_b": r["variante_b"] or "",
            "risultato_a": r["risultato_a"] or "",
            "risultato_b": r["risultato_b"] or "",
            "vincitore": r["vincitore"] or "",
            "nota": r["nota"] or "",
        }

    def chiudi(self):
        self.conn.close()


if __name__ == "__main__":
    e = EsperimentiCognitivi()
    eid = e.registra("smoke", "strategia", "A", "B", "ok", "meglio", "B", "test")
    print("OK esperimenti", eid, e.statistiche())
