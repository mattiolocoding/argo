"""
ARGO - modelli.py
Model Mesh con routing intelligente: RIFLESSO / RAGIONATORE / ESPERTO.

Rileva i modelli installati su Ollama e li assegna a tre livelli:
  - riflesso    : modello piccolo/veloce (risposte brevi e fattuali)
  - ragionatore : modello medio, default per la maggior parte dei task
  - esperto     : deliberazione best-of-N via Pensatore per task complessi

Nessuna libreria esterna: solo stdlib (urllib, json, os).

Metodi pubblici compatibili con le versioni precedenti:
  stato()              -> dict con mappatura ruolo->modello
  valuta_complessita() -> 'bassa' | 'media' | 'alta'
  pensa(testo, contesto="") -> dict {livello, modello, risposta}
  route(testo)         -> 'riflesso' | 'ragionatore' | 'esperto'
"""

import json
import os
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------
OLLAMA_HOST      = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT_RISPOSTA = 120  # secondi per /api/chat
TIMEOUT_STATO    = 5    # secondi per /api/tags

# ---------------------------------------------------------------------------
# Euristiche per classificare un nome-modello in una categoria di taglia
# ---------------------------------------------------------------------------
_PAROLE_PICCOLO = ["mini", ":1b", "1b", ":3b", "3b", "tiny", "nano", "phi3"]
_PAROLE_MEDIO   = [":7b", "7b", ":8b", "8b", ":9b", "9b", "mistral", "llama3.1:8b"]
_PAROLE_GRANDE  = [
    "qwen3", "llama3.3", ":70b", "70b", ":34b", "34b", ":32b", "32b",
    "mixtral", "command-r", "deepseek", "llama3.2:90b", ":72b", "72b",
    ":13b", "13b", ":14b", "14b", ":27b", "27b", ":20b", "20b",
]

# Frammenti che identificano i modelli di EMBEDDING: NON sono modelli di chat e
# non devono mai essere assegnati a un livello del mesh (riflesso/ragionatore/esperto).
_PAROLE_EMBEDDING = [
    "embed", "embedding", "bge", "nomic", "minilm", "mxbai",
    "e5-", "gte-", "snowflake-arctic-embed", "all-minilm", "paraphrase",
]


def _e_modello_embedding(nome: str) -> bool:
    """True se il nome del modello indica un modello di embedding (non chat)."""
    n = (nome or "").lower()
    return any(frammento in n for frammento in _PAROLE_EMBEDDING)

# Parole nel testo dell'utente che indicano alta complessita'
_PAROLE_ALTA_COMPLESSITA = [
    "analizza", "analisi", "codice", "perche'", "perche", "perché", "pianifica",
    "pianificazione", "spiega", "elabora", "progetta", "implementa",
    "implementazione", "architettura", "strategia", "confronta", "valuta",
    "ottimizza", "debugging", "debug", "refactor", "refactoring",
    "ricerca", "approfondisci", "dimostra", "calcola", "decidi", "decisione",
    "step", "passo per passo", "ragiona", "pro e contro", "vantaggi",
    "svantaggi", "rischi", "conviene",
]

# Parole che indicano complessita' media
_PAROLE_MEDIA_COMPLESSITA = [
    "scrivi", "crea", "elenca", "descrive", "descrivi", "riassumi",
    "riassunto", "cerca", "trova", "modifica", "aggiorna", "controlla",
    "verifica", "genera", "traduci",
]

# Soglie di lunghezza (in caratteri) per stimare la complessita' dal testo
_SOGLIA_BASSA = 80    # meno di N caratteri -> bassa (se niente parole speciali)
_SOGLIA_ALTA  = 300   # piu' di N caratteri -> alta  (se niente parole speciali)

# Soglia di parole per escalation esperto (lunghezza in parole)
_SOGLIA_PAROLE_ESPERTO = 60


def _taglia_modello(nome: str) -> str:
    """
    Classifica un nome di modello Ollama in 'piccolo', 'medio' o 'grande'.
    """
    n = nome.lower()
    for frammento in _PAROLE_GRANDE:
        if frammento in n:
            return "grande"
    for frammento in _PAROLE_MEDIO:
        if frammento in n:
            return "medio"
    for frammento in _PAROLE_PICCOLO:
        if frammento in n:
            return "piccolo"
    # Nessun indizio trovato: assume medio come default
    return "medio"


class ModelMesh:
    """
    Gestisce il pool di modelli Ollama e fa routing intelligente su tre livelli.

    Livelli:
      - 'riflesso'    -> modello piccolo/veloce (risposte brevi, System-1)
      - 'ragionatore' -> modello medio, default
      - 'esperto'     -> best-of-N via Pensatore.delibera() (System-2 completo)

    Utilizzo base:
        mesh = ModelMesh()
        risultato = mesh.pensa("Analizza questo codice e spiega perche' fallisce")
        print(risultato["livello"], risultato["modello"])
        print(risultato["risposta"])
    """

    def __init__(self):
        self.host = OLLAMA_HOST.rstrip("/")
        # Mappa livello -> nome modello (None finche' non inizializzato)
        self._livelli: dict = {
            "riflesso":    None,
            "ragionatore": None,
            "esperto":     None,
        }
        self._inizializzato = False
        self._errore_init: str | None = None
        # Istanza pigra del Pensatore (creata al primo uso esperto)
        self._pensatore = None
        # Tenta subito il rilevamento modelli
        self._rileva_modelli()

    # -----------------------------------------------------------------------
    # Sezione privata: rilevamento e assegnazione livelli
    # -----------------------------------------------------------------------

    def _get_modelli_installati(self) -> list[str]:
        """
        Chiama GET /api/tags su Ollama e ritorna la lista dei nomi modello.
        Lista vuota se Ollama non risponde (senza crashare).
        """
        try:
            url = self.host + "/api/tags"
            with urllib.request.urlopen(url, timeout=TIMEOUT_STATO) as r:
                dati = json.loads(r.read().decode("utf-8"))
                return [m.get("name", "") for m in dati.get("models", []) if m.get("name")]
        except urllib.error.URLError as e:
            self._errore_init = f"Ollama non raggiungibile: {e}"
            return []
        except Exception as e:
            self._errore_init = f"Errore lettura modelli: {e}"
            return []

    def _rileva_modelli(self):
        """
        Recupera i modelli installati e assegna ciascuno al livello appropriato.
        Strategia:
          1. Classifica ogni modello in piccolo/medio/grande.
          2. Sceglie il migliore candidato per ciascun livello.
          3. Se un livello rimane vuoto, usa il piu' vicino disponibile.
          4. Se c'e' un solo modello, lo usa per tutti i livelli.
        """
        modelli = self._get_modelli_installati()
        # Escludi i modelli di embedding: non sanno chattare, non vanno nei livelli.
        modelli = [m for m in modelli if not _e_modello_embedding(m)]
        if not modelli:
            return  # Ollama spento o nessun modello di chat: livelli restano None

        piccoli = [m for m in modelli if _taglia_modello(m) == "piccolo"]
        medi    = [m for m in modelli if _taglia_modello(m) == "medio"]
        grandi  = [m for m in modelli if _taglia_modello(m) == "grande"]

        # Caso degenere: un solo modello -> usalo per tutti i livelli
        if len(modelli) == 1:
            self._livelli["riflesso"]    = modelli[0]
            self._livelli["ragionatore"] = modelli[0]
            self._livelli["esperto"]     = modelli[0]
            self._inizializzato = True
            return

        # Livello 'riflesso': piccoli > medi > grandi
        if piccoli:
            self._livelli["riflesso"] = piccoli[0]
        elif medi:
            self._livelli["riflesso"] = medi[0]
        else:
            self._livelli["riflesso"] = grandi[0]

        # Livello 'esperto': grandi > medi[-1] > piccoli[-1]
        if grandi:
            self._livelli["esperto"] = grandi[0]
        elif medi:
            self._livelli["esperto"] = medi[-1]
        else:
            self._livelli["esperto"] = piccoli[-1]

        # Livello 'ragionatore': medi > anything between riflesso e esperto
        if medi:
            candidati = [m for m in medi
                         if m != self._livelli["riflesso"]
                         and m != self._livelli["esperto"]]
            self._livelli["ragionatore"] = candidati[0] if candidati else medi[0]
        else:
            altri = [m for m in modelli
                     if m != self._livelli["riflesso"]
                     and m != self._livelli["esperto"]]
            self._livelli["ragionatore"] = altri[0] if altri else self._livelli["esperto"]

        self._inizializzato = True

    def _get_pensatore(self):
        """
        Crea (la prima volta) e restituisce un'istanza di Pensatore
        che usa il modello 'esperto' di questo mesh.
        """
        if self._pensatore is not None:
            return self._pensatore
        # Import lazy per non creare dipendenza circolare al caricamento
        _argo_dir = os.path.dirname(os.path.abspath(__file__))
        if _argo_dir not in sys.path:
            sys.path.insert(0, _argo_dir)
        from cervello import Cervello
        from pensatore import Pensatore
        # Usa il modello esperto se disponibile, altrimenti il default
        modello_esperto = self._livelli.get("esperto")
        cervello = Cervello(modello=modello_esperto)
        self._pensatore = Pensatore(cervello=cervello, n_candidati=3)
        return self._pensatore

    def _chiama_ollama_diretto(self, modello: str, testo: str,
                               contesto: str = "", breve: bool = False) -> str:
        """
        Chiama /api/chat direttamente su Ollama con il modello dato.
        Se breve=True aggiunge istruzione per risposta concisa (livello riflesso).
        Ritorna stringa; non lancia eccezioni.
        """
        if breve:
            prompt = (
                "Rispondi in modo MOLTO BREVE e diretto (max 1-2 frasi). "
                "Solo fatti, nessuna spiegazione extra.\n\n" + testo
            )
        else:
            prompt = testo

        messaggi = []
        if contesto:
            messaggi.append({"role": "user", "content": contesto})
        messaggi.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model":    modello,
            "messages": messaggi,
            "stream":   False,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.host + "/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_RISPOSTA) as r:
                dati = json.loads(r.read().decode("utf-8"))
                contenuto = dati.get("message", {}).get("content", "").strip()
                return contenuto if contenuto else "[risposta vuota dal modello]"
        except urllib.error.URLError as e:
            return f"[ModelMesh] Ollama non raggiungibile ({modello}): {e}"
        except Exception as e:
            return f"[ModelMesh] Errore chiamata ({modello}): {e}"

    # -----------------------------------------------------------------------
    # Sezione pubblica: API principale
    # -----------------------------------------------------------------------

    def stato(self) -> dict:
        """
        Ritorna la mappatura attuale livello -> modello, piu' metadati.

        Esempio:
          {
            'riflesso':    'phi3:mini',
            'ragionatore': 'llama3.1:8b',
            'esperto':     'qwen3:32b',
            'inizializzato': True,
          }
        Se Ollama e' spento aggiunge anche 'errore'.
        """
        risultato = dict(self._livelli)
        risultato["inizializzato"] = self._inizializzato
        if not self._inizializzato:
            risultato["errore"] = self._errore_init or "Modelli non ancora rilevati"
        return risultato

    def valuta_complessita(self, testo: str) -> str:
        """
        Stima la complessita' del testo dell'utente.
        Ritorna: 'bassa', 'media' o 'alta'.

        Euristiche (in ordine di priorita'):
          1. Presenza di parole chiave ad alta complessita'  -> 'alta'
          2. Presenza di parole chiave a media complessita'  -> 'media'
          3. Lunghezza in parole >= soglia esperto           -> 'alta'
          4. Lunghezza in caratteri:
             - < _SOGLIA_BASSA  -> 'bassa'
             - > _SOGLIA_ALTA   -> 'alta'
             - nel mezzo        -> 'media'
        """
        testo_lower = testo.lower()

        for parola in _PAROLE_ALTA_COMPLESSITA:
            if parola in testo_lower:
                return "alta"

        for parola in _PAROLE_MEDIA_COMPLESSITA:
            if parola in testo_lower:
                return "media"

        n_parole = len(testo.split())
        if n_parole >= _SOGLIA_PAROLE_ESPERTO:
            return "alta"

        lunghezza = len(testo.strip())
        if lunghezza < _SOGLIA_BASSA:
            return "bassa"
        elif lunghezza > _SOGLIA_ALTA:
            return "alta"
        return "media"

    def route(self, testo: str) -> str:
        """
        Determina il livello di routing per il testo dato.
        Ritorna: 'riflesso' | 'ragionatore' | 'esperto'

        Mappa:
          complessita' bassa  -> 'riflesso'
          complessita' media  -> 'ragionatore'
          complessita' alta   -> 'esperto'
        """
        complessita = self.valuta_complessita(testo)
        return {
            "bassa": "riflesso",
            "media": "ragionatore",
            "alta":  "esperto",
        }[complessita]

    def pensa(self, testo: str, contesto: str = "") -> dict:
        """
        Instrada il testo al livello corretto e ritorna un dict strutturato.

        Routing:
          riflesso    -> chiamata diretta con risposta breve (veloce)
          ragionatore -> chiamata diretta al modello medio (default)
          esperto     -> Pensatore.delibera() best-of-N (deliberativo)

        Ritorna:
          {
            'livello':  'riflesso' | 'ragionatore' | 'esperto',
            'modello':  str | None,
            'risposta': str,
            # solo per esperto:
            'candidati': int,
            'modo':      str,
          }

        Degrada in modo silenzioso se Ollama e' spento.
        """
        livello = self.route(testo)
        modello = self._livelli.get(livello)

        # Fallback difensivo: se il modello del livello non e' disponibile
        if modello is None:
            for fallback in ("ragionatore", "riflesso", "esperto"):
                modello = self._livelli.get(fallback)
                if modello is not None:
                    livello = fallback
                    break

        if modello is None:
            return {
                "livello":  livello,
                "modello":  None,
                "risposta": (
                    "[ModelMesh offline] Nessun modello disponibile. "
                    f"Ollama e' acceso? {self._errore_init or ''}"
                ),
            }

        # --- RIFLESSO: risposta diretta, breve ---
        if livello == "riflesso":
            risposta = self._chiama_ollama_diretto(
                modello, testo, contesto=contesto, breve=True
            )
            return {"livello": "riflesso", "modello": modello, "risposta": risposta}

        # --- RAGIONATORE: risposta diretta standard ---
        if livello == "ragionatore":
            risposta = self._chiama_ollama_diretto(
                modello, testo, contesto=contesto, breve=False
            )
            return {"livello": "ragionatore", "modello": modello, "risposta": risposta}

        # --- ESPERTO: deliberazione best-of-N via Pensatore ---
        try:
            pensatore = self._get_pensatore()
            risultato = pensatore.delibera(testo, contesto=contesto)
            return {
                "livello":    "esperto",
                "modello":    modello,
                "risposta":   risultato.get("risposta", ""),
                "candidati":  risultato.get("candidati", 0),
                "modo":       risultato.get("modo", "deliberato"),
            }
        except Exception as e:
            # Se il Pensatore non e' disponibile, degrada al ragionatore
            modello_fallback = self._livelli.get("ragionatore") or modello
            risposta = self._chiama_ollama_diretto(
                modello_fallback, testo, contesto=contesto, breve=False
            )
            return {
                "livello":  "esperto",
                "modello":  modello_fallback,
                "risposta": risposta,
                "nota":     f"Pensatore non disponibile ({e}), degradato a ragionatore",
            }


# ---------------------------------------------------------------------------
# Smoke-test: python modelli.py   oppure   python -m modelli
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Bootstrap sys.path per import relativi (sia script che -m)
    _self_dir = os.path.dirname(os.path.abspath(__file__))
    if _self_dir not in sys.path:
        sys.path.insert(0, _self_dir)

    print("=" * 60)
    print("  ARGO - ModelMesh smoke-test")
    print("=" * 60)

    mesh = ModelMesh()
    s = mesh.stato()

    # -- STATO LIVELLI --
    print("\n[STATO LIVELLI]")
    if "errore" in s:
        print(f"  Attenzione: {s['errore']}")
    for livello in ("riflesso", "ragionatore", "esperto"):
        valore = s.get(livello)
        etichetta = valore if valore else "(nessun modello assegnato)"
        print(f"  {livello:12s} -> {etichetta}")

    # -- ROUTE --
    print("\n[ROUTE / VALUTAZIONE COMPLESSITA']")
    casi_test = [
        ("Ciao!",                                                "attesa: riflesso (bassa)"),
        ("Scrivi una lista della spesa",                         "attesa: ragionatore (media)"),
        ("Analizza questo codice e spiega perche' fallisce",     "attesa: esperto (alta)"),
        ("X" * 350,                                              "attesa: esperto (alta, lunga)"),
        ("ok",                                                   "attesa: riflesso (bassa, corta)"),
        ("pianifica la migrazione del database passo per passo", "attesa: esperto (alta)"),
    ]
    tutti_ok = True
    for testo, nota in casi_test:
        livello_stimato = mesh.route(testo)
        anteprima = testo[:45].replace("\n", " ")
        print(f"  [{livello_stimato:12s}] '{anteprima}...' ({nota})")

    # -- PROVA PENSIERO (solo se Ollama e' acceso) --
    print("\n[PROVA PENSA]")
    ollama_spento = all(v is None for v in (
        s["riflesso"], s["ragionatore"], s["esperto"]
    ))
    if ollama_spento:
        print("  Ollama non disponibile: test di pensiero saltato (degradazione corretta).")
        # Verifica che il dict di fallback sia strutturato correttamente
        r = mesh.pensa("Ciao")
        assert isinstance(r, dict), "pensa() deve ritornare un dict"
        assert "livello"  in r, "manca 'livello'"
        assert "modello"  in r, "manca 'modello'"
        assert "risposta" in r, "manca 'risposta'"
        print("  Struttura dict verificata (offline).")
    else:
        domanda_semplice = "Dimmi solo 'ok'."
        print(f"  Domanda riflesso: '{domanda_semplice}'")
        r = mesh.pensa(domanda_semplice)
        assert isinstance(r, dict), "pensa() deve ritornare un dict"
        print(f"  -> livello={r['livello']}  modello={r['modello']}")
        print(f"     risposta: {r['risposta'][:100]}")

    print("\n" + "=" * 60)
    print("  OK")
    print("=" * 60)
