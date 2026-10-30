"""
IndraNet — Indra-Knoten (Pod)
==============================

    Indra-Juwel   policy.py         Schutzstufen, Freigaben
    Navigator     navigator*.py     Parser + Vorlagen, eigener Prozess
    Firewall      firewall.py       geschlossenes Schema, JSON, kein pickle
    Speicher      store.py          Aussagen über SQLite
    Verifikation  verification.py   Beleglage, Belege, Prüflisten
    Resolver      resolver.py       Entity Resolution, Cluster statt Aliase
    Graph         graph.py          Pfade über rekursive CTEs
    Föderation    federation.py     Indra-Signal über PSI
    Axon          crypto_axon.py    Transport, Web of Trust

Die beiden Ausgänge sind streng getrennt:

    frage()   geht über die Firewall zum Sprachmodell. Liefert Text,
              niemals Belege oder Dokumentkennungen.
    belege()  bleibt auf der vertrauenswürdigen Seite, kontrolliert vom
              Indra-Juwel.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import subprocess
import sys
from pathlib import Path

import graph
from auth import AnmeldeFehler, Konten, Sitzung
from crypto_axon import Identitaet, Inbox, WebOfTrust
from federation import Foederation
from firewall import (PREDICATES, AuditLog, validate_answer, validate_question,
                      validate_request, validate_response)
from policy import PolicyEngine, Rolle, Stufe
from resolver import EntityResolver, block_key, strict_key
from store import Beleglage, Store
from verification import Verifikation

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "navigator_worker.py")


def _navigator_start() -> tuple[list, dict, str | None]:
    """Wie der Navigator-Unterprozess zu starten ist.

    Aus dem Quelltext heraus: Python mit dem Worker-Skript.
    Als gepackte Anwendung: die Programmdatei selbst mit Rollenschalter,
    weil dort kein Interpreter zur Verfuegung steht.
    """
    umgebung = dict(os.environ)
    # UTF-8 im Unterprozess erzwingen. Unter Windows verwendet Python sonst
    # die Konsolen-Codepage (cp1252); Umlaute in Frage und Antwort kommen
    # dann verstuemmelt an, und der Parser findet sein Muster nicht.
    # Unter Linux faellt das nicht auf, weil dort UTF-8 Vorgabe ist.
    umgebung["PYTHONIOENCODING"] = "utf-8"
    umgebung["PYTHONUTF8"] = "1"
    if getattr(sys, "frozen", False):
        umgebung["INDRANET_ROLE"] = "navigator"
        return [sys.executable], umgebung, None
    umgebung.pop("INDRANET_ROLE", None)
    return [sys.executable, "-u", WORKER], umgebung, os.path.dirname(WORKER)


class Pod:
    def __init__(self, name: str, *, datei: str | Path = ":memory:",
                 inbox_wurzel: str | Path = "/tmp/indranet",
                 identitaet: Identitaet | None = None,
                 navigator: bool = True,
                 passphrase: str | None = None,
                 schluesseldatei: str | Path | None = None):
        """`passphrase` oder `schluesseldatei` oeffnen einen verschluesselten
        Behaelter. Ohne beides laeuft der Pod im Speicher oder auf einer
        unverschluesselten Datei — das ist nur fuer Tests gedacht."""
        self.name = name
        self.ident = identitaet or Identitaet(name)
        self.pod_id = self.ident.pod_id
        self.vault = None

        self.resolver = EntityResolver()
        if passphrase is not None or schluesseldatei is not None:
            from vault import Vault
            self.vault = Vault(datei, passphrase=passphrase,
                               schluesseldatei=schluesseldatei)
            db = (self.vault.oeffnen() if self.vault.existiert()
                  else self.vault.anlegen())
            self.store = Store(":memory:", resolver=self.resolver, db=db)
        else:
            self.store = Store(datei, resolver=self.resolver)
        self.konten = Konten(self.store.db)

        # Dokumentenspeicher — nur bei verschluesseltem Behaelter. Ohne
        # Behaelter gibt es keinen Schluessel, und Belege unverschluesselt
        # abzulegen waere schlimmer als sie gar nicht abzulegen.
        self.dokumente = None
        if self.vault is not None:
            from docstore import Dokumentenspeicher
            ziel = Path(str(datei))
            self.dokumente = Dokumentenspeicher(
                ziel.parent / (ziel.stem + "-belege"),
                self.vault.dokumentschluessel())

        self.policy = PolicyEngine(pod_id=self.pod_id)
        self.verifikation = Verifikation(self.store, self.policy,
                                         dokumente=self.dokumente)
        self.audit = AuditLog()
        self._extrakt_cache: dict = {}      # doc_id -> Extraktion

        self.wot = WebOfTrust(self.ident)
        self.wot.bekannte[self.pod_id]["resolver"] = self.resolver.fingerprint()
        self.inbox = Inbox(inbox_wurzel)
        self.foed = Foederation(self.ident, self.wot, self.inbox, self.policy,
                                self.resolver.fingerprint())
        self.externe: dict = {}
        self.proc = None
        if navigator:
            befehl, umgebung, ordner = _navigator_start()
            self.proc = subprocess.Popen(
                befehl, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                text=True, encoding="utf-8", bufsize=1,
                cwd=ordner, env=umgebung,
                creationflags=(subprocess.CREATE_NO_WINDOW
                               if sys.platform == "win32" else 0))

    # ------------------------------------------------------------- Betrieb
    def _send(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _recv(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("Navigator-Prozess beendet")
        return json.loads(line)

    # ----------------------------------------------------------- Anmeldung
    def anmelden(self, benutzer: str, passwort: str,
                 herkunft: str = "lokal") -> Sitzung:
        return self.konten.anmelden(benutzer, passwort, herkunft)

    def rolle(self, token: str | None) -> Rolle:
        """Rolle aus der Sitzung — nicht aus der Anfrage."""
        return self.konten.rolle_aus_sitzung(token)

    def erstkonto(self, benutzer: str, passwort: str,
                  anzeige: str = "") -> dict:
        return self.konten.anlegen(benutzer, passwort, Rolle.ADMIN,
                                   anzeige=anzeige)

    @property
    def offen(self) -> bool:
        """Ob eine Anmeldung ueberhaupt noetig ist. Ein Pod ohne Konten ist
        ein Einzelplatz-Pod; sobald ein Konto besteht, gilt Anmeldepflicht."""
        return self.konten.anzahl() == 0

    # -------------------------------------------------------------- Sichern
    def sichern(self) -> dict:
        """Schreibt den Stand in den verschluesselten Behaelter."""
        if self.vault is None:
            return {"hinweis": "kein Behaelter — Pod laeuft unverschluesselt"}
        return self.vault.sichern(self.store.db)

    def close(self) -> None:
        if self.vault is not None:
            try:
                self.vault.sichern(self.store.db)
                self.vault.schliessen()
            except Exception:                                  # noqa: BLE001
                pass
        if self.proc is not None:
            try:
                self._send({"cmd": "stop"})
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()
            self.proc = None
        try:
            self.store.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------ Pfad 1: Frage
    def frage(self, text: str) -> dict:
        """Natürlichsprachliche Frage über die Firewall.

        Liefert alle passenden Fakten mit Beleglage. Mehrdeutigkeit ist
        hier keine Schwäche, sondern eine Eigenschaft der Welt — der
        Navigator formuliert nur den ersten, die Oberfläche zeigt alle.
        """
        validate_question(text)
        self._send({"question": text})

        msg = self._recv()
        if msg["phase"] == "extract_failed":
            self.audit.record("N->C", "extraktion", note=msg["reason"])
            return {"status": msg["reason"], "antwort": None, "fakten": [],
                    "warnungen": []}

        req = validate_request(msg["request"])                # GRENZE hinein
        self.audit.record("N->C", "abfrage",
                          predicate_id=req["predicate_id"], obj=req["object"])

        praedikat = PREDICATES[req["predicate_id"]]
        fakten = self.store.frage(praedikat, req["object"])
        lebend = [f for f in fakten if f.beleglage is not Beleglage.WIDERRUFEN]

        if not lebend:
            status, subjekt = "NO_MATCH", None
        elif len(lebend) == 1:
            status, subjekt = "MATCH", lebend[0].antwort
        else:
            status, subjekt = "AMBIGUOUS", None

        resp = validate_response({"v": 1, "req_id": req["req_id"],
                                  "status": status, "subject": subjekt})
        self.audit.record("C->N", "ergebnis", status=status, subject=subjekt)
        self._send({"response": resp})

        msg = self._recv()
        text_out = validate_answer(msg["answer"])
        if msg["warnings"]:
            self.audit.record("N->C", "verworfen",
                              note="unbelegt: " + ", ".join(msg["warnings"]))
        return {"status": status, "antwort": text_out, "praedikat": praedikat,
                "objekt": req["object"], "fakten": fakten,
                "warnungen": msg["warnings"]}

    # ------------------------------------------------------ Pfad 2: Beleg
    def belege(self, fact_id: str, rolle: Rolle) -> dict:
        return self.verifikation.belege(fact_id, rolle)

    def beweiskette(self, fact_id: str, rolle: Rolle) -> dict:
        return self.verifikation.beweiskette(fact_id, rolle)

    # -------------------------------------------------------- Handerfassung
    def dokument_anlegen(self, *, art: str, titel: str, quelle: str,
                         stufe: Stufe, erfasst_von: str,
                         sha256: str | None = None, ablageort: str = "",
                         notiz: str = "", datei: str | Path | bytes | None = None,
                         dateiname: str = "", typ: str = "") -> dict:
        """Legt einen Beleg an: Datei, Notiz oder freie Quelle.

        `art` = "datei"  -> Pruefsumme wird im Browser berechnet, die Datei
                            selbst erreicht den Pod nie
                "notiz"  -> eigene Aufzeichnung, ueber ihre Pruefsumme
                            festgehalten
                "quelle" -> alles ohne Datei: Auskunft, Webseite, Register
        """
        from provenance import Dokument
        if art == "datei" and datei is not None:
            # Beleg wird MITGESPEICHERT, verschluesselt im Ablageordner.
            # Der Regelfall fuer freie Journalistinnen ohne Redaktionsserver.
            if self.dokumente is None:
                raise ValueError(
                    "Belege können nur in einem verschlüsselten Pod abgelegt "
                    "werden. Legen Sie den Pod mit Passphrase an.")
            # Erst die Pruefsumme, dann ablegen: Die Dokumentkennung folgt
            # aus der Pruefsumme und muss feststehen, bevor verschluesselt
            # wird. Ein zweiter Durchlauf ueber die Datei ist billiger als
            # nachtraeglich am Kopfsatz zu flicken.
            from docstore import pruefsumme
            sha, groesse = pruefsumme(datei)
            dok = Dokument.aus_pruefsumme(
                sha, titel=titel, quelle=quelle, stufe=stufe,
                erfasst_von=erfasst_von, ablageort="[im Pod]")

            schon_da = self.dokumente.enthaelt(dok.doc_id)
            if not schon_da:
                self.dokumente.ablegen(dok.doc_id, datei,
                                       dateiname=dateiname or titel, typ=typ)
            self.store.dokument_aufnehmen(dok)

            # Sofort pruefen, ob Text herauszuholen ist. Ein Scan ohne
            # Textebene soll beim Ablegen auffallen, nicht erst dann, wenn
            # jemand eine Fundstelle sucht.
            lesbar = {}
            try:
                from extract import extrahieren
                roh = (datei if isinstance(datei, (bytes, bytearray))
                       else Path(datei).read_bytes())
                e = extrahieren(roh, dateiname or titel)
                self._extrakt_cache[dok.doc_id] = e
                lesbar = {"text_abschnitte": len(e.abschnitte),
                          "text_zeichen": e.zeichen,
                          "text_hinweis": e.hinweis}
            except Exception as fehler:                        # noqa: BLE001
                lesbar = {"text_abschnitte": 0,
                          "text_hinweis": f"Text nicht lesbar: {fehler}"}

            return {**lesbar, "doc_id": dok.doc_id, "titel": dok.titel,
                    "quelle": dok.quelle, "stufe": dok.stufe.name,
                    "sha256": dok.sha256, "ablageort": "[im Pod]",
                    "abgelegt": True, "bytes": groesse,
                    "dateiname": dateiname or titel,
                    "schon_vorhanden": schon_da, "notiz": ""}

        if art == "datei":
            if not sha256:
                raise ValueError("Prüfsumme fehlt")
            dok = Dokument.aus_pruefsumme(
                sha256, titel=titel, quelle=quelle, stufe=stufe,
                erfasst_von=erfasst_von, ablageort=ablageort or None)
        elif art == "notiz":
            if not notiz.strip():
                raise ValueError("Notiztext fehlt")
            dok = Dokument.notiz(notiz, titel=titel, quelle=quelle,
                                 stufe=stufe, erfasst_von=erfasst_von)
        else:
            dok = Dokument.virtuell(f"{quelle}|{titel}|{ablageort}",
                                    titel=titel, quelle=quelle, stufe=stufe,
                                    erfasst_von=erfasst_von)
        self.store.dokument_aufnehmen(dok)
        return {"doc_id": dok.doc_id, "titel": dok.titel,
                "quelle": dok.quelle, "stufe": dok.stufe.name,
                "sha256": dok.sha256, "ablageort": dok.pfad,
                "notiz": notiz if art == "notiz" else ""}

    def beleg_oeffnen(self, doc_id: str, rolle: Rolle,
                      ziel: str | Path) -> dict:
        """Entschlüsselt ein abgelegtes Belegdokument zum Ansehen.

        Der Zugriff läuft über das Indra-Juwel: Wer den Beleg nicht
        einsehen darf, bekommt auch die Datei nicht.
        """
        if self.dokumente is None or not self.dokumente.enthaelt(doc_id):
            raise ValueError("kein abgelegtes Dokument zu dieser Kennung")
        z = self.store.db.execute(
            "SELECT stufe, titel FROM dokument WHERE doc_id=?",
            (doc_id,)).fetchone()
        if z is None:
            raise ValueError(f"unbekannter Beleg {doc_id}")
        entscheidung = self.policy.beleg_einsehen(rolle, Stufe(z["stufe"]))
        if not entscheidung:
            raise PermissionError(entscheidung.grund)
        pfad = self.dokumente.ausgeben(doc_id, ziel)
        return {"datei": str(pfad), "bytes": pfad.stat().st_size,
                "titel": z["titel"]}

    # ------------------------------------------------------ Textextraktion
    def beleg_text(self, doc_id: str, rolle: Rolle):
        """Liest den Text eines abgelegten Belegs — mit Fundstellen.

        Laeuft ueber das Indra-Juwel: Wer den Beleg nicht einsehen darf,
        bekommt auch seinen Text nicht.
        """
        from extract import extrahieren
        if self.dokumente is None or not self.dokumente.enthaelt(doc_id):
            raise ValueError("kein abgelegtes Dokument zu dieser Kennung")
        z = self.store.db.execute(
            "SELECT stufe, titel FROM dokument WHERE doc_id=?",
            (doc_id,)).fetchone()
        if z is None:
            raise ValueError(f"unbekannter Beleg {doc_id}")
        ent = self.policy.beleg_einsehen(rolle, Stufe(z["stufe"]))
        if not ent:
            raise PermissionError(ent.grund)

        wenn = self._extrakt_cache.get(doc_id)
        if wenn is None:
            ang = self.dokumente.angaben(doc_id)
            wenn = extrahieren(self.dokumente.inhalt(doc_id),
                               ang.get("dateiname") or z["titel"])
            self._extrakt_cache[doc_id] = wenn
        return wenn

    def beleg_suchen(self, doc_id: str, begriff: str, rolle: Rolle,
                     grenze: int = 30) -> list:
        """Sucht im Belegtext und liefert Fundstellen mit Umfeld.

        Das ist der Punkt der ganzen Extraktion: nicht "kommt vor", sondern
        "S. 14, in diesem Satz" — direkt uebernehmbar in die Erfassung.
        """
        return self.beleg_text(doc_id, rolle).suchen(begriff)[:grenze]

    def beleg_angaben(self, doc_id: str) -> dict | None:
        if self.dokumente is None or not self.dokumente.enthaelt(doc_id):
            return None
        return self.dokumente.angaben(doc_id)

    def aussage_erfassen(self, doc_id: str, subjekt: str, praedikat: str,
                         objekt: str, *, fundstelle: str = "",
                         zitat: str = "", erfasst_von: str = "") -> dict:
        """Erfasst eine einzelne Aussage von Hand.

        Ohne Beleg geht das nicht — `doc_id` ist Pflicht. Das ist der
        gleiche Grundsatz wie beim Import: Fakten ohne Fundstelle entstehen
        gar nicht erst.
        """
        vorhanden = self.store.db.execute(
            "SELECT 1 FROM dokument WHERE doc_id=?", (doc_id,)).fetchone()
        if not vorhanden:
            raise ValueError(f"unbekannter Beleg {doc_id}")
        for feld, wert in (("Subjekt", subjekt), ("Objekt", objekt)):
            if not (wert or "").strip():
                raise ValueError(f"{feld} fehlt")
        from resolver import PREDICATE_SCHEMA
        if praedikat not in PREDICATE_SCHEMA:
            raise ValueError(f"unbekanntes Prädikat {praedikat}")

        fid = self.store.behaupten(
            doc_id, subjekt.strip(), praedikat, objekt.strip(),
            fundstelle=fundstelle.strip() or "von Hand erfasst",
            zitat=zitat.strip() or None, erfasst_von=erfasst_von)
        fakt = self.store.fakt(fid)
        return {"fact_id": fid,
                "subjekt": fakt.subjekt, "praedikat": fakt.praedikat,
                "objekt": fakt.objekt, "beleglage": fakt.beleglage.value,
                "quellen": fakt.quellen}

    # ----------------------------------------------------------- Korrektur
    def aussage_aendern(self, aussage_id: str, **kv) -> dict:
        return self.store.aussage_aendern(aussage_id, **kv)

    def aussage_verwerfen(self, aussage_id: str, grund: str,
                          pruefer: str = "") -> dict:
        return self.store.aussage_verwerfen(aussage_id, grund, pruefer)

    def aussage_widerrufen(self, aussage_id: str, grund: str,
                           pruefer: str = "") -> dict:
        return self.store.aussage_widerrufen(aussage_id, grund, pruefer)

    def korrekturen(self, grenze: int = 50) -> list:
        return self.store.korrekturen(grenze)

    # ------------------------------------------------ Sicherung und Export
    def sicherung(self, ziel=None) -> dict:
        from export import sichern
        return sichern(self, ziel)

    def sicherungsstand(self) -> dict:
        from export import letzte_sicherung
        return letzte_sicherung(self)

    def kette_exportieren(self, fact_id: str, rolle: Rolle,
                          sprache: str = "de") -> str:
        from export import beweiskette_markdown
        return beweiskette_markdown(self, fact_id, rolle, sprache)

    def dossier(self, fact_ids: list, rolle: Rolle, *, titel: str = "",
                sprache: str = "de") -> str:
        from export import dossier_markdown
        return dossier_markdown(self, fact_ids, rolle, titel=titel,
                                sprache=sprache)

    # ------------------------------------------------------------ Abfragen
    def fakten(self, praedikat: str, objekt: str) -> list:
        return self.store.frage(praedikat, objekt)

    def verbindungen(self, von: str, nach: str, max_schritte: int = 4) -> list:
        return graph.pfade(self.store, von, nach, max_schritte)

    def netz(self, entitaet: str, tiefe: int = 2) -> dict:
        return graph.umfeld(self.store, entitaet, tiefe)

    def schluesselfiguren(self, entitaet: str, tiefe: int = 2) -> list:
        return graph.zentralitaet(self.store, entitaet, tiefe)

    # -------------------------------------------------- Entity Resolution
    def vorschlaege(self, schwelle: float = 0.80) -> list:
        """Verschmelzungsvorschläge. Verschmilzt nichts."""
        getrennt = self.store.getrennt_erklaert()
        raus = []
        for v in self.resolver.vorschlaege(schwelle=schwelle):
            if (v.key_a, v.key_b) in getrennt or (v.key_b, v.key_a) in getrennt:
                continue
            if self.store._cid(v.key_a) == self.store._cid(v.key_b):
                continue                      # bereits im selben Cluster
            raus.append(v)
        return raus

    def verschmelzen(self, von_key: str, nach_key: str, *, pruefer: str,
                     begruendung: str) -> dict:
        return self.store.verschmelzen(von_key, nach_key, pruefer=pruefer,
                                       begruendung=begruendung)

    def trennen(self, a: str, b: str, *, pruefer: str, begruendung: str) -> None:
        self.store.trennen_festhalten(a, b, pruefer=pruefer,
                                      begruendung=begruendung)

    # ---------------------------------------------------------- Föderation
    def index_bauen(self) -> dict:
        return self.foed.index_bauen(self.store, self.verifikation)

    def kennenlernen(self, anderer: "Pod") -> None:
        self.wot.vorstellen({**anderer.ident.export(),
                             "resolver": anderer.resolver.fingerprint()})

    def vertrauen_setzen(self, pod_id: str) -> None:
        self.wot.bekannte[pod_id]["vertraut"] = True

    # ------------------------------------------------------ Externe Quellen
    def quelle_anmelden(self, quelle) -> None:
        """Meldet eine externe Quelle an diesem Pod an."""
        quelle.store = self.store
        self.externe[quelle.name] = quelle

    def abgleichen(self, quelle_name: str, **kw) -> list:
        """Gleicht die eigenen Entitäten gegen eine externe Quelle ab.

        Der Abgleich läuft lokal: Die Entitätsliste des Pods verlässt das
        Gerät nicht. Treffer sind Funde, keine Aussagen — die Übernahme ist
        ein eigener, menschlich freigegebener Schritt.
        """
        return self.externe[quelle_name].abgleichen(self, **kw)

    def treffer_uebernehmen(self, tripel: list, *, quelle_name: str,
                            titel: str, stufe, erfasst_von: str) -> dict:
        from sources import treffer_uebernehmen
        return treffer_uebernehmen(self, [], quelle_name=quelle_name,
                                   titel=titel, stufe=stufe,
                                   erfasst_von=erfasst_von, tripel=tripel)

    def quellen_gesundheit(self) -> list:
        from sources import Quelle
        return Quelle.gesundheit(self.store)

    # -------------------------------------------------------------- Status
    def stats(self) -> dict:
        return {"pod": self.name, "pod_id": self.pod_id,
                **self.store.stats(),
                **self.verifikation.uebersicht(),
                "policy": self.policy.bericht(),
                "konten": self.konten.bericht(),
                "verschluesselt": self.vault is not None,
                "vertraute_pods": sum(1 for p in self.wot.bekannte.values()
                                      if p.get("vertraut")) - 1}
