import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import re
import json

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
        
        #reject cookies
        try:
            page.wait_for_timeout(3000)
            reject_cookies = page.locator(".notification-popup__reject")
            if reject_cookies:
                reject_cookies.click()
        except Exception:
                pass  # Ignore if popup does not appear
            
            

            
        first_listing = page.locator(".listing-item__name").nth(0)
        first_listing.click()
        page.wait_for_load_state('domcontentloaded')
        
        
        image_url = None
        try:
            image_element = page.locator('img[role="presentation"]').first
            if image_element:
                image_url = image_element.get_attribute('src')
        except Exception as e:
            print(f"Error getting image: {e}", file=sys.stderr)
        
        oe_numbers = page.locator(".product-oem__list li")
        #remove OE and first space and anything after second space
        oe_number_pattern = re.compile(r"OE\s+(\S+)")   
        parsed_oe_numbers = []
        for i in range(oe_numbers.count()):
            text = oe_numbers.nth(i).inner_text()
            match = oe_number_pattern.search(text)
            if match:
                parsed_oe_numbers.append(match.group(1))
                
        result = {
           "oe_numbers": parsed_oe_numbers,
            "image": image_url
        }

        print(json.dumps(result))
        browser.close()
if __name__ == "__main__":
    main()
