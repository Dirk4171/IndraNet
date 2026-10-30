"""
IndraNet — Erscheinungsbild
============================

Zwei Themen, umschaltbar zur Laufzeit. Beide setzen dieselben
CSS-Variablen; der Rest der Oberfläche kennt nur die Variablen und muss
für ein neues Thema nicht angefasst werden.

LAGEZENTRALE (Vorgabe)
----------------------
Dunkle Kommandozentralen-Optik. Monospace durchgehend, Eckwinkel statt
Rahmen, dünne Trennlinien, Kennzahlen als Leuchtziffern. Statusfarben aus
dem Instrumentenbau: Cyan für Bestätigtes, Bernstein für Ungesichertes,
Rot für Widersprüchliches.

Gestaltungsregel: Der Schwärzungsbalken bleibt der stärkste Akzent im
Bild. In einem dunklen Thema ist Schwarz auf Dunkelgrau kaum sichtbar —
deshalb wird er hier zum leuchtenden Sperrmuster, das genauso deutlich
sagt "hier ist etwas, das Sie nicht sehen dürfen".

ARCHIV
------
Helles Aktenpapier, wie in Version 1.0. Für lange Lesestrecken und für
alle, die kein Werkzeug wollen, das nach Waffensystem aussieht.

KEINE WEBFONTS
--------------
Beide Themen verwenden ausschließlich Systemschriften. Ein Werkzeug für
Quellenmaterial darf beim Öffnen nichts nachladen — das gilt unabhängig
vom Erscheinungsbild.
"""

THEMEN = {
    "lagezentrale": {
        "name": ("Lagezentrale", "Command"),
        "dunkel": True,
        "vars": {
            "--grund":       "#070B10",
            "--grund2":      "#0B1118",
            "--flaeche":     "#0E151D",
            "--flaeche2":    "#121A24",
            "--tinte":       "#D8E4EE",
            "--gedaempft":   "#63788C",
            "--linie":       "#1C2836",
            "--linie-hell":  "#2A3B4E",
            "--akzent":      "#38E1D0",
            "--akzent-tief": "#0E3D3A",
            "--bestaetigt":  "#38E1D0",
            "--einfach":     "#E0A93C",
            "--umstritten":  "#FF5C5C",
            "--widerrufen":  "#4A5A6B",
            "--fokus":       "#38E1D0",
            "--schwarz-bg":  "#050709",
            "--raster":      "rgba(56,225,208,.035)",
            "--glanz":       "0 0 0 1px rgba(56,225,208,.18), "
                             "0 0 22px rgba(56,225,208,.10)",
            # Kommandozentrale: durchgehend Monospace — die Welt dieses
            # Werkzeugs besteht aus Kennungen, Prüfsummen, Fundstellen.
            "--sans":        "var(--mono)",
            "--zeichen":     "1.5",
        },
    },
    "archiv": {
        "name": ("Archiv", "Archive"),
        "dunkel": False,
        "vars": {
            "--grund":       "#EEF0F2",
            "--grund2":      "#E6E9EC",
            "--flaeche":     "#FFFFFF",
            "--flaeche2":    "#F7F8FA",
            "--tinte":       "#141A1F",
            "--gedaempft":   "#5B6770",
            "--linie":       "#C9D0D6",
            "--linie-hell":  "#DCE1E6",
            "--akzent":      "#1B4D8F",
            "--akzent-tief": "#DCE6F3",
            "--bestaetigt":  "#116149",
            "--einfach":     "#8A6A17",
            "--umstritten":  "#9B2C2C",
            "--widerrufen":  "#8A929A",
            "--fokus":       "#1B4D8F",
            "--schwarz-bg":  "#141A1F",
            "--raster":      "rgba(0,0,0,0)",
            "--glanz":       "0 0 0 1px rgba(27,77,143,.20)",
            # Archiv: Grotesk für lange Lesestrecken, Monospace nur dort,
            # wo Zeichengenauigkeit zählt.
            "--sans":        'system-ui,-apple-system,"Segoe UI",Roboto,'
                             '"Helvetica Neue",sans-serif',
            "--zeichen":     "1.55",
        },
    },
}

VORGABE = "lagezentrale"


def css_variablen(thema: str = VORGABE) -> str:
    t = THEMEN.get(thema, THEMEN[VORGABE])
    zeilen = "\n".join(f"  {k}: {v};" for k, v in t["vars"].items())
    return f":root[data-thema='{thema}'] {{\n{zeilen}\n}}"


def alle_css() -> str:
    return "\n".join(css_variablen(k) for k in THEMEN)


def liste(sprache: str = "de") -> list[dict]:
    i = 1 if sprache == "en" else 0
    return [{"schluessel": k, "name": v["name"][i], "dunkel": v["dunkel"]}
            for k, v in THEMEN.items()]
