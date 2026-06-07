# ARGO — immagine del MOTORE headless (API locale + UI web).
#
# Nota: questa immagine NON contiene l'app desktop nativa (Qt): in un container
# non c'è GUI. Contiene il motore headless, che serve la stessa UI via HTTP —
# la apri dal browser. Perfetta per uso dev/server e per la FLOTTA (piu'
# container = piu' istanze ARGO).
#
# Il motore usa solo la standard library: niente pip install, immagine snella.

FROM python:3.11-slim

LABEL org.opencontainers.image.title="ARGO" \
      org.opencontainers.image.description="Local-first AI engine (headless API + web UI)" \
      org.opencontainers.image.source="https://github.com/mattiolocoding/argo" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app
COPY . /app

# 0.0.0.0 per essere raggiungibile fuori dal container; Ollama sull'host.
ENV ARGO_HOST=0.0.0.0 \
    ARGO_PORT=8773 \
    ARGO_ISTANZA_NOME=ARGO-docker \
    OLLAMA_HOST=http://host.docker.internal:11434 \
    PYTHONUNBUFFERED=1

EXPOSE 8773

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('ARGO_PORT','8773')+'/stato', timeout=4)" || exit 1

CMD ["python", "serve.py"]
