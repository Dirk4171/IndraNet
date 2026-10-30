"""
IndraNetz — Indra-Signal (föderierter Abgleich)
===============================================

Die Korrektur an Whitepaper v0.1, Abschnitt 8.2: Der Klartext-Broadcast
verrät jedem Teilnehmer das Rechercheziel. Hier fließt stattdessen ein
geblendeter Kurvenpunkt.

ABLAUF
------
    Alice                          Bob
      |  hash_to_curve + blenden     |
      |----- r·P (verschlüsselt) --->|
      |                              |  b·(r·P), lernt nichts über P
      |<---- b·r·P -----------------|
      |  r⁻¹ anwenden -> b·P         |
      |  gegen Bobs Bloom-Indizes    |
      |  prüfen                      |

KLASSIFIKATION OHNE RÜCKFRAGE
-----------------------------
Ein Signal soll nicht nur "Treffer" sagen, sondern auch wie heikel Bobs
Material ist. Bob kann das aber nicht beantworten — er weiß ja nicht, wonach
gefragt wurde. Deshalb veröffentlicht er EINEN Bloom-Index JE SCHUTZSTUFE.
Alice prüft ihren PRF-Wert gegen alle und liest die Stufe aus dem Treffer
ab, ohne dass Bob je erfährt, worum es ging.

Whistleblower-Material kann per Policy vollständig aus der Indizierung
herausfallen. Dann existiert es für die Föderation schlicht nicht.

WAS BLEIBT
----------
Bob erfährt, DASS Alice etwas gefragt hat, und wie oft. Das ist der Preis
für Ratenbegrenzung, die ihrerseits nötig ist, damit Alice keine
Namenslisten durchprobiert. Wer auch das verbergen will, braucht anonyme
Zugangsnachweise über einen Mixnet-Pfad — der Weg, den DatashareNetwork
geht, und der nächste sinnvolle Ausbauschritt.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from crypto_axon import AxonFehler, Identitaet, Inbox, Kanal, WebOfTrust
from policy import PolicyEngine, Stufe
from psi import BloomIndex, PSIClient, PSIServer


@dataclass
class SignalTreffer:
    pod_id: str
    pod_name: str
    treffer: bool
    klassifikation: str | None = None
    stufe: str | None = None
    kollaboration_moeglich: bool = False

    def __str__(self) -> str:
        if not self.treffer:
            return f"  {self.pod_name:<18} kein Treffer"
        return (f"  {self.pod_name:<18} TREFFER  Klasse {self.klassifikation}"
                + ("  (gesprächsbereit)" if self.kollaboration_moeglich else ""))


@dataclass
class Foederation:
    """Föderationsschicht eines Pods."""

    eigen: Identitaet
    wot: WebOfTrust
    inbox: Inbox
    policy: PolicyEngine
    resolver_fingerprint: str

    psi_server: PSIServer = None
    kanaele: dict = field(default_factory=dict)          # pod_id -> Kanal
    fremd_indizes: dict = field(default_factory=dict)    # pod_id -> {stufe: Bloom}
    offene_anfragen: dict = field(default_factory=dict)  # req_id -> Zustand
    kollaborationsbereit: bool = True
    protokoll: list = field(default_factory=list)

    def __post_init__(self):
        if self.psi_server is None:
            self.psi_server = PSIServer(self.eigen.pod_id)

    # ------------------------------------------------------- Indizierung
    def index_bauen(self, store, verifikation) -> dict:
        """Baut je Schutzstufe einen Bloom-Index über die eigenen Entitäten.

        Eine Entität erbt die höchste Schutzstufe, in der sie vorkommt.
        Steht ein Name nur in einer Whistleblower-Übergabe, taucht er nur
        im Whistleblower-Index auf — und der verlässt den Pod gar nicht,
        wenn die Policy das so vorsieht.
        """
        stufe_je_entitaet: dict[str, Stufe] = {}
        for z in store.db.execute(
                "SELECT c1.cluster_id AS s, c2.cluster_id AS o, d.stufe "
                "FROM aussage a "
                "JOIN cluster c1 ON c1.schluessel=a.s_key "
                "JOIN cluster c2 ON c2.schluessel=a.o_key "
                "JOIN dokument d ON d.doc_id=a.doc_id "
                "WHERE a.widerrufen=0 AND d.widerrufen=0"):
            for cid in (z["s"], z["o"]):
                st = Stufe(z["stufe"])
                if cid not in stufe_je_entitaet or st > stufe_je_entitaet[cid]:
                    stufe_je_entitaet[cid] = st

        nach_stufe: dict[Stufe, list] = {}
        for cid, st in stufe_je_entitaet.items():
            nach_stufe.setdefault(st, []).append(cid)

        indizes = {}
        for stufe, entitaeten in nach_stufe.items():
            if not self.policy.signal_senden(stufe):
                continue                     # Stufe verlässt den Pod nicht
            indizes[stufe.name] = self.psi_server.indizieren(sorted(entitaeten))
        self._eigene_indizes = indizes
        return {s: i.n for s, i in indizes.items()}

    # --------------------------------------------------------- Verbinden
    def verbinden(self, gegen_id: str) -> None:
        """Handschlag anstoßen. Prüft vorher das Web of Trust und die
        Resolver-Gleichheit."""
        if not self.wot.vertraut(gegen_id):
            raise AxonFehler(f"{gegen_id} ist nicht vertraut")
        self.wot.resolver_pruefen(gegen_id, self.resolver_fingerprint)
        k = Kanal(self.eigen, self.wot, gegen_id)
        self.kanaele[gegen_id] = k
        self.inbox.zustellen(gegen_id, k.angebot())

    def index_verteilen(self) -> int:
        """Schickt die eigenen Bloom-Indizes an alle verbundenen Pods."""
        n = 0
        for gegen_id, k in self.kanaele.items():
            if not k.bereit:
                continue
            self.inbox.zustellen(gegen_id, k.verschliessen({
                "action": "psi_index",
                "indizes": {s: i.export() for s, i in self._eigene_indizes.items()},
                "kollaborationsbereit": self.kollaborationsbereit,
            }))
            n += 1
        return n

    # ------------------------------------------------------------ Signal
    def signal_starten(self, entitaet_key: str) -> str:
        """Sendet eine geblendete Anfrage an alle verbundenen Pods."""
        req_id = uuid.uuid4().hex[:16]
        client = PSIClient(self.eigen.pod_id)
        zustand = {"entitaet": entitaet_key, "client": client,
                   "blend": {}, "treffer": [], "ts": time.time()}
        for gegen_id, k in self.kanaele.items():
            if not k.bereit:
                continue
            geblendet, r = client.blenden(entitaet_key)
            zustand["blend"][gegen_id] = r
            self.inbox.zustellen(gegen_id, k.verschliessen({
                "action": "indra_signal_request",
                "request_id": req_id,
                "blinded": geblendet,
            }))
        self.offene_anfragen[req_id] = zustand
        self.protokoll.append({"aktion": "signal_gesendet", "req": req_id,
                               "empfaenger": len(zustand["blend"])})
        return req_id

    def ergebnisse(self, req_id: str) -> list[SignalTreffer]:
        return self.offene_anfragen.get(req_id, {}).get("treffer", [])

    # ------------------------------------------------------- Posteingang
    def posteingang(self) -> dict:
        """Arbeitet alle eingegangenen Nachrichten ab."""
        zaehler = {"handschlag": 0, "index": 0, "anfragen": 0,
                   "antworten": 0, "abgelehnt": 0}
        for msg in self.inbox.abholen(self.eigen.pod_id):
            typ = msg.get("typ")
            try:
                if typ == "axon_hello":
                    k = Kanal(self.eigen, self.wot, "")
                    ack = k.antwort(msg)
                    self.kanaele[msg["von"]] = k
                    self.inbox.zustellen(msg["von"], ack)
                    zaehler["handschlag"] += 1
                elif typ == "axon_hello_ack":
                    self.kanaele[msg["von"]].abschliessen(msg)
                    zaehler["handschlag"] += 1
                elif typ == "axon_umschlag":
                    self._umschlag(msg, zaehler)
            except (AxonFehler, PermissionError, KeyError) as e:
                zaehler["abgelehnt"] += 1
                self.protokoll.append({"aktion": "abgelehnt", "von":
                                       msg.get("von"), "grund": str(e)[:80]})
        return zaehler

    def _umschlag(self, msg: dict, zaehler: dict) -> None:
        k = self.kanaele[msg["von"]]
        inhalt = k.oeffnen(msg)
        aktion = inhalt.get("action")

        if aktion == "psi_index":
            self.fremd_indizes[msg["von"]] = {
                s: BloomIndex.laden(d) for s, d in inhalt["indizes"].items()}
            self.fremd_indizes[msg["von"]]["_kollab"] = inhalt.get(
                "kollaborationsbereit", False)
            zaehler["index"] += 1

        elif aktion == "indra_signal_request":
            antwort = self.psi_server.auswerten(msg["von"], inhalt["blinded"])
            self.inbox.zustellen(msg["von"], k.verschliessen({
                "action": "indra_signal_response",
                "request_id": inhalt["request_id"],
                "evaluated": antwort,
                "kollaborationsbereit": self.kollaborationsbereit,
            }))
            zaehler["anfragen"] += 1
            self.protokoll.append({"aktion": "signal_beantwortet",
                                   "von": msg["von"],
                                   "hinweis": "Inhalt unbekannt (geblendet)"})

        elif aktion == "indra_signal_response":
            self._auswerten(msg["von"], inhalt)
            zaehler["antworten"] += 1

    def _auswerten(self, von: str, inhalt: dict) -> None:
        zustand = self.offene_anfragen.get(inhalt["request_id"])
        if not zustand:
            return
        client: PSIClient = zustand["client"]
        prf = client.entblenden(inhalt["evaluated"], zustand["blend"][von])

        indizes = self.fremd_indizes.get(von, {})
        stufe_name = None
        for name, idx in indizes.items():
            if name.startswith("_"):
                continue
            if client.pruefen(prf, idx):
                # höchste Stufe gewinnt
                if stufe_name is None or Stufe[name] > Stufe[stufe_name]:
                    stufe_name = name

        name = self.wot.bekannte.get(von, {}).get("name", von)
        zustand["treffer"].append(SignalTreffer(
            pod_id=von, pod_name=name, treffer=stufe_name is not None,
            klassifikation=PolicyEngine.signal_klasse(Stufe[stufe_name])
            if stufe_name else None,
            stufe=stufe_name,
            kollaboration_moeglich=bool(inhalt.get("kollaborationsbereit"))
            and stufe_name is not None,
        ))
