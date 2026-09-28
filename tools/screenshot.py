"""Write a PNG of the desktop (DISPLAY :1) to stdout, for rosdev screenshot."""

import argparse
import io
import os
import sys

from PIL import ImageGrab

ap = argparse.ArgumentParser()
ap.add_argument("--region", help="X,Y,WIDTH,HEIGHT in desktop pixels")
ap.add_argument("--scale", type=float, default=1.0, help="resize factor, e.g. 0.5")
a = ap.parse_args()
if not 0.05 <= a.scale <= 1.0:
    sys.exit("--scale must be between 0.05 and 1")

try:
    image = ImageGrab.grab(xdisplay=os.environ.get("DISPLAY") or ":1")
except OSError as e:
    sys.exit(f"Cannot capture the desktop ({e}). Is it running? Try: rosdev up")
if a.region:
    try:
        x, y, w, h = (int(v) for v in a.region.split(","))
    except ValueError:
        sys.exit("--region must be X,Y,WIDTH,HEIGHT")
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > image.width or y + h > image.height:
        sys.exit(f"--region must lie within the {image.width}x{image.height} desktop")
    image = image.crop((x, y, x + w, y + h))
if a.scale != 1.0:
    image = image.resize((max(1, round(image.width * a.scale)), max(1, round(image.height * a.scale))))
buffer = io.BytesIO()
image.save(buffer, "PNG", optimize=True)
sys.stdout.buffer.write(buffer.getvalue())
