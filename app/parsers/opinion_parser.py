import re
from typing import Dict, List

import fitz

OPINION_PATTERN = r'Opinion'
END_PATTERN = r'End of Document'
PAGE_MARKER_PATTERN = re.compile(r'Page\s+\d+\s+of\s+\d+', flags=re.IGNORECASE)


def get_page_links(page: fitz.Page) -> List[Dict[str, str]]:
    links = []
    for link in page.get_links():
        if 'uri' in link:
            rect = fitz.Rect(link['from'])
            links.append({'raw_text': (page.get_textbox(rect) or '').strip(), 'link': link['uri']})
    return links


def extract_opinions(pdf_path: str, pdf_name: str) -> List[Dict[str, object]]:
    doc = fitz.open(pdf_path)

    opinion_started = False
    page_text = ''
    urls_dic_accumulated: List[Dict[str, str]] = []
    opinion_id = 0
    start_page_1based = None
    records: List[Dict[str, object]] = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_1based = page_num + 1
        urls_dic_accumulated += get_page_links(page)

        blocks = page.get_text('dict').get('blocks', [])
        for block in blocks:
            if 'lines' not in block:
                continue

            for line in block['lines']:
                for span in line.get('spans', []):
                    text = (span.get('text') or '').strip()
                    font = span.get('font')
                    size = span.get('size')

                    if size == 14.0 and font == 'Helvetica-Bold' and re.search(OPINION_PATTERN, text):
                        if opinion_started and page_text.strip():
                            records.append(
                                {
                                    'pdf': pdf_name,
                                    'opinion_id': opinion_id,
                                    'start_page': start_page_1based,
                                    'end_page': page_1based - 1,
                                    'content': page_text.strip(),
                                    'urls_dic': urls_dic_accumulated,
                                }
                            )
                            opinion_id += 1
                            page_text = ''
                            urls_dic_accumulated = []

                        opinion_started = True
                        start_page_1based = page_1based
                        continue

                    if opinion_started and size == 10 and font in ['Helvetica', 'Helvetica-BoldOblique', 'Helvetica-Oblique']:
                        if text:
                            page_text += f' {text}'
                            page_text = PAGE_MARKER_PATTERN.sub('', page_text).strip()

                    if opinion_started and re.search(END_PATTERN, text):
                        page_text = re.sub(END_PATTERN, '', page_text).strip()
                        records.append(
                            {
                                'pdf': pdf_name,
                                'opinion_id': opinion_id,
                                'start_page': start_page_1based,
                                'end_page': page_1based,
                                'content': page_text,
                                'urls_dic': urls_dic_accumulated,
                            }
                        )
                        opinion_id += 1
                        opinion_started = False
                        page_text = ''
                        urls_dic_accumulated = []

    if opinion_started and page_text.strip():
        records.append(
            {
                'pdf': pdf_name,
                'opinion_id': opinion_id,
                'start_page': start_page_1based,
                'end_page': len(doc),
                'content': page_text.strip(),
                'urls_dic': urls_dic_accumulated,
            }
        )

    doc.close()
    return records
