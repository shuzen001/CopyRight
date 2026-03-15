from pymongo import MongoClient, UpdateOne

import os
from dotenv import load_dotenv

load_dotenv()

# --- MongoDB connection ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "copyright"
COL_NAME = "TC_testing_writein"

def determine_court_level(court_name: str) -> str:
    if not court_name:
        return "Unknown"

    court_name_lower = str(court_name).lower()

    # District
    if "district" in court_name_lower:
        return "District"

    # Circuit (contains "circuit" or ordinal words)
    ordinal_words = [
        "first", "second", "third", "fourth", "fifth", "sixth",
        "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"
    ]
    if "circuit" in court_name_lower or any(w in court_name_lower for w in ordinal_words):
        return "Circuit"

    # Supreme (English/Spanish)
    if "supreme" in court_name_lower or "suprema" in court_name_lower:
        return "Supreme"

    # Treat Superior Court as District (your rule)
    if "superior" in court_name_lower:
        return "District"

    return "Unknown"

def run_circuit_level_annotation():
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COL_NAME]

    # --- Read -> compute -> write back (bulk) ---
    batch_size = 1000
    ops = []
    updated = 0
    skipped = 0

    # Only pull fields we need for efficiency
    cursor = col.find({}, {"Court": 1})

    for doc in cursor:
        court = doc.get("Court", None)
        level = determine_court_level(court)

        # If you want to skip documents with missing Court, do this:
        # if not court:
        #     skipped += 1
        #     continue

        ops.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {"Court Level": level}}
            )
        )

        if len(ops) >= batch_size:
            res = col.bulk_write(ops, ordered=False)
            updated += res.modified_count
            ops = []

    # flush remaining ops
    if ops:
        res = col.bulk_write(ops, ordered=False)
        updated += res.modified_count

    print(f"Done. updated={updated}, skipped={skipped}")

if __name__ == "__main__":
    run_circuit_level_annotation()
