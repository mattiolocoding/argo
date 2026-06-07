"""
config/permessi.py  — ARGO · sistema permessi cartelle

Gestisce il consenso dell'utente sulle cartelle che ARGO può osservare.
Il file di configurazione è config/permessi.json (locale, mai condiviso).
"""

import os
import json

_DIR = os.path.dirname(os.path.abspath(__file__))
_FILE = os.path.join(_DIR, "permessi.json")

MODI_VALIDI = ("tutto", "selezione", "niente")


class Permessi:
    """
    Gestisce il sistema di permessi sulle cartelle osservate da ARGO.

    Campi:
        modo (str): 'tutto' | 'selezione' | 'niente'
        cartelle (list[str]): percorsi consentiti in modo 'selezione'
        onboarding_fatto (bool): True se l'utente ha già scelto

    Metodi pubblici:
        carica() -> None
        salva() -> None
        imposta(modo, cartelle) -> None
        consentita(percorso) -> bool
        come_dict() -> dict
    """

    def __init__(self):
        self.modo: str = "selezione"
        self.cartelle: list[str] = []
        self.onboarding_fatto: bool = False
        self.carica()

    # ------------------------------------------------------------------ I/O

    def carica(self) -> None:
        """Carica il file config/permessi.json (se esiste)."""
        if not os.path.isfile(_FILE):
            return
        try:
            with open(_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.modo = d.get("modo", "selezione")
            if self.modo not in MODI_VALIDI:
                self.modo = "selezione"
            raw = d.get("cartelle", [])
            self.cartelle = [c for c in raw if isinstance(c, str)]
            self.onboarding_fatto = bool(d.get("onboarding_fatto", False))
        except Exception as e:
            print(f"[Permessi] avviso lettura: {e}")

    def salva(self) -> None:
        """Salva lo stato corrente in config/permessi.json."""
        try:
            os.makedirs(_DIR, exist_ok=True)
            with open(_FILE, "w", encoding="utf-8") as f:
                json.dump(self.come_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Permessi] errore salvataggio: {e}")

    # ------------------------------------------------------------------ API

    def imposta(self, modo: str, cartelle: list[str] | None = None) -> None:
        """
        Imposta il modo e le cartelle, segna l'onboarding come fatto e salva.

        Args:
            modo: 'tutto' | 'selezione' | 'niente'
            cartelle: lista di percorsi assoluti (usata solo se modo='selezione')
        """
        if modo not in MODI_VALIDI:
            raise ValueError(f"modo non valido: {modo!r}. Valori: {MODI_VALIDI}")
        self.modo = modo
        self.cartelle = [os.path.abspath(c) for c in (cartelle or [])]
        self.onboarding_fatto = True
        self.salva()

    def consentita(self, percorso: str) -> bool:
        """
        Restituisce True se ARGO è autorizzato ad accedere al percorso.

        Logica:
            - modo='tutto'     → sempre True
            - modo='niente'    → sempre False
            - modo='selezione' → True solo se il percorso è dentro una delle
                                 cartelle consentite (o è una di esse)
        """
        if self.modo == "tutto":
            return True
        if self.modo == "niente":
            return False
        # modo = 'selezione'
        percorso = os.path.abspath(percorso)
        for c in self.cartelle:
            c_norm = os.path.abspath(c)
            # il percorso è uguale alla cartella oppure è un suo figlio
            if percorso == c_norm or percorso.startswith(c_norm + os.sep):
                return True
        return False

    def come_dict(self) -> dict:
        """Restituisce lo stato come dizionario (pronto per JSON)."""
        return {
            "modo": self.modo,
            "cartelle": self.cartelle,
            "onboarding_fatto": self.onboarding_fatto,
        }


# ------------------------------------------------------------------ __main__

if __name__ == "__main__":
    p = Permessi()
    print(f"[Permessi] modo={p.modo!r}  onboarding_fatto={p.onboarding_fatto}")
    print(f"[Permessi] cartelle={p.cartelle}")

    # Test veloce
    home = os.path.expanduser("~")
    desktop = os.path.join(home, "Desktop")

    p.imposta("selezione", [desktop])
    assert p.consentita(desktop), "desktop dovrebbe essere consentito"
    assert p.consentita(os.path.join(desktop, "file.txt")), "figlio di desktop dovrebbe passare"
    assert not p.consentita(os.path.join(home, "Documents")), "Documents non dovrebbe passare"

    p.imposta("tutto")
    assert p.consentita(os.path.join(home, "AppData", "x.bin")), "tutto: qualsiasi percorso passa"

    p.imposta("niente")
    assert not p.consentita(desktop), "niente: nessun percorso passa"

    # Ripristina stato neutro per non sporcare il file di produzione
    p.modo = "selezione"
    p.cartelle = []
    p.onboarding_fatto = False
    # Non salviamo: era solo un test

    print("[Permessi] OK — tutti i test superati.")
