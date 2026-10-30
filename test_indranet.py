"""
IndraNet — Testsuite
=====================

Geprüft wird, was eine Redaktion sich zusagen lassen muss.

    python3 test_indranet.py
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

import psi as PSI
import webui
from clearing import Lichtung, LichtungGeschlossen
from crypto_axon import AxonFehler, Identitaet, Kanal, WebOfTrust
from firewall import (PREDICATE_IDS, FirewallViolation, validate_request,
                      validate_response)
from ingest import importiere_tripel
from pod import Pod
from policy import Rolle, Stufe
from provenance import Dokument
from resolver import T, block_key, strict_key
from store import Beleglage, Store

_ok = _fail = 0


def gilt(name, bedingung, detail=""):
    global _ok, _fail
    if bedingung:
        _ok += 1
        print(f"  [ok]     {name}" + (f"   {detail}" if detail else ""))
    else:
        _fail += 1
        print(f"  [FEHLER] {name}" + (f"   {detail}" if detail else ""))


def blockiert(name, fn, fehler=FirewallViolation):
    global _ok, _fail
    try:
        fn()
    except fehler as e:
        _ok += 1
        print(f"  [blockiert] {name:<44} {str(e)[:30]}")
    else:
        _fail += 1
        print(f"  [DURCHGELASSEN] {name:<40} <-- FEHLER")


def _pod(navigator=False):
    p = Pod("test", navigator=navigator)
    importiere_tripel(p, [
        ("Svensson Family Trust", "beneficial_owner_of", "Mare Liberum Ltd."),
        ("Mare Liberum Ltd.", "registered_in", "British Virgin Islands"),
        ("Mare Liberum Ltd.", "holds_shares_in", "Nordkap Shipping AS"),
        ("Anders Holm", "director_of", "Nordkap Shipping AS")],
        titel="Register", quelle="HR Oslo", stufe=Stufe.OEFFENTLICH,
        erfasst_von="a")
    return p


# ====================================================== 1 Aussage-Modell
def t_aussagen():
    print("\n1) Aussage-Modell")
    p = _pod()
    f = p.fakten("beneficial_owner_of", "Mare Liberum Ltd.")[0]
    gilt("Fakt aus Aussage abgeleitet", f.subjekt == "Svensson Family Trust")
    gilt("eine Quelle -> EINFACH_BELEGT",
         f.beleglage is Beleglage.EINFACH_BELEGT)

    importiere_tripel(p, [("Svensson Family Trust", "beneficial_owner_of",
                           "Mare Liberum Limited")],
                      titel="Leak", quelle="Übergabe 2026",
                      stufe=Stufe.VERTRAULICH, erfasst_von="a")
    f = p.fakten("beneficial_owner_of", "Mare Liberum Ltd.")[0]
    gilt("zweite unabhängige Quelle -> BESTAETIGT",
         f.beleglage is Beleglage.BESTAETIGT, ", ".join(f.quellen))
    gilt("Schreibvariante fällt in denselben Cluster", f.aussagen == 2)

    importiere_tripel(p, [("Svensson Family Trust", "beneficial_owner_of",
                           "Mare Liberum Ltd.")],
                      titel="Kopie", quelle="HR Oslo",
                      stufe=Stufe.OEFFENTLICH, erfasst_von="a")
    f = p.fakten("beneficial_owner_of", "Mare Liberum Ltd.")[0]
    gilt("gleiche Quelle zählt nicht doppelt", len(f.quellen) == 2)
    p.close()


def t_widerspruch():
    print("\n2) Widerspruch statt Überlagerungsartefakt")
    p = _pod()
    importiere_tripel(p, [("Mare Liberum Ltd.", "registered_in", "Panama")],
                      titel="DB", quelle="Handelsdatenbank",
                      stufe=Stufe.OEFFENTLICH, erfasst_von="a")
    wo = p.fakten("registry_of", "Mare Liberum Ltd.")
    gilt("zwei Sitze -> UMSTRITTEN",
         all(f.beleglage is Beleglage.UMSTRITTEN for f in wo), f"{len(wo)}")
    gilt("Widerspruch benennt die Gegenposition",
         any("Panama" in f.widersprueche for f in wo))

    was = p.fakten("registered_in", "Panama")
    gilt("Gegenrichtung ist kein Widerspruch",
         was[0].beleglage is not Beleglage.UMSTRITTEN)

    importiere_tripel(p, [("Ingrid Bech", "director_of", "Nordkap Shipping AS")],
                      titel="R2", quelle="HR Oslo", stufe=Stufe.OEFFENTLICH,
                      erfasst_von="a")
    d = p.fakten("director_of", "Nordkap Shipping AS")
    gilt("mehrere Direktoren sind kein Widerspruch",
         len(d) == 2 and all(f.beleglage is not Beleglage.UMSTRITTEN
                             for f in d))
    p.close()


def t_widerruf():
    print("\n3) Widerruf und Abhängigkeit")
    p = _pod()
    doc = list(p.store.db.execute("SELECT doc_id FROM dokument"))[0]["doc_id"]
    h = p.verifikation.haengt_an(doc)
    gilt("Abhängigkeiten vor dem Widerruf abfragbar",
         len(h["betroffen"]) == 4 and len(h["faellt_ersatzlos"]) == 4)

    info = p.store.dokument_widerrufen(doc, "Fälschung nachgewiesen")
    gilt("Widerruf erfasst alle Aussagen", info["aussagen"] == 4)
    f = p.fakten("beneficial_owner_of", "Mare Liberum Ltd.")[0]
    gilt("abhängiger Fakt ist WIDERRUFEN",
         f.beleglage is Beleglage.WIDERRUFEN)
    gilt("widerrufene Kanten fallen aus Pfaden",
         p.verbindungen("Svensson Family Trust", "Anders Holm") == [])
    p.close()


def t_er():
    print("\n4) Entity Resolution ohne Neuindizierung")
    p = Pod("test", navigator=False)
    importiere_tripel(p, [
        ("Mueller Handels GmbH", "holds_shares_in", "Alpha Ltd."),
        ("Müller Handels GmbH", "holds_shares_in", "Beta Ltd."),
        ("Nordkap Shipping AS", "holds_shares_in", "Gamma Ltd."),
        ("Nordkap Shipping AB", "holds_shares_in", "Delta Ltd.")],
        titel="R", quelle="HR", stufe=Stufe.OEFFENTLICH, erfasst_von="a")

    v = p.vorschlaege(0.75)
    gilt("Vorschläge erzeugt", len(v) >= 2, f"{len(v)}")
    gilt("Rechtsform-Warnung vorhanden",
         any(x.warnung for x in v if "AS" in x.a or "AS" in x.b))
    vor = p.fakten("shares_held_by", "Mueller Handels GmbH")
    gilt("Vorschläge ändern nichts", len(vor) == 1)

    mu = [x for x in v if "ller" in x.a or "ller" in x.b][0]
    p.verschmelzen(mu.key_a, mu.key_b, pruefer="test", begruendung="gleiche HRB")
    nach = p.fakten("shares_held_by", "Müller Handels GmbH")
    gilt("Verschmelzung wirkt sofort, ohne Neuindizierung", len(nach) == 2,
         ", ".join(sorted(f.antwort for f in nach)))
    gilt("Verschmelzung protokolliert",
         p.store.stats()["verschmelzungen"] == 1)

    na = [x for x in v if x.warnung][0]
    p.trennen(na.key_a, na.key_b, pruefer="test", begruendung="AS≠AB")
    gilt("getrennt Erklärtes verschwindet aus der Liste",
         not any(x.warnung for x in p.vorschlaege(0.75)))
    p.close()


def t_firewall():
    print("\n5) Firewall")
    gut = {"v": 1, "req_id": "a1b2c3d4e5f60718",
           "predicate_id": PREDICATE_IDS["beneficial_owner_of"],
           "object": "Mare Liberum Ltd."}
    resp = {"v": 1, "req_id": "a1b2c3d4e5f60718", "status": "MATCH",
            "subject": "Svensson Family Trust"}
    gilt("gültige Anfrage passiert",
         validate_request(gut)["predicate_id"] == gut["predicate_id"])
    blockiert("Array als Objekt",
              lambda: validate_request({**gut, "object": np.zeros(9)}))
    blockiert("Zusatzfeld doc_id",
              lambda: validate_response({**resp, "doc_id": "doc:x"}))
    blockiert("Zusatzfeld fact_id",
              lambda: validate_response({**resp, "fact_id": "f:x"}))
    blockiert("Beleglage nach aussen",
              lambda: validate_response({**resp, "beleglage": "BESTAETIGT"}))
    blockiert("Subjekt bei NO_MATCH",
              lambda: validate_response({**resp, "status": "NO_MATCH"}))

    p = _pod(navigator=True)
    a = p.frage("Wem gehört Mare Liberum Ltd.?")
    gilt("Frage über die Firewall beantwortet", a["status"] == "MATCH",
         "" if a["status"] == "MATCH" else f"erhalten: {a['status']}")
    # Umlaute in beide Richtungen: unter Windows der haeufigste Stolperstein.
    gilt("Umlaute passieren die Prozessgrenze unversehrt",
         a["antwort"] is not None and "gehört" not in str(a["antwort"] or ""),
         str(a["antwort"])[:46])
    gilt("Antworttext ohne Dokumentkennung",
         "doc:" not in (a["antwort"] or ""))
    gilt("Fakten kommen am Modell vorbei", len(a["fakten"]) == 1)
    gilt("Audit-Kette unversehrt", p.audit.verify() and len(p.audit.entries) >= 2)
    p.close()


def t_belege():
    print("\n6) Belegpfad und Schutzstufen")
    p = _pod()
    importiere_tripel(p, [("Politiker L", "beneficial_owner_of",
                           "Svensson Family Trust")],
                      titel="Übergabe", quelle="anonym",
                      stufe=Stufe.WHISTLEBLOWER, erfasst_von="a")
    f = p.fakten("beneficial_owner_of", "Svensson Family Trust")[0]
    gilt("Whistleblower-Beleg für JOURNALIST zurückgehalten",
         p.belege(f.fact_id, Rolle.JOURNALIST)["belege"][0]["status"]
         == "zurueckgehalten")
    gilt("...für ADMIN offen",
         p.belege(f.fact_id, Rolle.ADMIN)["belege"][0]["status"] == "offen")

    k = p.beweiskette(f.fact_id, Rolle.ADMIN)
    gilt("Beweiskette trägt Prüfsumme", len(k["sha256"]) == 64)
    gilt("Beweiskette nennt die Beleglage", k["beleglage"] is not None)
    gilt("Kette ohne Dokumentinhalt",
         all("inhalt" not in d for d in k["dokumente"].values()))
    p.close()


def t_krypto():
    print("\n7) Kryptographie")
    PSI.selbsttest()
    gilt("PSI-Selbsttest bestanden", True, f"b={hex(PSI.B)[:12]}…")
    s = PSI.PSIServer("bob", limit=2)
    idx = s.indizieren(["Mare Liberum Ltd."])
    c = PSI.PSIClient("alice")
    gb, r = c.blenden("Mare Liberum Ltd.")
    gilt("geblendete Anfrage verrät nichts", "mare" not in gb.lower())
    gilt("Treffer erkannt",
         c.pruefen(c.entblenden(s.auswerten("alice", gb), r), idx))
    gb2, r2 = c.blenden("Helios Inc.")
    gilt("Nichttreffer erkannt",
         not c.pruefen(c.entblenden(s.auswerten("alice", gb2), r2), idx))
    blockiert("Ratenbegrenzung greift",
              lambda: s.auswerten("alice", gb), PermissionError)

    a, b = Identitaet("a"), Identitaet("b")
    wa, wb = WebOfTrust(a), WebOfTrust(b)
    for w, f in ((wa, b), (wb, a)):
        w.vorstellen({**f.export(), "resolver": "gleich"})
        w.bekannte[f.pod_id]["vertraut"] = True
    ka, kb = Kanal(a, wa, b.pod_id), Kanal(b, wb, "")
    ka.abschliessen(kb.antwort(ka.angebot()))
    u = ka.verschliessen({"action": "x"})
    gilt("Nutzlast verschlüsselt", "action" not in str(u))
    gilt("entschlüsselbar", kb.oeffnen(u)["action"] == "x")
    blockiert("Replay abgewiesen", lambda: kb.oeffnen(u), AxonFehler)
    wa.bekannte[b.pod_id]["resolver"] = "anders"
    blockiert("Föderationssperre",
              lambda: wa.resolver_pruefen(b.pod_id, "gleich"), AxonFehler)


def t_lichtung():
    print("\n8) Indra-Lichtung")
    p = _pod()
    importiere_tripel(p, [("Politiker L", "beneficial_owner_of",
                           "Svensson Family Trust")],
                      titel="Übergabe", quelle="anonym",
                      stufe=Stufe.WHISTLEBLOWER, erfasst_von="a")
    offen = p.fakten("beneficial_owner_of", "Mare Liberum Ltd.")[0]
    geheim = p.fakten("beneficial_owner_of", "Svensson Family Trust")[0]

    li = Lichtung([p.pod_id, "pod:andere"])
    gilt("öffentlicher Fakt freigegeben",
         bool(li.einbringen(p, offen.fact_id, rolle=Rolle.JOURNALIST,
                            freigeber=["k"])))
    gilt("Whistleblower braucht ADMIN",
         not li.einbringen(p, geheim.fact_id, rolle=Rolle.JOURNALIST,
                           freigeber=["a", "b"]))
    gilt("Whistleblower braucht zwei Freigaben",
         not li.einbringen(p, geheim.fact_id, rolle=Rolle.ADMIN,
                           freigeber=["a"]))
    gilt("mit ADMIN und zwei Freigaben zulässig",
         bool(li.einbringen(p, geheim.fact_id, rolle=Rolle.ADMIN,
                            freigeber=["a", "b"])))
    gilt("Freigabe trägt Beleglage mit",
         li.freigaben[0].beleglage == offen.beleglage.value)

    kette = li.schliessen({p.pod_id: p.ident})
    ok, grund = Lichtung.kette_pruefen(kette, {p.pod_id: p.ident.pubkey})
    gilt("Kette prüfbar", ok, grund)
    blockiert("Zugriff nach dem Schliessen",
              lambda: li.frage("beneficial_owner_of", "Mare Liberum Ltd."),
              LichtungGeschlossen)
    kette["freigaben"][0]["aussage"] = "manipuliert"
    gilt("manipulierte Kette fällt auf",
         not Lichtung.kette_pruefen(kette, {p.pod_id: p.ident.pubkey})[0])
    p.close()


def t_webui():
    print("\n9) Weboberfläche")
    p = _pod(navigator=True)
    # Ein Pod ohne Konten ist ein Einzelplatz und laeuft als ADMIN. Fuer
    # den Rollentest braucht es echte Konten.
    p.erstkonto("admin", "geheim-2026-recherche")
    p.konten.anlegen("journalist", "auch-geheim-2026", Rolle.JOURNALIST,
                     durch="admin")
    importiere_tripel(p, [("Politiker L", "beneficial_owner_of",
                           "Svensson Family Trust")],
                      titel="Übergabe", quelle="anonym",
                      stufe=Stufe.WHISTLEBLOWER, erfasst_von="a")
    srv = webui.starte(p, port=8719)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.4)
    B = "http://127.0.0.1:8719"

    def get(u):
        return json.loads(urllib.request.urlopen(B + u).read())

    def post(u, d):
        # HTTP 400 ist eine gueltige Antwort des Servers, kein Transportfehler.
        req = urllib.request.Request(B + u, json.dumps(d).encode(),
                                     {"Content-Type": "application/json"})
        try:
            return json.loads(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read())
    try:
        html = urllib.request.urlopen(B + "/").read().decode()
        gilt("Seite wird ausgeliefert", "IndraNet" in html and len(html) > 5000)
        gilt("keine externen Ressourcen",
             "http://" not in html.replace("http://127.0.0.1", "")
             and "//fonts." not in html and "cdn" not in html.lower())
        gilt("Sprache umschaltbar",
             get("/api/sprache?lang=en")["texte"]["nav.verify"] == "Verify"
             and get("/api/sprache?lang=de")["texte"]["nav.verify"] == "Prüfen")

        a = post("/api/frage", {"frage": "Wem gehört Mare Liberum Ltd.?"})
        gilt("Frage über die API", a["status"] == "MATCH")
        fid = a["fakten"][0]["fact_id"]
        gilt("Belege rollenabhängig",
             get(f"/api/belege?fact_id={fid}&rolle=JOURNALIST")["belege"][0]
             ["status"] == "offen")

        gf = p.fakten("beneficial_owner_of", "Svensson Family Trust")[0]
        j = get(f"/api/belege?fact_id={gf.fact_id}")
        gilt("ohne Anmeldung: Whistleblower geschwärzt",
             j["belege"][0]["status"] == "zurueckgehalten"
             and "fundstelle" not in j["belege"][0])

        # Mit Anmeldung als JOURNALIST: weiterhin geschwärzt.
        req = urllib.request.Request(
            B + "/api/anmelden",
            json.dumps({"benutzer": "journalist",
                        "passwort": "auch-geheim-2026"}).encode(),
            {"Content-Type": "application/json"})
        antwort = urllib.request.urlopen(req)
        cookie = antwort.headers.get("Set-Cookie").split(";")[0]

        def get_auth(u):
            r = urllib.request.Request(B + u, headers={"Cookie": cookie})
            return json.loads(urllib.request.urlopen(r).read())

        gilt("angemeldet als JOURNALIST: weiterhin geschwärzt",
             get_auth(f"/api/belege?fact_id={gf.fact_id}")["belege"][0]
             ["status"] == "zurueckgehalten")
        gilt("Rolle kommt vom Server, nicht aus der Anfrage",
             get_auth("/api/state")["rolle"] == "JOURNALIST")

        pf = post("/api/pfad", {"von": "Svensson Family Trust",
                                "nach": "Anders Holm"})
        gilt("Pfad über die API", len(pf["pfade"]) >= 1,
             pf["pfade"][0]["schwaechstes"] if pf["pfade"] else "")
        gilt("Prüflisten ausgeliefert",
             "uebersicht" in get("/api/prueflisten"))
        gilt("Dokumentabhängigkeit ausgeliefert",
             get("/api/dokumente")["dokumente"][0]["faellt_ersatzlos"] >= 0)

        def post_auth(u, d):
            r = urllib.request.Request(
                B + u, json.dumps(d).encode(),
                {"Content-Type": "application/json", "Cookie": cookie})
            try:
                return json.loads(urllib.request.urlopen(r).read())
            except urllib.error.HTTPError as e:
                return json.loads(e.read())

        daten = {"csv": "firma,sitz\nHelios Inc.,Delaware",
                 "map": "firma:registered_in:sitz", "titel": "Web",
                 "quelle": "Weboberfläche", "stufe": "INTERN", "von": "test"}
        gilt("Import ohne Anmeldung abgewiesen",
             "fehler" in post("/api/import", daten))
        gilt("Import als JOURNALIST erlaubt",
             post_auth("/api/import", daten).get("aussagen") == 1)
        gilt("Widerruf verlangt LEITUNG",
             "fehler" in post_auth("/api/widerrufen",
                                   {"doc_id": "x", "grund": "y"}))
        gilt("fehlerhafte Zuordnung wird abgewiesen",
             "fehler" in post_auth("/api/import", {
                 "csv": "a,b\n1,2", "map": "kaputt", "titel": "t",
                 "quelle": "q", "stufe": "INTERN", "von": "v"}))
    finally:
        srv.shutdown()
        p.close()


def t_zweisprachig():
    print("\n10) Zweisprachigkeit")
    import i18n
    from navigator import adapter_a, adapter_b, pruefe_ableitbar
    gilt("Sprachtabellen vollständig",
         all(len(v) == 2 and all(v) for v in i18n.T.values()),
         f"{len(i18n.T)} Einträge")
    import resolver as _r
    gilt("Prädikat-Label in beiden Sprachen",
         len(i18n.praedikate("de")) == len(i18n.praedikate("en"))
         == len(_r.PREDICATE_SCHEMA), f"{len(_r.PREDICATE_SCHEMA)}")

    de = adapter_a("Wem gehört Mare Liberum Ltd.?")
    en = adapter_a("Who owns Mare Liberum Ltd.?")
    from firewall import PREDICATE_IDS as _PI
    gilt("gleiche Extraktion in beiden Sprachen",
         de["predicate_id"] == en["predicate_id"]
         == _PI["beneficial_owner_of"] and de["object"] == en["object"])
    gilt("Sprache wird mitgeführt", de["lang"] == "de" and en["lang"] == "en")
    gilt("Unbekanntes bleibt unbekannt (en)",
         adapter_a("How much revenue did X make?") == "UNKNOWN_PREDICATE")
    gilt("Gegenrichtung erkannt (en)",
         adapter_a("Where is Mare Liberum registered?")
         == "UNSUPPORTED_DIRECTION")

    txt, _ = adapter_b("MATCH", "Svensson Family Trust",
                       _PI["beneficial_owner_of"], "Mare Liberum Ltd.",
                       lang="en")
    gilt("englische Vorlage", "beneficial owner" in txt, txt)
    ok, unbelegt = pruefe_ableitbar(
        "The Swedish Svensson Family Trust has owned Mare Liberum Ltd. since 2016.",
        subjekt="Svensson Family Trust", objekt="Mare Liberum Ltd.",
        praedikat="beneficial_owner_of", lang="en")
    gilt("Ableitbarkeitsprüfung greift auch englisch", not ok,
         ", ".join(sorted(unbelegt)))

    p = _pod(navigator=True)
    a = p.frage("Who owns Mare Liberum Ltd.?")
    gilt("englische Frage über die Firewall",
         a["status"] == "MATCH" and "beneficial owner" in a["antwort"])
    p.close()


def t_extern():
    print("\n11) Externe Quellen")
    import json as _j
    import tempfile as _t
    from pathlib import Path as _P
    from connect_events import Ereignisquelle
    from connect_opensanctions import OpenSanctions
    from resolver import block_key
    from sources import Quelle

    tmp = _P(_t.mkdtemp())
    ftm = [
        {"id": "a1", "schema": "Person",
         "properties": {"name": ["Anders Holm"], "topics": ["role.pep"]}},
        {"id": "b2", "schema": "Company",
         "properties": {"name": ["Nordkap Shipping AS"], "topics": ["sanction"],
                        "jurisdiction": ["no"]}},
        {"id": "c3", "schema": "Company",
         "properties": {"name": ["Unbeteiligt GmbH"], "jurisdiction": ["de"]}},
        {"id": "o1", "schema": "Ownership",
         "properties": {"owner": ["a1"], "asset": ["b2"]}},
        {"id": "d1", "schema": "Directorship",
         "properties": {"director": ["a1"], "organization": ["c3"]}},
    ]
    (tmp / "os.json").write_text("\n".join(_j.dumps(x) for x in ftm))
    (tmp / "wm.json").write_text(_j.dumps([
        {"id": "ev1", "title": "Zwischenfall vor Zypern",
         "summary": "Beteiligt war die Nordkap Shipping AS.",
         "publishedAt": "2026-07-30", "category": "maritime"},
        {"id": "ev2", "title": "Ohne Bezug", "summary": "Nichts Bekanntes.",
         "publishedAt": "2026-07-29", "category": "other"}]))

    p = _pod()
    importiere_tripel(p, [("Anders Holm", "director_of", "Nordkap Shipping AS")],
                      titel="HR", quelle="Oslo", stufe=Stufe.OEFFENTLICH,
                      erfasst_von="a")
    os_q = OpenSanctions(store=p.store)
    info = os_q.holen(tmp / "os.json")
    gilt("FtM-Strom gelesen", info["entitaeten"] == 5)

    tr = os_q.abgleichen(p)
    namen = {t.entitaet for t in tr}
    gilt("Sanktionstreffer erkannt",
         any(t.art == "sanktion" for t in tr))
    gilt("PEP erkannt", any(t.art == "pep" for t in tr))
    gilt("Unbeteiligte erzeugen keinen Treffer",
         "Unbeteiligt GmbH" not in namen, ", ".join(sorted(namen)))

    vor = p.store.stats()["aussagen"]
    gilt("Abgleich legt nichts im Bestand ab",
         p.store.stats()["aussagen"] == vor)

    bekannt = {block_key(z["anzeige"]) for z in p.store.entitaeten()}
    bez = os_q.beziehungen(nur_zu=bekannt)
    gilt("nur Beziehungen zwischen bekannten Entitäten",
         all("Unbeteiligt" not in x[0] and "Unbeteiligt" not in x[2]
             for x in bez), f"{len(bez)}")
    nachbar = os_q.beziehungen(nur_zu=bekannt, beide_seiten=False)
    gilt("Nachbarschaft auf Wunsch erweitert", len(nachbar) > len(bez))

    wm = Ereignisquelle(store=p.store)
    wm.holen(tmp / "wm.json")
    ev = wm.abgleichen(p)
    gilt("Ereignis-Erwähnung gefunden", len(ev) == 1,
         ev[0].entitaet if ev else "")
    gilt("keine Doppeltreffer je Ereignis",
         len({(t.cluster_id, t.fremd_id) for t in ev}) == len(ev))

    zustand = {q["name"]: q for q in Quelle.gesundheit(p.store)}
    gilt("Quellen-Gesundheit erfasst", len(zustand) == 2)
    gilt("frische Quelle ist OK",
         zustand["OpenSanctions"]["zustand"] == "OK")
    gilt("Lizenz wird mitgeführt",
         "CC-BY-NC" in zustand["OpenSanctions"]["lizenz"])
    gilt("lokaler Abgleich ausgewiesen", zustand["OpenSanctions"]["lokal"])

    p.store.db.execute(
        "UPDATE quelle SET letzter_erfolg=? WHERE name='OpenSanctions'",
        (time.time() - 40 * 86400,))
    z2 = {q["name"]: q for q in Quelle.gesundheit(p.store)}
    gilt("veraltete Quelle wird gemeldet",
         z2["OpenSanctions"]["zustand"] == "VERALTET",
         f"{z2['OpenSanctions']['alter_tage']} Tage")

    fehlt = OpenSanctions(store=p.store, name="Kaputt")
    try:
        fehlt.holen(tmp / "gibtsnicht.json")
    except Exception:                                          # noqa: BLE001
        pass
    z3 = {q["name"]: q for q in Quelle.gesundheit(p.store)}
    gilt("gescheiterter Abruf wird protokolliert",
         z3["Kaputt"]["zustand"] == "FEHLER",
         (z3["Kaputt"]["fehler"] or "")[:34])
    p.close()


def t_vault():
    print("\n12) Verschlüsselter Behälter")
    import tempfile as _t
    from pathlib import Path as _P
    from vault import (FalschePassphrase, Vault, container_pruefen,
                       schluesseldatei_erzeugen)
    tmp = _P(_t.mkdtemp())

    v = Vault(tmp / "a.vault", passphrase="korrekt-pferd-batterie")
    db = v.anlegen()
    db.execute("CREATE TABLE g(x)")
    db.execute("INSERT INTO g VALUES ('Svensson Family Trust')")
    v.sichern(db)
    roh = (tmp / "a.vault").read_bytes()
    gilt("Klartext gelangt nicht auf die Platte", b"Svensson" not in roh)
    gilt("Kopfdaten ohne Passphrase lesbar",
         container_pruefen(tmp / "a.vault")["gueltig"])
    gilt("richtige Passphrase öffnet",
         Vault(tmp / "a.vault", passphrase="korrekt-pferd-batterie")
         .oeffnen().execute("SELECT x FROM g").fetchone()[0]
         == "Svensson Family Trust")
    blockiert("falsche Passphrase abgewiesen",
              lambda: Vault(tmp / "a.vault", passphrase="falsch").oeffnen(),
              FalschePassphrase)

    b = bytearray(roh)
    b[-24] ^= 0xFF
    (tmp / "a.vault").write_bytes(bytes(b))
    blockiert("Manipulation erkannt",
              lambda: Vault(tmp / "a.vault",
                            passphrase="korrekt-pferd-batterie").oeffnen(),
              FalschePassphrase)

    schluesseldatei_erzeugen(tmp / "k.bin")
    v2 = Vault(tmp / "b.vault", passphrase="pass", schluesseldatei=tmp / "k.bin")
    db2 = v2.anlegen()
    v2.sichern(db2)
    blockiert("Zwei-Faktor: Passphrase allein reicht nicht",
              lambda: Vault(tmp / "b.vault", passphrase="pass").oeffnen(),
              FalschePassphrase)
    gilt("Passphrase plus Schlüsseldatei öffnet",
         Vault(tmp / "b.vault", passphrase="pass",
               schluesseldatei=tmp / "k.bin").oeffnen() is not None)

    v3 = Vault(tmp / "c.vault", passphrase="alt-alt-alt-alt")
    db3 = v3.anlegen()
    db3.execute("CREATE TABLE t(x)")
    v3.passphrase_aendern(db3, neue_passphrase="neu-neu-neu-neu")
    blockiert("alte Passphrase gilt nicht mehr",
              lambda: Vault(tmp / "c.vault",
                            passphrase="alt-alt-alt-alt").oeffnen(),
              FalschePassphrase)
    gilt("neue Passphrase öffnet",
         Vault(tmp / "c.vault", passphrase="neu-neu-neu-neu").oeffnen()
         is not None)


def t_konten():
    print("\n13) Konten und Rollen")
    import tempfile as _t
    from pathlib import Path as _P
    from auth import AnmeldeFehler
    tmp = _P(_t.mkdtemp())

    p = Pod("alice", datei=tmp / "p.vault",
            passphrase="korrekt-pferd-batterie", navigator=False)
    gilt("Pod ohne Konten ist offen", p.offen)
    p.erstkonto("s.kern", "geheim-2026-recherche", "Sabine Kern")
    gilt("erstes Konto wird ADMIN",
         p.konten.rolle_von("s.kern") is Rolle.ADMIN)
    gilt("Pod mit Konto verlangt Anmeldung", not p.offen)

    p.konten.anlegen("m.roth", "auch-geheim-2026", Rolle.JOURNALIST,
                     durch="s.kern")
    blockiert("Journalist darf keine Konten anlegen",
              lambda: p.konten.anlegen("x", "passwort12", Rolle.ADMIN,
                                       durch="m.roth"), AnmeldeFehler)
    blockiert("letzter ADMIN kann sich nicht selbst herabstufen",
              lambda: p.konten.rolle_setzen("s.kern", Rolle.GAST,
                                            durch="s.kern"), AnmeldeFehler)
    blockiert("zu kurzes Passwort abgewiesen",
              lambda: p.konten.anlegen("y", "kurz", Rolle.GAST,
                                       durch="s.kern"), AnmeldeFehler)

    importiere_tripel(p, [("Politiker L", "beneficial_owner_of", "S Trust")],
                      titel="Leak", quelle="anonym",
                      stufe=Stufe.WHISTLEBLOWER, erfasst_von="s.kern")
    fid = p.verifikation.alle_fakten()[0].fact_id

    sa = p.anmelden("s.kern", "geheim-2026-recherche")
    sj = p.anmelden("m.roth", "auch-geheim-2026")
    gilt("Rolle kommt aus der Sitzung",
         p.rolle(sa.token) is Rolle.ADMIN
         and p.rolle(sj.token) is Rolle.JOURNALIST)
    gilt("ohne Sitzung nur GAST",
         p.rolle(None) is Rolle.GAST and p.rolle("erfunden") is Rolle.GAST)
    gilt("Beleg für Journalist zurückgehalten",
         p.belege(fid, p.rolle(sj.token))["belege"][0]["status"]
         == "zurueckgehalten")
    gilt("Beleg für ADMIN offen",
         p.belege(fid, p.rolle(sa.token))["belege"][0]["status"] == "offen")

    blockiert("falsches Passwort abgewiesen",
              lambda: p.anmelden("s.kern", "falsch"), AnmeldeFehler)
    blockiert("unbekanntes Konto abgewiesen",
              lambda: p.anmelden("gibtsnicht", "irgendwas"), AnmeldeFehler)
    for _ in range(5):
        try:
            p.anmelden("m.roth", "falsch")
        except AnmeldeFehler:
            pass
    blockiert("Sperre nach Fehlversuchen greift",
              lambda: p.anmelden("m.roth", "auch-geheim-2026"), AnmeldeFehler)

    gilt("Vier-Augen verlangt echte Konten",
         p.konten.freigabe_pruefen(["s.kern", "erfunden", "m.roth"])
         == {"s.kern", "m.roth"})
    gilt("Fehlversuche werden protokolliert",
         p.konten.bericht()["fehlversuche_24h"] >= 6)

    p.abmelden = p.konten.abmelden
    p.abmelden(sa.token)
    gilt("nach Abmeldung wieder GAST", p.rolle(sa.token) is Rolle.GAST)
    p.close()

    p2 = Pod("alice", datei=tmp / "p.vault",
             passphrase="korrekt-pferd-batterie", navigator=False)
    gilt("Konten überleben den Neustart", p2.konten.anzahl() == 2)
    gilt("Aussagen überleben den Neustart",
         p2.store.stats()["aussagen"] == 1)
    p2.close()


def t_vokabular():
    print("\n14) Erweitertes Prädikatsvokabular")
    import firewall as _fw
    import i18n as _i
    import resolver as _r
    import store as _s
    from navigator import adapter_a

    gilt("Vokabular umfasst 22 Grundprädikate", len(_r.INVERSE) == 22,
         f"{len(_r.PREDICATE_SCHEMA)} mit Gegenrichtung")
    gilt("Firewall-Vokabular deckungsgleich mit Speicher",
         set(_fw.PREDICATES.values()) == set(_r.PREDICATE_SCHEMA))
    gilt("Label in beiden Sprachen vollständig",
         not (set(_r.PREDICATE_SCHEMA) - set(_i.PRAEDIKAT_LABEL)))
    gilt("Funktionalität für jedes Grundprädikat festgelegt",
         not (set(_r.INVERSE) - set(_s.EIN_OBJEKT_JE_SUBJEKT)))

    for frage, erwartet in [
            ("Wer kontrolliert Nordkap AS?", "controls"),
            ("Wer bekleidet das Amt Finanzminister?", "holds_office"),
            ("Wer ist verwandt mit Anders Holm?", "family_of"),
            ("Who paid Nordstern SA?", "paid_to"),
            ("Who is sanctioned by the EU?", "sanctioned_by")]:
        r = adapter_a(frage)
        ok = isinstance(r, dict) and _fw.PREDICATES[r["predicate_id"]] == erwartet
        gilt(f"erkannt: {erwartet}", ok,
             "" if ok else str(r))
    gilt("Unbekanntes bleibt unbekannt",
         adapter_a("Wie hoch war der Umsatz 2019?") == "UNKNOWN_PREDICATE")

    p = Pod("t", navigator=True)
    importiere_tripel(p, [
        ("Anders Holm", "controls", "Nordkap AS"),
        ("Anders Holm", "holds_office", "Staatssekretär"),
        ("Nordkap AS", "paid_to", "Zypern Beteiligungs AG")],
        titel="R", quelle="Q", stufe=Stufe.OEFFENTLICH, erfasst_von="a")
    a = p.frage("Wer kontrolliert Nordkap AS?")
    gilt("neue Prädikate durch die ganze Kette",
         a["status"] == "MATCH" and "Anders Holm" in a["antwort"], a["antwort"])
    pf = p.verbindungen("Anders Holm", "Zypern Beteiligungs AG")
    gilt("Pfad über neue Prädikate", len(pf) >= 1,
         str(pf[0]) if pf else "")
    p.close()


def t_paket():
    print("\n15) Erscheinungsbild und Paketierung")
    import re as _re
    import theming
    import webui as _w

    a, b = (set(t["vars"]) for t in theming.THEMEN.values())
    gilt("beide Themen definieren denselben Variablensatz", a == b,
         f"{len(a)} Variablen")
    verwendet = set(_re.findall(r"var\((--[a-z0-9-]+)\)", _w.SEITE))
    gilt("keine undefinierte CSS-Variable",
         not (verwendet - a - {"--mono", "--eck"}))
    gilt("Themen-CSS ist eingesetzt", "__THEMEN__" not in _w.SEITE)
    extern = [x for x in _re.findall(r"https?://[^\"\s)]+", _w.SEITE)
              if "127.0.0.1" not in x]
    gilt("Oberfläche lädt nichts nach", not extern, str(extern[:2]))

    import indranet_app as app
    seite = app.SETUP_HTML
    gilt("Einrichtungsseite lädt nichts nach",
         not [x for x in _re.findall(r"https?://[^\"\s)]+", seite)
              if "127.0.0.1" not in x])
    gilt("Einrichtung kennt beide Sprachen",
         '"de"' in seite and '"en"' in seite)

    # Der Rollenschalter ist die Grundlage dafür, dass die Firewall auch in
    # der gepackten Anwendung eine echte Prozessgrenze bleibt.
    quelle = (pathlib.Path(__file__).parent / "indranet_app.py").read_text()
    schalter = quelle.index('INDRANET_ROLE") == "navigator"')
    gilt("Rollenschalter läuft vor allen anderen Importen",
         schalter < quelle.index("def datenordner"))
    gilt("Rollenschalter lädt nur den Worker",
         "import navigator_worker" in quelle
         and "from pod import" not in quelle[:schalter])

    import pod as _p
    befehl, umgebung, _ = _p._navigator_start()
    gilt("Navigator-Start im Quellbetrieb über Python",
         befehl[-1].endswith("navigator_worker.py")
         and "INDRANET_ROLE" not in umgebung)

    for datei in ("IndraNet.spec", "build_windows.bat", "installer.iss",
                  "BUILD.md", "LICENSE", "LIZENZHINWEIS.md"):
        gilt(f"vorhanden: {datei}",
             (pathlib.Path(__file__).parent / datei).exists())


def t_erfassen():
    print("\n16) Handerfassung")
    import hashlib as _h
    from provenance import Dokument

    p = _pod()
    sha = _h.sha256(b"pdf-inhalt").hexdigest()
    d = p.dokument_anlegen(art="datei", sha256=sha, titel="Leak S.14.pdf",
                           quelle="Übergabe 2026-03",
                           stufe=Stufe.WHISTLEBLOWER, erfasst_von="s.kern",
                           ablageort="D:\\Akten")
    gilt("Datei-Beleg über Prüfsumme", d["sha256"] == sha)
    gilt("Kennung folgt aus der Prüfsumme", d["doc_id"] == "doc:" + sha[:16])
    gilt("Ablageort festgehalten", d["ablageort"] == "D:\\Akten")

    a = p.aussage_erfassen(d["doc_id"], "Politiker Lindqvist",
                           "beneficial_owner_of", "Svensson Family Trust",
                           fundstelle="S. 14, Zeile 7",
                           zitat="…ultimate beneficial owner…",
                           erfasst_von="s.kern")
    gilt("Aussage erfasst", a["beleglage"] == "EINFACH_BELEGT")
    gilt("Fundstelle übernommen",
         p.belege(a["fact_id"], Rolle.ADMIN)["belege"][0]["fundstelle"]
         == "S. 14, Zeile 7")
    gilt("Erfasser festgehalten",
         p.belege(a["fact_id"], Rolle.ADMIN)["belege"][0]["erfasst_von"]
         == "s.kern")
    gilt("Schutzstufe wirkt auch bei Handerfassung",
         p.belege(a["fact_id"], Rolle.JOURNALIST)["belege"][0]["status"]
         == "zurueckgehalten")

    n = p.dokument_anlegen(art="notiz", notiz="Gespräch 3.3.: Quelle bestätigt.",
                           titel="Notiz 3.3.", quelle="eigene Recherche",
                           stufe=Stufe.VERTRAULICH, erfasst_von="s.kern")
    b = p.aussage_erfassen(n["doc_id"], "Politiker Lindqvist", "controls",
                           "Svensson Family Trust", erfasst_von="s.kern")
    gilt("Notiz als Beleg", b["quellen"] == ["eigene Recherche"])
    n2 = Dokument.notiz("Gespräch 3.3.: Quelle bestätigt.", titel="x",
                        quelle="y", stufe=Stufe.INTERN, erfasst_von="z")
    gilt("gleiche Notiz ergibt gleiche Kennung", n2.doc_id == n["doc_id"])
    n3 = Dokument.notiz("Gespräch 3.3.: Quelle widerruft.", titel="x",
                        quelle="y", stufe=Stufe.INTERN, erfasst_von="z")
    gilt("geänderte Notiz ergibt andere Kennung", n3.doc_id != n["doc_id"])

    # Handerfassung und Import müssen denselben Fakt treffen
    importiere_tripel(p, [("Politiker Lindqvist", "beneficial_owner_of",
                           "Svensson Family Trust")],
                      titel="Register", quelle="Handelsregister",
                      stufe=Stufe.OEFFENTLICH, erfasst_von="s.kern")
    f = p.store.fakt(a["fact_id"])
    gilt("Handerfassung und Import ergeben zusammen BESTAETIGT",
         f.beleglage is Beleglage.BESTAETIGT, ", ".join(f.quellen))

    blockiert("Aussage ohne Beleg abgewiesen",
              lambda: p.aussage_erfassen("doc:erfunden", "A", "controls", "B"),
              ValueError)
    blockiert("unbekanntes Prädikat abgewiesen",
              lambda: p.aussage_erfassen(n["doc_id"], "A", "gibts_nicht", "B"),
              ValueError)
    blockiert("leeres Subjekt abgewiesen",
              lambda: p.aussage_erfassen(n["doc_id"], "  ", "controls", "B"),
              ValueError)
    blockiert("ungültige Prüfsumme abgewiesen",
              lambda: p.dokument_anlegen(art="datei", sha256="abc", titel="x",
                                         quelle="y", stufe=Stufe.INTERN,
                                         erfasst_von="z"), ValueError)
    p.close()


def t_dokumentenspeicher():
    print("\n17) Verschlüsselter Dokumentenspeicher")
    import hashlib as _h
    import os as _o
    import tempfile as _t
    from pathlib import Path as _P
    from docstore import (Dokumentenspeicher, DokumentSpeicherFehler,
                          pruefsumme)

    tmp = _P(_t.mkdtemp())
    schluessel = _o.urandom(32)
    d = Dokumentenspeicher(tmp / "belege", schluessel)

    # Mehrere Bloecke, damit die Blockverkettung geprueft wird
    datei = tmp / "leak.pdf"
    inhalt = b"%PDF-1.7\n" + _o.urandom(2_600_000)
    datei.write_bytes(inhalt)

    sha, groesse = pruefsumme(datei)
    gilt("Prüfsumme vorab ohne Vollladen",
         sha == _h.sha256(inhalt).hexdigest() and groesse == len(inhalt))

    a = d.ablegen("doc:test1", datei, typ="application/pdf")
    gilt("abgelegt und Prüfsumme bestätigt", a.sha256 == sha)
    gilt("Überhang gering", a.bytes_verschluesselt - a.bytes_klar < 1000,
         f"{a.bytes_verschluesselt - a.bytes_klar} Byte")

    roh = list((tmp / "belege").glob("*.dok"))[0].read_bytes()
    gilt("kein Klartext auf der Platte", b"%PDF" not in roh)
    gilt("Dateiname verrät nichts",
         "leak" not in list((tmp / "belege").glob("*.dok"))[0].name)
    gilt("Originalname nur verschlüsselt", b"leak.pdf" not in roh)

    gilt("unverändert zurückgelesen", d.inhalt("doc:test1") == inhalt)
    ang = d.angaben("doc:test1")
    gilt("Angaben ohne Vollentschlüsselung",
         ang["dateiname"] == "leak.pdf" and ang["bytes"] == len(inhalt))

    ziel = d.ausgeben("doc:test1", tmp / "raus.pdf")
    gilt("Ausgabe identisch", ziel.read_bytes() == inhalt)

    # --- Angriffe --------------------------------------------------------
    f = list((tmp / "belege").glob("*.dok"))[0]
    orig = f.read_bytes()

    b = bytearray(orig)
    b[-40] ^= 0xFF
    f.write_bytes(bytes(b))
    blockiert("veränderter Block erkannt",
              lambda: d.inhalt("doc:test1"), DokumentSpeicherFehler)

    f.write_bytes(orig[: len(orig) // 2])
    blockiert("abgeschnittene Datei erkannt",
              lambda: d.inhalt("doc:test1"), DokumentSpeicherFehler)

    f.write_bytes(orig)
    fremd = Dokumentenspeicher(tmp / "belege", _o.urandom(32))
    blockiert("fremder Schlüssel abgewiesen",
              lambda: fremd.angaben("doc:test1"), DokumentSpeicherFehler)

    gilt("Original nach den Angriffen wieder lesbar",
         d.inhalt("doc:test1") == inhalt)
    gilt("doppelte Ablage abgelehnt",
         not d.enthaelt("doc:neu")
         and (d.ablegen("doc:neu", b"abc") is not None))
    blockiert("zweite Ablage derselben Kennung",
              lambda: d.ablegen("doc:neu", b"abc"), DokumentSpeicherFehler)
    gilt("Entfernen wirkt", d.entfernen("doc:neu") and not d.enthaelt("doc:neu"))


def t_belege_im_pod():
    print("\n18) Belege im Pod")
    import os as _o
    import tempfile as _t
    from pathlib import Path as _P

    tmp = _P(_t.mkdtemp())
    inhalt = b"%PDF-1.7\n" + _o.urandom(300_000)

    p = Pod("alice", datei=tmp / "p.vault",
            passphrase="korrekt-pferd-batterie", navigator=False)
    p.erstkonto("s.kern", "geheim-2026-recherche")
    d = p.dokument_anlegen(art="datei", datei=inhalt, titel="Leak.pdf",
                           quelle="Übergabe 2026-03",
                           stufe=Stufe.WHISTLEBLOWER, erfasst_von="s.kern",
                           dateiname="leak.pdf", typ="application/pdf")
    gilt("Beleg im Pod abgelegt", d["abgelegt"] and d["ablageort"] == "[im Pod]")
    gilt("Kennung folgt aus der Prüfsumme des Klartexts",
         d["doc_id"] == "doc:" + d["sha256"][:16])

    a = p.aussage_erfassen(d["doc_id"], "Politiker L", "beneficial_owner_of",
                           "Svensson Trust", fundstelle="S. 14",
                           erfasst_von="s.kern")
    gilt("Kennzeichen im Beleg gesetzt",
         p.belege(a["fact_id"], Rolle.ADMIN)["belege"][0]["abgelegt"])

    blockiert("Zugriff unter der Schutzstufe abgewiesen",
              lambda: p.beleg_oeffnen(d["doc_id"], Rolle.JOURNALIST,
                                      tmp / "x.pdf"), PermissionError)
    r = p.beleg_oeffnen(d["doc_id"], Rolle.ADMIN, tmp / "raus.pdf")
    gilt("ADMIN erhält das Original",
         (tmp / "raus.pdf").read_bytes() == inhalt, f"{r['bytes']} Byte")

    ordner = tmp / "p-belege"
    gilt("Ablage liegt neben dem Behälter, nicht darin",
         ordner.exists() and len(list(ordner.glob("*.dok"))) == 1)
    gilt("Behälter bleibt klein",
         (tmp / "p.vault").stat().st_size < 200_000,
         f"{(tmp / 'p.vault').stat().st_size // 1024} KB gegen "
         f"{len(inhalt) // 1024} KB Dokument")
    p.close()

    p2 = Pod("alice", datei=tmp / "p.vault",
             passphrase="korrekt-pferd-batterie", navigator=False)
    gilt("Beleg nach Neustart lesbar",
         p2.beleg_angaben(d["doc_id"])["dateiname"] == "leak.pdf")
    p2.close()

    # Ohne Behaelter gibt es keinen Schluessel — dann lieber gar nicht ablegen
    p3 = Pod("ohne", navigator=False)
    gilt("ohne Verschlüsselung kein Dokumentenspeicher", p3.dokumente is None)
    blockiert("Ablage ohne Behälter abgelehnt",
              lambda: p3.dokument_anlegen(art="datei", datei=b"x", titel="t",
                                          quelle="q", stufe=Stufe.INTERN,
                                          erfasst_von="z"), ValueError)
    p3.close()


def t_korrektur():
    print("\n19) Korrigieren, verwerfen, widerrufen")
    p = _pod()
    importiere_tripel(p, [("Svensson Famliy Trust", "beneficial_owner_of",
                           "Helios Inc.")],
                      titel="HR", quelle="Oslo", stufe=Stufe.OEFFENTLICH,
                      erfasst_von="s.kern")
    aid = [z["aussage_id"] for z in p.store.db.execute(
        "SELECT aussage_id, s_anzeige FROM aussage")
        if "Famliy" in z["s_anzeige"]][0]

    r = p.aussage_aendern(aid, subjekt="Svensson Family Trust",
                          grund="Tippfehler", pruefer="s.kern")
    gilt("Tippfehler korrigiert", "Family" in r["aussage"])
    gilt("Fakt trägt die korrigierte Schreibweise",
         p.fakten("beneficial_owner_of", "Helios Inc.")[0].subjekt
         == "Svensson Family Trust")
    gilt("alte Fassung im Protokoll",
         any("Famliy" in (k["vorher"] or "") for k in p.korrekturen()))

    # Ein Fakt kann von mehreren Aussagen getragen werden — der Widerruf
    # einer einzelnen genuegt nicht, um ihn als widerrufen zu zeigen.
    tragende = [z["aussage_id"] for z in p.store.db.execute(
        "SELECT aussage_id, s_anzeige, o_anzeige FROM aussage")
        if "Family" in z["s_anzeige"] and "Helios" in z["o_anzeige"]]
    gilt("Fakt wird von mindestens einer Aussage getragen", len(tragende) >= 1)
    p.aussage_widerrufen(tragende[0], "Quelle zurückgezogen", "s.kern")
    if len(tragende) > 1:
        gilt("bei mehreren Trägern bleibt der Fakt belegt",
             p.fakten("beneficial_owner_of", "Helios Inc.")[0].beleglage
             is not Beleglage.WIDERRUFEN)
        for weitere in tragende[1:]:
            p.aussage_widerrufen(weitere, "auch zurückgezogen", "s.kern")
    gilt("nach Widerruf aller Träger: WIDERRUFEN, aber sichtbar",
         p.fakten("beneficial_owner_of", "Helios Inc.")[0].beleglage
         is Beleglage.WIDERRUFEN)
    gilt("widerrufene Aussage bleibt in der Ablage",
         p.store.db.execute(
             "SELECT COUNT(*) FROM aussage WHERE widerrufen=1"
         ).fetchone()[0] >= 1)

    vorher = p.store.stats()["aussagen"]
    aid3 = list(p.store.db.execute(
        "SELECT aussage_id FROM aussage"))[0]["aussage_id"]
    p.aussage_verwerfen(aid3, "versehentlich erfasst", "s.kern")
    gilt("verworfene Aussage ist fort",
         p.store.stats()["aussagen"] == vorher - 1)
    gilt("Löschung bleibt im Protokoll",
         any(k["art"] == "verworfen" for k in p.korrekturen()))
    gilt("Protokoll nennt Prüfer und Grund",
         all(k["pruefer"] and k["begruendung"] for k in p.korrekturen()))

    blockiert("unbekannte Aussage abgewiesen",
              lambda: p.aussage_verwerfen("a:erfunden", "x"), KeyError)
    blockiert("leeres Subjekt abgewiesen",
              lambda: p.aussage_aendern(
                  list(p.store.db.execute(
                      "SELECT aussage_id FROM aussage"))[0]["aussage_id"],
                  subjekt="  ", grund="x"), ValueError)
    p.close()


def t_sicherung_export():
    print("\n20) Sicherung und Export")
    import tempfile as _t
    import zipfile as _z
    from pathlib import Path as _P

    tmp = _P(_t.mkdtemp())
    p = Pod("Redaktion", datei=tmp / "r.vault",
            passphrase="korrekt-pferd-batterie", navigator=False)
    p.erstkonto("s.kern", "geheim-2026-recherche")
    importiere_tripel(p, [("Svensson Family Trust", "beneficial_owner_of",
                           "Mare Liberum Ltd.")],
                      titel="Handelsregister", quelle="Register Oslo",
                      stufe=Stufe.OEFFENTLICH, erfasst_von="s.kern")
    importiere_tripel(p, [("Svensson Family Trust", "beneficial_owner_of",
                           "Mare Liberum Limited")],
                      titel="Orbis", quelle="Orbis",
                      stufe=Stufe.OEFFENTLICH, erfasst_von="s.kern")
    d = p.dokument_anlegen(art="datei", datei=b"%PDF geheim",
                           titel="Leak.pdf", quelle="Übergabe",
                           stufe=Stufe.WHISTLEBLOWER, erfasst_von="s.kern",
                           dateiname="leak.pdf")
    a = p.aussage_erfassen(d["doc_id"], "Svensson Family Trust",
                           "beneficial_owner_of", "Mare Liberum Ltd.",
                           fundstelle="S. 14", erfasst_von="s.kern")

    gilt("vor der ersten Sicherung gemeldet",
         not p.sicherungsstand()["vorhanden"])
    info = p.sicherung()
    gilt("Sicherung erstellt", _P(info["datei"]).exists())
    with _z.ZipFile(info["datei"]) as z:
        namen = z.namelist()
        gilt("Behälter enthalten", any(n.endswith(".vault") for n in namen))
        gilt("Belegdokumente enthalten",
             any(n.endswith(".dok") for n in namen), f"{info['belege']}")
        gilt("Manifest mit Prüfsummen",
             "SICHERUNG.json" in namen
             and len(json.loads(z.read("SICHERUNG.json"))["teile"]) >= 2)
        gilt("Anleitung beiliegend", "LIESMICH.txt" in namen)
        gilt("kein Klartext in der Sicherung",
             all(b"%PDF geheim" not in z.read(n) for n in namen
                 if n.endswith((".vault", ".dok"))))
    st = p.sicherungsstand()
    gilt("Sicherungsstand erkannt", st["vorhanden"] and st["tage"] < 1)

    md = p.kette_exportieren(a["fact_id"], Rolle.JOURNALIST)
    gilt("Export nennt die Beleglage", "bestätigt" in md)
    gilt("Export nennt die unabhängigen Quellen",
         "Register Oslo" in md and "Orbis" in md)
    gilt("Export enthält Prüfsummen", md.count("SHA-256") >= 2)
    gilt("Whistleblower-Beleg als zurückgehalten ausgewiesen",
         "Zurückgehaltener Beleg" in md)
    gilt("kein Dokumentinhalt im Export", "%PDF" not in md)
    gilt("Kettenprüfsumme angegeben", "Prüfsumme der Kette" in md)

    md_admin = p.kette_exportieren(a["fact_id"], Rolle.ADMIN)
    gilt("ADMIN sieht den Beleg offen",
         "Zurückgehaltener Beleg" not in md_admin and "Leak.pdf" in md_admin)

    en = p.kette_exportieren(a["fact_id"], Rolle.JOURNALIST, "en")
    gilt("englischer Export", "Evidence chain" in en
         and "corroborated" in en)

    alle = [f.fact_id for f in p.verifikation.alle_fakten()][:3]
    dos = p.dossier(alle, Rolle.ADMIN, titel="Offshore-Recherche")
    gilt("Dossier über mehrere Fakten",
         dos.startswith("# Offshore-Recherche") and dos.count("## ") >= 3)
    p.close()

    ohne = Pod("ohne", navigator=False)
    blockiert("unverschlüsselter Knoten nicht sicherbar",
              lambda: ohne.sicherung(), ValueError)
    ohne.close()


def t_extraktion():
    print("\n21) Textextraktion mit Fundstellen")
    import io as _io
    import json as _j
    import zipfile as _z
    from extract import (ExtraktionFehler, extrahieren,
                         unterstuetzte_formate)

    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    puf = _io.BytesIO()
    with _z.ZipFile(puf, "w") as z:
        ps = "".join(
            f"<w:p><w:r><w:t>{a}</w:t></w:r></w:p>" for a in
            ["Vorbemerkung.",
             "Der Berechtigte der Mare Liberum Ltd. ist der Svensson Trust."])
        z.writestr("word/document.xml",
                   f"<w:document {W}><w:body>{ps}</w:body></w:document>")
    e = extrahieren(puf.getvalue(), "leak.docx")
    gilt("docx gelesen", e.format == "docx" and len(e.abschnitte) == 2)
    gilt("Absatz als Fundstelle", e.abschnitte[0].fundstelle == "Absatz 1")
    t = e.suchen("Svensson")
    gilt("Suche liefert Fundstelle und Zitat",
         t and t[0]["fundstelle"] == "Absatz 2" and "Mare Liberum" in t[0]["zitat"],
         t[0]["fundstelle"] if t else "")

    X = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    R = ('xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
         '2006/relationships"')
    puf = _io.BytesIO()
    with _z.ZipFile(puf, "w") as z:
        z.writestr("xl/sharedStrings.xml",
                   f"<sst {X}><si><t>Mare Liberum Ltd.</t></si>"
                   f"<si><t>Panama</t></si></sst>")
        z.writestr("xl/workbook.xml",
                   f'<workbook {X} {R}><sheets><sheet name="Beteiligungen" '
                   f'r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" '
                   'Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet {X}><sheetData><row r="42">'
                   f"<c t=\"s\"><v>0</v></c><c t=\"s\"><v>1</v></c>"
                   f"</row></sheetData></worksheet>")
    e = extrahieren(puf.getvalue(), "beteiligungen.xlsx")
    gilt("xlsx gelesen", e.format == "xlsx" and e.abschnitte)
    gilt("Blatt und Zeile als Fundstelle",
         'Blatt "Beteiligungen", Zeile 42' == e.abschnitte[0].fundstelle,
         e.abschnitte[0].fundstelle)

    eml = (b"From: quelle@example.org\r\nTo: s.kern@redaktion.de\r\n"
           b"Subject: Unterlagen\r\nContent-Type: text/plain; charset=utf-8"
           b"\r\n\r\nDer Berechtigte ist der Svensson Trust.\r\n")
    e = extrahieren(eml, "post.eml")
    gilt("E-Mail gelesen", e.format == "eml" and len(e.abschnitte) >= 2)
    gilt("Kopfzeilen als eigener Abschnitt",
         e.abschnitte[0].art == "kopf" and "Subject" in e.abschnitte[0].text)

    e = extrahieren(b"firma,sitz\nMare Liberum Ltd.,Panama\n", "reg.csv")
    gilt("csv zeilenweise", e.abschnitte[1].fundstelle == "Zeile 2")
    e = extrahieren(_j.dumps({"firma": {"name": "Nordkap AS"}}).encode(),
                    "d.json")
    gilt("json mit Pfad als Fundstelle",
         e.abschnitte[0].fundstelle == "$.firma.name")
    e = extrahieren(b"<p>Mare Liberum in <b>Panama</b>.</p>", "s.html")
    gilt("html entfärbt", "Panama" in e.text and "<b>" not in e.text)
    e = extrahieren(rb"{\rtf1\ansi Anders Holm \par Direktor.}", "a.rtf")
    gilt("rtf gelesen", "Anders Holm" in e.text)

    e = extrahieren(b"\xd0\xcf\x11\xe0" + b"\x00" * 80, "alt.doc")
    gilt("altes Binärformat ehrlich gemeldet",
         not e.vollstaendig and "Office 2007" in e.hinweis)
    e = extrahieren(bytes(range(256)) * 8, "x.bin")
    gilt("Binärdatei ehrlich gemeldet",
         not e.vollstaendig and "kein" in e.hinweis.lower())

    fmt = unterstuetzte_formate()
    gilt("Formatübersicht vollständig",
         ".docx" in fmt["ohne Zusatzsoftware"] and ".pdf" in fmt["mit pypdf"]
         and ".doc" in fmt["nicht lesbar"])


def t_beleg_text():
    print("\n22) Belegtext im Pod")
    import io as _io
    import tempfile as _t
    import zipfile as _z
    from pathlib import Path as _P

    tmp = _P(_t.mkdtemp())
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    puf = _io.BytesIO()
    with _z.ZipFile(puf, "w") as z:
        ps = "".join(f"<w:p><w:r><w:t>{a}</w:t></w:r></w:p>" for a in
                     ["Vorbemerkung.",
                      "Berechtigter der Mare Liberum Ltd. ist der Svensson Trust."])
        z.writestr("word/document.xml",
                   f"<w:document {W}><w:body>{ps}</w:body></w:document>")

    p = Pod("alice", datei=tmp / "p.vault",
            passphrase="korrekt-pferd-batterie", navigator=False)
    p.erstkonto("s.kern", "geheim-2026-recherche")
    d = p.dokument_anlegen(art="datei", datei=puf.getvalue(),
                           titel="Übergabe.docx", quelle="anonyme Quelle",
                           stufe=Stufe.WHISTLEBLOWER, erfasst_von="s.kern",
                           dateiname="leak.docx")
    gilt("Text beim Ablegen sofort geprüft", d["text_abschnitte"] == 2)
    gilt("kein Hinweis bei lesbarem Dokument", not d["text_hinweis"])

    treffer = p.beleg_suchen(d["doc_id"], "Svensson", Rolle.ADMIN)
    gilt("Fundstelle im abgelegten Beleg gefunden",
         treffer and treffer[0]["fundstelle"] == "Absatz 2",
         treffer[0]["fundstelle"] if treffer else "")
    gilt("Zitat mit Umfeld", "Mare Liberum" in treffer[0]["zitat"])

    blockiert("Belegtext folgt der Schutzstufe",
              lambda: p.beleg_suchen(d["doc_id"], "Svensson",
                                     Rolle.JOURNALIST), PermissionError)

    # Fundstelle direkt in eine Aussage uebernehmen — der eigentliche Zweck
    a = p.aussage_erfassen(d["doc_id"], "Svensson Trust",
                           "beneficial_owner_of", "Mare Liberum Ltd.",
                           fundstelle=treffer[0]["fundstelle"],
                           zitat=treffer[0]["zitat"], erfasst_von="s.kern")
    beleg = p.belege(a["fact_id"], Rolle.ADMIN)["belege"][0]
    gilt("Fundstelle in die Belegkette übernommen",
         beleg["fundstelle"] == "Absatz 2")

    scan = p.dokument_anlegen(art="datei", datei=b"\x89PNG\r\n\x1a\n" + b"\x00" * 200,
                              titel="Scan.png", quelle="Kopie",
                              stufe=Stufe.INTERN, erfasst_von="s.kern",
                              dateiname="scan.png")
    gilt("nicht lesbares Format wird trotzdem abgelegt", scan["abgelegt"])
    gilt("und der Grund benannt", bool(scan["text_hinweis"]))
    p.close()


def t_netzansicht():
    print("\n23) Netzansicht")
    import json as _j
    import tempfile as _t
    import threading as _th
    import time as _ti
    import urllib.request as _u
    import webui as _w

    p = _pod()
    importiere_tripel(p, [
        ("Mare Liberum Ltd.", "holds_shares_in", "Nordkap Shipping AS"),
        ("Anders Holm", "director_of", "Nordkap Shipping AS")],
        titel="R2", quelle="Orbis", stufe=Stufe.OEFFENTLICH, erfasst_von="a")
    srv = _w.starte(p, port=8799)
    _th.Thread(target=srv.serve_forever, daemon=True).start()
    _ti.sleep(0.4)
    try:
        r = _u.Request("http://127.0.0.1:8799/api/netz",
                       _j.dumps({"entitaet": "Nordkap Shipping AS",
                                 "tiefe": 2}).encode(),
                       {"Content-Type": "application/json"})
        d = _j.loads(_u.urlopen(r).read())
        gilt("Netzdaten geliefert", d["knoten"] and d["kanten"],
             f"{len(d['knoten'])} Knoten, {len(d['kanten'])} Kanten")
        gilt("Mittelpunkt hat Abstand 0",
             any(k["abstand"] == 0 and k["anzeige"] == "Nordkap Shipping AS"
                 for k in d["knoten"]))
        gilt("Kanten tragen die Beleglage",
             all(k["beleglage"] in ("BESTAETIGT", "EINFACH_BELEGT",
                                    "UMSTRITTEN", "WIDERRUFEN")
                 for k in d["kanten"]))
        gilt("Knotengrad berechnet",
             all("grad" in k for k in d["knoten"]))

        seite = _u.urlopen("http://127.0.0.1:8799/").read().decode()
        gilt("Graph wird ohne Fremdbibliothek gezeichnet",
             "function malen(" in seite and "getContext" in seite
             and "d3" not in seite and "cesium" not in seite.lower())
        gilt("Oberfläche lädt weiterhin nichts nach",
             not [x for x in __import__("re").findall(r'https?://[^"\s)]+',
                                                      seite)
                  if "127.0.0.1" not in x])
    finally:
        srv.shutdown()
        p.close()


def main() -> int:
    print("=" * 78)
    print("IndraNet — Testsuite")
    print("=" * 78)
    for f in (t_aussagen, t_widerspruch, t_widerruf, t_er, t_firewall,
              t_belege, t_krypto, t_lichtung, t_webui, t_zweisprachig,
              t_extern, t_vault, t_konten, t_vokabular, t_erfassen,
              t_dokumentenspeicher, t_belege_im_pod, t_korrektur,
              t_sicherung_export, t_extraktion, t_beleg_text,
              t_netzansicht, t_paket):
        f()
    print("\n" + "=" * 78)
    print(f"{_ok} bestanden, {_fail} fehlgeschlagen")
    print("=" * 78)
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
