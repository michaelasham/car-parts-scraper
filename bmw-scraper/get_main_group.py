import sys
import json
import re
from urllib.parse import urljoin
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from utils import block_ads 

ROUTE_PATTERN = "**/*"

ALLOWED_GROUPS = {
    "engine": "ENGINE",
    "engine electrical system": "ENGINE ELECTRICAL SYSTEM",
    "fuel preparation system": "FUEL PREPARATION SYSTEM",
    "fuel supply": "FUEL SUPPLY",
    "radiator": "RADIATOR",
    "exhaust system": "EXHAUST SYSTEM",
    "clutch": "CLUTCH",
    "engine and transmission suspension": "ENGINE AND TRANSMISSION SUSPENSION",
    "manual transmission": "MANUAL TRANSMISSION",
    "automatic transmission": "AUTOMATIC TRANSMISSION",
    "gearshift": "GEARSHIFT",
    "drive shaft": "DRIVE SHAFT",
    "front axle": "FRONT AXLE",
    "steering": "STEERING",
    "rear axle": "REAR AXLE",
    "brakes": "BRAKES",
    "pedals": "PEDALS",
    "wheels": "WHEELS",
    "bodywork": "BODYWORK",
    "vehicle trim": "VEHICLE TRIM",
    "seats": "SEATS",
    "heating and air conditioning" : "HEATER AND AIR CONDITIONING",
    "sliding roof / folding top": "SLIDING ROOF / FOLDING TOP",
    "vehicle electrical system": "VEHICLE ELECTRICAL SYSTEM",
    "instruments measuring systems": "INSTRUMENTS, MEASURING SYSTEMS",
    "lighting": "LIGHTING",
    "audio navigation electronic systems": "AUDIO, NAVIGATION, ELECTRONIC SYSTEMS",
    "distance systems cruise control": "DISTANCE SYSTEMS, CRUISE CONTROL",
    "equipment parts": "EQUIPMENT PARTS",
    "restraint system and accessories": "RESTRAINT SYSTEM AND ACCESSORIES",
    "communication systems": "COMMUNICATION SYSTEMS",
    "auxiliary materials fluidscolorsystem": "AUXILIARY MATERIALS, FLUIDS/COLOR SYSTEM",
    "service and scope of repair work" : "SERVICE AND SCOPE OF REPAIR WORK"
}

# --- Helper functions for parsing the RealOEM parts table --- #

def _none(x: str) -> Optional[str]:
    x = (x or "").strip()
    return x if x else None

DATA_ROW = re.compile(
    r"""^
    (?P<no>\d{2})\t
    (?P<desc>[^\t]*)\t
    (?P<supp>[^\t]*)\t
    (?P<qty>[^\t]*)\t
    (?P<from>[^\t]*)\t
    (?P<upto>[^\t]*)\t
    (?P<part>[A-Z0-9]+)?\t?
    (?P<price>\$?[0-9.,]*)\t?
    (?P<tail>.*)
    $""",
    re.VERBOSE
)

def parse_table(table_text: str) -> List[Dict]:
    """Parse RealOEM table text into structured JSON rows."""
    items: List[Dict] = []
    current = None
    for raw in table_text.replace("\r", "").split("\n"):
        line = raw.strip("\n")
        if not line or line.startswith("No.\tDescription"):
            continue

        m = DATA_ROW.match(line)
        if m:
            d = m.groupdict()
            item = {
                "item_no": d["no"],
                "description": _none(d["desc"]),
                "supplement": _none(d["supp"]),
                "quantity": _none(d["qty"]),
                "from_date": _none(d["from"]),
                "to_date": _none(d["upto"]),
                "part_number": _none(d["part"]),
                "price": _none(d["price"]),
                "notes": []
            }
            if _none(d["tail"]):
                item["notes"].append(d["tail"].strip())
            items.append(item)
            current = item
        elif current:
            # Continuation line (notes, vehicle conditions, etc.)
            cleaned = re.sub(r"\s+", " ", line).strip()
            if cleaned:
                current["notes"].append(cleaned)

    return items


# --- Main scraping logic --- #

def main():
    if len(sys.argv) < 3:
        print("Usage: python get_main_group.py <vin> <group>")
        sys.exit(1)

    vin = sys.argv[1].strip()
    group_in = " ".join(sys.argv[2:]).strip().lower()
    if group_in not in ALLOWED_GROUPS:
        print(f"Unsupported group '{group_in}'. Allowed: {', '.join(ALLOWED_GROUPS.keys())}")
        sys.exit(2)

    results = []

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        context.route(ROUTE_PATTERN, block_ads)

        page = context.new_page()
        try:
            page.goto("http://www.realoem.com", wait_until="domcontentloaded")
            page.get_by_text("enter BMW catalog", exact=False).click()
            page.wait_for_load_state("domcontentloaded")

            page.locator("#vin").fill(vin)
            page.locator("input[type='submit'][value='Search']").first.click()
            page.wait_for_load_state("domcontentloaded")

            page.get_by_text("Browse Parts", exact=False).click()
            page.wait_for_load_state("domcontentloaded")

            page.get_by_text(ALLOWED_GROUPS[group_in], exact=False).click()
            page.wait_for_load_state("domcontentloaded")

            page.locator(".title").first.wait_for(state="attached")
            titles = page.locator(".title").all()[1:]  # skip header

            for link in titles:
                name = link.inner_text()
                if "REP. KIT" in name or "VALUE PARTS" in name:
                    continue
                link.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                table_text = page.locator("#partsList").inner_text()
                img_src = page.locator("#partsimg > img").get_attribute("src") or ""
                full_img = urljoin("http://www.realoem.com", img_src)

                # Parse and store cleaned data
                parsed_table = parse_table(table_text)
                results.append({
                    "subgroup":name,
                    "diagram_image": full_img,
                    "parts": parsed_table
                })

                page.go_back(wait_until="domcontentloaded")
        except Exception:
            pass
        finally:
            try:
                context.unroute(ROUTE_PATTERN, block_ads)
            except Exception:
                pass
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    # --- Final structured output ---
    clean_output = {
        # "vin": vin,
        # "group": ALLOWED_GROUPS[group_in],
        "subgroups": results
    }

    print(json.dumps(clean_output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
