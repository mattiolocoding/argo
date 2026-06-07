# -*- coding: utf-8 -*-
"""Controllo aggiornamenti per ARGO.

Confronta la versione corrente (importata da motore_web) con l'ultima
release pubblicata su GitHub. Tutto offline-safe: se la rete non risponde
non solleva mai eccezioni, ritorna semplicemente aggiornamento_disponibile
False e un campo 'errore' descrittivo.
"""

import json
import urllib.request

# URL dell'API GitHub per l'ultima release del progetto.
URL_RELEASE = "https://api.github.com/repos/mattiolocoding/argo/releases/latest"
# Pagina pubblica delle release (usata come 'url' di destinazione).
URL_PAGINA = "https://github.com/mattiolocoding/argo/releases/latest"


def _versione_corrente():
    """Legge la VERSIONE da motore_web in modo difensivo."""
    try:
        from motore_web import VERSIONE
        return str(VERSIONE)
    except Exception:
        # Degrada con grazia: se l'import fallisce assumiamo la versione zero.
        return "0.0.0"


def _normalizza(versione):
    """Trasforma una stringa di versione in una tupla di interi.

    Toglie un eventuale prefisso 'v' e ignora i pezzi non numerici
    (es. suffissi tipo '-beta'), così il confronto resta semplice.
    """
    testo = str(versione or "").strip()
    if testo[:1].lower() == "v":
        testo = testo[1:]
    pezzi = []
    for parte in testo.split("."):
        numero = ""
        for carattere in parte:
            if carattere.isdigit():
                numero += carattere
            else:
                break
        pezzi.append(int(numero) if numero else 0)
    # Almeno un elemento per evitare tuple vuote nel confronto.
    return tuple(pezzi) if pezzi else (0,)


def _confronta(corrente, ultima):
    """True se 'ultima' e' strettamente piu' recente di 'corrente'."""
    a = _normalizza(corrente)
    b = _normalizza(ultima)
    # Pareggia la lunghezza con zeri per un confronto tra tuple corretto.
    massimo = max(len(a), len(b))
    a = a + (0,) * (massimo - len(a))
    b = b + (0,) * (massimo - len(b))
    return b > a


def controlla(timeout=4):
    """Controlla se esiste un aggiornamento disponibile.

    Ritorna un dict con le chiavi:
        corrente                -> versione installata (str)
        ultima                  -> ultima release nota (str o None)
        aggiornamento_disponibile -> bool
        url                     -> pagina delle release (str)
    In caso di errore di rete aggiunge una chiave 'errore' e mantiene
    aggiornamento_disponibile a False. Non solleva mai.
    """
    corrente = _versione_corrente()
    risultato = {
        "corrente": corrente,
        "ultima": None,
        "aggiornamento_disponibile": False,
        "url": URL_PAGINA,
    }

    try:
        richiesta = urllib.request.Request(
            URL_RELEASE,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "ARGO-aggiornamenti",
            },
        )
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))

        tag = (dati.get("tag_name") or "").strip()
        if tag[:1].lower() == "v":
            tag = tag[1:]
        if not tag:
            risultato["errore"] = "tag_name assente nella release"
            return risultato

        risultato["ultima"] = tag
        # Se la release indica una propria pagina, preferiamola.
        pagina = dati.get("html_url")
        if pagina:
            risultato["url"] = pagina
        risultato["aggiornamento_disponibile"] = _confronta(corrente, tag)
    except Exception as e:
        # Offline-safe: nessuna eccezione esce da qui.
        risultato["errore"] = "{}: {}".format(type(e).__name__, e)

    return risultato


if __name__ == "__main__":
    esito = controlla()
    print(esito)
    print("OK aggiornamenti")
