"""
ARGO - presenza.py
Presenza vocale: ascolto CONTINUO + wake-word, offline (Vosk).

ARGO resta in ascolto in background; quando sente la wake-word (default
"argo") prende la frase-comando che segue e la passa a un callback
(tipicamente la chat di ARGO, che puo' poi rispondere a voce).

Privacy: l'ascolto continuo e' SPENTO di default e si attiva solo su
richiesta esplicita dell'utente. Tutto e' locale: nessun audio lascia il PC.
Degrada con grazia se vosk, il modello o il microfono mancano (non solleva mai).

Prova:  python presenza.py    (test della logica wake-word, senza microfono)
"""

import json
import queue
import threading

try:
    import voce as _voce            # riusa modello/STT di voce.py
except Exception:
    _voce = None


class Presenza:
    """Ascolto continuo con wake-word. Tutto best-effort, mai bloccante per il chiamante."""

    def __init__(self, wake: str = "argo", on_comando=None, sample_rate: int = 16000):
        self.wake = (wake or "argo").lower().strip()
        self.on_comando = on_comando        # callback(testo_comando)
        self.sample_rate = sample_rate
        self._thread = None
        self._stop = threading.Event()
        self.attiva = False
        self.ultimo_sentito = ""
        self.ultimo_comando = ""
        self.errore = None

    def disponibile(self) -> bool:
        """True se lo STT (vosk + modello) e' utilizzabile."""
        return bool(_voce and _voce.stt_disponibile())

    def _estrai_comando(self, testo: str):
        """
        Se 'testo' contiene la wake-word, ritorna la parte DOPO di essa (il comando,
        eventualmente vuoto). Se la wake-word non c'e', ritorna None.
        """
        t = (testo or "").lower()
        i = t.find(self.wake)
        if i < 0:
            return None
        return testo[i + len(self.wake):].strip(" ,.:;!?\t")

    def _loop(self):
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer
            model = _voce._carica_modello() if _voce else None
            if model is None:
                self.errore = "modello non disponibile"
                self.attiva = False
                return
            rec = KaldiRecognizer(model, self.sample_rate)
            q = queue.Queue()

            def _cb(indata, frames, t, status):
                q.put(bytes(indata))

            with sd.RawInputStream(samplerate=self.sample_rate, blocksize=8000,
                                   dtype="int16", channels=1, callback=_cb):
                while not self._stop.is_set():
                    try:
                        data = q.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        try:
                            testo = (json.loads(rec.Result()) or {}).get("text", "").strip()
                        except Exception:
                            testo = ""
                        if testo:
                            self.ultimo_sentito = testo
                            cmd = self._estrai_comando(testo)
                            if cmd is not None:
                                self.ultimo_comando = cmd
                                if cmd and self.on_comando:
                                    try:
                                        self.on_comando(cmd)
                                    except Exception:
                                        pass
        except Exception as e:
            self.errore = str(e)
        finally:
            self.attiva = False

    def avvia(self) -> dict:
        if not self.disponibile():
            return {"ok": False, "motivo": "STT non disponibile (vosk/modello assenti)"}
        if self.attiva:
            return {"ok": True, "motivo": "gia' in ascolto", "wake": self.wake}
        self._stop.clear()
        self.errore = None
        self.attiva = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return {"ok": True, "motivo": "in ascolto", "wake": self.wake}

    def ferma(self) -> dict:
        self._stop.set()
        self.attiva = False
        return {"ok": True, "motivo": "ascolto fermato"}

    def stato(self) -> dict:
        return {
            "attiva": self.attiva,
            "wake": self.wake,
            "disponibile": self.disponibile(),
            "ultimo_sentito": self.ultimo_sentito,
            "ultimo_comando": self.ultimo_comando,
            "errore": self.errore,
        }


if __name__ == "__main__":
    # Test della logica wake-word: NON richiede microfono (sicuro in CI).
    p = Presenza(wake="argo")
    casi = [
        ("argo cosa hai sistemato oggi", "cosa hai sistemato oggi"),
        ("ciao argo, apri i download", "apri i download"),
        ("ARGO   accendi la musica", "accendi la musica"),
        ("buongiorno a tutti", None),
        ("argo", ""),
    ]
    ok = True
    for testo, atteso in casi:
        got = p._estrai_comando(testo)
        esito = "OK  " if got == atteso else "FAIL"
        if got != atteso:
            ok = False
        print(f"  [{esito}] {testo!r} -> {got!r} (atteso {atteso!r})")
    print("STT disponibile :", p.disponibile())
    print("OK presenza" if ok else "FAIL presenza")
    if not ok:
        raise SystemExit(1)
