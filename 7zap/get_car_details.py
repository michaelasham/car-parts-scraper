import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json
import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv('ZAP_USER')
pwd = os.getenv('ZAP_PASS')


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <vin>")
        sys.exit(1)
    vin = sys.argv[1]
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True,timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = context.new_page()
        page.goto("https://7zap.com")
        page.wait_for_load_state("domcontentloaded")
        ##head > div.row.px-md-4.py-md-2 > div > div.d-none.d-md-block.p-2.px-0.ml-lg-5.__text-center__.d-md-flex.align-content-center.flex-wrap > a > i
        page.locator("div.row.px-md-4.py-md-2 > div > div.d-none.d-md-block.p-2.px-0.ml-lg-5.__text-center__.d-md-flex.align-content-center.flex-wrap > a > i").click()
        #head > div.modal-mask.d-flex.align-content-center.flex-wrap1.dev1.pt-5 > div > div > div > div > div.cabinet-panel-on > div:nth-child(1) > input:nth-child(1)
        page.locator("#head > div.modal-mask.d-flex.align-content-center.flex-wrap1.dev1.pt-5 > div > div > div > div > div.cabinet-panel-on").locator("div").nth(0).locator("input").nth(0).fill(user)
        #head > div.modal-mask.d-flex.align-content-center.flex-wrap1.dev1.pt-5 > div > div > div > div > div.cabinet-panel-on > div:nth-child(1) > input:nth-child(2)
        page.locator("#head > div.modal-mask.d-flex.align-content-center.flex-wrap1.dev1.pt-5 > div > div > div > div > div.cabinet-panel-on").locator("div").nth(0).locator("input").nth(1).fill(pwd)
        #head > div.modal-mask.d-flex.align-content-center.flex-wrap1.dev1.pt-5 > div > div > div > div > div.cabinet-panel-on > div:nth-child(1) > div > div:nth-child(2) > div > button
        page.locator("#head > div.modal-mask.d-flex.align-content-center.flex-wrap1.dev1.pt-5 > div > div > div > div > div.cabinet-panel-on").locator("div").nth(0).locator("div").locator("div").nth(1).locator("div > button").click()
        
        page.wait_for_load_state("domcontentloaded")
        
        page.locator(".search.w-100").click()
        page.locator("#mainSearchInput").fill(vin)
        
        table = page.locator("#htmlTableModifications")
        fields = table.locator("thead tr th")
        fields.first.wait_for(state="attached")
        values = table.locator("tbody tr td")
        values.first.wait_for(state="attached")
        car_data = {}
        for i in range(1,fields.count()):
            car_data[fields.nth(i).inner_text()] = values.nth(i).inner_text()
        

        print(json.dumps(car_data,indent=1))
            
if __name__ == "__main__":
    main()
        