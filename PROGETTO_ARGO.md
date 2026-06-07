# 🐕 PROGETTO ARGO — La Bibbia

> Documento di riferimento. Qui c'è cosa è Argo, cosa fa, come funziona e in che
> ordine lo costruiamo. Prima di scrivere codice nuovo, si guarda qui.
> **Regole d'oro:** niente cose abbozzate · si va per step · ogni step funziona prima del successivo.

Versione 1.0 — giugno 2026

---

## 1. Cos'è Argo (in una frase)

> Un **essere digitale che vive sul PC di Davide**: osserva cosa succede, ragiona,
> ricorda e — quando glielo permetti — agisce. Non aspetta che tu scriva: *c'è*.

Non è un chatbot. Un chatbot aspetta una domanda e risponde. Argo **percepisce, decide e si muove** da solo, e diventa più utile col tempo perché *ricorda*.

---

## 2. La rivoluzione (perché vale)

La cosa nuova non è "un'IA che ragiona" — quella è ormai una commodity. La rivoluzione è:

> **Una memoria che si accumula, è tua, e vive sul tuo PC.**

Oggi ogni IA è *smemorata e affittata*: riparte da zero, sta sul cloud di altri coi tuoi dati, e quando spengono il server sparisce. Argo ribalta tutto: ricorda per sempre, gira in locale, i dati non escono dal PC, e cresce nella direzione della *tua* vita. Il vero fossato competitivo non è la tecnologia — è la **memoria accumulata**: più a lungo lavora con te, più diventa insostituibile.

---

## 3. Le decisioni prese (fisse)

| Tema | Decisione |
|---|---|
| **Primo mestiere** | **Custode del PC** — ordina e sorveglia file, download, documenti, desktop. |
| **Autonomia** | **Tre livelli, scelti da Davide per ogni compito.** Default sicuro: *osserva, avvisa e chiede conferma*. |
| **Memoria** | **Architettura a strati (standard 2026)** — non un solo database. Riusa il motore di SONAR per la memoria profonda. |
| **Cervello** | **Ollama in locale** (modello attuale: llama3.1; valutiamo upgrade — vedi §7). |
| **Rapporto con SONAR** | Argo **usa** SONAR come memoria documentale/grafo. **Non lo modifica mai.** |

---

## 4. I quattro organi

```
        ┌─────────────────────────────────────────────┐
        │                   ARGO                       │
        │                                              │
        │   👁  SENSI  ──▶  🧠 CERVELLO  ──▶  ✋ MANI   │
        │      (vede)        (ragiona)       (agisce)  │
        │         ▲              │               │      │
        │         └──────  💾 MEMORIA  ◀─────────┘      │
        │              (ricorda e cresce)              │
        └─────────────────────────────────────────────┘
```

- **👁 Sensi** — percepisce: file aggiunti/spostati/cancellati, spazio disco, eventi. (Oggi: watcher cartelle.)
- **🧠 Cervello** — Ollama in locale. Ragiona su ciò che i sensi riportano e decide il prossimo passo.
- **💾 Memoria** — ricorda tutto e cresce. È il cuore (vedi §6).
- **✋ Mani** — esegue azioni controllate (sposta/rinomina/ordina file…), secondo il livello di autonomia.

**Il loop di vita:** percepisci → consulta memoria → pensa → (decidi secondo autonomia) → agisci → verifica → ricorda → ricomincia. Sempre, in background.

---

## 5. Il primo mestiere: Custode del PC

Argo impara UN mestiere e lo fa benissimo, poi si allarga. Il primo è tenere in ordine il PC.

**Cosa fa concretamente:**
- Sorveglia cartelle che gli indichi (Download, Desktop, Documenti…).
- Nota disordine: file fuori posto, duplicati, nomi caotici, accumuli ("hai 40 PDF nei Download").
- Ragiona su *cosa sono* i file (e, più avanti, sul loro contenuto via SONAR).
- Propone o esegue il riordino: cartelle per tipo/data/progetto, rinomine sensate, archiviazione.
- Ricorda le tue abitudini: come ti piace organizzare → la volta dopo lo fa già giusto.

**Perché questo per primo:** mette alla prova *tutti e quattro gli organi* insieme, si vede subito se funziona, è utile dal giorno uno e a basso rischio. È la palestra perfetta. Dopo, allarghiamo verso il tuo dominio professionale (sistema/IT) dove ci sono i soldi veri.

---

## 6. La memoria — architettura a strati (standard 2026)

Lo stato dell'arte 2026 **non è un singolo database**: è una memoria a più strati dove l'agente sceglie quale usare. Argo adotta questo schema, sfruttando ciò che SONAR ha già.

| Strato | A cosa serve | Come |
|---|---|---|
| **1. Memoria di lavoro** | Chi è Davide, preferenze, regole attive. Sempre "in testa". | File profilo locale, leggero, sempre nel contesto del modello. |
| **2. Memoria episodica** | Diario di tutto ciò che Argo vede e fa, con data/ora. | **SQLite** locale di Argo (autonomo, gira anche se SONAR è spento). |
| **3. Memoria semantica** | Ritrovare per *significato* ("quel file del progetto X"). | Embeddings (`nomic-embed-text`) → ricerca vettoriale. Riusa il **vector store di SONAR (pgvector)**. |
| **4. Memoria a grafo** | Collegare le cose: file ↔ progetti ↔ persone ↔ eventi, nel tempo. | Riusa il **graph_engine + knowledge_mapper di SONAR**. |

**Decisione chiave:** Argo tiene una **memoria propria leggera** (strati 1–2, sempre disponibile) e usa **SONAR come memoria profonda** (strati 3–4) quando serve ragionare su contenuti e relazioni. Così non reinventiamo nulla, e Argo funziona anche da solo.

*Riferimenti 2026:* il pattern vincente è "vector + episodico + grafo, con l'agente che instrada tra loro" (Letta / Zep-Graphiti / Mem0). SONAR implementa già pgvector + knowledge graph: noi ci appoggiamo lì.

---

## 7. Stack tecnico (locale, su 8 GB, di tua proprietà)

| Pezzo | Scelta | Note |
|---|---|---|
| Linguaggio | **Python** | veloce, già usato in SONAR, riuso diretto. |
| Cervello (LLM) | **Ollama** | oggi `llama3.1`. Upgrade consigliati per 8 GB: **Qwen3 8B** o **Llama 3.3 8B** (Q4_K_M ≈ 5 GB). Per tool-calling/agente: **Gemma 3/4** è tra le migliori. |
| Embeddings | **nomic-embed-text** | leggero, gira su CPU, 8192 token. (SONAR usa anche `bge-m3`.) |
| Memoria propria | **SQLite** (+ vettori) | semplice, robusto, cresce su disco. |
| Memoria profonda | **SONAR** (pgvector + graph) | via API, senza toccarlo. |
| Interfaccia | **Tkinter** | finestra leggera sempre in primo piano; niente da installare. |
| Avvio | `.bat` + Esecuzione automatica | parte da solo all'accensione. Niente Docker per Argo (è un'app desktop). |

> Nota onesta sul cervello: la memoria rende Argo *più sapiente e più tuo*, non alza il QI grezzo del modello. Per fare il Custode del PC non serve un genio: serve un modello discreto + memoria + mani. Gli 8 GB bastano.

---

## 8. Cosa riusiamo da SONAR (mappa — senza modificarlo)

SONAR ha già costruito pezzi che a noi servono. Li **leggiamo/chiamiamo**, non li tocchiamo.

| Serve ad Argo | Modulo in SONAR |
|---|---|
| Parlare con Ollama | `services/llm_router.py`, `services/think_engine.py` |
| Capire documenti (sensi sul contenuto) | `core/document_parser.py`, `services/file_processor.py`, `services/ingest/` |
| Memoria semantica (vettori) | `core/vector_store.py`, `core/embedding_cache.py` |
| Memoria a grafo | `core/graph_engine.py`, `services/knowledge_mapper.py`, `core/ner_hybrid.py` |
| Ricordare le tue abitudini | `core/user_profile_engine.py`, `core/personalized_retriever.py`, `services/personalization.py` |
| Agire in sicurezza (mani + guardia) | `sandbox/agent_worker.py`, `sandbox/space.py`, `services/sentinel_guard.py` |
| Coda di lavori in background | `services/job_queue.py`, `services/job_worker.py` |

Due strade per collegarli, da decidere allo step memoria: (A) **chiamare l'API REST di SONAR**, oppure (B) **importare i moduli** come libreria. Probabilmente A (più pulito, nessun accoppiamento).

---

## 9. Il modello di autonomia (3 livelli)

Per ogni tipo di compito, Davide sceglie quanto Argo può osare. Se non scegli, vale il default sicuro.

1. **🟢 OSSERVA** — guarda e basta. Ti segnala, non tocca niente.
2. **🟡 CHIEDE** *(default)* — propone l'azione, tu approvi con un click. Niente sorprese.
3. **🔴 AGISCE** — fa da solo e ti avvisa dopo. Solo per compiti di cui ti fidi.

Esempio: "ordinare i Download → 🔴 agisce", "cancellare file → 🟡 chiede sempre", "toccare cartelle di sistema → 🟢 osserva". Le scelte si salvano in memoria: Argo le rispetta sempre.

---

## 10. Struttura della cartella ARGO

```
Desktop/Argo/
├── argo.py                 # corpo: finestra + loop di vita (orchestratore)
├── cervello.py             # testa: client Ollama            ✅ fatto
├── sensi/                  # occhi: watcher file, stato sistema
├── memoria/                # SQLite + profilo + ponte verso SONAR
├── mani/                   # azioni: sposta/rinomina/ordina (con guardrail)
├── config/                 # regole di autonomia, cartelle sorvegliate
├── avvia_argo.bat          # avvio manuale                   ✅ fatto
├── installa_avvio_automatico.bat   # avvio all'accensione    ✅ fatto
├── PROGETTO_ARGO.md        # questo documento
└── COME_AVVIARE.md         # istruzioni d'uso                ✅ fatto
```

---

## 11. Roadmap a fasi (ogni fase funziona da sola)

- **Fase 0 — Respiro** ✅ *fatto.* Finestra viva, ti saluta, sorveglia una cartella, ragiona con Ollama sui cambiamenti.
- **Fase 1 — Memoria propria.** SQLite: Argo ricorda cosa ha visto/fatto tra una sessione e l'altra. + profilo di Davide.
- **Fase 2 — Mani sicure.** Argo agisce sui file (ordina/rinomina) col modello di autonomia a 3 livelli e i guardrail.
- **Fase 3 — Custode completo.** Regole, cartelle multiple, abitudini apprese. Il primo mestiere è *finito e usabile ogni giorno*.
- **Fase 4 — Memoria profonda.** Ponte verso SONAR: Argo capisce il *contenuto* dei file e li collega nel grafo.
- **Fase 5 — Si allarga.** Secondo mestiere verso il dominio sistema/IT (dove ci sono i soldi).

Regola: non si passa alla fase dopo finché quella prima non gira davvero.

---

## 12. Cosa NON facciamo (per non perderci)

- ❌ Non costruiamo "l'IA che fa tutto" subito. Un mestiere alla volta.
- ❌ Non addestriamo modelli (gli 8 GB non bastano e non serve).
- ❌ Non mettiamo Argo in Docker (è un'app desktop con finestra e accesso ai file).
- ❌ Non tocchiamo SONAR. Lo usiamo, non lo modifichiamo.
- ❌ Niente AGI, niente promesse di trilioni. Una cosa vera che gira, poi si cresce.

---

## 13. Fonti (ricerca stato dell'arte 2026)

- [The 10 Best AI Memory Layers for Agents in 2026 — DEV](https://dev.to/jonathanfarrow/the-10-best-ai-memory-layers-for-agents-in-2026-448e)
- [Best AI Agent Memory Frameworks in 2026 — Atlan](https://atlan.com/know/best-ai-agent-memory-frameworks-2026/)
- [AI Agent Memory 2026: Mem0 vs Zep vs Letta vs Cognee — DEV](https://dev.to/agdex_ai/ai-agent-memory-in-2026-mem0-vs-zep-vs-letta-vs-cognee-a-practical-guide-cfa)
- [Best Local LLMs for 8GB VRAM (2026) — LocalLLM.in](https://localllm.in/blog/best-local-llms-8gb-vram-2025)
- [Best LLM Models for 8GB VRAM in 2026 — InferenceRig](https://inferencerig.com/models/best-llm-models-for-8gb-vram-in-2026-tested-and-ranked/)
- [Best Local Embedding Models 2026 — Morph](https://www.morphllm.com/ollama-embedding-models)
- [Best Open-Source LLMs to Run Locally 2026 — Hugging Face](https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally)
