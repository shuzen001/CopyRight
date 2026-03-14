import re
from typing import Dict, List

import fitz


def extract_case_metadata_from_page(
    pdf_file_path: str,
    start_page_0based: int,
    *,
    local_scan_pages: int = 2,
    extended_scan_pages: int = 13,
) -> Dict[str, object]:
    with fitz.open(pdf_file_path) as doc:
        n_pages = len(doc)
        if not (0 <= start_page_0based < n_pages):
            raise ValueError(f'start_page out of range: {start_page_0based} / {n_pages}')

        local_text = '\n'.join(
            doc[p].get_text('text')
            for p in range(start_page_0based, min(start_page_0based + local_scan_pages, n_pages))
        )
        extended_text = '\n'.join(
            doc[p].get_text('text')
            for p in range(start_page_0based, min(start_page_0based + extended_scan_pages, n_pages))
        )
        start_page_blocks = doc[start_page_0based].get_text('dict').get('blocks', [])

    def extract_section(start_label: str, end_labels: List[str], text: str, max_len: int = 1000) -> str:
        end_pat = '|'.join(end_labels)
        m = re.search(rf"{re.escape(start_label)}\s+([\s\S]+?)(?=\n(?:{end_pat}))", text, flags=re.IGNORECASE)
        if not m:
            return ''
        content = m.group(1).replace('\n', ' ').strip()
        return content if len(content) <= max_len else ''

    def extract_one_line(label: str, text: str) -> str:
        m = re.search(rf'{re.escape(label)}:\s*(.+)', text, flags=re.IGNORECASE)
        return m.group(1).strip() if m else ''

    def extract_prior_history_loose(text: str) -> str:
        m = re.search(
            r'Prior History[:\s]+([\s\S]+?)(?=\n(?:Disposition:|Core Terms|Subsequent History:|LexisNexis|Headnotes|HN\d+\[|$))',
            text,
            flags=re.IGNORECASE,
        )
        return m.group(1).replace('\n', ' ').strip() if m else ''

    core_terms_raw = extract_section(
        'Core Terms',
        [r'Counsel:', r'LexisNexis', r'Headnotes', r'HN\d+\[', r'Opinion by:', r'Judges?:'],
        local_text,
        max_len=2000,
    )
    core_terms = [t.strip() for t in core_terms_raw.split(',')] if core_terms_raw else []

    judges = extract_section('Judges:', [r'Opinion by:', r'Core Terms', r'Counsel:'], local_text, max_len=300)
    if not judges:
        m = re.search(r'\bBefore\s+(.+?)\.', extended_text, flags=re.IGNORECASE)
        judges = m.group(1).strip() if m else ''

    counsel_match = re.search(
        r'Counsel:\s*(.+?)(?=\n(?:HN\d+\[|Headnotes|Judges?:|Opinion by:|Core Terms|Subsequent History:|Prior History:|Disposition:|$))',
        extended_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    counsel = counsel_match.group(1).replace('\n', ' ').strip() if counsel_match else ''

    def extract_case_title_by_font(blocks: List[dict]) -> str:
        candidate = ''
        max_size = 0.0
        for block in blocks:
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    txt = (span.get('text') or '').strip()
                    size = float(span.get('size', 0))
                    if 'v.' in txt and size > max_size:
                        candidate = txt
                        max_size = size
        return candidate

    return {
        'core term': core_terms,
        'judges': judges,
        'plaintiff_defendant': extract_case_title_by_font(start_page_blocks),
        'counsel': counsel,
        'opinion by': extract_one_line('Opinion by', extended_text),
        'prior history': extract_prior_history_loose(local_text),
        'subsequent history': extract_section(
            'Subsequent History:',
            [r'Prior History:', r'Disposition:', r'Core Terms', r'LexisNexis', r'Headnotes'],
            local_text,
            max_len=1000,
        ),
    }
