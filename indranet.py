"""
IndraNet 2 — Startprogramm
===========================

    python indranet.py                 startet und öffnet den Browser
    python indranet.py --port 8720     anderer Port
    python indranet.py --kein-browser  nur den Server starten

Die Oberfläche läuft im Browser unter http://127.0.0.1:8710 und ist nur
von diesem Rechner aus erreichbar. Beenden mit Strg+C oder über das Menü.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser


def main() -> int:
    if sys.platform == "win32":
        # Umlaute in der Konsole, auch unter cp1252
        for strom in (sys.stdout, sys.stderr):
            try:
                strom.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
    ap = argparse.ArgumentParser(description="IndraNet 2")
    ap.add_argument("--port", type=int, default=8710)
    ap.add_argument("--netzport", type=int, default=None,
                    help="Port des Netzwerk-Anschlusses (Vorgabe 8711)")
    ap.add_argument("--kein-browser", action="store_true")
    ap.add_argument("--daten", default=None,
                    help="eigener Datenordner, z. B. auf einem verschlüsselten "
                         "USB-Stick")
    args = ap.parse_args()
    if args.daten:
        import os
        os.environ["INDRANET_DATEN"] = args.daten

    from server import App, VERSION
    app = App(port=args.port)
    if args.netzport:
        app.netzdienst.port = args.netzport
    try:
        server = app.starten()
    except OSError as e:
        print(f"IndraNet kann Port {args.port} nicht öffnen: {e}\n"
              "Läuft IndraNet bereits? Sonst mit --port einen anderen wählen.")
        return 1
    url = f"http://127.0.0.1:{args.port}/"
    print(f"IndraNet {VERSION} läuft: {url}")
    print(f"Daten: {app.ordner}")
    print("Beenden mit Strg+C.")
    if not args.kein_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nIndraNet wird beendet, Projekt wird gesichert …")
        app.beenden()
    return 0


if __name__ == "__main__":
    sys.exit(main())
