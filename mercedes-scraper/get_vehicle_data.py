import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import re
import json
import os




def main():
    if len(sys.argv) < 2:
        print("Usage: python get_ac_parts.py <vin>")
        sys.exit(1)
    vin = sys.argv[1]

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False,timeout=30000)
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
        headers = page.locator("h3")
        headers.first.wait_for(state="attached")
     
     
        car_data = {}
        div_counter = 0
        for i in range (headers.count()):
    
            if headers.nth(i).inner_html().strip() == "Springs":
                #print("passing")
                div_counter -=1
                pass
            try:
                car_data[headers.nth(i).inner_html().strip()] = page.locator("div.tree").nth(div_counter).inner_text(timeout=1000)
                div_counter +=1
            except:
                div_counter+=1
                pass
    
        print(json.dumps(car_data,indent=1).replace("\\n","\n"))
if __name__ == "__main__":
    main()