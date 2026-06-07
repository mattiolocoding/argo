<div align="center">

<img src="assets/logo.svg" alt="ARGO" width="80" height="80" />

# ARGO — Cosa offre

**Deliverable completo delle capacità.** · v0.1.0 · aggiornato 2026-06-07

*Un essere digitale che vive sul tuo PC: osserva, ricorda, impara e — quando glielo permetti — agisce. 100% locale, di tua proprietà, offline.*

</div>

---

## In una riga

ARGO non è un chatbot che interroghi e dimentichi. **Percepisce** ciò che accade sul PC, **ragiona** con un LLM locale (Ollama), **ricorda** tra le sessioni e **agisce** sui file sotto il tuo controllo. Più a lungo lavora con te, più diventa insostituibile, perché la memoria è **tua** e non lascia mai la macchina.

Il vero vantaggio non è il modello (commodity), ma la **memoria accumulata, privata e locale**.

---

## I quattro organi + tre strati

```
   👁 SENSI  ──▶  🧠 CERVELLO  ──▶  ✋ MANI            🏛 GOVERNO  (policy · ruoli · audit · rollback)
   (vede)         (ragiona)        (agisce)           ✨ COGNIZIONE (world model · obiettivi · diario)
      ▲               │               │               🔒 SICUREZZA (segreti · audit a catena · DPAPI)
      └──────  💾 MEMORIA  ◀──────────┘
              (ricorda e cresce)
```

**Loop di vita:** percepisci → consulta memoria → pensa → (decidi secondo autonomia) → agisci → verifica → ricorda → ricomincia. Sempre, in background.

---

## Catalogo completo delle capacità

### 👁 Sensi — percepire
- **Occhi su tutto il PC**: sorveglia Desktop, Download, Documenti, Immagini, Musica, Video (+ `sorvegliata/`), reagisce ai file nuovi.
- **Sensi di sistema**: spazio disco, processi più pesanti, allerta disco pieno.
- **Sensi estesi** (privacy-safe): finestra attiva, stato rete, *metadati* degli appunti (mai il contenuto).

### 🧠 Cervello — ragionare
- **LLM locale via Ollama**, con **auto-accensione** e **riconnessione** automatica.
- **Model mesh** (`modelli.py`): instrada per complessità su tre livelli — **riflesso** (veloce), **ragionatore** (default), **esperto** (deliberazione best-of-N). *Esclude automaticamente i modelli di embedding dai ruoli di chat.*
- **Chat fondata (anti-allucinazione)**: risponde **solo** dai dati reali della memoria; se non sa, lo dice.
- **Deliberatore** (`pensatore.py`): best-of-N + verificatore per le domande complesse.

### 💾 Memoria — ricordare e crescere
- **Episodica** (`memoria/memoria.py`): diario di tutto ciò che vede e fa, con profilo e abitudini (SQLite).
- **A grafo** (`memoria/grafo.py`): collega file ↔ progetti ↔ persone ↔ eventi.
- **Semantica** (`memoria/semantica.py`): ritrova per *significato* via embeddings (`nomic-embed-text`).
- **Apprendimento abitudini**: smette di proporre ciò che rifiuti, fa da solo ciò che accetti sempre.

### ✋ Mani — agire in sicurezza
- **Azioni sui file** con guardrail: sposta, rinomina, archivia, crea cartelle.
- **Ordina** per tipo / data / progetto; **riconosce duplicati e accumuli**.
- **Tre livelli di autonomia**: 🟢 Osserva · 🟡 Chiede *(default)* · 🔴 Agisci — scelti da te, salvati in memoria.
- **Anteprima** ("ecco cosa farei") e conferma Sì/No prima di toccare il reale.

### 🏛 Governo dell'azione (enterprise)
- **Policy engine** (`governo/policy.py`): esiti Consenti / Escala / Blocca a runtime (es. contratti bloccati, buste paga sempre con conferma).
- **Ruoli / RBAC** (`governo/ruoli.py`): admin · operatore · auditor · utente, con endpoint protetti.
- **Rollback / Annulla** (`governo/rollback.py`): ogni azione reversibile con un click.
- **Metriche** (`governo/metriche.py`): azioni, rifiuti, rischi evitati, tempo risparmiato.
- **Consolidamento "sonno"** (`governo/consolidamento.py`): riassunto serale automatico.
- **Agenti specializzati** (`governo/agenti.py`): Diagnostico · Auditor · Guardiano · Archivista · Analista.

### ✨ Cognizione (nucleo cognitivo)
- **World Model** (`cognizione/world_model.py`): ipotesi, lacune, piani governati, proposte operative.
- **Timeline cognitiva**: eventi, pattern, ricorrenze, lacune del giorno.
- **Diario interno** (`cognizione/diario_interno.py`): auto-riflessioni persistenti.
- **Obiettivi permanenti** (`cognizione/obiettivi.py`): direzioni a lungo termine.
- **Esperimenti cognitivi** (`cognizione/esperimenti.py`): registro A/B delle strategie.
- **Sonno + skill synthesis**: osserva → lacuna → genera skill → sicurezza → sandbox → **proposta in attesa di approvazione umana** (mai auto-attiva).

### 🔌 Workflow & connettori
- **Workflow engine** (`workflow.py`) integrato nel motore: flussi multi-step con **gate di approvazione umano** e audit (es. `documento_in_arrivo`, `report_giornaliero`).
- **Connettori** (`connettori/`): email IMAP (sola lettura), filesystem, git, ricerca web governata.

### 🔒 Sicurezza
- **File/segreti sensibili intoccabili**: rilevati e saltati, mai letti/indicizzati/spostati (22+ pattern).
- **Audit a catena di hash**: a prova di manomissione, esportabile e verificabile.
- **Path traversal** bloccato (`percorso_sicuro`), redazione segreti pre-hash.
- **Chiave locale protetta con DPAPI**; cifratura a riposo opzionale (`cryptography`).
- **Solo locale**: API su `127.0.0.1`, nessun dato esce dalla macchina.

### 🌐 Scaling (questa sessione)
- **Verticale**: workflow end-to-end nel motore (avvia → gate → approva → archivia → audit).
- **Orizzontale (flotta)**: più istanze in parallelo su porte/macchine diverse (`ARGO_PORT`/`ARGO_ISTANZA_*`); `fleet.py` aggrega lo stato di tutta la flotta; card **Flotta** nella Console.

### 🖥 Interfaccia
- **App desktop nativa** (Qt/PySide6) con icona e logo, oppure finestra `--app` / browser (degrada con grazia).
- **UI 2026** a file singolo (`ui/index.html`): tema scuro indaco/viola, 4 viste **Chat / Console / Permessi / Audit**, qualità di design **impeccable** (contrasto WCAG, motion + reduced-motion, focus/ARIA).
- **Onboarding permessi** al primo avvio: Tutto il PC / Solo cartelle scelte / Niente.

---

## API locale completa (`127.0.0.1:8773`)

> Motore headless su `http.server` (stdlib, nessun framework web). Host/porta configurabili da ambiente.

### Lettura (GET)
| Endpoint | Cosa restituisce |
|---|---|
| `/stato` | stato live: cervello, ricordi, cartelle, grafo, modo, istanza |
| `/identita` | carta d'identità dell'istanza (id, nome, versione, porta, avvio) |
| `/flotta` | stato aggregato della flotta (istanze online, ricordi/azioni totali) |
| `/console`, `/dashboard` | dati completi della Console |
| `/metriche` | azioni, rifiuti, rischi evitati, tempo risparmiato |
| `/audit`, `/audit/export` | log a catena di hash + export per compliance |
| `/permessi` | modo e cartelle autorizzate |
| `/modelli` | model mesh (riflesso / ragionatore / esperto) |
| `/sensi` | finestra attiva, rete, metadati appunti |
| `/connettori` | connettori disponibili |
| `/skills` | skill proposte dal sonno e loro stato |
| `/workflow` | catalogo workflow + istanze in corso |
| `/agenti` | agenti specializzati disponibili |
| `/eventi` | stream eventi recenti |
| `/timeline`, `/cognizione` | timeline cognitiva |
| `/pensiero` | ultima/nuova analisi deliberata |
| `/world`, `/proposte` | world model e proposte operative |
| `/diario`, `/obiettivi`, `/esperimenti` | nucleo cognitivo |

### Azione (POST)
| Endpoint | Effetto |
|---|---|
| `/chat` | conversazione fondata sui dati reali |
| `/conferma` | approva/rifiuta una proposta (Sì/No) |
| `/autonomia` | cambia livello (Osserva / Chiede / Agisci) |
| `/annulla` | rollback dell'ultima azione |
| `/agente` | esegue un agente specializzato |
| `/consolida` | consolidamento "sonno" della giornata |
| `/rifletti` | riflessione interna |
| `/sonno` | cerca lacune e propone skill (sandbox) |
| `/ricerca` | ricerca web governata |
| `/skill/approva`·`/attiva`·`/scarta`·`/esegui`·`/bonifica` | ciclo di vita delle skill |
| `/workflow/avvia`, `/workflow/approva` | avvia un flusso / supera il gate umano |
| `/permessi`, `/proposta/stato` | aggiorna permessi / stato proposta |

---

## Stack tecnico

| Pezzo | Scelta |
|---|---|
| Linguaggio | **Python 3.11+** |
| Motore | `http.server` (**solo stdlib**, zero framework web) |
| Cervello | **Ollama** locale (qwen2.5:14b/7b, llama3.1:8b) |
| Embeddings | `nomic-embed-text` / `bge-m3` |
| Memoria | **SQLite** (episodica + grafo + vettori) |
| UI | HTML/CSS/JS a file singolo (design **impeccable**) |
| Desktop | **PySide6 / Qt** (opzionale; degrada a browser) |
| Sicurezza | DPAPI + `cryptography` (opzionale) |

---

## Come si avvia

```powershell
# 1. Ollama + modelli
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text

# 2. Ambiente isolato
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt        # opzionale (finestra nativa, cifratura)

# 3. Avvio
python argo_app.py        # app desktop nativa, oppure
python motore_web.py      # motore + finestra
```

Più istanze (flotta):
```powershell
$env:ARGO_PORT="8774"; $env:ARGO_ISTANZA_NOME="ARGO-2"; python motore_web.py
$env:ARGO_FLOTTA="http://127.0.0.1:8773,http://127.0.0.1:8774"; python fleet.py
```

---

## Stato (verificato dal vivo, 2026-06-07)

| Area | Stato |
|---|---|
| Compilazione (tutti i moduli) | ✅ 0 errori |
| Self-test moduli (17) | ✅ tutti OK |
| Motore + API (24 endpoint GET, 18 POST) | ✅ rispondono |
| Chat fondata | ✅ 200, nessuna allucinazione |
| Workflow end-to-end + gate umano | ✅ verificato |
| Deliberazione / cognizione | ✅ verificate |
| Sicurezza (suite) | ✅ |
| UI impeccable (anti-pattern) | ✅ detector 2→0 |
| Flotta multi-istanza | ✅ provata con 2 istanze |
| Model mesh | ✅ corretto (no embedding nei ruoli chat) |

**Bug corretti in questa sessione:** model-mesh (embedding nei ruoli chat) · chat (dict di `mesh.pensa()` non gestito).

---

## Cosa NON fa (per scelta)
Niente cloud, niente account, niente telemetria, niente Docker per l'app, nessun addestramento di modelli, nessuna promessa di AGI. Una cosa vera che gira, poi cresce.

## Prossimi strati (roadmap)
Workflow ancora più profondi · knowledge graph temporale · console centrale della flotta · voce/mobile · packaging firmato + auto-update · apprendimento federato · marketplace skill.

---

<div align="center">
<sub>ARGO · 100% locale · di tua proprietà · <a href="README.md">README</a> · <a href="PROGETTO_ARGO.md">la Bibbia</a> · <a href="SICUREZZA_REPORT.md">sicurezza</a></sub>
</div>
