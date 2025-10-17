import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json
import os
from dotenv import load_dotenv
import re

load_dotenv()

user = "michaelasham" #os.getenv('ETKA_USER')
pwd = os.getenv('ETKA_PASS')

AC_KEYWORD_MAP = {
            "compressor" : "A / C compressor",
            "a/c compressor" : "A / C compressor",
            "expansion valve": "System sensors, units, valves, controllers",
            "valve" : "System sensors, units, valves, controllers",
            "condenser" : "REFRIGERANT LINE ARRANGEMEN",
            "evaporator" : "HEATER AND EVAPORATOR HOUSING WITH BLOWER AND WIRING HARNESS"
        }
        
ALLOWED_PATTERNS = {
            "compressor" : r"Air conditioner compressor" ,
            "a/c compressor" : r"Air conditioner compressor",
            "expansion valve": [r"^VALVE$", r"EXPANSION VALVE"],
            "valve" : [r"^VALVE$", r"EXPANSION VALVE"],
            "condenser" : [r"^CONDENSER$"],
            "evaporator" : [r"^EVAPORATOR"],
        }

EXEMPT_KEYWORDS = {
    "compressor" : r"pulley|bearing|bracket",
}

def main():
    if len(sys.argv) < 3:
        print("Usage: python main.py <vin> <part>")
        sys.exit(1)
    vin = sys.argv[1]
    part = ' '.join(sys.argv[2:])
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False,timeout=30000)
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
        
        page.locator("a:has-text('Select')").click()
        
        page.wait_for_load_state("domcontentloaded")
        
        page.locator("span:has-text('Heating, a / C')").click()
        
        page.wait_for_timeout(10000)
        

        page.get_by_text(AC_KEYWORD_MAP[part]).click()
        exclude = re.compile(EXEMPT_KEYWORDS[part], re.I)
        rows = page.locator("div.row",has_text=ALLOWED_PATTERNS[part],has_not_text=exclude)
        rows.first.wait_for(state="attached")
        #pos-88320 > div:nth-child(3) > div > div.col.col-sm-5.offset-sm-7.col-md-4.offset-md-8.col-lg-6.offset-lg-6.col-xl-4.offset-xl-8 > small
        data = []
        for i in range(rows.count()):
            num = rows.nth(i).locator("small",has_text="Article").inner_text().split(": ",maxsplit=1)[-1]
            data.append(num)
        
        print(json.dumps(data))
if __name__ == "__main__":
    main()