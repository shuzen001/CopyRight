from typing import Dict, Iterable, List, Optional

from pymongo import MongoClient, UpdateOne


class MongoRepository:
    def __init__(self, mongo_uri: str, db_name: str):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

    def load_index_ranges(self, collection_name: str) -> Dict[str, List[Dict[str, Optional[int]]]]:
        ranges: Dict[str, List[Dict[str, Optional[int]]]] = {}
        for idx in self.db[collection_name].find({}, {'pdf': 1, 'page': 1, 'end_page': 1, 'No': 1}):
            pdf = idx.get('pdf')
            if not pdf:
                continue
            ranges.setdefault(pdf, []).append({'No': idx.get('No'), 'start': idx.get('page'), 'end': idx.get('end_page')})

        for pdf in ranges:
            ranges[pdf].sort(key=lambda x: x['start'] or 0)
        return ranges

    def upsert_many(self, collection_name: str, records: Iterable[Dict[str, object]], unique_keys: List[str]) -> int:
        ops = []
        for record in records:
            filt = {k: record[k] for k in unique_keys}
            ops.append(UpdateOne(filt, {'$set': record}, upsert=True))

        if not ops:
            return 0

        result = self.db[collection_name].bulk_write(ops, ordered=False)
        return result.upserted_count + result.modified_count

    def insert_many(self, collection_name: str, records: List[Dict[str, object]]) -> int:
        if not records:
            return 0
        result = self.db[collection_name].insert_many(records)
        return len(result.inserted_ids)
