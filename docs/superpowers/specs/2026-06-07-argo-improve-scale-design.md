# ARGO — Migliorare, mettere in sicurezza e scalare (con frontend impeccable)

> Spec di lavoro. Data: 2026-06-07. Mandato utente: "pianifica e fai tutto 1 2 3",
> impeccable per il frontend, motore avviabile/testabile dal vivo.

## Contesto e baseline (verificata oggi)

- **Ambiente**: nessun Python utilizzabile → installato Python 3.11.9 + creato `.venv` dedicato ("py env").
- **Compilazione**: tutti i `.py` del progetto compilano (0 errori).
- **Self-test moduli**: memoria, grafo, mani, impostazioni, sicurezza, sistema, policy, ruoli,
  lacune, skill_registry, sandbox_skill, validator, workflow, sensi, modelli, connettori, sonno → tutti OK.
- **Motore**: `motore_web.py` (stdlib `http.server`, porta 8773) si avvia; endpoint
  `/stato /console /audit /permessi /dashboard /metriche /sensi /modelli /skills` → tutti 200.
- **Ollama**: attivo, modelli `qwen2.5:14b-instruct`, `qwen2.5:7b-instruct`, `llama3.1:8b`,
  `nomic-embed-text`, `bge-m3`.
- **Conclusione**: i bug elencati nei doc (EN6/EN8/EN4, `/console`, `/audit`) risultano **già risolti**.
- **Impeccable**: installato in `.claude/skills/impeccable` (23 comandi + 7 domini di design).
  I comandi slash non sono registrati in questa sessione → applico le reference leggendole direttamente.

## Bug reale trovato

- **Model-mesh** (`modelli.py`): i modelli di embedding (`bge-m3`, `nomic-embed-text`) vengono
  assegnati ai ruoli di chat. Inoltre `qwen2.5:14b` è classificato "medio". Risultato live:
  `riflesso=bge-m3`, `esperto=nomic-embed-text` (entrambi NON sono modelli di chat). Da correggere.

## Fasi

### FASE 1 — Hardening verticale (base solida) ✅ in corso
1. Python/venv, compile, self-test, motore vivo, endpoint OK — **fatto**.
2. Fix model-mesh: escludere embedding dal pool chat; classificare 14b come "grande". Verifica via `/modelli`.
3. Caccia ad altri bug logici/runtime sugli endpoint principali (chat, proposte, annulla).

### FASE 2 — Frontend con impeccable
1. Audit del `ui/index.html` (monolite 1817 righe) con la metodologia impeccable (anti-pattern, tipografia, colore, spazio, motion, interazione, responsive, UX writing).
2. Refactor: separare CSS/JS dal markup; design system coerente (token, scala tipografica, spaziatura).
3. Polish: stati (loading/empty/error), micro-interazioni, accessibilità, responsive.
4. Verifica dal vivo che la UI continui a parlare con tutti gli endpoint.

### FASE 3 — Scalare
- **Verticale**: integrare workflow nel motore end-to-end; migliorare cognizione/chat fondata.
- **Orizzontale**: fondamenta multi-istanza/fleet (config istanza, identificazione, stato aggregabile).
- Ogni strato: un microtask alla volta, testato prima del successivo.

## Principi di lavoro
- Un microtask alla volta, **funziona prima del successivo** (principio del progetto).
- Testare dal vivo dopo ogni modifica (motore su, endpoint reali).
- Niente dipendenze pesanti non necessarie (il motore resta stdlib).
- git per poter annullare in sicurezza ogni passo.
