#!/usr/bin/env python3
import sys
import os
import time
import random
import math
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Prefer Camoufox; fallback to Playwright Chromium if unavailable or disabled
USE_CAMOUFOX = os.getenv("USE_CAMOUFOX", "1") == "1"

# ---- Logging helpers (stderr) ------------------------------------------------
def _ts():
    return datetime.now().strftime("%H:%M:%S")

def log(level, msg, **kv):
    line = f"[{_ts()}] {level} 7zap.get_ac_parts: {msg}"
    if kv:
        try:
            extra = " " + json.dumps(kv, ensure_ascii=False, default=str)
        except Exception:
            extra = " " + str(kv)
        line += extra
    print(line, file=sys.stderr, flush=True)

def DEBUG(msg, **kv): log("DEBUG", msg, **kv)
def INFO(msg, **kv):  log("INFO", msg, **kv)
def WARN(msg, **kv):  log("WARN", msg, **kv)
def ERROR(msg, **kv): log("ERROR", msg, **kv)

# ---- Hard exit to avoid lingering threads -----------------------------------
def hard_exit(code: int):
    # Sentinel for your Node wrapper to capture
    print(f"EXITING_WITH={code}", file=sys.stderr, flush=True)
    try:
        sys.exit(code)
    finally:
        os._exit(code)

# ---- Humanization tunables ---------------------------------------------------
HUMAN_DELAY_RANGE = (0.18, 0.58)
HUMAN_CLICK_HESITATION = (0.05, 0.18)
HUMAN_LONG_THINK = (0.6, 1.2)
TYPE_DELAY_RANGE_MS = (55, 160)
MOUSE_STEPS_RANGE = (18, 42)
SCROLL_CHANCE = 0.35
SCROLL_PIXELS = (180, 800)
_MOUSE_POS = [random.randint(30, 200), random.randint(120, 300)]

# ---- Humanization helpers ----------------------------------------------------
def human_sleep(a=None, b=None):
    lo, hi = (a, b) if a is not None else HUMAN_DELAY_RANGE
    t = random.uniform(lo, hi)
    DEBUG("Sleeping", seconds=round(t, 3))
    time.sleep(t)

def maybe_long_think(p=0.22):
    if random.random() < p:
        DEBUG("Long think triggered")
        human_sleep(*HUMAN_LONG_THINK)
    else:
        DEBUG("Long think skipped")

def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        (u**3) * p0[0] + 3 * (u**2) * t * p1[0] + 3 * u * (t**2) * p2[0] + (t**3) * p3[0],
        (u**3) * p0[1] + 3 * (u**2) * t * p1[1] + 3 * u * (t**2) * p2[1] + (t**3) * p3[1],
    )

def move_mouse_curve(page, target_x, target_y):
    global _MOUSE_POS
    sx, sy = _MOUSE_POS
    ex, ey = float(target_x), float(target_y)

    dist = math.hypot(ex - sx, ey - sy) + 1
    angle = math.atan2(ey - sy, ex - sx)
    r = dist / 2.0
    wobble1 = random.uniform(-0.35, 0.35)
    wobble2 = random.uniform(-0.35, 0.35)
    c1 = (sx + r * math.cos(angle + wobble1), sy + r * math.sin(angle + wobble1))
    c2 = (sx + r * math.cos(angle + wobble2), sy + r * math.sin(angle + wobble2))

    steps = random.randint(*MOUSE_STEPS_RANGE)
    DEBUG("Mouse move", start=(round(sx,1), round(sy,1)), end=(round(ex,1), round(ey,1)),
          c1=(round(c1[0],1), round(c1[1],1)), c2=(round(c2[0],1), round(c2[1],1)), steps=steps)
    for i in range(1, steps + 1):
        t = i / steps
        x, y = bezier((sx, sy), c1, c2, (ex, ey), t)
        page.mouse.move(float(x), float(y), steps=1)

    jitters = random.randint(0, 2)
    DEBUG("Micro-jitters", count=jitters)
    for _ in range(jitters):
        jitter_x = ex + random.uniform(-1.5, 1.5)
        jitter_y = ey + random.uniform(-1.5, 1.5)
        page.mouse.move(jitter_x, jitter_y, steps=1)

    _MOUSE_POS = [ex, ey]

def locator_bbox(page, locator):
    DEBUG("Waiting for locator visible + in view for bbox")
    locator.wait_for(state="visible")
    locator.scroll_into_view_if_needed()
    bbox = locator.bounding_box()
    if not bbox:
        locator.hover()
        bbox = locator.bounding_box()
    DEBUG("Locator bbox", bbox=bbox)
    return bbox

def click_like_human(page, locator):
    DEBUG("click_like_human: computing bbox and click position")
    bbox = locator_bbox(page, locator)
    if not bbox:
        DEBUG("No bbox; falling back to locator.click()")
        locator.click()
        return
    target_x = bbox["x"] + random.uniform(bbox["width"] * 0.2, bbox["width"] * 0.8)
    target_y = bbox["y"] + random.uniform(bbox["height"] * 0.2, bbox["height"] * 0.8)
    DEBUG("Click target", target=(round(target_x,1), round(target_y,1)), bbox=bbox)
    move_mouse_curve(page, target_x, target_y)
    human_sleep(*HUMAN_CLICK_HESITATION)
    page.mouse.down()
    human_sleep(0.03, 0.09)
    page.mouse.up()
    human_sleep()

def type_like_human(page, locator, text):
    DEBUG("Typing text", length=len(text), masked="*" * min(28, len(text)))
    locator.click()
    human_sleep(0.08, 0.2)
    for ch in text:
        if random.random() < 0.06:
            DEBUG("Typing pause")
            human_sleep(0.22, 0.55)
        page.keyboard.type(ch, delay=random.randint(*TYPE_DELAY_RANGE_MS))

def maybe_scroll(page):
    if random.random() < SCROLL_CHANCE:
        px = random.randint(*SCROLL_PIXELS)
        DEBUG("Scrolling", pixels=px)
        page.mouse.wheel(0, px)
        human_sleep(0.2, 0.5)
    else:
        DEBUG("Skipping scroll")

# ---- Robust helpers ----------------------------------------------------------
def wait_visible_css(page, selector: str, timeout=10000):
    DEBUG("wait_visible_css:start", selector=selector, timeout_ms=timeout)
    page.wait_for_function(
        """
        (sel) => {
          const el = document.querySelector(sel);
          if (!el) return false;
          const s = getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          const hidden = s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0';
          return !hidden && rect.width > 0 && rect.height > 0;
        }
        """,
        selector,
        timeout=timeout
    )
    DEBUG("wait_visible_css:ok", selector=selector)

def dismiss_overlays(page):
    DEBUG("Dismiss overlays: attempt")
    selectors = [
        "button:has-text('Accept')",
        "[id*='consent'] button:has-text('Accept')",
        "[class*='consent'] button",
        "button:has-text('I agree')",
        "button:has-text('Got it')",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=1200)
            el.click(timeout=1200)
            page.wait_for_timeout(250)
            DEBUG("Overlay dismissed", selector=sel)
            break
        except Exception:
            continue

def dump_diag(page, tag):
    try:
        url = page.url
        cont = page.content()[:6000]
        path = f"/tmp/{tag}-{int(time.time())}.png"
        page.screenshot(path=path, full_page=True)
        DEBUG("diag", url=url, screenshot=path)
        print(cont, file=sys.stderr, flush=True)
    except Exception as e:
        ERROR("diag_dump_failed", err=str(e))

# ---- Browser launcher (Camoufox -> Chromium fallback) -----------------------
def launch_browser():
    if USE_CAMOUFOX:
        try:
            from camoufox.sync_api import Camoufox
            INFO("Launching Camoufox browser", headless=True)
            return ("camoufox", Camoufox(headless=True, humanize=False, window=(1366, 864)))
        except Exception as e:
            ERROR("Camoufox launch failed; falling back", err=str(e))
    # Fallback to Playwright Chromium with safe container flags
    from playwright.sync_api import sync_playwright
    class PWWrapper:
        def __enter__(self):
            self.pw = sync_playwright().start()
            args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-zygote", "--single-process"]
            INFO("Launching Chromium fallback", headless=True, args=" ".join(args))
            self.browser = self.pw.chromium.launch(headless=True, args=args)
            return self.browser
        def __exit__(self, *a):
            try: self.browser.close()
            finally: self.pw.stop()
    return ("chromium", PWWrapper())

# ---- Main flow ---------------------------------------------------------------
def main():
    t0 = time.time()
    INFO("Script start")
    DEBUG("argv", argv=sys.argv)

    load_dotenv()
    user = os.getenv("ZAP_USER")
    pwd  = os.getenv("ZAP_PASS")

    INFO("Env present", ZAP_USER=bool(user), ZAP_PASS=bool(pwd),
         USE_CAMOUFOX=USE_CAMOUFOX, CAMOUFOX_CACHE_DIR=os.getenv("CAMOUFOX_CACHE_DIR","unset"))

    if len(sys.argv) < 3:
        print("[]")
        ERROR("Bad args; usage: python get_ac_parts.py <vin> <part>")
        return 2
    if not (user and pwd):
        print("[]")
        ERROR("Missing creds", need="ZAP_USER,ZAP_PASS")
        return 2

    vin  = sys.argv[1]
    part = " ".join(sys.argv[2:]).strip().lower()
    INFO("Inputs", vin=vin, part=part)

    browser_kind, wrapper = launch_browser()
    part_nums = []
    page = None
    ctx = None

    try:
        with wrapper as browser:
            # Create a context for stable UA/locale
            try:
                ctx = browser.new_context(
                    locale="en-US",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0" if browser_kind=="camoufox"
                               else None,
                    viewport={"width": 1366, "height": 864},
                    timezone_id="Africa/Cairo",
                )
                page = ctx.new_page()
                DEBUG("New page created", engine=browser_kind)
            except Exception:
                # Some wrappers don’t expose contexts; fallback to new_page()
                page = browser.new_page()
                DEBUG("New page created (no context)", engine=browser_kind)

            # Global timeouts
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)

            # --- Start navigating / logging in
            INFO("Navigating", url="https://7zap.com/en/")
            page.goto("https://7zap.com/en/", wait_until="domcontentloaded")
            DEBUG("DOM content loaded")
            human_sleep()
            maybe_scroll(page)
            dismiss_overlays(page)

            INFO("Opening login modal")
            login_icon = page.locator(
                "div.row.px-md-4.py-md-2 > div > div.d-none.d-md-block.p-2.px-0.ml-lg-5.__text-center__.d-md-flex.align-content-center.flex-wrap > a > i"
            )
            click_like_human(page, login_icon)
            maybe_long_think()

            INFO("Filling credentials")
            panel = page.locator(
                "#head > div.modal-mask.d-flex.align-content-center.flex-wrap1.dev1.pt-5 > div > div > div > div > div.cabinet-panel-on"
            ).locator("div").nth(0)

            user_input = panel.locator("input").nth(0)
            pass_input = panel.locator("input").nth(1)

            click_like_human(page, user_input)
            type_like_human(page, user_input, user or "")
            human_sleep()

            click_like_human(page, pass_input)
            type_like_human(page, pass_input, pwd or "")
            human_sleep()

            INFO("Submitting login form")
            submit_btn = panel.locator("div > div:nth-child(2) > div > button")
            click_like_human(page, submit_btn)

            # Assert modal closes (else later elements won't be visible)
            login_panel = page.locator("div.cabinet-panel-on")
            try:
                login_panel.wait_for(state="hidden", timeout=10000)
                DEBUG("Login panel hidden")
            except Exception:
                # Try a close button
                try:
                    page.locator(".modal .btn-close, .modal [data-dismiss='modal'], .modal .close").first.click(timeout=1500)
                    login_panel.wait_for(state="hidden", timeout=5000)
                    DEBUG("Login panel closed by close button")
                except Exception:
                    ERROR("Login panel did not close; interactions may be blocked")
                    dump_diag(page, "login_panel_stuck")
                    return 10

            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(300)
            dismiss_overlays(page)

            # --- Search VIN
            INFO("Focusing search box")
            try:
                # Try to open search toggle if present
                try:
                    page.get_by_role("button", name=lambda n: n and "search" in n.lower()).first.click(timeout=1500)
                    DEBUG("Search toggle clicked (role=button)")
                except Exception:
                    search_box_toggle = page.locator(".search.w-100")
                    click_like_human(page, search_box_toggle)
                    DEBUG("Search toggle clicked (.search.w-100)")

                wait_visible_css(page, "#mainSearchInput", timeout=15000)
            except Exception:
                ERROR("Search input not visible within timeout")
                dump_diag(page, "vin_input_timeout")
                return 11

            vin_input = page.locator("#mainSearchInput")
            try:
                click_like_human(page, vin_input)
                type_like_human(page, vin_input, vin)
            except Exception as e:
                ERROR("Failed to type VIN", err=str(e))
                dump_diag(page, "vin_type_fail")
                return 12
            maybe_long_think()

            # --- Open first modification
            INFO("Selecting first modification")
            table = page.locator("#htmlTableModifications")
            first_mod = table.locator("a").first
            first_mod.wait_for(state="visible")
            maybe_scroll(page)
            click_like_human(page, first_mod)
            page.wait_for_load_state("domcontentloaded")
            human_sleep()

            # --- Navigate to Air Conditioning section and scrape
            INFO("Opening Air Conditioning tree")
            page.locator(".zp-element-title.nodeTitle", has_text="Air Conditioning").click()
            page.wait_for_load_state("domcontentloaded")
            human_sleep(2.5, 4.2)

            part = part.strip().lower()
            INFO("Scrape branch", part=part)
            if part == "compressor":
                page.locator(".zp-element-title.nodeTitle", has_text="Compressor / Parts").click()
                page.wait_for_load_state("domcontentloaded")
                page.locator(".zp-element-title.nodeTitle", has_text="HEATING & AIR CONDITIONING - COMPRESSOR[]").nth(0).click()
                page.wait_for_load_state("domcontentloaded")
                rows = page.locator("div.px-1.flex-grow-1 > span", has_text="COMPRESSOR ASSY")
            elif part == "evaporator":
                page.locator(".zp-element-title.nodeTitle", has_text="Controls / Regulation").click()
                page.wait_for_load_state("domcontentloaded")
                page.locator(".zp-element-title.nodeTitle", has_text="HEATING & AIR CONDITIONING - COOLER UNIT").nth(0).click()
                page.wait_for_load_state("domcontentloaded")
                rows = page.locator("div.px-1.flex-grow-1 > span", has_text="EVAPORATOR SUB-ASSY")
            elif part == "expansion valve":
                page.locator(".zp-element-title.nodeTitle", has_text="Controls / Regulation").click()
                page.wait_for_load_state("domcontentloaded")
                page.locator(".zp-element-title.nodeTitle", has_text="HEATING & AIR CONDITIONING - COOLER UNIT").nth(0).click()
                page.wait_for_load_state("domcontentloaded")
                rows = page.locator("div.px-1.flex-grow-1 > span", has_text="VALVE")
            else:
                ERROR("Unsupported part", allowed=["compressor", "evaporator", "expansion valve"])
                print("[]")
                return 4

            rows.first.wait_for(state="attached")
            cnt = rows.count()
            DEBUG("Row count", count=cnt)
            for i in range(cnt):
                try:
                    num = rows.nth(i).locator("strong").inner_text(timeout=2000)
                    part_nums.append(num)
                except Exception:
                    # best-effort; keep going
                    WARN("Failed to read row", index=i)

        # End with wrapper context
        INFO("Scrape done", found=len(part_nums))
        print(json.dumps(part_nums, indent=1))
        return 0

    except Exception as e:
        ERROR("Unhandled exception", err=str(e))
        traceback.print_exc(file=sys.stderr)
        try:
            if page:
                dump_diag(page, "fatal")
        except Exception:
            pass
        print("[]")
        return 1

    finally:
        dt = round(time.time() - t0, 2)
        INFO("Script end", elapsed_s=dt)

# ---- Entrypoint --------------------------------------------------------------
if __name__ == "__main__":
    code = main()
    hard_exit(code)
