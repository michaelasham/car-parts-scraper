import sys
from playwright.sync_api import sync_playwright
from utils import block_ads
from playwright_stealth import Stealth
from actions import Actions

def main():
    if len(sys.argv) < 3:
        print("Usage: python main.py <vin> <part>")
        sys.exit(1)
    vin = sys.argv[1]
    part = " ".join(sys.argv[2:])  # Join all remaining args as part

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True,timeout=30000, args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-gpu'
        ])
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.route("**/*", block_ads)
        page.goto("http://www.realoem.com")
        page.wait_for_load_state('domcontentloaded')
        actions = Actions(page)
        result = actions.find_ac_part_by_keyword(vin, part)
        import json
        print(json.dumps(result, ensure_ascii=False))
        #browser.close()

if __name__ == "__main__":
    main()