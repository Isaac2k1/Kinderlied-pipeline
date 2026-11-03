"""Rendern: ein MP4 pro Abschnitt (parallel), dann verlustfrei zusammenfügen und Ton dazumischen."""
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

from . import music
from .director import Director


def segments(song):
    segs = [("intro", 0.0, song.intro_end)]
    for s in song.sections:
        segs.append(("%02d_%s" % (s.index + 1, s.kind), s.start, s.end))
    segs.append(("outro", song.sections[-1].end, song.total))
    return [(n, a, b) for n, a, b in segs if b - a > 0.05]


def _frame_range(song, a, b):
    fps = song.fps
    return int(round(a * fps)), int(round(b * fps))


def _encode(song, a, b, path, log=None):
    f0, f1 = _frame_range(song, a, b)
    if f1 <= f0:
        return path
    dr = Director(song)
    tmp = path[:-4] + ".tmp.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (song.width, song.height),
           "-r", str(song.fps), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-r", str(song.fps), tmp]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(f0, f1):
        ff.stdin.write(dr.frame(i / float(song.fps)).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg-Fehler in %s" % path)
    os.replace(tmp, path)
    return path


def _job(args):
    song, a, b, path = args
    _encode(song, a, b, path)
    return path


def render(song, out_path, only=None, workers=None):
    out_path = os.path.abspath(out_path)
    base = os.path.splitext(out_path)[0]
    segdir = base + "_segmente"
    os.makedirs(segdir, exist_ok=True)
    segs = segments(song)
    jobs, files = [], []
    for name, a, b in segs:
        p = os.path.join(segdir, name + ".mp4")
        files.append(p)
        if only is None or name in only or not os.path.exists(p):
            jobs.append((song, a, b, p))

    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    print("Rendere %d von %d Segmenten mit %d Prozessen ..." % (len(jobs), len(segs), workers), flush=True)
    if jobs:
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as ex:
            for i, p in enumerate(ex.map(_job, jobs), 1):
                print("  [%d/%d] %s" % (i, len(jobs), os.path.basename(p)), flush=True)

    # Ton
    if song.audio:
        audio = song.audio
    else:
        audio = base + "_musik.wav"
        music.render(song, audio)

    lst = os.path.join(segdir, "liste.txt")
    with open(lst, "w") as f:
        for p in files:
            f.write("file '%s'\n" % p.replace("'", "'\\''"))
    silent = os.path.join(segdir, "_video.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", silent], check=True)
    tmp = base + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", silent, "-i", audio,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-t", "%.3f" % song.total, "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out_path)
    return out_path


def stills(song, times, out_dir):
    dr = Director(song)
    paths = []
    for t in times:
        p = os.path.join(out_dir, "standbild_%06.2f.png" % t)
        dr.frame(t).save(p)
        paths.append(p)
    return paths


def description(song, path):
    lines = [song.title]
    if song.subtitle:
        lines.append(song.subtitle)
    lines.append("")
    if song.description:
        lines += [song.description.strip(), ""]
    if song.lehrplan:
        lines += ["Lehrplan 21: " + song.lehrplan, ""]
    lines.append("Liedtext zum Mitsingen:")
    for s in song.sections:
        lines.append("")
        lines.append("[%s]" % s.kind.capitalize())
        lines += [ln.text for ln in s.lines]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg nicht gefunden (macOS: brew install ffmpeg)")
