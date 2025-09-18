import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import re

def main():
    if len(sys.argv) < 2:
        print("Usage: python autodoc.py <part_num>")
        sys.exit(1)
    part_num = str(sys.argv[1]).capitalize()
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True,timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = context.new_page()
        page.goto(f"https://www.autodoc.co.uk/spares-search?keyword={part_num}")
        page.wait_for_load_state('domcontentloaded')
        
        #reject cookkies
        try:
            reject_cookies = page.locator(".notification-popup__reject")
            if reject_cookies:
                reject_cookies.click()
        except Exception:
                pass  # Ignore if popup does not appear
            
        first_listing = page.locator(".listing-item__name").nth(0)
        first_listing.click()
        page.wait_for_load_state('domcontentloaded')
        
        oe_numbers = page.locator(".product-oem__list li")
        #remove OE and first space and anything after second space
        oe_number_pattern = re.compile(r"OE\s+(\S+)")   
        parsed_oe_numbers = []
        for i in range(oe_numbers.count()):
            text = oe_numbers.nth(i).inner_text()
            match = oe_number_pattern.search(text)
            if match:
                parsed_oe_numbers.append(match.group(1))

        print(parsed_oe_numbers)
        #browser.close()
if __name__ == "__main__":
    main()
