#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

INDEX = Path('/tmp/netlify-deploy/index.html')


def clean_spaces(text: str) -> str:
    text = text.replace('\xa0', ' ')
    return re.sub(r'\s{2,}', ' ', text).strip()


def replace_alo(text: str) -> str:
    out = re.sub(r'\bALO\b', 'оксид алюминия', text)
    out = re.sub(r'\balo\b', 'оксид алюминия', out)
    return out


def clean_title(text: str) -> str:
    t = text
    t = re.sub(r'\s*\(APC\s*#\d+\)\s*', '', t, flags=re.IGNORECASE)
    t = t.replace('Sand Master', '')
    t = t.replace('Concord', '')
    t = t.replace('Blue Drill', '')
    t = t.replace('blue drill', '')
    t = replace_alo(t)
    t = re.sub(r'\(\s*\)', '', t)
    return clean_spaces(t)


def clean_desc(text: str) -> str:
    t = text
    t = t.replace('Новая позиция из каталога APC 2026.', '')
    t = replace_alo(t)
    return clean_spaces(t)


def simplify_option(value: str) -> str:
    v = str(value)
    v = replace_alo(v)
    v = re.sub(r'\s*\|\s*модель\s*[^|]+', '', v, flags=re.IGNORECASE)
    v = re.sub(r'\s*\|\s*model\s*[^|]+', '', v, flags=re.IGNORECASE)
    v = re.sub(r'\s*\|\s*grit\s*', ' | зерно ', v, flags=re.IGNORECASE)
    v = v.replace('APC', '')
    v = clean_spaces(v)
    v = re.sub(r'\s*\|\s*', ' | ', v)
    return clean_spaces(v.strip('| '))


def main() -> None:
    html = INDEX.read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    # ---- CSS overflow + hide removed cards ----
    style = soup.find('style')
    if style and style.string and '.product[data-removed="true"]' not in style.string:
        style.string += """

.product[data-removed="true"]{display:none!important}
.prod-body{min-width:0}
.prod-inputs{flex-wrap:wrap;align-items:flex-end}
.size-wrap,.params-wrap{flex:1 1 220px;min-width:170px}
.size-select,.params-input{width:100%;min-width:0}
.note-input{min-width:0}
.size-variants{width:100%;overflow:hidden}
.size-variants-list{width:100%}
.size-variant-row{width:100%;grid-template-columns:minmax(170px,1.2fr) 86px minmax(140px,1fr) minmax(140px,1fr) 34px}
.size-variant-row > *{min-width:0}
"""

    # ---- Abrasive cards edits ----
    sec = soup.find('div', {'id': 'cat-abrasives'})
    cards = sec.find_all('div', class_='product', recursive=False)

    # hide abr 20 and 21
    for c in cards:
        cid = c.get('data-id', '')
        if cid in {'20', '21'}:
            c['data-removed'] = 'true'

    # general APC cleanups
    for c in cards:
        cid = c.get('data-id', '')
        if not cid.isdigit() or int(cid) < 221:
            continue

        t = c.find('span', class_='prod-name')
        if t:
            t.string = clean_title(t.get_text(' ', strip=True))

        d = c.find('div', class_='prod-desc')
        if d:
            d.string = clean_desc(d.get_text(' ', strip=True))

        search = c.get('data-search', '')
        search = clean_desc(search)
        search = re.sub(r'\s*\|\s*модель\s*[^|]+', '', search, flags=re.IGNORECASE)
        search = clean_spaces(search)
        c['data-search'] = search.lower()

    # user-requested specific correction: ABR-041 belts text
    if len(cards) >= 41:
        c41 = cards[40]
        t41 = c41.find('span', class_='prod-name')
        d41 = c41.find('div', class_='prod-desc')
        if t41:
            t41.string = 'Абразивные ленты'
        if d41:
            d41.string = 'Для шлифовки и зачистки по металлу и древесине. Доступны длинные, узкие и широкие ленты с разными типами стыков под задачу и машину.'

    # user-requested shift: ABR-42 description empty, then ABR-43+ move up by one
    if len(cards) >= 43:
        old_desc = []
        for c in cards:
            d = c.find('div', class_='prod-desc')
            old_desc.append(d.get_text(' ', strip=True) if d else '')

        t42 = cards[41].find('span', class_='prod-name')
        if t42:
            t42.string = 'Алмазные диски горячего прессования (Сегментный)'

        d42 = cards[41].find('div', class_='prod-desc')
        if d42:
            d42.string = ''

        for i in range(42, len(cards) - 1):
            d = cards[i].find('div', class_='prod-desc')
            if d:
                d.string = old_desc[i + 1]
        dlast = cards[-1].find('div', class_='prod-desc')
        if dlast:
            dlast.string = ''

    # ---- JS edits ----
    scripts = soup.find_all('script')
    if scripts:
        js = scripts[-1].string or scripts[-1].get_text('\n')

        # keep removed cards hidden during search and counters
        js = js.replace(
            "const count = sec.querySelectorAll('.product').length;",
            "const count = sec.querySelectorAll('.product:not([data-removed=\"true\"])').length;",
        )
        if "card.dataset.removed === 'true'" not in js:
            js = js.replace(
                "document.querySelectorAll('.product').forEach(card => {\n    const text = card.dataset.search || '';",
                "document.querySelectorAll('.product').forEach(card => {\n    if (card.dataset.removed === 'true') { card.style.display = 'none'; return; }\n    const text = card.dataset.search || '';",
            )

        # delta size options cleanup
        m = re.search(
            r'(// APC2026_DELTA_SIZE_OPTIONS_START\s*const ABRASIVE_DELTA_SIZE_OPTIONS = )(\{.*?\})(;\s*Object\.assign\(ABRASIVE_SIZE_OPTIONS, ABRASIVE_DELTA_SIZE_OPTIONS\);)',
            js,
            flags=re.S,
        )
        if m:
            prefix, obj_raw, suffix = m.groups()
            try:
                obj = json.loads(obj_raw)
                for k, arr in list(obj.items()):
                    if isinstance(arr, list):
                        cleaned = [simplify_option(v) for v in arr]
                        dedup = []
                        seen = set()
                        for v in cleaned:
                            if not v or v in seen:
                                continue
                            seen.add(v)
                            dedup.append(v)
                        obj[k] = dedup
                # explicit: ABR-041 (id 240) should describe belts, not grinder note
                obj['240'] = ['Длинные, узкие и широкие ленты']
                js = js[:m.start()] + prefix + json.dumps(obj, ensure_ascii=False, indent=2) + suffix + js[m.end():]
            except Exception:
                pass

        js = js.replace('✍️ Custom размер…', '✍️ Свой размер…')
        js = js.replace('✍️ Custom размер', '✍️ Свой размер')

        scripts[-1].string = js

    out = str(soup)
    out = out.replace('(APC #', '(#')  # just in case any remnants survive unexpected nested spans
    out = out.replace('(#', '(')       # remove the temporary marker and keep clean title text

    INDEX.write_text(out, encoding='utf-8')
    print('Updated', INDEX)


if __name__ == '__main__':
    main()
