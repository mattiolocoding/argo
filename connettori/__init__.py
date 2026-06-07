"""
ARGO - connettori/__init__.py
Pacchetto connettori enterprise di ARGO.

Espone RegistroConnettori, punto di accesso unico per tutte le integrazioni.

Uso rapido:
    from connettori import RegistroConnettori

    registro = RegistroConnettori()
    print(registro.disponibili())           # lista dei nomi connettori attivi
    dati = registro.leggi("filesystem", {"cartella": "C:/Users/..."})
"""

from .base import Connettore
from .filesystem import ConnettoreFilesystem
from .email_imap import ConnettoreEmail
from .git import ConnettoreGit
from .ricerca_web import ConnettoreRicercaWeb


class RegistroConnettori:
    """
    Registro centrale di tutti i connettori enterprise di ARGO.

    Istanzia i connettori disponibili e offre un'interfaccia uniforme
    per interrogarli per nome.
    """

    def __init__(self):
        # Istanzia tutti i connettori noti
        self._connettori: dict[str, Connettore] = {
            c.nome: c
            for c in [
                ConnettoreFilesystem(),
                ConnettoreEmail(),
                ConnettoreGit(),
                ConnettoreRicercaWeb(),
            ]
        }

    # --- ispezione ---

    def tutti(self) -> dict[str, Connettore]:
        """Ritorna il dizionario {nome: connettore} di tutti i connettori registrati."""
        return dict(self._connettori)

    def disponibili(self) -> list[str]:
        """
        Ritorna la lista dei nomi dei connettori attualmente disponibili
        (cioè dove disponibile() == True).
        """
        return [nome for nome, c in self._connettori.items() if c.disponibile()]

    def non_disponibili(self) -> list[str]:
        """Ritorna la lista dei nomi dei connettori non disponibili."""
        return [nome for nome, c in self._connettori.items() if not c.disponibile()]

    def info(self) -> list[dict]:
        """
        Ritorna una lista di dizionari con nome, descrizione e stato
        per ciascun connettore registrato.
        """
        return [
            {
                "nome": nome,
                "descrizione": c.descrizione,
                "disponibile": c.disponibile(),
            }
            for nome, c in self._connettori.items()
        ]

    # --- lettura ---

    def leggi(self, nome: str, parametri: dict | None = None) -> list | dict:
        """
        Delega la lettura al connettore identificato da `nome`.

        Parametri
        ---------
        nome       : str  — nome del connettore (es. 'filesystem', 'git', 'email_imap')
        parametri  : dict — parametri specifici del connettore (opzionale)

        Ritorna
        -------
        list | dict — dati letti, oppure {"errore": "..."} in caso di problemi.
        """
        if nome not in self._connettori:
            nomi_validi = ", ".join(self._connettori.keys())
            return {"errore": f"Connettore '{nome}' non trovato. Disponibili: {nomi_validi}"}

        connettore = self._connettori[nome]

        if not connettore.disponibile():
            return {
                "errore": (
                    f"Il connettore '{nome}' non è disponibile. "
                    "Controlla la configurazione in config/connettori.json."
                )
            }

        try:
            return connettore.leggi(parametri)
        except Exception as e:
            return {"errore": f"Errore durante la lettura dal connettore '{nome}': {e}"}

    # --- registrazione dinamica ---

    def registra(self, connettore: Connettore) -> None:
        """
        Aggiunge un nuovo connettore al registro.
        Permette l'estensione del sistema senza modificare questo file.

        Esempio:
            registro.registra(MioConnettoreCustom())
        """
        if not isinstance(connettore, Connettore):
            raise TypeError(
                f"Il connettore deve essere una sottoclasse di Connettore, "
                f"ricevuto: {type(connettore).__name__}"
            )
        self._connettori[connettore.nome] = connettore

    def __repr__(self) -> str:
        disp = self.disponibili()
        totale = len(self._connettori)
        return f"<RegistroConnettori {len(disp)}/{totale} disponibili: {disp}>"


# --- esportazioni pubbliche del pacchetto ---
__all__ = [
    "Connettore",
    "RegistroConnettori",
    "ConnettoreFilesystem",
    "ConnettoreEmail",
    "ConnettoreGit",
    "ConnettoreRicercaWeb",
]


# ---------------------------------------------------------------------------
# Smoke-test del pacchetto: `python -m connettori`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    registro = RegistroConnettori()
    print(f"Registro: {registro}")

    # Verifica struttura base
    assert hasattr(registro, "disponibili"), "Manca metodo disponibili()"
    assert hasattr(registro, "leggi"), "Manca metodo leggi()"
    assert hasattr(registro, "registra"), "Manca metodo registra()"

    # Verifica info()
    info = registro.info()
    assert isinstance(info, list), "info() deve ritornare una lista"
    assert len(info) == 4, f"Attesi 4 connettori, trovati {len(info)}"

    nomi_attesi = {"filesystem", "email_imap", "git", "ricerca_web"}
    nomi_trovati = {c["nome"] for c in info}
    assert nomi_trovati == nomi_attesi, f"Connettori errati: {nomi_trovati}"

    print("\nConnettori registrati:")
    for voce in info:
        stato = "SI" if voce["disponibile"] else "NO"
        print(f"  [{stato}] {voce['nome']:15} — {voce['descrizione'][:60]}...")

    # Verifica connettore inesistente
    errore = registro.leggi("connettore_inesistente")
    assert "errore" in errore, "Connettore inesistente deve ritornare errore"

    # Verifica registrazione dinamica
    class _ConnettoreProva(Connettore):
        @property
        def nome(self): return "_prova"
        @property
        def descrizione(self): return "Connettore di prova per smoke-test"
        def disponibile(self): return True
        def leggi(self, parametri=None): return [{"test": True}]

    registro.registra(_ConnettoreProva())
    assert "_prova" in registro.tutti(), "Registrazione dinamica fallita"
    assert registro.leggi("_prova") == [{"test": True}], "Lettura connettore di prova fallita"

    print("\nOK")
