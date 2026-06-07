#!/usr/bin/env bash
# ARGO — installer one-command (Linux / macOS), motore headless.
#
#   curl -fsSL https://raw.githubusercontent.com/mattiolocoding/argo/main/install.sh | bash
#
# Su Linux/mac la UI nativa Qt non e' il percorso principale: questo script
# prepara il MOTORE headless (UI via browser). Per l'app desktop usa Windows,
# oppure usa Docker (vedi README). Idempotente: rilanciarlo aggiorna.

set -euo pipefail
REPO="https://github.com/mattiolocoding/argo.git"
DEST="${ARGO_HOME:-$HOME/argo}"

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }

step "ARGO installer (engine)"

command -v git >/dev/null 2>&1 || { echo "git richiesto"; exit 1; }
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Python 3.11+ richiesto"; exit 1; }

if [ -d "$DEST/.git" ]; then
  step "Aggiorno ARGO in $DEST"; git -C "$DEST" pull --ff-only
else
  step "Clono ARGO in $DEST"; git clone --depth 1 "$REPO" "$DEST"
fi
cd "$DEST"

step "Creo l'ambiente Python (.venv)"
[ -x ".venv/bin/python" ] || "$PY" -m venv .venv
./.venv/bin/python -m pip install --quiet --upgrade pip

if command -v ollama >/dev/null 2>&1; then
  step "Ollama trovato: scarico i modelli (se mancano)"
  ollama pull qwen2.5:7b-instruct || true
  ollama pull nomic-embed-text || true
else
  echo "!  Ollama non trovato: installalo da https://ollama.com (oppure usa lo stack Docker con Ollama)."
fi

step "Creo il comando 'argo'"
BIN="$HOME/.local/bin"; mkdir -p "$BIN"
cat > "$BIN/argo" <<EOF
#!/usr/bin/env bash
exec "$DEST/.venv/bin/python" "$DEST/cli.py" "\$@"
EOF
chmod +x "$BIN/argo"
echo "   creato $BIN/argo (assicurati che \$HOME/.local/bin sia nel PATH)"

step "Fatto. Avvio il motore (Ctrl-C per fermare)..."
echo "   In futuro:  argo engine  ·  argo fleet  ·  argo version"
exec "$DEST/.venv/bin/python" "$DEST/cli.py" engine
