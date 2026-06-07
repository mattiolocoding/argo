"""
ARGO - sensi.py
Sistema nervoso esteso: finestra attiva, stato rete, info appunti,
processi in foreground, batteria, file recenti, ora/giorno.
Solo lettura / osservazione. Nessun contenuto sensibile viene restituito.
Solo libreria standard + ctypes su Windows. Tutto best-effort: None/[] se
la piattaforma non supporta.

Prova:  python sensi.py
        python -m sensi
"""

import os
import time
import socket
import subprocess


# ──────────────────────────────────────────────
# Sezione Windows: importazione ctypes difensiva
# ──────────────────────────────────────────────

_user32 = None
_kernel32 = None
_ctypes = None

if os.name == "nt":
    try:
        import ctypes
        import ctypes.wintypes
        _ctypes = ctypes
        _user32 = ctypes.windll.user32
        _kernel32 = ctypes.windll.kernel32
    except Exception:
        pass  # Non critico: le funzioni restituiranno None


# ──────────────────────────────────────────────
# Euristiche per contenuto sospetto/sensibile
# ──────────────────────────────────────────────

# Parole chiave che suggeriscono la presenza di dati sensibili nel testo
_KEYWORD_SOSPETTI = [
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "privatekey", "auth", "credential", "bearer",
    "-----BEGIN",   # intestazione PEM (chiave privata/certificato)
    "ghp_", "ghs_", # token GitHub
    "sk-",          # token OpenAI
    "eyJ",          # JWT (Base64 header tipico)
]

# Lunghezza minima oltre cui una stringa senza spazi e' sospetta (es. hash/token)
_LUNGHEZZA_TOKEN_MIN = 30


def _sembra_sensibile(testo: str) -> bool:
    """
    Euristica veloce: ritorna True se il testo assomiglia a
    una password, chiave API, token o certificato.
    Non legge oltre il necessario: si ferma al primo indizio.
    """
    if not testo:
        return False
    testo_lower = testo.lower()
    # Controllo keyword esplicite
    for kw in _KEYWORD_SOSPETTI:
        if kw.lower() in testo_lower:
            return True
    # Stringa lunga senza spazi = possibile hash/token/password
    if len(testo) >= _LUNGHEZZA_TOKEN_MIN and " " not in testo.strip():
        return True
    return False


# ──────────────────────────────────────────────
# Funzione 1: finestra in primo piano
# ──────────────────────────────────────────────

def finestra_attiva() -> str | None:
    """
    Titolo della finestra in primo piano.
    Windows: ctypes user32 GetForegroundWindow + GetWindowTextW.
    Altre piattaforme: None (best-effort, non crashare).
    """
    if os.name != "nt" or _user32 is None or _ctypes is None:
        return None
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        # Buffer di 512 caratteri wide
        buf = _ctypes.create_unicode_buffer(512)
        _user32.GetWindowTextW(hwnd, buf, 512)
        titolo = buf.value.strip()
        return titolo if titolo else None
    except Exception:
        return None


# ──────────────────────────────────────────────
# Funzione 2: connettivita' di rete
# ──────────────────────────────────────────────

def rete_attiva(host: str = "8.8.8.8", porta: int = 53, timeout: float = 1.5) -> bool:
    """
    Controlla se c'e' connessione internet aprendo un socket TCP
    verso un DNS pubblico (Google 8.8.8.8:53). Non scarica nulla.
    Ritorna True se raggiungibile, False altrimenti.
    """
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# Funzione 3: tipo di connessione di rete (best-effort Windows)
# ──────────────────────────────────────────────

def tipo_rete() -> str | None:
    """
    Tipo di connessione attiva: 'wifi', 'ethernet', 'vpn' o None.
    Windows: usa netsh via subprocess con timeout e try/except.
    Restituisce None se non determinabile o su piattaforme diverse.
    """
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True, timeout=4,
        )
        # Decodifica robusta: ignora caratteri non-ASCII
        testo = out.stdout.decode("utf-8", errors="replace")
        testo_lower = testo.lower()
        # Cerca interfacce connesse nell'output
        tipo_trovato = None
        for riga in testo_lower.splitlines():
            if "connected" not in riga and "connessa" not in riga:
                continue
            if "wi-fi" in riga or "wireless" in riga or "wlan" in riga:
                tipo_trovato = "wifi"
                break
            if "vpn" in riga or "tunnel" in riga or "tap" in riga or "tun" in riga:
                tipo_trovato = "vpn"
                break
            if "ethernet" in riga or "local area" in riga or "lan" in riga:
                tipo_trovato = "ethernet"
                # Non fare break subito: se c'e' anche wifi, preferisce wifi
        return tipo_trovato
    except Exception:
        return None


# ──────────────────────────────────────────────
# Funzione 4: info sugli appunti (senza contenuto)
# ──────────────────────────────────────────────

def appunti_info() -> dict:
    """
    Metadati sugli appunti di sistema. NON restituisce il contenuto.
    Ritorna dict: {ha_testo, lunghezza, sospetto_sensibile}.
    Se 'sospetto_sensibile' e' True la lunghezza viene omessa per privacy.
    Windows: ctypes user32 OpenClipboard / GetClipboardData.
    Altre piattaforme: best-effort con xclip/xsel/pbpaste via subprocess,
    oppure fallback a valori None.
    """
    risultato = {
        "ha_testo": False,
        "lunghezza": None,
        "sospetto_sensibile": False,
    }

    if os.name == "nt":
        risultato = _appunti_windows(risultato)
    else:
        risultato = _appunti_unix(risultato)

    return risultato


def _appunti_windows(risultato: dict) -> dict:
    """Legge metadati appunti su Windows via ctypes."""
    if _user32 is None or _ctypes is None:
        return risultato
    try:
        CF_UNICODETEXT = 13  # formato testo Unicode standard
        # Prova ad aprire gli appunti (max 5 tentativi veloci)
        aperto = False
        for _ in range(5):
            if _user32.OpenClipboard(0):
                aperto = True
                break
            time.sleep(0.05)
        if not aperto:
            return risultato

        try:
            h = _user32.GetClipboardData(CF_UNICODETEXT)
            if h:
                risultato["ha_testo"] = True
                # Blocca l'handle per leggere solo i primi N caratteri
                ptr = _kernel32.GlobalLock(h)
                if ptr:
                    try:
                        # Legge i primi 200 caratteri: basta per l'euristica
                        campione = _ctypes.wstring_at(ptr, 200) if ptr else ""
                    except Exception:
                        campione = ""
                    finally:
                        _kernel32.GlobalUnlock(h)

                    sospetto = _sembra_sensibile(campione)
                    risultato["sospetto_sensibile"] = sospetto

                    if not sospetto:
                        # Dimensione reale in byte del blocco di memoria
                        size_bytes = _kernel32.GlobalSize(h)
                        # Ogni carattere Unicode = 2 byte; -1 per il null finale
                        risultato["lunghezza"] = max(0, size_bytes // 2 - 1)
                    # Se sospetto: lunghezza rimane None per non rivelare info
        finally:
            _user32.CloseClipboard()
    except Exception:
        pass  # Fallback silenzioso
    return risultato


def _appunti_unix(risultato: dict) -> dict:
    """
    Best-effort su Linux/macOS: prova xclip, xsel o pbpaste.
    Legge solo i primi 200 caratteri per l'euristica di sensibilita'.
    """
    comandi = [
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
        ["pbpaste"],  # macOS
    ]
    for cmd in comandi:
        try:
            out = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if out.returncode == 0:
                testo = out.stdout
                risultato["ha_testo"] = bool(testo)
                sospetto = _sembra_sensibile(testo[:200])
                risultato["sospetto_sensibile"] = sospetto
                if not sospetto:
                    risultato["lunghezza"] = len(testo)
                return risultato
        except Exception:
            continue
    return risultato


# ──────────────────────────────────────────────
# Funzione 5: processi in foreground / principali
# ──────────────────────────────────────────────

# Nomi di processo da escludere: processi di sistema rumorosi
_PROCESSI_SISTEMA = {
    "system", "system idle process", "registry", "smss.exe",
    "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "svchost.exe", "dwm.exe", "conhost.exe",
    "fontdrvhost.exe", "sihost.exe", "taskhostw.exe",
    "spoolsv.exe", "searchindexer.exe", "wuauclt.exe",
    "mscorsvw.exe", "ngen.exe", "dllhost.exe",
}


def processi_foreground(n: int = 8) -> list[dict]:
    """
    Lista delle app principali in esecuzione (non di sistema).
    Usa tasklist su Windows (subprocess con timeout e try/except).
    Ritorna lista di dict {nome, mem_mb}: al massimo n elementi.
    Nessuna info sensibile: solo nome del processo e memoria.
    """
    if os.name != "nt":
        return _processi_unix(n)

    try:
        out = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, timeout=8,
        )
        # Decodifica robusta (CP1252 / UTF-8 / fallback)
        try:
            testo = out.stdout.decode("utf-8")
        except UnicodeDecodeError:
            try:
                testo = out.stdout.decode("cp1252")
            except UnicodeDecodeError:
                testo = out.stdout.decode("latin-1", errors="replace")

        visti: dict[str, float] = {}
        for ln in testo.splitlines():
            parti = [p.strip('"') for p in ln.split('","')]
            if len(parti) < 5:
                continue
            nome = parti[0].lower()
            if nome in _PROCESSI_SISTEMA:
                continue
            mem_str = parti[4]
            kb = int("".join(ch for ch in mem_str if ch.isdigit()) or 0)
            mb = round(kb / 1024, 1)
            # Se il processo compare piu' volte, somma la memoria
            visti[parti[0]] = visti.get(parti[0], 0.0) + mb

        # Ordina per memoria decrescente
        ordinati = sorted(visti.items(), key=lambda x: x[1], reverse=True)
        return [{"nome": nm, "mem_mb": mem} for nm, mem in ordinati[:n]]
    except Exception:
        return []


def _processi_unix(n: int) -> list[dict]:
    """Fallback Unix: ps per i processi principali."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "comm,rss", "--sort=-rss"],
            capture_output=True, timeout=6,
        )
        testo = out.stdout.decode("utf-8", errors="replace")
        risultati = []
        for ln in testo.splitlines()[1:]:
            parti = ln.split()
            if len(parti) >= 2:
                nome = parti[0]
                if nome.lower() in _PROCESSI_SISTEMA:
                    continue
                risultati.append({"nome": nome, "mem_mb": round(int(parti[1]) / 1024, 1)})
                if len(risultati) >= n:
                    break
        return risultati
    except Exception:
        return []


# ──────────────────────────────────────────────
# Funzione 6: stato batteria
# ──────────────────────────────────────────────

def batteria() -> dict | None:
    """
    Stato della batteria. Ritorna dict {percentuale, in_carica, presente}
    oppure None se non applicabile (PC fisso senza batteria).
    Windows: ctypes GetSystemPowerStatus.
    """
    if os.name != "nt" or _ctypes is None:
        return _batteria_unix()

    try:
        class SYSTEM_POWER_STATUS(_ctypes.Structure):
            _fields_ = [
                ("ACLineStatus",        _ctypes.c_byte),
                ("BatteryFlag",         _ctypes.c_byte),
                ("BatteryLifePercent",  _ctypes.c_byte),
                ("SystemStatusFlag",    _ctypes.c_byte),
                ("BatteryLifeTime",     _ctypes.c_uint),
                ("BatteryFullLifeTime", _ctypes.c_uint),
            ]

        sps = SYSTEM_POWER_STATUS()
        ok = _ctypes.windll.kernel32.GetSystemPowerStatus(_ctypes.byref(sps))
        if not ok:
            return None

        # BatteryFlag 128 = nessuna batteria / PC fisso
        if sps.BatteryFlag == 128:
            return {"presente": False}

        # BatteryLifePercent 255 = sconosciuta
        perc = sps.BatteryLifePercent if sps.BatteryLifePercent != 255 else None
        in_carica = (sps.ACLineStatus == 1)

        return {
            "presente": True,
            "percentuale": perc,
            "in_carica": in_carica,
        }
    except Exception:
        return None


def _batteria_unix() -> dict | None:
    """Best-effort batteria su Linux/macOS via /sys o pmset."""
    # Linux: legge /sys/class/power_supply
    try:
        base = "/sys/class/power_supply"
        if os.path.isdir(base):
            for entry in os.listdir(base):
                cap_path = os.path.join(base, entry, "capacity")
                stat_path = os.path.join(base, entry, "status")
                if os.path.isfile(cap_path):
                    with open(cap_path) as f:
                        perc = int(f.read().strip())
                    in_carica = False
                    if os.path.isfile(stat_path):
                        with open(stat_path) as f:
                            in_carica = "charging" in f.read().strip().lower()
                    return {"presente": True, "percentuale": perc, "in_carica": in_carica}
    except Exception:
        pass
    # macOS: pmset
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, timeout=3)
        testo = out.stdout.decode("utf-8", errors="replace")
        import re
        m = re.search(r"(\d+)%", testo)
        if m:
            perc = int(m.group(1))
            in_carica = "charging" in testo.lower()
            return {"presente": True, "percentuale": perc, "in_carica": in_carica}
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# Funzione 7: file recenti (Recent Items di Windows)
# ──────────────────────────────────────────────

def file_recenti_info() -> dict:
    """
    Metadati sui file recenti da %APPDATA%\\Microsoft\\Windows\\Recent.
    NON legge i contenuti, solo i nomi dei .lnk (shortcut).
    Filtra i nomi sensibili tramite sicurezza.file_sensibile.
    Ritorna dict {totale, non_sensibili, nomi_visibili}.
    """
    risultato = {"totale": 0, "non_sensibili": 0, "nomi_visibili": []}

    if os.name != "nt":
        return risultato

    try:
        # Importa file_sensibile da sicurezza (solo lettura)
        try:
            import sys as _sys
            _dir_argo = os.path.dirname(os.path.abspath(__file__))
            if _dir_argo not in _sys.path:
                _sys.path.insert(0, _dir_argo)
            from sicurezza import file_sensibile as _file_sensibile
        except Exception:
            # Fallback: funzione minima locale se sicurezza.py non e' disponibile
            def _file_sensibile(p: str) -> bool:
                parole = ("password", "secret", "token", "key", "credential",
                          "passwd", "private", "wallet", "seed")
                nome = os.path.basename(p).lower()
                return any(kw in nome for kw in parole)

        recent_dir = os.path.join(
            os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent"
        )
        if not os.path.isdir(recent_dir):
            return risultato

        nomi_visibili = []
        totale = 0

        for entry in os.scandir(recent_dir):
            if not entry.is_file():
                continue
            nome = entry.name
            # I file recenti sono .lnk; salta file nascosti / di sistema
            if nome.startswith("."):
                continue
            totale += 1
            # Rimuove l'estensione .lnk per ottenere il nome originale
            nome_base = nome
            if nome_base.lower().endswith(".lnk"):
                nome_base = nome_base[:-4]

            # Controlla se il nome (senza estensione) e' sensibile
            if not _file_sensibile(nome_base):
                # Filtra ulteriormente: niente caratteri strani / troppo lunghi
                # (evita garbage nei .lnk di sistema)
                if len(nome_base) <= 80 and nome_base.isprintable():
                    nomi_visibili.append(nome_base)

        # Ordina alfabeticamente per output stabile
        nomi_visibili.sort()

        risultato["totale"] = totale
        risultato["non_sensibili"] = len(nomi_visibili)
        risultato["nomi_visibili"] = nomi_visibili[:20]  # max 20 nomi

    except Exception:
        pass  # Fallback silenzioso

    return risultato


# ──────────────────────────────────────────────
# Funzione 8: ora e giorno contestuale
# ──────────────────────────────────────────────

def ora_contestuale() -> dict:
    """
    Ora e contesto temporale normalizzato.
    Ritorna dict {timestamp, iso, ora, minuto, giorno_settimana,
                  fascia_giorno, giorno_lavorativo}.
    Fascia giorno: 'notte', 'mattina', 'pomeriggio', 'sera'.
    """
    t = time.localtime()
    ora = t.tm_hour
    giorno_iso = t.tm_wday  # 0=lunedi, 6=domenica

    if 0 <= ora < 6:
        fascia = "notte"
    elif 6 <= ora < 13:
        fascia = "mattina"
    elif 13 <= ora < 18:
        fascia = "pomeriggio"
    else:
        fascia = "sera"

    giorni = ["lunedi", "martedi", "mercoledi", "giovedi",
              "venerdi", "sabato", "domenica"]

    return {
        "timestamp": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", t),
        "ora": ora,
        "minuto": t.tm_min,
        "giorno_settimana": giorni[giorno_iso],
        "fascia_giorno": fascia,
        "giorno_lavorativo": giorno_iso < 5,  # lun-ven
    }


# ──────────────────────────────────────────────
# Funzione 9: stato rete completo
# ──────────────────────────────────────────────

def stato_rete() -> dict:
    """
    Stato di rete completo: online/offline + tipo interfaccia.
    Ritorna dict {online, tipo}.
    """
    online = rete_attiva()
    tipo = tipo_rete() if online else None
    return {
        "online": online,
        "tipo": tipo,
    }


# ──────────────────────────────────────────────
# Funzione 10: istantanea unificata
# ──────────────────────────────────────────────

def istantanea() -> dict:
    """
    Evento normalizzato con timestamp che raccoglie tutti i sensi:
    finestra attiva, stato rete, info appunti, processi principali,
    batteria, file recenti, ora/giorno.

    Campi garantiti (sempre presenti, anche se None/vuoti):
      timestamp, timestamp_iso, finestra_attiva, rete_attiva, appunti,
      rete, processi, batteria, file_recenti, ora.
    """
    ora = ora_contestuale()
    return {
        # Campi originali (compatibilita' garantita)
        "timestamp": ora["timestamp"],
        "timestamp_iso": ora["iso"],
        "finestra_attiva": finestra_attiva(),
        "rete_attiva": rete_attiva(),          # bool (retrocompatibilita')
        "appunti": appunti_info(),
        # Nuovi campi
        "rete": stato_rete(),                  # dict {online, tipo}
        "processi": processi_foreground(),     # lista app principali
        "batteria": batteria(),                # dict o None
        "file_recenti": file_recenti_info(),   # dict con conteggio e nomi
        "ora": ora,                            # dict temporale completo
    }


# ──────────────────────────────────────────────
# Classe Sensi
# ──────────────────────────────────────────────

class Sensi:
    """
    Interfaccia orientata agli oggetti per i sensi di ARGO.
    Chiama le funzioni del modulo e restituisce un'istantanea.
    """

    def istantanea(self) -> dict:
        """Ritorna un dict con tutti i dati sensoriali del momento."""
        return istantanea()

    def finestra(self) -> str | None:
        """Titolo della finestra in primo piano."""
        return finestra_attiva()

    def rete(self) -> bool:
        """True se c'e' connessione internet."""
        return rete_attiva()

    def appunti(self) -> dict:
        """Metadati sugli appunti, senza contenuto sensibile."""
        return appunti_info()

    def processi(self, n: int = 8) -> list:
        """Lista delle app principali in esecuzione."""
        return processi_foreground(n)

    def batteria_stato(self) -> dict | None:
        """Stato batteria o None se non presente."""
        return batteria()

    def recenti(self) -> dict:
        """Metadati sui file recenti (solo conteggio e nomi non sensibili)."""
        return file_recenti_info()

    def ora(self) -> dict:
        """Ora e contesto temporale."""
        return ora_contestuale()


# ──────────────────────────────────────────────
# Smoke-test: python sensi.py  /  python -m sensi
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # Nota: usiamo solo ASCII nei print per evitare crash su CP1252
    print("=== ARGO sensi.py -- smoke-test ===")

    titolo = finestra_attiva()
    # Codifica sicura: sostituisce caratteri non-ASCII con '?'
    titolo_safe = (titolo.encode("ascii", errors="replace").decode("ascii")
                   if titolo else None)
    print("Finestra attiva  :", repr(titolo_safe))

    rete_ok = rete_attiva()
    print("Rete attiva      :", rete_ok)

    t_rete = tipo_rete()
    print("Tipo rete        :", t_rete)

    clip = appunti_info()
    print("Appunti          :", clip)

    proc = processi_foreground(5)
    print("Processi top (5) :", len(proc), "trovati")
    for p in proc:
        nome_safe = p["nome"].encode("ascii", errors="replace").decode("ascii")
        print("  -", nome_safe, p["mem_mb"], "MB")

    batt = batteria()
    print("Batteria         :", batt)

    recenti = file_recenti_info()
    print("File recenti     : totale=%d non-sensibili=%d" % (
        recenti["totale"], recenti["non_sensibili"]
    ))

    ora = ora_contestuale()
    print("Ora              :", ora["iso"], ora["fascia_giorno"])

    # Istantanea completa
    snap = istantanea()
    assert "timestamp" in snap, "campo timestamp mancante"
    assert "timestamp_iso" in snap, "campo timestamp_iso mancante"
    assert "finestra_attiva" in snap, "campo finestra_attiva mancante"
    assert "rete_attiva" in snap, "campo rete_attiva mancante"
    assert "appunti" in snap, "campo appunti mancante"
    assert "rete" in snap, "campo rete mancante"
    assert "processi" in snap, "campo processi mancante"
    assert "batteria" in snap, "campo batteria mancante"
    assert "file_recenti" in snap, "campo file_recenti mancante"
    assert "ora" in snap, "campo ora mancante"
    assert isinstance(snap["rete_attiva"], bool), "rete_attiva deve essere bool"
    assert isinstance(snap["processi"], list), "processi deve essere lista"
    assert isinstance(snap["appunti"], dict), "appunti deve essere dict"
    assert isinstance(snap["file_recenti"], dict), "file_recenti deve essere dict"
    assert isinstance(snap["ora"], dict), "ora deve essere dict"

    # Test via classe
    s = Sensi()
    snap2 = s.istantanea()
    assert "finestra_attiva" in snap2, "classe: finestra_attiva mancante"
    assert "rete_attiva" in snap2, "classe: rete_attiva mancante"
    assert "appunti" in snap2, "classe: appunti mancante"
    assert isinstance(s.processi(3), list), "classe: processi deve essere lista"
    assert isinstance(s.recenti(), dict), "classe: recenti deve essere dict"
    assert isinstance(s.ora(), dict), "classe: ora deve essere dict"

    print("OK")
