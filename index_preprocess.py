"""
index_todo_backfill_cleanup.py

Purpose
-------
Backfill / cleanup for index_todo collection:
1) Remove Lexis footnote markers like [*1], [**12] from selected fields
2) Convert date strings "YYYY/M/D" or "YYYY/MM/DD" in Argued/Decided/Others into timezone-aware datetime (Asia/Taipei)

Notes
-----
- Only updates documents that actually change.
- Uses bulk_write for performance.
- Safe to re-run (idempotent for cleaned content + date conversion).

Python >= 3.9 recommended (zoneinfo).
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient, UpdateOne


# =========================
# MongoDB config
# =========================
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "copyright"
COLLECTION_NAME = "TC_testing_writein"

# =========================
# Settings
# =========================
BATCH_SIZE = 500
TZ = ZoneInfo("Asia/Taipei")  # GMT+8

# Fields to clean markers
CLEAN_FIELDS = [
    "prior history",
    "subsequent history",
    "opinion by",
    "judges",
    # 如果你要把 counsel 也清掉 marker，取消下一行註解
    # "counsel",
]

# Date fields to convert to datetime
DATE_FIELDS = ["Decided", "Others", "Argued"]

# Lexis footnote markers like [*1], [**12]
FOOTNOTE_PATTERN = re.compile(r"\[\*+\d+\]")


# =========================
# Text cleaning
# =========================
def clean_text(text: str) -> str:
    # Remove markers then trim spaces
    return FOOTNOTE_PATTERN.sub("", text).strip()


def clean_field(value: Any) -> Any:
    """
    Clean strings or list[str]; keep other types unchanged.
    """
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        cleaned_list = []
        for x in value:
            if isinstance(x, str):
                cleaned_list.append(clean_text(x))
            else:
                cleaned_list.append(x)
        return cleaned_list
    return value


# =========================
# Date conversion
# =========================
def parse_date_str(date_str: str) -> Optional[datetime]:
    """
    Parse "YYYY/M/D" or "YYYY/MM/DD" into timezone-aware datetime (Asia/Taipei).
    Returns None if not parsable.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    s = date_str.strip()
    if not s:
        return None

    # Accept both "2024/1/2" and "2024/01/02"
    # datetime.strptime("%Y/%m/%d") already supports both, as long as separators match.
    try:
        dt = datetime.strptime(s, "%Y/%m/%d")
        return dt.replace(tzinfo=TZ)
    except Exception:
        return None


def parse_others_field(value: Any) -> Tuple[Any, bool]:
    """
    'Others' sometimes is:
    - string: "YYYY/M/D, YYYY/M/D, ..."
    - already datetime
    - empty
    We convert it into:
    - list[datetime] when it's a comma-separated string
    Returns (new_value, changed?)
    """
    if not isinstance(value, str):
        return value, False

    s = value.strip()
    if not s:
        return value, False

    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) <= 1:
        # If it's a single date string, convert to datetime
        dt = parse_date_str(s)
        if dt:
            return dt, True
        return value, False

    dts: List[datetime] = []
    for p in parts:
        dt = parse_date_str(p)
        if dt:
            dts.append(dt)

    # If none parsed, keep original
    if not dts:
        return value, False

    return dts, True


# =========================
# One-document processor
# =========================
def build_updates(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build $set updates for a single document.
    Only includes keys that actually change.
    """
    updates: Dict[str, Any] = {}

    # ---- (1) Clean footnote markers ----
    for f in CLEAN_FIELDS:
        if f in doc and doc[f] is not None:
            old_v = doc.get(f)
            new_v = clean_field(old_v)
            if new_v != old_v:
                updates[f] = new_v

    # ---- (2) Convert date strings to datetime ----
    for f in DATE_FIELDS:
        if f not in doc:
            continue

        old_v = doc.get(f)

        # If already datetime, skip
        if isinstance(old_v, datetime):
            continue

        if f == "Others":
            new_v, changed = parse_others_field(old_v)
            if changed and new_v != old_v:
                updates[f] = new_v
        else:
            if isinstance(old_v, str):
                dt = parse_date_str(old_v)
                if dt is not None and dt != old_v:
                    updates[f] = dt

    return updates


# =========================
# Runner
# =========================
def run(query: Optional[Dict[str, Any]] = None) -> None:
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION_NAME]

    if query is None:
        # 你也可以改成只跑可能需要處理的文件，降低掃描量
        # 例如只跑：有這些欄位存在的
        query = {
            "$or": [
                {f: {"$exists": True, "$ne": None}} for f in (CLEAN_FIELDS + DATE_FIELDS)
            ]
        }

    cursor = col.find(query)

    ops: List[UpdateOne] = []
    seen = 0
    will_update = 0

    for doc in cursor:
        seen += 1
        updates = build_updates(doc)

        if updates:
            will_update += 1
            ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": updates}))

        if len(ops) >= BATCH_SIZE:
            res = col.bulk_write(ops, ordered=False)
            print(f"[WRITE] matched={res.matched_count}, modified={res.modified_count}")
            ops.clear()

    if ops:
        res = col.bulk_write(ops, ordered=False)
        print(f"[WRITE] final matched={res.matched_count}, modified={res.modified_count}")

    print(f"\n✅ Done. Seen={seen}, Documents_with_updates={will_update}")


def main():
    # 直接全跑；你也可以把 query 換成只補缺漏的條件
    run(query=None)


if __name__ == "__main__":
    main()
