"""
ARGO - fai_sonno_ora.py
Forza il "sonno" di ARGO ADESSO, senza aspettare le 20:00, e ti mostra le skill
proposte (i "figli esperti") con l'id per approvarle/attivarle.

ARGO deve essere gia' avviato (la sua finestra aperta).
Uso:  python fai_sonno_ora.py
Solo libreria standard.
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8773"


def _post(path, dati=None):
    corpo = json.dumps(dati or {}).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=corpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    print("== Faccio fare il SONNO ad ARGO adesso ==\n")
    try:
        _get("/stato")
    except Exception:
        print("ARGO non risponde su 127.0.0.1:8773. Apri prima l'app ARGO e riprova.")
        return

    print("Avvio il ciclo di sonno (puo' richiedere 1-2 minuti)...\n")
    try:
        r = _post("/sonno")
    except Exception as e:
        print("Errore nel chiamare /sonno:", e)
        return

    rep = r.get("report") or r
    print("--- ESITO SONNO ---")
    print(json.dumps(rep, indent=2, ensure_ascii=False)[:2000])

    # Mostra le skill proposte (figli esperti in attesa di approvazione)
    try:
        sk = _get("/skills")
        skills = sk.get("skills", sk)
        print("\n--- SKILL NEL REGISTRO ---")
        if not skills:
            print("Nessuna skill proposta in questo ciclo.")
        else:
            for s in skills:
                sid = s.get("id", "?")
                nome = s.get("nome", "?")
                stato = s.get("stato", "?")
                print(f"  [id={sid}] {nome}  (stato: {stato})")
            print("\nPer ATTIVARE una skill (farla diventare un 'figlio esperto'):")
            print("  -> nella Console premi Attiva, oppure:")
            print("     python -c \"import urllib.request,json;"
                  "urllib.request.urlopen(urllib.request.Request("
                  "'http://127.0.0.1:8773/skill/attiva',"
                  "data=json.dumps({'id':ID}).encode(),"
                  "headers={'Content-Type':'application/json'}))\"")
    except Exception as e:
        print("Non sono riuscito a leggere /skills:", e)

    print("\nOK")


if __name__ == "__main__":
    main()
