"""Liedkonfiguration (YAML) laden, mit Standardwerten ergänzen und in ein Datenmodell überführen.

Silben werden im Liedtext mit Bindestrich markiert:  "Fünf klei-ne Nacht-lich-ter"
Ein echter Bindestrich im Wort wird als "--" geschrieben.
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml

SCENES = ("nacht", "tag", "herbst", "winter")
ACCESSORIES = ("flamme", "blatt", "muetze", "ohren", "keine")
CHOREOS = ("schweben", "tanzen", "kreis", "reihe")
EFFECTS = ("schnee", "blaetter", "regen", "gluehwuermchen", "konfetti", "funkeln")

SCENE_DEFAULT_EFFECTS = {
    "nacht": ["gluehwuermchen"],
    "tag": ["funkeln"],
    "herbst": ["blaetter"],
    "winter": ["schnee"],
}

DEFAULT_COLORS = ["#FFD666", "#80E6C4", "#FF96BE", "#9DB8FF", "#FFB36B",
                  "#C7A2FF", "#A6E36B", "#FF8A80", "#7FDBFF", "#FFE08A"]


class ConfigError(Exception):
    pass


@dataclass
class Syllable:
    text: str            # Anzeigetext (inkl. Satzzeichen, ohne Silbentrennstrich)
    word_end: bool       # letzte Silbe eines Worts -> Leerzeichen danach
    line: int            # globaler Zeilenindex
    start: float = 0.0
    dur: float = 0.0
    pitch: int = 0       # MIDI-Note (nur Platzhaltermusik)


@dataclass
class Line:
    text: str
    syllables: List[Syllable]
    section: int


@dataclass
class Section:
    index: int
    kind: str                    # strophe | refrain | bridge | ...
    scene: str
    effects: List[str]
    choreo: str
    count: Optional[int]         # sichtbare Figuren (Zähllied), None = alle
    show_number: bool
    lines: List[Line]
    start: float = 0.0
    end: float = 0.0


@dataclass
class Character:
    name: str
    color: tuple
    accessory: str
    size: float


@dataclass
class Song:
    path: str
    title: str
    subtitle: str
    lehrplan: str
    description: str
    width: int
    height: int
    fps: int
    bpm: float
    key: str
    seed: int
    audio: Optional[str]
    timing: str
    intro_bars: int
    outro_bars: int
    gap_bars: int
    font: Optional[str]
    characters: List[Character]
    sections: List[Section]
    lines: List[Line] = field(default_factory=list)
    intro_end: float = 0.0
    total: float = 0.0

    @property
    def syllables(self):
        return [s for ln in self.lines for s in ln.syllables]

    @property
    def beat(self):
        return 60.0 / self.bpm


def _hex(c):
    c = str(c).lstrip("#")
    if len(c) != 6:
        raise ConfigError("Farbe muss #RRGGBB sein: %s" % c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def split_syllables(text, line_idx):
    out = []
    for word in text.split():
        word = word.replace("--", "\x00")
        parts = [p.replace("\x00", "-") for p in word.split("-") if p != ""]
        for i, p in enumerate(parts):
            out.append(Syllable(text=p, word_end=(i == len(parts) - 1), line=line_idx))
    return out


def load(path, overrides=None):
    path = os.path.abspath(path)
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    if overrides:
        d.update(overrides)
    base = os.path.dirname(path)

    def rel(p):
        if not p:
            return None
        p = os.path.expanduser(str(p))
        return p if os.path.isabs(p) else os.path.join(base, p)

    fmt = d.get("format", {}) or {}
    mus = d.get("musik", {}) or {}
    if "titel" not in d or "abschnitte" not in d:
        raise ConfigError("Pflichtfelder: titel, abschnitte")

    chars = []
    for i, c in enumerate(d.get("figuren") or [{} for _ in range(3)]):
        acc = c.get("accessoire", "keine")
        if acc not in ACCESSORIES:
            raise ConfigError("Unbekanntes Accessoire '%s' (erlaubt: %s)" % (acc, ", ".join(ACCESSORIES)))
        chars.append(Character(name=c.get("name", "Figur%d" % (i + 1)),
                               color=_hex(c.get("farbe", DEFAULT_COLORS[i % len(DEFAULT_COLORS)])),
                               accessory=acc, size=float(c.get("groesse", 1.0))))

    default_scene = d.get("szene", "nacht")
    sections, lines = [], []
    for si, s in enumerate(d["abschnitte"]):
        kind = s.get("typ", "strophe")
        scene = s.get("szene", default_scene)
        if scene not in SCENES:
            raise ConfigError("Unbekannte Szene '%s' (erlaubt: %s)" % (scene, ", ".join(SCENES)))
        eff = s.get("effekte", SCENE_DEFAULT_EFFECTS[scene] + (["konfetti"] if kind == "refrain" else []))
        for e in eff:
            if e not in EFFECTS:
                raise ConfigError("Unbekannter Effekt '%s' (erlaubt: %s)" % (e, ", ".join(EFFECTS)))
        choreo = s.get("choreo", "tanzen" if kind == "refrain" else "schweben")
        if choreo not in CHOREOS:
            raise ConfigError("Unbekannte Choreo '%s' (erlaubt: %s)" % (choreo, ", ".join(CHOREOS)))
        count = s.get("anzahl")
        if count is not None and not (0 <= int(count) <= len(chars)):
            raise ConfigError("anzahl %s in Abschnitt %d grösser als Anzahl Figuren" % (count, si + 1))
        sec = Section(index=si, kind=kind, scene=scene, effects=list(eff), choreo=choreo,
                      count=None if count is None else int(count),
                      show_number=bool(s.get("zahl_zeigen", count is not None)), lines=[])
        for txt in s.get("zeilen", []):
            ln = Line(text=" ".join(w.replace("--", "\x00").replace("-", "").replace("\x00", "-")
                                    for w in str(txt).split()),
                      syllables=split_syllables(str(txt), len(lines)), section=si)
            if not ln.syllables:
                continue
            sec.lines.append(ln)
            lines.append(ln)
        if not sec.lines:
            raise ConfigError("Abschnitt %d hat keine Zeilen" % (si + 1))
        sections.append(sec)

    timing = str(d.get("timing", "auto"))
    song = Song(path=path, title=str(d["titel"]), subtitle=str(d.get("untertitel", "")),
                lehrplan=str(d.get("lehrplan", "")), description=str(d.get("beschreibung", "")),
                width=int(fmt.get("breite", 1920)), height=int(fmt.get("hoehe", 1080)),
                fps=int(fmt.get("fps", 30)), bpm=float(mus.get("bpm", 100)),
                key=str(mus.get("tonart", "C")), seed=int(mus.get("seed", 1)),
                audio=rel(d.get("audio")), timing=timing,
                intro_bars=int(d.get("intro_takte", 2)), outro_bars=int(d.get("outro_takte", 2)),
                gap_bars=int(d.get("zwischenspiel_takte", 1)), font=rel(d.get("schrift")),
                characters=chars, sections=sections, lines=lines)
    if song.audio and not os.path.exists(song.audio):
        raise ConfigError("Audiodatei nicht gefunden: %s" % song.audio)
    return song
