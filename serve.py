"""
ARGO — avvio headless del motore (per container / server, senza finestra).

A differenza di `motore_web.py` eseguito come script, qui NON si apre nessuna
finestra: si avvia solo il server HTTP. La UI resta raggiungibile via browser
all'indirizzo del motore. Host/porta/identità si configurano da ambiente
(ARGO_HOST, ARGO_PORT, ARGO_ISTANZA_ID, ARGO_ISTANZA_NOME, OLLAMA_HOST).

Uso:
    python serve.py
"""

import os
from http.server import ThreadingHTTPServer

import motore_web as M


def main():
    motore = M.Motore()
    server = ThreadingHTTPServer((M.HOST, M.PORT), M.crea_handler(motore))
    print(
        f"[ARGO] motore headless su http://{M.HOST}:{M.PORT}"
        f"  (istanza {M.ISTANZA_ID}, ollama {os.environ.get('OLLAMA_HOST', 'default')})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        motore.running = False
        print("[ARGO] spento.", flush=True)


if __name__ == "__main__":
    main()
