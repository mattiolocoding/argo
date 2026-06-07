"""
ARGO — launcher a riga di comando.

Uso:
  argo                 avvia l'app desktop nativa (default)
  argo engine          avvia solo il motore headless (server / container)
  argo fleet           mostra lo stato aggregato della flotta
  argo version         stampa la versione
  argo help            questo aiuto
"""

import sys

USAGE = __doc__


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0].lower() if argv else "desktop")

    if cmd in ("version", "-v", "--version"):
        try:
            from motore_web import VERSIONE
        except Exception:
            VERSIONE = "?"
        print(f"ARGO {VERSIONE}")
        return 0

    if cmd in ("help", "-h", "--help"):
        print(USAGE)
        return 0

    if cmd in ("engine", "serve", "headless"):
        import serve
        serve.main()
        return 0

    if cmd in ("fleet", "flotta"):
        import runpy
        runpy.run_module("fleet", run_name="__main__")
        return 0

    if cmd in ("desktop", "app", "ui", "gui"):
        import argo_app
        argo_app.main()
        return 0

    print(f"Comando sconosciuto: {cmd}\n")
    print(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
