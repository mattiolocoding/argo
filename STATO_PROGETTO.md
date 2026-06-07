# 📒 ARGO — Diario di progetto (stato vivo)

> Il registro di tutto ciò che è stato costruito. **Si aggiorna ad ogni sessione.**
> Ultimo aggiornamento: **6 giugno 2026**
> Legenda: ✅ fatto e testato · 🟡 fatto, da testare · ⬜ da fare

---

## Cos'è ARGO
Un essere digitale che vive sul PC Windows di Davide: osserva, ricorda, impara,
agisce in sicurezza e risponde. 100% locale, di proprietà dell'utente.
**Indipendente da SONAR** (progetto separato: nessuna dipendenza, nessun file condiviso).

## Principi
Niente di provvisorio · si va per task/microtask · si testa dopo ogni passo ·
memoria che cresce = il fossato. Visione completa in `ARGO_VISIONE_ENTERPRISE.md`,
piano in `PIANO_LAVORO.md`, test in `TEST_DA_FARE.md`.

---

## Architettura attuale
```
ARGO (app desktop locale)
├─ argo.py            UI moderna (chat + conversazione) + orchestratore
├─ cervello.py        Ollama (auto-accensione + riconnessione)
├─ memoria/
│   ├─ memoria.py     diario episodico + profilo + abitudini (SQLite)
│   ├─ grafo.py       knowledge graph: nodi/archi (SQLite)
│   └─ semantica.py   memoria vettoriale: embeddings Ollama (SQLite)
├─ mani/mani.py       azioni file sicure (archivia/sposta/rinomina) + duplicati
├─ config/            impostazioni + autonomia 3 livelli (config.json)
├─ sistema.py         sensi di sistema (disco, processi)
├─ comprensione.py    capisce il contenuto dei file testuali
└─ produzione/        architettura di rilascio
    ├─ motore.py          engine headless + API locale (127.0.0.1:8773)
    ├─ interfaccia.py     finestra-client (la chiudi, il motore vive)
    ├─ installa_servizio.py  avvio automatico (NSSM / schtasks)
    └─ build/             primo_avvio.py · argo.spec · installer.iss · COSTRUISCI.md
```

---

## Stato per componente

| Componente | Stato | Note |
|---|---|---|
| Finestra + saluto + memoria | ✅ | testato dal vivo |
| Cervello Ollama + riconnessione | ✅ | reboot autostart confermato |
| Memoria episodica + profilo | ✅ | persistenza verificata |
| Mani sicure + guardrail + Sì/No | ✅ | testato dal vivo (immagine→Immagini) |
| Multi-cartella / regole / duplicati / accumuli | 🟡 | scritto, da testare |
| Apprendimento abitudini | 🟡 | scritto, da testare |
| Comprensione contenuto (Fase 4) | 🟡 | scritto, da testare |
| Sensi di sistema (Fase 5) | 🟡 | scritto, da testare |
| **Knowledge graph (memoria/grafo.py)** | 🟡 | nuovo, da testare |
| **Memoria semantica (memoria/semantica.py)** | 🟡 | nuovo, serve `ollama pull nomic-embed-text` |
| **UI moderna WEB (motore_web.py + ui/index.html)** | 🟡 | nuova, look 2026, da testare. Sostituisce Tkinter |
| Tkinter argo.py | ⚠️ | versione "classica" legacy (look datato), tenuta come riferimento |
| Riepilogo all'avvio B9 | 🟡 | implementato nel motore web |
| Occhi su tutto il PC | 🟡 | cartelle utente, da testare |
| Motore + UI + servizio (Fase A) | 🟡 | scritto, da testare |
| Installer (Fase Finale) | 🟡 | script pronti, da costruire |
| **Timeline cognitiva** | ✅ | eventi/file/chat/azioni/rifiuti/pattern/lacune |
| **World Model v0** | ✅ | ipotesi, lacune, piani governati, proposte operative |
| **Deliberatore** | ✅ | `pensatore.py`, best-of-3 + verificatore per domande complesse |
| **Diario interno** | ✅ | `cognizione/diario_interno.py`, riflessioni persistenti |
| **Obiettivi permanenti** | ✅ | `cognizione/obiettivi.py`, direzioni a lungo termine |
| **Esperimenti cognitivi** | ✅ | `cognizione/esperimenti.py`, registro A/B strategie |
| **Sonno + skill synthesis** | 🟡 | pipeline proposta/sandbox/approvazione presente, da maturare |

---

## Cosa sa fare ARGO oggi (concreto)
- Vive in finestra moderna, ti saluta, **chatti con lui** (casella in basso).
- **Occhi su tutto il PC**: sorveglia Desktop, Download, Documenti, Immagini,
  Musica, Video (+ `sorvegliata/`). Reagisce ai file nuovi.
- **Ordina i file** per tipo/data/progetto, chiedendo conferma (o da solo, se glielo dici).
- **Riconosce i doppioni** e segnala gli **accumuli**.
- **Impara**: smette di proporre ciò che rifiuti, fa da solo ciò che accetti sempre.
- **Ricorda** tutto tra le sessioni e costruisce un **grafo** delle relazioni.
- **Memoria semantica**: ritrova per significato (con `nomic-embed-text`).
- Si **riaccende il cervello** da solo e parte all'avvio del PC.

---

## Roadmap enterprise rimanente (prossimi strati)
- 🟡 Agenti specializzati + registro skill (società di menti)
- 🟡 Auto-creazione di skill (proposta/sandbox/approvazione presente, da rendere utile)
- 🟡 "Sonno" di consolidamento della memoria (presente, da rendere stabile e quotidiano)
- ✅ World model / anticipazione proattiva v0
- ✅ Sentinel: policy di sicurezza e audit avanzati v0
- ⬜ Diario errori esplicito: `errore -> correzione Davide -> test -> esito`
- ⬜ Workflow reali end-to-end su email/browser/calendario/app
- ⬜ Multi-istanza / flotta + apprendimento federato (livello aziendale)
- ⬜ Voce e presenza · mobile · (IoT/robotica = orizzonte lungo)

> Questi strati richiedono più sessioni e, alcuni, infrastruttura/hardware: si
> costruiscono sopra il cuore locale già pronto, uno alla volta, testando.

---

## Changelog
- **2026-06-06**
  - Rimosso il ponte SONAR: ARGO 100% indipendente.
  - Aggiunta memoria enterprise: `grafo.py` (knowledge graph) e `semantica.py` (vettoriale).
  - UI riscritta (v1.0): conversazione + chat + occhi estesi alle cartelle utente.
  - Aggiunte Fasi 3/4/5 + kit produzione (motore/UI/servizio/installer).
  - Memoria propria, mani sicure, cervello robusto: testati.
  - Creato questo diario.

- **2026-06-06 (2)** — dopo feedback "UI anni '90":
  - Nuova **UI moderna 2026** web (`motore_web.py` + `ui/index.html`): finestra
    scura, avatar, pill di stato, bolle chat, proposte come card. Apertura in
    finestra nativa (pywebview) o browser. Sostituisce Tkinter.
  - **Riepilogo all'avvio (B9)** implementato.
  - Motore al root: niente trucchi di path → packageable, apre davvero la 8773.
  - `avvia_argo.bat` ora lancia la UI web.

- **2026-06-06 (3)** — dopo feedback (allucinazione + sicurezza + app desktop):
  - **Anti-allucinazione**: la chat ora risponde SOLO dai dati reali della memoria
    (azioni/file di oggi); PERSONA aggiornata: vietato inventare. Rimosso il recall
    semantico che portava dati finti del test.
  - **Sicurezza avanzata** (`sicurezza.py`): file/segreti sensibili mai letti né
    indicizzati né spostati; **audit a catena di hash** (a prova di manomissione,
    endpoint `/audit`); chiave locale protetta con **DPAPI** + cifratura opzionale.
  - **App desktop vera**: apertura in Edge/Chrome `--app` (niente barre) o pywebview;
    non più semplice scheda browser.
  - **Pulsante modalità** in UI: 👁 Osserva / ✋ Chiede / ⚡ Agisci (endpoint /autonomia).
  - Test del modulo semantico ora su db temporaneo (non sporca la memoria vera).

- **2026-06-06 (4)** — nucleo cognitivo:
  - Aggiunti `cognizione/diario_interno.py`, `cognizione/obiettivi.py`,
    `cognizione/esperimenti.py`.
  - `motore_web.py` collega diario/obiettivi/esperimenti a chat deliberata,
    `/pensiero`, `/consolida`, `/sonno`, `/rifletti`, `/dashboard`.
  - Console aggiornata con Diario interno, Obiettivi permanenti, Esperimenti cognitivi.
  - Test: compilazione OK, `test_sicurezza.py` 123 OK/0 FAIL, `pensatore.py` OK,
    `esperimento_apprendimento.py` baseline 0/4 -> memoria 4/4.

- **2026-06-06 (4)** — "deve essere un'app desktop con logo":
  - **`argo_app.py`**: applicazione desktop NATIVA via pywebview (finestra con barra
    del titolo, icona, taskbar) — non più scheda browser. Si auto-installa pywebview.
  - **Logo ARGO** disegnato (`assets/logo.svg`), embeddato nell'header della UI.
  - `avvia_argo.bat` ora lancia `argo_app.py`.
  - Per l'icona in taskbar/installer: convertire `assets/logo.svg` in `logo.ico`/`logo.png`
    (vedi build) — opzionale, l'app funziona comunque.

- **2026-06-06 (5)** — "no Edge, vera app desktop":
  - `argo_app.py` riscritto: **app desktop NATIVA con Qt (PySide6 + QWebEngine)**.
    Finestra vera, titolo "ARGO", **icona ARGO in taskbar** (QIcon da logo.svg +
    AppUserModelID). Niente più Edge/browser/scheda. Auto-install PySide6 con
    piccola finestra di avanzamento (no terminale).
  - Per il packaging: l'app è ora Qt — l'installer dovrà includere PySide6
    (PyInstaller con hook QtWebEngine). Da aggiornare in build quando ci arriviamo.

- **2026-06-06 (6)** — rifiniture dopo test di Davide:
  - **Icona ARGO**: generata a runtime dall'SVG con QSvgRenderer (più misure) →
    appare in finestra e taskbar (prima Qt non rendeva l'SVG).
  - **Stop al flood duplicati**: ricerca duplicati + accumuli ora SOLO nelle cartelle
    dedicate (`sorvegliata`), non nei Download/Desktop. Gli "occhi su tutto il PC"
    restano per i soli file NUOVI → test puliti possibili.

- **2026-06-06 (7)** — SALTO ENTERPRISE (governo dell'azione + agenti in parallelo):
  - **Policy engine** (`governo/policy.py`): esiti Consenti/Escala/Blocca a runtime
    (es. contratti bloccati, HR/fiscali sempre conferma). Applicato nel motore.
  - **Ruoli/RBAC** (`governo/ruoli.py`): admin/operatore/auditor/utente; endpoint protetti.
  - **Audit pro**: export JSON, ricerca, report, sigillo (`/audit`, `/audit/export`).
  - **Rollback/Annulla** (`governo/rollback.py`): ogni azione reversibile, pulsante Annulla.
  - **Metriche** (`governo/metriche.py`): azioni, rifiuti, rischi evitati, tempo risparmiato.
  - **Consolidamento "sonno"** (`governo/consolidamento.py`): riassunto serale automatico.
  - **Agenti specializzati** (`governo/agenti.py`): Diagnostico/Auditor/Guardiano/Archivista/Analista.
  - **Dashboard Console** nella UI: metriche, audit, agenti, annulla, consolida, export.
  - Costruiti da AGENTI in parallelo (verificati e collegati):
    - **Sonno + Skill synthesis** (`governo/sonno.py`, `lacune.py`, `skill_registry.py`,
      `sandbox_skill.py`, `skill_writer.py`): osserva→lacuna→genera skill→analisi
      sicurezza→sandbox→**proposta in attesa di approvazione umana** (mai auto-attiva).
    - **Workflow engine** (`workflow.py`): flussi multi-step con approval gate e audit.
    - **Connettori** (`connettori/`): email IMAP (sola lettura), filesystem, git.
    - **Model mesh** (`modelli.py`): riflesso/ragionatore/esperto con routing per complessità.
    - **Sensi estesi** (`sensi.py`): finestra attiva, rete, appunti (solo metadati, privacy).
  - Endpoint nuovi: /dashboard /metriche /audit(/export) /annulla /agente /consolida
    /sonno /sensi /modelli /connettori /skills /skill/approva.

- **2026-06-06 (8)** — round fix + UI frontier + permessi + cybersecurity (5 agenti):
  - **Cybersecurity**: `sicurezza.py` indurito (22 pattern segreti, `percorso_sicuro` anti
    path-traversal, audit con retention + redazione pre-hash), `SICUREZZA_REPORT.md`,
    `test_sicurezza.py`. Patch applicate: whitelist agenti, niente path assoluto in
    /audit/export, `import os`/`urllib`/`requests` bloccati nel sandbox skill.
  - **Skill/sonno**: corretti i bug (sandbox IndentationError, sonno/connettori/governo
    eseguibili come script E come `-m`), aggiunto `governo/validator.py` e pipeline
    proposta→approvata→attiva (attivazione solo con approvazione umana).
  - **UI di frontiera**: `ui/index.html` riscritta con SIDEBAR (Chat/Console/Permessi/
    Audit), look 2026, animazioni; saluto meno robotico.
  - **Permessi**: `config/permessi.py` + onboarding al 1° avvio (Tutto il PC / Solo
    cartelle scelte / Niente). Motore: endpoint /permessi (GET/POST), /console, e
    `_costruisci_cartelle()` rispetta i permessi (ARGO vede solo ciò che autorizzi).
  - **Packaging** rifatto per l'app Qt: `argo.spec` (collect_all PySide6/QtWebEngine),
    `fai_icona.py` (svg→ico), `primo_avvio.py`, `installer.iss`.
  - Creato `RICHIESTE_VS_IMPLEMENTATO.md` (mappa richieste↔stato).

- **2026-06-07** — sessione "migliora + impeccable + scala + open source":
  - **Ambiente**: installato Python 3.11.9 + `.venv` dedicato; impeccable in `.claude/skills`; git inizializzato.
  - **Verifica base**: compila tutto, 17 self-test moduli OK, motore vivo, tutti gli endpoint 200
    (inclusi `/console` e `/audit`: i bug dei resoconti risultano già risolti).
  - **Fix model-mesh** (`modelli.py`): esclusi i modelli di *embedding* (bge-m3, nomic) dai ruoli
    chat; 14b→grande. Ora riflesso=qwen2.5:7b, ragionatore=llama3.1:8b, esperto=qwen2.5:14b.
  - **Frontend impeccable** (`ui/index.html`): polish (anti-pattern detector 2→0): contrasto WCAG,
    tipografia, motion + `prefers-reduced-motion`, focus-visible/ARIA, lighting intenzionale.
    Selettori JS e 27 endpoint preservati.
  - **Scaling orizzontale (flotta)**: `fleet.py` + endpoint `/identita` e `/flotta`; HOST/PORT/identità
    configurabili da ambiente. Verificato dal vivo con 2 istanze (8773+8774) → flotta vede 2 online.
  - **Scaling verticale**: confermato che il workflow engine è già integrato nel motore
    (`/workflow`, `/workflow/avvia`, `/workflow/approva` con audit+timeline).
  - **Open source**: README (EN), LICENSE (MIT), CONTRIBUTING, SECURITY, CoC, CI GitHub Actions,
    issue/PR template, PRODUCT.md. (Non ancora pushato.)

## Mancano ancora (verso la visione piena)
Workflow profondi nel motore, KG temporale serio, fleet/multi-istanza, mobile/voce,
packaging firmato + auto-update, apprendimento federato, marketplace skill. Sono i
prossimi strati: si costruiscono sopra questo governo, con cautela e test.

## Sicurezza — stato
| Difesa | Stato |
|---|---|
| File/segreti sensibili non toccati | 🟡 fatto, da testare (SEC1/SEC2) |
| Audit immutabile (hash-chain) | 🟡 fatto, da testare (SEC3) |
| Chiave locale protetta (DPAPI) | 🟡 fatto, da testare |
| Cifratura a riposo dati | ⚠️ opzionale (richiede `pip install cryptography`) |
| Solo locale (127.0.0.1, nessun dato esce) | ✅ per design |

## Da fare subito (debito test)
Appena l'ambiente di verifica è stabile: `py_compile` di tutti i file + test moduli
(`grafo.py`, `memoria.py`, `mani.py`, `sistema.py`). Poi i test dal vivo di `TEST_DA_FARE.md`.
