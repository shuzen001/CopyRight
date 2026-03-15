import os
from typing import Dict

from app.config import settings
from app.parsers.footnote_parser import attach_case_no, extract_footnotes
from app.parsers.metadata_parser import extract_case_metadata_from_page
from app.parsers.opinion_parser import extract_opinions
from app.repository import MongoRepository


class IngestService:
    def __init__(self, repo: MongoRepository | None = None):
        self.repo = repo or MongoRepository(settings.mongo_uri, settings.mongo_db)

    def _resolve_pdf_path(self, filename: str) -> str:
        path = os.path.join(settings.data_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f'PDF not found: {path}')
        return path

    def ingest_metadata(self, pdf_filename: str, start_page: int, collection: str = 'TC_index_todo') -> Dict[str, object]:
        pdf_path = self._resolve_pdf_path(pdf_filename)
        meta = extract_case_metadata_from_page(pdf_path, start_page - 1)
        record = {'pdf': pdf_filename, 'page': start_page, **meta}
        count = self.repo.upsert_many(collection, [record], unique_keys=['pdf', 'page'])
        return {'inserted': count, 'collection': collection, 'sample': record}

    def ingest_footnotes(self, pdf_filename: str, collection: str = 'TC_footNote_testing', index_collection: str = 'TC_index_todo') -> Dict[str, object]:
        pdf_path = self._resolve_pdf_path(pdf_filename)
        rows = extract_footnotes(pdf_path)
        index_ranges = self.repo.load_index_ranges(index_collection)
        records = [{'pdf': pdf_filename, **row} for row in attach_case_no(rows, index_ranges, pdf_filename)]
        count = self.repo.upsert_many(collection, records, unique_keys=['pdf', 'page', 'Footnote'])
        return {'inserted': count, 'collection': collection, 'sample': records[0] if records else None}

    def ingest_opinions(self, pdf_filename: str, collection: str = 'TC_new_format_opinion') -> Dict[str, object]:
        pdf_path = self._resolve_pdf_path(pdf_filename)
        records = extract_opinions(pdf_path, pdf_filename)
        sample = dict(records[0]) if records else None
        count = self.repo.insert_many(collection, records)
        return {'inserted': count, 'collection': collection, 'sample': sample}

    def ingest_all_footnotes(self, collection: str = 'TC_footNote_testing', index_collection: str = 'TC_index_todo') -> Dict[str, object]:
        by_file: Dict[str, int] = {}
        total = 0
        for filename in sorted(f for f in os.listdir(settings.data_dir) if f.lower().endswith('.pdf')):
            result = self.ingest_footnotes(filename, collection=collection, index_collection=index_collection)
            by_file[filename] = result['inserted']
            total += result['inserted']
        return {'total_pdfs': len(by_file), 'total_inserted': total, 'by_file': by_file}
