# Lizenzhinweise / Licensing notes

IndraNet selbst steht unter der GNU Affero General Public License, Version 3
(vollständiger Text in LICENSE).
IndraNet itself is licensed under the GNU AGPL, version 3 (full text in LICENSE).

```
IndraNet
Copyright (C) 2026 VELVIUM Technologies UG (haftungsbeschränkt)

Dieses Programm ist freie Software: Sie können es unter den Bedingungen der
GNU Affero General Public License, Version 3, weitergeben und/oder verändern.

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU Affero General Public License, version 3, as
published by the Free Software Foundation.

Der vollständige Lizenztext: https://www.gnu.org/licenses/agpl-3.0.txt
Full licence text: https://www.gnu.org/licenses/agpl-3.0.txt

PATENTHINWEIS / PATENT NOTICE
-----------------------------
§11 AGPL-3.0 gewährt eine Patentlizenz für die Nutzung dieser Software.
VELVIUM Technologies hält Schutzrechte an anderen Verfahren; diese bleiben
davon unberührt.

Section 11 AGPL-3.0 grants a patent licence for the use of this software.
VELVIUM Technologies holds rights to other methods; these remain unaffected.

HAFTUNGSAUSSCHLUSS / DISCLAIMER
-------------------------------
Diese Software wird ohne jede Gewährleistung bereitgestellt. Sie ersetzt
keine journalistische Sorgfalt und keine rechtliche Prüfung vor einer
Veröffentlichung.

This software comes with no warranty. It does not replace journalistic
diligence or legal review before publication.
```

## Verwendete Bibliotheken / Third-party libraries

- **cryptography** (Apache-2.0 / BSD-3-Clause) — Verschlüsselung, Signaturen
- **Python Standard Library** (PSF License)
- **numpy** (BSD-3-Clause) — nur für externe Anschlüsse / connectors only

## Externe Daten / External data

**OpenSanctions**: Der Programmcode ist MIT-lizenziert, **die Daten sind es
nicht** — sie stehen unter CC-BY-NC (Namensnennung, nicht kommerziell). Für
redaktionelle Nutzung unproblematisch. Wer IndraNet mit vorbefülltem
Bestand verkauft, braucht eine Datenlizenz von OpenSanctions.

*The OpenSanctions codebase is MIT-licensed; **the data is not** — it is
CC-BY-NC. Unproblematic for editorial use. Anyone selling IndraNet with a
pre-filled dataset needs a data licence from OpenSanctions.*

**Weitere Datenquellen / further data sources** — beim Abruf gelten die
Bedingungen der Betreiber / the operators' terms apply:
GLEIF (CC0), ICIJ Offshore Leaks (ODbL, Quelle nennen), Wikidata (CC0),
Wikipedia (CC BY-SA), GDELT, adsb.lol, Global Fishing Watch (Quelle nennen,
nicht kommerziell / attribution, non-commercial).

**Tor Expert Bundle** (BSD-3-Clause und weitere, siehe `tor/docs`) wird nicht
im Repository mitgeführt, sondern beim Bauen dazugelegt. / Not kept in the
repository; added at build time.

**Ereignisquellen** (World Monitor u. a.): Bedingungen des jeweiligen
Betreibers prüfen. / Check the respective operator's terms.
