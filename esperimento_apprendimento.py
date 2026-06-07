"""
ARGO - esperimento_apprendimento.py
LA DOMANDA: un modello piccolo locale puo' diventare piu' capace IMPARANDO cose
che non sa (salvate in memoria), SENZA essere riaddestrato? E puo' RAGIONARE su
cio' che ha appena imparato?

Questo script ci da' una risposta NUMERICA, cosi' sappiamo se la strada e' giusta.

Metodo (rigoroso):
  FASE A - BASELINE: chiediamo al modello fatti che NON puo' conoscere
           (inventati apposta). Quasi sicuramente sbaglia o non sa.
  PASSO   - INSEGNAMENTO: salviamo i fatti in "memoria" (come farebbe ARGO quando
           tu gli rispondi a una cosa che non sapeva).
  FASE B - DOPO: ri-chiediamo le stesse cose, ma ora con la memoria a disposizione.
  PROVA RAGIONAMENTO: una domanda che richiede di COMBINARE due fatti appresi,
           mai detta direttamente. Se la azzecca, sta ragionando sul nuovo sapere.

Verdetto: accuratezza PRIMA vs DOPO. Se sale, la "memoria che cresce" funziona.
Serve Ollama acceso.  Prova:  python esperimento_apprendimento.py
"""

import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cervello import Cervello

# Fatti INVENTATI: il modello non puo' conoscerli -> baseline pulita
FATTI = [
    "Il gatto di Davide si chiama Pixel.",
    "Il progetto ARGO usa un database chiamato MnemoDB.",
    "MnemoDB gira sulla porta 7421.",
    "Davide fa la riunione del team ogni martedi alle 9:30.",
]

# Domande dirette su quei fatti  (domanda, parola_che_deve_comparire)
DOMANDE = [
    ("Come si chiama il gatto di Davide?", "pixel"),
    ("Quale database usa il progetto ARGO?", "mnemodb"),
    ("Su quale porta gira MnemoDB?", "7421"),
    ("Che giorno e a che ora e' la riunione del team di Davide?", "martedi"),
]

# Domanda di RAGIONAMENTO: richiede di unire 2 fatti (ARGO->MnemoDB->7421).
# Non e' mai stata detta cosi'.
DOMANDA_RAGIONAMENTO = ("Su quale porta gira il database del progetto ARGO?", "7421")


def _norm(s):
    s = (s or "").lower().replace("\n", " ")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def corretta(risposta, chiave):
    return _norm(chiave) in _norm(risposta)


def chiedi(cerv, domanda, memoria=None):
    if memoria:
        ctx = "Conosci questi fatti (usali se servono):\n- " + "\n- ".join(memoria)
        prompt = ctx + "\n\nDomanda: " + domanda + "\nRispondi in una frase. Se non sai, dillo."
    else:
        prompt = "Domanda: " + domanda + "\nRispondi in una frase. Se non sai, dillo onestamente."
    return (cerv.pensa(prompt) or "").strip()


def main():
    print("== ESPERIMENTO: il modello impara dalla memoria? ==\n")
    c = Cervello()
    if not c.vivo():
        print("Ollama spento. Accendilo e rilancia.")
        return

    # ---------------- FASE A: BASELINE (senza memoria) ----------------
    print("--- FASE A: BASELINE (il modello NON conosce i fatti) ---")
    giusti_prima = 0
    for d, k in DOMANDE:
        r = chiedi(c, d, memoria=None)
        ok = corretta(r, k)
        giusti_prima += ok
        print(f"  [{'OK' if ok else '..'}] {d}\n       -> {r[:140]}")
    base = round(100 * giusti_prima / len(DOMANDE))
    print(f"\n  BASELINE: {giusti_prima}/{len(DOMANDE)} corrette ({base}%)\n")

    # ---------------- PASSO: INSEGNAMENTO ----------------
    print("--- PASSO: insegno i fatti (li salvo in memoria) ---")
    for f in FATTI:
        print("  + " + f)
    print()

    # ---------------- FASE B: DOPO (con memoria) ----------------
    print("--- FASE B: DOPO (stesse domande, ora con memoria) ---")
    giusti_dopo = 0
    for d, k in DOMANDE:
        r = chiedi(c, d, memoria=FATTI)
        ok = corretta(r, k)
        giusti_dopo += ok
        print(f"  [{'OK' if ok else '..'}] {d}\n       -> {r[:140]}")
    dopo = round(100 * giusti_dopo / len(DOMANDE))
    print(f"\n  DOPO L'APPRENDIMENTO: {giusti_dopo}/{len(DOMANDE)} corrette ({dopo}%)\n")

    # ---------------- PROVA DI RAGIONAMENTO ----------------
    print("--- PROVA RAGIONAMENTO: combinare 2 fatti mai uniti prima ---")
    dq, dk = DOMANDA_RAGIONAMENTO
    # diretto
    r_dir = chiedi(c, dq, memoria=FATTI)
    ok_dir = corretta(r_dir, dk)
    print(f"  [diretto]    {'OK' if ok_dir else '..'} -> {r_dir[:140]}")
    # con deliberazione (best-of-N + verifica), se disponibile
    ok_del = ok_dir
    try:
        from pensatore import Pensatore
        ctx = "Fatti noti:\n- " + "\n- ".join(FATTI)
        res = Pensatore(c, n_candidati=3).delibera(dq, contesto=ctx)
        ok_del = corretta(res.get("risposta", ""), dk)
        print(f"  [deliberato] {'OK' if ok_del else '..'} -> {str(res.get('risposta',''))[:140]}")
    except Exception as e:
        print("  (deliberatore non disponibile:", e, ")")

    # ---------------- VERDETTO ----------------
    print("\n========== VERDETTO ==========")
    print(f"  Conoscenza:   prima {base}%  ->  dopo {dopo}%   (delta +{dopo-base}%)")
    print(f"  Ragionamento sul nuovo sapere: "
          f"{'RIESCE' if ok_del else 'non ancora'}")
    if dopo > base:
        print("\n  >> La strada FUNZIONA: imparare in memoria rende il modello")
        print("     piu' capace SENZA riaddestrarlo. E' il cuore di ARGO.")
        if ok_del and not ok_dir:
            print("  >> BONUS: con la deliberazione RAGIONA su cio' che ha imparato.")
    else:
        print("\n  >> Nessun miglioramento misurato: va cambiato il modo di")
        print("     recuperare/iniettare la memoria. Sappiamo dove guardare.")
    print("==============================")


if __name__ == "__main__":
    main()
