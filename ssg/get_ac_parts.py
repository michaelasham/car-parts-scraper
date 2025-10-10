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
        
        
        
        
        page.locator("#article").fill(vin)
        ##art_val > td:nth-child(2) > input
        page.locator("#art_val > td").nth(1).locator("input").click()
        