"""Demo-Inserate für Vorführungen – lokal, mit der echten Extension prüfbar.

    python demo/server.py            # http://kleinanzeigen.localhost:8090/

Die Extension erkennt neben kleinanzeigen.de auch kleinanzeigen.localhost (Browser leiten *.localhost
auf den eigenen Rechner). Inhalte frei erfunden, Fotos werden beim Start gezeichnet. Das PS5-Foto
steht als Demo-Eintrag in data/lexicons/known_fake_image_hashes.txt („bekanntes Betrugsbild“).
Server dazu wie immer: scamguard start (bzw. scamguard api).
"""

from __future__ import annotations

import argparse
import io
import math
from datetime import date, timedelta
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
HOST = "kleinanzeigen.localhost"

# Pfad → (Vorlage, Platzhalter); Kontoalter relativ zu heute, damit die Demo an jedem Tag gleich wirkt
PAGES = {
    "/s-anzeige/winterraeder-17-zoll-alufelgen/3000000001-223-0001": ("haendler.html", {"ACTIVE_SINCE": 2100}),
    "/s-anzeige/playstation-5-slim-neu-ovp/3000000002-279-0002": ("ps5.html", {"ACTIVE_SINCE": 0}),
}


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)))
    return img


def draw_ps5() -> Image.Image:
    """Konsole im Produktfoto-Stil: weiße Seitenteile, schwarzer Kern, Schatten auf heller Fläche."""
    img = _gradient((800, 600), (236, 240, 246), (204, 212, 224))
    shadow = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow).ellipse((250, 500, 560, 545), fill=120)
    img.paste((150, 158, 170), mask=shadow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((372, 90, 432, 515), radius=18, fill=(28, 30, 36))          # Kern
    d.rounded_rectangle((300, 70, 380, 520), radius=40, fill=(250, 250, 252))        # Seitenteil links
    d.rounded_rectangle((424, 70, 504, 520), radius=40, fill=(244, 245, 248))        # Seitenteil rechts
    d.rounded_rectangle((310, 85, 330, 505), radius=10, fill=(255, 255, 255))        # Glanzkante
    d.rounded_rectangle((395, 120, 409, 180), radius=6, fill=(60, 120, 230))         # Leuchtstreifen
    d.ellipse((392, 470, 412, 490), fill=(70, 74, 82))                               # Taste
    d.rounded_rectangle((330, 515, 474, 530), radius=6, fill=(40, 42, 48))           # Standfuß
    return img


def draw_wheels(variant: int) -> Image.Image:
    """Vier Kompletträder in der Werkstatt."""
    img = _gradient((800, 600), (88, 92, 98), (52, 54, 58))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 470, 800, 600), fill=(70, 72, 76))
    offset = variant * 18
    for i, cx in enumerate((150, 320, 490, 660)):
        cy = 330 + (i % 2) * 12 - offset // 3
        d.ellipse((cx - 115, cy - 115, cx + 115, cy + 115), fill=(22, 22, 24))      # Reifen
        d.ellipse((cx - 72, cy - 72, cx + 72, cy + 72), fill=(196, 200, 206))       # Felge
        d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(150, 156, 164))
        for k in range(5):                                                         # Speichen
            a = math.radians(k * 72 + offset)
            d.line((cx, cy, cx + 60 * math.cos(a), cy + 60 * math.sin(a)), fill=(214, 218, 224), width=14)
        d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(60, 62, 66))          # Nabe
    return img


@cache
def image_bytes(name: str) -> bytes | None:
    drawings = {"ps5": draw_ps5, **{f"raeder-{i}": (lambda i=i: draw_wheels(i)) for i in range(1, 4)}}
    if name not in drawings:
        return None
    buf = io.BytesIO()
    drawings[name]().save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def render(template: str, values: dict[str, int]) -> bytes:
    html = (HERE / "seiten" / template).read_text(encoding="utf-8")
    for key, days in values.items():
        html = html.replace("{{" + key + "}}", (date.today() - timedelta(days=days)).strftime("%d.%m.%Y"))
    return html.encode("utf-8")


def index() -> bytes:
    links = "".join(f'<li><a href="{path}">{path.split("/")[2]}</a></li>' for path in PAGES)
    return (f'<!doctype html><meta charset="utf-8"><title>ScamGuard-Demo</title>'
            f'<link rel="stylesheet" href="/style.css"><main class="index"><h1>Demo-Inserate</h1>'
            f"<ul>{links}</ul></main>").encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in PAGES:
            self._send(200, "text/html; charset=utf-8", render(*PAGES[path]))
        elif path == "/":
            self._send(200, "text/html; charset=utf-8", index())
        elif path == "/style.css":
            self._send(200, "text/css; charset=utf-8", (HERE / "seiten" / "style.css").read_bytes())
        elif path.startswith("/bilder/") and (body := image_bytes(path.removeprefix("/bilder/").removesuffix(".jpg"))):
            self._send(200, "image/jpeg", body)
        else:
            self._send(404, "text/plain; charset=utf-8", b"Nicht Teil der Demo")

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # leise
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Demo-Inserate: http://{HOST}:{args.port}/  (Beenden mit Ctrl+C)")
    for path in PAGES:
        print(f"  http://{HOST}:{args.port}{path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
