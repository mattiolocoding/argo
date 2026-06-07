"""
ARGO - voce.py
Voce di ARGO: TTS (Text-To-Speech) reale e offline.
Usa pyttsx3 per parlare attraverso l'audio locale del sistema
(SAPI5 su Windows, nsss su macOS, espeak su Linux). Nessuna rete,
nessuna dipendenza nuova: pyttsx3 e' gia' installato nel venv.

Tutto best-effort: se pyttsx3 o l'audio mancano, le funzioni
degradano con grazia restituendo un dict {ok, motivo} senza mai
sollevare eccezioni.

Nota onesta: lo STT (ascolto / Speech-To-Text) NON e' ancora
implementato. La funzione ascolta() e' uno stub esplicito.

Prova:  python voce.py
        python -m voce
"""

import threading


# ──────────────────────────────────────────────
# Importazione difensiva di pyttsx3
# ──────────────────────────────────────────────

_pyttsx3 = None
_errore_import = None

try:
    import pyttsx3 as _pyttsx3
except Exception as e:  # ImportError o errori di backend a livello di import
    _errore_import = str(e)


# Timeout di sicurezza per non bloccare mai il chiamante (secondi).
# Una frase breve in genere richiede 1-3s; oltre questo limite
# consideriamo l'audio bloccato e degradiamo con grazia.
_TIMEOUT_PARLA = 15.0


# ──────────────────────────────────────────────
# Disponibilita'
# ──────────────────────────────────────────────

def disponibile() -> bool:
    """
    True se la sintesi vocale e' utilizzabile su questa macchina.
    Tenta di inizializzare un motore pyttsx3 e poi lo rilascia.
    Non parla e non blocca: solo una verifica rapida e silenziosa.
    """
    if _pyttsx3 is None:
        return False
    try:
        motore = _pyttsx3.init()
        # Se siamo arrivati qui il backend (es. SAPI5) e' presente.
        try:
            motore.stop()
        except Exception:
            pass
        del motore
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# Parla (TTS)
# ──────────────────────────────────────────────

def _parla_sincrono(testo: str, esito: dict) -> None:
    """
    Esegue effettivamente la sintesi vocale. Pensata per girare in un
    thread separato cosi' da poter applicare un timeout dall'esterno.
    Scrive l'esito (mutando il dict condiviso) invece di restituirlo.
    """
    try:
        motore = _pyttsx3.init()
        try:
            motore.say(testo)
            # runAndWait() e' bloccante: il timeout esterno ci protegge
            motore.runAndWait()
            esito["ok"] = True
            esito["motivo"] = "ok"
        finally:
            try:
                motore.stop()
            except Exception:
                pass
    except Exception as e:
        esito["ok"] = False
        esito["motivo"] = f"errore durante la sintesi: {e}"


def parla(testo: str) -> dict:
    """
    Pronuncia 'testo' tramite l'audio locale.
    Ritorna sempre un dict {ok: bool, motivo: str}; non solleva mai.

    La sintesi gira in un thread con timeout: se l'audio si blocca,
    la funzione ritorna comunque (degrada con grazia) lasciando il
    thread in background a morire da solo.
    """
    # Validazione input: niente da dire
    if testo is None or not str(testo).strip():
        return {"ok": False, "motivo": "testo vuoto"}

    if _pyttsx3 is None:
        motivo = "pyttsx3 non disponibile"
        if _errore_import:
            motivo += f" ({_errore_import})"
        return {"ok": False, "motivo": motivo}

    testo = str(testo)
    # Dict condiviso col thread: valore di default se andiamo in timeout
    esito = {"ok": False, "motivo": "sintesi non completata"}

    # daemon=True: se il processo termina, il thread non blocca l'uscita
    th = threading.Thread(
        target=_parla_sincrono, args=(testo, esito), daemon=True
    )
    try:
        th.start()
        th.join(timeout=_TIMEOUT_PARLA)
    except Exception as e:
        return {"ok": False, "motivo": f"impossibile avviare la voce: {e}"}

    if th.is_alive():
        # Audio bloccato: non aspettiamo oltre, degradiamo con grazia.
        return {"ok": False, "motivo": "timeout sintesi vocale"}

    return esito


# ──────────────────────────────────────────────
# Ascolto (STT) - TODO: non ancora implementato
# ──────────────────────────────────────────────

def ascolta() -> dict:
    """
    Stub per il riconoscimento vocale (Speech-To-Text).

    TODO: lo STT non e' ancora implementato. Quando lo sara', qui andra'
    la cattura dal microfono + trascrizione offline (es. vosk o whisper
    locale), sempre con la stessa filosofia: best-effort e degradazione
    con grazia. Per ora ritorna onestamente un esito negativo.
    """
    return {"ok": False, "motivo": "STT non ancora implementato"}


# ──────────────────────────────────────────────
# Classe Voce (interfaccia OO, coerente col resto del progetto)
# ──────────────────────────────────────────────

class Voce:
    """Interfaccia orientata agli oggetti per la voce di ARGO."""

    def disponibile(self) -> bool:
        """True se la sintesi vocale e' utilizzabile."""
        return disponibile()

    def parla(self, testo: str) -> dict:
        """Pronuncia il testo. Ritorna {ok, motivo}."""
        return parla(testo)

    def ascolta(self) -> dict:
        """STT: stub, non ancora implementato."""
        return ascolta()


# ──────────────────────────────────────────────
# Smoke-test: python voce.py  /  python -m voce
# Non blocca e NON richiede audio (sicuro in CI).
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # Solo ASCII nei print per evitare crash su CP1252.
    print("=== ARGO voce.py -- smoke-test ===")

    disp = disponibile()
    print("Voce disponibile :", disp)
    print("pyttsx3 importato:", _pyttsx3 is not None)
    if _errore_import:
        err_safe = _errore_import.encode("ascii", errors="replace").decode("ascii")
        print("Errore import    :", err_safe)

    # Stub STT: deve sempre rispondere in modo onesto, senza bloccare.
    print("Ascolto (STT)    :", ascolta())

    # NON parliamo di default: in CI non c'e' audio e non vogliamo
    # bloccare. La sintesi reale e' coperta dal timeout in parla().
    print("OK voce")
