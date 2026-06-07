"""
ARGO - argo.py  (v1.0 - finestra moderna + chat + occhi su tutto il PC)
Vive sul PC: ti saluta, sorveglia le tue cartelle, ricorda, impara, agisce in
sicurezza, capisce e RISPONDE alle tue domande. Memoria di frontiera: diario +
knowledge graph + semantica. Se Ollama è spento lo accende da solo.

AVVIO:  python argo.py   (oppure avvia_argo.bat)
Impostazioni in config/config.json.
"""

import os
import datetime
import threading
import tkinter as tk

from cervello import Cervello
from memoria import Memoria, Grafo, Semantica
from mani import Mani, categoria_di
from mani.mani import CARTELLE_DI_ARGO
from config import Impostazioni
import sistema

_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_EVERY_SECONDS = 3
HEALTH_EVERY_SECONDS = 5
SCAN_EVERY_SECONDS = 60

# palette
BG = "#0d1117"
BG2 = "#161b22"
TX = "#c9d1d9"
MUTE = "#8b949e"
BLU = "#58a6ff"
VERDE = "#3fb950"
ARANCIO = "#d29922"
ROSSO = "#f85149"


def saluto_orario():
    o = datetime.datetime.now().hour
    if 5 <= o < 12:
        return "Buongiorno, Davide."
    if 12 <= o < 18:
        return "Buon pomeriggio, Davide."
    if 18 <= o < 23:
        return "Buonasera, Davide."
    return "E' tardi, Davide. Veglio io."


def cartelle_utente():
    """Le cartelle principali dell'utente (gli 'occhi su tutto il PC')."""
    home = os.path.expanduser("~")
    nomi = ["Desktop", "Downloads", "Documents", "Pictures", "Music", "Videos"]
    out = []
    for n in nomi:
        p = os.path.join(home, n)
        if os.path.isdir(p):
            out.append(p)
    return out


class Argo:
    def __init__(self, root):
        self.root = root
        self.memoria = Memoria()
        self.impostazioni = Impostazioni()
        self.cervello = Cervello()
        self.grafo = Grafo()
        self.semantica = Semantica()

        # ---- occhi: cartelle sorvegliate ----
        self.cartelle = []
        for c in self.impostazioni.cartelle_sorvegliate():
            p = c if os.path.isabs(c) else os.path.join(_DIR, c)
            self._aggiungi_cartella(os.path.abspath(p))
        if self.impostazioni.occhi_tutto_pc():
            for p in cartelle_utente():
                self._aggiungi_cartella(p)
        if not self.cartelle:
            self._aggiungi_cartella(os.path.join(_DIR, "sorvegliata"))

        self.regola = self.impostazioni.regola_ordine()
        self.soglia = self.impostazioni.soglia_accumulo()
        self.mani = Mani(radici=self.cartelle,
                         cartelle_protette=self.impostazioni.cartelle_protette())

        self.ultimo_accesso, self.numero_accessi = self.memoria.registra_accesso()
        self.cervello_online = None
        self._accensione_in_corso = False
        self.coda = []
        self.in_coda = set()
        self.in_attesa_conferma = False
        self.piano_corrente = None
        self.accumulo_segnalato = set()
        self.disco_segnalato = False

        self._costruisci_ui()

        self.viste = {f: self._scatta(f) for f in self.cartelle}
        self._dialogo("ARGO", self._benvenuto(), "argo")
        self._dialogo("ARGO", "Tengo d'occhio " + str(len(self.cartelle))
                      + " cartelle. Scrivimi pure qui sotto.", "sistema")

        self._heal_async()
        self._health_loop()
        self._batti_cuore()
        self.root.after(10000, self._scansione)

        root.protocol("WM_DELETE_WINDOW", self._chiudi)

    def _aggiungi_cartella(self, p):
        try:
            os.makedirs(p, exist_ok=True)
            if p not in self.cartelle:
                self.cartelle.append(p)
        except Exception:
            pass

    # ---------------- UI ----------------
    def _costruisci_ui(self):
        r = self.root
        r.title("ARGO")
        r.geometry("480x600+60+40")
        r.configure(bg=BG)
        r.minsize(420, 480)

        top = tk.Frame(r, bg=BG)
        top.pack(fill="x", pady=(12, 4))
        self.faccia = tk.Label(top, text="( ◕‿◕ )", font=("Consolas", 26),
                               fg=BLU, bg=BG)
        self.faccia.pack()
        tk.Label(top, text="ARGO", font=("Consolas", 11, "bold"),
                 fg=MUTE, bg=BG).pack()

        # area conversazione
        cont = tk.Frame(r, bg=BG)
        cont.pack(fill="both", expand=True, padx=12, pady=6)
        self.chat = tk.Text(cont, bg=BG2, fg=TX, relief="flat", wrap="word",
                            font=("Segoe UI", 10), padx=10, pady=10,
                            state="disabled", height=10)
        sb = tk.Scrollbar(cont, command=self.chat.yview)
        self.chat.configure(yscrollcommand=sb.set)
        self.chat.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.chat.tag_config("argo", foreground=BLU)
        self.chat.tag_config("tu", foreground=VERDE)
        self.chat.tag_config("sistema", foreground=MUTE, font=("Segoe UI", 9, "italic"))
        self.chat.tag_config("azione", foreground=VERDE)
        self.chat.tag_config("proposta", foreground=ARANCIO)
        self.chat.tag_config("errore", foreground=ROSSO)

        # bottoni conferma
        self.bottoni = tk.Frame(r, bg=BG)
        tk.Button(self.bottoni, text="Sì, sistema", width=12, bg="#238636", fg="white",
                  relief="flat", command=lambda: self._conferma(True)).pack(side="left", padx=6)
        tk.Button(self.bottoni, text="No, lascia", width=12, bg="#30363d", fg="white",
                  relief="flat", command=lambda: self._conferma(False)).pack(side="left", padx=6)

        # input chat
        bar = tk.Frame(r, bg=BG)
        bar.pack(fill="x", padx=12, pady=(2, 8))
        self.entry = tk.Entry(bar, bg=BG2, fg=TX, insertbackground=TX, relief="flat",
                              font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda e: self._chat())
        tk.Button(bar, text="Invia", bg="#1f6feb", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), command=self._chat).pack(side="left", padx=(8, 0))

        self.stato = tk.Label(r, text="Accendo il cervello…", font=("Segoe UI", 8),
                              fg=ARANCIO, bg=BG, anchor="w")
        self.stato.pack(fill="x", side="bottom")

    def _dialogo(self, mittente, testo, tag="argo"):
        self.chat.configure(state="normal")
        if mittente:
            self.chat.insert("end", f"{mittente}: ", (tag,))
        self.chat.insert("end", testo + "\n\n", (tag,))
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _faccia(self, f):
        self.faccia.config(text=f)

    def _mostra_bottoni(self, mostra):
        if mostra:
            self.bottoni.pack(pady=2, before=self.stato)
        else:
            self.bottoni.pack_forget()

    # ---------------- benvenuto ----------------
    def _benvenuto(self):
        base = saluto_orario()
        if self.numero_accessi <= 1 or not self.ultimo_accesso:
            return base + " È la prima volta che ci vediamo: comincio a ricordare da ora."
        quando = self.ultimo_accesso.replace("T", " alle ")
        return f"{base} Bentornato. Ultima volta: {quando}. Ho {self.memoria.conta()} ricordi."

    # ---------------- occhi ----------------
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
            try:
                if os.path.isfile(os.path.join(c, n)):
                    out.append(n)
            except Exception:
                pass
        return out

    # ---------------- cervello ----------------
    def _heal_async(self):
        if self._accensione_in_corso:
            return
        self._accensione_in_corso = True

        def lavoro():
            try:
                self.cervello.assicura_acceso(timeout=45)
            finally:
                self._accensione_in_corso = False
        threading.Thread(target=lavoro, daemon=True).start()

    def _health_loop(self):
        def check():
            vivo = self.cervello.vivo()
            self.root.after(0, lambda: self._aggiorna_cervello(vivo))
        threading.Thread(target=check, daemon=True).start()
        self.root.after(HEALTH_EVERY_SECONDS * 1000, self._health_loop)

    def _aggiorna_cervello(self, vivo):
        self.cervello_online = vivo
        ric = self.memoria.conta()
        g = self.grafo.statistiche()
        if vivo:
            self.stato.config(
                text=f"  Cervello connesso  •  Ricordi {ric}  •  Grafo {g['nodi']}n/{g['archi']}a  •  {len(self.cartelle)} cartelle",
                fg=VERDE)
        else:
            self.stato.config(text=f"  Cervello offline, lo accendo…  •  Ricordi {ric}", fg=ARANCIO)
            self._heal_async()

    # ---------------- chat ----------------
    def _chat(self):
        testo = self.entry.get().strip()
        if not testo:
            return
        self.entry.delete(0, "end")
        self._dialogo("Tu", testo, "tu")
        self._dialogo("ARGO", "…sto pensando", "sistema")
        self._faccia("( •_•)")

        def lavoro():
            contesto = ""
            try:
                simili = self.semantica.cerca(testo, k=3)
                if simili:
                    contesto = "\n\nPotrebbero essere rilevanti questi miei ricordi: " + \
                        "; ".join(s["testo"] for s in simili)
            except Exception:
                pass
            risp = self.cervello.pensa(testo + contesto)
            self.root.after(0, lambda: self._risposta_chat(risp))
        threading.Thread(target=lavoro, daemon=True).start()

    def _risposta_chat(self, risp):
        self._dialogo("ARGO", risp, "argo")
        self._faccia("( ◕‿◕ )")
        try:
            self.memoria.ricorda("chat", risp[:200])
        except Exception:
            pass

    # ---------------- loop di vita ----------------
    def _batti_cuore(self):
        for c in self.cartelle:
            adesso = self._scatta(c)
            nuovi = self._solo_file(c, adesso - self.viste.get(c, set()))
            for nome in sorted(nuovi):
                self.memoria.ricorda("file_aggiunto", nome)
                self._accoda(self.mani.proponi_archiviazione(os.path.join(c, nome), self.regola),
                             categoria_di(nome))
            self.viste[c] = adesso
        self._processa_coda()
        self.root.after(CHECK_EVERY_SECONDS * 1000, self._batti_cuore)

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
        try:
            for c in self.cartelle:
                for dup in self.mani.trova_duplicati(c):
                    if dup not in self.in_coda:
                        self._accoda(self.mani.proponi_sposta_duplicato(dup), "duplicati")
                n_file = len(self._solo_file(c, self._scatta(c)))
                if n_file > self.soglia and c not in self.accumulo_segnalato:
                    self.accumulo_segnalato.add(c)
                    self.memoria.ricorda("accumulo", f"{n_file} file in {os.path.basename(c)}")
                    self._dialogo("ARGO", f"Hai {n_file} file accumulati in «{os.path.basename(c)}».",
                                  "sistema")
            d = sistema.disco()
            if "errore" not in d and d.get("perc_usato", 0) >= 90 and not self.disco_segnalato:
                self.disco_segnalato = True
                self._dialogo("ARGO", "Attenzione: " + sistema.stato_sintetico()
                              + " Disco quasi pieno.", "errore")
            self._processa_coda()
        except Exception as e:
            print("[ARGO] scansione:", e)
        self.root.after(SCAN_EVERY_SECONDS * 1000, self._scansione)

    def _livello(self, piano):
        cat = piano.get("_categoria")
        pref = self.memoria.preferenza(cat) if cat else None
        return pref or self.impostazioni.autonomia(piano["azione"])

    def _processa_coda(self):
        if self.in_attesa_conferma or not self.coda:
            return
        piano = self.coda.pop(0)
        src = piano.get("sorgente")
        if src:
            self.in_coda.discard(src)
        if src and not os.path.exists(src):
            self.root.after(50, self._processa_coda)
            return
        livello = self._livello(piano)
        if livello == "osserva":
            self._dialogo("ARGO", "Noto: " + piano["descrizione"] + " (resto a guardare).", "sistema")
            self.memoria.ricorda("osservato", piano["descrizione"])
            self.root.after(1200, self._processa_coda)
        elif livello == "agisce":
            r = self.mani.esegui(piano)
            self._dopo_azione(piano, r)
            self.root.after(1200, self._processa_coda)
        else:
            self.in_attesa_conferma = True
            self.piano_corrente = piano
            self._dialogo("ARGO", piano["descrizione"] + " Procedo?", "proposta")
            self._faccia("( •_•)")
            self._mostra_bottoni(True)

    def _dopo_azione(self, piano, r):
        if r["ok"]:
            self._dialogo("ARGO", "Fatto. " + piano["descrizione"], "azione")
            self._registra_grafo(piano)
            self._registra_semantica(piano)
        else:
            self._dialogo("ARGO", "Non sono riuscito: " + r["messaggio"], "errore")
        self.memoria.ricorda("azione", piano["descrizione"], esito=r["messaggio"])

    def _registra_grafo(self, piano):
        try:
            src = piano.get("sorgente")
            if not src:
                return
            nome = os.path.basename(src)
            cat = piano.get("_categoria") or categoria_di(nome)
            self.grafo.collega("file", nome, "è_un", "categoria", cat)
            self.grafo.collega("file", nome, "sta_in", "cartella",
                               os.path.basename(os.path.dirname(piano.get("destinazione", src))))
        except Exception as e:
            print("[ARGO] grafo:", e)

    def _registra_semantica(self, piano):
        def lavoro():
            try:
                src = piano.get("destinazione") or piano.get("sorgente")
                nome = os.path.basename(src) if src else ""
                cat = piano.get("_categoria") or ""
                self.semantica.ricorda_testo(f"{nome} (categoria {cat})", origine=src or "")
            except Exception:
                pass
        threading.Thread(target=lavoro, daemon=True).start()

    def _conferma(self, si):
        piano = self.piano_corrente
        self._mostra_bottoni(False)
        if si:
            r = self.mani.esegui(piano)
            self._dopo_azione(piano, r)
            self.memoria.registra_scelta(piano.get("_categoria"), True)
        else:
            self._dialogo("ARGO", "Va bene, lo lascio dov'è.", "sistema")
            self.memoria.ricorda("azione_rifiutata", piano["descrizione"] if piano else "")
            if piano:
                self.memoria.registra_scelta(piano.get("_categoria"), False)
        self._faccia("( ◕‿◕ )")
        self.in_attesa_conferma = False
        self.piano_corrente = None
        self.root.after(600, self._processa_coda)

    def _chiudi(self):
        try:
            self.memoria.ricorda("sessione", "Argo si spegne")
            self.memoria.chiudi()
            self.grafo.chiudi()
            self.semantica.chiudi()
        finally:
            self.root.destroy()


if __name__ == "__main__":
    print("[ARGO] mi sveglio...")
    root = tk.Tk()
    Argo(root)
    root.mainloop()
