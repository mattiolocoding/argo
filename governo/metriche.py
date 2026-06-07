"""
ARGO - governo/metriche.py  (METRICHE: senza numeri non vendi enterprise)
Calcola quanto ha fatto ARGO, dai dati reali della memoria e dell'audit.

  - azioni eseguite, confermate, rifiutate, osservate
  - file visti
  - rischi evitati (file sensibili ignorati)
  - tempo stimato risparmiato
Solo libreria standard.
"""

SECONDI_PER_AZIONE = 30   # stima prudente del tempo manuale risparmiato per azione


class Metriche:
    def __init__(self, memoria, audit=None):
        self.memoria = memoria
        self.audit = audit

    def calcola(self):
        t = self.memoria.conta_per_tipo()
        azioni = t.get("azione", 0) + t.get("azione_confermata", 0)
        rifiutate = t.get("azione_rifiutata", 0)
        osservate = t.get("osservato", 0)
        file_visti = t.get("file_aggiunto", 0)
        sensibili = 0
        if self.audit is not None:
            try:
                for v in self.audit.recenti(1000):
                    if v.get("evento") == "sensibile_ignorato":
                        sensibili += 1
            except Exception:
                pass
        risparmio_min = round(azioni * SECONDI_PER_AZIONE / 60, 1)
        return {
            "azioni_eseguite": azioni,
            "azioni_rifiutate": rifiutate,
            "osservazioni": osservate,
            "file_visti": file_visti,
            "rischi_evitati": sensibili,
            "ricordi_totali": self.memoria.conta(),
            "tempo_risparmiato_min": risparmio_min,
            "chat": t.get("chat", 0),
        }
