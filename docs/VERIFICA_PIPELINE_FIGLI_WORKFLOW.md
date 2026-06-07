# VERIFICA PIPELINE FIGLI ESPERTI + WORKFLOW

Data: 2026-06-07

## Problema verificato

Il riepilogo "Fatto" non corrispondeva completamente all'app reale:

- il sonno esisteva, ma spesso non produceva skill visibili;
- una skill attiva era rotta;
- il workflow funzionava solo come modulo standalone, non nell'app;
- la Console mostrava "Figli esperti", ma mancava una bonifica chiara delle skill rotte;
- il writer lasciava passare codice con esempi top-level e `print`.

## Fix applicati

### 1. Validatore skill piu' severo

File: `governo/validator.py`

- blocca codice top-level diverso da import sicuri + `def esegui(contesto)`;
- non accetta output sandbox non JSON;
- non accetta skill che non restituiscono un dizionario.

### 2. Skill writer piu' pulito

File: `governo/skill_writer.py`

- prompt aggiornato: vietati esempi, `print`, chiamate top-level;
- pulizia AST: mantiene solo import e funzione `esegui`;
- rimuove codice demo aggiunto dal modello dopo la funzione.

### 3. Sonno corretto

File: `governo/sonno.py`

- prima il filtro skill usava lacune lette dal DB senza `conteggio`, quindi il ciclo poteva scartare tutto;
- ora filtra sulle lacune del ciclo corrente, che hanno conteggio reale;
- se non ci sono lacune correnti usa lo storico come fallback.

### 4. Bonifica skill rotte

File: `governo/skill_registry.py`

- aggiunto `bonifica_non_valide()`;
- scarta skill proposte/approvate/attive che non passano Validator.

Risultato reale:

- skill `id=2` scartata: era attiva ma aveva bug (`contestos`);
- skill `id=4` scartata: conteneva codice demo/top-level;
- skill valide rimangono in `proposta`.

### 5. Workflow integrato nel motore

File: `motore_web.py`

- carica `MotoreWorkflow`;
- registra `documento_in_arrivo` e `report_giornaliero`;
- aggiunge metodi:
  - `workflow_stato()`
  - `workflow_avvia()`
  - `workflow_approva()`
- aggiunge endpoint:
  - `GET /workflow`
  - `POST /workflow/avvia`
  - `POST /workflow/approva`

### 6. UI Console aggiornata

File: `ui/index.html`

- pulsante "Bonifica skill rotte";
- pannello "Workflow end-to-end";
- pulsanti per avviare workflow;
- pulsanti per approvare istanze in attesa.

## Test eseguiti

```cmd
python -m py_compile cognizione\obiettivi.py governo\validator.py governo\skill_writer.py governo\skill_registry.py governo\sonno.py motore_web.py workflow.py
python governo\validator.py
python governo\sonno.py
python workflow.py
```

Risultati:

- compilazione OK;
- validator OK;
- sonno OK;
- workflow OK;
- motore nuovo importa workflow: `documento_in_arrivo`, `report_giornaliero`;
- bonifica skill: 4 controllate, 2 scartate.

## Da testare nell'app dopo riavvio

Riavvia ARGO, poi:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8773/workflow
Invoke-RestMethod -Uri http://127.0.0.1:8773/skills
```

In Console devono comparire:

- Figli esperti con bottone "Bonifica skill rotte";
- Workflow end-to-end;
- pulsanti per `documento_in_arrivo` e `report_giornaliero`.

## Stato reale

- Figli esperti: infrastruttura reale, ora piu' pulita, ma la qualita' dipende ancora dal modello.
- Sonno: reale e corretto nel filtro lacune; genera skill solo se non sono scheletri e passano validator.
- Workflow: integrato nel motore e UI, da testare nell'app riavviata.
- Auto-versione di ARGO: non esiste ancora. Esistono skill/figli sandboxati approvabili.

