"""
ARGO - governo/consolidamento.py  (il "SONNO" della memoria)
La differenza tra un log e un'intelligenza persistente: ogni giorno ARGO rilegge
ciò che ha fatto, lo RIASSUME, lo collega nel grafo e aggiorna il profilo.

Deterministico (conta i fatti reali) + opzionale frase del cervello, SEMPRE
fondata sui dati reali (niente invenzioni). Solo libreria standard.
"""

import datetime


def gia_fatto_oggi(memoria):
    oggi = datetime.date.today().isoformat()
    return memoria.leggi_profilo("ultimo_consolidamento", "").startswith(oggi)


def consolida(memoria, grafo=None, cervello=None, forza=False):
    """Esegue il consolidamento della giornata. Ritorna il testo del riassunto."""
    oggi = datetime.date.today().isoformat()
    if not forza and gia_fatto_oggi(memoria):
        return None

    # raccogli i fatti reali di oggi
    conteggi = {}
    categorie = {}
    for r in memoria.ricordi_recenti(500):
        if not str(r.get("quando", "")).startswith(oggi):
            continue
        conteggi[r["tipo"]] = conteggi.get(r["tipo"], 0) + 1

    azioni = conteggi.get("azione", 0) + conteggi.get("azione_confermata", 0)
    visti = conteggi.get("file_aggiunto", 0)
    rifiuti = conteggi.get("azione_rifiutata", 0)

    riassunto = (f"Consolidamento {oggi}: visti {visti} file, "
                 f"{azioni} azioni eseguite, {rifiuti} rifiutate.")

    # frase naturale opzionale, fondata sui numeri reali
    if cervello is not None:
        try:
            if cervello.vivo():
                frase = cervello.pensa(
                    "Riassumi la mia giornata in UNA frase, solo con questi numeri "
                    f"reali (non inventare): file visti {visti}, azioni {azioni}, "
                    f"rifiutate {rifiuti}.")
                if frase and not frase.startswith("["):
                    riassunto = frase
        except Exception:
            pass

    memoria.ricorda("consolidamento", riassunto)
    memoria.salva_profilo("ultimo_consolidamento", datetime.datetime.now().isoformat(timespec="seconds"))
    return riassunto
