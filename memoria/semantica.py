"""
ARGO - memoria/semantica.py  (Memoria enterprise: SEMANTICA / VETTORIALE)
Costruita da ZERO dentro ARGO. Nessun SONAR.

Permette di ritrovare i ricordi PER SIGNIFICATO, non per parola esatta:
  "quel file del mare" trova "vacanze_spiaggia.jpg" anche senza la parola "mare".

Come: trasforma il testo in un vettore (embedding) con Ollama (modello
'nomic-embed-text', leggero, gira in locale). Confronto per similarità del coseno.
Tutto in SQLite, solo libreria standard.

Se manca il modello:  ollama pull nomic-embed-text
"""

import os
import json
import math
import sqlite3
import datetime
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODELLO_EMBED = os.environ.get("ARGO_EMBED", "nomic-embed-text")


def _ora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _coseno(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return num / (na * nb) if na and nb else 0.0


class Semantica:
    def __init__(self, percorso=None, host=None, modello=None):
        if percorso is None:
            percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "argo_semantica.db")
        self.percorso = percorso
        self.host = (host or OLLAMA_HOST).rstrip("/")
        self.modello = modello or MODELLO_EMBED
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._schema()

    def _schema(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS vettori (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                testo   TEXT NOT NULL,
                origine TEXT,
                vettore TEXT NOT NULL,
                quando  TEXT
            )
        """)
        self.conn.commit()

    # ---- embedding via Ollama ----
    def _embedding(self, testo):
        payload = json.dumps({"model": self.modello, "prompt": testo}).encode("utf-8")
        req = urllib.request.Request(
            self.host + "/api/embeddings", data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                dati = json.loads(r.read().decode("utf-8"))
                return dati.get("embedding")
        except Exception:
            return None

    def disponibile(self):
        return self._embedding("test") is not None

    # ---- memoria ----
    def ricorda_testo(self, testo, origine=""):
        """Salva un testo con il suo vettore. Ritorna l'id o None se embedding fallito."""
        vec = self._embedding(testo)
        if vec is None:
            return None
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO vettori (testo, origine, vettore, quando) VALUES (?,?,?,?)",
            (testo, origine, json.dumps(vec), _ora()),
        )
        self.conn.commit()
        return c.lastrowid

    def cerca(self, query, k=5):
        """Ritorna i k ricordi piu' vicini per significato."""
        qv = self._embedding(query)
        if qv is None:
            return []
        c = self.conn.cursor()
        c.execute("SELECT testo, origine, vettore FROM vettori")
        risultati = []
        for r in c.fetchall():
            try:
                v = json.loads(r["vettore"])
            except Exception:
                continue
            risultati.append((_coseno(qv, v), r["testo"], r["origine"]))
        risultati.sort(key=lambda x: x[0], reverse=True)
        return [{"score": round(s, 3), "testo": t, "origine": o}
                for s, t, o in risultati[:k]]

    def conta(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM vettori")
        return c.fetchone()["n"]

    def chiudi(self):
        self.conn.close()


if __name__ == "__main__":
    # usa un db TEMPORANEO: i test non devono sporcare la memoria vera
    _tmp = os.path.join(os.path.dirname(__file__), "test_semantica.db")
    s = Semantica(percorso=_tmp)
    if not s.disponibile():
        print("Embeddings non disponibili. Esegui:  ollama pull nomic-embed-text")
    else:
        s.ricorda_testo("Foto delle vacanze al mare in Sardegna", "demo")
        s.ricorda_testo("Fattura della luce di marzo", "demo")
        print("cerca 'spiaggia':", s.cerca("spiaggia", k=2))
        print("totale vettori:", s.conta())
