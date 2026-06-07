"""
ARGO - cognizione/obiettivi.py
Obiettivi permanenti locali: direzioni che restano tra le sessioni.
"""

import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "memoria", "argo_obiettivi.db")


def _now():
    return datetime.now().isoformat(timespec="seconds")


class Obiettivi:
    DEFAULT = [
        ("Proteggere dati sensibili", "Non leggere, spostare o indicizzare segreti, password, chiavi e documenti critici.", "alta"),
        ("Organizzare file con conferma", "Proporre ordine utile e reversibile, rispettando la modalita' scelta da Davide.", "media"),
        ("Migliorare classificazione progetti", "Ridurre eventi senza progetto e collegare file, finestre e azioni a contesti coerenti.", "alta"),
        ("Ridurre incertezze ricorrenti", "Usare diario, sonno e skill proposte per chiudere lacune osservate piu' volte.", "media"),
    ]

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self.assicura_default()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS obiettivi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creato TEXT NOT NULL,
                aggiornato TEXT NOT NULL,
                titolo TEXT NOT NULL UNIQUE,
                descrizione TEXT,
                stato TEXT NOT NULL,
                priorita TEXT NOT NULL,
                progresso INTEGER NOT NULL,
                origine TEXT
            )
            """
        )
        self.conn.commit()

    def assicura_default(self):
        for titolo, descrizione, priorita in self.DEFAULT:
            self.crea(titolo, descrizione, priorita=priorita, origine="sistema", se_esiste_ok=True)

    def crea(self, titolo, descrizione="", priorita="media", origine="utente", se_esiste_ok=False):
        titolo = (titolo or "").strip()[:220]
        if not titolo:
            return None
        priorita = priorita if priorita in {"bassa", "media", "alta", "critica"} else "media"
        try:
            cur = self.conn.cursor()
            if se_esiste_ok:
                row = cur.execute("SELECT id FROM obiettivi WHERE titolo=?", (titolo,)).fetchone()
                if row:
                    return None
            cur.execute(
                """
                INSERT INTO obiettivi(creato, aggiornato, titolo, descrizione, stato, priorita, progresso, origine)
                VALUES (?, ?, ?, ?, 'attivo', ?, 0, ?)
                """,
                (_now(), _now(), titolo, (descrizione or "")[:2000], priorita, origine),
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            if se_esiste_ok:
                return None
            raise

    def aggiorna(self, obj_id, stato=None, progresso=None, descrizione=None):
        att = self._get(obj_id)
        if not att:
            return {"ok": False, "messaggio": "obiettivo non trovato"}
        stato = stato or att["stato"]
        progresso = att["progresso"] if progresso is None else max(0, min(int(progresso), 100))
        descrizione = att["descrizione"] if descrizione is None else str(descrizione)[:2000]
        self.conn.execute(
            """
            UPDATE obiettivi
            SET aggiornato=?, stato=?, progresso=?, descrizione=?
            WHERE id=?
            """,
            (_now(), stato, progresso, descrizione, obj_id),
        )
        self.conn.commit()
        return {"ok": True}

    def lista(self, limite=30, stato=None):
        limite = max(1, min(int(limite or 30), 100))
        if stato:
            rows = self.conn.execute(
                "SELECT * FROM obiettivi WHERE stato=? ORDER BY priorita DESC, aggiornato DESC LIMIT ?",
                (stato, limite),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM obiettivi ORDER BY stato ASC, priorita DESC, aggiornato DESC LIMIT ?",
                (limite,),
            ).fetchall()
        return [self._row(r) for r in rows]

    def attivi(self, limite=20):
        return self.lista(limite, "attivo")

    def valuta_da_world(self, analisi):
        if not analisi:
            return {"creati": 0, "aggiornati": 0}
        creati = 0
        aggiornati = 0
        lacune = analisi.get("lacune") or []
        for lac in lacune[:6]:
            titolo = lac.get("titolo") if isinstance(lac, dict) else str(lac)
            if not titolo:
                continue
            nome = "Colmare lacuna: " + titolo[:160]
            if self.crea(nome, str(lac), priorita="alta", origine="world_model", se_esiste_ok=True):
                creati += 1
        conf = analisi.get("confidenza")
        if isinstance(conf, (int, float)) and conf >= 0.65:
            for o in self.attivi(50):
                if o["titolo"] == "Migliorare classificazione progetti" and o["progresso"] < 35:
                    self.aggiorna(o["id"], progresso=35)
                    aggiornati += 1
        return {"creati": creati, "aggiornati": aggiornati}

    def contesto_chat(self, limite=6):
        return "\n".join(
            f"- {o['titolo']} ({o['stato']}, {o['progresso']}%)"
            for o in self.attivi(limite)
        )

    def _get(self, obj_id):
        row = self.conn.execute("SELECT * FROM obiettivi WHERE id=?", (obj_id,)).fetchone()
        return self._row(row) if row else None

    def _row(self, r):
        return {
            "id": r["id"],
            "creato": r["creato"],
            "aggiornato": r["aggiornato"],
            "titolo": r["titolo"],
            "descrizione": r["descrizione"] or "",
            "stato": r["stato"],
            "priorita": r["priorita"],
            "progresso": r["progresso"],
            "origine": r["origine"] or "",
        }

    def chiudi(self):
        self.conn.close()


if __name__ == "__main__":
    o = Obiettivi()
    print("OK obiettivi", len(o.lista()), o.attivi(2))
