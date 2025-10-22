import sys
import os
import time
import random
import math
import json
from dotenv import load_dotenv

# Camoufox (Playwright-compatible API)
from camoufox.sync_api import Camoufox
from playwright.sync_api import TimeoutError

load_dotenv()

user = os.getenv("ZAP_USER")
pwd = os.getenv("ZAP_PASS")

# Tunables for "humanization"
HUMAN_DELAY_RANGE = (0.18, 0.58)   # short pauses between actions
HUMAN_CLICK_HESITATION = (0.05, 0.18)
HUMAN_LONG_THINK = (0.6, 1.2)      # occasional longer pause
TYPE_DELAY_RANGE_MS = (55, 160)    # per-key type delay in ms
MOUSE_STEPS_RANGE = (18, 42)       # path smoothness
SCROLL_CHANCE = 0.35
SCROLL_PIXELS = (180, 800)

# Track a "current" mouse position (best-effort)
_MOUSE_POS = [random.randint(30, 200), random.randint(120, 300)]

AC_PARTS_KEYWORDS = ["compressor", "condenser", "evaporator", "expansion valve"]

def human_sleep(a=None, b=None):
    lo, hi = (a, b) if a is not None else HUMAN_DELAY_RANGE
    time.sleep(random.uniform(lo, hi))


def maybe_long_think(p=0.22):
    if random.random() < p:
        human_sleep(*HUMAN_LONG_THINK)


def bezier(p0, p1, p2, p3, t):
    # Cubic Bezier interpolation
    u = 1 - t
    return (
        (u**3) * p0[0] + 3 * (u**2) * t * p1[0] + 3 * u * (t**2) * p2[0] + (t**3) * p3[0],
        (u**3) * p0[1] + 3 * (u**2) * t * p1[1] + 3 * u * (t**2) * p2[1] + (t**3) * p3[1],
    )


def move_mouse_curve(page, target_x, target_y):
    global _MOUSE_POS
    sx, sy = _MOUSE_POS
    ex, ey = float(target_x), float(target_y)

    # Create 2 control points with some wobble
    dist = math.hypot(ex - sx, ey - sy) + 1
    angle = math.atan2(ey - sy, ex - sx)
    r = dist / 2.0
    wobble1 = random.uniform(-0.35, 0.35)
    wobble2 = random.uniform(-0.35, 0.35)
    c1 = (sx + r * math.cos(angle + wobble1), sy + r * math.sin(angle + wobble1))
    c2 = (sx + r * math.cos(angle + wobble2), sy + r * math.sin(angle + wobble2))

    steps = random.randint(*MOUSE_STEPS_RANGE)
    for i in range(1, steps + 1):
        t = i / steps
        x, y = bezier((sx, sy), c1, c2, (ex, ey), t)
        page.mouse.move(float(x), float(y), steps=1)

    # Micro-correction/jitter near the target
    for _ in range(random.randint(0, 2)):
        jitter_x = ex + random.uniform(-1.5, 1.5)
        jitter_y = ey + random.uniform(-1.5, 1.5)
        page.mouse.move(jitter_x, jitter_y, steps=1)

    _MOUSE_POS = [ex, ey]


def locator_bbox(page, locator):
    locator.wait_for(state="visible")
    locator.scroll_into_view_if_needed()
    bbox = locator.bounding_box()
    if not bbox:
        # Fallback: hover to force layout
        locator.hover()
        bbox = locator.bounding_box()
    return bbox


def click_like_human(page, locator):
    bbox = locator_bbox(page, locator)
    if not bbox:
        locator.click()
        return

    target_x = bbox["x"] + random.uniform(bbox["width"] * 0.2, bbox["width"] * 0.8)
    target_y = bbox["y"] + random.uniform(bbox["height"] * 0.2, bbox["height"] * 0.8)

    move_mouse_curve(page, target_x, target_y)
    human_sleep(*HUMAN_CLICK_HESITATION)
    page.mouse.down()
    human_sleep(0.03, 0.09)
    page.mouse.up()
    human_sleep()


def type_like_human(page, locator, text):
    locator.click()
    human_sleep(0.08, 0.2)
    for ch in text:
        if random.random() < 0.06:
            human_sleep(0.22, 0.55)
        page.keyboard.type(ch, delay=random.randint(*TYPE_DELAY_RANGE_MS))


def maybe_scroll(page):
    if random.random() < SCROLL_CHANCE:
        page.mouse.wheel(0, random.randint(*SCROLL_PIXELS))
        human_sleep(0.2, 0.5)


def main():
    if len(sys.argv) < 3:
        print("Usage: python get_ac_parts.py <vin> <part>")
        sys.exit(1)

    if not (user and pwd):
        print("ZAP_USER/ZAP_PASS are required (set in your environment or .env)")
        sys.exit(2)

    vin = sys.argv[1]
    part = " ".join(sys.argv[2:])  

    # Camoufox context (Playwright-like API), with humanize enabled
    with Camoufox(
        headless=True,
        humanize=False,
        window=(1366, 864)
    ) as browser:
        page = browser.new_page()

        # Open site
        page.goto("https://7zap.com")
        page.wait_for_load_state("domcontentloaded")
        human_sleep()
        maybe_scroll(page)

        # Open login modal
        login_icon = page.locator(
            "div.row.px-md-4.py-md-2 > div > div.d-none.d-md-block.p-2.px-0.ml-lg-5.__text-center__.d-md-flex.align-content-center.flex-wrap > a > i"
        )
        click_like_human(page, login_icon)
        maybe_long_think()

        # Fill creds
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

        # Submit
        submit_btn = panel.locator("div > div:nth-child(2) > div > button")
        click_like_human(page, submit_btn)

        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2500)
        maybe_long_think()

        # Focus search
        search_box_toggle = page.locator(".search.w-100")
        click_like_human(page, search_box_toggle)
        human_sleep()
        print(f"page content: {page.locator('body').inner_html()}")
        vin_input = page.locator("#mainSearchInput")
        click_like_human(page, vin_input)
        type_like_human(page, vin_input, vin)
        maybe_long_think()

        # Open first modification result
        table = page.locator("#htmlTableModifications")
        first_mod = table.locator("a").first
        first_mod.wait_for(state="visible")
        maybe_scroll(page)
        click_like_human(page, first_mod)

        page.wait_for_load_state("domcontentloaded")
        human_sleep()

        

        # Let content expand/load
        human_sleep(2.5, 4.2)
        
        page.locator(".zp-element-title.nodeTitle",has_text="Air Conditioning").click()
        page.wait_for_load_state("domcontentloaded")
        human_sleep(2.5, 4.2)
        part_nums = []
        if part == "compressor":
            page.locator(".zp-element-title.nodeTitle",has_text="Compressor / Parts").click()
            page.wait_for_load_state("domcontentloaded")
            page.locator(".zp-element-title.nodeTitle",has_text="HEATING & AIR CONDITIONING - COMPRESSOR[]").nth(0).click()
            page.wait_for_load_state("domcontentloaded")
            ##\38 8310li > div > div.px-1.flex-grow-1 > span
            rows = page.locator("div.px-1.flex-grow-1 > span",has_text="COMPRESSOR ASSY")
            rows.first.wait_for(state="attached")
            #print(rows.count())
            for i in range(rows.count()):
                num = rows.nth(i).locator("strong").inner_text()
                part_nums.append(num)
        elif part == "evaporator":
            page.locator(".zp-element-title.nodeTitle",has_text="Controls / Regulation").click()
            page.wait_for_load_state("domcontentloaded")
            page.locator(".zp-element-title.nodeTitle",has_text="HEATING & AIR CONDITIONING - COOLER UNIT").nth(0).click()
            page.wait_for_load_state("domcontentloaded")
            ##\38 8310li > div > div.px-1.flex-grow-1 > span
            rows = page.locator("div.px-1.flex-grow-1 > span",has_text="EVAPORATOR SUB-ASSY")
            rows.first.wait_for(state="attached")
            #print(rows.count())
            for i in range(rows.count()):
                num = rows.nth(i).locator("strong").inner_text()
                part_nums.append(num)  
        elif part == "expansion valve":
            page.locator(".zp-element-title.nodeTitle",has_text="Controls / Regulation").click()
            page.wait_for_load_state("domcontentloaded")
            page.locator(".zp-element-title.nodeTitle",has_text="HEATING & AIR CONDITIONING - COOLER UNIT").nth(0).click()
            page.wait_for_load_state("domcontentloaded")
            ##\38 8310li > div > div.px-1.flex-grow-1 > span
            rows = page.locator("div.px-1.flex-grow-1 > span",has_text="VALVE")
            rows.first.wait_for(state="attached")
            #print(rows.count())
            for i in range(rows.count()):
                num = rows.nth(i).locator("strong").inner_text()
                part_nums.append(num)  
        
        print(json.dumps(part_nums,indent=1))
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except TimeoutError:
        print("Operation timed out")
        sys.exit(3)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)