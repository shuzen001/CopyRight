import requests
from bs4 import BeautifulSoup
import json
from pymongo import MongoClient

import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# MongoDB config
# ==========================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "copyright"
SOURCE_COL = "TC_index_todo"
TARGET_COL = "TC_judges"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
}

def extract_court_names(text):
    return any(kw in text for kw in ["Court", "Circuit"])

def scrape_ballotpedia_judge_info(judge_name):
    # Convert name to Ballotpedia URL format
    url_name = judge_name.strip().title().replace(" ", "_")
    url = f"https://ballotpedia.org/{url_name}"

    res = requests.get(url, headers=headers)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, "html.parser")

    box = soup.find('div', class_='infobox person')
    data = {}
    education = {}
    circuit_history = []
    Aliases = []

    if not box:
        data["error"] = f"No infobox found for {judge_name}"
        return data

    rows = box.find_all('div', class_='widget-row')

    # Get the official name from the page title
    page_name_tag = soup.find('span', class_='mw-page-title-main')
    page_name = ""
    if page_name_tag:
        page_name = page_name_tag.get_text(strip=True)
        data["Name"] = page_name

    # Check if judge_name (normalized) differs from the page name
    normalized_input = judge_name.strip().lower().replace("_", "").replace(" ", "")
    normalized_page = page_name.lower().replace(" ", "")
    if normalized_input != normalized_page:
        Aliases.append(judge_name)

    # Party
    party_tag = box.find('a', href=lambda x: x and ("Democratic_Party" in x or "Republican_Party" in x or "Nonpartisan" in x))
    if party_tag:
        data["Party"] = party_tag.get_text(strip=True)

    # Main infobox parsing
    for row in rows:
        key_tag = row.find('div', class_='widget-key')
        value_tag = row.find('div', class_='widget-value')

        if key_tag and value_tag:
            key = key_tag.get_text(strip=True)
            val = value_tag.get_text(separator=' ', strip=True)

            if key in ["Bachelor's", "Law"]:
                education[key] = val
            elif extract_court_names(key):
                circuit_history.append(key)
            elif extract_court_names(val):
                circuit_history.append(val)
            else:
                data[key] = val

    # Bold label above, value below
    bold_divs = box.find_all('div', style=lambda x: x and 'font-weight: bold' in x)
    for div in bold_divs:
        key = div.get_text(strip=True)
        next_div = div.find_next_sibling('div')
        if next_div:
            val = next_div.get_text(strip=True)
            if extract_court_names(key):
                circuit_history.append(key)
            if extract_court_names(val):
                circuit_history.append(val)
            if not extract_court_names(key) and not extract_court_names(val):
                data[key] = val

    # Clean circuit entries
    cleaned_circuits = list(set([
        entry.strip() for entry in circuit_history if ':' not in entry
    ]))

    # Attach structured fields
    if education:
        data["Education"] = education
    if cleaned_circuits:
        data["Circuit"] = cleaned_circuits

    # Paragraphs and gender detection
    paragraphs = soup.find_all('p')
    all_text = ' '.join(p.get_text(strip=True) for p in paragraphs).lower()
    data["content"] = all_text

    she_count = all_text.count(' she ')
    her_count = all_text.count(' her ')
    he_count = all_text.count(' he ')
    his_count = all_text.count(' his ')

    if she_count + her_count > he_count + his_count:
        data["Gender"] = "Female"
    elif he_count + his_count > 0:
        data["Gender"] = "Male"

    data["Ballotpedia URL"] = url
    if Aliases:
        data["Aliases"] = Aliases

    return data


def run_judge_extraction():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    collection_index = db[SOURCE_COL]
    
    # query to get names of judges from the new index_todo collection
    cursor = collection_index.find(
        {"judges": {"$exists": True, "$ne": ""}},
        {"judges": 1, "_id": 0}
    )

    judge_names = []
    for doc in cursor:
        raw = doc.get("judges", "")
        if not raw:
            continue
        # Parse judge string like "Phillips, Chief Judge, Weick and Edwards, Circuit Judges."
        # Remove titles like "Chief Judge", "Circuit Judges.", "District Judge", etc.
        import re
        cleaned = re.sub(r',?\s*(Chief |Senior |Associate |Acting )?(Circuit |District |Bankruptcy )?Judges?\.?', '', raw)
        # Split by " and " or ", "
        parts = re.split(r'\s+and\s+|,\s*', cleaned)
        for part in parts:
            name = part.strip().rstrip('.')
            if name and len(name) > 1:
                name = name.strip().title()
                judge_names.append(name)

    unique_names = list(set(judge_names))

    collection_judges = db[TARGET_COL]
    existing_names = set()

    for doc in collection_judges.find({}, {"Name": 1, "Aliases": 1, "_id": 0}):
        if "Name" in doc:
            existing_names.add(doc["Name"])
        if "Aliases" in doc and isinstance(doc["Aliases"], list):
            existing_names.update(doc["Aliases"])

    new_names = [name for name in unique_names if name not in existing_names]
    print(f"Judges to add: {len(new_names)}")

    for judge in new_names:
        info = scrape_ballotpedia_judge_info(judge)

        if "error" in info:
            print(f"Skipped {judge}: {info['error']}")
            # store skipping reason to avoid trying again
            collection_judges.insert_one({
                "original_search_name": judge,
                "error": info["error"]
            })
        else:
            try:
                collection_judges.insert_one(info)
                print(f"Saved data for {judge}")
            except Exception as e:
                print(f"Error saving {judge}: {e}")

if __name__ == "__main__":
    run_judge_extraction()
