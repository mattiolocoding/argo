"""
ARGO - sistema.py  (Fase 5 - nuovi sensi: il sistema)
Argo inizia a sentire il PC oltre ai file: spazio disco e processi.
E' il primo passo verso il dominio sistema/IT (dove c'e' valore enterprise).

Solo libreria standard: shutil per il disco, subprocess per i processi.
Tutto difensivo: niente crash se qualcosa non e' disponibile.

Prova:  python sistema.py
"""

import os
import shutil
import subprocess


def disco(percorso=None):
    """Spazio del disco dove sta 'percorso'. Ritorna dict con GB e percentuale usata."""
    percorso = percorso or os.path.abspath(os.sep)
    try:
        tot, usato, libero = shutil.disk_usage(percorso)
        gb = 1024 ** 3
        return {
            "totale_gb": round(tot / gb, 1),
            "usato_gb": round(usato / gb, 1),
            "libero_gb": round(libero / gb, 1),
            "perc_usato": round(usato / tot * 100, 1) if tot else 0.0,
        }
    except Exception as e:
        return {"errore": str(e)}


def processi_top(n=5):
    """I processi che usano piu' memoria (best-effort, multipiattaforma)."""
    try:
        if os.name == "nt":
            # tasklist in formato CSV
            out = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                                 capture_output=True, text=True, timeout=10).stdout
            righe = []
            for ln in out.splitlines():
                parti = [p.strip('"') for p in ln.split('","')]
                if len(parti) >= 5:
                    nome = parti[0]
                    mem = parti[4].replace(".", "").replace(" ", " ")
                    kb = int("".join(ch for ch in mem if ch.isdigit()) or 0)
                    righe.append((nome, kb))
            righe.sort(key=lambda x: x[1], reverse=True)
            return [{"nome": nm, "mem_mb": round(kb / 1024, 1)} for nm, kb in righe[:n]]
        else:
            out = subprocess.run(["ps", "-eo", "comm,rss", "--sort=-rss"],
                                 capture_output=True, text=True, timeout=10).stdout
            righe = []
            for ln in out.splitlines()[1:]:
                parti = ln.split()
                if len(parti) >= 2:
                    righe.append({"nome": parti[0], "mem_mb": round(int(parti[1]) / 1024, 1)})
            return righe[:n]
    except Exception:
        return []


def stato_sintetico(percorso=None):
    """Una riga sullo stato del sistema, pronta da mostrare."""
    d = disco(percorso)
    if "errore" in d:
        return "Stato disco non disponibile."
    return f"Disco: {d['libero_gb']} GB liberi su {d['totale_gb']} ({d['perc_usato']}% usato)."


def diagnosi(cervello=None, percorso=None):
    """Diagnosi sintetica. Se il cervello e' vivo, aggiunge un commento."""
    d = disco(percorso)
    proc = processi_top(3)
    testo = stato_sintetico(percorso)
    allerta = ("errore" not in d) and d.get("perc_usato", 0) >= 90
    commento = None
    if cervello is not None and cervello.vivo():
        elenco = ", ".join(f"{p['nome']} ({p['mem_mb']} MB)" for p in proc) or "n/d"
        commento = cervello.pensa(
            f"Stato PC: {testo} Processi piu' pesanti: {elenco}. "
            "In una riga: va tutto bene o c'e' qualcosa da segnalare?"
        )
    return {"disco": d, "processi": proc, "allerta_disco": allerta, "commento": commento}


if __name__ == "__main__":
    print(stato_sintetico())
    print("Processi top:")
    for p in processi_top(5):
        print("  ", p["nome"], p["mem_mb"], "MB")
