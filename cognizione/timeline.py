"""
ARGO - cognizione/timeline.py
Osservazione cognitiva isolata: normalizza eventi della giornata, li salva
localmente, produce timeline e inferisce progetti/pattern semplici.

Non importa motore_web.py e non tocca la UI. Solo libreria standard.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any


TIPI_EVENTO = {
    "avvio",
    "file_visto",
    "finestra_attiva",
    "chat",
    "risposta_chat",
    "azione",
    "rifiuto",
    "rischio",
    "sistema",
    "errore",
    "consolidamento",
    # eventi cognitivi/enterprise aggiunti
    "sonno",
    "ricerca_web",
    "skill_proposta",
    "skill_eseguita",
    "proposta_approvata",
    "pensiero",
    "permessi",
    "agente",
}

_GENERICI_PROGETTO = {
    "",
    ".",
    "desktop",
    "downloads",
    "download",
    "documenti",
    "documents",
    "immagini",
    "pictures",
    "sorvegliata",
    "argo",
    "users",
    "user",
    "tufilli davide",
    "davide",
    "action required",
    "required",
    "codex",
    "chatgpt",
}

_STOP_TITOLO = {
    "google",
    "chrome",
    "edge",
    "mozilla",
    "firefox",
    "visual",
    "studio",
    "code",
    "notepad",
    "blocco",
    "note",
    "cmd",
    "powershell",
    "argo",
    "action",
    "required",
}


def _ora() -> _dt.datetime:
    return _dt.datetime.now().replace(microsecond=0)


def _parse_quando(quando: Any = None) -> _dt.datetime:
    if quando is None:
        return _ora()
    if isinstance(quando, _dt.datetime):
        return quando.replace(microsecond=0)
    if isinstance(quando, _dt.date):
        return _dt.datetime.combine(quando, _dt.time.min)
    testo = str(quando).strip()
    if not testo:
        return _ora()
    try:
        return _dt.datetime.fromisoformat(testo).replace(microsecond=0)
    except ValueError:
        return _ora()


def _redigi(testo: Any) -> str:
    """Usa sicurezza.redigi se disponibile, altrimenti fallback minimale."""
    if testo is None:
        return ""
    s = str(testo)
    try:
        import sicurezza

        return sicurezza.redigi(s)
    except Exception:
        s = re.sub(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", s)
        s = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "sk-[REDACTED]", s)
        return s


def _pulito_nome(nome: str) -> str:
    nome = re.sub(r"[_\-.]+", " ", nome or "").strip()
    nome = re.sub(r"[\[\]{}()!•·]+", " ", nome).strip()
    nome = re.sub(r"\s+", " ", nome)
    return nome[:80]


def _nome_generico(nome: str) -> bool:
    pulito = _pulito_nome(nome).lower().strip()
    if not pulito:
        return True
    if pulito in _GENERICI_PROGETTO:
        return True
    parole = [p for p in re.findall(r"[a-z0-9]{3,}", pulito) if p not in _STOP_TITOLO]
    if not parole:
        return True
    if "action" in parole and "required" in parole:
        return True
    if len(pulito) <= 2:
        return True
    return False


def progetto_valido(nome: str | None) -> bool:
    """True solo per nomi che sembrano veri progetti, non titoli/placeholder UI."""
    return not _nome_generico(str(nome or ""))


def normalizza_progetto(nome: str | None) -> str | None:
    pulito = _pulito_nome(str(nome or ""))
    if _nome_generico(pulito):
        return None
    return pulito


def _inferisci_progetto_da_path(percorso: str) -> str | None:
    if not percorso:
        return None
    try:
        parti = [p for p in re.split(r"[\\/]+", percorso) if p]
        candidati = []
        for parte in parti[:-1]:
            basso = parte.lower().strip()
            if basso in _GENERICI_PROGETTO:
                continue
            if _nome_generico(parte):
                continue
            if re.match(r"^[a-z]:$", basso):
                continue
            if basso.startswith("."):
                continue
            candidati.append(parte)
        if candidati:
            return _pulito_nome(candidati[-1])
    except Exception:
        return None
    return None


def _inferisci_progetto_da_titolo(titolo: str) -> str | None:
    if not titolo:
        return None
    pezzi = re.split(r"\s+[-|]\s+|\s+-\s+| — ", titolo)
    candidati = []
    for pezzo in pezzi:
        if _nome_generico(pezzo):
            continue
        parole = [_pulito_nome(p).lower() for p in re.findall(r"[A-Za-z0-9_]{3,}", pezzo)]
        parole = [p for p in parole if p and p not in _STOP_TITOLO]
        if parole:
            candidati.append(_pulito_nome(pezzo))
    if candidati:
        return candidati[0][:80]
    return None


def _inferisci_progetto(tipo: str, titolo: str, riferimento: str, progetto: str | None) -> str | None:
    if progetto:
        return normalizza_progetto(progetto)
    if tipo == "file_visto":
        return _inferisci_progetto_da_path(riferimento)
    if tipo == "finestra_attiva":
        return _inferisci_progetto_da_titolo(titolo)
    if riferimento:
        return _inferisci_progetto_da_path(riferimento)
    return None


@dataclass(frozen=True)
class EventoCognitivo:
    tipo: str
    quando: str
    giorno: str
    origine: str = "argo"
    titolo: str = ""
    descrizione: str = ""
    riferimento: str = ""
    progetto: str | None = None
    esito: str | None = None
    rischio_livello: str | None = None
    dati: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def compatto(self) -> dict[str, Any]:
        return {
            "quando": self.quando,
            "ora": self.quando[11:19],
            "tipo": self.tipo,
            "titolo": self.titolo,
            "progetto": self.progetto,
            "esito": self.esito,
            "rischio_livello": self.rischio_livello,
            "riferimento": self.riferimento,
        }


def normalizza_evento(
    tipo: str,
    *,
    origine: str = "argo",
    titolo: str = "",
    descrizione: str = "",
    riferimento: str = "",
    progetto: str | None = None,
    esito: str | None = None,
    rischio_livello: str | None = None,
    dati: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    quando: Any = None,
) -> EventoCognitivo:
    """Normalizza un evento grezzo nel formato cognitivo unico."""
    tipo_norm = str(tipo or "").strip().lower()
    alias = {
        "file": "file_visto",
        "file_aggiunto": "file_visto",
        "finestra": "finestra_attiva",
        "window": "finestra_attiva",
        "messaggio": "chat",
        "azione_confermata": "azione",
        "azione_rifiutata": "azione",
        "sensibile": "rischio",
        "sensibile_ignorato": "rischio",
        "argo": "sistema",
    }
    tipo_norm = alias.get(tipo_norm, tipo_norm)
    if tipo_norm not in TIPI_EVENTO:
        # tollerante: non scartiamo mai un evento, lo registriamo come 'sistema'
        tipo_norm = "sistema"

    dt = _parse_quando(quando)
    titolo = _redigi(titolo)
    descrizione = _redigi(descrizione)
    riferimento = _redigi(riferimento)
    progetto_norm = _inferisci_progetto(tipo_norm, titolo, riferimento, progetto)
    tag_norm = sorted({str(t).strip().lower() for t in (tags or []) if str(t).strip()})

    return EventoCognitivo(
        tipo=tipo_norm,
        quando=dt.isoformat(timespec="seconds"),
        giorno=dt.date().isoformat(),
        origine=_redigi(origine)[:80] or "argo",
        titolo=titolo[:240],
        descrizione=descrizione[:1000],
        riferimento=riferimento[:500],
        progetto=progetto_norm,
        esito=_redigi(esito)[:80] if esito else None,
        rischio_livello=_redigi(rischio_livello)[:40] if rischio_livello else None,
        dati=dati or {},
        tags=tag_norm,
    )


class TimelineCognitiva:
    """Storage e inferenza della giornata, isolati dal motore principale."""

    def __init__(self, percorso: str | None = None):
        if percorso is None:
            percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "argo_cognizione.db")
        self.percorso = percorso
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._crea_schema()

    def _crea_schema(self) -> None:
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS eventi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quando TEXT NOT NULL,
                giorno TEXT NOT NULL,
                tipo TEXT NOT NULL,
                origine TEXT NOT NULL,
                titolo TEXT,
                descrizione TEXT,
                riferimento TEXT,
                progetto TEXT,
                esito TEXT,
                rischio_livello TEXT,
                dati_json TEXT,
                tags_json TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_cog_eventi_giorno ON eventi(giorno, quando)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cog_eventi_tipo ON eventi(tipo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cog_eventi_progetto ON eventi(progetto)")
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS consolidamenti (
                giorno TEXT PRIMARY KEY,
                creato TEXT NOT NULL,
                sintesi TEXT,
                riepilogo_json TEXT
            )
            """
        )
        self.conn.commit()

    def registra(
        self,
        tipo: str,
        descrizione: str = "",
        origine: str = "argo",
        entita: str = "",
        progetto: str | None = None,
        meta: dict[str, Any] | None = None,
        **campi: Any,
    ) -> int:
        if descrizione and "descrizione" not in campi:
            campi["descrizione"] = descrizione
        campi.setdefault("origine", origine)
        if entita and "titolo" not in campi:
            campi["titolo"] = entita
        if progetto and "progetto" not in campi:
            campi["progetto"] = progetto
        if meta:
            dati = dict(campi.get("dati") or {})
            dati.update(meta)
            campi["dati"] = dati
        evento = normalizza_evento(tipo, **campi)
        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO eventi (
                quando, giorno, tipo, origine, titolo, descrizione, riferimento,
                progetto, esito, rischio_livello, dati_json, tags_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                evento.quando,
                evento.giorno,
                evento.tipo,
                evento.origine,
                evento.titolo,
                evento.descrizione,
                evento.riferimento,
                evento.progetto,
                evento.esito,
                evento.rischio_livello,
                json.dumps(evento.dati, ensure_ascii=True, sort_keys=True),
                json.dumps(evento.tags, ensure_ascii=True),
            ),
        )
        self.conn.commit()
        return int(c.lastrowid)

    def registra_file(self, percorso: str, *, quando: Any = None, progetto: str | None = None, **dati: Any) -> int:
        titolo = os.path.basename(percorso) or percorso
        return self.registra(
            "file_visto",
            origine="filesystem",
            titolo=titolo,
            riferimento=percorso,
            progetto=progetto,
            dati=dati,
            quando=quando,
        )

    def registra_sensi(self, snapshot: dict[str, Any]) -> int | None:
        if not isinstance(snapshot, dict):
            return None
        titolo = snapshot.get("finestra_attiva")
        appunti = snapshot.get("appunti") or {}
        dati = {
            "rete_attiva": bool(snapshot.get("rete_attiva")),
            "appunti_ha_testo": bool(appunti.get("ha_testo")),
            "appunti_sospetto_sensibile": bool(appunti.get("sospetto_sensibile")),
        }
        if titolo:
            return self.registra_finestra(str(titolo), **dati)
        return self.registra("finestra_attiva", titolo="nessuna finestra attiva", origine="sensi", dati=dati)

    def registra_finestra(self, titolo: str, *, quando: Any = None, **dati: Any) -> int:
        return self.registra(
            "finestra_attiva",
            origine="sensi",
            titolo=titolo,
            dati=dati,
            quando=quando,
        )

    def registra_chat(self, testo: str, *, ruolo: str = "utente", quando: Any = None) -> int:
        return self.registra(
            "chat",
            origine="chat",
            titolo=f"chat:{ruolo}",
            descrizione=testo,
            dati={"ruolo": ruolo},
            quando=quando,
        )

    def registra_azione(
        self,
        titolo: str,
        *,
        riferimento: str = "",
        esito: str = "proposta",
        progetto: str | None = None,
        quando: Any = None,
        **dati: Any,
    ) -> int:
        return self.registra(
            "azione",
            origine="motore",
            titolo=titolo,
            riferimento=riferimento,
            esito=esito,
            progetto=progetto,
            dati=dati,
            quando=quando,
        )

    def registra_rischio(
        self,
        descrizione: str,
        *,
        livello: str = "medio",
        riferimento: str = "",
        quando: Any = None,
        **dati: Any,
    ) -> int:
        return self.registra(
            "rischio",
            origine="sicurezza",
            titolo="rischio rilevato",
            descrizione=descrizione,
            riferimento=riferimento,
            rischio_livello=livello,
            dati=dati,
            tags=["sicurezza"],
            quando=quando,
        )

    def eventi_giorno(self, giorno: str | _dt.date | None = None, limite: int = 1000) -> list[dict[str, Any]]:
        giorno_s = self._giorno(giorno)
        c = self.conn.cursor()
        c.execute(
            "SELECT * FROM eventi WHERE giorno=? ORDER BY quando ASC, id ASC LIMIT ?",
            (giorno_s, int(limite)),
        )
        return [self._riga(r) for r in c.fetchall()]

    def eventi_oggi(self, limite: int = 120) -> list[dict[str, Any]]:
        eventi = self.eventi_giorno(None, limite)
        eventi.sort(key=lambda e: (e.get("quando", ""), e.get("id", 0)), reverse=True)
        return eventi

    def recenti(self, limite: int = 80) -> list[dict[str, Any]]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM eventi ORDER BY quando DESC, id DESC LIMIT ?", (int(limite),))
        return [self._riga(r) for r in c.fetchall()]

    def timeline_giorno(self, giorno: str | _dt.date | None = None) -> list[dict[str, Any]]:
        return [EventoCognitivo(**self._evento_kwargs(e)).compatto() for e in self.eventi_giorno(giorno)]

    def riepilogo_giorno(self, giorno: str | _dt.date | None = None) -> dict[str, Any]:
        giorno_s = self._giorno(giorno)
        eventi = self.eventi_giorno(giorno_s)
        conteggi: dict[str, int] = {}
        for e in eventi:
            conteggi[e["tipo"]] = conteggi.get(e["tipo"], 0) + 1
        inferenze = self.inferisci_giorno(giorno_s)
        return {
            "giorno": giorno_s,
            "eventi": len(eventi),
            "conteggi": conteggi,
            "progetti": inferenze["progetti"],
            "pattern": inferenze["pattern"],
            "lacune": inferenze["lacune"],
            "suggerimenti": inferenze["suggerimenti"],
            "timeline": self.timeline_giorno(giorno_s),
        }

    def pattern_oggi(self) -> dict[str, Any]:
        r = self.riepilogo_giorno()
        progetti = {p["nome"]: p["eventi"] for p in r.get("progetti", [])}
        finestre: dict[str, int] = {}
        categorie: dict[str, int] = {}
        parole: dict[str, int] = {}
        for e in self.eventi_giorno(None, 500):
            if e.get("tipo") == "finestra_attiva" and e.get("titolo"):
                finestre[e["titolo"]] = finestre.get(e["titolo"], 0) + 1
            dati = e.get("dati") or {}
            cat = dati.get("categoria")
            if cat:
                categorie[str(cat)] = categorie.get(str(cat), 0) + 1
            testo = " ".join(str(x or "") for x in [e.get("titolo"), e.get("descrizione"), e.get("progetto")])
            for p in re.findall(r"[A-Za-z0-9_]{4,}", testo.lower()):
                if p not in _STOP_TITOLO and p not in _GENERICI_PROGETTO:
                    parole[p] = parole.get(p, 0) + 1
        return {
            "giorno": r["giorno"],
            "eventi": r["eventi"],
            "tipi": r.get("conteggi", {}),
            "progetti": dict(sorted(progetti.items(), key=lambda x: (-x[1], x[0]))[:8]),
            "finestre": dict(sorted(finestre.items(), key=lambda x: (-x[1], x[0]))[:8]),
            "categorie": dict(sorted(categorie.items(), key=lambda x: (-x[1], x[0]))[:8]),
            "parole": [k for k, _ in sorted(parole.items(), key=lambda x: (-x[1], x[0]))[:12]],
        }

    def lacune_oggi(self) -> list[str]:
        r = self.riepilogo_giorno()
        out: list[str] = []
        for lacuna in r.get("lacune", []):
            if isinstance(lacuna, dict):
                out.append(str(lacuna.get("messaggio") or lacuna.get("tipo") or lacuna))
            else:
                out.append(str(lacuna))
        return out

    def consolida_oggi(self) -> dict[str, Any]:
        r = self.riepilogo_giorno()
        lacune = self.lacune_oggi()
        sintesi = self._sintesi_da_riepilogo(r)
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO consolidamenti (giorno,creato,sintesi,riepilogo_json) VALUES (?,?,?,?) "
            "ON CONFLICT(giorno) DO UPDATE SET creato=excluded.creato, "
            "sintesi=excluded.sintesi, riepilogo_json=excluded.riepilogo_json",
            (
                r["giorno"],
                _ora().isoformat(timespec="seconds"),
                sintesi,
                json.dumps(r, ensure_ascii=True, sort_keys=True),
            ),
        )
        self.conn.commit()
        return {"sintesi": sintesi, "pattern": self.pattern_oggi(), "lacune": lacune, "riepilogo": r}

    def ultimo_consolidamento(self, giorno: str | _dt.date | None = None) -> dict[str, Any] | None:
        giorno_s = self._giorno(giorno)
        c = self.conn.cursor()
        c.execute("SELECT * FROM consolidamenti WHERE giorno=?", (giorno_s,))
        r = c.fetchone()
        if not r:
            return None
        d = dict(r)
        try:
            d["riepilogo"] = json.loads(d.pop("riepilogo_json") or "{}")
        except Exception:
            d["riepilogo"] = {}
        progetti = []
        for p in d["riepilogo"].get("progetti", []) or []:
            if isinstance(p, dict):
                nome = normalizza_progetto(p.get("nome"))
                if nome:
                    p = dict(p)
                    p["nome"] = nome
                    progetti.append(p)
        d["riepilogo"]["progetti"] = progetti
        timeline = []
        for evento in d["riepilogo"].get("timeline", []) or []:
            if isinstance(evento, dict):
                evento = dict(evento)
                evento["progetto"] = normalizza_progetto(evento.get("progetto"))
            timeline.append(evento)
        d["riepilogo"]["timeline"] = timeline
        d["riepilogo"]["suggerimenti"] = [
            s for s in (d["riepilogo"].get("suggerimenti", []) or [])
            if "action required" not in str(s).lower()
        ]
        if "action required" in str(d.get("sintesi", "")).lower():
            d["sintesi"] = self._sintesi_da_riepilogo(d["riepilogo"])
        return d

    def contesto_chat(self) -> str:
        p = self.pattern_oggi()
        cons = self.ultimo_consolidamento()
        righe = [
            "Timeline cognitiva di oggi:",
            f"- eventi cognitivi: {p.get('eventi', 0)}",
        ]
        if p.get("tipi"):
            righe.append("- tipi: " + ", ".join(f"{k}={v}" for k, v in list(p["tipi"].items())[:8]))
        if p.get("progetti"):
            righe.append("- progetti probabili: " + ", ".join(p["progetti"].keys()))
        if p.get("finestre"):
            righe.append("- finestre viste: " + ", ".join(list(p["finestre"].keys())[:5]))
        if cons:
            righe.append("- ultimo consolidamento: " + cons.get("sintesi", ""))
        lacune = self.lacune_oggi()
        if lacune:
            righe.append("- lacune note: " + " | ".join(lacune[:3]))
        return "\n".join(righe)

    def inferisci_giorno(self, giorno: str | _dt.date | None = None) -> dict[str, Any]:
        eventi = self.eventi_giorno(giorno)
        progetti: dict[str, dict[str, Any]] = {}
        tipi: dict[str, int] = {}
        azioni: dict[str, int] = {}
        finestre: dict[str, int] = {}
        ore: dict[str, int] = {}
        estensioni: dict[str, int] = {}
        senza_progetto = 0
        rischi = 0

        for e in eventi:
            tipi[e["tipo"]] = tipi.get(e["tipo"], 0) + 1
            ora = str(e["quando"])[11:13]
            ore[ora] = ore.get(ora, 0) + 1
            progetto = e.get("progetto")
            if progetto and not _nome_generico(progetto):
                p = progetti.setdefault(progetto, {"nome": progetto, "eventi": 0, "tipi": {}, "riferimenti": set()})
                p["eventi"] += 1
                p["tipi"][e["tipo"]] = p["tipi"].get(e["tipo"], 0) + 1
                if e.get("riferimento"):
                    p["riferimenti"].add(e["riferimento"])
            else:
                senza_progetto += 1

            if e["tipo"] == "azione":
                titolo = e.get("titolo") or "azione"
                azioni[titolo] = azioni.get(titolo, 0) + 1
            elif e["tipo"] == "finestra_attiva":
                titolo = e.get("titolo") or "finestra"
                finestre[titolo] = finestre.get(titolo, 0) + 1
            elif e["tipo"] == "file_visto":
                ext = os.path.splitext(e.get("riferimento") or e.get("titolo") or "")[1].lower()
                if ext:
                    estensioni[ext] = estensioni.get(ext, 0) + 1
            elif e["tipo"] == "rischio":
                rischi += 1

        progetti_lista = []
        for p in progetti.values():
            progetti_lista.append(
                {
                    "nome": p["nome"],
                    "eventi": p["eventi"],
                    "tipi": dict(sorted(p["tipi"].items())),
                    "riferimenti": len(p["riferimenti"]),
                }
            )
        progetti_lista.sort(key=lambda p: (-p["eventi"], p["nome"].lower()))

        pattern = self._costruisci_pattern(tipi, azioni, finestre, ore, estensioni, rischi)
        lacune = self._costruisci_lacune(len(eventi), senza_progetto, tipi)
        suggerimenti = self._costruisci_suggerimenti(progetti_lista, pattern, lacune, rischi)
        return {
            "progetti": progetti_lista,
            "pattern": pattern,
            "lacune": lacune,
            "suggerimenti": suggerimenti,
        }

    def cerca(self, testo: str, limite: int = 50) -> list[dict[str, Any]]:
        like = f"%{testo}%"
        c = self.conn.cursor()
        c.execute(
            """
            SELECT * FROM eventi
            WHERE titolo LIKE ? OR descrizione LIKE ? OR riferimento LIKE ? OR progetto LIKE ?
            ORDER BY quando DESC, id DESC LIMIT ?
            """,
            (like, like, like, like, int(limite)),
        )
        return [self._riga(r) for r in c.fetchall()]

    def chiudi(self) -> None:
        self.conn.close()

    @staticmethod
    def _giorno(giorno: str | _dt.date | None) -> str:
        if giorno is None:
            return _dt.date.today().isoformat()
        if isinstance(giorno, _dt.date):
            return giorno.isoformat()
        return str(giorno)[:10]

    @staticmethod
    def _riga(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        try:
            d["dati"] = json.loads(d.pop("dati_json") or "{}")
        except Exception:
            d["dati"] = {}
        try:
            d["tags"] = json.loads(d.pop("tags_json") or "[]")
        except Exception:
            d["tags"] = []
        d["progetto"] = normalizza_progetto(d.get("progetto"))
        return d

    @staticmethod
    def _sintesi_da_riepilogo(r: dict[str, Any]) -> str:
        tipi = r.get("conteggi", {}) or {}
        progetti = [
            p for p in (r.get("progetti", []) or [])
            if isinstance(p, dict) and progetto_valido(p.get("nome"))
        ]
        lacune = r.get("lacune", []) or []
        parti = [f"Oggi ho registrato {r.get('eventi', 0)} eventi cognitivi."]
        if tipi:
            parti.append("Tipi principali: " + ", ".join(f"{k}:{v}" for k, v in list(tipi.items())[:5]) + ".")
        if progetti:
            parti.append("Progetti probabili: " + ", ".join(p["nome"] for p in progetti[:4]) + ".")
        if lacune:
            testi = []
            for lacuna in lacune[:3]:
                if isinstance(lacuna, dict):
                    testi.append(str(lacuna.get("messaggio") or lacuna.get("tipo") or lacuna))
                else:
                    testi.append(str(lacuna))
            parti.append("Lacune: " + " | ".join(testi))
        return " ".join(parti)

    @staticmethod
    def _evento_kwargs(e: dict[str, Any]) -> dict[str, Any]:
        return {
            "tipo": e["tipo"],
            "quando": e["quando"],
            "giorno": e["giorno"],
            "origine": e.get("origine") or "argo",
            "titolo": e.get("titolo") or "",
            "descrizione": e.get("descrizione") or "",
            "riferimento": e.get("riferimento") or "",
            "progetto": e.get("progetto"),
            "esito": e.get("esito"),
            "rischio_livello": e.get("rischio_livello"),
            "dati": e.get("dati") or {},
            "tags": e.get("tags") or [],
        }

    @staticmethod
    def _top(mappa: dict[str, int], minimo: int = 1, limite: int = 5) -> list[tuple[str, int]]:
        return sorted([(k, v) for k, v in mappa.items() if v >= minimo], key=lambda x: (-x[1], x[0]))[:limite]

    def _costruisci_pattern(
        self,
        tipi: dict[str, int],
        azioni: dict[str, int],
        finestre: dict[str, int],
        ore: dict[str, int],
        estensioni: dict[str, int],
        rischi: int,
    ) -> list[dict[str, Any]]:
        pattern: list[dict[str, Any]] = []
        for nome, n in self._top(azioni, minimo=2):
            pattern.append({"tipo": "azione_ripetuta", "chiave": nome, "conteggio": n})
        for nome, n in self._top(finestre, minimo=3):
            pattern.append({"tipo": "focus_finestra", "chiave": nome, "conteggio": n})
        for ext, n in self._top(estensioni, minimo=3):
            pattern.append({"tipo": "formato_frequente", "chiave": ext, "conteggio": n})
        for ora, n in self._top(ore, minimo=5, limite=3):
            pattern.append({"tipo": "fascia_intensa", "chiave": f"{ora}:00", "conteggio": n})
        if rischi:
            pattern.append({"tipo": "rischi_rilevati", "chiave": "sicurezza", "conteggio": rischi})
        if tipi.get("chat", 0) >= 3:
            pattern.append({"tipo": "uso_chat", "chiave": "domande frequenti", "conteggio": tipi["chat"]})
        return pattern

    @staticmethod
    def _costruisci_lacune(totale: int, senza_progetto: int, tipi: dict[str, int]) -> list[dict[str, Any]]:
        lacune: list[dict[str, Any]] = []
        if totale and senza_progetto / max(1, totale) >= 0.35:
            lacune.append(
                {
                    "tipo": "classificazione_progetto",
                    "messaggio": "Molti eventi non hanno un progetto inferito.",
                    "conteggio": senza_progetto,
                }
            )
        if tipi.get("finestra_attiva", 0) and not tipi.get("file_visto", 0):
            lacune.append(
                {
                    "tipo": "contesto_file_mancante",
                    "messaggio": "Sono state viste finestre, ma pochi file collegati.",
                    "conteggio": tipi.get("finestra_attiva", 0),
                }
            )
        if tipi.get("chat", 0) and not (tipi.get("azione", 0) or tipi.get("file_visto", 0)):
            lacune.append(
                {
                    "tipo": "chat_non_fondata",
                    "messaggio": "Ci sono chat senza abbastanza fatti operativi collegati.",
                    "conteggio": tipi.get("chat", 0),
                }
            )
        return lacune

    @staticmethod
    def _costruisci_suggerimenti(
        progetti: list[dict[str, Any]],
        pattern: list[dict[str, Any]],
        lacune: list[dict[str, Any]],
        rischi: int,
    ) -> list[str]:
        suggerimenti: list[str] = []
        if progetti:
            p = progetti[0]
            suggerimenti.append(f"Preparare riepilogo progetto '{p['nome']}' con {p['eventi']} eventi.")
        if any(p["tipo"] == "azione_ripetuta" for p in pattern):
            suggerimenti.append("Valutare automazione per le azioni ripetute, sempre con policy e conferma.")
        if rischi:
            suggerimenti.append("Portare i rischi rilevati nel riepilogo sicurezza della giornata.")
        if lacune:
            suggerimenti.append("Nel sonno, proporre regole migliori per classificare gli eventi senza progetto.")
        return suggerimenti


if __name__ == "__main__":
    c = TimelineCognitiva()
    c.registra_file(r"C:\Users\Davide\Desktop\Argo\report.pdf")
    c.registra_finestra("ARGO - Visual Studio Code")
    c.registra_chat("cosa hai visto oggi?")
    c.registra_azione("proposta archiviazione", riferimento=r"C:\Users\Davide\Desktop\Argo\report.pdf")
    print(json.dumps(c.riepilogo_giorno(), indent=2, ensure_ascii=True))
    c.chiudi()
