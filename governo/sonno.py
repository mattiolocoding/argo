"""
ARGO - governo/sonno.py
Il ciclo del "Sonno + Skill Synthesis": ARGO rilegge la propria giornata,
aggiorna i moduli cognitivi e prova a generare skill per colmare le lacune.

Flusso:
  1. Legge episodi recenti (memoria episodica) + consolida la giornata
     (timeline cognitiva, audit).
  2. Produce una sintesi leggibile della giornata.
  3. Aggiorna (difensivamente) diario_interno, world_model e obiettivi se i
     moduli esistono; li salta senza errori se assenti.
  4. Individua lacune con criteri sensati:
     - rifiuti ripetuti sullo stesso argomento (>= SOGLIA_RIFIUTI)
     - errori ricorrenti (>= SOGLIA_ERRORI)
     - formati non riconosciuti (estensioni che compaiono in errori, >= SOGLIA_FORMATO)
     - file osservati senza classificazione progetto (alta percentuale)
  5. Filtra le lacune per frequenza/impatto: passa allo skill_writer SOLO quelle
     che superano la soglia e che non producono skill banali.
  6. Genera la skill con SkillWriter -> valida con Validator -> propone nel
     registry SOLO come 'proposta' (MAI auto-attiva).
  7. Registra l'evento "sonno" nella timeline cognitiva.
  8. Ritorna un report testuale chiaro.

SICUREZZA: nessun codice generato viene mai eseguito in produzione; la
sandbox usa cartelle temporanee isolate. Lo stato 'proposta' richiede sempre
approvazione umana esplicita prima di qualsiasi attivazione.

Librerie usate: solo stdlib + moduli interni ARGO.
"""

# ── Bootstrap sys.path ───────────────────────────────────────────────────────
# Permette di eseguire sia come:
#   python -m governo.sonno
#   python governo\sonno.py
import os as _os
import sys as _sys
_root = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
if _root not in _sys.path:
    _sys.path.insert(0, _root)
# ─────────────────────────────────────────────────────────────────────────────

import datetime
import re
from collections import Counter

from governo.lacune import Lacune
from governo.skill_registry import SkillRegistry
from governo.skill_writer import SkillWriter
from governo.validator import Validator
from memoria.consolidamento import consolida_giornata, formatta_report


# ── Soglie di rilevamento lacune ─────────────────────────────────────────────
SOGLIA_RIFIUTI   = 2   # min occorrenze rifiuto per segnalare una lacuna
SOGLIA_ERRORI    = 2   # min occorrenze errore per segnalare una lacuna
SOGLIA_FORMATO   = 2   # min estensioni problematiche uguali
SOGLIA_IMPATTO   = 2   # min conteggio per passare allo skill_writer

# ── Limiti ciclo ─────────────────────────────────────────────────────────────
N_EPISODI_ANALISI    = 200   # episodi recenti analizzati
MAX_SKILL_PER_CICLO  = 5     # skill generate in un singolo ciclo


# ══════════════════════════════════════════════════════════════════════════════
#  Funzioni di supporto — analisi episodi
# ══════════════════════════════════════════════════════════════════════════════

def _normalizza_testo(testo, limite=120):
    """Pulisce spazi multipli e tronca."""
    testo = re.sub(r"\s+", " ", str(testo or "")).strip()
    return testo[:limite]


def _estrai_estensione(testo):
    """Restituisce l'estensione (es. '.heic') se trovata nel testo, altrimenti ''."""
    m = re.search(r"(\.[A-Za-z0-9]{2,8})\b", testo or "")
    return m.group(1).lower() if m else ""


def _individua_lacune_dai_rifiuti(episodi: list) -> list:
    """
    Analizza gli episodi e ritorna lacune rilevate.
    Criteri:
      - azione_rifiutata ripetuta >= SOGLIA_RIFIUTI
      - errore/azione_fallita ripetuti >= SOGLIA_ERRORI
      - estensioni problematiche >= SOGLIA_FORMATO
    Ogni lacuna e' un dict {'tipo', 'descrizione', 'conteggio'}.
    """
    rifiuti:    Counter = Counter()
    errori:     Counter = Counter()
    estensioni: Counter = Counter()

    for e in episodi:
        tipo     = e.get("tipo", "")
        testo    = _normalizza_testo(e.get("dettaglio", "") or e.get("descrizione", ""))
        if not testo:
            continue

        if tipo in ("azione_rifiutata",):
            rifiuti[testo] += 1

        if tipo in ("errore", "azione_fallita"):
            errori[testo] += 1
            ext = _estrai_estensione(testo)
            if ext:
                estensioni[ext] += 1

    lacune: list = []

    for desc, n in rifiuti.items():
        if n >= SOGLIA_RIFIUTI:
            lacune.append({
                "tipo": "rifiuto_ripetuto",
                "descrizione": f"Azione rifiutata {n} volte: {desc}",
                "conteggio": n,
            })

    for desc, n in errori.items():
        if n >= SOGLIA_ERRORI:
            lacune.append({
                "tipo": "errore_ricorrente",
                "descrizione": f"Errore ricorrente {n} volte: {desc}",
                "conteggio": n,
            })

    for ext, n in estensioni.items():
        if n >= SOGLIA_FORMATO:
            lacune.append({
                "tipo": "formato_non_gestito",
                "descrizione": f"Formato con errori ricorrenti: {ext} ({n} volte)",
                "conteggio": n,
            })

    return lacune


def _lacune_da_consolidamento(consolidato: dict) -> list:
    """
    Trasforma le lacune candidate del consolidamento in record registrabili.
    Mantiene le descrizioni stabili per permettere la deduplicazione nel DB.
    """
    out = []
    for lc in (consolidato or {}).get("lacune", []):
        tipo        = str(lc.get("tipo", "lacuna_consolidata"))[:80]
        descrizione = str(lc.get("descrizione", "")).strip()
        if not descrizione:
            continue
        out.append({
            "tipo":        tipo,
            "descrizione": descrizione[:500],
            "conteggio":   int(lc.get("conteggio", 1) or 1),
        })
    return out


def _dedup_lacune(lacune_lista: list) -> list:
    """Rimuove duplicati (tipo, descrizione) mantenendo la prima occorrenza."""
    viste: set = set()
    out:   list = []
    for lc in lacune_lista:
        chiave = (lc.get("tipo"), lc.get("descrizione"))
        if chiave in viste:
            continue
        viste.add(chiave)
        out.append(lc)
    return out


def _filtra_lacune_per_impatto(lacune: list, soglia: int = SOGLIA_IMPATTO) -> list:
    """
    Ordina le lacune per conteggio decrescente e restituisce SOLO quelle con
    conteggio >= soglia. Evita di passare allo skill_writer lacune banali
    con una sola occorrenza (rumore di fondo).
    """
    utili = [lc for lc in lacune if lc.get("conteggio", 1) >= soglia]
    utili.sort(key=lambda x: -x.get("conteggio", 1))
    return utili


def _audit_default():
    """Prova a costruire un'istanza Audit locale se il motore non lo passa."""
    try:
        import sicurezza
        return sicurezza.Audit()
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  Import difensivi — moduli cognitivi opzionali
# ══════════════════════════════════════════════════════════════════════════════

def _carica_timeline_cognitiva():
    try:
        from cognizione.timeline import TimelineCognitiva
        return TimelineCognitiva
    except Exception:
        return None


def _carica_world_model():
    try:
        from cognizione.world_model import WorldModel
        return WorldModel
    except Exception:
        return None


def _carica_diario_interno():
    try:
        from cognizione.diario_interno import DiarioInterno
        return DiarioInterno
    except Exception:
        return None


def _carica_obiettivi():
    try:
        from cognizione.obiettivi import Obiettivi
        return Obiettivi
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  Funzione principale — sonno(...)
# ══════════════════════════════════════════════════════════════════════════════

def sonno(
    memoria,
    lacune:   Lacune,
    registry: SkillRegistry,
    writer:   SkillWriter,
    cervello,
    audit     = None,
    timeline  = None,
    # Parametri opzionali extra (compatibilità futura):
    world_model  = None,
    diario       = None,
    obiettivi_db = None,
) -> str:
    """
    Esegue il ciclo completo di Sonno + Skill Synthesis.

    SICUREZZA: le skill generate vengono sempre inserite nel registry come
    'proposta' e non vengono mai attivate automaticamente. Nessun codice
    generato viene eseguito su filesystem reale: la sandbox usa cartelle
    temporanee isolate.

    :param memoria:      istanza di Memoria (memoria episodica di ARGO)
    :param lacune:       istanza di Lacune (registro delle lacune)
    :param registry:     istanza di SkillRegistry (registro delle skill)
    :param writer:       istanza di SkillWriter (generatore di skill)
    :param cervello:     istanza di Cervello (per la generazione LLM)
    :param audit:        (opz.) istanza di Audit; se None viene creata in automatico
    :param timeline:     (opz.) lista di eventi della timeline o TimelineCognitiva
    :param world_model:  (opz.) istanza di WorldModel; se None viene costruita
    :param diario:       (opz.) istanza di DiarioInterno; se None viene costruita
    :param obiettivi_db: (opz.) istanza di Obiettivi; se None viene costruita
    :return:             report testuale del ciclo di sonno
    """
    ora_inizio = datetime.datetime.now().isoformat(timespec="seconds")
    righe: list = [f"=== Ciclo di Sonno avviato {ora_inizio} ==="]

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 1: lettura memoria + consolidamento giornaliero
    # ──────────────────────────────────────────────────────────────────────────
    try:
        episodi = memoria.ricordi_recenti(N_EPISODI_ANALISI)
        righe.append(f"Episodi analizzati: {len(episodi)}")
    except Exception as e:
        righe.append(f"[ERRORE] Impossibile leggere la memoria: {e}")
        return "\n".join(righe)

    audit_usato = audit if audit is not None else _audit_default()

    # Converti timeline oggetto → lista se necessario
    timeline_lista = []
    timeline_cognitiva = None
    if timeline is not None:
        if isinstance(timeline, list):
            timeline_lista = timeline
        elif hasattr(timeline, "eventi_oggi"):
            # E' un'istanza di TimelineCognitiva
            timeline_cognitiva = timeline
            try:
                timeline_lista = timeline.eventi_oggi(N_EPISODI_ANALISI)
            except Exception:
                timeline_lista = []
        elif hasattr(timeline, "recenti"):
            try:
                timeline_lista = timeline.recenti(N_EPISODI_ANALISI)
            except Exception:
                timeline_lista = []

    # Se non abbiamo una TimelineCognitiva dall'esterno, proviamo a costruirne una
    if timeline_cognitiva is None:
        TL = _carica_timeline_cognitiva()
        if TL is not None:
            try:
                timeline_cognitiva = TL()
            except Exception:
                timeline_cognitiva = None

    try:
        consolidato = consolida_giornata(
            memoria         = memoria,
            audit           = audit_usato,
            timeline        = timeline_lista,
            limite_episodi  = N_EPISODI_ANALISI,
            salva           = True,
        )
        righe.append("")
        righe.append(formatta_report(consolidato))
    except Exception as e:
        righe.append(f"[ERRORE] Consolidamento giornaliero fallito: {e}")
        consolidato = {"lacune": []}

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 2: sintesi della giornata tramite TimelineCognitiva
    # ──────────────────────────────────────────────────────────────────────────
    sintesi_giornata = ""
    if timeline_cognitiva is not None:
        try:
            dati_cons = timeline_cognitiva.consolida_oggi()
            sintesi_giornata = dati_cons.get("sintesi", "")
            if sintesi_giornata:
                righe.append(f"\nSintesi cognitiva della giornata:\n  {sintesi_giornata}")
        except Exception as e:
            righe.append(f"[AVVISO] Consolidamento timeline cognitiva non riuscito: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 3a: aggiorna WorldModel (difensivo)
    # ──────────────────────────────────────────────────────────────────────────
    analisi_world = None
    wm_istanza = world_model
    if wm_istanza is None:
        WM = _carica_world_model()
        if WM is not None:
            try:
                wm_istanza = WM()
            except Exception:
                wm_istanza = None

    if wm_istanza is not None:
        try:
            analisi_world = wm_istanza.analizza(
                timeline = timeline_cognitiva,
                memoria  = memoria,
                audit    = audit_usato,
            )
            righe.append(
                f"\nWorldModel aggiornato: {analisi_world.get('sintesi', '(no sintesi)')}"
            )
        except Exception as e:
            righe.append(f"[AVVISO] WorldModel non aggiornato: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 3b: aggiorna DiarioInterno (difensivo)
    # ──────────────────────────────────────────────────────────────────────────
    diario_istanza = diario
    if diario_istanza is None:
        DI = _carica_diario_interno()
        if DI is not None:
            try:
                diario_istanza = DI()
            except Exception:
                diario_istanza = None

    if diario_istanza is not None:
        try:
            ris_diario = diario_istanza.rifletti(
                timeline = timeline_cognitiva,
                world    = wm_istanza,
                memoria  = memoria,
                audit    = audit_usato,
            )
            righe.append(
                f"DiarioInterno: {ris_diario.get('create', 0)} riflessioni registrate."
            )
            # Registra anche la sintesi del sonno come riflessione esplicita
            if sintesi_giornata:
                diario_istanza.registra(
                    tipo       = "sonno",
                    titolo     = "Ciclo di sonno — sintesi giornata",
                    dettaglio  = sintesi_giornata[:2000],
                    importanza = "alta",
                )
        except Exception as e:
            righe.append(f"[AVVISO] DiarioInterno non aggiornato: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 3c: aggiorna Obiettivi da WorldModel (difensivo)
    # ──────────────────────────────────────────────────────────────────────────
    obj_istanza = obiettivi_db
    if obj_istanza is None:
        OB = _carica_obiettivi()
        if OB is not None:
            try:
                obj_istanza = OB()
            except Exception:
                obj_istanza = None

    if obj_istanza is not None and analisi_world is not None:
        try:
            ris_obj = obj_istanza.valuta_da_world(analisi_world)
            righe.append(
                f"Obiettivi: {ris_obj.get('creati', 0)} creati, "
                f"{ris_obj.get('aggiornati', 0)} aggiornati."
            )
        except Exception as e:
            righe.append(f"[AVVISO] Obiettivi non aggiornati: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 4: individua pattern di lacune
    # ──────────────────────────────────────────────────────────────────────────
    try:
        lacune_grezze = _dedup_lacune(
            _individua_lacune_dai_rifiuti(episodi)
            + _lacune_da_consolidamento(consolidato)
        )
        righe.append(f"\nLacune grezze rilevate: {len(lacune_grezze)}")
    except Exception as e:
        righe.append(f"[ERRORE] Analisi pattern fallita: {e}")
        lacune_grezze = []

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 5: registra le nuove lacune nel database
    # ──────────────────────────────────────────────────────────────────────────
    for lc in lacune_grezze:
        try:
            id_lc = lacune.registra(lc["tipo"], lc["descrizione"])
            lc["id"] = id_lc
            righe.append(
                f"  Lacuna registrata [id={id_lc}]: {lc['descrizione'][:60]}"
            )
        except Exception as e:
            righe.append(f"  [ERRORE] Registrazione lacuna fallita: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 6: filtra per impatto e genera skill per le lacune aperte
    # ──────────────────────────────────────────────────────────────────────────
    try:
        lacune_aperte = lacune.aperte()
    except Exception as e:
        righe.append(f"[ERRORE] Impossibile leggere le lacune aperte: {e}")
        lacune_aperte = []

    # Il DB storico non conserva ancora il conteggio; le lacune appena rilevate si'.
    # Per non perdere l'impatto e bloccare la generazione skill, filtriamo prima
    # le lacune del ciclo corrente. Se non ci sono, usiamo lo storico come fallback.
    lacune_utili = _filtra_lacune_per_impatto(lacune_grezze, soglia=SOGLIA_IMPATTO)
    if not lacune_utili:
        lacune_utili = _filtra_lacune_per_impatto(lacune_aperte, soglia=SOGLIA_IMPATTO)
    righe.append(
        f"Lacune aperte totali: {len(lacune_aperte)}  "
        f"(filtrate per impatto >= {SOGLIA_IMPATTO}: {len(lacune_utili)})"
    )

    skill_generate = 0
    for lc in lacune_utili:
        if skill_generate >= MAX_SKILL_PER_CICLO:
            righe.append(
                f"  Limite massimo skill per ciclo ({MAX_SKILL_PER_CICLO}) raggiunto."
            )
            break

        id_lacuna  = lc.get("id", "?")
        desc_lacuna = lc.get("descrizione", "")
        conteggio   = lc.get("conteggio", 1)
        righe.append(
            f"\n--- Lacuna [id={id_lacuna}, x{conteggio}]: "
            f"{desc_lacuna[:70]} ---"
        )

        # ── 6a: genera la skill ─────────────────────────────────────────────
        try:
            skill_dati = writer.genera(desc_lacuna)
        except Exception as e:
            righe.append(f"  [ERRORE] Generazione skill fallita: {e}")
            continue

        if skill_dati is None:
            righe.append("  Generazione skill non riuscita (writer ha restituito None).")
            continue

        righe.append(f"  Skill generata: '{skill_dati['nome']}'")
        codice = skill_dati.get("codice", "")

        # ── 6b: filtro anti-scheletro ────────────────────────────────────────
        # Skill scheletro (cervello offline) non vengono proposte: non aggiungono valore.
        if "non_implementata" in codice:
            righe.append(
                "  Skill e' uno scheletro (cervello offline): non proposta nel registry."
            )
            continue

        # ── 6c: validazione (sicurezza statica + sandbox) ───────────────────
        try:
            validatore = Validator()
            val_ris    = validatore.valida(codice)
        except Exception as e:
            righe.append(f"  [ERRORE] Validazione fallita con eccezione: {e}")
            continue

        if not val_ris.get("ok"):
            motivi_str = "; ".join(val_ris.get("motivi", []))
            righe.append(f"  Validazione FALLITA: {motivi_str}")
            righe.append("  Skill scartata. NON inserita nel registry.")
            continue

        righe.append("  Validazione (sicurezza + sandbox): PASSATA")

        # ── 6d: proponi nel registry come 'proposta' ─────────────────────────
        try:
            id_skill = registry.proponi(
                nome        = skill_dati["nome"],
                descrizione = skill_dati["descrizione"],
                codice      = codice,
            )
            righe.append(
                f"  Skill proposta nel registry [id={id_skill}]. "
                f"Stato: 'proposta' — RICHIEDE APPROVAZIONE UMANA."
            )
            skill_generate += 1
        except Exception as e:
            righe.append(f"  [ERRORE] Inserimento nel registry fallito: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FASE 7: registra evento "sonno" nella TimelineCognitiva
    # ──────────────────────────────────────────────────────────────────────────
    if timeline_cognitiva is not None:
        try:
            timeline_cognitiva.registra(
                "sonno",
                descrizione = (
                    f"Ciclo di sonno completato: {len(lacune_grezze)} lacune, "
                    f"{skill_generate} skill proposte."
                ),
                origine = "governo",
                esito   = "ok",
            )
        except Exception as e:
            righe.append(f"[AVVISO] Registrazione evento sonno fallita: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Riepilogo finale
    # ──────────────────────────────────────────────────────────────────────────
    ora_fine = datetime.datetime.now().isoformat(timespec="seconds")
    righe.append(f"\n=== Ciclo di Sonno completato {ora_fine} ===")
    righe.append(
        f"Riepilogo: {len(lacune_grezze)} lacune rilevate, "
        f"{skill_generate} skill proposte (in attesa di approvazione umana)."
    )

    return "\n".join(righe)


# ══════════════════════════════════════════════════════════════════════════════
#  Smoke-test
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import tempfile
    import os

    print("== Smoke-test sonno ==")

    with tempfile.TemporaryDirectory() as tmp:

        # ── Stub Memoria ──────────────────────────────────────────────────────
        class MemoriaFinta:
            def ricordi_recenti(self, n=10):
                oggi = datetime.date.today().isoformat()
                # 3 rifiuti sulla stessa azione → lacuna rifiuto_ripetuto
                rifiuti = [
                    {
                        "id": i,
                        "quando": f"{oggi}T10:0{i}:00",
                        "tipo": "azione_rifiutata",
                        "dettaglio": "Conversione file HEIC non supportata",
                        "esito": None,
                    }
                    for i in range(1, 4)
                ]
                # 3 errori sullo stesso formato → lacuna formato_non_gestito
                errori = [
                    {
                        "id": 10 + i,
                        "quando": f"{oggi}T11:0{i}:00",
                        "tipo": "errore",
                        "dettaglio": f"Impossibile aprire file.heic (tentativo {i})",
                        "esito": None,
                    }
                    for i in range(1, 4)
                ]
                conferme = [
                    {
                        "id": 20,
                        "quando": f"{oggi}T09:00:00",
                        "tipo": "azione_confermata",
                        "dettaglio": "Spostamento file PDF",
                        "esito": "ok",
                    }
                ]
                return rifiuti + errori + conferme

            def salva_profilo(self, chiave, valore):
                pass

            def ricorda(self, tipo, dettaglio="", esito=None):
                pass

        # ── Stub Cervello offline ─────────────────────────────────────────────
        class CervelloFinto:
            def vivo(self):
                return False

            def pensa(self, msg, contesto=None):
                return "[offline]"

        # ── Istanze reali su database temporanei ──────────────────────────────
        lacune_db   = Lacune(percorso=os.path.join(tmp, "lacune.db"))
        registry_db = SkillRegistry(percorso=os.path.join(tmp, "skills.db"))
        writer_obj  = SkillWriter(CervelloFinto())
        memoria_obj = MemoriaFinta()
        cervello_obj = CervelloFinto()

        # ── Esegui il sonno ───────────────────────────────────────────────────
        report = sonno(
            memoria  = memoria_obj,
            lacune   = lacune_db,
            registry = registry_db,
            writer   = writer_obj,
            cervello = cervello_obj,
            # world_model, diario, obiettivi_db: lasciati a None → import difensivo
        )
        print(report)
        print()

        # ── Asserzioni ────────────────────────────────────────────────────────
        aperte = lacune_db.aperte()
        assert len(aperte) >= 1, (
            f"Attesa almeno 1 lacuna aperta, trovate {len(aperte)}"
        )
        print(f"Lacune aperte nel DB: {len(aperte)}")

        # Con cervello offline le skill scheletro vengono scartate → 0 proposte
        proposte = registry_db.proposte()
        print(f"Skill proposte (attese 0, cervello offline): {len(proposte)}")
        assert len(proposte) == 0, (
            f"Con cervello offline non devono esserci proposte, trovate {len(proposte)}"
        )

        # ── Pulisci ───────────────────────────────────────────────────────────
        lacune_db.chiudi()
        registry_db.chiudi()

    print("\nOK")
