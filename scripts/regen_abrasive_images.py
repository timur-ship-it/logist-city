#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

CATALOG_DIR = Path('/tmp/catalogue_pages')
OUT_DIR = Path('/tmp/netlify-deploy/images')
PREVIEW_DIR = Path('/tmp/netlify-deploy/tmp_previews')
TARGET_SIZE = 400


@dataclass(frozen=True)
class CropSpec:
    src: str
    box: Tuple[float, float, float, float]
    mode: str = 'largest'  # largest | row
    note: str = ''


# Primary + fallback candidate for each abrasive card.
# If primary crop quality is poor, generator automatically uses fallback.
ABR_SPECS: Dict[int, List[CropSpec]] = {
    1: [
        CropSpec('tbaw-03.jpg', (0.20, 0.17, 0.34, 0.30), 'largest', 'steel cut-off set'),
        CropSpec('cumi-08.jpg', (0.12, 0.30, 0.28, 0.43), 'largest', 'fallback from CUMI cutting row'),
    ],
    2: [
        CropSpec('tbaw-03.jpg', (0.73, 0.16, 0.85, 0.35), 'largest', 'steel cut-off flush-style view'),
        CropSpec('cumi-08.jpg', (0.28, 0.30, 0.45, 0.43), 'largest', 'fallback from CUMI cutting row'),
    ],
    3: [
        CropSpec('tbaw-04.jpg', (0.11, 0.16, 0.31, 0.37), 'largest', 'large diameter steel cut-off'),
        CropSpec('cumi-08.jpg', (0.10, 0.46, 0.31, 0.60), 'largest', 'fallback from CUMI large diameter row'),
    ],
    4: [
        CropSpec('tbaw-04.jpg', (0.61, 0.16, 0.81, 0.37), 'largest', 'railway cut-off wheel'),
        CropSpec('cumi-08.jpg', (0.69, 0.46, 0.90, 0.60), 'largest', 'fallback from CUMI large diameter row'),
    ],
    5: [
        CropSpec('tbaw-05.jpg', (0.35, 0.16, 0.48, 0.31), 'largest', 'steel grinding wheel'),
        CropSpec('cumi-08.jpg', (0.11, 0.12, 0.30, 0.25), 'largest', 'fallback from CUMI grinding row'),
    ],
    6: [
        CropSpec('tbaw-05.jpg', (0.58, 0.16, 0.74, 0.35), 'largest', 'ultra-thin inox cut-off'),
        CropSpec('cumi-08.jpg', (0.12, 0.70, 0.30, 0.87), 'largest', 'fallback from CUMI ultra-thin row'),
    ],
    7: [
        CropSpec('tbaw-06.jpg', (0.02, 0.20, 0.18, 0.34), 'largest', 'inox cut-off set'),
        CropSpec('cumi-08.jpg', (0.44, 0.30, 0.61, 0.43), 'largest', 'fallback from CUMI cutting row'),
    ],
    8: [
        CropSpec('tbaw-06.jpg', (0.04, 0.73, 0.16, 0.96), 'largest', 'inox cut-off (depressed center style)'),
        CropSpec('cumi-08.jpg', (0.30, 0.30, 0.47, 0.43), 'largest', 'fallback from CUMI cutting row'),
    ],
    9: [
        CropSpec('tbaw-07.jpg', (0.22, 0.14, 0.43, 0.35), 'largest', 'inox grinding wheel'),
        CropSpec('cumi-08.jpg', (0.28, 0.12, 0.46, 0.25), 'largest', 'fallback from CUMI grinding row'),
    ],
    10: [
        CropSpec('tbaw-07.jpg', (0.54, 0.25, 0.66, 0.47), 'largest', 'stone cut-off wheel'),
        CropSpec('cumi-08.jpg', (0.61, 0.30, 0.79, 0.43), 'largest', 'fallback from CUMI cutting row'),
    ],
    11: [
        CropSpec('tbaw-07.jpg', (0.54, 0.47, 0.66, 0.66), 'largest', 'stone cut-off (depressed center set)'),
        CropSpec('cumi-08.jpg', (0.61, 0.30, 0.79, 0.43), 'largest', 'fallback from CUMI cutting row'),
    ],
    12: [
        CropSpec('tbaw-08.jpg', (0.18, 0.14, 0.40, 0.40), 'largest', 'stone large diameter cut-off'),
        CropSpec('cumi-08.jpg', (0.69, 0.46, 0.90, 0.60), 'largest', 'fallback from CUMI large diameter row'),
    ],
    13: [
        CropSpec('tbaw-08.jpg', (0.65, 0.14, 0.86, 0.36), 'largest', 'stone grinding wheel'),
        CropSpec('cumi-08.jpg', (0.61, 0.12, 0.80, 0.25), 'largest', 'fallback from CUMI grinding row'),
    ],
    14: [
        CropSpec('tbaw-09.jpg', (0.03, 0.13, 0.24, 0.32), 'largest', 'flexible grinding discs'),
        CropSpec('cumi-12.jpg', (0.08, 0.74, 0.46, 0.93), 'largest', 'fallback from CUMI flap row'),
    ],
    15: [
        CropSpec('tbaw-09.jpg', (0.55, 0.16, 0.64, 0.34), 'largest', 'flap disc (universal)'),
        CropSpec('cumi-12.jpg', (0.08, 0.74, 0.46, 0.93), 'largest', 'fallback from CUMI flap row'),
    ],
    16: [
        CropSpec('tbaw-10.jpg', (0.02, 0.15, 0.23, 0.38), 'largest', 'flap disc T29 (aggressive)'),
        CropSpec('tbaw-09.jpg', (0.54, 0.16, 0.71, 0.35), 'largest', 'fallback from TBAW flap page'),
    ],
    17: [
        CropSpec('tbaw-10.jpg', (0.54, 0.24, 0.74, 0.40), 'largest', 'flower impeller flap disc'),
        CropSpec('tbaw-09.jpg', (0.54, 0.64, 0.80, 0.95), 'largest', 'fallback from TBAW flap assortment'),
    ],
    18: [
        CropSpec('cumi-12.jpg', (0.08, 0.23, 0.22, 0.36), 'largest', 'fiber disc (ceramic sample)'),
        CropSpec('tbaw-09.jpg', (0.03, 0.55, 0.35, 0.95), 'largest', 'fallback from TBAW mixed disc set'),
    ],
    19: [
        CropSpec('tbaw-10.jpg', (0.56, 0.54, 0.74, 0.72), 'row', 'stick&strip / velcro discs'),
        CropSpec('cumi-12.jpg', (0.08, 0.45, 0.87, 0.58), 'row', 'fallback from CUMI stick&strip row'),
    ],
    20: [
        CropSpec('cumi-14.jpg', (0.10, 0.12, 0.25, 0.30), 'largest', 'diamond cutting disc (segmented sample)'),
        CropSpec('cumi-14.jpg', (0.25, 0.12, 0.40, 0.30), 'largest', 'fallback from CUMI continuous rim'),
    ],
    21: [
        CropSpec('cumi-14.jpg', (0.10, 0.44, 0.25, 0.60), 'largest', 'cup wheel (segmented sample)'),
        CropSpec('cumi-14.jpg', (0.25, 0.44, 0.40, 0.60), 'largest', 'fallback from CUMI cup wheel row'),
    ],
}


def crop_rel(page: Image.Image, rel: Tuple[float, float, float, float]) -> Image.Image:
    w, h = page.size
    x0, y0, x1, y1 = rel
    return page.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))


def trim_nonwhite(img: Image.Image, threshold: int = 244, pad: int = 4) -> Image.Image:
    arr = np.asarray(img.convert('RGB'))
    mask = np.any(arr < threshold, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img
    l = max(int(xs.min()) - pad, 0)
    r = min(int(xs.max()) + pad + 1, img.width)
    t = max(int(ys.min()) - pad, 0)
    b = min(int(ys.max()) + pad + 1, img.height)
    return img.crop((l, t, r, b))


def largest_component_crop(img: Image.Image, threshold: int = 244, pad: int = 8) -> Image.Image:
    arr = np.asarray(img.convert('RGB'))
    gray = arr.min(axis=2)
    mask = (gray < threshold).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    comp_count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if comp_count <= 1:
        return trim_nonwhite(img, threshold=threshold, pad=pad)

    best = None
    h, w = mask.shape
    min_area = max(40, int(w * h * 0.0025))

    for i in range(1, comp_count):
        x, y, ww, hh, area = stats[i]
        if area < min_area:
            continue
        aspect = max(ww / max(hh, 1), hh / max(ww, 1))
        roundish_bonus = 1.5 if aspect < 1.6 else 1.0
        score = area * roundish_bonus
        if best is None or score > best[0]:
            best = (score, (x, y, ww, hh))

    if best is None:
        return trim_nonwhite(img, threshold=threshold, pad=pad)

    x, y, ww, hh = best[1]
    l = max(x - pad, 0)
    t = max(y - pad, 0)
    r = min(x + ww + pad, w)
    b = min(y + hh + pad, h)
    return img.crop((l, t, r, b))


def render_square(img: Image.Image, size: int = TARGET_SIZE, pad: int = 18) -> Image.Image:
    canvas = Image.new('RGB', (size, size), 'white')
    obj = img.convert('RGB')
    obj.thumbnail((size - 2 * pad, size - 2 * pad), Image.Resampling.LANCZOS)
    ox = (size - obj.width) // 2
    oy = (size - obj.height) // 2
    canvas.paste(obj, (ox, oy))
    return canvas


def quality_ok(extracted: Image.Image) -> bool:
    arr = np.asarray(extracted.convert('RGB'))
    nonwhite = float(np.any(arr < 245, axis=2).mean())
    short_side = min(extracted.width, extracted.height)
    return short_side >= 70 and nonwhite >= 0.01


def extract_from_spec(spec: CropSpec) -> Tuple[Image.Image, Dict[str, float]]:
    page = Image.open(CATALOG_DIR / spec.src).convert('RGB')
    raw = crop_rel(page, spec.box)

    if spec.mode == 'largest':
        extracted = largest_component_crop(raw)
    else:
        extracted = trim_nonwhite(raw)

    arr = np.asarray(extracted.convert('RGB'))
    meta = {
        'w': int(extracted.width),
        'h': int(extracted.height),
        'nonwhite': round(float(np.any(arr < 245, axis=2).mean()), 4),
    }
    return extracted, meta


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    audit = []
    cards: List[Image.Image] = []

    for idx in range(1, 22):
        specs = ABR_SPECS[idx]
        chosen_img = None
        chosen_spec = None
        chosen_meta = None
        fallback_used = False

        for cand_i, spec in enumerate(specs):
            extracted, meta = extract_from_spec(spec)
            if quality_ok(extracted) or cand_i == len(specs) - 1:
                chosen_img = extracted
                chosen_spec = spec
                chosen_meta = meta
                fallback_used = cand_i > 0
                break

        if chosen_img is None or chosen_spec is None or chosen_meta is None:
            raise RuntimeError(f'Failed to generate abr-{idx:03d}')

        out_img = render_square(chosen_img)
        out_path = OUT_DIR / f'abr-{idx:03d}.jpg'
        out_img.save(out_path, 'JPEG', quality=92)

        card = Image.new('RGB', (250, 276), '#f8fafc')
        thumb = out_img.resize((232, 232), Image.Resampling.LANCZOS)
        card.paste(thumb, (9, 7))
        draw = ImageDraw.Draw(card)
        draw.rectangle((0, 244, 249, 275), fill='#e2e8f0')
        draw.text((8, 249), f'abr-{idx:03d} {chosen_spec.src}', fill='black')
        cards.append(card)

        audit.append({
            'abr_id': idx,
            'output': out_path.name,
            'source_page': chosen_spec.src,
            'source_box': chosen_spec.box,
            'mode': chosen_spec.mode,
            'note': chosen_spec.note,
            'fallback_used': fallback_used,
            'crop_w': chosen_meta['w'],
            'crop_h': chosen_meta['h'],
            'nonwhite': chosen_meta['nonwhite'],
        })

    cols = 7
    rows = (len(cards) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 255 + 10, rows * 281 + 10), '#cbd5e1')
    for i, card in enumerate(cards):
        x = 5 + (i % cols) * 255
        y = 5 + (i // cols) * 281
        sheet.paste(card, (x, y))
    sheet_path = PREVIEW_DIR / 'abr_fallback_sheet.png'
    sheet.save(sheet_path)

    json_path = PREVIEW_DIR / 'abr_fallback_audit.json'
    csv_path = PREVIEW_DIR / 'abr_fallback_audit.csv'

    with json_path.open('w', encoding='utf-8') as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    with csv_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(audit[0].keys()))
        writer.writeheader()
        writer.writerows(audit)

    print('Regenerated abrasive images with primary/fallback pipeline.')
    print('Preview:', sheet_path)
    print('Audit :', csv_path)


if __name__ == '__main__':
    build()
