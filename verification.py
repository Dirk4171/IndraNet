"""
IndraNet — Verifikation
========================

Journalismus ist nicht Abruf, sondern Prüfung. Palantirs eigentliches
Produkt ist nicht die Datenbank, sondern das, was Ermittler acht Stunden am
Tag damit tun. Das journalistische Gegenstück ist dieser Ablauf:

    Was ist bestätigt?      >= 2 unabhängige Quellen
    Was hängt an einer?     Einzelquelle — vor Veröffentlichung nachlegen
    Was ist umstritten?     Quellen widersprechen sich bei einem Prädikat,
                            das nur einen Wert haben kann
    Was ist widerrufen?     Dokument oder Aussage zurückgezogen
    Woran hängt was?        Welche Fakten fallen, wenn dieses Dokument fällt

Dazu der Belegzugriff: der zweite Pfad aus dem Pod, am Sprachmodell vorbei
und vom Indra-Juwel kontrolliert.
"""

from __future__ import annotations

import hashlib
import json
import time

from policy import Entscheidung, PolicyEngine, Rolle, Stufe
from store import Beleglage, Store


class Verifikation:
    def __init__(self, store: Store, policy: PolicyEngine, dokumente=None):
        self.store = store
        self.policy = policy
        self.dokumente = dokumente          # Dokumentenspeicher, optional

    # ------------------------------------------------------------ Stufen
    def stufe_von(self, fact_id: str) -> Stufe:
        """Ein Fakt ist so schutzbedürftig wie seine schutzbedürftigste
        Aussage — auch wenn dieselbe Tatsache anderswo öffentlich steht."""
        aussagen = self.store.aussagen_zu(fact_id)
        if not aussagen:
            return Stufe.INTERN
        return Stufe(max(a["stufe"] for a in aussagen))

    # ------------------------------------------------------------ Belege
    def belege(self, fact_id: str, rolle: Rolle) -> dict:
        """Belege eines Fakts, gefiltert nach Rolle.

        Zurückgehaltene Belege werden nicht verschwiegen, sondern
        geschwärzt: Die Journalistin soll wissen, dass es weitere gibt.
        """
        aussagen = self.store.aussagen_zu(fact_id)
        if not aussagen:
            return {"fact_id": fact_id, "stufe": None, "belege": [],
                    "zugriff": "keine Belege hinterlegt"}

        gesamt = self.policy.beleg_einsehen(rolle, self.stufe_von(fact_id))
        eintraege = []
        for a in aussagen:
            stufe = Stufe(a["stufe"])
            if self.policy.beleg_einsehen(rolle, stufe):
                eintraege.append({
                    "status": "offen", "aussage_id": a["aussage_id"],
                    "doc_id": a["doc_id"], "quelle": a["quelle"],
                    "stufe": stufe.name, "fundstelle": a["fundstelle"],
                    "zitat": a["zitat"], "erfasst_von": a["erfasst_von"],
                    "ts": a["ts"], "widerrufen": bool(a["widerrufen"]
                                                      or a["doc_weg"]),
                    "widerruf_grund": a["widerruf_grund"],
                    # Liegt das Dokument verschluesselt im Pod? Dann kann
                    # die Oberflaeche es zum Ansehen anbieten.
                    "abgelegt": bool(self.dokumente is not None
                                     and self.dokumente.enthaelt(a["doc_id"])),
                })
            else:
                eintraege.append({
                    "status": "zurueckgehalten", "stufe": stufe.name,
                    "grund": f"{stufe.name} verlangt eine höhere Rolle",
                    "ts": a["ts"],
                })
        return {"fact_id": fact_id, "stufe": self.stufe_von(fact_id).name,
                "belege": eintraege, "zugriff": gesamt.grund}

    def beweiskette(self, fact_id: str, rolle: Rolle) -> dict:
        """Maschinenlesbare Kette für Veröffentlichung und Gericht.

        Enthält Prüfsummen, keine Inhalte. Wer die Kette prüft, braucht die
        Originaldokumente — genau so soll es sein.
        """
        f = self.store.fakt(fact_id)
        belege = self.belege(fact_id, rolle)
        docs = {}
        for a in self.store.aussagen_zu(fact_id):
            z = self.store.db.execute(
                "SELECT * FROM dokument WHERE doc_id=?", (a["doc_id"],)).fetchone()
            if self.policy.beleg_einsehen(rolle, Stufe(z["stufe"])):
                docs[z["doc_id"]] = {
                    "titel": z["titel"], "quelle": z["quelle"],
                    "stufe": Stufe(z["stufe"]).name, "sha256": z["sha256"],
                    "widerrufen": bool(z["widerrufen"]),
                    "widerruf_grund": z["widerruf_grund"]}

        kette = {
            "format": "indranet-beweiskette-1",
            "fact_id": fact_id,
            "aussage": None if f is None else
                       f"{f.subjekt} · {f.praedikat} · {f.objekt}",
            "beleglage": None if f is None else f.beleglage.value,
            "unabhaengige_quellen": [] if f is None else f.quellen,
            "stufe": belege["stufe"],
            "belege": [b for b in belege["belege"]],
            "dokumente": docs,
            "erstellt": round(time.time(), 3),
        }
        kette["sha256"] = hashlib.sha256(json.dumps(
            kette, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return kette

    # --------------------------------------------------------- Prüfliste
    def alle_fakten(self) -> list:
        """Alle abgeleiteten Fakten mit ihrer Beleglage."""
        from resolver import INVERSE
        gesehen, raus = set(), []
        # Hinrichtung
        for z in self.store.db.execute(
                "SELECT DISTINCT praedikat, o_key FROM aussage"):
            for f in self.store.frage(z["praedikat"], z["o_key"]):
                if f.fact_id not in gesehen:
                    gesehen.add(f.fact_id); raus.append(f)
        # Gegenrichtung — nur dort werden Widersprüche sichtbar
        for z in self.store.db.execute(
                "SELECT DISTINCT praedikat, s_key FROM aussage"):
            for f in self.store.frage(INVERSE[z["praedikat"]], z["s_key"]):
                if f.beleglage.value == "UMSTRITTEN":
                    gesehen.discard(f.fact_id)
                    raus = [x for x in raus if x.fact_id != f.fact_id]
                if f.fact_id not in gesehen:
                    gesehen.add(f.fact_id); raus.append(f)
        return raus

    def prueflisten(self) -> dict:
        """Was vor einer Veröffentlichung noch Arbeit braucht."""
        fakten = self.alle_fakten()
        geprueft = {z["fact_id"] for z in self.store.db.execute(
            "SELECT DISTINCT fact_id FROM pruefung WHERE ergebnis='bestaetigt'")}
        return {
            "umstritten": [f for f in fakten
                           if f.beleglage is Beleglage.UMSTRITTEN],
            "einfach_belegt": [f for f in fakten
                               if f.beleglage is Beleglage.EINFACH_BELEGT
                               and f.fact_id not in geprueft],
            "widerrufen": [f for f in fakten
                           if f.beleglage is Beleglage.WIDERRUFEN],
            "bestaetigt": [f for f in fakten
                           if f.beleglage is Beleglage.BESTAETIGT],
        }

    def haengt_an(self, doc_id: str) -> dict:
        """Welche Fakten fallen, wenn dieses Dokument fällt?

        Im faktenzentrierten Modell war das praktisch nicht zu beantworten.
        Hier ist es eine Abfrage — und vor jedem Widerruf die erste Frage.
        """
        betroffen, allein = [], []
        for a in self.store.db.execute(
                "SELECT aussage_id, s_key, praedikat, o_key FROM aussage "
                "WHERE doc_id=?", (doc_id,)):
            fid = self.store.fact_id(self.store._cid(a["s_key"]),
                                     a["praedikat"],
                                     self.store._cid(a["o_key"]))
            f = self.store.fakt(fid)
            if f is None:
                continue
            betroffen.append(f)
            uebrig = {x["quelle"] for x in self.store.aussagen_zu(fid)
                      if x["doc_id"] != doc_id and not x["widerrufen"]
                      and not x["doc_weg"]}
            if not uebrig:
                allein.append(f)
        return {"doc_id": doc_id, "betroffen": betroffen,
                "faellt_ersatzlos": allein}

    # ----------------------------------------------------------- Prüfung
    def pruefen(self, fact_id: str, ergebnis: str, *, pruefer: str,
                notiz: str = "") -> None:
        """Hält eine menschliche Prüfentscheidung fest."""
        if ergebnis not in ("bestaetigt", "zweifelhaft", "verworfen"):
            raise ValueError("ergebnis: bestaetigt | zweifelhaft | verworfen")
        self.store.db.execute(
            "INSERT INTO pruefung (fact_id,ergebnis,pruefer,notiz,ts) "
            "VALUES (?,?,?,?,?)", (fact_id, ergebnis, pruefer, notiz,
                                   time.time()))
        self.store.db.commit()

    def pruefungen(self, fact_id: str) -> list:
        return [dict(z) for z in self.store.db.execute(
            "SELECT * FROM pruefung WHERE fact_id=? ORDER BY ts", (fact_id,))]

    def uebersicht(self) -> dict:
        p = self.prueflisten()
        gesamt = sum(len(v) for v in p.values())
        return {"fakten": gesamt,
                **{k: len(v) for k, v in p.items()},
                "anteil_bestaetigt": round(
                    len(p["bestaetigt"]) / gesamt * 100, 1) if gesamt else 0.0}
