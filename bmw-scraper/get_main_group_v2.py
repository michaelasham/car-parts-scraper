import sys
import os
import time
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
    "heater and air conditioning": "HEATER AND AIR CONDITIONING",
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
    "service and scope of repair work": "SERVICE AND SCOPE OF REPAIR WORK",
}

def _none(x: str) -> Optional[str]:
    x = (x or "").strip()
    return x if x else None

DATA_ROW = re.compile(
    r"""
    ^
    (?P<no>\d{2})\t
    (?P<desc>[^\t]*)\t
    (?P<supp>[^\t]*)\t
    (?P<qty>[^\t]*)\t
    (?P<from>[^\t]*)\t
    (?P<upto>[^\t]*)\t
    (?P<part>[A-Z0-9]+)?\t?
    (?P<price>\$?[0-9.,]*)\t?
    (?P<tail>.*)
    $
    """,
    re.VERBOSE
)

def parse_table(table_text: str) -> List[Dict]:
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
            cleaned = re.sub(r"\s+", " ", line).strip()
            if cleaned:
                current["notes"].append(cleaned)
    return items

# ---------- reliability helpers (no console prints) ----------

def _route_wrapper(route):
    url = route.request.url
    if "realoem.com" in url:
        return route.continue_()
    try:
        return block_ads(route)  # keep existing behavior for non-core hosts
    except Exception:
        return route.continue_()

def _pre_click_cleanup(page):
    js = """
(() => {
  const selectors = [
    '._1mbd8ky', '#eavgqh',
    "[id*='sp_message_container']", "[class*='sp_message']",
    "iframe[id^='google_ads_iframe']", "iframe[src*='pub.network']",
    "iframe[src*='googlesyndication']", "iframe[src*='doubleclick']",
    "[id*='aswift_']", "[class*='qc-cmp2']",
    "#onetrust-banner-sdk", "#onetrust-consent-sdk",
    ".fc-dialog-container", ".fc-consent-root",
    ".cc-window", ".cookie-consent", ".consent-modal"
  ];
  try {
    document.querySelectorAll(selectors.join(',')).forEach(el => {
      el.style.setProperty('pointer-events','none','important');
      el.style.setProperty('display','none','important');
    });
    const cand = Array.from(document.querySelectorAll('body *')).filter(e => {
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (!(cs.position === 'fixed' || cs.position === 'sticky' || cs.position === 'absolute')) return false;
      const r = e.getBoundingClientRect();
      return r.width >= 200 && r.height >= 80 && r.top <= (window.innerHeight * 0.9) && r.left <= (window.innerWidth * 0.9);
    });
    cand.forEach(e => e.style.setProperty('pointer-events','none','important'));
  } catch (e) {}
})();
"""
    try:
        page.evaluate(js)
    except Exception:
        pass

def _safe_click_subgroup(page, titles_locator, idx, timeout_ms=60000):
    import random
    deadline = time.time() + timeout_ms / 1000.0
    last_err = None
    while time.time() < deadline:
        try:
            el = titles_locator.nth(idx)
            anchor = el.locator("a")
            target = anchor if anchor.count() > 0 else el
            try:
                target.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            _pre_click_cleanup(page)
            bbox = None
            try:
                bbox = target.bounding_box(timeout=3000)
            except Exception:
                pass
            if bbox:
                rx = min(10, max(3, bbox["width"] * 0.1))
                ry = min(10, max(3, bbox["height"] * 0.5))
                target.click(timeout=5000, position={"x": rx, "y": ry})
            else:
                target.click(timeout=5000)
            return
        except Exception as e:
            last_err = e
            try:
                page.mouse.wheel(0, random.choice([200, 300, 400, -200]))
            except Exception:
                pass
            time.sleep(0.2)
    if last_err:
        raise last_err
    raise RuntimeError("Failed to click subgroup")

# ---------- main ----------

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"subgroups": []}, ensure_ascii=False, indent=2))
        sys.exit(1)

    vin = sys.argv[1].strip()
    group_in = sys.argv[2].strip().lower()
    subgroup_filters = [s.strip().lower() for s in sys.argv[3:]]

    if group_in not in ALLOWED_GROUPS:
        print(json.dumps({"subgroups": []}, ensure_ascii=False, indent=2))
        sys.exit(2)

    results: List[Dict] = []

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(
            headless=True,
            timeout=30_000,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )

        context = None
        page = None
        try:
            context = browser.new_context(
                viewport={"width": 1200, "height": 800},
                user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"),
            )
            context.set_default_timeout(60_000)
            context.set_default_navigation_timeout(60_000)
            context.route(ROUTE_PATTERN, _route_wrapper)

            page = context.new_page()

            page.goto("https://www.realoem.com", wait_until="domcontentloaded")
            page.get_by_text("enter BMW catalog", exact=False).first.click()
            page.wait_for_load_state("domcontentloaded")

            page.locator("#vin").fill(vin)
            page.locator("input[type='submit'][value='Search']").first.click()
            page.wait_for_load_state("domcontentloaded")

            try:
                page.wait_for_timeout(1000)
                if page.locator("span.ggmtgz:has-text('×')").first.is_visible():
                    page.locator("span.ggmtgz:has-text('×')").first.click()
            except Exception:
                pass

            page.get_by_text("Browse Parts", exact=False).first.click()
            page.wait_for_load_state("domcontentloaded")

            page.get_by_text(ALLOWED_GROUPS[group_in], exact=False).first.click()
            page.wait_for_load_state("domcontentloaded")

            # Ensure subgroup list is fully populated
            page.wait_for_selector(".title", state="visible", timeout=30_000)
            page.wait_for_function("document.querySelectorAll('.title').length > 1", timeout=30_000)

            titles = page.locator(".title")
            count = titles.count()

            # Build (index, name) list, skipping header
            sub_items: List[Dict] = []
            for i in range(1, count):
                try:
                    txt = (titles.nth(i).inner_text() or "").strip()
                    if not txt or "REP. KIT" in txt or "VALUE PARTS" in txt:
                        continue
                    sub_items.append((i, txt))
                except Exception:
                    pass

            # Optional filters
            if subgroup_filters:
                norm = lambda s: s.strip().lower()
                sub_items = [(i, n) for (i, n) in sub_items if any(f in norm(n) for f in subgroup_filters)]

            # Visit each subgroup via click (session-safe)
            for idx, name in sub_items:
                try:
                    _pre_click_cleanup(page)
                    _safe_click_subgroup(page, titles, idx, timeout_ms=60_000)
                    page.wait_for_load_state("domcontentloaded")
                    page.locator("#partsList").wait_for(state="visible", timeout=30_000)

                    table_text = page.locator("#partsList").inner_text()
                    img_src = page.locator("#partsimg > img").first.get_attribute("src") or ""
                    full_img = urljoin("https://www.realoem.com", img_src)

                    parsed_table = parse_table(table_text)
                    results.append({
                        "subgroup": name,
                        "diagram_image": full_img,
                        "parts": parsed_table
                    })
                except Exception:
                    pass
                finally:
                    try:
                        page.go_back(wait_until="domcontentloaded")
                        page.wait_for_selector(".title", state="visible", timeout=30_000)
                        page.wait_for_function("document.querySelectorAll('.title').length > 1", timeout=30_000)
                        titles = page.locator(".title")  # re-evaluate after navigation
                    except Exception:
                        pass

        finally:
            try:
                if page: page.close()
            except Exception:
                pass
            try:
                if context: context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    print(json.dumps({"subgroups": results}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
