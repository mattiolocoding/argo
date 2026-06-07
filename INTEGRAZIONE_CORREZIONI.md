# Aggancio del ciclo correzione (correzioni.py) al motore

> Modulo isolato gia' pronto e testato a parte: `correzioni.py`.
> Qui le 3 modifiche minime a `motore_web.py` (+ 1 opzionale alla UI).
> NIENTE riscritture: solo aggiunte.

## 1) In `Motore.__init__` (dopo gli altri moduli, in blocco try)
```python
self.correttore = None
try:
    from correzioni import Correttore
    self.correttore = Correttore(cervello=self.cervello)
except Exception as e:
    print("[MOTORE] correzioni:", e)
```

## 2) Nel metodo `chat(self, testo)` — inietta le lezioni prima di rispondere
Subito prima della riga che costruisce/usa il prompt per `self.cervello.pensa(...)`:
```python
if self.correttore:
    try:
        prompt = self.correttore.applica(prompt, contesto=testo)
    except Exception:
        pass
```
(così ogni risposta tiene conto degli errori passati corretti da Davide)

## 3) Nuovo metodo + endpoint per registrare una correzione
Metodo nella classe `Motore`:
```python
def correggi(self, contesto, sbagliato, corretto):
    if not self.correttore:
        return {"ok": False, "messaggio": "modulo correzioni non disponibile"}
    r = self.correttore.registra(contesto, sbagliato, corretto)
    self.audit.registra("correzione", r.get("regola", "")[:120])
    self._evento("ARGO", "Ho imparato la lezione: " + r.get("regola", ""), "sistema")
    return {"ok": True, **r}
```
Endpoint in `do_POST` (handler):
```python
elif self.path.startswith("/correggi"):
    b = self._body()
    self._json(m.correggi(b.get("contesto", ""), b.get("sbagliato", ""), b.get("corretto", "")))
```
Endpoint in `do_GET` (per vederle):
```python
elif self.path.startswith("/correzioni"):
    self._json({"correzioni": m.correttore.elenco() if m.correttore else []})
```

## 4) (Opzionale) Comando naturale in chat
All'inizio di `chat()`, riconosci una correzione scritta a voce:
```python
ltest = testo.lower()
if self.correttore and (ltest.startswith("correzione:") or "hai sbagliato" in ltest):
    corretto = testo.split(":", 1)[1].strip() if ":" in testo else testo
    r = self.correttore.registra("chat", "", corretto)
    return {"risposta": "Ok, ho imparato: " + r.get("regola", "")}
```

## 5) (Opzionale) Console UI
Aggiungi una card "Correzioni imparate" che fa GET `/correzioni` e le elenca,
e un campo per inviare POST `/correggi` (contesto, sbagliato, corretto).

## Come testare (Davide)
- Modulo da solo:  `python correzioni.py`  -> deve finire con `OK`.
- Dopo l'aggancio, con ARGO avviato:
  1. POST `/correggi` con una correzione (o scrivi in chat: `correzione: le fatture vanno in Documenti/Fiscale`).
  2. Fai una domanda sull'argomento -> la risposta deve rispettare la lezione.
  3. GET `http://127.0.0.1:8773/correzioni` -> vedi la lezione salvata.
- Misura oggettiva: `Correttore.verifica_miglioramento(domanda, chiave_giusta)` dice
  se la risposta passa da sbagliata a giusta dopo la lezione.
