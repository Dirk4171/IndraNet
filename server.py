"""
IndraNet — Oberflächen-Server
==============================

Liefert die Weboberfläche aus web/ und die JSON-Schnittstelle unter /api.
Bindet ausschließlich an 127.0.0.1 — die Oberfläche ist von außen nicht zu
erreichen, auch nicht über Tor (dort hängt nur der Netzwerk-Anschluss).

SCHUTZ GEGEN FREMDE WEBSEITEN
-----------------------------
Ein lokaler Server ist für jede Webseite im selben Browser erreichbar.
Drei Riegel:
  Host-Prüfung   Nur Anfragen an 127.0.0.1/localhost — verhindert
                 DNS-Rebinding.
  Sitzungsmarke  Zufällig je Programmstart, steht nur in der ausgelieferten
                 Seite. Fremde Seiten können sie wegen der Same-Origin-
                 Policy nicht lesen und damit keine API-Aufrufe absetzen.
  CSP            Die Oberfläche darf nichts von außen laden. Abgelegte
                 Webseiten-Belege werden in einer Sandbox ausgeliefert,
                 ohne Skripte.
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import auftraege as ab
import quellen_offen
from bruecke import BrueckeFehler
from einstellungen import Einstellungen
from ki import KI, MODELLE, KIFehler
from netz import Netzweg, NetzwegFehler
from netzwerk import NetzwerkDienst, Netzwerke, NetzwerkFehler
from policy import Rolle, Stufe
from projekt import ProjektFehler, Verwaltung
from tor import TorDienst

VERSION = "2.0.0"
MAX_UPLOAD = 250 * 1024 * 1024


def _webordner() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "web"
    return Path(__file__).resolve().parent / "web"


class Fehler(Exception):
    def __init__(self, text: str, code: int = 400):
        super().__init__(text)
        self.code = code


# ===================================================================== App
class App:
    def __init__(self, port: int = 8710):
        self.port = port
        self.token = secrets.token_urlsafe(24)
        self.einst = Einstellungen()
        self.ordner = self.einst.ordner
        self.tor = TorDienst(self.ordner, self.einst)
        self.netzweg = Netzweg(self.einst, self.tor)
        self.ki = KI(self.einst, self.netzweg)
        self.verwaltung = Verwaltung(self.ordner)
        self.auftraege = ab.Auftraege(threads=3)
        self.projekt = None
        self.netzwerke: Netzwerke | None = None
        self.netzdienst = NetzwerkDienst(self.einst, self.tor,
                                         lambda: self.netzwerke)
        self._stop = threading.Event()

    # ------------------------------------------------------------ Betrieb
    def starten(self) -> ThreadingHTTPServer:
        app = self

        class H(Handler):
            pass
        H.app = app
        server = ThreadingHTTPServer(("127.0.0.1", self.port), H)
        server.daemon_threads = True
        self.server = server
        self.netzdienst.starten()
        if self.einst.get("netzweg") == "tor":
            self.tor.starten(self.netzdienst.port
                             if self.einst.get("netzwerk_dienst") else None)
        threading.Thread(target=self._wartung, daemon=True).start()
        return server

    def _wartung(self) -> None:
        """Sichert geänderte Projekte und gleicht Netzwerke ab."""
        letzter_abgleich = 0.0
        while not self._stop.wait(15):
            p = self.projekt
            if p is None:
                continue
            try:
                if p.geaendert and time.time() - p.zuletzt_gesichert > 20:
                    p.sichern()
                if self.netzwerke and time.time() - letzter_abgleich > 180:
                    letzter_abgleich = time.time()
                    if self.netzwerke.liste():
                        self.netzwerke.abgleichen()
            except Exception:                               # noqa: BLE001
                traceback.print_exc()

    def beenden(self) -> None:
        self._stop.set()
        if self.projekt is not None:
            try:
                self.projekt.sichern()
                self.projekt.schliessen()
            except Exception:                               # noqa: BLE001
                traceback.print_exc()
        self.netzdienst.stoppen()
        self.tor.stoppen()
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    # ------------------------------------------------------------ Projekt
    def p(self):
        if self.projekt is None:
            raise Fehler("Kein Projekt geöffnet.", 409)
        return self.projekt

    def nw(self) -> Netzwerke:
        self.p()
        return self.netzwerke

    def projekt_setzen(self, projekt) -> None:
        if self.projekt is not None:
            self.projekt.sichern()
            self.projekt.schliessen()
        self.projekt = projekt
        self.netzwerke = Netzwerke(projekt, self.netzdienst) if projekt else None

    @property
    def benutzer(self) -> str:
        if self.projekt is None:
            return ""
        i = self.projekt.info()
        return i.get("netzname") or os.environ.get("USERNAME") or "Recherche"

    def status(self) -> dict:
        return {"version": VERSION,
                "projekt": (self.projekt.oeffentliche_info()
                            if self.projekt else None),
                "ki": self.ki.zustand(), "netzweg": self.netzweg.beschreibung(),
                "tor": self.tor.status(),
                "netzadresse": self.netzdienst.eigene_adresse(),
                "einstellungen": {"thema": self.einst.get("thema"),
                                  "belege_sichern":
                                      self.einst.get("belege_sichern")},
                "auftraege_laufend": (self.auftraege.laufend(self.projekt.name)
                                      if self.projekt else 0)}


# ================================================================ Handler
class Handler(BaseHTTPRequestHandler):
    app: App
    server_version = "IndraNet"
    sys_version = ""
    # HTTP/1.1: Die Verbindung bleibt nach der Antwort offen, der Browser
    # schließt sie. Mit HTTP/1.0 schließt der Server sofort nach dem
    # Schreiben — Virenscanner, die den lokalen Verkehr mitlesen (Avast),
    # verlieren dabei gelegentlich das Ende großer Antworten.
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    # ------------------------------------------------------------ Antwort
    def _sicherheitskoepfe(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Cache-Control", "no-store")

    def _json(self, obj, code: int = 200) -> None:
        roh = json.dumps(obj, ensure_ascii=False, default=str).encode()
        if code >= 400:
            # Ein ungelesener Anfragekörper darf nicht in die nächste
            # Anfrage auf derselben Verbindung geraten.
            self.close_connection = True
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self._sicherheitskoepfe()
        self.end_headers()
        self.wfile.write(roh)

    def _datei(self, roh: bytes, typ: str, *, sandbox: bool = False,
               name: str | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(roh)))
        self._sicherheitskoepfe()
        if sandbox:
            self.send_header("Content-Security-Policy", "sandbox; default-src "
                             "'none'; img-src data:; style-src 'unsafe-inline'")
        else:
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; img-src 'self' data: blob:; "
                             "style-src 'self' 'unsafe-inline'; "
                             "script-src 'self'; connect-src 'self'; "
                             "frame-src 'self'; object-src 'none'; "
                             "base-uri 'none'; form-action 'self'")
        if name:
            self.send_header("Content-Disposition",
                             f"attachment; filename=\"{name}\"")
        self.end_headers()
        self.wfile.write(roh)

    # ------------------------------------------------------------- Prüfung
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _token_ok(self) -> bool:
        t = self.headers.get("X-Indra-Token") or ""
        if not t:
            t = parse_qs(urlparse(self.path).query).get("t", [""])[0]
        return secrets.compare_digest(t, self.app.token)

    def _koerper(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20 * 1024 * 1024:
            raise Fehler("Anfrage zu groß", 413)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            raise Fehler("kein gültiges JSON")

    # -------------------------------------------------------------- Routen
    def do_GET(self):
        self._verteilen("GET")

    def do_POST(self):
        self._verteilen("POST")

    def _verteilen(self, methode: str) -> None:
        if not self._host_ok():
            return self._json({"fehler": "Host nicht erlaubt"}, 403)
        url = urlparse(self.path)
        pfad = url.path
        if not pfad.startswith("/api/"):
            if methode != "GET":
                return self._json({"fehler": "nicht erlaubt"}, 405)
            return self._statisch(pfad)
        if not self._token_ok():
            return self._json({"fehler": "Sitzung ungültig — Seite neu laden"},
                              401)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if methode == "POST" and pfad == "/api/datei":
                return self._json(self._hochladen())
            if methode == "GET" and pfad == "/api/beleg":
                return self._beleg(q)
            if methode == "GET" and pfad == "/api/dossier":
                return self._dossier(q)
            k = self._koerper() if methode == "POST" else {}
            funktion = ROUTEN.get((methode, pfad))
            if funktion is None:
                return self._json({"fehler": "unbekannte Schnittstelle"}, 404)
            return self._json(funktion(self.app, k, q))
        except Fehler as e:
            self._json({"fehler": str(e)}, e.code)
        except (ProjektFehler, KIFehler, NetzwerkFehler, NetzwegFehler,
                BrueckeFehler, ValueError, PermissionError, KeyError) as e:
            self._json({"fehler": str(e)}, 400)
        except Exception as e:                              # noqa: BLE001
            traceback.print_exc()
            self._json({"fehler": f"Interner Fehler: {e}"}, 500)

    def _statisch(self, pfad: str) -> None:
        web = _webordner()
        if pfad in ("/", "/index.html"):
            html = (web / "index.html").read_text(encoding="utf-8")
            html = html.replace("{{TOKEN}}", self.app.token).replace(
                "{{VERSION}}", VERSION)
            return self._datei(html.encode(), "text/html; charset=utf-8")
        ziel = (web / unquote(pfad).lstrip("/")).resolve()
        if web.resolve() not in ziel.parents or not ziel.is_file():
            return self._json({"fehler": "nicht gefunden"}, 404)
        typ = mimetypes.guess_type(ziel.name)[0] or "application/octet-stream"
        if typ.startswith("text/") or typ.endswith(("javascript", "json")):
            typ += "; charset=utf-8"
        self._datei(ziel.read_bytes(), typ)

    def _hochladen(self) -> dict:
        app = self.app
        p = app.p()
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            raise Fehler("leere Datei")
        if n > MAX_UPLOAD:
            raise Fehler("Datei größer als 250 MB", 413)
        name = unquote(self.headers.get("X-Dateiname") or "datei")
        name = os.path.basename(name.replace("\\", "/"))[:200] or "datei"
        stufe = Stufe[(self.headers.get("X-Stufe") or "INTERN").upper()]
        analysieren = self.headers.get("X-Analysieren", "1") == "1"
        typ = (self.headers.get("Content-Type") or "").split(";")[0] or \
            mimetypes.guess_type(name)[0] or "application/octet-stream"
        roh = self.rfile.read(n)
        if analysieren and not app.ki.zustand()["bereit"]:
            analysieren = False
        a = app.auftraege.starten(
            "datei", f"Datei: {name}", p.name,
            ab.datei(p, app.ki, roh, name, typ, stufe, app.benutzer,
                     analysieren))
        return {"auftrag": a.id, "analyse": analysieren}

    def _beleg(self, q: dict) -> None:
        p = self.app.p()
        doc_id = q.get("doc_id", "")
        if p.pod.dokumente is None or not p.pod.dokumente.enthaelt(doc_id):
            return self._json({"fehler": "kein abgelegter Beleg"}, 404)
        with p.lock:
            z = p.db.execute("SELECT stufe FROM dokument WHERE doc_id=?",
                             (doc_id,)).fetchone()
            if not z or not p.pod.policy.beleg_einsehen(Rolle.ADMIN,
                                                        Stufe(z["stufe"])):
                return self._json({"fehler": "kein Zugriff"}, 403)
            ang = p.pod.dokumente.angaben(doc_id)
            roh = p.pod.dokumente.inhalt(doc_id)
        name = ang.get("dateiname") or "beleg"
        typ = ang.get("typ") or mimetypes.guess_type(name)[0] or \
            "application/octet-stream"
        herunter = q.get("laden") == "1"
        self._datei(roh, typ, sandbox=True, name=name if herunter else None)

    def _dossier(self, q: dict) -> None:
        p = self.app.p()
        with p.lock:
            ids = [f["fact_id"] for f in p.alle_fakten()
                   if f["beleglage"] != "WIDERRUFEN"]
            md = p.pod.dossier(ids, Rolle.ADMIN,
                               titel=p.info().get("titel", p.name))
        self._datei(md.encode("utf-8"), "text/markdown; charset=utf-8",
                    sandbox=True, name=f"{p.name}-dossier.md")


# ============================================================ Schnittstellen
def _ki_bereit(app: App) -> None:
    z = app.ki.zustand()
    if not z["bereit"]:
        raise Fehler(z["grund"], 409)


def api_status(app, k, q):
    return app.status()


def api_vokabular(app, k, q):
    import i18n
    from ki import ENTITAETSTYPEN
    return {"praedikate": i18n.praedikate(app.einst.get("sprache") or "de"),
            "typen": ENTITAETSTYPEN, "quellen": quellen_offen.QUELLEN}


def api_einstellungen(app, k, q):
    return {**app.einst.oeffentlich(), "modelle": MODELLE}


def api_einstellungen_setzen(app, k, q):
    alt_weg = app.einst.get("netzweg")
    r = app.einst.setzen(k)
    if k.get("netzweg") == "tor" and alt_weg != "tor":
        app.tor.starten(app.netzdienst.port
                        if app.einst.get("netzwerk_dienst") else None)
    return r


def api_tor_starten(app, k, q):
    if k.get("neu"):            # nach geänderter Brückenwahl
        app.tor.stoppen()
    return app.tor.starten(app.netzdienst.port
                           if app.einst.get("netzwerk_dienst") else None)


def api_tor_stoppen(app, k, q):
    app.tor.stoppen()
    return app.tor.status()


def api_netzweg_pruefen(app, k, q):
    return app.netzweg.pruefen()


def api_projekte(app, k, q):
    return {"projekte": app.verwaltung.liste(),
            "offen": app.projekt.name if app.projekt else None}


def api_projekt_anlegen(app, k, q):
    p = app.verwaltung.anlegen(k.get("name", ""), k.get("passphrase", ""),
                               zweck=k.get("zweck", ""),
                               beschreibung=k.get("beschreibung", ""))
    if k.get("netzname"):
        p.info_setzen(netzname=k["netzname"])
    app.projekt_setzen(p)
    return app.status()


def api_projekt_oeffnen(app, k, q):
    p = app.verwaltung.oeffnen(k.get("name", ""), k.get("passphrase", ""))
    app.projekt_setzen(p)
    return app.status()


def api_projekt_schliessen(app, k, q):
    app.projekt_setzen(None)
    return app.status()


def api_projekt_sichern(app, k, q):
    return app.p().sichern()


def api_projekt_info(app, k, q):
    erlaubt = {x: str(k[x])[:2000] for x in ("titel", "zweck", "beschreibung",
                                              "netzname") if x in k}
    app.p().info_setzen(**erlaubt)
    return app.p().oeffentliche_info()


def api_stats(app, k, q):
    return app.p().stats()


def api_recherche(app, k, q):
    p = app.p()
    _ki_bereit(app)
    auftrag = (k.get("auftrag") or "").strip()
    if len(auftrag) < 2:
        raise Fehler("Bitte einen Suchauftrag eingeben.")
    if app.ki.anbieter == "chat":
        a = app.auftraege.starten("recherche", auftrag, p.name,
                                  ab.bruecke_recherche(p, app.netzweg, auftrag,
                                                       k.get("fokus", "")))
        return {"auftrag": a.id, "bruecke": True}
    a = app.auftraege.starten("recherche", auftrag, p.name,
                              ab.recherche(p, app.ki, auftrag,
                                           k.get("fokus", "")))
    return {"auftrag": a.id}


def api_bruecke_antwort(app, k, q):
    p = app.p()
    a = app.auftraege.get(k.get("auftrag", ""))
    if a is None or a.projekt != p.name:
        raise Fehler("Auftrag unbekannt — nach einem Neustart von IndraNet "
                     "bitte die Recherche neu anstoßen.", 404)
    return ab.bruecke_einlesen(p, a, k.get("antwort", ""))


def api_register(app, k, q):
    p = app.p()
    quelle = k.get("quelle")
    if quelle not in quellen_offen.QUELLEN:
        raise Fehler("unbekannte Quelle")
    a = app.auftraege.starten("register", f"{quelle}: {k.get('begriff')}",
                              p.name, ab.register(p, app.netzweg, quelle,
                                                  k.get("begriff", "")))
    return {"auftrag": a.id}


def api_auftraege(app, k, q):
    return {"auftraege": app.auftraege.liste(
        app.projekt.name if app.projekt else None)}


def api_auftrag(app, k, q):
    a = app.auftraege.get(q.get("id", ""))
    if a is None:
        raise Fehler("Auftrag unbekannt", 404)
    return a.als_dict()


def api_funde(app, k, q):
    return {"funde": app.p().funde(q.get("status") or None)}


def api_fund(app, k, q):
    return app.p().fund(q.get("id", ""))


def api_fund_uebernehmen(app, k, q):
    p = app.p()
    fund_id = k.get("fund_id", "")
    auswahl = k.get("auswahl") or {}
    auswahl.setdefault("belege_sichern", app.einst.get("belege_sichern"))

    def nachher():
        z = app.ki.zustand()
        if z["bereit"] and z.get("hintergrund", True):
            app.auftraege.starten("verknuepfen", "Verknüpfen im Hintergrund",
                                  p.name, ab.verknuepfen(p, app.ki,
                                                         app.auftraege,
                                                         app.einst))
    a = app.auftraege.starten("uebernahme", "Übernahme in den Bestand", p.name,
                              ab.uebernehmen(p, fund_id, auswahl, app.benutzer,
                                             app.netzweg, nachher))
    return {"auftrag": a.id}


def api_fund_verwerfen(app, k, q):
    app.p().fund_verwerfen(k.get("fund_id", ""), app.benutzer,
                           k.get("notiz", ""))
    return {"ok": True}


def api_netz(app, k, q):
    return app.p().netz(ohne_widerrufen=q.get("alle") != "1")


def api_karte(app, k, q):
    return app.p().karte()


def api_entitaet(app, k, q):
    return app.p().entitaet(q.get("id", ""))


def api_entitaet_setzen(app, k, q):
    p = app.p()
    name = k.get("name") or ""
    if not name:
        raise Fehler("Name fehlt")
    p.steckbrief_setzen(name, typ=k.get("typ"),
                        beschreibung=k.get("beschreibung"),
                        notiz=k.get("notiz"), markiert=k.get("markiert"))
    return {"ok": True}


def api_ort(app, k, q):
    p = app.p()
    with p.lock:
        r = p.orte.setzen(k["name"], float(k["lat"]), float(k["lon"]),
                          genauigkeit=k.get("genauigkeit", "punkt"),
                          quelle="hand")
        p.geaendert = True
    return r


def api_ort_nominatim(app, k, q):
    p = app.p()
    r = p.orte.nominatim(k.get("name", ""), app.netzweg)
    if not r:
        raise Fehler("Ort nicht gefunden")
    p.geaendert = True
    return r


def api_aussage_widerrufen(app, k, q):
    p = app.p()
    with p.lock:
        r = p.pod.aussage_widerrufen(k["aussage_id"], k.get("grund", ""),
                                     app.benutzer)
        p.geaendert = True
    return r


def api_dokument_widerrufen(app, k, q):
    p = app.p()
    with p.lock:
        r = p.store.dokument_widerrufen(k["doc_id"], k.get("grund", ""))
        p.geaendert = True
    return r


def api_dubletten(app, k, q):
    p = app.p()
    with p.lock:
        v = p.pod.vorschlaege(schwelle=float(q.get("schwelle", 0.8)))
    return {"vorschlaege": [{"a": x.a, "b": x.b, "key_a": x.key_a,
                             "key_b": x.key_b, "score": round(x.score, 3),
                             "grund": x.grund, "typ": x.etype,
                             "warnung": x.warnung} for x in v[:100]]}


def api_verschmelzen(app, k, q):
    p = app.p()
    if not (k.get("begruendung") or "").strip():
        raise Fehler("Begründung ist Pflicht — sie steht im Protokoll.")
    with p.lock:
        r = p.pod.verschmelzen(k["von"], k["nach"], pruefer=app.benutzer,
                               begruendung=k["begruendung"])
        p.geaendert = True
    return r


def api_trennen(app, k, q):
    p = app.p()
    with p.lock:
        p.pod.trennen(k["a"], k["b"], pruefer=app.benutzer,
                      begruendung=k.get("begruendung", "verschieden"))
        p.geaendert = True
    return {"ok": True}


def api_lagebild(app, k, q):
    p = app.p()
    _ki_bereit(app)
    a = app.auftraege.starten("lagebild", "Lagebild: " + (k.get("frage") or
                                                          "Gesamtlage"),
                              p.name, ab.lagebild(p, app.ki,
                                                  k.get("frage", "")))
    return {"auftrag": a.id, "bruecke": app.ki.anbieter == "chat"}


def api_lagebilder(app, k, q):
    return {"lagebilder": app.p().lagebilder()}


def api_lagebild_loeschen(app, k, q):
    app.p().lagebild_loeschen(k.get("id", ""))
    return {"ok": True}


def api_vorschlaege(app, k, q):
    return {"vorschlaege": app.p().vorschlaege(q.get("status", "offen"))}


def api_vorschlag(app, k, q):
    app.p().vorschlag_status(int(k["id"]), k.get("status", "erledigt"))
    return {"ok": True}


def api_verlauf(app, k, q):
    return {"verlauf": app.p().verlauf()}


def api_quellen(app, k, q):
    return {"quellen": quellen_offen.gesundheit()}


def api_netzwerke(app, k, q):
    return {"netzwerke": app.nw().liste(),
            "adresse": app.netzdienst.eigene_adresse(),
            "name": app.nw().mein_name}


def api_netzwerk(app, k, q):
    return app.nw().netz(q.get("id", ""))


def api_netzwerk_anlegen(app, k, q):
    if not (k.get("name") or "").strip():
        raise Fehler("Name fehlt")
    return app.nw().anlegen(k["name"], k.get("beschreibung", ""))


def api_netzwerk_einladen(app, k, q):
    return app.nw().einladen(k.get("netz_id", ""))


def api_netzwerk_beitreten(app, k, q):
    return app.nw().beitreten(k.get("code", ""))


def api_netzwerk_freigeben(app, k, q):
    return app.nw().freigeben(k.get("netz_id", ""), k.get("fact_ids") or [],
                              k.get("kommentar", ""))


def api_netzwerk_uebernehmen(app, k, q):
    fid = app.nw().als_fund(k.get("netz_id", ""), k.get("item_ids") or [])
    return {"fund_id": fid}


def api_netzwerk_abgleichen(app, k, q):
    p = app.p()
    a = app.auftraege.starten("abgleich", "Netzwerkabgleich", p.name,
                              ab.abgleich(app.nw(), k.get("netz_id")))
    return {"auftrag": a.id}


def api_beispiel(app, k, q):
    import beispiel
    return {"funde": beispiel.laden(app.p())}


def api_beenden(app, k, q):
    threading.Timer(0.3, app.beenden).start()
    return {"ok": True}


ROUTEN = {
    ("GET", "/api/status"): api_status,
    ("GET", "/api/vokabular"): api_vokabular,
    ("GET", "/api/einstellungen"): api_einstellungen,
    ("POST", "/api/einstellungen"): api_einstellungen_setzen,
    ("POST", "/api/tor/starten"): api_tor_starten,
    ("POST", "/api/tor/stoppen"): api_tor_stoppen,
    ("POST", "/api/netzweg/pruefen"): api_netzweg_pruefen,
    ("GET", "/api/projekte"): api_projekte,
    ("POST", "/api/projekt/anlegen"): api_projekt_anlegen,
    ("POST", "/api/projekt/oeffnen"): api_projekt_oeffnen,
    ("POST", "/api/projekt/schliessen"): api_projekt_schliessen,
    ("POST", "/api/projekt/sichern"): api_projekt_sichern,
    ("POST", "/api/projekt/info"): api_projekt_info,
    ("GET", "/api/stats"): api_stats,
    ("POST", "/api/recherche"): api_recherche,
    ("POST", "/api/bruecke/antwort"): api_bruecke_antwort,
    ("POST", "/api/register"): api_register,
    ("GET", "/api/auftraege"): api_auftraege,
    ("GET", "/api/auftrag"): api_auftrag,
    ("GET", "/api/funde"): api_funde,
    ("GET", "/api/fund"): api_fund,
    ("POST", "/api/fund/uebernehmen"): api_fund_uebernehmen,
    ("POST", "/api/fund/verwerfen"): api_fund_verwerfen,
    ("GET", "/api/netz"): api_netz,
    ("GET", "/api/karte"): api_karte,
    ("GET", "/api/entitaet"): api_entitaet,
    ("POST", "/api/entitaet"): api_entitaet_setzen,
    ("POST", "/api/ort"): api_ort,
    ("POST", "/api/ort/nominatim"): api_ort_nominatim,
    ("POST", "/api/aussage/widerrufen"): api_aussage_widerrufen,
    ("POST", "/api/dokument/widerrufen"): api_dokument_widerrufen,
    ("GET", "/api/dubletten"): api_dubletten,
    ("POST", "/api/verschmelzen"): api_verschmelzen,
    ("POST", "/api/trennen"): api_trennen,
    ("POST", "/api/lagebild"): api_lagebild,
    ("GET", "/api/lagebilder"): api_lagebilder,
    ("POST", "/api/lagebild/loeschen"): api_lagebild_loeschen,
    ("GET", "/api/vorschlaege"): api_vorschlaege,
    ("POST", "/api/vorschlag"): api_vorschlag,
    ("GET", "/api/verlauf"): api_verlauf,
    ("GET", "/api/quellen"): api_quellen,
    ("GET", "/api/netzwerke"): api_netzwerke,
    ("GET", "/api/netzwerk"): api_netzwerk,
    ("POST", "/api/netzwerk/anlegen"): api_netzwerk_anlegen,
    ("POST", "/api/netzwerk/einladen"): api_netzwerk_einladen,
    ("POST", "/api/netzwerk/beitreten"): api_netzwerk_beitreten,
    ("POST", "/api/netzwerk/freigeben"): api_netzwerk_freigeben,
    ("POST", "/api/netzwerk/uebernehmen"): api_netzwerk_uebernehmen,
    ("POST", "/api/netzwerk/abgleichen"): api_netzwerk_abgleichen,
    ("POST", "/api/beispiel"): api_beispiel,
    ("POST", "/api/beenden"): api_beenden,
}
