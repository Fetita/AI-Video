"""Tile PNG stills into a labeled contact sheet: python3 contact_sheet.py out.png cols w img1 img2 ..."""
import sys
from PIL import Image, ImageDraw
out, cols, w = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
files = sys.argv[4:]
hh = int(w * 9 / 16)
rows = (len(files) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w + (cols + 1) * 8, rows * (hh + 26) + 8), (30, 30, 34))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB').resize((w, hh), Image.LANCZOS)
    x, y = 8 + (i % cols) * (w + 8), 8 + (i // cols) * (hh + 26)
    sheet.paste(im, (x, y))
    d.text((x + 4, y + hh + 6), f.split('/')[-1], fill=(200, 200, 200))
sheet.save(out)
print(out)
