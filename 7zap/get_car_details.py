import sys
import os
import time
import random
import math
import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

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


def human_sleep(a=None, b=None):
    lo, hi = (a, b) if a is not None else HUMAN_DELAY_RANGE
    time.sleep(random.uniform(lo, hi))


def maybe_long_think(p=0.22):
    if random.random() < p:
        human_sleep(*HUMAN_LONG_THINK)


def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        (u**3) * p0[0] + 3 * (u**2) * t * p1[0] + 3 * u * (t**2) * p2[0] + (t**3) * p3[0],
        (u**3) * p0[1] + 3 * (u**2) * t * p1[1] + 3 * u * (t**2) * p2[1] + (t**3) * p3[1],
    )


def move_mouse_curve(page, target_x, target_y):
    global _MOUSE_POS
    sx, sy = _MOUSE_POS
    ex, ey = target_x, target_y

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
        page.mouse.move(x, y, steps=1)

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
    if len(sys.argv) < 2:
        print("Usage: python get_car_details.py <vin>")
        sys.exit(1)

    vin = sys.argv[1]

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False, timeout=30000, slow_mo=0)
        context = browser.new_context(
            viewport={"width": random.randint(1200, 1920), "height": random.randint(720, 1080)}
        )
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = context.new_page()

        # Open site
        page.goto("https://7zap.com", wait_until="domcontentloaded")
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

        # Submit login
        submit_btn = panel.locator("div > div:nth-child(2) > div > button")
        click_like_human(page, submit_btn)

        page.wait_for_load_state("domcontentloaded")
        maybe_long_think()

        # Focus search and enter VIN
        search_box_toggle = page.locator(".search.w-100")
        click_like_human(page, search_box_toggle)
        human_sleep()

        vin_input = page.locator("#mainSearchInput")
        click_like_human(page, vin_input)
        type_like_human(page, vin_input, vin)

        # Sometimes press Enter like a user
        if random.random() < 0.45:
            human_sleep(0.1, 0.3)
            page.keyboard.press("Enter")

        maybe_long_think()

        # Wait for table, then extract details
        table = page.locator("#htmlTableModifications")
        header_cells = table.locator("thead tr th")
        value_cells = table.locator("tbody tr td")

        header_cells.first.wait_for(state="attached")
        value_cells.first.wait_for(state="attached")

        headers_count = header_cells.count()
        values_count = value_cells.count()
        take = min(headers_count, values_count)

        car_data = {}
        # Start from 1 to mimic original behavior (often first column is "#")
        for i in range(1, take):
            key = header_cells.nth(i).inner_text().strip()
            val = value_cells.nth(i).inner_text().strip()
            car_data[key] = val

        print(json.dumps(car_data, indent=1))


if __name__ == "__main__":
    main()