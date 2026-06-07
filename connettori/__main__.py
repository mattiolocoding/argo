"""
ARGO - connettori/__main__.py
Smoke-test del pacchetto connettori.

Eseguire con:
    python -m connettori          (dalla root del progetto Argo)

Verifica:
  - RegistroConnettori si istanzia correttamente
  - I connettori noti sono registrati
  - disponibili() e non_disponibili() coprono tutti i connettori
  - info() ritorna la struttura attesa
  - leggi() su connettore inesistente ritorna {"errore": ...}
  - registra() aggiunge un connettore custom dinamicamente
"""

import os
import sys

# Assicura che la root del progetto sia nel path (necessario se si lancia
# con `python -m connettori` da una sottocartella o da IDE)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from connettori import RegistroConnettori, Connettore  # noqa: E402 (import dopo sys.path)


def main() -> None:
    registro = RegistroConnettori()
    print(f"Registro: {registro}")

    # --- verifica metodi obbligatori ---
    assert hasattr(registro, "disponibili"),     "Manca metodo disponibili()"
    assert hasattr(registro, "non_disponibili"), "Manca metodo non_disponibili()"
    assert hasattr(registro, "info"),            "Manca metodo info()"
    assert hasattr(registro, "leggi"),           "Manca metodo leggi()"
    assert hasattr(registro, "registra"),        "Manca metodo registra()"

    # --- verifica connettori attesi ---
    info = registro.info()
    assert isinstance(info, list), "info() deve ritornare una lista"
    assert len(info) == 4, f"Attesi 4 connettori, trovati {len(info)}"

    nomi_attesi = {"filesystem", "email_imap", "git", "ricerca_web"}
    nomi_trovati = {c["nome"] for c in info}
    assert nomi_trovati == nomi_attesi, f"Connettori errati: {nomi_trovati}"

    # --- verifica che disponibili() + non_disponibili() coprano tutti ---
    tutti = set(registro.tutti().keys())
    disp = set(registro.disponibili())
    non_disp = set(registro.non_disponibili())
    assert disp | non_disp == tutti, "disponibili() + non_disponibili() non coprono tutti i connettori"
    assert disp & non_disp == set(), "Intersezione non vuota tra disponibili e non_disponibili"

    # --- stampa riepilogo ---
    print("\nConnettori registrati:")
    for voce in info:
        stato = "SI" if voce["disponibile"] else "NO"
        print(f"  [{stato}] {voce['nome']:15} — {voce['descrizione'][:65]}...")

    print(f"\nDisponibili    : {registro.disponibili()}")
    print(f"Non disponibili: {registro.non_disponibili()}")

    # --- verifica gestione errore connettore inesistente ---
    errore = registro.leggi("connettore_inesistente")
    assert isinstance(errore, dict) and "errore" in errore, \
        "Connettore inesistente deve ritornare {'errore': ...}"

    # --- verifica registrazione dinamica ---
    class _ConnettoreProva(Connettore):
        @property
        def nome(self):        return "_prova"
        @property
        def descrizione(self): return "Connettore di prova per smoke-test __main__"
        def disponibile(self): return True
        def leggi(self, parametri=None): return [{"test": True}]

    registro.registra(_ConnettoreProva())
    assert "_prova" in registro.tutti(), "Registrazione dinamica fallita"
    assert registro.leggi("_prova") == [{"test": True}], "Lettura connettore di prova fallita"

    print("\nOK")


if __name__ == "__main__":
    main()
