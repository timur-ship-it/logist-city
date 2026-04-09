#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from PIL import Image

WORKBOOK = Path('/Users/Timur/Documents/New project/картинки каталог/new_and_out_of_range_apc2026_vs_wanna_simple.xlsx')
BY_HAND_DIR = Path('/Users/Timur/Documents/New project/картинки каталог/картинки apc2026/by hand')
OUT_IMG_DIR = Path('/tmp/netlify-deploy/images')
INDEX_HTML = Path('/tmp/netlify-deploy/index.html')
AUDIT_JSON = Path('/tmp/netlify-deploy/tmp_previews/apc_delta_rebuild_audit.json')

CARD_SIZE = 400
INNER_MAX = 340


TYPE_MAP = {
    'Valve Lapping Compound': 'Паста для притирки клапанов',
    'Snagging Wheels': 'Обдирочные круги',
    'Resinoid Cup Wheels': 'Бакелитовые чашечные круги',
    'Rubber Control Wheels': 'Резиновые контактные круги',
    'SIC Latex Waterproof Paper Sheet': 'Водостойкая латексная шлифшкурка SiC (лист)',
    'ALO Cabinet Paper': 'Шлифшкурка ALO для мебельных работ (лист)',
    'Emery Cloth Blue Drill Sheet': 'Наждачная ткань Blue Drill (лист)',
    'Emery Paper Sheet': 'Наждачная бумага (лист)',
    'Cloth Sheet': 'Шлифовальная ткань (лист)',
    'Flint Paper Sheet': 'Флинтовая шлифшкурка (лист)',
    'ALO Stearate Paper': 'Стеаратная шлифшкурка ALO (лист)',
    'ALO Resin Metal Cloth Roll': 'Шлифовальная ткань ALO на смоле по металлу (рулон)',
    'Sand Master Roll': 'Шлифовальный рулон Sand Master',
    'Concord Roll': 'Шлифовальный рулон Concord',
    'ALO Resin Industrial Cloth Roll': 'Промышленная шлифткань ALO на смоле (рулон)',
    'Emery Cloth Blue Drill Roll': 'Наждачная ткань Blue Drill (рулон)',
    'Emery Cloth Plain Weave Roll': 'Наждачная ткань полотняного плетения (рулон)',
    'Belts': 'Абразивные ленты',
    'Hand Pads and Rolls': 'Ручные пады и рулоны',
    'Discs': 'Нетканые абразивные диски',
    'Floor Pads': 'Напольные абразивные пады',
    'Hot Press Diamond Saws': 'Алмазные диски горячего прессования',
    'Laser Welded Saws': 'Лазерно-сварные алмазные диски',
    'Cup Wheels': 'Алмазные чашки',
}

FORM_MAP = {
    'Compound paste': 'Паста',
    'Wheel': 'Круг',
    'Cup wheel': 'Чашечный круг',
    'Control wheel': 'Контактный круг',
    'Sheet': 'Лист',
    'Roll': 'Рулон',
    'Belt': 'Лента',
    'Pad/Roll': 'Пад/рулон',
    'Disc': 'Диск',
    'Pad': 'Пад',
    'Segmented': 'Сегментный',
    'Continuous Rim': 'Сплошная кромка',
    'Rim Turbo': 'Турбо-кромка',
    'Turbo Segmented': 'Турбо-сегментный',
    'Segmented Cup Wheel': 'Сегментная чашка',
    'Continuous Rim Cup Wheel': 'Чашка со сплошной кромкой',
    'Turbo Cup Wheel': 'Турбо-чашка',
}

PHRASE_MAP = {
    'Used for polishing of Valve seats and discs': 'Притирка седел и тарелок клапанов',
    'for automobile body - putty and paint': 'Кузовные работы: шпатлевка и лакокрасочное покрытие',
    'Melamine, PU fillers, wood polishing': 'Меламиновые покрытия, ПУ-шпатлевки, полировка древесины',
    'Metal': 'Металл',
    'Wood, wall, metal': 'Древесина, стены, металл',
    'Wood and wall': 'Древесина и стены',
    'Wood, wall and filler': 'Древесина, стены и шпатлевка',
    'Sanding of plywood and furniture': 'Шлифование фанеры и мебельных деталей',
    'Furniture and construction': 'Мебельное и строительное производство',
    'Finishing of stainless steel surface and sheet metal fabrication': 'Финишная обработка нержавеющей стали и листового металла',
    'Metal and wood working': 'Обработка металла и древесины',
    'Brass, carbon steel, aluminium, stainless steel, wood': 'Латунь, углеродистая сталь, алюминий, нержавеющая сталь, древесина',
    'Brass, copper, carbon steel': 'Латунь, медь, углеродистая сталь',
    'Floor maintenance': 'Уход и обслуживание полов',
    'Ceramic/tile/stone cutting': 'Резка керамики, плитки и камня',
    'Heavy-duty cutting': 'Тяжелые режимы резки',
    'Surface grinding': 'Поверхностное шлифование',
    'Long, narrow and wide belts': 'Длинные, узкие и широкие ленты',
    'Various': 'Различные исполнения',
    'Used with angle grinders': 'Для УШМ (углошлифмашин)',
    'Runs at 175-350 rpm': 'Рабочая скорость 175-350 об/мин',
}

GRIT_MAP = {
    'Extra Coarse': 'очень крупное',
    'Coarse': 'крупное',
    'Medium': 'среднее',
    'Fine': 'мелкое',
    'Extra Coarse to Super Fine': 'от очень крупного до сверхмелкого',
    'Coarse to Extra Fine (24-220)': 'от крупного до очень мелкого (24-220)',
}


@dataclass
class Entry:
    idx: int
    id: int
    code: int
    raw_type: str
    raw_form: str
    image_source: Path
    image_output: str
    title_ru: str
    form_ru: str
    desc_ru: str
    search_text: str
    size_options: List[str]


def clean_str(value: object) -> str:
    if value is None:
        return ''
    out = str(value).strip()
    if out.lower() == 'nan':
        return ''
    return out


def normalize_dimension(text: str) -> str:
    t = clean_str(text)
    if not t:
        return ''
    if t in PHRASE_MAP:
        return PHRASE_MAP[t]

    t = re.sub(r'(?<=\d)\s*[xX]\s*(?=\d)', '×', t)
    t = re.sub(r'\b(\d+)\s*gm\b', r'\1 г', t, flags=re.IGNORECASE)
    t = re.sub(r'\bWidth\s+(\d+)\s+to\s+(\d+)\b', r'Ширина \1-\2 мм', t, flags=re.IGNORECASE)
    t = re.sub(r'\bSize\s+(\d+)\b', r'Размер \1', t, flags=re.IGNORECASE)
    t = re.sub(r'^\s*(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s*$', r'\1-\2 мм', t, flags=re.IGNORECASE)
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t


def translate_type(text: str) -> str:
    t = clean_str(text)
    return TYPE_MAP.get(t, t)


def translate_form(text: str) -> str:
    t = clean_str(text)
    return FORM_MAP.get(t, t)


def translate_material(text: str) -> str:
    t = clean_str(text)
    if not t:
        return ''
    return PHRASE_MAP.get(t, t)


def translate_grit(text: str) -> str:
    t = clean_str(text)
    if not t:
        return ''
    return GRIT_MAP.get(t, t)


def format_rpm(text: str) -> str:
    t = clean_str(text)
    if not t:
        return ''
    if re.fullmatch(r'[0-9]+(?:\s*[-–]\s*[0-9]+)?', t):
        return f'{t} об/мин'
    return t


def trim_nonwhite(img: Image.Image, threshold: int = 246, pad: int = 4) -> Image.Image:
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


def render_square(img: Image.Image, size: int = CARD_SIZE, inner_max: int = INNER_MAX) -> Image.Image:
    canvas = Image.new('RGB', (size, size), 'white')
    obj = img.convert('RGB')
    obj.thumbnail((inner_max, inner_max), Image.Resampling.LANCZOS)
    x = (size - obj.width) // 2
    y = (size - obj.height) // 2
    canvas.paste(obj, (x, y))
    return canvas


def replace_between_markers(text: str, start: str, end: str, new_block: str) -> str:
    if start not in text or end not in text:
        raise RuntimeError(f'Marker not found: {start} / {end}')
    i = text.index(start)
    j = text.index(end, i)
    return text[: i + len(start)] + '\n' + new_block.rstrip() + '\n' + text[j:]


def dedupe_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        v = clean_str(item)
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def build_size_option(row: pd.Series) -> str:
    parts: List[str] = []

    dim = normalize_dimension(row.get('Dimension DxTxH (mm)', ''))
    model = clean_str(row.get('PRODUCT CODE / MODEL', ''))
    grit = translate_grit(row.get('GRIT / GRADE', ''))
    rpm = format_rpm(row.get('MAX SPEED (R.P.M)', ''))

    if dim:
        parts.append(dim)
    if model:
        parts.append(f'модель {model}')
    if grit:
        parts.append(f'зерно {grit}')
    if rpm and rpm.lower() not in dim.lower():
        parts.append(f'макс. скорость {rpm}')

    return ' | '.join(parts)


def build() -> None:
    if not WORKBOOK.exists():
        raise FileNotFoundError(WORKBOOK)
    if not BY_HAND_DIR.exists():
        raise FileNotFoundError(BY_HAND_DIR)

    df = pd.read_excel(WORKBOOK, sheet_name='NEW').fillna('')
    df = df[df['status'].astype(str).str.upper() == 'NEW'].copy()

    grouped: OrderedDict[tuple, List[pd.Series]] = OrderedDict()
    for _, row in df.iterrows():
        key = (
            int(row['code']),
            clean_str(row['Тип']),
            clean_str(row['Форма']),
            clean_str(row['image_path']),
        )
        grouped.setdefault(key, []).append(row)

    grouped_items = sorted(
        grouped.items(),
        key=lambda kv: (kv[0][0], list(grouped.keys()).index(kv[0])),
    )

    by_hand_files = sorted(
        [p for p in BY_HAND_DIR.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )

    if len(grouped_items) != len(by_hand_files):
        raise RuntimeError(f'Card count mismatch: entries={len(grouped_items)} images={len(by_hand_files)}')

    code_counts = Counter(key[0] for key, _ in grouped_items)

    entries: List[Entry] = []
    size_options_map: Dict[str, List[str]] = {}
    audit_rows: List[dict] = []

    OUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON.parent.mkdir(parents=True, exist_ok=True)

    for idx, ((code, raw_type, raw_form, _raw_image_path), rows) in enumerate(grouped_items, start=1):
        card_id = 220 + idx
        image_src = by_hand_files[idx - 1]
        image_out_name = f'abr-apc-{card_id}.png'
        image_out_path = OUT_IMG_DIR / image_out_name

        img = Image.open(image_src).convert('RGB')
        img = trim_nonwhite(img)
        img = render_square(img)
        img.save(image_out_path, 'PNG', optimize=True)

        type_ru = translate_type(raw_type)
        form_ru = translate_form(raw_form)

        # Disambiguate titles for repeated APC code entries with different forms.
        if code_counts[code] > 1 and form_ru:
            title_ru = f'{type_ru} ({form_ru})'
        else:
            title_ru = type_ru

        material_values = dedupe_keep_order([translate_material(r.get('материал применения', '')) for r in rows])
        material_ru = '; '.join(material_values)

        size_options = dedupe_keep_order([build_size_option(r) for r in rows])
        if size_options:
            size_options_map[str(card_id)] = size_options

        desc_parts = ['Новая позиция из каталога APC 2026.']
        if form_ru:
            desc_parts.append(f'Форма профиля: {form_ru}.')
        if material_ru:
            desc_parts.append(f'Материал применения: {material_ru}.')
        if len(size_options) > 1:
            desc_parts.append(f'Варианты: {len(size_options)}.')
        desc_ru = ' '.join(desc_parts)

        search_parts = [title_ru, form_ru, material_ru, ' '.join(size_options)]
        search_text = ' '.join([p for p in search_parts if p]).lower()

        entries.append(
            Entry(
                idx=idx,
                id=card_id,
                code=code,
                raw_type=raw_type,
                raw_form=raw_form,
                image_source=image_src,
                image_output=image_out_name,
                title_ru=title_ru,
                form_ru=form_ru,
                desc_ru=desc_ru,
                search_text=search_text,
                size_options=size_options,
            )
        )

        audit_rows.append(
            {
                'entry_idx': idx,
                'id': card_id,
                'code': code,
                'type_en': raw_type,
                'form_en': raw_form,
                'type_ru': type_ru,
                'form_ru': form_ru,
                'source_image': str(image_src),
                'output_image': str(image_out_path),
                'size_options_count': len(size_options),
            }
        )

    cards_html: List[str] = []
    for e in entries:
        cards_html.append(
            f'''<div class="product" data-id="{e.id}" data-form-profile="{escape(e.form_ru)}" data-search="{escape(e.search_text)}">
<div class="prod-img">
<img alt="" loading="lazy" src="images/{escape(e.image_output)}" style="width:100%;height:100%;object-fit:cover"/>
</div>
<div class="prod-body">
<div class="prod-top">
<span class="prod-name">{escape(e.title_ru)} <span style="opacity:.65">(APC #{e.code})</span></span>
<div class="prod-tags">
<span style="display:inline-flex;align-items:center;padding:3px 8px;border-radius:999px;background:#dcfce7;color:#166534;border:1px solid #86efac;font-size:10px;font-weight:800;line-height:1">NEW</span>
</div>
</div>
<div class="prod-desc">{escape(e.desc_ru)}</div>
<div class="prod-inputs">
<div>
<label>Кол-во</label>
<input class="qty-input" data-qty="{e.id}" min="0" oninput="onQtyChange(this)" placeholder="—" type="number"/>
</div>
<span class="unit-label">шт.</span>
<div style="flex:1">
<label>Примечание</label>
<input class="note-input" data-note="{e.id}" oninput="saveState()" placeholder="комментарий по позиции…" type="text"/>
</div>
</div>
</div>
</div>'''
        )

    js_map = json.dumps(size_options_map, ensure_ascii=False, indent=2)
    js_block = f'''const ABRASIVE_DELTA_SIZE_OPTIONS = {js_map};
Object.assign(ABRASIVE_SIZE_OPTIONS, ABRASIVE_DELTA_SIZE_OPTIONS);

function normalizeSizeOptionText(value) {{
  const raw = String(value || '').trim();
  if (!raw) return '';

  let out = raw
    .split('|')
    .map(part => part.trim())
    .filter(Boolean)
    .join(' | ');

  out = out.replace(/\s{{2,}}/g, ' ').trim();
  out = out.replace(/\s+\|/g, ' |').replace(/\|\s*$/g, '').trim();
  return out || raw;
}}

function normalizeSizeOptions(list) {{
  const out = [];
  const seen = new Set();
  (Array.isArray(list) ? list : []).forEach(item => {{
    const normalized = normalizeSizeOptionText(item);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    out.push(normalized);
  }});
  return out;
}}

Object.keys(ABRASIVE_SIZE_OPTIONS).forEach(key => {{
  ABRASIVE_SIZE_OPTIONS[key] = normalizeSizeOptions(ABRASIVE_SIZE_OPTIONS[key]);
}});'''

    html_text = INDEX_HTML.read_text(encoding='utf-8')
    html_text = replace_between_markers(
        html_text,
        '<!-- APC2026_DELTA_START -->',
        '<!-- APC2026_DELTA_END -->',
        '\n'.join(cards_html),
    )
    html_text = replace_between_markers(
        html_text,
        '// APC2026_DELTA_SIZE_OPTIONS_START',
        '// APC2026_DELTA_SIZE_OPTIONS_END',
        js_block,
    )

    # Auto-select the single available size option to reduce extra clicks.
    html_text = html_text.replace(
        "  if (selected) select.value = selected;\n  return select;",
        "  if (selected) select.value = selected;\n  else if (options.length === 1) select.value = options[0];\n  return select;",
    )

    INDEX_HTML.write_text(html_text, encoding='utf-8')
    AUDIT_JSON.write_text(json.dumps(audit_rows, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'APC delta rebuilt: {len(entries)} cards')
    print(f'Index updated: {INDEX_HTML}')
    print(f'Audit: {AUDIT_JSON}')


if __name__ == '__main__':
    build()
