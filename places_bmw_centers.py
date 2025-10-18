#!/usr/bin/env python3
"""
Create-only: Google Places → ClickUp (NO custom fields, includes Place ID)
- Always creates NEW tasks in a target ClickUp List.
- Writes all data (including Place ID) into the task description.
- Adds tags like ["google-maps", "city-cairo"] (optional and free).

ENV (.env or system):
  GOOGLE_MAPS_API_KEY=...
  CLICKUP_TOKEN=pk_************************
  CLICKUP_LIST_ID=123456789

You can tweak:
  CITIES, QUERY_TMPL, MIN_REVIEWS, TAG_PREFIX
"""

import os
import time
import requests
from typing import Optional

# ---- optional .env ----
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# ---------- Config ----------
GOOGLE_API_KEY  = os.environ.get("GOOGLE_MAPS_API_KEY")
CLICKUP_TOKEN   = os.environ.get("CLICKUP_TOKEN")
CLICKUP_LIST_ID = os.environ.get("CLICKUP_LIST_ID")

CITIES = ["Cairo", "Alexandria"]
QUERY_TMPL = "bmw service center in {city}"
MIN_REVIEWS = 15
TAG_PREFIX = "city-"  # becomes, e.g., "city-cairo"

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL     = "https://maps.googleapis.com/maps/api/place/details/json"

CU_BASE    = "https://api.clickup.com/api/v2"
CU_HEADERS = {"Authorization": os.environ.get("CLICKUP_TOKEN",""), "Content-Type": "application/json"}

# ---------- Helpers ----------
def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(f"Missing required env var: {name}")
    return val

def maps_link_from_place_id(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def safe_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

# ---------- Google Places ----------
def text_search_all_pages(query: str, region: str = "eg", language: str = "en"):
    params = {"query": query, "key": GOOGLE_API_KEY, "region": region, "language": language}
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
        # token needs a short warm-up before next page becomes available
        time.sleep(2.0)
        params = {"pagetoken": next_token, "key": GOOGLE_API_KEY}

def place_details(place_id: str) -> dict:
    fields = ",".join([
        "name","formatted_address","formatted_phone_number",
        "rating","user_ratings_total","url",
    ])
    params = {"place_id": place_id, "fields": fields, "key": GOOGLE_API_KEY, "language": "en"}
    r = requests.get(DETAILS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("result", {}) if data.get("status") == "OK" else {}

# ---------- ClickUp (create-only) ----------
def cu_create_task(list_id: str, name: str, description: str, tags: list[str]) -> dict:
    payload = {"name": name, "description": description, "tags": tags}
    r = requests.post(f"{CU_BASE}/list/{list_id}/task", headers=CU_HEADERS, json=payload, timeout=30)
    try:
        r.raise_for_status()
    except Exception as e:
        raise SystemExit(f"Create failed for '{name}': {e}\nBody: {r.text}")
    return r.json()

# ---------- Orchestration ----------
def main():
    require_env("GOOGLE_MAPS_API_KEY")
    require_env("CLICKUP_TOKEN")
    list_id = require_env("CLICKUP_LIST_ID")

    created = 0

    for city in CITIES:
        query = QUERY_TMPL.format(city=city)
        print(f"🔎 Searching: {query}")
        for res in text_search_all_pages(query):
            pid = res.get("place_id")
            if not pid:
                continue

            # simple quality gate
            reviews = res.get("user_ratings_total", 0) or 0
            if reviews <= MIN_REVIEWS:
                continue

            d = place_details(pid) or {}
            name    = d.get("name") or res.get("name") or "Unknown"
            address = d.get("formatted_address", "") or res.get("formatted_address", "")
            phone   = d.get("formatted_phone_number", "")
            rating  = d.get("rating", res.get("rating", ""))
            reviews = d.get("user_ratings_total", reviews)
            maps_url = (d.get("url") or "").strip() or maps_link_from_place_id(pid)

            # Build a rich description (includes PLACE_ID marker)
            description = "\n".join([
                address,
                "",
                f"Maps: {maps_url}",
                f"Rating: {rating if rating not in (None,'') else '-'}",
                f"Reviews: {reviews if reviews not in (None,'') else '-'}",
                f"Phone: {phone if phone else '-'}",
                f"Source: Google Maps",
                f"City: {city}",
                f"PLACE_ID: {pid}",
            ])

            # Helpful tags; totally optional, not custom fields
            tags = ["google-maps", f"{TAG_PREFIX}{city.lower()}"]

            obj = cu_create_task(list_id, name, description, tags)
            print(f"🆕 Created: {obj.get('url','<no url>')}")
            created += 1

            time.sleep(0.10)  # be nice to both APIs

    print(f"✅ Done. Created {created} tasks (no custom fields, includes Place ID in description).")

if __name__ == "__main__":
    if not GOOGLE_API_KEY:
        raise SystemExit("Missing GOOGLE_MAPS_API_KEY")
    if not CLICKUP_TOKEN:
        raise SystemExit("Missing CLICKUP_TOKEN")
    if not CLICKUP_LIST_ID:
        raise SystemExit("Missing CLICKUP_LIST_ID")
    main()
