"""
IndraNet — Recherche-Netzwerke
===============================

Journalistinnen in mehreren Ländern arbeiten an derselben Geschichte. Jede
hat ihr eigenes Projekt auf ihrem eigenen Rechner. Ein Netzwerk verbindet
diese Projekte: Wer etwas Geprüftes gefunden hat, gibt es frei, und alle
anderen sehen es — mit Autor, Quelle und Signatur.

KEIN SERVER
-----------
Jede Installation ist über Tor als .onion-Adresse erreichbar (tor.py).
Die Teilnehmer holen sich gegenseitig ab, was neu ist. Was einer weiß,
gibt er beim Abgleich weiter — auch Freigaben Dritter, unverändert und mit
deren Signatur. So erreicht ein Fund das ganze Netz, auch wenn sein Autor
gerade offline ist.

VERTRAUEN
---------
  Einladung    Wer im Netz ist, erzeugt einen Einladungscode (einmalig,
               48 Stunden gültig). Der Code enthält Adresse und öffentlichen
               Schlüssel des Einladenden — er ist der Vertrauensanker des
               Neuen. Den Code über einen sicheren Kanal weitergeben
               (Signal, persönlich).
  Nachweis     Jede Mitgliedschaft ist vom Einladenden signiert. Ein
               Mitglied, für das kein bekanntes Mitglied bürgt, wird beim
               Abgleich nicht angenommen.
  Freigabe     Jeder Fund ist vom Autor signiert. Eine veränderte Freigabe
               fällt bei der Prüfung durch und wird verworfen.
  Abgleich     Jede Anfrage ist signiert und höchstens zehn Minuten alt;
               die Antwort ist mit dem Netzwerkschlüssel verschlüsselt.

WAS GETEILT WIRD
----------------
Nur Fakten, deren Belege öffentlich sind (Stufe OEFFENTLICH): Webseiten,
Register, Presse. Hochgeladene interne Dokumente, Notizen und vertrauliche
Belege verlassen das Projekt nicht — das Indra-Juwel aus Version 1 gilt
auch hier. Und was ankommt, ist ein Hinweis, kein Fakt: Es geht in den
Prüfkorb, die Quelle wird beim Übernehmen selbst abgerufen.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization

EINLADUNG_GUELTIG = 48 * 3600
MAX_ALTER = 600
MAX_KOERPER = 4 * 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS netz (
  netz_id TEXT PRIMARY KEY, name TEXT, beschreibung TEXT, schluessel TEXT,
  gruender TEXT, ts REAL, zuletzt_abgleich REAL);
CREATE TABLE IF NOT EXISTS netz_mitglied (
  netz_id TEXT, pod_id TEXT, name TEXT, adresse TEXT, pubkey TEXT,
  nachweis TEXT, status TEXT DEFAULT 'aktiv', zuletzt_gesehen REAL,
  seit REAL DEFAULT 0, fehler TEXT, PRIMARY KEY (netz_id, pod_id));
CREATE TABLE IF NOT EXISTS netz_einladung (
  token TEXT PRIMARY KEY, netz_id TEXT, ablauf REAL, benutzt_von TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS netz_freigabe (
  netz_id TEXT, item_id TEXT, autor_pod TEXT, autor_name TEXT, inhalt TEXT,
  ts REAL, signatur TEXT, empfangen REAL, eigen INTEGER DEFAULT 0,
  uebernommen INTEGER DEFAULT 0, PRIMARY KEY (netz_id, item_id));
"""


class NetzwerkFehler(Exception):
    pass


# ------------------------------------------------------------- Werkzeuge
def kanonisch(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _pub_hex(sk: ed25519.Ed25519PrivateKey) -> str:
    return sk.public_key().public_bytes(serialization.Encoding.Raw,
                                        serialization.PublicFormat.Raw).hex()


def pod_id_aus(pubkey_hex: str) -> str:
    return "pod:" + pubkey_hex[:16]


def pruefen(pubkey_hex: str, daten: dict, signatur: str) -> bool:
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(pubkey_hex)).verify(_unb64(signatur),
                                              kanonisch(daten))
        return True
    except (InvalidSignature, ValueError):
        return False


def verschluesseln(schluessel_hex: str, obj) -> dict:
    nonce = os.urandom(12)
    c = AESGCM(bytes.fromhex(schluessel_hex)).encrypt(nonce, kanonisch(obj),
                                                     b"indranet-netz-1")
    return {"n": _b64(nonce), "c": _b64(c)}


def entschluesseln(schluessel_hex: str, paket: dict):
    klar = AESGCM(bytes.fromhex(schluessel_hex)).decrypt(
        _unb64(paket["n"]), _unb64(paket["c"]), b"indranet-netz-1")
    return json.loads(klar)


# --------------------------------------------------------------- Netzwerke
class Netzwerke:
    """Netzwerke eines Projekts. Lebt im verschlüsselten Projektbehälter."""

    def __init__(self, projekt, dienst):
        self.p = projekt
        self.dienst = dienst            # NetzwerkDienst: eigene Adresse, Client
        self.db = projekt.db
        with projekt.lock:
            self.db.executescript(_SCHEMA)

    @property
    def sk(self) -> ed25519.Ed25519PrivateKey:
        return self.p.ident._sk

    @property
    def pubkey(self) -> str:
        return _pub_hex(self.sk)

    @property
    def pod_id(self) -> str:
        return pod_id_aus(self.pubkey)

    @property
    def mein_name(self) -> str:
        return self.p.info().get("netzname") or self.p.info().get(
            "titel") or self.p.name

    def signieren(self, daten: dict) -> str:
        return _b64(self.sk.sign(kanonisch(daten)))

    def _nachweis(self, netz_id: str, pod_id: str, name: str, pubkey: str,
                  adresse: str) -> dict:
        rec = {"netz_id": netz_id, "pod_id": pod_id, "name": name,
               "pubkey": pubkey, "adresse": adresse,
               "eingeladen_von": self.pod_id, "ts": time.time()}
        return {"daten": rec, "signatur": self.signieren(rec)}

    # ----------------------------------------------------------- Anlegen
    def anlegen(self, name: str, beschreibung: str = "") -> dict:
        netz_id = os.urandom(12).hex()
        schluessel = os.urandom(32).hex()
        with self.p.lock:
            self.db.execute("INSERT INTO netz VALUES (?,?,?,?,?,?,?)",
                            (netz_id, name.strip(), beschreibung.strip(),
                             schluessel, self.pod_id, time.time(), None))
            self._mitglied_eintragen(self._nachweis(
                netz_id, self.pod_id, self.mein_name, self.pubkey,
                self.dienst.eigene_adresse() or ""))
            self.db.commit()
            self.p.geaendert = True
        return self.netz(netz_id)

    def _mitglied_eintragen(self, nachweis: dict) -> None:
        d = nachweis["daten"]
        self.db.execute(
            "INSERT INTO netz_mitglied (netz_id,pod_id,name,adresse,pubkey,"
            "nachweis,status,zuletzt_gesehen,seit) VALUES (?,?,?,?,?,?,"
            "'aktiv',NULL,0) ON CONFLICT(netz_id,pod_id) DO UPDATE SET "
            "name=excluded.name, adresse=excluded.adresse, "
            "nachweis=excluded.nachweis",
            (d["netz_id"], d["pod_id"], d["name"], d.get("adresse", ""),
             d["pubkey"], json.dumps(nachweis)))

    # ---------------------------------------------------------- Auskunft
    def liste(self) -> list[dict]:
        with self.p.lock:
            netze = [dict(z) for z in self.db.execute(
                "SELECT netz_id, name, beschreibung, gruender, ts, "
                "zuletzt_abgleich FROM netz ORDER BY ts")]
            for n in netze:
                n["mitglieder"] = self.db.execute(
                    "SELECT COUNT(*) FROM netz_mitglied WHERE netz_id=?",
                    (n["netz_id"],)).fetchone()[0]
                n["freigaben"] = self.db.execute(
                    "SELECT COUNT(*) FROM netz_freigabe WHERE netz_id=?",
                    (n["netz_id"],)).fetchone()[0]
                n["neu"] = self.db.execute(
                    "SELECT COUNT(*) FROM netz_freigabe WHERE netz_id=? AND "
                    "eigen=0 AND uebernommen=0", (n["netz_id"],)).fetchone()[0]
        return netze

    def netz(self, netz_id: str) -> dict:
        with self.p.lock:
            z = self.db.execute("SELECT * FROM netz WHERE netz_id=?",
                                (netz_id,)).fetchone()
            if not z:
                raise NetzwerkFehler("Netzwerk unbekannt")
            n = {k: z[k] for k in z.keys() if k != "schluessel"}
            n["mitglieder"] = [
                {k: m[k] for k in ("pod_id", "name", "adresse", "status",
                                   "zuletzt_gesehen", "fehler")}
                | {"ich": m["pod_id"] == self.pod_id}
                for m in self.db.execute(
                    "SELECT * FROM netz_mitglied WHERE netz_id=? ORDER BY name",
                    (netz_id,))]
            n["freigaben"] = [self._freigabe_dict(f) for f in self.db.execute(
                "SELECT * FROM netz_freigabe WHERE netz_id=? ORDER BY ts DESC",
                (netz_id,))]
            n["einladungen_offen"] = self.db.execute(
                "SELECT COUNT(*) FROM netz_einladung WHERE netz_id=? AND "
                "benutzt_von IS NULL AND ablauf>?", (netz_id, time.time())
            ).fetchone()[0]
        n["ich"] = self.pod_id
        n["eigene_adresse"] = self.dienst.eigene_adresse()
        return n

    @staticmethod
    def _freigabe_dict(z) -> dict:
        d = dict(z)
        d["inhalt"] = json.loads(d["inhalt"])
        d.pop("signatur", None)
        return d

    def _schluessel(self, netz_id: str) -> str:
        z = self.db.execute("SELECT schluessel FROM netz WHERE netz_id=?",
                            (netz_id,)).fetchone()
        if not z:
            raise NetzwerkFehler("Netzwerk unbekannt")
        return z["schluessel"]

    def _mitglied(self, netz_id: str, pod_id: str):
        return self.db.execute(
            "SELECT * FROM netz_mitglied WHERE netz_id=? AND pod_id=? AND "
            "status='aktiv'", (netz_id, pod_id)).fetchone()

    # ---------------------------------------------------------- Einladen
    def einladen(self, netz_id: str) -> dict:
        adresse = self.dienst.eigene_adresse()
        if not adresse:
            raise NetzwerkFehler(
                "Keine eigene Netzwerkadresse. Starten Sie Tor (Einstellungen "
                "→ Netzweg) oder tragen Sie eine Adresse von Hand ein.")
        token = _b64(os.urandom(18))
        with self.p.lock:
            self._schluessel(netz_id)
            self.db.execute("INSERT INTO netz_einladung VALUES (?,?,?,?,?)",
                            (token, netz_id, time.time() + EINLADUNG_GUELTIG,
                             None, time.time()))
            name = self.db.execute("SELECT name FROM netz WHERE netz_id=?",
                                   (netz_id,)).fetchone()["name"]
            self.db.commit()
            self.p.geaendert = True
        code = {"v": 1, "netz_id": netz_id, "netz": name, "adresse": adresse,
                "pubkey": self.pubkey, "von": self.mein_name, "token": token}
        return {"code": "INDRA1-" + _b64(kanonisch(code)),
                "gueltig_bis": time.time() + EINLADUNG_GUELTIG}

    @staticmethod
    def code_lesen(code: str) -> dict:
        code = code.strip()
        if not code.startswith("INDRA1-"):
            raise NetzwerkFehler("Das ist kein IndraNet-Einladungscode.")
        try:
            return json.loads(_unb64(code[7:]))
        except Exception:                                   # noqa: BLE001
            raise NetzwerkFehler("Einladungscode beschädigt.")

    def beitreten(self, code: str) -> dict:
        """Tritt mit einem Einladungscode bei. Spricht den Einladenden an."""
        e = self.code_lesen(code)
        if e["pubkey"] == self.pubkey:
            raise NetzwerkFehler("Das ist Ihre eigene Einladung.")
        mein = {"pod_id": self.pod_id, "name": self.mein_name,
                "pubkey": self.pubkey,
                "adresse": self.dienst.eigene_adresse() or ""}
        anfrage = {"netz_id": e["netz_id"], "token": e["token"],
                   "mitglied": mein, "ts": time.time()}
        antwort = self.dienst.senden(e["adresse"], "/netz/beitreten", {
            **anfrage, "signatur": self.signieren(anfrage)})
        daten, sig = antwort.get("daten"), antwort.get("signatur", "")
        if not daten or not pruefen(e["pubkey"], daten, sig):
            raise NetzwerkFehler("Antwort des Einladenden ist nicht korrekt "
                                 "signiert — Beitritt abgebrochen.")
        with self.p.lock:
            self.db.execute("INSERT OR REPLACE INTO netz VALUES "
                            "(?,?,?,?,?,?,?)",
                            (e["netz_id"], daten["name"],
                             daten.get("beschreibung", ""),
                             daten["schluessel"], daten.get("gruender"),
                             time.time(), None))
            for nw in daten["mitglieder"]:
                d = nw["daten"]
                if pod_id_aus(d["pubkey"]) == d["pod_id"]:
                    self._mitglied_eintragen(nw)
            self.db.commit()
            self.p.geaendert = True
        self.abgleichen(e["netz_id"])
        return self.netz(e["netz_id"])

    # ------------------------------------------------------------ Teilen
    def freigeben(self, netz_id: str, fact_ids: list[str],
                  kommentar: str = "") -> dict:
        """Gibt Fakten frei — nur mit öffentlichen Belegen."""
        from policy import Stufe
        fakten = {f["fact_id"]: f for f in self.p.alle_fakten()}
        geteilt, abgelehnt = [], []
        with self.p.lock:
            self._schluessel(netz_id)
            for fid in fact_ids:
                f = fakten.get(fid)
                if not f or f["beleglage"] == "WIDERRUFEN":
                    abgelehnt.append({"fact_id": fid, "grund": "unbekannt oder "
                                      "widerrufen"})
                    continue
                belege = []
                for z in self.p.store.aussagen_zu(fid):
                    if z["widerrufen"] or z["doc_weg"]:
                        continue
                    d = self.db.execute(
                        "SELECT titel, quelle, pfad, stufe FROM dokument "
                        "WHERE doc_id=?", (z["doc_id"],)).fetchone()
                    if d and d["stufe"] == Stufe.OEFFENTLICH and \
                            (d["pfad"] or "").startswith("http"):
                        belege.append({"url": d["pfad"], "titel": d["titel"],
                                       "herausgeber": d["quelle"],
                                       "zitat": z["zitat"] or ""})
                if not belege:
                    abgelehnt.append({"fact_id": fid, "grund":
                                      "keine öffentliche Quelle — interne "
                                      "Belege verlassen das Projekt nicht"})
                    continue
                inhalt = {"subjekt": f["subjekt"], "praedikat": f["praedikat"],
                          "objekt": f["objekt"], "beleglage": f["beleglage"],
                          "belege": belege, "kommentar": kommentar.strip()}
                ts = time.time()
                item_id = hashlib.sha256(kanonisch(
                    [self.pod_id, inhalt, ts])).hexdigest()[:24]
                kern = {"netz_id": netz_id, "item_id": item_id,
                        "autor_pod": self.pod_id, "autor_name": self.mein_name,
                        "inhalt": inhalt, "ts": ts}
                self.db.execute(
                    "INSERT OR IGNORE INTO netz_freigabe VALUES "
                    "(?,?,?,?,?,?,?,?,1,1)",
                    (netz_id, item_id, self.pod_id, self.mein_name,
                     json.dumps(inhalt, ensure_ascii=False), ts,
                     self.signieren(kern), time.time()))
                geteilt.append(item_id)
            self.db.commit()
            self.p.geaendert = True
        return {"geteilt": len(geteilt), "abgelehnt": abgelehnt}

    def als_fund(self, netz_id: str, item_ids: list[str]) -> str | None:
        """Empfangene Freigaben in den Prüfkorb legen."""
        with self.p.lock:
            zeilen = [self._freigabe_dict(z) for z in self.db.execute(
                f"SELECT * FROM netz_freigabe WHERE netz_id=? AND item_id IN "
                f"({','.join('?' * len(item_ids))})", (netz_id, *item_ids))]
            netzname = self.db.execute("SELECT name FROM netz WHERE netz_id=?",
                                       (netz_id,)).fetchone()["name"]
        if not zeilen:
            return None
        aussagen, quellen, entitaeten, gesehen = [], [], [], set()
        for z in zeilen:
            i = z["inhalt"]
            for b in i["belege"]:
                aussagen.append({"subjekt": i["subjekt"],
                                 "praedikat": i["praedikat"],
                                 "objekt": i["objekt"], "beleg": b["url"],
                                 "zitat": b.get("zitat", ""), "datum": "",
                                 "sicherheit": "mittel"})
                if b["url"] not in gesehen:
                    gesehen.add(b["url"])
                    quellen.append({"url": b["url"], "titel": b.get("titel", ""),
                                    "herausgeber": b.get("herausgeber", ""),
                                    "art": "sonstige", "datum": ""})
        autoren = sorted({z["autor_name"] for z in zeilen})
        befund = {"zusammenfassung": f"{len(zeilen)} Freigabe(n) aus dem "
                  f"Netzwerk '{netzname}' von {', '.join(autoren)}. Beim "
                  "Übernehmen werden die Originalquellen selbst abgerufen.",
                  "entitaeten": entitaeten, "aussagen": aussagen, "orte": [],
                  "quellen": quellen, "offene_fragen": [],
                  "naechste_schritte": []}
        fid = self.p.fund_anlegen(art="netzwerk", anfrage=f"Netzwerk {netzname}",
                                  befund=befund, herkunft=", ".join(autoren),
                                  titel=f"Aus Netzwerk {netzname}")
        with self.p.lock:
            self.db.execute(
                f"UPDATE netz_freigabe SET uebernommen=1 WHERE netz_id=? AND "
                f"item_id IN ({','.join('?' * len(item_ids))})",
                (netz_id, *item_ids))
            self.db.commit()
        return fid

    # --------------------------------------------- Gegenstelle (eingehend)
    def anfrage_beitreten(self, k: dict) -> dict:
        netz_id, token, m = k.get("netz_id"), k.get("token"), k.get("mitglied")
        if not (netz_id and token and isinstance(m, dict)):
            raise NetzwerkFehler("unvollständige Anfrage")
        sig = k.pop("signatur", "")
        if not pruefen(m.get("pubkey", ""), k, sig) or \
                pod_id_aus(m["pubkey"]) != m.get("pod_id"):
            raise NetzwerkFehler("Signatur ungültig")
        if abs(time.time() - float(k.get("ts", 0))) > MAX_ALTER:
            raise NetzwerkFehler("Anfrage zu alt")
        with self.p.lock:
            e = self.db.execute("SELECT * FROM netz_einladung WHERE token=? "
                                "AND netz_id=?", (token, netz_id)).fetchone()
            if not e or e["benutzt_von"] or e["ablauf"] < time.time():
                raise NetzwerkFehler("Einladung ungültig, abgelaufen oder "
                                     "bereits benutzt")
            self.db.execute("UPDATE netz_einladung SET benutzt_von=? WHERE "
                            "token=?", (m["pod_id"], token))
            self._mitglied_eintragen(self._nachweis(
                netz_id, m["pod_id"], str(m.get("name", ""))[:80], m["pubkey"],
                str(m.get("adresse", ""))[:200]))
            n = self.db.execute("SELECT * FROM netz WHERE netz_id=?",
                                (netz_id,)).fetchone()
            mitglieder = [json.loads(z["nachweis"]) for z in self.db.execute(
                "SELECT nachweis FROM netz_mitglied WHERE netz_id=? AND "
                "status='aktiv'", (netz_id,))]
            self.db.commit()
            self.p.geaendert = True
        daten = {"netz_id": netz_id, "name": n["name"],
                 "beschreibung": n["beschreibung"], "gruender": n["gruender"],
                 "schluessel": n["schluessel"], "mitglieder": mitglieder}
        return {"daten": daten, "signatur": self.signieren(daten)}

    def anfrage_abgleich(self, k: dict) -> dict:
        netz_id, von = k.get("netz_id"), k.get("von")
        sig = k.pop("signatur", "")
        with self.p.lock:
            m = self._mitglied(netz_id, von)
            if m is None:
                raise NetzwerkFehler("kein Mitglied")
            if not pruefen(m["pubkey"], k, sig):
                raise NetzwerkFehler("Signatur ungültig")
            if abs(time.time() - float(k.get("ts", 0))) > MAX_ALTER:
                raise NetzwerkFehler("Anfrage zu alt")
            # Adresse des Anfragenden aktualisieren, falls mitgeschickt
            if k.get("adresse") and k["adresse"] != m["adresse"]:
                self.db.execute("UPDATE netz_mitglied SET adresse=? WHERE "
                                "netz_id=? AND pod_id=?",
                                (str(k["adresse"])[:200], netz_id, von))
            self.db.execute("UPDATE netz_mitglied SET zuletzt_gesehen=?, "
                            "fehler=NULL WHERE netz_id=? AND pod_id=?",
                            (time.time(), netz_id, von))
            seit = float(k.get("seit", 0))
            jetzt = time.time()
            freigaben = [{"netz_id": z["netz_id"], "item_id": z["item_id"],
                          "autor_pod": z["autor_pod"],
                          "autor_name": z["autor_name"],
                          "inhalt": json.loads(z["inhalt"]), "ts": z["ts"],
                          "signatur": z["signatur"]}
                         for z in self.db.execute(
                             "SELECT * FROM netz_freigabe WHERE netz_id=? AND "
                             "empfangen>? ORDER BY empfangen LIMIT 2000",
                             (netz_id, seit))]
            mitglieder = [json.loads(z["nachweis"]) for z in self.db.execute(
                "SELECT nachweis FROM netz_mitglied WHERE netz_id=? AND "
                "status='aktiv'", (netz_id,))]
            schluessel = self._schluessel(netz_id)
            self.db.commit()
        return verschluesseln(schluessel, {"freigaben": freigaben,
                                           "mitglieder": mitglieder,
                                           "jetzt": jetzt})

    # --------------------------------------------- Abgleich (ausgehend)
    def abgleichen(self, netz_id: str | None = None) -> dict:
        ergebnis = {"neu": 0, "erreicht": 0, "fehler": 0}
        with self.p.lock:
            netze = [netz_id] if netz_id else [z["netz_id"] for z in
                                              self.db.execute(
                                                  "SELECT netz_id FROM netz")]
        for nid in netze:
            with self.p.lock:
                partner = [dict(z) for z in self.db.execute(
                    "SELECT * FROM netz_mitglied WHERE netz_id=? AND "
                    "status='aktiv' AND pod_id!=? AND adresse!=''",
                    (nid, self.pod_id))]
                schluessel = self._schluessel(nid)
            for m in partner:
                anfrage = {"netz_id": nid, "von": self.pod_id,
                           "seit": m["seit"] or 0, "ts": time.time(),
                           "adresse": self.dienst.eigene_adresse() or ""}
                try:
                    paket = self.dienst.senden(
                        m["adresse"], "/netz/abgleich",
                        {**anfrage, "signatur": self.signieren(anfrage)})
                    daten = entschluesseln(schluessel, paket)
                except Exception as e:                      # noqa: BLE001
                    ergebnis["fehler"] += 1
                    with self.p.lock:
                        self.db.execute("UPDATE netz_mitglied SET fehler=? "
                                        "WHERE netz_id=? AND pod_id=?",
                                        (str(e)[:200], nid, m["pod_id"]))
                        self.db.commit()
                    continue
                ergebnis["erreicht"] += 1
                ergebnis["neu"] += self._einspielen(nid, m, daten)
            with self.p.lock:
                self.db.execute("UPDATE netz SET zuletzt_abgleich=? WHERE "
                                "netz_id=?", (time.time(), nid))
                self.db.commit()
        if ergebnis["neu"]:
            self.p.geaendert = True
        return ergebnis

    def _einspielen(self, netz_id: str, partner: dict, daten: dict) -> int:
        neu = 0
        with self.p.lock:
            bekannt = {z["pod_id"]: z["pubkey"] for z in self.db.execute(
                "SELECT pod_id, pubkey FROM netz_mitglied WHERE netz_id=?",
                (netz_id,))}
            # Mitglieder: nur mit Bürgschaft eines bekannten Mitglieds
            for _ in range(3):              # Ketten: A bürgt B, B bürgt C
                for nw in daten.get("mitglieder", []):
                    d = nw.get("daten", {})
                    if d.get("netz_id") != netz_id or \
                            pod_id_aus(d.get("pubkey", "")) != d.get("pod_id"):
                        continue
                    buerge = bekannt.get(d.get("eingeladen_von"))
                    if buerge and pruefen(buerge, d, nw.get("signatur", "")):
                        if d["pod_id"] not in bekannt or \
                                d["pod_id"] == d["eingeladen_von"]:
                            self._mitglied_eintragen(nw)
                            bekannt[d["pod_id"]] = d["pubkey"]
            # Freigaben: nur mit gültiger Autorensignatur
            for f in daten.get("freigaben", []):
                pub = bekannt.get(f.get("autor_pod"))
                kern = {k: f.get(k) for k in ("netz_id", "item_id", "autor_pod",
                                              "autor_name", "inhalt", "ts")}
                if not pub or kern["netz_id"] != netz_id or \
                        not pruefen(pub, kern, f.get("signatur", "")):
                    continue
                r = self.db.execute(
                    "INSERT OR IGNORE INTO netz_freigabe VALUES "
                    "(?,?,?,?,?,?,?,?,0,0)",
                    (netz_id, f["item_id"], f["autor_pod"], f["autor_name"],
                     json.dumps(f["inhalt"], ensure_ascii=False), f["ts"],
                     f["signatur"], time.time()))
                neu += r.rowcount
            self.db.execute("UPDATE netz_mitglied SET seit=?, zuletzt_gesehen=?,"
                            " fehler=NULL WHERE netz_id=? AND pod_id=?",
                            (daten.get("jetzt", 0), time.time(), netz_id,
                             partner["pod_id"]))
            self.db.commit()
        return neu


# ---------------------------------------------------------- Netzwerkdienst
class _AnschlussServer(ThreadingHTTPServer):
    """Tor schließt gehaltene Verbindungen gern abrupt — das ist kein Fehler
    und gehört nicht als Traceback ins Protokoll."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class NetzwerkDienst:
    """Der von außen erreichbare Anschluss (über Tor) und der Client für
    ausgehende Anfragen an andere Teilnehmer."""

    def __init__(self, einstellungen, tor, aktuelles_projekt):
        self.einst = einstellungen
        self.tor = tor
        self.aktuell = aktuelles_projekt      # () -> Netzwerke | None
        self.server: ThreadingHTTPServer | None = None
        self.port = int(einstellungen.get("netzwerk_port") or 8711)

    def eigene_adresse(self) -> str | None:
        if self.tor is not None and self.tor.bereit and self.tor.onion:
            return f"http://{self.tor.onion}"
        if os.environ.get("INDRANET_NETZ_ADRESSE"):       # Tests, LAN
            return os.environ["INDRANET_NETZ_ADRESSE"]
        return None

    def senden(self, adresse: str, pfad: str, koerper: dict) -> dict:
        import httpx2 as httpx
        from urllib.parse import urlparse
        host = urlparse(adresse).hostname or ""
        if host.endswith(".onion"):
            if self.tor is None or not self.tor.bereit:
                raise NetzwerkFehler("Tor läuft nicht — .onion-Adressen sind "
                                     "nur über Tor erreichbar.")
            proxy = f"socks5://127.0.0.1:{self.tor.socks_port}"
        elif host in ("127.0.0.1", "localhost") or host.startswith(
                ("192.168.", "10.")):
            proxy = None
        else:
            from netz import Netzweg
            proxy = Netzweg(self.einst, self.tor).proxy()
        with httpx.Client(proxy=proxy, timeout=90) as c:
            r = c.post(adresse.rstrip("/") + pfad, json=koerper)
        if r.status_code >= 400:
            try:
                fehler = r.json().get("fehler")
            except Exception:                               # noqa: BLE001
                fehler = f"HTTP {r.status_code}"
            raise NetzwerkFehler(fehler or f"HTTP {r.status_code}")
        return r.json()

    # -------------------------------------------------------- Anschluss
    def starten(self) -> None:
        if self.server is not None:
            return
        dienst = self

        class Anschluss(BaseHTTPRequestHandler):
            server_version = "IndraNet"
            sys_version = ""
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _antwort(self, obj, code=200):
                roh = json.dumps(obj, ensure_ascii=False).encode()
                if code >= 400:
                    self.close_connection = True
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)

            def do_GET(self):
                if self.path == "/netz/ping":
                    return self._antwort({"indranet": 2})
                self._antwort({"fehler": "unbekannt"}, 404)

            def do_POST(self):
                laenge = int(self.headers.get("Content-Length") or 0)
                if laenge > MAX_KOERPER:
                    return self._antwort({"fehler": "zu groß"}, 413)
                try:
                    k = json.loads(self.rfile.read(laenge) or b"{}")
                except json.JSONDecodeError:
                    return self._antwort({"fehler": "kein JSON"}, 400)
                netze = dienst.aktuell()
                if netze is None:
                    return self._antwort({"fehler": "Teilnehmer hat gerade "
                                          "kein Projekt geöffnet"}, 503)
                try:
                    if self.path == "/netz/beitreten":
                        return self._antwort(netze.anfrage_beitreten(k))
                    if self.path == "/netz/abgleich":
                        return self._antwort(netze.anfrage_abgleich(k))
                except NetzwerkFehler as e:
                    return self._antwort({"fehler": str(e)}, 403)
                self._antwort({"fehler": "unbekannt"}, 404)

        self.server = _AnschlussServer(("127.0.0.1", self.port), Anschluss)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stoppen(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server = None
