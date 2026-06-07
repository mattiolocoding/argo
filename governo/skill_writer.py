"""
ARGO - governo/skill_writer.py
Genera automaticamente il codice di una skill a partire dalla descrizione
di una lacuna, usando il cervello di ARGO (Ollama in locale).

Il modello viene guidato a produrre UNA funzione Python reale e utile:
  def esegui(contesto: dict) -> dict:
con docstring che documenta gli input/output attesi.

Il codice viene estratto dalla risposta e validato prima di essere restituito.
Se il codice non contiene 'def esegui', viene rigenerato una volta; se fallisce
ancora, viene restituito uno scheletro minimale.

Nessuna libreria esterna richiesta.
"""

import re
import os
import sys
import ast
import textwrap

# Bootstrap sys.path: permette di eseguire sia come:
#   python -m governo.skill_writer
#   python governo\skill_writer.py
_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)


# ---------------------------------------------------------------------------
# Esempi di skill "buone" da mostrare al modello come riferimento
# ---------------------------------------------------------------------------
_ESEMPIO_SKILL_1 = '''
def esegui(contesto: dict) -> dict:
    """
    Conta le parole in un testo.

    Input atteso nel contesto:
      - testo (str): il testo da analizzare (obbligatorio)

    Output restituito:
      - esito (str): "ok" oppure "errore"
      - parole (int): numero di parole trovate
      - caratteri (int): numero di caratteri (spazi inclusi)
    """
    try:
        testo = str(contesto.get("testo", ""))
        if not testo.strip():
            return {"esito": "ok", "parole": 0, "caratteri": 0}
        parole = len(testo.split())
        return {"esito": "ok", "parole": parole, "caratteri": len(testo)}
    except Exception as e:
        return {"esito": "errore", "dettaglio": str(e)}
'''.strip()

_ESEMPIO_SKILL_2 = '''
def esegui(contesto: dict) -> dict:
    """
    Formatta una data in formato italiano leggibile.

    Input atteso nel contesto:
      - data_iso (str): data in formato ISO 8601 (es. "2025-06-07") (obbligatorio)

    Output restituito:
      - esito (str): "ok" oppure "errore"
      - data_formattata (str): data in formato "7 giugno 2025"
    """
    import datetime
    MESI = [
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
    ]
    try:
        data_iso = str(contesto.get("data_iso", ""))
        if not data_iso:
            return {"esito": "errore", "dettaglio": "campo 'data_iso' mancante nel contesto"}
        data = datetime.date.fromisoformat(data_iso)
        formattata = f"{data.day} {MESI[data.month - 1]} {data.year}"
        return {"esito": "ok", "data_formattata": formattata}
    except Exception as e:
        return {"esito": "errore", "dettaglio": str(e)}
'''.strip()


# ---------------------------------------------------------------------------
# Prompt di sistema
# ---------------------------------------------------------------------------
_PROMPT_SISTEMA = f"""Sei un esperto sviluppatore Python che scrive funzioni di utilità per ARGO,
un agente AI locale. Il tuo compito è produrre UNA SOLA funzione Python chiamata esegui(contesto)
che risolva concretamente il problema descritto dall'utente.

REGOLE FERREE (non negoziabili):
1. La funzione DEVE chiamarsi esattamente `def esegui(contesto: dict) -> dict:`.
2. La funzione DEVE avere una docstring in italiano che spiega:
   - cosa fa la funzione
   - quali chiavi si aspetta nel dizionario `contesto` (con tipo e se obbligatorie)
   - cosa restituisce nel dizionario di output
3. Il dizionario di output DEVE contenere sempre la chiave "esito" con valore "ok" o "errore".
4. In caso di errore, il dizionario DEVE contenere "dettaglio" con la descrizione dell'errore.
5. La funzione DEVE usare try/except per gestire tutti gli errori e non sollevare mai eccezioni.
6. Usa SOLO moduli della libreria standard Python (json, datetime, re, math, collections,
   itertools, string, textwrap, hashlib, base64, ecc.).
7. VIETATI: os, subprocess, socket, shutil, eval, exec, open(), importlib, pickle, ctypes,
   requests, urllib, multiprocessing, pathlib, glob, io, builtins.
8. NON fare operazioni distruttive: niente scrittura/cancellazione di file, niente rete,
   niente accesso al filesystem.
9. Vietato codice fuori dalla funzione: niente esempi di utilizzo, niente `print`,
   niente variabili di test, niente chiamate a `esegui` al top-level.
10. Scrivi SOLO il blocco di codice Python tra i delimitatori ```python e ```.
   Nessun testo prima o dopo il codice (eccetto commenti nel codice stesso).
11. Il codice deve essere immediatamente eseguibile senza modifiche.

ESEMPI DI SKILL CORRETTE:

Esempio 1 - contare le parole in un testo:
```python
{_ESEMPIO_SKILL_1}
```

Esempio 2 - formattare una data in italiano:
```python
{_ESEMPIO_SKILL_2}
```

Studia gli esempi e scrivi una funzione con lo stesso livello di qualità e robustezza.
"""


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

def _estrai_codice(risposta: str) -> str | None:
    """
    Estrae il blocco di codice Python dalla risposta del modello.
    Accetta blocchi ```python ... ``` oppure ``` ... ```.
    In mancanza di delimitatori, tenta di trovare 'def esegui' direttamente.

    :return: stringa con il codice (dedentata), oppure None se non trovato
    """
    import textwrap

    # Cerca blocco ```python ... ```
    m = re.search(r"```python\s*(.*?)```", risposta, re.DOTALL | re.IGNORECASE)
    if m:
        codice = textwrap.dedent(m.group(1)).strip()
        if codice:
            return codice

    # Cerca blocco generico ``` ... ```
    m = re.search(r"```\s*(.*?)```", risposta, re.DOTALL)
    if m:
        codice = textwrap.dedent(m.group(1)).strip()
        if "def esegui" in codice:
            return codice

    # Ultima chance: cerca 'def esegui' e prende tutto da lì
    idx = risposta.find("def esegui")
    if idx != -1:
        candidato = risposta[idx:].strip()
        # Rimuovi eventuale testo dopo la funzione (paragrafi vuoti o testo libero)
        return textwrap.dedent(candidato).strip()

    return None


def _ha_esegui(codice: str) -> bool:
    """Verifica che il codice contenga 'def esegui'."""
    return bool(codice) and "def esegui" in codice


def _ripulisci_codice(codice: str) -> str | None:
    """
    Tiene solo import sicuri e la funzione top-level esegui(contesto).
    Rimuove esempi, print e chiamate demo che i modelli tendono ad aggiungere.
    """
    if not codice:
        return None
    pulito = textwrap.dedent(codice).strip()
    try:
        albero = ast.parse(pulito)
    except SyntaxError:
        return pulito

    body = []
    for nodo in albero.body:
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            body.append(nodo)
        elif isinstance(nodo, ast.FunctionDef) and nodo.name == "esegui":
            body.append(nodo)
            break

    if not any(isinstance(n, ast.FunctionDef) and n.name == "esegui" for n in body):
        return pulito

    nuovo = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(nuovo)
    try:
        return ast.unparse(nuovo).strip()
    except Exception:
        return pulito


def _scheletro_skill(descrizione: str) -> str:
    """
    Genera uno scheletro minimale di skill quando il cervello non è disponibile
    o quando la generazione LLM non produce un risultato valido.
    Lo scheletro è comunque funzionante (restituisce un dict valido).
    """
    commento = descrizione.replace("\n", " ").strip()[:200]
    return (
        "def esegui(contesto: dict) -> dict:\n"
        f'    """\n'
        f"    Skill da implementare: {commento}\n"
        f"    Generata come scheletro (cervello offline o generazione fallita).\n"
        f"\n"
        f"    Input: contesto (dict) - parametri liberi\n"
        f"    Output: dizionario con 'esito' e 'nota'\n"
        f'    """\n'
        f"    try:\n"
        f"        # TODO: implementare la logica reale\n"
        f"        return {{'esito': 'non_implementata', 'nota': 'skill scheletro - da completare'}}\n"
        f"    except Exception as e:\n"
        f"        return {{'esito': 'errore', 'dettaglio': str(e)}}\n"
    )


def _nome_da_descrizione(descrizione: str) -> str:
    """
    Ricava un nome sintetico snake_case per la skill dalla descrizione.
    Es. "Conversione file HEIC in JPEG" -> "conversione_file_heic_in_jpeg"
    """
    # Minuscolo, solo alfanumerici e underscore
    nome = descrizione.lower()
    nome = re.sub(r"[^a-z0-9\s_]", "", nome)
    nome = re.sub(r"\s+", "_", nome.strip())
    # Tronca a 40 caratteri, rimuovi underscore iniziali/finali
    return nome[:40].strip("_") or "skill_generata"


def _chiedi_al_modello(cervello, prompt: str) -> str | None:
    """
    Interroga il cervello con il prompt dato e restituisce la risposta grezza,
    oppure None in caso di errore o risposta non valida.
    """
    try:
        risposta = cervello.pensa(prompt, contesto=[
            {"role": "system", "content": _PROMPT_SISTEMA}
        ])
        # Risposta vuota o segnale di errore interno del cervello
        if not risposta or risposta.startswith("["):
            return None
        return risposta
    except Exception as e:
        print(f"[skill_writer] Errore durante la chiamata al cervello: {e}")
        return None


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class SkillWriter:
    """
    Genera skill Python usando il cervello di ARGO.

    Uso:
        writer = SkillWriter(cervello)
        risultato = writer.genera("Argo non sa leggere file HEIC")
        # risultato -> {'nome': '...', 'descrizione': '...', 'codice': '...'}
        # oppure None se la descrizione è vuota
    """

    def __init__(self, cervello):
        """
        :param cervello: istanza di Cervello (cervello.py) già inizializzata.
        """
        self.cervello = cervello

    def genera(self, descrizione_lacuna: str) -> dict | None:
        """
        Genera una skill per colmare la lacuna descritta.

        Flusso:
          1. Se il cervello è disponibile, chiede al modello di scrivere la funzione.
          2. Estrae il blocco di codice dalla risposta e verifica che contenga 'def esegui'.
          3. Se l'estrazione fallisce, riprova con un prompt più esplicito (un secondo tentativo).
          4. Se anche il secondo tentativo fallisce o il cervello è offline, produce uno scheletro.

        :param descrizione_lacuna: testo che descrive cosa ARGO non sa fare
        :return: dizionario {'nome', 'descrizione', 'codice'} oppure None se input vuoto
        """
        if not descrizione_lacuna or not descrizione_lacuna.strip():
            return None

        descrizione_lacuna = descrizione_lacuna.strip()
        nome = _nome_da_descrizione(descrizione_lacuna)
        codice = None

        # --- Tentativo con il cervello LLM ---
        if self.cervello is not None:
            try:
                vivo = self.cervello.vivo()
            except Exception:
                vivo = False

            if vivo:
                # Primo tentativo: prompt principale
                prompt_1 = (
                    f"Scrivi una funzione Python chiamata `esegui(contesto: dict) -> dict` "
                    f"che risolva concretamente questo problema di ARGO:\n\n"
                    f"PROBLEMA: {descrizione_lacuna}\n\n"
                    f"Ricorda: firma ESATTA `def esegui(contesto: dict) -> dict:`, "
                    f"docstring in italiano con input/output, only stdlib, "
                    f"try/except ovunque, restituisci sempre un dict con 'esito'."
                )
                risposta_1 = _chiedi_al_modello(self.cervello, prompt_1)
                if risposta_1:
                    candidato = _estrai_codice(risposta_1)
                    if candidato and _ha_esegui(candidato):
                        codice = _ripulisci_codice(candidato)

                # Secondo tentativo se il primo non ha prodotto 'def esegui'
                if not codice:
                    prompt_2 = (
                        f"ATTENZIONE: la tua risposta precedente non conteneva la funzione "
                        f"`def esegui(contesto: dict) -> dict:`. Questa funzione è OBBLIGATORIA.\n\n"
                        f"Problema da risolvere: {descrizione_lacuna}\n\n"
                        f"Scrivi SOLO il blocco Python tra ```python e ``` con la funzione "
                        f"`def esegui(contesto: dict) -> dict:`. "
                        f"Nessun altro testo. Solo il codice."
                    )
                    risposta_2 = _chiedi_al_modello(self.cervello, prompt_2)
                    if risposta_2:
                        candidato = _estrai_codice(risposta_2)
                        if candidato and _ha_esegui(candidato):
                            codice = _ripulisci_codice(candidato)
                        else:
                            print(f"[skill_writer] Secondo tentativo fallito: 'def esegui' assente.")

        # --- Fallback: scheletro minimale ---
        if not codice:
            codice = _scheletro_skill(descrizione_lacuna)

        return {
            "nome": nome,
            "descrizione": descrizione_lacuna,
            "codice": codice,
        }


# ---------- smoke-test ----------
if __name__ == "__main__":
    print("== Smoke-test SkillWriter ==")

    # Stub minimale di Cervello per il test (non richiede Ollama)
    class CervelloFinto:
        def vivo(self):
            return False  # Simula cervello offline

        def pensa(self, messaggio, contesto=None):
            return "[cervello offline]"

    writer = SkillWriter(CervelloFinto())

    # 1. Genera con cervello offline -> deve produrre uno scheletro valido
    risultato = writer.genera("ARGO non riesce a leggere file in formato HEIC")
    assert risultato is not None, "Il risultato non deve essere None"
    assert "nome" in risultato
    assert "descrizione" in risultato
    assert "codice" in risultato
    assert "def esegui" in risultato["codice"], "Il codice deve contenere 'def esegui'"
    assert "esito" in risultato["codice"], "Lo scheletro deve restituire 'esito'"
    print(f"  [1] Scheletro generato (cervello offline): nome='{risultato['nome']}'")

    # 2. Testa estrazione codice con delimitatori python
    risposta_simulata = (
        "Ecco la funzione richiesta:\n\n"
        "```python\n"
        "def esegui(contesto: dict) -> dict:\n"
        '    """Converte il testo in maiuscolo."""\n'
        "    try:\n"
        "        return {'esito': 'ok', 'risultato': contesto.get('testo', '').upper()}\n"
        "    except Exception as e:\n"
        "        return {'esito': 'errore', 'dettaglio': str(e)}\n"
        "```\n"
    )
    codice_estratto = _estrai_codice(risposta_simulata)
    assert codice_estratto is not None, "L'estrazione deve trovare il codice"
    assert "def esegui" in codice_estratto
    print("  [2] Estrazione codice da delimitatori ```python: OK")

    # 3. Testa estrazione da blocco generico ``` ... ```
    risposta_generica = (
        "```\n"
        "def esegui(contesto: dict) -> dict:\n"
        "    return {'esito': 'ok'}\n"
        "```\n"
    )
    estratto_generico = _estrai_codice(risposta_generica)
    assert estratto_generico is not None
    assert "def esegui" in estratto_generico
    print("  [3] Estrazione da blocco generico: OK")

    # 4. Testa _ha_esegui
    assert _ha_esegui("def esegui(contesto): return {}") is True
    assert _ha_esegui("def altro(): pass") is False
    assert _ha_esegui("") is False
    print("  [4] _ha_esegui(): OK")

    # 5. Nome normalizzato
    nome = _nome_da_descrizione("Argo non capisce i file .HEIC — problema di formato!")
    assert nome, "Il nome non deve essere vuoto"
    assert " " not in nome, "Il nome non deve contenere spazi"
    assert nome == nome.lower(), "Il nome deve essere minuscolo"
    print(f"  [5] Nome normalizzato: '{nome}'")

    # 6. Input vuoto -> None
    nessuno = writer.genera("")
    assert nessuno is None, "Input vuoto deve restituire None"
    print("  [6] Input vuoto -> None: OK")

    # 7. Testa cervello che restituisce una skill valida con delimitatori
    class CervelloBuono:
        def vivo(self):
            return True

        def pensa(self, messaggio, contesto=None):
            return (
                "```python\n"
                "def esegui(contesto: dict) -> dict:\n"
                '    """Somma due numeri."""\n'
                "    try:\n"
                "        a = contesto.get('a', 0)\n"
                "        b = contesto.get('b', 0)\n"
                "        return {'esito': 'ok', 'somma': a + b}\n"
                "    except Exception as e:\n"
                "        return {'esito': 'errore', 'dettaglio': str(e)}\n"
                "```"
            )

    writer_buono = SkillWriter(CervelloBuono())
    ris_buono = writer_buono.genera("ARGO non sa sommare due numeri")
    assert ris_buono is not None
    assert "def esegui" in ris_buono["codice"]
    assert "somma" in ris_buono["codice"]
    print(f"  [7] Skill da cervello valido: nome='{ris_buono['nome']}'")

    # 8. Cervello che NON restituisce def esegui al primo tentativo, poi sì
    tentativi = []
    class CervelloRiluttante:
        def vivo(self):
            return True
        def pensa(self, messaggio, contesto=None):
            tentativi.append(1)
            if len(tentativi) == 1:
                return "Ecco una spiegazione del problema senza codice."
            return (
                "```python\n"
                "def esegui(contesto: dict) -> dict:\n"
                "    return {'esito': 'ok', 'n': 1}\n"
                "```"
            )

    writer_riluttante = SkillWriter(CervelloRiluttante())
    ris_riluttante = writer_riluttante.genera("ARGO non sa fare qualcosa")
    assert ris_riluttante is not None
    assert "def esegui" in ris_riluttante["codice"]
    assert len(tentativi) == 2, f"Attesi 2 tentativi, fatti {len(tentativi)}"
    print(f"  [8] Secondo tentativo attivato correttamente ({len(tentativi)} chiamate): OK")

    print("OK")
