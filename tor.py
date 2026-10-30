"""
IndraNet — Tor-Dienst
======================

IndraNet startet seinen eigenen Tor-Prozess. Er leistet zweierlei:

  1. SOCKS-Zugang für alle Abrufe — die Rechercheurin erscheint nach außen
     mit einer Tor-Ausgangsadresse, nicht mit ihrer eigenen.
  2. Einen Onion-Dienst für die Recherche-Netzwerke. Jede Installation ist
     unter einer .onion-Adresse erreichbar, ohne Server, ohne Portfreigabe
     am Router, und keiner der Teilnehmer erfährt die IP-Adresse der
     anderen.

Der Onion-Dienst zeigt ausschließlich auf den Netzwerk-Anschluss
(netzwerk.py), niemals auf die Oberfläche. Die Oberfläche bindet an
127.0.0.1 und ist von außen nicht zu erreichen — auch nicht über Tor.

WOHER KOMMT TOR?
----------------
Gesucht wird in dieser Reihenfolge:
  - der in den Einstellungen eingetragene Pfad
  - tor/tor.exe neben dem Programm (Tor Expert Bundle, mitgeliefert)
  - ein installierter Tor Browser (Desktop, Programme, AppData)
  - tor im Suchpfad

Der Tor-Prozess bekommt ein eigenes Datenverzeichnis. Ein laufender
Tor Browser wird nicht angefasst.

BRÜCKEN
-------
Manche Virenscanner brechen jede TLS-Verbindung auf, um sie zu prüfen
(Avast „Web/Mail Shield", ähnlich Kaspersky, ESET). Tor merkt das am
falschen Zertifikat und verweigert die Verbindung — der Aufbau bleibt bei
14 % stehen. Dasselbe passiert in Netzen, die Tor sperren. Abhilfe sind
Brücken mit verschleiertem Verkehr (obfs4, Snowflake, meek), deren
Programme das Expert Bundle mitbringt. Vorgabe "auto": erst direkt, bei
Hängen selbsttätig obfs4; die Wahl wird für den nächsten Start gemerkt.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

_BOOT = re.compile(r"Bootstrapped (\d+)%")
STAU_SEKUNDEN = 120         # so lange ohne Fortschritt gilt der Aufbau als hängend
STAU_VERSUCHE = 3


def _programmordner() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def tor_finden(eigener_pfad: str = "") -> Path | None:
    exe = "tor.exe" if sys.platform == "win32" else "tor"
    kandidaten: list[Path] = []
    if eigener_pfad:
        kandidaten.append(Path(eigener_pfad))
    app = _programmordner()
    kandidaten += [app / "tor" / exe, app / "tor" / "tor" / exe]
    heim = Path.home()
    for basis in [heim / "Desktop", heim / "OneDrive" / "Desktop",
                  Path(os.environ.get("ProgramFiles", "C:/Program Files")),
                  Path(os.environ.get("LOCALAPPDATA", heim)),
                  heim / "AppData" / "Local"]:
        kandidaten.append(basis / "Tor Browser" / "Browser" / "TorBrowser"
                          / "Tor" / exe)
    if sys.platform == "darwin":
        kandidaten.append(Path("/Applications/Tor Browser.app/Contents/"
                               "MacOS/Tor/tor"))
    gefunden = shutil.which("tor")
    if gefunden:
        kandidaten.append(Path(gefunden))
    for k in kandidaten:
        if k.is_file():
            return k
    return None


class TorDienst:
    def __init__(self, ordner: Path, einstellungen):
        self.ordner = ordner / "tor"
        self.einst = einstellungen
        self.proc: subprocess.Popen | None = None
        self.fortschritt = 0
        self.fehler: str | None = None
        self.letzte_meldung = ""
        self.pfad: Path | None = None
        self.bruecke: str | None = None       # aktive Brückenart
        self.hinweis: str | None = None
        self._dienst_port: int | None = None
        self._tls_gestoert = False
        self._fortschritt_zeit = 0.0
        self._lock = threading.RLock()

    @property
    def socks_port(self) -> int:
        return int(self.einst.get("tor_socks_port") or 19050)

    @property
    def bereit(self) -> bool:
        return (self.proc is not None and self.proc.poll() is None
                and self.fortschritt >= 100)

    @property
    def onion(self) -> str | None:
        datei = self.ordner / "dienst" / "hostname"
        if datei.exists():
            return datei.read_text().strip()
        return None

    def status(self) -> dict:
        self.pfad = self.pfad or tor_finden(self.einst.get("tor_pfad") or "")
        return {"gefunden": self.pfad is not None,
                "pfad": str(self.pfad) if self.pfad else None,
                "laeuft": self.proc is not None and self.proc.poll() is None,
                "bereit": self.bereit, "fortschritt": self.fortschritt,
                "onion": self.onion if self.bereit else None,
                "socks_port": self.socks_port, "fehler": self.fehler,
                "bruecken": self.bruecke, "hinweis": self.hinweis,
                "brueckenarten": self.brueckenarten(),
                "meldung": self.letzte_meldung}

    # ----------------------------------------------------------- Brücken
    def _pt_config(self) -> tuple[dict, Path] | None:
        """pt_config.json des Expert Bundles bzw. des Tor Browsers."""
        if self.pfad is None:
            return None
        for ordner in (self.pfad.parent / "pluggable_transports",
                       self.pfad.parent / "PluggableTransports"):
            datei = ordner / "pt_config.json"
            if datei.exists():
                try:
                    return json.loads(datei.read_text(encoding="utf-8")), ordner
                except (OSError, json.JSONDecodeError):
                    return None
        return None

    def brueckenarten(self) -> list[str]:
        pt = self._pt_config()
        return sorted(pt[0].get("bridges", {})) if pt else []

    def _bruecken_zeilen(self, art: str) -> list[str]:
        pt = self._pt_config()
        if pt is None:
            raise RuntimeError("Keine Brücken-Programme gefunden "
                               "(pluggable_transports fehlt)")
        cfg, ordner = pt
        if art == "eigene":
            bruecken = [z.strip().removeprefix("Bridge ").strip() for z in
                        (self.einst.get("tor_eigene_bruecken") or "")
                        .splitlines() if z.strip()]
        else:
            bruecken = cfg.get("bridges", {}).get(art, [])
        if not bruecken:
            raise RuntimeError(f"Keine Brücken für '{art}' vorhanden")
        pfad = ordner.as_posix() + "/"
        plugins = [z.replace("${pt_path}", pfad)
                   for z in cfg.get("pluggableTransports", {}).values()]
        return ["UseBridges 1", *plugins, *("Bridge " + b for b in bruecken)]

    # ------------------------------------------------------------ Starten
    def starten(self, dienst_port: int | None = None) -> dict:
        """Startet Tor. Mit Brücken-Einstellung 'auto' zuerst direkt; hängt
        der Aufbau, geht es selbsttätig über obfs4-Brücken weiter.

        Direkte Tor-Verbindungen scheitern, wenn ein Virenscanner TLS
        aufbricht (Avast, Kaspersky, ESET mit HTTPS-Prüfung) oder ein Netz
        Tor sperrt. obfs4 sieht nicht nach TLS aus und kommt durch.
        """
        with self._lock:
            if self.proc is not None and self.proc.poll() is None:
                return self.status()
            self.pfad = tor_finden(self.einst.get("tor_pfad") or "")
            if self.pfad is None:
                self.fehler = ("Tor nicht gefunden. Installieren Sie den Tor "
                               "Browser oder legen Sie das Tor Expert Bundle "
                               "in den Ordner 'tor' neben IndraNet.")
                return self.status()
            self._dienst_port = dienst_port
            wahl = self.einst.get("tor_bruecken") or "auto"
            self.hinweis = None
            if wahl == "auto":
                gemerkt = self.ordner / "bruecken-auto"
                art = gemerkt.read_text().strip() if gemerkt.exists() else "aus"
                self._prozess(art, wachen=(art == "aus"))
            else:
                self._prozess(wahl, wachen=False)
            return self.status()

    def _prozess(self, art: str, wachen: bool, versuch: int = 1) -> None:
        daten = self.ordner / "daten"
        daten.mkdir(parents=True, exist_ok=True)
        zeilen = [f"SocksPort 127.0.0.1:{self.socks_port}",
                  f"DataDirectory {daten.as_posix()}",
                  "AvoidDiskWrites 1",
                  "Log notice stdout",
                  "ClientOnly 1"]
        # Expert Bundle: tor/tor.exe und daneben data/geoip
        geo = self.pfad.parent.parent / "data"
        if (geo / "geoip").exists():
            zeilen += [f"GeoIPFile {(geo / 'geoip').as_posix()}",
                       f"GeoIPv6File {(geo / 'geoip6').as_posix()}"]
        self.bruecke = None
        if art != "aus":
            try:
                zeilen += self._bruecken_zeilen(art)
                self.bruecke = art
            except RuntimeError as e:
                self.fehler = str(e)
        if self._dienst_port:
            dienst = self.ordner / "dienst"
            dienst.mkdir(parents=True, exist_ok=True)
            if sys.platform != "win32":
                os.chmod(dienst, 0o700)
            zeilen += [f"HiddenServiceDir {dienst.as_posix()}",
                       f"HiddenServicePort 80 127.0.0.1:{self._dienst_port}"]
        torrc = self.ordner / "torrc"
        torrc.write_text("\n".join(zeilen) + "\n", encoding="utf-8")

        self.fortschritt, self.fehler, self._tls_gestoert = 0, None, False
        self._fortschritt_zeit = time.time()
        self.proc = subprocess.Popen(
            [str(self.pfad), "-f", str(torrc)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
            cwd=str(self.pfad.parent),
            creationflags=(subprocess.CREATE_NO_WINDOW
                           if sys.platform == "win32" else 0))
        threading.Thread(target=self._mitlesen, args=(self.proc,),
                         daemon=True).start()
        if wachen:
            threading.Thread(target=self._waechter, args=(self.proc,),
                             daemon=True).start()
        elif self.bruecke:
            threading.Thread(target=self._stau_waechter,
                             args=(self.proc, art, versuch), daemon=True).start()

    def _stau_waechter(self, proc, art: str, versuch: int) -> None:
        """Brücken sind oft überlastet; der Aufbau bleibt dann bei 25 oder
        50 % stehen, ebenso nach dem Aufwachen aus dem Ruhezustand. Tor
        versucht es nicht von selbst neu — ein Neustart wählt die Brücken
        frisch aus und kommt meist sofort durch."""
        while proc is self.proc and proc.poll() is None and not self.bereit:
            if time.time() - self._fortschritt_zeit > STAU_SEKUNDEN:
                break
            time.sleep(2)
        else:
            return
        with self._lock:
            if proc is not self.proc or self.bereit:
                return
            stand = self.fortschritt
            if versuch >= STAU_VERSUCHE:
                self.hinweis = (f"Tor-Aufbau hängt bei {stand} % — auch nach "
                                f"{versuch} Versuchen. Andere Brückenart wählen "
                                "oder eigene Brücken eintragen.")
                return
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:                               # noqa: BLE001
                proc.kill()
            self._prozess(art, wachen=False, versuch=versuch + 1)
            self.hinweis = (f"Tor-Aufbau hing bei {stand} % — neuer Versuch "
                            f"({versuch + 1}/{STAU_VERSUCHE}).")

    def _waechter(self, proc) -> None:
        """Hängt der direkte Aufbau, auf obfs4-Brücken umschalten."""
        ende = time.time() + 45
        while time.time() < ende:
            if proc is not self.proc or proc.poll() is not None or self.bereit:
                return
            if self._tls_gestoert and self.fortschritt < 20 and \
                    time.time() > ende - 30:
                break
            time.sleep(1)
        with self._lock:
            if proc is not self.proc or self.bereit:
                return
            if "obfs4" not in self.brueckenarten():
                self.hinweis = ("Direkte Tor-Verbindung hängt, und es sind "
                                "keine Brücken vorhanden.")
                return
            self.hinweis = ("Direkte Tor-Verbindung gestört"
                            + (" — ein Virenscanner bricht TLS auf (z. B. "
                               "HTTPS-Prüfung von Avast)" if self._tls_gestoert
                               else "") + ". IndraNet nutzt obfs4-Brücken.")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:                               # noqa: BLE001
                proc.kill()
            (self.ordner / "bruecken-auto").write_text("obfs4")
            self._prozess("obfs4", wachen=False)

    def _mitlesen(self, proc) -> None:
        for zeile in proc.stdout:
            zeile = zeile.strip()
            if proc is not self.proc:
                continue
            self.letzte_meldung = zeile[-200:]
            m = _BOOT.search(zeile)
            if m:
                self.fortschritt = int(m.group(1))
                self._fortschritt_zeit = time.time()
            if "bad CERTS cell" in zeile:
                self._tls_gestoert = True
            if "[err]" in zeile:
                self.fehler = zeile[-300:]
        with self._lock:        # nicht mitten in einen Neustart hineinmelden
            if proc is self.proc and proc.poll() not in (None, 0):
                self.fehler = self.fehler or f"Tor beendet ({proc.returncode})"

    def warten(self, sekunden: float = 90) -> bool:
        ende = time.time() + sekunden
        while time.time() < ende:
            if self.bereit:
                return True
            if self.proc is None or self.proc.poll() is not None:
                # Der Wächter hält die Sperre, während er auf Brücken
                # umschaltet — erst danach steht fest, ob Tor wirklich aus ist.
                with self._lock:
                    if self.proc is None or self.proc.poll() is not None:
                        return False
            time.sleep(0.5)
        return self.bereit

    def stoppen(self) -> None:
        with self._lock:
            if self.proc is not None:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=5)
                except Exception:                           # noqa: BLE001
                    self.proc.kill()
            self.proc = None
            self.fortschritt = 0
            self.bruecke = None
