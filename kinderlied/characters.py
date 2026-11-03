"""Figuren: runde Leuchtwesen mit Gesicht, Mund singt mit, Accessoires (flamme, blatt, muetze, ohren)."""
import math

from PIL import Image, ImageDraw

from .scenes import glow_sprite


def light(c, f):
    return tuple(min(255, int(v + (255 - v) * f)) for v in c)


def dark(c, f):
    return tuple(int(v * (1 - f)) for v in c)


class CharacterArt:
    def __init__(self, ch, S, night=True):
        self.ch = ch
        self.r = 64 * S * ch.size
        self.S = S
        self.glow = glow_sprite(self.r * 1.6, ch.color, 0.8 if night else 0.35)

    def draw(self, img, x, y, t, mouth=0.0, blink=1.0, phase=0.0, squash=0.0):
        r, ch = self.r, self.ch
        g = self.glow
        img.alpha_composite(g, (int(x - g.width / 2), int(y - g.height / 2)))
        size = int(r * 3.6)
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        ox = oy = size / 2.0
        oy += r * 0.25
        rx, ry = r * (1 + squash * 0.12), r * (1 - squash * 0.12)
        col = ch.color
        acc = ch.accessory
        # Accessoires hinter dem Körper
        if acc == "ohren":
            for sx in (-1, 1):
                ex, ey, er = ox + sx * rx * .62, oy - ry * .78, r * .36
                d.ellipse((ex - er, ey - er, ex + er, ey + er), fill=dark(col, .15))
                d.ellipse((ex - er * .55, ey - er * .55, ex + er * .55, ey + er * .55), fill=(255, 170, 190))
        if acc == "flamme":
            fl = 0.85 + 0.15 * math.sin(t * 9 + phase)
            d.polygon([(ox - r * .28, oy - ry * .82), (ox + r * .05 * math.sin(t * 5 + phase), oy - ry * 1.55 * fl),
                       (ox + r * .28, oy - ry * .82)], fill=light(col, .55))
        if acc == "blatt":
            sw = math.sin(t * 2.5 + phase) * .25
            d.line((ox, oy - ry * .9, ox + r * .08, oy - ry * 1.25), fill=(110, 80, 50), width=max(2, int(r * .08)))
            lx, ly = ox + r * .1, oy - ry * 1.25
            pts = [(lx, ly), (lx + r * (.45 + sw * .3), ly - r * .32), (lx + r * .75, ly - r * .05 + sw * r * .2),
                   (lx + r * .35, ly + r * .08)]
            d.polygon(pts, fill=(96, 176, 80))
        # Körper
        d.ellipse((ox - rx, oy - ry, ox + rx, oy + ry), fill=col)
        d.ellipse((ox - rx * .62, oy - ry * .78, ox + rx * .1, oy - ry * .2), fill=light(col, .45))
        if acc == "muetze":
            hc = dark(col, .35)
            d.chord((ox - rx * 1.02, oy - ry * 1.08, ox + rx * 1.02, oy + ry * .25), 180, 360, fill=hc)
            d.rectangle((ox - rx * 1.0, oy - ry * .48, ox + rx * 1.0, oy - ry * .32), fill=(255, 255, 255))
            pr = r * .2
            d.ellipse((ox - pr, oy - ry * 1.12 - pr, ox + pr, oy - ry * 1.12 + pr), fill=(255, 255, 255))
        # Augen
        ey = oy - ry * .02 + (r * .1 if acc == "muetze" else 0)
        ew, eh = r * .13, r * .2 * blink
        for ex in (ox - rx * .32, ox + rx * .32):
            d.ellipse((ex - ew, ey - eh, ex + ew, ey + eh), fill=(40, 30, 60))
            if blink > .6:
                d.ellipse((ex - ew * .2, ey - eh * .7, ex + ew * .6, ey - eh * .1), fill=(255, 255, 255))
        for ex in (ox - rx * .55, ox + rx * .55):
            d.ellipse((ex - r * .14, ey + r * .2, ex + r * .14, ey + r * .36), fill=(255, 120, 140, 150))
        # Mund
        my = ey + r * .3
        if mouth > 0.08:
            # fröhlicher, offener Mund (Halbkreis, flache Oberkante)
            mw, mh = r * (.2 + .04 * mouth), r * (.12 + .2 * mouth)
            top = my - r * .12
            d.chord((ox - mw, top - mh, ox + mw, top + mh), 0, 180, fill=(70, 30, 50))
            d.chord((ox - mw * .55, top + mh * .35, ox + mw * .55, top + mh * 1.0), 180, 360, fill=(255, 130, 150))
        else:
            d.arc((ox - r * .22, ey + r * .08, ox + r * .22, ey + r * .42), 20, 160, fill=(40, 30, 60),
                  width=max(3, int(r * .07)))
        img.alpha_composite(layer, (int(x - ox), int(y - oy)))
