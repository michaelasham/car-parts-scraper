import sys
import os
import time
import json
import random
import math
import logging
from pathlib import Path
from dotenv import load_dotenv

# Playwright-compatible Camoufox (synchronous)
from camoufox.sync_api import Camoufox
from playwright.sync_api import TimeoutError as PlaywrightTimeout, Error as PlaywrightError

# --- Config / env ----------------------------------------------------------
load_dotenv()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("7zap.get_ac_parts")

ZAP_USER = os.getenv("ZAP_USER")
ZAP_PASS = os.getenv("ZAP_PASS")
HEADLESS = os.getenv("HEADLESS", "true").lower() not in ("0", "false", "no")
DEBUG_DIR = Path(os.getenv("DEBUG_DIR", "/tmp/7zap_debug"))
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
GCS_BUCKET = os.getenv("GCS_BUCKET")

# Humanization tunables (conservative)
HUMAN_DELAY_RANGE = (0.08, 0.28)
TYPE_DELAY_RANGE_MS = (30, 90)
MOUSE_STEPS_RANGE = (8, 28)
SCROLL_CHANCE = 0.25
SCROLL_PIXELS = (120, 420)

# --- Helpers ---------------------------------------------------------------
def short_sleep(a=None, b=None):
    lo, hi = (a, b) if a is not None else HUMAN_DELAY_RANGE
    time.sleep(random.uniform(lo, hi))

def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        (u**3) * p0[0] + 3 * (u**2) * t * p1[0] + 3 * u * (t**2) * p2[0] + (t**3) * p3[0],
        (u**3) * p0[1] + 3 * (u**2) * t * p1[1] + 3 * u * (t**2) * p2[1] + (t**3) * p3[1],
    )

_MOUSE_POS = [random.randint(60, 240), random.randint(80, 260)]

def move_mouse_curve(page, tx, ty):
    global _MOUSE_POS
    sx, sy = _MOUSE_POS
    ex, ey = float(tx), float(ty)
    dist = math.hypot(ex - sx, ey - sy) + 1
    angle = math.atan2(ey - sy, ex - sx)
    r = dist / 2.0
    c1 = (sx + r * math.cos(angle + random.uniform(-0.35, 0.35)),
          sy + r * math.sin(angle + random.uniform(-0.35, 0.35)))
    c2 = (sx + r * math.cos(angle + random.uniform(-0.35, 0.35)),
          sy + r * math.sin(angle + random.uniform(-0.35, 0.35)))
    steps = random.randint(*MOUSE_STEPS_RANGE)
    for i in range(1, steps + 1):
        t = i / steps
        x, y = bezier((sx, sy), c1, c2, (ex, ey), t)
        try:
            page.mouse.move(float(x), float(y), steps=1)
        except Exception:
            # best-effort; ignore movement errors
            pass
    for _ in range(random.randint(0, 2)):
        try:
            page.mouse.move(ex + random.uniform(-1.2, 1.2), ey + random.uniform(-1.2, 1.2), steps=1)
        except Exception:
            pass
    _MOUSE_POS = [ex, ey]

def click_like_human(page, locator, timeout=30000):
    locator.wait_for(state="visible", timeout=timeout)
    locator.scroll_into_view_if_needed()
    bbox = locator.bounding_box()
    if not bbox:
        locator.click()
        return
    tx = bbox["x"] + random.uniform(bbox["width"] * 0.2, bbox["width"] * 0.8)
    ty = bbox["y"] + random.uniform(bbox["height"] * 0.2, bbox["height"] * 0.8)
    move_mouse_curve(page, tx, ty)
    short_sleep(0.04, 0.14)
    try:
        page.mouse.down()
        short_sleep(0.02, 0.06)
        page.mouse.up()
    except Exception:
        locator.click()

def type_like_human(page, locator, text):
    try:
        locator.click()
    except Exception:
        pass
    short_sleep(0.04, 0.12)
    for ch in text:
        if random.random() < 0.05:
            short_sleep(0.12, 0.35)
        try:
            page.keyboard.type(ch, delay=random.randint(*TYPE_DELAY_RANGE_MS))
        except Exception:
            try:
                locator.fill(text)
                return
            except Exception:
                pass

def maybe_scroll(page):
    if random.random() < SCROLL_CHANCE:
        try:
            page.mouse.wheel(0, random.randint(*SCROLL_PIXELS))
        except Exception:
            pass

# Artifact helpers
_console_logs = []
def attach_console(page):
    try:
        page.on("console", lambda msg: _console_logs.append(f"{msg.type}: {msg.text}"))
    except Exception:
        pass

def save_artifacts(page, tag):
    ts = int(time.time())
    base = DEBUG_DIR / f"{ts}_{tag}"
    out = []
    try:
        png = base.with_suffix(".png")
        page.screenshot(path=str(png), full_page=True)
        out.append(str(png))
    except Exception as e:
        logger.debug("screenshot failed: %s", e)
    try:
        html = base.with_suffix(".html")
        html.write_text(page.content())
        out.append(str(html))
    except Exception as e:
        logger.debug("html dump failed: %s", e)
    try:
        logf = base.with_suffix(".log")
        logf.write_text("\n".join(_console_logs))
        out.append(str(logf))
    except Exception:
        pass
    print("[ARTIFACTS] " + " ".join(out))
    if GCS_BUCKET:
        upload_to_gcs(out)
    return out

def upload_to_gcs(paths):
    try:
        from google.cloud import storage
    except Exception as e:
        logger.warning("google-cloud-storage not available: %s", e)
        return []
    uploaded = []
    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        prefix = f"7zap/{int(time.time())}"
        for p in paths:
            blob = bucket.blob(f"{prefix}/{Path(p).name}")
            blob.upload_from_filename(p)
            uploaded.append(f"gs://{GCS_BUCKET}/{prefix}/{Path(p).name}")
        print("[GCS UPLOAD] " + " ".join(uploaded))
    except Exception as e:
        logger.warning("GCS upload failed: %s", e)
    return uploaded

# --- Main flow -------------------------------------------------------------
def require_args():
    if len(sys.argv) < 3:
        print("Usage: python get_ac_parts.py <vin> <part>")
        sys.exit(1)
    vin = sys.argv[1].strip()
    part = " ".join(sys.argv[2:]).strip().lower()
    return vin, part

def validate_env():
    if not (ZAP_USER and ZAP_PASS):
        logger.error("ZAP_USER/ZAP_PASS missing")
        print("ZAP_USER/ZAP_PASS are required")
        sys.exit(2)

def find_vin_input(page, timeout=15000):
    candidates = [
        "#mainSearchInput",
        "input#mainSearchInput",
        "input[placeholder*='VIN' i]",
        "input[name*='vin' i]",
        "input[type='search']",
        "input.search-input",
    ]
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=timeout)
            return loc
        except PlaywrightTimeout:
            continue
    return None

def extract_parts_for(page, part):
    parts = []
    if part == "compressor":
        page.locator(".zp-element-title.nodeTitle", has_text="Compressor / Parts").first.click()
        page.locator(".zp-element-title.nodeTitle", has_text="HEATING & AIR CONDITIONING - COMPRESSOR").first.click()
        rows = page.locator("div.px-1.flex-grow-1 > span", has_text="COMPRESSOR ASSY")
    elif part == "evaporator":
        page.locator(".zp-element-title.nodeTitle", has_text="Controls / Regulation").first.click()
        page.locator(".zp-element-title.nodeTitle", has_text="HEATING & AIR CONDITIONING - COOLER UNIT").first.click()
        rows = page.locator("div.px-1.flex-grow-1 > span", has_text="EVAPORATOR SUB-ASSY")
    elif part == "expansion valve":
        page.locator(".zp-element-title.nodeTitle", has_text="Controls / Regulation").first.click()
        page.locator(".zp-element-title.nodeTitle", has_text="HEATING & AIR CONDITIONING - COOLER UNIT").first.click()
        rows = page.locator("div.px-1.flex-grow-1 > span", has_text="VALVE")
    else:
        return parts
    try:
        rows.first.wait_for(state="attached", timeout=20000)
        count = rows.count()
        for i in range(count):
            try:
                num = rows.nth(i).locator("strong").inner_text().strip()
                if num:
                    parts.append(num)
            except Exception:
                continue
    except PlaywrightTimeout:
        logger.debug("rows did not appear for part=%s", part)
    return parts

def main():
    vin, part = require_args()
    validate_env()
    logger.info("VIN=%s part=%s headless=%s", vin, part, HEADLESS)

    try:
        with Camoufox(headless=HEADLESS, humanize=False, window=(1366, 864)) as browser:
            page = browser.new_page()
            attach_console(page)
            try:
                # prefer explicit english landing to stabilise UI
                page.goto("https://7zap.com/en/", timeout=60000)
            except Exception:
                page.goto("https://7zap.com", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            short_sleep()
            maybe_scroll(page)

            # accept cookie banners (best-effort)
            try:
                consent = page.locator("button:has-text('Accept'), button:has-text('I agree'), #onetrust-accept-btn-handler").first
                if consent and consent.is_visible():
                    click_like_human(page, consent)
                    short_sleep()
            except Exception:
                pass

            # open login
            login_icon = page.locator("a:has(i.fa-user), a.account, .cabinet-link, a[href*='login']").first
            try:
                click_like_human(page, login_icon)
            except PlaywrightTimeout:
                logger.debug("login icon not clickable; continuing")

            short_sleep()
            # try to fill creds if modal exists
            try:
                panel = page.locator("div.cabinet-panel-on").first
                if panel and panel.is_visible():
                    user_input = panel.locator("input").nth(0)
                    pass_input = panel.locator("input").nth(1)
                    click_like_human(page, user_input)
                    type_like_human(page, user_input, ZAP_USER)
                    short_sleep()
                    click_like_human(page, pass_input)
                    type_like_human(page, pass_input, ZAP_PASS)
                    short_sleep()
                    submit_btn = panel.locator("button:has-text('Login'), button[type='submit']").first
                    try:
                        click_like_human(page, submit_btn)
                    except Exception:
                        pass
            except Exception:
                logger.debug("login panel not found or login failed")

            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
            maybe_long = random.random()
            if maybe_long < 0.3:
                short_sleep(0.5, 1.2)

            # Focus / open search
            try:
                search_toggle = page.locator(".search.w-100, .search-toggle, .search-box").first
                if search_toggle:
                    try:
                        click_like_human(page, search_toggle)
                    except Exception:
                        pass
            except Exception:
                pass

            vin_input = find_vin_input(page, timeout=20000)
            if vin_input is None:
                # try opening search via keyboard
                try:
                    page.keyboard.press("/")
                    short_sleep(0.15, 0.4)
                    vin_input = find_vin_input(page, timeout=8000)
                except Exception:
                    vin_input = None

            if vin_input is None:
                save_artifacts(page, "vin_input_missing")
                raise PlaywrightTimeout("VIN input not found")

            click_like_human(page, vin_input)
            type_like_human(page, vin_input, vin)
            short_sleep(0.25, 0.6)

            # wait for results and click first modification
            table = page.locator("#htmlTableModifications, .modifications-table").first
            try:
                first_mod = table.locator("a").first
                first_mod.wait_for(state="visible", timeout=45000)
                maybe_scroll(page)
                click_like_human(page, first_mod, timeout=45000)
            except PlaywrightTimeout:
                save_artifacts(page, "first_mod_missing")
                raise PlaywrightTimeout("First modification not found")

            page.wait_for_load_state("domcontentloaded", timeout=30000)
            short_sleep(1.2, 2.6)

            # expand and navigate to AC section
            try:
                ac = page.locator(".zp-element-title.nodeTitle", has_text="Air Conditioning").first
                ac.wait_for(state="visible", timeout=45000)
                ac.scroll_into_view_if_needed()
                click_like_human(page, ac)
            except PlaywrightTimeout:
                save_artifacts(page, "ac_section_missing")
                raise PlaywrightTimeout("Air Conditioning section not found")

            page.wait_for_load_state("domcontentloaded", timeout=30000)
            short_sleep(1.2, 2.6)

            part_nums = extract_parts_for(page, part)
            logger.info("Extracted %d parts for %s", len(part_nums), part)
            print(json.dumps(part_nums, indent=1))
            return 0

    except PlaywrightTimeout as e:
        logger.error("Operation timed out: %s", e)
        # ensure artifacts printed to stdout so server can capture paths
        try:
            # if page exists in scope, best-effort artifact saved earlier
            pass
        except Exception:
            pass
        print("Operation timed out")
        return 3
    except PlaywrightError as e:
        logger.exception("Playwright error")
        print(f"Error: {e}")
        return 1
    except SystemExit:
        raise
    except Exception as e:
        logger.exception("Unhandled error")
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    try:
        rc = main()
        if isinstance(rc, int) and rc != 0:
            sys.exit(rc)
    except SystemExit:
        raise
    except Exception as e:
        logger.exception("Fatal")
        print(f"Error: {e}")
        sys.exit(1)