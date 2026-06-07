"""
ARGO - cognizione/world_model.py

World Model v2: inferenza avanzata su dati locali.
Legge timeline, memoria e audit; produce ipotesi con confidenza, lacune,
priorita' e piani governati. Non esegue azioni: prepara decisioni spiegabili.

Miglioramenti v2:
  - Raggruppamento PROGETTI per cartella/finestra con blocklist robusta
  - FILE COLLEGATI nella stessa finestra temporale o cartella
  - RICORRENZE settimanali/giornaliere rilevate dai timestamp
  - IPOTESI con campo 'confidenza' esplicito
  - LACUNE per file senza progetto noto
  - Inferenza deterministica; Ollama usato solo per arricchimento opzionale
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
import sqlite3
from collections import Counter, defaultdict
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from cognizione.timeline import normalizza_progetto, _GENERICI_PROGETTO, _STOP_TITOLO
except Exception:
    _GENERICI_PROGETTO: set = {"", ".", "desktop", "downloads", "argo", "documents"}
    _STOP_TITOLO: set = {"google", "chrome", "edge", "firefox", "visual", "studio", "code"}

    def normalizza_progetto(nome):
        return str(nome or "").strip() or None


# ---------------------------------------------------------------------------
# Blocklist robusta per titoli di finestre "sporchi" / generici
# ---------------------------------------------------------------------------

_BLOCKLIST_TITOLI: set[str] = {
    # Browser e motori di ricerca
    "google", "chrome", "edge", "firefox", "mozilla", "safari", "opera",
    "brave", "vivaldi", "internet explorer", "ie", "chromium",
    # Editor e IDE generici
    "visual studio code", "visual studio", "vscode", "code",
    "notepad", "notepad++", "blocco note", "textedit", "nano", "vim", "nvim",
    "sublime text", "atom", "gedit", "kate",
    # Shell e terminali
    "cmd", "command prompt", "powershell", "windows powershell", "terminal",
    "bash", "wsl", "konsole", "iterm", "iterm2", "gnome terminal",
    # App di sistema Windows
    "file explorer", "esplora file", "esplora risorse", "windows explorer",
    "task manager", "gestione attivita", "registry editor",
    "pannello di controllo", "control panel", "impostazioni", "settings",
    # Email e calendario generici
    "outlook", "thunderbird", "mail", "apple mail",
    # Titoli di avviso / notifiche comuni
    "action required", "required", "attention", "attenzione", "avviso",
    "notifica", "notification", "alert", "warning", "errore", "error",
    # App Argo stessa
    "argo", "argo console", "argo chat",
    # Piattaforme IA
    "chatgpt", "claude", "copilot", "gemini", "perplexity", "codex",
    "openai", "anthropic",
    # Nomi utente / percorsi generici
    "users", "user", "tufilli davide", "davide", "home",
    "desktop", "downloads", "download", "documenti", "documents",
    "immagini", "pictures", "musica", "music", "video",
    # Titoli brevi senza senso
    "new tab", "nuova scheda", "about:blank",
    # Applicazioni di collaborazione
    "teams", "slack", "discord", "zoom", "meet", "webex", "skype",
    # Varie
    "explorer", "finder", "spotlight",
}

# Pattern di titolo che indicano un titolo "sporco" (es. solo numeri, molto corto)
_PATTERN_TITOLO_SPORCO = re.compile(
    r"^(\d+|[\W_]+|.{1,2}|https?://[^\s]+)$", re.IGNORECASE
)

# Pattern per estrarre orario da timestamp ISO
_RE_ORA = re.compile(r"T(\d{2}):(\d{2})")
_RE_GIORNO_SETTIMANA = [
    "lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"
]


def _ora() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _oggi() -> str:
    return _dt.date.today().isoformat()


def _safe_json(dati: Any) -> str:
    try:
        return json.dumps(dati, ensure_ascii=True, sort_keys=True)
    except Exception:
        return "{}"


def _load_json(testo: str) -> Any:
    try:
        return json.loads(testo or "{}")
    except Exception:
        return {}


def _titolo_pulito(titolo: str) -> str:
    """Normalizza un titolo rimuovendo separatori e spazi in eccesso."""
    t = re.sub(r"\s+[-|]\s+|\s+-\s+| — ", " | ", str(titolo or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120]


def _titolo_sporco(titolo: str) -> bool:
    """True se il titolo e' da escludere (blocklist o pattern)."""
    if not titolo:
        return True
    t = titolo.strip().lower()
    # Controlla blocklist diretta
    if t in _BLOCKLIST_TITOLI:
        return True
    # Controlla se ogni parola significativa e' nella blocklist
    parole = [p for p in re.findall(r"[a-z0-9]{3,}", t) if p not in _STOP_TITOLO]
    if not parole:
        return True
    if all(p in _BLOCKLIST_TITOLI or p in _STOP_TITOLO or p in _GENERICI_PROGETTO for p in parole):
        return True
    # Pattern sporco
    if _PATTERN_TITOLO_SPORCO.match(t):
        return True
    return False


def _cartella_da_path(percorso: str) -> str | None:
    """Ritorna l'ultima cartella significativa da un percorso file."""
    if not percorso:
        return None
    parti = [p for p in re.split(r"[\\/]+", percorso) if p]
    for parte in reversed(parti[:-1]):  # escludi il filename
        basso = parte.lower().strip()
        if basso in _GENERICI_PROGETTO or _STOP_TITOLO and basso in _STOP_TITOLO:
            continue
        if re.match(r"^[a-z]:$", basso) or basso.startswith("."):
            continue
        if len(basso) >= 3:
            return parte
    return None


def _finestra_temporale(timestamp_iso: str, minuti: int = 15) -> str:
    """Ritorna un bucket temporale arrotondato al multiplo di 'minuti'."""
    try:
        dt = _dt.datetime.fromisoformat(timestamp_iso)
        bucket = (dt.hour * 60 + dt.minute) // minuti
        return f"{dt.date().isoformat()}_{bucket:04d}"
    except Exception:
        return "unknown"


def _giorno_settimana_iso(timestamp_iso: str) -> int | None:
    """0=lunedi, 6=domenica. None se il timestamp e' invalido."""
    try:
        return _dt.datetime.fromisoformat(timestamp_iso).weekday()
    except Exception:
        return None


def _ora_intera(timestamp_iso: str) -> int | None:
    """Ora del giorno (0-23). None se invalido."""
    try:
        return _dt.datetime.fromisoformat(timestamp_iso).hour
    except Exception:
        return None


# ---------------------------------------------------------------------------
# World Model
# ---------------------------------------------------------------------------

class WorldModel:
    def __init__(self, percorso: str | None = None):
        if percorso is None:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memoria"))
            os.makedirs(base, exist_ok=True)
            percorso = os.path.join(base, "argo_world_model.db")
        self.percorso = percorso
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._crea_schema()

    def _crea_schema(self) -> None:
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS analisi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quando TEXT NOT NULL,
                giorno TEXT NOT NULL,
                sintesi TEXT,
                dati_json TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_world_giorno ON analisi(giorno, id)")
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS proposte (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chiave TEXT UNIQUE NOT NULL,
                creata TEXT NOT NULL,
                aggiornata TEXT NOT NULL,
                stato TEXT NOT NULL,
                obiettivo TEXT NOT NULL,
                rischio TEXT,
                richiede_conferma INTEGER NOT NULL DEFAULT 1,
                passi_json TEXT,
                origine_json TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_world_proposte_stato ON proposte(stato, aggiornata)")
        self.conn.commit()

    # -----------------------------------------------------------------------
    # Interfaccia pubblica (mantenuta compatibile)
    # -----------------------------------------------------------------------

    def analizza(self, timeline=None, memoria=None, audit=None, grafo=None) -> dict[str, Any]:
        """Esegue un ciclo analitico su dati reali locali."""
        giorno = _oggi()

        # Raccoglie dati grezzi
        eventi_grezzi = self._carica_eventi(timeline)
        stato = self._stato(timeline, memoria, audit, grafo, eventi_grezzi)

        # Inferenza avanzata
        progetti_v2 = self._inferisci_progetti_v2(eventi_grezzi)
        file_collegati = self._collega_file(eventi_grezzi)
        ricorrenze = self._rileva_ricorrenze(timeline, eventi_grezzi)

        # Aggiorna stato con le inferenze v2
        stato["progetti_v2"] = progetti_v2
        stato["file_collegati"] = file_collegati
        stato["ricorrenze"] = ricorrenze

        ipotesi = self._ipotesi(stato)
        lacune = self._lacune(stato, ipotesi, eventi_grezzi)
        piani = self._piani(stato, ipotesi, lacune)
        meta = self._metacognizione(stato, ipotesi, lacune)

        sintesi = self._sintesi(stato, ipotesi, lacune, piani)
        analisi = {
            "quando": _ora(),
            "giorno": giorno,
            "sintesi": sintesi,
            "stato": stato,
            "ipotesi": ipotesi,
            "lacune": lacune,
            "piani": piani,
            "metacognizione": meta,
        }
        analisi["proposte_generate"] = self.aggiorna_proposte(analisi)
        analisi["proposte"] = self.proposte("proposta", limite=12)
        self._salva(analisi)
        return analisi

    def ultimo(self) -> dict[str, Any] | None:
        c = self.conn.cursor()
        c.execute("SELECT * FROM analisi ORDER BY id DESC LIMIT 1")
        r = c.fetchone()
        if not r:
            return None
        d = _load_json(r["dati_json"])
        d.setdefault("quando", r["quando"])
        d.setdefault("giorno", r["giorno"])
        d.setdefault("sintesi", r["sintesi"])
        return d

    def contesto_chat(self) -> str:
        u = self.ultimo()
        if not u:
            return "World model: non ho ancora eseguito un'analisi."
        righe = ["World model recente:", "- " + u.get("sintesi", "")]
        if u.get("ipotesi"):
            righe.append("- ipotesi: " + " | ".join(i["titolo"] for i in u["ipotesi"][:3]))
        if u.get("lacune"):
            righe.append("- lacune: " + " | ".join(l["titolo"] for l in u["lacune"][:3]))
        if u.get("piani"):
            righe.append("- piani proposti: " + " | ".join(p["obiettivo"] for p in u["piani"][:3]))
        props = self.proposte("proposta", limite=5)
        if props:
            righe.append("- proposte operative aperte: " + " | ".join(p["obiettivo"] for p in props[:3]))
        # Aggiungi ricorrenze rilevate
        stato = u.get("stato", {})
        ricorrenze = stato.get("ricorrenze", [])
        if ricorrenze:
            righe.append("- ricorrenze: " + " | ".join(r["descrizione"] for r in ricorrenze[:2]))
        return "\n".join(righe)

    def aggiorna_proposte(self, analisi: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for piano in analisi.get("piani", []) or []:
            obiettivo = str(piano.get("obiettivo") or "").strip()
            if not obiettivo:
                continue
            chiave = self._chiave_proposta(obiettivo)
            now = _ora()
            c = self.conn.cursor()
            c.execute(
                """
                INSERT INTO proposte (
                    chiave, creata, aggiornata, stato, obiettivo, rischio,
                    richiede_conferma, passi_json, origine_json
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(chiave) DO UPDATE SET
                    aggiornata=excluded.aggiornata,
                    rischio=excluded.rischio,
                    richiede_conferma=excluded.richiede_conferma,
                    passi_json=excluded.passi_json,
                    origine_json=excluded.origine_json
                """,
                (
                    chiave,
                    now,
                    now,
                    "proposta",
                    obiettivo,
                    str(piano.get("rischio") or "medio"),
                    1 if piano.get("richiede_conferma", True) else 0,
                    _safe_json(piano.get("passi") or []),
                    _safe_json({
                        "analisi": analisi.get("quando"),
                        "sintesi": analisi.get("sintesi"),
                        "ipotesi": [i.get("titolo") for i in analisi.get("ipotesi", [])[:4]],
                        "lacune": [l.get("titolo") for l in analisi.get("lacune", [])[:4]],
                    }),
                ),
            )
            self.conn.commit()
            out.append(self._proposta_da_chiave(chiave))
        return [p for p in out if p]

    def proposte(self, stato: str | None = None, limite: int = 20) -> list[dict[str, Any]]:
        c = self.conn.cursor()
        if stato:
            c.execute(
                "SELECT * FROM proposte WHERE stato=? ORDER BY aggiornata DESC LIMIT ?",
                (stato, int(limite)),
            )
        else:
            c.execute("SELECT * FROM proposte ORDER BY aggiornata DESC LIMIT ?", (int(limite),))
        return [self._riga_proposta(r) for r in c.fetchall()]

    def cambia_stato_proposta(self, id_proposta: int, stato: str) -> dict[str, Any]:
        if stato not in {"proposta", "approvata", "scartata"}:
            return {"ok": False, "messaggio": "stato non valido"}
        c = self.conn.cursor()
        c.execute(
            "UPDATE proposte SET stato=?, aggiornata=? WHERE id=?",
            (stato, _ora(), int(id_proposta)),
        )
        self.conn.commit()
        if c.rowcount == 0:
            return {"ok": False, "messaggio": "proposta non trovata"}
        return {"ok": True, "proposta": self._proposta_da_id(id_proposta)}

    # -----------------------------------------------------------------------
    # Caricamento eventi grezzi dalla timeline
    # -----------------------------------------------------------------------

    @staticmethod
    def _carica_eventi(timeline) -> list[dict[str, Any]]:
        """Ritorna tutti gli eventi di oggi dalla timeline (o lista vuota)."""
        if timeline is None:
            return []
        try:
            return timeline.eventi_oggi(500) or []
        except Exception:
            try:
                return timeline.recenti(200) or []
            except Exception:
                return []

    # -----------------------------------------------------------------------
    # Stato base (compatibile v1)
    # -----------------------------------------------------------------------

    def _stato(self, timeline, memoria, audit, grafo, eventi_grezzi: list[dict[str, Any]]) -> dict[str, Any]:
        tr: dict[str, Any] = {}
        pattern: dict[str, Any] = {}
        eventi: list[dict[str, Any]] = []
        if timeline is not None:
            try:
                tr = timeline.riepilogo_giorno()
                pattern = timeline.pattern_oggi()
                eventi = timeline.eventi_oggi(120)
            except Exception:
                tr, pattern, eventi = {}, {}, []

        mem_recenti: list[dict[str, Any]] = []
        mem_tipi: Counter = Counter()
        if memoria is not None:
            try:
                mem_recenti = memoria.ricordi_recenti(500)
                for r in mem_recenti:
                    if str(r.get("quando", "")).startswith(_oggi()):
                        mem_tipi[r.get("tipo", "")] += 1
            except Exception:
                pass

        audit_eventi: Counter = Counter()
        audit_voci = 0
        if audit is not None:
            try:
                recenti = audit.recenti(1000)
                audit_voci = len(recenti)
                for v in recenti:
                    audit_eventi[v.get("evento") or v.get("tipo") or "audit"] += 1
            except Exception:
                pass

        grafo_stat: dict[str, Any] = {}
        if grafo is not None:
            try:
                grafo_stat = grafo.statistiche()
            except Exception:
                pass

        return {
            "giorno": _oggi(),
            "timeline_eventi": int((tr or {}).get("eventi") or (pattern or {}).get("eventi") or 0),
            "timeline_tipi": dict((tr or {}).get("conteggi") or (pattern or {}).get("tipi") or {}),
            "timeline_pattern": list((tr or {}).get("pattern") or []),
            "timeline_lacune": list((tr or {}).get("lacune") or []),
            "progetti": self._progetti_puliti((tr or {}).get("progetti") or []),
            "finestre": dict((pattern or {}).get("finestre") or {}),
            "memoria_tipi": dict(mem_tipi),
            "audit_eventi": dict(audit_eventi),
            "audit_voci": audit_voci,
            "grafo": grafo_stat,
            "eventi_recenti": [
                {
                    "tipo": e.get("tipo"),
                    "titolo": e.get("titolo") or e.get("descrizione") or "",
                    "progetto": e.get("progetto"),
                    "quando": e.get("quando", ""),
                    "riferimento": e.get("riferimento", ""),
                }
                for e in eventi[:30]
            ],
        }

    @staticmethod
    def _progetti_puliti(progetti: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        visti: set[str] = set()
        for p in progetti:
            if not isinstance(p, dict):
                continue
            nome = normalizza_progetto(p.get("nome"))
            if not nome or nome.lower() in visti:
                continue
            pulito = dict(p)
            pulito["nome"] = nome
            out.append(pulito)
            visti.add(nome.lower())
        return out

    # -----------------------------------------------------------------------
    # MIGLIORAMENTO 1: Raggruppamento PROGETTI v2
    # -----------------------------------------------------------------------

    def _inferisci_progetti_v2(self, eventi: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Raggruppa gli eventi per progetto usando:
        1) Il campo 'progetto' gia' inferito dalla timeline
        2) La cartella estratta dal campo 'riferimento' (percorso file)
        3) Il titolo della finestra, filtrato dalla blocklist robusta

        Esclude titoli sporchi con _titolo_sporco().
        Restituisce la lista ordinata per numero di eventi (decrescente).
        """
        bucket: dict[str, dict[str, Any]] = {}

        for e in eventi:
            progetto = normalizza_progetto(e.get("progetto"))

            # Fallback: cartella dal riferimento
            if not progetto and e.get("riferimento"):
                progetto = _cartella_da_path(str(e["riferimento"]))
                if progetto:
                    progetto = normalizza_progetto(progetto)

            # Fallback: titolo finestra (filtrato)
            if not progetto and e.get("tipo") == "finestra_attiva" and e.get("titolo"):
                titolo = _titolo_pulito(e["titolo"])
                if not _titolo_sporco(titolo):
                    # Prende solo il primo segmento significativo
                    parti = re.split(r"\s*\|\s*|\s+-\s+| — ", titolo)
                    for parte in reversed(parti):
                        parte = parte.strip()
                        if parte and not _titolo_sporco(parte):
                            progetto = normalizza_progetto(parte)
                            break

            if not progetto:
                continue

            chiave = progetto.lower()
            if chiave not in bucket:
                bucket[chiave] = {
                    "nome": progetto,
                    "eventi": 0,
                    "tipi": Counter(),
                    "file": set(),
                    "finestre": set(),
                    "quando_primo": e.get("quando", ""),
                    "quando_ultimo": e.get("quando", ""),
                }
            b = bucket[chiave]
            b["eventi"] += 1
            b["tipi"][e.get("tipo", "sconosciuto")] += 1
            if e.get("tipo") == "file_visto" and e.get("riferimento"):
                b["file"].add(str(e["riferimento"]))
            if e.get("tipo") == "finestra_attiva" and e.get("titolo"):
                b["finestre"].add(str(e["titolo"])[:80])
            ts = e.get("quando", "")
            if ts:
                if not b["quando_primo"] or ts < b["quando_primo"]:
                    b["quando_primo"] = ts
                if ts > b["quando_ultimo"]:
                    b["quando_ultimo"] = ts

        out = []
        for b in bucket.values():
            out.append({
                "nome": b["nome"],
                "eventi": b["eventi"],
                "tipi": dict(b["tipi"]),
                "file_count": len(b["file"]),
                "file_campione": sorted(b["file"])[:5],
                "finestre_count": len(b["finestre"]),
                "finestre_campione": sorted(b["finestre"])[:3],
                "quando_primo": b["quando_primo"],
                "quando_ultimo": b["quando_ultimo"],
            })

        out.sort(key=lambda x: (-x["eventi"], x["nome"].lower()))
        return out[:12]

    # -----------------------------------------------------------------------
    # MIGLIORAMENTO 2: FILE COLLEGATI
    # -----------------------------------------------------------------------

    @staticmethod
    def _collega_file(eventi: list[dict[str, Any]], finestra_minuti: int = 15) -> list[dict[str, Any]]:
        """
        Collega file visti nella stessa finestra temporale (15 min di default)
        o nella stessa cartella. Restituisce gruppi di file correlati.
        """
        # Raggruppa per finestra temporale
        bucket_tempo: dict[str, list[str]] = defaultdict(list)
        # Raggruppa per cartella
        bucket_cartella: dict[str, list[str]] = defaultdict(list)

        for e in eventi:
            if e.get("tipo") != "file_visto" or not e.get("riferimento"):
                continue
            percorso = str(e["riferimento"])
            ts = e.get("quando", "")

            # Bucket temporale
            if ts:
                bucket = _finestra_temporale(ts, finestra_minuti)
                bucket_tempo[bucket].append(percorso)

            # Bucket cartella
            cartella = _cartella_da_path(percorso)
            if cartella:
                bucket_cartella[cartella.lower()].append(percorso)

        gruppi: list[dict[str, Any]] = []

        # Gruppi per finestra temporale (almeno 2 file)
        for bucket_key, file_lista in bucket_tempo.items():
            file_unici = list(dict.fromkeys(file_lista))  # dedup preservando ordine
            if len(file_unici) >= 2:
                gruppi.append({
                    "tipo": "finestra_temporale",
                    "chiave": bucket_key,
                    "file": file_unici[:8],
                    "conteggio": len(file_unici),
                })

        # Gruppi per cartella (almeno 2 file distinti)
        for cartella, file_lista in bucket_cartella.items():
            file_unici = list(dict.fromkeys(file_lista))
            if len(file_unici) >= 2:
                # Evita duplicati con i gruppi temporali gia' inseriti
                già_inseriti = any(
                    set(g["file"]) >= set(file_unici[:8]) for g in gruppi
                )
                if not già_inseriti:
                    gruppi.append({
                        "tipo": "stessa_cartella",
                        "chiave": cartella,
                        "file": file_unici[:8],
                        "conteggio": len(file_unici),
                    })

        gruppi.sort(key=lambda g: -g["conteggio"])
        return gruppi[:10]

    # -----------------------------------------------------------------------
    # MIGLIORAMENTO 3: RICORRENZE
    # -----------------------------------------------------------------------

    @staticmethod
    def _rileva_ricorrenze(timeline, eventi_oggi: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Rileva azioni o pattern che si ripetono:
        - Stesso tipo+titolo in piu' giorni => ricorrenza giornaliera/settimanale
        - Stesso tipo+titolo alla stessa ora => ricorrenza oraria

        Usa gli eventi di oggi piu' quelli storici dalla timeline se disponibile.
        """
        ricorrenze: list[dict[str, Any]] = []

        # Raccoglie eventi storici (ultimi 30 giorni) se la timeline e' disponibile
        eventi_storici: list[dict[str, Any]] = []
        if timeline is not None:
            try:
                # Prende gli ultimi 500 eventi (non solo oggi)
                eventi_storici = timeline.recenti(500) or []
            except Exception:
                eventi_storici = []

        if not eventi_storici:
            eventi_storici = eventi_oggi

        # Raggruppa per (tipo, titolo_normalizzato) -> lista di (giorno, ora, giorno_settimana)
        chiavi: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in eventi_storici:
            tipo = e.get("tipo", "")
            titolo = str(e.get("titolo") or e.get("descrizione") or "").strip()[:60]
            if not titolo or tipo in ("chat", "risposta_chat", "sistema", "avvio"):
                continue
            chiave = f"{tipo}|{titolo.lower()}"
            ts = e.get("quando", "")
            giorno = ts[:10] if ts else ""
            ora = _ora_intera(ts) if ts else None
            dow = _giorno_settimana_iso(ts) if ts else None
            if giorno:
                chiavi[chiave].append({"giorno": giorno, "ora": ora, "dow": dow})

        for chiave, occorrenze in chiavi.items():
            if len(occorrenze) < 2:
                continue

            tipo_ev, titolo_ev = chiave.split("|", 1)
            giorni_distinti = len({o["giorno"] for o in occorrenze})
            ore = [o["ora"] for o in occorrenze if o["ora"] is not None]
            dows = [o["dow"] for o in occorrenze if o["dow"] is not None]

            # Ricorrenza giornaliera: appare in 3+ giorni
            if giorni_distinti >= 3:
                descrizione = f"'{titolo_ev}' ({tipo_ev}) ricorre in {giorni_distinti} giorni distinti"
                # Controlla se c'e' una fascia oraria stabile
                if ore:
                    ore_counter = Counter(ore)
                    ora_modale, freq_ora = ore_counter.most_common(1)[0]
                    if freq_ora >= 2 and freq_ora / len(ore) >= 0.5:
                        descrizione += f" — spesso alle {ora_modale:02d}:xx"
                # Controlla se c'e' un giorno della settimana prevalente
                if dows:
                    dow_counter = Counter(dows)
                    dow_modale, freq_dow = dow_counter.most_common(1)[0]
                    if freq_dow >= 2 and freq_dow / len(dows) >= 0.4:
                        nome_giorno = _RE_GIORNO_SETTIMANA[dow_modale]
                        descrizione += f" — spesso di {nome_giorno}"
                    freq_pattern = "giornaliero" if giorni_distinti >= 5 else "frequente"
                else:
                    freq_pattern = "frequente"
                ricorrenze.append({
                    "tipo": tipo_ev,
                    "titolo": titolo_ev,
                    "pattern": freq_pattern,
                    "giorni_distinti": giorni_distinti,
                    "occorrenze": len(occorrenze),
                    "descrizione": descrizione,
                    "confidenza": min(0.95, 0.5 + giorni_distinti / 20),
                })
                continue

            # Ricorrenza nella stessa ora in piu' giorni
            if ore and giorni_distinti >= 2:
                ore_counter = Counter(ore)
                ora_modale, freq_ora = ore_counter.most_common(1)[0]
                if freq_ora >= 2 and freq_ora / len(ore) >= 0.6:
                    ricorrenze.append({
                        "tipo": tipo_ev,
                        "titolo": titolo_ev,
                        "pattern": "orario_fisso",
                        "giorni_distinti": giorni_distinti,
                        "occorrenze": len(occorrenze),
                        "descrizione": f"'{titolo_ev}' tende a comparire alle {ora_modale:02d}:xx ({giorni_distinti} giorni)",
                        "confidenza": min(0.85, 0.4 + freq_ora / 10),
                    })

        # Ordina per confidenza decrescente
        ricorrenze.sort(key=lambda r: -r.get("confidenza", 0))
        return ricorrenze[:8]

    # -----------------------------------------------------------------------
    # MIGLIORAMENTO 4+5: IPOTESI con confidenza e LACUNE su file senza progetto
    # -----------------------------------------------------------------------

    def _ipotesi(self, s: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        tipi = s.get("timeline_tipi", {})
        mem = s.get("memoria_tipi", {})
        progetti_v2 = s.get("progetti_v2", [])
        ricorrenze = s.get("ricorrenze", [])
        file_collegati = s.get("file_collegati", [])

        # Ipotesi sul progetto principale (usa progetti_v2 se disponibili, altrimenti fallback)
        progetti_fonte = progetti_v2 if progetti_v2 else s.get("progetti", [])
        if progetti_fonte:
            p = progetti_fonte[0]
            n_eventi = p.get("eventi", 0)
            confidenza = round(min(0.92, 0.40 + n_eventi / 25), 2)
            out.append({
                "tipo": "focus_progetto",
                "titolo": f"Il focus probabile e' '{p.get('nome')}'",
                "evidenza": (
                    f"{n_eventi} eventi collegati"
                    + (f", {p.get('file_count', 0)} file" if p.get("file_count") else "")
                    + (f", {p.get('finestre_count', 0)} finestre" if p.get("finestre_count") else "")
                    + "."
                ),
                "confidenza": confidenza,
            })

        # Ipotesi su secondo progetto attivo (se abbastanza evidenze)
        if len(progetti_fonte) >= 2:
            p2 = progetti_fonte[1]
            n2 = p2.get("eventi", 0)
            if n2 >= 3:
                out.append({
                    "tipo": "progetto_secondario",
                    "titolo": f"Progetto secondario rilevato: '{p2.get('nome')}'",
                    "evidenza": f"{n2} eventi.",
                    "confidenza": round(min(0.75, 0.30 + n2 / 20), 2),
                })

        # Ipotesi su ricorrenze
        for ric in ricorrenze[:2]:
            out.append({
                "tipo": "ricorrenza",
                "titolo": f"Azione ricorrente: {ric['descrizione']}",
                "evidenza": f"Pattern: {ric['pattern']}, {ric['occorrenze']} occorrenze.",
                "confidenza": ric.get("confidenza", 0.55),
            })

        # Ipotesi su file collegati (contesto collaborativo)
        if len(file_collegati) >= 2:
            out.append({
                "tipo": "lavoro_su_piu_file",
                "titolo": f"Davide sta lavorando su piu' file correlati ({len(file_collegati)} gruppi).",
                "evidenza": f"Primo gruppo: {file_collegati[0].get('conteggio', 0)} file in {file_collegati[0].get('tipo', '?')}.",
                "confidenza": round(min(0.80, 0.45 + len(file_collegati) / 15), 2),
            })

        # Ipotesi su operativita' (azioni ripetute)
        if tipi.get("azione", 0) >= 2 or mem.get("azione", 0) >= 3:
            out.append({
                "tipo": "operativita",
                "titolo": "Ci sono azioni ripetute che potrebbero diventare workflow.",
                "evidenza": f"azioni timeline={tipi.get('azione', 0)}, memoria={mem.get('azione', 0)}.",
                "confidenza": 0.72,
            })

        # Ipotesi su preferenza utente (rifiuti ripetuti)
        if mem.get("azione_rifiutata", 0) >= 2:
            out.append({
                "tipo": "preferenza_utente",
                "titolo": "Davide sta rifiutando alcune proposte: serve adattare le regole.",
                "evidenza": f"rifiuti oggi={mem.get('azione_rifiutata', 0)}.",
                "confidenza": 0.78,
            })

        # Ipotesi su sicurezza
        if s.get("audit_eventi", {}).get("sensibile_ignorato", 0):
            out.append({
                "tipo": "sicurezza",
                "titolo": "Sono comparsi file sensibili: la priorita' e' non toccarli.",
                "evidenza": f"{s['audit_eventi'].get('sensibile_ignorato', 0)} eventi protetti.",
                "confidenza": 0.90,
            })

        # Ipotesi residua su chat senza fatti
        if tipi.get("chat", 0) >= 2 and not out:
            out.append({
                "tipo": "chat_context",
                "titolo": "Ci sono domande, ma pochi fatti operativi collegati.",
                "evidenza": f"chat timeline={tipi.get('chat', 0)}.",
                "confidenza": 0.55,
            })

        return out[:8]

    def _lacune(
        self,
        s: dict[str, Any],
        ipotesi: list[dict[str, Any]],
        eventi_grezzi: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        # Lacune dalla timeline
        raw_lacune = s.get("timeline_lacune", [])
        for l in raw_lacune[:5]:
            if isinstance(l, dict):
                titolo = l.get("messaggio") or l.get("tipo") or str(l)
                tipo = l.get("tipo") or "timeline"
            else:
                titolo = str(l)
                tipo = "timeline"
            out.append({"tipo": tipo, "titolo": titolo, "priorita": "media"})

        # Lacuna: file senza progetto noto (NUOVO)
        file_senza_progetto = [
            e for e in eventi_grezzi
            if e.get("tipo") == "file_visto"
            and not normalizza_progetto(e.get("progetto"))
            and not _cartella_da_path(str(e.get("riferimento") or ""))
        ]
        if file_senza_progetto:
            campione = [
                os.path.basename(str(e.get("riferimento") or e.get("titolo") or ""))
                for e in file_senza_progetto[:4]
                if e.get("riferimento") or e.get("titolo")
            ]
            out.append({
                "tipo": "file_senza_progetto",
                "titolo": (
                    f"Non so a che progetto appartengono {len(file_senza_progetto)} file visti"
                    + (f" (es: {', '.join(campione[:3])})" if campione else "") + "."
                ),
                "priorita": "alta",
            })

        # Lacuna: finestre senza progetto associato
        finestre_sporche = [
            e for e in eventi_grezzi
            if e.get("tipo") == "finestra_attiva"
            and not normalizza_progetto(e.get("progetto"))
            and _titolo_sporco(str(e.get("titolo") or ""))
        ]
        if len(finestre_sporche) >= 3:
            out.append({
                "tipo": "finestre_senza_contesto",
                "titolo": f"{len(finestre_sporche)} finestre viste non hanno un progetto riconoscibile.",
                "priorita": "media",
            })

        # Lacuna: nessun progetto rilevato in assoluto
        if not s.get("progetti") and not s.get("progetti_v2"):
            out.append({
                "tipo": "world_model",
                "titolo": "Non so ancora associare molti eventi a un progetto.",
                "priorita": "alta",
            })

        # Lacuna: nessuna ipotesi generata
        if not ipotesi:
            out.append({
                "tipo": "metacognizione",
                "titolo": "Ho pochi segnali affidabili per generare ipotesi.",
                "priorita": "alta",
            })

        # Lacuna: pochi eventi in totale
        if s.get("timeline_eventi", 0) < 10:
            out.append({
                "tipo": "osservazione",
                "titolo": "La giornata ha pochi eventi cognitivi: devo osservare piu' contesto autorizzato.",
                "priorita": "media",
            })

        # Lacuna: ricorrenze rilevate ma mai proposte come workflow
        ricorrenze = s.get("ricorrenze", [])
        if ricorrenze and not any(i.get("tipo") == "ricorrenza" for i in ipotesi):
            out.append({
                "tipo": "ricorrenza_non_gestita",
                "titolo": f"Ho rilevato {len(ricorrenze)} ricorrenze ma non ho ancora proposto automazioni.",
                "priorita": "media",
            })

        return out[:10]

    def _piani(
        self,
        s: dict[str, Any],
        ipotesi: list[dict[str, Any]],
        lacune: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        piani: list[dict[str, Any]] = []

        # Piano per azioni ripetute => workflow
        if any(i["tipo"] == "operativita" for i in ipotesi):
            piani.append({
                "obiettivo": "Proporre un workflow per le azioni ripetute",
                "rischio": "medio",
                "richiede_conferma": True,
                "passi": [
                    "Raccogliere le ultime azioni simili.",
                    "Simulare una regola di automazione.",
                    "Passare da policy e chiedere conferma a Davide.",
                ],
            })

        # Piano per classificazione progetti
        if any(l["tipo"] in ("world_model", "classificazione_progetto") for l in lacune):
            piani.append({
                "obiettivo": "Migliorare classificazione progetto",
                "rischio": "basso",
                "richiede_conferma": False,
                "passi": [
                    "Usare cartelle, titoli finestre e nomi file come indizi.",
                    "Aggiornare il grafo con relazioni file-progetto probabili.",
                    "Segnalare in Console le associazioni a bassa confidenza.",
                ],
            })

        # Piano per file senza progetto (NUOVO)
        if any(l["tipo"] == "file_senza_progetto" for l in lacune):
            piani.append({
                "obiettivo": "Proporre a Davide l'etichettatura dei file senza progetto",
                "rischio": "basso",
                "richiede_conferma": True,
                "passi": [
                    "Elencare i file visti privi di progetto riconoscibile.",
                    "Proporre una categoria probabile per ciascuno.",
                    "Attendere conferma prima di aggiornare la memoria.",
                ],
            })

        # Piano per ricorrenze rilevate (NUOVO)
        ricorrenze = s.get("ricorrenze", [])
        if ricorrenze:
            ric_descrizioni = "; ".join(r["descrizione"] for r in ricorrenze[:2])
            piani.append({
                "obiettivo": f"Proporre automazione per ricorrenze: {ric_descrizioni[:100]}",
                "rischio": "medio",
                "richiede_conferma": True,
                "passi": [
                    "Mostrare a Davide le ricorrenze rilevate.",
                    "Proporre un trigger o reminder per ognuna.",
                    "Attendere conferma prima di creare qualsiasi regola.",
                ],
            })

        # Piano per sicurezza
        if s.get("audit_eventi", {}).get("sensibile_ignorato", 0):
            piani.append({
                "obiettivo": "Rafforzare riepilogo sicurezza giornaliero",
                "rischio": "basso",
                "richiede_conferma": False,
                "passi": [
                    "Contare rischi evitati.",
                    "Separare file sensibili da memoria semantica.",
                    "Mostrare il riepilogo in audit/console.",
                ],
            })

        # Piano per progetto secondario (NUOVO)
        if any(i["tipo"] == "progetto_secondario" for i in ipotesi):
            p2 = next(
                (i for i in ipotesi if i["tipo"] == "progetto_secondario"), None
            )
            if p2:
                piani.append({
                    "obiettivo": f"Preparare riepilogo per {p2['titolo']}",
                    "rischio": "basso",
                    "richiede_conferma": False,
                    "passi": [
                        "Raccogliere tutti gli eventi del progetto secondario.",
                        "Generare un mini-riepilogo da mostrare in Console.",
                    ],
                })

        return piani[:6]

    # -----------------------------------------------------------------------
    # Metacognizione, sintesi, helper (compatibili v1)
    # -----------------------------------------------------------------------

    @staticmethod
    def _metacognizione(
        s: dict[str, Any],
        ipotesi: list[dict[str, Any]],
        lacune: list[dict[str, Any]],
    ) -> dict[str, Any]:
        conf = 0.35
        conf += min(0.25, s.get("timeline_eventi", 0) / 80)
        conf += min(0.20, len(ipotesi) / 10)
        conf -= min(0.20, len(lacune) / 20)
        # Bonus per progetti v2 rilevati
        if s.get("progetti_v2"):
            conf += min(0.10, len(s["progetti_v2"]) / 20)
        # Bonus per ricorrenze
        if s.get("ricorrenze"):
            conf += 0.05
        conf = round(max(0.05, min(0.95, conf)), 2)
        priorita = "osservare" if conf < 0.45 else "pianificare" if ipotesi else "consolidare"
        return {
            "confidenza": conf,
            "priorita": priorita,
            "limiti": [l["titolo"] for l in lacune[:4]],
        }

    @staticmethod
    def _sintesi(
        s: dict[str, Any],
        ipotesi: list[dict[str, Any]],
        lacune: list[dict[str, Any]],
        piani: list[dict[str, Any]],
    ) -> str:
        n_progetti = len(s.get("progetti_v2") or s.get("progetti") or [])
        n_ric = len(s.get("ricorrenze") or [])
        extra = ""
        if n_progetti:
            extra += f", {n_progetti} progetti rilevati"
        if n_ric:
            extra += f", {n_ric} ricorrenze"
        return (
            f"Ho analizzato {s.get('timeline_eventi', 0)} eventi cognitivi{extra}: "
            f"{len(ipotesi)} ipotesi, {len(lacune)} lacune, {len(piani)} piani governati."
        )

    def _salva(self, analisi: dict[str, Any]) -> None:
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO analisi (quando,giorno,sintesi,dati_json) VALUES (?,?,?,?)",
            (analisi["quando"], analisi["giorno"], analisi["sintesi"], _safe_json(analisi)),
        )
        self.conn.commit()

    @staticmethod
    def _chiave_proposta(obiettivo: str) -> str:
        pulito = "".join(ch.lower() if ch.isalnum() else "_" for ch in obiettivo)
        while "__" in pulito:
            pulito = pulito.replace("__", "_")
        return pulito.strip("_")[:120] or "proposta"

    def _proposta_da_chiave(self, chiave: str) -> dict[str, Any] | None:
        c = self.conn.cursor()
        c.execute("SELECT * FROM proposte WHERE chiave=?", (chiave,))
        r = c.fetchone()
        return self._riga_proposta(r) if r else None

    def _proposta_da_id(self, id_proposta: int) -> dict[str, Any] | None:
        c = self.conn.cursor()
        c.execute("SELECT * FROM proposte WHERE id=?", (int(id_proposta),))
        r = c.fetchone()
        return self._riga_proposta(r) if r else None

    @staticmethod
    def _riga_proposta(r: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": r["id"],
            "chiave": r["chiave"],
            "creata": r["creata"],
            "aggiornata": r["aggiornata"],
            "stato": r["stato"],
            "obiettivo": r["obiettivo"],
            "rischio": r["rischio"],
            "richiede_conferma": bool(r["richiede_conferma"]),
            "passi": _load_json(r["passi_json"]) or [],
            "origine": _load_json(r["origine_json"]) or {},
        }

    def chiudi(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# __main__ smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    # Bootstrap sys.path (funziona sia come script che come -m)
    _self_dir = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_self_dir, ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    import tempfile
    from cognizione.timeline import TimelineCognitiva

    print("[smoke-test] WorldModel v2 ...")

    with tempfile.TemporaryDirectory() as tmp:
        db_tl = os.path.join(tmp, "tl.db")
        db_wm = os.path.join(tmp, "wm.db")

        t = TimelineCognitiva(percorso=db_tl)

        # Inserisci eventi di test coprendo tutti i rami v2
        import datetime
        oggi = datetime.date.today().isoformat()

        # Finestra attiva (progetto reale)
        t.registra_finestra("SONAR-master - Visual Studio Code")
        t.registra_finestra("ARGO Console")  # titolo sporco -> deve essere escluso
        t.registra_finestra("Relazione finale - Word")

        # File visti in cartella progetto
        t.registra_file(rf"C:\Users\Davide\Desktop\SONAR-master\modulo.py")
        t.registra_file(rf"C:\Users\Davide\Desktop\SONAR-master\utils.py")
        t.registra_file(rf"C:\Users\Davide\Desktop\Argo\cognizione\world_model.py")
        t.registra_file(rf"C:\Users\Davide\Documents\report.pdf")  # file senza progetto chiaro

        # Azione ripetuta
        t.registra_azione("salva file", riferimento=rf"C:\Users\Davide\Desktop\SONAR-master\modulo.py")
        t.registra_azione("salva file", riferimento=rf"C:\Users\Davide\Desktop\SONAR-master\utils.py")

        w = WorldModel(percorso=db_wm)
        risultato = w.analizza(timeline=t)

        # Controlli
        assert "ipotesi" in risultato, "Mancano le ipotesi"
        assert "lacune" in risultato, "Mancano le lacune"
        assert "piani" in risultato, "Mancano i piani"
        assert "proposte" in risultato, "Mancano le proposte"
        assert "stato" in risultato, "Manca lo stato"

        stato = risultato["stato"]
        assert "progetti_v2" in stato, "Manca progetti_v2"
        assert "file_collegati" in stato, "Manca file_collegati"
        assert "ricorrenze" in stato, "Manca ricorrenze"

        # Verifica che ARGO console NON sia nei progetti (blocklist)
        nomi_progetti = [p["nome"].lower() for p in stato.get("progetti_v2", [])]
        assert not any("argo" in n and "console" in n for n in nomi_progetti), \
            f"'ARGO Console' non deve essere un progetto valido, trovato: {nomi_progetti}"

        # Verifica che SONAR-master sia rilevato
        assert any("sonar" in n.lower() for n in nomi_progetti), \
            f"SONAR-master deve essere rilevato come progetto, trovato: {nomi_progetti}"

        # Verifica contesto_chat
        ctx = w.contesto_chat()
        assert "World model" in ctx, "contesto_chat deve iniziare con 'World model'"

        # Verifica che le ipotesi abbiano il campo confidenza
        for ip in risultato.get("ipotesi", []):
            assert "confidenza" in ip, f"Ipotesi senza confidenza: {ip}"
            assert 0.0 <= ip["confidenza"] <= 1.0, f"Confidenza fuori range: {ip}"

        # Verifica che i piani non eseguano azioni (solo proposta/conferma)
        for piano in risultato.get("piani", []):
            assert "obiettivo" in piano, "Piano senza obiettivo"
            assert piano.get("rischio") in ("basso", "medio", "alto"), "Rischio non valido"

        w.chiudi()
        t.chiudi()

    print("OK")
