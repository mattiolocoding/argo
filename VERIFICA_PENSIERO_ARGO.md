# VERIFICA PENSIERO ARGO

Data: 2026-06-06

## Obiettivo

Verificare se ARGO sta andando nella direzione descritta nel documento:

- agente persistente;
- memoria continua;
- world model;
- auto-riflessione;
- apprendimento tramite memoria, non retraining;
- deliberazione su domande complesse;
- ciclo `osserva -> capisce lacuna -> propone -> testa -> approva -> usa`.

## Stato reale nel codice

### Presente

- Memoria episodica persistente: `memoria/memoria.py`.
- Memoria semantica: `memoria/semantica.py`.
- Grafo locale: `memoria/grafo.py`.
- Timeline cognitiva: `cognizione/timeline.py`.
- World Model v0: `cognizione/world_model.py`.
- Sonno/consolidamento: `governo/sonno.py` + `memoria/consolidamento.py`.
- Lacune: `governo/lacune.py`.
- Skill registry: `governo/skill_registry.py`.
- Skill writer: `governo/skill_writer.py`.
- Sandbox e validator: `governo/sandbox_skill.py`, `governo/validator.py`.
- Figli esperti attivabili/eseguibili in sandbox via motore.
- Ricerca web governata: `connettori/ricerca_web.py`.
- Deliberatore/test-time compute: `pensatore.py`.
- Esperimento numerico apprendimento: `esperimento_apprendimento.py`.
- Diario interno persistente: `cognizione/diario_interno.py`.
- Obiettivi permanenti: `cognizione/obiettivi.py`.
- Registro esperimenti cognitivi: `cognizione/esperimenti.py`.

### Integrato ora

- `motore_web.py` carica `Pensatore`.
- La chat usa il Deliberatore sulle domande non banali.
- Le domande semplici restano dirette.
- Ogni deliberazione registra evento cognitivo `pensiero`.
- Il Deliberatore ora ha guardrail: non suggerire eliminazioni definitive, preferire backup, conferma, audit e azioni reversibili.
- `motore_web.py` carica diario interno, obiettivi permanenti ed esperimenti cognitivi.
- La chat deliberata registra riflessione interna ed esperimento `chat_deliberazione`.
- `/pensiero`, `/consolida`, `/sonno` e `/rifletti` aggiornano diario e obiettivi.
- `/dashboard` e Console mostrano diario interno, obiettivi permanenti ed esperimenti.
- Nuovi endpoint: `/diario`, `/obiettivi`, `/esperimenti`, `/rifletti`.

## Test eseguiti

### Compilazione

Comando:

```cmd
python -m py_compile pensatore.py esperimento_apprendimento.py motore_web.py cognizione\diario_interno.py cognizione\obiettivi.py cognizione\esperimenti.py cognizione\__init__.py
```

Risultato: OK.

### Moduli metacognitivi

Comandi:

```cmd
python cognizione\diario_interno.py
python cognizione\obiettivi.py
python cognizione\esperimenti.py
```

Risultato: OK.

### Integrazione motore

Test senza aprire la UI:

```cmd
python -c "from motore_web import Motore; m=Motore(); print(m.rifletti_ora().get('ok')); print(len(m.diario_stato().get('riflessioni', []))); print(len(m.obiettivi_stato().get('obiettivi', []))); print(len(m.esperimenti_stato().get('esperimenti', []))); m.running=False"
```

Risultato:

- `rifletti`: True;
- dashboard contiene `diario`, `obiettivi`, `esperimenti`;
- diario, obiettivi ed esperimenti rispondono.

### Esperimento apprendimento

Comando:

```cmd
python esperimento_apprendimento.py
```

Risultato:

- baseline senza memoria: 0/4 corrette, 0%;
- dopo memoria: 4/4 corrette, 100%;
- delta: +100%;
- ragionamento su fatto combinato: RIESCE.

Verdetto: la strada funziona nel test controllato. Il modello locale diventa piu' capace quando riceve memoria corretta, senza retraining.

### Deliberatore

Comando:

```cmd
python pensatore.py
```

Risultato:

- domanda semplice: classificata bassa;
- domanda complessa: classificata alta;
- risposta diretta: proponeva eliminazione file;
- risposta deliberata: propone backup, classificazione e conferma umana.

Verdetto: la deliberazione migliora qualita' e sicurezza della risposta.

## Cosa manca ancora per il "pensiero" vero

- Misura degli errori piu' precisa: ora il diario registra riflessioni e lacune, ma manca ancora una pipeline completa `errore -> correzione di Davide -> test -> esito`.
- Curiosita' governata: ARGO cerca online solo su richiesta; non propone ancora autonomamente esperimenti di conoscenza da approvare.
- Test A/B continuo maturo: il registro esiste, ma non c'e' ancora un valutatore automatico stabile che assegna punteggi affidabili alle strategie.
- World model piu' causale: oggi produce ipotesi, lacune, piani e obiettivi; non ha ancora relazioni causa-effetto robuste.
- Workflow reali end-to-end: il pensiero produce proposte governate, ma non orchestra ancora processi completi su email/browser/calendario/app.

## Prossimo passo consigliato

Costruire il ciclo di correzione esplicita:

1. Davide corregge ARGO dalla UI;
2. ARGO salva `errore -> correzione -> fonte`;
3. il diario interno aggiorna una regola operativa;
4. il registro esperimenti testa se la correzione migliora le risposte;
5. il sonno promuove la correzione a skill/proposta solo se passa sandbox e verifica.
