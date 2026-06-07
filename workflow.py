"""
ARGO - workflow.py
Motore di workflow multi-step con approval gate e tracciabilita' completa.

Concetti fondamentali:
  - Passo: unita' di lavoro atomica. Puo' richiedere approvazione umana prima
    di proseguire (approval gate).
  - Workflow: sequenza ordinata di Passi con un log immutabile per ogni
    esecuzione (audit trail).
  - MotoreWorkflow: registro centrale di tutti i workflow e delle esecuzioni
    in corso. Tiene lo stato di ogni istanza: in_corso /
    in_attesa_approvazione / completato / fallito.

Integrazione con il progetto ARGO:
  - Usa sicurezza.file_sensibile() per bloccare file sensibili.
  - Usa comprensione.Comprensione per capire il contenuto testuale del file.
  - Usa Cervello per estrarre dati strutturati in JSON e generare bozze.
  - Usa Mani per proporre e compiere spostamenti.
  - Usa sicurezza.Audit per registrare ogni passo nell'audit a catena di hash.
  - I workflow di esempio mostrano flussi reali con gate di approvazione.

API pubblica del MotoreWorkflow:
  motore.avvia(nome_workflow, parametri)  -> id_esecuzione (str)
  motore.stato(id_esecuzione)             -> dict con stato e dati chiave
  motore.approva(id_esecuzione)           -> dict con stato aggiornato
  motore.passi(id_esecuzione)             -> lista dei passi con il loro stato
  motore.log_completo(id_esecuzione)      -> audit trail completo

Solo libreria standard Python. Compatibile Windows e Linux.
"""

import os
import json
import uuid
import datetime
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Utilita' interne
# ---------------------------------------------------------------------------

def _ora() -> str:
    """Timestamp ISO con precisione al secondo."""
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Classe Passo
# ---------------------------------------------------------------------------

@dataclass
class Passo:
    """
    Un singolo passo di un workflow.

    Attributi:
        nome        : identificativo leggibile del passo.
        funzione    : callable(contesto: dict) -> dict.
                      Riceve il contesto corrente, lo arricchisce e lo
                      restituisce. NON deve avere effetti distruttivi.
        approvazione: se True il workflow si ferma DOPO questo passo e
                      aspetta la conferma umana prima di passare al
                      passo successivo.
        reversibile : indica se il passo puo' essere annullato (metadato).
    """
    nome: str
    funzione: Callable[[Dict], Dict]
    approvazione: bool = False
    reversibile: bool = True


# ---------------------------------------------------------------------------
# Classe Workflow
# ---------------------------------------------------------------------------

class Workflow:
    """
    Sequenza ordinata di Passi con log per audit e supporto agli
    approval gate.

    Uso tipico:
        wf = Workflow("mio_flusso", [passo1, passo2, passo3])
        ctx = wf.avvia({"file": "/tmp/doc.pdf"})
        if ctx["__stato"] == "in_attesa_approvazione":
            # mostro all'utente l'anteprima, aspetto conferma
            ctx = wf.riprendi(ctx)
    """

    def __init__(self, nome: str, passi: List[Passo]):
        self.nome = nome
        self.passi = passi

    # ------------------------------------------------------------------
    # Metodi pubblici principali
    # ------------------------------------------------------------------

    def avvia(self, contesto: Dict) -> Dict:
        """
        Avvia il workflow dall'inizio.
        Inizializza i metadati interni nel contesto e chiama _esegui_da().
        """
        ctx = dict(contesto)
        ctx["__workflow"] = self.nome
        ctx["__id_esecuzione"] = str(uuid.uuid4())[:8]
        ctx["__indice_passo"] = 0           # prossimo passo da eseguire
        ctx["__log"] = []                   # log immutabile (audit trail)
        ctx["__stato"] = "in_corso"
        ctx["__avviato"] = _ora()
        # registro degli stati per-passo: nome -> "ok" | "saltato" | "fallito" | "attesa"
        ctx["__stato_passi"] = {}
        return self._esegui_da(ctx)

    def riprendi(self, contesto: Dict) -> Dict:
        """
        Riprende il workflow da dove si era fermato (dopo approvazione).
        L'indice del passo successivo e' gia' salvato nel contesto.
        """
        ctx = dict(contesto)
        if ctx.get("__stato") != "in_attesa_approvazione":
            # nessun gate aperto: non c'e' nulla da riprendere
            ctx["__errore"] = "riprendi() chiamato ma lo stato non e' in_attesa_approvazione"
            return ctx
        # registra nel log che l'approvazione e' avvenuta
        self._log(ctx, "APPROVAZIONE", "approvazione umana ricevuta, riprendo il workflow")
        ctx["__stato"] = "in_corso"
        return self._esegui_da(ctx)

    # ------------------------------------------------------------------
    # Metodi interni
    # ------------------------------------------------------------------

    def _esegui_da(self, ctx: Dict) -> Dict:
        """Esegue i passi a partire da ctx['__indice_passo']."""
        while ctx["__indice_passo"] < len(self.passi):
            i = ctx["__indice_passo"]
            passo = self.passi[i]

            # --- esecuzione del singolo passo ---
            self._log(ctx, "AVVIO_PASSO", f"[{i+1}/{len(self.passi)}] {passo.nome}")
            try:
                ctx = passo.funzione(ctx)
            except Exception as exc:
                # qualsiasi eccezione imprevista blocca il workflow con stato fallito
                dettaglio = traceback.format_exc()
                self._log(ctx, "ERRORE_PASSO",
                          f"{passo.nome} ha sollevato un'eccezione: {exc}")
                ctx["__stato"] = "fallito"
                ctx["__errore"] = str(exc)
                ctx["__traceback"] = dettaglio
                ctx.setdefault("__stato_passi", {})[passo.nome] = "fallito"
                return ctx

            # aggiorna l'indice (lo spostamento e' ATOMICO prima del gate)
            ctx["__indice_passo"] = i + 1
            ctx.setdefault("__stato_passi", {})[passo.nome] = "ok"
            self._log(ctx, "PASSO_COMPLETATO", passo.nome)

            # --- approval gate: mi fermo in attesa di conferma umana ---
            if passo.approvazione and ctx["__indice_passo"] < len(self.passi):
                ctx["__stato"] = "in_attesa_approvazione"
                ctx["__gate_su"] = passo.nome
                # segna i passi rimanenti come "attesa"
                for j in range(ctx["__indice_passo"], len(self.passi)):
                    nome_futuro = self.passi[j].nome
                    if nome_futuro not in ctx.get("__stato_passi", {}):
                        ctx.setdefault("__stato_passi", {})[nome_futuro] = "attesa"
                self._log(ctx, "GATE_APPROVAZIONE",
                          f"in attesa di approvazione dopo '{passo.nome}'")
                return ctx

        # tutti i passi completati
        ctx["__stato"] = "completato"
        ctx["__completato"] = _ora()
        self._log(ctx, "WORKFLOW_COMPLETATO", self.nome)
        return ctx

    @staticmethod
    def _log(ctx: Dict, evento: str, dettaglio: str = "") -> None:
        """Aggiunge una voce immutabile al log interno del contesto."""
        if "__log" not in ctx:
            ctx["__log"] = []
        ctx["__log"].append({
            "quando": _ora(),
            "evento": evento,
            "dettaglio": dettaglio,
        })


# ---------------------------------------------------------------------------
# Classe MotoreWorkflow
# ---------------------------------------------------------------------------

class MotoreWorkflow:
    """
    Registro centrale di workflow e istanze in esecuzione.

    API pubblica (usata dal motore HTTP e dalla UI):
      avvia(nome_workflow, parametri)  -> id_esecuzione (str)
      stato(id_esecuzione)             -> dict riepilogativo
      approva(id_esecuzione)           -> dict riepilogativo aggiornato
      passi(id_esecuzione)             -> lista dei passi con stato
      log_completo(id_esecuzione)      -> lista di voci audit

    API di basso livello (compatibilita' interna):
      registra(workflow)
      avvia_ctx(nome_workflow, contesto) -> dict contesto completo
      riprendi_ctx(id_esecuzione, ...)   -> dict contesto completo
      tutte_istanze()                    -> lista dict riepilogativi
    """

    def __init__(self):
        # catalogo dei workflow disponibili: nome -> Workflow
        self._catalogo: Dict[str, Workflow] = {}
        # istanze in esecuzione / sospese / completate: id_esecuzione -> ctx
        self._istanze: Dict[str, Dict] = {}

    # ------------------------------------------------------------------
    # Registrazione
    # ------------------------------------------------------------------

    def registra(self, workflow: Workflow) -> None:
        """Aggiunge un workflow al catalogo."""
        self._catalogo[workflow.nome] = workflow

    # ------------------------------------------------------------------
    # API PUBBLICA (usata dal motore HTTP / UI)
    # ------------------------------------------------------------------

    def avvia(self, nome_workflow: str, parametri: Optional[Dict] = None) -> str:
        """
        Crea una nuova istanza del workflow e la avvia.
        Ritorna l'id_esecuzione (str) da usare con stato/approva/passi.
        Lancia ValueError se il workflow non esiste.
        """
        if nome_workflow not in self._catalogo:
            raise ValueError(f"Workflow '{nome_workflow}' non trovato nel catalogo.")
        wf = self._catalogo[nome_workflow]
        ctx = wf.avvia(parametri or {})
        eid = ctx["__id_esecuzione"]
        self._istanze[eid] = ctx
        return eid

    def stato(self, id_esecuzione: str) -> Optional[Dict]:
        """
        Ritorna un riepilogo leggibile dello stato dell'istanza.
        Contiene i dati chiave estratti dal contesto (senza i metadati interni).
        """
        ctx = self._istanze.get(id_esecuzione)
        if ctx is None:
            return None
        # dati chiave specifici del workflow documento_in_arrivo
        dati_chiave = {}
        for k in ("tipo_documento", "estensione", "bloccato", "riassunto_contenuto",
                  "categoria_contenuto", "dati_estratti", "bozza_report",
                  "nota_proposta", "risultato_archiviazione", "audit_registrato",
                  "dati_report", "testo_report", "report_salvato_in"):
            if k in ctx:
                dati_chiave[k] = ctx[k]
        return {
            "id": id_esecuzione,
            "workflow": ctx.get("__workflow"),
            "stato": ctx.get("__stato"),
            "gate_su": ctx.get("__gate_su"),
            "avviato": ctx.get("__avviato"),
            "completato": ctx.get("__completato"),
            "passo_corrente": ctx.get("__indice_passo"),
            "errore": ctx.get("__errore"),
            "n_voci_log": len(ctx.get("__log", [])),
            "dati": dati_chiave,
        }

    def approva(self, id_esecuzione: str) -> Dict:
        """
        Approva il gate aperto sull'istanza e riprende l'esecuzione.
        Ritorna il riepilogo aggiornato (stesso formato di stato()).
        Lancia ValueError se l'istanza non esiste o non e' in attesa.
        """
        if id_esecuzione not in self._istanze:
            raise ValueError(f"Istanza '{id_esecuzione}' non trovata.")
        ctx = self._istanze[id_esecuzione]
        if ctx.get("__stato") != "in_attesa_approvazione":
            raise ValueError(
                f"Istanza '{id_esecuzione}' non e' in attesa di approvazione "
                f"(stato attuale: {ctx.get('__stato')})."
            )
        nome_wf = ctx.get("__workflow")
        if nome_wf not in self._catalogo:
            raise ValueError(f"Workflow '{nome_wf}' non piu' nel catalogo.")
        wf = self._catalogo[nome_wf]
        ctx = wf.riprendi(ctx)
        self._istanze[id_esecuzione] = ctx
        return self.stato(id_esecuzione)

    def passi(self, id_esecuzione: str) -> List[Dict]:
        """
        Ritorna la lista dei passi del workflow con il loro stato corrente.
        Ogni voce: {nome, indice, approvazione, reversibile, stato}.
        """
        ctx = self._istanze.get(id_esecuzione)
        if ctx is None:
            return []
        nome_wf = ctx.get("__workflow")
        wf = self._catalogo.get(nome_wf)
        if wf is None:
            return []
        stati_passi = ctx.get("__stato_passi", {})
        indice_corrente = ctx.get("__indice_passo", 0)
        risultato = []
        for i, p in enumerate(wf.passi):
            if p.nome in stati_passi:
                stato_passo = stati_passi[p.nome]
            elif i < indice_corrente:
                stato_passo = "ok"
            elif i == indice_corrente and ctx.get("__stato") == "in_corso":
                stato_passo = "in_corso"
            else:
                stato_passo = "in_attesa"
            risultato.append({
                "nome": p.nome,
                "indice": i + 1,
                "approvazione": p.approvazione,
                "reversibile": p.reversibile,
                "stato": stato_passo,
            })
        return risultato

    # ------------------------------------------------------------------
    # API di basso livello (compatibilita' con il codice esistente)
    # ------------------------------------------------------------------

    def avvia_ctx(self, nome_workflow: str, contesto: Optional[Dict] = None) -> Dict:
        """
        Crea e avvia una nuova istanza. Ritorna il contesto completo.
        (compatibilita' con il vecchio metodo avvia() che restituiva ctx)
        """
        if nome_workflow not in self._catalogo:
            return {
                "__stato": "fallito",
                "__errore": f"Workflow '{nome_workflow}' non trovato nel catalogo.",
            }
        wf = self._catalogo[nome_workflow]
        ctx = wf.avvia(contesto or {})
        self._istanze[ctx["__id_esecuzione"]] = ctx
        return ctx

    def riprendi_ctx(self, id_esecuzione: str,
                     contesto_aggiornato: Optional[Dict] = None) -> Dict:
        """
        Riprende un'istanza sospesa. Ritorna il contesto completo.
        (compatibilita' con il vecchio metodo riprendi())
        """
        if id_esecuzione not in self._istanze:
            return {
                "__stato": "fallito",
                "__errore": f"Istanza '{id_esecuzione}' non trovata.",
            }
        ctx = contesto_aggiornato or self._istanze[id_esecuzione]
        nome_wf = ctx.get("__workflow")
        if nome_wf not in self._catalogo:
            return {
                "__stato": "fallito",
                "__errore": f"Workflow '{nome_wf}' non piu' nel catalogo.",
            }
        wf = self._catalogo[nome_wf]
        ctx = wf.riprendi(ctx)
        self._istanze[id_esecuzione] = ctx
        return ctx

    def tutte_istanze(self) -> List[Dict]:
        """Ritorna un riepilogo di tutte le istanze registrate."""
        return [self.stato(eid) for eid in self._istanze]

    def log_completo(self, id_esecuzione: str) -> List[Dict]:
        """Ritorna il log audit completo dell'istanza."""
        ctx = self._istanze.get(id_esecuzione)
        if ctx is None:
            return []
        return ctx.get("__log", [])


# ===========================================================================
# WORKFLOW 1: "documento_in_arrivo"
# Flusso governato end-to-end con gate di approvazione.
#
# Passi:
#   1. capisci_tipo            -> determina estensione/tipo (no gate)
#   2. blocca_se_sensibile     -> sicurezza.file_sensibile() (no gate, fallisce se sensibile)
#   3. capisci_contenuto       -> Comprensione: riassunto + categoria (solo file testuali)
#   4. estrai_dati_json        -> Cervello: estrae dati strutturati in JSON
#   5. genera_bozza_report     -> Cervello: bozza report in linguaggio naturale
#   6. proponi_archiviazione   -> Mani: piano di spostamento (GATE: attende approvazione)
#   7. archivia                -> Mani: esegue il piano approvato (irreversibile)
#   8. registra_audit          -> sicurezza.Audit: voce a catena di hash
# ===========================================================================

def _passo_capisci_tipo(ctx: Dict) -> Dict:
    """
    Determina il tipo del documento in base all'estensione.
    Legge ctx['percorso_file'] e aggiunge ctx['tipo_documento'], ctx['estensione'].
    """
    percorso = ctx.get("percorso_file", "")
    ext = os.path.splitext(percorso)[1].lower()
    mappa = {
        ".pdf": "documento",
        ".docx": "documento", ".doc": "documento",
        ".txt": "testo",
        ".md": "testo",
        ".jpg": "immagine", ".jpeg": "immagine", ".png": "immagine",
        ".xlsx": "foglio di calcolo", ".xls": "foglio di calcolo",
        ".py": "codice",
        ".js": "codice", ".ts": "codice",
        ".csv": "dati",
        ".json": "dati",
        ".env": "configurazione sensibile",
        ".key": "chiave crittografica",
    }
    ctx["tipo_documento"] = mappa.get(ext, "generico")
    ctx["estensione"] = ext
    return ctx


def _passo_blocca_se_sensibile(ctx: Dict) -> Dict:
    """
    Controlla se il file e' sensibile tramite sicurezza.file_sensibile().
    In caso affermativo imposta ctx['bloccato'] = True e lancia un'eccezione
    controllata che ferma il workflow con stato 'fallito'.
    Non si deve archiviare un file sensibile in modo automatico.
    """
    import sicurezza  # importato localmente per non creare dipendenze globali

    percorso = ctx.get("percorso_file", "")
    if sicurezza.file_sensibile(percorso):
        ctx["bloccato"] = True
        raise ValueError(
            f"File '{os.path.basename(percorso)}' classificato come SENSIBILE. "
            "Archiviazione automatica bloccata per sicurezza."
        )
    ctx["bloccato"] = False
    return ctx


def _passo_capisci_contenuto(ctx: Dict) -> Dict:
    """
    Usa comprensione.Comprensione per leggere e riassumere il contenuto del file.
    Funziona solo per file testuali (txt, md, csv, json, py, ecc.).
    Se il file non e' leggibile o il cervello e' offline, prosegue senza bloccarsi.
    Aggiunge: ctx['riassunto_contenuto'], ctx['categoria_contenuto'].
    """
    from comprensione import Comprensione, leggibile  # importato localmente

    percorso = ctx.get("percorso_file", "")
    ctx["riassunto_contenuto"] = None
    ctx["categoria_contenuto"] = None

    if not leggibile(percorso):
        ctx["nota_comprensione"] = (
            f"File non testuale ({ctx.get('estensione', '?')}): "
            "comprensione del contenuto saltata."
        )
        return ctx

    comp = Comprensione()
    risultato = comp.capisci(percorso)
    if risultato:
        ctx["riassunto_contenuto"] = risultato.get("riassunto")
        ctx["categoria_contenuto"] = risultato.get("categoria")
        ctx["nota_comprensione"] = "Contenuto analizzato con successo."
    else:
        ctx["nota_comprensione"] = (
            "Cervello offline o contenuto vuoto: comprensione saltata."
        )
    return ctx


def _passo_estrai_dati_json(ctx: Dict) -> Dict:
    """
    Usa il Cervello per estrarre dati strutturati dal file in formato JSON.
    Input: legge il testo del file (fino a 4000 caratteri per efficienza).
    Output: ctx['dati_estratti'] (dict con i dati chiave trovati).
    Se il cervello e' offline o il file non e' testuale, mette un dict vuoto.
    """
    from comprensione import leggibile
    from cervello import Cervello

    percorso = ctx.get("percorso_file", "")
    ctx["dati_estratti"] = {}

    if not leggibile(percorso):
        ctx["nota_estrazione"] = "Estrazione JSON saltata: file non testuale."
        return ctx

    try:
        with open(percorso, "r", encoding="utf-8", errors="ignore") as f:
            testo = f.read(4000)
    except Exception as e:
        ctx["nota_estrazione"] = f"Impossibile leggere il file: {e}"
        return ctx

    if not testo.strip():
        ctx["nota_estrazione"] = "File vuoto: nessun dato da estrarre."
        return ctx

    cervello = Cervello()
    if not cervello.vivo():
        ctx["nota_estrazione"] = "Cervello offline: estrazione JSON saltata."
        return ctx

    nome = os.path.basename(percorso)
    prompt = (
        f"Sei un estrattore di dati. Analizza questo documento chiamato «{nome}»:\n\n"
        f"{testo}\n\n"
        "Estrai i dati piu' importanti e restituiscili SOLO come oggetto JSON valido, "
        "senza testo aggiuntivo prima o dopo. Includi campi come: "
        "mittente, destinatario, data, oggetto, importo, scadenza, tipo_documento, "
        "parole_chiave (array). Usa null per i campi non presenti. "
        "Risposta: solo il JSON, niente altro."
    )

    risposta = cervello.pensa(prompt)

    # estrae il JSON dalla risposta (il LLM a volte aggiunge testo intorno)
    try:
        inizio = risposta.find("{")
        fine = risposta.rfind("}") + 1
        if inizio >= 0 and fine > inizio:
            json_str = risposta[inizio:fine]
            ctx["dati_estratti"] = json.loads(json_str)
            ctx["nota_estrazione"] = "Dati estratti con successo."
        else:
            ctx["dati_estratti"] = {"testo_grezzo": risposta}
            ctx["nota_estrazione"] = "Il cervello non ha restituito JSON valido: salvato come testo grezzo."
    except json.JSONDecodeError:
        ctx["dati_estratti"] = {"testo_grezzo": risposta}
        ctx["nota_estrazione"] = "JSON non parsabile: salvato come testo grezzo."

    return ctx


def _passo_genera_bozza_report(ctx: Dict) -> Dict:
    """
    Usa il Cervello per generare una bozza di report in linguaggio naturale
    a partire dai dati estratti e dal riassunto del contenuto.
    Output: ctx['bozza_report'] (stringa testo).
    Se il cervello e' offline, genera un report minimo deterministico.
    """
    from cervello import Cervello

    nome_file = os.path.basename(ctx.get("percorso_file", "documento sconosciuto"))
    tipo = ctx.get("tipo_documento", "generico")
    riassunto = ctx.get("riassunto_contenuto") or "Non disponibile"
    categoria = ctx.get("categoria_contenuto") or "Non classificato"
    dati = ctx.get("dati_estratti", {})

    # report minimo deterministico (fallback se cervello offline)
    def _report_deterministico():
        righe = [
            "=" * 60,
            f"BOZZA REPORT - {_ora()}",
            "=" * 60,
            f"File          : {nome_file}",
            f"Tipo          : {tipo}",
            f"Categoria     : {categoria}",
            f"Riassunto     : {riassunto}",
            "",
            "Dati estratti :",
        ]
        if dati:
            for k, v in dati.items():
                righe.append(f"  {k}: {v}")
        else:
            righe.append("  (nessun dato strutturato disponibile)")
        righe += ["", "Generato da ARGO in modalita' offline.", "=" * 60]
        return "\n".join(righe)

    cervello = Cervello()
    if not cervello.vivo():
        ctx["bozza_report"] = _report_deterministico()
        ctx["nota_report"] = "Cervello offline: bozza generata in modalita' deterministica."
        return ctx

    dati_str = json.dumps(dati, ensure_ascii=False, indent=2) if dati else "nessuno"
    prompt = (
        f"Sei ARGO, assistente di Davide. Genera una bozza di report professionale "
        f"in italiano per il documento «{nome_file}».\n\n"
        f"Tipo documento: {tipo}\n"
        f"Categoria: {categoria}\n"
        f"Riassunto contenuto: {riassunto}\n"
        f"Dati estratti:\n{dati_str}\n\n"
        "Scrivi un report chiaro, conciso (max 10 righe), adatto ad un archivio aziendale. "
        "Includi: intestazione con data, descrizione del documento, dati chiave, "
        "e una raccomandazione di archiviazione."
    )

    bozza = cervello.pensa(prompt)
    ctx["bozza_report"] = bozza if bozza else _report_deterministico()
    ctx["nota_report"] = "Bozza generata dal cervello."
    return ctx


def _passo_proponi_archiviazione(ctx: Dict) -> Dict:
    """
    Usa Mani.proponi_archiviazione() per generare un piano di spostamento.
    Applica anche la Policy di governo prima di proporre.
    Il piano viene salvato in ctx['piano'] per il passo successivo.
    Non esegue ancora nulla: e' solo una proposta (GATE).
    """
    from mani import Mani
    from governo import Policy

    percorso = ctx.get("percorso_file", "")
    radice = ctx.get("radice_cartella", os.path.dirname(percorso))
    regola = ctx.get("regola_archiviazione", "tipo")

    # verifica policy prima di proporre
    policy = Policy()
    categoria = ctx.get("categoria_contenuto") or ctx.get("tipo_documento", "")
    valutazione = policy.valuta("archivia", percorso, categoria)

    if valutazione["esito"] == "blocca":
        ctx["piano"] = None
        ctx["nota_proposta"] = (
            f"BLOCCATO dalla policy '{valutazione['regola']}': "
            f"{valutazione['motivo']}"
        )
        # blocco policy: il workflow si ferma qui (eccezione controllata)
        raise ValueError(
            f"Policy BLOCCA l'archiviazione di '{os.path.basename(percorso)}': "
            f"{valutazione['motivo']}"
        )

    if valutazione["esito"] == "escala":
        # escala: il gate si apre comunque, ma aggiunge un avviso
        ctx["avviso_policy"] = (
            f"Attenzione policy '{valutazione['regola']}': "
            f"{valutazione['motivo']}"
        )
    else:
        ctx["avviso_policy"] = None

    mani = Mani(radici=[radice])
    piano = mani.proponi_archiviazione(percorso, regola)

    if piano is None:
        ctx["piano"] = None
        ctx["nota_proposta"] = "Nessuna azione necessaria: il file e' gia' correttamente posizionato."
    else:
        ctx["piano"] = piano
        ctx["nota_proposta"] = piano.get("descrizione", "")

    return ctx


def _passo_archivia(ctx: Dict) -> Dict:
    """
    Esegue il piano di archiviazione precedentemente proposto e approvato.
    Se il piano e' None (file gia' in posizione), salta senza errori.
    Questo passo e' IRREVERSIBILE: il file viene spostato fisicamente.
    """
    from mani import Mani

    piano = ctx.get("piano")
    if piano is None:
        ctx["risultato_archiviazione"] = "saltato: nessun piano da eseguire"
        return ctx

    percorso = ctx.get("percorso_file", "")
    radice = ctx.get("radice_cartella", os.path.dirname(percorso))
    mani = Mani(radici=[radice])
    risultato = mani.esegui(piano)
    ctx["risultato_archiviazione"] = risultato.get("messaggio", str(risultato))
    if not risultato.get("ok", False):
        raise RuntimeError(f"Archiviazione fallita: {risultato.get('messaggio')}")
    return ctx


def _passo_registra_audit(ctx: Dict) -> Dict:
    """
    Registra l'evento di archiviazione nell'audit a catena di hash (sicurezza.Audit).
    Usa il percorso del db passato in ctx['percorso_db_audit'] oppure il default.
    Imposta ctx['audit_registrato'] = True al termine.
    """
    from sicurezza import Audit

    percorso_db = ctx.get("percorso_db_audit")
    audit = Audit(percorso_db)  # None -> default di sistema (memoria/argo_audit.db)

    nome_file = os.path.basename(ctx.get("percorso_file", "?"))
    tipo = ctx.get("tipo_documento", "?")
    esito_arch = ctx.get("risultato_archiviazione", "?")
    riassunto = ctx.get("riassunto_contenuto", "non analizzato")

    audit.registra(
        evento="workflow_documento_in_arrivo",
        dettaglio=(
            f"file={nome_file} | tipo={tipo} | "
            f"riassunto={riassunto} | archiviazione={esito_arch}"
        ),
    )
    audit.chiudi()
    ctx["audit_registrato"] = True
    return ctx


def crea_workflow_documento_in_arrivo() -> Workflow:
    """
    Costruisce il workflow "documento_in_arrivo".

    Flusso:
      1. capisci_tipo            -> determina estensione/tipo
      2. blocca_se_sensibile     -> stop se il file e' sensibile
      3. capisci_contenuto       -> Comprensione: riassunto + categoria (solo testuali)
      4. estrai_dati_json        -> Cervello: estrae dati strutturati
      5. genera_bozza_report     -> Cervello: bozza report in linguaggio naturale
      6. proponi_archiviazione   -> Mani + Policy: piano di spostamento [GATE]
      7. archivia                -> Mani: esegue il piano approvato (irreversibile)
      8. registra_audit          -> sicurezza.Audit: voce nella catena di hash
    """
    passi = [
        Passo(
            nome="capisci_tipo",
            funzione=_passo_capisci_tipo,
            reversibile=True,
        ),
        Passo(
            nome="blocca_se_sensibile",
            funzione=_passo_blocca_se_sensibile,
            reversibile=True,
        ),
        Passo(
            nome="capisci_contenuto",
            funzione=_passo_capisci_contenuto,
            reversibile=True,
        ),
        Passo(
            nome="estrai_dati_json",
            funzione=_passo_estrai_dati_json,
            reversibile=True,
        ),
        Passo(
            nome="genera_bozza_report",
            funzione=_passo_genera_bozza_report,
            reversibile=True,
        ),
        Passo(
            nome="proponi_archiviazione",
            funzione=_passo_proponi_archiviazione,
            approvazione=True,   # <-- GATE: mostra la proposta, aspetta ok umano
            reversibile=True,
        ),
        Passo(
            nome="archivia",
            funzione=_passo_archivia,
            reversibile=False,   # irreversibile: sposta il file
        ),
        Passo(
            nome="registra_audit",
            funzione=_passo_registra_audit,
            reversibile=True,
        ),
    ]
    return Workflow("documento_in_arrivo", passi)


# ===========================================================================
# WORKFLOW 2: "report_giornaliero"
# Passi: raccogli_dati -> componi_report -> salva_report
# Completamente deterministico: non richiede LLM ne' approvazione.
# ===========================================================================

def _passo_raccogli_dati(ctx: Dict) -> Dict:
    """
    Raccoglie in modo deterministico le informazioni per il report:
    - conta i file presenti nella cartella indicata in ctx['cartella']
    - suddivide per estensione
    - aggiunge data e ora del report
    """
    cartella = ctx.get("cartella", ".")
    conteggio: Dict[str, int] = {}
    totale = 0
    try:
        for nome in os.listdir(cartella):
            p = os.path.join(cartella, nome)
            if os.path.isfile(p):
                ext = os.path.splitext(nome)[1].lower() or "(nessuna)"
                conteggio[ext] = conteggio.get(ext, 0) + 1
                totale += 1
    except Exception as exc:
        ctx["errore_raccolta"] = str(exc)
        conteggio = {}
        totale = 0

    ctx["dati_report"] = {
        "cartella": cartella,
        "totale_file": totale,
        "per_estensione": conteggio,
        "generato": _ora(),
    }
    return ctx


def _passo_componi_report(ctx: Dict) -> Dict:
    """
    Compone il testo del report in italiano a partire dai dati raccolti.
    Puramente deterministico, nessuna chiamata a LLM.
    """
    dati = ctx.get("dati_report", {})
    righe = [
        "=" * 60,
        f"REPORT GIORNALIERO ARGO  --  {dati.get('generato', _ora())}",
        "=" * 60,
        f"Cartella analizzata : {dati.get('cartella', '?')}",
        f"Totale file trovati : {dati.get('totale_file', 0)}",
        "",
        "Distribuzione per estensione:",
    ]
    per_ext = dati.get("per_estensione", {})
    if per_ext:
        for ext, n in sorted(per_ext.items(), key=lambda x: -x[1]):
            righe.append(f"  {ext:<20} {n:>4} file")
    else:
        righe.append("  (nessun file trovato)")
    righe += ["", "=" * 60]
    ctx["testo_report"] = "\n".join(righe)
    return ctx


def _passo_salva_report(ctx: Dict) -> Dict:
    """
    Scrive il report in un file .txt nella cartella indicata da
    ctx['percorso_output_report']. Se non specificata usa la stessa
    cartella analizzata.
    """
    testo = ctx.get("testo_report", "")
    cartella = ctx.get("cartella", ".")
    percorso_out = ctx.get(
        "percorso_output_report",
        os.path.join(cartella, f"report_{datetime.date.today().isoformat()}.txt"),
    )
    try:
        with open(percorso_out, "w", encoding="utf-8") as f:
            f.write(testo)
        ctx["report_salvato_in"] = percorso_out
    except Exception as exc:
        raise RuntimeError(f"Impossibile salvare il report: {exc}") from exc
    return ctx


def crea_workflow_report_giornaliero() -> Workflow:
    """
    Costruisce il workflow "report_giornaliero".

    Flusso (completamente autonomo, nessun gate):
      1. raccogli_dati    -> elenca file nella cartella
      2. componi_report   -> formatta il testo
      3. salva_report     -> scrive su disco
    """
    passi = [
        Passo(nome="raccogli_dati",  funzione=_passo_raccogli_dati,  reversibile=True),
        Passo(nome="componi_report", funzione=_passo_componi_report, reversibile=True),
        Passo(nome="salva_report",   funzione=_passo_salva_report,   reversibile=False),
    ]
    return Workflow("report_giornaliero", passi)


# ===========================================================================
# SMOKE-TEST
# ===========================================================================

if __name__ == "__main__":
    import tempfile
    import shutil

    print("=" * 60)
    print("SMOKE-TEST workflow.py")
    print("=" * 60)

    # --- preparazione cartella temporanea ---
    tmp = tempfile.mkdtemp(prefix="argo_workflow_test_")
    print(f"\nCartella temporanea: {tmp}")

    try:
        # crea file finti per i test
        file_doc = os.path.join(tmp, "relazione.txt")
        file_sensibile_nome = os.path.join(tmp, "password.txt")
        db_audit = os.path.join(tmp, "test_audit.db")

        with open(file_doc, "w", encoding="utf-8") as f:
            f.write(
                "Relazione trimestrale Q1 2026\n"
                "Mittente: Mario Rossi\n"
                "Destinatario: Direzione Generale\n"
                "Data: 2026-03-31\n"
                "Oggetto: Risultati di vendita del primo trimestre.\n"
                "Fatturato totale: 1.250.000 euro.\n"
                "Margine netto: 18%. Crescita rispetto Q1 2025: +12%.\n"
                "Raccomandazione: investire nel reparto marketing per il Q2.\n"
            )
        with open(file_sensibile_nome, "w", encoding="utf-8") as f:
            f.write("p4ssw0rd_segreta")

        # crea anche qualche altro file per il report giornaliero
        for nome in ["foto.png", "appunti.txt", "codice.py", "altro.py"]:
            with open(os.path.join(tmp, nome), "w") as f:
                f.write("finto")

        # --- costruisce il motore e registra i workflow ---
        motore = MotoreWorkflow()
        motore.registra(crea_workflow_documento_in_arrivo())
        motore.registra(crea_workflow_report_giornaliero())
        print(f"\nWorkflow registrati: {list(motore._catalogo.keys())}")

        # -------------------------------------------------------
        # TEST A: documento_in_arrivo con file SENSIBILE
        # atteso: ValueError + workflow fallisce a 'blocca_se_sensibile'
        # -------------------------------------------------------
        print("\n--- TEST A: file sensibile (deve bloccare) ---")
        id_a = motore.avvia("documento_in_arrivo", {
            "percorso_file": file_sensibile_nome,
            "radice_cartella": tmp,
            "percorso_db_audit": db_audit,
        })
        st_a = motore.stato(id_a)
        assert st_a["stato"] == "fallito", \
            f"Atteso 'fallito', ottenuto '{st_a['stato']}'"
        assert st_a["dati"].get("bloccato") is True, "Doveva essere marcato come bloccato"
        print(f"  Stato    : {st_a['stato']}")
        print(f"  Errore   : {st_a['errore']}")
        print(f"  Bloccato : {st_a['dati'].get('bloccato')}")
        print("  PASS")

        # -------------------------------------------------------
        # TEST B: documento_in_arrivo con file normale (relazione.txt)
        # atteso:
        #   1. si ferma al gate dopo 'proponi_archiviazione' (in_attesa_approvazione)
        #   2. passi() mostra stato corretto
        #   3. approva() riprende e completa il workflow
        # -------------------------------------------------------
        print("\n--- TEST B: file normale - comprensione + estrazione + gate + archiviazione ---")
        id_b = motore.avvia("documento_in_arrivo", {
            "percorso_file": file_doc,
            "radice_cartella": tmp,
            "percorso_db_audit": db_audit,
        })
        st_b = motore.stato(id_b)

        print(f"  Stato dopo avvio : {st_b['stato']}")
        print(f"  Gate aperto su   : {st_b['gate_su']}")

        # verifica che il workflow si sia fermato al gate corretto
        assert st_b["stato"] == "in_attesa_approvazione", \
            f"Atteso 'in_attesa_approvazione', ottenuto '{st_b['stato']}'"
        assert st_b["gate_su"] == "proponi_archiviazione", \
            f"Gate atteso su 'proponi_archiviazione', trovato '{st_b['gate_su']}'"

        # verifica dati intermedi prodotti dai passi pre-gate
        dati_b = st_b["dati"]
        print(f"  Tipo documento   : {dati_b.get('tipo_documento')}")
        print(f"  Riassunto        : {dati_b.get('riassunto_contenuto')}")
        print(f"  Categoria        : {dati_b.get('categoria_contenuto')}")
        print(f"  Dati estratti    : {dati_b.get('dati_estratti')}")
        print(f"  Proposta arch.   : {dati_b.get('nota_proposta')}")

        # verifica la lista passi
        elenco_passi = motore.passi(id_b)
        print(f"\n  Passi del workflow:")
        for p in elenco_passi:
            print(f"    [{p['indice']}] {p['nome']:<30} stato={p['stato']}"
                  f"{'  [GATE]' if p['approvazione'] else ''}"
                  f"{'  [IRREVERSIBILE]' if not p['reversibile'] else ''}")

        # simula approvazione umana
        print("\n  [utente approva]")
        st_b_finale = motore.approva(id_b)

        assert st_b_finale["stato"] == "completato", \
            f"Atteso 'completato', ottenuto '{st_b_finale['stato']}'"
        print(f"  Stato finale     : {st_b_finale['stato']}")
        print(f"  Audit registrato : {st_b_finale['dati'].get('audit_registrato')}")
        print(f"  Archiviazione    : {st_b_finale['dati'].get('risultato_archiviazione')}")
        print("  PASS")

        # -------------------------------------------------------
        # TEST C: report_giornaliero (completamente autonomo)
        # -------------------------------------------------------
        print("\n--- TEST C: report_giornaliero ---")
        report_path = os.path.join(tmp, "report_test.txt")
        id_c = motore.avvia("report_giornaliero", {
            "cartella": tmp,
            "percorso_output_report": report_path,
        })
        st_c = motore.stato(id_c)

        assert st_c["stato"] == "completato", \
            f"Atteso 'completato', ottenuto '{st_c['stato']}'"
        assert os.path.exists(report_path), "Il file di report non e' stato creato"

        print(f"  Stato            : {st_c['stato']}")
        print(f"  Report salvato in: {st_c['dati'].get('report_salvato_in')}")
        print(f"  File analizzati  : {st_c['dati'].get('dati_report', {}).get('totale_file')}")
        print("  PASS")

        # -------------------------------------------------------
        # TEST D: approva() su istanza non in attesa -> ValueError
        # -------------------------------------------------------
        print("\n--- TEST D: approva su istanza gia' completata -> ValueError ---")
        try:
            motore.approva(id_c)
            assert False, "Doveva sollevare ValueError"
        except ValueError as e:
            print(f"  ValueError attesa: {e}")
            print("  PASS")

        # -------------------------------------------------------
        # TEST E: riepilogo motore e log audit
        # -------------------------------------------------------
        print("\n--- TEST E: riepilogo istanze nel motore ---")
        istanze = motore.tutte_istanze()
        assert len(istanze) == 3, f"Attese 3 istanze, trovate {len(istanze)}"
        for ist in istanze:
            print(f"  [{ist['workflow']}] id={ist['id']} stato={ist['stato']} "
                  f"log={ist['n_voci_log']} voci")
        print("  PASS")

        print("\n--- TEST F: log audit completo istanza B ---")
        log = motore.log_completo(id_b)
        assert len(log) > 0, "Il log non deve essere vuoto"
        for voce in log:
            print(f"  {voce['quando']}  {voce['evento']:<30} {voce['dettaglio'][:55]}")
        print("  PASS")

        print("\n" + "=" * 60)
        print("OK")
        print("=" * 60)

    finally:
        # pulizia cartella temporanea (sempre, anche in caso di errore)
        shutil.rmtree(tmp, ignore_errors=True)
