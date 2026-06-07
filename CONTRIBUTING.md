# Contributing to ARGO

Thanks for your interest. ARGO is a local-first AI companion for Windows, and it
grows one tested step at a time. The golden rule of this project:

> **Nothing half-baked. Work in tasks. Each step works before the next one.**

## Ground rules

- **Local & private by default.** No feature may send user data off the machine.
  The API stays bound to `127.0.0.1`. No telemetry, no phone-home.
- **Safety first.** Actions on files must go through the guard-rails in `mani/` and
  the governance layer in `governo/` (policy, roles, audit, rollback). Sensitive
  files and secrets must never be read, indexed, or moved.
- **Graceful degradation.** If Ollama is off, a model is missing, or an optional
  dependency isn't installed, ARGO must keep running and say what's missing.
- **Stdlib core.** The engine (`motore_web.py`) uses the standard library only.
  New runtime dependencies need a good reason and must be optional.

## Development setup

```powershell
git clone <your-fork-url> argo
cd argo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt        # optional extras
```

Run the engine headless for testing (no window):

```powershell
python -c "import threading; from http.server import ThreadingHTTPServer; import motore_web as M; s=ThreadingHTTPServer((M.HOST,M.PORT),M.crea_handler(M.Motore())); print('up'); s.serve_forever()"
```

## Before you open a PR

1. **Everything compiles:**
   ```powershell
   python -c "import py_compile,glob;[py_compile.compile(f,doraise=True) for f in glob.glob('**/*.py',recursive=True) if '__pycache__' not in f and 'sorvegliata' not in f and '.venv' not in f];print('OK')"
   ```
2. **Module self-tests pass** — most modules run a small self-test when executed
   directly, e.g. `python memoria\memoria.py`, `python governo\policy.py`,
   `python workflow.py`, `python modelli.py`. They should end with `OK` or sensible output.
3. **Security suite is green:** `python test_sicurezza.py`.
4. Keep changes focused. One concern per PR. Match the surrounding code style.

## Frontend

The UI is a single self-contained file (`ui/index.html`). It is held to the
[impeccable](https://impeccable.style) design standard (installed under
`.claude/skills/impeccable`). Before shipping UI changes, run the anti-pattern
detector and respect contrast, motion (`prefers-reduced-motion`), and a11y rules:

```bash
node .claude/skills/impeccable/scripts/detect.mjs --json ui/index.html
```

Do not break JS selectors or `fetch` endpoints when restyling.

## Commit messages

Conventional, imperative, scoped: `fix(model-mesh): ...`, `feat(ui): ...`,
`docs(readme): ...`. Explain the *why* in the body when it isn't obvious.

## Reporting bugs & ideas

Open an issue with steps to reproduce, expected vs. actual, and your environment
(Windows version, Python version, Ollama models). For security issues, see
[SECURITY.md](SECURITY.md) — do not open a public issue.
