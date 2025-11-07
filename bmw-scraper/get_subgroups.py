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

def _route_wrapper(route):
    url = route.request.url
    if "realoem.com" in url:
        return route.continue_()
    try:
        return block_ads(route)
    except Exception:
        return route.continue_()

def _defuse_overlays(page):
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

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"subgroups": []}, ensure_ascii=False, indent=2))
        sys.exit(1)

    vin = sys.argv[1].strip()
    group_in = sys.argv[2].strip().lower()

    if group_in not in ALLOWED_GROUPS:
        print(json.dumps({"subgroups": []}, ensure_ascii=False, indent=2))
        sys.exit(2)

    subgroups: List[str] = []

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
                close_btn = page.locator("span.ggmtgz:has-text('×')").first
                if close_btn.is_visible():
                    close_btn.click()
            except Exception:
                pass

            page.get_by_text("Browse Parts", exact=False).first.click()
            page.wait_for_load_state("domcontentloaded")

            page.get_by_text(ALLOWED_GROUPS[group_in], exact=False).first.click()
            page.wait_for_load_state("domcontentloaded")

            _defuse_overlays(page)
            page.wait_for_selector(".title", state="visible", timeout=30_000)
            page.wait_for_function("document.querySelectorAll('.title').length > 1", timeout=30_000)

            titles = page.locator(".title")
            count = titles.count()
            for i in range(1, count):
                try:
                    txt = (titles.nth(i).inner_text() or "").strip()
                    if not txt:
                        continue
                    if "REP. KIT" in txt or "VALUE PARTS" in txt:
                        continue
                    subgroups.append(txt.lower())
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

    print(json.dumps({"subgroups": subgroups}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
