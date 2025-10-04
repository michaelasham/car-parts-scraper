import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json
import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv('ETKA_USER')
pwd = os.getenv('ETKA_PASS')


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <vin> <part>")
        sys.exit(1)
    vin = sys.argv[1]
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True,timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = context.new_page()
        page.goto("https://superetka.com/etka/")
        page.wait_for_load_state("domcontentloaded")
        if page.locator("input[name=lgn]"):
            page.locator("input[name=lgn]").fill(user)
            page.locator("input[name=pwd]").fill(pwd)
            page.locator("button[name='go']").click()
            page.wait_for_load_state("domcontentloaded")

        page.locator("#vinSearch").fill(vin)
        page.locator("#buttonVinSearch").click()
        rows = page.locator("div.modal-dialog table tbody").nth(1).locator("tr")
        rows.first.wait_for(state="attached")
        rows = rows.all()
        car_data = {}
        for row in rows:
            tds = row.locator("td")
            tds.first.wait_for(state="attached")
            car_data[tds.nth(0).inner_text()] = tds.nth(1).inner_text()
        print(json.dumps(car_data,indent=1))
        
        
        
if __name__ == "__main__":
    main()