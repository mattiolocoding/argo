"""
ARGO - memoria/consolidamento.py
Consolidamento deterministico della memoria: trasforma episodi e audit recenti
in una sintesi giornaliera, pattern e lacune candidate.

Non attiva skill e non esegue azioni. Produce solo dati fondati sui log locali.
"""

import datetime
import json
import os
import re
from collections import Counter


TIPI_AZIONE = {"azione", "azione_confermata"}
TIPI_RIFIUTO = {"azione_rifiutata"}
TIPI_ERRORE = {"errore", "azione_fallita"}
EVENTI_AZIONE = {"azione", "conferma_si", "annulla"}
EVENTI_RIFIUTO = {"conferma_no"}
EVENTI_ERRORE = {"errore", "policy_blocca"}


def _oggi():
    return datetime.date.today().isoformat()


def _redigi(testo):
    try:
        from sicurezza import redigi
        return redigi(str(testo))
    except Exception:
        return str(testo)


def _solo_giorno(voci, giorno):
    out = []
    for voce in voci or []:
        quando = str(voce.get("quando", ""))
        if quando.startswith(giorno):
            out.append(dict(voce))
    return out


def _normalizza_testo(testo, limite=120):
    testo = _redigi(testo or "")
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo[:limite]


def _leggi_episodi(memoria, limite):
    if memoria is None or not hasattr(memoria, "ricordi_recenti"):
        return []
    return memoria.ricordi_recenti(limite)


def _leggi_audit(audit, limite):
    if audit is None or not hasattr(audit, "recenti"):
        return []
    return audit.recenti(limite)


def _estrai_estensione(testo):
    m = re.search(r"(\.[A-Za-z0-9]{2,8})\b", testo or "")
    return m.group(1).lower() if m else ""


def _top(counter, n=5):
    return [{"valore": k, "conteggio": v} for k, v in counter.most_common(n)]


def _pattern_da_ripetizioni(episodi, audit_voci):
    pattern = []

    rifiuti = Counter()
    errori = Counter()
    estensioni_problematiche = Counter()

    for e in episodi:
        tipo = e.get("tipo")
        dettaglio = _normalizza_testo(e.get("dettaglio", ""))
        if not dettaglio:
            continue
        if tipo in TIPI_RIFIUTO:
            rifiuti[dettaglio] += 1
        if tipo in TIPI_ERRORE:
            errori[dettaglio] += 1
            ext = _estrai_estensione(dettaglio)
            if ext:
                estensioni_problematiche[ext] += 1

    for a in audit_voci:
        evento = a.get("evento")
        dettaglio = _normalizza_testo(a.get("dettaglio", ""))
        if not dettaglio:
            continue
        if evento in EVENTI_RIFIUTO:
            rifiuti[dettaglio] += 1
        if evento in EVENTI_ERRORE:
            errori[dettaglio] += 1
            ext = _estrai_estensione(dettaglio)
            if ext:
                estensioni_problematiche[ext] += 1

    for dettaglio, n in rifiuti.items():
        if n >= 2:
            pattern.append({
                "tipo": "rifiuto_ripetuto",
                "descrizione": f"Azione rifiutata piu' volte: {dettaglio}",
                "conteggio": n,
            })

    for dettaglio, n in errori.items():
        if n >= 2:
            pattern.append({
                "tipo": "errore_ricorrente",
                "descrizione": f"Errore ricorrente: {dettaglio}",
                "conteggio": n,
            })

    for ext, n in estensioni_problematiche.items():
        if n >= 2:
            pattern.append({
                "tipo": "formato_problematico",
                "descrizione": f"Formato con problemi ricorrenti: {ext}",
                "conteggio": n,
            })

    return pattern


def _pattern_da_volume(conteggi_episodi, conteggi_audit):
    pattern = []
    file_visti = conteggi_episodi.get("file_aggiunto", 0)
    sensibili = conteggi_audit.get("sensibile_ignorato", 0)
    blocchi_policy = conteggi_audit.get("policy_blocca", 0)

    if file_visti > 10:
        pattern.append({
            "tipo": "accumulo_file_giornaliero",
            "descrizione": "Molti file visti nello stesso giorno: valutare archiviazione batch.",
            "conteggio": file_visti,
        })
    if sensibili > 0:
        pattern.append({
            "tipo": "sensibili_osservati",
            "descrizione": "File sensibili incontrati e lasciati intatti.",
            "conteggio": sensibili,
        })
    if blocchi_policy > 0:
        pattern.append({
            "tipo": "policy_ricorrente",
            "descrizione": "Policy di governo intervenuta su azioni rischiose.",
            "conteggio": blocchi_policy,
        })
    return pattern


def _lacune_da_pattern(pattern):
    lacune = []
    tipi_utili = {
        "rifiuto_ripetuto",
        "errore_ricorrente",
        "formato_problematico",
        "accumulo_file_giornaliero",
    }
    for p in pattern:
        if p.get("tipo") not in tipi_utili:
            continue
        lacune.append({
            "tipo": p["tipo"],
            "descrizione": p["descrizione"],
            "conteggio": p.get("conteggio", 1),
        })
    return lacune


def consolida_giornata(memoria, audit=None, timeline=None, giorno=None,
                       limite_episodi=500, limite_audit=500, salva=False):
    """
    Legge episodi, audit e una eventuale timeline esterna e ritorna un pacchetto
    di consolidamento fondato sui dati reali.
    """
    giorno = giorno or _oggi()
    episodi = _solo_giorno(_leggi_episodi(memoria, limite_episodi), giorno)
    audit_voci = _solo_giorno(_leggi_audit(audit, limite_audit), giorno)
    timeline = _solo_giorno(timeline or [], giorno)

    conteggi_episodi = Counter(e.get("tipo", "") for e in episodi)
    conteggi_audit = Counter(a.get("evento", "") for a in audit_voci)

    azioni = sum(conteggi_episodi.get(t, 0) for t in TIPI_AZIONE)
    azioni += sum(conteggi_audit.get(t, 0) for t in EVENTI_AZIONE)
    rifiuti = sum(conteggi_episodi.get(t, 0) for t in TIPI_RIFIUTO)
    rifiuti += sum(conteggi_audit.get(t, 0) for t in EVENTI_RIFIUTO)
    errori = sum(conteggi_episodi.get(t, 0) for t in TIPI_ERRORE)
    errori += sum(conteggi_audit.get(t, 0) for t in EVENTI_ERRORE)

    dettagli = Counter()
    for voce in episodi:
        d = _normalizza_testo(voce.get("dettaglio", ""))
        if d:
            dettagli[d] += 1
    for voce in audit_voci:
        d = _normalizza_testo(voce.get("dettaglio", ""))
        if d:
            dettagli[d] += 1

    pattern = []
    pattern.extend(_pattern_da_ripetizioni(episodi, audit_voci))
    pattern.extend(_pattern_da_volume(conteggi_episodi, conteggi_audit))

    lacune = _lacune_da_pattern(pattern)
    sintesi = (
        f"Consolidamento {giorno}: {len(episodi)} episodi, "
        f"{len(audit_voci)} voci audit, {azioni} azioni, "
        f"{rifiuti} rifiuti, {errori} errori/blocchi, "
        f"{len(pattern)} pattern."
    )

    risultato = {
        "giorno": giorno,
        "sintesi": sintesi,
        "conteggi_episodi": dict(conteggi_episodi),
        "conteggi_audit": dict(conteggi_audit),
        "timeline_eventi": len(timeline),
        "top_dettagli": _top(dettagli),
        "pattern": pattern,
        "lacune": lacune,
    }

    if salva and memoria is not None:
        try:
            memoria.salva_profilo(
                f"consolidamento_sonno_{giorno}",
                json.dumps(risultato, ensure_ascii=False),
            )
            memoria.salva_profilo("ultimo_sonno_avanzato", datetime.datetime.now().isoformat(timespec="seconds"))
            memoria.ricorda("sonno_consolidato", sintesi, esito="ok")
        except Exception:
            pass

    return risultato


def formatta_report(consolidato):
    """Rende leggibile il pacchetto di consolidamento."""
    righe = [
        "Sintesi giornaliera:",
        f"  {consolidato.get('sintesi', '')}",
        "Pattern rilevati:",
    ]
    pattern = consolidato.get("pattern", [])
    if not pattern:
        righe.append("  Nessun pattern significativo.")
    else:
        for p in pattern[:10]:
            righe.append(
                f"  - [{p.get('tipo')}] {p.get('descrizione')} "
                f"(x{p.get('conteggio', 1)})"
            )

    lacune = consolidato.get("lacune", [])
    righe.append("Lacune candidate:")
    if not lacune:
        righe.append("  Nessuna lacuna candidata.")
    else:
        for l in lacune[:10]:
            righe.append(
                f"  - [{l.get('tipo')}] {l.get('descrizione')} "
                f"(x{l.get('conteggio', 1)})"
            )
    return "\n".join(righe)


if __name__ == "__main__":
    print("== Smoke-test consolidamento memoria ==")

    class MemoriaFinta:
        def __init__(self):
            self.profilo = {}
            self.episodi_scritti = []

        def ricordi_recenti(self, n=10):
            oggi = _oggi()
            return [
                {"quando": oggi + "T09:00:00", "tipo": "file_aggiunto", "dettaglio": "foto.heic", "esito": None},
                {"quando": oggi + "T09:01:00", "tipo": "azione_rifiutata", "dettaglio": "Conversione HEIC", "esito": None},
                {"quando": oggi + "T09:02:00", "tipo": "azione_rifiutata", "dettaglio": "Conversione HEIC", "esito": None},
            ]

        def salva_profilo(self, chiave, valore):
            self.profilo[chiave] = valore

        def ricorda(self, tipo, dettaglio="", esito=None):
            self.episodi_scritti.append((tipo, dettaglio, esito))

    class AuditFinto:
        def recenti(self, n=20):
            oggi = _oggi()
            return [
                {"quando": oggi + "T10:00:00", "evento": "conferma_no", "dettaglio": "Conversione HEIC"},
                {"quando": oggi + "T10:01:00", "evento": "sensibile_ignorato", "dettaglio": "password.txt"},
            ]

    m = MemoriaFinta()
    c = consolida_giornata(m, AuditFinto(), salva=True)
    print(formatta_report(c))
    assert c["lacune"], "Attesa almeno una lacuna candidata"
    assert m.episodi_scritti, "Il consolidamento deve scrivere un episodio"
    assert "ultimo_sonno_avanzato" in m.profilo
    print("OK consolidamento memoria")
