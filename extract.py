"""
IndraNet — Textextraktion
==========================

Ablegen konnte IndraNet immer schon jedes Format: `docstore.py` ist
byteweise blind. Was hier dazukommt, ist das Lesen — Text herausholen und
daraus Fundstellen bilden.

WARUM FUNDSTELLEN UND NICHT NUR TEXT
------------------------------------
Ein Textklumpen ohne Position ist für die Belegkette wertlos. „S. 14,
Zeile 7" ist ein Beleg, „irgendwo im PDF" ist keiner. Jeder Abschnitt trägt
deshalb eine Fundstelle, die man später wiederfindet:

    PDF            S. 14
    Tabelle        Blatt "Beteiligungen", Zeile 42
    Text/Word      Absatz 17
    E-Mail         Betreff/Text, Nachricht 3
    Präsentation   Folie 8

FAST ALLES OHNE FREMDBIBLIOTHEKEN
---------------------------------
docx, xlsx, pptx, odt, ods und odp sind ZIP-Archive mit XML darin —
`zipfile` und `xml.etree` aus der Standardbibliothek genügen. E-Mail-Formate
deckt `email` ab. Nur PDF braucht `pypdf`, und auch das ist optional: Fehlt
es, meldet die Extraktion das ehrlich, statt zu scheitern.

Bewusst KEINE Abhängigkeit von python-docx, openpyxl oder odfpy. Jede
zusätzliche Bibliothek vergrößert die Windows-Anwendung und die
Angriffsfläche — für ein paar Dutzend Zeilen XML-Auswertung lohnt das nicht.

WAS NICHT GEHT
--------------
Alte Binärformate (.doc, .xls vor 2007) sind OLE-Container und brauchen
LibreOffice oder antiword. Gescannte Seiten ohne Textebene brauchen OCR.
Beides wird gemeldet, nicht stillschweigend als leeres Dokument
durchgereicht — ein leeres Ergebnis, das wie ein Erfolg aussieht, ist
schlimmer als eine Fehlermeldung.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------- Formate
TEXTARTIG = {".txt", ".md", ".markdown", ".log", ".rst", ".ini", ".cfg",
             ".yaml", ".yml", ".srt", ".vtt", ".sql", ".py", ".js"}
TABELLE = {".csv", ".tsv"}
OFFICE_ZIP = {".docx": "word", ".xlsx": "excel", ".pptx": "powerpoint",
              ".odt": "odf", ".ods": "odf", ".odp": "odf"}
MAIL = {".eml", ".mbox", ".msg"}
ALT = {".doc", ".xls", ".ppt"}

MAX_ABSCHNITT = 4000          # Zeichen je Abschnitt, damit Auszüge lesbar bleiben


class ExtraktionFehler(Exception):
    pass


@dataclass
class Abschnitt:
    """Ein Textstück mit seiner Fundstelle."""
    text: str
    fundstelle: str
    seite: int | None = None
    art: str = "text"          # text | tabelle | kopf | anhang

    def kurz(self, n: int = 160) -> str:
        t = " ".join(self.text.split())
        return t[:n] + ("…" if len(t) > n else "")


@dataclass
class Extraktion:
    dateiname: str
    format: str
    abschnitte: list = field(default_factory=list)
    seiten: int = 0
    zeichen: int = 0
    hinweis: str = ""
    vollstaendig: bool = True

    @property
    def text(self) -> str:
        return "\n\n".join(a.text for a in self.abschnitte)

    def suchen(self, begriff: str, umfeld: int = 120) -> list[dict]:
        """Findet einen Begriff und liefert Fundstelle plus Umfeld.

        Das ist der eigentliche Zweck: Nicht „das Wort kommt vor", sondern
        „auf Seite 14, in diesem Satz".
        """
        muster = re.compile(re.escape(begriff), re.I)
        treffer = []
        for a in self.abschnitte:
            for m in muster.finditer(a.text):
                von = max(0, m.start() - umfeld)
                bis = min(len(a.text), m.end() + umfeld)
                auszug = " ".join(a.text[von:bis].split())
                treffer.append({
                    "fundstelle": a.fundstelle, "seite": a.seite,
                    "zitat": ("…" if von else "") + auszug
                             + ("…" if bis < len(a.text) else ""),
                    "position": m.start(), "art": a.art})
        return treffer

    def als_dict(self) -> dict:
        return {"dateiname": self.dateiname, "format": self.format,
                "seiten": self.seiten, "zeichen": self.zeichen,
                "abschnitte": len(self.abschnitte), "hinweis": self.hinweis,
                "vollstaendig": self.vollstaendig}


# ------------------------------------------------------------ Einstiegspunkt
def extrahieren(daten: bytes | str | Path, dateiname: str = "",
                grenze_zeichen: int = 8_000_000) -> Extraktion:
    """Holt Text samt Fundstellen aus einer Datei oder einem Puffer."""
    if isinstance(daten, (str, Path)):
        pfad = Path(daten)
        dateiname = dateiname or pfad.name
        roh = pfad.read_bytes()
    else:
        roh = bytes(daten)
    endung = Path(dateiname).suffix.lower()

    if endung in ALT:
        return Extraktion(dateiname, endung.lstrip("."), vollstaendig=False,
                          hinweis="Altes Binärformat vor Office 2007. Bitte "
                                  "in .docx/.xlsx umwandeln — etwa mit "
                                  "LibreOffice — und erneut ablegen.")

    try:
        if endung == ".pdf" or roh[:5] == b"%PDF-":
            e = _pdf(roh, dateiname)
        elif endung in OFFICE_ZIP or (roh[:2] == b"PK" and endung != ".zip"):
            e = _office(roh, dateiname, endung)
        elif endung in MAIL:
            e = _mail(roh, dateiname, endung)
        elif endung in TABELLE:
            e = _tabelle_text(roh, dateiname, endung)
        elif endung in (".json", ".geojson"):
            e = _json(roh, dateiname)
        elif endung in (".html", ".htm", ".xhtml"):
            e = _html(roh, dateiname)
        elif endung == ".xml":
            e = _xml_roh(roh, dateiname)
        elif endung == ".rtf":
            e = _rtf(roh, dateiname)
        elif endung in TEXTARTIG or not endung:
            e = _text(roh, dateiname)
        else:
            e = _versuch_text(roh, dateiname, endung)
    except ExtraktionFehler:
        raise
    except Exception as fehler:                                # noqa: BLE001
        raise ExtraktionFehler(
            f"{dateiname}: {type(fehler).__name__}: {fehler}")

    e.zeichen = sum(len(a.text) for a in e.abschnitte)
    if e.zeichen > grenze_zeichen:
        e.hinweis = (e.hinweis + " " if e.hinweis else "") + \
            f"Nur die ersten {grenze_zeichen:,} Zeichen ausgewertet."
        e.vollstaendig = False
    if e.zeichen == 0 and not e.hinweis:
        e.hinweis = ("Kein Text gefunden. Bei eingescannten Seiten liegt "
                     "keine Textebene vor — dafür wäre eine "
                     "Texterkennung (OCR) nötig.")
        e.vollstaendig = False
    return e


# ------------------------------------------------------------------- PDF
def _pdf(roh: bytes, name: str) -> Extraktion:
    try:
        from pypdf import PdfReader
    except ImportError:
        return Extraktion(name, "pdf", vollstaendig=False,
                          hinweis="Für PDF wird pypdf benötigt: "
                                  "pip install pypdf")
    leser = PdfReader(io.BytesIO(roh))
    e = Extraktion(name, "pdf", seiten=len(leser.pages))
    if getattr(leser, "is_encrypted", False):
        try:
            leser.decrypt("")
        except Exception:                                      # noqa: BLE001
            return Extraktion(name, "pdf", vollstaendig=False,
                              hinweis="PDF ist kennwortgeschützt.")
    for nr, seite in enumerate(leser.pages, start=1):
        try:
            text = seite.extract_text() or ""
        except Exception:                                      # noqa: BLE001
            text = ""
        if text.strip():
            e.abschnitte.append(Abschnitt(text.strip(), f"S. {nr}", nr))
    if not e.abschnitte and e.seiten:
        e.vollstaendig = False
        e.hinweis = (f"{e.seiten} Seiten ohne Textebene — vermutlich ein "
                     "Scan. Dafür wäre eine Texterkennung (OCR) nötig.")
    return e


# ------------------------------------------- Office (ZIP + XML, stdlib)
def _txt(knoten) -> str:
    return "".join(knoten.itertext())


def _office(roh: bytes, name: str, endung: str) -> Extraktion:
    z = zipfile.ZipFile(io.BytesIO(roh))
    namen = set(z.namelist())
    if "word/document.xml" in namen:
        return _docx(z, name)
    if "xl/workbook.xml" in namen:
        return _xlsx(z, name)
    if any(n.startswith("ppt/slides/slide") for n in namen):
        return _pptx(z, name)
    if "content.xml" in namen:
        return _odf(z, name, endung)
    raise ExtraktionFehler(f"{name}: unbekanntes ZIP-Format")


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(z: zipfile.ZipFile, name: str) -> Extraktion:
    e = Extraktion(name, "docx")
    baum = ET.fromstring(z.read("word/document.xml"))
    nr = 0
    for absatz in baum.iter(f"{_W}p"):
        text = "".join(t.text or "" for t in absatz.iter(f"{_W}t")).strip()
        nr += 1
        if text:
            e.abschnitte.append(Abschnitt(text, f"Absatz {nr}", art="text"))
    # Tabellen stehen im selben Dokument; sie wurden oben mitgelesen, aber
    # zeilenweise ist fuer eine Fundstelle brauchbarer.
    for i, tab in enumerate(baum.iter(f"{_W}tbl"), start=1):
        for j, zeile in enumerate(tab.iter(f"{_W}tr"), start=1):
            zellen = [_txt(c).strip() for c in zeile.iter(f"{_W}tc")]
            if any(zellen):
                e.abschnitte.append(Abschnitt(
                    " | ".join(zellen), f"Tabelle {i}, Zeile {j}",
                    art="tabelle"))
    for anhang in ("word/footnotes.xml", "word/endnotes.xml",
                   "word/comments.xml"):
        if anhang in z.namelist():
            t = _txt(ET.fromstring(z.read(anhang))).strip()
            if t:
                e.abschnitte.append(Abschnitt(
                    t, Path(anhang).stem.capitalize(), art="anhang"))
    return e


_X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _xlsx(z: zipfile.ZipFile, name: str) -> Extraktion:
    e = Extraktion(name, "xlsx")
    # Gemeinsame Zeichenkettentabelle
    texte = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{_X}si"):
            texte.append("".join(t.text or "" for t in si.iter(f"{_X}t")))

    blaetter = {}
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {}
    if "xl/_rels/workbook.xml.rels" in z.namelist():
        for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
            rels[r.get("Id")] = r.get("Target")
    for s in wb.iter(f"{_X}sheet"):
        ziel = rels.get(s.get(f"{_R}id"), "")
        blaetter[("xl/" + ziel.lstrip("/")).replace("xl/xl/", "xl/")] = \
            s.get("name") or "Blatt"

    for pfad, blattname in blaetter.items():
        if pfad not in z.namelist():
            continue
        baum = ET.fromstring(z.read(pfad))
        for zeile in baum.iter(f"{_X}row"):
            nr = zeile.get("r") or "?"
            werte = []
            for c in zeile.iter(f"{_X}c"):
                v = c.find(f"{_X}v")
                if v is None or v.text is None:
                    inline = c.find(f"{_X}is")
                    werte.append(_txt(inline).strip() if inline is not None else "")
                    continue
                if c.get("t") == "s":
                    i = int(v.text)
                    werte.append(texte[i] if i < len(texte) else "")
                else:
                    werte.append(v.text)
            if any(w.strip() for w in werte if w):
                e.abschnitte.append(Abschnitt(
                    " | ".join(w for w in werte if w),
                    f'Blatt "{blattname}", Zeile {nr}', art="tabelle"))
    e.seiten = len(blaetter)
    return e


_P = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _pptx(z: zipfile.ZipFile, name: str) -> Extraktion:
    e = Extraktion(name, "pptx")
    folien = sorted(n for n in z.namelist()
                    if re.match(r"ppt/slides/slide\d+\.xml$", n))
    for nr, f in enumerate(folien, start=1):
        baum = ET.fromstring(z.read(f))
        zeilen = [_txt(p).strip() for p in baum.iter(f"{_P}p")]
        text = "\n".join(x for x in zeilen if x)
        if text:
            e.abschnitte.append(Abschnitt(text, f"Folie {nr}", nr))
        notiz = f.replace("slides/slide", "notesSlides/notesSlide")
        if notiz in z.namelist():
            t = _txt(ET.fromstring(z.read(notiz))).strip()
            if t:
                e.abschnitte.append(Abschnitt(
                    t, f"Folie {nr}, Notizen", nr, art="anhang"))
    e.seiten = len(folien)
    return e


_TEXT_NS = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_TAB_NS = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"


def _odf(z: zipfile.ZipFile, name: str, endung: str) -> Extraktion:
    e = Extraktion(name, endung.lstrip(".") or "odf")
    baum = ET.fromstring(z.read("content.xml"))

    tabellen = list(baum.iter(f"{_TAB_NS}table"))
    if tabellen:                                   # ods
        for tab in tabellen:
            blatt = tab.get(f"{_TAB_NS}name") or "Blatt"
            for nr, zeile in enumerate(tab.iter(f"{_TAB_NS}table-row"), 1):
                zellen = [_txt(c).strip()
                          for c in zeile.iter(f"{_TAB_NS}table-cell")]
                if any(zellen):
                    e.abschnitte.append(Abschnitt(
                        " | ".join(x for x in zellen if x),
                        f'Blatt "{blatt}", Zeile {nr}', art="tabelle"))
        e.seiten = len(tabellen)
        return e

    nr = 0                                          # odt / odp
    for p in baum.iter():
        if p.tag not in (f"{_TEXT_NS}p", f"{_TEXT_NS}h"):
            continue
        t = _txt(p).strip()
        nr += 1
        if t:
            e.abschnitte.append(Abschnitt(t, f"Absatz {nr}"))
    return e


# ------------------------------------------------------------------ E-Mail
def _mail(roh: bytes, name: str, endung: str) -> Extraktion:
    import email
    from email import policy

    e = Extraktion(name, endung.lstrip("."))
    if endung == ".msg":
        return Extraktion(name, "msg", vollstaendig=False,
                          hinweis="Outlook-.msg wird nicht gelesen. Bitte "
                                  "als .eml exportieren.")

    if endung == ".mbox":
        rohe = re.split(rb"\r?\nFrom ", roh)
        nachrichten = [r if i == 0 else b"From " + r
                       for i, r in enumerate(rohe) if r.strip()]
    else:
        nachrichten = [roh]

    for nr, m in enumerate(nachrichten, start=1):
        try:
            msg = email.message_from_bytes(m, policy=policy.default)
        except Exception:                                      # noqa: BLE001
            continue
        kopf = " | ".join(
            f"{f}: {msg.get(f)}" for f in ("Date", "From", "To", "Cc",
                                           "Subject") if msg.get(f))
        marke = f"Nachricht {nr}" if len(nachrichten) > 1 else "Kopf"
        if kopf:
            e.abschnitte.append(Abschnitt(kopf, marke, nr, art="kopf"))
        try:
            teil = msg.get_body(preferencelist=("plain", "html"))
            text = teil.get_content() if teil else ""
        except Exception:                                      # noqa: BLE001
            text = ""
        if isinstance(text, str) and text.strip():
            if "<" in text and ">" in text:
                text = _entfaerbe_html(text)
            e.abschnitte.append(Abschnitt(
                text.strip(),
                f"{marke}, Text" if len(nachrichten) > 1 else "Text", nr))
        anhaenge = [t.get_filename() for t in msg.iter_attachments()
                    if t.get_filename()]
        if anhaenge:
            e.abschnitte.append(Abschnitt(
                "Anhänge: " + ", ".join(anhaenge),
                f"{marke}, Anhänge", nr, art="anhang"))
    e.seiten = len(nachrichten)
    return e


# ----------------------------------------------------------- Einfachformate
def _entfaerbe_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    import html as _h
    return re.sub(r"[ \t]{2,}", " ", _h.unescape(text))


def _dekodieren(roh: bytes) -> str:
    for kodierung in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return roh.decode(kodierung)
        except UnicodeDecodeError:
            continue
    return roh.decode("utf-8", errors="replace")


def _absatzweise(text: str, name: str, format: str) -> Extraktion:
    e = Extraktion(name, format)
    puffer, nr, start = [], 0, 1
    for i, zeile in enumerate(text.splitlines(), start=1):
        if zeile.strip():
            if not puffer:
                start = i
            puffer.append(zeile)
        elif puffer:
            nr += 1
            e.abschnitte.append(Abschnitt("\n".join(puffer),
                                          f"Zeile {start}"))
            puffer = []
        if sum(len(x) for x in puffer) > MAX_ABSCHNITT:
            nr += 1
            e.abschnitte.append(Abschnitt("\n".join(puffer), f"Zeile {start}"))
            puffer = []
    if puffer:
        e.abschnitte.append(Abschnitt("\n".join(puffer), f"Zeile {start}"))
    return e


def _text(roh: bytes, name: str) -> Extraktion:
    return _absatzweise(_dekodieren(roh), name,
                        Path(name).suffix.lstrip(".") or "txt")


def _html(roh: bytes, name: str) -> Extraktion:
    return _absatzweise(_entfaerbe_html(_dekodieren(roh)), name, "html")


def _xml_roh(roh: bytes, name: str) -> Extraktion:
    try:
        return _absatzweise(_txt(ET.fromstring(roh)), name, "xml")
    except ET.ParseError:
        return _absatzweise(_entfaerbe_html(_dekodieren(roh)), name, "xml")


def _rtf(roh: bytes, name: str) -> Extraktion:
    """Einfache RTF-Auswertung ohne Fremdbibliothek."""
    t = _dekodieren(roh)
    t = re.sub(r"\\'([0-9a-fA-F]{2})",
               lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r"\\par[d]?\b", "\n", t)
    t = re.sub(r"\{\\\*[^{}]*\}", " ", t)
    t = re.sub(r"\\[a-zA-Z]+-?\d*\s?", " ", t)
    t = t.replace("{", " ").replace("}", " ")
    return _absatzweise(re.sub(r"[ \t]{2,}", " ", t), name, "rtf")


def _tabelle_text(roh: bytes, name: str, endung: str) -> Extraktion:
    e = Extraktion(name, endung.lstrip("."))
    text = _dekodieren(roh)
    trenner = "\t" if endung == ".tsv" else None
    if trenner is None:
        try:
            trenner = csv.Sniffer().sniff(text[:4000]).delimiter
        except csv.Error:
            trenner = ","
    for nr, zeile in enumerate(csv.reader(io.StringIO(text),
                                          delimiter=trenner), start=1):
        if any(z.strip() for z in zeile):
            e.abschnitte.append(Abschnitt(" | ".join(zeile), f"Zeile {nr}",
                                          art="tabelle"))
    return e


def _json(roh: bytes, name: str) -> Extraktion:
    e = Extraktion(name, "json")
    daten = json.loads(_dekodieren(roh))

    def gehe(knoten, pfad="$"):
        if isinstance(knoten, dict):
            for k, v in knoten.items():
                gehe(v, f"{pfad}.{k}")
        elif isinstance(knoten, list):
            for i, v in enumerate(knoten):
                gehe(v, f"{pfad}[{i}]")
        elif knoten not in (None, "", True, False):
            e.abschnitte.append(Abschnitt(str(knoten), pfad))
    gehe(daten)
    return e


def _versuch_text(roh: bytes, name: str, endung: str) -> Extraktion:
    """Unbekanntes Format: als Text versuchen, sonst ehrlich melden."""
    kopf = roh[:2048]
    druckbar = sum(1 for b in kopf if 9 <= b <= 13 or 32 <= b < 127 or b >= 160)
    if kopf and druckbar / len(kopf) > 0.85:
        return _absatzweise(_dekodieren(roh), name,
                            endung.lstrip(".") or "text")
    return Extraktion(name, endung.lstrip(".") or "binär", vollstaendig=False,
                      hinweis=f"Format {endung or 'ohne Endung'} enthält "
                              "keinen auswertbaren Text. Die Datei ist "
                              "trotzdem verschlüsselt abgelegt und kann "
                              "geöffnet werden.")


def unterstuetzte_formate() -> dict:
    return {
        "ohne Zusatzsoftware": sorted(
            list(TEXTARTIG | TABELLE | set(OFFICE_ZIP) | {".eml", ".mbox"}
                 | {".json", ".html", ".htm", ".xml", ".rtf"})),
        "mit pypdf": [".pdf"],
        "nicht lesbar": sorted(ALT | {".msg"}),
        "hinweis": "Alle übrigen Formate werden verschlüsselt abgelegt, aber "
                   "nicht nach Text durchsucht.",
    }
