"""
ARGO - correzioni.py  (CICLO ERRORE -> CORREZIONE -> APPRENDIMENTO)
Il pezzo che fa migliorare ARGO con te, senza riaddestrare il modello.

Flusso:
  1) ARGO sbaglia qualcosa.
  2) Tu lo correggi ("no, era cosi'").
  3) ARGO salva: contesto + risposta sbagliata + tua correzione, e ne ricava una
     REGOLA breve ("lezione").
  4) Da quel momento, prima di rispondere su argomenti simili, ARGO inietta le
     lezioni imparate -> non rifa' lo stesso errore.
  5) Si puo' MISURARE se la lezione ha migliorato la risposta.

Tutto locale (SQLite). Funziona anche senza Ollama (la regola = la tua correzione).
Prova:  python correzioni.py
"""

import os
import sqlite3
import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))


def _ora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _parole(testo):
    return {p for p in "".join(c.lower() if c.isalnum() else " " for c in (testo or "")).split()
            if len(p) > 3}


class Correttore:
    def __init__(self, percorso=None, cervello=None):
        self.percorso = percorso or os.path.join(_DIR, "memoria", "argo_correzioni.db")
        os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
        self.cervello = cervello
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS correzioni (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                quando    TEXT,
                contesto  TEXT,
                sbagliato TEXT,
                corretto  TEXT,
                regola    TEXT,
                attiva    INTEGER DEFAULT 1,
                usi       INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    # ---- 3) salva errore + correzione, ricava la regola ----
    def _ricava_regola(self, contesto, sbagliato, corretto):
        # se il cervello e' vivo, sintetizza una lezione generale; altrimenti usa la correzione
        if self.cervello is not None:
            try:
                if self.cervello.vivo():
                    p = ("Ho sbagliato. Contesto: " + (contesto or "") +
                         "\nRisposta sbagliata: " + (sbagliato or "") +
                         "\nCorrezione giusta: " + (corretto or "") +
                         "\n\nScrivi in UNA frase la REGOLA generale da ricordare "
                         "per non rifare questo errore. Solo la regola.")
                    r = self.cervello.pensa(p)
                    if r and not r.startswith("["):
                        return r.strip()
            except Exception:
                pass
        return (corretto or "").strip()

    def registra(self, contesto, sbagliato, corretto):
        regola = self._ricava_regola(contesto, sbagliato, corretto)
        c = self.conn.cursor()
        c.execute("INSERT INTO correzioni (quando, contesto, sbagliato, corretto, regola) "
                  "VALUES (?,?,?,?,?)", (_ora(), contesto, sbagliato, corretto, regola))
        self.conn.commit()
        return {"id": c.lastrowid, "regola": regola}

    # ---- 4) recupera le lezioni rilevanti per un contesto ----
    def regole_rilevanti(self, contesto, max_regole=5):
        c = self.conn.cursor()
        c.execute("SELECT id, contesto, regola FROM correzioni WHERE attiva=1 ORDER BY id DESC")
        righe = c.fetchall()
        pc = _parole(contesto)
        scelte = []
        for r in righe:
            sovrapp = len(pc & _parole(r["contesto"] + " " + r["regola"]))
            scelte.append((sovrapp, r["id"], r["regola"]))
        # prima quelle piu' pertinenti; se nessuna pertinenza, prendi le piu' recenti
        scelte.sort(key=lambda x: x[0], reverse=True)
        out = [(rid, reg) for s, rid, reg in scelte if s > 0][:max_regole]
        if not out:
            out = [(rid, reg) for s, rid, reg in scelte][:max_regole]
        return out

    def applica(self, prompt, contesto=""):
        """Inietta le lezioni imparate nel prompt, prima della domanda."""
        regole = self.regole_rilevanti(contesto or prompt)
        if not regole:
            return prompt
        for rid, _ in regole:
            self.conn.execute("UPDATE correzioni SET usi=usi+1 WHERE id=?", (rid,))
        self.conn.commit()
        testo = "\n".join("- " + reg for _, reg in regole)
        return ("Lezioni imparate dai tuoi errori passati (rispettale SEMPRE):\n"
                + testo + "\n\n" + prompt)

    # ---- 5) misura se la lezione migliora ----
    def verifica_miglioramento(self, domanda, chiave_giusta, contesto=""):
        if self.cervello is None or not self.cervello.vivo():
            return {"ok": None, "messaggio": "cervello offline"}
        def giusta(r): return chiave_giusta.lower() in (r or "").lower()
        prima = self.cervello.pensa("Domanda: " + domanda)
        dopo = self.cervello.pensa(self.applica("Domanda: " + domanda, contesto))
        return {"prima_ok": giusta(prima), "dopo_ok": giusta(dopo),
                "prima": (prima or "")[:120], "dopo": (dopo or "")[:120]}

    def elenco(self, n=20):
        c = self.conn.cursor()
        c.execute("SELECT id, quando, regola, attiva, usi FROM correzioni ORDER BY id DESC LIMIT ?", (n,))
        return [dict(x) for x in c.fetchall()]

    def disattiva(self, id_corr):
        self.conn.execute("UPDATE correzioni SET attiva=0 WHERE id=?", (int(id_corr),))
        self.conn.commit()

    def chiudi(self):
        self.conn.close()


if __name__ == "__main__":
    print("== Test ciclo ERRORE -> CORREZIONE -> APPRENDIMENTO ==\n")
    tmp = os.path.join(_DIR, "memoria", "test_correzioni.db")
    if os.path.exists(tmp):
        os.remove(tmp)
    co = Correttore(percorso=tmp)

    # 1-3) ARGO sbaglia, tu correggi, lui salva la regola
    res = co.registra(
        contesto="archiviazione fatture e documenti fiscali",
        sbagliato="Ho spostato la fattura in 'Documenti generici'.",
        corretto="Le fatture vanno in 'Documenti/Fiscale/2026', mai nei generici.",
    )
    print("Regola imparata:", res["regola"])

    # 4) la prossima volta la lezione viene iniettata
    prompt = co.applica("Domanda: dove archivio questa fattura?",
                        contesto="devo archiviare una fattura")
    print("\nPrompt arricchito con la lezione:\n" + prompt)

    assert "Lezioni imparate" in prompt and "fattur" in prompt.lower()
    print("\nElenco correzioni:", co.elenco())
    co.chiudi()
    os.remove(tmp)
    print("\nOK")
