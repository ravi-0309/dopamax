"""
One-time helper: generate PNG app icons for the iOS home screen.

Run once (free):
    pip install pillow
    python make_icon.py

It writes static/icon-180.png, icon-192.png and icon-512.png.
You don't strictly need this — the app already ships an SVG icon — but
iOS shows a sharper home-screen icon when a real PNG is present.
"""
from PIL import Image, ImageDraw

SIZE = 512
C1 = (76, 201, 240)    # cyan
C2 = (139, 124, 246)   # violet
C3 = (192, 132, 252)   # purple


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build():
    img = Image.new("RGB", (SIZE, SIZE))
    px = img.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = (x + y) / (2 * SIZE)
            px[x, y] = lerp(C1, C2, t / 0.5) if t < 0.5 else lerp(C2, C3, (t - 0.5) / 0.5)
    d = ImageDraw.Draw(img)
    bolt = [(300, 68), (158, 282), (250, 282), (212, 448), (364, 224), (276, 224)]
    d.polygon(bolt, fill=(255, 255, 255))
    return img


if __name__ == "__main__":
    base = build()
    for s in (180, 192, 512):
        base.resize((s, s), Image.LANCZOS).save(f"static/icon-{s}.png")
    print("Wrote static/icon-180.png, icon-192.png, icon-512.png")
