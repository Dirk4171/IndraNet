"""
IndraNetz — Entity Resolution
==============================

Der Faktenspeicher generalisiert nicht. Zufallsvektoren kennen keine Ähnlichkeit:
"Mare Liberum Ltd." und "Mare Liberum Limited" sind orthogonal, so wie
"Mare Liberum Ltd." und "Panama" orthogonal sind. Ohne diese Schicht
liefert ein Pod massenhaft NO_MATCH auf Fakten, die er tatsächlich enthält.

ZWEI SCHLÜSSEL, NICHT EINER
---------------------------
Ein einziger Normalisierungsschlüssel zwingt zu einer unmöglichen Wahl:

  aggressiv  -> "Müller" und "Muller" kollidieren korrekt,
                aber auch "Goethe" und "Gothe" — eine erfundene Verbindung
  konservativ-> keine Falschverschmelzung,
                aber "Mare Liberum Limited" bleibt unauffindbar

Deshalb:

  strict_key   Konservativ, deterministisch, zustandslos. Erzeugt den
               Speichervektor. Verschmilzt nur, was zweifelsfrei identisch
               ist: Unicode-Form, Groß-/Kleinschreibung, Leerraum,
               Rechtsformschreibweise, Namensreihenfolge.

  block_key    Aggressiv: Diakritika, Digraphen, Rechtsform, Reihenfolge
               werden eingeebnet. Erzeugt NIEMALS einen Vektor. Dient
               ausschließlich dazu, Kandidatenpaare für die menschliche
               Prüfung zu finden.

Damit bleibt der Faktenspeicher exakt, und die Unschärfe lebt vollständig
in einer Vorschlagsliste, die ein Mensch bestätigt. Bestätigte Verbindungen
landen in der Alias-Tabelle und wirken ab dann auf den strikten Schlüssel.

WARUM NICHTS AUTOMATISCH VERSCHMOLZEN WIRD
------------------------------------------
"Anders Holm" aus dem Handelsregister Oslo und "Anders Holm" aus dem Leak
sind womöglich zwei Menschen. Ein Schwellwert, der beide zusammenlegt,
erzeugt eine publizierbare Behauptung, die niemand geprüft hat. Der
Resolver schlägt vor; entschieden wird von Hand, und die Entscheidung geht
mit Begründung ins Audit-Log.

VERSIONIERUNG
-------------
Alle Pods müssen identisch normalisieren, sonst scheitert der föderierte
Abgleich still. `fingerprint()` hasht sämtliche Regeltabellen. Zwei Pods
vergleichen den Fingerabdruck vor dem ersten Abgleich; weicht er ab, wird
die Verbindung abgelehnt statt halb funktionierender Treffer zu liefern.
Eine Regeländerung erzwingt eine Neuindizierung des Speichers.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

RESOLVER_VERSION = "ir-res-1"


# ------------------------------------------------------------------- Typen
class T:
    ORG = "ORG"
    PERSON = "PERSON"
    PLACE = "PLACE"
    VESSEL = "VESSEL"
    REGISTER = "REGISTER"
    ADRESSE = "ADRESSE"
    AMT = "AMT"
    KENNUNG = "KENNUNG"      # Registernummer, Steuernummer, LEI
    BETRAG = "BETRAG"
    DATUM = "DATUM"
    AUTO = "AUTO"        # Rechtsform vorhanden -> ORG, sonst PERSON-Regeln


# Typsignatur je Prädikat. Das geschlossene Prädikatsvokabular liefert die
# Entitätstypen frei Haus — ohne Ratespiel und ohne Modell.
PREDICATE_SCHEMA: dict[str, tuple[str, str]] = {
    # --- Eigentum und Beteiligung ---
    "beneficial_owner_of": (T.AUTO,   T.ORG),
    "holds_shares_in":     (T.AUTO,   T.ORG),
    "controls":            (T.AUTO,   T.ORG),
    "parent_of":           (T.ORG,    T.ORG),

    # --- Ämter und Funktionen ---
    "director_of":         (T.PERSON, T.ORG),
    "employed_by":         (T.PERSON, T.ORG),
    "holds_office":        (T.PERSON, T.AMT),
    "advisor_to":          (T.PERSON, T.AUTO),

    # --- Ort und Identität ---
    "registered_in":       (T.ORG,    T.PLACE),
    "resident_in":         (T.PERSON, T.PLACE),
    "address_of":          (T.AUTO,   T.ADRESSE),
    "identified_by":       (T.AUTO,   T.KENNUNG),
    "national_of":         (T.PERSON, T.PLACE),

    # --- Beziehungen zwischen Personen ---
    "family_of":           (T.PERSON, T.PERSON),
    "associate_of":        (T.PERSON, T.AUTO),

    # --- Geld und Vorgänge ---
    "paid_to":             (T.AUTO,   T.AUTO),
    "contracted_with":     (T.AUTO,   T.AUTO),
    "amount_of":           (T.AUTO,   T.BETRAG),
    "dated":               (T.AUTO,   T.DATUM),

    # --- Sonstiges ---
    "listed_in":           (T.AUTO,   T.REGISTER),
    "operates_vessel":     (T.ORG,    T.VESSEL),
    "sanctioned_by":       (T.AUTO,   T.ORG),
}

# Umkehrprädikate. Machen die Gegenrichtung als Frageform verfügbar;
# im Aussage-Modell ist das eine Indexabfrage, keine zweite Ablage.
INVERSE: dict[str, str] = {
    "beneficial_owner_of": "beneficially_owned_by",
    "holds_shares_in":     "shares_held_by",
    "controls":            "controlled_by",
    "parent_of":           "subsidiary_of",
    "director_of":         "has_director",
    "employed_by":         "employs",
    "holds_office":        "office_held_by",
    "advisor_to":          "advised_by",
    "registered_in":       "registry_of",
    "resident_in":         "residence_of",
    "address_of":          "address_used_by",
    "identified_by":       "identifies",
    "national_of":         "nationals",
    "family_of":           "family_reverse",
    "associate_of":        "associate_reverse",
    "paid_to":             "received_from",
    "contracted_with":     "contract_reverse",
    "amount_of":           "amount_reverse",
    "dated":               "date_of",
    "listed_in":           "lists_entity",
    "operates_vessel":     "operated_by",
    "sanctioned_by":       "sanctions",
}
INVERSE_OF: dict[str, str] = {v: k for k, v in INVERSE.items()}

for _p, (_st, _ot) in list(PREDICATE_SCHEMA.items()):
    PREDICATE_SCHEMA[INVERSE[_p]] = (_ot, _st)


def ist_umkehr(praedikat: str) -> bool:
    return praedikat in INVERSE_OF


# ------------------------------------------------------------- Rechtsformen
# Kanonisches Kürzel -> Schreibweisen. Die Rechtsform wird VEREINHEITLICHT,
# nicht entfernt: "Nordkap Shipping AS" (Norwegen) und "Nordkap Shipping AB"
# (Schweden) sind verschiedene Gesellschaften.
LEGAL_FORMS: dict[str, list[str]] = {
    "LTD":   ["ltd", "limited", "co ltd", "company limited", "coltd"],
    "PLC":   ["plc", "public limited company"],
    "LLC":   ["llc", "limited liability company"],
    "INC":   ["inc", "incorporated"],
    "CORP":  ["corp", "corporation"],
    "LP":    ["lp", "limited partnership"],
    "LLP":   ["llp"],
    "GMBH":  ["gmbh", "gesellschaft mit beschrankter haftung"],
    "UG":    ["ug", "ug haftungsbeschrankt", "unternehmergesellschaft"],
    "AG":    ["ag", "aktiengesellschaft"],
    "KG":    ["kg", "kommanditgesellschaft"],
    "GMBHCOKG": ["gmbh co kg", "gmbh und co kg"],
    "SA":    ["sa", "societe anonyme", "sociedad anonima"],
    "SARL":  ["sarl", "societe a responsabilite limitee"],
    "BV":    ["bv", "besloten vennootschap"],
    "NV":    ["nv", "naamloze vennootschap"],
    "AS":    ["as", "a s", "aksjeselskap", "aktieselskab"],
    "ASA":   ["asa"],
    "AB":    ["ab", "aktiebolag"],
    "OY":    ["oy", "oyj"],
    "APS":   ["aps", "anpartsselskab"],
    "HF":    ["hf"],
    "EHF":   ["ehf"],
    "PTE":   ["pte", "pte ltd"],
    "SDNBHD": ["sdn bhd", "sendirian berhad"],
    "IBC":   ["ibc", "international business company"],
    "SPA":   ["spa", "societa per azioni"],
    "SRL":   ["srl"],
    "SL":    ["sl", "sociedad limitada"],
    "TRUST": ["trust"],
    "FOUNDATION": ["foundation", "stiftung", "fundacion"],
}
def _fold(text: str) -> str:
    """Diakritika entfernen — nur fuer den Rechtsform-Nachschlag, damit
    'beschränkter' und 'beschrankter' dieselbe Tabellenzeile treffen."""
    d = unicodedata.normalize("NFKD", text)
    return "".join(c for c in d if not unicodedata.combining(c))


_FORM_LOOKUP: dict[str, str] = {
    _fold(v): k for k, variants in LEGAL_FORMS.items() for v in variants
}
_MAX_FORM_TOKENS = max(len(v.split()) for v in _FORM_LOOKUP)

# Rauschmarker, die keine Entität bezeichnen.
NOISE_PATTERNS = [
    r"\bin liquidation\b", r"\bi\.?\s?l\.?\b(?=\s*$)", r"\bin liq\b",
    r"\bformerly known as\b", r"\bf\.?k\.?a\.?\b", r"\bc/o\b",
    r"\bdormant\b", r"\bstruck off\b",
    # Juristische Pflichtangabe der deutschen UG — trägt keine Unterscheidung.
    r"\bhaftungsbeschr(ä|a)nkt\b",
]

# Titel und Namenszusätze bei Personen.
TITLES = {"dr", "prof", "mr", "mrs", "ms", "sir", "lord", "lady", "herr",
          "frau", "ing", "mag", "dipl", "med", "phd", "hon"}

# Kyrillisch -> Latein, konservative Umschrift.
CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s&]", re.UNICODE)
_PAREN = re.compile(r"\s*\([^)]*\)")


# ------------------------------------------------------------- Grundschritte
def _translit(text: str) -> str:
    return "".join(CYRILLIC.get(c, CYRILLIC.get(c.lower(), c).upper()
                                if c.isupper() and c.lower() in CYRILLIC else c)
                   for c in text)


def _basis(raw: str) -> str:
    """Gemeinsame Vorstufe beider Schlüssel."""
    s = unicodedata.normalize("NFKC", raw)
    s = _translit(s).casefold()
    for pat in NOISE_PATTERNS:
        s = re.sub(pat, " ", s)
    return _WS.sub(" ", s).strip(" .,;:!?\"'-")


def _split_legal_form(tokens: list[str]) -> tuple[list[str], str | None]:
    """Trennt eine am Ende stehende Rechtsform ab. Längster Treffer gewinnt."""
    for n in range(min(_MAX_FORM_TOKENS, len(tokens) - 1), 0, -1):
        kandidat = _fold(" ".join(tokens[-n:]))
        form = _FORM_LOOKUP.get(kandidat)
        if form:
            return tokens[:-n], form
    return tokens, None


def _person_order(tokens: list[str]) -> list[str]:
    """'holm, anders' -> ['anders', 'holm']; Titel entfallen."""
    tokens = [t for t in tokens if t not in TITLES]
    return tokens


# ------------------------------------------------------------ Strikter Weg
def strict_key(raw: str, etype: str = T.AUTO) -> str:
    """Konservativer Schlüssel. Erzeugt den Speichervektor.

    Verschmilzt ausschließlich Schreibweisen derselben Zeichenfolge, keine
    inhaltlichen Urteile. Diakritika bleiben erhalten (nach NFKC), Vornamen
    bleiben erhalten, Klammerzusätze bleiben erhalten.
    """
    s = _basis(raw)
    hat_komma = "," in s
    # Klammerzusätze abtrennen, damit "Mare Liberum Ltd (BVI)" die Rechtsform
    # sauber kanonisiert und den Zusatz trotzdem unterscheidend behält.
    zusatz = [z.strip() for z in re.findall(r"\(([^)]*)\)", s) if z.strip()]
    s = _PAREN.sub(" ", s)
    s = _PUNCT.sub(" ", s)
    tokens = [t for t in _WS.sub(" ", s).split() if t]
    if not tokens:
        return ""

    rumpf, form = _split_legal_form(tokens)
    if etype == T.AUTO:
        etype = T.ORG if form else T.PERSON

    if etype == T.PERSON:
        rumpf = _person_order(rumpf if not form else tokens)
        if hat_komma and len(rumpf) > 1:
            # "Holm, Anders Kristian" -> "anders kristian holm"
            teile = [p.strip() for p in _basis(raw).split(",")]
            if len(teile) == 2:
                links = [t for t in _PUNCT.sub(" ", teile[0]).split() if t]
                rechts = [t for t in _PUNCT.sub(" ", teile[1]).split() if t]
                rumpf = _person_order(rechts + links)
        return " ".join(rumpf)

    kern = " ".join(rumpf) + (f"|{form}" if form else "")
    if zusatz:
        kern += "(" + ",".join(_PUNCT.sub(" ", z).split() and
                               " ".join(_PUNCT.sub(" ", z).split())
                               for z in zusatz) + ")"
    return kern


# ------------------------------------------------------------ Unscharfer Weg
_DIGRAPHS = [("ue", "u"), ("oe", "o"), ("ae", "a"), ("ss", "s"),
             ("ph", "f"), ("th", "t"), ("ck", "k")]


def block_key(raw: str, etype: str = T.AUTO) -> str:
    """Aggressiver Schlüssel. Nur für Kandidatensuche, nie für Vektoren.

    Zusätzlich zu strict_key: Diakritika entfernt, deutsche und griechische
    Digraphen eingeebnet, Rechtsform verworfen, Klammerzusätze verworfen,
    Tokens sortiert.
    """
    s = _PAREN.sub(" ", _basis(raw))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in _DIGRAPHS:
        s = s.replace(a, b)
    s = _PUNCT.sub(" ", s)
    tokens = [t for t in s.split() if t]
    rumpf, _ = _split_legal_form(tokens)
    rumpf = [t for t in (rumpf or tokens) if t not in TITLES]
    # Einzelinitialen fallen weg: "anders k holm" == "anders holm"
    rumpf = [t for t in rumpf if len(t) > 1]
    return " ".join(sorted(rumpf))


# --------------------------------------------------------------- Ähnlichkeit
def _trigramme(s: str) -> set[str]:
    s = f"  {s} "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def aehnlichkeit(a: str, b: str) -> float:
    """Trigramm-Dice und Token-Jaccard, gewichtet. 0.0 bis 1.0."""
    if not a or not b:
        return 0.0
    ta, tb = _trigramme(a), _trigramme(b)
    dice = 2 * len(ta & tb) / (len(ta) + len(tb))
    sa, sb = set(a.split()), set(b.split())
    jacc = len(sa & sb) / len(sa | sb) if sa | sb else 0.0
    return round(0.6 * dice + 0.4 * jacc, 4)


# ------------------------------------------------------------------ Vorschlag
@dataclass
class Vorschlag:
    a: str                 # Anzeigeform 1
    b: str                 # Anzeigeform 2
    key_a: str
    key_b: str
    score: float
    grund: str
    etype: str
    warnung: str | None = None

    def __str__(self) -> str:
        z = f"{self.score:.3f}  {self.a!r}  <->  {self.b!r}   [{self.etype}, {self.grund}]"
        return z + (f"\n           ACHTUNG: {self.warnung}" if self.warnung else "")


# ------------------------------------------------------------------ Resolver
@dataclass
class EntityResolver:
    """Hält die Alias-Tabelle und erzeugt Verschmelzungsvorschläge."""

    # bestätigter Alias-Schlüssel -> kanonischer Schlüssel
    alias: dict[str, str] = field(default_factory=dict)
    # kanonischer Schlüssel -> zuerst gesehene Anzeigeform
    anzeige: dict[str, str] = field(default_factory=dict)
    _block: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    _token: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    _typ: dict[str, str] = field(default_factory=dict)
    _token_freq: Counter = field(default_factory=Counter)
    entscheidungen: list[dict] = field(default_factory=list)

    # Tokens, die in mehr als diesem Anteil der Entitäten vorkommen, taugen
    # nicht zum Blocken ("shipping", "holding", "capital").
    token_stop_anteil: float = 0.05
    token_stop_min: int = 4

    # ------------------------------------------------------------- Schlüssel
    def key(self, raw: str, etype: str = T.AUTO) -> str:
        """Kanonischer Schlüssel inklusive bestätigter Aliase."""
        k = strict_key(raw, etype)
        return self.alias.get(k, k)

    def register(self, raw: str, etype: str = T.AUTO) -> str:
        """Nimmt eine Entität auf und liefert ihren kanonischen Schlüssel."""
        k = self.key(raw, etype)
        if not k:
            return k
        if k not in self.anzeige:
            self.anzeige[k] = raw.strip()
            self._typ[k] = etype
        bk = block_key(raw, etype)
        if bk:
            self._block[bk].add(k)
            for t in set(bk.split()):
                self._token[t].add(k)
                self._token_freq[t] += 1
        return k

    # ------------------------------------------------------------ Vorschläge
    def vorschlaege(self, schwelle: float = 0.80,
                    max_pro_entitaet: int = 5) -> list[Vorschlag]:
        """Kandidatenpaare für die manuelle Prüfung. Verschmilzt nichts."""
        gesamt = max(len(self.anzeige), 1)
        # Absolute Untergrenze: bei kleinen Beständen ueberschreitet sonst
        # jedes Token den relativen Anteil und das Token-Blocking faellt
        # vollstaendig aus.
        grenze = max(self.token_stop_min, self.token_stop_anteil * gesamt)
        stop = {t for t, c in self._token_freq.items() if c > grenze}

        paare: dict[tuple[str, str], str] = {}
        for bk, keys in self._block.items():
            if len(keys) > 1:
                for a, b in _paare(keys):
                    paare[(a, b)] = "gleicher Block"
        for t, keys in self._token.items():
            if t in stop or len(keys) < 2 or len(keys) > 50:
                continue
            for a, b in _paare(keys):
                paare.setdefault((a, b), f"Token '{t}'")

        raus: list[Vorschlag] = []
        for (a, b), grund in paare.items():
            if self._typ.get(a) != self._typ.get(b):
                # Person und Gesellschaft werden nicht verglichen.
                if T.AUTO not in (self._typ.get(a), self._typ.get(b)):
                    continue
            score = aehnlichkeit(block_key(self.anzeige[a], self._typ.get(a, T.AUTO)),
                                 block_key(self.anzeige[b], self._typ.get(b, T.AUTO)))
            if score >= schwelle:
                warnung = None
                fa, fb = _form_von(a), _form_von(b)
                if fa != fb:
                    warnung = (f"unterschiedliche Rechtsform ({fa or '—'} vs. "
                               f"{fb or '—'}) — verschiedene Jurisdiktionen "
                               f"bedeuten in aller Regel verschiedene Gesellschaften")
                raus.append(Vorschlag(self.anzeige[a], self.anzeige[b], a, b,
                                      score, grund, self._typ.get(a, T.AUTO),
                                      warnung))
        raus.sort(key=lambda v: -v.score)

        zaehler: Counter = Counter()
        gefiltert = []
        for v in raus:
            if zaehler[v.key_a] < max_pro_entitaet and zaehler[v.key_b] < max_pro_entitaet:
                gefiltert.append(v)
                zaehler[v.key_a] += 1
                zaehler[v.key_b] += 1
        return gefiltert

    # ---------------------------------------------------------- Entscheidung
    def bestaetige(self, alias_key: str, kanonisch_key: str, *,
                   pruefer: str, begruendung: str) -> None:
        """Bestätigt eine Verschmelzung. Wirkt ab jetzt auf strict_key.

        Achtung: Bereits gespeicherte Fakten tragen den alten Schlüssel.
        Nach jeder Bestätigung ist eine Neuindizierung des Speichers nötig
        — `Faktenkern.reindex()`.
        """
        if alias_key == kanonisch_key:
            return
        self.alias[alias_key] = kanonisch_key
        self.entscheidungen.append({
            "typ": "verschmolzen", "alias": alias_key, "kanonisch": kanonisch_key,
            "pruefer": pruefer, "begruendung": begruendung,
        })

    def verwerfe(self, key_a: str, key_b: str, *, pruefer: str,
                 begruendung: str) -> None:
        """Hält fest, dass zwei ähnliche Entitäten NICHT dieselbe sind."""
        self.entscheidungen.append({
            "typ": "getrennt", "a": key_a, "b": key_b,
            "pruefer": pruefer, "begruendung": begruendung,
        })

    # ------------------------------------------------------------- Integrität
    def fingerprint(self) -> str:
        """Hash über sämtliche Regeltabellen. Zwei Pods dürfen nur
        föderieren, wenn der Fingerabdruck übereinstimmt."""
        h = hashlib.sha256()
        h.update(RESOLVER_VERSION.encode())
        for kanon in sorted(LEGAL_FORMS):
            h.update(kanon.encode())
            for v in sorted(LEGAL_FORMS[kanon]):
                h.update(b"|" + v.encode())
        for pat in sorted(NOISE_PATTERNS):
            h.update(pat.encode())
        for t in sorted(TITLES):
            h.update(t.encode())
        for c in sorted(CYRILLIC):
            h.update(f"{c}{CYRILLIC[c]}".encode())
        for a, b in _DIGRAPHS:
            h.update(f"{a}{b}".encode())
        for p in sorted(INVERSE):
            h.update(f"{p}->{INVERSE[p]}".encode())
        for p in sorted(PREDICATE_SCHEMA):
            h.update(f"{p}{PREDICATE_SCHEMA[p]}".encode())
        return f"{RESOLVER_VERSION}:{h.hexdigest()[:16]}"


def _form_von(key: str) -> str | None:
    """Liest die kanonische Rechtsform aus einem strikten Schlüssel."""
    if "|" not in key:
        return None
    return key.split("|", 1)[1].split("(", 1)[0]


def _paare(keys):
    ks = sorted(keys)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            yield ks[i], ks[j]


def typen_fuer(praedikat: str) -> tuple[str, str]:
    return PREDICATE_SCHEMA.get(praedikat, (T.AUTO, T.AUTO))
