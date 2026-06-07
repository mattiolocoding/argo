# SICUREZZA_REPORT — ARGO Pentest & Hardening
**Data:** 2026-06-06  
**Analisi:** statica (lettura di tutti i file sorgente Python + HTML + JSON)  
**Analista:** Claude (claude-sonnet-4-6), ruolo Cybersecurity Senior  
**Scope:** `Desktop\Argo` — app desktop IA locale, server HTTP 127.0.0.1:8773, Ollama locale

---

## INDICE

1. Vulnerabilità già corrette in `sicurezza.py`
2. Vulnerabilità da applicare negli altri file (con patch precisa)
3. Risultati attività di supporto (non-vulnerabilità / note positive)

---

## 1. VULNERABILITÀ GIA' CORRETTE IN `sicurezza.py`

Le seguenti debolezze esistevano nella versione precedente e sono state risolte nel nuovo `sicurezza.py` (2026-06-06).

---

### [SEC-01] SEVERITÀ ALTA — Pattern di segreti insufficienti in `testo_contiene_segreti` e `redigi`

**File:** `sicurezza.py` (versione precedente)  
**Impatto:** ARGO poteva memorizzare, loggare o mostrare in chat testi contenenti JWT, cookie di sessione, codici fiscali italiani, chiavi Stripe/Twilio/SendGrid, SSH public key, partita IVA, numeri di telefono, hash bcrypt — tutti non riconosciuti dalla regex originale.  
**Fix applicato in `sicurezza.py`:** aggiunto un set completo di 20+ pattern regexp. Ora `redigi()` maschera tutti questi tipi prima che entrino nell'audit, negli eventi, nella chat o in qualunque log.

---

### [SEC-02] SEVERITÀ ALTA — Assenza di `percorso_sicuro()` (path-traversal non bloccato)

**File:** `sicurezza.py` (versione precedente), `connettori/filesystem.py`  
**Impatto:** il `ConnettoreFilesystem` accetta la chiave `cartella` da parametri passati a runtime (dall'utente via UI → POST /chat → codice LLM). Un valore come `{"cartella": "C:\\Windows\\System32"}` o `{"cartella": "../../.."}` avrebbe causato la lettura di qualunque directory del PC senza alcuna verifica.  
**Fix applicato in `sicurezza.py`:** aggiunta la funzione `percorso_sicuro(base, target) -> bool` che usa `os.path.realpath` per risolvere `..` e symlink prima del confronto. Resistente a path-traversal su Windows (backslash e forward-slash).  
**Ancora da applicare in `connettori/filesystem.py`:** vedi Sezione 2, SEC-A.

---

### [SEC-03] SEVERITÀ MEDIA — `file_sensibile()` non controllava directory sensibili nel percorso

**File:** `sicurezza.py` (versione precedente)  
**Impatto:** un file `C:\Users\Davide\.ssh\config` (senza estensione sensibile e senza parole sensibili nel nome) non veniva rilevato come sensibile. ARGO avrebbe potuto leggerlo e indicizzarlo.  
**Fix applicato in `sicurezza.py`:** `file_sensibile()` ora controlla anche i segmenti del percorso completo contro la lista `_CARTELLE_SENSIBILI` (`.ssh`, `.gnupg`, `.aws`, `.azure`, `.gcloud`, ecc.).

---

### [SEC-04] SEVERITÀ MEDIA — Estensioni sensibili incomplete

**File:** `sicurezza.py` (versione precedente)  
**Impatto:** file `.p8` (chiavi Apple/JWT), `.der` (certificati DER binari), `.csr` (richieste di firma certificati), `.pkcs12`, `.pub` (chiavi pubbliche SSH, che di norma accompagnano le private) non erano in lista.  
**Fix applicato in `sicurezza.py`:** aggiunte `.p8`, `.der`, `.csr`, `.pkcs12`, `.pub`.

---

### [SEC-05] SEVERITÀ BASSA — Nessuna retention nell'Audit (crescita illimitata del DB)

**File:** `sicurezza.py` (versione precedente)  
**Impatto:** il database `argo_audit.db` cresceva senza limite; su uso prolungato avrebbe potuto occupare GigaByte e rallentare il sistema. Secondariamente, un audit infinito è meno gestibile per compliance.  
**Fix applicato in `sicurezza.py`:** aggiunto parametro `retention_giorni` (default 90 giorni) alla classe `Audit`. Al costruttore, le voci più vecchie vengono rimosse automaticamente. Impostare `retention_giorni=0` disabilita il limite.

---

### [SEC-06] SEVERITÀ BASSA — `Audit.registra()` non applicava `redigi()` prima di salvare

**File:** `sicurezza.py` (versione precedente)  
**Impatto:** se un nome di file o una descrizione di azione conteneva un segreto (es. file chiamato `backup_password_cartella: /path/...`), il dato non mascherato veniva salvato nell'audit e poi esposto via `/audit` GET.  
**Fix applicato in `sicurezza.py`:** `Audit.registra()` chiama `redigi()` sul dettaglio prima di calcolarne l'hash e salvarlo; il campo `dettaglio` nell'audit non contiene mai segreti in chiaro.

---

## 2. VULNERABILITÀ DA APPLICARE NEGLI ALTRI FILE

Queste vulnerabilità sono nei file che **non ho modificato** (regola: non toccare gli altri file). Di seguito le patch precise da applicare manualmente.

---

### [SEC-A] SEVERITÀ ALTA — `connettori/filesystem.py`: nessuna verifica path-traversal sulla `cartella` passata

**File:** `connettori/filesystem.py`, righe 65-79  
**Impatto:** `leggi({"cartella": "C:\\Windows\\System32"})` o `leggi({"cartella": "../../etc/passwd"})` viene eseguita senza alcun controllo. Il connettore filesystem elenca qualunque path ricevuta, inclusi percorsi di sistema o dell'utente al di fuori delle radici sorvegliate. Se un attore (o un payload dell'LLM) controlla i parametri, può enumerare l'intero filesystem.  

**Patch da applicare in `connettori/filesystem.py`** (dopo riga 79, nel metodo `leggi()`):

```python
# Aggiungere in cima al metodo, DOPO aver letto la variabile 'cartella':
import sicurezza as _sic

# Verifica path-traversal: se c'è una cartella_default in config, la cartella
# richiesta DEVE essere al suo interno. Se non c'è default configurato,
# almeno verifica che non sia una cartella di sistema evidente.
if cartella_default:
    if not _sic.percorso_sicuro(cartella_default, cartella):
        return {"errore": (
            f"Accesso negato: '{cartella}' non e' dentro la radice configurata "
            f"'{cartella_default}'. Modifica config/connettori.json per ampliare l'accesso."
        )}
# Blocca percorsi di sistema noti (difesa in profondità)
_CARTELLE_SISTEMA = (
    os.environ.get("SystemRoot", "C:\\Windows").lower(),
    os.environ.get("SystemDrive", "C:").lower() + "\\program files",
    os.environ.get("SystemDrive", "C:").lower() + "\\program files (x86)",
    "/etc", "/proc", "/sys", "/boot",
)
if any(os.path.abspath(cartella).lower().startswith(c) for c in _CARTELLE_SISTEMA):
    return {"errore": f"Accesso a cartella di sistema non consentito: '{cartella}'"}
```

---

### [SEC-B] SEVERITÀ ALTA — `motore_web.py`: endpoint `/agente` POST accetta qualsiasi nome senza validazione

**File:** `motore_web.py`, riga 561  
**Codice attuale:**
```python
elif self.path.startswith("/agente"):
    self._json(m.esegui_agente(self._body().get("nome", "")))
```
**`governo/agenti.py` riga 84:**
```python
def esegui(self, nome, motore):
    a = self.agenti.get(nome)
    if not a:
        return f"Agente «{nome}» non trovato."
    return a.esegui(motore)
```
**Impatto:** qualunque richiesta POST a `/agente` con `{"nome": "<qualsiasi stringa>"}` viene accettata. Sebbene il registro agenti sia chiuso (solo 5 agenti hardcoded), il nome viene riflesso nella risposta (`«{nome}» non trovato`) — reflection che potrebbe diventare XSS se mai l'output finisse in HTML. Più grave: se in futuro un agente venisse registrato dinamicamente da codice LLM-generato, l'endpoint non avrebbe barriere.  

**Patch da applicare in `motore_web.py`** (sostituire la riga dell'agente):
```python
elif self.path.startswith("/agente"):
    nome_richiesto = self._body().get("nome", "")
    # Validazione: accetta solo nomi nell'elenco degli agenti registrati
    if nome_richiesto not in m.agenti.nomi():
        self._json({"ok": False, "messaggio": "agente non trovato"}, 404)
    else:
        self._json(m.esegui_agente(nome_richiesto))
```

---

### [SEC-C] SEVERITÀ ALTA — `motore_web.py`: endpoint `/audit/export` scrive su path fisso non verificato

**File:** `motore_web.py`, righe 525-528  
**Codice attuale:**
```python
elif self.path.startswith("/audit/export"):
    dest = os.path.join(_DIR, "audit_export.json")
    n = m.audit.esporta(dest)
    self._json({"ok": True, "file": dest, "voci": n})
```
**Impatto:** il percorso è fisso, il che in sé non è un rischio di traversal. Tuttavia, la risposta JSON restituisce il percorso assoluto completo del file sul disco (`"file": "C:\\Users\\Davide\\Desktop\\Argo\\audit_export.json"`). Questa informazione espone la struttura delle directory dell'utente. Se la UI venisse aperta in un contesto di iframe (o se ci fosse XSS) sarebbe information disclosure.  

**Patch:**
```python
elif self.path.startswith("/audit/export"):
    dest = os.path.join(_DIR, "audit_export.json")
    n = m.audit.esporta(dest)
    # Restituire solo il nome file, non il percorso assoluto
    self._json({"ok": True, "file": "audit_export.json", "voci": n})
```

---

### [SEC-D] SEVERITÀ MEDIA — `motore_web.py`: testo della chat non limitato in lunghezza (DoS locale)

**File:** `motore_web.py`, riga 553  
**Codice attuale:**
```python
elif self.path.startswith("/chat"):
    self._json(m.chat(self._body().get("testo", "")))
```
**Impatto:** un messaggio di chat molto lungo (es. megabyte di testo) viene passato direttamente a Ollama e salvato in memoria episodica. Può causare: (1) saturazione RAM, (2) prompt injection verso Ollama con payload gigante, (3) overflow della memoria SQLite. Non è un attacco remoto (server locale), ma è un rischio se l'UI è raggiungibile da script o automazione.  

**Patch:**
```python
elif self.path.startswith("/chat"):
    testo_raw = self._body().get("testo", "")
    # Limite 2000 caratteri per prevenire DoS e prompt injection massivo
    testo_raw = str(testo_raw)[:2000]
    self._json(m.chat(testo_raw))
```

---

### [SEC-E] SEVERITÀ MEDIA — `governo/sandbox_skill.py`: `os` e `pathlib` non esplicitamente in lista nera, `__builtins__` accessibile via `globals()`

**File:** `governo/sandbox_skill.py`, righe 28-59  
**Impatto:**  
- `os` non è nella `_MODULI_VIETATI` (c'è `os.system` come stringa ma non `os` come modulo). Un import `import os` passa la verifica AST.
- `pathlib` è nella lista ma `os` no — un attaccante può fare `import os; os.environ["PATH"]` o `os.getcwd()`.
- `getattr` è in `_CHIAMATE_VIETATE` ma `type("x").__mro__[1].__subclasses__()` (attacco via MRO) non è bloccato.

**Patch da applicare in `governo/sandbox_skill.py`:**

Aggiungere `"os"` alla frozenset `_MODULI_VIETATI`:
```python
_MODULI_VIETATI = frozenset({
    "os",                   # AGGIUNTO: blocca import os (os.environ, os.system, ecc.)
    "subprocess", "multiprocessing", "os.system",
    ...
})
```
Aggiungere alla lista `_CHIAMATE_VIETATE`:
```python
_CHIAMATE_VIETATE = frozenset({
    ...
    "__mro__", "__subclasses__",   # AGGIUNTO: blocca attacchi via MRO Python
    "environ",                      # AGGIUNTO: os.environ diretto
})
```

---

### [SEC-F] SEVERITÀ MEDIA — `connettori/email_imap.py`: password IMAP in chiaro in `connettori.json`

**File:** `config/connettori.json`, `connettori/email_imap.py`  
**Impatto:** la password IMAP viene salvata in chiaro nel file JSON non cifrato. Chiunque abbia accesso alla cartella `Argo` (o un processo con permessi utente) può leggerla. Il file JSON non ha restrizioni di permesso aggiuntive.  

**Fix consigliato:** usare la classe `Chiave` di `sicurezza.py` per cifrare la password in `connettori.json` con Fernet prima della scrittura, e decifrarla al momento dell'uso.  
Patch minima (in `connettori/email_imap.py`, dentro `leggi()`):
```python
# Dopo aver letto la password dalla config:
import sicurezza as _sic
_chiave = _sic.Chiave()
if _chiave.cifratura_disponibile():
    try:
        password = _chiave.decifra(password)
    except Exception:
        pass  # Non cifrata: usa il valore grezzo
```
E fornire uno script di utilità che cifra la password al momento della configurazione iniziale.

---

### [SEC-G] SEVERITÀ MEDIA — `motore_web.py`: nessun rate-limit sugli endpoint POST

**File:** `motore_web.py`  
**Impatto:** il server su 127.0.0.1 è raggiungibile da qualunque processo locale. Un processo malevolo (o uno script) può inondare `/chat` con migliaia di richieste/secondo, saturando Ollama, la memoria SQLite e il thread del motore. Non è un rischio remoto ma è un rischio locale reale se si eseguono altri processi non fidati.  

**Fix consigliato:** aggiungere un rate-limiter semplice basato su timestamp (finestra scorrevole) prima di ogni POST a `/chat`, `/agente`, `/sonno`:

```python
# In cima alla classe H (handler), aggiungere:
_ultimo_chat = {}  # ip -> timestamp

def _rate_limit(self, chiave, max_per_minuto=30):
    """Blocca se supera max_per_minuto richieste."""
    import time
    adesso = time.time()
    bucket = H._ultimo_chat.setdefault(chiave, [])
    # Rimuovi timestamp piu' vecchi di 60 secondi
    H._ultimo_chat[chiave] = [t for t in bucket if adesso - t < 60]
    if len(H._ultimo_chat[chiave]) >= max_per_minuto:
        return False
    H._ultimo_chat[chiave].append(adesso)
    return True
```

---

### [SEC-H] SEVERITÀ BASSA — `mani/mani.py`: hash duplicati usa MD5 (debole per integrità)

**File:** `mani/mani.py`, righe 133-141  
**Impatto:** MD5 è vulnerabile a collisioni. Per il rilevamento di duplicati di file (non per sicurezza crittografica) è sufficiente, ma due file con stesso MD5 ma contenuto diverso potrebbero essere erroneamente classificati come duplicati. Non è un rischio di sicurezza grave in questo contesto, ma è una debolezza tecnica.  

**Fix consigliato:** sostituire MD5 con SHA-256:
```python
def _hash(self, percorso):
    try:
        h = hashlib.sha256()   # PRIMA: hashlib.md5()
        with open(percorso, "rb") as f:
            for blocco in iter(lambda: f.read(65536), b""):
                h.update(blocco)
        return h.hexdigest()
    except Exception:
        return None
```

---

### [SEC-I] SEVERITÀ BASSA — `ui/index.html`: proposta ARGO inserita con `.textContent` ma testo LLM non sanitizzato prima di andare in JS

**File:** `ui/index.html`, riga 178  
**Codice:**
```javascript
const t = propbox.querySelector('.txt'); if(t) t.textContent = testo;
```
**Impatto:** `textContent` (non `innerHTML`) è sicuro per XSS. Tuttavia, il testo della proposta (`s.proposta`) viene costruito in Python da un nome file che l'LLM ha elaborato. Se in futuro il rendering passasse a `innerHTML` (comune durante refactoring), o se un dato LLM contenesse markup, ci sarebbe rischio XSS. Questo è un **rischio latente da tenere monitorato** — allo stato attuale non è sfruttabile.  

**Fix consigliato:** mantenere `textContent` e non passare mai a `innerHTML` per contenuto proveniente dall'LLM o dai nomi file.

---

### [SEC-L] SEVERITÀ BASSA — `memoria/argo.key` non ha permessi restrittivi espliciti

**File:** `sicurezza.py`, metodo `Chiave._carica_o_crea()`  
**Impatto:** su Windows, il file `argo.key` viene scritto con i permessi di default dell'utente corrente. La DPAPI lo protegge dalla decifratura da parte di altri utenti, ma il file è leggibile (anche se inutilizzabile senza la stessa sessione Windows). Su Linux/macOS (dove DPAPI non c'è), il file è in chiaro ed è leggibile da altri processi dell'utente.  

**Fix consigliato:** aggiungere in `_carica_o_crea()`, dopo la scrittura del file:
```python
# Restringe i permessi a sola lettura per l'utente corrente
try:
    if os.name != "nt":  # Su Windows ci pensa DPAPI
        os.chmod(self.percorso, 0o600)
except Exception:
    pass
```

---

## 3. RISULTATI POSITIVI (NON-VULNERABILITÀ)

- **Server HTTP vincolato a 127.0.0.1**: `HOST = "127.0.0.1"` hardcoded in `motore_web.py` riga 34. Il server non è raggiungibile dalla rete locale o da Internet. Corretto.
- **Directory traversal nella UI**: il server serve solo `/` e `/index.html` dal percorso fisso `UI_FILE`. Nessun endpoint serve file arbitrari dal filesystem. Non c'è traversal.
- **File sensibili non letti né spostati**: ogni punto di ingresso file controlla `sicurezza.file_sensibile()` prima di accodarli (riga 216, 230, 240, 317 di `motore_web.py`). Il guardrail è coerente.
- **Sandbox skill**: `governo/sandbox_skill.py` usa analisi AST + subprocess isolato con `cwd` temporaneo e `env` minimale. Architettura corretta; vedi SEC-E per il gap residuo su `import os`.
- **Skill mai attive in automatico**: il ciclo di sonno inserisce skill solo come `'proposta'`, mai `'attiva'`. L'approvazione umana è obbligatoria (confermato in `SkillRegistry.approva()` e `sonno.py`).
- **Audit a catena di hash**: la verifica della catena (`Audit.verifica()`) è corretta e rileva qualunque modifica diretta al DB. Il sigillo (`Audit.sigillo()`) copre l'intero storico.
- **Policy engine**: `governo/policy.py` valuta ogni azione prima dell'esecuzione; le regole di default bloccano eliminazioni e escalano documenti sensibili.
- **Rollback**: `governo/rollback.py` registra il piano inverso e lo esegue tramite `Mani`, rispettando i guardrail di sicurezza.
- **Mani guardrail**: `Mani._sicuro()` controlla che sorgente e destinazione siano dentro le radici consentite per ogni operazione (righe 185-186 di `mani.py`).
- **Dati non escono dal PC**: Ollama gira in locale, nessuna chiamata HTTP verso API esterne, nessun webhook, nessun upload.

---

## RIEPILOGO PRIORITÀ

| ID    | Severità | File                        | Stato       |
|-------|----------|-----------------------------|-------------|
| SEC-01| ALTA     | sicurezza.py                | RISOLTO     |
| SEC-02| ALTA     | sicurezza.py / filesystem.py| RISOLTO in sicurezza.py; DA APPLICARE in filesystem.py (SEC-A) |
| SEC-A | ALTA     | connettori/filesystem.py    | DA APPLICARE|
| SEC-B | ALTA     | motore_web.py               | DA APPLICARE|
| SEC-C | ALTA     | motore_web.py               | DA APPLICARE|
| SEC-03| MEDIA    | sicurezza.py                | RISOLTO     |
| SEC-04| MEDIA    | sicurezza.py                | RISOLTO     |
| SEC-D | MEDIA    | motore_web.py               | DA APPLICARE|
| SEC-E | MEDIA    | governo/sandbox_skill.py    | DA APPLICARE|
| SEC-F | MEDIA    | connettori/email_imap.py    | DA APPLICARE|
| SEC-G | MEDIA    | motore_web.py               | DA APPLICARE|
| SEC-05| BASSA    | sicurezza.py                | RISOLTO     |
| SEC-06| BASSA    | sicurezza.py                | RISOLTO     |
| SEC-H | BASSA    | mani/mani.py                | DA APPLICARE|
| SEC-I | BASSA    | ui/index.html               | MONITORARE  |
| SEC-L | BASSA    | sicurezza.py/argo.key       | DA APPLICARE|

---

*Report generato il 2026-06-06 da analisi statica completa del codebase ARGO.*
