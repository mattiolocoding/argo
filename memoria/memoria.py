"""
ARGO - memoria/memoria.py
La memoria propria di Argo: ricorda tra una sessione e l'altra e IMPARA le abitudini.

Tessuti:
  - EPISODICA -> 'episodi': il diario di tutto cio' che Argo vede e fa.
  - PROFILO   -> 'profilo': chi e' Davide, preferenze, dati persistenti.
  - ABITUDINI -> 'abitudini': quante volte Davide accetta/rifiuta per categoria
                 (cosi' Argo smette di proporre cio' che non vuoi e fa da solo
                 cio' che accetti sempre).

Tutto in un unico file SQLite locale. Nessuna libreria da installare.
"""

import os
import sqlite3
import datetime


def _ora():
    return datetime.datetime.now().isoformat(timespec="seconds")


class Memoria:
    def __init__(self, percorso=None):
        if percorso is None:
            percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "argo_memory.db")
        self.percorso = percorso
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._crea_schema()

    # ---------- schema ----------
    def _crea_schema(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS episodi (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                quando    TEXT NOT NULL,
                tipo      TEXT NOT NULL,
                dettaglio TEXT,
                esito     TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS profilo (
                chiave     TEXT PRIMARY KEY,
                valore     TEXT,
                aggiornato TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS abitudini (
                categoria  TEXT PRIMARY KEY,
                accettati  INTEGER NOT NULL DEFAULT 0,
                rifiutati  INTEGER NOT NULL DEFAULT 0,
                aggiornato TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_episodi_quando ON episodi(quando)")
        self.conn.commit()

    # ---------- memoria episodica ----------
    def ricorda(self, tipo, dettaglio="", esito=None):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO episodi (quando, tipo, dettaglio, esito) VALUES (?,?,?,?)",
            (_ora(), tipo, dettaglio, esito),
        )
        self.conn.commit()
        return c.lastrowid

    def aggiorna_esito(self, id_episodio, esito):
        c = self.conn.cursor()
        c.execute("UPDATE episodi SET esito=? WHERE id=?", (esito, id_episodio))
        self.conn.commit()

    def ricordi_recenti(self, n=10):
        c = self.conn.cursor()
        c.execute("SELECT * FROM episodi ORDER BY id DESC LIMIT ?", (n,))
        return [dict(r) for r in c.fetchall()]

    def conta(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM episodi")
        return c.fetchone()["n"]

    def conta_per_tipo(self):
        c = self.conn.cursor()
        c.execute("SELECT tipo, COUNT(*) AS n FROM episodi GROUP BY tipo")
        return {r["tipo"]: r["n"] for r in c.fetchall()}

    def cerca(self, testo, n=20):
        c = self.conn.cursor()
        like = f"%{testo}%"
        c.execute(
            "SELECT * FROM episodi WHERE tipo LIKE ? OR dettaglio LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (like, like, n),
        )
        return [dict(r) for r in c.fetchall()]

    # ---------- riepilogo (3.5) ----------
    def riepilogo_oggi(self):
        """Conta le azioni completate oggi, per dare un riassunto proattivo."""
        oggi = datetime.date.today().isoformat()
        c = self.conn.cursor()
        c.execute(
            "SELECT COUNT(*) AS n FROM episodi WHERE quando LIKE ? "
            "AND tipo IN ('azione','azione_confermata')",
            (oggi + "%",),
        )
        return c.fetchone()["n"]

    # ---------- profilo ----------
    def salva_profilo(self, chiave, valore):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO profilo (chiave, valore, aggiornato) VALUES (?,?,?) "
            "ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore, "
            "aggiornato=excluded.aggiornato",
            (chiave, str(valore), _ora()),
        )
        self.conn.commit()

    def leggi_profilo(self, chiave, default=None):
        c = self.conn.cursor()
        c.execute("SELECT valore FROM profilo WHERE chiave=?", (chiave,))
        r = c.fetchone()
        return r["valore"] if r else default

    def tutto_profilo(self):
        c = self.conn.cursor()
        c.execute("SELECT chiave, valore FROM profilo")
        return {r["chiave"]: r["valore"] for r in c.fetchall()}

    def registra_accesso(self):
        ultimo = self.leggi_profilo("ultimo_accesso")
        self.salva_profilo("ultimo_accesso", _ora())
        n = int(self.leggi_profilo("numero_accessi", 0)) + 1
        self.salva_profilo("numero_accessi", n)
        return ultimo, n

    # ---------- abitudini (3.4) ----------
    def registra_scelta(self, categoria, accettato):
        """Impara: +1 ad accettati o rifiutati per quella categoria."""
        if not categoria:
            return
        col = "accettati" if accettato else "rifiutati"
        c = self.conn.cursor()
        c.execute(
            f"INSERT INTO abitudini (categoria, {col}, aggiornato) VALUES (?,1,?) "
            f"ON CONFLICT(categoria) DO UPDATE SET {col}={col}+1, aggiornato=excluded.aggiornato",
            (categoria, _ora()),
        )
        self.conn.commit()

    def preferenza(self, categoria):
        """Cosa ha imparato Argo per questa categoria.
        Ritorna 'agisce', 'osserva' oppure None (usa la config)."""
        if not categoria:
            return None
        c = self.conn.cursor()
        c.execute("SELECT accettati, rifiutati FROM abitudini WHERE categoria=?", (categoria,))
        r = c.fetchone()
        if not r:
            return None
        acc, rif = r["accettati"], r["rifiutati"]
        if rif >= 3 and rif > acc * 2:
            return "osserva"          # lo rifiuti spesso -> smetto di proporlo
        if acc >= 5 and rif == 0:
            return "agisce"           # lo accetti sempre -> faccio da solo
        return None

    def chiudi(self):
        self.conn.close()


if __name__ == "__main__":
    print("== Test memoria di Argo ==")
    m = Memoria()
    u, n = m.registra_accesso()
    print(f"Accesso n.{n}. Ultimo: {u or 'mai'}")
    m.ricorda("test", "prova", esito="ok")
    print("Totale episodi:", m.conta(), "| azioni oggi:", m.riepilogo_oggi())
    m.registra_scelta("Immagini", True)
    print("preferenza Immagini:", m.preferenza("Immagini"))
    m.chiudi()
