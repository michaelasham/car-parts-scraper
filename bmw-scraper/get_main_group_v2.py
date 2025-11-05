import sys
import os
import time
import json
import re
import traceback
from contextlib import contextmanager
from urllib.parse import urljoin
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
from utils import block_ads

# ---------------- DEBUG/FAIL-HARD SETTINGS ---------------- #
DEBUG = os.getenv("DEBUG", "1") != "0"
FAIL_HARD = os.getenv("FAIL_HARD", "1") != "0"  # set FAIL_HARD=0 to keep going on errors
DEBUG_SCREENSHOTS = os.getenv("DEBUG_SHOTS", "0") != "0"  # set to 1 to save screenshots on failures
SCREENSHOT_DIR = os.getenv("SHOT_DIR", "shots")

if DEBUG_SCREENSHOTS and not os.path.isdir(SCREENSHOT_DIR):
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    except Exception:
        pass

def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def _log(msg: str) -> None:
    if DEBUG:
        print(f"[{_ts()}] {msg}", flush=True)

def _shot(page, label: str) -> None:
    if not DEBUG_SCREENSHOTS:
        return
    try:
        fname = f"{SCREENSHOT_DIR}/{int(time.time())}_{re.sub(r'[^a-zA-Z0-9_-]+','_',label)[:60]}.png"
        page.screenshot(path=fname, full_page=True)
        _log(f"[SHOT] Saved screenshot: {fname}")
    except Exception as e:
        _log(f"[SHOT] Failed to save screenshot: {e}")

@contextmanager
def timed_step(name: str, page=None):
    start = time.time()
    _log(f"[STEP] {name} - start")
    try:
        yield
        dur = (time.time() - start) * 1000
        _log(f"[OK]   {name} - done in {dur:.1f} ms")
    except Exception as e:
        dur = (time.time() - start) * 1000
        _log(f"[ERR]  {name} - failed in {dur:.1f} ms: {e.__class__.__name__}: {e}")
        if page is not None:
            try:
                _log(f"[PAGE] url={page.url}")
            except Exception:
                pass
            _shot(page, f"FAIL_{name}")
        traceback.print_exc()
        if FAIL_HARD:
            raise
        # else continue (do not alter control flow when FAIL_HARD=0)

# ---------------- ORIGINAL CONSTANTS / DATA ---------------- #

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

# ---------------------- Main scraping logic ---------------------- #

def main():
    if len(sys.argv) < 3:
        print("Usage: python get_main_group.py <vin> <group> [<subgroup1> <subgroup2> ...]")
        sys.exit(1)

    vin = sys.argv[1].strip()
    group_in = sys.argv[2].strip().lower()
    subgroup_filters = [s.strip().lower() for s in sys.argv[3:]]  # optional: only parse these subgroups
    if group_in not in ALLOWED_GROUPS:
        print(f"Unsupported group '{group_in}'. Allowed: {', '.join(ALLOWED_GROUPS.keys())}")
        sys.exit(2)

    _log(f"[ARGS] vin={vin} group_in={group_in} filters={subgroup_filters or '[]'} FAIL_HARD={FAIL_HARD} DEBUG={DEBUG}")

    results = []

    with Stealth().use_sync(sync_playwright()) as p:
        with timed_step("launch_browser"):
            browser = p.chromium.launch(headless=True, timeout=30000)

        with timed_step("new_context"):
            context = browser.new_context()
            context.set_default_timeout(60000)
            context.set_default_navigation_timeout(60000)

            # Network diagnostics
            def on_req(req):
                _log(f"[REQ] {req.method} {req.url}")

            def on_res(res):
                try:
                    _log(f"[RES] {res.status} {res.url}")
                except Exception:
                    pass

            def on_req_failed(req):
                _log(f"[REQ_FAIL] {req.url} error={req.failure}")

            context.on("request", on_req)
            context.on("response", on_res)
            context.on("requestfailed", on_req_failed)

            context.route(ROUTE_PATTERN, block_ads)

        with timed_step("new_page"):
            page = context.new_page()

            # Console diagnostics
            def on_console(msg):
                _log(f"[CONSOLE] type={msg.type} text={msg.text}")
            page.on("console", on_console)

        try:
            with timed_step("goto_realoem", page):
                page.goto("http://www.realoem.com", wait_until="domcontentloaded")

            with timed_step("click_enter_catalog", page):
                page.get_by_text("enter BMW catalog", exact=False).click()
                page.wait_for_load_state("domcontentloaded")

            with timed_step("fill_vin_and_search", page):
                page.locator("#vin").fill(vin)
                page.locator("input[type='submit'][value='Search']").first.click()
                page.wait_for_load_state("domcontentloaded")

            with timed_step("handle_adblock_popup_if_present", page):
                page.wait_for_timeout(3000)
                try:
                    if page.locator("span.ggmtgz:has-text('×')").is_visible():
                        page.locator("span.ggmtgz:has-text('×')").click()
                except Exception as e:
                    _log(f"[POPUP] No popup or failed to close: {e}")

            with timed_step("open_browse_parts", page):
                page.get_by_text("Browse Parts", exact=False).click()
                page.wait_for_load_state("domcontentloaded")

            with timed_step(f"open_group_{ALLOWED_GROUPS[group_in]}", page):
                page.get_by_text(ALLOWED_GROUPS[group_in], exact=False).click()
                page.wait_for_load_state("domcontentloaded")

            with timed_step("collect_titles_locator", page):
                page.locator(".title").first.wait_for(state="attached")
                titles_locator = page.locator(".title")
                total = titles_locator.count()
                _log(f"[INFO] .title count (including header): {total}")

            # Collect (index, text) for subgroups. Skip header at index 0.
            with timed_step("enumerate_subgroups", page):
                items = []
                for i in range(1, total):
                    try:
                        txt = titles_locator.nth(i).inner_text()
                        items.append((i, txt))
                    except Exception as e:
                        _log(f"[WARN] reading subgroup title at index={i} failed: {e}")
                _log(f"[INFO] Found {len(items)} subgroup entries")

            # Normalize and optionally filter by provided subgroup filters
            def normalize(s: str) -> str:
                return s.strip().lower()

            if subgroup_filters:
                with timed_step("apply_subgroup_filters"):
                    filtered = [(i, n) for (i, n) in items if any(f in normalize(n) for f in subgroup_filters)]
                    items = filtered
                    _log(f"[INFO] Filtered subgroups: {len(items)} after applying filters={subgroup_filters}")

                    if not items:
                        print("No matching subgroups found for the provided filters.")
                        sys.exit(3)

            for idx, name in items:
                if "REP. KIT" in name or "VALUE PARTS" in name:
                    _log(f"[SKIP] Skipping subgroup '{name}' (kit/value parts)")
                    continue
                try:
                    with timed_step(f"enter_subgroup_{idx}_{name}", page):
                        # Re-evaluate locator and click by nth(index) to avoid matching wrong element by text
                        titles_locator = page.locator(".title")
                        titles_locator.nth(idx).click()
                        page.wait_for_load_state("domcontentloaded")

                    with timed_step(f"read_table_and_image_{idx}", page):
                        table_text = page.locator("#partsList").inner_text()
                        img_src = page.locator("#partsimg > img").get_attribute("src") or ""
                        full_img = urljoin("http://www.realoem.com", img_src)

                    with timed_step(f"parse_table_{idx}"):
                        parsed_table = parse_table(table_text)

                    results.append({
                        "subgroup": name,
                        "diagram_image": full_img,
                        "parts": parsed_table
                    })
                    _log(f"[APPEND] Added subgroup '{name}' with {len(parsed_table)} parts")

                except (PlaywrightTimeoutError, Exception) as e:
                    _log(f"[SUBGROUP ERR] idx={idx} name='{name}' err={e.__class__.__name__}: {e}")
                    traceback.print_exc()
                    _shot(page, f"SUBGROUP_FAIL_{idx}")
                    if FAIL_HARD:
                        raise
                    # continue with next subgroup on any failure
                finally:
                    with timed_step(f"back_from_subgroup_{idx}", page):
                        try:
                            page.go_back(wait_until="domcontentloaded")
                            page.wait_for_load_state("domcontentloaded")
                        except Exception as e:
                            _log(f"[BACK WARN] Could not go back cleanly: {e}")
                            if FAIL_HARD:
                                raise

        except Exception as e:
            _log(f"[FATAL] Top-level error: {e.__class__.__name__}: {e}")
            traceback.print_exc()
            _shot(page, "TOP_LEVEL_FAIL")
        finally:
            with timed_step("close_page"):
                try:
                    page.close()
                except Exception as e:
                    _log(f"[CLOSE WARN] page.close failed: {e}")
                    if FAIL_HARD:
                        raise
            with timed_step("close_context"):
                try:
                    context.close()
                except Exception as e:
                    _log(f"[CLOSE WARN] context.close failed: {e}")
                    if FAIL_HARD:
                        raise
            with timed_step("close_browser"):
                try:
                    browser.close()
                except Exception as e:
                    _log(f"[CLOSE WARN] browser.close failed: {e}")
                    if FAIL_HARD:
                        raise

    # --- Final structured output ---
    clean_output = {
        # "vin": vin,
        # "group": ALLOWED_GROUPS[group_in],
        "subgroups": results
    }

    print(json.dumps(clean_output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
# ...existing code...
