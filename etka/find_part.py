import sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
import os
from dotenv import load_dotenv
load_dotenv()

USERNAME = os.getenv("ETKA_USER")
PASSWORD = os.getenv("ETKA_PASS")

ETKA_URL = "https://superetka.com/etka"

def normalize_text_py(s: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (s or "")).split())

def find_part_number(page, part_type: str) -> str | None:
    part_type_norm = normalize_text_py(part_type)
    return page.evaluate(
        """(partType) => {
            const normalize = (text) =>
              (text ?? '')
                .toLowerCase()
                .replace(/[^a-z0-9\\s]/g, ' ')
                .replace(/\\s+/g, ' ')
                .trim();

            const PART_ALIASES = {
              compressor: ["compressor","ac compressor","a/c compressor","a c compressor"],
              condenser: ["condenser"],
              evaporator: ["evaporator"],
              expansion: ["expansion","expansion valve","valve","regulation valve"]
            };

            const rows = Array.from(document.querySelectorAll("table.detailsTable tr"));
            let lastValidPart = null;

            for (const row of rows) {
              const tds = Array.from(row.querySelectorAll("td.etkTd"));

              for (const td of tds) {
                const rawText = td.textContent || "";
                const text = normalize(rawText);

                if (td.hasAttribute("num") && text) {
                  const color = window.getComputedStyle(td).color;
                  const rgb = color.match(/\\d+/g)?.map(Number);
                  const hex = rgb ? "#" + rgb.map(v => v.toString(16).padStart(2,"0")).join("") : "";
                  if (hex === "#212529") {
                    lastValidPart = {
                      num: td.getAttribute("num"),
                      numn: td.getAttribute("numn"),
                      title: td.getAttribute("title"),
                      text: rawText.trim()
                    };
                  }
                }

                if (lastValidPart) {
                  const aliases = PART_ALIASES[partType] || [partType];
                  const normText = text;
                  const disallowedWords = ({
                    compressor: ["bracket","oil"],
                    expansion: ["evaporator"]
                  })[partType] || [];
                  if (disallowedWords.some(w => normText.includes(w))) continue;

                  for (const alias of aliases) {
                    const normAlias = normalize(alias);
                    const isMatch = partType === "expansion"
                      ? normText.startsWith(normAlias)
                      : normText.includes(normAlias);
                    if (isMatch) return lastValidPart.num || null;
                  }
                }
              }
            }
            return null;
        }""",
        part_type_norm
    )

def click_air_conditioning_category(page):
    ac_item = page.locator(".etka_newImg_mainTable li:has-text('Air cond. system')")
    if ac_item.count() > 0:
        ac_item.first.click()
    else:
        page.evaluate("""
            () => {
              const items = Array.from(document.querySelectorAll(".etka_newImg_mainTable li"));
              const el = items.find(li => (li.innerText || "").includes("Air cond. system"));
              if (el) el.click();
            }
        """)

def select_part_row(page, part_type: str):
    page.evaluate(
        """(partType) => {
            const normalize = (text) => text.toLowerCase().replace(/\\s+/g, ' ').trim();
            const rows = Array.from(document.querySelectorAll("table.subGrTable tr"));

            function getHexColor(td) {
              const color = window.getComputedStyle(td).color;
              const rgb = color.match(/\\d+/g)?.map(Number);
              return rgb ? "#" + rgb.map(v => v.toString(16).padStart(2, "0")).join("") : "";
            }
            function isRowActive(row) {
              const tds = Array.from(row.querySelectorAll("td"));
              return tds.some(td => getHexColor(td) === "#212529");
            }
            function findByMatch(method) {
              return rows.find(row => {
                const text = normalize(row.textContent || "");
                return method(text) && isRowActive(row);
              });
            }
            const tryKeywords = (keywords) => {
              for (const keyword of keywords) {
                const target =
                  findByMatch(t => t === keyword) ||
                  findByMatch(t => t.startsWith(keyword)) ||
                  findByMatch(t => t.includes(keyword));
                if (target) return target;
              }
              return null;
            };

            const keyword = normalize(partType);
            let targetRow = tryKeywords([keyword]);
            if (!targetRow && keyword === "expansion") targetRow = tryKeywords(["evaporator", "electronic regulation"]);
            if (!targetRow && keyword === "evaporator") targetRow = tryKeywords(["electronic regulation"]);
            if (targetRow) targetRow.click();
        }""",
        part_type
    )

def scrape_part(vin: str, part_type: str) -> str | None:
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, timeout=30000)
        context = browser.new_context()
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)

        page = context.new_page()
        page.goto(ETKA_URL, wait_until="domcontentloaded")

        # Conditional login
        try:
            if page.locator('input[name="lgn"]').first.is_visible(timeout=2000):
                if not USERNAME or not PASSWORD:
                    raise RuntimeError("ETKA_USERNAME / ETKA_PASSWORD env vars are required for login.")
                page.fill('input[name="lgn"]', USERNAME)
                page.fill('input[name="pwd"]', PASSWORD)
                page.click('button[name="go"]')
                page.wait_for_load_state("networkidle")
        except PlaywrightTimeoutError:
            # If the locator check times out, assume already logged in.
            pass

        # VIN search
        page.locator("#vinSearch").wait_for(state="visible")
        page.fill("#vinSearch", vin)
        page.click("#buttonVinSearch")

        # VIN modal open/close
        modal = page.locator("div.modal-content.ui-draggable")
        modal.wait_for(state="visible", timeout=190000)
        page.keyboard.press("Escape")
        modal.wait_for(state="hidden", timeout=190000)

        # Category list must be present
        page.locator(".etka_newImg_mainTable li").first.wait_for(state="visible", timeout=120000)
        click_air_conditioning_category(page)

        # 🔧 Instead of scroll_into_view_if_needed (which requires visibility), just wait for the table to exist.
        # Some views lazy-render; attached is enough before we click inside it via JS.
        page.locator("table.subGrTable").wait_for(state="attached", timeout=120000)

        # Now pick the sub-row
        select_part_row(page, part_type)

        # Wait for details table to reflect the chosen part
        part_type_norm = normalize_text_py(part_type)
        page.wait_for_function(
            """(needle) => {
                const tds = Array.from(document.querySelectorAll("table.detailsTable td.etkTd"));
                return tds.some(td => (td.textContent || '').toLowerCase().includes(needle));
            }""",
            arg=part_type_norm,
            timeout=120000
        )

        num = find_part_number(page, part_type)
        context.close()
        browser.close()
        return num

def main():
    if len(sys.argv) < 3:
        print("Usage: python find_part.py <vin> <part>")
        sys.exit(1)

    vin = sys.argv[1]
    part = " ".join(sys.argv[2:])

    try:
        part_num = scrape_part(vin, part)
        if part_num:
            print(part_num)
            sys.exit(0)
        else:
            print("Not found")
            sys.exit(2)
    except PlaywrightTimeoutError as e:
        print(f"Timeout: {e}")
        sys.exit(3)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(4)

if __name__ == "__main__":
    main()
