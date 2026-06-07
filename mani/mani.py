"""
ARGO - mani/mani.py
Le MANI di Argo: agisce sui file in modo SICURO.

Filosofia:
  - Ogni azione e' prima un PIANO proponibile (anteprima), poi eseguito.
  - GUARDRAIL: solo dentro le radici consentite, MAI cartelle di sistema,
    MAI elimina, MAI sovrascrive.
  - Regole d'ordine: per TIPO, per DATA (anno-mese) o per PROGETTO (prefisso nome).
  - Sa riconoscere i DUPLICATI (per contenuto) e proporne lo spostamento.

Nessuna libreria da installare: os, shutil, hashlib (standard).
"""

import os
import shutil
import hashlib
import datetime

CATEGORIE = {
    "Immagini":  {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg", ".heic"},
    "Documenti": {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".md",
                  ".xls", ".xlsx", ".ppt", ".pptx", ".csv"},
    "Video":     {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"},
    "Audio":     {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Archivi":   {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Codice":    {".py", ".js", ".ts", ".java", ".c", ".cpp", ".html",
                  ".css", ".json", ".sh", ".bat", ".ps1"},
}

# cartelle generate da Argo: non vanno trattate come file da ordinare
CARTELLE_DI_ARGO = set(CATEGORIE.keys()) | {"Altro", "Duplicati"}


def categoria_di(nomefile):
    ext = os.path.splitext(nomefile)[1].lower()
    for cat, exts in CATEGORIE.items():
        if ext in exts:
            return cat
    return "Altro"


def _sottocartella(file_path, regola):
    """Nome della sottocartella di destinazione secondo la regola scelta."""
    nome = os.path.basename(file_path)
    if regola == "data":
        try:
            ts = os.path.getmtime(file_path)
            return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m")
        except Exception:
            return "Senza-data"
    if regola == "progetto":
        base = os.path.splitext(nome)[0]
        for sep in (" ", "_", "-"):
            if sep in base:
                base = base.split(sep)[0]
                break
        return base.strip().capitalize() or "Vari"
    # default: tipo
    return categoria_di(nome)


class Mani:
    def __init__(self, radici, cartelle_protette=None):
        self.radici = [os.path.abspath(r) for r in radici]
        self.protette = [p.lower() for p in (cartelle_protette or [])]

    # ---------- guardrail ----------
    def _dentro_radici(self, percorso):
        p = os.path.abspath(percorso)
        return any(p == r or p.startswith(r + os.sep) for r in self.radici)

    def _protetto(self, percorso):
        segmenti = os.path.abspath(percorso).lower().split(os.sep)
        return any(seg in self.protette for seg in segmenti)

    def _sicuro(self, percorso):
        return self._dentro_radici(percorso) and not self._protetto(percorso)

    # ---------- proposte (anteprima) ----------
    def proponi_archiviazione(self, file_path, regola="tipo"):
        if not os.path.isfile(file_path) or not self._sicuro(file_path):
            return None
        cartella = os.path.dirname(file_path)
        nome = os.path.basename(file_path)
        sub = _sottocartella(file_path, regola)
        dest = os.path.join(cartella, sub, nome)
        if os.path.abspath(dest) == os.path.abspath(file_path):
            return None
        return {
            "azione": "archivia",
            "sorgente": file_path,
            "destinazione": dest,
            "descrizione": f"Sposterei «{nome}» nella cartella «{sub}».",
        }

    def proponi_sposta_duplicato(self, file_path):
        if not os.path.isfile(file_path) or not self._sicuro(file_path):
            return None
        cartella = os.path.dirname(file_path)
        nome = os.path.basename(file_path)
        dest = os.path.join(cartella, "Duplicati", nome)
        return {
            "azione": "sposta",
            "sorgente": file_path,
            "destinazione": dest,
            "descrizione": f"«{nome}» sembra un doppione: lo metterei in «Duplicati».",
        }

    def proponi_rinomina(self, file_path, nuovo_nome):
        if not os.path.isfile(file_path) or not self._sicuro(file_path):
            return None
        nuovo_nome = os.path.basename(nuovo_nome)
        dest = os.path.join(os.path.dirname(file_path), nuovo_nome)
        return {
            "azione": "rinomina",
            "sorgente": file_path,
            "destinazione": dest,
            "descrizione": f"Rinominerei «{os.path.basename(file_path)}» in «{nuovo_nome}».",
        }

    def proponi_crea_cartella(self, cartella_base, nome):
        dest = os.path.join(cartella_base, os.path.basename(nome))
        if not self._sicuro(dest):
            return None
        return {
            "azione": "crea_cartella",
            "destinazione": dest,
            "descrizione": f"Creerei la cartella «{os.path.basename(nome)}».",
        }

    # ---------- duplicati ----------
    def _hash(self, percorso):
        try:
            h = hashlib.sha256()
            with open(percorso, "rb") as f:
                for blocco in iter(lambda: f.read(65536), b""):
                    h.update(blocco)
            return h.hexdigest()
        except Exception:
            return None

    def trova_duplicati(self, cartella):
        """Doppioni per contenuto tra i file in cima alla cartella.
        Ritorna lista di percorsi che sono copie di un file gia' visto."""
        visti = {}
        dups = []
        try:
            nomi = sorted(os.listdir(cartella))
        except Exception:
            return dups
        for nome in nomi:
            p = os.path.join(cartella, nome)
            if not os.path.isfile(p):
                continue
            h = self._hash(p)
            if h is None:
                continue
            if h in visti:
                dups.append(p)
            else:
                visti[h] = p
        return dups

    # ---------- esecuzione (ricontrolla SEMPRE la sicurezza) ----------
    def esegui(self, piano):
        if not piano or "azione" not in piano:
            return {"ok": False, "messaggio": "piano vuoto"}
        az = piano["azione"]
        try:
            if az in ("archivia", "sposta", "rinomina"):
                return self._sposta(piano["sorgente"], piano["destinazione"],
                                    piano.get("descrizione", "fatto"))
            if az == "crea_cartella":
                dst = piano["destinazione"]
                if not self._sicuro(dst):
                    return {"ok": False, "messaggio": "percorso non sicuro, annullo"}
                os.makedirs(dst, exist_ok=True)
                return {"ok": True, "messaggio": piano.get("descrizione", "cartella creata")}
            return {"ok": False, "messaggio": f"azione sconosciuta: {az}"}
        except Exception as e:
            return {"ok": False, "messaggio": f"errore: {e}"}

    def _sposta(self, src, dst, messaggio_ok):
        if not (self._sicuro(src) and self._sicuro(dst)):
            return {"ok": False, "messaggio": "percorso non sicuro, annullo"}
        if not os.path.exists(src):
            return {"ok": False, "messaggio": "il file non esiste piu'"}
        if os.path.exists(dst):
            return {"ok": False, "messaggio": "esiste gia' un file con quel nome, non sovrascrivo"}
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return {"ok": True, "messaggio": messaggio_ok}


if __name__ == "__main__":
    m = Mani(radici=["."], cartelle_protette=["Windows", "System32"])
    print("categoria foto.png ->", categoria_di("foto.png"))
    print("sottocartella progetto 'Tesi_cap1.docx' ->", _sottocartella("Tesi_cap1.docx", "progetto"))
    print("sicuro './x.txt'?", m._sicuro("./x.txt"))
    print("sicuro 'C:/Windows/x'?", m._sicuro("C:/Windows/x"))
