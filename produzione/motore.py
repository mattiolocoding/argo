"""
ARGO - produzione/motore.py  (Fase A - il MOTORE, livello 2)
Il cervello di Argo che vive in background, SENZA finestra. Espone una piccola
API locale su 127.0.0.1 cosi' la finestra (interfaccia.py) puo' collegarsi.
Chiudere la finestra NON spegne il motore: e' qui che vive Argo.

Riusa i moduli gia' testati della cartella Argo (cervello, memoria, mani, config,
sistema). Solo libreria standard (http.server).

Avvio manuale (per provarlo):  python motore.py
Poi apri la finestra:          python interfaccia.py
"""

import os
import sys
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# permetti di importare i moduli della cartella Argo (la cartella sopra)
_QUI = os.path.dirname(os.path.abspath(__file__))
_ARGO = os.path.dirname(_QUI)
if _ARGO not in sys.path:
    sys.path.insert(0, _ARGO)

from cervello import Cervello
from memoria import Memoria
from mani import Mani, categoria_di
from mani.mani import CARTELLE_DI_ARGO
from config import Impostazioni
import sistema

HOST, PORT = "127.0.0.1", 8773
CHECK_EVERY = 3
SCAN_EVERY = 60


class Motore:
    def __init__(self):
        self.memoria = Memoria()
        self.impostazioni = Impostazioni()
        self.cervello = Cervello()

        self.cartelle = []
        for c in self.impostazioni.cartelle_sorvegliate():
            p = c if os.path.isabs(c) else os.path.join(_ARGO, c)
            p = os.path.abspath(p)
            try:
                os.makedirs(p, exist_ok=True)
                self.cartelle.append(p)
            except Exception:
                pass
        self.regola = self.impostazioni.regola_ordine()
        self.soglia = self.impostazioni.soglia_accumulo()
        self.mani = Mani(radici=self.cartelle,
                         cartelle_protette=self.impostazioni.cartelle_protette())

        self.lock = threading.Lock()
        self.coda = []
        self.in_coda = set()
        self.proposta = None              # piano in attesa di conferma
        self.ultimo_messaggio = "Sono sveglio."
        self.cervello_online = False
        self.viste = {f: self._scatta(f) for f in self.cartelle}
        self.accumulo_segnalato = set()
        self.disco_segnalato = False
        self.running = True

        self.memoria.registra_accesso()
        threading.Thread(target=self.cervello.assicura_acceso, daemon=True).start()
        threading.Thread(target=self._loop, daemon=True).start()

    # ---- util ----
    def _scatta(self, c):
        try:
            return set(os.listdir(c))
        except Exception:
            return set()

    def _solo_file(self, c, nomi):
        out = []
        for n in nomi:
            if n in CARTELLE_DI_ARGO:
                continue
            if os.path.isfile(os.path.join(c, n)):
                out.append(n)
        return out

    def _msg(self, testo):
        self.ultimo_messaggio = testo
        print("[MOTORE]", testo)

    # ---- loop di vita ----
    def _loop(self):
        contatore = 0
        while self.running:
            try:
                self.cervello_online = self.cervello.vivo()
                self._percepisci()
                contatore += CHECK_EVERY
                if contatore >= SCAN_EVERY:
                    contatore = 0
                    self._scansione()
                self._processa()
            except Exception as e:
                print("[MOTORE] errore loop:", e)
            time.sleep(CHECK_EVERY)

    def _percepisci(self):
        with self.lock:
            for c in self.cartelle:
                adesso = self._scatta(c)
                nuovi = self._solo_file(c, adesso - self.viste.get(c, set()))
                for nome in sorted(nuovi):
                    self.memoria.ricorda("file_aggiunto", nome)
                    piano = self.mani.proponi_archiviazione(os.path.join(c, nome), self.regola)
                    self._accoda(piano, categoria_di(nome))
                self.viste[c] = adesso

    def _accoda(self, piano, categoria):
        if not piano:
            return
        src = piano.get("sorgente")
        if src and src in self.in_coda:
            return
        piano["_categoria"] = categoria
        if src:
            self.in_coda.add(src)
        self.coda.append(piano)

    def _scansione(self):
        for c in self.cartelle:
            for dup in self.mani.trova_duplicati(c):
                if dup not in self.in_coda:
                    self._accoda(self.mani.proponi_sposta_duplicato(dup), "duplicati")
            n_file = len(self._solo_file(c, self._scatta(c)))
            if n_file > self.soglia and c not in self.accumulo_segnalato:
                self.accumulo_segnalato.add(c)
                self.memoria.ricorda("accumulo", f"{n_file} file in {os.path.basename(c)}")
        d = sistema.disco()
        if "errore" not in d and d.get("perc_usato", 0) >= 90 and not self.disco_segnalato:
            self.disco_segnalato = True
            self._msg("Attenzione: " + sistema.stato_sintetico())

    def _livello(self, piano):
        cat = piano.get("_categoria")
        pref = self.memoria.preferenza(cat) if cat else None
        return pref or self.impostazioni.autonomia(piano["azione"])

    def _processa(self):
        with self.lock:
            if self.proposta or not self.coda:
                return
            piano = self.coda.pop(0)
            src = piano.get("sorgente")
            if src:
                self.in_coda.discard(src)
            if src and not os.path.exists(src):
                return
            livello = self._livello(piano)
            if livello == "osserva":
                self._msg("Noto: " + piano["descrizione"] + " (resto a guardare).")
                self.memoria.ricorda("osservato", piano["descrizione"])
            elif livello == "agisce":
                r = self.mani.esegui(piano)
                self._msg(("Fatto. " + piano["descrizione"]) if r["ok"]
                          else ("Non riuscito: " + r["messaggio"]))
                self.memoria.ricorda("azione", piano["descrizione"], esito=r["messaggio"])
            else:
                self.proposta = piano
                self._msg(piano["descrizione"] + " Procedo?")

    # ---- API azioni ----
    def conferma(self, si):
        with self.lock:
            piano = self.proposta
            if not piano:
                return {"ok": False, "messaggio": "nessuna proposta in attesa"}
            self.proposta = None
            if si:
                r = self.mani.esegui(piano)
                self.memoria.ricorda("azione_confermata", piano["descrizione"], esito=r["messaggio"])
                self.memoria.registra_scelta(piano.get("_categoria"), True)
                self._msg(("Fatto. " + piano["descrizione"]) if r["ok"]
                          else ("Non riuscito: " + r["messaggio"]))
                return r
            else:
                self.memoria.ricorda("azione_rifiutata", piano["descrizione"])
                self.memoria.registra_scelta(piano.get("_categoria"), False)
                self._msg("Va bene, lo lascio dov'è.")
                return {"ok": True, "messaggio": "lasciato"}

    def stato(self):
        return {
            "cervello_online": self.cervello_online,
            "ricordi": self.memoria.conta(),
            "cartelle": len(self.cartelle),
            "messaggio": self.ultimo_messaggio,
            "proposta": (self.proposta["descrizione"] if self.proposta else None),
        }

    def chat(self, testo):
        return {"risposta": self.cervello.pensa(testo)}


# ---- API HTTP ----
def crea_handler(motore):
    class H(BaseHTTPRequestHandler):
        def _json(self, dati, code=200):
            corpo = json.dumps(dati).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _body(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                return json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return {}

        def log_message(self, *a):
            pass  # silenzio

        def do_GET(self):
            if self.path.startswith("/stato"):
                self._json(motore.stato())
            elif self.path.startswith("/ricordi"):
                self._json({"ricordi": motore.memoria.ricordi_recenti(10)})
            else:
                self._json({"argo": "motore attivo"})

        def do_POST(self):
            if self.path.startswith("/conferma"):
                self._json(motore.conferma(bool(self._body().get("si"))))
            elif self.path.startswith("/chat"):
                self._json(motore.chat(self._body().get("testo", "")))
            else:
                self._json({"ok": False}, 404)
    return H


if __name__ == "__main__":
    print(f"[MOTORE] avvio su http://{HOST}:{PORT}")
    m = Motore()
    server = ThreadingHTTPServer((HOST, PORT), crea_handler(m))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        m.running = False
        print("\n[MOTORE] spento.")
