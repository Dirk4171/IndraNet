"""
IndraNet — Sicherung und Export
================================

Zwei Wege aus dem Pod heraus, die bisher fehlten.

SICHERUNG
---------
Ein Knoten besteht aus zwei Dingen: dem Behälter und dem Belegordner. Zwei
Dinge, die man getrennt vergessen kann. `sichern()` packt beide in eine
datierte Datei mit Prüfsummenliste.

Der Inhalt ist bereits verschlüsselt — die Sicherung darf also auf ein
Netzlaufwerk, eine externe Platte oder in einen Cloudspeicher. Ohne
Passphrase ist sie wertlos, auch für den Anbieter.

Bewusst kein Aufräumen alter Sicherungen: Ein Werkzeug, das
Recherchestände von sich aus löscht, ist keins.

EXPORT DER BEWEISKETTE
----------------------
Der ganze Sinn ist Veröffentlichungsreife, aber bisher kam nichts wieder
heraus. Ein Fakt mit seiner Belegkette als lesbares Dokument ist das, was
man dem Justiziar oder der Chefredaktion vorlegt.

Der Export enthält Prüfsummen, keine Dokumentinhalte. Wer ihn prüft,
braucht die Originale — genau so soll es sein. Zurückgehaltene Belege
erscheinen als solche: Dass es sie gibt, gehört ins Dokument, was in ihnen
steht, nicht.
"""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from datetime import datetime
from pathlib import Path

from policy import Rolle, Stufe

MARKE = {"BESTAETIGT": "bestätigt", "EINFACH_BELEGT": "einfach belegt",
         "UMSTRITTEN": "umstritten", "WIDERRUFEN": "widerrufen"}
MARKE_EN = {"BESTAETIGT": "corroborated", "EINFACH_BELEGT": "single-sourced",
            "UMSTRITTEN": "contested", "WIDERRUFEN": "retracted"}


# ============================================================== Sicherung
def sichern(pod, ziel: str | Path | None = None) -> dict:
    """Packt Behälter und Belegordner in eine datierte Sicherungsdatei."""
    if pod.vault is None:
        raise ValueError("Nur verschlüsselte Knoten können gesichert werden")
    pod.sichern()                                  # aktuellen Stand schreiben

    behaelter = Path(pod.vault.pfad)
    belege = behaelter.parent / (behaelter.stem + "-belege")
    stempel = datetime.now().strftime("%Y-%m-%d_%H%M")
    ziel = Path(ziel) if ziel else (
        behaelter.parent / f"{behaelter.stem}-sicherung-{stempel}.zip")
    ziel.parent.mkdir(parents=True, exist_ok=True)

    teile, gesamt = [], 0
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_STORED) as z:
        # ZIP_STORED, nicht DEFLATE: Verschlüsselte Daten lassen sich nicht
        # komprimieren, der Versuch kostet nur Zeit.
        def dazu(pfad: Path, name: str):
            nonlocal gesamt
            z.write(pfad, name)
            h = hashlib.sha256(pfad.read_bytes()).hexdigest()
            teile.append({"datei": name, "bytes": pfad.stat().st_size,
                          "sha256": h})
            gesamt += pfad.stat().st_size

        dazu(behaelter, behaelter.name)
        sig = behaelter.with_suffix(".sig")
        if sig.exists():
            dazu(sig, sig.name)
        if belege.is_dir():
            for f in sorted(belege.glob("*.dok")):
                dazu(f, f"{belege.name}/{f.name}")

        z.writestr("SICHERUNG.json", json.dumps({
            "format": "indranet-sicherung-1",
            "knoten": pod.name, "pod_id": pod.pod_id,
            "erstellt": datetime.now().isoformat(timespec="seconds"),
            "resolver": pod.resolver.fingerprint(),
            "aussagen": pod.store.stats()["aktive_aussagen"],
            "dokumente": pod.store.stats()["dokumente"],
            "teile": teile,
        }, ensure_ascii=False, indent=1))
        z.writestr("LIESMICH.txt", _liesmich(pod, behaelter.name, len(teile)))

    return {"datei": str(ziel), "bytes": ziel.stat().st_size,
            "teile": len(teile), "klartext_bytes": gesamt,
            "belege": sum(1 for t in teile if "/" in t["datei"])}


def _liesmich(pod, behaelter: str, teile: int) -> str:
    return f"""IndraNet - Sicherung
====================

Knoten:   {pod.name}
Kennung:  {pod.pod_id}
Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}
Teile:    {teile}

WIEDERHERSTELLEN
Diese Datei entpacken. Der Behaelter ({behaelter}) und der Ordner mit den
Belegen muessen NEBENEINANDER liegen - genau so, wie sie im Archiv stehen.
Danach den Knoten wie gewohnt oeffnen.

PASSPHRASE
Der Inhalt ist verschluesselt. Ohne die Passphrase ist diese Sicherung
nicht zu oeffnen - auch nicht von uns, auch nicht von Ihrem Cloudanbieter.
Es gibt keine Wiederherstellung.

Bewahren Sie die Passphrase getrennt von dieser Datei auf.
"""


def letzte_sicherung(pod) -> dict:
    """Wann wurde zuletzt gesichert? Für den Hinweis in der Oberfläche."""
    if pod.vault is None:
        return {"vorhanden": False, "tage": None}
    ordner = Path(pod.vault.pfad).parent
    muster = Path(pod.vault.pfad).stem + "-sicherung-*.zip"
    dateien = sorted(ordner.glob(muster), key=lambda f: f.stat().st_mtime)
    if not dateien:
        return {"vorhanden": False, "tage": None}
    letzte = dateien[-1]
    return {"vorhanden": True, "datei": letzte.name,
            "tage": round((time.time() - letzte.stat().st_mtime) / 86400, 1),
            "anzahl": len(dateien)}


# ================================================== Export der Beweiskette
def beweiskette_markdown(pod, fact_id: str, rolle: Rolle,
                         sprache: str = "de") -> str:
    """Belegkette eines Fakts als lesbares Dokument."""
    kette = pod.beweiskette(fact_id, rolle)
    f = pod.store.fakt(fact_id)
    en = sprache == "en"
    marke = (MARKE_EN if en else MARKE).get(kette.get("beleglage") or "", "?")

    t = _texte(en)
    z = [f"# {t['titel']}", "",
         f"**{kette['aussage'] or '—'}**", "",
         f"| | |", "|---|---|",
         f"| {t['state']} | **{marke}** |",
         f"| {t['sources']} | {len(kette['unabhaengige_quellen'])}"
         f" — {', '.join(kette['unabhaengige_quellen']) or '—'} |",
         f"| {t['level']} | {kette['stufe']} |",
         f"| {t['fact_id']} | `{fact_id}` |"]
    if f is not None and f.widersprueche:
        z.append(f"| {t['contradicts']} | {', '.join(f.widersprueche)} |")
    z += ["", f"## {t['evidence']}", ""]

    offen = zurueck = 0
    for b in kette["belege"]:
        if b["status"] == "zurueckgehalten":
            zurueck += 1
            z += [f"### {t['withheld']}", "",
                  f"> {t['withheld_note'].format(stufe=b['stufe'])}", ""]
            continue
        offen += 1
        dok = kette["dokumente"].get(b["doc_id"], {})
        z += [f"### {dok.get('titel', b['doc_id'])}", "",
              f"- **{t['source']}:** {b['quelle']}",
              f"- **{t['locator']}:** {b['fundstelle'] or '—'}",
              f"- **{t['level']}:** {b['stufe']}",
              f"- **{t['recorded']}:** {b['erfasst_von'] or '—'}, "
              f"{datetime.fromtimestamp(b['ts']).strftime('%d.%m.%Y')}",
              f"- **SHA-256:** `{dok.get('sha256', '—')}`"]
        if b.get("zitat"):
            z += ["", f"> {b['zitat']}"]
        if b.get("widerrufen"):
            z += ["", f"**{t['retracted']}:** {b.get('widerruf_grund') or '—'}"]
        z.append("")

    pruefungen = pod.verifikation.pruefungen(fact_id)
    if pruefungen:
        z += [f"## {t['checks']}", ""]
        for pr in pruefungen:
            z.append(f"- {datetime.fromtimestamp(pr['ts']).strftime('%d.%m.%Y')}"
                     f" · {pr['ergebnis']} · {pr['pruefer']}"
                     + (f" — {pr['notiz']}" if pr["notiz"] else ""))
        z.append("")

    z += ["---", "",
          t["footer"].format(offen=offen, zurueck=zurueck,
                             rolle=rolle.name,
                             pod=pod.name,
                             zeit=datetime.now().strftime("%d.%m.%Y %H:%M")),
          "", f"`{t['checksum']}: {kette['sha256']}`", ""]
    return "\n".join(z)


def dossier_markdown(pod, fact_ids: list, rolle: Rolle, *, titel: str = "",
                     sprache: str = "de") -> str:
    """Mehrere Fakten in einem Dokument — für eine ganze Geschichte."""
    en = sprache == "en"
    t = _texte(en)
    kopf = [f"# {titel or t['dossier']}", "",
            f"*{t['dossier_note'].format(n=len(fact_ids), pod=pod.name, rolle=rolle.name, zeit=datetime.now().strftime('%d.%m.%Y %H:%M'))}*",
            "", "---", ""]
    teile = [beweiskette_markdown(pod, f, rolle, sprache).replace("# ", "## ", 1)
             for f in fact_ids]
    return "\n".join(kopf) + "\n\n---\n\n".join(teile)


def _texte(en: bool) -> dict:
    if en:
        return {
            "titel": "Evidence chain", "state": "Evidential state",
            "sources": "Independent sources", "level": "Protection level",
            "fact_id": "Fact ID", "contradicts": "Contradicts",
            "evidence": "Evidence", "withheld": "Withheld evidence",
            "withheld_note": "Evidence at level {stufe} exists but is not "
                             "shown at this role. Its existence is part of "
                             "the record; its content is not.",
            "source": "Source", "locator": "Locator", "recorded": "Recorded by",
            "retracted": "Retracted", "checks": "Verification log",
            "checksum": "Chain checksum",
            "footer": "{offen} evidence item(s) shown, {zurueck} withheld. "
                      "Exported from node *{pod}* at role {rolle} on {zeit}. "
                      "Checksums refer to the original documents; these are "
                      "not part of this export.",
            "dossier": "Evidence dossier",
            "dossier_note": "{n} facts from node {pod}, role {rolle}, {zeit}.",
        }
    return {
        "titel": "Beweiskette", "state": "Beleglage",
        "sources": "Unabhängige Quellen", "level": "Schutzstufe",
        "fact_id": "Faktenkennung", "contradicts": "Widerspricht",
        "evidence": "Belege", "withheld": "Zurückgehaltener Beleg",
        "withheld_note": "Es existiert ein Beleg der Stufe {stufe}, der bei "
                         "dieser Rolle nicht angezeigt wird. Dass es ihn "
                         "gibt, gehört zur Beleglage; was in ihm steht, "
                         "nicht.",
        "source": "Quelle", "locator": "Fundstelle", "recorded": "Erfasst von",
        "retracted": "Widerrufen", "checks": "Prüfvermerke",
        "checksum": "Prüfsumme der Kette",
        "footer": "{offen} Beleg(e) ausgewiesen, {zurueck} zurückgehalten. "
                  "Exportiert aus Knoten *{pod}* mit Rolle {rolle} am {zeit}. "
                  "Die Prüfsummen beziehen sich auf die Originaldokumente; "
                  "diese sind nicht Teil dieses Exports.",
        "dossier": "Belegdossier",
        "dossier_note": "{n} Fakten aus Knoten {pod}, Rolle {rolle}, {zeit}.",
    }
