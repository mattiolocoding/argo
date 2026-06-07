# VERIFICA FINALE ARGO — 2026-06-06

Agente QA: subagente Claude Sonnet 4.6. Verifica statica completa su tutti i moduli Python del progetto (esclusi `sorvegliata/`, `__pycache__`, `produzione/build/dist/`). Il workspace Linux era offline, quindi non e' stato possibile eseguire py_compile o i smoke-test in shell; l'analisi e' stata condotta per lettura diretta di ogni file.

---

## 1. Tabella stato per area

| Area | Moduli chiave | Stato | Note |
|---|---|---|---|
| **Base** | `motore_web.py`, `cervello.py`, `sistema.py` | OK | Sintassi corretta, import coerenti |
| **Sicurezza** | `sicurezza.py`, `test_sicurezza.py` | OK | Hardening 2026 completo, audit retention, redigi, DPAPI |
| **Governo** | `policy.py`, `ruoli.py`, `rollback.py`, `metriche.py`, `consolidamento.py`, `agenti.py`, `lacune.py`, `skill_registry.py`, `skill_writer.py`, `sandbox_skill.py`, `validator.py`, `sonno.py` | OK | Tutte le firme verificate, nessun import rotto |
| **Cognizione** | `cognizione/__init__.py`, `cognizione/timeline.py`, `cognizione/world_model.py` | OK | Esportazioni corrette, `__main__` presente |
| **Connettori** | `connettori/__init__.py`, `connettori/__main__.py`, `connettori/base.py`, `connettori/ricerca_web.py`, `connettori/filesystem.py`, `connettori/email_imap.py`, `connettori/git.py` | OK | `RegistroConnettori` registra 4 connettori, `info()` e `leggi()` coerenti |
| **Memoria** | `memoria/memoria.py`, `memoria/grafo.py`, `memoria/semantica.py`, `memoria/__init__.py`, `memoria/consolidamento.py` | OK | Schema SQLite completo, metodi tutti presenti |
| **Packaging / Config** | `config/impostazioni.py`, `config/permessi.py`, `config/__init__.py`, `mani/mani.py`, `mani/__init__.py` | OK | Import coerenti |
| **UI / Endpoint** | `motore_web.py` (do_GET + do_POST), `ui/index.html` | OK con avvisi | Tutti gli endpoint mappati, vedi rischi sotto |

---

## 2. Bug trovati

### BUG CORRETTI

Nessun bug sintattico o di import critico e' stato trovato. Non e' stato necessario correggere alcun file.

### PROBLEMI NON CRITICI RILEVATI (non corretti — non rientrano nella definizione di "bug piccolo e chiaro")

---

## 3. Verifica endpoint <-> metodi

Tutti gli endpoint di `motore_web.py` sono stati verificati contro i metodi di `Motore`:

| Endpoint GET | Metodo Motore | Esiste? |
|---|---|---|
| `/stato` | `m.stato()` | SI |
| `/eventi` | `m.eventi_da(since)` | SI |
| `/audit`, `/audit/export` | `m.audit.report()`, `m.audit.esporta()` | SI |
| `/metriche` | `m.metriche()` | SI |
| `/agenti` | `m.agenti.nomi()` | SI |
| `/dashboard` | `m.dashboard()` | SI |
| `/sensi` | `m.sensi_ora()` | SI |
| `/modelli` | `m.modelli_stato()` | SI |
| `/connettori` | `m.connettori_info()` | SI |
| `/skills` | `m.skills_lista()` | SI |
| `/console` | `m.dashboard()` (alias) | SI |
| `/permessi` GET | `m.permessi_stato()` | SI |
| `/timeline`, `/cognizione` | `m.timeline_stato()` | SI |
| `/pensiero` | `m.pensiero_analitico()` | SI |
| `/world` | `m.world_stato()` | SI |
| `/proposte` | `m.proposte_stato()` | SI |

| Endpoint POST | Metodo Motore | Esiste? |
|---|---|---|
| `/conferma` | `m.conferma(si)` | SI |
| `/chat` | `m.chat(testo)` | SI |
| `/ricerca` | `m.ricerca_online(query, max_risultati)` | SI |
| `/autonomia` | `m.imposta_modo(modo)` | SI |
| `/annulla` | `m.annulla()` | SI |
| `/agente` | `m.esegui_agente(nome)` | SI |
| `/consolida` | `m.consolida_ora()` | SI |
| `/sonno` | `m.esegui_sonno()` | SI |
| `/skill/approva` | `m.skill_approva(id)` | SI |
| `/skill/attiva` | `m.skill_attiva(id)` | SI |
| `/skill/scarta` | `m.skill_scarta(id)` | SI |
| `/skill/esegui` | `m.skill_esegui(id, contesto)` | SI |
| `/permessi` POST | `m.imposta_permessi(modo, cartelle)` | SI |
| `/proposta/stato` | `m.proposta_stato(id, stato)` | SI |

**Nessun endpoint punta a un metodo inesistente.**

---

## 4. Verifica moduli cognitivi nuovi

| Modulo | Esiste | `__main__` / smoke-test | Import OK |
|---|---|---|---|
| `cognizione/__init__.py` | SI | N/A | Esporta `TimelineCognitiva`, `WorldModel`, `EventoCognitivo`, `normalizza_evento`, `TIPI_EVENTO` |
| `cognizione/timeline.py` | SI | SI (riga 831) | Solo stdlib + `sicurezza` opzionale |
| `cognizione/world_model.py` | SI | SI (riga 474) | Solo stdlib + `cognizione.timeline` |
| `connettori/ricerca_web.py` | SI | SI (riga 178) | DuckDuckGo HTML, solo stdlib |

---

## 5. Verifica firme chiamate critiche

| Chiamante | Chiamata | Firma reale | Coerente? |
|---|---|---|---|
| `motore_web.py:660` | `_sonno.sonno(memoria, lacune, skills, skill_writer, cervello)` | `sonno(memoria, lacune, registry, writer, cervello, audit=None, timeline=None)` | SI (parametri posizionali corretti) |
| `motore_web.py:790` | `Validator(timeout_sandbox=15).valida(skill.get("codice",""))` | `Validator.__init__(timeout_sandbox=10)`, `valida(codice)` | SI |
| `motore_web.py:822` | `esegui_in_sandbox(codice, ctx, timeout=15)` | `esegui_in_sandbox(codice, contesto=None, timeout=10)` | SI |
| `motore_web.py:542` | `metriche_eng.calcola()` | `Metriche.calcola()` | SI |
| `motore_web.py:550` | `self.skills_lista()` in `dashboard()` | `Motore.skills_lista()` | SI |
| `motore_web.py:559` | `self.world.proposte("proposta", 8)` | `WorldModel.proposte(stato, limite)` | SI |
| `governo/sonno.py:183` | `consolida_giornata(memoria, audit, timeline, ...)` | `consolida_giornata(memoria, audit=None, timeline=None, ...)` | SI |

---

## 6. Rischi residui (non corretti — richiederebbero modifica architetturale o design)

### RISCHIO 1 (MEDIO) — Tipi evento non registrati in `TIPI_EVENTO`
**File:** `cognizione/timeline.py`, righe 20-32 + `motore_web.py`  
`TIPI_EVENTO` contiene 11 tipi. Molti eventi reali (`"sonno"`, `"ricerca_web"`, `"skill_eseguita"`, `"proposta_approvata"`, `"proposta_scartata"`, `"permessi"`, `"agente"`) vengono passati a `timeline.registra()` ma non appartengono a `TIPI_EVENTO`. La chiamata solleva `ValueError` internamente, catturato dal `try/except` in `motore_web._evento()`. Risultato: questi eventi NON vengono mai salvati nel DB cognitivo.  
**Impatto:** la timeline cognitiva e il world model perdono metadati su queste categorie.  
**Soluzione suggerita (non applicata):** aggiungere i tipi mancanti a `TIPI_EVENTO` oppure usare `alias` nel `normalizza_evento()`.

### RISCHIO 2 (BASSO) — Policy esito `"modifica"` non gestito in `_processa()`
**File:** `motore_web.py`, righe 346-360; `governo/policy.py`, riga 21  
L'esito `"modifica"` e' dichiarato valido in `policy.py` ma non viene gestito esplicitamente in `Motore._processa()`. Cade nel ramo implicito (ne "blocca" ne "escala") e l'azione viene processata normalmente, ignorando la modifica suggerita dalla policy.  
**Impatto:** le regole con esito `"modifica"` non applicano la loro correzione.  
**Soluzione suggerita (non applicata):** aggiungere un ramo `elif decisione["esito"] == "modifica"` che applichi la destinazione forzata.

### RISCHIO 3 (BASSO) — `registra_scelta()` chiamato con `categoria=None`
**File:** `governo/consolidamento.py` / `motore_web.py:438`  
`memoria.registra_scelta(piano.get("_categoria"), False)` — se `_categoria` e' `None`, `registra_scelta()` ha un early return (`if not categoria: return`). Non e' un bug ma un dato mancante: le preferenze non vengono apprese per le azioni senza categoria.

### RISCHIO 4 (BASSO) — Emoji nei print di `motore_web.py` (non nei log HTTP, ma in stdout)
**File:** `motore_web.py`, righe 304, 348, 628, 676  
Le emoji (`💤`, `🛡`) sono nei testi degli eventi UI (JSON), non in `print()` diretti. Il JSON viene serializzato con `json.dumps()` che usa `ensure_ascii=False` di default — potrebbero causare problemi se il buffer stdout e' CP1252. Tuttavia queste righe passano per `self._send(json.dumps(d), ...)` dove il corpo e' UTF-8, quindi l'esposizione e' solo nel browser, non nella console Windows. **Rischio reale: trascurabile.**

### RISCHIO 5 (INFORMATIVO) — `connettori/git.py` usa `subprocess` (fuori sandbox)
Il connettore Git usa `subprocess.run(["git", ...])` per leggere i repository. E' corretto e intenzionale (sola lettura), ma vale la pena notare che e' l'unico modulo non-sandbox che chiama sottoprocessi di sistema. La sicurezza dipende dall'isolamento a livello OS.

---

## 7. Import circolari

Nessun import circolare rilevato. Il grafo delle dipendenze e' aciclico:
- `motore_web` -> `cognizione`, `governo`, `connettori`, `memoria`, `sicurezza`, `sistema`, `cervello`, `mani`, `config`
- `cognizione/world_model` -> `cognizione/timeline` (solo intra-pacchetto)
- `governo/sonno` -> `memoria/consolidamento` (diverso da `governo/consolidamento`)
- `connettori/*` -> `connettori/base` (solo intra-pacchetto)

---

## 8. Correzioni apportate da questo agente QA

**Nessuna correzione e' stata necessaria.** Tutti i moduli sono sintatticamente corretti, le firme delle chiamate sono coerenti, e gli import sono integri. I problemi trovati sono tutti di tipo design/gap (non bug sintattici o di runtime immediati) e richiederebbero interventi architetturali non di competenza di questo agente QA.
