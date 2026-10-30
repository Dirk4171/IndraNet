"""
IndraNet — Vorführung / demonstration

Eine Recherche von der Übernahme bis zur signierten Beweiskette.

    python3 demo.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from clearing import Lichtung
from ingest import Zuordnung, importiere_csv, importiere_tripel
from pod import Pod
from policy import Rolle, Stufe

REGISTER = """firma,rechtsform,sitz,eigentuemer,direktor
Mare Liberum,Ltd.,British Virgin Islands,Svensson Family Trust,Anders Holm
Nordkap Shipping,AS,Norwegen,Mare Liberum Ltd.,Anders Holm
Nordstern Capital,SA,Panama,Nordkap Shipping AS,Ingrid Bech
"""


def kopf(n, titel):
    print(f"\n{'─' * 76}\n{n})  {titel}\n{'─' * 76}")


def zeige(f):
    strich = "|" * min(len(f.quellen), 5)
    wid = f"   ≠ {', '.join(f.widersprueche)}" if f.widersprueche else ""
    print(f"  {f.beleglage.value:<16}{strich:<6} {f.subjekt} · {f.praedikat} "
          f"· {f.objekt}{wid}")
    print(f"        {' · '.join(f.quellen) or '—'}")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="indranet_"))
    alice = Pod("Tagesschau", datei=tmp / "alice.vault",
                passphrase="vorfuehrung-nicht-fuer-echtes-material",
                inbox_wurzel=tmp / "inbox")
    bob = Pod("Süddeutsche", inbox_wurzel=tmp / "inbox", navigator=False)
    alice.erstkonto("s.kern", "geheim-2026-recherche", "Sabine Kern")
    alice.konten.anlegen("j.weber", "auch-geheim-2026", Rolle.JOURNALIST,
                         durch="s.kern", anzeige="Jonas Weber")
    print("=" * 76)
    print("INDRANET — von der Datenübernahme zur Beweiskette")
    print("=" * 76)
    try:
        kopf(1, "Übernahme — jede Zeile wird zu einer Aussage mit Fundstelle")
        csv = tmp / "register.csv"
        csv.write_text(REGISTER, encoding="utf-8")
        b = importiere_csv(alice, csv, [
            Zuordnung("eigentuemer", "beneficial_owner_of",
                      "{firma} {rechtsform}"),
            Zuordnung("direktor", "director_of", "{firma} {rechtsform}"),
            Zuordnung("{firma} {rechtsform}", "registered_in", "sitz")],
            titel="Handelsregister Q3", quelle="Register Oslo/BVI",
            stufe=Stufe.OEFFENTLICH, erfasst_von="s.kern@tagesschau")
        print(f"  {b}")

        importiere_tripel(alice, [
            ("Svensson Family Trust", "beneficial_owner_of",
             "Mare Liberum Limited")],
            titel="Zweitquelle", quelle="Handelsdatenbank",
            stufe=Stufe.OEFFENTLICH, erfasst_von="s.kern@tagesschau")
        importiere_tripel(alice, [
            ("Politiker Lindqvist", "beneficial_owner_of",
             "Svensson Family Trust")],
            titel="Übergabe 2026-03", quelle="anonyme Quelle",
            stufe=Stufe.WHISTLEBLOWER, erfasst_von="s.kern@tagesschau")
        importiere_tripel(alice, [
            ("Mare Liberum Ltd.", "registered_in", "Panama")],
            titel="Firmendatenbank", quelle="Orbis-Auszug",
            stufe=Stufe.OEFFENTLICH, erfasst_von="s.kern@tagesschau")

        kopf(2, "Beleglage — was trägt und was nicht")
        for f in alice.fakten("beneficial_owner_of", "Mare Liberum Ltd."):
            zeige(f)
        print("\n  Wo ist Mare Liberum registriert?")
        for f in alice.fakten("registry_of", "Mare Liberum Ltd."):
            zeige(f)
        print("\n  Zwei Quellen nennen verschiedene Sitze. Das ist kein Fehler")
        print("  des Speichers, sondern eine Feststellung über die Welt.")

        kopf(3, "Anmeldung — die Rolle kommt aus der Sitzung")
        sa = alice.anmelden("s.kern", "geheim-2026-recherche")
        sj = alice.anmelden("j.weber", "auch-geheim-2026")
        print(f"  {sa.anzeige:<14} {alice.rolle(sa.token).name}")
        print(f"  {sj.anzeige:<14} {alice.rolle(sj.token).name}")
        print(f"  ohne Sitzung   {alice.rolle(None).name}")
        print(f"  Behälter       verschlüsselt, "
              f"{alice.vault.pfad.name}")

        kopf(4, "Frage über die Firewall, Belege daneben")
        a = alice.frage("Wem gehört Mare Liberum Ltd.?")
        print(f"  {a['antwort']}\n")
        fid = a["fakten"][0].fact_id
        for sitzung in (sj, sa):
            zustand = [x["status"] for x in
                       alice.belege(fid, alice.rolle(sitzung.token))["belege"]]
            print(f"  als {sitzung.anzeige:<14} "
                  f"({alice.rolle(sitzung.token).name}) {zustand}")
        gf = alice.fakten("beneficial_owner_of", "Svensson Family Trust")[0]
        print(f"  Whistleblower-Fakt als JOURNALIST: "
              f"{alice.belege(gf.fact_id, Rolle.JOURNALIST)['belege'][0]['status']}")

        kopf(5, "Abhängigkeit — was fällt, wenn eine Quelle fällt")
        for z in alice.store.db.execute("SELECT doc_id, titel FROM dokument"):
            h = alice.verifikation.haengt_an(z["doc_id"])
            print(f"  {z['titel']:<24} betroffen {len(h['betroffen']):>2}, "
                  f"ersatzlos {len(h['faellt_ersatzlos']):>2}")

        kopf(6, "Prüfliste vor der Veröffentlichung")
        u = alice.verifikation.uebersicht()
        print(f"  {u['anteil_bestaetigt']} % bestätigt · "
              f"{u['umstritten']} umstritten · "
              f"{u['einfach_belegt']} einfach belegt")

        kopf(7, "Verbindungen")
        for p in alice.verbindungen("Svensson Family Trust", "Ingrid Bech")[:2]:
            print(f"  {p}")
            print(f"    schwächstes Glied: {p.schwaechstes_glied}")

        kopf(8, "Föderiertes Signal ohne Preisgabe des Rechercheziels")
        importiere_tripel(bob, [
            ("Svensson Family Trust", "holds_shares_in", "Zypern Beteiligungs AG"),
            ("Ingrid Bech", "director_of", "Zypern Beteiligungs AG")],
            titel="Vorrecherche", quelle="Redaktion SZ", stufe=Stufe.INTERN,
            erfasst_von="m.roth@sz")
        alice.kennenlernen(bob); bob.kennenlernen(alice)
        alice.vertrauen_setzen(bob.pod_id); bob.vertrauen_setzen(alice.pod_id)
        alice.foed.verbinden(bob.pod_id)
        bob.foed.posteingang(); alice.foed.posteingang()
        print(f"  Indizes  Alice {alice.index_bauen()}")
        print(f"           Bob   {bob.index_bauen()}")
        bob.foed.index_verteilen(); alice.foed.posteingang()

        ziel = alice.store._cid(alice.resolver.key("Svensson Family Trust"))
        req = alice.foed.signal_starten(ziel)
        bob.foed.posteingang(); alice.foed.posteingang()
        for t in alice.foed.ergebnisse(req):
            print(f"{t}")
        print(f"  Bobs Protokoll: {bob.foed.protokoll[-1]['hinweis']}")

        kopf(9, "Lichtung — Freigabe, Nutzung, Vernichtung")
        li = Lichtung([alice.pod_id, bob.pod_id])
        for f in alice.verifikation.alle_fakten():
            if alice.verifikation.stufe_von(f.fact_id) is Stufe.OEFFENTLICH:
                li.einbringen(alice, f.fact_id, rolle=Rolle.JOURNALIST,
                              freigeber=["s.kern"])
        for f in bob.verifikation.alle_fakten():
            li.einbringen(bob, f.fact_id, rolle=Rolle.LEITUNG,
                          freigeber=["m.roth", "chefredaktion"])
        e = li.einbringen(alice, gf.fact_id, rolle=Rolle.JOURNALIST,
                          freigeber=["s.kern"])
        print(f"  Whistleblower-Material: abgelehnt — {e.grund}")
        print(f"  Bestand: {li.bestand()}")
        for p in li.pfade("Anders Holm", "Zypern Beteiligungs AG")[:1]:
            print(f"  {p}")

        kette = li.schliessen({alice.pod_id: alice.ident, bob.pod_id: bob.ident})
        ok, grund = Lichtung.kette_pruefen(
            kette, {alice.pod_id: alice.ident.pubkey,
                    bob.pod_id: bob.ident.pubkey})
        print(f"  Beweiskette: {len(kette['freigaben'])} Fakten, {grund}")

        kopf(10, "Kennzahlen")
        for k, v in alice.stats().items():
            print(f"  {k:<24} {v}")
        print("\n  Oberfläche starten:")
        print("    python3 cli.py init  ./pod.vault --benutzer ihr.name")
        print("    python3 cli.py serve ./pod.vault --open")
    finally:
        alice.close(); bob.close()
        shutil.rmtree(tmp, ignore_errors=True)
    print("=" * 76)


if __name__ == "__main__":
    main()
