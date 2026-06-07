"""
ARGO - produzione/build/fai_icona.py
Converte assets/logo.svg in assets/logo.ico e assets/logo.png.

Dipendenze (opzionali ma consigliate):
    pip install pillow cairosvg

Se cairosvg non e' installato, il fallback usa la libreria Qt (PySide6)
per renderizzare l'SVG.  Se nemmeno PySide6 e' disponibile, le istruzioni
vengono stampate senza che lo script vada in crash.

UTILIZZO:
    python produzione\\build\\fai_icona.py

Genera (o sovrascrive):
    assets/logo.png   (256 x 256 pixel)
    assets/logo.ico   (multi-risoluzione: 16, 32, 48, 64, 128, 256)
"""

import os
import sys

# Percorsi relativi a questo script (produzione/build/ -> radice Argo)
_QUI  = os.path.dirname(os.path.abspath(__file__))
_ARGO = os.path.abspath(os.path.join(_QUI, "..", ".."))

SVG_SRC  = os.path.join(_ARGO, "assets", "logo.svg")
PNG_DEST = os.path.join(_ARGO, "assets", "logo.png")
ICO_DEST = os.path.join(_ARGO, "assets", "logo.ico")

# Risoluzioni da includere nell'ICO (le big tech usano almeno queste)
ICO_SIZES = [16, 32, 48, 64, 128, 256]


# ---------------------------------------------------------------------------
# Funzioni di conversione
# ---------------------------------------------------------------------------

def svg_to_png_cairosvg(svg_path: str, png_path: str, size: int = 256) -> bool:
    """Usa cairosvg per convertire SVG -> PNG. Ritorna True se riesce."""
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path,
                         output_width=size, output_height=size)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[fai_icona] cairosvg errore: {e}")
        return False


def svg_to_png_qt(svg_path: str, png_path: str, size: int = 256) -> bool:
    """Usa PySide6 (QSvgRenderer) per convertire SVG -> PNG. Ritorna True se riesce."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QImage, QPainter, QColor
        from PySide6.QtCore import Qt

        app = QApplication.instance() or QApplication(sys.argv)
        renderer = QSvgRenderer(svg_path)
        if not renderer.isValid():
            print("[fai_icona] QSvgRenderer: SVG non valido.")
            return False
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        ok = img.save(png_path, "PNG")
        return ok
    except ImportError:
        return False
    except Exception as e:
        print(f"[fai_icona] Qt errore: {e}")
        return False


def png_to_ico(png_path: str, ico_path: str, sizes: list) -> bool:
    """Usa Pillow per creare un ICO multi-risoluzione. Ritorna True se riesce."""
    try:
        from PIL import Image
        base = Image.open(png_path).convert("RGBA")
        frames = []
        for s in sizes:
            frames.append(base.resize((s, s), Image.LANCZOS))
        # Il primo frame e' la dimensione principale
        frames[0].save(
            ico_path,
            format="ICO",
            sizes=[(s, s) for s in sizes],
            append_images=frames[1:],
        )
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[fai_icona] Pillow ICO errore: {e}")
        return False


def svg_to_png_con_fallback(svg_path: str, png_path: str, size: int = 256) -> bool:
    """Prova cairosvg, poi Qt. Ritorna True se uno dei due riesce."""
    if svg_to_png_cairosvg(svg_path, png_path, size):
        print(f"[fai_icona] PNG generato con cairosvg -> {png_path}")
        return True
    if svg_to_png_qt(svg_path, png_path, size):
        print(f"[fai_icona] PNG generato con PySide6/Qt -> {png_path}")
        return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== fai_icona.py — conversione logo ARGO ===")
    print(f"Sorgente SVG : {SVG_SRC}")
    print(f"Destinazione : {PNG_DEST}")
    print(f"             : {ICO_DEST}")

    # Controlla che il file SVG esista
    if not os.path.isfile(SVG_SRC):
        print(f"\n[ERRORE] Logo SVG non trovato: {SVG_SRC}")
        print("Metti il file logo.svg nella cartella assets/ e riprova.")
        sys.exit(1)

    # Assicura che la cartella assets/ esista
    os.makedirs(os.path.dirname(PNG_DEST), exist_ok=True)

    # --- Passo 1: SVG -> PNG ---
    print("\n--- Passo 1: SVG -> PNG (256x256) ---")
    ok_png = svg_to_png_con_fallback(SVG_SRC, PNG_DEST, size=256)

    if not ok_png:
        print("\n[ATTENZIONE] Non sono riuscito a convertire l'SVG in PNG.")
        print("Installa almeno uno dei seguenti e riprova:\n")
        print("    pip install cairosvg pillow")
        print("oppure:")
        print("    pip install PySide6 pillow\n")
        print("In alternativa puoi creare manualmente assets/logo.png")
        print("(256x256 pixel, sfondo trasparente) e rieseguire lo script.")
        sys.exit(2)

    # --- Passo 2: PNG -> ICO ---
    print(f"\n--- Passo 2: PNG -> ICO (risoluzioni: {ICO_SIZES}) ---")
    ok_ico = png_to_ico(PNG_DEST, ICO_DEST, ICO_SIZES)

    if not ok_ico:
        print("\n[ATTENZIONE] Non sono riuscito a creare l'ICO.")
        print("Installa Pillow e riprova:\n")
        print("    pip install pillow\n")
        print("Il PNG e' stato creato correttamente.")
        print("Puoi convertirlo manualmente in ICO con qualsiasi tool grafico.")
        sys.exit(3)

    print(f"[fai_icona] ICO multi-risoluzione creato -> {ICO_DEST}")
    print("\n=== Fatto! Puoi ora eseguire PyInstaller. ===")


if __name__ == "__main__":
    main()
