"""
ARGO - governo/lacune.py
Registro delle "lacune" di ARGO: cose che non sa fare bene o categorie dove
viene rifiutato spesso. Usa un database SQLite separato (memoria/argo_lacune.db)
per non interferire con la memoria principale.

Nessuna libreria esterna richiesta.
"""

import os
import sqlite3
import datetime


def _ora():
    """Restituisce il timestamp ISO dell'istante corrente."""
    return datetime.datetime.now().isoformat(timespec="seconds")


# Percorso di default del database lacune, accanto agli altri db di memoria
_DB_DEFAULT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "memoria", "argo_lacune.db"
)


class Lacune:
    """
    Gestisce il registro delle lacune di ARGO.

    Una lacuna è un punto debole rilevato in automatico (es. azioni rifiutate
    ripetutamente su una certa categoria, formati non capiti, richieste
    sistematicamente fallite). Persiste su SQLite.
    """

    def __init__(self, percorso=None):
        if percorso is None:
            percorso = os.path.normpath(_DB_DEFAULT)
        self.percorso = percorso
        # Crea la cartella 'memoria' se non esiste
        os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._crea_schema()

    def _crea_schema(self):
        """Crea la tabella se non esiste."""
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS lacune (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                quando      TEXT NOT NULL,
                tipo        TEXT NOT NULL,
                descrizione TEXT NOT NULL,
                stato       TEXT NOT NULL DEFAULT 'aperta',
                risolta_il  TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_lacune_tipo  ON lacune(tipo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lacune_stato ON lacune(stato)")
        self.conn.commit()

    # ---------- operazioni principali ----------

    def registra(self, tipo: str, descrizione: str) -> int:
        """
        Aggiunge una nuova lacuna. Evita i duplicati aperti identici.

        :param tipo:        categoria sintetica (es. 'rifiuto_ripetuto', 'formato_ignoto')
        :param descrizione: spiegazione estesa del problema
        :return:            id del record inserito (o dell'esistente se duplicato)
        """
        try:
            c = self.conn.cursor()
            # Controlla se esiste già una lacuna aperta con stesso tipo+descrizione
            c.execute(
                "SELECT id FROM lacune WHERE tipo=? AND descrizione=? AND stato='aperta'",
                (tipo, descrizione)
            )
            esistente = c.fetchone()
            if esistente:
                return esistente["id"]
            c.execute(
                "INSERT INTO lacune (quando, tipo, descrizione, stato) VALUES (?,?,?,?)",
                (_ora(), tipo, descrizione, "aperta")
            )
            self.conn.commit()
            return c.lastrowid
        except Exception as e:
            print(f"[lacune] Errore in registra(): {e}")
            return -1

    def aperte(self) -> list:
        """
        Restituisce tutte le lacune con stato 'aperta', dalla più recente.

        :return: lista di dizionari con le colonne del record
        """
        try:
            c = self.conn.cursor()
            c.execute(
                "SELECT * FROM lacune WHERE stato='aperta' ORDER BY id DESC"
            )
            return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"[lacune] Errore in aperte(): {e}")
            return []

    def risolvi(self, id_lacuna: int) -> bool:
        """
        Marca una lacuna come risolta.

        :param id_lacuna: id del record da chiudere
        :return:          True se la modifica è avvenuta, False altrimenti
        """
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE lacune SET stato='risolta', risolta_il=? WHERE id=?",
                (_ora(), id_lacuna)
            )
            self.conn.commit()
            return c.rowcount > 0
        except Exception as e:
            print(f"[lacune] Errore in risolvi(): {e}")
            return False

    def tutte(self, limite: int = 200) -> list:
        """Restituisce tutte le lacune (aperte e risolte), dalla più recente."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT * FROM lacune ORDER BY id DESC LIMIT ?", (limite,))
            return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"[lacune] Errore in tutte(): {e}")
            return []

    def chiudi(self):
        """Chiude la connessione al database."""
        try:
            self.conn.close()
        except Exception:
            pass


# ---------- smoke-test ----------
if __name__ == "__main__":
    import tempfile, os, sys as _sys_main
    _root_main = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    if _root_main not in _sys_main.path:
        _sys_main.path.insert(0, _root_main)

    print("== Smoke-test Lacune ==")

    # Usa un db temporaneo per non sporcare il db reale
    with tempfile.TemporaryDirectory() as tmp:
        percorso_test = os.path.join(tmp, "test_lacune.db")
        lacune = Lacune(percorso=percorso_test)

        # Inserimento
        id1 = lacune.registra("rifiuto_ripetuto", "Argo rifiuta sempre le azioni su PDF")
        id2 = lacune.registra("formato_ignoto", "Non capisce i file .heic")
        print(f"  Lacuna 1 id={id1}, Lacuna 2 id={id2}")
        assert id1 > 0 and id2 > 0, "Gli id devono essere positivi"

        # Duplicato: deve ritornare lo stesso id
        id1b = lacune.registra("rifiuto_ripetuto", "Argo rifiuta sempre le azioni su PDF")
        assert id1b == id1, f"Duplicato: atteso {id1}, ottenuto {id1b}"
        print(f"  Duplicato correttamente ignorato (id={id1b})")

        # Elenco aperte
        aperte = lacune.aperte()
        assert len(aperte) == 2, f"Attese 2 aperte, trovate {len(aperte)}"
        print(f"  Lacune aperte: {len(aperte)}")

        # Risoluzione
        ok = lacune.risolvi(id1)
        assert ok, "Risoluzione deve restituire True"
        aperte_dopo = lacune.aperte()
        assert len(aperte_dopo) == 1, f"Attesa 1 aperta dopo risoluzione, trovate {len(aperte_dopo)}"
        print(f"  Dopo risoluzione, lacune aperte: {len(aperte_dopo)}")

        # Tutte
        tutte = lacune.tutte()
        assert len(tutte) == 2, f"Attese 2 totali, trovate {len(tutte)}"
        print(f"  Lacune totali: {len(tutte)}")

        lacune.chiudi()

    print("OK")
