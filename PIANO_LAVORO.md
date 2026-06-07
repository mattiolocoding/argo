# 🧩 ARGO — Piano di lavoro (task & microtask)

> Come si costruisce, pezzo per pezzo. Regola: **un microtask alla volta, e funziona prima del successivo.**
> Stato: ✅ fatto · 🔧 in corso · ⬜ da fare

> **AGGIORNAMENTO (giugno 2026): tutte le fasi sono state IMPLEMENTATE.**
> Fasi 0-1-2-R verificate (alcune dal vivo da Davide). Fasi 3-4-5-A-Finale scritte
> e in attesa di test → vedi **`TEST_DA_FARE.md`** per la lista completa dei test.

---

## 🏛️ Decisioni di architettura e distribuzione (fisse)

**Architettura app** (scelta di Davide):
- **ARGO Engine = Servizio Windows** — il motore (Memory + Event + Cervello/Ollama) gira in background, non muore con la finestra.
- **ARGO UI = app nella tray** — finestra separata (chat, dashboard memoria, impostazioni, notifiche). La GUI vive qui perché il Servizio (session 0) non può mostrarla.
- **Comunicano via API locale** su `127.0.0.1`.

**Distribuzione** ("come le big tech"):
- **Installer leggero** (decine di MB). Al **primo avvio scarica modello + runtime** (Ollama/llama.cpp), scegliendo il migliore per l'hardware.
- L'utente **non vede mai Docker né container**. Per la versione personale: niente Docker.
- **Host:** GitHub Releases o sito proprio (bottone "Scarica"). Ospitare il file **non richiede chiavi**.
- **Chiavi/licenze:** layer separato, **solo se/quando si vende**. Il modello open non richiede chiavi.
- **L'installer è l'ULTIMO passo:** si impacchetta ciò che già funziona.

---

## ✅ FASE 0 — Il Respiro *(fatto)*
- ✅ Finestra viva sempre in primo piano, saluto orario
- ✅ Occhi: sorveglia una cartella (watcher)
- ✅ Cervello: collegato a Ollama 3.1
- ✅ Avvio manuale (`.bat`) + avvio automatico all'accensione

---

## 🔧 FASE 1 — La Memoria propria *(PARTIAMO DA QUI)*
Obiettivo: Argo **ricorda tra una sessione e l'altra**. Spento e riacceso, sa cosa è successo.

- ⬜ **1.1 Schema del database** — disegnare le tabelle: `episodi` (diario) e `profilo` (chi è Davide, preferenze)
- ⬜ **1.2 Modulo `memoria.py`** — classe `Memoria`: connessione SQLite + creazione automatica dello schema
- ⬜ **1.3 Memoria episodica** — metodi `ricorda()`, `ricordi_recenti()`, `conta()`, `cerca()`
- ⬜ **1.4 Memoria di lavoro / profilo** — metodi `salva_profilo()`, `leggi_profilo()` + registro accessi
- ⬜ **1.5 Integrazione in `argo.py`** — ogni evento viene salvato; all'avvio Argo dice "bentornato, l'ultima volta…"
- ⬜ **1.6 Test di persistenza** — chiudere e riaprire: i ricordi ci sono ancora ✔

---

## ⬜ FASE 2 — Le Mani sicure
Obiettivo: Argo non solo nota, ma **agisce** sui file, in sicurezza.

- ⬜ 2.1 Modello di autonomia a 3 livelli (osserva / chiede / agisce) in `config/`
- ⬜ 2.2 Modulo `mani.py` — azioni base: sposta, rinomina, crea cartella, archivia
- ⬜ 2.3 Guardrail — niente azioni distruttive senza conferma; cartelle protette
- ⬜ 2.4 Sandbox/anteprima — "ecco cosa farei" prima di toccare il reale
- ⬜ 2.5 Conferma nella finestra (bottoni Sì/No) per il livello "chiede"
- ⬜ 2.6 Test — Argo riordina una cartella di prova senza fare danni

---

## ⬜ FASE 3 — Il Custode completo
Obiettivo: il primo mestiere **finito e usabile ogni giorno**.

- ⬜ 3.1 Sorveglianza multi-cartella (Download, Desktop, Documenti)
- ⬜ 3.2 Regole d'ordine (per tipo / data / progetto) configurabili
- ⬜ 3.3 Rilevamento duplicati e accumuli
- ⬜ 3.4 Apprendimento delle abitudini (impara come ordini tu)
- ⬜ 3.5 Riepilogo proattivo ("oggi ho sistemato…")
- ⬜ 3.6 Test sul campo per qualche giorno

---

## ⬜ FASE 4 — La Memoria profonda (ponte con SONAR)
Obiettivo: Argo capisce il **contenuto** dei file e li collega.

- ⬜ 4.1 Decidere il collegamento: API REST di SONAR (consigliato)
- ⬜ 4.2 Modulo `ponte_sonar.py` — interroga vettori + knowledge graph
- ⬜ 4.3 Argo usa SONAR per ragionare sui contenuti
- ⬜ 4.4 Memoria semantica e a grafo integrate nel ragionamento
- ⬜ 4.5 Test — "trova quel file del progetto X" funziona

---

## ⬜ FASE 5 — Si allarga (verso il dominio IT)
Obiettivo: il secondo mestiere, dove ci sono i soldi.

- ⬜ 5.1 Nuovi sensi: processi, spazio disco, log, servizi
- ⬜ 5.2 Diagnosi automatica di un problema reale
- ⬜ 5.3 Primo sotto-agente specializzato (società di menti)
- ⬜ 5.4 Verso SRE/DevOps autonomo

---

## ⬜ FASE A — Architettura app (motore + UI) *(dopo Fase 2)*
Obiettivo: separare il **motore** (sempre attivo) dalla **finestra** (vista).
- ⬜ A.1 Estrarre il motore in un processo a sé (Engine): memoria + eventi + cervello
- ⬜ A.2 API locale su 127.0.0.1 (il motore espone stato, ricordi, comandi)
- ⬜ A.3 App tray (UI) che si collega al motore via API
- ⬜ A.4 Chiudere la finestra non spegne il motore
- ⬜ A.5 Registrare il motore come **Servizio Windows** (avvio senza login)
- ⬜ A.6 Notifiche Windows dalla tray

## ⬜ FASE FINALE — Packaging & installer *(ultimo passo)*
Obiettivo: un solo installer, come le big tech.
- ⬜ F.1 Impacchettare Engine + UI in eseguibili (es. PyInstaller)
- ⬜ F.2 Bundle del runtime (Ollama/llama.cpp) dentro l'app
- ⬜ F.3 Primo avvio: download automatico del modello adatto all'hardware
- ⬜ F.4 Installer unico (`ARGO Setup.exe`) con icona, tray, avvio automatico
- ⬜ F.5 Pubblicazione (GitHub Releases / sito) + pagina di download
- ⬜ F.6 (futuro) sistema di licenze, se si monetizza

---

*Dettaglio operativo delle fasi successive verrà aggiunto quando ci arriviamo — non si pianifica troppo in là, si tiene il piano vivo.*
