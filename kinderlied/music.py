"""Platzhaltermusik: Melodie aus dem Liedtext generieren und synthetisieren (Glockenspiel, Bass, Pad, Beat).

Gleicher Abschnittstyp + gleiche Zeilenposition => gleiche Melodie (Strophen sind wiedererkennbar).
"""
import wave
import zlib

import numpy as np

SR = 44100
KEYS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11, "H": 11}
PENTA = [0, 2, 4, 7, 9]
PROG = {"strophe": [0, 5, 3, 4], "refrain": [3, 4, 0, 0], "intro": [0, 3, 4, 0]}
TRIADS = {0: [0, 4, 7], 2: [2, 5, 9], 3: [5, 9, 12], 4: [7, 11, 14], 5: [9, 12, 16]}
DEG_SEMI = {0: 0, 2: 4, 3: 5, 4: 7, 5: 9}


def _penta_note(idx, root):
    o, r = divmod(idx, 5)
    return root + 12 * o + PENTA[r]


def _template(kind, slot, seed):
    rng = np.random.default_rng(seed * 1000 + zlib.crc32(kind.encode()) % 997 + slot * 31)
    pos = int(rng.integers(3, 6))
    tpl = []
    for _ in range(16):
        tpl.append(pos)
        pos = int(np.clip(pos + rng.choice([-2, -1, -1, 0, 1, 1, 2]), 1, 8))
    return tpl


def compose(song):
    root = 60 + KEYS.get(song.key[:1].upper(), 0)
    for s in song.sections:
        for li, ln in enumerate(s.lines):
            tpl = _template(s.kind, li % 4, song.seed)
            n = len(ln.syllables)
            for j, syl in enumerate(ln.syllables):
                k = 0 if n == 1 else int(round(j / (n - 1.0) * 15))
                idx = tpl[k]
                if j == n - 1:
                    idx = 3 if li % 2 == 0 else 5  # Halbschluss auf G, Ganzschluss auf C
                syl.pitch = _penta_note(idx, root)


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


class _Mix:
    def __init__(self, dur):
        self.n = int(SR * dur)
        self.buf = np.zeros(self.n)

    def add(self, sig, t0):
        i = int(t0 * SR)
        if i >= self.n or i < 0:
            return
        j = min(self.n, i + len(sig))
        self.buf[i:j] += sig[: j - i]


def _bell(f, dur, amp):
    t = np.arange(int(SR * (dur + 0.6))) / SR
    env = np.exp(-t * 3.2) * np.minimum(1, t / 0.004)
    s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) * np.exp(-t * 6)
         + 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 9))
    return amp * s * env


def _pad(f, dur, amp):
    t = np.arange(int(SR * dur)) / SR
    env = np.minimum(1, t / 0.15) * np.minimum(1, np.maximum(0, dur - t) / 0.3)
    vib = 1 + 0.003 * np.sin(2 * np.pi * 5 * t)
    return amp * env * sum(np.sin(2 * np.pi * f * k * vib * t) / k ** 1.6 for k in range(1, 6))


def _bass(f, dur, amp):
    t = np.arange(int(SR * dur)) / SR
    return amp * np.sin(2 * np.pi * f * t) * np.exp(-t * 2.0) * np.minimum(1, t / 0.01)


_RNG = np.random.default_rng(5)
_NOISE = _RNG.standard_normal(SR)


def _hat(amp):
    t = np.arange(int(SR * 0.05)) / SR
    return amp * _NOISE[: len(t)] * np.exp(-t * 90)


def _clap(amp):
    t = np.arange(int(SR * 0.12)) / SR
    n = _NOISE[: len(t)] - np.roll(_NOISE[: len(t)], 1)
    return amp * n * np.exp(-t * 35)


def _kick(amp):
    t = np.arange(int(SR * 0.25)) / SR
    f = 110 * np.exp(-t * 18) + 45
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 12)


def render(song, out_path):
    compose(song)
    beat, bar = song.beat, song.beat * 4
    mix = _Mix(song.total)
    root = 48 + KEYS.get(song.key[:1].upper(), 0)

    for syl in song.syllables:
        mix.add(_bell(_hz(syl.pitch), syl.dur, 0.25), syl.start)

    for i, m in enumerate([84, 88, 91, 96]):
        mix.add(_bell(_hz(m + root - 48), 0.2, 0.08), 0.3 + i * 0.15)

    def kind_at(t):
        for s in song.sections:
            if s.start <= t < s.end:
                return s.kind
        return "intro"

    nbars = int(np.ceil(song.total / bar))
    for b in range(nbars):
        t0 = b * bar
        kind = kind_at(t0 + 0.01)
        prog = PROG.get(kind, PROG["strophe"])
        deg = prog[b % 4]
        chord = TRIADS[deg]
        dur = min(bar, song.total - t0)
        for c in chord:
            mix.add(_pad(_hz(root + 12 + c), dur, 0.07), t0)
        for k in range(4):
            tb = t0 + k * beat
            if tb >= song.total - 0.2:
                break
            mix.add(_bass(_hz(root - 12 + DEG_SEMI[deg]), beat * 0.9, 0.22), tb)
            if t0 >= song.intro_end:
                mix.add(_hat(0.03), tb + beat / 2)
                if k in (0, 2):
                    mix.add(_kick(0.18), tb)
                if kind == "refrain" and k in (1, 3):
                    mix.add(_clap(0.05), tb)

    buf = mix.buf
    fade = int(SR * 1.0)
    buf[-fade:] *= np.linspace(1, 0, fade)
    buf /= max(1e-9, np.max(np.abs(buf))) * 1.12
    pcm = (buf * 32767).astype(np.int16)
    st = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
    return out_path
