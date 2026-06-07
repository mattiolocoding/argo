"""
ARGO - curiosita.py
Curiosita' governata: ARGO propone di cercare online quando ha una lacuna,
ma NON naviga mai senza approvazione esplicita dell'umano.

Flusso:
  1. ARGO rileva una lacuna -> chiama proponi_ricerche(lacune)
     -> vengono salvate proposte in SQLite con stato='proposta'
  2. L'umano decide -> approva(id) o rifiuta(id)
  3. Solo dopo approva() viene eseguita la ricerca via RegistroConnettori

Nessuna ricerca automatica. Nessun download. Query limitata a 180 caratteri.

Eseguibile come script:
    python curiosita.py
    python -m curiosita
"""

from __future__ import annotations

import os
import sqlite3
import datetime
import sys

# ---------------------------------------------------------------------------
# Percorsi
# ---------------------------------------------------------------------------
_DIR_ARGO = os.path.dirname(os.path.abspath(__file__))
_DB_DEFAULT = os.path.join(_DIR_ARGO, "memoria", "argo_curiosita.db")

# Assicura che la root di ARGO sia nel path per gli import difensivi
if _DIR_ARGO not in sys.path:
    sys.path.insert(0, _DIR_ARGO)


def _ora() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _tronca(testo: str, max_len: int = 180) -> str:
    """Tronca una stringa a max_len caratteri, strip degli spazi."""
    return str(testo or "").strip()[:max_len]


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class Curiosita:
    """
    Gestisce la curiosita' governata di ARGO.

    ARGO propone ricerche, l'umano approva o rifiuta.
    La ricerca viene eseguita SOLO dopo approvazione esplicita.

    Tutti gli stati persistono in memoria/argo_curiosita.db (SQLite).
    """

    def __init__(self, percorso_db: str | None = None):
        """
        Parametri
        ---------
        percorso_db : percorso del file SQLite. Default: memoria/argo_curiosita.db
        """
        if percorso_db is None:
            percorso_db = os.path.normpath(_DB_DEFAULT)
        self.percorso_db = percorso_db
        os.makedirs(os.path.dirname(self.percorso_db), exist_ok=True)
        self._conn = sqlite3.connect(self.percorso_db, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._crea_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _crea_schema(self) -> None:
        c = self._conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS curiosita (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                quando         TEXT    NOT NULL,
                lacuna         TEXT    NOT NULL,
                query_proposta TEXT    NOT NULL,
                stato          TEXT    NOT NULL DEFAULT 'proposta',
                risultato      TEXT,
                aggiornato     TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cur_stato ON curiosita(stato)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # 1. Proponi ricerche (NON esegue nulla)
    # ------------------------------------------------------------------

    def proponi_ricerche(self, lacune: list[str | dict]) -> list[dict]:
        """
        Crea proposte di ricerca per le lacune fornite.

        ARGO NON cerca nulla qui: registra solo le intenzioni e aspetta
        l'approvazione umana.

        Parametri
        ---------
        lacune : lista di stringhe (descrizione della lacuna) oppure dizionari
                 con chiave 'descrizione' (compatibile con governo/lacune.py).

        Ritorna
        -------
        Lista di proposte: [{id, lacuna, query_proposta, stato:'proposta'}, ...]
        """
        proposte: list[dict] = []
        c = self._conn.cursor()

        for elemento in lacune:
            # Accetta sia stringhe sia dict (da governo/lacune.py)
            if isinstance(elemento, dict):
                testo_lacuna = str(
                    elemento.get("descrizione") or elemento.get("lacuna") or ""
                ).strip()
            else:
                testo_lacuna = str(elemento).strip()

            if not testo_lacuna:
                continue

            lacuna_troncata = _tronca(testo_lacuna, 300)
            query = _costruisci_query(testo_lacuna)

            c.execute(
                """
                INSERT INTO curiosita (quando, lacuna, query_proposta, stato)
                VALUES (?, ?, ?, 'proposta')
                """,
                (_ora(), lacuna_troncata, query),
            )
            self._conn.commit()
            nuovo_id = c.lastrowid

            proposta = {
                "id": nuovo_id,
                "lacuna": lacuna_troncata,
                "query_proposta": query,
                "stato": "proposta",
            }
            proposte.append(proposta)

        return proposte

    # ------------------------------------------------------------------
    # 2. Approva (esegue la ricerca SOLO ora)
    # ------------------------------------------------------------------

    def approva(self, id_proposta: int) -> dict:
        """
        Approva una proposta ed esegue la ricerca tramite RegistroConnettori.

        La ricerca viene eseguita SOLO in questo momento, mai prima.
        Il risultato sintetico viene salvato in SQLite e in memoria/timeline
        (import difensivo: se Memoria non e' disponibile, il dato e' solo in SQLite).

        Parametri
        ---------
        id_proposta : id della proposta da approvare

        Ritorna
        -------
        dict con chiavi: id, stato, risultato (oppure errore)
        """
        c = self._conn.cursor()
        c.execute("SELECT * FROM curiosita WHERE id=?", (id_proposta,))
        riga = c.fetchone()

        if riga is None:
            return {"errore": f"Proposta {id_proposta} non trovata."}

        if riga["stato"] == "fatta":
            return {
                "id": id_proposta,
                "stato": "fatta",
                "risultato": riga["risultato"],
                "nota": "Ricerca gia' eseguita in precedenza.",
            }

        if riga["stato"] == "rifiutata":
            return {
                "errore": f"Proposta {id_proposta} e' stata rifiutata. Non puo' essere approvata."
            }

        # --- Esegui la ricerca tramite RegistroConnettori ---
        query = riga["query_proposta"]
        risultato_testo, errore = _esegui_ricerca(query)

        if errore:
            # Connettore non disponibile o errore: la proposta rimane 'proposta'
            # (non la blocchiamo definitivamente, l'umano puo' riprovare)
            return {
                "id": id_proposta,
                "stato": "proposta",
                "errore": errore,
                "nota": "La proposta resta in attesa. Riprova quando il connettore sara' disponibile.",
            }

        # --- Aggiorna SQLite ---
        c.execute(
            """
            UPDATE curiosita
            SET stato='fatta', risultato=?, aggiornato=?
            WHERE id=?
            """,
            (risultato_testo, _ora(), id_proposta),
        )
        self._conn.commit()

        # --- Salva in memoria/timeline (import difensivo) ---
        _salva_in_memoria(
            tipo="curiosita_ricerca",
            dettaglio=f"[Curiosita' id={id_proposta}] Lacuna: {riga['lacuna'][:120]} | Query: {query}",
            esito=risultato_testo[:200],
        )

        return {
            "id": id_proposta,
            "stato": "fatta",
            "query": query,
            "risultato": risultato_testo,
        }

    # ------------------------------------------------------------------
    # 3. Rifiuta
    # ------------------------------------------------------------------

    def rifiuta(self, id_proposta: int) -> dict:
        """
        Rifiuta una proposta: nessuna ricerca verra' mai eseguita per questo id.

        Parametri
        ---------
        id_proposta : id della proposta da rifiutare

        Ritorna
        -------
        dict con id e stato aggiornato, oppure errore
        """
        c = self._conn.cursor()
        c.execute("SELECT stato FROM curiosita WHERE id=?", (id_proposta,))
        riga = c.fetchone()

        if riga is None:
            return {"errore": f"Proposta {id_proposta} non trovata."}

        if riga["stato"] == "fatta":
            return {"errore": f"Proposta {id_proposta} e' gia' stata eseguita, non si puo' rifiutare."}

        c.execute(
            "UPDATE curiosita SET stato='rifiutata', aggiornato=? WHERE id=?",
            (_ora(), id_proposta),
        )
        self._conn.commit()
        return {"id": id_proposta, "stato": "rifiutata"}

    # ------------------------------------------------------------------
    # 4. Elenco
    # ------------------------------------------------------------------

    def elenco(self, stato: str | None = None) -> list[dict]:
        """
        Elenca le proposte, con filtro opzionale sullo stato.

        Parametri
        ---------
        stato : 'proposta' | 'fatta' | 'rifiutata' | None (tutte)

        Ritorna
        -------
        Lista di dizionari con i campi di ogni proposta.
        """
        c = self._conn.cursor()
        stati_validi = {"proposta", "fatta", "rifiutata"}

        if stato is not None:
            if stato not in stati_validi:
                return []
            c.execute(
                "SELECT * FROM curiosita WHERE stato=? ORDER BY id DESC",
                (stato,),
            )
        else:
            c.execute("SELECT * FROM curiosita ORDER BY id DESC")

        return [dict(r) for r in c.fetchall()]

    # ------------------------------------------------------------------
    # Utilita'
    # ------------------------------------------------------------------

    def chiudi(self) -> None:
        """Chiude la connessione al database."""
        try:
            self._conn.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        totale = len(self.elenco())
        in_attesa = len(self.elenco("proposta"))
        return f"<Curiosita db='{self.percorso_db}' totale={totale} in_attesa={in_attesa}>"


# ---------------------------------------------------------------------------
# Funzioni interne di supporto (non parte dell'API pubblica)
# ---------------------------------------------------------------------------

def _costruisci_query(testo_lacuna: str) -> str:
    """
    Ricava una query di ricerca sintetica dalla descrizione della lacuna.
    Non usa librerie esterne. Query max 180 caratteri.
    """
    # Prendi le prime ~150 caratteri della lacuna come base query
    base = testo_lacuna.strip()
    # Rimuovi prefissi verbosi tipici delle lacune di ARGO
    for prefisso in (
        "non so", "non capisco", "non conosco", "non riesco a", "devo capire",
        "lacuna:", "lacuna su", "lacuna:", "argo non sa",
    ):
        if base.lower().startswith(prefisso):
            base = base[len(prefisso):].strip()
            break
    # Capitalizza e tronca
    if base:
        base = base[0].upper() + base[1:]
    return _tronca(base, 180)


def _esegui_ricerca(query: str) -> tuple[str | None, str | None]:
    """
    Esegue la ricerca tramite RegistroConnettori.
    Import difensivo: se il connettore non e' disponibile ritorna (None, messaggio_errore).

    Ritorna
    -------
    (risultato_testo, None)   se la ricerca e' andata a buon fine
    (None, testo_errore)      se il connettore non e' disponibile o ha fallito
    """
    try:
        from connettori import RegistroConnettori
    except ImportError:
        return None, "Impossibile importare RegistroConnettori. Pacchetto connettori non disponibile."

    try:
        registro = RegistroConnettori()
        connettore = registro.tutti().get("ricerca_web")
        if connettore is None:
            return None, "Connettore 'ricerca_web' non registrato."
        if not connettore.disponibile():
            return None, "Connettore 'ricerca_web' non disponibile (disabilitato in config/connettori.json)."

        risposta = connettore.leggi({"query": query, "max_risultati": 5})
    except Exception as e:
        return None, f"Errore durante la ricerca: {e}"

    if isinstance(risposta, dict) and "errore" in risposta:
        return None, risposta["errore"]

    # Sintetizza i risultati in testo breve
    righe: list[str] = []
    if isinstance(risposta, dict):
        risultati = risposta.get("risultati", [])
        for r in risultati[:5]:
            titolo = str(r.get("titolo", "")).strip()
            snippet = str(r.get("snippet", "")).strip()
            url = str(r.get("url", "")).strip()
            riga = titolo
            if snippet:
                riga += f" — {snippet[:120]}"
            if url:
                riga += f" [{url[:80]}]"
            if riga:
                righe.append(riga)
    elif isinstance(risposta, list):
        for r in risposta[:5]:
            righe.append(str(r)[:200])

    if not righe:
        return "Ricerca completata ma nessun risultato trovato.", None

    testo = "\n".join(righe)
    return testo[:1000], None  # cap a 1000 caratteri per salvataggio sobrio


def _salva_in_memoria(tipo: str, dettaglio: str, esito: str | None = None) -> None:
    """
    Salva un episodio nella memoria episodica di ARGO (memoria/Memoria).
    Import difensivo: se Memoria non e' disponibile, non lancia eccezione.
    """
    try:
        from memoria import Memoria
        mem = Memoria()
        mem.ricorda(tipo=tipo, dettaglio=dettaglio, esito=esito)
    except Exception:
        # Non bloccare il flusso principale se la memoria non e' raggiungibile
        pass


# ---------------------------------------------------------------------------
# Smoke-test  (python curiosita.py  oppure  python -m curiosita)
# ---------------------------------------------------------------------------

def _smoke_test() -> None:
    import tempfile

    print("== Smoke-test Curiosita ==")

    with tempfile.TemporaryDirectory() as tmp:
        db_test = os.path.join(tmp, "test_curiosita.db")
        cur = Curiosita(percorso_db=db_test)

        # 1. proponi_ricerche con stringhe
        lacune_test = [
            "non so cosa sia il protocollo MQTT",
            "non capisco come funziona il GIL in Python",
        ]
        proposte = cur.proponi_ricerche(lacune_test)
        assert len(proposte) == 2, f"Attese 2 proposte, ottenute {len(proposte)}"
        assert proposte[0]["stato"] == "proposta", "Stato iniziale deve essere 'proposta'"
        assert proposte[0]["query_proposta"], "Query proposta non deve essere vuota"
        print(f"  proponi_ricerche: {len(proposte)} proposte create")

        # 2. proponi_ricerche con dict (formato governo/lacune.py)
        proposte_dict = cur.proponi_ricerche([
            {"descrizione": "non riesco a leggere i file .heic", "tipo": "formato_ignoto"}
        ])
        assert len(proposte_dict) == 1, "Attesa 1 proposta da dict"
        print(f"  proponi_ricerche (dict): ok, id={proposte_dict[0]['id']}")

        # 3. elenco
        tutte = cur.elenco()
        assert len(tutte) == 3, f"Attese 3 proposte totali, trovate {len(tutte)}"
        solo_proposte = cur.elenco("proposta")
        assert len(solo_proposte) == 3, "Tutte devono essere 'proposta'"
        print(f"  elenco(): {len(tutte)} totali, {len(solo_proposte)} in attesa")

        # 4. rifiuta
        id_rifiuto = proposte[1]["id"]
        esito_rifiuto = cur.rifiuta(id_rifiuto)
        assert esito_rifiuto["stato"] == "rifiutata", "Stato atteso 'rifiutata'"
        # Tentativo di approvare una rifiutata
        err = cur.approva(id_rifiuto)
        assert "errore" in err, "Approvare una rifiutata deve dare errore"
        print(f"  rifiuta() e protezione approvazione: ok")

        # 5. approva senza connettore reale (connettore assente = errore gestito)
        id_approva = proposte[0]["id"]
        esito_approva = cur.approva(id_approva)
        # In smoke-test il connettore potrebbe o non essere disponibile:
        # accettiamo sia successo che errore gestito (non deve crashare)
        assert isinstance(esito_approva, dict), "approva() deve restituire un dict"
        assert "stato" in esito_approva or "errore" in esito_approva, \
            "approva() deve avere 'stato' o 'errore'"
        print(f"  approva(): risposta gestita correttamente -> {list(esito_approva.keys())}")

        # 6. rifiuta id inesistente
        err2 = cur.rifiuta(99999)
        assert "errore" in err2, "ID inesistente deve dare errore"
        print(f"  rifiuta(id_inesistente): errore gestito correttamente")

        # 7. elenco con stato non valido
        lista_vuota = cur.elenco("stato_inventato")
        assert lista_vuota == [], "Stato non valido deve ritornare lista vuota"
        print(f"  elenco(stato_non_valido): lista vuota corretta")

        cur.chiudi()

    print("OK")


if __name__ == "__main__":
    _smoke_test()
