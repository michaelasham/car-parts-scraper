import os
import re
import sys
import json
from typing import Callable, List, Optional

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, ElementHandle
from playwright_stealth import Stealth

load_dotenv()

# ----------------------------
# Helpers
# ----------------------------

def normalize_text(s: str) -> str:
    return " ".join(s.split()).lower()

#returns key for appropriate part category
def determine_category(s: str) -> str:
    return next((k for k, v in PART_ALIASES.items() if s in v), None)

    



PART_ALIASES = {
    "Spark plugs": ["spark plugs", "spark-plugs"],
    "Air filter elements": ["air filter", "air-filter"],
    "Engine oil filter": ["engine oil filter"],
    "Engine oil" : ["engine oil"],
    "Dust/pollen filter": ["dust filter", "pollen filter", "ac filter", "insert filter","harmful substance filter"],
    "Transmisson oil": ["transmisson oil"]
}

# ----------------------------
# Core scrape
# ----------------------------

def core_scrape(vin: str, part_type: str) -> Optional[str]:
    user = os.getenv("ETKA_USER") or ""
    pwd = os.getenv("ETKA_PASS") or ""
    part_key = normalize_text(part_type)
    include_qty = False
    if part_key in PART_ALIASES["Spark plugs"]:
        include_qty = True
    category = determine_category(part_key)
    
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False, timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = context.new_page()
        
        # Go to site & login if needed
        page.goto("https://superetka.com/etka/", wait_until="domcontentloaded")
        if page.locator('input[name="lgn"]').count() > 0:
            page.locator('input[name="lgn"]').fill(user)
            page.locator('input[name="pwd"]').fill(pwd)
            page.locator("button[name='go']").click()
            page.wait_for_load_state("domcontentloaded")

        # VIN search and close modal with Escape
        page.locator("#vinSearch").fill(vin)
        page.locator("#buttonVinSearch").click()
        page.wait_for_selector("div.modal-content.ui-draggable", timeout=120000)
        page.locator("#Modal2 > div > div > div.modal-footer.ui-draggable-handle > button").click()
        page.wait_for_selector("div.modal-content.ui-draggable", state="hidden", timeout=120000)
        
        #nav-epc > div.topButtons > table > tbody > tr:nth-child(1) > td:nth-child(2)
        page.locator("#nav-epc > div.topButtons > table > tbody > tr").nth(0).locator("td").nth(1).click()
        
        pattern = re.compile(fr"^{category}$", re.IGNORECASE)
        page.get_by_text(pattern).click()
        page.wait_for_timeout(1000)
        
        #spareContent0 > table > tbody > tr   //single element
        #spareContent0 > table > tbody > tr:nth-child(1)  //one out of multiple elements
        #spareContent0 > table > tbody > tr:nth-child(1) > td:nth-child(6)
        #spareContent0 > table > tbody > tr:nth-child(2) > td:nth-child(6)
        #qty at index 5 and part num at 2
        data = []
        rows = page.locator("#spareContent0 > table > tbody > tr")
        rows.first.wait_for(state="attached")
        for i in range(rows.count()):
            qty = rows.nth(i).locator("td").nth(5).inner_text()
            if not re.match(r"\d+",qty):
                continue
            part_num = rows.nth(i).locator("td").nth(2).inner_text()
            if include_qty:
                data.append({"part":part_num, "qty": qty})
            else:
                data.append(part_num)

        
        print(json.dumps(data,indent=1))
       
        

def main():
    if len(sys.argv) < 3:
        print("Usage: python get_maintenance_parts.py <vin> <part>")
        sys.exit(1)
    vin = sys.argv[1]
    part = " ".join(sys.argv[2:])
    core_scrape(vin, part)

if __name__ == "__main__":
    main()