import sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
from utils import block_ads
from playwright_stealth import Stealth
from actions import Actions

def main():
    if len(sys.argv) < 2:
        print("Usage: python get_car_details.py <vin>")
        sys.exit(1)
    vin = sys.argv[1]

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True,timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = context.new_page()
        page.route("**/*", block_ads)
        page.goto("http://www.realoem.com")
        page.wait_for_load_state('domcontentloaded')
        actions = Actions(page)
        details = actions.get_car_details(vin)
        import json
        print(json.dumps(details, ensure_ascii=False))
        page.close()
        context.close()
        browser.close()

if __name__ == "__main__":
    main()