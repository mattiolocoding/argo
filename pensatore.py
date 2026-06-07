"""
ARGO - pensatore.py  (IL DELIBERATORE: test-time compute per modelli piccoli)

Da' ad ARGO "pensiero analitico". Invece di rispondere di getto, sui problemi
COMPLESSI genera piu' ragionamenti diversi (best-of-N) e poi un VERIFICATORE
sceglie/sintetizza la risposta migliore, scartando errori e invenzioni.
Sui problemi SEMPLICI risponde diretto (riflettere troppo sul facile peggiora,
lo dice la ricerca 2026).

Frontiera 2026: un modello PICCOLO, se gli dai "tempo per pensare" (piu' calcolo
al momento della risposta), puo' battere modelli molto piu' grandi. Questa e' la
leva: non un cervello piu' grande, ma un cervello che pensa meglio.

Solo libreria standard. Usa il modello locale via cervello.Cervello.
Prova:  python pensatore.py
"""

import os
import sys

# parole che segnalano un compito che richiede ragionamento vero
_PAROLE_COMPLESSE = (
    "analizza", "analisi", "confronta", "perche", "perché", "spiega",
    "pianifica", "piano", "strategia", "valuta", "decidi", "progetta",
    "ottimizza", "causa", "conseguenza", "codice", "debug", "dimostra",
    "calcola", "passo", "step", "come mai", "conviene", "rischi",
)


class Pensatore:
    def __init__(self, cervello=None, n_candidati=3):
        if cervello is None:
            from cervello import Cervello
            cervello = Cervello()
        self.cervello = cervello
        self.n = max(2, int(n_candidati))

    # ---- 1) quanto e' difficile la domanda? ----
    def valuta_complessita(self, testo):
        t = (testo or "").lower().strip()
        n_parole = len(t.split())
        if any(p in t for p in _PAROLE_COMPLESSE):
            return "alta"
        if n_parole >= 40:
            return "alta"
        if n_parole <= 10:
            return "bassa"
        return "media"

    # ---- 2) genera piu' ragionamenti (best-of-N) ----
    def _genera_candidati(self, domanda, contesto):
        candidati = []
        for i in range(self.n):
            prompt = (
                (contesto + "\n\n" if contesto else "")
                + "Domanda: " + domanda + "\n\n"
                "Ragiona passo per passo, poi dai la risposta finale. "
                "Sii concreto e non inventare nulla che non sia nei dati. "
                "Regole ARGO: non proporre eliminazioni definitive; preferisci "
                "backup, conferma umana, audit e azioni reversibili."
            )
            r = self.cervello.pensa(prompt)
            if r and not r.startswith("["):
                candidati.append(r.strip())
        return candidati

    # ---- 3) il verificatore sceglie/sintetizza la migliore ----
    def _verifica_e_scegli(self, domanda, contesto, candidati):
        if not candidati:
            return None, "nessun candidato (cervello offline?)"
        if len(candidati) == 1:
            return candidati[0], "unico candidato"
        elenco = "\n\n".join(f"[Candidata {i+1}]\n{c}" for i, c in enumerate(candidati))
        prompt = (
            (contesto + "\n\n" if contesto else "")
            + "Domanda originale: " + domanda + "\n\n"
            "Qui sotto ci sono piu' risposte candidate alla stessa domanda:\n\n"
            + elenco + "\n\n"
            "Tu sei un VERIFICATORE rigoroso. Confronta le candidate, individua "
            "errori, contraddizioni o invenzioni, e produci UNA sola risposta "
            "finale: la piu' corretta e fondata, sintetizzata e pulita. "
            "Scarta qualunque candidata che suggerisca eliminazioni definitive "
            "o azioni non reversibili senza conferma. "
            "Non menzionare le candidate ne' i loro numeri. Solo la risposta finale."
        )
        finale = self.cervello.pensa(prompt)
        if not finale or finale.startswith("["):
            return candidati[0], "verifica fallita, uso la prima"
        return finale.strip(), f"verifica best-of-{len(candidati)}"

    # ---- API principale ----
    def delibera(self, domanda, contesto=""):
        compl = self.valuta_complessita(domanda)
        if compl == "bassa":
            r = self.cervello.pensa(
                (contesto + "\n\n" if contesto else "")
                + "Domanda: " + domanda
                + "\nRegole ARGO: non inventare; non proporre eliminazioni definitive."
            )
            return {"complessita": compl, "modo": "diretto",
                    "candidati": 1, "risposta": (r or "").strip()}
        candidati = self._genera_candidati(domanda, contesto)
        finale, motivo = self._verifica_e_scegli(domanda, contesto, candidati)
        return {"complessita": compl, "modo": "deliberato",
                "candidati": len(candidati), "motivo": motivo, "risposta": finale}


# --------------------------------------------------------------------------
# Test: confronto "risponde" (diretto) vs "ragiona" (deliberato)
# --------------------------------------------------------------------------
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cervello import Cervello

    print("== Test DELIBERATORE ==")
    c = Cervello()

    p = Pensatore(c, n_candidati=3)

    # 1) la stima di complessita' funziona sempre (anche senza Ollama)
    prove = [
        "che ore sono?",
        "riassumi questo file",
        "analizza i pro e i contro di spostare i log su un altro disco e decidi",
    ]
    print("\n-- Stima complessita' --")
    for q in prove:
        print(f"  [{p.valuta_complessita(q)}] {q}")

    # 2) se Ollama e' acceso, confronto diretto vs deliberato sulla stessa domanda
    if not c.vivo():
        print("\nOllama spento: salto il confronto. Accendilo e rilancia.")
        print("OK (logica di complessita' verificata)")
        sys.exit(0)

    domanda = ("Ho 200 file misti nei Download e poco tempo. "
               "Analizza come conviene organizzarli e decidi un piano in 3 passi.")
    print("\n-- DIRETTO (risponde di getto) --")
    print(c.pensa("Domanda: " + domanda).strip())

    print("\n-- DELIBERATO (genera 3 ragionamenti + verificatore) --")
    res = p.delibera(domanda)
    print(f"[complessita: {res['complessita']} | candidati: {res['candidati']} | {res.get('motivo','')}]")
    print(res["risposta"])
    print("\nOK")
