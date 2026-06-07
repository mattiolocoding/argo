"""
ARGO - connettori/ricerca_web.py
Ricerca web controllata in sola lettura.

Non scarica file, non apre pagine arbitrarie e non naviga da solo: restituisce
solo titoli/link/snippet da una ricerca esplicitamente richiesta.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

try:
    from .base import Connettore
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from connettori.base import Connettore

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import sicurezza as _sec
except Exception:
    _sec = None

_DIR_ARGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILE_CONFIG = os.path.join(_DIR_ARGO, "config", "connettori.json")
_ULTIMA_RICERCA = 0.0


def _carica_config() -> dict:
    try:
        with open(_FILE_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _limita_testo(v: object, max_len: int) -> str:
    s = str(v or "").strip()
    s = re.sub(r"\s+", " ", s)
    if _sec:
        s = _sec.redigi(s)
    return s[:max_len]


class _DuckParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.risultati = []
        self._in_link = False
        self._in_snippet = False
        self._titolo = ""
        self._snippet = ""
        self._href = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = attrs.get("class", "")
        if tag == "a" and "result__a" in cls:
            self._in_link = True
            self._titolo = ""
            self._href = attrs.get("href", "")
        elif tag in ("a", "div") and "result__snippet" in cls:
            self._in_snippet = True
            self._snippet = ""

    def handle_data(self, data):
        if self._in_link:
            self._titolo += data
        elif self._in_snippet:
            self._snippet += data

    def handle_endtag(self, tag):
        if self._in_link and tag == "a":
            titolo = html.unescape(self._titolo).strip()
            link = self._normalizza_link(self._href)
            if titolo and link:
                self.risultati.append({"titolo": titolo, "url": link, "snippet": ""})
            self._in_link = False
        elif self._in_snippet and tag in ("a", "div"):
            snippet = html.unescape(self._snippet).strip()
            if snippet and self.risultati:
                self.risultati[-1]["snippet"] = snippet
            self._in_snippet = False

    @staticmethod
    def _normalizza_link(href: str) -> str:
        if not href:
            return ""
        if href.startswith("//duckduckgo.com/l/?"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse("https:" + href).query)
            return qs.get("uddg", [""])[0]
        if href.startswith("/l/?"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            return qs.get("uddg", [""])[0]
        return href


class ConnettoreRicercaWeb(Connettore):
    @property
    def nome(self) -> str:
        return "ricerca_web"

    @property
    def descrizione(self) -> str:
        return "Cerca online in sola lettura, con query limitata e risultati sintetici."

    def disponibile(self) -> bool:
        cfg = _carica_config().get("ricerca_web", {})
        return bool(cfg.get("abilitata", True))

    def leggi(self, parametri: dict | None = None) -> list | dict:
        global _ULTIMA_RICERCA

        if not self.disponibile():
            return {"errore": "Ricerca web disabilitata in config/connettori.json."}

        p = parametri or {}
        query = _limita_testo(p.get("query", ""), 180)
        if not query:
            return {"errore": "Query mancante."}

        if _sec and _sec.testo_contiene_segreti(query):
            return {"errore": "Query bloccata: contiene dati sensibili o segreti."}

        adesso = time.time()
        if adesso - _ULTIMA_RICERCA < 5:
            return {"errore": "Rate limit: attendi qualche secondo prima di una nuova ricerca."}
        _ULTIMA_RICERCA = adesso

        max_risultati = max(1, min(int(p.get("max_risultati", 5)), 8))
        url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ARGO-local-research/1.0",
                "Accept": "text/html",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                corpo = resp.read(512_000).decode("utf-8", errors="replace")
        except Exception as e:
            return {
                "errore": (
                    "Ricerca online non riuscita. Verifica connessione o firewall. "
                    f"Dettaglio: {e}"
                )
            }

        parser = _DuckParser()
        parser.feed(corpo)
        risultati = []
        for r in parser.risultati[:max_risultati]:
            risultati.append({
                "titolo": _limita_testo(r.get("titolo"), 160),
                "url": _limita_testo(r.get("url"), 300),
                "snippet": _limita_testo(r.get("snippet"), 320),
            })

        return {
            "query": query,
            "fonte": "duckduckgo_html",
            "risultati": risultati,
            "nota": "Risultati non scaricati: ARGO conserva solo titolo, link e snippet.",
        }


if __name__ == "__main__":
    c = ConnettoreRicercaWeb()
    print(f"{c.nome}: {'disponibile' if c.disponibile() else 'non disponibile'}")
    r = c.leggi({"query": "ARGO intelligenza artificiale locale", "max_risultati": 2})
    if "errore" in r:
        print(r["errore"])
    else:
        print(f"OK ricerca: {len(r.get('risultati', []))} risultati")
