# ARGO — come avviarlo

## Cosa è (per ora)
Una finestra che vive sul tuo PC, ti saluta, sta sempre in primo piano e
**sorveglia una cartella**. Quando aggiungi o togli un file, Argo se ne accorge
da solo, **lo passa al cervello (Ollama 3.1) e ti dice cosa ha capito**.
Non aspetta che tu scriva.

## File
- `cervello.py` → la testa: parla con Ollama 3.1
- `argo.py` → il corpo: finestra + occhi + loop di vita
- `avvia_argo.bat` → doppio click per accendere Argo (senza terminale nero)
- `installa_avvio_automatico.bat` → doppio click UNA volta: Argo parte da solo a ogni accensione del PC
- `COME_AVVIARE.md` → questo file

## Avvio comodo (doppio click)
- Per accenderlo a mano: doppio click su **`avvia_argo.bat`**.
- Per farlo partire **da solo a ogni accensione del PC**: doppio click su
  **`installa_avvio_automatico.bat`** (una volta sola).
  Per disattivarlo: premi `Win+R`, scrivi `shell:startup`, cancella il
  collegamento "Argo".

> Nota: serve che Python sia installato e raggiungibile. Se il doppio click
> non fa nulla, prima fai funzionare l'avvio manuale qui sotto.

## Avvio in 3 passi
1. Apri il **Prompt dei comandi** nella cartella `Argo` (sul Desktop).
2. (Facoltativo) controlla il cervello da solo: `python cervello.py`
   → deve scrivere una frase di presentazione. Se dice "Ollama non risponde",
   avvia Ollama.
3. Avvia Argo: `python argo.py`
   → si apre la finestra. Aggiungi un file qualsiasi nella cartella e
   guardalo reagire e ragionare.

## Se il modello ha un altro nome
In `cervello.py`, riga `MODELLO = "llama3.1"`, mettici il nome esatto che vedi
con `ollama list` (es. `llama3.1:8b`).

## Prossimi step (non ancora fatti, andiamo per ordine)
- **Memoria su disco** → Argo ricorda tra una sessione e l'altra (il database).
- **Mani** → Argo non solo nota e ragiona, ma agisce (sposta/ordina file, ecc.)
  sempre in modo controllato.
- **Più sensi** → oltre ai file, altre cose del sistema.
