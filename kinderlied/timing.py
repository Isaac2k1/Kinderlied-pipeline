"""Silben-Timings bestimmen.

timing: auto            -> Whisper, falls Audio + Whisper vorhanden, sonst generiert
timing: generiert       -> Rhythmus aus Takt/BPM (für Platzhaltermusik)
timing: labels:<datei>  -> Audacity-Textmarken (eine Marke pro Zeile, Start und Ende)
timing: whisper         -> Wort-Zeitstempel aus der Gesangsaufnahme (mlx-whisper oder faster-whisper)
"""
import difflib
import os
import re
import wave


def rhythm(n):
    """Dauern in Achteln für n Silben. Rückgabe (dauern, achtel_pro_zeile)."""
    if n <= 0:
        return [], 16
    slots = 16 if n <= 13 else 32
    if n <= 5:
        durs = [4] * (n - 1)
    else:
        durs = [2] * (n - 1)
    last = slots - sum(durs) - 2
    i = 0
    while last < 2 and i < len(durs):
        if durs[i] == 2:
            durs[i] = 1
        i += 1
        last = slots - sum(durs) - 2
    durs.append(max(2, last))
    return durs, slots


def _finalize(song, lead=None):
    secs = song.sections
    beat = song.beat
    lead = beat if lead is None else lead
    for k, s in enumerate(secs):
        first = s.lines[0].syllables[0].start
        if k == 0:
            s.start = max(0.0, first - lead)
        else:
            prev_last = secs[k - 1].lines[-1].syllables[-1]
            prev_end = prev_last.start + prev_last.dur
            s.start = max(prev_end, (prev_end + first) / 2.0, first - 2 * beat)
            secs[k - 1].end = s.start
    song.intro_end = secs[0].start
    last = secs[-1].lines[-1].syllables[-1]
    secs[-1].end = last.start + last.dur + beat
    if song.audio:
        song.total = max(secs[-1].end + 0.5, audio_duration(song.audio))
    else:
        song.total = secs[-1].end + song.outro_bars * 4 * beat
    secs[-1].end = min(secs[-1].end, song.total)


def audio_duration(path):
    if path.lower().endswith(".wav"):
        with wave.open(path) as w:
            return w.getnframes() / float(w.getframerate())
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def generated(song):
    beat = song.beat
    eighth = beat / 2
    t = song.intro_bars * 4 * beat
    for k, s in enumerate(song.sections):
        if k > 0:
            t += song.gap_bars * 4 * beat
        for ln in s.lines:
            durs, slots = rhythm(len(ln.syllables))
            pos = 0
            for syl, dd in zip(ln.syllables, durs):
                syl.start = t + pos * eighth
                syl.dur = dd * eighth
                pos += dd
            t += slots * eighth
    _finalize(song)


def _spread(line, t0, t1):
    durs, slots = rhythm(len(line.syllables))
    used = float(sum(durs))
    span = max(0.2, t1 - t0)
    pos = 0
    for syl, dd in zip(line.syllables, durs):
        syl.start = t0 + span * pos / used
        syl.dur = span * dd / used
        pos += dd


def labels(song, path):
    marks = []
    with open(path, encoding="utf-8") as f:
        for row in f:
            p = row.strip().split("\t")
            if len(p) >= 2 and re.match(r"^[\d.]+$", p[0]):
                marks.append((float(p[0]), float(p[1])))
    if len(marks) < len(song.lines):
        raise ValueError("Labels-Datei hat %d Marken, Lied hat %d Zeilen" % (len(marks), len(song.lines)))
    for ln, (a, b) in zip(song.lines, marks):
        if b <= a:
            b = a + 2.0
        _spread(ln, a, b)
    _finalize(song)


def _norm(w):
    w = w.lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss")):
        w = w.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", w)


def _transcribe(audio):
    try:
        import mlx_whisper  # Apple Silicon
        r = mlx_whisper.transcribe(audio, path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                                   language="de", word_timestamps=True)
        return [(w["word"], w["start"], w["end"]) for seg in r["segments"] for w in seg.get("words", [])]
    except ImportError:
        pass
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3", compute_type="int8")
        segs, _ = model.transcribe(audio, language="de", word_timestamps=True)
        return [(w.word, w.start, w.end) for s in segs for w in (s.words or [])]
    except ImportError:
        return None


def whisper(song):
    words = _transcribe(song.audio)
    if not words:
        raise RuntimeError("Whisper nicht installiert: pip install mlx-whisper (Mac) oder faster-whisper")
    # Liedwörter mit ihren Silben
    lyric = []
    for ln in song.lines:
        cur = []
        for syl in ln.syllables:
            cur.append(syl)
            if syl.word_end:
                lyric.append(("".join(x.text for x in cur), cur))
                cur = []
    a = [_norm(w) for w, _ in lyric]
    b = [_norm(w[0]) for w in words]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    times = [None] * len(lyric)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            _, ws, we = words[blk.b + k]
            times[blk.a + k] = (ws, we)
    # Lücken linear interpolieren
    known = [i for i, x in enumerate(times) if x]
    if not known:
        raise RuntimeError("Kein Liedwort in der Transkription gefunden")
    for i in range(len(times)):
        if times[i]:
            continue
        lo = max([k for k in known if k < i], default=None)
        hi = min([k for k in known if k > i], default=None)
        if lo is None:
            t1 = times[hi][0]
            times[i] = (t1 - 0.4 * (hi - i), t1 - 0.4 * (hi - i) + 0.35)
        elif hi is None:
            t0 = times[lo][1]
            times[i] = (t0 + 0.4 * (i - lo - 1), t0 + 0.4 * (i - lo))
        else:
            f = (i - lo) / float(hi - lo)
            t = times[lo][1] + f * (times[hi][0] - times[lo][1])
            times[i] = (t, t + 0.3)
    for (word, syls), (ws, we) in zip(lyric, times):
        letters = [max(1, len(s.text)) for s in syls]
        tot = float(sum(letters))
        t = ws
        for s, n in zip(syls, letters):
            s.start = t
            s.dur = max(0.08, (we - ws) * n / tot)
            t += s.dur
    _finalize(song, lead=0.8)


def apply(song):
    mode = song.timing
    if mode.startswith("labels:"):
        p = mode.split(":", 1)[1]
        p = p if os.path.isabs(p) else os.path.join(os.path.dirname(song.path), p)
        labels(song, p)
        return "labels"
    if mode == "whisper" or (mode == "auto" and song.audio):
        if mode == "auto":
            try:
                whisper(song)
                return "whisper"
            except RuntimeError:
                pass
        else:
            whisper(song)
            return "whisper"
    if song.audio and mode == "auto":
        raise RuntimeError("Audio angegeben, aber kein Timing möglich: Whisper installieren "
                           "oder timing: labels:<datei> setzen")
    generated(song)
    return "generiert"
