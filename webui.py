"""
IndraNet — Weboberfläche
=========================

Ein lokaler HTTP-Server ohne Fremdbibliotheken. Bindet standardmäßig an
127.0.0.1: Das Werkzeug arbeitet mit Quellenmaterial und gehört nicht ins
Netz, solange kein Betreiber das ausdrücklich entscheidet.

GESTALTUNG
----------
Das Layout bildet die Architektur ab statt sie zu dekorieren: Antwort
links, Belege rechts. Die zwei Ausgänge des Pods sind zwei Spalten, kein
Klickpfad — wer eine Antwort liest, sieht daneben, worauf sie beruht.

Signatur ist der Schwärzungsbalken. Zurückgehaltene Belege verschwinden
nicht, sie erscheinen als schwarzer Balken, der auf Klick den GRUND
preisgibt, nie den Inhalt. Dazu Strichlisten für unabhängige Quellen — das
Notizbuchvokabular dieses Berufs.

Keine Webfonts, keine externen Ressourcen. Ein Werkzeug für sensibles
Material darf beim Öffnen nichts nachladen.
"""

from __future__ import annotations

import json
import mimetypes
import threading
from pathlib import Path
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import i18n
import theming
from ingest import Zuordnung, importiere_tripel
from policy import Rolle, Stufe
from provenance import Dokument
from store import Beleglage

# ============================================================ Oberfläche
SEITE = r"""<!doctype html>
<html lang="de" data-thema="lagezentrale"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IndraNet</title>
<style>
/* ===== Themen (theming.py) ===== */
__THEMEN__

:root{
  --mono:ui-monospace,"SF Mono","JetBrains Mono","Cascadia Mono",
        "Roboto Mono",Menlo,Consolas,"DejaVu Sans Mono",monospace;
  --eck:9px;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--grund);color:var(--tinte);font-family:var(--sans);
  font-size:13.5px;line-height:var(--zeichen);-webkit-font-smoothing:antialiased;
  letter-spacing:.005em}
/* Feines Raster im Hintergrund — nur im dunklen Thema sichtbar */
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    linear-gradient(var(--raster) 1px,transparent 1px) 0 0/100% 34px,
    linear-gradient(90deg,var(--raster) 1px,transparent 1px) 0 0/34px 100%}
.huelle,aside,main{position:relative;z-index:1}
button,input,select,textarea{font:inherit;color:inherit}
:focus-visible{outline:1px solid var(--fokus);outline-offset:2px}
a{color:var(--akzent)}

/* ===== Rahmen ===== */
.huelle{display:grid;grid-template-columns:224px 1fr;min-height:100%}
aside{background:var(--grund2);border-right:1px solid var(--linie);
  padding:18px 16px;display:flex;flex-direction:column;gap:22px}
.marke{font-family:var(--mono);font-size:17px;letter-spacing:.16em;font-weight:600;
  text-transform:uppercase;color:var(--tinte)}
.marke span{color:var(--akzent)}
.marke-zeile{display:flex;align-items:center;gap:8px}
.puls{width:6px;height:6px;border-radius:50%;background:var(--akzent);
  box-shadow:0 0 8px var(--akzent);animation:puls 2.6s ease-in-out infinite}
@keyframes puls{0%,100%{opacity:1}50%{opacity:.28}}
.claim{font-size:10.5px;line-height:1.5;color:var(--gedaempft);margin-top:7px;
  letter-spacing:.02em}
nav{display:flex;flex-direction:column;gap:1px}
nav button{background:none;border:0;border-left:2px solid transparent;
  text-align:left;padding:7px 11px;color:var(--gedaempft);cursor:pointer;
  font-size:12px;text-transform:uppercase;letter-spacing:.11em}
nav button:hover{color:var(--tinte);background:var(--flaeche)}
nav button[aria-current="true"]{border-left-color:var(--akzent);
  color:var(--akzent);background:var(--flaeche)}
.fuss{margin-top:auto;font-size:10.5px;color:var(--gedaempft);
  line-height:1.7;letter-spacing:.03em}
.schalter{display:flex;gap:1px;margin-top:9px}
.schalter button{flex:1;text-align:center;border:1px solid var(--linie);
  background:none;color:var(--gedaempft);padding:4px;cursor:pointer;
  font-size:10px;letter-spacing:.1em;text-transform:uppercase}
.schalter button[aria-pressed="true"]{background:var(--akzent-tief);
  color:var(--akzent);border-color:var(--akzent)}

main{padding:18px 26px 60px;max-width:1560px}
.statusleiste{display:flex;gap:0;align-items:center;flex-wrap:wrap;
  border-bottom:1px solid var(--linie);background:var(--grund2);
  padding:0 26px;font-family:var(--mono);font-size:10.5px;
  letter-spacing:.11em;text-transform:uppercase;color:var(--gedaempft);
  min-height:32px}
.statusleiste .feld{padding:8px 16px 8px 0;margin-right:16px;
  border-right:1px solid var(--linie);white-space:nowrap}
.statusleiste .feld:last-child{border-right:0;margin-left:auto;margin-right:0}
.statusleiste b{color:var(--tinte);font-weight:600;letter-spacing:.04em}
.statusleiste .gut{color:var(--bestaetigt)}
.statusleiste .warn{color:var(--einfach)}
.statusleiste .schlecht{color:var(--umstritten)}
h1{font-size:15px;letter-spacing:.18em;text-transform:uppercase;
  font-weight:600;margin:0 0 4px;color:var(--tinte)}
h1::before{content:"▸ ";color:var(--akzent)}
.lead{color:var(--gedaempft);font-size:12px;margin:0 0 20px;max-width:70ch;
  letter-spacing:.01em}

/* ===== Karte mit Eckwinkeln ===== */
.karte{background:var(--flaeche);border:1px solid var(--linie);
  padding:15px 17px;margin-bottom:13px;position:relative}
.karte::before,.karte::after{content:"";position:absolute;width:var(--eck);
  height:var(--eck);border-color:var(--akzent);opacity:.55}
.karte::before{top:-1px;left:-1px;border-top:1px solid;border-left:1px solid}
.karte::after{bottom:-1px;right:-1px;border-bottom:1px solid;
  border-right:1px solid}
.karte h2{font-size:10.5px;text-transform:uppercase;letter-spacing:.16em;
  color:var(--gedaempft);margin:0 0 12px;font-weight:600;
  border-bottom:1px solid var(--linie);padding-bottom:7px}

/* ===== Zwei Spalten ===== */
.zwei{display:grid;grid-template-columns:minmax(0,1fr) 396px;gap:20px;
  align-items:start}
@media(max-width:1120px){.zwei{grid-template-columns:1fr}}
@media(max-width:760px){.huelle{grid-template-columns:1fr}
  aside{flex-direction:row;flex-wrap:wrap;align-items:center;padding:10px;
    border-right:0;border-bottom:1px solid var(--linie)}
  nav{flex-direction:row;flex-wrap:wrap}.fuss{display:none}main{padding:14px}}

/* ===== Eingabe ===== */
.suchzeile{display:flex;gap:7px;margin-bottom:16px}
.suchzeile input{flex:1;padding:11px 13px;border:1px solid var(--linie);
  background:var(--flaeche);color:var(--tinte)}
.suchzeile input:focus{border-color:var(--akzent);box-shadow:var(--glanz)}
.knopf{background:var(--akzent-tief);color:var(--akzent);
  border:1px solid var(--akzent);padding:11px 20px;cursor:pointer;
  font-weight:600;text-transform:uppercase;letter-spacing:.12em;font-size:11px}
.knopf:hover{background:var(--akzent);color:var(--grund)}
.knopf.leise{background:none;color:var(--gedaempft);border-color:var(--linie);
  font-weight:400;padding:6px 12px;letter-spacing:.08em}
.knopf.leise:hover{color:var(--tinte);border-color:var(--linie-hell);
  background:var(--flaeche2)}
.knopf.warn{background:none;color:var(--umstritten);
  border-color:var(--umstritten)}
.knopf.warn:hover{background:var(--umstritten);color:var(--grund)}
label{display:block;font-size:10.5px;color:var(--gedaempft);margin:12px 0 4px;
  text-transform:uppercase;letter-spacing:.13em}
input[type=text],input[type=password],select,textarea{width:100%;
  padding:8px 10px;border:1px solid var(--linie);background:var(--flaeche2);
  color:var(--tinte)}
input:focus,textarea:focus,select:focus{border-color:var(--akzent);outline:none}
textarea{font-family:var(--mono);font-size:12px;resize:vertical}

/* ===== Antwort ===== */
.antwort{font-size:16px;line-height:1.5;margin:0 0 16px;color:var(--tinte);
  border-left:2px solid var(--akzent);padding-left:13px}
.leer{color:var(--gedaempft);font-size:12.5px}

/* ===== Fakt ===== */
.fakt{border:1px solid var(--linie);border-left-width:3px;padding:10px 13px;
  margin-bottom:7px;background:var(--flaeche);cursor:pointer;
  transition:background .12s,border-color .12s}
.fakt:hover{background:var(--flaeche2);border-color:var(--linie-hell)}
.fakt[aria-selected="true"]{border-color:var(--akzent);box-shadow:var(--glanz)}
.fakt.BESTAETIGT{border-left-color:var(--bestaetigt)}
.fakt.EINFACH_BELEGT{border-left-color:var(--einfach)}
.fakt.UMSTRITTEN{border-left-color:var(--umstritten)}
.fakt.WIDERRUFEN{border-left-color:var(--widerrufen);opacity:.5}
.fakt.WIDERRUFEN .tripel{text-decoration:line-through}
.tripel{font-size:14px}
.tripel .ent{font-weight:600;color:var(--tinte)}
.tripel .prd{color:var(--gedaempft);font-size:11.5px;
  text-transform:lowercase;letter-spacing:.04em}
.zeile2{display:flex;align-items:center;gap:11px;margin-top:6px;
  font-size:10.5px;letter-spacing:.06em;flex-wrap:wrap}
.marke-lage{text-transform:uppercase;letter-spacing:.15em;font-weight:600}
.BESTAETIGT .marke-lage{color:var(--bestaetigt)}
.EINFACH_BELEGT .marke-lage{color:var(--einfach)}
.UMSTRITTEN .marke-lage{color:var(--umstritten)}
.WIDERRUFEN .marke-lage{color:var(--widerrufen)}
.striche{display:inline-flex;gap:3px;align-items:flex-end;height:11px}
.striche i{width:2px;height:11px;background:currentColor;display:block;
  box-shadow:0 0 4px currentColor}
.striche i:nth-child(5){transform:rotate(58deg);margin-left:-11px}
.widerspruch{color:var(--umstritten)}

/* ===== Belege ===== */
.beleg{border-top:1px solid var(--linie);padding:11px 0}
.beleg:first-of-type{border-top:0}
.beleg .kopf{display:flex;justify-content:space-between;gap:8px;
  align-items:baseline}
.beleg .titel{font-weight:600;font-size:13px}
.stufe{font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;
  padding:2px 7px;border:1px solid var(--linie);color:var(--gedaempft);
  white-space:nowrap}
.stufe.WHISTLEBLOWER{border-color:var(--umstritten);color:var(--umstritten);
  background:repeating-linear-gradient(45deg,transparent,transparent 3px,
    rgba(255,92,92,.12) 3px,rgba(255,92,92,.12) 6px)}
.stufe.VERTRAULICH{border-color:var(--einfach);color:var(--einfach)}
.meta{font-family:var(--mono);font-size:10.5px;color:var(--gedaempft);
  margin-top:5px;
  word-break:break-word;letter-spacing:.03em}
.zitat{font-size:12px;color:var(--tinte);opacity:.82;
  border-left:2px solid var(--linie-hell);padding-left:9px;margin-top:7px}

/* ===== Schwärzung: der stärkste Akzent im Bild ===== */
.schwarz{background:var(--schwarz-bg);color:var(--schwarz-bg);border:0;
  border-left:2px solid var(--umstritten);width:100%;text-align:left;
  padding:8px 11px;cursor:pointer;font-size:11.5px;letter-spacing:.12em;
  transition:color .18s ease;
  background-image:repeating-linear-gradient(45deg,transparent,transparent 5px,
    rgba(255,92,92,.10) 5px,rgba(255,92,92,.10) 10px)}
.schwarz:hover,.schwarz:focus-visible{color:var(--gedaempft)}
.schwarz[aria-expanded="true"]{color:var(--umstritten)}
.schwarz-grund{font-size:11.5px;color:var(--gedaempft);margin-top:6px;
  display:none;border-left:2px solid var(--umstritten);padding-left:9px}
.schwarz[aria-expanded="true"]+.schwarz-grund{display:block}
@media(prefers-reduced-motion:reduce){*{animation:none!important;
  transition:none!important}}

/* ===== Listen ===== */
.reiter{display:flex;gap:0;border-bottom:1px solid var(--linie);
  margin-bottom:15px;flex-wrap:wrap}
.reiter button{background:none;border:0;border-bottom:2px solid transparent;
  padding:8px 14px;cursor:pointer;color:var(--gedaempft);font-size:11px;
  text-transform:uppercase;letter-spacing:.12em}
.reiter button[aria-selected="true"]{border-bottom-color:var(--akzent);
  color:var(--akzent)}
.zahl{font-size:10px;margin-left:6px;border:1px solid var(--linie);
  padding:0 5px;color:var(--gedaempft)}
.paar{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;
  align-items:center;padding:11px 0;border-top:1px solid var(--linie)}
.paar:first-child{border-top:0}
.gegen{color:var(--akzent);font-size:11px;letter-spacing:.06em}
.achtung{border-left:2px solid var(--umstritten);padding:8px 11px;
  font-size:11.5px;margin-top:8px;color:var(--umstritten);
  background:rgba(255,92,92,.055)}
.aktionen{display:flex;gap:7px;margin-top:10px;flex-wrap:wrap;
  align-items:center}
.pfad{font-family:var(--mono);font-size:12px;line-height:2;padding:11px 0;
  border-top:1px solid var(--linie);word-break:break-word}
.pfad:first-child{border-top:0}
.pfad .ent{background:var(--flaeche2);border:1px solid var(--linie);
  padding:2px 7px;font-weight:600}
.pfad .prd{color:var(--akzent);font-size:11px;letter-spacing:.05em}
.kennz{display:flex;gap:26px;flex-wrap:wrap;font-size:10.5px;
  color:var(--gedaempft);margin-top:6px;text-transform:uppercase;
  letter-spacing:.13em}
.kennz b{display:block;font-size:22px;color:var(--akzent);font-weight:600;
  letter-spacing:0;text-shadow:0 0 14px var(--akzent)}
.hinweis{font-size:11.5px;color:var(--gedaempft);margin-top:10px}
.fehler{border:1px solid var(--umstritten);color:var(--umstritten);
  padding:9px 12px;font-size:12px;margin-bottom:12px;
  background:rgba(255,92,92,.06)}
</style></head><body>
<div class="huelle">
<aside>
  <div>
    <div class="marke-zeile"><span class="puls"></span>
      <span class="marke">Indra<span>Net</span></span></div>
    <div class="claim" data-t="app.tagline"></div>
  </div>
  <nav id="nav"></nav>
  <div class="fuss">
    <div><span class="punkt">●</span> <span data-t="app.local"></span></div>
    <div id="fuss-zahlen"></div>
    <div class="schalter">
      <button data-lang="de" onclick="setzeSprache('de')">DE</button>
      <button data-lang="en" onclick="setzeSprache('en')">EN</button>
    </div>
    <div class="schalter" id="themen"></div>
  </div>
</aside>
<div style="display:flex;flex-direction:column;min-width:0">
  <div class="statusleiste" id="status"></div>
  <main id="main"></main>
</div>
</div>
<script>
let L={}, P={}, SPRACHE="de", ANSICHT="ask", STATE={}, GEWAEHLT=null,
    LETZTE=null, ROLLE="GAST", SITZUNG=null, THEMA="lagezentrale", THEMEN=[],
    SICHERUNG=null;

async function jetztSichern(){
  try{
    const r = await api("/api/sichern", {});
    await ladeState(); zeichne();
    alert(tr("bk.done")+"\n\n"+r.datei+"\n"+(r.bytes/1048576).toFixed(1)+" MB · "
          +r.teile+" "+tr("bk.parts"));
  }catch(e){ alert(fehlerText(e)); }
}

function setzeThema(t){
  THEMA=t;
  document.documentElement.setAttribute("data-thema",t);
  zeichneThemen();
  // Kein localStorage: Die Wahl gilt fuer die Sitzung. Ein Werkzeug fuer
  // Quellenmaterial soll moeglichst wenig auf dem Geraet hinterlassen.
}
function zeichneThemen(){
  const z=$("#themen"); if(!z) return;
  z.innerHTML=THEMEN.map(t=>
    `<button aria-pressed="${t.schluessel===THEMA}"
      onclick="setzeThema('${t.schluessel}')">${esc(t.name)}</button>`).join("");
}

const $=(s,w=document)=>w.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const tr=k=>L[k]||k;

async function api(pfad,daten){
  const opt=daten?{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(daten)}:{};
  const r=await fetch(pfad,opt);
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

async function setzeSprache(s){
  SPRACHE=s;
  const d=await api("/api/sprache?lang="+s);
  L=d.texte; P=d.praedikate; THEMEN=d.themen||THEMEN;
  document.documentElement.lang=s;
  document.querySelectorAll("[data-lang]").forEach(b=>
    b.setAttribute("aria-pressed",b.dataset.lang===s));
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
  zeichneNav(); zeichneThemen(); zeichne();
}

function zeichneNav(){
  const punkte=[["ask","nav.ask"],["verify","nav.verify"],
    ["entities","nav.entities"],["network","nav.network"],
    ["record","nav.record"],
    ["sources","nav.sources"],["external","nav.external"],
    ["import","nav.import"]];
  $("#nav").innerHTML=punkte.map(([k,t])=>
    `<button onclick="geheZu('${k}')" aria-current="${ANSICHT===k}">${esc(tr(t))}</button>`
  ).join("");
}
function geheZu(a){ANSICHT=a;GEWAEHLT=null;zeichneNav();zeichne();}

function striche(n){
  const s=[];for(let i=0;i<Math.min(n,5);i++)s.push("<i></i>");
  return `<span class="striche">${s.join("")}</span>${n>5?"+"+(n-5):""}`;
}
function faktKarte(f,waehlbar=true){
  const lage=f.beleglage;
  const wid=f.widersprueche&&f.widersprueche.length
    ? `<span class="widerspruch">${esc(tr("ev.contradicts"))}: ${esc(f.widersprueche.join(", "))}</span>`:"";
  return `<div class="fakt ${lage}" ${waehlbar?`onclick="waehle('${f.fact_id}')"`:""}
      aria-selected="${GEWAEHLT===f.fact_id}" tabindex="0"
      onkeydown="if(event.key==='Enter')waehle('${f.fact_id}')">
    <div class="tripel"><span class="ent">${esc(f.subjekt)}</span>
      <span class="prd">${esc(P[f.praedikat]||f.praedikat)}</span>
      <span class="ent">${esc(f.objekt)}</span></div>
    <div class="zeile2"><span class="marke-lage" title="${esc(tr("state."+lage+".hint"))}">${esc(tr("state."+lage))}</span>
      ${f.quellen.length?striche(f.quellen.length):""}
      <span>${esc(f.quellen.join(" · "))}</span>${wid}</div></div>`;
}

async function waehle(id){
  GEWAEHLT=id;
  const d=await api("/api/belege?fact_id="+encodeURIComponent(id));
  zeichne(); zeichneBelege(d);
}
function zeichneBelege(d){
  const ziel=$("#belege"); if(!ziel) return;
  if(!d||!d.belege.length){ziel.innerHTML=`<p class="leer">${esc(tr("ev.none"))}</p>`;return;}
  ziel.innerHTML=`
    <div class="meta">${esc(tr("ev.role"))}: <b>${esc(ROLLE)}</b></div>
    <div style="margin-top:14px">`+
    d.belege.map((b,i)=>{
      if(b.status==="zurueckgehalten"){
        return `<div class="beleg">
          <button class="schwarz" aria-expanded="false"
            onclick="this.setAttribute('aria-expanded',this.getAttribute('aria-expanded')!=='true')">
            ${"█".repeat(26)}</button>
          <div class="schwarz-grund"><b>${esc(tr("ev.withheld"))} · ${esc(b.stufe)}</b><br>
            ${esc(tr("ev.withheld_why"))}</div></div>`;
      }
      return `<div class="beleg">
        <div class="kopf"><span class="titel">${esc(b.quelle)}</span>
          <span class="stufe ${esc(b.stufe)}">${esc(b.stufe)}</span></div>
        <div class="meta">${esc(tr("ev.locator"))}: ${esc(b.fundstelle||"—")}<br>
          ${esc(tr("ev.recorded"))}: ${esc(b.erfasst_von||"—")}<br>
          ${esc(b.doc_id)}</div>
        ${b.zitat?`<div class="zitat">${esc(b.zitat)}</div>`:""}
        <div class="aktionen">
          ${b.abgelegt?`<button class="knopf leise" onclick="belegOeffnen('${esc(b.doc_id)}')">
            ${esc(tr("ev.open_doc"))}</button>`:""}
          ${b.widerrufen?"":`
            <button class="knopf leise" onclick="korrigieren('${esc(b.aussage_id)}','aendern')">
              ${esc(tr("cor.edit"))}</button>
            <button class="knopf leise" onclick="korrigieren('${esc(b.aussage_id)}','widerrufen')">
              ${esc(tr("cor.retract"))}</button>
            <button class="knopf leise warn" onclick="korrigieren('${esc(b.aussage_id)}','verwerfen')">
              ${esc(tr("cor.discard"))}</button>`}
        </div>
        <div id="kor-${esc(b.aussage_id)}"></div>
        ${b.widerrufen?`<div class="achtung">${esc(tr("state.WIDERRUFEN"))}: ${esc(b.widerruf_grund||"")}</div>`:""}
      </div>`;}).join("")+
    `</div><div class="aktionen">
      <button class="knopf leise" onclick="kopiereKette('${d.fact_id}')">${esc(tr("ev.copy"))}</button>
      <button class="knopf leise" onclick="ketteExport('${d.fact_id}')">${esc(tr("ev.export"))}</button>
    </div>`;
}
function ketteExport(fact_id){
  window.open("/api/kette_export?fact_id="+encodeURIComponent(fact_id)
    +"&lang="+SPRACHE, "_blank");
}

function korrigieren(aussage_id, art){
  const z = document.getElementById("kor-"+aussage_id);
  if(!z) return;
  if(z.innerHTML){ z.innerHTML=""; return; }
  const felder = art==="aendern" ? `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
      <div><label>${esc(tr("rec.subject"))}</label><input type="text" id="k-s-${esc(aussage_id)}"></div>
      <div><label>${esc(tr("rec.object"))}</label><input type="text" id="k-o-${esc(aussage_id)}"></div>
    </div>
    <label>${esc(tr("rec.locator"))}</label>
    <input type="text" id="k-f-${esc(aussage_id)}">
    <div class="hinweis">${esc(tr("cor.edit_hint"))}</div>` : "";
  const warnung = art==="verwerfen"
    ? `<div class="achtung">${esc(tr("cor.discard_hint"))}</div>`
    : (art==="widerrufen" ? `<div class="hinweis">${esc(tr("cor.retract_hint"))}</div>` : "");
  z.innerHTML = `<div style="border-left:2px solid var(--akzent);padding-left:11px;
      margin-top:10px">${felder}${warnung}
    <label>${esc(tr("en.reason"))}</label>
    <input type="text" id="k-g-${esc(aussage_id)}">
    <div class="aktionen">
      <button class="knopf" onclick="korrekturAusfuehren('${esc(aussage_id)}','${art}')">
        ${esc(tr("cor.confirm"))}</button>
      <button class="knopf leise" onclick="korrigieren('${esc(aussage_id)}','${art}')">
        ${esc(tr("gen.cancel"))}</button>
    </div></div>`;
  const erstes = z.querySelector("input"); if(erstes) erstes.focus();
}

async function korrekturAusfuehren(aussage_id, art){
  const g = document.getElementById("k-g-"+aussage_id);
  const grund = (g&&g.value||"").trim();
  if(!grund){ if(g){ g.focus(); g.placeholder=tr("gen.required"); } return; }
  const pfad = {aendern:"/api/aussage_aendern", widerrufen:"/api/aussage_widerrufen",
                verwerfen:"/api/aussage_verwerfen"}[art];
  const daten = {aussage_id, begruendung:grund};
  if(art==="aendern"){
    const g1=document.getElementById("k-s-"+aussage_id);
    const g2=document.getElementById("k-o-"+aussage_id);
    const g3=document.getElementById("k-f-"+aussage_id);
    if(g1&&g1.value.trim()) daten.subjekt=g1.value.trim();
    if(g2&&g2.value.trim()) daten.objekt=g2.value.trim();
    if(g3&&g3.value.trim()) daten.fundstelle=g3.value.trim();
  }
  try{
    await api(pfad, daten);
    await ladeState(); GEWAEHLT=null; LETZTE=null; ANSICHT="ask"; zeichne();
  }catch(e){ alert(fehlerText(e)); }
}

function belegOeffnen(doc_id){
  // Fuehrt ueber den Server, damit das Indra-Juwel den Zugriff prueft.
  window.open("/api/beleg_datei?doc_id="+encodeURIComponent(doc_id), "_blank");
}

async function kopiereKette(id){
  const k=await api("/api/kette?fact_id="+encodeURIComponent(id));
  await navigator.clipboard.writeText(JSON.stringify(k,null,2));
}

function ansichtAnmeldung(fehler){
  return `<div style="max-width:380px;margin:60px auto">
    <h1 style="margin-bottom:6px">IndraNet</h1>
    <p class="lead">${esc(tr("auth.lead"))}</p>
    <div class="karte">
      ${fehler?`<div class="fehler">${esc(fehler)}</div>`:""}
      <label>${esc(tr("auth.user"))}</label>
      <input type="text" id="benutzer" autocomplete="username"
        onkeydown="if(event.key==='Enter')document.getElementById('passwort').focus()">
      <label>${esc(tr("auth.pass"))}</label>
      <input type="password" id="passwort" autocomplete="current-password"
        onkeydown="if(event.key==='Enter')anmelden()">
      <div class="aktionen">
        <button class="knopf" onclick="anmelden()">${esc(tr("auth.login"))}</button>
      </div>
    </div>
    <p class="hinweis">${esc(tr("auth.note"))}</p>
  </div>`;
}
async function anmelden(){
  const benutzer=$("#benutzer").value.trim(), passwort=$("#passwort").value;
  if(!benutzer||!passwort) return;
  try{
    await api("/api/anmelden",{benutzer,passwort});
    await ladeState(); ANSICHT="ask"; zeichneNav(); zeichne();
  }catch(e){
    let m=tr("auth.failed");
    try{ m=JSON.parse(String(e).replace(/^Error: /,"")).fehler||m; }catch(_){}
    $("#main").innerHTML=ansichtAnmeldung(m);
    document.querySelectorAll("[data-t]").forEach(x=>x.textContent=tr(x.dataset.t));
  }
}
async function abmelden(){
  await api("/api/abmelden",{}); await ladeState();
  zeichneNav(); zeichne();
}

/* ------------------------------- Ansichten ------------------------------ */
function zeichne(){
  const m=$("#main");
  if(STATE.anmeldepflicht && ROLLE==="GAST"){
    m.innerHTML=ansichtAnmeldung(null);
    $("#nav").innerHTML="";
    document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
    return;
  }
  if(ANSICHT==="ask") m.innerHTML=ansichtFragen();
  else if(ANSICHT==="verify") {m.innerHTML="";ansichtPruefen();}
  else if(ANSICHT==="entities"){m.innerHTML="";ansichtEntitaeten();}
  else if(ANSICHT==="network"){ m.innerHTML=ansichtNetz();
    if(NETZ.modus==="graph") setTimeout(malen, 30); }
  else if(ANSICHT==="sources"){m.innerHTML="";ansichtQuellen();}
  else if(ANSICHT==="record"){m.innerHTML="";ansichtErfassen();}
  else if(ANSICHT==="external"){m.innerHTML="";ansichtExtern();}
  else if(ANSICHT==="import") m.innerHTML=ansichtImport();
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
  if(ANSICHT==="ask"&&LETZTE) zeichneBelege(LETZTE.belege||null);
  fussZahlen(); zeichneStatus();
}
function zeichneStatus(){
  const z=$("#status"); if(!z||!STATE.stats) return;
  const s=STATE.stats;
  const anteil = s.anteil_bestaetigt!=null ? s.anteil_bestaetigt : 0;
  const klasse = anteil>=60?"gut":(anteil>=25?"warn":"schlecht");
  const teile=[
    `<span class="feld">${esc(tr("st.pod"))} <b>${esc(STATE.pod||"—")}</b></span>`,
    `<span class="feld">${esc(STATE.pod_id||"")}</span>`,
    `<span class="feld">${esc(tr("st.role"))} <b>${esc(ROLLE)}</b></span>`,
    `<span class="feld">${esc(tr("gen.assertions"))} <b>${s.aktive_aussagen}</b></span>`,
    `<span class="feld">${esc(tr("vf.share"))} <b class="${klasse}">${anteil}%</b></span>`,
    `<span class="feld">${s.verschluesselt?"🔒 "+esc(tr("auth.encrypted")):
      "⚠ "+esc(tr("st.plain"))}</span>`];
  if(SICHERUNG && s.verschluesselt){
    const alt = SICHERUNG.tage;
    const kl = !SICHERUNG.vorhanden||alt>14 ? "schlecht" : (alt>3?"warn":"gut");
    teile.splice(teile.length-1, 0,
      `<span class="feld"><a href="#" onclick="jetztSichern();return false"
        class="${kl}" style="text-decoration:none">${esc(tr("bk.label"))}
        <b class="${kl}">${SICHERUNG.vorhanden?alt+" "+esc(tr("ex.days")):esc(tr("bk.never"))}</b>
        · ${esc(tr("bk.now"))}</a></span>`);
  }
  z.innerHTML=teile.join("");
}

function fussZahlen(){
  if(!STATE.stats) return;
  $("#fuss-zahlen").innerHTML=
    `<span style="color:var(--akzent)">${STATE.stats.aktive_aussagen}</span> ${esc(tr("gen.assertions"))}<br>`+
    `<span style="color:var(--akzent)">${STATE.stats.entitaeten}</span> ${esc(tr("gen.entities"))}`+
    (STATE.stats.verschluesselt?`<br>🔒 ${esc(tr("auth.encrypted"))}`:"")+
    (SITZUNG?`<br>${esc(SITZUNG.anzeige)} · ${esc(SITZUNG.rolle)}
      <br><a href="#" onclick="abmelden();return false"
        style="color:#8D979F">${esc(tr("auth.logout"))}</a>`:"");
}

function ansichtFragen(){
  const a=LETZTE;
  let block=`<p class="leer">${esc(tr("ask.empty"))}</p>`;
  if(a){
    let kopf="";
    if(a.status==="UNKNOWN_PREDICATE") kopf=`<p class="antwort">${esc(tr("ask.no_predicate"))}</p>`;
    else if(a.status==="UNSUPPORTED_DIRECTION") kopf=`<p class="antwort">${esc(tr("ask.unsupported"))}</p>`;
    else kopf=`<p class="antwort">${esc(a.antwort||tr("ask.nomatch"))}</p>`;
    const warn=a.warnungen&&a.warnungen.length
      ?`<div class="achtung">${esc(tr("ask.discarded"))} ${esc(a.warnungen.join(", "))}</div>`:"";
    block=kopf+warn+(a.fakten||[]).map(f=>faktKarte(f)).join("");
  }
  return `<h1 data-t="ask.title"></h1>
  <div class="zwei"><div>
    <div class="suchzeile">
      <input id="frage" placeholder="${esc(tr("ask.placeholder"))}"
        onkeydown="if(event.key==='Enter')frag()">
      <button class="knopf" onclick="frag()">${esc(tr("ask.submit"))}</button>
    </div>
    <div id="ergebnis">${block}</div>
  </div>
  <div class="karte"><h2>${esc(tr("ev.title"))}</h2><div id="belege">
    <p class="leer">${esc(tr("ev.none"))}</p></div></div></div>`;
}
async function frag(){
  const f=$("#frage").value.trim(); if(!f) return;
  try{ LETZTE=await api("/api/frage",{frage:f}); GEWAEHLT=null; }
  catch(e){ LETZTE={status:"FEHLER",antwort:String(e),fakten:[]}; }
  zeichne(); $("#frage").value=f;
}

async function ansichtPruefen(){
  const d=await api("/api/prueflisten");
  const gruppen=[["umstritten","vf.contested"],["einfach_belegt","vf.single"],
                 ["widerrufen","vf.retracted"],["bestaetigt","vf.confirmed"]];
  const aktiv=window._pruefReiter||"umstritten";
  const liste=d[aktiv]||[];
  $("#main").innerHTML=`<h1 data-t="vf.title"></h1>
    <p class="lead">${esc(tr("vf.share"))}: <b>${d.uebersicht.anteil_bestaetigt}%</b></p>
    <div class="zwei"><div>
      <div class="reiter">${gruppen.map(([k,t])=>
        `<button aria-selected="${k===aktiv}" onclick="window._pruefReiter='${k}';ansichtPruefen()">
          ${esc(tr(t))}<span class="zahl">${d[k].length}</span></button>`).join("")}</div>
      ${liste.length?liste.map(f=>faktKarte(f)).join(""):
        `<p class="leer">${esc(tr("vf.clean"))}</p>`}
    </div>
    <div class="karte"><h2>${esc(tr("ev.title"))}</h2><div id="belege">
      <p class="leer">${esc(tr("ev.none"))}</p></div></div></div>`;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
}

async function ansichtEntitaeten(){
  const d=await api("/api/vorschlaege");
  $("#main").innerHTML=`<h1 data-t="en.title"></h1>
    <p class="lead">${esc(tr("en.lead"))}</p>
    <div class="karte">${d.vorschlaege.length?d.vorschlaege.map((v,i)=>`
      <div class="paar">
        <div><b>${esc(v.a)}</b><div class="meta">${esc(v.key_a)}</div></div>
        <div class="gegen">↔ ${v.score.toFixed(3)}</div>
        <div><b>${esc(v.b)}</b><div class="meta">${esc(v.key_b)}</div></div>
      </div>
      ${v.warnung?`<div class="achtung"><b>${esc(tr("en.warn"))}:</b> ${esc(v.warnung)}</div>`:""}
      <div class="aktionen">
        <input type="text" id="grund${i}" placeholder="${esc(tr("en.reason"))}"
          style="flex:1;min-width:200px">
        <button class="knopf leise" onclick="entscheide(${i},'merge')">${esc(tr("en.merge"))}</button>
        <button class="knopf leise" onclick="entscheide(${i},'separate')">${esc(tr("en.separate"))}</button>
      </div>`).join("<hr style='border:0;border-top:1px solid var(--linie);margin:16px 0'>")
      :`<p class="leer">${esc(tr("en.clean"))}</p>`}</div>`;
  window._vorschlaege=d.vorschlaege;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
}
async function entscheide(i,art){
  const v=window._vorschlaege[i];
  const grund=$("#grund"+i).value.trim();
  if(!grund){$("#grund"+i).focus();$("#grund"+i).placeholder=tr("gen.required");return;}
  await api("/api/entscheiden",{art,key_a:v.key_a,key_b:v.key_b,begruendung:grund});
  await ladeState(); ansichtEntitaeten();
}

let NETZ = {modus:"graph", daten:null, mittelpunkt:"", tiefe:2};

function ansichtNetz(){
  const p = window._pfade;
  const g = NETZ.modus === "graph";
  return `<h1>${esc(g?tr("nw.graph_title"):tr("nw.title"))}</h1>
  <p class="lead">${esc(g?tr("nw.graph_hint"):tr("nw.hint"))}</p>
  <div class="reiter">
    <button aria-selected="${g}" onclick="NETZ.modus='graph';zeichne()">
      ${esc(tr("nw.graph"))}</button>
    <button aria-selected="${!g}" onclick="NETZ.modus='pfade';zeichne()">
      ${esc(tr("nw.paths"))}</button>
  </div>
  ${g ? `
  <div class="karte">
    <div style="display:grid;grid-template-columns:1fr 120px auto;gap:10px;align-items:end">
      <div><label>${esc(tr("nw.center"))}</label>
        <input type="text" id="mitte" value="${esc(NETZ.mittelpunkt)}"
          onkeydown="if(event.key==='Enter')netzZeichnen()"></div>
      <div><label>${esc(tr("nw.depth"))}</label>
        <select id="tiefe">${[1,2,3].map(x=>
          `<option ${x===NETZ.tiefe?"selected":""}>${x}</option>`).join("")}</select></div>
      <button class="knopf" onclick="netzZeichnen()">${esc(tr("nw.draw"))}</button>
    </div>
  </div>
  <div class="karte" style="padding:0;overflow:hidden">
    <canvas id="netz" style="width:100%;height:560px;display:block;
      cursor:grab"></canvas>
  </div>
  <div class="kennz" id="netz-info"></div>` : `
  <div class="karte">
    <div style="display:grid;grid-template-columns:1fr 1fr auto;gap:10px;align-items:end">
      <div><label>${esc(tr("nw.from"))}</label><input type="text" id="von"></div>
      <div><label>${esc(tr("nw.to"))}</label><input type="text" id="nach"></div>
      <button class="knopf" onclick="suchePfad()">${esc(tr("nw.find"))}</button>
    </div>
  </div>
  ${p?`<div class="karte">${p.pfade.length?p.pfade.map(x=>`
    <div class="pfad">${x.html}
      <div class="meta">${esc(tr("nw.weakest"))}: ${esc(tr("state."+x.schwaechstes))}</div>
    </div>`).join(""):`<p class="leer">${esc(tr("nw.none"))}</p>`}</div>`:""}`}`;
}

async function netzZeichnen(){
  const feld = $("#mitte");
  const mitte = (feld ? feld.value : NETZ.mittelpunkt).trim();
  if(!mitte) return;
  NETZ.mittelpunkt = mitte;
  const tf = $("#tiefe"); if(tf) NETZ.tiefe = parseInt(tf.value, 10);
  try{
    NETZ.daten = await api("/api/netz", {entitaet:mitte, tiefe:NETZ.tiefe});
  }catch(e){ NETZ.daten = null; }
  malen();
}

/* Kraftgerichteter Graph. Bewusst eigenhaendig statt einer Bibliothek:
   Die Oberflaeche laedt nichts nach, und fuer ein paar hundert Knoten
   genuegen zweihundert Zeilen. */
function malen(){
  const c = $("#netz"); if(!c) return;
  const info = $("#netz-info");
  const d = NETZ.daten;
  if(!d || !d.knoten.length){
    if(info) info.innerHTML = `<span>${esc(tr("nw.empty"))}</span>`;
    const x = c.getContext("2d"); x.clearRect(0,0,c.width,c.height); return;
  }
  const dpr = window.devicePixelRatio || 1;
  const b = c.getBoundingClientRect();
  c.width = b.width*dpr; c.height = b.height*dpr;
  const ctx = c.getContext("2d"); ctx.scale(dpr,dpr);
  const W = b.width, H = b.height;

  const stil = getComputedStyle(document.documentElement);
  const farbe = n => stil.getPropertyValue(n).trim();
  const LAGE = {BESTAETIGT:farbe("--bestaetigt"), EINFACH_BELEGT:farbe("--einfach"),
                UMSTRITTEN:farbe("--umstritten"), WIDERRUFEN:farbe("--widerrufen")};

  // Knoten anlegen, Startknoten in die Mitte
  const idx = new Map();
  const kn = d.knoten.map((n,i)=>{
    const start = n.anzeige === d.start;
    const w = i/d.knoten.length*Math.PI*2;
    const o = {name:n.anzeige, abstand:n.abstand, grad:n.grad||1, start,
      x: W/2 + (start?0:Math.cos(w)*(60+n.abstand*90)),
      y: H/2 + (start?0:Math.sin(w)*(60+n.abstand*90)), vx:0, vy:0};
    idx.set(n.anzeige, o); return o;
  });
  const ka = d.kanten.map(k=>({...k, a:idx.get(k.von), b:idx.get(k.nach)}))
                     .filter(k=>k.a&&k.b);

  for(let s=0; s<220; s++){
    for(const n of kn){                       // Abstossung
      for(const m of kn){
        if(n===m) continue;
        let dx=n.x-m.x, dy=n.y-m.y, q=dx*dx+dy*dy||1;
        if(q<62500){ const f=1400/q; n.vx+=dx*f; n.vy+=dy*f; }
      }
      const dx=W/2-n.x, dy=H/2-n.y;           // sanft zur Mitte
      n.vx += dx*0.0016; n.vy += dy*0.0016;
    }
    for(const k of ka){                       // Anziehung
      const dx=k.b.x-k.a.x, dy=k.b.y-k.a.y;
      const l=Math.sqrt(dx*dx+dy*dy)||1, f=(l-120)*0.012;
      const ux=dx/l*f, uy=dy/l*f;
      k.a.vx+=ux; k.a.vy+=uy; k.b.vx-=ux; k.b.vy-=uy;
    }
    for(const n of kn){
      if(n.start){ n.x=W/2; n.y=H/2; n.vx=n.vy=0; continue; }
      n.x += n.vx*0.5; n.y += n.vy*0.5; n.vx*=0.82; n.vy*=0.82;
      n.x = Math.max(60, Math.min(W-60, n.x));
      n.y = Math.max(28, Math.min(H-28, n.y));
    }
  }

  ctx.clearRect(0,0,W,H);
  const belegt = new Map();                    // Beschriftungsplätze je Knoten
  for(const k of ka){                          // Kanten
    ctx.beginPath();
    ctx.moveTo(k.a.x,k.a.y); ctx.lineTo(k.b.x,k.b.y);
    ctx.strokeStyle = LAGE[k.beleglage] || farbe("--linie");
    ctx.lineWidth = k.beleglage==="BESTAETIGT" ? 2 : 1;
    if(k.beleglage==="WIDERRUFEN") ctx.setLineDash([3,4]); else ctx.setLineDash([]);
    ctx.globalAlpha = k.beleglage==="WIDERRUFEN" ? .35 : .75;
    ctx.stroke(); ctx.globalAlpha = 1;
    // Beschriftung: bei kurzen Kanten weglassen, sonst versetzt setzen,
    // damit zwei Kanten zum selben Knoten sich nicht ueberschreiben.
    const laenge = Math.hypot(k.b.x-k.a.x, k.b.y-k.a.y);
    if(laenge > 96){
      const t = 0.34 + (belegt.get(k.a)||0)*0.13;
      belegt.set(k.a, (belegt.get(k.a)||0)+1);
      const mx=k.a.x+(k.b.x-k.a.x)*t, my=k.a.y+(k.b.y-k.a.y)*t;
      ctx.font = "9px ui-monospace,monospace";
      ctx.textAlign="center";
      const wort = (P[k.praedikat]||k.praedikat).slice(0,20);
      const br = ctx.measureText(wort).width;
      ctx.fillStyle = farbe("--grund");        // Hintergrund freistellen
      ctx.fillRect(mx-br/2-3, my-11, br+6, 12);
      ctx.fillStyle = farbe("--gedaempft");
      ctx.fillText(wort, mx, my-2);
    }
  }
  ctx.setLineDash([]);
  for(const n of kn){                           // Knoten
    const r = n.start ? 9 : Math.min(4+n.grad, 9);
    if(n.start){
      ctx.beginPath(); ctx.arc(n.x,n.y,r+7,0,Math.PI*2);
      ctx.strokeStyle=farbe("--akzent"); ctx.globalAlpha=.35;
      ctx.lineWidth=1; ctx.stroke(); ctx.globalAlpha=1;
    }
    ctx.beginPath(); ctx.arc(n.x,n.y,r,0,Math.PI*2);
    ctx.fillStyle = n.start ? farbe("--akzent") : farbe("--flaeche2");
    ctx.fill();
    ctx.strokeStyle = n.start ? farbe("--akzent") : farbe("--linie-hell");
    ctx.lineWidth = 1.5; ctx.stroke();
    ctx.font = (n.start?"600 ":"")+"11px ui-monospace,monospace";
    ctx.fillStyle = n.start ? farbe("--akzent") : farbe("--tinte");
    ctx.textAlign = "center";
    const t = n.name.length>26 ? n.name.slice(0,25)+"…" : n.name;
    ctx.fillText(t, n.x, n.y + r + 13);
  }
  NETZ.knoten = kn;
  c.onclick = ev => {
    const r = c.getBoundingClientRect();
    const mx = ev.clientX-r.left, my = ev.clientY-r.top;
    const treffer = kn.find(n => Math.hypot(n.x-mx, n.y-my) < 16);
    if(treffer && !treffer.start){
      NETZ.mittelpunkt = treffer.name;
      const f=$("#mitte"); if(f) f.value = treffer.name;
      netzZeichnen();
    }
  };
  if(info) info.innerHTML =
    `<span><b>${kn.length}</b> ${esc(tr("nw.nodes"))}</span>
     <span><b>${ka.length}</b> ${esc(tr("nw.edges"))}</span>
     <span style="text-transform:none;letter-spacing:0">
       ${esc(tr("nw.legend"))} · ${esc(tr("nw.click"))}</span>`;
}

async function suchePfad(){
  const von=$("#von").value.trim(), nach=$("#nach").value.trim();
  if(!von||!nach) return;
  window._pfade = await api("/api/pfad",{von,nach});
  zeichne(); $("#von").value=von; $("#nach").value=nach;
}

async function ansichtQuellen(){
  const d=await api("/api/dokumente");
  $("#main").innerHTML=`<h1 data-t="src.title"></h1>
  <div class="karte">${d.dokumente.map((k,i)=>`
    <div class="beleg">
      <div class="kopf">
        <span class="titel" ${k.widerrufen?"style='text-decoration:line-through'":""}>${esc(k.titel)}</span>
        <span class="stufe ${esc(k.stufe)}">${esc(k.stufe)}</span></div>
      <div class="meta">${esc(k.quelle)} · ${esc(k.aussagen)} ${esc(tr("gen.assertions"))}
        · sha256 ${esc(k.sha256.slice(0,16))}…</div>
      ${k.widerrufen?`<div class="achtung">${esc(tr("src.retracted"))}: ${esc(k.widerruf_grund||"")}</div>`
        :`<div class="aktionen">
          <span class="meta">${esc(tr("src.falls"))}: <b>${k.faellt_ersatzlos}</b> / ${k.betroffen}</span>
          <input type="text" id="wg${i}" placeholder="${esc(tr("en.reason"))}" style="flex:1;min-width:180px">
          <button class="knopf warn" onclick="widerrufe('${esc(k.doc_id)}',${i})">${esc(tr("src.retract"))}</button>
        </div>`}
    </div>`).join("")}</div>`;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
}
async function widerrufe(id,i){
  const g=$("#wg"+i).value.trim();
  if(!g){$("#wg"+i).focus();$("#wg"+i).placeholder=tr("gen.required");return;}
  if(!confirm(tr("src.confirm_retract"))) return;
  await api("/api/widerrufen",{doc_id:id,grund:g});
  await ladeState(); ansichtQuellen();
}

let ERF = {beleg:null, letzte:[], art:"datei"};

async function ansichtErfassen(fehler){
  const d = await api("/api/belege_liste");
  const b = ERF.beleg;
  $("#main").innerHTML = `<h1 data-t="rec.title"></h1>
  <p class="lead">${esc(tr("rec.lead"))}</p>
  <div class="zwei">
    <div>
      <div class="karte"><h2>${esc(tr("rec.step2"))}</h2>
        ${b ? `
          <div class="fakt EINFACH_BELEGT" style="cursor:default">
            <div class="tripel"><span class="ent">${esc(b.titel)}</span></div>
            <div class="zeile2"><span class="marke-lage">${esc(b.quelle)}</span>
              <span>${esc(b.stufe)}</span>
              <span>sha ${esc((b.sha256||"").slice(0,16))}…</span>
              ${b.abgelegt?`<span style="color:var(--bestaetigt)">
                🔒 ${esc(tr("rec.stored"))}${b.bytes?" · "+(b.bytes/1024).toFixed(0)+" KB":""}
              </span>`:""}</div>
          </div>
          ${fehler?`<div class="fehler">${esc(fehler)}</div>`:""}
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div><label>${esc(tr("rec.subject"))}</label>
              <input type="text" id="subj" autofocus></div>
            <div><label>${esc(tr("rec.object"))}</label>
              <input type="text" id="obj"></div>
          </div>
          <label>${esc(tr("rec.predicate"))}</label>
          <select id="prd">${d.praedikate.map(x=>
            `<option value="${esc(x)}">${esc(P[x]||x)}</option>`).join("")}</select>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div><label>${esc(tr("rec.locator"))}</label>
              <input type="text" id="fund" placeholder="${esc(tr("rec.locator_ph"))}"></div>
            <div><label>${esc(tr("rec.quote"))}</label>
              <input type="text" id="zitat"></div>
          </div>
          <div class="aktionen">
            <button class="knopf" onclick="aussageSpeichern()">${esc(tr("rec.save"))}</button>
            <button class="knopf leise" onclick="ERF.beleg=null;ansichtErfassen()">
              ${esc(tr("rec.other_source"))}</button>
          </div>`
        : `<p class="leer">${esc(tr("rec.pick_first"))}</p>`}
      </div>
      ${ERF.letzte.length?`<div class="karte"><h2>${esc(tr("rec.recent"))}</h2>
        ${ERF.letzte.map(f=>faktKarte(f)).join("")}</div>`:""}
    </div>

    <div class="karte"><h2>${esc(tr("rec.step1"))}</h2>
      <label>${esc(tr("rec.existing"))}</label>
      <select id="belegwahl" onchange="belegWaehlen(this.value)">
        <option value="">— ${esc(tr("rec.new"))} —</option>
        ${d.belege.map(x=>`<option value="${esc(x.doc_id)}"
          ${b&&b.doc_id===x.doc_id?"selected":""}>${esc(x.titel)} · ${esc(x.quelle)}</option>`).join("")}
      </select>
      <div id="neuerBeleg" style="${b?"display:none":""}">
        <div class="reiter" style="margin-top:16px">
          ${[["datei","rec.file"],["notiz","rec.note"],["quelle","rec.source"]].map(([k,t])=>
            `<button aria-selected="${ERF.art===k}"
              onclick="ERF.art='${k}';ansichtErfassen()">${esc(tr(t))}</button>`).join("")}
        </div>
        ${ERF.art==="datei"?`
          <label>${esc(tr("rec.file_pick"))}</label>
          <input type="file" id="datei" onchange="dateiGewaehlt()">
          <div class="meta" id="hashanzeige">${esc(tr("rec.file_hint"))}</div>
          <label style="display:flex;gap:8px;align-items:flex-start;
                        text-transform:none;letter-spacing:0;font-size:12.5px">
            <input type="checkbox" id="ablegen" style="width:auto;margin-top:2px"
              ${ERF.ablegen!==false?"checked":""} onchange="ERF.ablegen=this.checked;ansichtErfassen()">
            <span>${esc(tr("rec.keep"))}</span>
          </label>
          <div class="hinweis">${esc(ERF.ablegen!==false?tr("rec.keep_hint"):tr("rec.ref_hint"))}</div>
          ${ERF.ablegen===false?`
            <label>${esc(tr("rec.location"))}</label>
            <input type="text" id="ablageort" placeholder="D:\\Akten\\Leak-2026">`:""}
        `:""}
        ${ERF.art==="notiz"?`
          <label>${esc(tr("rec.note_text"))}</label>
          <textarea id="notiz" rows="5"
            placeholder="${esc(tr("rec.note_ph"))}"></textarea>
        `:""}
        <label>${esc(tr("rec.doc_title"))}</label>
        <input type="text" id="btitel">
        <label>${esc(tr("rec.doc_source"))}</label>
        <input type="text" id="bquelle" placeholder="${esc(tr("rec.source_ph"))}">
        <label>${esc(tr("im.level"))}</label>
        <select id="bstufe">
          <option>OEFFENTLICH</option><option selected>INTERN</option>
          <option>VERTRAULICH</option><option>WHISTLEBLOWER</option></select>
        <div class="aktionen">
          <button class="knopf" onclick="belegSpeichern()">${esc(tr("rec.create"))}</button>
        </div>
        <div class="hinweis">${esc(tr("rec.privacy"))}</div>
      </div>
    </div>
  </div>`;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
  window._belege = d.belege;
}

async function dateiGewaehlt(){
  const f = $("#datei").files[0];
  const z = $("#hashanzeige");
  if(!f){ z.textContent = tr("rec.file_hint"); ERF.sha=null; return; }
  z.textContent = tr("rec.hashing");
  const puffer = await f.arrayBuffer();
  const roh = await crypto.subtle.digest("SHA-256", puffer);
  ERF.sha = Array.from(new Uint8Array(roh))
    .map(b=>b.toString(16).padStart(2,"0")).join("");
  ERF.datei = f;
  z.textContent = `${f.name} · ${(f.size/1024).toFixed(0)} KB · sha256 ${ERF.sha.slice(0,20)}…`;
  if(!$("#btitel").value) $("#btitel").value = f.name;
}

function _b64(puffer){
  const bytes = new Uint8Array(puffer);
  let s = "", n = 0x8000;
  for(let i=0;i<bytes.length;i+=n)
    s += String.fromCharCode.apply(null, bytes.subarray(i,i+n));
  return btoa(s);
}

async function belegSpeichern(){
  const daten = {art:ERF.art, titel:$("#btitel").value.trim(),
    quelle:$("#bquelle").value.trim(), stufe:$("#bstufe").value};
  if(!daten.titel||!daten.quelle) return ansichtErfassen(tr("rec.need_title"));
  if(ERF.art==="datei"){
    if(!ERF.sha||!ERF.datei) return ansichtErfassen(tr("rec.need_file"));
    if(ERF.ablegen!==false){
      // Datei mitspeichern: geht ueber 127.0.0.1, verlaesst den Rechner nicht.
      const knopf = document.querySelector("#neuerBeleg .knopf");
      if(knopf){ knopf.disabled=true; knopf.textContent=tr("rec.uploading"); }
      try{
        daten.inhalt_b64 = _b64(await ERF.datei.arrayBuffer());
        daten.dateiname = ERF.datei.name;
        daten.typ = ERF.datei.type || "application/octet-stream";
        ERF.beleg = await api("/api/beleg_datei", daten);
        ERF.sha=null; ERF.datei=null; return ansichtErfassen();
      }catch(e){ return ansichtErfassen(fehlerText(e)); }
    }
    daten.sha256=ERF.sha;
    const ao=$("#ablageort"); daten.ablageort = ao?ao.value.trim():"";
  }
  if(ERF.art==="notiz"){
    daten.notiz=$("#notiz").value.trim();
    if(!daten.notiz) return ansichtErfassen(tr("rec.need_note"));
  }
  try{
    ERF.beleg = await api("/api/beleg_neu", daten);
    ERF.sha=null; ansichtErfassen();
  }catch(e){ ansichtErfassen(fehlerText(e)); }
}

function belegWaehlen(id){
  if(!id){ ERF.beleg=null; return ansichtErfassen(); }
  ERF.beleg = (window._belege||[]).find(x=>x.doc_id===id) || null;
  ansichtErfassen();
}

async function aussageSpeichern(){
  const daten = {doc_id:ERF.beleg.doc_id, subjekt:$("#subj").value.trim(),
    praedikat:$("#prd").value, objekt:$("#obj").value.trim(),
    fundstelle:$("#fund").value.trim(), zitat:$("#zitat").value.trim()};
  if(!daten.subjekt||!daten.objekt) return ansichtErfassen(tr("rec.need_both"));
  try{
    const f = await api("/api/aussage_neu", daten);
    ERF.letzte.unshift({...f, aussagen:1, widersprueche:[]});
    ERF.letzte = ERF.letzte.slice(0,8);
    await ladeState(); ansichtErfassen();
  }catch(e){ ansichtErfassen(fehlerText(e)); }
}

function fehlerText(e){
  try{ return JSON.parse(String(e).replace(/^Error: /,"")).fehler||String(e); }
  catch(_){ return String(e); }
}

async function ansichtExtern(){
  const d=await api("/api/extern");
  const zf={OK:"var(--bestaetigt)",ALT:"var(--einfach)",
            VERALTET:"var(--umstritten)",FEHLER:"var(--umstritten)",
            NIE:"var(--gedaempft)"};
  $("#main").innerHTML=`<h1 data-t="ex.title"></h1>
  <p class="lead">${esc(tr("ex.lead"))}</p>
  <div class="karte"><h2>${esc(tr("ex.health"))}</h2>
    ${d.quellen.length?d.quellen.map(q=>`
      <div class="beleg"><div class="kopf">
        <span class="titel">${esc(q.name)}</span>
        <span class="stufe" style="color:${zf[q.zustand]};border-color:${zf[q.zustand]}">
          ${esc(q.zustand)}</span></div>
        <div class="meta">${esc(q.datensaetze)} ${esc(tr("ex.records"))} ·
          ${q.alter_tage!=null?esc(q.alter_tage)+" "+esc(tr("ex.days")):esc(tr("ex.never"))} ·
          ${q.lokal?esc(tr("ex.local")):esc(tr("ex.remote"))} · ${esc(q.lizenz||"—")}</div>
        ${q.fehler?`<div class="achtung">${esc(q.fehler)}</div>`:""}
      </div>`).join(""):`<p class="leer">${esc(tr("ex.nosources"))}</p>`}
  </div>
  <div class="karte"><h2>${esc(tr("ex.findings"))}</h2>
    ${d.treffer.length?d.treffer.map(t=>`
      <div class="fakt ${t.art==="sanktion"?"UMSTRITTEN":"EINFACH_BELEGT"}">
        <div class="tripel"><span class="ent">${esc(t.entitaet)}</span>
          <span class="prd">←</span> <span class="ent">${esc(t.fremd_name)}</span></div>
        <div class="zeile2"><span class="marke-lage">${esc(t.quelle)}</span>
          <span>${esc(t.merkmale.join(", "))}</span>
          ${t.zusatz&&t.zusatz.titel?`<span>${esc(t.zusatz.titel)}</span>`:""}</div>
      </div>`).join(""):`<p class="leer">${esc(tr("ex.nofindings"))}</p>`}
    <div class="hinweis">${esc(tr("ex.note"))}</div>
  </div>`;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
}

function ansichtImport(){
  const r=window._import;
  return `<h1 data-t="im.title"></h1><p class="lead">${esc(tr("im.lead"))}</p>
  <div class="karte" style="max-width:760px">
    <label>${esc(tr("im.csv"))}</label>
    <textarea id="csv" rows="7" placeholder="firma,sitz,eigentuemer&#10;Mare Liberum Ltd.,Panama,Svensson Family Trust"></textarea>
    <label>${esc(tr("im.mapping"))}</label>
    <textarea id="map" rows="3" placeholder="eigentuemer:beneficial_owner_of:firma&#10;firma:registered_in:sitz"></textarea>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div><label>${esc(tr("im.doc_title"))}</label><input type="text" id="dtitel"></div>
      <div><label>${esc(tr("im.doc_source"))}</label><input type="text" id="dquelle"></div>
      <div><label>${esc(tr("im.level"))}</label><select id="dstufe">
        <option>OEFFENTLICH</option><option selected>INTERN</option>
        <option>VERTRAULICH</option><option>WHISTLEBLOWER</option></select></div>
      <div><label>${esc(tr("im.by"))}</label><input type="text" id="dvon"></div>
    </div>
    <div class="aktionen"><button class="knopf" onclick="importiere()">${esc(tr("im.run"))}</button></div>
    ${r?`<div class="hinweis"><b>${esc(tr("im.done"))}:</b> ${esc(r.zeilen)} → ${esc(r.aussagen)} ${esc(tr("gen.assertions"))}
      ${r.fehler.length?`<div class="achtung">${r.fehler.map(esc).join("<br>")}</div>`:""}</div>`:""}
  </div>`;
}
async function importiere(){
  const daten={csv:$("#csv").value,map:$("#map").value,
    titel:$("#dtitel").value||"Import",quelle:$("#dquelle").value||"unbenannt",
    stufe:$("#dstufe").value,von:$("#dvon").value||"unbekannt"};
  try{ window._import=await api("/api/import",daten); }
  catch(e){ window._import={zeilen:0,aussagen:0,fehler:[String(e)]}; }
  await ladeState(); zeichne();
}

async function ladeState(){
  STATE=await api("/api/state");
  ROLLE=STATE.rolle||"GAST";
  try{ SITZUNG=(await api("/api/sitzung")).sitzung; }catch(e){ SITZUNG=null; }
  try{ SICHERUNG=await api("/api/sicherungsstand"); }catch(e){ SICHERUNG=null; }
}
(async()=>{ await ladeState(); await setzeSprache("de"); })();
</script></body></html>"""


# ================================================================ Server
class Handler(BaseHTTPRequestHandler):
    pod = None
    server_version = "IndraNet"

    def log_message(self, *a):        # kein Zugriffsprotokoll ins Terminal
        pass

    # ------------------------------------------------------------ Helfer
    # -------------------------------------------------------- Sitzung
    def _token(self) -> str | None:
        roh = self.headers.get("Cookie") or ""
        for teil in roh.split(";"):
            k, _, v = teil.strip().partition("=")
            if k == "indranet_sitzung":
                return v
        return None

    def _benutzer(self) -> str:
        s = self.pod.konten.sitzung(self._token())
        return s.benutzer if s else "einzelplatz"

    def _rolle(self) -> Rolle:
        """Rolle aus der Sitzung. Ein Pod ohne Konten laeuft als
        Einzelplatz mit ADMIN; sobald ein Konto besteht, gilt
        Anmeldepflicht."""
        if self.pod.offen:
            return Rolle.ADMIN
        return self.pod.rolle(self._token())

    def _braucht(self, mindest: Rolle) -> bool:
        return self._rolle() >= mindest

    def _json(self, obj, code: int = 200) -> None:
        roh = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(roh)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    @staticmethod
    def _fakt(f) -> dict:
        return {"fact_id": f.fact_id, "subjekt": f.subjekt,
                "praedikat": f.praedikat, "objekt": f.objekt,
                "beleglage": f.beleglage.value, "quellen": f.quellen,
                "aussagen": f.aussagen, "widersprueche": f.widersprueche}

    # --------------------------------------------------------------- GET
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = self.pod
        try:
            if u.path in ("/", "/index.html"):
                roh = SEITE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)

            elif u.path == "/api/sprache":
                lang = (q.get("lang") or ["de"])[0]
                self._json({"texte": i18n.als_dict(lang),
                            "praedikate": i18n.praedikate(lang),
                            "themen": theming.liste(lang)})

            elif u.path == "/api/state":
                self._json({"stats": p.stats(), "pod": p.name,
                            "pod_id": p.pod_id, "rolle": self._rolle().name,
                            "anmeldepflicht": not p.offen})

            elif u.path == "/api/belege":
                self._json(p.belege(q["fact_id"][0], self._rolle()))

            elif u.path == "/api/kette":
                self._json(p.beweiskette(q["fact_id"][0], self._rolle()))

            elif u.path == "/api/sitzung":
                s = p.konten.sitzung(self._token())
                self._json({"angemeldet": s is not None,
                            "anmeldepflicht": not p.offen,
                            "sitzung": s.als_dict() if s else None,
                            "rolle": self._rolle().name})

            elif u.path == "/api/prueflisten":
                listen = p.verifikation.prueflisten()
                self._json({**{k: [self._fakt(f) for f in v]
                               for k, v in listen.items()},
                            "uebersicht": p.verifikation.uebersicht()})

            elif u.path == "/api/vorschlaege":
                self._json({"vorschlaege": [
                    {"a": v.a, "b": v.b, "key_a": v.key_a, "key_b": v.key_b,
                     "score": v.score, "warnung": v.warnung}
                    for v in p.vorschlaege()]})

            elif u.path == "/api/extern":
                from sources import Quelle
                treffer = []
                for name, q in p.externe.items():
                    try:
                        for t in q.abgleichen(p):
                            treffer.append({
                                "entitaet": t.entitaet, "quelle": t.quelle,
                                "fremd_name": t.fremd_name, "art": t.art,
                                "merkmale": t.merkmale, "score": t.score,
                                "zusatz": t.zusatz})
                    except Exception:                          # noqa: BLE001
                        pass
                self._json({"quellen": Quelle.gesundheit(p.store),
                            "treffer": treffer[:100]})

            elif u.path == "/api/beleg_datei":
                import tempfile as _t
                doc_id = q["doc_id"][0]
                angaben = p.beleg_angaben(doc_id)
                if angaben is None:
                    self._json({"fehler": "kein abgelegtes Dokument"}, 404)
                    return
                ordner = _t.mkdtemp(prefix="indranet-")
                try:
                    r = p.beleg_oeffnen(doc_id, self._rolle(),
                                        Path(ordner) / angaben["dateiname"])
                except PermissionError as e:
                    self._json({"fehler": str(e)}, 403)
                    return
                roh = Path(r["datei"]).read_bytes()
                Path(r["datei"]).unlink(missing_ok=True)
                Path(ordner).rmdir()
                self.send_response(200)
                self.send_header("Content-Type",
                                 angaben.get("typ") or "application/octet-stream")
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="{angaben["dateiname"]}"')
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)

            elif u.path == "/api/kette_export":
                text = p.kette_exportieren(q["fact_id"][0], self._rolle(),
                                           (q.get("lang") or ["de"])[0])
                roh = text.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="beweiskette-'
                    f'{q["fact_id"][0].replace(":", "")[:16]}.md"')
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)

            elif u.path == "/api/sicherungsstand":
                self._json(p.sicherungsstand())

            elif u.path == "/api/korrekturen":
                self._json({"korrekturen": p.korrekturen(30)})

            elif u.path == "/api/beleg_text":
                doc_id = q["doc_id"][0]
                try:
                    e = p.beleg_text(doc_id, self._rolle())
                except PermissionError as fehler:
                    self._json({"fehler": str(fehler)}, 403)
                    return
                begriff = (q.get("q") or [""])[0].strip()
                self._json({
                    **e.als_dict(),
                    "treffer": e.suchen(begriff)[:40] if begriff else [],
                    "vorschau": [{"fundstelle": a.fundstelle,
                                  "text": a.kurz(220), "art": a.art}
                                 for a in e.abschnitte[:25]]})

            elif u.path == "/api/belege_liste":
                self._json({"belege": [
                    {"doc_id": z["doc_id"], "titel": z["titel"],
                     "quelle": z["quelle"], "stufe": Stufe(z["stufe"]).name,
                     "widerrufen": bool(z["widerrufen"])}
                    for z in p.store.db.execute(
                        "SELECT * FROM dokument WHERE widerrufen=0 "
                        "ORDER BY ts DESC LIMIT 40")],
                    "praedikate": sorted(
                        __import__("resolver").INVERSE)})

            elif u.path == "/api/dokumente":
                raus = []
                for z in p.store.db.execute(
                        "SELECT d.*, (SELECT COUNT(*) FROM aussage a "
                        "WHERE a.doc_id=d.doc_id) AS aussagen FROM dokument d"):
                    h = p.verifikation.haengt_an(z["doc_id"])
                    raus.append({"doc_id": z["doc_id"], "titel": z["titel"],
                                 "quelle": z["quelle"],
                                 "stufe": Stufe(z["stufe"]).name,
                                 "sha256": z["sha256"], "aussagen": z["aussagen"],
                                 "widerrufen": bool(z["widerrufen"]),
                                 "widerruf_grund": z["widerruf_grund"],
                                 "betroffen": len(h["betroffen"]),
                                 "faellt_ersatzlos": len(h["faellt_ersatzlos"])})
                self._json({"dokumente": raus})
            else:
                self._json({"fehler": "unbekannter Pfad"}, 404)
        except Exception as e:                                # noqa: BLE001
            self._json({"fehler": str(e)}, 400)

    # -------------------------------------------------------------- POST
    def do_POST(self):
        u = urlparse(self.path)
        p = self.pod
        try:
            d = self._body()

            if u.path == "/api/anmelden":
                try:
                    s = p.anmelden(d["benutzer"], d["passwort"], herkunft="webui")
                except Exception as e:                         # noqa: BLE001
                    self._json({"fehler": str(e)}, 401)
                    return
                roh = json.dumps({"ok": True, "sitzung": s.als_dict()},
                                 ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type",
                                 "application/json; charset=utf-8")
                self.send_header(
                    "Set-Cookie",
                    f"indranet_sitzung={s.token}; Path=/; HttpOnly; "
                    f"SameSite=Strict; Max-Age=28800")
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)
                return

            if u.path == "/api/abmelden":
                if self._token():
                    p.konten.abmelden(self._token())
                self._json({"ok": True})
                return

            # Schreibende Vorgaenge verlangen mindestens JOURNALIST.
            schreibend = {"/api/entscheiden", "/api/pruefen",
                          "/api/widerrufen", "/api/import",
                          "/api/beleg_neu", "/api/beleg_datei",
                          "/api/aussage_neu", "/api/aussage_aendern",
                          "/api/aussage_verwerfen", "/api/aussage_widerrufen",
                          "/api/sichern"}
            if u.path in schreibend and not self._braucht(Rolle.JOURNALIST):
                self._json({"fehler": "nicht angemeldet oder Rolle "
                                      "unzureichend"}, 403)
                return
            if u.path == "/api/widerrufen" and not self._braucht(Rolle.LEITUNG):
                self._json({"fehler": "Widerruf verlangt mindestens "
                                      "LEITUNG"}, 403)
                return

            if u.path == "/api/frage":
                a = p.frage(d["frage"])
                self._json({"status": a["status"], "antwort": a["antwort"],
                            "warnungen": a["warnungen"],
                            "fakten": [self._fakt(f) for f in a["fakten"]]})

            elif u.path == "/api/netz":
                import graph as _g
                netz = _g.umfeld(p.store, d["entitaet"], int(d.get("tiefe", 2)))
                # Beleglage je Kante, damit die Darstellung sie faerben kann
                kanten = []
                for k in netz["kanten"]:
                    cid_v = p.store._cid(p.store.resolver.key(k["von"]))
                    cid_n = p.store._cid(p.store.resolver.key(k["nach"]))
                    fid = p.store.fact_id(cid_v, k["praedikat"], cid_n)
                    f = p.store.fakt(fid)
                    kanten.append({**k, "fact_id": fid,
                                   "beleglage": f.beleglage.value if f else "?",
                                   "quellen": len(f.quellen) if f else 0})
                grade = {}
                for k in kanten:
                    grade[k["von"]] = grade.get(k["von"], 0) + 1
                    grade[k["nach"]] = grade.get(k["nach"], 0) + 1
                self._json({
                    "knoten": [{**n, "grad": grade.get(n["anzeige"], 0)}
                               for n in netz["knoten"]],
                    "kanten": kanten, "start": d["entitaet"]})

            elif u.path == "/api/pfad":
                gefunden = p.verbindungen(d["von"], d["nach"],
                                          int(d.get("schritte", 4)))
                raus = []
                for pf in gefunden:
                    teile = [f'<span class="ent">{pf.schritte[0].von}</span>']
                    for s in pf.schritte:
                        pfeil = "←" if s.rueckwaerts else "→"
                        teile.append(f'<span class="prd">{pfeil} {s.praedikat} {pfeil}</span>')
                        teile.append(f'<span class="ent">{s.nach}</span>')
                    raus.append({"html": " ".join(teile),
                                 "schwaechstes": pf.schwaechstes_glied,
                                 "laenge": pf.laenge})
                self._json({"pfade": raus})

            elif u.path == "/api/entscheiden":
                pruefer = (p.konten.sitzung(self._token()) or None)
                pruefer = pruefer.benutzer if pruefer else "einzelplatz"
                if d["art"] == "merge":
                    p.verschmelzen(d["key_a"], d["key_b"], pruefer=pruefer,
                                   begruendung=d["begruendung"])
                else:
                    p.trennen(d["key_a"], d["key_b"], pruefer=pruefer,
                              begruendung=d["begruendung"])
                self._json({"ok": True})

            elif u.path == "/api/pruefen":
                s_ = p.konten.sitzung(self._token())
                p.verifikation.pruefen(
                    d["fact_id"], d["ergebnis"],
                    pruefer=s_.benutzer if s_ else "einzelplatz",
                    notiz=d.get("notiz", ""))
                self._json({"ok": True})

            elif u.path == "/api/widerrufen":
                self._json(p.store.dokument_widerrufen(d["doc_id"], d["grund"]))

            elif u.path == "/api/beleg_datei":
                # Die Datei kommt ueber 127.0.0.1 — sie verlaesst den
                # Rechner nicht. Der Server verschluesselt sie sofort und
                # legt sie im Ablageordner ab.
                import base64
                roh = base64.b64decode(d["inhalt_b64"])
                if len(roh) > 300 * 1024 * 1024:
                    raise ValueError("Datei größer als 300 MB — bitte über "
                                     "die Kommandozeile ablegen")
                self._json(p.dokument_anlegen(
                    art="datei", datei=roh, titel=d["titel"],
                    quelle=d["quelle"], stufe=Stufe[d["stufe"]],
                    erfasst_von=self._benutzer(),
                    dateiname=d.get("dateiname", ""), typ=d.get("typ", "")))

            elif u.path == "/api/beleg_neu":
                self._json(p.dokument_anlegen(
                    art=d.get("art", "quelle"), titel=d["titel"],
                    quelle=d["quelle"], stufe=Stufe[d["stufe"]],
                    erfasst_von=self._benutzer(),
                    sha256=d.get("sha256"), ablageort=d.get("ablageort", ""),
                    notiz=d.get("notiz", "")))

            elif u.path == "/api/aussage_neu":
                self._json(p.aussage_erfassen(
                    d["doc_id"], d["subjekt"], d["praedikat"], d["objekt"],
                    fundstelle=d.get("fundstelle", ""),
                    zitat=d.get("zitat", ""), erfasst_von=self._benutzer()))

            elif u.path == "/api/aussage_aendern":
                self._json(p.aussage_aendern(
                    d["aussage_id"], subjekt=d.get("subjekt"),
                    praedikat=d.get("praedikat"), objekt=d.get("objekt"),
                    fundstelle=d.get("fundstelle"), zitat=d.get("zitat"),
                    grund=d["begruendung"], pruefer=self._benutzer()))

            elif u.path == "/api/aussage_verwerfen":
                self._json(p.aussage_verwerfen(
                    d["aussage_id"], d["begruendung"], self._benutzer()))

            elif u.path == "/api/aussage_widerrufen":
                self._json(p.aussage_widerrufen(
                    d["aussage_id"], d["begruendung"], self._benutzer()))

            elif u.path == "/api/sichern":
                self._json(p.sicherung())

            elif u.path == "/api/import":
                import csv as _csv
                import io
                zuordnungen = [Zuordnung.aus_text(z.strip())
                               for z in d["map"].splitlines() if z.strip()]
                if not zuordnungen:
                    raise ValueError("keine Zuordnung angegeben")
                zeilen = list(_csv.DictReader(io.StringIO(d["csv"])))
                tripel = []
                for z in zeilen:
                    for zu in zuordnungen:
                        if zu.gilt(z):
                            tripel.append((zu.subjekt(z), zu.praedikat,
                                           zu.objekt(z)))
                b = importiere_tripel(p, tripel, titel=d["titel"],
                                      quelle=d["quelle"],
                                      stufe=Stufe[d["stufe"]],
                                      erfasst_von=d["von"])
                b.zeilen = len(zeilen)
                self._json(b.als_dict())
            else:
                self._json({"fehler": "unbekannter Pfad"}, 404)
        except Exception as e:                                # noqa: BLE001
            self._json({"fehler": str(e)}, 400)


SEITE = SEITE.replace("__THEMEN__", theming.alle_css())


def starte(pod, host: str = "127.0.0.1", port: int = 8710,
           oeffnen: bool = False) -> ThreadingHTTPServer:
    """Startet die Oberfläche. Bindet bewusst nur an localhost."""
    Handler.pod = pod
    srv = ThreadingHTTPServer((host, port), Handler)
    if oeffnen:
        threading.Timer(0.6, lambda: webbrowser.open(
            f"http://{host}:{port}/")).start()
    return srv
