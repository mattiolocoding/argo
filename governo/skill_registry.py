"""
ARGO - governo/skill_registry.py
Registro delle skill generate dinamicamente dal ciclo di sonno.

Una skill è una funzione Python che ARGO può imparare per colmare una lacuna.
Gli stati del ciclo di vita sono:
  'proposta'  -> generata e analizzata, in attesa di approvazione umana
  'approvata' -> l'utente ha dato il via libera (ma non ancora in esecuzione)
  'attiva'    -> in uso nel sistema
  'scartata'  -> rifiutata (da analisi statica, sandbox o utente)

SICUREZZA: una skill NON passa mai a 'attiva' automaticamente.
           Richiede sempre approvazione umana esplicita.

Nessuna libreria esterna richiesta.
"""

import os
import sqlite3
import datetime


def _ora():
    """Restituisce il timestamp ISO dell'istante corrente."""
    return datetime.datetime.now().isoformat(timespec="seconds")


# Percorso di default del database skill
_DB_DEFAULT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "memoria", "argo_skills.db"
)

# Stati validi per una skill
STATI_VALIDI = {"proposta", "approvata", "attiva", "scartata"}


class SkillRegistry:
    """
    Gestisce il ciclo di vita delle skill di ARGO su SQLite.

    Ogni skill contiene:
      - nome:        identificatore sintetico (es. 'converti_heic')
      - descrizione: cosa fa la skill
      - codice:      sorgente Python (funzione def esegui(contesto): ...)
      - stato:       proposta | approvata | attiva | scartata
      - quando:      timestamp di inserimento
    """

    def __init__(self, percorso=None):
        if percorso is None:
            percorso = os.path.normpath(_DB_DEFAULT)
        self.percorso = percorso
        os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._crea_schema()

    def _crea_schema(self):
        """Crea la tabella 'skill' se non esiste."""
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS skill (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nome        TEXT    NOT NULL,
                descrizione TEXT    NOT NULL,
                codice      TEXT    NOT NULL,
                stato       TEXT    NOT NULL DEFAULT 'proposta',
                quando      TEXT    NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_skill_stato ON skill(stato)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_skill_nome  ON skill(nome)")
        self.conn.commit()

    # ---------- scrittura ----------

    def proponi(self, nome: str, descrizione: str, codice: str) -> int:
        """
        Inserisce una nuova skill in stato 'proposta'.
        La skill NON è attiva: serve approvazione umana.

        :return: id del record inserito, oppure -1 in caso di errore
        """
        try:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO skill (nome, descrizione, codice, stato, quando) "
                "VALUES (?,?,?,?,?)",
                (nome, descrizione, codice, "proposta", _ora())
            )
            self.conn.commit()
            return c.lastrowid
        except Exception as e:
            print(f"[skill_registry] Errore in proponi(): {e}")
            return -1

    def _cambia_stato(self, id_skill: int, nuovo_stato: str) -> bool:
        """Modifica lo stato di una skill. Uso interno."""
        if nuovo_stato not in STATI_VALIDI:
            print(f"[skill_registry] Stato '{nuovo_stato}' non valido.")
            return False
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE skill SET stato=? WHERE id=?",
                (nuovo_stato, id_skill)
            )
            self.conn.commit()
            return c.rowcount > 0
        except Exception as e:
            print(f"[skill_registry] Errore in _cambia_stato(): {e}")
            return False

    def approva(self, id_skill: int) -> bool:
        """
        Marca una skill come 'approvata' (l'utente ha letto e approvato).
        NON la attiva: attivare richiede un passo esplicito separato.

        :return: True se la modifica è avvenuta
        """
        return self._cambia_stato(id_skill, "approvata")

    def scarta(self, id_skill: int) -> bool:
        """
        Marca una skill come 'scartata' (rifiutata da analisi, sandbox o utente).

        :return: True se la modifica è avvenuta
        """
        return self._cambia_stato(id_skill, "scartata")

    def attiva(self, id_skill: int) -> bool:
        """
        Porta una skill a stato 'attiva'. Deve essere chiamata SOLO da codice
        esplicito (ad esempio da una UI di amministrazione), mai in automatico.

        SICUREZZA:
          - Questa funzione NON esegue il codice della skill.
          - RICHIEDE APPROVAZIONE UMANA ESPLICITA: la skill deve essere già
            in stato 'approvata' (tramite approva()) prima di poter essere
            attivata. Non è possibile saltare il passaggio di approvazione.

        :return: True se la modifica è avvenuta, False se la skill non esiste
                 o non è nello stato 'approvata'
        """
        skill = self.per_id(id_skill)
        if skill is None:
            print(f"[skill_registry] attiva(): skill id={id_skill} non trovata.")
            return False
        if skill["stato"] != "approvata":
            print(
                f"[skill_registry] attiva(): la skill id={id_skill} è in stato "
                f"'{skill['stato']}', non 'approvata'. "
                f"Chiama prima approva() per ottenere l'approvazione umana."
            )
            return False
        return self._cambia_stato(id_skill, "attiva")

    # ---------- lettura ----------

    def attive(self) -> list:
        """
        Restituisce le skill con stato 'attiva'.

        :return: lista di dizionari
        """
        try:
            c = self.conn.cursor()
            c.execute("SELECT * FROM skill WHERE stato='attiva' ORDER BY id DESC")
            return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"[skill_registry] Errore in attive(): {e}")
            return []

    def caricabili(self) -> list:
        """
        Alias di attive(): restituisce le skill in stato 'attiva' pronte per
        essere caricate ed eseguite dal motore.

        SICUREZZA: il caricamento ed esecuzione del codice resta responsabilità
        del chiamante, che deve verificare l'approvazione umana già registrata.

        :return: lista di dizionari con nome, descrizione, codice
        """
        return self.attive()

    def proposte(self) -> list:
        """Restituisce le skill in attesa di approvazione."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT * FROM skill WHERE stato='proposta' ORDER BY id DESC")
            return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"[skill_registry] Errore in proposte(): {e}")
            return []

    def tutte(self, limite: int = 200) -> list:
        """Restituisce tutte le skill, dalla più recente."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT * FROM skill ORDER BY id DESC LIMIT ?", (limite,))
            return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"[skill_registry] Errore in tutte(): {e}")
            return []

    def bonifica_non_valide(self, validator=None, stati=("proposta", "approvata", "attiva")) -> dict:
        """
        Valida le skill caricabili e scarta quelle rotte/pericolose.
        Non attiva nulla e non esegue codice nel processo principale.
        """
        try:
            if validator is None:
                from governo.validator import Validator
                validator = Validator(timeout_sandbox=10)
            controllate = 0
            scartate = 0
            dettagli = []
            for skill in self.tutte(500):
                if skill.get("stato") not in set(stati):
                    continue
                controllate += 1
                ris = validator.valida(skill.get("codice", ""))
                if not ris.get("ok"):
                    self.scarta(int(skill["id"]))
                    scartate += 1
                    dettagli.append({
                        "id": skill["id"],
                        "nome": skill.get("nome"),
                        "motivi": ris.get("motivi", []),
                    })
            return {"ok": True, "controllate": controllate, "scartate": scartate, "dettagli": dettagli}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def per_id(self, id_skill: int) -> dict | None:
        """Restituisce una singola skill per id, o None se non trovata."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT * FROM skill WHERE id=?", (id_skill,))
            r = c.fetchone()
            return dict(r) if r else None
        except Exception as e:
            print(f"[skill_registry] Errore in per_id(): {e}")
            return None

    def chiudi(self):
        """Chiude la connessione al database."""
        try:
            self.conn.close()
        except Exception:
            pass


# ---------- smoke-test ----------
if __name__ == "__main__":
    import tempfile
    import sys as _sys_main
    import os as _os_main
    _root_main = _os_main.path.abspath(_os_main.path.join(_os_main.path.dirname(_os_main.path.abspath(__file__)), ".."))
    if _root_main not in _sys_main.path:
        _sys_main.path.insert(0, _root_main)

    print("== Smoke-test SkillRegistry ==")

    with tempfile.TemporaryDirectory() as tmp:
        percorso_test = os.path.join(tmp, "test_skills.db")
        reg = SkillRegistry(percorso=percorso_test)

        codice_esempio = (
            "def esegui(contesto):\n"
            "    return {'esito': 'ok', 'messaggio': 'skill di prova'}\n"
        )

        # Proposta
        id1 = reg.proponi("skill_prova", "Skill di prova senza effetti", codice_esempio)
        assert id1 > 0, "L'id deve essere positivo"
        print(f"  Proposta id={id1}")

        # Proposte in attesa
        proposte = reg.proposte()
        assert len(proposte) == 1, f"Attesa 1 proposta, trovate {len(proposte)}"
        print(f"  Proposte in attesa: {len(proposte)}")

        # Attive (nessuna ancora)
        assert len(reg.attive()) == 0, "Non ci devono essere skill attive"
        print("  Nessuna skill attiva (corretto)")

        # Tentativo di attiva() senza approvazione: deve fallire
        ok_no = reg.attiva(id1)
        assert not ok_no, "attiva() su skill 'proposta' deve restituire False"
        skill_ancora = reg.per_id(id1)
        assert skill_ancora["stato"] == "proposta", "Lo stato non deve cambiare"
        print("  attiva() senza approvazione -> correttamente bloccata")

        # Approvazione (umana esplicita)
        ok = reg.approva(id1)
        assert ok, "Approvazione deve restituire True"
        skill = reg.per_id(id1)
        assert skill["stato"] == "approvata", f"Stato atteso 'approvata', trovato '{skill['stato']}'"
        print(f"  Dopo approva: stato='{skill['stato']}'")

        # Attivazione (dopo approvazione)
        ok_attiva = reg.attiva(id1)
        assert ok_attiva, "attiva() su skill 'approvata' deve restituire True"
        skill_attiva = reg.per_id(id1)
        assert skill_attiva["stato"] == "attiva"
        print(f"  Dopo attiva: stato='{skill_attiva['stato']}'")

        # caricabili() deve restituire la skill appena attivata
        caricabili = reg.caricabili()
        assert len(caricabili) == 1, f"Attesa 1 skill caricabile, trovate {len(caricabili)}"
        print(f"  caricabili(): {len(caricabili)} skill")

        # Seconda skill, poi scartata
        id2 = reg.proponi("skill_cattiva", "Skill con problemi di sicurezza", codice_esempio)
        ok2 = reg.scarta(id2)
        assert ok2
        skill2 = reg.per_id(id2)
        assert skill2["stato"] == "scartata"
        print(f"  Skill scartata: stato='{skill2['stato']}'")

        # Tutte
        tutte = reg.tutte()
        assert len(tutte) == 2, f"Attese 2 skill totali, trovate {len(tutte)}"
        print(f"  Skill totali nel registro: {len(tutte)}")

        reg.chiudi()

    print("OK")
