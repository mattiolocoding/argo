"""
ARGO - produzione/interfaccia.py  (Fase A - la UI, livello 1)
La FINESTRA di Argo. Non contiene il cervello: si COLLEGA al motore (motore.py)
via l'API locale. Puoi aprirla e chiuderla quando vuoi: il motore continua a
vivere in background.

Avvio:  prima 'python motore.py', poi 'python interfaccia.py'.
Solo libreria standard (tkinter + urllib).
"""

import json
import threading
import urllib.request
import tkinter as tk

API = "http://127.0.0.1:8773"
POLL_MS = 1500


def _get(path):
    with urllib.request.urlopen(API + path, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path, dati):
    corpo = json.dumps(dati).encode("utf-8")
    req = urllib.request.Request(API + path, data=corpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


class Interfaccia:
    def __init__(self, root):
        self.root = root
        root.title("ARGO")
        root.geometry("410x380+60+60")
        root.attributes("-topmost", True)
        root.configure(bg="#0d1117")
        root.resizable(False, False)

        self.faccia = tk.Label(root, text="( ◕‿◕ )", font=("Consolas", 30),
                               fg="#58a6ff", bg="#0d1117")
        self.faccia.pack(pady=(14, 2))
        tk.Label(root, text="ARGO", font=("Consolas", 12, "bold"),
                 fg="#8b949e", bg="#0d1117").pack()

        self.msg = tk.Label(root, text="Mi collego al motore…", font=("Segoe UI", 10),
                            fg="#c9d1d9", bg="#0d1117", wraplength=370, justify="center")
        self.msg.pack(pady=10, padx=12)

        self.bottoni = tk.Frame(root, bg="#0d1117")
        tk.Button(self.bottoni, text="Sì, sistema", width=12, bg="#238636", fg="white",
                  relief="flat", command=lambda: self._conferma(True)).pack(side="left", padx=6)
        tk.Button(self.bottoni, text="No, lascia", width=12, bg="#30363d", fg="white",
                  relief="flat", command=lambda: self._conferma(False)).pack(side="left", padx=6)

        # chat
        chat = tk.Frame(root, bg="#0d1117")
        chat.pack(side="bottom", fill="x", padx=10, pady=4)
        self.entry = tk.Entry(chat, bg="#161b22", fg="#c9d1d9", insertbackground="#c9d1d9",
                              relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.entry.bind("<Return>", lambda e: self._chat())
        tk.Button(chat, text="Chiedi", bg="#1f6feb", fg="white", relief="flat",
                  command=self._chat).pack(side="left", padx=(6, 0))

        self.stato = tk.Label(root, text="", font=("Segoe UI", 8),
                              fg="#8b949e", bg="#0d1117")
        self.stato.pack(side="bottom", pady=2)

        self._proposta_attiva = False
        self._aggiorna()

    def parla(self, testo, colore="#c9d1d9", faccia="( ◕‿◕ )"):
        self.msg.config(text=testo, fg=colore)
        self.faccia.config(text=faccia)

    def _aggiorna(self):
        def lavoro():
            try:
                s = _get("/stato")
            except Exception:
                s = None
            self.root.after(0, lambda: self._mostra(s))
        threading.Thread(target=lavoro, daemon=True).start()
        self.root.after(POLL_MS, self._aggiorna)

    def _mostra(self, s):
        if s is None:
            self.parla("Motore non raggiungibile. È avviato? (python motore.py)",
                       colore="#f85149", faccia="( ・_・)")
            self.stato.config(text="offline")
            self.bottoni.pack_forget()
            return
        if s.get("proposta"):
            self.parla(s["proposta"], colore="#d29922", faccia="( •_•)")
            if not self._proposta_attiva:
                self.bottoni.pack(pady=2)
                self._proposta_attiva = True
        else:
            self.parla(s.get("messaggio", "…"))
            if self._proposta_attiva:
                self.bottoni.pack_forget()
                self._proposta_attiva = False
        cer = "connesso" if s.get("cervello_online") else "in accensione…"
        self.stato.config(text=f"Cervello {cer}  •  Ricordi: {s.get('ricordi',0)}  •  {s.get('cartelle',0)} cartelle")

    def _conferma(self, si):
        self.bottoni.pack_forget()
        self._proposta_attiva = False

        def lavoro():
            try:
                _post("/conferma", {"si": si})
            except Exception:
                pass
        threading.Thread(target=lavoro, daemon=True).start()

    def _chat(self):
        testo = self.entry.get().strip()
        if not testo:
            return
        self.entry.delete(0, "end")
        self.parla("…sto pensando", colore="#8b949e", faccia="( •_•)")

        def lavoro():
            try:
                r = _post("/chat", {"testo": testo})
                risp = r.get("risposta", "…")
            except Exception:
                risp = "Non riesco a contattare il motore."
            self.root.after(0, lambda: self.parla(risp, colore="#58a6ff", faccia="( ⊙▿⊙ )"))
        threading.Thread(target=lavoro, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    Interfaccia(root)
    root.mainloop()
