# ARGO cognizione - integrazione futura

Questo modulo e' isolato. Non modifica `motore_web.py` e non modifica la UI.

## API minima

```python
from cognizione import TimelineCognitiva

cog = TimelineCognitiva()
cog.registra_file(percorso_file)
cog.registra_finestra(titolo_finestra)
cog.registra_chat(testo, ruolo="utente")
cog.registra_azione("proposta archiviazione", riferimento=percorso_file, esito="confermata")
cog.registra_rischio("file sensibile ignorato", livello="alto", riferimento=percorso_file)

riepilogo = cog.riepilogo_giorno()
```

## Dove collegarlo nel motore

- Quando il watcher vede un file: chiamare `registra_file(percorso)`.
- Quando arriva una chat: chiamare `registra_chat(testo, ruolo="utente")`.
- Quando ARGO propone/esegue/rifiuta un'azione: chiamare `registra_azione(...)`.
- Quando la sicurezza blocca un file: chiamare `registra_rischio(...)`.
- Quando `sensi.istantanea()` legge la finestra attiva: chiamare `registra_finestra(titolo)`.

## Cosa produce

- Timeline giornaliera ordinata.
- Conteggi per tipo evento.
- Progetti inferiti da path/titoli finestra.
- Pattern semplici: azioni ripetute, finestre ricorrenti, formati frequenti, rischi.
- Lacune: eventi senza progetto, chat non fondata su fatti, finestre senza file collegati.
- Suggerimenti per il ciclo di sonno.

## Limiti voluti

- Nessun LLM.
- Nessuna rete.
- Nessuna azione sul PC.
- Nessuna integrazione automatica con motore/UI.
- Redazione best-effort tramite `sicurezza.redigi()` se disponibile.
