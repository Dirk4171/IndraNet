"""
IndraNet — Netzweg
===================

Jeder Abruf nach draußen läuft durch dieses Modul. Es gibt keinen zweiten
Weg — wer im Code eine Webseite holen will, bekommt seinen Client von hier.

WARUM DAS ZÄHLT
---------------
Öffentliche Daten zu recherchieren ist nicht geheim. Dass SIE es tun,
schon. Ein Firmenregister, das zehn Abrufe zu derselben Briefkastenfirma
aus einem Redaktionsnetz sieht, weiß, dass jemand fragt. Wer eine
Zielperson recherchiert, verrät sich über die eigene IP-Adresse.

DREI WEGE
---------
direkt   ohne Verschleierung — schnell, für unkritische Recherchen
tor      über den mitgestarteten Tor-Dienst (SOCKS5, DNS über Tor)
proxy    über einen eigenen SOCKS5- oder HTTP-Proxy (VPN-Anbieter u. a.)

GESCHLOSSEN STATT OFFEN
-----------------------
Ist Tor gewählt, aber nicht verbunden, schlägt der Abruf fehl. Er fällt
nicht still auf den direkten Weg zurück — eine Verschleierung, die
gelegentlich aussetzt, ist schlimmer als keine, weil man sich auf sie
verlässt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx2 as httpx

# Gleiche Kennung wie der Tor Browser: Wer über Tor abruft, soll in der
# Menge der Tor-Browser-Nutzer verschwinden, nicht als Python-Skript
# auffallen.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; rv:128.0) "
              "Gecko/20100101 Firefox/128.0")
MAX_BYTES = 8 * 1024 * 1024


class NetzwegFehler(Exception):
    """Der gewählte Netzweg steht nicht zur Verfügung."""


@dataclass
class Antwort:
    url: str
    status: int
    typ: str
    inhalt: bytes

    @property
    def text(self) -> str:
        roh = self.inhalt
        m = re.search(rb'charset=["\']?([\w-]+)', roh[:2048])
        for kodierung in ([m.group(1).decode()] if m else []) + ["utf-8",
                                                                  "latin-1"]:
            try:
                return roh.decode(kodierung)
            except (UnicodeDecodeError, LookupError):
                continue
        return roh.decode("utf-8", "replace")

    @property
    def domain(self) -> str:
        return domain_von(self.url)


def domain_von(url: str) -> str:
    host = (urlparse(url).hostname or url).lower()
    return host[4:] if host.startswith("www.") else host


class Netzweg:
    """Erzeugt Clients für den eingestellten Weg."""

    def __init__(self, einstellungen, tor=None):
        self.einst = einstellungen
        self.tor = tor          # TorDienst oder None

    # ------------------------------------------------------------ Auskunft
    @property
    def modus(self) -> str:
        return self.einst.get("netzweg") or "direkt"

    def proxy(self) -> str | None:
        """Proxy-Adresse oder None für direkt. Wirft, wenn der gewählte Weg
        nicht steht."""
        if self.modus == "tor":
            if self.tor is None or not self.tor.bereit:
                raise NetzwegFehler(
                    "Tor ist gewählt, aber nicht verbunden. Abruf "
                    "abgebrochen — kein Rückfall auf die direkte Verbindung.")
            return f"socks5://127.0.0.1:{self.tor.socks_port}"
        if self.modus == "proxy":
            url = (self.einst.get("proxy_url") or "").strip()
            if not url:
                raise NetzwegFehler("Proxy gewählt, aber keine Adresse "
                                    "eingetragen.")
            return url
        return None

    def beschreibung(self) -> dict:
        try:
            p = self.proxy()
            bereit = True
            fehler = None
        except NetzwegFehler as e:
            p, bereit, fehler = None, False, str(e)
        return {"modus": self.modus, "bereit": bereit, "fehler": fehler,
                "proxy": (p.split("@")[-1] if p else None)}

    # ------------------------------------------------------------- Clients
    def client(self, timeout: float = 30.0, **kw) -> httpx.Client:
        if self.modus == "tor":
            timeout = max(timeout, 75.0)     # Tor-Kreise sind langsamer
        return httpx.Client(
            proxy=self.proxy(), timeout=timeout, follow_redirects=True,
            headers={"User-Agent": USER_AGENT,
                     "Accept-Language": "de,en;q=0.8"}, **kw)

    def ki_proxy(self) -> str | None:
        """Proxy für KI-Anfragen. Lokale Modelle (Ollama) laufen nie über
        den Proxy — sie verlassen den Rechner gar nicht."""
        if not self.einst.get("ki_ueber_proxy"):
            return None
        return self.proxy()

    # ------------------------------------------------------------- Abrufen
    def abrufen(self, url: str, *, timeout: float = 30.0,
                max_bytes: int = MAX_BYTES, params: dict | None = None,
                headers: dict | None = None) -> Antwort:
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("nur http(s)-Adressen")
        with self.client(timeout=timeout) as c:
            with c.stream("GET", url, params=params,
                          headers=headers or {}) as r:
                teile, n = [], 0
                for stueck in r.iter_bytes():
                    teile.append(stueck)
                    n += len(stueck)
                    if n > max_bytes:
                        break
                return Antwort(str(r.url), r.status_code,
                               r.headers.get("content-type", ""),
                               b"".join(teile)[:max_bytes])

    def json(self, url: str, *, params: dict | None = None,
             timeout: float = 30.0, headers: dict | None = None):
        a = self.abrufen(url, params=params, timeout=timeout,
                         headers={"Accept": "application/json",
                                  **(headers or {})})
        if a.status >= 400:
            raise NetzwegFehler(f"{a.domain}: HTTP {a.status}")
        import json as _json
        return _json.loads(a.text)

    def pruefen(self) -> dict:
        """Fragt check.torproject.org, unter welcher Adresse wir erscheinen."""
        try:
            d = self.json("https://check.torproject.org/api/ip", timeout=60)
            return {**self.beschreibung(), "ok": True,
                    "ist_tor": bool(d.get("IsTor")), "ip": d.get("IP")}
        except Exception as e:                              # noqa: BLE001
            return {**self.beschreibung(), "ok": False,
                    "fehler": str(e) or e.__class__.__name__}
