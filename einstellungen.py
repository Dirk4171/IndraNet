"""
IndraNet — Einstellungen
=========================

Installationsweite Einstellungen: KI-Anbieter, Netzweg, Sprache, Thema.
Sie gelten für alle Projekte auf diesem Rechner und liegen als JSON im
Datenordner — Projekte selbst liegen verschlüsselt daneben.

DER API-SCHLÜSSEL
-----------------
Ein Claude-Schlüssel ist Geld. Unter Windows wird er mit DPAPI an das
Benutzerkonto gebunden: Wer die Datei kopiert, kann damit auf einem anderen
Rechner oder unter einem anderen Konto nichts anfangen. Auf anderen
Systemen bleibt nur die Dateiberechtigung — das steht ehrlich in der
Oberfläche, statt eine Sicherheit vorzutäuschen, die es nicht gibt.

DATENORDNER
-----------
Windows:  %APPDATA%\\IndraNet
sonst:    ~/.indranet
Überschreibbar mit der Umgebungsvariablen INDRANET_DATEN — für Tests und
für den Betrieb von einem verschlüsselten USB-Stick.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import threading
from pathlib import Path

VORGABEN: dict = {
    "sprache": "de",
    "thema": "lagezentrale",
    # KI
    "ki_anbieter": "claude",          # claude | chat | ollama | aus
    "claude_modell": "claude-opus-5-5",
    "claude_schluessel": "",          # geschützt abgelegt, nie ausgeliefert
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_modell": "qwen3:14b",
    "ki_ueber_proxy": True,           # auch KI-Anfragen über den Netzweg
    # Datenquellen mit eigenem Zugang
    "opensanctions_schluessel": "",   # geschützt abgelegt, nie ausgeliefert
    "gfw_schluessel": "",             # Global Fishing Watch (Schiffe), dto.
    # Netzweg
    "netzweg": "direkt",              # direkt | tor | proxy
    "proxy_url": "",                  # socks5://host:port oder http://host:port
    "tor_pfad": "",                   # leer = automatisch suchen
    "tor_socks_port": 19050,
    "tor_bruecken": "auto",           # auto | aus | obfs4 | snowflake | meek | eigene
    "tor_eigene_bruecken": "",        # Brückenzeilen von bridges.torproject.org
    "netzwerk_dienst": True,          # .onion-Adresse für Recherche-Netzwerke
    "netzwerk_port": 8711,
    # Recherche
    "autopilot": False,               # Folgerecherchen selbständig starten
    "autopilot_max": 3,               # höchstens so viele je Übernahme
    "belege_sichern": True,           # Quellseiten verschlüsselt mitspeichern
}

_GEHEIM = {"claude_schluessel", "opensanctions_schluessel", "gfw_schluessel"}


def datenordner() -> Path:
    eigen = os.environ.get("INDRANET_DATEN")
    if eigen:
        p = Path(eigen)
    elif sys.platform == "win32" and os.environ.get("APPDATA"):
        p = Path(os.environ["APPDATA"]) / "IndraNet"
    else:
        p = Path.home() / ".indranet"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------------ DPAPI
def _dpapi(daten: bytes, schuetzen: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    puffer = ctypes.create_string_buffer(daten, len(daten))
    ein = _Blob(len(daten), ctypes.cast(puffer, ctypes.POINTER(ctypes.c_char)))
    aus = _Blob()
    crypt32 = ctypes.windll.crypt32
    funktion = (crypt32.CryptProtectData if schuetzen
                else crypt32.CryptUnprotectData)
    # 0x01 = CRYPTPROTECT_UI_FORBIDDEN: niemals einen Dialog öffnen
    if not funktion(ctypes.byref(ein), None, None, None, None, 0x01,
                    ctypes.byref(aus)):
        raise OSError("DPAPI fehlgeschlagen")
    try:
        return ctypes.string_at(aus.pbData, aus.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(aus.pbData,
                                                     ctypes.c_void_p))


def _verbergen(wert: str) -> str:
    if not wert:
        return ""
    if sys.platform == "win32":
        try:
            return "dpapi:" + base64.b64encode(
                _dpapi(wert.encode(), True)).decode()
        except OSError:
            pass
    return "klar:" + wert


def _aufdecken(wert: str) -> str:
    if not wert:
        return ""
    if wert.startswith("dpapi:"):
        try:
            return _dpapi(base64.b64decode(wert[6:]), False).decode()
        except OSError:
            return ""           # anderes Konto oder anderer Rechner
    if wert.startswith("klar:"):
        return wert[5:]
    return wert


class Einstellungen:
    """Liest und schreibt die Einstellungsdatei. Threadsicher."""

    def __init__(self, ordner: Path | None = None):
        self.ordner = ordner or datenordner()
        self.ordner.mkdir(parents=True, exist_ok=True)
        self.datei = self.ordner / "einstellungen.json"
        self._lock = threading.Lock()
        self._werte = dict(VORGABEN)
        if self.datei.exists():
            try:
                self._werte.update(json.loads(
                    self.datei.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass        # kaputte Datei: Vorgaben statt Absturz
        # Umgebungsvariable als bequemer Weg für Entwickler
        if not self._werte.get("claude_schluessel") and os.environ.get(
                "ANTHROPIC_API_KEY"):
            self._werte["_schluessel_aus_umgebung"] = True

    def get(self, name: str, vorgabe=None):
        with self._lock:
            wert = self._werte.get(name, VORGABEN.get(name, vorgabe))
        if name in _GEHEIM:
            klar = _aufdecken(wert or "")
            if not klar and name == "claude_schluessel":
                klar = os.environ.get("ANTHROPIC_API_KEY", "")
            if not klar and name == "opensanctions_schluessel":
                klar = os.environ.get("OPENSANCTIONS_API_KEY", "")
            if not klar and name == "gfw_schluessel":
                klar = os.environ.get("GFW_API_TOKEN", "")
            return klar
        return wert

    def __getitem__(self, name: str):
        return self.get(name)

    def setzen(self, aenderungen: dict) -> dict:
        with self._lock:
            for k, v in aenderungen.items():
                if k not in VORGABEN:
                    continue
                if k in _GEHEIM:
                    if v is None:
                        continue                  # unverändert lassen
                    v = _verbergen(str(v).strip())
                elif isinstance(VORGABEN[k], bool):
                    v = bool(v)
                elif isinstance(VORGABEN[k], int):
                    v = int(v)
                else:
                    v = str(v).strip()
                self._werte[k] = v
            self._schreiben()
        return self.oeffentlich()

    def _schreiben(self) -> None:
        roh = {k: v for k, v in self._werte.items() if not k.startswith("_")}
        tmp = self.datei.with_suffix(".tmp")
        tmp.write_text(json.dumps(roh, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        os.replace(tmp, self.datei)
        if sys.platform != "win32":
            os.chmod(self.datei, 0o600)

    def oeffentlich(self) -> dict:
        """Was die Oberfläche sehen darf: alles außer Geheimnissen."""
        with self._lock:
            raus = {k: self._werte.get(k, v) for k, v in VORGABEN.items()
                    if k not in _GEHEIM}
        raus["claude_schluessel_gesetzt"] = bool(self.get("claude_schluessel"))
        raus["opensanctions_schluessel_gesetzt"] = bool(
            self.get("opensanctions_schluessel"))
        raus["gfw_schluessel_gesetzt"] = bool(self.get("gfw_schluessel"))
        raus["schluessel_schutz"] = ("DPAPI (an dieses Windows-Konto gebunden)"
                                     if sys.platform == "win32"
                                     else "Dateiberechtigung 600")
        raus["datenordner"] = str(self.ordner)
        return raus
