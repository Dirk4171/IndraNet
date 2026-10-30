"""
IndraNet — Kommandozeile / command line

    python3 cli.py serve   ./pod.db --open
    python3 cli.py import  ./pod.db register.csv \
        --map 'eigentuemer:beneficial_owner_of:{firma} {rechtsform}' \
        --titel "HR Q3" --quelle "Register Oslo" --stufe OEFFENTLICH --von s.kern
    python3 cli.py ask     ./pod.db "Wem gehört Mare Liberum Ltd.?"
    python3 cli.py verify  ./pod.db
    python3 cli.py path    ./pod.db "Svensson Family Trust" "Anders Holm"
    python3 cli.py stats   ./pod.db
    python3 cli.py demo
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

import i18n
from ingest import Zuordnung, importiere_csv, importiere_json
from pod import Pod
from policy import Rolle, Stufe

FARBE = {"BESTAETIGT": "\033[32m", "EINFACH_BELEGT": "\033[33m",
         "UMSTRITTEN": "\033[31m", "WIDERRUFEN": "\033[90m"}
AUS = "\033[0m"


def _passphrase(a, neu: bool = False) -> str | None:
    """Passphrase aus Umgebung oder Eingabe. Nie als Argument — sie stuende
    sonst in der Prozessliste und im Shell-Verlauf."""
    import getpass
    if getattr(a, "unverschluesselt", False):
        return None
    p = os.environ.get("INDRANET_PASSPHRASE")
    if p:
        return p
    p = getpass.getpass("Passphrase: ")
    if neu:
        if len(p) < 12:
            sys.exit("Passphrase zu kurz (mindestens 12 Zeichen).")
        if getpass.getpass("Wiederholen: ") != p:
            sys.exit("Passphrasen stimmen nicht überein.")
    return p


def _pod(a, navigator: bool = False) -> Pod:
    from vault import FalschePassphrase
    schluessel = getattr(a, "schluesseldatei", None)
    try:
        return Pod("pod", datei=a.datei, navigator=navigator,
                   passphrase=_passphrase(a), schluesseldatei=schluessel)
    except FalschePassphrase as e:
        sys.exit(f"Fehler: {e}")


def _fakt_zeile(f, sprache: str) -> str:
    lab = i18n.praedikate(sprache).get(f.praedikat, f.praedikat)
    farbe = FARBE.get(f.beleglage.value, "")
    strich = "|" * min(len(f.quellen), 5)
    wid = (f"  ≠ {', '.join(f.widersprueche)}" if f.widersprueche else "")
    return (f"  {farbe}{i18n.t('state.' + f.beleglage.value, sprache):<16}{AUS}"
            f"{strich:<6} {f.subjekt} · {lab} · {f.objekt}{wid}\n"
            f"        {' · '.join(f.quellen) or '—'}   {f.fact_id}")


def cmd_serve(a) -> None:
    import webui
    pod = _pod(a, navigator=True)
    srv = webui.starte(pod, host=a.host, port=a.port, oeffnen=a.open)
    print(f"IndraNet läuft auf http://{a.host}:{a.port}/")
    print(f"  Pod {pod.pod_id} · {pod.store.stats()['aktive_aussagen']} Aussagen")
    print("  Strg-C beendet den Server.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbeendet.")
    finally:
        srv.shutdown()
        pod.close()


def cmd_import(a) -> None:
    pod = _pod(a)
    try:
        zuordnungen = [Zuordnung.aus_text(m) for m in a.map]
        f = importiere_json if a.datei_ein.endswith(".json") else importiere_csv
        bericht = f(pod, a.datei_ein, zuordnungen, titel=a.titel,
                    quelle=a.quelle, stufe=Stufe[a.stufe], erfasst_von=a.von)
        print(bericht)
        for fehler in bericht.fehler[:5]:
            print(f"  ! {fehler}")
        pod.sichern()
    finally:
        pod.close()


def cmd_ask(a) -> None:
    pod = _pod(a, navigator=True)
    try:
        r = pod.frage(a.frage)
        if r["antwort"] is None:
            print(f"[{r['status']}]")
            return
        print(r["antwort"] + "\n")
        for f in r["fakten"]:
            print(_fakt_zeile(f, a.lang))
        for w in r["warnungen"]:
            print(f"  ! unbelegter Begriff verworfen: {w}")
    finally:
        pod.close()


def cmd_verify(a) -> None:
    pod = _pod(a)
    try:
        listen = pod.verifikation.prueflisten()
        u = pod.verifikation.uebersicht()
        print(f"{i18n.t('vf.share', a.lang)}: {u['anteil_bestaetigt']} %"
              f"   ({u['fakten']} {i18n.t('gen.facts', a.lang)})\n")
        for schluessel, titel in (("umstritten", "vf.contested"),
                                  ("einfach_belegt", "vf.single"),
                                  ("widerrufen", "vf.retracted")):
            fakten = listen[schluessel]
            if not fakten:
                continue
            print(f"{i18n.t(titel, a.lang)} ({len(fakten)})")
            for f in fakten[:a.limit]:
                print(_fakt_zeile(f, a.lang))
            print()
        if not any(listen[k] for k in ("umstritten", "einfach_belegt",
                                       "widerrufen")):
            print(i18n.t("vf.clean", a.lang))
    finally:
        pod.close()


def cmd_evidence(a) -> None:
    pod = _pod(a)
    try:
        kette = pod.beweiskette(a.fact_id, Rolle[a.rolle])
        print(f"{kette['aussage']}")
        print(f"  {kette['beleglage']} · "
              f"{len(kette['unabhaengige_quellen'])} "
              f"{i18n.t('ev.sources_n', a.lang)}\n")
        for b in kette["belege"]:
            if b["status"] == "zurueckgehalten":
                print(f"  {'█' * 34}   [{b['stufe']}]")
            else:
                print(f"  {b['quelle']}  [{b['stufe']}]")
                print(f"    {i18n.t('ev.locator', a.lang)}: {b['fundstelle']}")
        print(f"\n  sha256 {kette['sha256']}")
    finally:
        pod.close()


def cmd_path(a) -> None:
    pod = _pod(a)
    try:
        gefunden = pod.verbindungen(a.von, a.nach, a.schritte)
        if not gefunden:
            print(i18n.t("nw.none", a.lang))
            return
        for p in gefunden:
            print(f"  {p}")
            farbe = FARBE.get(p.schwaechstes_glied, "")
            print(f"    {i18n.t('nw.weakest', a.lang)}: "
                  f"{farbe}{p.schwaechstes_glied}{AUS}\n")
    finally:
        pod.close()


def cmd_review(a) -> None:
    pod = _pod(a)
    try:
        v = pod.vorschlaege(a.schwelle)
        if not v:
            print(i18n.t("en.clean", a.lang))
            return
        print(i18n.t("en.lead", a.lang) + "\n")
        for x in v:
            print(f"  {x}")
    finally:
        pod.close()


def cmd_init(a) -> None:
    """Legt einen verschlüsselten Pod mit erstem Konto an."""
    import getpass
    from vault import container_pruefen, schluesseldatei_erzeugen
    if Path(a.datei).exists():
        sys.exit(f"Fehler: {a.datei} besteht bereits.")
    if a.neue_schluesseldatei:
        schluesseldatei_erzeugen(a.neue_schluesseldatei)
        print(f"  Schlüsseldatei: {a.neue_schluesseldatei}")
        print("  Bewahren Sie sie GETRENNT vom Pod auf.")
        a.schluesseldatei = a.neue_schluesseldatei
    pod = Pod("pod", datei=a.datei, navigator=False,
              passphrase=_passphrase(a, neu=True),
              schluesseldatei=getattr(a, "schluesseldatei", None))
    try:
        passwort = getpass.getpass(f"Passwort für {a.benutzer}: ")
        info = pod.erstkonto(a.benutzer, passwort, a.anzeige or a.benutzer)
        pod.sichern()
        print(f"  Pod angelegt: {a.datei}")
        print(f"  Kennung   {pod.pod_id}")
        print(f"  Konto     {info['benutzer']} ({info['rolle']})")
        print(f"  Resolver  {pod.resolver.fingerprint()}")
        print("\n  Ohne Passphrase ist der Pod nicht lesbar. Es gibt keine "
              "Wiederherstellung.")
    finally:
        pod.close()


def cmd_user(a) -> None:
    """Konten verwalten."""
    import getpass
    pod = _pod(a)
    try:
        if a.aktion == "list":
            for k in pod.konten.liste():
                sperre = " [gesperrt]" if k["gesperrt"] else ""
                print(f"  {k['benutzer']:<18} {k['rolle']:<11} "
                      f"{k['anzeige']}{sperre}")
            print(f"\n  {pod.konten.bericht()}")
        elif a.aktion == "add":
            if not a.benutzer or not a.rolle:
                sys.exit("--benutzer und --rolle erforderlich")
            admin = input("Ihr ADMIN-Benutzername: ").strip()
            passwort = getpass.getpass(f"Passwort für {a.benutzer}: ")
            info = pod.konten.anlegen(a.benutzer, passwort, Rolle[a.rolle],
                                      anzeige=a.anzeige or "", durch=admin)
            pod.sichern()
            print(f"  Konto angelegt: {info}")
        elif a.aktion == "role":
            admin = input("Ihr ADMIN-Benutzername: ").strip()
            pod.konten.rolle_setzen(a.benutzer, Rolle[a.rolle], durch=admin)
            pod.sichern()
            print(f"  {a.benutzer} ist jetzt {a.rolle}")
        elif a.aktion == "passwd":
            alt = getpass.getpass("Altes Passwort: ")
            neu = getpass.getpass("Neues Passwort: ")
            pod.konten.passwort_aendern(a.benutzer, alt, neu)
            pod.sichern()
            print("  Passwort geändert.")
    except Exception as e:                                     # noqa: BLE001
        sys.exit(f"Fehler: {e}")
    finally:
        pod.close()


def cmd_vault(a) -> None:
    """Behälter prüfen oder Passphrase wechseln."""
    from vault import container_pruefen
    if a.aktion == "info":
        info = container_pruefen(a.datei)
        for k, v in info.items():
            print(f"  {k:<12} {v}")
        return
    pod = _pod(a)
    try:
        import getpass
        neu = getpass.getpass("Neue Passphrase: ")
        if len(neu) < 12:
            sys.exit("Passphrase zu kurz (mindestens 12 Zeichen).")
        if getpass.getpass("Wiederholen: ") != neu:
            sys.exit("Passphrasen stimmen nicht überein.")
        info = pod.vault.passphrase_aendern(pod.store.db, neue_passphrase=neu,
                                            neue_schluesseldatei=getattr(
                                                a, "schluesseldatei", None))
        pod.vault = None                    # close() darf nicht neu sichern
        print(f"  Passphrase gewechselt. {info['bytes']} Bytes geschrieben.")
        print("  Ältere Kopien des Behälters bleiben mit der alten "
              "Passphrase lesbar — vernichten Sie sie.")
    finally:
        pod.close()


def cmd_fetch(a) -> None:
    """Externen Korpus holen. Ein bewusster, einmaliger Vorgang."""
    pod = _pod(a)
    try:
        if a.quelle == "opensanctions":
            from connect_opensanctions import OpenSanctions
            q = OpenSanctions(store=pod.store)
            info = q.holen(a.von or None, grenze=a.grenze)
        else:
            from connect_events import Ereignisquelle
            q = Ereignisquelle(name=a.name or "World Monitor",
                               store=pod.store, profil=a.profil)
            if not a.von:
                raise SystemExit("--von wird für Ereignisquellen benötigt")
            info = q.holen(a.von, grenze=a.grenze)
        print(f"  {q.name}: {info}")
        print("  Der Abgleich läuft lokal; nichts wurde nach außen gesendet.")
    finally:
        pod.close()


def cmd_screen(a) -> None:
    """Eigene Entitäten gegen einen externen Korpus prüfen — lokal."""
    pod = _pod(a)
    try:
        if a.quelle == "opensanctions":
            from connect_opensanctions import OpenSanctions
            q = OpenSanctions(store=pod.store)
            q.holen(a.von or None, grenze=a.grenze)
        else:
            from connect_events import Ereignisquelle
            q = Ereignisquelle(name=a.name or "World Monitor",
                               store=pod.store, profil=a.profil)
            q.holen(a.von, grenze=a.grenze)
        treffer = q.abgleichen(pod)
        if not treffer:
            print("  Keine Funde.")
            return
        for t in treffer[:a.limit]:
            farbe = FARBE["UMSTRITTEN"] if t.art == "sanktion" else ""
            print(f"  {farbe}{t}{AUS}")
        print(f"\n  {q.bericht(treffer)}")
        print("\n  Funde sind keine Aussagen. Übernahme über die Oberfläche"
              "\n  oder importiere_tripel() — nach menschlicher Prüfung.")
    finally:
        pod.close()


def cmd_sources(a) -> None:
    pod = _pod(a)
    try:
        eintraege = pod.quellen_gesundheit()
        if not eintraege:
            print("  Keine externe Quelle angemeldet.")
            return
        for q in eintraege:
            alter = (f"{q['alter_tage']} Tage" if q["alter_tage"] is not None
                     else "nie")
            print(f"  {q['name']:<16} {q['zustand']:<9} {q['datensaetze']:>7} "
                  f"Sätze  {alter:<12} {'lokal' if q['lokal'] else 'extern'}")
            if q["fehler"]:
                print(f"      Fehler: {q['fehler']}")
            if q["lizenz"]:
                print(f"      Lizenz: {q['lizenz']}")
    finally:
        pod.close()


def cmd_backup(a) -> None:
    """Knoten und Belege in eine datierte Sicherungsdatei packen."""
    pod = _pod(a)
    try:
        stand = pod.sicherungsstand()
        if stand["vorhanden"]:
            print(f"  letzte Sicherung: {stand['datei']} "
                  f"({stand['tage']} Tage alt)")
        info = pod.sicherung(a.ziel)
        print(f"  {Path(info['datei']).name}")
        print(f"  {info['bytes'] / 1048576:.1f} MB · {info['teile']} Teile · "
              f"{info['belege']} Belegdokument(e)")
        print("\n  Der Inhalt ist verschlüsselt — die Datei darf auf ein "
              "Netzlaufwerk\n  oder in einen Cloudspeicher. Ohne Passphrase "
              "ist sie wertlos.")
    finally:
        pod.close()


def cmd_export(a) -> None:
    """Beweiskette eines Fakts als lesbares Dokument."""
    pod = _pod(a)
    try:
        text = (pod.dossier(a.fact_id, Rolle[a.rolle], sprache=a.lang)
                if len(a.fact_id) > 1
                else pod.kette_exportieren(a.fact_id[0], Rolle[a.rolle], a.lang))
        if a.ziel:
            Path(a.ziel).write_text(text, encoding="utf-8")
            print(f"  geschrieben: {a.ziel}")
        else:
            print(text)
    finally:
        pod.close()


def cmd_fix(a) -> None:
    """Aussage korrigieren, widerrufen oder verwerfen."""
    pod = _pod(a)
    try:
        if a.aktion == "list":
            for z in pod.store.db.execute(
                    "SELECT a.aussage_id, a.s_anzeige, a.praedikat, "
                    "a.o_anzeige, a.fundstelle, a.widerrufen, d.quelle "
                    "FROM aussage a JOIN dokument d USING(doc_id) "
                    "ORDER BY a.ts DESC LIMIT ?", (a.limit,)):
                marke = " [widerrufen]" if z["widerrufen"] else ""
                print(f"  {z['aussage_id']}")
                print(f"    {z['s_anzeige']} · {z['praedikat']} · "
                      f"{z['o_anzeige']}{marke}")
                print(f"    {z['quelle']} · {z['fundstelle'] or '—'}")
            return
        if not a.begruendung:
            sys.exit("--begruendung ist Pflicht")
        if a.aktion == "edit":
            r = pod.aussage_aendern(
                a.aussage_id, subjekt=a.subjekt, objekt=a.objekt,
                praedikat=a.praedikat, fundstelle=a.fundstelle,
                grund=a.begruendung, pruefer=a.von or "cli")
            print(f"  geändert: {r['aussage']}")
        elif a.aktion == "retract":
            pod.aussage_widerrufen(a.aussage_id, a.begruendung, a.von or "cli")
            print("  widerrufen — die Aussage bleibt sichtbar.")
        elif a.aktion == "discard":
            pod.aussage_verwerfen(a.aussage_id, a.begruendung, a.von or "cli")
            print("  verworfen — der Vorgang steht im Korrekturprotokoll.")
        elif a.aktion == "log":
            for k in pod.korrekturen(a.limit):
                print(f"  {k['art']:<11} {k['pruefer'] or '—':<14} "
                      f"{k['begruendung']}")
                if k["vorher"]:
                    print(f"      vorher:  {k['vorher']}")
                if k["nachher"]:
                    print(f"      nachher: {k['nachher']}")
        pod.sichern()
    except Exception as e:                                     # noqa: BLE001
        sys.exit(f"Fehler: {e}")
    finally:
        pod.close()


def cmd_stats(a) -> None:
    pod = _pod(a)
    try:
        for k, val in pod.stats().items():
            print(f"  {k:<24} {val}")
    finally:
        pod.close()


def cmd_demo(_) -> None:
    import demo
    demo.main()


def main() -> None:
    p = argparse.ArgumentParser(prog="indranet",
                                description="IndraNet — Indra-Knoten")
    p.add_argument("--lang", default="de", choices=list(i18n.SPRACHEN))
    p.add_argument("--schluesseldatei", help="zusätzliche Schlüsseldatei / "
                                             "additional key file")
    p.add_argument("--unverschluesselt", action="store_true",
                   help="ohne Verschlüsselung (nur für Tests) / "
                        "unencrypted (testing only)")
    sub = p.add_subparsers(dest="befehl", required=True)

    def mit_datei(name, hilfe):
        s = sub.add_parser(name, help=hilfe)
        s.add_argument("datei")
        return s

    s = mit_datei("init", "Pod anlegen / create a pod")
    s.add_argument("--benutzer", required=True)
    s.add_argument("--anzeige")
    s.add_argument("--neue-schluesseldatei", dest="neue_schluesseldatei")
    s.set_defaults(fn=cmd_init)

    s = mit_datei("user", "Konten verwalten / manage accounts")
    s.add_argument("aktion", choices=["list", "add", "role", "passwd"])
    s.add_argument("--benutzer")
    s.add_argument("--rolle", choices=[x.name for x in Rolle])
    s.add_argument("--anzeige")
    s.set_defaults(fn=cmd_user)

    s = mit_datei("vault", "Behälter / vault")
    s.add_argument("aktion", choices=["info", "passwd"])
    s.set_defaults(fn=cmd_vault)

    s = mit_datei("serve", "Weboberfläche starten / start the web interface")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8710)
    s.add_argument("--open", action="store_true")
    s.set_defaults(fn=cmd_serve)

    s = mit_datei("import", "CSV oder JSON übernehmen / import CSV or JSON")
    s.add_argument("datei_ein")
    s.add_argument("--map", action="append", required=True)
    s.add_argument("--titel", required=True)
    s.add_argument("--quelle", required=True)
    s.add_argument("--stufe", default="INTERN", choices=[x.name for x in Stufe])
    s.add_argument("--von", required=True)
    s.set_defaults(fn=cmd_import)

    s = mit_datei("ask", "Frage stellen / ask a question")
    s.add_argument("frage"); s.set_defaults(fn=cmd_ask)

    s = mit_datei("verify", "Prüflisten / verification worklists")
    s.add_argument("--limit", type=int, default=10); s.set_defaults(fn=cmd_verify)

    s = mit_datei("evidence", "Beweiskette / evidence chain")
    s.add_argument("fact_id")
    s.add_argument("--rolle", default="JOURNALIST", choices=[x.name for x in Rolle])
    s.set_defaults(fn=cmd_evidence)

    s = mit_datei("path", "Verbindungen / connections")
    s.add_argument("von"); s.add_argument("nach")
    s.add_argument("--schritte", type=int, default=4); s.set_defaults(fn=cmd_path)

    s = mit_datei("review", "Verschmelzungsvorschläge / merge suggestions")
    s.add_argument("--schwelle", type=float, default=0.80)
    s.set_defaults(fn=cmd_review)

    s = mit_datei("fetch", "Externen Korpus holen / fetch external corpus")
    s.add_argument("quelle", choices=["opensanctions", "events"])
    s.add_argument("--von", help="URL oder Datei / URL or file")
    s.add_argument("--name", help="Anzeigename / display name")
    s.add_argument("--profil", default="worldmonitor",
                   choices=["worldmonitor", "gdelt", "generisch"])
    s.add_argument("--grenze", type=int, default=None)
    s.set_defaults(fn=cmd_fetch)

    s = mit_datei("screen", "Lokal gegen externen Korpus prüfen / screen locally")
    s.add_argument("quelle", choices=["opensanctions", "events"])
    s.add_argument("--von", help="URL oder Datei / URL or file")
    s.add_argument("--name")
    s.add_argument("--profil", default="worldmonitor",
                   choices=["worldmonitor", "gdelt", "generisch"])
    s.add_argument("--grenze", type=int, default=None)
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(fn=cmd_screen)

    s = mit_datei("sources", "Zustand externer Quellen / external source health")
    s.set_defaults(fn=cmd_sources)

    s = mit_datei("backup", "Sicherung erstellen / create a backup")
    s.add_argument("--ziel"); s.set_defaults(fn=cmd_backup)

    s = mit_datei("export", "Beweiskette ausgeben / export evidence chain")
    s.add_argument("fact_id", nargs="+")
    s.add_argument("--rolle", default="JOURNALIST",
                   choices=[x.name for x in Rolle])
    s.add_argument("--ziel"); s.set_defaults(fn=cmd_export)

    s = mit_datei("fix", "Aussagen korrigieren / correct assertions")
    s.add_argument("aktion",
                   choices=["list", "edit", "retract", "discard", "log"])
    s.add_argument("--aussage-id", dest="aussage_id")
    s.add_argument("--subjekt"); s.add_argument("--objekt")
    s.add_argument("--praedikat"); s.add_argument("--fundstelle")
    s.add_argument("--begruendung"); s.add_argument("--von")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_fix)

    s = mit_datei("stats", "Kennzahlen / statistics"); s.set_defaults(fn=cmd_stats)

    s = sub.add_parser("demo", help="Vorführung / demonstration")
    s.set_defaults(fn=cmd_demo)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
