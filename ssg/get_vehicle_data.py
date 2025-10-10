import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json
import os
from dotenv import load_dotenv

load_dotenv()

user = "michaelasham" #os.getenv('ETKA_USER')
pwd = os.getenv('ETKA_PASS')


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
        page.goto("https://ssg.asia/")
        page.wait_for_load_state("domcontentloaded")
        # #login > div.menulogin > div > a.cboxElement
        page.locator("#login > div.menulogin > div > a.cboxElement").click()
        page.wait_for_selector("#cboxLoadedContent")
        page.locator("#iduserlogin").fill(user)
        page.locator("#iduserpassword").fill(pwd)
        
        ##cboxLoadedContent > form > table > tbody > tr:nth-child(3) > td:nth-child(2) > input
        
        page.locator("#cboxLoadedContent > form > table > tbody > tr").nth(2).locator("td").nth(1).locator("input").click()
        
        page.wait_for_selector("#cboxLoadedContent",state="detached")
        
        
        
        
        page.locator("#article").fill(vin)
        ##art_val > td:nth-child(2) > input
        page.locator("#art_val > td").nth(1).locator("input").click()
        page.wait_for_load_state("domcontentloaded")
        # body > div > div.row.shadow.rounded.mb-3.pt-2.pb-2.car-row > div.col-md-2 > a.btn.btn-outline-secondary.btn-sm.btn-block
        page.locator("body > div > div.row.shadow.rounded.mb-3.pt-2.pb-2.car-row > div.col-md-2 > a.btn.btn-outline-secondary.btn-sm.btn-block").click()
        
        car_data = {}
        car_data["brand"] = page.locator("h3.pb-2").nth(0).inner_text()
        car_data["model"] = page.locator("h5").nth(0).inner_text()
        car_data["body"] = page.locator("small[title='Body']").nth(0).inner_text()
        car_data["tags"] = page.locator("span.badge.badge-info").all_inner_texts()
        car_data["year"] = page.locator("div[title='Year']").nth(0).inner_text()
        #body > div > div.row.shadow.rounded.mb-3.pt-2.pb-2.car-row > div.col-md-6 > div > div.col-lg-5.col-md-12 > div.Engine
        car_data["engine"] = page.locator("div.Engine").inner_text()
        # body > div > div.row.shadow.rounded.mb-3.pt-2.pb-2.car-row > div.col-md-6 > div > div.col-lg-5.col-md-12 > div:nth-child(2) > small
        car_data["engine_code"] = page.locator("small[title='Engine code']").inner_text()
        #body > div > div.row.shadow.rounded.mb-3.pt-2.pb-2.car-row > div.col-md-6 > div > div.col-lg.col-md-12
        car_data["transmission"] = page.locator("div > div.row.shadow.rounded.mb-3.pt-2.pb-2.car-row > div.col-md-6 > div > div.col-lg.col-md-12").inner_text()
        # #dcr-0 > div:nth-child(3)
        
        more_info = page.locator("#dcr-0")
        car_data["type"] = more_info.locator("div").nth(0).inner_text().split(": ")[1]
        car_data["class"] = more_info.locator("div").nth(1).inner_text().split(": ")[1]
        car_data["production_period"] = more_info.locator("div").nth(2).inner_text().split(": ")[1]
        
        print(json.dumps(car_data,indent=1))
                
if __name__ == "__main__":
    main()