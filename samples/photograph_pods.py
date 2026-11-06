"""Turn the rendered sample PODs into phone-style photos, so the AI check meets something
closer to a real capture than a flat render: paper on a desk, a slight angle, uneven light,
a soft shadow, a little camera noise and JPEG compression.

These are synthetic photos, not photographs. The TDD says so: accuracy measured on them is
a first estimate, and real photos of printed sheets are the better test.

Usage (needs Pillow and numpy):
    python3 samples/photograph_pods.py

Reads samples/pods/scenarios.json and the rendered sheets beside it, and writes
samples/pods/photos/<scenario>.jpg, each under 300 KB. Each scenario uses a fixed seed,
so running it again gives the same photos.
"""

import io
import json
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

PODS = Path(__file__).resolve().parent / "pods"
OUT = PODS / "photos"
FRAME = (1200, 1600)  # 3:4, like a phone camera in portrait
MAX_BYTES = 300 * 1024


def perspective_coefficients(src, dst):
    """Coefficients for PIL's PERSPECTIVE transform, which maps output points back to input."""
    rows = []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(rows, dtype=float)
    b = np.array(src, dtype=float).reshape(8)
    return np.linalg.solve(a, b).tolist()


def desk(rng):
    """A warm grey desk surface with low-frequency mottling and fine grain."""
    w, h = FRAME
    small = rng.normal(0, 1, (h // 40, w // 40))
    mottle = np.array(Image.fromarray(((small - small.min()) / np.ptp(small) * 255).astype(np.uint8)).resize(FRAME, Image.BICUBIC), dtype=float) / 255
    base = np.array([118, 104, 92], dtype=float)  # warm grey-brown
    img = base[None, None, :] * (0.8 + 0.35 * mottle[..., None])
    img += rng.normal(0, 6, (h, w, 1))
    return np.clip(img, 0, 255)


def lighting(rng):
    """A light falloff from one side plus a vignette, as from a room light off to one side."""
    w, h = FRAME
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    cx, cy = w * rng.uniform(0.25, 0.75), h * rng.uniform(-0.2, 0.3)
    dist = np.sqrt(((xx - cx) / w) ** 2 + ((yy - cy) / h) ** 2)
    light = 1.08 - 0.32 * dist
    vignette = 1 - 0.18 * (((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2) * 2)
    return np.clip(light * vignette, 0.55, 1.1)[..., None]


def motion_blur(img, length, rng):
    """Average shifted copies along one direction, like a hand moving during the shot."""
    arr = np.asarray(img, dtype=float)
    angle = rng.uniform(0, np.pi)
    dx, dy = np.cos(angle), np.sin(angle)
    acc = np.zeros_like(arr)
    for i in range(length):
        t = i - length / 2
        acc += np.roll(np.roll(arr, int(round(t * dy)), axis=0), int(round(t * dx)), axis=1)
    return Image.fromarray(np.clip(acc / length, 0, 255).astype(np.uint8))


def photograph(sheet, seed, shaky):
    rng = np.random.default_rng(seed)
    w, h = FRAME

    # Where the sheet's corners land in the frame: about 82% of the height, a little skewed.
    sw, sh = sheet.size
    target_h = h * rng.uniform(0.80, 0.86)
    target_w = target_h * sw / sh
    x0, y0 = (w - target_w) / 2, (h - target_h) / 2
    jitter = lambda: rng.uniform(-0.035, 0.035) * w  # noqa: E731
    corners = [
        (x0 + jitter(), y0 + jitter()),
        (x0 + target_w + jitter(), y0 + jitter()),
        (x0 + target_w + jitter(), y0 + target_h + jitter()),
        (x0 + jitter(), y0 + target_h + jitter()),
    ]
    src = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
    coeffs = perspective_coefficients(src, corners)

    paper = sheet.convert("RGB").transform(FRAME, Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(0, 0, 0))
    mask = Image.new("L", sheet.size, 255).transform(FRAME, Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=0)

    # A soft shadow below and to one side of the sheet.
    shadow = mask.filter(ImageFilter.GaussianBlur(18))
    shadow = Image.fromarray(np.roll(np.roll(np.asarray(shadow), 14, axis=0), 9, axis=1))

    background = desk(rng)
    background *= 1 - 0.45 * (np.asarray(shadow, dtype=float)[..., None] / 255)

    paper_arr = np.asarray(paper, dtype=float) * np.array([0.97, 0.955, 0.93])  # paper isn't pure white
    m = np.asarray(mask, dtype=float)[..., None] / 255
    img = background * (1 - m) + paper_arr * m

    img *= lighting(rng)
    img += rng.normal(0, 3.5, img.shape)  # sensor noise
    photo = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

    photo = photo.filter(ImageFilter.GaussianBlur(0.7))  # a phone lens is never pin-sharp
    if shaky:
        photo = motion_blur(photo, length=int(rng.integers(16, 22)), rng=rng)
        photo = photo.filter(ImageFilter.GaussianBlur(1.6))
    return photo


def save_under_limit(photo, path):
    for quality in (82, 76, 70, 64, 58, 52):
        buf = io.BytesIO()
        photo.save(buf, "JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_BYTES:
            path.write_bytes(buf.getvalue())
            return quality, buf.tell()
    raise SystemExit(f"{path.name} is still over 300 KB at quality 52")


def main():
    OUT.mkdir(exist_ok=True)
    scenarios = json.loads((PODS / "scenarios.json").read_text())
    for scenario in scenarios:
        sheet = Image.open(PODS / scenario["image"])
        seed = zlib.crc32(scenario["id"].encode())
        photo = photograph(sheet, seed, shaky=scenario["id"] == "blurry")
        quality, size = save_under_limit(photo, OUT / f"{scenario['id']}.jpg")
        print(f"{scenario['id']:16} {size // 1024:4d} KB  (JPEG quality {quality})")


if __name__ == "__main__":
    main()
