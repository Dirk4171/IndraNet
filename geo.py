"""
IndraNet — Orte
================

Fakten über Sitz und Wohnort nennen Orte als Namen: "Panama",
"Britische Jungferninseln", "Limassol". Für die Karte braucht jeder Ort
Koordinaten. Drei Wege, in dieser Reihenfolge:

  1. Ländertabelle (unten, eingebaut) — Staaten und die üblichen
     Offshore-Rechtsordnungen, mit deutschen und englischen Namen und
     gängigen Kürzeln. Kein Netzabruf, keine Spur.
  2. Koordinaten, die die KI zu einem Ort mitliefert. Sie werden wie jede
     KI-Angabe im Prüfkorb vom Menschen bestätigt.
  3. Nominatim (OpenStreetMap) — nur auf ausdrücklichen Wunsch und nur
     über den eingestellten Netzweg, denn die Anfrage verrät, welchen Ort
     man sucht.

Die Ländertabelle ist eigene Arbeit (Schwerpunkt bzw. Hauptort, gerundet)
und damit frei von Lizenzauflagen.
"""

from __future__ import annotations

import time
import unicodedata

# ISO|deutsch|englisch|breite|länge|weitere Namen (Komma-getrennt)
_LAENDER = """
AF|Afghanistan|Afghanistan|33.9|67.7|
AL|Albanien|Albania|41.1|20.2|
DZ|Algerien|Algeria|28.0|1.7|
AD|Andorra|Andorra|42.5|1.5|
AO|Angola|Angola|-11.2|17.9|
AI|Anguilla|Anguilla|18.22|-63.05|
AG|Antigua und Barbuda|Antigua and Barbuda|17.06|-61.8|Antigua
AR|Argentinien|Argentina|-38.4|-63.6|
AM|Armenien|Armenia|40.1|45.0|
AW|Aruba|Aruba|12.52|-69.97|
AU|Australien|Australia|-25.3|133.8|
AT|Österreich|Austria|47.5|14.6|Oesterreich
AZ|Aserbaidschan|Azerbaijan|40.1|47.6|
BS|Bahamas|Bahamas|25.03|-77.4|The Bahamas
BH|Bahrain|Bahrain|26.07|50.56|
BD|Bangladesch|Bangladesh|23.7|90.4|
BB|Barbados|Barbados|13.19|-59.54|
BY|Belarus|Belarus|53.7|28.0|Weißrussland,Weissrussland
BE|Belgien|Belgium|50.5|4.5|
BZ|Belize|Belize|17.2|-88.5|
BJ|Benin|Benin|9.3|2.3|
BM|Bermuda|Bermuda|32.3|-64.75|Bermudas
BT|Bhutan|Bhutan|27.5|90.4|
BO|Bolivien|Bolivia|-16.3|-63.6|
BA|Bosnien und Herzegowina|Bosnia and Herzegovina|43.9|17.7|Bosnien
BW|Botswana|Botswana|-22.3|24.7|
BR|Brasilien|Brazil|-14.2|-51.9|
VG|Britische Jungferninseln|British Virgin Islands|18.42|-64.64|BVI,Jungferninseln,Virgin Islands (British),Tortola
BN|Brunei|Brunei|4.5|114.7|Brunei Darussalam
BG|Bulgarien|Bulgaria|42.7|25.5|
BF|Burkina Faso|Burkina Faso|12.2|-1.6|
BI|Burundi|Burundi|-3.4|29.9|
KH|Kambodscha|Cambodia|12.6|105.0|
CM|Kamerun|Cameroon|7.4|12.4|
CA|Kanada|Canada|56.1|-106.3|
CV|Kap Verde|Cape Verde|16.0|-24.0|Cabo Verde
KY|Kaimaninseln|Cayman Islands|19.31|-81.25|Cayman,Caymaninseln,Grand Cayman
CF|Zentralafrikanische Republik|Central African Republic|6.6|20.9|
TD|Tschad|Chad|15.5|18.7|
CL|Chile|Chile|-35.7|-71.5|
CN|China|China|35.9|104.2|Volksrepublik China,PRC,VR China
CO|Kolumbien|Colombia|4.6|-74.3|
KM|Komoren|Comoros|-11.9|43.9|
CG|Republik Kongo|Republic of the Congo|-0.2|15.8|Kongo-Brazzaville
CD|Demokratische Republik Kongo|DR Congo|-4.0|21.8|Kongo-Kinshasa,DRC,Kongo
CK|Cookinseln|Cook Islands|-21.24|-159.78|
CR|Costa Rica|Costa Rica|9.7|-83.8|
CI|Elfenbeinküste|Côte d'Ivoire|7.5|-5.5|Cote d'Ivoire,Ivory Coast,Elfenbeinkueste
HR|Kroatien|Croatia|45.1|15.2|
CU|Kuba|Cuba|21.5|-77.8|
CW|Curaçao|Curaçao|12.17|-68.98|Curacao
CY|Zypern|Cyprus|35.1|33.4|Limassol,Nikosia,Nicosia
CZ|Tschechien|Czechia|49.8|15.5|Tschechische Republik,Czech Republic
DK|Dänemark|Denmark|56.3|9.5|Daenemark
DJ|Dschibuti|Djibouti|11.8|42.6|
DM|Dominica|Dominica|15.41|-61.37|
DO|Dominikanische Republik|Dominican Republic|18.7|-70.2|
EC|Ecuador|Ecuador|-1.8|-78.2|
EG|Ägypten|Egypt|26.8|30.8|Aegypten
SV|El Salvador|El Salvador|13.8|-88.9|
GQ|Äquatorialguinea|Equatorial Guinea|1.6|10.3|
ER|Eritrea|Eritrea|15.2|39.8|
EE|Estland|Estonia|58.6|25.0|
SZ|Eswatini|Eswatini|-26.5|31.5|Swasiland
ET|Äthiopien|Ethiopia|9.1|40.5|Aethiopien
FO|Färöer|Faroe Islands|62.0|-6.8|Faeroeer
FJ|Fidschi|Fiji|-17.7|178.1|
FI|Finnland|Finland|61.9|25.7|
FR|Frankreich|France|46.2|2.2|
GA|Gabun|Gabon|-0.8|11.6|
GM|Gambia|Gambia|13.4|-15.3|
GE|Georgien|Georgia|42.3|43.4|
DE|Deutschland|Germany|51.17|10.45|BRD,Bundesrepublik Deutschland,Federal Republic of Germany
GH|Ghana|Ghana|7.9|-1.0|
GI|Gibraltar|Gibraltar|36.14|-5.35|
GR|Griechenland|Greece|39.1|21.8|
GL|Grönland|Greenland|71.7|-42.6|Groenland
GD|Grenada|Grenada|12.12|-61.68|
GT|Guatemala|Guatemala|15.8|-90.2|
GG|Guernsey|Guernsey|49.45|-2.58|
GN|Guinea|Guinea|9.9|-9.7|
GW|Guinea-Bissau|Guinea-Bissau|11.8|-15.2|
GY|Guyana|Guyana|4.9|-58.9|
HT|Haiti|Haiti|19.0|-72.3|
HN|Honduras|Honduras|15.2|-86.2|
HK|Hongkong|Hong Kong|22.32|114.17|Hong Kong SAR
HU|Ungarn|Hungary|47.2|19.5|
IS|Island|Iceland|64.96|-19.0|
IN|Indien|India|20.6|79.0|
ID|Indonesien|Indonesia|-0.8|113.9|
IR|Iran|Iran|32.4|53.7|
IQ|Irak|Iraq|33.2|43.7|
IE|Irland|Ireland|53.4|-8.2|
IM|Isle of Man|Isle of Man|54.24|-4.55|Insel Man
IL|Israel|Israel|31.0|34.9|
IT|Italien|Italy|41.9|12.6|
JM|Jamaika|Jamaica|18.1|-77.3|
JP|Japan|Japan|36.2|138.3|
JE|Jersey|Jersey|49.21|-2.13|
JO|Jordanien|Jordan|30.6|36.2|
KZ|Kasachstan|Kazakhstan|48.0|66.9|
KE|Kenia|Kenya|-0.02|37.9|
KI|Kiribati|Kiribati|1.87|-157.4|
XK|Kosovo|Kosovo|42.6|20.9|
KW|Kuwait|Kuwait|29.3|47.5|
KG|Kirgisistan|Kyrgyzstan|41.2|74.8|
LA|Laos|Laos|19.9|102.5|
LV|Lettland|Latvia|56.9|24.6|
LB|Libanon|Lebanon|33.9|35.9|
LS|Lesotho|Lesotho|-29.6|28.2|
LR|Liberia|Liberia|6.4|-9.4|
LY|Libyen|Libya|26.3|17.2|
LI|Liechtenstein|Liechtenstein|47.17|9.55|Vaduz
LT|Litauen|Lithuania|55.2|23.9|
LU|Luxemburg|Luxembourg|49.8|6.1|
MO|Macau|Macao|22.2|113.55|Macao SAR
MG|Madagaskar|Madagascar|-18.8|46.9|
MW|Malawi|Malawi|-13.3|34.3|
MY|Malaysia|Malaysia|4.2|102.0|Labuan
MV|Malediven|Maldives|3.2|73.2|
ML|Mali|Mali|17.6|-4.0|
MT|Malta|Malta|35.94|14.38|
MH|Marshallinseln|Marshall Islands|7.13|171.18|Marshall Islands,Majuro
MR|Mauretanien|Mauritania|21.0|-10.9|
MU|Mauritius|Mauritius|-20.35|57.55|
MX|Mexiko|Mexico|23.6|-102.6|
FM|Mikronesien|Micronesia|6.9|158.2|
MD|Moldau|Moldova|47.4|28.4|Moldawien,Republik Moldau
MC|Monaco|Monaco|43.74|7.42|
MN|Mongolei|Mongolia|46.9|103.8|
ME|Montenegro|Montenegro|42.7|19.4|
MS|Montserrat|Montserrat|16.74|-62.19|
MA|Marokko|Morocco|31.8|-7.1|
MZ|Mosambik|Mozambique|-18.7|35.5|
MM|Myanmar|Myanmar|21.9|95.96|Birma,Burma
NA|Namibia|Namibia|-22.96|18.5|
NR|Nauru|Nauru|-0.52|166.93|
NP|Nepal|Nepal|28.4|84.1|
NL|Niederlande|Netherlands|52.1|5.3|Holland,The Netherlands
NZ|Neuseeland|New Zealand|-40.9|174.9|
NI|Nicaragua|Nicaragua|12.9|-85.2|
NE|Niger|Niger|17.6|8.1|
NG|Nigeria|Nigeria|9.1|8.7|
NU|Niue|Niue|-19.05|-169.87|
KP|Nordkorea|North Korea|40.3|127.5|DPRK,Demokratische Volksrepublik Korea
MK|Nordmazedonien|North Macedonia|41.6|21.7|Mazedonien
NO|Norwegen|Norway|60.5|8.5|
OM|Oman|Oman|21.5|55.9|
PK|Pakistan|Pakistan|30.4|69.3|
PW|Palau|Palau|7.5|134.6|
PS|Palästina|Palestine|31.95|35.23|Palaestina,Palästinensische Gebiete
PA|Panama|Panama|8.54|-80.78|Panama City,Panama-Stadt
PG|Papua-Neuguinea|Papua New Guinea|-6.3|143.96|
PY|Paraguay|Paraguay|-23.4|-58.4|
PE|Peru|Peru|-9.2|-75.0|
PH|Philippinen|Philippines|12.9|121.8|
PL|Polen|Poland|51.9|19.1|
PT|Portugal|Portugal|39.4|-8.2|Madeira
PR|Puerto Rico|Puerto Rico|18.22|-66.59|
QA|Katar|Qatar|25.35|51.18|
RO|Rumänien|Romania|45.9|24.97|Rumaenien
RU|Russland|Russia|61.5|105.3|Russische Föderation,Russian Federation
RW|Ruanda|Rwanda|-1.9|29.9|
KN|St. Kitts und Nevis|Saint Kitts and Nevis|17.36|-62.78|Nevis,St Kitts
LC|St. Lucia|Saint Lucia|13.91|-60.98|
VC|St. Vincent und die Grenadinen|Saint Vincent and the Grenadines|13.25|-61.2|
WS|Samoa|Samoa|-13.76|-172.1|
SM|San Marino|San Marino|43.94|12.46|
ST|São Tomé und Príncipe|Sao Tome and Principe|0.19|6.61|
SA|Saudi-Arabien|Saudi Arabia|23.9|45.1|
SN|Senegal|Senegal|14.5|-14.45|
RS|Serbien|Serbia|44.0|21.0|
SC|Seychellen|Seychelles|-4.68|55.49|Seychelles
SL|Sierra Leone|Sierra Leone|8.46|-11.78|
SG|Singapur|Singapore|1.35|103.82|
SX|Sint Maarten|Sint Maarten|18.04|-63.07|
SK|Slowakei|Slovakia|48.7|19.7|
SI|Slowenien|Slovenia|46.15|14.99|
SB|Salomonen|Solomon Islands|-9.6|160.2|
SO|Somalia|Somalia|5.15|46.2|
ZA|Südafrika|South Africa|-30.6|22.9|Suedafrika
KR|Südkorea|South Korea|35.9|127.8|Republik Korea,Korea
SS|Südsudan|South Sudan|6.9|31.3|
ES|Spanien|Spain|40.5|-3.7|
LK|Sri Lanka|Sri Lanka|7.9|80.8|
SD|Sudan|Sudan|12.9|30.2|
SR|Suriname|Suriname|3.9|-56.0|
SE|Schweden|Sweden|60.1|18.6|
CH|Schweiz|Switzerland|46.8|8.2|Zug,Genf,Zürich
SY|Syrien|Syria|34.8|39.0|
TW|Taiwan|Taiwan|23.7|121.0|
TJ|Tadschikistan|Tajikistan|38.9|71.3|
TZ|Tansania|Tanzania|-6.4|34.9|
TH|Thailand|Thailand|15.9|100.99|
TL|Osttimor|Timor-Leste|-8.9|125.7|
TG|Togo|Togo|8.6|0.8|
TO|Tonga|Tonga|-21.18|-175.2|
TT|Trinidad und Tobago|Trinidad and Tobago|10.7|-61.2|
TN|Tunesien|Tunisia|33.9|9.5|
TR|Türkei|Türkiye|38.96|35.2|Tuerkei,Turkey
TM|Turkmenistan|Turkmenistan|38.97|59.6|
TC|Turks- und Caicosinseln|Turks and Caicos Islands|21.69|-71.8|Turks and Caicos
TV|Tuvalu|Tuvalu|-7.1|177.6|
UG|Uganda|Uganda|1.4|32.3|
UA|Ukraine|Ukraine|48.4|31.2|
AE|Vereinigte Arabische Emirate|United Arab Emirates|23.4|53.8|VAE,UAE,Dubai,Abu Dhabi,Emirate
GB|Vereinigtes Königreich|United Kingdom|54.0|-2.0|UK,Großbritannien,Grossbritannien,Great Britain,England,London,Schottland,Wales
US|Vereinigte Staaten|United States|39.8|-98.6|USA,US,Vereinigte Staaten von Amerika,United States of America,Amerika
UY|Uruguay|Uruguay|-32.5|-55.8|
UZ|Usbekistan|Uzbekistan|41.4|64.6|
VU|Vanuatu|Vanuatu|-15.4|166.96|
VA|Vatikanstadt|Vatican City|41.9|12.45|Vatikan,Heiliger Stuhl
VE|Venezuela|Venezuela|6.4|-66.6|
VN|Vietnam|Vietnam|14.06|108.3|
VI|Amerikanische Jungferninseln|US Virgin Islands|18.34|-64.9|Virgin Islands (U.S.)
YE|Jemen|Yemen|15.55|48.5|
ZM|Sambia|Zambia|-13.1|27.85|
ZW|Simbabwe|Zimbabwe|-19.0|29.15|
"""

# Häufige Sitz-Rechtsordnungen unterhalb der Staatsebene
_REGIONEN = """
US-DE|Delaware|Delaware|39.0|-75.5|Wilmington
US-NV|Nevada|Nevada|39.3|-116.6|
US-WY|Wyoming|Wyoming|43.0|-107.5|
US-SD|South Dakota|South Dakota|44.4|-100.2|
US-FL|Florida|Florida|27.8|-81.7|Miami
US-NY|New York|New York|40.71|-74.0|
GB-LND|London|London|51.51|-0.13|City of London
AE-DU|Dubai|Dubai|25.2|55.27|DIFC
CH-ZG|Zug|Zug|47.17|8.52|Kanton Zug
"""


def _falten(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.replace(".", " ").replace("-", " ").split())


class _Eintrag(dict):
    pass


def _laden() -> tuple[dict, dict]:
    nach_code, nach_name = {}, {}
    for block, art in ((_LAENDER, "land"), (_REGIONEN, "region")):
        for zeile in block.strip().splitlines():
            code, de, en, lat, lon, weitere = zeile.split("|")
            e = _Eintrag(code=code, de=de, en=en, lat=float(lat),
                         lon=float(lon), art=art)
            nach_code[code] = e
            for n in [code, de, en] + [w for w in weitere.split(",") if w]:
                nach_name.setdefault(_falten(n), e)
    return nach_code, nach_name


LAENDER, _NAMEN = _laden()


def nachschlagen(name: str) -> dict | None:
    """Ort aus der eingebauten Tabelle — exakt nach Namen oder Kürzel.

    Klammerzusätze und "Republik"-Varianten werden mitgeprüft, darüber
    hinaus wird nichts geraten. Ein falscher Punkt auf der Karte ist
    schlimmer als ein fehlender.
    """
    if not name:
        return None
    f = _falten(name)
    if f in _NAMEN:
        return dict(_NAMEN[f])
    # "Panama City, Panama" / "Limassol (Zypern)"
    for teil in [t for t in f.replace("(", ",").replace(")", "").split(",")
                 if t.strip()][::-1]:
        if teil.strip() in _NAMEN:
            return dict(_NAMEN[teil.strip()])
    return None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ort (
  schluessel  TEXT PRIMARY KEY,   -- strict_key der Ortsentität
  name        TEXT,
  lat         REAL,
  lon         REAL,
  land        TEXT,
  genauigkeit TEXT,               -- land | region | stadt | adresse | punkt
  quelle      TEXT,               -- tabelle | ki | nominatim | hand
  ts          REAL);
"""


class Orte:
    """Koordinaten für Ortsentitäten (PLACE, ADRESSE) eines Projekts."""

    def __init__(self, db, resolver):
        self.db = db
        self.resolver = resolver
        self.db.executescript(_SCHEMA)

    def _key(self, name: str) -> str:
        from resolver import strict_key
        return strict_key(name, "PLACE")

    def setzen(self, name: str, lat: float, lon: float, *, land: str = "",
               genauigkeit: str = "punkt", quelle: str = "hand") -> dict:
        if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
            raise ValueError("Koordinaten außerhalb des gültigen Bereichs")
        k = self._key(name)
        self.db.execute(
            "INSERT OR REPLACE INTO ort VALUES (?,?,?,?,?,?,?,?)",
            (k, name.strip(), float(lat), float(lon), land, genauigkeit,
             quelle, time.time()))
        self.db.commit()
        return {"schluessel": k, "name": name, "lat": lat, "lon": lon}

    def fuer(self, name: str) -> dict | None:
        """Koordinaten zu einem Ortsnamen: gespeichert, sonst Tabelle."""
        z = self.db.execute("SELECT * FROM ort WHERE schluessel=?",
                            (self._key(name),)).fetchone()
        if z:
            return dict(z)
        t = nachschlagen(name)
        if t:
            return {"name": name, "lat": t["lat"], "lon": t["lon"],
                    "land": t["code"][:2],
                    "genauigkeit": "land" if t["art"] == "land" else "region",
                    "quelle": "tabelle"}
        return None

    def alle(self) -> dict:
        return {z["schluessel"]: dict(z)
                for z in self.db.execute("SELECT * FROM ort")}

    def nominatim(self, name: str, netzweg) -> dict | None:
        """Geokodierung über OpenStreetMap — nur auf Anforderung."""
        d = netzweg.json("https://nominatim.openstreetmap.org/search",
                         params={"q": name, "format": "jsonv2", "limit": 1},
                         timeout=30)
        if not d:
            return None
        treffer = d[0]
        return self.setzen(name, float(treffer["lat"]), float(treffer["lon"]),
                           genauigkeit=treffer.get("addresstype", "punkt"),
                           quelle="nominatim")
