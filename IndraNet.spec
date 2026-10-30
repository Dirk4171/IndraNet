# -*- mode: python ; coding: utf-8 -*-
"""
IndraNet — PyInstaller-Beschreibung
====================================

Erzeugt eine eigenständige Anwendung ohne Python-Installation.

    pyinstaller IndraNet.spec --noconfirm

Ergebnis: dist/IndraNet/IndraNet.exe (Windows) bzw. dist/IndraNet/IndraNet.

WARUM EIN ORDNER UND KEINE EINZELDATEI
--------------------------------------
Eine Einzeldatei (--onefile) entpackt sich bei jedem Start in einen
temporären Ordner. Für ein Werkzeug, das mit Quellenmaterial arbeitet, ist
das die falsche Voreinstellung: Der entpackte Programmcode landet in
%TEMP% und bleibt bei einem Absturz dort liegen. Der Ordnermodus startet
zudem spürbar schneller.

WARUM KEIN --windowed
---------------------
Das Konsolenfenster ist hier keine Nachlässigkeit, sondern die
Bedienoberfläche des Servers: Es zeigt, dass IndraNet läuft, unter welcher
Adresse, und sein Schließen beendet die Anwendung sauber mit Sicherung des
Behälters. Ohne Fenster liefe der Prozess unsichtbar weiter.

NAVIGATOR-UNTERPROZESS
----------------------
Der Navigator läuft in einem eigenen Prozess (siehe firewall.py). In der
gepackten Anwendung gibt es kein `python`, das ein Skript starten könnte —
deshalb muss navigator_worker.py als Datenanhang mitgeliefert und über
sys.executable mit einem Umgebungsschalter gestartet werden. Siehe
`navigator_start.py`.
"""

import sys
from pathlib import Path

block_cipher = None

datas = [
    # Die Weboberflaeche (HTML, CSS, JS, Kartendaten) — wird zur Laufzeit
    # aus sys._MEIPASS/web ausgeliefert.
    ("web", "web"),
    # Der Navigator-Worker wird zur Laufzeit als Skript benoetigt.
    ("navigator_worker.py", "."),
    ("navigator.py", "."),
    ("firewall.py", "."),
    # Dokumentation neben der Anwendung, damit sie ohne Netz lesbar ist.
    # Alle Quelldateien liegen flach im Projektordner; ein Unterordner
    # waere eine unnoetige Fehlerquelle beim Zusammenstellen.
    ("README.md", "Dokumentation"),
    ("MANUAL.de.md", "Dokumentation"),
    ("MANUAL.en.md", "Dokumentation"),
    ("WHITEPAPER.de.md", "Dokumentation"),
    ("WHITEPAPER.en.md", "Dokumentation"),
    ("LIZENZHINWEIS.md", "Dokumentation"),
    ("LICENSE", "Dokumentation"),
]

hiddenimports = [
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.kdf.scrypt",
    "cryptography.hazmat.primitives.kdf.hkdf",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "cryptography.hazmat.primitives.asymmetric.x25519",
    "cryptography.hazmat.primitives.asymmetric.ec",
    "cryptography.hazmat.bindings._rust",
    "sqlite3",
    "webbrowser",
    # Module, die nur ueber Zeichenketten geladen werden
    "connect_opensanctions",
    "connect_events",
    "sources",
    "theming",
    "auth",
    "vault",
    "docstore",
    "export",
    "extract",
    "pypdf",
    # IndraNet 2
    "server", "projekt", "ki", "netz", "tor", "netzwerk", "auftraege",
    "quellen_offen", "geo", "einstellungen", "beispiel", "bruecke",
    "anthropic", "httpx2", "socksio",
]

# numpy wird nur von den externen Anschluessen gebraucht und ist gross.
# Wer es nicht braucht, kann es hier ausschliessen.
excludes = [
    "tkinter", "matplotlib", "PIL", "pytest", "playwright",
    "IPython", "notebook", "pandas", "scipy",
]

a = Analysis(
    ["indranet.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IndraNet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX loest bei manchen Virenscannern Fehlalarm aus
    console=True,            # siehe Kopfkommentar
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="indranet.ico" if Path("indranet.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="IndraNet",
)
