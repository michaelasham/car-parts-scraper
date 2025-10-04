import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import re
import json
import os


def assert_any_word_in_string(words_array, target_string):
    for pattern in words_array:
        if re.match(pattern,target_string):
            return True  # Assertion passes
    return False  # Assertion fails


def main():
    if len(sys.argv) < 3:
        print("Usage: python get_ac_parts.py <vin> <part>")
        sys.exit(1)
    vin = sys.argv[1]
    part = " ".join(sys.argv[2:])
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True,timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = context.new_page()
        # page.route("**/*", block_ads) might need this if website keeps showing popups
        page.goto("https://mb-teilekatalog.info/?lang=E") #this will probably load in german so we need to change the language from the website header
        page.wait_for_load_state("domcontentloaded")
        page.locator("a[title='English']").click() #change to english
        page.wait_for_load_state("domcontentloaded")
        page.locator("input[name='vin']").fill(vin)
        page.locator("button[type='submit']").nth(0).click()
        #find catalog
        catalog = page.locator("a.btn.btn-success.btn-sm")
        catalog.click()
        page.get_by_text("HEATING AND VENTILATION").click()
        
        AC_KEYWORD_MAP = {
            "compressor" : "A/C COMPRESSOR",
            "a/c compressor" : "A/C COMPRESSOR",
            "expansion valve": "REFRIGERANT LINE ARRANGEMENT",
            "valve" : "REFRIGERANT LINE ARRANGEMENT",
            "condenser" : "REFRIGERANT LINE ARRANGEMEN",
            "evaporator" : "HEATER AND EVAPORATOR HOUSING WITH BLOWER AND WIRING HARNESS"
        }
        
        ALLOWED_PATTERNS = {
            "compressor" : [r"^COMPRESSOR$", r"^REFRIGERANT COMPRESSOR$"] ,
            "a/c compressor" : [r"^COMPRESSOR$", r"^REFRIGERANT COMPRESSOR$"],
            "expansion valve": [r"^VALVE$", r"EXPANSION VALVE"],
            "valve" : [r"^VALVE$", r"EXPANSION VALVE"],
            "condenser" : [r"^CONDENSER$"],
            "evaporator" : [r"^EVAPORATOR"],
        }
        
        #click according to selected parts in the program arguments
        page.get_by_text(AC_KEYWORD_MAP[part]).click()
        
        table_headers = page.locator("table.table-striped.table-condensed.table-hover  tbody > tr > th")
        
        table_headers.first.wait_for(state="attached")

        rows = page.locator("table.table-striped.table-condensed.table-hover > tbody > tr")
        rows.first.wait_for(state="attached")

        search_data = {}
        for i in range(1,rows.count()):
            part_type = page.locator("table.table-striped.table-condensed.table-hover > tbody > tr").nth(i).locator("td").locator("b").first.inner_text()
            if assert_any_word_in_string(ALLOWED_PATTERNS[part],part_type):
                
                part_num = rows.nth(i).locator("td").nth(1).inner_text()
                #body > div.page-wrapper > div.page-wrapper-row.full-height > div > div > div.page-content > div > div:nth-child(4) > div:nth-child(2) > div.portlet.light > div > div > div.table-scrollable > table > tbody > tr:nth-child(4) > td:nth-child(4)
                qty = rows.nth(i).locator(" > td").nth(3).inner_text()
                search_data[part_num] = qty           
        print(json.dumps(search_data))
        
        
        

if __name__ == "__main__":
    main()

        