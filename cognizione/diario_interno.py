"""
ARGO - cognizione/diario_interno.py
Diario interno persistente: riflessioni, errori, correzioni e limiti noti.

Non e' "coscienza": e' metacognizione pratica. ARGO conserva cosa ha capito,
dove e' debole e quali prove hanno portato a quella conclusione.
"""

import json
import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "memoria", "argo_diario_interno.db")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _json(data):
    try:
        return json.dumps(data or {}, ensure_ascii=False, default=str)
    except Exception:
        return "{}"


def _loads(text):
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


class DiarioInterno:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS riflessioni (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quando TEXT NOT NULL,
                tipo TEXT NOT NULL,
                titolo TEXT NOT NULL,
                dettaglio TEXT,
                evidenza_json TEXT,
                esito TEXT,
                importanza TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_riflessioni_quando ON riflessioni(quando)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_riflessioni_tipo ON riflessioni(tipo)")
        self.conn.commit()

    def registra(self, tipo, titolo, dettaglio="", evidenza=None, esito=None, importanza="media"):
        tipo = (tipo or "riflessione").strip()[:80]
        titolo = (titolo or "Riflessione").strip()[:220]
        dettaglio = (dettaglio or "").strip()[:4000]
        importanza = importanza if importanza in {"bassa", "media", "alta", "critica"} else "media"
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO riflessioni(quando, tipo, titolo, dettaglio, evidenza_json, esito, importanza)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (_now(), tipo, titolo, dettaglio, _json(evidenza), esito, importanza),
        )
        self.conn.commit()
        return cur.lastrowid

    def recenti(self, limite=20):
        limite = max(1, min(int(limite or 20), 100))
        rows = self.conn.execute(
            """
            SELECT id, quando, tipo, titolo, dettaglio, evidenza_json, esito, importanza
            FROM riflessioni
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def statistiche(self):
        cur = self.conn.cursor()
        totale = cur.execute("SELECT COUNT(*) FROM riflessioni").fetchone()[0]
        per_tipo = cur.execute(
            "SELECT tipo, COUNT(*) AS n FROM riflessioni GROUP BY tipo ORDER BY n DESC LIMIT 12"
        ).fetchall()
        critiche = cur.execute(
            "SELECT COUNT(*) FROM riflessioni WHERE importanza IN ('alta','critica')"
        ).fetchone()[0]
        return {
            "totale": totale,
            "importanti": critiche,
            "per_tipo": [{"tipo": r["tipo"], "n": r["n"]} for r in per_tipo],
        }

    def contesto_chat(self, limite=6):
        parti = []
        for r in self.recenti(limite):
            parti.append(f"- [{r['tipo']}] {r['titolo']}: {r.get('dettaglio','')[:220]}")
        return "\n".join(parti)

    def rifletti(self, timeline=None, world=None, memoria=None, audit=None):
        create = []

        try:
            lacune = timeline.lacune_oggi() if timeline else []
            if lacune:
                create.append((
                    "lacuna",
                    "Lacune cognitive rilevate",
                    "; ".join(str(x) for x in lacune[:5]),
                    {"lacune": lacune[:10]},
                    "da_rivedere",
                    "alta",
                ))
        except Exception:
            pass

        try:
            pattern = timeline.pattern_oggi() if timeline else []
            if pattern:
                create.append((
                    "pattern",
                    "Pattern della giornata",
                    "; ".join((p.get("descrizione") or str(p)) for p in pattern[:5]),
                    {"pattern": pattern[:10]},
                    "osservato",
                    "media",
                ))
        except Exception:
            pass

        try:
            analisi = world.ultimo() if world else {}
            if analisi:
                lac = analisi.get("lacune") or []
                piani = analisi.get("piani") or []
                conf = analisi.get("confidenza")
                if lac or piani:
                    create.append((
                        "world_model",
                        "Autovalutazione del world model",
                        f"Confidenza: {conf}. Lacune: {len(lac)}. Piani: {len(piani)}.",
                        {"lacune": lac[:8], "piani": piani[:8], "confidenza": conf},
                        "monitorare",
                        "alta" if lac else "media",
                    ))
        except Exception:
            pass

        try:
            rep = audit.report() if audit else {}
            if rep and not rep.get("integro", True):
                create.append((
                    "sicurezza",
                    "Audit non integro",
                    "La catena audit risulta alterata o non verificabile.",
                    rep,
                    "intervento_necessario",
                    "critica",
                ))
        except Exception:
            pass

        ids = []
        for item in create:
            ids.append(self.registra(*item))
        return {"create": len(ids), "ids": ids, "statistiche": self.statistiche()}

    def _row(self, r):
        return {
            "id": r["id"],
            "quando": r["quando"],
            "tipo": r["tipo"],
            "titolo": r["titolo"],
            "dettaglio": r["dettaglio"] or "",
            "evidenza": _loads(r["evidenza_json"]),
            "esito": r["esito"],
            "importanza": r["importanza"] or "media",
        }

    def chiudi(self):
        self.conn.close()


if __name__ == "__main__":
    d = DiarioInterno()
    rid = d.registra("test", "Diario interno operativo", "Smoke test metacognizione.", {"ok": True})
    print("OK diario_interno", rid, d.statistiche())
