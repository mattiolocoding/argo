"""
ARGO - cervello.py
Il cervello di Argo: parla con Ollama in locale e, se serve, lo ACCENDE da solo.
Nessuna libreria da installare: usa solo la libreria standard di Python.

DIAGNOSI RAPIDA:  python cervello.py
  -> dice se Ollama e' acceso, quali modelli hai e se Argo riesce a pensare.
"""

import os
import json
import time
import shutil
import subprocess
import urllib.request
import urllib.error

# --- CONFIG -------------------------------------------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODELLO_PREFERITO = "llama3.1"
TIMEOUT_SECONDI = 120
# ------------------------------------------------------------------

PERSONA = (
    "Sei ARGO, un essere digitale che vive sul computer di Davide. "
    "Parli SEMPRE in italiano, in modo breve, diretto e concreto (max 2-3 frasi). "
    "REGOLA FONDAMENTALE: non inventare MAI nulla. Usa solo i dati reali che ti "
    "vengono forniti nel messaggio. Se un'informazione non è nei dati, dì "
    "chiaramente che non ce l'hai. Niente supposizioni, niente storie inventate. "
    "Niente elenchi, niente fronzoli."
)


class Cervello:
    def __init__(self, modello=None):
        self.host = OLLAMA_HOST.rstrip("/")
        self.modello_preferito = modello or MODELLO_PREFERITO
        self.modello = None          # risolto al primo uso
        self.ultimo_errore = None

    # ---- stato ----
    def vivo(self):
        """True se Ollama risponde."""
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=5) as r:
                return r.status == 200
        except Exception as e:
            self.ultimo_errore = str(e)
            return False

    def modelli(self):
        """Lista dei modelli installati in Ollama."""
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=5) as r:
                dati = json.loads(r.read().decode("utf-8"))
                return [m.get("name", "") for m in dati.get("models", [])]
        except Exception as e:
            self.ultimo_errore = str(e)
            return []

    def scegli_modello(self):
        """Il preferito se c'e', altrimenti il primo disponibile."""
        disponibili = self.modelli()
        if not disponibili:
            return None
        for m in disponibili:
            if m == self.modello_preferito or m.startswith(self.modello_preferito):
                self.modello = m
                return m
        self.modello = disponibili[0]
        return self.modello

    # ---- accensione automatica (come fanno le app serie) ----
    def avvia_ollama(self):
        """Lancia 'ollama serve' in background se l'eseguibile c'e'. True se avviato."""
        exe = shutil.which("ollama")
        if not exe:
            self.ultimo_errore = "eseguibile 'ollama' non trovato nel PATH"
            return False
        try:
            kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          stdin=subprocess.DEVNULL)
            if os.name == "nt":
                # niente finestra nera del terminale (CREATE_NO_WINDOW)
                kwargs["creationflags"] = 0x08000000
            subprocess.Popen([exe, "serve"], **kwargs)
            return True
        except Exception as e:
            self.ultimo_errore = str(e)
            return False

    def assicura_acceso(self, timeout=45, passo=2):
        """Garantisce il cervello raggiungibile: se spento accende Ollama e attende.
        Ritorna True se alla fine e' vivo."""
        if self.vivo():
            return True
        self.avvia_ollama()
        atteso = 0
        while atteso < timeout:
            time.sleep(passo)
            atteso += passo
            if self.vivo():
                return True
        return False

    def diagnosi(self):
        if not self.vivo():
            return (False,
                    "Ollama NON risponde su " + self.host + ".\n"
                    "  -> Avvia Ollama (menu Start) oppure: ollama serve")
        disponibili = self.modelli()
        if not disponibili:
            return (False,
                    "Ollama acceso ma senza modelli.\n  -> ollama pull llama3.1")
        m = self.scegli_modello()
        nota = "" if (m == self.modello_preferito or m.startswith(self.modello_preferito)) \
            else f"  (preferito '{self.modello_preferito}' assente, uso '{m}')"
        return (True, f"Tutto ok. Modelli: {', '.join(disponibili)}. Uso: {m}{nota}")

    # ---- pensiero ----
    def pensa(self, messaggio, contesto=None):
        if self.modello is None:
            if self.scegli_modello() is None:
                return "[cervello offline: Ollama non risponde o non ha modelli]"

        messaggi = [{"role": "system", "content": PERSONA}]
        if contesto:
            messaggi.extend(contesto)
        messaggi.append({"role": "user", "content": messaggio})

        payload = json.dumps({
            "model": self.modello,
            "messages": messaggi,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.host + "/api/chat", data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDI) as r:
                dati = json.loads(r.read().decode("utf-8"))
                return dati.get("message", {}).get("content", "").strip()
        except urllib.error.URLError as e:
            return f"[cervello non raggiungibile: {e}. Ollama e' acceso?]"
        except Exception as e:
            return f"[errore cervello: {e}]"


# ---- diagnostica: python cervello.py ----
if __name__ == "__main__":
    print("== Diagnosi cervello di ARGO ==")
    print("Host Ollama:", OLLAMA_HOST)
    c = Cervello()
    if not c.vivo():
        print("Cervello spento: provo ad accenderlo da solo...")
        c.assicura_acceso(timeout=30)
    ok, msg = c.diagnosi()
    print(("[OK] " if ok else "[PROBLEMA] ") + msg)
    if ok:
        print("\nProva di pensiero:")
        print("ARGO:", c.pensa("Presentati in una frase."))
