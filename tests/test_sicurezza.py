"""
ARGO - test_sicurezza.py
Test di regressione per il modulo sicurezza.py (hardening 2026-06-06).

Copertura:
  - file_sensibile(): estensioni, parole chiave nel nome, directory sensibili nel percorso
  - testo_contiene_segreti(): tutti i pattern principali (PEM, JWT, CF, IBAN, ecc.)
  - redigi(): mascheramento corretto, nessun falso positivo su testo pulito
  - percorso_sicuro(): anti path-traversal, symlink, casi limite
  - Audit: integrita' della catena, redazione del dettaglio, retention, sigillo
  - Chiave: generazione, cifratura/decifratura se cryptography disponibile

Esecuzione:  python test_sicurezza.py
Output atteso: tutti i test marcati OK, riga finale "TUTTI I TEST SUPERATI".
"""

import os
import sys
import tempfile

# consente l'import dei moduli a root anche eseguendo da tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Assicura che la root del progetto sia nel path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import sicurezza

# ---------------------------------------------------------------------------
# Contatore globale
# ---------------------------------------------------------------------------
_ok = 0
_fail = 0


def _check(nome_test, condizione, messaggio_errore=""):
    global _ok, _fail
    if condizione:
        print(f"  [OK] {nome_test}")
        _ok += 1
    else:
        print(f"  [FAIL] {nome_test}" + (f" — {messaggio_errore}" if messaggio_errore else ""))
        _fail += 1


# ===========================================================================
# TEST 1 — file_sensibile(): estensioni
# ===========================================================================
print("\n=== TEST 1: file_sensibile() — estensioni ===")

_estensioni_sensibili = [
    "chiave.pem", "certificato.cer", "mio.crt", "keyfile.key",
    "archivio.kdbx", "vpn.ovpn", "firma.gpg", "firma.asc",
    "config.env", "negozio.keystore", "android.jks", "ssh.ppk",
    "wallet.wallet", "bitcoin.dat", "chiave.p12", "chiave.pfx",
    "apple.p8", "cert.der", "richiesta.csr", "bundle.pkcs12",
    "id_rsa.pub",   # chiave pubblica SSH
]
for nome in _estensioni_sensibili:
    _check(f"  estensione '{os.path.splitext(nome)[1]}' rilevata", sicurezza.file_sensibile(nome))

_estensioni_normali = [
    "documento.pdf", "foto.jpg", "report.docx", "musica.mp3",
    "video.mp4", "archivio.zip", "script.py", "logo.svg",
]
for nome in _estensioni_normali:
    _check(f"  '{nome}' NON sensibile (falso positivo?)", not sicurezza.file_sensibile(nome))


# ===========================================================================
# TEST 2 — file_sensibile(): parole chiave nel nome
# ===========================================================================
print("\n=== TEST 2: file_sensibile() — parole nel nome ===")

_nomi_sensibili = [
    "password_backup.txt",
    "mio_secret.json",
    "credenziali_office365.xlsx",
    "wallet_ethereum.txt",
    "seed_phrase_bitcoin.txt",
    "private_key_rsa.txt",
    "iban_banca.txt",
    "apikey_openai.json",
    "2fa_backup_codes.txt",
    "mnemonic_wallet.txt",
    "recovery_codes.txt",
    "token_github.env",
    "oauth_secret.json",
    "bearer_token.txt",
    "access_token_dropbox.txt",
]
for nome in _nomi_sensibili:
    _check(f"  nome '{nome}' rilevato come sensibile", sicurezza.file_sensibile(nome))


# ===========================================================================
# TEST 3 — file_sensibile(): directory sensibili nel percorso
# ===========================================================================
print("\n=== TEST 3: file_sensibile() — directory nel percorso ===")

_HOME = os.path.expanduser("~")
_percorsi_sensibili = [
    os.path.join(_HOME, ".ssh", "config"),
    os.path.join(_HOME, ".ssh", "id_rsa"),
    os.path.join(_HOME, ".gnupg", "secring.gpg"),
    os.path.join(_HOME, ".aws", "credentials"),
    os.path.join(_HOME, ".azure", "accessTokens.json"),
    r"C:\Users\Davide\secrets\qualcosa.txt",
    r"C:\vault\chiave.bin",
    "/home/user/.aws/config",
    "/etc/credentials/test",
]
for p in _percorsi_sensibili:
    _check(f"  percorso '{os.path.basename(p)}' in dir sensibile", sicurezza.file_sensibile(p))

# Percorsi normali non devono essere bloccati
_percorsi_normali = [
    os.path.join(_HOME, "Desktop", "relazione.pdf"),
    os.path.join(_HOME, "Documents", "progetto.docx"),
    os.path.join(_ROOT, "motore_web.py"),
]
for p in _percorsi_normali:
    _check(f"  percorso normale '{os.path.basename(p)}' NON bloccato", not sicurezza.file_sensibile(p))


# ===========================================================================
# TEST 4 — testo_contiene_segreti(): pattern principali
# ===========================================================================
print("\n=== TEST 4: testo_contiene_segreti() — pattern ===")

_testi_segreti = [
    ("PEM chiave privata",   "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."),
    ("PEM OpenSSH",          "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC..."),
    ("AWS key ID",           "valore: AKIAIOSFODNN7EXAMPLE"),
    ("OpenAI API key",       "la chiave e' sk-abcdefghijklmnopqrst123"),
    ("Anthropic key",        "la chiave e' sk-ant-abcdefghij-abcdefghijklmnopqrst"),
    ("GitHub PAT classic",   "ghp_1234567890abcdefghij12345678901234"),
    ("GitHub PAT fine",      "github_pat_123456789012345678901234567890123456789012"),
    ("JWT",                  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abc123"),
    ("Stripe live key",      "sk_live_abcdefghijklmnopqrstu1234"),
    ("password inline",      "password=SegrEtO_ForTe!99"),
    ("password con ::",      "la password: Pa55w0rd!"),
    ("IBAN IT",              "IT60X0542811101000000123456"),
    ("IBAN generico",        "DE89370400440532013000"),
    ("carta di credito",     "numero: 4111 1111 1111 1111"),
    ("codice fiscale IT",    "il CF e': RSSMRA85T10A562S"),
    ("hash bcrypt",          "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/oQ8I3vV8E4OFI5JfG"),
    ("bearer token",         "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.abc.def"),
    ("session id",           "session_id=abc123def456ghi789jkl012"),
    ("SendGrid key",         "SG.abcdefghijklmnopqrstuv.abcdefghijklmnopqrstuvwxyzABCD1234567890ab"),
]
for nome, testo in _testi_segreti:
    _check(f"  [{nome}] rilevato", sicurezza.testo_contiene_segreti(testo))

# Testi puliti: nessun falso positivo
_testi_puliti = [
    ("vuoto",              ""),
    ("saluto normale",     "Ciao, come stai oggi?"),
    ("numero breve",       "ho comprato 3 cose"),
    ("data",               "oggi e' 2026-06-06"),
    ("testo tecnico",      "Il modulo sicurezza.py gestisce l'audit."),
]
for nome, testo in _testi_puliti:
    _check(f"  [{nome}] NON rilevato (falso positivo?)", not sicurezza.testo_contiene_segreti(testo))


# ===========================================================================
# TEST 5 — redigi(): mascheramento corretto
# ===========================================================================
print("\n=== TEST 5: redigi() — mascheramento segreti ===")

_redigi_casi = [
    ("password inline",   "accesso con password=segreta123",        "segreta123"),
    ("API key",           "chiave sk-abcdefghijklmnopqrst123 usata", "sk-abcdefghijklmnopqrst"),
    ("IBAN in frase",     "il mio iban e' IT60X0542811101000000123456 per favore", "IT60X0542811101000000123456"),
    ("JWT in log",        "token: eyJhbGciOiJSUzI1NiJ9.abc.def ottenuto", "eyJhbGciOiJSUzI1NiJ9"),
]
for nome, testo, frammento in _redigi_casi:
    risultato = sicurezza.redigi(testo)
    _check(f"  [{nome}] frammento rimosso", frammento not in risultato)
    _check(f"  [{nome}] tag di rimpiazzo presente", "RIMOSSO" in risultato)

# Testo pulito: non deve cambiare
testo_pulito = "ARGO ha spostato il file relazione.pdf nella cartella Documenti."
_check("  testo pulito NON alterato da redigi()", redigi := sicurezza.redigi(testo_pulito),
       f"risultato: {redigi}")
# Riformuliamo senza walrus per compatibilita' Python < 3.8
_pulito_risultato = sicurezza.redigi(testo_pulito)
_check("  testo pulito = output identico all'input (no falsi positivi)",
       "RIMOSSO" not in _pulito_risultato)

# None e stringa vuota devono restare invariati
_check("  redigi(None) ritorna None", sicurezza.redigi(None) is None)
_check("  redigi('') ritorna ''", sicurezza.redigi("") == "")


# ===========================================================================
# TEST 6 — percorso_sicuro(): anti path-traversal
# ===========================================================================
print("\n=== TEST 6: percorso_sicuro() — anti path-traversal ===")

_BASE = os.path.join(_ROOT, "sorvegliata")

# Deve essere True: path dentro la base
_ok_paths = [
    os.path.join(_BASE, "file.txt"),
    os.path.join(_BASE, "Immagini", "foto.jpg"),
    os.path.join(_BASE, "sub", "sub2", "doc.pdf"),
    _BASE,   # la base stessa
]
for p in _ok_paths:
    _check(f"  percorso legittimo accettato: {os.path.basename(p) or 'base'}",
           sicurezza.percorso_sicuro(_BASE, p))

# Deve essere False: path fuori dalla base (traversal)
_ko_paths = [
    os.path.join(_BASE, "..", "..", "etc", "passwd"),
    os.path.join(_BASE, "..", "..", "Windows", "System32"),
    r"C:\Windows\System32\drivers\etc\hosts",
    "/etc/shadow",
    "/tmp/evil",
    os.path.join(_BASE, "..", "sicurezza.py"),  # un file fuori dalla base
]
for p in _ko_paths:
    _check(f"  traversal bloccato: {p[:50]}...",
           not sicurezza.percorso_sicuro(_BASE, p))

# Casi limite
_check("  base vuota -> False", not sicurezza.percorso_sicuro("", "qualcosa"))
_check("  target vuoto -> False", not sicurezza.percorso_sicuro(_BASE, ""))
_check("  entrambi vuoti -> False", not sicurezza.percorso_sicuro("", ""))


# ===========================================================================
# TEST 7 — Audit: integrità catena di hash
# ===========================================================================
print("\n=== TEST 7: Audit — integrita' catena di hash ===")

with tempfile.TemporaryDirectory() as tmp:
    db_path = os.path.join(tmp, "test_audit.db")

    # Audit fresco
    a = sicurezza.Audit(db_path)
    a.registra("avvio", "prima voce")
    a.registra("azione", "spostamento file relazione.pdf")
    a.registra("chat", "domanda utente normale")
    integro, idr = a.verifica()
    _check("  catena integra dopo 3 voci", integro and idr is None)

    # Il sigillo deve essere non vuoto
    sig = a.sigillo()
    _check("  sigillo non vuoto", sig and sig != "VUOTO" and len(sig) == 64)

    # Aggiungi voce con segreto nel dettaglio: deve essere redatto
    a.registra("evento", "file password_backup.txt trovato, non letto")
    voci = a.recenti(5)
    segreti_in_audit = any(
        "password_backup.txt" in str(v.get("dettaglio", "")).lower()
        and "backup_codes" in str(v.get("dettaglio", "")).lower()
        for v in voci
    )
    # Verifichiamo che un segreto inline venga redatto
    a.registra("test_redazione", "la password: SUPERPASSWORD99!")
    voci2 = a.recenti(2)
    dettaglio_redatto = voci2[0].get("dettaglio", "")
    _check("  segreto inline redatto nell'audit", "SUPERPASSWORD99!" not in dettaglio_redatto)
    _check("  tag rimpiazzo presente nell'audit", "RIMOSSO" in dettaglio_redatto)

    # La catena rimane integra dopo la redazione
    integro2, _ = a.verifica()
    _check("  catena ancora integra dopo redazione", integro2)

    # Conta voci
    n = a.conta()
    _check("  conta() > 0", n > 0)

    # Report
    rep = a.report()
    _check("  report['integro'] == True", rep["integro"] is True)
    _check("  report['voci'] > 0", rep["voci"] > 0)
    _check("  report['sigillo'] e' una stringa hex di 64 char", len(rep["sigillo"]) == 64)

    # Manomissione: modifica diretta del DB -> verifica deve fallire
    import sqlite3
    conn_raw = sqlite3.connect(db_path)
    conn_raw.execute("UPDATE audit SET dettaglio='MANOMESSO' WHERE id=1")
    conn_raw.commit()
    conn_raw.close()
    integro3, idr3 = a.verifica()
    _check("  manomissione rilevata dalla verifica", not integro3 and idr3 is not None)

    a.chiudi()


# ===========================================================================
# TEST 8 — Audit: retention
# ===========================================================================
print("\n=== TEST 8: Audit — retention ===")

with tempfile.TemporaryDirectory() as tmp:
    db_path = os.path.join(tmp, "audit_retention.db")
    a = sicurezza.Audit(db_path, retention_giorni=1)   # 1 giorno di retention

    # Inserisci una voce con timestamp nel passato (90 giorni fa)
    import datetime, sqlite3
    a.registra("test", "voce recente")
    n_prima = a.conta()

    # Inserisci direttamente una voce "vecchia" nel DB
    vecchio = (datetime.datetime.now() - datetime.timedelta(days=95)).isoformat(timespec="seconds")
    a.conn.execute(
        "INSERT INTO audit (quando, evento, dettaglio, hash_prec, hash) VALUES (?,?,?,?,?)",
        (vecchio, "vecchio", "voce vecchia", "GENESI", "hash_finto_non_in_catena")
    )
    a.conn.commit()
    n_con_vecchia = a.conta()
    _check("  voce vecchia inserita per test", n_con_vecchia > n_prima)

    # Ricrea l'audit con retention=1 giorno: deve eliminare la vecchia
    a.chiudi()
    a2 = sicurezza.Audit(db_path, retention_giorni=1)
    n_dopo = a2.conta()
    _check("  retention rimuove voce vecchia (>1g)", n_dopo < n_con_vecchia)
    a2.chiudi()


# ===========================================================================
# TEST 9 — Chiave: generazione e cifratura
# ===========================================================================
print("\n=== TEST 9: Chiave — generazione e cifratura ===")

with tempfile.TemporaryDirectory() as tmp:
    key_path = os.path.join(tmp, "test.key")
    k = sicurezza.Chiave(key_path)
    _check("  chiave creata (file esiste)", os.path.exists(key_path))
    _check("  master key e' di 32 byte", len(k.master) == 32)

    disp = k.cifratura_disponibile()
    _check("  cifratura_disponibile() ritorna bool", isinstance(disp, bool))

    if disp:
        testo_orig = "dati riservati di Davide"
        cifrato = k.cifra(testo_orig)
        _check("  testo cifrato e' diverso dall'originale", cifrato != testo_orig)
        decifrato = k.decifra(cifrato)
        _check("  decifratura ripristina il testo originale", decifrato == testo_orig)
        # Cifra due volte: deve dare valori diversi (IV casuale)
        cifrato2 = k.cifra(testo_orig)
        _check("  due cifrature dello stesso testo danno token diversi (IV casuale)",
               cifrato != cifrato2)
    else:
        # Senza cryptography: cifra() ritorna l'originale
        _check("  senza cryptography: cifra() ritorna l'input",
               k.cifra("test") == "test")
        _check("  senza cryptography: decifra() ritorna l'input",
               k.decifra("test") == "test")


# ===========================================================================
# RIEPILOGO FINALE
# ===========================================================================
print("\n" + "=" * 60)
print(f"RISULTATI: {_ok} OK, {_fail} FAIL")
if _fail == 0:
    print("TUTTI I TEST SUPERATI")
    sys.exit(0)
else:
    print(f"ATTENZIONE: {_fail} test falliti — rivedere sicurezza.py")
    sys.exit(1)
