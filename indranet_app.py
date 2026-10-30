"""
IndraNet — Startprogramm
=========================

Einstiegspunkt der eigenständigen Anwendung. Aufgaben:

  1. Ablageort bestimmen (unter Windows %APPDATA%\\IndraNet)
  2. Beim ersten Start einen Einrichtungsassistenten anzeigen
  3. Den Pod öffnen und die Oberfläche starten
  4. Browser öffnen, Fenster offen halten, sauber beenden

WARUM DER ASSISTENT IM BROWSER LÄUFT
------------------------------------
Passphrase und erstes Konto müssen vor dem Öffnen des Behälters feststehen.
Naheliegend wäre eine Abfrage im Konsolenfenster — aber wer keine
Programmierkenntnisse hat, soll kein schwarzes Fenster mit Eingabezeile
sehen. Deshalb startet zuerst ein kleiner Einrichtungsserver mit derselben
Gestaltung wie die Anwendung; danach wird auf den eigentlichen Server
umgeschaltet.

WAS NICHT PASSIERT
------------------
Kein Autostart, kein Dienst im Hintergrund, keine Netzwerkfreigabe. Der
Server bindet an 127.0.0.1 und endet mit dem Fenster. Ein Werkzeug für
Quellenmaterial soll nicht laufen, wenn niemand es benutzt.
"""

from __future__ import annotations

import os
import sys

import json
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_NAME = "IndraNet"
VERSION = "1.1"

# ---------------------------------------------------------------------------
# ROLLENSCHALTER — muss vor allem anderen laufen
#
# In der gepackten Anwendung ist sys.executable die Programmdatei selbst,
# nicht ein Python-Interpreter. Der Navigator kann also nicht als Skript
# gestartet werden. Stattdessen startet der Pod die eigene Programmdatei
# erneut mit INDRANET_ROLE=navigator; hier wird das abgefangen, bevor
# irgendetwas anderes geladen wird.
#
# Wichtig fuer die Firewall: Der so gestartete Prozess laedt AUSSCHLIESSLICH
# navigator_worker — kein store, kein vault, keine Faktendaten. Die
# Prozessgrenze bleibt damit auch in der gepackten Anwendung eine echte.
# ---------------------------------------------------------------------------
if os.environ.get("INDRANET_ROLE") == "navigator":
    import navigator_worker
    navigator_worker.main()
    sys.exit(0)


# ---------------------------------------------------------------- Ablage
def datenordner() -> Path:
    """Ordner für Pods. Unter Windows im Benutzerprofil, nicht neben der
    Programmdatei — dort fehlen im Regelfall die Schreibrechte."""
    if sys.platform == "win32":
        wurzel = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        wurzel = Path.home() / "Library" / "Application Support"
    else:
        wurzel = Path(os.environ.get("XDG_DATA_HOME",
                                     Path.home() / ".local" / "share"))
    ordner = wurzel / APP_NAME
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def pods() -> list[Path]:
    return sorted(datenordner().glob("*.vault"))


def freier_port(start: int = 8710) -> int:
    for port in range(start, start + 40):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("kein freier Port gefunden")


# ------------------------------------------------------ Einrichtungsseite
def _setup_seite() -> str:
    import theming
    vorhanden = pods()
    liste = "".join(
        f'<option value="{p.name}">{p.stem}</option>' for p in vorhanden)
    return SETUP_HTML.replace("__THEMEN__", theming.alle_css()) \
        .replace("__PODS__", liste) \
        .replace("__HAT_PODS__", "true" if vorhanden else "false") \
        .replace("__ORDNER__", str(datenordner()).replace("\\", "\\\\")) \
        .replace("__VERSION__", VERSION)


SETUP_HTML = r"""<!doctype html>
<html lang="de" data-thema="lagezentrale"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IndraNet — Einrichtung</title>
<style>
__THEMEN__
:root{--mono:ui-monospace,"Cascadia Mono","Segoe UI Mono",Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:var(--grund);color:var(--tinte);
  font-family:var(--mono);font-size:13.5px;display:flex;align-items:center;
  justify-content:center;padding:28px;line-height:1.55}
body::before{content:"";position:fixed;inset:0;pointer-events:none;
  background:linear-gradient(var(--raster) 1px,transparent 1px) 0 0/100% 34px,
    linear-gradient(90deg,var(--raster) 1px,transparent 1px) 0 0/34px 100%}
.box{width:100%;max-width:520px;position:relative;z-index:1}
.marke{font-size:21px;letter-spacing:.2em;text-transform:uppercase;
  font-weight:600;margin-bottom:4px}
.marke span{color:var(--akzent)}
.unter{color:var(--gedaempft);font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;margin-bottom:22px}
.karte{background:var(--flaeche);border:1px solid var(--linie);
  padding:22px;position:relative}
.karte::before,.karte::after{content:"";position:absolute;width:10px;height:10px;
  border-color:var(--akzent);opacity:.6}
.karte::before{top:-1px;left:-1px;border-top:1px solid;border-left:1px solid}
.karte::after{bottom:-1px;right:-1px;border-bottom:1px solid;border-right:1px solid}
h2{font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--gedaempft);margin:0 0 16px;border-bottom:1px solid var(--linie);
  padding-bottom:8px}
label{display:block;font-size:10.5px;color:var(--gedaempft);
  margin:14px 0 5px;text-transform:uppercase;letter-spacing:.13em}
input,select{width:100%;padding:10px 11px;border:1px solid var(--linie);
  background:var(--flaeche2);color:var(--tinte);font:inherit}
input:focus,select:focus{border-color:var(--akzent);outline:none}
.knopf{width:100%;margin-top:20px;background:var(--akzent-tief);
  color:var(--akzent);border:1px solid var(--akzent);padding:12px;
  cursor:pointer;font:inherit;font-weight:600;text-transform:uppercase;
  letter-spacing:.14em}
.knopf:hover{background:var(--akzent);color:var(--grund)}
.knopf[disabled]{opacity:.45;cursor:wait}
.hinweis{font-size:11px;color:var(--gedaempft);margin-top:14px;line-height:1.6}
.warnung{border-left:2px solid var(--einfach);padding:9px 12px;
  font-size:11.5px;color:var(--einfach);margin-top:14px;
  background:rgba(224,169,60,.06)}
.fehler{border:1px solid var(--umstritten);color:var(--umstritten);
  padding:9px 12px;font-size:12px;margin-bottom:14px;
  background:rgba(255,92,92,.06)}
.reiter{display:flex;margin-bottom:18px;border-bottom:1px solid var(--linie)}
.reiter button{flex:1;background:none;border:0;border-bottom:2px solid transparent;
  padding:9px;color:var(--gedaempft);cursor:pointer;font:inherit;font-size:11px;
  text-transform:uppercase;letter-spacing:.12em}
.reiter button[aria-selected="true"]{border-bottom-color:var(--akzent);
  color:var(--akzent)}
.staerke{height:3px;background:var(--linie);margin-top:6px}
.staerke i{display:block;height:100%;width:0;transition:width .2s,background .2s}
.fuss{text-align:center;color:var(--gedaempft);font-size:10px;margin-top:18px;
  letter-spacing:.1em}
</style></head><body>
<div class="box">
  <div class="marke">Indra<span>Net</span></div>
  <div class="unter" id="unter">Einrichtung · Setup</div>
  <div class="karte">
    <div class="reiter" id="reiter"></div>
    <div id="inhalt"></div>
  </div>
  <div class="fuss">v__VERSION__ · 127.0.0.1 · <span id="ordner"></span></div>
</div>
<script>
const HAT_PODS=__HAT_PODS__, ORDNER="__ORDNER__";
let MODUS = HAT_PODS ? "oeffnen" : "neu", SPRACHE="de";
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",
  ">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const T={
 de:{neu:"Neuer Knoten",oeffnen:"Öffnen",name:"Name des Knotens",
     pass:"Passphrase",pass2:"Passphrase wiederholen",user:"Benutzername",
     upass:"Passwort",start:"Anlegen und starten",open:"Öffnen und starten",
     pod:"Knoten",
     hint:"Die Passphrase schützt alle Daten dieses Knotens. Es gibt keine "+
          "Wiederherstellung — notieren Sie sie an einem sicheren Ort.",
     warn:"Mindestens 12 Zeichen. Ein Satz ist besser als ein Wort.",
     mismatch:"Die Passphrasen stimmen nicht überein.",
     short:"Passphrase zu kurz (mindestens 12 Zeichen).",
     upshort:"Passwort zu kurz (mindestens 8 Zeichen).",
     needname:"Bitte einen Namen angeben.",
     working:"Wird eingerichtet…",opening:"Wird geöffnet…"},
 en:{neu:"New node",oeffnen:"Open",name:"Node name",
     pass:"Passphrase",pass2:"Repeat passphrase",user:"Username",
     upass:"Password",start:"Create and start",open:"Open and start",
     pod:"Node",
     hint:"The passphrase protects all data in this node. There is no "+
          "recovery — write it down somewhere safe.",
     warn:"At least 12 characters. A sentence beats a word.",
     mismatch:"Passphrases do not match.",
     short:"Passphrase too short (at least 12 characters).",
     upshort:"Password too short (at least 8 characters).",
     needname:"Please enter a name.",
     working:"Setting up…",opening:"Opening…"}};
const tr=k=>T[SPRACHE][k]||k;

function zeichne(fehler){
  $("#ordner").textContent=ORDNER;
  $("#reiter").innerHTML=
    (HAT_PODS?`<button aria-selected="${MODUS==='oeffnen'}"
       onclick="MODUS='oeffnen';zeichne()">${esc(tr("oeffnen"))}</button>`:"")+
    `<button aria-selected="${MODUS==='neu'}"
       onclick="MODUS='neu';zeichne()">${esc(tr("neu"))}</button>`;
  const f=fehler?`<div class="fehler">${esc(fehler)}</div>`:"";
  if(MODUS==="oeffnen"){
    $("#inhalt").innerHTML=f+`
      <label>${esc(tr("pod"))}</label>
      <select id="podwahl">__PODS__</select>
      <label>${esc(tr("pass"))}</label>
      <input type="password" id="p1" autofocus
        onkeydown="if(event.key==='Enter')los()">
      <button class="knopf" id="go" onclick="los()">${esc(tr("open"))}</button>`;
  }else{
    $("#inhalt").innerHTML=f+`
      <label>${esc(tr("name"))}</label>
      <input type="text" id="name" placeholder="recherche-offshore" autofocus>
      <label>${esc(tr("pass"))}</label>
      <input type="password" id="p1" oninput="staerke()">
      <div class="staerke"><i id="bar"></i></div>
      <label>${esc(tr("pass2"))}</label>
      <input type="password" id="p2">
      <label>${esc(tr("user"))}</label>
      <input type="text" id="user" placeholder="s.kern">
      <label>${esc(tr("upass"))}</label>
      <input type="password" id="up" onkeydown="if(event.key==='Enter')los()">
      <button class="knopf" id="go" onclick="los()">${esc(tr("start"))}</button>
      <div class="warnung">${esc(tr("warn"))}</div>
      <div class="hinweis">${esc(tr("hint"))}</div>`;
  }
}
function staerke(){
  const v=$("#p1").value, b=$("#bar");
  const s=Math.min(100, v.length*5 + (/[^a-z]/.test(v)?15:0) +
    (v.split(/\s+/).length>2?20:0));
  b.style.width=s+"%";
  b.style.background = s<45?"var(--umstritten)":(s<75?"var(--einfach)":
    "var(--bestaetigt)");
}
async function los(){
  const knopf=$("#go");
  const daten = MODUS==="neu" ? {
      modus:"neu", name:$("#name").value.trim(),
      passphrase:$("#p1").value, passphrase2:$("#p2").value,
      benutzer:$("#user").value.trim(), passwort:$("#up").value
    } : {modus:"oeffnen", datei:$("#podwahl").value, passphrase:$("#p1").value};

  if(MODUS==="neu"){
    if(!daten.name) return zeichne(tr("needname"));
    if(daten.passphrase.length<12) return zeichne(tr("short"));
    if(daten.passphrase!==daten.passphrase2) return zeichne(tr("mismatch"));
    if(daten.passwort.length<8) return zeichne(tr("upshort"));
  }
  knopf.disabled=true;
  knopf.textContent = MODUS==="neu"?tr("working"):tr("opening");
  try{
    const r=await fetch("/setup",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(daten)});
    const d=await r.json();
    if(d.ok){ document.body.innerHTML=
        `<div class="box"><div class="marke">Indra<span>Net</span></div>
         <div class="unter">${esc(d.hinweis||"")}</div></div>`;
      setTimeout(()=>location.href=d.url, 1400);
    } else { zeichne(d.fehler||"Fehler"); }
  }catch(e){ zeichne(String(e)); }
}
if(navigator.language && navigator.language.startsWith("en")) SPRACHE="en";
zeichne(null);
</script></body></html>"""


# ----------------------------------------------------- Einrichtungsserver
class SetupHandler(BaseHTTPRequestHandler):
    ergebnis: dict = {}
    fertig: threading.Event = None
    haupt_port: int = 0

    def log_message(self, *a):
        pass

    def _sende(self, roh: bytes, typ: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):
        if urlparse(self.path).path in ("/", "/index.html"):
            self._sende(_setup_seite().encode(), "text/html; charset=utf-8")
        else:
            self._sende(b"{}", "application/json", 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        d = json.loads(self.rfile.read(n) or b"{}")
        try:
            if d["modus"] == "neu":
                name = "".join(c for c in d["name"]
                               if c.isalnum() or c in "-_ ").strip()
                if not name:
                    raise ValueError("ungültiger Name")
                pfad = datenordner() / f"{name}.vault"
                if pfad.exists():
                    raise ValueError(f"{name} besteht bereits")
                SetupHandler.ergebnis = {
                    "datei": pfad, "passphrase": d["passphrase"],
                    "neu": True, "benutzer": d["benutzer"],
                    "passwort": d["passwort"]}
                hinweis = "Knoten wird angelegt…"
            else:
                SetupHandler.ergebnis = {
                    "datei": datenordner() / d["datei"],
                    "passphrase": d["passphrase"], "neu": False}
                hinweis = "Knoten wird geöffnet…"

            # Passphrase sofort prüfen, damit ein Tippfehler hier auffällt
            # und nicht erst nach dem Umschalten.
            if not SetupHandler.ergebnis["neu"]:
                from vault import FalschePassphrase, Vault
                try:
                    Vault(SetupHandler.ergebnis["datei"],
                          passphrase=d["passphrase"]).oeffnen()
                except FalschePassphrase:
                    raise ValueError("Passphrase falsch oder Datei verändert")

            self._sende(json.dumps({
                "ok": True, "hinweis": hinweis,
                "url": f"http://127.0.0.1:{self.haupt_port}/"
            }).encode(), "application/json")
            threading.Timer(0.3, self.fertig.set).start()
        except Exception as e:                                 # noqa: BLE001
            self._sende(json.dumps({"ok": False, "fehler": str(e)}).encode(),
                        "application/json", 400)


def einrichten(haupt_port: int, port: int) -> dict:
    """Zeigt den Assistenten und liefert die Auswahl des Benutzers."""
    fertig = threading.Event()
    SetupHandler.fertig = fertig
    SetupHandler.haupt_port = haupt_port
    srv = ThreadingHTTPServer(("127.0.0.1", port), SetupHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"  Einrichtung: {url}", flush=True)
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        while not fertig.wait(0.5):
            pass
    except KeyboardInterrupt:
        srv.shutdown()
        sys.exit(0)
    srv.shutdown()
    return SetupHandler.ergebnis


# ------------------------------------------------------------------ Start
def main() -> int:
    # Ohne Zeilenpufferung: Sonst bleibt das Fenster beim Start leer, bis
    # genug Text zusammengekommen ist — das sieht nach Absturz aus.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:                                          # noqa: BLE001
        pass
    print("=" * 62)
    print(f"  {APP_NAME} {VERSION}")
    print("=" * 62)
    print(f"  Ablage: {datenordner()}")

    haupt_port = freier_port()
    setup_port = freier_port(haupt_port + 1)
    wahl = einrichten(haupt_port, setup_port)
    if not wahl:
        return 1

    from pod import Pod
    import webui

    pod = Pod(wahl["datei"].stem, datei=wahl["datei"],
              passphrase=wahl["passphrase"],
              inbox_wurzel=datenordner() / "inbox")
    try:
        if wahl["neu"] and pod.offen:
            pod.erstkonto(wahl["benutzer"], wahl["passwort"])
            pod.sichern()
            print(f"  Konto angelegt: {wahl['benutzer']} (ADMIN)")

        srv = webui.starte(pod, host="127.0.0.1", port=haupt_port)
        print(f"  Knoten: {pod.name}  ({pod.pod_id})")
        print(f"  Oberfläche: http://127.0.0.1:{haupt_port}/")
        print("\n  Dieses Fenster offen lassen. Schließen beendet IndraNet.")
        print("=" * 62)
        threading.Timer(0.8, lambda: webbrowser.open(
            f"http://127.0.0.1:{haupt_port}/")).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n  Wird beendet…")
        finally:
            srv.shutdown()
    finally:
        pod.close()
        print("  Gesichert und geschlossen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
