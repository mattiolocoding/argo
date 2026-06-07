"""
ARGO - memoria/grafo.py  (Memoria enterprise: KNOWLEDGE GRAPH)
Costruito da ZERO dentro ARGO. Nessuna dipendenza esterna, nessun SONAR.

Il grafo collega le cose tra loro: file ↔ categorie ↔ cartelle ↔ progetti ↔ eventi.
È la base del ragionamento "di frontiera": non solo ricordare, ma capire le RELAZIONI.

  nodi  = entità  (es. tipo="file" nome="foto.png", tipo="categoria" nome="Immagini")
  archi = relazioni (es. foto.png --[è_un]--> Immagini)

SQLite locale, file dedicato. Solo libreria standard.
"""

import os
import sqlite3
import datetime


def _ora():
    return datetime.datetime.now().isoformat(timespec="seconds")


class Grafo:
    def __init__(self, percorso=None):
        if percorso is None:
            percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "argo_grafo.db")
        self.percorso = percorso
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._schema()

    def _schema(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS nodi (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                nome TEXT NOT NULL,
                UNIQUE(tipo, nome)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS archi (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                src    INTEGER NOT NULL,
                rel    TEXT NOT NULL,
                dst    INTEGER NOT NULL,
                quando TEXT,
                UNIQUE(src, rel, dst)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_nodi_nome ON nodi(nome)")
        self.conn.commit()

    # ---- nodi ----
    def aggiungi_nodo(self, tipo, nome):
        c = self.conn.cursor()
        c.execute("INSERT OR IGNORE INTO nodi (tipo, nome) VALUES (?,?)", (tipo, nome))
        c.execute("SELECT id FROM nodi WHERE tipo=? AND nome=?", (tipo, nome))
        self.conn.commit()
        return c.fetchone()["id"]

    # ---- archi ----
    def collega(self, tipo1, nome1, rel, tipo2, nome2):
        a = self.aggiungi_nodo(tipo1, nome1)
        b = self.aggiungi_nodo(tipo2, nome2)
        c = self.conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO archi (src, rel, dst, quando) VALUES (?,?,?,?)",
            (a, rel, b, _ora()),
        )
        self.conn.commit()

    # ---- interrogazioni ----
    def vicini(self, tipo, nome):
        """Tutto ciò che è collegato a questo nodo (in entrambe le direzioni)."""
        c = self.conn.cursor()
        c.execute("SELECT id FROM nodi WHERE tipo=? AND nome=?", (tipo, nome))
        r = c.fetchone()
        if not r:
            return []
        nid = r["id"]
        c.execute("""
            SELECT n.tipo AS tipo, n.nome AS nome, a.rel AS rel, 'uscente' AS verso
            FROM archi a JOIN nodi n ON n.id=a.dst WHERE a.src=?
            UNION ALL
            SELECT n.tipo, n.nome, a.rel, 'entrante'
            FROM archi a JOIN nodi n ON n.id=a.src WHERE a.dst=?
        """, (nid, nid))
        return [dict(x) for x in c.fetchall()]

    def cerca(self, frammento, n=20):
        c = self.conn.cursor()
        c.execute("SELECT tipo, nome FROM nodi WHERE nome LIKE ? LIMIT ?",
                  (f"%{frammento}%", n))
        return [dict(x) for x in c.fetchall()]

    def statistiche(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM nodi")
        nodi = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) AS n FROM archi")
        archi = c.fetchone()["n"]
        return {"nodi": nodi, "archi": archi}

    def chiudi(self):
        self.conn.close()


if __name__ == "__main__":
    g = Grafo(os.path.join(os.path.dirname(__file__), "test_grafo.db"))
    g.collega("file", "foto_mare.png", "è_un", "categoria", "Immagini")
    g.collega("file", "foto_mare.png", "sta_in", "cartella", "Vacanze")
    print("vicini di foto_mare.png:", g.vicini("file", "foto_mare.png"))
    print("statistiche:", g.statistiche())
    g.chiudi()
    os.remove(os.path.join(os.path.dirname(__file__), "test_grafo.db"))
    print("OK grafo")
