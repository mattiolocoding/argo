# 📋 ARGO — Cosa hai chiesto in questa chat, e cosa c'è davvero

> Mappa onesta di TUTTE le richieste fatte da Davide in conversazione e il loro stato.
> ✅ fatto e collegato · 🟡 fatto, da rifinire/testare · ❌ non ancora · 🔧 in lavorazione ora
> Aggiornato: 6 giugno 2026

## Fondamenta (Custode del PC) — Orizzonte 0
- ✅ Essere digitale che vive sul PC, osserva e agisce (non solo risponde)
- ✅ Memoria che cresce (episodica + profilo + abitudini + grafo + semantica)
- ✅ Avvio automatico all'accensione + cervello che si accende/riconnette da solo
- ✅ Occhi su più cartelle (Desktop, Download, Documenti, Immagini, Musica, Video)
- ✅ Archiviazione file per tipo/data/progetto, duplicati, accumuli
- ✅ Autonomia 3 livelli (Osserva / Chiede / Agisci) con pulsante
- ✅ Riepilogo "oggi ho sistemato N file"
- ✅ Indipendenza totale da SONAR (nessuna dipendenza)

## App & interfaccia
- ✅ App desktop NATIVA (Qt/PySide6), non browser, con icona/logo
- 🔧 Grafica di frontiera 2026 (in redesign — non ancora definitiva)
- 🔧 Frasi meno "robotiche"/canned, più intelligenti e fondate
- ❌→🔧 Schermata permessi al primo avvio (tutto il PC / cartelle / file / app)

## Cervello / cognizione
- ✅ Ollama locale, auto-accensione
- ✅ Chat fondata sui dati reali (anti-allucinazione)
- 🟡 Model mesh (riflesso/ragionatore/esperto) — modulo c'è, 🔧 da collegare alla chat
- ❌ Metacognizione/auto-valutazione, world model (strati futuri)

## Sicurezza (punto cruciale)
- ✅ File/segreti sensibili mai letti/spostati/memorizzati
- ✅ Audit a catena di hash (a prova di manomissione) + export/report
- ✅ Chiave locale protetta (DPAPI) + cifratura opzionale
- 🔧 Pentest completo + hardening da agente Cybersecurity dedicato (in corso)

## Governo dell'azione (enterprise)
- ✅ Policy engine (Consenti/Escala/Blocca) a runtime
- ✅ Ruoli/permessi (RBAC: admin/operatore/auditor/utente)
- ✅ Rollback / Annulla (piano inverso)
- ✅ Metriche (azioni, rifiuti, rischi evitati, tempo risparmiato)
- ✅ Dashboard Console nella UI
- ✅ Consolidamento serale ("sonno" base)
- ✅ Agenti specializzati (Diagnostico/Auditor/Guardiano/Archivista/Analista)

## Workflow / integrazioni / skill
- 🟡 Workflow engine multi-step (modulo c'è, da integrare nel motore)
- 🟡 Connettori (email/file/git) — 🔧 da rendere eseguibili come da test
- 🟡 Sensi estesi (finestra/rete/appunti) — ok
- 🔧 Skill synthesis completa (sonno → lacuna → genera → valida → sandbox →
  proposta → APPROVAZIONE → attivazione): oggi ci sono i pezzi, manca la
  pipeline robusta end-to-end (in corso)

## Bug trovati nei tuoi test (in fix ora, un agente per problema)
- 🔧 EN6 `sandbox_skill.py`: IndentationError sul caso "skill sicura"
- 🔧 EN8 `python -m connettori`: manca `connettori/__main__.py`
- 🔧 EN8 `connettori/git.py`: import relativo non eseguibile come script
- 🔧 EN4 `python governo\sonno.py`: "No module named governo" (manca bootstrap path)
- 🔧 /console: endpoint mancante (la Console usa altri endpoint) — da chiarire/implementare
- 🔧 formato /audit: ora `{report,voci}` — allineare test/contratto
- 🔧 Packaging: `argo.spec` punta alla vecchia app; exe non apre la porta — da rifare per l'app Qt
- 🔧 Inno Setup non nel PATH (serve installarlo per generare il Setup.exe)

## Non ancora fatto (strati futuri, dalla visione)
- ❌ Workflow profondi dentro il motore (oltre il modulo)
- ❌ Knowledge graph temporale serio (validità nel tempo)
- ❌ Fleet / multi-istanza + console centrale
- ❌ Mobile, voce/avatar, browser extension
- ❌ Apprendimento federato, marketplace skill, SDK/plugin
- ❌ Packaging firmato + auto-update + .ico definitivo

---
*Limite tecnico: l'ambiente di esecuzione di Claude è stato offline gran parte della sessione → il codice nuovo è scritto/revisionato ma il test di esecuzione lo fa Davide (vedi TEST_DA_FARE.md).*
