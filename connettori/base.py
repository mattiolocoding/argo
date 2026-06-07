"""
ARGO - connettori/base.py
Classe astratta di base per tutti i connettori enterprise di ARGO.

Ogni connettore deve implementare:
  - nome      : stringa identificativa univoca
  - descrizione: stringa leggibile che descrive cosa fa
  - disponibile(): bool — indica se il connettore è utilizzabile ora
  - leggi(parametri): list | dict — recupera dati in sola lettura
"""

from abc import ABC, abstractmethod


class Connettore(ABC):
    """Interfaccia uniforme per tutti i connettori enterprise di ARGO."""

    # --- proprietà da definire nelle sottoclassi ---

    @property
    @abstractmethod
    def nome(self) -> str:
        """Nome identificativo del connettore (es. 'filesystem', 'email_imap')."""

    @property
    @abstractmethod
    def descrizione(self) -> str:
        """Descrizione leggibile di cosa il connettore è in grado di fare."""

    # --- metodi da implementare ---

    @abstractmethod
    def disponibile(self) -> bool:
        """
        Ritorna True se il connettore è utilizzabile in questo momento.
        Deve essere veloce e non sollevare eccezioni.
        """

    @abstractmethod
    def leggi(self, parametri: dict | None = None) -> list | dict:
        """
        Recupera dati dal sistema esterno in SOLA LETTURA.

        Parametri
        ---------
        parametri : dict, opzionale
            Dizionario di opzioni specifiche del connettore.

        Ritorna
        -------
        list | dict
            I dati letti. In caso di errore ritorna {"errore": "<messaggio>"}.
        """

    # --- metodo di utilità comune ---

    def __repr__(self) -> str:
        stato = "disponibile" if self.disponibile() else "non disponibile"
        return f"<Connettore '{self.nome}' [{stato}]>"
