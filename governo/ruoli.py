"""
ARGO - governo/ruoli.py  (RBAC: ruoli e permessi)
Enterprise = separazione dei privilegi. Quattro ruoli:

  admin     -> tutto (configura, agisce, conferma, audit, annulla)
  operatore -> agisce e conferma, NON configura policy/ruoli
  auditor   -> vede ed esporta audit, NON agisce
  utente    -> vede e chatta, NON agisce

Il ruolo attuale sta in config/config.json ("ruolo": "admin" di default, monoutente).
Solo libreria standard.
"""

PERMESSI = {
    "admin":     {"vedere", "chattare", "confermare", "agire", "annullare",
                  "configurare", "vedere_audit", "esportare_audit"},
    "operatore": {"vedere", "chattare", "confermare", "agire", "annullare",
                  "vedere_audit"},
    "auditor":   {"vedere", "chattare", "vedere_audit", "esportare_audit"},
    "utente":    {"vedere", "chattare"},
}


class Ruoli:
    def __init__(self, impostazioni=None, ruolo=None):
        if ruolo:
            self.ruolo = ruolo
        elif impostazioni is not None:
            self.ruolo = impostazioni.dati.get("ruolo", "admin")
        else:
            self.ruolo = "admin"
        if self.ruolo not in PERMESSI:
            self.ruolo = "admin"

    def puo(self, permesso):
        return permesso in PERMESSI.get(self.ruolo, set())

    def permessi(self):
        return sorted(PERMESSI.get(self.ruolo, set()))


if __name__ == "__main__":
    for r in PERMESSI:
        print(r, "->", sorted(PERMESSI[r]))
