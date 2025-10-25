#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
7zap/get_ac_parts.py

Fully rewritten with:
- Timestamped DEBUG/INFO/WARN/ERROR logs to stderr
- Camoufox -> Chromium fallback (toggle with USE_CAMOUFOX=0)
- Stable browser context (locale, UA, viewport, timezone)
- Overlay dismissal and modal-close assertion
- Robust VIN input discovery (multiple selectors + retries)
- Resilient catalog interactions (no_wait_after, JS/force click fallback)
- Diagnostics on failure (URL, HTML slice, screenshot in /tmp)
- Final JSON ONLY to stdout; sentinel EXITING_WITH=<code> to stderr
"""

import sys
import os
import time
import random
import math
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv

# =============================== Logging ======================================

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def _json(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)

def _log(level: str, msg: str, **kv):
    line = f"[{_ts()}] {level} 7zap.get_ac_parts: {msg}"
    if kv:
        line += " " + _json(kv)
    print(line, file=sys.stderr, flush=True)

def DEBUG(msg, **kv): _log("DEBUG", msg, **kv)
def INFO(msg, **kv):  _log("INFO",  msg, **kv)
def WARN(msg, **kv):  _log("WARN",  msg, **kv)
def ERROR(msg, **kv): _log("ERROR", msg, **kv)

def hard_exit(code: int):
    print(f"EXITING_WITH={code}", file=sys.stderr, flush=True)
    try:
        sys.exit(code)
    finally:
        os._exit(code)

# ============================ Humanization ====================================

HUMAN_DELAY_RANGE = (0.18, 0.58)
HUMAN_CLICK_HESITATION = (0.05, 0.18)
HUMAN_LONG_THINK = (0.6, 1.2)
TYPE_DELAY_RANGE_MS = (55, 160)
MOUSE_STEPS_RANGE = (18, 42)
SCROLL_CHANCE = 0.35
SCROLL_PIXELS = (180, 800)

_MOUSE_POS = [random.randint(30, 200), random.randint(120, 300)]

def human_sleep(a=None, b=None):
    lo, hi = (a, b) if a is not None else HUMAN_DELAY_RANGE
    dur = random.uniform(lo, hi)
    DEBUG("Sleeping", seconds=round(dur, 3))
    time.sleep(dur)

def maybe_long_think(p=0.22):
    if random.random() < p:
        DEBUG("Long think triggered")
        human_sleep(*HUMAN_LONG_THINK)
    else:
        DEBUG("Long think skipped")

def _bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        (u**3) * p0[0] + 3 * (u**2) * t * p1[0] + 3 * u * (t**2) * p2[0] + (t**3) * p3[0],
        (u**3) * p0[1] + 3 * (u**2) * t * p1[1] + 3 * u * (t**2) * p2[1] + (t**3) * p3[1],
    )

def move_mouse_curve(page, tx, ty):
    global _MOUSE_POS
    sx, sy = _MOUSE_POS
    ex, ey = float(tx), float(ty)

    dist = math.hypot(ex - sx, ey - sy) + 1
    angle = math.atan2(ey - sy, ex - sx)
    r = dist / 2
    wobble1 = random.uniform(-0.35, 0.35)
    wobble2 = random.uniform(-0.35, 0.35)
    c1 = (sx + r * math.cos(angle + wobble1), sy + r * math.sin(angle + wobble1))
    c2 = (sx + r * math.cos(angle + wobble2), sy + r * math.sin(angle + wobble2))

    steps = random.randint(*MOUSE_STEPS_RANGE)
    DEBUG("Mouse move",
          start=[round(sx,1), round(sy,1)],
          end=[round(ex,1), round(ey,1)],
          c1=[round(c1[0],1), round(c1[1],1)],
          c2=[round(c2[0],1), round(c2[1],1)],
          steps=steps)
    for i in range(1, steps + 1):
        t = i / steps
        x, y = _bezier((sx, sy), c1, c2, (ex, ey), t)
        page.mouse.move(float(x), float(y), steps=1)

    jit = random.randint(0, 2)
    DEBUG("Micro-jitters", count=jit)
    for _ in range(jit):
        page.mouse.move(ex + random.uniform(-1.5, 1.5), ey + random.uniform(-1.5, 1.5), steps=1)

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
        DEBUG("No bbox; fallback to locator.click()")
        locator.click()
        return
    tx = bbox["x"] + random.uniform(bbox["width"] * 0.2, bbox["width"] * 0.8)
    ty = bbox["y"] + random.uniform(bbox["height"] * 0.2, bbox["height"] * 0.8)
    DEBUG("Click target", target=[round(tx,1), round(ty,1)], bbox=bbox)
    move_mouse_curve(page, tx, ty)
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

# ============================== Helpers =======================================

def wait_visible_css(page, selector: str, timeout=10000):
    DEBUG("wait_visible_css:start", selector=selector, timeout_ms=timeout)
    page.wait_for_function(
        """
        (sel) => {
          const el = document.querySelector(sel);
          if (!el) return false;
          const s = getComputedStyle(el);
          const r = el.getBoundingClientRect();
          const hidden = s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0';
          return !hidden && r.width > 0 && r.height > 0;
        }
        """,
        selector,
        timeout=timeout
    )
    DEBUG("wait_visible_css:ok", selector=selector)

def dismiss_overlays(page):
    DEBUG("Dismiss overlays: attempt")
    sels = [
        "button:has-text('Accept')",
        "[id*='consent'] button:has-text('Accept')",
        "[class*='consent'] button",
        "button:has-text('I agree')",
        "button:has-text('Got it')",
    ]
    for sel in sels:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=1200)
            el.click(timeout=1200)
            page.wait_for_timeout(250)
            DEBUG("Overlay dismissed", selector=sel)
            break
        except Exception:
            continue

def dump_diag(page, tag: str):
    try:
        url = page.url
        content = page.content()[:8000]
        path = f"/tmp/{tag}-{int(time.time())}.png"
        page.screenshot(path=path, full_page=True)
        DEBUG("diag", url=url, screenshot=path)
        print(content, file=sys.stderr, flush=True)
    except Exception as e:
        ERROR("diag_dump_failed", err=str(e))

def list_inputs(page, tag: str):
    try:
        inputs = page.evaluate("""
            () => Array.from(document.querySelectorAll('input')).map(el => {
              const s = getComputedStyle(el);
              const r = el.getBoundingClientRect();
              const visible = !(s.display==='none'||s.visibility==='hidden'||s.opacity==='0') && r.width>0 && r.height>0;
              return {id: el.id||null, name: el.name||null, type: el.type||null, placeholder: el.placeholder||null, visible};
            })
        """)
        DEBUG(f"Input inventory ({tag})", count=len(inputs))
        for i, el in enumerate(inputs[:30]):
            DEBUG("input", idx=i, **el)
    except Exception as e:
        WARN("Failed to list inputs", err=str(e))

def find_vin_input(page, timeout_ms=8000):
    candidates = [
        "#mainSearchInput",
        "input[name='vin']",
        "input[id*='SearchInput' i]",
        "input[placeholder*='VIN' i]",
        "input[type='search']",
        "input[name*='search' i]",
    ]
    end = time.time() + (timeout_ms / 1000.0)
    while time.time() < end:
        for sel in candidates:
            try:
                loc = page.locator(sel).first
                loc.wait_for(state="attached", timeout=600)
                return loc
            except Exception:
                continue
        page.wait_for_timeout(200)
    DEBUG("VIN input not attached by selectors tried")
    return None

def try_open_search_ui(page):
    tried = False
    try:
        page.get_by_role("button", name=lambda n: n and "search" in n.lower()).first.click(timeout=1000)
        DEBUG("Search UI opened via role button")
        tried = True
    except Exception:
        pass
    if not tried:
        try:
            page.locator(".search.w-100").first.click(timeout=1000)
            DEBUG("Search UI opened via .search.w-100")
            tried = True
        except Exception:
            pass
    if not tried:
        try:
            page.keyboard.press("/")
            DEBUG("Search UI opened via '/' key")
        except Exception:
            pass
    page.wait_for_timeout(400)

def click_safely(locator, label="(unnamed)", timeout=8000):
    locator = locator.first
    locator.wait_for(state="attached", timeout=timeout)
    try:
        locator.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    try:
        locator.wait_for(state="visible", timeout=timeout)
    except Exception:
        DEBUG("click_safely: not visible, attempting JS click anyway", label=label)

    try:
        locator.click(no_wait_after=True, timeout=timeout)
        DEBUG("click_safely: normal click ok", label=label)
        return
    except Exception as e:
        WARN("click_safely: normal click failed", label=label, err=str(e))
    try:
        locator.evaluate("(el)=>el.click()")
        DEBUG("click_safely: JS click ok", label=label)
        return
    except Exception as e:
        WARN("click_safely: JS click failed", label=label, err=str(e))
    try:
        locator.click(force=True, no_wait_after=True, timeout=timeout)
        DEBUG("click_safely: force click ok", label=label)
        return
    except Exception as e:
        ERROR("click_safely: force click failed", label=label, err=str(e))
        raise

def wait_for_catalog_ready(page, timeout_ms=15000):
    DEBUG("wait_for_catalog_ready:start", timeout_ms=timeout_ms)
    page.wait_for_function(
        """
        () => {
          const nodes = document.querySelectorAll('.zp-element-title.nodeTitle');
          return nodes && nodes.length > 3;
        }
        """,
        timeout=timeout_ms
    )
    page.wait_for_timeout(200)
    try:
        titles = page.evaluate("""
          () => Array.from(document.querySelectorAll('.zp-element-title.nodeTitle'))
                      .map(e => e.textContent.trim()).slice(0, 50)
        """)
        DEBUG("catalog_titles", count=len(titles))
        for i, t in enumerate(titles):
            DEBUG("catalog_title", idx=i, title=t)
    except Exception as e:
        WARN("could not list catalog titles", err=str(e))
    DEBUG("wait_for_catalog_ready:ok")

# ============================ Browser launcher =================================

def launch_browser():
    use_camoufox = os.getenv("USE_CAMOUFOX", "1") == "1"
    if use_camoufox:
        try:
            from camoufox.sync_api import Camoufox
            INFO("Launching Camoufox browser", headless=True)
            return ("camoufox", Camoufox(headless=True, humanize=False, window=(1366, 864)))
        except Exception as e:
            ERROR("Camoufox launch failed; falling back", err=str(e))
    # Fallback to Chromium with safe container flags
    from playwright.sync_api import sync_playwright
    class PWWrapper:
        def __enter__(self):
            self.pw = sync_playwright().start()
            args = ["--no-sandbox","--disable-dev-shm-usage","--disable-gpu","--no-zygote","--single-process"]
            INFO("Launching Chromium fallback", headless=True, args=" ".join(args))
            self.browser = self.pw.chromium.launch(headless=True, args=args)
            return self.browser
        def __exit__(self, *a):
            try: self.browser.close()
            finally: self.pw.stop()
    return ("chromium", PWWrapper())

# ================================ Main ========================================

def main() -> int:
    t0 = time.time()
    INFO("Script start")
    DEBUG("argv", argv=sys.argv)

    load_dotenv()
    user = os.getenv("ZAP_USER")
    pwd  = os.getenv("ZAP_PASS")
    INFO("Env present",
         ZAP_USER=bool(user),
         ZAP_PASS=bool(pwd),
         USE_CAMOUFOX=os.getenv("USE_CAMOUFOX","unset"),
         CAMOUFOX_CACHE_DIR=os.getenv("CAMOUFOX_CACHE_DIR","unset"))

    if len(sys.argv) < 3:
        ERROR("Bad args; usage: python get_ac_parts.py <vin> <part>")
        print("[]")
        return 2
    if not (user and pwd):
        ERROR("Missing creds", need="ZAP_USER,ZAP_PASS")
        print("[]")
        return 2

    vin  = sys.argv[1].strip()
    part = " ".join(sys.argv[2:]).strip().lower()
    INFO("Inputs", vin=vin, part=part)

    browser_kind, wrapper = launch_browser()
    page = None
    ctx = None
    part_nums = []

    try:
        with wrapper as browser:
            # Prefer a context for stable UA/locale
            try:
                ctx = browser.new_context(
                    locale="en-US",
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                    viewport={"width": 1366, "height": 864},
                    timezone_id="Africa/Cairo",
                )
                page = ctx.new_page()
                DEBUG("New page created", engine=browser_kind)
            except Exception:
                page = browser.new_page()
                DEBUG("New page created (no context)", engine=browser_kind)

            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)

            # --- Home
            INFO("Navigating", url="https://7zap.com/en/")
            page.goto("https://7zap.com/en/", wait_until="domcontentloaded")
            DEBUG("DOM content loaded")
            human_sleep()
            maybe_scroll(page)
            dismiss_overlays(page)

            # --- Login
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

            login_panel = page.locator("div.cabinet-panel-on")
            try:
                login_panel.wait_for(state="hidden", timeout=10000)
                DEBUG("Login panel hidden")
            except Exception:
                try:
                    page.locator(".modal .btn-close, .modal [data-dismiss='modal'], .modal .close").first.click(timeout=1500)
                    login_panel.wait_for(state="hidden", timeout=5000)
                    DEBUG("Login panel closed by close button")
                except Exception:
                    ERROR("Login panel did not close; interactions may be blocked")
                    dump_diag(page, "login_panel_stuck")
                    print("[]")
                    return 10

            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(300)
            dismiss_overlays(page)

            # --- VIN Search (robust)
            INFO("Focusing search box")
            list_inputs(page, "before-open")
            try_open_search_ui(page)

            vin_input = find_vin_input(page, timeout_ms=8000)
            if not vin_input:
                dismiss_overlays(page)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(300)
                try_open_search_ui(page)
                vin_input = find_vin_input(page, timeout_ms=8000)

            if not vin_input:
                ERROR("VIN input missing after attempts")
                list_inputs(page, "after-open-fail")
                dump_diag(page, "vin_input_missing")
                print("[]")
                return 11

            try:
                try:
                    wait_visible_css(page, "#mainSearchInput", timeout=3000)
                except Exception:
                    try:
                        vin_input.scroll_into_view_if_needed(timeout=1000)
                    except Exception:
                        pass
                    try:
                        page.evaluate("(el)=>el.focus()", vin_input)
                    except Exception:
                        pass

                click_like_human(page, vin_input)
                type_like_human(page, vin_input, vin)
            except Exception as e:
                ERROR("Failed to interact with VIN input", err=str(e))
                list_inputs(page, "interact-fail")
                dump_diag(page, "vin_interact_fail")
                print("[]")
                return 12

            maybe_long_think()

            # --- First modification
            INFO("Selecting first modification")
            table = page.locator("#htmlTableModifications")
            first_mod = table.locator("a").first
            first_mod.wait_for(state="visible")
            maybe_scroll(page)
            click_like_human(page, first_mod)

            # Ensure the catalog page is fully ready
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_load_state("networkidle")
            human_sleep()

            # --- Air Conditioning tree (resilient)
            INFO("Opening Air Conditioning tree")
            try:
                wait_for_catalog_ready(page, timeout_ms=20000)
                ac_node = page.locator(".zp-element-title.nodeTitle", has_text="Air Conditioning").first
                click_safely(ac_node, label="Air Conditioning")
                page.wait_for_timeout(400)
            except Exception as e:
                ERROR("Failed to open Air Conditioning node", err=str(e))
                dump_diag(page, "ac_node_click_fail")
                print("[]")
                return 13

            human_sleep(1.5, 2.2)

            # --- Branch selection
            INFO("Scrape branch", part=part)
            if part == "compressor":
                click_safely(
                    page.locator(".zp-element-title.nodeTitle", has_text="Compressor / Parts"),
                    label="Compressor / Parts",
                )
                page.wait_for_timeout(300)
                click_safely(
                    page.locator(".zp-element-title.nodeTitle",
                                 has_text="HEATING & AIR CONDITIONING - COMPRESSOR[]").nth(0),
                    label="HEATING & AIR CONDITIONING - COMPRESSOR[]",
                )
                page.wait_for_load_state("domcontentloaded")
                rows = page.locator("div.px-1.flex-grow-1 > span", has_text="COMPRESSOR ASSY")

            elif part == "evaporator":
                click_safely(
                    page.locator(".zp-element-title.nodeTitle", has_text="Controls / Regulation"),
                    label="Controls / Regulation",
                )
                page.wait_for_timeout(300)
                click_safely(
                    page.locator(".zp-element-title.nodeTitle",
                                 has_text="HEATING & AIR CONDITIONING - COOLER UNIT").nth(0),
                    label="HEATING & AIR CONDITIONING - COOLER UNIT",
                )
                page.wait_for_load_state("domcontentloaded")
                rows = page.locator("div.px-1.flex-grow-1 > span", has_text="EVAPORATOR SUB-ASSY")

            elif part == "expansion valve":
                click_safely(
                    page.locator(".zp-element-title.nodeTitle", has_text="Controls / Regulation"),
                    label="Controls / Regulation",
                )
                page.wait_for_timeout(300)
                click_safely(
                    page.locator(".zp-element-title.nodeTitle",
                                 has_text="HEATING & AIR CONDITIONING - COOLER UNIT").nth(0),
                    label="HEATING & AIR CONDITIONING - COOLER UNIT",
                )
                page.wait_for_load_state("domcontentloaded")
                rows = page.locator("div.px-1.flex-grow-1 > span", has_text="VALVE")

            else:
                ERROR("Unsupported part", allowed=["compressor", "evaporator", "expansion valve"])
                print("[]")
                return 4

            # --- Extract rows
            rows.first.wait_for(state="attached", timeout=15000)
            cnt = rows.count()
            DEBUG("Row count", count=cnt)
            for i in range(cnt):
                try:
                    num = rows.nth(i).locator("strong").inner_text(timeout=3000)
                    if num:
                        part_nums.append(num)
                except Exception:
                    WARN("Failed to read row", index=i)

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
        INFO("Script end", elapsed_s=round(time.time() - t0, 2))

# ============================== Entrypoint ====================================

if __name__ == "__main__":
    code = main()
    hard_exit(code)
