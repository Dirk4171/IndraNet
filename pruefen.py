"""
IndraNet — Vollständigkeit prüfen
==================================

Prüft vor dem Bauen, ob alle Dateien vorhanden sind und die Umgebung passt.
Läuft ohne jede Abhängigkeit — auch dann, wenn sonst nichts installiert ist.

    python pruefen.py

Beim ersten Einrichten zuerst diese Datei ausführen. Sie sagt genau, was
fehlt, statt einen Fehler mitten im Bau zu erzeugen.
"""

import os
import sys
from pathlib import Path

HIER = Path(__file__).parent

# --- Programmdateien (ohne diese läuft nichts) -----------------------------
PFLICHT = {
    "Kern": [
        "store.py", "resolver.py", "verification.py", "graph.py",
        "provenance.py", "policy.py", "ingest.py", "export.py", "extract.py",
    ],
    "Firewall und Navigator": [
        "firewall.py", "navigator.py", "navigator_worker.py",
    ],
    "Sicherheit": [
        "vault.py", "auth.py", "psi.py", "crypto_axon.py", "docstore.py",
    ],
    "Föderation": [
        "federation.py", "clearing.py",
    ],
    "Externe Quellen": [
        "sources.py", "connect_opensanctions.py", "connect_events.py",
    ],
    "Oberfläche": [
        "webui.py", "theming.py", "i18n.py",
    ],
    "Anwendung": [
        "pod.py", "cli.py", "indranet_app.py", "demo.py",
    ],
    "Tests": [
        "test_indranet.py",
    ],
}

# --- Für den Bau der Windows-Version ---------------------------------------
BAU = ["IndraNet.spec"]                       # zwingend zum Bauen
BAU_OPTIONAL = ["build_windows.bat"]          # Bequemlichkeit
INSTALLER = ["installer.iss", "LICENSE", "HINWEIS_VOR_INSTALLATION.txt"]

# --- Dokumentation (nützlich, aber nicht zwingend) -------------------------
DOKU = [
    "README.md", "BUILD.md", "MANUAL.de.md", "MANUAL.en.md",
    "WHITEPAPER.de.md", "WHITEPAPER.en.md", "LIZENZHINWEIS.md",
]

BIBLIOTHEKEN = [
    ("cryptography", "zwingend — Verschlüsselung, Signaturen, PSI"),
    ("numpy", "nur für die Tests und externe Anschlüsse"),
    ("pypdf", "nur für PDF-Textextraktion"),
    ("PyInstaller", "nur zum Bauen der Windows-Version"),
]


def zeile(zeichen, text, zusatz=""):
    print(f"  {zeichen}  {text}" + (f"   {zusatz}" if zusatz else ""))


def main() -> int:
    print("=" * 66)
    print("  IndraNet — Vollständigkeit prüfen")
    print("=" * 66)
    print(f"  Ordner: {HIER}")

    fehler = 0
    warnung = 0

    # ---------------------------------------------------------------- Python
    print("\nPython")
    v = sys.version_info
    if (v.major, v.minor) >= (3, 11):
        zeile("OK", f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        zeile("!!", f"Python {v.major}.{v.minor} — benötigt wird 3.11 oder neuer")
        fehler += 1

    # ------------------------------------------------------------- Programm
    print("\nProgrammdateien")
    fehlend = []
    for gruppe, dateien in PFLICHT.items():
        weg = [d for d in dateien if not (HIER / d).exists()]
        if weg:
            zeile("!!", f"{gruppe}: fehlt {', '.join(weg)}")
            fehlend += weg
            fehler += 1
        else:
            zeile("OK", f"{gruppe} ({len(dateien)})")

    # ------------------------------------------------------------------ Bau
    print("\nDateien zum Bauen")
    for d in BAU:
        if (HIER / d).exists():
            zeile("OK", d)
        else:
            zeile("!!", f"{d} fehlt", "zwingend")
            fehlend.append(d)
            fehler += 1
    for d in BAU_OPTIONAL:
        zeile("OK" if (HIER / d).exists() else "--", d,
              "" if (HIER / d).exists() else "(nicht nötig — Befehle s. u.)")

    print("\nDateien für das Installationsprogramm")
    weg_i = [d for d in INSTALLER if not (HIER / d).exists()]
    if weg_i:
        zeile("--", f"fehlt: {', '.join(weg_i)}",
              "(erst für den Installer nötig)")
        warnung += 1
    else:
        zeile("OK", f"vollständig ({len(INSTALLER)})")

    # ----------------------------------------------------------- Dokumente
    print("\nDokumentation")
    weg = [d for d in DOKU if not (HIER / d).exists()]
    if weg:
        zeile("--", f"fehlt: {', '.join(weg)}", "(nicht zwingend)")
        warnung += 1
    else:
        zeile("OK", f"vollständig ({len(DOKU)})")

    # ---------------------------------------------------------- Bibliotheken
    print("\nBibliotheken")
    for name, zweck in BIBLIOTHEKEN:
        try:
            __import__(name)
            zeile("OK", name, zweck)
        except ImportError:
            if name == "cryptography":
                zeile("!!", f"{name} fehlt", zweck)
                fehler += 1
            else:
                zeile("--", f"{name} fehlt", zweck)
                warnung += 1

    # ----------------------------------------------------------- Ladeprobe
    if not fehlend:
        print("\nLadeprobe")
        sys.path.insert(0, str(HIER))
        for modul in ("store", "firewall", "vault", "pod", "webui",
                      "indranet_app"):
            try:
                __import__(modul)
                zeile("OK", modul)
            except Exception as e:                             # noqa: BLE001
                zeile("!!", f"{modul}: {type(e).__name__}: {e}")
                fehler += 1

    # ------------------------------------------------------------- Ergebnis
    print("\n" + "=" * 66)
    if fehler:
        print(f"  {fehler} Problem(e) gefunden.")
        if fehlend:
            print("\n  Diese Dateien fehlen im Ordner:")
            for d in sorted(set(fehlend)):
                print(f"      {d}")
            print("\n  Laden Sie sie herunter und legen Sie sie in denselben")
            print("  Ordner wie diese Datei. Alle Dateien gehören flach")
            print("  nebeneinander, ohne Unterordner.")
        try:
            import cryptography                                # noqa: F401
        except ImportError:
            print("\n  Bibliotheken installieren:")
            print("      python -m pip install cryptography numpy pyinstaller")
        print("=" * 66)
        return 1

    print("  Alles vorhanden." + (f"  ({warnung} Hinweis(e))" if warnung else ""))
    print("\n  Nächste Schritte:")
    print("      python test_indranet.py                        (Tests)")
    print("      python demo.py                                 (Vorführung)")
    print("      python -m PyInstaller IndraNet.spec --noconfirm --clean")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
