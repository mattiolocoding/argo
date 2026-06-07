"""
ARGO - argo_app.py  (APPLICAZIONE DESKTOP NATIVA, con Qt)
Una vera finestra desktop (non un browser): barra del titolo "ARGO", icona ARGO
nella taskbar, l'interfaccia moderna dentro. Tecnologia: Qt (PySide6 + QWebEngine).

Al primo avvio installa da solo il componente (PySide6) mostrando una piccola
finestra di avanzamento. Niente terminale, niente Edge, niente scheda browser.

AVVIO:  doppio click su avvia_argo.bat  (oppure  python argo_app.py)
"""

import os
import sys
import time
import threading
import subprocess

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(_DIR, "assets", "logo.svg")


# ---------------------------------------------------------------
# Primo avvio: assicura PySide6 (con piccola finestra di avanzamento Tk)
# ---------------------------------------------------------------
def _ha_pyside():
    try:
        import PySide6  # noqa
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa
        return True
    except Exception:
        return False


def assicura_pyside():
    if _ha_pyside():
        return True

    import tkinter as tk
    root = tk.Tk()
    root.title("ARGO — primo avvio")
    root.geometry("420x150+200+200")
    root.configure(bg="#0b0f1a")
    tk.Label(root, text="ARGO", fg="#8b5cf6", bg="#0b0f1a",
             font=("Segoe UI", 16, "bold")).pack(pady=(18, 4))
    msg = tk.Label(root, text="Installo i componenti dell'app (1-2 minuti)…",
                   fg="#c9d1d9", bg="#0b0f1a", font=("Segoe UI", 10))
    msg.pack(pady=6)
    sub = tk.Label(root, text="Solo la prima volta.", fg="#7d8597", bg="#0b0f1a",
                   font=("Segoe UI", 9))
    sub.pack()

    esito = {"ok": False, "fine": False}

    def lavoro():
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"],
                           check=False)
            esito["ok"] = _ha_pyside()
        except Exception:
            esito["ok"] = False
        esito["fine"] = True

    threading.Thread(target=lavoro, daemon=True).start()

    def controlla():
        if esito["fine"]:
            root.destroy()
        else:
            root.after(400, controlla)
    root.after(400, controlla)
    root.mainloop()

    if not esito["ok"]:
        # messaggio chiaro se l'installazione non riesce
        try:
            import tkinter as tk
            r = tk.Tk(); r.title("ARGO")
            r.geometry("460x160+200+200"); r.configure(bg="#0b0f1a")
            tk.Label(r, text="Non sono riuscito a installare i componenti.",
                     fg="#f87171", bg="#0b0f1a", font=("Segoe UI", 11, "bold")).pack(pady=(20, 6))
            tk.Label(r, text="Apri il Prompt dei comandi e scrivi:\n\npip install PySide6\n\npoi riavvia ARGO.",
                     fg="#c9d1d9", bg="#0b0f1a", font=("Segoe UI", 10), justify="center").pack()
            r.mainloop()
        except Exception:
            pass
    return esito["ok"]


# ---------------------------------------------------------------
# Avvio app
# ---------------------------------------------------------------
def main():
    # motore + server in background (riusa motore_web)
    from motore_web import Motore, crea_handler, HOST, PORT
    from http.server import ThreadingHTTPServer

    motore = Motore()
    server = ThreadingHTTPServer((HOST, PORT), crea_handler(motore))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://{HOST}:{PORT}"

    if not assicura_pyside():
        return

    from PySide6.QtWidgets import QApplication, QMainWindow
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtGui import QIcon, QPixmap, QPainter
    from PySide6.QtCore import QUrl, Qt

    # identità app (icona corretta in taskbar su Windows)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Argo.Custode.1")
    except Exception:
        pass

    def fai_icona():
        """Disegna il logo SVG su un'immagine: icona affidabile a varie misure."""
        try:
            from PySide6.QtSvg import QSvgRenderer
            r = QSvgRenderer(LOGO)
            ico = QIcon()
            for s in (16, 32, 48, 64, 128, 256):
                pm = QPixmap(s, s)
                pm.fill(Qt.transparent)
                p = QPainter(pm)
                r.render(p)
                p.end()
                ico.addPixmap(pm)
            return ico
        except Exception:
            return QIcon(LOGO)

    app = QApplication(sys.argv)
    app.setApplicationName("ARGO")
    icona = fai_icona()
    app.setWindowIcon(icona)

    win = QMainWindow()
    win.setWindowTitle("ARGO")
    win.setWindowIcon(icona)
    win.resize(560, 840)

    view = QWebEngineView()
    time.sleep(0.4)               # dà tempo al server di partire
    view.load(QUrl(url))
    win.setCentralWidget(view)
    win.show()

    app.exec()
    motore.running = False


if __name__ == "__main__":
    main()
