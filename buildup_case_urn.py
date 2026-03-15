import re
from collections import Counter
from pymongo import MongoClient, UpdateOne

import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# MongoDB config
# ==========================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "copyright"
SOURCE_COL = "TC_new_format_opinion"  # <- Updated to use the correct source collection
TARGET_COL = "TC_case_link"

def run_case_urn_extraction():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    src = db[SOURCE_COL]
    tgt = db[TARGET_COL]

    print(f"Working on connecting source '{SOURCE_COL}' and target '{TARGET_COL}' collections.")

    # 1. build up the basic `case_link` elements
    tgt.drop()
    tgt.create_index("link", unique=True)

    BATCH_SIZE = 2000
    ops = []
    processed_docs = 0
    processed_hits = 0

    cursor = src.find(
        {"urls_dic": {"$exists": True}},
        {"urls_dic": 1, "pdf": 1},
        no_cursor_timeout=True
    )

    try:
        for doc in cursor:
            source_id = doc["_id"]
            urls = doc.get("urls_dic")
            pdf_name = doc.get("pdf", "Unknown")

            if not isinstance(urls, list):
                continue

            for u in urls:
                if u.get("category") != "Cases":
                    continue

                link = u.get("link")
                if not isinstance(link, str) or not link.strip():
                    continue
                link = link.strip()

                citation = u.get("raw_text")
                if isinstance(citation, str):
                    citation = citation.strip()
                else:
                    citation = None

                update_dict = {
                    "$addToSet": {
                        "source_ids": source_id,
                        "pdfs": pdf_name
                    }
                }

                if citation:
                    update_dict["$addToSet"]["citations"] = citation

                ops.append(
                    UpdateOne(
                        {"link": link},
                        {
                            "$setOnInsert": {"link": link},
                            **update_dict
                        },
                        upsert=True
                    )
                )
                processed_hits += 1

                if len(ops) >= BATCH_SIZE:
                    tgt.bulk_write(ops, ordered=False)
                    ops = []

            processed_docs += 1

        if ops:
            tgt.bulk_write(ops, ordered=False)

    finally:
        cursor.close()

    print("Processed source docs:", processed_docs)
    print("Processed case-link hits:", processed_hits)
    print("Distinct links stored:", tgt.count_documents({}))

    # 2. Add URNs
    URN_RE = re.compile(r"(urn:contentItem:[A-Z0-9\-]+)", re.IGNORECASE)
    ops = []

    for doc in tgt.find({"urn": {"$exists": False}, "link": {"$type": "string"}}):
        m = URN_RE.search(doc["link"])
        if not m:
            continue

        urn = m.group(1)
        ops.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {"urn": urn}}
            )
        )

    if ops:
        result = tgt.bulk_write(ops)
        print("URNs Modified:", result.modified_count)
    else:
        print("No URNs to update.")

    # 3. Check for duplicates
    urns = [
        doc["urn"]
        for doc in tgt.find({"urn": {"$exists": True}}, {"urn": 1})
    ]

    counter = Counter(urns)
    duplicates = {u: c for u, c in counter.items() if c > 1}

    print("重複的 URN 數量:", len(duplicates))

if __name__ == "__main__":
    run_case_urn_extraction()
