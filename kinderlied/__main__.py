"""Aufruf:
  python -m kinderlied render  songs/lied.yaml [--vorschau] [--nur 03_refrain,outro] [--out datei.mp4]
  python -m kinderlied bilder  songs/lied.yaml 3.5 12 20.2 [--vorschau]
  python -m kinderlied info    songs/lied.yaml
"""
import argparse
import os
import sys
import time

from . import config, render, timing


def _load(args):
    ov = {}
    if args.vorschau:
        ov["format"] = {"breite": 960, "hoehe": 540, "fps": 24}
    song = config.load(args.lied, ov)
    mode = timing.apply(song)
    return song, mode


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kinderlied", description="Animierte Kinderlied-Videos aus YAML-Konfiguration")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("render", "bilder", "info"):
        p = sub.add_parser(name)
        p.add_argument("lied", help="Liedkonfiguration (.yaml)")
        p.add_argument("--vorschau", action="store_true", help="960x540, 24 fps – schnell zum Prüfen")
        if name == "render":
            p.add_argument("--out", help="Ausgabedatei (Standard: neben der YAML-Datei)")
            p.add_argument("--nur", help="nur diese Segmente neu rendern, z.B. 03_refrain,outro")
            p.add_argument("--prozesse", type=int, help="Anzahl paralleler Prozesse")
        if name == "bilder":
            p.add_argument("zeiten", nargs="+", type=float, help="Zeitpunkte in Sekunden")
    args = ap.parse_args(argv)

    try:
        song, mode = _load(args)
    except (config.ConfigError, RuntimeError, ValueError) as e:
        sys.exit("Fehler: %s" % e)

    stem = os.path.splitext(args.lied)[0] + ("_vorschau" if args.vorschau else "")

    if args.cmd == "info":
        print("%s  (%s, Timing: %s, %.1f s, %d BPM)" % (song.title, song.lehrplan or "-", mode, song.total, song.bpm))
        print("  %-14s %7.2f – %7.2f" % ("intro", 0.0, song.intro_end))
        for s in song.sections:
            print("  %-14s %7.2f – %7.2f  szene=%-7s choreo=%-8s anzahl=%s  effekte=%s" % (
                "%02d_%s" % (s.index + 1, s.kind), s.start, s.end, s.scene, s.choreo,
                "-" if s.count is None else s.count, ",".join(s.effects)))
        print("  %-14s %7.2f – %7.2f" % ("outro", song.sections[-1].end, song.total))
        return

    render.check_ffmpeg()
    if args.cmd == "bilder":
        out_dir = os.path.dirname(os.path.abspath(args.lied))
        for p in render.stills(song, args.zeiten, out_dir):
            print(p)
        return

    out = args.out or stem + ".mp4"
    t0 = time.time()
    only = set(args.nur.split(",")) if args.nur else None
    path = render.render(song, out, only=only, workers=args.prozesse)
    desc = render.description(song, os.path.splitext(path)[0] + "_beschreibung.txt")
    print("Fertig in %.0f s: %s" % (time.time() - t0, path))
    print("Beschreibungstext: %s" % desc)


if __name__ == "__main__":
    main()
