"""
ARGO - connettori/email_imap.py
Connettore SOLA LETTURA per caselle email via IMAP.

Legge le intestazioni (mittente, oggetto, data) delle ultime N email
usando solo imaplib e email dalla libreria standard Python.
Non invia mai messaggi. Non scarica allegati.

Credenziali lette da config/connettori.json:
  email_imap.host, .porta, .ssl, .utente, .password, .cartella, .max_messaggi
"""

import imaplib
import email
import email.header
import json
import os
import ssl
import sys

# Import difensivo: funziona sia come modulo del pacchetto sia come script diretto
try:
    from .base import Connettore
except ImportError:
    # Eseguito come script diretto (python connettori/email_imap.py)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from connettori.base import Connettore

# --- percorso config ---
_DIR_ARGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILE_CONFIG = os.path.join(_DIR_ARGO, "config", "connettori.json")


def _decifra_password(password: str) -> str:
    """Decifra password IMAP cifrate con sicurezza.Chiave, lasciando compatibile il chiaro."""
    if not password:
        return password
    try:
        sys.path.insert(0, _DIR_ARGO)
        import sicurezza as _sic
        chiave = _sic.Chiave()
        if chiave.cifratura_disponibile():
            return chiave.decifra(password)
    except Exception:
        pass
    return password


def _carica_config_imap() -> dict:
    """Legge la sezione email_imap dal file di configurazione connettori."""
    try:
        with open(_FILE_CONFIG, "r", encoding="utf-8") as f:
            dati = json.load(f)
        return dati.get("email_imap", {})
    except Exception:
        return {}


def _decodifica_header(valore: str | None) -> str:
    """Decodifica un header email (es. soggetto codificato RFC 2047) in stringa leggibile."""
    if not valore:
        return ""
    try:
        parti = email.header.decode_header(valore)
        pezzi = []
        for testo, enc in parti:
            if isinstance(testo, bytes):
                pezzi.append(testo.decode(enc or "utf-8", errors="replace"))
            else:
                pezzi.append(str(testo))
        return " ".join(pezzi)
    except Exception:
        return str(valore)


class ConnettoreEmail(Connettore):
    """
    Connettore email IMAP in sola lettura.

    Legge le intestazioni delle ultime N email dalla cartella configurata.
    Non scarica il corpo del messaggio né gli allegati.

    Parametri accettati in leggi():
      - max_messaggi : int — quante email leggere (default da config, max 50)
      - cartella     : str — cartella IMAP da leggere (default da config, es. 'INBOX')
    """

    @property
    def nome(self) -> str:
        return "email_imap"

    @property
    def descrizione(self) -> str:
        return (
            "Legge le intestazioni (mittente, oggetto, data) delle ultime N email "
            "via IMAP in sola lettura. Credenziali da config/connettori.json."
        )

    def disponibile(self) -> bool:
        """
        Ritorna True solo se le credenziali IMAP sono configurate (host + utente + password).
        Non apre nessuna connessione di rete in questo metodo.
        """
        cfg = _carica_config_imap()
        host = cfg.get("host", "").strip()
        utente = cfg.get("utente", "").strip()
        password = cfg.get("password", "").strip()
        return bool(host and utente and password)

    def leggi(self, parametri: dict | None = None) -> list | dict:
        """
        Ritorna una lista di dizionari con le intestazioni delle email.

        Ogni voce contiene: uid, mittente, oggetto, data.
        In caso di errore ritorna {"errore": "<messaggio>"}.
        """
        if not self.disponibile():
            return {
                "errore": (
                    "Credenziali IMAP non configurate. "
                    "Compilare config/connettori.json (email_imap.host / .utente / .password)."
                )
            }

        cfg = _carica_config_imap()
        p = parametri or {}

        host: str = cfg["host"].strip()
        porta: int = int(cfg.get("porta", 993))
        usa_ssl: bool = bool(cfg.get("ssl", True))
        utente: str = cfg["utente"].strip()
        password: str = _decifra_password(cfg["password"].strip())
        cartella: str = p.get("cartella", cfg.get("cartella", "INBOX"))
        max_msg: int = min(int(p.get("max_messaggi", cfg.get("max_messaggi", 10))), 50)

        imap = None
        try:
            # --- connessione ---
            if usa_ssl:
                ctx = ssl.create_default_context()
                imap = imaplib.IMAP4_SSL(host, porta, ssl_context=ctx)
            else:
                imap = imaplib.IMAP4(host, porta)

            # --- autenticazione ---
            imap.login(utente, password)

            # --- selezione cartella in sola lettura ---
            stato, _ = imap.select(cartella, readonly=True)
            if stato != "OK":
                return {"errore": f"Impossibile aprire la cartella IMAP: {cartella}"}

            # --- ricerca degli ultimi N messaggi ---
            stato, dati = imap.search(None, "ALL")
            if stato != "OK":
                return {"errore": "Ricerca messaggi fallita."}

            uid_list = dati[0].split()
            # prendi gli ultimi max_msg uid
            uid_selezionati = uid_list[-max_msg:] if uid_list else []

            risultati = []
            for uid in reversed(uid_selezionati):  # dal più recente al più vecchio
                try:
                    stato_fetch, msg_dati = imap.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    if stato_fetch != "OK" or not msg_dati or msg_dati[0] is None:
                        continue

                    raw_header = msg_dati[0][1]
                    msg = email.message_from_bytes(raw_header)

                    risultati.append({
                        "uid": uid.decode(),
                        "mittente": _decodifica_header(msg.get("From")),
                        "oggetto": _decodifica_header(msg.get("Subject")),
                        "data": _decodifica_header(msg.get("Date")),
                    })
                except Exception:
                    # messaggio singolo non leggibile: lo saltiamo
                    continue

            return risultati

        except imaplib.IMAP4.error as e:
            return {"errore": f"Errore IMAP: {e}"}
        except ConnectionRefusedError:
            return {"errore": f"Connessione rifiutata da {host}:{porta}"}
        except OSError as e:
            return {"errore": f"Errore di rete: {e}"}
        except Exception as e:
            return {"errore": f"Errore imprevisto: {e}"}
        finally:
            if imap is not None:
                try:
                    imap.logout()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Smoke-test: verifica la struttura senza credenziali reali
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Bootstrap sys.path per esecuzione diretta (python connettori\email_imap.py)
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    conn = ConnettoreEmail()
    print(f"Connettore: {conn}")

    # Verifica che disponibile() ritorni un bool
    disp = conn.disponibile()
    assert isinstance(disp, bool), "disponibile() deve ritornare bool"

    if disp:
        # Credenziali presenti: proviamo una lettura reale (max 3 email)
        risultato = conn.leggi({"max_messaggi": 3})
        if isinstance(risultato, list):
            print(f"  Email lette: {len(risultato)}")
        else:
            print(f"  Risultato: {risultato}")
    else:
        # Credenziali assenti: verifica che leggi() ritorni gracefully
        risultato = conn.leggi()
        assert isinstance(risultato, dict) and "errore" in risultato, \
            "Senza credenziali deve ritornare {'errore': ...}"
        print(f"  Senza credenziali: degradazione corretta -> {risultato['errore'][:60]}...")

    print("OK")
