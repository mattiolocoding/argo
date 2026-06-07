"""
ARGO - governo/agenti.py  (AGENTI specializzati: pochi e utili)
Non mille agenti finti. Una piccola squadra reale, ognuno con un compito:

  Diagnostico  -> stato del sistema (disco, processi)
  Auditor      -> verifica l'audit e ne riassume lo stato
  Guardiano    -> quanti file sensibili sono stati protetti
  Archivista   -> quante proposte di riordino sono in attesa
  Analista     -> stato della conoscenza (grafo + memoria semantica)

Ogni agente ha esegui(motore) e ritorna un report testuale.
Solo libreria standard.
"""

import sistema


class Agente:
    def __init__(self, nome, ruolo, fn):
        self.nome = nome
        self.ruolo = ruolo
        self._fn = fn

    def esegui(self, motore):
        try:
            return self._fn(motore)
        except Exception as e:
            return f"{self.nome}: errore ({e})"


def _diagnostico(m):
    d = sistema.disco()
    proc = sistema.processi_top(3)
    top = ", ".join(p["nome"] for p in proc) if proc else "n/d"
    if "errore" in d:
        return "Diagnostico: stato disco non disponibile."
    return (f"Diagnostico: {d['libero_gb']} GB liberi ({d['perc_usato']}% usato). "
            f"Processi pesanti: {top}.")


def _auditor(m):
    ok, idr = m.audit.verifica()
    n = len(m.audit.recenti(1000))
    if ok:
        return f"Auditor: catena audit INTEGRA su {n} voci. Nessuna manomissione."
    return f"Auditor: ATTENZIONE, audit alterato alla voce {idr}."


def _guardiano(m):
    n = sum(1 for v in m.audit.recenti(1000) if v.get("evento") == "sensibile_ignorato")
    return f"Guardiano: ho protetto {n} file sensibili (mai letti né spostati)."


def _archivista(m):
    inattesa = 1 if m.proposta else 0
    return (f"Archivista: {len(m.coda)} proposte in coda, {inattesa} in attesa di "
            f"conferma. Cartelle sorvegliate: {len(m.cartelle)}.")


def _analista(m):
    g = m.grafo.statistiche()
    sem = 0
    try:
        sem = m.semantica.conta()
    except Exception:
        pass
    return (f"Analista: conoscenza = grafo con {g['nodi']} nodi e {g['archi']} relazioni, "
            f"{sem} ricordi semantici.")


class RegistroAgenti:
    def __init__(self):
        self.agenti = {
            "Diagnostico": Agente("Diagnostico", "diagnostico", _diagnostico),
            "Auditor": Agente("Auditor", "auditor", _auditor),
            "Guardiano": Agente("Guardiano", "guardiano", _guardiano),
            "Archivista": Agente("Archivista", "archivista", _archivista),
            "Analista": Agente("Analista", "analista", _analista),
        }

    def nomi(self):
        return list(self.agenti.keys())

    def esegui(self, nome, motore):
        a = self.agenti.get(nome)
        if not a:
            return f"Agente «{nome}» non trovato."
        return a.esegui(motore)
