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
        self._migra_temporale()

    def _migra_temporale(self):
        """
        Migrazione difensiva: aggiunge la validità temporale agli archi.
          valido_da = quando l'arco comincia a valere (ISO, default = ora creazione)
          valido_a  = quando smette di valere (ISO, oppure NULL = ancora valido)
        Controlla PRAGMA table_info per non riaggiungere colonne già presenti,
        così archi creati con versioni precedenti restano intatti.
        """
        c = self.conn.cursor()
        c.execute("PRAGMA table_info(archi)")
        colonne = {r["name"] for r in c.fetchall()}

        if "valido_da" not in colonne:
            c.execute("ALTER TABLE archi ADD COLUMN valido_da TEXT")
            # Retrocompatibilità: gli archi esistenti valgono "da sempre".
            # Usiamo 'quando' (l'istante di creazione) se disponibile, altrimenti
            # un istante minimo così risultano validi a qualunque query as-of.
            c.execute(
                "UPDATE archi SET valido_da = COALESCE(quando, ?) "
                "WHERE valido_da IS NULL",
                ("0000-01-01T00:00:00",),
            )

        if "valido_a" not in colonne:
            # Default implicito NULL = ancora valido. Nessun UPDATE necessario.
            c.execute("ALTER TABLE archi ADD COLUMN valido_a TEXT")

        self.conn.commit()

    # ---- nodi ----
    def aggiungi_nodo(self, tipo, nome):
        c = self.conn.cursor()
        c.execute("INSERT OR IGNORE INTO nodi (tipo, nome) VALUES (?,?)", (tipo, nome))
        c.execute("SELECT id FROM nodi WHERE tipo=? AND nome=?", (tipo, nome))
        self.conn.commit()
        return c.fetchone()["id"]

    # ---- archi ----
    def collega(self, tipo1, nome1, rel, tipo2, nome2, valido_da=None, valido_a=None):
        """
        Crea l'arco tipo1/nome1 --[rel]--> tipo2/nome2.
        valido_da/valido_a (ISO) sono opzionali e definiscono la finestra di
        validità temporale dell'arco:
          - valido_da assente  -> ora di creazione (l'arco vale da subito)
          - valido_a  assente  -> NULL (l'arco è ancora valido, senza scadenza)
        Firma retrocompatibile: i due parametri sono in coda e opzionali.
        """
        a = self.aggiungi_nodo(tipo1, nome1)
        b = self.aggiungi_nodo(tipo2, nome2)
        ora = _ora()
        if valido_da is None:
            valido_da = ora
        c = self.conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO archi (src, rel, dst, quando, valido_da, valido_a) "
            "VALUES (?,?,?,?,?,?)",
            (a, rel, b, ora, valido_da, valido_a),
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

    def vicini_al(self, tipo, nome, istante_iso):
        """
        Vicini "as-of": ciò che era collegato a questo nodo a un dato istante.
        Un arco è valido all'istante se:
            valido_da <= istante AND (valido_a IS NULL OR valido_a > istante)
        Gli archi pre-migrazione (valido_da = epoca minima, valido_a NULL)
        risultano quindi sempre validi, preservando la retrocompatibilità.
        """
        c = self.conn.cursor()
        c.execute("SELECT id FROM nodi WHERE tipo=? AND nome=?", (tipo, nome))
        r = c.fetchone()
        if not r:
            return []
        nid = r["id"]
        cond = "a.valido_da <= ? AND (a.valido_a IS NULL OR a.valido_a > ?)"
        c.execute("""
            SELECT n.tipo AS tipo, n.nome AS nome, a.rel AS rel, 'uscente' AS verso
            FROM archi a JOIN nodi n ON n.id=a.dst
            WHERE a.src=? AND """ + cond + """
            UNION ALL
            SELECT n.tipo, n.nome, a.rel, 'entrante'
            FROM archi a JOIN nodi n ON n.id=a.src
            WHERE a.dst=? AND """ + cond + """
        """, (nid, istante_iso, istante_iso, nid, istante_iso, istante_iso))
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

    # ---- prova validità temporale (query as-of) ----
    # Arco valido solo in una finestra del 2020.
    g.collega("file", "foto_mare.png", "taggato", "categoria", "Estate2020",
              valido_da="2020-06-01T00:00:00", valido_a="2020-09-30T00:00:00")

    # Dentro la finestra: il tag deve comparire.
    dentro = g.vicini_al("file", "foto_mare.png", "2020-07-15T12:00:00")
    nomi_dentro = {v["nome"] for v in dentro}
    assert "Estate2020" in nomi_dentro, "as-of: il tag doveva essere valido nel 2020"

    # Fuori dalla finestra (oggi): il tag NON deve comparire...
    fuori = g.vicini_al("file", "foto_mare.png", _ora())
    nomi_fuori = {v["nome"] for v in fuori}
    assert "Estate2020" not in nomi_fuori, "as-of: il tag non doveva valere oggi"

    # ...ma gli archi senza scadenza (retrocompatibili) restano sempre validi.
    assert "Immagini" in nomi_fuori, "as-of: gli archi senza scadenza valgono sempre"
    print("as-of 2020-07-15:", dentro)

    g.chiudi()
    os.remove(os.path.join(os.path.dirname(__file__), "test_grafo.db"))
    print("OK grafo")
