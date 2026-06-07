"""
ARGO - voce.py
Voce di ARGO: TTS (Text-To-Speech) reale e offline.
Usa pyttsx3 per parlare attraverso l'audio locale del sistema
(SAPI5 su Windows, nsss su macOS, espeak su Linux). Nessuna rete,
nessuna dipendenza nuova: pyttsx3 e' gia' installato nel venv.

Tutto best-effort: se pyttsx3 o l'audio mancano, le funzioni
degradano con grazia restituendo un dict {ok, motivo} senza mai
sollevare eccezioni.

STT (ascolto / Speech-To-Text): offline via Vosk + microfono (sounddevice).
Il modello sta in dati/vosk-it (oppure env ARGO_VOSK_MODEL). Se vosk, il
modello o il microfono mancano, ascolta() degrada con grazia.

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
# Ascolto (STT) — Vosk offline + microfono (sounddevice)
# ──────────────────────────────────────────────

import os as _os
import json as _json

_vosk = None
_errore_vosk = None
try:
    import vosk as _vosk
    _vosk.SetLogLevel(-1)          # niente log rumorosi
except Exception as e:
    _errore_vosk = str(e)

_SAMPLE_RATE = 16000
_modello_stt = None                # cache del modello caricato
_modello_stt_path = None


def _percorso_modello() -> str:
    """Cartella del modello Vosk: env ARGO_VOSK_MODEL, altrimenti dati/vosk-it."""
    p = _os.environ.get("ARGO_VOSK_MODEL", "").strip()
    if p:
        return p
    base = _os.path.dirname(_os.path.abspath(__file__))
    return _os.path.join(base, "dati", "vosk-it")


def stt_disponibile() -> bool:
    """True se vosk e' importabile e il modello e' presente su disco."""
    return _vosk is not None and _os.path.isdir(_percorso_modello())


def _carica_modello():
    """Carica (una sola volta) il modello Vosk. Ritorna il Model o None."""
    global _modello_stt, _modello_stt_path
    if _vosk is None:
        return None
    path = _percorso_modello()
    if _modello_stt is not None and _modello_stt_path == path:
        return _modello_stt
    if not _os.path.isdir(path):
        return None
    try:
        _modello_stt = _vosk.Model(path)
        _modello_stt_path = path
        return _modello_stt
    except Exception:
        return None


def _trascrivi_pcm(pcm_bytes: bytes) -> str:
    """Trascrive PCM 16kHz mono int16 con Vosk. Stringa vuota se nulla."""
    model = _carica_modello()
    if model is None:
        return ""
    rec = _vosk.KaldiRecognizer(model, _SAMPLE_RATE)
    rec.AcceptWaveform(pcm_bytes)
    try:
        return (_json.loads(rec.FinalResult()) or {}).get("text", "").strip()
    except Exception:
        return ""


def trascrivi_wav(percorso: str) -> dict:
    """Trascrive un file WAV mono 16-bit (utile per test senza microfono)."""
    if not stt_disponibile():
        return {"ok": False, "motivo": "STT non disponibile (modello Vosk assente)", "testo": ""}
    try:
        import wave
        with wave.open(percorso, "rb") as wf:
            pcm = wf.readframes(wf.getnframes())
        return {"ok": True, "motivo": "ok", "testo": _trascrivi_pcm(pcm)}
    except Exception as e:
        return {"ok": False, "motivo": f"errore lettura wav: {e}", "testo": ""}


def ascolta(secondi: float = 5.0) -> dict:
    """
    Cattura dal microfono per 'secondi' e trascrive offline con Vosk.
    Ritorna sempre {ok, motivo, testo}; non solleva mai. Degrada con grazia
    se vosk, il modello o il microfono mancano.
    """
    if _vosk is None:
        m = "vosk non disponibile"
        if _errore_vosk:
            m += f" ({_errore_vosk})"
        return {"ok": False, "motivo": m, "testo": ""}
    if not _os.path.isdir(_percorso_modello()):
        return {"ok": False, "motivo": f"modello Vosk assente in {_percorso_modello()}", "testo": ""}
    try:
        import sounddevice as sd
    except Exception as e:
        return {"ok": False, "motivo": f"sounddevice non disponibile ({e})", "testo": ""}
    try:
        secondi = max(0.5, min(float(secondi), 30.0))
        audio = sd.rec(int(secondi * _SAMPLE_RATE), samplerate=_SAMPLE_RATE,
                       channels=1, dtype="int16")
        sd.wait()
        return {"ok": True, "motivo": "ok", "testo": _trascrivi_pcm(bytes(audio))}
    except Exception as e:
        return {"ok": False, "motivo": f"errore microfono: {e}", "testo": ""}


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

    def ascolta(self, secondi: float = 5.0) -> dict:
        """STT: ascolta dal microfono e trascrive (Vosk offline)."""
        return ascolta(secondi)

    def stt_disponibile(self) -> bool:
        """True se il riconoscimento vocale e' utilizzabile."""
        return stt_disponibile()


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

    # STT (Vosk): verifica senza microfono (CI-safe).
    print("STT disponibile  :", stt_disponibile())
    if stt_disponibile():
        import tempfile, wave, os
        p = os.path.join(tempfile.gettempdir(), "_argo_stt_test.wav")
        with wave.open(p, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 8000)   # 0.5s di silenzio
        r = trascrivi_wav(p)
        try: os.remove(p)
        except Exception: pass
        print("Trascrizione test:", r.get("ok"), repr(r.get("testo")))

    # NON parliamo e NON ascoltiamo dal vivo di default: in CI non c'e'
    # audio. La sintesi reale e' coperta dal timeout in parla().
    print("OK voce")
