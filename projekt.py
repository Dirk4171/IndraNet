"""
IndraNet — Projekte
====================

Ein Projekt ist eine Recherche: ein verschlüsselter Behälter (.indra) mit
dem Bestand, daneben der verschlüsselte Belegordner. Unter der Haube ist
das ein Pod aus Version 1 — das Aussage-Modell, die Beleglage, der
Widerruf mit Folgenabschätzung bleiben unverändert. Neu kommen hinzu:

    Prüfkorb      Befunde der KI, die ein Mensch übernimmt oder verwirft
    Orte          Koordinaten für die Karte
    Steckbriefe   Beschreibung, Typ, Notiz, Markierung je Entität
    Lagebilder    gespeicherte Analysen der KI
    Vorschläge    Folgerecherchen und vermutete Verbindungen
    Verlauf       was wann gesucht oder hochgeladen wurde

Alles liegt in derselben Datenbank wie der Bestand und damit im selben
verschlüsselten Behälter.

NEBENLÄUFIGKEIT
---------------
Die Oberfläche fragt aus mehreren Threads, Recherchen laufen im
Hintergrund. SQLite verträgt das mit einer gemeinsamen Verbindung nur, wenn
jeder Zugriff serialisiert ist — dafür steht `projekt.lock`. Die langen
KI-Aufrufe laufen außerhalb der Sperre, nur das Schreiben innerhalb.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

from geo import Orte
from policy import Rolle, Stufe
from resolver import INVERSE, PREDICATE_SCHEMA, strict_key
from store import EIN_OBJEKT_JE_SUBJEKT, Beleglage

ENDUNG = ".indra"
ROLLE = Rolle.ADMIN          # Einzelplatz: wer die Passphrase hat, sieht alles

ORTS_PRAEDIKATE = {"registered_in": 2, "resident_in": 2, "address_of": 3,
                   "national_of": 1}
SICHERHEIT = {"hoch": 0.9, "mittel": 0.7, "niedrig": 0.4}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projekt_info (schluessel TEXT PRIMARY KEY, wert TEXT);

CREATE TABLE IF NOT EXISTS fund (
  fund_id     TEXT PRIMARY KEY,
  art         TEXT,            -- web | datei | netzwerk | register
  anfrage     TEXT,
  titel       TEXT,
  zusammenfassung TEXT,
  inhalt      TEXT,            -- JSON: normalisierter Befund
  status      TEXT DEFAULT 'offen',   -- offen | uebernommen | teilweise | verworfen
  herkunft    TEXT,
  doc_id      TEXT,            -- bei Dateien: der abgelegte Beleg
  ts          REAL,
  erledigt_ts REAL,
  pruefer     TEXT,
  notiz       TEXT);

CREATE TABLE IF NOT EXISTS steckbrief (
  schluessel   TEXT PRIMARY KEY,   -- strict_key
  name         TEXT,
  typ          TEXT,
  beschreibung TEXT,
  notiz        TEXT,
  markiert     INTEGER DEFAULT 0,
  ts           REAL);

CREATE TABLE IF NOT EXISTS lagebild (
  lagebild_id TEXT PRIMARY KEY,
  titel TEXT, frage TEXT, inhalt TEXT, modell TEXT, ts REAL);

CREATE TABLE IF NOT EXISTS vorschlag (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  art TEXT,            -- recherche | verbindung
  text TEXT, grund TEXT, status TEXT DEFAULT 'offen', ts REAL);

CREATE TABLE IF NOT EXISTS verlauf (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  art TEXT, eingabe TEXT, ergebnis TEXT, ts REAL);
"""


class ProjektFehler(Exception):
    pass


def _sicherer_name(name: str) -> str:
    n = re.sub(r"[^\w\- ]+", "", name, flags=re.UNICODE).strip()
    n = re.sub(r"\s+", "-", n)
    if not n:
        raise ProjektFehler("Projektname ungültig")
    return n[:60]


# ---------------------------------------------------------------- Verwaltung
class Verwaltung:
    """Findet, legt an und öffnet Projekte im Datenordner."""

    def __init__(self, ordner: Path):
        self.ordner = ordner / "projekte"
        self.ordner.mkdir(parents=True, exist_ok=True)

    def liste(self) -> list[dict]:
        raus = []
        for p in sorted(self.ordner.glob("*" + ENDUNG),
                        key=lambda x: -x.stat().st_mtime):
            raus.append({"name": p.stem, "datei": str(p),
                         "groesse": p.stat().st_size,
                         "geaendert": p.stat().st_mtime})
        return raus

    def pfad(self, name: str) -> Path:
        return self.ordner / (_sicherer_name(name) + ENDUNG)

    def anlegen(self, name: str, passphrase: str, *, zweck: str = "",
                beschreibung: str = "") -> "Projekt":
        if len(passphrase) < 10:
            raise ProjektFehler("Die Passphrase muss mindestens 10 Zeichen "
                                "haben. Es gibt keine Wiederherstellung.")
        pfad = self.pfad(name)
        if pfad.exists():
            raise ProjektFehler(f"Projekt '{pfad.stem}' besteht bereits.")
        p = Projekt(pfad, passphrase)
        p.info_setzen(titel=name.strip(), zweck=zweck.strip(),
                      beschreibung=beschreibung.strip(),
                      angelegt=str(time.time()))
        p.sichern()
        return p

    def oeffnen(self, name: str, passphrase: str) -> "Projekt":
        pfad = self.pfad(name)
        if not pfad.exists():
            raise ProjektFehler(f"Projekt '{name}' nicht gefunden.")
        return Projekt(pfad, passphrase)


# ------------------------------------------------------------------ Projekt
class Projekt:
    def __init__(self, pfad: Path, passphrase: str):
        from crypto_axon import Identitaet
        from pod import Pod
        from vault import FalschePassphrase

        self.pfad = Path(pfad)
        self.name = self.pfad.stem
        self.lock = threading.RLock()
        try:
            self.pod = Pod(self.name, datei=self.pfad, passphrase=passphrase,
                           navigator=False,
                           inbox_wurzel=self.pfad.parent / ".inbox")
        except FalschePassphrase:
            raise ProjektFehler("Falsche Passphrase — oder die Datei wurde "
                                "verändert.")
        self.store = self.pod.store
        self.db = self.store.db
        self.db.executescript(_SCHEMA)
        self.orte = Orte(self.db, self.store.resolver)
        self._identitaet_laden(Identitaet)
        self._resolver_auffrischen()
        self.geaendert = False
        self.zuletzt_gesichert = time.time()

    # -------------------------------------------------------- Grundlagen
    def _identitaet_laden(self, Identitaet) -> None:
        """Jedes Projekt hat eine eigene, dauerhafte Signaturidentität —
        Recherchen in verschiedenen Netzwerken sind so nicht über einen
        gemeinsamen Schlüssel verknüpfbar."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        roh = self.info().get("_schluessel")
        if roh:
            sk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(roh))
            self.pod.ident = Identitaet(self.name, sk)
            self.pod.pod_id = self.pod.ident.pod_id
        else:
            sk = self.pod.ident._sk
            self.info_setzen(_schluessel=sk.private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                serialization.NoEncryption()).hex())
        self.ident = self.pod.ident

    def _resolver_auffrischen(self) -> None:
        """Der Resolver hält seine Vorschlagstabellen im Speicher. Nach dem
        Öffnen kennt er die vorhandenen Entitäten nicht — ohne diesen
        Schritt fände er keine Dubletten im Altbestand."""
        for z in self.db.execute("SELECT anzeige, typ FROM cluster"):
            self.store.resolver.register(z["anzeige"], z["typ"] or "AUTO")

    def info(self) -> dict:
        return {z["schluessel"]: z["wert"] for z in
                self.db.execute("SELECT * FROM projekt_info")}

    def info_setzen(self, **werte) -> None:
        with self.lock:
            for k, v in werte.items():
                self.db.execute("INSERT OR REPLACE INTO projekt_info "
                                "VALUES (?,?)", (k, str(v)))
            self.db.commit()
            self.geaendert = True

    def oeffentliche_info(self) -> dict:
        i = {k: v for k, v in self.info().items() if not k.startswith("_")}
        return {"name": self.name, **i, "pod_id": self.ident.pod_id}

    def sichern(self) -> dict:
        with self.lock:
            r = self.pod.sichern()
            self.geaendert = False
            self.zuletzt_gesichert = time.time()
            return r

    def schliessen(self) -> None:
        with self.lock:
            self.pod.close()

    def verlauf_eintragen(self, art: str, eingabe: str, ergebnis: str = "") -> None:
        with self.lock:
            self.db.execute("INSERT INTO verlauf (art,eingabe,ergebnis,ts) "
                            "VALUES (?,?,?,?)", (art, eingabe[:500],
                                                 ergebnis[:500], time.time()))
            self.db.commit()
            self.geaendert = True

    def verlauf(self, grenze: int = 50) -> list[dict]:
        return [dict(z) for z in self.db.execute(
            "SELECT * FROM verlauf ORDER BY ts DESC LIMIT ?", (grenze,))]

    # ------------------------------------------------------------ Kontext
    def kontext(self, fokus: str = "") -> dict:
        with self.lock:
            namen = [z["anzeige"] for z in self.db.execute(
                "SELECT MIN(anzeige) AS anzeige, COUNT(*) AS n FROM cluster "
                "GROUP BY cluster_id ORDER BY n DESC LIMIT 120")]
        return {"zweck": self.info().get("zweck", ""), "entitaeten": namen,
                "fokus": fokus}

    # -------------------------------------------------------------- Funde
    def fund_anlegen(self, *, art: str, anfrage: str, befund: dict,
                     herkunft: str = "", doc_id: str | None = None,
                     titel: str = "") -> str:
        fund_id = "fund:" + hashlib.sha256(
            f"{art}|{anfrage}|{time.time_ns()}".encode()).hexdigest()[:16]
        with self.lock:
            self.db.execute(
                "INSERT INTO fund (fund_id,art,anfrage,titel,zusammenfassung,"
                "inhalt,status,herkunft,doc_id,ts) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (fund_id, art, anfrage, titel or anfrage,
                 befund.get("zusammenfassung", ""),
                 json.dumps(befund, ensure_ascii=False), "offen", herkunft,
                 doc_id, time.time()))
            self.db.commit()
            self.geaendert = True
        return fund_id

    def funde(self, status: str | None = None) -> list[dict]:
        with self.lock:
            if status:
                zeilen = self.db.execute(
                    "SELECT * FROM fund WHERE status=? ORDER BY ts DESC",
                    (status,)).fetchall()
            else:
                zeilen = self.db.execute(
                    "SELECT * FROM fund ORDER BY ts DESC").fetchall()
        raus = []
        for z in zeilen:
            d = dict(z)
            inhalt = json.loads(d.pop("inhalt") or "{}")
            d["anzahl"] = {k: len(inhalt.get(k, [])) for k in
                           ("aussagen", "entitaeten", "orte", "quellen")}
            raus.append(d)
        return raus

    def fund(self, fund_id: str) -> dict:
        with self.lock:
            z = self.db.execute("SELECT * FROM fund WHERE fund_id=?",
                                (fund_id,)).fetchone()
        if not z:
            raise ProjektFehler("Fund nicht gefunden")
        d = dict(z)
        d["inhalt"] = json.loads(d["inhalt"] or "{}")
        # Bekanntes markieren: Was davon steht schon im Bestand?
        bekannt = self._bekannte_schluessel()
        for e in d["inhalt"].get("entitaeten", []):
            e["_bekannt"] = strict_key(e["name"], e.get("typ") or "AUTO") \
                in bekannt
        for a in d["inhalt"].get("aussagen", []):
            a["_bekannt_s"] = strict_key(a["subjekt"]) in bekannt
            a["_bekannt_o"] = strict_key(a["objekt"]) in bekannt
        return d

    def _bekannte_schluessel(self) -> set:
        return {z["schluessel"] for z in
                self.db.execute("SELECT schluessel FROM cluster")}

    def fund_verwerfen(self, fund_id: str, pruefer: str, notiz: str = "") -> None:
        with self.lock:
            self.db.execute("UPDATE fund SET status='verworfen', erledigt_ts=?,"
                            " pruefer=?, notiz=? WHERE fund_id=?",
                            (time.time(), pruefer, notiz, fund_id))
            self.db.commit()
            self.geaendert = True

    def beleg_fuer_quelle(self, url: str, titel: str, herausgeber: str,
                          netzweg=None, *, sichern: bool = True,
                          erfasst_von: str = "") -> str:
        """Legt zu einer Web-Quelle einen Beleg an.

        Wenn möglich wird die Seite abgerufen und VERSCHLÜSSELT im Projekt
        abgelegt — eine Webseite kann morgen anders aussehen oder weg sein,
        und dann zählt, was am Tag der Übernahme dort stand. Die
        Unabhängigkeit der Quellen bemisst sich am Herausgeber (Domain):
        Zwei Seiten derselben Zeitung sind eine Quelle, nicht zwei.
        """
        from netz import domain_von
        from provenance import Dokument
        quelle = (domain_von(url) if url.startswith("http")
                  else (herausgeber or url))
        titel = (titel or url)[:300]
        if sichern and netzweg is not None and url.startswith("http"):
            try:
                import quellen_offen
                s = quellen_offen.seitentext(netzweg, url, max_zeichen=10)
                if s["status"] < 400 and s["roh"]:
                    endung = ".pdf" if "pdf" in s["typ"] else ".html"
                    name = re.sub(r"[^\w.-]+", "_", quelle)[:50] + endung
                    with self.lock:
                        erg = self.pod.dokument_anlegen(
                            art="datei", titel=s["titel"] or titel,
                            quelle=quelle, stufe=Stufe.OEFFENTLICH,
                            erfasst_von=erfasst_von, datei=s["roh"],
                            dateiname=name, typ=s["typ"])
                        self.db.execute("UPDATE dokument SET pfad=? WHERE "
                                        "doc_id=?", (url, erg["doc_id"]))
                        self.db.commit()
                    return erg["doc_id"]
            except Exception:                               # noqa: BLE001
                pass            # Abruf gescheitert: dann eben nur der Verweis
        dok = Dokument.virtuell(f"{url}|{titel}", titel=titel, quelle=quelle,
                                stufe=Stufe.OEFFENTLICH,
                                erfasst_von=erfasst_von)
        dok.pfad = url
        with self.lock:
            self.store.dokument_aufnehmen(dok)
        return dok.doc_id

    def fund_uebernehmen(self, fund_id: str, auswahl: dict, *, pruefer: str,
                         netzweg=None, fortschritt=None) -> dict:
        """Übernimmt die ausgewählten Teile eines Befunds in den Bestand.

        `auswahl` = {"aussagen": [i, …], "entitaeten": [i, …],
                     "orte": [i, …], "bearbeitet": {"aussagen": {i: {…}}}}
        Bearbeitete Fassungen ersetzen die der KI — der Mensch hat das
        letzte Wort, auch über die Schreibweise.
        """
        f = self.fund(fund_id)
        inhalt = f["inhalt"]
        bearb = auswahl.get("bearbeitet", {}) or {}
        sichern = bool(auswahl.get("belege_sichern", True))
        quellen = {q["url"]: q for q in inhalt.get("quellen", [])}
        belege: dict[str, str] = {}
        ergebnis = {"aussagen": 0, "entitaeten": 0, "orte": 0, "fakten": []}

        for i in auswahl.get("aussagen", []):
            i = int(i)
            if i >= len(inhalt.get("aussagen", [])):
                continue
            a = {**inhalt["aussagen"][i],
                 **(bearb.get("aussagen", {}).get(str(i)) or {})}
            if a["praedikat"] not in PREDICATE_SCHEMA:
                continue
            if f["art"] == "datei" and f.get("doc_id"):
                doc_id, fundstelle = f["doc_id"], a.get("beleg", "")
            else:
                url = a.get("beleg", "")
                if url not in belege:
                    q = quellen.get(url, {})
                    if fortschritt:
                        fortschritt(f"Beleg sichern: {url}")
                    belege[url] = self.beleg_fuer_quelle(
                        url, q.get("titel", ""), q.get("herausgeber", ""),
                        netzweg, sichern=sichern, erfasst_von=pruefer)
                doc_id, fundstelle = belege[url], url
            with self.lock:
                fid = self.store.behaupten(
                    doc_id, a["subjekt"], a["praedikat"], a["objekt"],
                    fundstelle=fundstelle, zitat=a.get("zitat") or None,
                    erfasst_von=pruefer,
                    konfidenz=SICHERHEIT.get(a.get("sicherheit"), 0.7))
            ergebnis["aussagen"] += 1
            ergebnis["fakten"].append(fid)

        for i in auswahl.get("entitaeten", []):
            i = int(i)
            if i >= len(inhalt.get("entitaeten", [])):
                continue
            e = {**inhalt["entitaeten"][i],
                 **(bearb.get("entitaeten", {}).get(str(i)) or {})}
            with self.lock:
                typ = e.get("typ") or "AUTO"
                self.store.cluster_von(e["name"], typ)
                self.steckbrief_setzen(e["name"], typ=typ,
                                       beschreibung=e.get("beschreibung", ""),
                                       nur_wenn_leer=True)
            ergebnis["entitaeten"] += 1

        for i in auswahl.get("orte", []):
            i = int(i)
            if i >= len(inhalt.get("orte", [])):
                continue
            o = inhalt["orte"][i]
            with self.lock:
                self.orte.setzen(o["name"], o["lat"], o["lon"],
                                 land=o.get("land_iso", ""),
                                 genauigkeit=o.get("genauigkeit", "stadt"),
                                 quelle="ki")
            ergebnis["orte"] += 1

        gesamt = sum(len(inhalt.get(k, [])) for k in
                     ("aussagen", "entitaeten", "orte"))
        genommen = ergebnis["aussagen"] + ergebnis["entitaeten"] + \
            ergebnis["orte"]
        status = "uebernommen" if genommen >= gesamt else "teilweise"
        with self.lock:
            self.db.execute("UPDATE fund SET status=?, erledigt_ts=?, pruefer=?"
                            " WHERE fund_id=?",
                            (status, time.time(), pruefer, fund_id))
            self.db.commit()
            self.geaendert = True
        ergebnis["status"] = status
        return ergebnis

    # ------------------------------------------------------- Steckbriefe
    def steckbrief_setzen(self, name: str, *, typ: str | None = None,
                          beschreibung: str | None = None,
                          notiz: str | None = None,
                          markiert: bool | None = None,
                          nur_wenn_leer: bool = False) -> None:
        k = strict_key(name, typ or "AUTO")
        with self.lock:
            alt = self.db.execute("SELECT * FROM steckbrief WHERE schluessel=?",
                                  (k,)).fetchone()
            alt = dict(alt) if alt else {"schluessel": k, "name": name,
                                         "typ": None, "beschreibung": "",
                                         "notiz": "", "markiert": 0}
            if typ and not (nur_wenn_leer and alt["typ"]):
                alt["typ"] = typ
            if beschreibung is not None and not (nur_wenn_leer
                                                 and alt["beschreibung"]):
                alt["beschreibung"] = beschreibung
            if notiz is not None:
                alt["notiz"] = notiz
            if markiert is not None:
                alt["markiert"] = int(bool(markiert))
            self.db.execute(
                "INSERT OR REPLACE INTO steckbrief VALUES (?,?,?,?,?,?,?)",
                (k, alt["name"], alt["typ"], alt["beschreibung"], alt["notiz"],
                 alt["markiert"], time.time()))
            self.db.commit()
            self.geaendert = True

    def _steckbriefe_je_cluster(self) -> dict:
        raus = {}
        for z in self.db.execute(
                "SELECT c.cluster_id, s.* FROM steckbrief s JOIN cluster c "
                "ON c.schluessel = s.schluessel"):
            d = dict(z)
            ziel = raus.setdefault(d["cluster_id"], {})
            for k in ("typ", "beschreibung", "notiz"):
                if d.get(k) and not ziel.get(k):
                    ziel[k] = d[k]
            ziel["markiert"] = ziel.get("markiert", 0) or d["markiert"]
        return raus

    # ------------------------------------------------------------ Fakten
    def alle_fakten(self) -> list[dict]:
        """Alle Fakten mit Beleglage — die Grundlage für Netz und Karte.

        Gleiche Logik wie Store._buendeln, aber in einem Durchgang über den
        ganzen Bestand statt je Frage.
        """
        with self.lock:
            zeilen = self.db.execute(self.store._BASIS).fetchall()
            anzeige = {z["cluster_id"]: z["anzeige"] for z in self.db.execute(
                "SELECT cluster_id, MIN(anzeige) AS anzeige FROM cluster "
                "GROUP BY cluster_id")}
        gruppen: dict[tuple, list] = {}
        for z in zeilen:
            gruppen.setdefault((z["praedikat"], z["s_cid"], z["o_cid"]),
                               []).append(z)
        fakten = []
        for (p, s, o), gruppe in gruppen.items():
            aktiv = [z for z in gruppe if not z["widerrufen"]
                     and not z["doc_weg"]]
            quellen = sorted({z["quelle"] for z in aktiv})
            lage = (Beleglage.WIDERRUFEN if not aktiv else
                    Beleglage.BESTAETIGT if len(quellen) >= 2 else
                    Beleglage.EINFACH_BELEGT)
            fakten.append({
                "fact_id": self.store.fact_id(s, p, o), "praedikat": p,
                "s": s, "o": o, "subjekt": anzeige.get(s, s),
                "objekt": anzeige.get(o, o), "beleglage": lage.value,
                "quellen": quellen, "aussagen": len(gruppe),
                "konfidenz": round(max([z["konfidenz"] or 0 for z in aktiv]
                                       or [0]), 2),
                "zeit": max(z["ts"] or 0 for z in gruppe)})
        # Widerspruch bei Prädikaten mit genau einem Wert je Subjekt
        je_subjekt: dict[tuple, list] = {}
        for f in fakten:
            if EIN_OBJEKT_JE_SUBJEKT.get(f["praedikat"]) and \
                    f["beleglage"] != "WIDERRUFEN":
                je_subjekt.setdefault((f["praedikat"], f["s"]), []).append(f)
        for gruppe in je_subjekt.values():
            if len(gruppe) > 1:
                for f in gruppe:
                    f["beleglage"] = "UMSTRITTEN"
                    f["widersprueche"] = [g["objekt"] for g in gruppe
                                          if g is not f]
        return fakten

    def _typ_raten(self, cid: str, typ: str | None, rollen: set) -> str:
        if typ and typ != "AUTO":
            return typ
        if rollen & {"PLACE"}:
            return "PLACE"
        if rollen:
            return sorted(rollen)[0]
        return "ORG" if "|" in cid else "PERSON"

    def netz(self, ohne_widerrufen: bool = True) -> dict:
        """Knoten und Kanten für die Netzansicht."""
        fakten = self.alle_fakten()
        with self.lock:
            cluster = {z["cluster_id"]: dict(z) for z in self.db.execute(
                "SELECT cluster_id, MIN(anzeige) AS anzeige, MIN(typ) AS typ, "
                "COUNT(*) AS schluessel FROM cluster GROUP BY cluster_id")}
            steck = self._steckbriefe_je_cluster()
        rollen: dict[str, set] = {}
        for f in fakten:
            st, ot = PREDICATE_SCHEMA.get(f["praedikat"], ("AUTO", "AUTO"))
            if st != "AUTO":
                rollen.setdefault(f["s"], set()).add(st)
            if ot != "AUTO":
                rollen.setdefault(f["o"], set()).add(ot)
        kanten = [f for f in fakten
                  if not (ohne_widerrufen and f["beleglage"] == "WIDERRUFEN")]
        grad: dict[str, int] = {}
        for f in kanten:
            grad[f["s"]] = grad.get(f["s"], 0) + 1
            grad[f["o"]] = grad.get(f["o"], 0) + 1
        knoten = []
        for cid, c in cluster.items():
            sb = steck.get(cid, {})
            knoten.append({
                "id": cid, "name": c["anzeige"],
                "typ": self._typ_raten(cid, sb.get("typ") or c["typ"],
                                       rollen.get(cid, set())),
                "grad": grad.get(cid, 0),
                "beschreibung": sb.get("beschreibung", ""),
                "markiert": bool(sb.get("markiert"))})
        return {"knoten": knoten, "kanten": kanten}

    def karte(self) -> dict:
        """Orte mit Koordinaten, die dort verankerten Entitäten und die
        Bögen zwischen verankerten Entitäten."""
        n = self.netz()
        typ = {k["id"]: k["typ"] for k in n["knoten"]}
        name = {k["id"]: k["name"] for k in n["knoten"]}
        with self.lock:
            koord_cache: dict[str, dict | None] = {}

            def koord(cid):
                if cid not in koord_cache:
                    koord_cache[cid] = None
                    for z in self.db.execute("SELECT anzeige FROM cluster "
                                             "WHERE cluster_id=?", (cid,)):
                        k = self.orte.fuer(z["anzeige"])
                        if k:
                            koord_cache[cid] = k
                            break
                return koord_cache[cid]

            orte: dict[str, dict] = {}
            verankert: dict[str, tuple] = {}     # cid -> (ort_cid, gewicht)
            unverortet = set()
            for k in n["knoten"]:
                if k["typ"] in ("PLACE", "ADRESSE"):
                    c = koord(k["id"])
                    if c:
                        orte[k["id"]] = {"id": k["id"], "name": k["name"],
                                         "lat": c["lat"], "lon": c["lon"],
                                         "genauigkeit": c.get("genauigkeit"),
                                         "quelle": c.get("quelle"),
                                         "entitaeten": []}
                    elif k["grad"]:
                        unverortet.add(k["name"])
            for f in n["kanten"]:
                gewicht = ORTS_PRAEDIKATE.get(f["praedikat"])
                if not gewicht or f["o"] not in orte:
                    continue
                alt = verankert.get(f["s"])
                if alt is None or gewicht > alt[1]:
                    verankert[f["s"]] = (f["o"], gewicht, f["praedikat"],
                                         f["beleglage"])
            for cid, (ort, _, praed, lage) in verankert.items():
                orte[ort]["entitaeten"].append({"id": cid, "name": name[cid],
                                                "typ": typ[cid],
                                                "praedikat": praed,
                                                "beleglage": lage})
            boegen = []
            for f in n["kanten"]:
                if f["praedikat"] in ORTS_PRAEDIKATE:
                    continue
                a, b = verankert.get(f["s"]), verankert.get(f["o"])
                if a and b and a[0] != b[0]:
                    boegen.append({"von": a[0], "nach": b[0],
                                   "praedikat": f["praedikat"],
                                   "beleglage": f["beleglage"],
                                   "subjekt": f["subjekt"],
                                   "objekt": f["objekt"],
                                   "fact_id": f["fact_id"]})
        ohne = [k for k in n["knoten"] if k["typ"] not in ("PLACE", "ADRESSE")
                and k["id"] not in verankert]
        return {"orte": list(orte.values()), "boegen": boegen,
                "unverortet": sorted(unverortet),
                "ohne_ort": len(ohne)}

    def entitaet(self, cid: str) -> dict:
        with self.lock:
            namen = [dict(z) for z in self.db.execute(
                "SELECT schluessel, anzeige, typ FROM cluster WHERE "
                "cluster_id=?", (cid,))]
            if not namen:
                raise ProjektFehler("Entität nicht gefunden")
            zeilen = [dict(z) for z in self.store.kanten(cid)]
            steck = self._steckbriefe_je_cluster().get(cid, {})
            dok = {z["doc_id"]: dict(z) for z in self.db.execute(
                "SELECT doc_id, titel, quelle, pfad, stufe FROM dokument")}
        fakten = [f for f in self.alle_fakten() if cid in (f["s"], f["o"])]
        belege: dict[str, list] = {}
        for z in zeilen:
            fid = self.store.fact_id(z["s_cid"], z["praedikat"], z["o_cid"])
            d = dok.get(z["doc_id"], {})
            belege.setdefault(fid, []).append({
                "aussage_id": z["aussage_id"], "doc_id": z["doc_id"],
                "titel": d.get("titel"), "quelle": d.get("quelle"),
                "url": d.get("pfad"), "fundstelle": z["fundstelle"],
                "zitat": z["zitat"], "erfasst_von": z["erfasst_von"],
                "ts": z["ts"], "abgelegt": bool(
                    self.pod.dokumente and
                    self.pod.dokumente.enthaelt(z["doc_id"]))})
        for f in fakten:
            f["belege"] = belege.get(f["fact_id"], [])
        ort = None
        for n in namen:
            ort = ort or self.orte.fuer(n["anzeige"])
        return {"id": cid, "name": self.store.anzeige(cid), "namen": namen,
                "typ": steck.get("typ") or namen[0]["typ"],
                "beschreibung": steck.get("beschreibung", ""),
                "notiz": steck.get("notiz", ""),
                "markiert": bool(steck.get("markiert")),
                "fakten": fakten, "ort": ort}

    def bestand_text(self, grenze: int = 3000) -> str:
        """Der Bestand als kompakter Text für die KI-Analyse."""
        import i18n
        lab = i18n.praedikate("de")
        fakten = [f for f in self.alle_fakten()
                  if f["beleglage"] != "WIDERRUFEN"][:grenze]
        zeilen = ["FAKTEN:"]
        for f in fakten:
            zeilen.append(f"- {f['subjekt']} —[{lab.get(f['praedikat'], f['praedikat'])}]→ "
                          f"{f['objekt']}  [{f['beleglage']}; Quellen: "
                          f"{', '.join(f['quellen'])}]")
        with self.lock:
            steck = [dict(z) for z in self.db.execute(
                "SELECT name, typ, beschreibung, notiz FROM steckbrief "
                "WHERE beschreibung != '' OR notiz != ''")]
        if steck:
            zeilen.append("\nSTECKBRIEFE:")
            for s in steck:
                zeilen.append(f"- {s['name']} ({s['typ']}): {s['beschreibung']}"
                              + (f" — Notiz: {s['notiz']}" if s["notiz"] else ""))
        return "\n".join(zeilen)

    # ----------------------------------------------------------- Lagebilder
    def lagebild_speichern(self, frage: str, inhalt: dict) -> str:
        lid = "lage:" + hashlib.sha256(
            f"{frage}|{time.time_ns()}".encode()).hexdigest()[:14]
        with self.lock:
            self.db.execute("INSERT INTO lagebild VALUES (?,?,?,?,?,?)",
                            (lid, inhalt.get("titel", "Lagebild"), frage,
                             json.dumps(inhalt, ensure_ascii=False),
                             inhalt.get("_modell", ""), time.time()))
            self.db.commit()
            self.geaendert = True
        return lid

    def lagebilder(self) -> list[dict]:
        with self.lock:
            return [{**dict(z), "inhalt": json.loads(z["inhalt"])}
                    for z in self.db.execute(
                        "SELECT * FROM lagebild ORDER BY ts DESC")]

    def lagebild_loeschen(self, lid: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM lagebild WHERE lagebild_id=?", (lid,))
            self.db.commit()
            self.geaendert = True

    # ---------------------------------------------------------- Vorschläge
    def vorschlaege_speichern(self, daten: dict) -> int:
        n = 0
        with self.lock:
            offen = {z["text"] for z in self.db.execute(
                "SELECT text FROM vorschlag")}
            for r in daten.get("recherchen", []):
                if r.get("auftrag") and r["auftrag"] not in offen:
                    self.db.execute("INSERT INTO vorschlag (art,text,grund,ts) "
                                    "VALUES ('recherche',?,?,?)",
                                    (r["auftrag"], r.get("grund", ""),
                                     time.time()))
                    n += 1
            for v in daten.get("verbindungen", []):
                text = f"{v.get('a')} ↔ {v.get('b')}"
                if v.get("a") and text not in offen:
                    self.db.execute("INSERT INTO vorschlag (art,text,grund,ts) "
                                    "VALUES ('verbindung',?,?,?)",
                                    (text, v.get("vermutung", ""), time.time()))
                    n += 1
            self.db.commit()
            self.geaendert = True
        return n

    def vorschlaege(self, status: str = "offen") -> list[dict]:
        with self.lock:
            return [dict(z) for z in self.db.execute(
                "SELECT * FROM vorschlag WHERE status=? ORDER BY ts DESC",
                (status,))]

    def vorschlag_status(self, vid: int, status: str) -> None:
        with self.lock:
            self.db.execute("UPDATE vorschlag SET status=? WHERE id=?",
                            (status, vid))
            self.db.commit()
            self.geaendert = True

    # --------------------------------------------------------------- Status
    def stats(self) -> dict:
        with self.lock:
            g = lambda q: self.db.execute(q).fetchone()[0]       # noqa: E731
            offen = g("SELECT COUNT(*) FROM fund WHERE status='offen'")
            vorschl = g("SELECT COUNT(*) FROM vorschlag WHERE status='offen'")
            basis = self.store.stats()
        fakten = self.alle_fakten()
        lagen = {}
        for f in fakten:
            lagen[f["beleglage"]] = lagen.get(f["beleglage"], 0) + 1
        return {"dokumente": basis["dokumente"],
                "aussagen": basis["aktive_aussagen"],
                "entitaeten": basis["entitaeten"], "fakten": len(fakten),
                "beleglage": lagen, "pruefkorb": offen,
                "vorschlaege": vorschl, "geaendert": self.geaendert,
                "zuletzt_gesichert": self.zuletzt_gesichert}
