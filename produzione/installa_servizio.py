"""
ARGO - produzione/installa_servizio.py  (Fase A - far vivere il motore in background)
Registra il MOTORE perche' parta da solo e resti attivo.

Tre strade, dalla piu' robusta:
  1) NSSM (Non-Sucking Service Manager) -> VERO servizio Windows. Consigliato.
  2) Attivita' pianificata (schtasks) all'accesso -> nessun tool extra, affidabile.
  3) (manuale) pywin32 per un servizio NT puro.

Esegui:  python installa_servizio.py
"""

import os
import sys
import shutil
import subprocess

_QUI = os.path.dirname(os.path.abspath(__file__))
MOTORE = os.path.join(_QUI, "motore.py")
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
if not os.path.exists(PYW):
    PYW = sys.executable


def con_nssm():
    nssm = shutil.which("nssm")
    if not nssm:
        return False
    try:
        subprocess.run([nssm, "install", "ARGO", PYW, MOTORE], check=True)
        subprocess.run([nssm, "set", "ARGO", "Start", "SERVICE_AUTO_START"], check=True)
        subprocess.run([nssm, "start", "ARGO"], check=True)
        print("OK: servizio Windows 'ARGO' creato e avviato con NSSM.")
        return True
    except Exception as e:
        print("NSSM presente ma errore:", e)
        return False


def con_schtasks():
    """Attivita' pianificata all'accesso utente (non richiede admin)."""
    try:
        cmd = f'"{PYW}" "{MOTORE}"'
        subprocess.run([
            "schtasks", "/Create", "/TN", "ARGO_Motore", "/SC", "ONLOGON",
            "/TR", cmd, "/RL", "LIMITED", "/F"
        ], check=True)
        print("OK: attivita' pianificata 'ARGO_Motore' creata (parte ad ogni accesso).")
        print("Per avviarla subito:  schtasks /Run /TN ARGO_Motore")
        return True
    except Exception as e:
        print("schtasks errore:", e)
        return False


if __name__ == "__main__":
    print("Installo l'avvio automatico del motore di ARGO...")
    print("Motore:", MOTORE)
    if con_nssm():
        pass
    elif con_schtasks():
        pass
    else:
        print("\nNessun metodo automatico riuscito.")
        print("Soluzione robusta consigliata: installa NSSM (https://nssm.cc) e rilancia,")
        print("oppure usa il collegamento nella cartella Esecuzione automatica (avvia_argo.bat).")
