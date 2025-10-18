import os
import time
import json
import math
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
if not API_KEY:
    raise SystemExit("Missing GOOGLE_MAPS_API_KEY env var")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

CITIES = ["Cairo", "Alexandria"]
QUERY_TMPL = "bmw service center in {city}"
MIN_REVIEWS = 15

# Keep columns in the exact order you’ll map in ClickUp
OUT_COLUMNS = [
    "Name",
    "Address",
    "City",
    "Google Maps Link",
    "Google Rating",
    "Phone",
    "Reviews Count",
    "Source",
]

def text_search_all_pages(query: str, region: str = "eg", language: str = "en"):
    """Yield all results across pagination for a given text search query."""
    params = {
        "query": query,
        "key": API_KEY,
        "region": region,     # bias results to Egypt
        "language": language, # english labels
    }
    while True:
        r = requests.get(TEXT_SEARCH_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            raise RuntimeError(f"TextSearch status={status} error={data}")

        for res in data.get("results", []):
            yield res

        next_token = data.get("next_page_token")
        if not next_token:
            break
        # Google requires a short wait before the next page token becomes active
        time.sleep(2.0)
        params = {"pagetoken": next_token, "key": API_KEY}

def place_details(place_id: str):
    """Fetch selected fields from Place Details."""
    fields = ",".join([
        "name",
        "formatted_address",
        "formatted_phone_number",
        "rating",
        "user_ratings_total",
        "url"  # may return a canonical Maps URL; not guaranteed
    ])
    params = {"place_id": place_id, "fields": fields, "key": API_KEY, "language": "en"}
    r = requests.get(DETAILS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK":
        # some places block details; return minimal structure
        return {}
    return data.get("result", {})

def maps_link_from_place_id(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def main():
    rows = []
    seen = set()  # dedupe by place_id across both cities

    for city in CITIES:
        query = QUERY_TMPL.format(city=city)
        for res in text_search_all_pages(query):
            pid = res.get("place_id")
            if not pid or pid in seen:
                continue
            seen.add(pid)

            # Quick filter on rating count (exists in textsearch result)
            reviews = res.get("user_ratings_total", 0) or 0
            if reviews <= MIN_REVIEWS:
                continue

            details = place_details(pid) or {}
            name = details.get("name") or res.get("name")
            address = details.get("formatted_address", "")
            phone = details.get("formatted_phone_number", "")
            rating = details.get("rating", res.get("rating", ""))
            reviews = details.get("user_ratings_total", reviews)

            maps_link = details.get("url") or maps_link_from_place_id(pid)

            rows.append({
                "Name": name,
                "Address": address,
                "City": city,
                "Google Maps Link": maps_link,
                "Google Rating": rating,
                "Phone": phone,
                "Reviews Count": reviews,
                "Source": "Google Places",
            })

    # Sort by city then rating desc, then reviews desc
    def rating_key(v):
        try:
            return float(v) if v not in ("", None) else -math.inf
        except Exception:
            return -math.inf

    rows.sort(key=lambda r: (r["City"], -rating_key(r["Google Rating"]), -(r["Reviews Count"] or 0)))

    # Export to XLSX
    df = pd.DataFrame(rows, columns=OUT_COLUMNS)
    out_path = "bmw_service_centers.xlsx"
    df.to_excel(out_path, index=False)
    print(f"✅ Exported {len(df)} rows to {out_path}")

if __name__ == "__main__":
    main()
