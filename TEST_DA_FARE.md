# ✅ ARGO — Tutti i test da fare (in ordine)

> Tutto si lancia dal **Prompt dei comandi** dentro la cartella `Desktop\Argo`.
> Per ogni test c'è il comando e cosa devi vedere. Segna ✅ man mano.
> Se qualcosa non torna, copiami l'output e lo sistemiamo.

**Prerequisiti:** Python installato · Ollama installato (con un modello, es. `ollama pull llama3.1`).
**Per la finestra nativa moderna (consigliato):** `pip install pywebview` (se non c'è, ARGO si apre nel browser — funziona uguale).

---

## 🔧 VERIFICA 0 — "compila e funziona?" (FAI QUESTA PER PRIMA)

Questa è la verifica che io non ho potuto eseguire (ambiente offline). Falla tu:

- [ ] **V0.1 — Tutto compila** (dalla cartella `Desktop\Argo`):
  ```
  python -c "import py_compile,glob;[py_compile.compile(f,doraise=True) for f in glob.glob('**/*.py',recursive=True) if '__pycache__' not in f and 'sorvegliata' not in f];print('COMPILA TUTTO OK')"
  ```
  Atteso: `COMPILA TUTTO OK`. Se esce un errore, copiamelo e lo sistemo.

- [ ] **V0.2 — Auto-test dei moduli** (ognuno deve finire con "OK" o output sensato):
  ```
  python memoria\memoria.py
  python memoria\grafo.py
  python mani\mani.py
  python config\impostazioni.py
  python sicurezza.py
  python sistema.py
  python governo\policy.py
  python governo\ruoli.py
  python governo\lacune.py
  python governo\skill_registry.py
  python governo\sandbox_skill.py
  python workflow.py
  python sensi.py
  python -m connettori
  python modelli.py
  python governo\sonno.py
  ```
  (Quelli che usano Ollama — modelli, sonno, semantica — degradano con grazia se Ollama è spento.)

---

## ⭐ 0 · NUOVA UI moderna (la cosa da provare per prima)

- [ ] **0.1 — Avvio ARGO come APP DESKTOP NATIVA (Qt)**
  `python argo_app.py`  (oppure doppio click su `avvia_argo.bat`)
  Al primo avvio appare una piccola finestra "installo i componenti" (installa
  PySide6, 1-2 min, solo la prima volta), poi si apre la **vera finestra desktop**:
  barra del titolo "ARGO", **icona ARGO nella taskbar**, interfaccia dentro.
  NON un browser, NON Edge, NON una scheda. Se l'installazione fallisce, ti dice di
  fare `pip install PySide6`.

- [ ] **0.2 — Riepilogo all'avvio (B9)**
  Se hai già sistemato file oggi, nel saluto compare "Oggi ho già sistemato N file".

- [ ] **0.3 — Chat moderna**
  Scrivi nella barra in basso e premi Invia → risposta a bolle (serve Ollama).

- [ ] **0.4 — Proposta come card**
  Metti un file in `sorvegliata\` → appare una **card PROPOSTA** con Sì/No. Premi Sì → sistemato.

- [ ] **0.5 — Il motore apre la porta**
  Con ARGO avviato, apri nel browser `http://127.0.0.1:8773/stato` → vedi un JSON con lo stato.

- [ ] **0.6 — Logo e icona**
  Verifica che il **logo ARGO** (muso su sfondo viola) sia nell'header della finestra
  e nella taskbar. Se la dipendenza non si installa: `pip install pywebview` e riprova.

- [ ] **0.7 — Chat fondata sui dati reali (anti-allucinazione)**
  Chiedi "cosa hai sistemato oggi?". Atteso: risponde SOLO con file/azioni veri di
  oggi; se non ha fatto nulla lo dice. NON deve inventare (niente PayPal/Sardegna ecc.).

- [ ] **0.8 — Pulsante modalità**
  In alto: 👁 Osserva / ✋ Chiede / ⚡ Agisci. Clicca → cambia come ARGO opera.
  In "Osserva" non agisce; in "Chiede" mostra la card; in "Agisci" fa da solo.

## 🔒 Sicurezza (il punto cruciale)

- [ ] **SEC1 — File sensibili intoccabili**
  Metti in `sorvegliata\` un file tipo `password.txt` o `chiave.pem`.
  Atteso: ARGO dice "Ho visto un file sensibile: non lo tocco e non lo memorizzo." e NON lo sposta.

- [ ] **SEC2 — Modulo sicurezza**
  `python sicurezza.py`
  Atteso: rileva 'password.txt' sensibile, segreti nel testo, audit integro, "OK sicurezza".

- [ ] **SEC3 — Audit a prova di manomissione**
  Con ARGO avviato apri `http://127.0.0.1:8773/audit` → `{"integro": true, "voci":[...]}`.
  Registra ogni azione in catena di hash.

---

## A · Moduli di base (veloci, non serve la finestra)

- [ ] **A1 — Cervello / Ollama**
  `python cervello.py`
  Atteso: `[OK] Tutto ok. Modelli: …` e una frase di presentazione. Se dice
  "spento", prova ad aspettare: ora prova ad accenderlo da solo.

- [ ] **A2 — Memoria**
  `python memoria\memoria.py`
  Atteso: stampa "Accesso n.X", episodi che crescono. Rilancialo: il numero sale → ricorda.

- [ ] **A3 — Impostazioni / autonomia**
  `python config\impostazioni.py`
  Atteso: mostra cartelle sorvegliate, regola, e i livelli di autonomia.

- [ ] **A4 — Mani (a secco, non sposta niente)**
  `python mani\mani.py`
  Atteso: categoria di foto.png = Immagini; `sicuro 'C:/Windows/x'? False` (guardrail ok).

- [ ] **A5 — Sistema**
  `python sistema.py`
  Atteso: riga sul disco (GB liberi) + elenco processi più pesanti.

---

## B · Il Custode (la finestra) — Fasi 0,1,2,3

- [ ] **B1 — Avvio + saluto + memoria (Fasi 0-1)**
  `python argo.py`
  Atteso: si apre la finestra, ti saluta. Chiudi e riapri: ti dice "Bentornato,
  l'ultima volta…". In basso: "Cervello connesso • Ricordi: N".

- [ ] **B2 — Riconnessione cervello (Fase R)**
  Chiudi Ollama (dalla tray), guarda la finestra → "Cervello offline, lo sto
  accendendo…", e dopo qualche secondo deve tornare **connesso da solo**.
  *(Hai già confermato che dopo il reboot riparte: ✔)*

- [ ] **B3 — Archiviazione con conferma (Fase 2)**
  Metti una foto o un PDF in `Desktop\Argo\sorvegliata\`.
  Atteso: Argo propone "Sposterei «…» nella cartella «Immagini/Documenti». Procedo?"
  con i bottoni **Sì/No**. Premi **Sì** → il file finisce nella sottocartella.

- [ ] **B4 — Più cartelle (Fase 3.1)**
  In `config\config.json` aggiungi a `cartelle_sorvegliate` il percorso dei
  Download (es. `"C:\\Users\\Tufilli Davide\\Downloads"`), riavvia Argo, metti un
  file lì → deve accorgersene.

- [ ] **B5 — Regola d'ordine (Fase 3.2)**
  In `config\config.json` metti `"regola_ordine": "data"`, riavvia, aggiungi un
  file → deve proporre una cartella tipo `2026-06`. (Prova anche `"progetto"`.)

- [ ] **B6 — Duplicati (Fase 3.3)**
  Metti due copie identiche (stesso contenuto) in `sorvegliata\`.
  Atteso: entro ~1 minuto propone di mettere il doppione in «Duplicati».

- [ ] **B7 — Accumuli (Fase 3.3)**
  Metti più di 10 file in una cartella sorvegliata → ti avvisa dell'accumulo.

- [ ] **B8 — Impara le abitudini (Fase 3.4)**
  Rifiuta ("No") più volte la stessa categoria → col tempo smette di proporla.
  Accettala sempre ("Sì") molte volte → inizia a farlo da solo. (La memoria cresce.)

- [ ] **B9 — Riepilogo (Fase 3.5)**
  Dopo aver sistemato dei file, riavvia Argo → ti dice "Oggi ho già sistemato N file".

- [ ] **B10 — Allerta disco (Fase 5)**
  Solo se il disco è oltre il 90% pieno: te lo segnala. (Altrimenti salta.)

- [ ] **B11 — Chat (UI moderna v1.0)**
  Nella casella in basso scrivi una domanda (es. "che cosa sai fare?") e premi Invia.
  Atteso: Argo risponde nell'area conversazione (serve Ollama acceso).

- [ ] **B12 — Occhi su tutto il PC**
  In basso deve dire "N cartelle" (>1). Metti un file nuovo nei **Download** →
  Argo se ne accorge e propone. (Disattivabile: `"occhi_tutto_pc": false` in config.)

---

## C · Memoria di frontiera — Fasi 4 + enterprise

- [ ] **C1 — Comprensione contenuto**
  `python comprensione.py percorso\di\un_file.txt`
  Atteso: una riga di riassunto + una categoria suggerita (serve Ollama acceso).

- [ ] **C2 — Knowledge graph**
  `python memoria\grafo.py`
  Atteso: stampa i "vicini" di foto_mare.png e le statistiche, poi "OK grafo".

- [ ] **C3 — Memoria semantica (embeddings)**
  Prima: `ollama pull nomic-embed-text` (una volta). Poi: `python memoria\semantica.py`
  Atteso: cerca "spiaggia" trova "vacanze al mare" anche senza la parola. Se dice
  "Embeddings non disponibili", manca il modello: fai il pull qui sopra.

*(Nota: il ponte con SONAR è stato RIMOSSO. ARGO è indipendente.)*

---

## D · Architettura motore + finestra — Fase A (cartella `produzione\`)

- [ ] **D1 — Motore in background**
  `python produzione\motore.py`
  Atteso: "[MOTORE] avvio su http://127.0.0.1:8773". Lascialo aperto.

- [ ] **D2 — Finestra collegata al motore**
  In un altro Prompt: `python produzione\interfaccia.py`
  Atteso: la finestra mostra lo stato che arriva dal motore.

- [ ] **D3 — La finestra si chiude, il motore vive**
  Chiudi la finestra → il motore (D1) continua a girare. Riapri la finestra → si
  ricollega. *(Questo è il cuore dell'architettura che volevi.)*

- [ ] **D4 — Proposte + chat via motore**
  Metti un file in `sorvegliata\` → la finestra mostra la proposta con Sì/No.
  Scrivi nella chat in basso una domanda → Argo risponde (usa Ollama).

- [ ] **D5 — Avvio automatico del motore**
  `python produzione\installa_servizio.py`
  Atteso: crea il servizio (NSSM) o l'attività pianificata. Riavvia il PC → il
  motore deve essere già attivo (apri solo la finestra).

---

## E · Installer — Fase Finale (cartella `produzione\build\`)

- [ ] **E1 — Primo avvio (dev)**
  `python produzione\build\primo_avvio.py`
  Atteso: accende Ollama, scarica il modello se manca, avvia motore + finestra.

- [ ] **E2 — Build e installer**
  Segui `produzione\build\COSTRUISCI.md`: `pyinstaller argo.spec` poi compila
  `installer.iss` con Inno Setup → ottieni **`ARGO Setup.exe`**.

- [ ] **E3 — Prova su macchina pulita**
  Installa con `ARGO Setup.exe` → al primo avvio scarica il modello → parte da solo.

---

## 🏛 ENTERPRISE — Governo dell'azione & moduli nuovi

> Prima i moduli da soli (veloci, dalla cartella `Desktop\Argo`), poi nell'app (Console).

### Moduli governo (standalone)
- [ ] **EN1 — Policy** `python governo\policy.py` → contratto = blocca, busta_paga = escala, foto = consenti.
- [ ] **EN2 — Ruoli** `python governo\ruoli.py` → stampa i permessi per ruolo.
- [ ] **EN3 — Rollback** (testato nell'app, vedi EN13).
- [ ] **EN4 — Sonno/Skill** `python governo\sonno.py` → "OK" (cerca lacune, propone skill in sandbox).
- [ ] **EN5 — Lacune** `python governo\lacune.py` → "OK". **Skill registry** `python governo\skill_registry.py` → "OK".
- [ ] **EN6 — Sandbox skill** `python governo\sandbox_skill.py` → blocca codice pericoloso, "OK".
- [ ] **EN7 — Workflow** `python workflow.py` → i 5 test (blocco sensibile, gate+approva+archivia, report) "OK".
- [ ] **EN8 — Connettori** `python -m connettori` → elenca disponibili/non; `python connettori\git.py` "OK".
- [ ] **EN9 — Model mesh** `python modelli.py` → mostra riflesso/ragionatore/esperto (o avvisa se Ollama spento).
- [ ] **EN10 — Sensi** `python sensi.py` → finestra attiva, rete, info appunti (senza contenuti), "OK".

### Nell'app (vista Console)
- [ ] **EN11 — Vista Console** Avvia ARGO, in alto premi **📊 Console**. Atteso: card con
  Operatività, Memoria, Governo (ruolo, policy, audit integro), Agenti, Azioni, Sistema cognitivo.
- [ ] **EN12 — Metriche** I numeri (azioni, file visti, rischi evitati, tempo risparmiato) sono coerenti.
- [ ] **EN13 — Annulla (rollback)** In `sorvegliata\` metti un file, in modalità **Agisci** lo fa spostare
  (o conferma Sì). Poi Console → **↩ Annulla ultima azione** → il file torna dov'era.
- [ ] **EN14 — Policy runtime** Metti in `sorvegliata\` un file con nome tipo `Contratto_2025.pdf`
  → ARGO dice "🛡 Policy: non procedo" e NON lo tocca. Con `busta_paga.pdf` → chiede SEMPRE conferma.
- [ ] **EN15 — Agenti** Console → premi un agente (Diagnostico/Auditor/Guardiano/…) → mostra il report.
- [ ] **EN16 — Consolida** Console → **💤 Consolida memoria ora** → riassunto della giornata.
- [ ] **EN17 — Export audit** Console → **⬇ Esporta audit** → crea `audit_export.json` (per compliance).
- [ ] **EN18 — Sistema cognitivo** Console → 👁 Sensi, 🧠 Model mesh, 🔌 Connettori, 🌙 Sonno: ognuno risponde.
- [ ] **EN19 — RBAC** In `config\config.json` metti `"ruolo": "auditor"`, riavvia: provare a confermare/agire
  deve essere **negato**; vedere/esportare audit invece consentito. (Rimetti `"ruolo": "admin"` dopo.)
- [ ] **EN20 — Skill in attesa di approvazione** Dopo un "sonno", apri `http://127.0.0.1:8773/skills`:
  eventuali skill proposte risultano in stato **proposta** (mai attive senza tua approvazione).

## 🆕 ROUND FIX + UI FRONTIER + PERMESSI + CYBERSECURITY (ultima tornata)

### Bug del tuo resoconto — ora dovrebbero passare
- [ ] **FX1 — sandbox skill** `python governo\sandbox_skill.py` → caso "skill sicura" esegue, codice pericoloso bloccato. (era IndentationError)
- [ ] **FX2 — connettori** `python -m connettori` e `python connettori\git.py` → "OK" (creato `__main__.py`, import difensivi).
- [ ] **FX3 — sonno diretto** `python governo\sonno.py` → "OK" (bootstrap sys.path). Anche `python -m governo.sonno`.
- [ ] **FX4 — validator (nuovo)** `python governo\validator.py` → "OK" (valida: sicurezza + `def esegui(contesto)` + sandbox).
- [ ] **FX5 — skill registry pipeline** `python governo\skill_registry.py` → `attiva()` fallisce se NON approvata, riesce dopo `approva()` (proposta→approvata→attiva).
- [ ] **FX6 — /console** Avvia ARGO, apri `http://127.0.0.1:8773/console` → ora ritorna la dashboard (non più `{"argo":"ok"}`).

### UI di frontiera + Permessi
- [ ] **UX1 — Nuovo look** Avvia ARGO: sidebar a sinistra (Chat / Console / Permessi / Audit), header con logo, pill animate. Più "azienda 2026".
- [ ] **UX2 — Onboarding permessi (primo avvio)** Se è la prima volta (o premi "Modifica permessi"), appare la schermata: **Tutto il PC / Solo cartelle che scelgo / Niente**. Scegli "Solo cartelle", aggiungi una cartella, conferma.
- [ ] **UX3 — Permessi rispettati** Dopo aver scelto "Solo cartelle che scelgo io" con una cartella X: ARGO sorveglia solo `sorvegliata` + X (controlla la pill "cartelle" e che non tocchi i Download). `python config\permessi.py` → "OK".
- [ ] **UX4 — Permessi via API** `http://127.0.0.1:8773/permessi` → JSON con modo/cartelle/onboarding_fatto.
- [ ] **UX5 — Saluto meno robotico** All'avvio il saluto è più naturale (niente "Ho N ricordi" meccanico).

### Cybersecurity (agente dedicato)
- [ ] **CY1 — Suite sicurezza** `python sicurezza.py` e `python test_sicurezza.py` → "TUTTI I TEST SUPERATI".
- [ ] **CY2 — Report** Apri `SICUREZZA_REPORT.md`: leggi le vulnerabilità trovate (con severità) e cosa è stato indurito. Le voci "da applicare in altri file" segnate ALTA le ho già applicate (whitelist agenti, niente percorso assoluto nell'export audit, `import os` bloccato nel sandbox skill).
- [ ] **CY3 — Path traversal** Nel modulo: `percorso_sicuro(base,target)` blocca i `..` fuori dalla base (vedi test_sicurezza).

### Packaging (rifatto per l'app Qt)
- [ ] **PK1 — Icona** `pip install pillow` poi `python produzione\build\fai_icona.py` → crea `assets\logo.ico` + `logo.png`.
- [ ] **PK2 — Build** `pip install pyinstaller pillow` → `pyinstaller produzione\build\argo.spec` → in `dist\ARGO\` c'è `ARGO.exe`. Avvialo: deve aprire la finestra e `http://127.0.0.1:8773/stato`.
- [ ] **PK3 — Installer** Con Inno Setup installato: compila `produzione\build\installer.iss` → `ARGO Setup.exe`. (Serve `iscc` nel PATH.)

### Come dirmi com'è andato
Per ogni test: ✅ se ok, oppure incolla l'errore. Partiamo dai test **A** e **B**
(il cuore funzionante), poi C, D, E. Io intanto, appena torna il mio ambiente,
rieseguo i miei controlli automatici sui moduli.
