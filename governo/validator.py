"""
ARGO - governo/validator.py
Validatore di skill generate dinamicamente dal ciclo di sonno.

Esegue tre controlli in sequenza:
  (a) Analisi statica AST di sicurezza (tramite sandbox_skill.analizza_sicurezza).
  (b) Verifica che il codice definisca la funzione `def esegui(contesto)` al
      livello radice con almeno un parametro.
  (c) Esecuzione di prova in sandbox isolata con un contesto di esempio realistico.
      La skill deve restituire un dizionario (non None, non eccezione).

Ritorna sempre un dizionario {ok: bool, motivi: [lista di stringhe]}.

SICUREZZA: il codice non viene mai eseguito nel processo principale.
           La sandbox usa cartelle temporanee isolate (vedi sandbox_skill.py).
           L'ATTIVAZIONE di una skill richiede sempre approvazione umana esplicita
           tramite SkillRegistry.approva() prima di poter chiamare attiva().

Nessuna libreria esterna richiesta.
"""

# Bootstrap sys.path: permette di eseguire sia come:
#   python -m governo.validator
#   python governo\validator.py
import os as _os
import sys as _sys
_root = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
if _root not in _sys.path:
    _sys.path.insert(0, _root)

import ast
import json

from governo.sandbox_skill import analizza_sicurezza, prova_in_sandbox, esegui_in_sandbox


# Contesto di esempio da passare alla skill durante la validazione.
# Contiene chiavi tipiche usate dalle skill per testare la robustezza.
_CONTESTO_ESEMPIO = {
    "testo": "Questo è un testo di esempio per la validazione della skill.",
    "n": 42,
    "data_iso": "2025-06-07",
    "valore": 3.14,
    "lista": [1, 2, 3],
    "flag": True,
}


class Validator:
    """
    Valida una skill Python generata dal ciclo di sonno prima che venga
    proposta nel SkillRegistry.

    Uso tipico:
        v = Validator()
        risultato = v.valida(codice_skill)
        # risultato -> {'ok': True, 'motivi': []}
        # oppure    -> {'ok': False, 'motivi': ['errore di sintassi: ...', ...]}
    """

    def __init__(self, timeout_sandbox: int = 10):
        """
        :param timeout_sandbox: secondi massimi per l'esecuzione in sandbox (default 10)
        """
        self.timeout_sandbox = timeout_sandbox

    def valida(self, codice: str) -> dict:
        """
        Esegue la pipeline completa di validazione su una skill.

        Passi:
          1. Analisi statica AST (sicurezza + sintassi) tramite analizza_sicurezza().
          2. Verifica esplicita che `def esegui(contesto)` sia al livello radice
             con almeno un parametro.
          3. Esecuzione in sandbox con un contesto di esempio realistico.
             Il risultato deve essere un dizionario Python valido (non None,
             non stringa vuota, non eccezione non gestita).

        Se uno qualsiasi dei passi fallisce, la validazione si ferma e
        restituisce {ok: False, motivi: [...]}.

        :param codice: sorgente Python della skill
        :return: {'ok': bool, 'motivi': lista di stringhe con i problemi trovati}
        """
        motivi: list[str] = []

        # ----------------------------------------------------------------
        # Passo 1: analisi statica AST (sicurezza + sintassi)
        # ----------------------------------------------------------------
        try:
            analisi = analizza_sicurezza(codice)
        except Exception as e:
            return {"ok": False, "motivi": [f"Eccezione durante l'analisi statica: {e}"]}

        if not analisi["ok"]:
            # analizza_sicurezza() include già la verifica 'def esegui' tra i suoi
            # controlli; raccogliamo tutti i motivi e usciamo subito.
            return {"ok": False, "motivi": analisi.get("motivi", ["analisi statica fallita"])}

        # ----------------------------------------------------------------
        # Passo 2: verifica esplicita di def esegui(contesto) al top-level
        # ----------------------------------------------------------------
        try:
            import textwrap
            albero = ast.parse(textwrap.dedent(codice))

            # Cerca funzioni di primo livello (figli diretti del Module)
            funzioni_top = [
                n for n in ast.iter_child_nodes(albero)
                if isinstance(n, ast.FunctionDef) and n.name == "esegui"
            ]

            if not funzioni_top:
                # Potrebbe essere nidificata dentro un'altra funzione/classe: non accettabile
                funzioni_qualsiasi = [
                    n for n in ast.walk(albero)
                    if isinstance(n, ast.FunctionDef) and n.name == "esegui"
                ]
                if funzioni_qualsiasi:
                    motivi.append(
                        "'def esegui' trovata ma non al livello radice del modulo "
                        "(non deve essere nidificata in classi o altre funzioni)"
                    )
                else:
                    motivi.append(
                        "la skill deve definire 'def esegui(contesto)' al livello radice del modulo"
                    )
            else:
                fn = funzioni_top[0]
                # Deve avere almeno un argomento posizionale
                n_args = len(fn.args.args)
                if n_args < 1:
                    motivi.append(
                        "def esegui deve accettare almeno un parametro (contesto)"
                    )

            for nodo in ast.iter_child_nodes(albero):
                if isinstance(nodo, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(nodo, ast.FunctionDef) and nodo.name == "esegui":
                    continue
                motivi.append(
                    "codice top-level non consentito: la skill deve contenere solo "
                    "import sicuri e def esegui(contesto)"
                )
                break

        except SyntaxError as e:
            motivi.append(f"errore di sintassi nella verifica AST: {e}")
        except Exception as e:
            motivi.append(f"errore imprevisto nella verifica AST: {e}")

        if motivi:
            return {"ok": False, "motivi": motivi}

        # ----------------------------------------------------------------
        # Passo 3: esecuzione in sandbox con contesto di esempio realistico
        # ----------------------------------------------------------------
        try:
            sandbox_ris = esegui_in_sandbox(
                codice,
                contesto=_CONTESTO_ESEMPIO,
                timeout=self.timeout_sandbox,
            )
        except Exception as e:
            return {"ok": False, "motivi": [f"Eccezione durante l'esecuzione sandbox: {e}"]}

        if not sandbox_ris["ok"]:
            output_breve = (sandbox_ris.get("output") or "nessun output")[:300]
            motivi.append(f"sandbox fallita: {output_breve}")
            return {"ok": False, "motivi": motivi}

        # Verifica che il risultato sia un dizionario valido.
        # La sandbox wrappa l'output come: {"esito": "ok", "risultato": str(_risultato)}
        # quindi 'risultato' contiene str(dict) se la skill ha restituito un dict.
        dati = sandbox_ris.get("dati")
        if dati is None or "risultato" not in dati:
            motivi.append("sandbox senza risultato JSON valido")
            return {"ok": False, "motivi": motivi}

        # 'risultato' è str(dict()) -> deve iniziare con '{'
        # Se la skill restituisce None -> str(None) == "None" (non inizia con '{')
        risultato_str = str(dati["risultato"]).strip()
        if not risultato_str.startswith("{"):
            motivi.append(
                f"la funzione esegui() deve restituire un dizionario, "
                f"ma ha restituito: {risultato_str[:100]}"
            )
            return {"ok": False, "motivi": motivi}

        # Tutti i controlli superati
        return {"ok": True, "motivi": []}


# ---------- smoke-test ----------
if __name__ == "__main__":
    print("== Smoke-test Validator ==")

    v = Validator(timeout_sandbox=15)

    # --- [1] Skill valida completa: deve passare tutti i controlli ---
    codice_valido = (
        "def esegui(contesto: dict) -> dict:\n"
        '    """\n'
        "    Skill di prova: restituisce un dizionario con l'eco del testo.\n"
        "\n"
        "    Input: testo (str) - il testo da echeggiare\n"
        "    Output: esito (str), eco (str)\n"
        '    """\n'
        "    try:\n"
        "        testo = contesto.get('testo', 'vuoto')\n"
        "        return {'esito': 'ok', 'eco': testo}\n"
        "    except Exception as e:\n"
        "        return {'esito': 'errore', 'dettaglio': str(e)}\n"
    )
    ris = v.valida(codice_valido)
    assert ris["ok"] is True, f"Atteso ok=True, motivi={ris['motivi']}"
    print(f"  [1] skill valida -> ok={ris['ok']}, motivi={ris['motivi']}")

    # --- [2] Skill pericolosa: deve essere bloccata all'analisi statica ---
    codice_pericoloso = (
        "import subprocess\n"
        "def esegui(contesto):\n"
        "    subprocess.run(['whoami'])\n"
        "    return {}\n"
    )
    ris2 = v.valida(codice_pericoloso)
    assert ris2["ok"] is False, "Il codice pericoloso deve essere bloccato"
    assert len(ris2["motivi"]) > 0
    print(f"  [2] skill pericolosa -> ok={ris2['ok']}, motivi={ris2['motivi']}")

    # --- [3] Skill senza def esegui: deve fallire ---
    codice_senza_esegui = "x = 42\ny = x * 2\n"
    ris3 = v.valida(codice_senza_esegui)
    assert ris3["ok"] is False
    print(f"  [3] senza esegui -> ok={ris3['ok']}, motivi={ris3['motivi']}")

    # --- [4] Skill che solleva eccezione non gestita in sandbox: deve fallire ---
    codice_errore = (
        "def esegui(contesto):\n"
        "    raise RuntimeError('errore intenzionale di prova')\n"
    )
    ris4 = v.valida(codice_errore)
    assert ris4["ok"] is False
    print(f"  [4] errore sandbox -> ok={ris4['ok']}, motivi={ris4['motivi'][:1]}")

    # --- [5] Skill con sintassi errata: deve fallire ---
    codice_sintassi = "def esegui(contesto\n    return {}\n"
    ris5 = v.valida(codice_sintassi)
    assert ris5["ok"] is False
    print(f"  [5] sintassi errata -> ok={ris5['ok']}, motivi={ris5['motivi'][:1]}")

    # --- [6] Skill che restituisce None: deve fallire al passo 3 ---
    codice_none = (
        "def esegui(contesto):\n"
        "    return None\n"
    )
    ris6 = v.valida(codice_none)
    assert ris6["ok"] is False, f"Skill che restituisce None deve fallire: {ris6}"
    print(f"  [6] restituisce None -> ok={ris6['ok']}, motivi={ris6['motivi'][:1]}")

    # --- [7] Skill con eval vietato: deve fallire all'analisi statica ---
    codice_eval = (
        "def esegui(contesto):\n"
        "    return eval('1+1')\n"
    )
    ris7 = v.valida(codice_eval)
    assert ris7["ok"] is False
    print(f"  [7] eval vietato -> ok={ris7['ok']}, motivi={ris7['motivi'][:1]}")

    # --- [8] Skill 'conta parole' (esempio buono da sandbox_skill) ---
    codice_conta_parole = (
        "def esegui(contesto: dict) -> dict:\n"
        '    """Conta le parole in un testo."""\n'
        "    try:\n"
        "        testo = str(contesto.get('testo', ''))\n"
        "        parole = len(testo.split()) if testo.strip() else 0\n"
        "        return {'esito': 'ok', 'parole': parole, 'caratteri': len(testo)}\n"
        "    except Exception as e:\n"
        "        return {'esito': 'errore', 'dettaglio': str(e)}\n"
    )
    ris8 = v.valida(codice_conta_parole)
    assert ris8["ok"] is True, f"Skill conta-parole deve passare: {ris8['motivi']}"
    print(f"  [8] skill conta-parole -> ok={ris8['ok']}, motivi={ris8['motivi']}")

    # --- [9] Skill con import datetime (consentito) ---
    codice_datetime = (
        "import datetime\n"
        "def esegui(contesto: dict) -> dict:\n"
        '    """Restituisce la data corrente."""\n'
        "    try:\n"
        "        oggi = datetime.date.today().isoformat()\n"
        "        return {'esito': 'ok', 'data': oggi}\n"
        "    except Exception as e:\n"
        "        return {'esito': 'errore', 'dettaglio': str(e)}\n"
    )
    ris9 = v.valida(codice_datetime)
    assert ris9["ok"] is True, f"Skill con datetime deve passare: {ris9['motivi']}"
    print(f"  [9] skill con datetime -> ok={ris9['ok']}, motivi={ris9['motivi']}")

    # --- [10] Skill con esegui nidificata (non al top level) ---
    codice_nidificato = (
        "def wrapper():\n"
        "    def esegui(contesto):\n"
        "        return {'esito': 'ok'}\n"
        "    return esegui\n"
    )
    ris10 = v.valida(codice_nidificato)
    assert ris10["ok"] is False, f"esegui nidificata deve fallire: {ris10}"
    print(f"  [10] esegui nidificata -> ok={ris10['ok']}, motivi={ris10['motivi'][:1]}")

    print("OK")
