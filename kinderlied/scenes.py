"""Szenen-Presets: nacht, tag, herbst, winter. Statische Ebenen werden einmal gezeichnet und gecacht;
alle Koordinaten sind auf 1920x1080 bezogen und werden mit S skaliert."""
import math

import numpy as np
from PIL import Image, ImageDraw

PRESETS = {
    "nacht": dict(sky=((14, 18, 52), (62, 40, 98)), far=(44, 34, 86), near=(24, 20, 52),
                  body="moon", stars=True, clouds=False, silhouette=(16, 13, 36),
                  foliage=None, trunk=None, roof=None, wall=None, window=(255, 205, 120),
                  flowers=False, snow=False, tree="laub"),
    "tag": dict(sky=((96, 180, 250), (205, 236, 255)), far=(128, 204, 116), near=(84, 172, 84),
                body="sun", stars=False, clouds=True, silhouette=None,
                foliage=[(76, 160, 70), (98, 184, 84)], trunk=(120, 80, 50), roof=(214, 84, 70),
                wall=(250, 236, 210), window=(140, 200, 255), flowers=True, snow=False, tree="laub"),
    "herbst": dict(sky=((250, 170, 120), (255, 226, 176)), far=(214, 140, 80), near=(160, 96, 52),
                   body="sun_low", stars=False, clouds=True, silhouette=None,
                   foliage=[(232, 120, 40), (210, 70, 40), (240, 180, 60)], trunk=(100, 64, 40),
                   roof=(150, 60, 50), wall=(240, 220, 190), window=(255, 210, 120),
                   flowers=False, snow=False, tree="laub"),
    "winter": dict(sky=((150, 186, 228), (226, 238, 250)), far=(220, 232, 248), near=(246, 249, 255),
                   body="sun_pale", stars=False, clouds=True, silhouette=None,
                   foliage=[(44, 110, 84), (56, 128, 96)], trunk=(90, 64, 44), roof=(250, 252, 255),
                   wall=(200, 120, 90), window=(255, 214, 130), flowers=False, snow=True, tree="tanne"),
}


def glow_sprite(r, color, strength=1.0):
    s = max(4, int(r * 4))
    yy, xx = np.mgrid[0:s, 0:s] - s / 2.0
    d = np.sqrt(xx ** 2 + yy ** 2) / (s / 2.0)
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


class Scene:
    def __init__(self, name, W, H, seed=7):
        self.name, self.W, self.H = name, W, H
        self.S = S = W / 1920.0
        self.p = p = PRESETS[name]
        rng = np.random.default_rng(seed)
        y = np.linspace(0, 1, H)[:, None]
        top, bot = np.array(p["sky"][0]), np.array(p["sky"][1])
        g = top + (bot - top) * y ** 1.3
        self.sky = Image.fromarray(np.repeat(g[:, None, :], W, axis=1).reshape(H, W, 3).astype(np.uint8)).convert("RGBA")
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H * .62), rng.uniform(1.2, 3.2) * S,
                       rng.uniform(0, 6.28), rng.uniform(1.5, 4)) for _ in range(140)] if p["stars"] else []
        self.body = self._body()
        self.far = self._hills(p["far"], 760, 70, 1, W + int(400 * S))
        self.near = self._hills(p["near"], 880, 50, 2, W + int(900 * S), flowers=p["flowers"])
        self.props = self._props()
        self.clouds = []
        if p["clouds"]:
            cs = self._cloud()
            for i in range(4):
                self.clouds.append((cs, rng.uniform(0, W), rng.uniform(60, 330) * S, rng.uniform(8, 22) * S,
                                    rng.uniform(0.6, 1.1)))
        self.win_glow = glow_sprite(70 * S, p["window"], 0.7 if name == "nacht" else 0.35)

    # ---------- statische Teile ----------
    def _body(self):
        S, kind = self.S, self.p["body"]
        if kind == "moon":
            m = Image.new("RGBA", (int(260 * S), int(260 * S)), (0, 0, 0, 0))
            d = ImageDraw.Draw(m)
            d.ellipse((10 * S, 10 * S, 250 * S, 250 * S), fill=(255, 246, 214, 255))
            for cx, cy, r in [(90, 100, 26), (170, 160, 18), (150, 80, 12), (95, 185, 14)]:
                d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=(236, 224, 190, 255))
            return dict(img=m, glow=glow_sprite(260 * S, (255, 240, 200), .55), pos=(1500, 180), rays=False)
        col = {"sun": (255, 222, 90), "sun_low": (255, 190, 90), "sun_pale": (255, 246, 210)}[kind]
        pos = {"sun": (1560, 190), "sun_low": (1500, 420), "sun_pale": (1500, 200)}[kind]
        m = Image.new("RGBA", (int(220 * S), int(220 * S)), (0, 0, 0, 0))
        ImageDraw.Draw(m).ellipse((10 * S, 10 * S, 210 * S, 210 * S), fill=col + (255,))
        return dict(img=m, glow=glow_sprite(240 * S, col, .6), pos=pos, rays=(kind == "sun"), col=col)

    def _hills(self, color, base, amp, seed, width, flowers=False):
        S, H = self.S, self.H
        r = np.random.default_rng(seed)
        img = Image.new("RGBA", (width, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        ph = r.uniform(0, 6, 3)

        def hy(xb):
            return base - amp * (0.55 * math.sin(xb / 310 + ph[0]) + 0.3 * math.sin(xb / 140 + ph[1])
                                 + 0.15 * math.sin(xb / 70 + ph[2]))
        pts = [(x, hy(x / S) * S) for x in range(0, width + 10, 10)]
        d.polygon(pts + [(width, H), (0, H)], fill=color + (255,))
        if flowers:
            cols = [(255, 255, 255), (255, 220, 80), (255, 140, 180), (200, 160, 255)]
            for i in range(160):
                xb = r.uniform(0, width / S)
                yb = hy(xb) + r.uniform(20, 160)
                c = cols[i % 4]
                rr = r.uniform(4, 7) * S
                d.ellipse((xb * S - rr, yb * S - rr, xb * S + rr, yb * S + rr), fill=c + (255,))
                d.ellipse((xb * S - rr / 3, yb * S - rr / 3, xb * S + rr / 3, yb * S + rr / 3), fill=(255, 200, 40, 255))
        return img

    def _cloud(self):
        S = self.S
        img = Image.new("RGBA", (int(320 * S), int(140 * S)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        col = (255, 255, 255, 220) if self.name != "herbst" else (255, 240, 225, 220)
        for cx, cy, r in [(90, 85, 50), (160, 65, 62), (230, 88, 48), (150, 100, 45)]:
            d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=col)
        return img

    def _props(self):
        S, p = self.S, self.p
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        def R(*v):
            return [x * S for x in v]
        sil = p["silhouette"]
        # Haus
        wall = sil or p["wall"]
        roof = sil or p["roof"]
        d.rectangle(R(1400, 700, 1640, 900), fill=wall + (255,))
        d.rectangle(R(1590, 610, 1620, 690), fill=(sil or (150, 90, 70)) + (255,))
        d.polygon([tuple(R(1380, 705)), tuple(R(1520, 590)), tuple(R(1660, 705))], fill=roof + (255,))
        if not sil:
            d.rectangle(R(1450, 800, 1490, 900), fill=(120, 80, 60, 255))  # Tür
        # Bäume
        trees = [(268, 920, 1.0), (520, 900, 0.7)] if p["tree"] == "laub" else [(260, 930, 1.0), (430, 915, .75), (560, 905, .6)]
        for i, (x, base, k) in enumerate(trees):
            tc = sil or p["trunk"]
            fc = [sil] if sil else p["foliage"]
            if p["tree"] == "laub":
                d.rectangle(R(x - 17 * k, base - 280 * k, x + 17 * k, base), fill=tc + (255,))
                for j, (dx, dy, r) in enumerate([(0, -320, 110), (-68, -260, 80), (67, -270, 85), (0, -400, 80)]):
                    c = fc[(i + j) % len(fc)]
                    d.ellipse(R(x + (dx - r) * k, base + (dy - r) * k, x + (dx + r) * k, base + (dy + r) * k), fill=c + (255,))
            else:
                d.rectangle(R(x - 14 * k, base - 60 * k, x + 14 * k, base), fill=tc + (255,))
                for j, (w, y0, y1) in enumerate([(130, -60, -200), (105, -150, -290), (75, -240, -370)]):
                    c = fc[j % len(fc)]
                    d.polygon([tuple(R(x - w * k, base + y0 * k)), tuple(R(x, base + y1 * k)), tuple(R(x + w * k, base + y0 * k))],
                              fill=c + (255,))
                    if p["snow"]:
                        d.polygon([tuple(R(x - w * .35 * k, base + (y1 + (y0 - y1) * .35) * k)), tuple(R(x, base + y1 * k)),
                                   tuple(R(x + w * .35 * k, base + (y1 + (y0 - y1) * .35) * k))], fill=(250, 252, 255, 255))
        return img

    # ---------- pro Frame ----------
    def draw(self, t, img=None):
        S, W = self.S, self.W
        img = self.sky.copy() if img is None else img
        d = ImageDraw.Draw(img)
        for sx, sy, sr, sp, sf in self.stars:
            tw = 0.55 + 0.45 * math.sin(t * sf + sp)
            r = sr * (0.7 + 0.3 * tw)
            c = int(160 + 95 * tw)
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(c, c, int(c * .9), 255))
        b = self.body
        bx, by = b["pos"][0] * S, (b["pos"][1] + 6 * math.sin(t * .5)) * S
        if b.get("rays"):
            for k in range(12):
                a = t * 0.3 + k * math.pi / 6
                r0, r1 = 125 * S, (165 + 12 * math.sin(t * 2 + k)) * S
                d.line((bx + r0 * math.cos(a), by + r0 * math.sin(a), bx + r1 * math.cos(a), by + r1 * math.sin(a)),
                       fill=b["col"] + (200,), width=max(2, int(10 * S)))
        g = b["glow"]
        img.alpha_composite(g, (int(bx - g.width / 2), int(by - g.height / 2)))
        m = b["img"]
        img.alpha_composite(m, (int(bx - m.width / 2), int(by - m.height / 2)))
        for cs, x0, y0, v, sc in self.clouds:
            x = (x0 + t * v) % (W + cs.width) - cs.width
            img.alpha_composite(cs, (int(x), int(y0)))
        u = 0.5 - 0.5 * math.cos(t * 0.06)  # langsames Hin- und Herschwenken, beliebig lange Lieder
        img.alpha_composite(self.far, (-int(u * (self.far.width - W)), 0))
        img.alpha_composite(self.props, (0, 0))
        wa = 0.75 + 0.25 * math.sin(t * 3)
        wg = self.win_glow.copy()
        wg.putalpha(wg.getchannel("A").point(lambda v: int(v * wa)))
        img.alpha_composite(wg, (int(1520 * S - wg.width / 2), int(780 * S - wg.height / 2)))
        d = ImageDraw.Draw(img)
        wc = self.p["window"]
        d.rectangle((1490 * S, 750 * S, 1550 * S, 810 * S), fill=wc + (255,))
        fr = self.p["silhouette"] or (255, 255, 255)
        d.line((1520 * S, 750 * S, 1520 * S, 810 * S), fill=fr + (255,), width=max(2, int(5 * S)))
        d.line((1490 * S, 780 * S, 1550 * S, 780 * S), fill=fr + (255,), width=max(2, int(5 * S)))
        img.alpha_composite(self.near, (-int(u * (self.near.width - W)), 0))
        return img
