"""Dish photos for the built-in menu, from Wikimedia Commons (freely licensed), stored locally.

Run from apps/api:  python -m seed.photos [--only "Dal Makhani"] [--sheet out.jpg]

For each dish the script uses the pinned Commons file in PINNED when there is one, otherwise the first
search result that is a JPEG under CC0, public domain, CC BY or CC BY-SA. Each photo is centre-cropped
to 4:3, resized to 480 x 360 and saved as WebP in apps/web/public/dishes/<slug>.webp. Credits (author,
licence, source page) go to apps/web/public/dishes/credits.json; the Menu page links to them.
Photos are downloaded once, at setup; the app itself never contacts Wikimedia.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageOps

import settings
from seed.menu import MENU

OUT_DIR = settings.API_DIR.parent / "web" / "public" / "dishes"
API = "https://commons.wikimedia.org/w/api.php"
UA = "TadkaRestaurantApp/1.0 (offline restaurant software; one-time photo setup)"
SIZE = (480, 360)
FREE = re.compile(r"^(cc0|public domain|pd|cc by(-sa)?( \d\.\d)?|cc-by(-sa)?-\d\.\d)", re.I)

# Commons search words per dish (the dish name is used when a dish is not listed).
QUERIES: dict[str, str] = {
    "Chilli Paneer": "chilli paneer",
    "Veg Manchurian": "vegetable manchurian",
    "Hara Bhara Kabab": "hara bhara kabab",
    "Crispy Corn": "crispy corn kernels snack",
    "Veg Thali": "vegetarian thali",
    "Paneer Tikka Masala": "paneer tikka masala",
    "Mix Veg": "mixed vegetable curry indian",
    "Tandoori Roti": "tandoori roti",
    "Veg Fried Rice": "vegetable fried rice",
    "Steamed Rice": "steamed basmati rice bowl",
    "Green Salad": "green salad cucumber onion tomato",
    "Sizzling Brownie": "sizzling brownie ice cream",
    "Cold Drink": "cola glass ice",
    "Cold Coffee": "cold coffee glass",
    "Sweet Lassi": "lassi glass",
    "Masala Chaas": "chaas buttermilk",
    "Fresh Lime Soda": "lime soda glass",
}

# Specific Commons files chosen after review (file title without the "File:" prefix).
PINNED: dict[str, str] = {
    "Paneer Tikka Masala": "Paneer Tikka Masala (2026) 01.jpg",
    "Chicken Curry": "Chicken Curry (490198749).jpg",
    "Mix Veg": "Mixed vegetable curry 1.jpg",
    "Butter Naan": "Butter Naan Flatbread from North India.jpg",
    "Veg Biryani": "Dum veg biryani by fatima.jpg",
    "Chicken Biryani": "Chicken Dum Biryani 03.jpg",
    "Steamed Rice": "Steamed rice in bowl 01.jpg",
    "Cold Coffee": "Cold Coffee 2.jpg",
    "Fresh Lime Soda": "Nimbu Soda Or Lemon Soda.jpg",
    "Green Salad": "Indian Vegetable Salad.jpg",
}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _open(url: str, timeout: int = 60) -> bytes:
    """GET with a polite retry: Wikimedia answers 429 when asked too quickly."""
    for attempt in range(6):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == 5:
                raise
            wait = float(exc.headers.get("Retry-After") or 0) or 5 * 2 ** attempt
            print(f"  rate limited, waiting {wait:.0f} s", flush=True)
            time.sleep(min(wait, 120))
    raise RuntimeError("unreachable")


def _get(params: dict) -> dict:
    return json.loads(_open(API + "?" + urllib.parse.urlencode({**params, "format": "json"}), 30))


def _strip(html: str | None) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html or "")).strip()


def _info(pages: dict) -> list[dict]:
    out = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        ii = (page.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        lic = _strip(meta.get("LicenseShortName", {}).get("value"))
        out.append({
            "title": page["title"].removeprefix("File:"), "mime": ii.get("mime"), "width": ii.get("width", 0),
            "height": ii.get("height", 0), "thumb": ii.get("thumburl"), "page": ii.get("descriptionurl"),
            "license": lic, "license_url": _strip(meta.get("LicenseUrl", {}).get("value")) or None,
            "author": _strip(meta.get("Artist", {}).get("value"))[:120] or "Unknown",
        })
    return out


IIPROP = {"prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 800}


def candidates(query: str, limit: int = 12) -> list[dict]:
    data = _get({"action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{query} filetype:bitmap",
                 "gsrlimit": limit, **IIPROP})
    return _info((data.get("query") or {}).get("pages") or {})


def pinned(title: str) -> dict | None:
    data = _get({"action": "query", "titles": f"File:{title}", **IIPROP})
    found = _info((data.get("query") or {}).get("pages") or {})
    return found[0] if found and found[0]["thumb"] else None


def usable(c: dict) -> bool:
    return (c["mime"] == "image/jpeg" and c["width"] >= 600 and c["height"] >= 400 and bool(c["thumb"])
            and bool(FREE.match(c["license"] or "")))


def fetch(c: dict, dest: Path) -> None:
    img = Image.open(io.BytesIO(_open(c["thumb"]))).convert("RGB")
    ImageOps.fit(img, SIZE, Image.LANCZOS, centering=(0.5, 0.5)).save(dest, "WEBP", quality=80, method=6)


def contact_sheet(paths: list[tuple[str, Path]], out: Path) -> None:
    from PIL import ImageDraw
    cols, w, h = 6, 240, 210
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    draw = ImageDraw.Draw(sheet)
    for k, (name, p) in enumerate(paths):
        x, y = (k % cols) * w, (k // cols) * h
        if p.exists():
            sheet.paste(Image.open(p).resize((w - 8, 180)), (x + 4, y + 4))
        draw.text((x + 6, y + 188), name, fill="black")
    sheet.save(out, quality=85)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Download dish photos from Wikimedia Commons.")
    ap.add_argument("--only", action="append", help="dish name (repeatable); default all")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--sheet", type=Path, help="write a contact sheet of all dish photos here")
    ap.add_argument("--list", metavar="DISH", help="print usable candidates for one dish and stop")
    args = ap.parse_args(argv)
    if args.list:
        for c in candidates(QUERIES.get(args.list, args.list), 20):
            print(("OK " if usable(c) else "-- ") + f"{c['title']} | {c['license']} | {c['width']}x{c['height']}")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    credits_path = OUT_DIR / "credits.json"
    credits = json.loads(credits_path.read_text(encoding="utf-8")) if credits_path.exists() else {}
    dishes = [i.name for i in MENU if not args.only or i.name in args.only]
    for name in dishes:
        dest = OUT_DIR / f"{slug(name)}.webp"
        if args.skip_existing and dest.exists() and name in credits:
            continue
        choice = pinned(PINNED[name]) if name in PINNED else next(
            (c for c in candidates(QUERIES.get(name, name)) if usable(c)), None)
        if choice is None:
            print(f"no free photo found for {name}")
            continue
        fetch(choice, dest)
        credits[name] = {"file": f"/dishes/{dest.name}", "title": choice["title"], "author": choice["author"],
                         "license": choice["license"], "license_url": choice["license_url"], "source": choice["page"]}
        print(f"{name}: {choice['title']} ({choice['license']})", flush=True)
        credits_path.write_text(json.dumps(dict(sorted(credits.items())), indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
        time.sleep(2)  # be polite to the API
    if args.sheet:
        contact_sheet([(i.name, OUT_DIR / f"{slug(i.name)}.webp") for i in MENU], args.sheet)
        print(f"Contact sheet: {args.sheet}")


if __name__ == "__main__":
    main()
