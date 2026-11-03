"""Regie: erzeugt aus dem Liedaufbau den Ablauf (Auftritte, Choreografien, Zählmechanik, Szenenwechsel,
Kamerafahrt, Karaoke-Text) und setzt daraus jedes Bild zusammen. Alles ist eine reine Funktion der Zeit t."""
import bisect
import math
import os

from PIL import Image, ImageDraw, ImageFont

from .characters import CharacterArt
from .effects import Effects
from .scenes import Scene

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

BASE_Y = 450.0
XFADE = 0.8       # Szenen-Überblendung (s)
BLEND = 0.9       # Choreo-Übergang (s)
LEAVE = 1.6       # Abflug-Dauer (s)
ENTER = 1.2       # Auftritt-Dauer (s)


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def find_font(song):
    for f in ([song.font] if song.font else []) + FONT_CANDIDATES:
        if f and os.path.exists(f):
            return f
    # Fallback über fontconfig (z.B. NixOS, wo es kein /usr/share/fonts gibt)
    import subprocess
    for pattern in ("DejaVu Sans:bold", "sans-serif:bold"):
        try:
            r = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True)
            f = r.stdout.strip()
            if r.returncode == 0 and f.lower().endswith((".ttf", ".otf")) and os.path.exists(f):
                return f
        except OSError:
            break
    raise RuntimeError("Keine Schrift gefunden – 'schrift:' in der Liedkonfiguration setzen")


class Director:
    def __init__(self, song):
        self.song = song
        self.W, self.H = song.width, song.height
        self.S = S = song.width / 1920.0
        self.scenes = {}
        for s in song.sections:
            if s.scene not in self.scenes:
                self.scenes[s.scene] = Scene(s.scene, self.W, self.H)
        self.fx = Effects(self.W, self.H)
        self.arts = [CharacterArt(c, S, night=False) for c in song.characters]
        self.arts_night = [CharacterArt(c, S, night=True) for c in song.characters]
        ff = find_font(song)
        self.f_title = ImageFont.truetype(ff, int(96 * S))
        self.f_sub = ImageFont.truetype(ff, int(42 * S))
        self.f_num = ImageFont.truetype(ff, int(120 * S))
        self.font_path = ff
        self._lyr_fonts = {}
        self.onsets = [syl.start for syl in song.syllables]
        self.syls = song.syllables
        self.nchar = len(song.characters)
        self.pages = self._pages()
        self._scaled = {}

    # ---------- Zeitachse ----------
    def section_at(self, t):
        secs = self.song.sections
        if t < secs[0].start:
            return -1
        for s in secs:
            if t < s.end:
                return s.index
        return len(secs)  # Outro

    def count_of(self, k):
        secs = self.song.sections
        if k < 0:
            k = 0
        if k >= len(secs):
            k = len(secs) - 1
        c = secs[k].count
        return self.nchar if c is None else c

    def scene_of(self, k):
        secs = self.song.sections
        return secs[min(max(k, 0), len(secs) - 1)].scene

    def mode_of(self, k):
        secs = self.song.sections
        if k < 0:
            return "schweben"
        if k >= len(secs):
            return "reihe"
        return secs[k].choreo

    # ---------- Choreografie ----------
    def _slot(self, j, n):
        if n <= 1:
            return 960.0
        span = min(1200.0, 260.0 * (n - 1))
        return 960 - span / 2 + span * j / (n - 1.0)

    def _scale(self, n):
        if n <= 1:
            return 1.0
        span = min(1200.0, 260.0 * (n - 1))
        return min(1.0, (span / (n - 1.0)) / 150.0)

    def _mode_pos(self, mode, j, n, t):
        beat = self.song.beat
        ph = j * 1.7
        slot = self._slot(j, n)
        sq = 0.0
        if mode == "tanzen":
            hop = abs(math.sin(math.pi * t / beat + (j % 2) * math.pi / 2))
            x = slot + 30 * math.sin(2 * math.pi * t / (4 * beat) + ph)
            y = BASE_Y + 40 - 90 * hop
            sq = max(0.0, 1 - hop * 4) * 1.0 - max(0.0, hop - 0.7)
        elif mode == "kreis":
            a = 2 * math.pi * t / (8 * beat) + 2 * math.pi * j / max(1, n)
            x = 960 + min(480, 120 + 70 * n) * math.cos(a)
            y = BASE_Y + 120 * math.sin(a)
        elif mode == "reihe":
            x = slot + 20 * math.sin(t * 0.8 + ph)
            y = BASE_Y + 45 * math.sin(2 * math.pi * t / (2 * beat) - j * 0.8)
        else:  # schweben
            x = slot + 50 * math.sin(t * 0.45 + ph)
            y = BASE_Y + 55 * math.sin(t * 1.05 + ph) + 12 * abs(math.sin(math.pi * t / beat))
        return x, y, sq

    def char_state(self, j, t):
        """(x, y, squash, scale) in Basis-Koordinaten oder None, wenn die Figur nicht im Bild ist."""
        song = self.song
        secs = song.sections
        k = self.section_at(t)
        kk = min(max(k, 0), len(secs) - 1)
        n = self.count_of(k)
        n_prev = self.count_of(k - 1) if k > 0 else n
        n_next = self.count_of(k + 1) if k + 1 < len(secs) else n
        start = 0.0 if k < 0 else (secs[k].start if k < len(secs) else secs[-1].end)
        end = secs[kk].end if 0 <= k < len(secs) else song.total

        # Auftritt im Intro
        if k < 0:
            if j >= n:
                return None
            t_in = 0.4 + j * 0.3
            e = ease_out((t - t_in) / ENTER)
            if e <= 0:
                return None
            x, y, sq = self._mode_pos("schweben", j, n, t)
            return x, y + (1 - e) * 800, sq, self._scale(n)

        if j >= n:
            return None

        x, y, sq = self._mode_pos(self.mode_of(k), j, n, t)
        sc = self._scale(n)
        # weicher Übergang von der vorherigen Choreografie (bzw. vom Intro)
        if t - start < BLEND:
            w = smooth((t - start) / BLEND)
            px, py, psq = self._mode_pos(self.mode_of(k - 1), min(j, max(0, n_prev - 1)), n_prev, t)
            x, y, sq = px + (x - px) * w, py + (y - py) * w, psq + (sq - psq) * w
            sc = self._scale(n_prev) + (sc - self._scale(n_prev)) * w
        # Zähllied: neue Figuren kommen dazu
        if k < len(secs) and n > n_prev and j >= n_prev:
            e = ease_out((t - start) / ENTER)
            y += (1 - e) * 800
        # Zähllied: Figuren fliegen am Abschnittsende davon
        if k < len(secs) and n_next < n and j >= n_next:
            e = (t - (end - LEAVE)) / LEAVE
            if e > 0:
                e = e * e
                y -= e * 900
                x += e * 160 * (1 if j % 2 else -1)
        return x, y, sq, sc

    # ---------- Hilfen ----------
    def mouth(self, t):
        i = bisect.bisect_right(self.onsets, t) - 1
        if i < 0:
            return 0.0
        syl = self.syls[i]
        if t > syl.start + syl.dur + 0.05:
            return 0.0
        return max(0.25, 1 - (t - syl.start) / 0.3)

    def zoom(self, t):
        z = 1.0
        for s in self.song.sections:
            if s.kind == "refrain":
                z += 0.05 * smooth((t - s.start) / 1.5) * smooth((s.end - t) / 1.5)
        return z

    def _pages(self):
        """Je zwei Zeilen pro Seite. Eine Seite erscheint frühestens, wenn die vorherige ausgesungen ist."""
        pages = []
        for s in self.song.sections:
            ls = s.lines
            for i in range(0, len(ls), 2):
                pages.append((s.index, ls[i:i + 2]))
        starts = []
        prev_end = -1e9
        for si, lines in pages:
            sec = self.song.sections[si]
            t0 = max(sec.start, lines[0].syllables[0].start - 1.0, prev_end + 0.1)
            starts.append(t0)
            last = lines[-1].syllables[-1]
            prev_end = last.start + last.dur
        out = []
        for i, (si, lines) in enumerate(pages):
            sec = self.song.sections[si]
            if i + 1 < len(pages):
                t1 = starts[i + 1] if pages[i + 1][0] == si else min(starts[i + 1], sec.end)
            else:
                t1 = sec.end
            out.append([starts[i], t1, lines, True, True])
        for i in range(len(out) - 1):  # direkt anschliessende Seiten ohne Aus-/Einblenden
            if abs(out[i][1] - out[i + 1][0]) < 1e-6:
                out[i][4] = False
                out[i + 1][3] = False
        return out

    def lyr_font(self, px):
        px = int(px)
        if px not in self._lyr_fonts:
            self._lyr_fonts[px] = ImageFont.truetype(self.font_path, px)
        return self._lyr_fonts[px]

    # ---------- Bild ----------
    def world(self, scene_name, k, t):
        sc = self.scenes[scene_name]
        img = sc.draw(t)
        secs = self.song.sections
        eff = secs[min(max(k, 0), len(secs) - 1)].effects
        self.fx.draw(img, eff, t)
        return img

    def frame(self, t):
        S, W, H = self.S, self.W, self.H
        song = self.song
        secs = song.sections
        k = self.section_at(t)
        kk = min(max(k, 0), len(secs) - 1)
        img = self.world(self.scene_of(k), kk, t)
        if 0 < k < len(secs) and secs[k].scene != secs[k - 1].scene and t - secs[k].start < XFADE:
            prev = self.world(secs[k - 1].scene, k - 1, t)
            img = Image.blend(prev, img, smooth((t - secs[k].start) / XFADE))
        night = self.scene_of(k) == "nacht"
        arts = self.arts_night if night else self.arts
        mouth = self.mouth(t)
        states = []
        for j in range(self.nchar):
            st = self.char_state(j, t)
            if st:
                states.append((st[1], j, st))
        d = ImageDraw.Draw(img)
        for _, j, (x, y, sq, scl) in sorted(states):  # Funkenspur
            col = song.characters[j].color
            for q in range(1, 7):
                ps = self.char_state(j, t - q * 0.07)
                if not ps:
                    continue
                r = (6 - q * .7) * S
                py = ps[1] + 60 * ps[3] + q * 6
                a = int(200 * (1 - q / 7.0))
                d.ellipse((ps[0] * S - r, py * S - r, ps[0] * S + r, py * S + r),
                          fill=tuple(min(255, c + 80) for c in col) + (a,))
        for _, j, (x, y, sq, scl) in sorted(states):
            art = arts[j]
            if abs(scl - 1.0) > 0.02:
                key = (j, round(scl, 2), night)
                if key not in self._scaled:
                    self._scaled[key] = CharacterArt(song.characters[j], S * round(scl, 2), night)
                art = self._scaled[key]
            blink = 1.0
            bp = (t * 0.23 + j * 0.37) % 1.0
            if bp < 0.025:
                blink = max(0.1, abs(bp - 0.0125) / 0.0125)
            art.draw(img, x * S, y * S, t, mouth=mouth, blink=blink, phase=j * 1.3, squash=sq)

        z = self.zoom(t)
        if z > 1.001:
            cw, ch = W / z, H / z
            cx = min(max(960 * S, cw / 2), W - cw / 2)
            cy = min(max(470 * S, ch / 2), H - ch / 2)
            box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
            img = img.resize((W, H), Image.BILINEAR, box=box)

        self._number(img, t, k)
        self._title(img, t)
        self._lyrics(img, t)
        fade = min(1.0, t / 0.5, (song.total - t) / 1.2)
        out = img.convert("RGB")
        if fade < 1:
            out = Image.eval(out, lambda v: int(v * max(0.0, fade)))
        return out

    def _number(self, img, t, k):
        secs = self.song.sections
        if not (0 <= k < len(secs)) or not secs[k].show_number:
            return
        s = secs[k]
        n = self.count_of(k)
        S = self.S
        pop = ease_out((t - s.start) / 0.5)
        over = 1 + 0.25 * math.sin(min(1.0, (t - s.start) / 0.5) * math.pi)
        r = 85 * S * pop * over
        if r < 2:
            return
        cx, cy = 150 * S, 150 * S
        d = ImageDraw.Draw(img)
        d.ellipse((cx - r, cy - r + 6 * S, cx + r, cy + r + 6 * S), fill=(0, 0, 0, 70))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 235))
        d.ellipse((cx - r * .86, cy - r * .86, cx + r * .86, cy + r * .86), outline=(255, 190, 70, 255),
                  width=max(2, int(8 * S)))
        txt = str(n)
        f = self.f_num
        bb = d.textbbox((0, 0), txt, font=f)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if pop > 0.6:
            d.text((cx - w / 2 - bb[0], cy - h / 2 - bb[1]), txt, font=f, fill=(70, 50, 110, 255))

    def _band(self, img, a):
        """Halbtransparentes Textband unten (gleich gross für Titel und Liedtext, damit nichts springt)."""
        S, W, H = self.S, self.W, self.H
        box_h = int(108 * S * 2 + 44 * S)
        y0 = int(H - box_h - 36 * S)
        band = Image.new("RGBA", (W, box_h), (10, 8, 30, int(150 * a)))
        img.alpha_composite(band, (0, y0))
        return y0

    def _title(self, img, t):
        song, S = self.song, self.S
        last = song.sections[-1].end
        first_page = self.pages[0][0] if self.pages else song.intro_end
        if t < first_page:
            a = min(1.0, t / 0.6, (first_page - t) / 0.4)
        elif t > last:
            a = min(1.0, (t - last) / 0.6)
        else:
            return
        if a <= 0:
            return
        y0 = self._band(img, a)
        d = ImageDraw.Draw(img)
        lift = 12 * S * (1 - a)
        self._center(d, song.title, self.f_title, y0 + 24 * S + lift, (255, 236, 170), a, shadow=True)
        if song.subtitle:
            self._center(d, song.subtitle, self.f_sub, y0 + 160 * S + lift, (235, 225, 255), a)

    def _center(self, d, s, f, y, col, a, shadow=False):
        w = d.textlength(s, font=f)
        x = (self.W - w) / 2
        if shadow:
            d.text((x + 4 * self.S, y + 5 * self.S), s, font=f, fill=(0, 0, 0, int(120 * a)))
        d.text((x, y), s, font=f, fill=col + (int(255 * a),))

    def _lyrics(self, img, t):
        S, W, H = self.S, self.W, self.H
        for t0, t1, lines, fin, fout in self.pages:
            if not (t0 <= t < t1):
                continue
            a = min(1.0, (t - t0) / 0.3 if fin else 1.0, (t1 - t) / 0.3 if fout else 1.0)
            d = ImageDraw.Draw(img)
            lh = 108 * S
            y0 = self._band(img, a)
            for li, ln in enumerate(lines):
                parts = [(s.text + (" " if s.word_end else ""), s.start) for s in ln.syllables]
                px = 64 * S
                f = self.lyr_font(px)
                total = sum(d.textlength(p, font=f) for p, _ in parts)
                if total > W * 0.92:
                    px = px * W * 0.92 / total
                    f = self.lyr_font(px)
                    total = sum(d.textlength(p, font=f) for p, _ in parts)
                x = (W - total) / 2
                y = y0 + 28 * S + li * lh + (2 - len(lines)) * lh / 2
                for p, ts in parts:
                    done = t >= ts
                    col = (255, 214, 102) if done else (255, 255, 255)
                    lift = -6 * S if ts <= t < ts + 0.22 else 0
                    d.text((x + 3 * S, y + 4 * S + lift), p, font=f, fill=(0, 0, 0, int(130 * a)))
                    d.text((x, y + lift), p, font=f, fill=col + (int(255 * a),))
                    x += d.textlength(p, font=f)
