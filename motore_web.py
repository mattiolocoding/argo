"""
ARGO - motore_web.py  (UI moderna 2026, sicura, fondata sui dati reali)
Motore di ARGO + server web che serve l'interfaccia moderna e la apre come
APP DESKTOP (pywebview, oppure Edge/Chrome in modalità --app: niente barre).

Sicurezza: file/segreti sensibili non vengono letti né indicizzati; ogni azione
è registrata in un audit a catena di hash; chiave locale protetta (DPAPI).
La chat risponde SOLO dai dati reali di ARGO: vietato inventare.

AVVIO:  python motore_web.py   (oppure avvia_argo.bat)
"""

import os
import json
import time
import shutil
import threading
import subprocess
import webbrowser
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cervello import Cervello
from memoria import Memoria, Grafo, Semantica
from mani import Mani, categoria_di
from mani.mani import CARTELLE_DI_ARGO
from config import Impostazioni
import sistema
import sicurezza
from governo import Policy, Ruoli, Rollback, Metriche, RegistroAgenti
from governo.consolidamento import consolida, gia_fatto_oggi
from cognizione import (
    DiarioInterno,
    EsperimentiCognitivi,
    Obiettivi,
    TimelineCognitiva,
    WorldModel,
)

_DIR = os.path.dirname(os.path.abspath(__file__))
UI_FILE = os.path.join(_DIR, "ui", "index.html")

# Versione di ARGO (usata in identità/flotta e nei doc).
VERSIONE = "0.1.0"

# Host/porta configurabili da ambiente: così piu' istanze possono girare in
# parallelo su porte diverse (fondamenta della flotta orizzontale) senza
# toccare il codice. Default: locale, porta storica.
HOST = os.environ.get("ARGO_HOST", "127.0.0.1")
try:
    PORT = int(os.environ.get("ARGO_PORT", "8773"))
except (TypeError, ValueError):
    PORT = 8773

# Identità dell'istanza (per distinguerla nella flotta). Se l'id non e' dato,
# se ne deriva uno stabile da nome-macchina + porta.
def _id_istanza_default():
    try:
        import socket
        host = socket.gethostname() or "pc"
    except Exception:
        host = os.environ.get("COMPUTERNAME", "pc")
    return f"{host}-{PORT}"

ISTANZA_ID = os.environ.get("ARGO_ISTANZA_ID", "").strip() or _id_istanza_default()
ISTANZA_NOME = os.environ.get("ARGO_ISTANZA_NOME", "").strip() or "ARGO"

CHECK_EVERY = 3
SCAN_EVERY = 60
MAX_BODY_BYTES = 64 * 1024
MAX_CHAT_CHARS = 2000


def saluto_orario():
    o = time.localtime().tm_hour
    if 5 <= o < 12: return "Buongiorno, Davide."
    if 12 <= o < 18: return "Buon pomeriggio, Davide."
    if 18 <= o < 23: return "Buonasera, Davide."
    return "È tardi, Davide. Veglio io."


def cartelle_utente():
    home = os.path.expanduser("~")
    out = []
    for n in ["Desktop", "Downloads", "Documents", "Pictures", "Music", "Videos"]:
        p = os.path.join(home, n)
        if os.path.isdir(p):
            out.append(p)
    return out


class Motore:
    def __init__(self):
        self.avviato_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.memoria = Memoria()
        self.impostazioni = Impostazioni()
        self.cervello = Cervello()
        self.grafo = Grafo()
        self.semantica = Semantica()
        self.audit = sicurezza.Audit()
        self.chiave = sicurezza.Chiave()      # crea/carica chiave protetta
        # governo dell'azione (enterprise)
        self.policy = Policy()
        self.ruoli = Ruoli(self.impostazioni)
        self.rollback = Rollback()
        self.metriche_eng = Metriche(self.memoria, self.audit)
        self.agenti = RegistroAgenti()
        self.timeline = TimelineCognitiva()
        self.world = WorldModel()
        self.diario = DiarioInterno()
        self.obiettivi = Obiettivi()
        self.esperimenti = EsperimentiCognitivi()
        self.pensatore = None
        try:
            from pensatore import Pensatore
            self.pensatore = Pensatore(self.cervello, n_candidati=3)
        except Exception as e:
            print("[MOTORE] pensatore:", e)

        # moduli enterprise (costruiti dagli agenti) — caricati in modo sicuro
        self.sensi = self.mesh = self.connettori = None
        self.lacune = self.skills = self.skill_writer = self._sonno = None
        try:
            import sensi as _sensi
            self.sensi = _sensi
        except Exception as e:
            print("[MOTORE] sensi:", e)
        try:
            from modelli import ModelMesh
            self.mesh = ModelMesh()
        except Exception as e:
            print("[MOTORE] modelli:", e)
        try:
            from connettori import RegistroConnettori
            self.connettori = RegistroConnettori()
        except Exception as e:
            print("[MOTORE] connettori:", e)
        try:
            from governo.lacune import Lacune
            from governo.skill_registry import SkillRegistry
            from governo.skill_writer import SkillWriter
            from governo import sonno as _sonno
            self.lacune = Lacune()
            self.skills = SkillRegistry()
            self.skill_writer = SkillWriter(self.cervello)
            self._sonno = _sonno
        except Exception as e:
            print("[MOTORE] skill/sonno:", e)

        self.workflow = None
        try:
            from workflow import (
                MotoreWorkflow,
                crea_workflow_documento_in_arrivo,
                crea_workflow_report_giornaliero,
            )
            self.workflow = MotoreWorkflow()
            self.workflow.registra(crea_workflow_documento_in_arrivo())
            self.workflow.registra(crea_workflow_report_giornaliero())
        except Exception as e:
            print("[MOTORE] workflow:", e)

        # permessi (cosa ARGO può vedere) — caricati in modo sicuro
        self.permessi = None
        try:
            from config.permessi import Permessi
            self.permessi = Permessi()
        except Exception as e:
            print("[MOTORE] permessi:", e)

        self._costruisci_cartelle()

        self.regola = self.impostazioni.regola_ordine()
        self.soglia = self.impostazioni.soglia_accumulo()
        self.mani = Mani(radici=self.cartelle,
                         cartelle_protette=self.impostazioni.cartelle_protette())

        self.lock = threading.Lock()
        self.eventi = []
        self._eid = 0
        self.coda = []
        self.in_coda = set()
        self.proposta = None
        self.piano_corrente = None
        self.cervello_online = False
        self.accumulo_segnalato = set()
        self.disco_segnalato = False
        self._ultima_finestra = None
        self._ultima_rete = None
        self._ultimo_appunti = None
        self._ultimo_battito = 0
        self._ultima_proattiva = 0
        self._ultimo_scan = time.time()
        self.attivita = {
            "stato": "avvio",
            "dettaglio": "Sto avviando sensi, memoria e cervello locale.",
            "ultimo_battito": time.time(),
            "prossima_scansione_s": SCAN_EVERY,
            "coda": 0,
            "finestra": "",
        }
        self.viste = {f: self._scatta(f) for f in self.cartelle}
        self.running = True

        ultimo, n_acc = self.memoria.registra_accesso()
        self.audit.registra("avvio", f"accesso #{n_acc}")
        self.timeline.registra("avvio", f"accesso #{n_acc}", origine="motore")
        msg = saluto_orario()
        if n_acc > 1:
            fatti = self.memoria.riepilogo_oggi()
            if fatti > 0:
                msg += f" Bentornato. Oggi ho già messo in ordine {fatti} file per te."
            else:
                msg += " Bentornato. Sto tenendo tutto sott'occhio."
        else:
            msg += " Piacere, sono ARGO. Da ora tengo in ordine il tuo PC e imparo come lavori."
        self._evento("ARGO", msg, "argo")
        self._evento("ARGO", f"Tengo d'occhio {len(self.cartelle)} cartelle. "
                     "I file sensibili (password, chiavi…) non li tocco. Scrivimi pure.", "sistema")

        threading.Thread(target=self.cervello.assicura_acceso, daemon=True).start()
        threading.Thread(target=self._loop, daemon=True).start()

    def _add_cartella(self, p):
        try:
            os.makedirs(p, exist_ok=True)
            if p not in self.cartelle:
                self.cartelle.append(p)
            return True
        except Exception:
            return False

    def _costruisci_cartelle(self):
        """Decide quali cartelle sorvegliare, rispettando i PERMESSI."""
        self.cartelle = []
        self.cartelle_gestite = []   # solo queste: duplicati + accumuli
        # cartelle esplicite (sempre, es. 'sorvegliata')
        for c in self.impostazioni.cartelle_sorvegliate():
            p = c if os.path.isabs(c) else os.path.join(_DIR, c)
            p = os.path.abspath(p)
            if self._add_cartella(p):
                self.cartelle_gestite.append(p)
        # accesso esteso secondo i permessi (default: vecchia logica occhi_tutto_pc)
        modo = "tutto" if self.impostazioni.occhi_tutto_pc() else "selezione"
        extra = []
        if self.permessi is not None:
            modo = self.permessi.modo
            extra = list(getattr(self.permessi, "cartelle", []) or [])
        if modo == "tutto":
            for p in cartelle_utente():          # solo file NUOVI, niente duplicati/accumuli
                self._add_cartella(p)
        elif modo == "selezione":
            for p in extra:
                if os.path.isdir(p):
                    self._add_cartella(os.path.abspath(p))
        # modo 'niente' -> resta solo la cartella esplicita
        if not self.cartelle:
            p = os.path.join(_DIR, "sorvegliata")
            self._add_cartella(p)
            self.cartelle_gestite.append(p)

    # ---- eventi ----
    def _evento(self, mittente, testo, tag):
        testo_pulito = sicurezza.redigi(testo)
        with self.lock:
            self._eid += 1
            self.eventi.append({"id": self._eid, "mittente": mittente,
                                "testo": testo_pulito, "tag": tag})
            self.eventi = self.eventi[-200:]
        try:
            self.timeline.registra(tag or "evento", testo_pulito, origine=mittente)
        except Exception:
            pass

    def _set_attivita(self, stato, dettaglio=None):
        self.attivita.update({
            "stato": stato,
            "dettaglio": sicurezza.redigi(dettaglio or stato),
            "ultimo_battito": time.time(),
            "prossima_scansione_s": max(0, int(SCAN_EVERY - (time.time() - self._ultimo_scan))),
            "coda": len(self.coda),
            "finestra": self._ultima_finestra or "",
        })

    def eventi_da(self, since):
        with self.lock:
            return [e for e in self.eventi if e["id"] > since]

    # ---- occhi ----
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

    # ---- loop ----
    def _loop(self):
        cont = 0
        while self.running:
            try:
                self.cervello_online = self.cervello.vivo()
                self._set_attivita("osservo", f"Sto osservando {len(self.cartelle)} cartelle autorizzate.")
                self._percepisci()
                cont += CHECK_EVERY
                if cont >= SCAN_EVERY:
                    cont = 0
                    self._ultimo_scan = time.time()
                    self._scansione()
                self._processa()
                self._battito()
            except Exception as e:
                print("[MOTORE] loop:", e)
            time.sleep(CHECK_EVERY)

    def _battito(self):
        """Segnale leggero di vita: aggiorna stato e ogni tanto produce insight, non spam."""
        now = time.time()
        self._set_attivita(
            "vigile",
            f"Coda: {len(self.coda)} · proposta: {'sì' if self.proposta else 'no'} · cervello: {'online' if self.cervello_online else 'offline'}."
        )
        if now - self._ultimo_battito < 180:
            return
        self._ultimo_battito = now
        if self.proposta or self.coda:
            return
        try:
            pattern = self.timeline.pattern_oggi()
            eventi = int(pattern.get("eventi", 0) or 0)
            lacune = self.timeline.lacune_oggi()
            if eventi and now - self._ultima_proattiva > 600:
                self._ultima_proattiva = now
                breve = f"Sto seguendo la giornata: {eventi} eventi cognitivi registrati."
                if lacune:
                    breve += " Ho anche lacune da consolidare nel sonno."
                self._evento("ARGO", breve, "sistema")
        except Exception:
            pass

    def _percepisci(self):
        for c in self.cartelle:
            adesso = self._scatta(c)
            nuovi = self._solo_file(c, adesso - self.viste.get(c, set()))
            for nome in sorted(nuovi):
                percorso = os.path.join(c, nome)
                self._set_attivita("file nuovo", f"Ho visto «{nome}» in {os.path.basename(c)}.")
                # SICUREZZA: i file sensibili non si toccano né si memorizzano
                if sicurezza.file_sensibile(percorso):
                    self.audit.registra("sensibile_ignorato", nome)
                    self._evento("ARGO", f"Ho visto un file sensibile («{nome}»): "
                                 "non lo tocco e non lo memorizzo.", "sistema")
                    continue
                self.memoria.ricorda("file_aggiunto", nome)
                try:
                    self.timeline.registra_file(percorso, tipo="file_visto",
                                                categoria=categoria_di(nome))
                except Exception:
                    pass
                self._accoda(self.mani.proponi_archiviazione(percorso, self.regola),
                             categoria_di(nome))
            self.viste[c] = adesso

    def _accoda(self, piano, categoria):
        if not piano:
            return
        src = piano.get("sorgente")
        if src and (src in self.in_coda or sicurezza.file_sensibile(src)):
            return
        piano["_categoria"] = categoria
        if src:
            self.in_coda.add(src)
        self.coda.append(piano)

    def _scansione(self):
        self._set_attivita("scansione", "Controllo duplicati, accumuli, sensi PC e consolidamento.")
        self._osserva_pc()
        for c in self.cartelle_gestite:   # duplicati/accumuli solo nelle cartelle dedicate
            for dup in self.mani.trova_duplicati(c):
                if dup not in self.in_coda and not sicurezza.file_sensibile(dup):
                    self._accoda(self.mani.proponi_sposta_duplicato(dup), "duplicati")
            n_file = len(self._solo_file(c, self._scatta(c)))
            if n_file > self.soglia and c not in self.accumulo_segnalato:
                self.accumulo_segnalato.add(c)
                self._evento("ARGO", f"Hai {n_file} file accumulati in «{os.path.basename(c)}».", "sistema")
        d = sistema.disco()
        if "errore" not in d and d.get("perc_usato", 0) >= 90 and not self.disco_segnalato:
            self.disco_segnalato = True
            self._evento("ARGO", "Attenzione: " + sistema.stato_sintetico() + " Disco quasi pieno.", "errore")
        # consolidamento serale della memoria (il "sonno"): una volta al giorno
        if time.localtime().tm_hour >= 20 and not gia_fatto_oggi(self.memoria):
            try:
                self.timeline.consolida_oggi()
            except Exception:
                pass
            s = consolida(self.memoria, self.grafo, self.cervello)
            if s:
                self._evento("ARGO", "💤 " + s, "sistema")

    def _osserva_pc(self):
        """Registra segnali PC autorizzati, senza contenuti sensibili."""
        if not self.sensi:
            return
        try:
            snap = self.sensi.istantanea()
            appunti = snap.get("appunti") or {}
            firma_appunti = (
                bool(appunti.get("ha_testo")),
                bool(appunti.get("sospetto_sensibile")),
            )
            cambiato = (
                snap.get("finestra_attiva") != self._ultima_finestra or
                bool(snap.get("rete_attiva")) != self._ultima_rete or
                firma_appunti != self._ultimo_appunti
            )
            if not cambiato:
                return
            self._ultima_finestra = snap.get("finestra_attiva")
            self._ultima_rete = bool(snap.get("rete_attiva"))
            self._ultimo_appunti = firma_appunti
            self.timeline.registra_sensi(snap)
            self._set_attivita("sensi", f"Finestra attiva: {self._ultima_finestra or 'nessuna'}.")
        except Exception as e:
            print("[MOTORE] osserva_pc:", e)

    def _livello(self, piano):
        cat = piano.get("_categoria")
        pref = self.memoria.preferenza(cat) if cat else None
        return pref or self.impostazioni.autonomia(piano["azione"])

    def _processa(self):
        if self.proposta or not self.coda:
            return
        piano = self.coda.pop(0)
        src = piano.get("sorgente")
        if src:
            self.in_coda.discard(src)
        if src and not os.path.exists(src):
            return
        # POLICY ENGINE a runtime (governo dell'azione)
        decisione = self.policy.valuta(piano["azione"], src or "", piano.get("_categoria", ""))
        if decisione["esito"] == "blocca":
            self._evento("ARGO", f"🛡 Policy: non procedo. {decisione['motivo']}", "sistema")
            self.audit.registra("policy_blocca",
                                piano.get("descrizione", "") + " | " + decisione.get("regola", ""))
            return
        livello = self._livello(piano)
        if decisione["esito"] == "escala":
            livello = "chiede"      # la policy impone la conferma umana
        if livello == "osserva":
            self._evento("ARGO", "Noto: " + piano["descrizione"] + " (resto a guardare).", "sistema")
            self.memoria.ricorda("osservato", piano["descrizione"])
        elif livello == "agisce":
            r = self.mani.esegui(piano)
            self._dopo_azione(piano, r)
        else:
            self.piano_corrente = piano
            self.proposta = piano["descrizione"] + " Procedo?"

    def _dopo_azione(self, piano, r):
        if r["ok"]:
            self._evento("ARGO", "Fatto. " + piano["descrizione"], "argo")
            self.audit.registra("azione", piano["descrizione"])
            try:
                self.timeline.registra(
                    "azione",
                    piano["descrizione"],
                    origine=piano.get("sorgente", ""),
                    entita=os.path.basename(piano.get("sorgente", "")),
                    meta={
                        "azione": piano.get("azione"),
                        "sorgente": piano.get("sorgente"),
                        "destinazione": piano.get("destinazione"),
                        "categoria": piano.get("_categoria"),
                    },
                )
            except Exception:
                pass
            self.rollback.registra(piano)        # azione reversibile (Annulla)
            self._grafo(piano)
            self._sem(piano)
        else:
            self._evento("ARGO", "Non sono riuscito: " + r["messaggio"], "errore")
        self.memoria.ricorda("azione", piano["descrizione"], esito=r["messaggio"])

    def _grafo(self, piano):
        try:
            src = piano.get("sorgente")
            if not src: return
            nome = os.path.basename(src)
            cat = piano.get("_categoria") or categoria_di(nome)
            self.grafo.collega("file", nome, "è_un", "categoria", cat)
            dest = piano.get("destinazione", src)
            self.grafo.collega("file", nome, "sta_in", "cartella", os.path.basename(os.path.dirname(dest)))
        except Exception as e:
            print("[MOTORE] grafo:", e)

    def _sem(self, piano):
        def lav():
            try:
                src = piano.get("destinazione") or piano.get("sorgente")
                if not src or sicurezza.file_sensibile(src):
                    return
                nome = os.path.basename(src)
                cat = piano.get("_categoria") or ""
                self.semantica.ricorda_testo(f"{nome} (categoria {cat})", origine=src)
            except Exception:
                pass
        threading.Thread(target=lav, daemon=True).start()

    # ---- API ----
    def conferma(self, si):
        piano = self.piano_corrente
        self.proposta = None
        self.piano_corrente = None
        if not piano:
            return {"ok": False, "messaggio": "nessuna proposta"}
        if si:
            r = self.mani.esegui(piano)
            self._dopo_azione(piano, r)
            self.memoria.registra_scelta(piano.get("_categoria"), True)
            self.audit.registra("conferma_si", piano["descrizione"])
            return r
        else:
            self._evento("ARGO", "Va bene, lo lascio dov'è.", "sistema")
            self.memoria.ricorda("azione_rifiutata", piano["descrizione"])
            try:
                self.timeline.registra("rifiuto", piano["descrizione"],
                                       origine=piano.get("sorgente", ""),
                                       meta={"categoria": piano.get("_categoria")})
            except Exception:
                pass
            self.memoria.registra_scelta(piano.get("_categoria"), False)
            self.audit.registra("conferma_no", piano["descrizione"])
            return {"ok": True, "messaggio": "lasciato"}

    def imposta_modo(self, modo):
        if modo not in ("osserva", "chiede", "agisce"):
            return {"ok": False}
        for az in ("archivia", "sposta", "rinomina"):
            self.impostazioni.imposta_autonomia(az, modo)
        self.audit.registra("modo_autonomia", modo)
        self._evento("ARGO", f"Modalità impostata su «{modo}».", "sistema")
        return {"ok": True, "modo": modo}

    def stato(self):
        try:
            cognizione = self.timeline.pattern_oggi()
        except Exception:
            cognizione = {"eventi": 0}
        return {
            "istanza": ISTANZA_ID,
            "nome_istanza": ISTANZA_NOME,
            "versione": VERSIONE,
            "cervello_online": self.cervello_online,
            "ricordi": self.memoria.conta(),
            "cartelle": len(self.cartelle),
            "grafo": self.grafo.statistiche(),
            "proposta": self.proposta,
            "modo": self.impostazioni.autonomia("archivia"),
            "attivita": dict(self.attivita),
            "cognizione": {
                "eventi_oggi": cognizione.get("eventi", 0),
                "progetti": list((cognizione.get("progetti") or {}).keys())[:5],
            },
        }

    def identita(self):
        """Carta d'identità dell'istanza, per distinguerla nella flotta."""
        try:
            azioni = self.metriche_eng.calcola().get("azioni_eseguite", 0)
        except Exception:
            azioni = 0
        return {
            "id": ISTANZA_ID,
            "nome": ISTANZA_NOME,
            "versione": VERSIONE,
            "host": HOST,
            "porta": PORT,
            "avviato": getattr(self, "avviato_iso", None),
            "cervello_online": self.cervello_online,
            "ricordi": self.memoria.conta(),
            "azioni": azioni,
            "modo": self.impostazioni.autonomia("archivia"),
        }

    def flotta(self):
        """Panoramica aggregata della flotta (questa istanza + eventuali peer)."""
        try:
            from fleet import Flotta
            f = Flotta()
            # ARGO_BASE_URL: indirizzo con cui questa istanza e' raggiungibile dai
            # peer (es. nome di servizio Docker). Evita il self-base "0.0.0.0" e i
            # doppioni quando l'istanza e' gia' elencata in ARGO_FLOTTA.
            base = os.environ.get("ARGO_BASE_URL", "").strip() or f"http://{HOST}:{PORT}"
            f.aggiungi(base)  # includi sempre se stessa
            return f.panoramica()
        except Exception as e:
            return {"totale": 0, "online": 0, "istanze": [], "errore": str(e)[:140]}

    def _contesto_reale(self):
        """Costruisce i DATI REALI per la chat: solo cose vere dalla memoria."""
        oggi = time.strftime("%Y-%m-%d")
        righe = []
        for r in self.memoria.ricordi_recenti(60):
            if not str(r.get("quando", "")).startswith(oggi):
                continue
            if r["tipo"] in ("azione", "azione_confermata", "osservato",
                             "file_aggiunto", "accumulo"):
                d = r.get("dettaglio", "")
                righe.append(f"- {r['tipo']}: {d}")
        if not righe:
            righe.append("- (oggi non ho ancora registrato azioni o file)")
        cartelle = ", ".join(os.path.basename(c) for c in self.cartelle)
        try:
            timeline = self.timeline.contesto_chat()
        except Exception:
            timeline = "Timeline cognitiva non disponibile."
        try:
            world = self.world.contesto_chat()
        except Exception:
            world = "World model non disponibile."
        try:
            diario = self.diario.contesto_chat()
        except Exception:
            diario = ""
        try:
            obiettivi = self.obiettivi.contesto_chat()
        except Exception:
            obiettivi = ""
        return ("Cartelle sorvegliate: " + cartelle + ".\n"
                "Attività reali registrate oggi:\n" + "\n".join(righe[:25]) +
                "\n\n" + timeline + "\n\n" + world +
                ("\n\nDiario interno recente:\n" + diario if diario else "") +
                ("\n\nObiettivi permanenti:\n" + obiettivi if obiettivi else ""))

    def chat(self, testo):
        testo = sicurezza.redigi(str(testo or "")[:MAX_CHAT_CHARS])
        self.audit.registra("chat", testo)
        try:
            self.timeline.registra("chat", testo, origine="utente")
        except Exception:
            pass
        testo_lower = testo.lower().strip()
        for prefisso in ("cerca online ", "ricerca online ", "cerca sul web ", "esplora online "):
            if testo_lower.startswith(prefisso):
                query = testo[len(prefisso):].strip()
                r = self.ricerca_online(query)
                if r.get("errore"):
                    return {"risposta": r["errore"], "ricerca": r}
                righe = []
                for i, item in enumerate(r.get("risultati", [])[:5], 1):
                    titolo = item.get("titolo", "")
                    url = item.get("url", "")
                    snippet = item.get("snippet", "")
                    righe.append(f"{i}. {titolo} - {snippet}\n{url}".strip())
                risposta = "Ho cercato online adesso:\n" + ("\n\n".join(righe) if righe else "nessun risultato utile trovato.")
                return {"risposta": sicurezza.redigi(risposta), "ricerca": r}
        contesto = self._contesto_reale()
        prompt = (
            f"Davide ti chiede: «{testo}».\n\n"
            f"QUESTI SONO I TUOI DATI REALI (non aggiungere NULLA che non sia qui):\n"
            f"{contesto}\n\n"
            "Rispondi in 1-3 frasi usando SOLO questi dati. "
            "Se la risposta non è nei dati, dì che non hai quell'informazione. "
            "Non inventare file, eventi o storie."
        )
        risp = ""
        if self.pensatore:
            try:
                compl = self.pensatore.valuta_complessita(testo)
                if compl != "bassa":
                    res = self.pensatore.delibera(testo, contesto=contesto)
                    risp = res.get("risposta") or ""
                    try:
                        self.timeline.registra(
                            "pensiero",
                            f"chat deliberata: {compl}, candidati={res.get('candidati')}",
                            origine="pensatore",
                            progetto="Deliberazione",
                            meta={k: v for k, v in res.items() if k != "risposta"},
                        )
                    except Exception:
                        pass
                    try:
                        self.diario.registra(
                            "deliberazione",
                            "Chat deliberata",
                            testo,
                            evidenza={k: v for k, v in res.items() if k != "risposta"},
                            esito="risposta_generata",
                            importanza="media",
                        )
                        self.esperimenti.registra(
                            "chat_deliberazione",
                            "complessita",
                            "risposta_diretta",
                            "deliberatore",
                            "",
                            risp[:500],
                            "deliberatore",
                            testo[:500],
                        )
                    except Exception:
                        pass
            except Exception as e:
                print("[MOTORE] pensatore chat:", e)
                risp = ""
        if not risp and self.mesh:
            res = self.mesh.pensa(prompt)
            # mesh.pensa() ritorna un dict {risposta, livello, modello}: estrai il testo.
            risp = res.get("risposta", "") if isinstance(res, dict) else str(res)
            if not risp or str(risp).startswith("[ModelMesh"):
                risp = self.cervello.pensa(prompt)
        elif not risp:
            risp = self.cervello.pensa(prompt)
        if not isinstance(risp, str):
            risp = str(risp)
        risp = sicurezza.redigi(risp)
        try:
            self.memoria.ricorda("chat", risp[:200])
            self.timeline.registra("risposta_chat", risp[:500], origine="ARGO")
        except Exception:
            pass
        return {"risposta": risp}

    # ---- governo: metriche, dashboard, annulla, agenti, consolida ----
    def metriche(self):
        return self.metriche_eng.calcola()

    def dashboard(self):
        return {
            "stato": self.stato(),
            "metriche": self.metriche_eng.calcola(),
            "audit": self.audit.report(),
            "agenti": self.agenti.nomi(),
            "rollback": self.rollback.lista(8),
            "ruolo": self.ruoli.ruolo,
            "permessi": self.ruoli.permessi(),
            "policy_regole": len(self.policy.regole()),
            "skills": self.skills_lista() if self.skills else {"skills": []},
            "workflow": self.workflow_stato(),
            "cognizione": {
                "pattern": self.timeline.pattern_oggi(),
                "consolidamento": self.timeline.ultimo_consolidamento(),
                "lacune": self.timeline.lacune_oggi(),
                "pensiero": self.world.ultimo(),
                "proposte": self.world.proposte("proposta", 8),
                "diario": self.diario.recenti(8),
                "obiettivi": self.obiettivi.lista(12),
                "esperimenti": self.esperimenti.recenti(8),
            },
        }

    def annulla(self):
        if not self.ruoli.puo("annullare"):
            return {"ok": False, "messaggio": f"permesso negato (ruolo {self.ruoli.ruolo})"}
        r = self.rollback.annulla_ultima(self.mani)
        self.audit.registra("annulla", r.get("messaggio", ""))
        self._evento("ARGO", ("Annullato. " if r.get("ok") else "Annulla non riuscito: ")
                     + r.get("messaggio", ""), "sistema")
        return r

    def esegui_agente(self, nome):
        if nome not in self.agenti.nomi():     # sicurezza: solo agenti registrati
            return {"report": "Agente non riconosciuto."}
        rep = self.agenti.esegui(nome, self)
        self.audit.registra("agente", nome)
        self._evento(nome, rep, "argo")
        return {"report": rep}

    def permessi_stato(self):
        if not self.permessi:
            return {"onboarding_fatto": True, "modo": "tutto", "cartelle": []}
        try:
            d = self.permessi.come_dict()
            d.setdefault("onboarding_fatto", getattr(self.permessi, "onboarding_fatto", True))
            return d
        except Exception as e:
            return {"errore": str(e)}

    def imposta_permessi(self, modo, cartelle):
        if not self.permessi:
            return {"ok": False, "messaggio": "permessi non disponibili"}
        try:
            self.permessi.imposta(modo, cartelle or [])
            try:
                self.permessi.onboarding_fatto = True
                self.permessi.salva()
            except Exception:
                pass
            self._costruisci_cartelle()
            self.mani = Mani(radici=self.cartelle,
                             cartelle_protette=self.impostazioni.cartelle_protette())
            self.viste = {f: self._scatta(f) for f in self.cartelle}
            self.audit.registra("permessi", f"{modo} ({len(cartelle or [])} cartelle)")
            self._evento("ARGO", f"Permessi aggiornati: «{modo}». Ora vedo {len(self.cartelle)} cartelle.", "sistema")
            return {"ok": True, "cartelle": len(self.cartelle)}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def consolida_ora(self):
        cognitivo = None
        try:
            cognitivo = self.timeline.consolida_oggi()
        except Exception:
            pass
        s = consolida(self.memoria, self.grafo, self.cervello, forza=True)
        pensiero = None
        try:
            pensiero = self.world.analizza(self.timeline, self.memoria, self.audit, self.grafo)
            self.obiettivi.valuta_da_world(pensiero)
        except Exception:
            pass
        riflessione = None
        try:
            riflessione = self.diario.rifletti(self.timeline, self.world, self.memoria, self.audit)
        except Exception:
            pass
        parti = [p for p in [s, (cognitivo or {}).get("sintesi")] if p]
        if pensiero:
            parti.append(pensiero.get("sintesi", ""))
        if riflessione:
            parti.append(f"Diario interno aggiornato: {riflessione.get('create', 0)} riflessioni.")
        finale = "\n".join(parti)
        if finale:
            self._evento("ARGO", "💤 " + finale, "sistema")
        return {"riassunto": finale, "cognizione": cognitivo, "pensiero": pensiero, "riflessione": riflessione}

    # ---- moduli enterprise ----
    def sensi_ora(self):
        if not self.sensi:
            return {"errore": "sensi non disponibili"}
        try:
            return self.sensi.istantanea()
        except Exception as e:
            return {"errore": str(e)}

    def modelli_stato(self):
        if not self.mesh:
            return {"errore": "model mesh non disponibile"}
        try:
            return self.mesh.stato()
        except Exception as e:
            return {"errore": str(e)}

    def connettori_info(self):
        if not self.connettori:
            return {"errore": "connettori non disponibili"}
        try:
            return self.connettori.info()
        except Exception as e:
            return {"errore": str(e)}

    def esegui_sonno(self):
        if not self._sonno:
            return {"errore": "modulo sonno non disponibile"}
        try:
            rep = self._sonno.sonno(self.memoria, self.lacune, self.skills,
                                    self.skill_writer, self.cervello)
            try:
                cog = self.timeline.consolida_oggi()
                rep = str(rep) + "\n\n[Cognizione]\n" + cog.get("sintesi", "")
                for lacuna in cog.get("lacune", []):
                    if self.lacune:
                        self.lacune.registra("cognizione", lacuna)
                pensiero = self.world.analizza(self.timeline, self.memoria, self.audit, self.grafo)
                self.obiettivi.valuta_da_world(pensiero)
                rep = str(rep) + "\n\n[Pensiero analitico]\n" + pensiero.get("sintesi", "")
                for lacuna in pensiero.get("lacune", []):
                    if self.lacune:
                        self.lacune.registra("world_model", lacuna.get("titolo", str(lacuna)))
                rif = self.diario.rifletti(self.timeline, self.world, self.memoria, self.audit)
                rep = str(rep) + f"\n\n[Diario interno]\nRiflessioni registrate: {rif.get('create', 0)}"
            except Exception:
                pass
            self.audit.registra("sonno", "ciclo eseguito")
            self._evento("ARGO", "💤 Sonno: " + str(rep), "sistema")
            return {"report": rep}
        except Exception as e:
            return {"errore": str(e)}

    def skills_lista(self):
        if not self.skills:
            return {"skills": []}
        try:
            bonifica = self.skills.bonifica_non_valide()
            return {"skills": self.skills.tutte()}
        except Exception as e:
            return {"errore": str(e)}

    def skills_bonifica(self):
        if not self.skills:
            return {"ok": False, "messaggio": "skill non disponibili"}
        try:
            r = self.skills.bonifica_non_valide()
            self.audit.registra("skill_bonifica", f"{r.get('scartate', 0)} scartate")
            return r
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def workflow_stato(self):
        if not self.workflow:
            return {"disponibile": False, "workflow": [], "istanze": []}
        try:
            return {
                "disponibile": True,
                "workflow": sorted(list(getattr(self.workflow, "_catalogo", {}).keys())),
                "istanze": self.workflow.tutte_istanze(),
            }
        except Exception as e:
            return {"disponibile": False, "errore": str(e)}

    def workflow_avvia(self, nome, parametri=None):
        if not self.workflow:
            return {"ok": False, "messaggio": "workflow non disponibile"}
        if not self.ruoli.puo("confermare"):
            return {"ok": False, "messaggio": "permesso negato"}
        try:
            eid = self.workflow.avvia(nome, parametri or {})
            stato = self.workflow.stato(eid)
            self.audit.registra("workflow_avvia", f"{nome} -> {eid}")
            try:
                self.timeline.registra("workflow", f"{nome} avviato: {eid}", origine="workflow", meta=stato)
            except Exception:
                pass
            return {"ok": True, "id": eid, "stato": stato, "passi": self.workflow.passi(eid)}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def workflow_approva(self, id_esecuzione):
        if not self.workflow:
            return {"ok": False, "messaggio": "workflow non disponibile"}
        if not self.ruoli.puo("confermare"):
            return {"ok": False, "messaggio": "permesso negato"}
        try:
            stato = self.workflow.approva(str(id_esecuzione))
            self.audit.registra("workflow_approva", str(id_esecuzione))
            return {"ok": True, "stato": stato, "passi": self.workflow.passi(str(id_esecuzione))}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def timeline_stato(self):
        try:
            return {
                "eventi": self.timeline.eventi_oggi(80),
                "pattern": self.timeline.pattern_oggi(),
                "consolidamento": self.timeline.ultimo_consolidamento(),
                "lacune": self.timeline.lacune_oggi(),
            }
        except Exception as e:
            return {"errore": str(e)}

    def pensiero_analitico(self):
        try:
            a = self.world.analizza(self.timeline, self.memoria, self.audit, self.grafo)
            self.obiettivi.valuta_da_world(a)
            self.diario.registra(
                "analisi",
                "Pensiero analitico",
                a.get("sintesi", "analisi eseguita"),
                evidenza={
                    "ipotesi": a.get("ipotesi", [])[:6],
                    "lacune": a.get("lacune", [])[:6],
                    "piani": a.get("piani", [])[:6],
                    "confidenza": a.get("confidenza"),
                },
                esito="registrato",
                importanza="media",
            )
            self.audit.registra("pensiero", a.get("sintesi", "analisi eseguita"))
            self._evento("ARGO", "Pensiero analitico: " + a.get("sintesi", ""), "sistema")
            return a
        except Exception as e:
            return {"errore": str(e)}

    def diario_stato(self):
        try:
            return {"riflessioni": self.diario.recenti(40), "statistiche": self.diario.statistiche()}
        except Exception as e:
            return {"errore": str(e)}

    def obiettivi_stato(self):
        try:
            return {"obiettivi": self.obiettivi.lista(50)}
        except Exception as e:
            return {"errore": str(e)}

    def esperimenti_stato(self):
        try:
            return {"esperimenti": self.esperimenti.recenti(40), "statistiche": self.esperimenti.statistiche()}
        except Exception as e:
            return {"errore": str(e)}

    def rifletti_ora(self):
        try:
            pensiero = self.world.analizza(self.timeline, self.memoria, self.audit, self.grafo)
            ob = self.obiettivi.valuta_da_world(pensiero)
            rif = self.diario.rifletti(self.timeline, self.world, self.memoria, self.audit)
            self.audit.registra("riflessione", f"{rif.get('create', 0)} riflessioni")
            self._evento("ARGO", f"Riflessione completata: {rif.get('create', 0)} note interne.", "sistema")
            return {"ok": True, "pensiero": pensiero, "diario": rif, "obiettivi": ob}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def world_stato(self):
        try:
            return {
                "ultimo": self.world.ultimo(),
                "contesto": self.world.contesto_chat(),
                "proposte": self.world.proposte(None, 20),
            }
        except Exception as e:
            return {"errore": str(e)}

    def proposte_stato(self):
        try:
            return {"proposte": self.world.proposte(None, 30)}
        except Exception as e:
            return {"errore": str(e)}

    def proposta_stato(self, id_proposta, stato):
        if not self.ruoli.puo("configurare"):
            return {"ok": False, "messaggio": "permesso negato"}
        try:
            r = self.world.cambia_stato_proposta(int(id_proposta), stato)
            self.audit.registra("proposta_" + str(stato), str(id_proposta))
            return r
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def ricerca_online(self, query, max_risultati=5):
        if not self.connettori:
            return {"errore": "connettori non disponibili"}
        query = sicurezza.redigi(str(query or "")[:180]).strip()
        if not query:
            return {"errore": "query mancante"}
        if sicurezza.testo_contiene_segreti(query):
            return {"errore": "query bloccata: contiene dati sensibili o segreti"}
        try:
            r = self.connettori.leggi("ricerca_web", {
                "query": query,
                "max_risultati": max_risultati,
            })
            if isinstance(r, dict) and "errore" not in r:
                self.audit.registra("ricerca_web", query)
                self.timeline.registra(
                    "ricerca_web",
                    f"{query} -> {len(r.get('risultati', []))} risultati",
                    origine="web",
                    progetto="Ricerca",
                    meta={"query": query, "risultati": r.get("risultati", [])[:5]},
                )
            return r
        except Exception as e:
            return {"errore": str(e)}

    def skill_approva(self, id_skill):
        if not self.skills or not self.ruoli.puo("configurare"):
            return {"ok": False, "messaggio": "non consentito"}
        try:
            self.skills.approva(id_skill)
            self.audit.registra("skill_approva", str(id_skill))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def skill_scarta(self, id_skill):
        if not self.skills or not self.ruoli.puo("configurare"):
            return {"ok": False, "messaggio": "non consentito"}
        try:
            ok = self.skills.scarta(int(id_skill))
            self.audit.registra("skill_scarta", str(id_skill))
            return {"ok": bool(ok)}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def skill_attiva(self, id_skill):
        if not self.skills or not self.ruoli.puo("configurare"):
            return {"ok": False, "messaggio": "non consentito"}
        try:
            from governo.validator import Validator

            skill = self.skills.per_id(int(id_skill))
            if not skill:
                return {"ok": False, "messaggio": "skill non trovata"}
            val = Validator(timeout_sandbox=15).valida(skill.get("codice", ""))
            if not val.get("ok"):
                self.skills.scarta(int(id_skill))
                self.audit.registra("skill_bloccata", "; ".join(val.get("motivi", [])))
                return {"ok": False, "messaggio": "validazione fallita", "motivi": val.get("motivi", [])}
            if skill.get("stato") == "proposta":
                self.skills.approva(int(id_skill))
            ok = self.skills.attiva(int(id_skill))
            self.audit.registra("skill_attiva", str(id_skill))
            return {"ok": bool(ok), "figlio": self.skills.per_id(int(id_skill))}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}

    def skill_esegui(self, id_skill, contesto=None):
        if not self.skills:
            return {"ok": False, "messaggio": "skill non disponibili"}
        try:
            from governo.sandbox_skill import esegui_in_sandbox

            skill = self.skills.per_id(int(id_skill))
            if not skill:
                return {"ok": False, "messaggio": "skill non trovata"}
            if skill.get("stato") != "attiva":
                return {"ok": False, "messaggio": "skill non attiva"}
            input_utente = contesto if isinstance(contesto, dict) else {"testo": contesto}
            ctx = dict(input_utente or {})
            ctx.update({
                "input": input_utente or {},
                "timeline": self.timeline.pattern_oggi(),
                "eventi": self.timeline.eventi_oggi(80),
                "world": self.world.ultimo(),
            })
            r = esegui_in_sandbox(skill.get("codice", ""), ctx, timeout=15)
            self.audit.registra("skill_esegui", f"{skill.get('nome')} -> {r.get('ok')}")
            try:
                self.timeline.registra(
                    "skill_eseguita",
                    f"{skill.get('nome')} -> {r.get('ok')}",
                    origine="skill",
                    progetto="Skill",
                    meta={"id": int(id_skill), "risultato": r},
                )
            except Exception:
                pass
            return {"ok": r.get("ok"), "skill": skill.get("nome"), "risultato": r}
        except Exception as e:
            return {"ok": False, "messaggio": str(e)}


def crea_handler(m):
    class H(BaseHTTPRequestHandler):
        _rate = defaultdict(list)
        def log_message(self, *a): pass
        def _send(self, corpo, ctype="application/json", code=200):
            if isinstance(corpo, str): corpo = corpo.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        def _json(self, d, code=200): self._send(json.dumps(d), "application/json", code)
        def _body(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                if n > MAX_BODY_BYTES:
                    return {"_errore": "body troppo grande"}
                return json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return {}
        def _rate_limit(self, nome, max_per_minuto=60):
            now = time.time()
            ip = self.client_address[0] if self.client_address else "local"
            key = (ip, nome)
            bucket = [t for t in H._rate[key] if now - t < 60]
            H._rate[key] = bucket
            if len(bucket) >= max_per_minuto:
                return False
            bucket.append(now)
            return True
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                try:
                    with open(UI_FILE, "r", encoding="utf-8") as f:
                        self._send(f.read(), "text/html; charset=utf-8")
                except Exception as e:
                    self._send(f"UI non trovata: {e}", "text/plain", 500)
            elif self.path.startswith("/stato"):
                self._json(m.stato())
            elif self.path.startswith("/eventi"):
                since = 0
                if "since=" in self.path:
                    try: since = int(self.path.split("since=")[1])
                    except Exception: since = 0
                self._json({"eventi": m.eventi_da(since)})
            elif self.path.startswith("/audit/export"):
                dest = os.path.join(_DIR, "audit_export.json")
                n = m.audit.esporta(dest)
                self._json({"ok": True, "file": os.path.basename(dest), "voci": n})
            elif self.path.startswith("/audit"):
                self._json({"report": m.audit.report(), "voci": m.audit.recenti(15)})
            elif self.path.startswith("/metriche"):
                self._json(m.metriche())
            elif self.path.startswith("/agenti"):
                self._json({"agenti": m.agenti.nomi()})
            elif self.path.startswith("/dashboard"):
                self._json(m.dashboard())
            elif self.path.startswith("/sensi"):
                self._json(m.sensi_ora())
            elif self.path.startswith("/modelli"):
                self._json(m.modelli_stato())
            elif self.path.startswith("/connettori"):
                self._json(m.connettori_info())
            elif self.path.startswith("/skills"):
                self._json(m.skills_lista())
            elif self.path.startswith("/identita"):
                self._json(m.identita())
            elif self.path.startswith("/flotta"):
                self._json(m.flotta())
            elif self.path.startswith("/workflow"):
                self._json(m.workflow_stato())
            elif self.path.startswith("/console"):
                self._json(m.dashboard())
            elif self.path.startswith("/permessi"):
                self._json(m.permessi_stato())
            elif self.path.startswith("/timeline") or self.path.startswith("/cognizione"):
                self._json(m.timeline_stato())
            elif self.path.startswith("/pensiero"):
                self._json(m.pensiero_analitico())
            elif self.path.startswith("/world"):
                self._json(m.world_stato())
            elif self.path.startswith("/proposte"):
                self._json(m.proposte_stato())
            elif self.path.startswith("/diario"):
                self._json(m.diario_stato())
            elif self.path.startswith("/obiettivi"):
                self._json(m.obiettivi_stato())
            elif self.path.startswith("/esperimenti"):
                self._json(m.esperimenti_stato())
            else:
                self._json({"argo": "ok"})
        def do_POST(self):
            if not self._rate_limit(self.path.split("?")[0], 30 if self.path.startswith("/chat") else 60):
                self._json({"ok": False, "messaggio": "troppe richieste"}, 429); return
            if self.path.startswith("/conferma"):
                if not m.ruoli.puo("confermare"):
                    self._json({"ok": False, "messaggio": "permesso negato"}); return
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.conferma(bool(b.get("si"))))
            elif self.path.startswith("/chat"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.chat(b.get("testo", "")))
            elif self.path.startswith("/ricerca"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.ricerca_online(b.get("query", ""), int(b.get("max_risultati", 5))))
            elif self.path.startswith("/autonomia"):
                if not m.ruoli.puo("configurare"):
                    self._json({"ok": False, "messaggio": "permesso negato"}); return
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.imposta_modo(b.get("modo", "chiede")))
            elif self.path.startswith("/annulla"):
                self._json(m.annulla())
            elif self.path.startswith("/agente"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.esegui_agente(b.get("nome", "")))
            elif self.path.startswith("/consolida"):
                self._json(m.consolida_ora())
            elif self.path.startswith("/rifletti"):
                self._json(m.rifletti_ora())
            elif self.path.startswith("/sonno"):
                self._json(m.esegui_sonno())
            elif self.path.startswith("/skill/approva"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.skill_approva(b.get("id")))
            elif self.path.startswith("/skill/attiva"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.skill_attiva(b.get("id")))
            elif self.path.startswith("/skill/scarta"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.skill_scarta(b.get("id")))
            elif self.path.startswith("/skill/esegui"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.skill_esegui(b.get("id"), b.get("contesto", {})))
            elif self.path.startswith("/skill/bonifica"):
                self._json(m.skills_bonifica())
            elif self.path.startswith("/workflow/avvia"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.workflow_avvia(b.get("nome", ""), b.get("parametri", {})))
            elif self.path.startswith("/workflow/approva"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.workflow_approva(b.get("id")))
            elif self.path.startswith("/permessi"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.imposta_permessi(b.get("modo", "selezione"), b.get("cartelle", [])))
            elif self.path.startswith("/proposta/stato"):
                b = self._body()
                if b.get("_errore"): self._json({"ok": False, "messaggio": b["_errore"]}, 413); return
                self._json(m.proposta_stato(b.get("id"), b.get("stato", "proposta")))
            else:
                self._json({"ok": False}, 404)
    return H


def _trova_browser():
    cand = [
        shutil.which("msedge"), shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in cand:
        if p and os.path.exists(p):
            return p
    return None


def apri_finestra():
    url = f"http://{HOST}:{PORT}"
    # 1) finestra nativa vera (se pywebview è installato)
    try:
        import webview
        webview.create_window("ARGO", url, width=540, height=800)
        webview.start()
        return "nativa"
    except Exception:
        pass
    # 2) Edge/Chrome in modalità APP: finestra senza barre, sembra un'app desktop
    b = _trova_browser()
    if b:
        try:
            subprocess.Popen([b, f"--app={url}", "--window-size=540,820"])
            return "appmode"
        except Exception:
            pass
    # 3) fallback: scheda browser
    webbrowser.open(url)
    return "browser"


if __name__ == "__main__":
    print(f"[ARGO] motore web su http://{HOST}:{PORT}")
    motore = Motore()
    server = ThreadingHTTPServer((HOST, PORT), crea_handler(motore))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    modo = apri_finestra()
    print("[ARGO] finestra:", modo)
    if modo != "nativa":
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            motore.running = False
            print("\n[ARGO] spento.")
