# get_ac_parts.py
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

def get_hex_color(el: ElementHandle) -> str:
    color = el.evaluate("el => getComputedStyle(el).color")
    rgb = list(map(int, re.findall(r"\d+", color)[:3]))
    return "#{:02x}{:02x}{:02x}".format(*rgb)

def is_row_active(row_el: ElementHandle) -> bool:
    for td in row_el.query_selector_all("td"):
        if get_hex_color(td) == "#212529":
            return True
    return False

def find_by_match(
    rows: List[ElementHandle],
    predicate: Callable[[str], bool],
    normalize: Callable[[str], str] = normalize_text,
) -> Optional[ElementHandle]:
    for row in rows:
        text = row.evaluate("el => el.textContent || ''")
        text = normalize(text)
        if predicate(text) and is_row_active(row):
            return row
    return None

def try_keywords(
    rows: List[ElementHandle],
    keywords: List[str],
    normalize: Callable[[str], str] = normalize_text,
) -> Optional[ElementHandle]:
    for kw in keywords:
        target = (
            find_by_match(rows, lambda t, kw=kw: t == kw, normalize)
            or find_by_match(rows, lambda t, kw=kw: t.startswith(kw), normalize)
            or find_by_match(rows, lambda t, kw=kw: kw in t, normalize)
        )
        if target:
            return target
    return None

PART_ALIASES = {
    "compressor": ["compressor", "ac compressor", "a/c compressor", "a c compressor"],
    "condenser": ["condenser"],
    "evaporator": ["evaporator"],
    "expansion": ["expansion", "expansion valve", "valve", "regulation valve"],
}

# ----------------------------
# Core scrape
# ----------------------------

def core_scrape(vin: str, part_type: str) -> Optional[str]:
    user = os.getenv("ETKA_USER") or ""
    pwd = os.getenv("ETKA_PASS") or ""
    part_key = normalize_text(part_type)

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, timeout=30000)
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
            page.wait_for_load_state("networkidle")

        # VIN search and close modal with Escape
        page.locator("#vinSearch").fill(vin)
        page.locator("#buttonVinSearch").click()
        page.wait_for_selector("div.modal-content.ui-draggable", timeout=120000)
        # page.wait_for_timeout(1000)
        # #Modal2 > div > div > div.modal-footer.ui-draggable-handle > button
        page.locator("#Modal2 > div > div > div.modal-footer.ui-draggable-handle > button").click()
        page.wait_for_selector("div.modal-content.ui-draggable", state="hidden", timeout=120000)

        # Click “Air cond. system”
        page.wait_for_selector(".etka_newImg_mainTable li", timeout=120000)
        page.evaluate("""
            () => {
                const items = Array.from(document.querySelectorAll(".etka_newImg_mainTable li"));
                const acItem = items.find(el => el.innerText.includes("Air cond. system"));
                if (acItem) acItem.click();
            }
        """)
        page.wait_for_selector("table.subGrTable", timeout=120000)
        page.evaluate("() => document.querySelector('table.subGrTable')?.scrollIntoView()")
        page.wait_for_timeout(600)

        # Build ElementHandle list (not Locators)
        rows: List[ElementHandle] = page.query_selector_all("table.subGrTable tr")

        kw = normalize_text(part_type)
        target_row = try_keywords(rows, [kw])

        if not target_row and kw == "expansion":
            target_row = try_keywords(rows, ["evaporator", "electronic regulation"])
        if not target_row and kw == "evaporator":
            target_row = try_keywords(rows, ["electronic regulation"])

        if not target_row:
            print("No matching sub-group row found.")
            browser.close()
            return None

        target_row.click()
        page.wait_for_selector("table.detailsTable", timeout=120000)

        # Extract part number in one DOM pass
        aliases = PART_ALIASES.get(part_key, [part_key])
        part_info = page.evaluate(
            """([partKey, aliases]) => {
                const normalize = (text) => (text || '')
                    .toLowerCase()
                    .replace(/[^a-z0-9\\s]/g, '')
                    .replace(/\\s+/g, ' ')
                    .trim();

                const rows = Array.from(document.querySelectorAll("table.detailsTable tr"));
                let lastValidPart = null;

                const disallowedMap = {
                    compressor: ["bracket", "oil"],
                    expansion: ["evaporator"],
                };
                const disallowed = disallowedMap[partKey] || [];

                const getHex = (el) => {
                    const c = getComputedStyle(el).color;
                    const nums = c.match(/\\d+/g)?.map(Number);
                    if (!nums) return '';
                    return "#" + nums.slice(0,3).map(v => v.toString(16).padStart(2, "0")).join("");
                };

                for (const row of rows) {
                    const tds = Array.from(row.querySelectorAll("td.etkTd"));
                    for (const td of tds) {
                        const text = (td.textContent || '').trim();
                        const norm = normalize(text);

                        if (td.hasAttribute("num") && text) {
                            const hex = getHex(td);
                            if (hex === "#212529") {
                                lastValidPart = {
                                    num: td.getAttribute("num"),
                                    numn: td.getAttribute("numn"),
                                    title: td.getAttribute("title"),
                                    text: text
                                };
                            }
                        }

                        if (!lastValidPart || !norm) continue;

                        const hasDisallowed = disallowed.some(w => norm.includes(w));
                        if (hasDisallowed) continue;

                        for (let a of aliases) {
                            const na = normalize(a);
                            const isMatch = partKey === "expansion"
                                ? norm.startsWith(na)
                                : norm.includes(na);
                            if (isMatch) return lastValidPart;
                        }
                    }
                }
                return null;
            }""",
            [part_key, aliases],
        )

        num = part_info["num"] if part_info else None
        #print(f"🔩 {part_type} Part Number:", num or "Not found")
        print(json.dumps(num))

        browser.close()
        return num

# ----------------------------
# CLI
# ----------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: python get_ac_parts.py <vin> <part>")
        sys.exit(1)
    vin = sys.argv[1]
    part = " ".join(sys.argv[2:])
    core_scrape(vin, part)

if __name__ == "__main__":
    main()
