import re
from typing import Dict, List, Optional

import fitz


def extract_footnotes(
    pdf_path: str,
    *,
    target_font: str = 'Helvetica',
    footnote_size: float = 6.0,
    body_size: float = 9.0,
) -> List[Dict[str, object]]:
    doc = fitz.open(pdf_path)
    rows: List[Dict[str, object]] = []
    collecting = False
    footnote_text = ''

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        blocks = page.get_text('dict').get('blocks', [])

        for block in blocks:
            if 'lines' not in block:
                continue

            for line_num, line in enumerate(block['lines']):
                spans = line.get('spans', [])
                for i, span in enumerate(spans):
                    font_name = span.get('font', '')
                    size = float(span.get('size', 0))
                    text = (span.get('text') or '').strip()

                    if collecting:
                        if i < len(spans) - 1:
                            next_text = (spans[i + 1].get('text') or '').strip()
                            if text.endswith('.') and re.match(r'^[A-Z]', next_text):
                                rows.append({'page': page_num + 1, 'Footnote': footnote_text.strip()})
                                collecting = False
                                footnote_text = ''
                                continue
                        footnote_text += f' {text}'

                    if (
                        not collecting
                        and font_name == target_font
                        and size == float(footnote_size)
                        and i < len(spans) - 1
                        and float(spans[i + 1].get('size', 0)) == float(body_size)
                    ):
                        collecting = True
                        footnote_text = f"{text} {(spans[i + 1].get('text') or '').strip()}".strip()

                if collecting and line_num == len(block['lines']) - 1:
                    rows.append({'page': page_num + 1, 'Footnote': footnote_text.strip()})
                    collecting = False
                    footnote_text = ''

    if collecting and footnote_text.strip():
        rows.append({'page': len(doc), 'Footnote': footnote_text.strip()})

    doc.close()
    return rows


def attach_case_no(rows: List[Dict[str, object]], index_ranges: Dict[str, List[Dict[str, Optional[int]]]], pdf_name: str) -> List[Dict[str, object]]:
    def find_no(page: int) -> Optional[int]:
        for entry in index_ranges.get(pdf_name, []):
            start = entry.get('start')
            end = entry.get('end')
            if start is None:
                continue
            if end is None and page >= start:
                return entry.get('No')
            if end is not None and start <= page <= end:
                return entry.get('No')
        return None

    with_no: List[Dict[str, object]] = []
    for row in rows:
        page = int(row['page'])
        with_no.append({**row, 'No': find_no(page)})
    return with_no
