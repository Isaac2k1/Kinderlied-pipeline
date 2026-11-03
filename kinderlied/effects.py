"""Zustandslose Partikeleffekte: Position = f(t). Damit lässt sich jedes Segment unabhängig rendern."""
import math

import numpy as np
from PIL import ImageDraw

from .scenes import glow_sprite


class Effects:
    def __init__(self, W, H, seed=11):
        self.W, self.H, self.S = W, H, W / 1920.0
        r = np.random.default_rng(seed)
        self.p = {k: r.uniform(0, 1, (n, 6)) for k, n in
                  [("schnee", 140), ("blaetter", 28), ("regen", 120), ("gluehwuermchen", 26),
                   ("konfetti", 70), ("funkeln", 30)]}
        self.ff_glow = glow_sprite(18 * self.S, (220, 255, 140), .9)

    def draw(self, img, names, t, alpha=1.0):
        if alpha <= 0:
            return
        d = ImageDraw.Draw(img)
        for n in names:
            getattr(self, "_" + n)(img, d, t, alpha)

    def _schnee(self, img, d, t, a):
        W, H, S = self.W, self.H, self.S
        for x0, y0, sp, sz, ph, _ in self.p["schnee"]:
            y = (y0 * H + t * (40 + 70 * sp) * S) % (H + 20) - 10
            x = (x0 * W + 25 * S * math.sin(t * (0.6 + sp) + ph * 6)) % W
            r = (2 + 4 * sz) * S
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, int(220 * a)))

    def _blaetter(self, img, d, t, a):
        W, H, S = self.W, self.H, self.S
        cols = [(232, 120, 40), (210, 70, 40), (240, 180, 60), (180, 90, 40)]
        for i, (x0, y0, sp, sz, ph, rot) in enumerate(self.p["blaetter"]):
            y = (y0 * H + t * (50 + 60 * sp) * S) % (H + 60) - 30
            x = (x0 * W + 60 * S * math.sin(t * (0.8 + sp) + ph * 6)) % W
            ang = t * (1 + 2 * rot) + ph * 6
            L, B = (16 + 10 * sz) * S, (8 + 5 * sz) * S
            ca, sa = math.cos(ang), math.sin(ang)
            pts = [(x + L * ca, y + L * sa), (x - B * sa, y + B * ca), (x - L * ca, y - L * sa), (x + B * sa, y - B * ca)]
            d.polygon(pts, fill=cols[i % 4] + (int(240 * a),))

    def _regen(self, img, d, t, a):
        W, H, S = self.W, self.H, self.S
        for x0, y0, sp, sz, _, _ in self.p["regen"]:
            y = (y0 * H + t * (900 + 300 * sp) * S) % (H + 40) - 20
            x = (x0 * W - (y * 0.15)) % W
            ln = (18 + 14 * sz) * S
            d.line((x, y, x - ln * .15, y + ln), fill=(200, 220, 255, int(150 * a)), width=max(1, int(2 * S)))

    def _gluehwuermchen(self, img, d, t, a):
        W, H, S = self.W, self.H, self.S
        g = self.ff_glow
        for x0, y0, sp, sz, ph, ph2 in self.p["gluehwuermchen"]:
            x = x0 * W + 90 * S * math.sin(t * (0.3 + 0.4 * sp) + ph * 6)
            y = (0.35 + 0.45 * y0) * H + 50 * S * math.sin(t * (0.5 + 0.3 * sz) + ph2 * 6)
            blink = max(0.0, math.sin(t * (1.2 + sp) + ph * 9))
            if blink < 0.05:
                continue
            gg = g.copy()
            gg.putalpha(gg.getchannel("A").point(lambda v: int(v * blink * a)))
            img.alpha_composite(gg, (int(x - g.width / 2), int(y - g.height / 2)))

    def _konfetti(self, img, d, t, a):
        W, H, S = self.W, self.H, self.S
        cols = [(255, 214, 102), (128, 230, 196), (255, 150, 190), (157, 184, 255), (255, 179, 107)]
        for i, (x0, y0, sp, sz, ph, rot) in enumerate(self.p["konfetti"]):
            y = (y0 * H + t * (80 + 90 * sp) * S) % (H * .8)
            x = (x0 * W + 40 * S * math.sin(t * 2 + ph * 6)) % W
            w = (6 + 4 * sz) * S * abs(math.cos(t * (3 + 3 * rot) + ph * 6))
            h = (10 + 4 * sz) * S
            d.rectangle((x - w, y - h / 2, x + w, y + h / 2), fill=cols[i % 5] + (int(220 * a),))

    def _funkeln(self, img, d, t, a):
        W, H, S = self.W, self.H, self.S
        for x0, y0, sp, sz, ph, _ in self.p["funkeln"]:
            k = max(0.0, math.sin(t * (1.5 + sp) + ph * 6)) ** 3
            if k < 0.05:
                continue
            x, y = x0 * W, (0.08 + 0.55 * y0) * H
            r = (6 + 10 * sz) * S * k
            c = (255, 255, 240, int(230 * k * a))
            d.line((x - r, y, x + r, y), fill=c, width=max(1, int(3 * S)))
            d.line((x, y - r, x, y + r), fill=c, width=max(1, int(3 * S)))
