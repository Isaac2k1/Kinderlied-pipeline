# kinderlied – animierte Kinderlied-Videos aus YAML

Eine YAML-Datei beschreibt Lied, Szenen und Figuren. Die Pipeline erzeugt daraus den Ablauf: Auftritte, Choreografien, Zählmechanik, Szenenwechsel, Kamerafahrt im Refrain und Karaoke-Text. Am Ende stehen ein MP4 (1080p, 30 fps) und ein Beschreibungstext für YouTube.

## Installation

```
python3 -m venv .venv
.venv/bin/python -m pip install numpy pillow pyyaml
```

ffmpeg muss im PATH sein (`brew install ffmpeg`). Optional für automatisches Timing aus einer Gesangsaufnahme: `pip install mlx-whisper` (Apple Silicon) oder `faster-whisper`.

## Aufruf (im Projektordner)

| Befehl | Zweck |
|---|---|
| `.venv/bin/python -m kinderlied info songs/lied.yaml` | Zeitachse anzeigen: Abschnitte, Szenen, Choreos |
| `.venv/bin/python -m kinderlied bilder songs/lied.yaml 5 30.5` | Standbilder zu bestimmten Zeitpunkten (PNG) |
| `.venv/bin/python -m kinderlied render songs/lied.yaml --vorschau` | schnelle Vorschau mit 960×540 und 24 fps |
| `.venv/bin/python -m kinderlied render songs/lied.yaml` | Endfassung |
| `... render songs/lied.yaml --nur 03_refrain,outro` | nur diese Segmente neu rendern |

Ausgabe neben der YAML-Datei: `lied.mp4`, `lied_beschreibung.txt`, `lied_musik.wav` (nur ohne eigenes Audio) und `lied_segmente/`. Die Abschnitte werden parallel gerendert.

## Konfiguration

```yaml
titel: Fünf kleine Nachtlichter
untertitel: Ein Zähllied zum Mitsingen
lehrplan: "MA.1 Zahl und Variable – zählen bis 5 (Zyklus 1)"
beschreibung: |              # erscheint im YouTube-Beschreibungstext
  ...
musik: {bpm: 104, tonart: C, seed: 3}   # Platzhaltermusik; seed ändert die Melodie
audio: gesang.wav            # optional: eigene Aufnahme ersetzt die Platzhaltermusik
timing: auto                 # auto | generiert | whisper | labels:gesang.txt
szene: nacht                 # Standardszene
intro_takte: 2
zwischenspiel_takte: 1
outro_takte: 2
format: {breite: 1920, hoehe: 1080, fps: 30}
schrift: /Pfad/zur/Schrift.ttf   # optional

figuren:
  - {name: Lumi, farbe: "#FFD666", accessoire: flamme, groesse: 1.0}

abschnitte:
  - typ: strophe             # strophe | refrain | bridge (frei wählbar)
    szene: nacht             # nacht | tag | herbst | winter
    choreo: schweben         # schweben | tanzen | kreis | reihe
    effekte: [gluehwuermchen]  # schnee | blaetter | regen | gluehwuermchen | konfetti | funkeln
    anzahl: 5                # Zähllied: sichtbare Figuren in diesem Abschnitt
    zahl_zeigen: true        # Zahl-Badge oben links (Standard: wenn anzahl gesetzt)
    zeilen:
      - "Fünf klei-ne Nacht-lich-ter"   # Silben mit Bindestrich trennen; echter Bindestrich: --
```

**Accessoires:** `flamme`, `blatt`, `muetze`, `ohren`, `keine`

**Standardwerte, wenn nicht angegeben**
- Effekte gehören zur Szene: nacht → Glühwürmchen, tag → Funkeln, herbst → Blätter, winter → Schnee. Im Refrain kommt Konfetti dazu.
- Choreo: Refrain → `tanzen`, sonst `schweben`.

## So entsteht der Ablauf

- **Intro:** Die Figuren fliegen gestaffelt von unten ein, Titel und Untertitel stehen im Textband.
- **Choreo-Wechsel:** Wechselt die Choreografie zwischen zwei Abschnitten, gleiten die Figuren weich in die neue Formation.
- **Zählmechanik:** Hat der nächste Abschnitt eine kleinere `anzahl`, fliegen die überzähligen Figuren am Abschnittsende zum Mond. Bei einer grösseren `anzahl` kommen sie von unten herein. Ein Zahl-Badge zeigt die aktuelle Anzahl.
- **Szenenwechsel:** Wechselt die Szene, wird über 0,8 s überblendet.
- **Refrain:** Die Kamera fährt langsam heran, die Figuren hüpfen im Takt.
- **Gesang:** Die Münder öffnen sich auf jeder Silbe. Der Liedtext erscheint als Karaoke, zwei Zeilen pro Seite, Silbe für Silbe eingefärbt.
- **Outro:** Die Figuren stehen in einer Wellenreihe, der Titel erscheint erneut, dann wird ausgeblendet.

## Eigene Gesangsaufnahme

1. Audiodatei aufnehmen (WAV oder M4A) und in der YAML setzen: `audio: gesang.wav`.
2. Timing wählen:
   - **Automatisch mit Whisper:** `timing: auto`. Die Wörter werden mit Zeitstempeln transkribiert und dem Liedtext zugeordnet.
   - **Manuell mit Audacity:** Pro Liedzeile eine Bereichsmarke setzen, dann *Datei → Exportieren → Textmarken exportieren* wählen und in der YAML `timing: labels:gesang.txt` eintragen. Die Silben werden innerhalb jeder Zeile rhythmisch verteilt.
3. Mit `info` prüfen und eine Vorschau rendern.

## Erweitern

| Datei | Inhalt |
|---|---|
| `kinderlied/scenes.py` | Szenen-Presets (`PRESETS`): Farben, Himmelskörper, Bäume, Haus |
| `kinderlied/characters.py` | Figurenzeichnung und Accessoires |
| `kinderlied/effects.py` | Partikeleffekte (zustandslos, Position = f(t)) |
| `kinderlied/director.py` | Choreografien (`_mode_pos`), Zählmechanik (`char_state`), Kamera, Text |
| `kinderlied/music.py` | Melodiegenerator und Synthese der Platzhaltermusik |

Jedes Bild ist eine reine Funktion der Zeit. Deshalb kann jedes Segment für sich gerendert werden, und `--nur` funktioniert ohne Nebenwirkungen.

Hinweis: Die Lehrplan-21-Angaben in den Beispielen sind grob formuliert. Die genauen Kompetenzcodes vor der Veröffentlichung im Lehrplan nachschlagen.
