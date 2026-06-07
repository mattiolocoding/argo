@echo off
REM Avvia ARGO come APPLICAZIONE DESKTOP (finestra nativa), senza terminale.
cd /d "%~dp0"
start "" pythonw "%~dp0argo_app.py"
