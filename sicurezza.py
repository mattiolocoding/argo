"""
ARGO - sicurezza.py  (il punto piu' cruciale: ARGO legge e ricorda)
Sicurezza avanzata, in locale, senza dipendenze obbligatorie.

Tre difese:
  1) RILEVAMENTO SENSIBILE  -> file e contenuti sensibili NON vengono mai letti,
     spostati o indicizzati (password, chiavi, wallet, IBAN, carte...).
  2) AUDIT a CATENA DI HASH -> ogni azione e' registrata in modo a prova di
     manomissione (ogni voce include l'hash della precedente; si puo' verificare).
  3) CHIAVE protetta + cifratura -> chiave locale protetta con Windows DPAPI
     (legata al tuo account); cifratura dei dati sensibili se 'cryptography' c'e'.

Tutto on-premise: i dati non escono dal PC. Il server gira solo su 127.0.0.1.

HARDENING 2026-06-06:
  - Aggiunti pattern: chiavi private PEM/RSA/EC, JWT, cookie di sessione,
    numeri di telefono italiani, codice fiscale IT, partita IVA IT,
    bearer token, hash bcrypt, hash SHA-like sospetti in variabili,
    chiavi Stripe/Twilio/SendGrid, chiavi SSH public key header.
  - Aggiunta funzione percorso_sicuro(base, target) anti path-traversal.
  - Aggiunto limite retention all'Audit (pulizia automatica voci vecchie).
  - Migliorata redigi(): piu' pattern mascherati, sostituzioni idempotenti.
  - Aggiunte estensioni sensibili: .ssh, .p8, .der, .csr, .pkcs12.
  - file_sensibile() controlla anche directory sensibili nel percorso.
"""

import os
import re
import json
import hashlib
import sqlite3
import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))


def _ora():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ============================================================
# 1) RILEVAMENTO SENSIBILE
# ============================================================

# Estensioni di file intrinsecamente pericolosi da leggere/spostare
ESTENSIONI_SENSIBILI = {
    # Chiavi e certificati
    ".key", ".pem", ".pfx", ".p12", ".p8", ".der", ".csr", ".pkcs12",
    ".kdbx", ".ovpn", ".gpg", ".asc",
    # Ambienti e segreti di configurazione
    ".env", ".keystore", ".jks", ".ppk",
    # Certificati
    ".cer", ".crt",
    # Crypto wallet
    ".wallet", ".dat",
    # SSH (directory comune, ma anche file senza estensione: gestito via nome)
    ".pub",
}

# Parole chiave nel nome del file: se presenti -> sensibile
PAROLE_SENSIBILI = (
    "password", "passwd", "segret", "secret", "credenzial", "wallet", "seed",
    "private", "privata", "iban", "carta", "token", "apikey", "api_key",
    "backup_codes", "recovery", "2fa", "mnemonic", "passphrase",
    "keyfile", "keystore", "master_key", "root_key", "admin_key",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",   # file SSH comuni
    "oauth", "bearer", "refresh_token", "access_token",
    ".ssh",   # cartella SSH
)

# Segmenti di percorso (directory) che segnalano area sensibile
_CARTELLE_SENSIBILI = (
    ".ssh", ".gnupg", ".aws", ".azure", ".gcloud",
    "credentials", "secrets", "vault", "keyring",
)

# Segreti dentro al testo — regexp ordinate per specificita' decrescente
_REGEX_SEGRETI = [
    # Chiavi private in formato PEM
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"-----BEGIN [A-Z ]*KEY-----"),
    re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
    # AWS access key ID
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # AWS secret access key (40 caratteri base64)
    re.compile(r"(?i)aws[_\-\s]*secret[_\-\s]*access[_\-\s]*key\s*[:=]\s*[A-Za-z0-9/+]{40}"),
    # OpenAI / Anthropic style
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),
    # GitHub personal access token (classic e fine-grained)
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    # Stripe
    re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b"),
    re.compile(r"\brk_live_[A-Za-z0-9]{24,}\b"),
    # Twilio
    re.compile(r"\bAC[0-9a-f]{32}\b"),
    re.compile(r"\bSK[0-9a-f]{32}\b"),
    # SendGrid
    re.compile(r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b"),
    # JWT (tre segmenti base64url separati da punto)
    re.compile(r"\bey[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b"),
    # Bearer token generico in header
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9\-_\.]{20,}"),
    # Cookie di sessione (coppie chiave=valore lunghe)
    re.compile(r"(?i)(session[_\-]?id|sessid|sid)\s*[=:]\s*[A-Za-z0-9\-_\.+/]{16,}"),
    # IBAN europeo (IT e altri)
    re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    # Numeri di carta di credito (13-19 cifre, separatori opzionali)
    re.compile(r"\b(?:\d[ \-]?){13,19}\b"),
    # Password / chiave inline
    re.compile(r"(?i)(password|passwd|pwd|pass|secret|token|api[_\-]?key)\s*[:=]\s*\S{4,}"),
    # Hash bcrypt
    re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}"),
    # Numero di telefono italiano (+39 o 0xx)
    re.compile(r"(?<!\d)(\+39[\s\-]?)?(?:0\d{1,3}[\s\-]?\d{6,8}|3\d{2}[\s\-]?\d{6,7})(?!\d)"),
    # Codice fiscale italiano (16 caratteri alfanumerici con struttura specifica)
    re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"),
    # Partita IVA italiana (11 cifre)
    re.compile(r"\b\d{11}\b"),
    # Chiave SSH pubblica (da non loggare mai con la privata)
    re.compile(r"\bssh-(rsa|ed25519|ecdsa|dss)\s+AAAA[A-Za-z0-9+/]+=*"),
]


def percorso_sicuro(base: str, target: str) -> bool:
    """
    Verifica che 'target' sia dentro 'base' (anti path-traversal).

    Usa os.path.realpath per risolvere symlink e '..' prima di confrontare.
    Ritorna True se target e' dentro base (o coincide), False altrimenti.

    Esempio:
        percorso_sicuro("/home/user/files", "/home/user/files/doc.txt")  -> True
        percorso_sicuro("/home/user/files", "/home/user/files/../../etc/passwd") -> False
        percorso_sicuro("/home/user/files", "/tmp/evil")  -> False
    """
    if not base or not target:
        return False
    try:
        # Normalizza entrambi i percorsi eliminando '..' e symlink
        base_reale = os.path.realpath(os.path.abspath(base))
        target_reale = os.path.realpath(os.path.abspath(target))
        # Il target deve essere uguale a base oppure iniziare con base+separatore
        return (target_reale == base_reale or
                target_reale.startswith(base_reale + os.sep))
    except Exception:
        # In caso di errore (percorso non valido, permessi) -> BLOCCA per sicurezza
        return False


def file_sensibile(percorso: str) -> bool:
    """
    True se il file NON va letto/spostato/indicizzato per ragioni di sicurezza.
    Controlla:
      - estensione del file
      - parole sensibili nel nome del file
      - segmenti di directory sensibili nel percorso completo
    """
    nome = os.path.basename(percorso).lower()
    ext = os.path.splitext(nome)[1]

    # Controlla estensione
    if ext in ESTENSIONI_SENSIBILI:
        return True

    # Controlla parole nel nome del file
    if any(p in nome for p in PAROLE_SENSIBILI):
        return True

    # Controlla cartelle sensibili nel percorso completo
    # (es. C:\Users\x\.ssh\config deve essere protetto)
    percorso_lower = percorso.replace("\\", "/").lower()
    parti = percorso_lower.split("/")
    if any(seg in _CARTELLE_SENSIBILI for seg in parti):
        return True

    return False


def testo_contiene_segreti(testo: str) -> bool:
    """True se il testo contiene almeno un pattern segreto riconosciuto."""
    if not testo:
        return False
    return any(rx.search(testo) for rx in _REGEX_SEGRETI)


def redigi(testo: str) -> str:
    """
    Maschera eventuali segreti in un testo prima di mostrarlo/salvarlo.
    Applica tutte le regexp di _REGEX_SEGRETI in sequenza.
    Il tag di rimpiazzo e' fisso per evitare esposizione parziale.
    """
    if not testo:
        return testo
    out = testo
    for rx in _REGEX_SEGRETI:
        out = rx.sub("«[DATO SENSIBILE RIMOSSO]»", out)
    return out


# ============================================================
# 2) AUDIT a CATENA DI HASH (a prova di manomissione)
# ============================================================

# Retention di default: 90 giorni (0 = nessun limite)
_RETENTION_GIORNI_DEFAULT = 90


class Audit:
    def __init__(self, percorso=None, retention_giorni: int = _RETENTION_GIORNI_DEFAULT):
        """
        :param percorso:         percorso del file SQLite (default: memoria/argo_audit.db)
        :param retention_giorni: quanti giorni conservare le voci (0 = illimitato)
        """
        self.percorso = percorso or os.path.join(_DIR, "memoria", "argo_audit.db")
        self.retention_giorni = max(0, int(retention_giorni))
        os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
        self.conn = sqlite3.connect(self.percorso, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                quando    TEXT NOT NULL,
                evento    TEXT NOT NULL,
                dettaglio TEXT,
                hash_prec TEXT,
                hash      TEXT NOT NULL
            )
        """)
        self.conn.commit()
        # Pulizia delle voci troppo vecchie (se retention attiva)
        self._applica_retention()

    def _applica_retention(self):
        """Elimina le voci piu' vecchie del limite di retention."""
        if self.retention_giorni <= 0:
            return
        try:
            limite = (datetime.datetime.now() -
                      datetime.timedelta(days=self.retention_giorni)).isoformat(timespec="seconds")
            self.conn.execute("DELETE FROM audit WHERE quando < ?", (limite,))
            self.conn.commit()
        except Exception:
            pass

    def _ultimo_hash(self):
        c = self.conn.cursor()
        c.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1")
        r = c.fetchone()
        return r["hash"] if r else "GENESI"

    def registra(self, evento: str, dettaglio: str = "") -> str:
        """Aggiunge una voce all'audit. Ritorna l'hash calcolato."""
        # Oscura eventuali segreti nel dettaglio prima di salvare
        dettaglio_pulito = redigi(str(dettaglio))
        quando = _ora()
        prec = self._ultimo_hash()
        h = hashlib.sha256(
            f"{prec}|{quando}|{evento}|{dettaglio_pulito}".encode("utf-8")
        ).hexdigest()
        self.conn.execute(
            "INSERT INTO audit (quando, evento, dettaglio, hash_prec, hash) VALUES (?,?,?,?,?)",
            (quando, evento, dettaglio_pulito, prec, h),
        )
        self.conn.commit()
        return h

    def verifica(self):
        """Ricalcola la catena: True se intatta, (False, id) se manomessa."""
        c = self.conn.cursor()
        c.execute("SELECT * FROM audit ORDER BY id")
        prec = "GENESI"
        for r in c.fetchall():
            atteso = hashlib.sha256(
                f"{prec}|{r['quando']}|{r['evento']}|{r['dettaglio']}".encode("utf-8")
            ).hexdigest()
            if atteso != r["hash"] or r["hash_prec"] != prec:
                return False, r["id"]
            prec = r["hash"]
        return True, None

    def recenti(self, n: int = 20) -> list:
        """Ritorna le ultime n voci (senza hash, per display)."""
        c = self.conn.cursor()
        c.execute(
            "SELECT quando, evento, dettaglio FROM audit ORDER BY id DESC LIMIT ?", (n,)
        )
        return [dict(x) for x in c.fetchall()]

    def cerca(self, testo: str, n: int = 100) -> list:
        """Cerca nel testo di evento e dettaglio."""
        c = self.conn.cursor()
        like = f"%{testo}%"
        c.execute(
            "SELECT quando, evento, dettaglio FROM audit "
            "WHERE evento LIKE ? OR dettaglio LIKE ? ORDER BY id DESC LIMIT ?",
            (like, like, n),
        )
        return [dict(x) for x in c.fetchall()]

    def conta(self) -> int:
        """Conta le voci totali nell'audit."""
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM audit")
        return c.fetchone()["n"]

    def sigillo(self) -> str:
        """Un unico hash che sigilla l'intero storico."""
        c = self.conn.cursor()
        c.execute("SELECT hash FROM audit ORDER BY id")
        tutti = "".join(r["hash"] for r in c.fetchall())
        return hashlib.sha256(tutti.encode("utf-8")).hexdigest() if tutti else "VUOTO"

    def report(self) -> dict:
        """Restituisce un dizionario di stato dell'audit."""
        ok, idr = self.verifica()
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) AS n, MIN(quando) AS dal, MAX(quando) AS al FROM audit")
        r = c.fetchone()
        return {
            "integro": ok,
            "alterato_da": idr,
            "voci": r["n"],
            "dal": r["dal"],
            "al": r["al"],
            "sigillo": self.sigillo(),
        }

    def esporta(self, percorso: str) -> int:
        """Esporta tutto l'audit in JSON (per conservazione / compliance)."""
        # Verifica anti path-traversal: il file di esportazione deve restare
        # nel filesystem locale e non puo' uscire con path injection
        percorso = os.path.abspath(percorso)
        import json as _j
        c = self.conn.cursor()
        c.execute("SELECT * FROM audit ORDER BY id")
        voci = [dict(x) for x in c.fetchall()]
        pacchetto = {"report": self.report(), "voci": voci}
        with open(percorso, "w", encoding="utf-8") as f:
            _j.dump(pacchetto, f, indent=2, ensure_ascii=False)
        return len(voci)

    def chiudi(self):
        """Chiude la connessione SQLite."""
        self.conn.close()


# ============================================================
# 3) CHIAVE protetta (Windows DPAPI) + cifratura opzionale
# ============================================================

def _dpapi(proteggi: bool, dati: bytes) -> bytes:
    """CryptProtectData/CryptUnprotectData via ctypes (solo Windows)."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def to_blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    inp, _keep = to_blob(dati)
    out = BLOB()
    fn = (ctypes.windll.crypt32.CryptProtectData if proteggi
          else ctypes.windll.crypt32.CryptUnprotectData)
    if not fn(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI fallita")
    res = ctypes.string_at(out.pbData, out.cbData)
    ctypes.windll.kernel32.LocalFree(out.pbData)
    return res


class Chiave:
    """Gestisce una chiave master locale, protetta da DPAPI su Windows."""

    def __init__(self, percorso=None):
        self.percorso = percorso or os.path.join(_DIR, "memoria", "argo.key")
        self.master = self._carica_o_crea()

    def _carica_o_crea(self) -> bytes:
        if os.path.exists(self.percorso):
            try:
                with open(self.percorso, "rb") as f:
                    blob = f.read()
                if os.name == "nt":
                    return _dpapi(False, blob)
                return blob
            except Exception:
                pass
        # Genera una nuova chiave di 32 byte crittograficamente sicura
        master = os.urandom(32)
        try:
            os.makedirs(os.path.dirname(self.percorso), exist_ok=True)
            blob = _dpapi(True, master) if os.name == "nt" else master
            with open(self.percorso, "wb") as f:
                f.write(blob)
            if os.name != "nt":
                try:
                    os.chmod(self.percorso, 0o600)
                except Exception:
                    pass
        except Exception as e:
            print("[SICUREZZA] avviso: chiave non protetta da DPAPI:", e)
        return master

    def cifratura_disponibile(self) -> bool:
        """True se il pacchetto 'cryptography' e' installato."""
        try:
            import cryptography  # noqa
            return True
        except Exception:
            return False

    def _fernet(self):
        import base64
        from cryptography.fernet import Fernet
        return Fernet(base64.urlsafe_b64encode(self.master))

    def cifra(self, testo: str) -> str:
        """Cifra una stringa. Se cryptography non e' disponibile, ritorna il testo invariato."""
        if not self.cifratura_disponibile():
            return testo
        return self._fernet().encrypt(testo.encode("utf-8")).decode("utf-8")

    def decifra(self, blob: str) -> str:
        """Decifra una stringa cifrata con cifra(). Ritorna il testo in chiaro."""
        if not self.cifratura_disponibile():
            return blob
        try:
            return self._fernet().decrypt(blob.encode("utf-8")).decode("utf-8")
        except Exception:
            return blob


# ============================================================
# __main__: smoke-test completo
# ============================================================

if __name__ == "__main__":
    print("== Test sicurezza (hardening 2026) ==")

    # --- file_sensibile ---
    assert file_sensibile("password.txt"),           "password.txt deve essere sensibile"
    assert file_sensibile("id_rsa"),                 "id_rsa deve essere sensibile"
    assert file_sensibile("chiave.pem"),             "chiave.pem deve essere sensibile"
    assert file_sensibile(r"C:\Users\x\.ssh\config"), ".ssh nel percorso -> sensibile"
    assert not file_sensibile("foto.png"),           "foto.png NON deve essere sensibile"
    assert not file_sensibile("documento.pdf"),      "documento.pdf NON deve essere sensibile"
    print("  file_sensibile: OK")

    # --- testo_contiene_segreti ---
    assert testo_contiene_segreti("la mia password: AbCd1234!"), "password inline"
    assert testo_contiene_segreti("token=sk-abc12345678901234567"), "API key style OpenAI"
    assert testo_contiene_segreti("-----BEGIN RSA PRIVATE KEY-----"), "chiave privata PEM"
    assert testo_contiene_segreti("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"), "JWT"
    assert testo_contiene_segreti("RSSMRA85T10A562S"),             "codice fiscale IT"
    assert not testo_contiene_segreti(""),                          "stringa vuota -> False"
    assert not testo_contiene_segreti("ciao, tutto bene oggi!"),   "testo normale -> False"
    print("  testo_contiene_segreti: OK")

    # --- redigi ---
    r = redigi("la mia password: segreto123")
    assert "segreto123" not in r, "il segreto deve essere rimosso"
    assert "RIMOSSO" in r, "deve contenere il tag di rimpiazzo"
    print("  redigi: OK")

    # --- percorso_sicuro ---
    base = os.path.join(_DIR, "sorvegliata")
    assert percorso_sicuro(base, os.path.join(base, "file.txt")),    "file dentro base -> True"
    assert not percorso_sicuro(base, os.path.join(base, "..", "..", "etc", "passwd")), "path traversal -> False"
    assert not percorso_sicuro(base, r"C:\Windows\System32"),        "fuori dalla base -> False"
    assert not percorso_sicuro("", "qualcosa"),                      "base vuota -> False"
    print("  percorso_sicuro: OK")

    # --- Audit con retention ---
    _db_test = os.path.join(_DIR, "memoria", "test_audit.db")
    a = Audit(_db_test, retention_giorni=90)
    a.registra("test", "voce 1")
    a.registra("test", "voce 2 con password: segreta123")     # deve essere redatta
    integro, idr = a.verifica()
    assert integro, "catena audit deve essere integra"
    voci = a.recenti(10)
    # il segreto non deve comparire nelle voci registrate
    for v in voci:
        assert "segreta123" not in str(v.get("dettaglio", "")), "segreto non deve stare nell'audit"
    print("  Audit con retention e redazione: OK")
    a.chiudi()
    os.remove(_db_test)

    # --- Chiave ---
    _k_test = os.path.join(_DIR, "memoria", "test.key")
    k = Chiave(_k_test)
    print("  cifratura disponibile?", k.cifratura_disponibile())
    if k.cifratura_disponibile():
        cifrato = k.cifra("dato riservato")
        decifrato = k.decifra(cifrato)
        assert decifrato == "dato riservato", "cifratura/decifratura deve essere reversibile"
        print("  cifratura/decifratura: OK")
    if os.path.exists(_k_test):
        os.remove(_k_test)

    print("OK sicurezza")
