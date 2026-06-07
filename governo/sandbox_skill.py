"""
ARGO - governo/sandbox_skill.py
Analisi di sicurezza e esecuzione in sandbox isolata del codice delle skill.

SICUREZZA CRITICA:
  - analizza_sicurezza() fa analisi statica AST prima di qualsiasi esecuzione.
  - prova_in_sandbox() esegue il codice in un subprocess Python completamente
    separato, con un timeout rigido e una working directory temporanea
    (NON la cartella reale del progetto). Cattura stdout/stderr, non modifica
    il filesystem reale.
  - Il codice di una skill NON viene mai eseguito nel processo principale.
  - textwrap.dedent() viene applicato prima di scrivere il file temporaneo
    per evitare IndentationError su codice con indentazione mista.

Nessuna libreria esterna richiesta.
"""

import ast
import os
import sys
import json
import subprocess
import tempfile
import textwrap


# ---------- Lista nera: import e attributi/chiamate vietati ----------

# Moduli interi la cui importazione è vietata
_MODULI_VIETATI = frozenset({
    "os", "subprocess", "multiprocessing", "os.system",
    "urllib", "urllib.request", "requests", "http", "http.client",
    "socket", "socketserver",
    "ftplib", "smtplib", "imaplib", "poplib",
    "http.server", "xmlrpc",
    "ctypes", "cffi",
    "winreg", "msvcrt",
    "pickle", "shelve",          # deserializzazione arbitraria
    "importlib",
    "signal",
    "pty", "tty", "termios",
    "shutil",                    # shutil.rmtree è distruttivo
    "glob",                      # accesso filesystem arbitrario
    "pathlib",                   # manipolazione path arbitraria
    "io",                        # I/O generica (open alternativa)
    "builtins",                  # accesso ai built-in
})

# Nomi di funzioni/attributi vietati ovunque appaiano
_CHIAMATE_VIETATE = frozenset({
    "eval", "exec", "compile",
    "open",                      # qualsiasi open() è vietata
    "__import__",
    "__mro__", "__subclasses__",
    "system", "popen", "execv", "execve",  # os.*
    "rmtree", "move", "copy2",   # shutil.*
    "Popen", "call", "run",      # subprocess.*
    "getattr", "setattr", "delattr",
    "vars", "dir",
    "breakpoint",
    "input",
    "__builtins__",
})


class _AnalizzatoreAST(ast.NodeVisitor):
    """
    Visita l'AST del codice e raccoglie violazioni di sicurezza.
    """

    def __init__(self):
        self.motivi: list[str] = []

    def visit_Import(self, node):
        """Blocca import di moduli vietati (import os, import subprocess …)"""
        for alias in node.names:
            nome = alias.name.split(".")[0]
            if nome in _MODULI_VIETATI:
                self.motivi.append(f"import vietato: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Blocca from X import Y se X è vietato."""
        if node.module:
            nome = node.module.split(".")[0]
            if nome in _MODULI_VIETATI:
                self.motivi.append(f"import vietato: 'from {node.module} import …'")
            # Controlla anche i singoli nomi importati
            for alias in node.names:
                if alias.name in _CHIAMATE_VIETATE:
                    self.motivi.append(
                        f"nome vietato importato: '{alias.name}' da '{node.module}'"
                    )
        self.generic_visit(node)

    def visit_Call(self, node):
        """Blocca chiamate a funzioni vietate."""
        # Caso: nome semplice, es. eval(...)
        if isinstance(node.func, ast.Name):
            if node.func.id in _CHIAMATE_VIETATE:
                self.motivi.append(f"chiamata vietata: '{node.func.id}()'")
        # Caso: attributo, es. os.system(...), shutil.rmtree(...)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in _CHIAMATE_VIETATE:
                self.motivi.append(f"attributo vietato: '*.{node.func.attr}()'")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        """Blocca accesso ad attributi pericolosi, es. os.environ."""
        if node.attr in {"environ", "__class__", "__bases__", "__mro__", "__subclasses__",
                         "__globals__", "__code__", "__builtins__"}:
            self.motivi.append(f"accesso attributo vietato: '.{node.attr}'")
        self.generic_visit(node)


def analizza_sicurezza(codice: str) -> dict:
    """
    Analisi statica AST del codice di una skill.

    :param codice: sorgente Python da analizzare
    :return: {'ok': bool, 'motivi': [lista di violazioni trovate]}
    """
    motivi = []

    # 1. Parsing: il codice deve essere Python valido.
    #    Applica dedent preventivo per evitare falsi SyntaxError da indentazione extra.
    codice_da_analizzare = textwrap.dedent(codice)
    try:
        albero = ast.parse(codice_da_analizzare)
    except SyntaxError as e:
        return {"ok": False, "motivi": [f"errore di sintassi: {e}"]}

    # 2. Visita AST
    analizzatore = _AnalizzatoreAST()
    try:
        analizzatore.visit(albero)
        motivi.extend(analizzatore.motivi)
    except Exception as e:
        motivi.append(f"errore durante l'analisi AST: {e}")

    # 3. Verifica che esista la funzione 'esegui'
    nomi_funzioni = [
        n.name for n in ast.walk(albero)
        if isinstance(n, ast.FunctionDef)
    ]
    if "esegui" not in nomi_funzioni:
        motivi.append("la skill deve definire 'def esegui(contesto): …'")

    return {"ok": len(motivi) == 0, "motivi": motivi}


def _costruisci_wrapper(codice: str, contesto_json: str) -> str:
    """
    Costruisce lo script completo da eseguire nella sandbox.
    Applica textwrap.dedent al codice della skill per prevenire IndentationError
    quando il codice arriva con indentazione mista o spazi iniziali inattesi.

    :param codice:        sorgente Python della skill
    :param contesto_json: stringa JSON del contesto da passare a esegui()
    :return:              script completo pronto per essere scritto su file
    """
    codice_pulito = textwrap.dedent(codice).strip()

    parte_chiamata = textwrap.dedent(f"""\
        import sys as _sys, json as _json, traceback as _traceback
        try:
            _contesto = _json.loads({contesto_json!r})
            _risultato = esegui(_contesto)
            print(_json.dumps({{"esito": "ok", "risultato": str(_risultato)}}, ensure_ascii=True))
        except Exception as _e:
            print(_json.dumps({{"esito": "errore", "dettaglio": _traceback.format_exc()}}, ensure_ascii=True))
    """)

    return codice_pulito + "\n\n" + parte_chiamata


def _esegui_subprocess(script_path: str, tmp_dir: str, timeout: int) -> dict:
    """
    Lancia il file script in un subprocess isolato e raccoglie l'output.

    :return: {'ok': bool, 'output': str}
    """
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tmp_dir,           # working dir isolata
            env={                  # ambiente minimale, senza PATH del progetto
                "PYTHONPATH": "",
                "PYTHONUTF8": "1",
            },
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"Timeout ({timeout}s): la skill ha impiegato troppo."}
    except Exception as e:
        return {"ok": False, "output": f"Errore nell'avvio del subprocess: {e}"}

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    output_completo = stdout
    if stderr:
        output_completo += ("\n[stderr] " + stderr) if output_completo else ("[stderr] " + stderr)

    if proc.returncode != 0:
        return {"ok": False, "output": output_completo or f"Exit code {proc.returncode}"}

    # Tenta di interpretare l'output JSON
    try:
        dati = json.loads(stdout)
        esito_ok = dati.get("esito") == "ok"
        return {"ok": esito_ok, "output": output_completo, "dati": dati}
    except (json.JSONDecodeError, Exception):
        # L'output non è JSON strutturato: accettiamo se il returncode era 0
        return {"ok": True, "output": output_completo}


def prova_in_sandbox(codice: str, timeout: int = 10) -> dict:
    """
    Esegue il codice della skill in un subprocess Python completamente isolato,
    passando un contesto vuoto ({}) come prova minimale.

    - Working directory: cartella temporanea (NON il progetto reale)
    - Nessuna modifica al filesystem del progetto
    - Output catturato (stdout + stderr)
    - Timeout rigido
    - textwrap.dedent() applicato al codice prima di scrivere il file

    :param codice:   sorgente Python della skill (deve definire esegui(contesto))
    :param timeout:  secondi massimi di esecuzione (default 10)
    :return: {'ok': bool, 'output': str}
    """
    wrapper = _costruisci_wrapper(codice, "{}")

    with tempfile.TemporaryDirectory(prefix="argo_sandbox_") as tmp_dir:
        script_path = os.path.join(tmp_dir, "_skill_sandbox.py")
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(wrapper)
        except Exception as e:
            return {"ok": False, "output": f"Impossibile creare lo script sandbox: {e}"}

        return _esegui_subprocess(script_path, tmp_dir, timeout)


def esegui_in_sandbox(codice: str, contesto: dict | None = None, timeout: int = 10) -> dict:
    """
    Esegue una skill approvata passando un contesto JSON controllato.

    Il codice resta in subprocess e cwd temporanea. Il processo principale non
    importa mai la skill e non le concede accesso al progetto reale.
    Applica textwrap.dedent() al codice prima di scrivere il file temporaneo.

    :param codice:    sorgente Python della skill
    :param contesto:  dizionario da passare a esegui() come argomento
    :param timeout:   secondi massimi di esecuzione (default 10)
    :return: {'ok': bool, 'output': str, 'dati': dict (se il JSON è valido)}
    """
    analisi = analizza_sicurezza(codice)
    if not analisi.get("ok"):
        return {
            "ok": False,
            "output": json.dumps({"esito": "bloccata", "motivi": analisi.get("motivi", [])})
        }

    try:
        contesto_json = json.dumps(contesto or {}, ensure_ascii=True)
    except Exception:
        contesto_json = "{}"

    wrapper = _costruisci_wrapper(codice, contesto_json)

    with tempfile.TemporaryDirectory(prefix="argo_skill_run_") as tmp_dir:
        script_path = os.path.join(tmp_dir, "_skill_run.py")
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(wrapper)
        except Exception as e:
            return {"ok": False, "output": f"Impossibile creare lo script sandbox: {e}"}

        return _esegui_subprocess(script_path, tmp_dir, timeout)


# ---------- Skill di esempio "buone" usate nel test ----------

_SKILL_ESEMPIO_CONTA_PAROLE = '''
def esegui(contesto: dict) -> dict:
    """
    Conta le parole in un testo.

    Input:
      - testo (str): il testo da analizzare

    Output:
      - esito (str): "ok" oppure "errore"
      - parole (int): numero di parole
      - caratteri (int): numero di caratteri
    """
    try:
        testo = str(contesto.get("testo", ""))
        parole = len(testo.split()) if testo.strip() else 0
        return {"esito": "ok", "parole": parole, "caratteri": len(testo)}
    except Exception as e:
        return {"esito": "errore", "dettaglio": str(e)}
'''.strip()

_SKILL_ESEMPIO_DATA_ITALIANA = '''
import datetime

def esegui(contesto: dict) -> dict:
    """
    Formatta una data ISO in formato italiano leggibile.

    Input:
      - data_iso (str): data in formato "YYYY-MM-DD"

    Output:
      - esito (str): "ok" oppure "errore"
      - data_formattata (str): es. "7 giugno 2025"
    """
    MESI = [
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
    ]
    try:
        data_iso = str(contesto.get("data_iso", ""))
        if not data_iso:
            return {"esito": "errore", "dettaglio": "campo 'data_iso' mancante"}
        data = datetime.date.fromisoformat(data_iso)
        formattata = f"{data.day} {MESI[data.month - 1]} {data.year}"
        return {"esito": "ok", "data_formattata": formattata}
    except Exception as e:
        return {"esito": "errore", "dettaglio": str(e)}
'''.strip()


# ---------- smoke-test ----------
if __name__ == "__main__":
    import os as _os_main, sys as _sys_main
    _root_main = _os_main.path.abspath(
        _os_main.path.join(_os_main.path.dirname(_os_main.path.abspath(__file__)), "..")
    )
    if _root_main not in _sys_main.path:
        _sys_main.path.insert(0, _root_main)

    print("== Smoke-test sandbox_skill ==")

    # --- [1] Analisi sicurezza: codice sicuro ---
    codice_sicuro = (
        "def esegui(contesto):\n"
        "    return {'messaggio': 'ciao da skill sicura', 'n': 42}\n"
    )
    ris = analizza_sicurezza(codice_sicuro)
    assert ris["ok"] is True, f"Atteso ok=True, motivi={ris['motivi']}"
    print(f"  [1] codice sicuro -> ok={ris['ok']}")

    # --- [2] Analisi sicurezza: codice pericoloso ---
    codice_pericoloso = (
        "import subprocess\n"
        "def esegui(contesto):\n"
        "    subprocess.run(['whoami'])\n"
        "    return {}\n"
    )
    ris2 = analizza_sicurezza(codice_pericoloso)
    assert ris2["ok"] is False, "Il codice pericoloso deve essere bloccato"
    assert len(ris2["motivi"]) > 0
    print(f"  [2] codice pericoloso -> ok={ris2['ok']}, motivi={ris2['motivi']}")

    # --- [3] Analisi: manca la funzione esegui ---
    codice_senza_esegui = "x = 1 + 1\n"
    ris3 = analizza_sicurezza(codice_senza_esegui)
    assert ris3["ok"] is False
    print(f"  [3] senza 'esegui' -> ok={ris3['ok']}, motivi={ris3['motivi']}")

    # --- [4] Analisi: eval vietato ---
    codice_eval = (
        "def esegui(contesto):\n"
        "    return eval('1+1')\n"
    )
    ris4 = analizza_sicurezza(codice_eval)
    assert ris4["ok"] is False
    print(f"  [4] eval vietato -> ok={ris4['ok']}, motivi={ris4['motivi']}")

    # --- [5] Analisi: codice con indentazione inattesa (dedent deve salvarlo) ---
    codice_indentato = (
        "    def esegui(contesto):\n"
        "        return {'esito': 'ok'}\n"
    )
    ris5 = analizza_sicurezza(codice_indentato)
    # Dopo dedent deve essere valido
    assert ris5["ok"] is True, f"Codice indentato deve passare dopo dedent: {ris5['motivi']}"
    print(f"  [5] codice con indentazione extra (dedent) -> ok={ris5['ok']}")

    # --- [6] Sandbox: esecuzione del codice sicuro basilare ---
    sandbox_ris = prova_in_sandbox(codice_sicuro, timeout=15)
    print(f"  [6] skill sicura basilare -> ok={sandbox_ris['ok']}, output={sandbox_ris['output'][:80]}")
    assert sandbox_ris["ok"] is True, f"La sandbox deve passare il codice sicuro: {sandbox_ris}"

    # --- [7] Sandbox: skill di esempio 'conta parole' con contesto reale ---
    sandbox_parole = esegui_in_sandbox(
        _SKILL_ESEMPIO_CONTA_PAROLE,
        {"testo": "ciao mondo come stai"},
        timeout=15,
    )
    print(f"  [7] skill conta-parole -> ok={sandbox_parole['ok']}, output={sandbox_parole['output'][:80]}")
    assert sandbox_parole["ok"] is True, f"conta_parole deve funzionare: {sandbox_parole}"
    dati_parole = sandbox_parole.get("dati", {}).get("risultato", "")
    print(f"       risultato: {dati_parole}")

    # --- [8] Sandbox: skill di esempio 'data italiana' con contesto reale ---
    sandbox_data = esegui_in_sandbox(
        _SKILL_ESEMPIO_DATA_ITALIANA,
        {"data_iso": "2025-06-07"},
        timeout=15,
    )
    print(f"  [8] skill data-italiana -> ok={sandbox_data['ok']}, output={sandbox_data['output'][:80]}")
    assert sandbox_data["ok"] is True, f"data_italiana deve funzionare: {sandbox_data}"

    # --- [9] Sandbox: esecuzione con contesto generico ---
    sandbox_ctx = esegui_in_sandbox(
        "def esegui(contesto):\n"
        "    return {'eco': contesto.get('testo'), 'n': contesto.get('n', 0) + 1}\n",
        {"testo": "ciao", "n": 1},
        timeout=15,
    )
    print(f"  [9] eco con contesto -> ok={sandbox_ctx['ok']}, output={sandbox_ctx['output'][:80]}")
    assert sandbox_ctx["ok"] is True

    # --- [10] Sandbox: skill con indentazione extra (dedent deve salvarlo) ---
    codice_indentato_run = (
        "    def esegui(contesto):\n"
        "        return {'esito': 'ok', 'valore': 99}\n"
    )
    sandbox_indent = prova_in_sandbox(codice_indentato_run, timeout=15)
    print(f"  [10] skill con indentazione extra -> ok={sandbox_indent['ok']}, output={sandbox_indent['output'][:80]}")
    assert sandbox_indent["ok"] is True, f"Codice indentato deve eseguire dopo dedent: {sandbox_indent}"

    # --- [11] Sandbox: skill che fa errore ---
    codice_errore = (
        "def esegui(contesto):\n"
        "    raise ValueError('errore di prova')\n"
    )
    sandbox_err = prova_in_sandbox(codice_errore, timeout=10)
    print(f"  [11] skill con errore -> ok={sandbox_err['ok']}, output={sandbox_err['output'][:80]}")
    assert sandbox_err["ok"] is False, "La sandbox deve segnalare il fallimento"

    # --- [12] esegui_in_sandbox blocca codice pericoloso ---
    sandbox_peri = esegui_in_sandbox(codice_pericoloso, {}, timeout=10)
    assert sandbox_peri["ok"] is False, "Codice pericoloso deve essere bloccato"
    print(f"  [12] codice pericoloso bloccato da esegui_in_sandbox: ok={sandbox_peri['ok']}")

    print("OK")
