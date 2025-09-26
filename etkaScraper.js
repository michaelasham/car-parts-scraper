import fs from "fs";
import path, { dirname } from "path";
import { fileURLToPath } from "url";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";
import axios from "axios";
import express from "express";
import dotenv from "dotenv";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const profileDir = path.join(__dirname, "tmp_profile_superetka_scraper");
const lockFile = path.join(profileDir, "SingletonLock");

// Ensure profile folder exists
if (!fs.existsSync(profileDir)) {
  fs.mkdirSync(profileDir, { recursive: true });
}

// Remove leftover lock file
if (fs.existsSync(lockFile)) {
  fs.unlinkSync(lockFile);
  console.log("🔓 Removed leftover SingletonLock file");
}
puppeteer.use(StealthPlugin());

const USERNAME = process.env.ETKA_USER;
const PASSWORD = process.env.ETKA_PASS;
const N8N_WEBHOOK_URL = process.env.N8N_URL;
let browser; // ✅ Global browser instance

const app = express();
app.use(express.json());

export async function initBrowser() {
  if (!browser) {
    console.log("🚀 Launching browser...");
    browser = await puppeteer.launch({
      headless: "new",
      userDataDir: profileDir,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-features=BlockInsecurePrivateNetworkRequests",
        "--disable-features=BlockInsecurePrivateNetworkRequestsFromPrivate",
        "--disable-blink-features=AutomationControlled",
        "--ignore-certificate-errors",
        "--disable-dev-shm-usage",
      ],
      ignoreHTTPSErrors: true,
    });

    console.log("✅ Browser launched successfully");

    // Set up browser close on process exit
    process.on("exit", () => {
      if (browser) browser.close();
    });
  }
  return browser;
}

export async function scrapeSuperEtka(vin, partType) {
  const singletonLockPath = path.join(profileDir, "SingletonLock"); // Fixed absolute path
  let page = null;

  try {
    console.log(`🔍 Scraping ${partType} for VIN: ${vin}`);

    // Clean up leftover lock file if exists
    if (fs.existsSync(singletonLockPath)) {
      fs.unlinkSync(singletonLockPath);
      console.log("🔓 Removed leftover SingletonLock file");
    }

    const browserInstance = await initBrowser();
    page = await browserInstance.newPage();

    // Configure page settings for better stability
    await page.setDefaultNavigationTimeout(90000);
    await page.setDefaultTimeout(60000);
    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    );

    // Disable unnecessary resources to improve performance
    await page.setRequestInterception(true);
    page.on("request", (req) => {
      const resourceType = req.resourceType();
      if (
        resourceType === "image" ||
        resourceType === "font" ||
        resourceType === "media"
      ) {
        req.abort();
      } else {
        req.continue();
      }
    });

    // Navigate with retry logic
    console.log("🌐 Navigating to SuperETKA...");
    let navSuccess = false;
    for (let attempt = 1; attempt <= 3 && !navSuccess; attempt++) {
      try {
        await page.goto("https://superetka.com/etka", {
          waitUntil: "networkidle2",
          timeout: 60000,
        });
        navSuccess = true;
      } catch (navError) {
        console.log(
          `⚠️ Navigation attempt ${attempt} failed: ${navError.message}`
        );
        if (attempt === 3) throw navError;
        await page.waitForTimeout(3000);
      }
    }

    // Login if needed with error handling
    if (await page.$('input[name="lgn"]')) {
      console.log("🔐 Logging in to SuperETKA...");
      await page.type('input[name="lgn"]', USERNAME);
      await page.type('input[name="pwd"]', PASSWORD);

      await page.click('button[name="go"]');

      try {
        await page.waitForNavigation({
          waitUntil: "networkidle2",
          timeout: 30000,
        });
      } catch (navError) {
        console.warn(
          "⚠️ Login navigation timeout, but continuing:",
          navError.message
        );
      }

      // Check for login errors
      const errorElement = await page.$(".alert-danger");
      if (errorElement) {
        const errorText = await page.evaluate(
          (el) => el.textContent.trim(),
          errorElement
        );
        throw new Error(`Login failed: ${errorText}`);
      }
      console.log("✅ Logged in successfully.");
    } else {
      console.log("✅ Already logged in.");
    }

    // Enter VIN with error handling
    console.log("✅ Entering VIN...");
    try {
      await page.waitForSelector("#vinSearch", {
        visible: true,
        timeout: 20000,
      });
      await page.type("#vinSearch", vin);
      await page.click("#buttonVinSearch");
    } catch (vinError) {
      console.error(`❌ VIN input error: ${vinError.message}`);
      await page.screenshot({ path: `/tmp/vin-input-error-${Date.now()}.png` });
      throw new Error(`Failed to enter VIN: ${vinError.message}`);
    }

    // Wait for modal with better error handling
    console.log("⏱️ Waiting for VIN modal...");
    try {
      await page.waitForSelector("div.modal-content.ui-draggable", {
        visible: true,
        timeout: 60000,
      });
      await page.waitForTimeout(1000);
    } catch (modalError) {
      console.error(`❌ VIN modal error: ${modalError.message}`);
      await page.screenshot({ path: `/tmp/modal-error-${Date.now()}.png` });
      throw new Error(`VIN modal not found: ${modalError.message}`);
    }

    // Close modal
    await page.keyboard.press("Escape");
    console.log("✅ Pressed Escape to close VIN modal");

    try {
      await page.waitForSelector("div.modal-content.ui-draggable", {
        hidden: true,
        timeout: 30000,
      });
    } catch (modalCloseError) {
      console.warn(
        "⚠️ Modal may not have closed properly:",
        modalCloseError.message
      );
      // Continue anyway - sometimes the modal stays in DOM but is not visible
    }

    // Wait for menu items
    console.log("⏱️ Waiting for menu to load...");
    try {
      await page.waitForSelector(".etka_newImg_mainTable li", {
        visible: true,
        timeout: 60000,
      });
      await page.waitForTimeout(2000);
    } catch (menuError) {
      console.error(`❌ Menu loading error: ${menuError.message}`);
      await page.screenshot({ path: `/tmp/menu-error-${Date.now()}.png` });
      throw new Error(`Menu items not found: ${menuError.message}`);
    }

    // Click Air Conditioning with defensive programming
    console.log("🔍 Finding Air Conditioning category...");
    const acResult = await page.evaluate(() => {
      try {
        // Safely get menu items with null checks
        const menuItems = document.querySelectorAll(
          ".etka_newImg_mainTable li"
        );
        if (!menuItems || menuItems.length === 0) {
          return { success: false, error: "No menu items found" };
        }

        const items = Array.from(menuItems);

        // Find AC item with null/undefined safety
        for (let i = 0; i < items.length; i++) {
          const el = items[i];
          if (!el) continue;

          const text = el.innerText || el.textContent || "";
          if (typeof text !== "string") continue;

          if (
            text.includes("Air cond. system") ||
            text.includes("Air condition")
          ) {
            el.click();
            return { success: true, method: "text-match", index: i };
          }
        }

        // Fallback: Try item at index 8 (common position for AC)
        if (items.length > 8) {
          items[8].click();
          return { success: true, method: "position-fallback", position: 8 };
        }

        return { success: false, error: "AC category not found" };
      } catch (err) {
        return { success: false, error: err.toString() };
      }
    });

    if (!acResult.success) {
      console.warn(`⚠️ Could not find AC category: ${acResult.error}`);
      await page.screenshot({ path: `/tmp/ac-category-${Date.now()}.png` });
    } else {
      console.log(`✅ Clicked AC category via ${acResult.method}`);
    }

    // Scroll to part table
    await page.evaluate(() => {
      try {
        const el = document.querySelector("table.subGrTable");
        if (el) el.scrollIntoView();
      } catch (err) {
        console.error("Error scrolling to table:", err);
      }
    });
    await page.waitForTimeout(1000);

    // Select part type row with defensive programming
    console.log(`🔍 Selecting part type: ${partType}...`);
    const partRowResult = await page.evaluate((partType) => {
      try {
        // Safety function for text normalization
        const normalize = (text) => {
          if (!text || typeof text !== "string") return "";
          return text.toLowerCase().replace(/\s+/g, " ").trim();
        };

        // Safely get table rows with null checks
        const tableEl = document.querySelector("table.subGrTable");
        if (!tableEl) {
          return { success: false, error: "Part table not found" };
        }

        const rowElements = tableEl.querySelectorAll("tr");
        if (!rowElements || rowElements.length === 0) {
          return { success: false, error: "No rows in part table" };
        }

        const rows = Array.from(rowElements);

        // Color detection with error handling
        function getHexColor(td) {
          try {
            const style = window.getComputedStyle(td);
            const color = style ? style.color : null;
            if (!color) return "";

            const rgb = color.match(/\d+/g)?.map(Number);
            return rgb
              ? "#" + rgb.map((v) => v.toString(16).padStart(2, "0")).join("")
              : "";
          } catch (e) {
            return "";
          }
        }

        function isRowActive(row) {
          try {
            const tds = Array.from(row.querySelectorAll("td") || []);
            return tds.some((td) => getHexColor(td) === "#212529");
          } catch (e) {
            return false;
          }
        }

        function findByMatch(method) {
          for (const row of rows) {
            if (!row) continue;
            const text = normalize(row.textContent || "");
            if (method(text) && isRowActive(row)) {
              return row;
            }
          }
          return null;
        }

        const tryKeywords = (keywords) => {
          for (const keyword of keywords) {
            const target =
              findByMatch((t) => t === keyword) ||
              findByMatch((t) => t.startsWith(keyword)) ||
              findByMatch((t) => t.includes(keyword));
            if (target) return target;
          }
          return null;
        };

        const keyword = normalize(partType);
        let targetRow = tryKeywords([keyword]);

        // Fallbacks for specific part types
        if (!targetRow && keyword === "expansion") {
          targetRow = tryKeywords(["evaporator", "electronic regulation"]);
        }

        if (!targetRow && keyword === "evaporator") {
          targetRow = tryKeywords(["electronic regulation"]);
        }

        if (targetRow) {
          targetRow.click();
          return { success: true };
        }

        return { success: false, error: `Part type '${partType}' not found` };
      } catch (err) {
        return { success: false, error: err.toString() };
      }
    }, partType);

    if (!partRowResult.success) {
      console.warn(`⚠️ Part row selection failed: ${partRowResult.error}`);
      await page.screenshot({ path: `/tmp/part-row-${Date.now()}.png` });
    } else {
      console.log("🖱️ Clicked on part type row");
    }

    // Wait for part details with error handling
    console.log("⏱️ Waiting for part details...");
    try {
      await page.waitForFunction(
        (partType) => {
          try {
            const tds = document.querySelectorAll(
              "table.detailsTable td.etkTd"
            );
            if (!tds || tds.length === 0) return false;

            for (const td of tds) {
              if (!td || !td.textContent) continue;
              const text = td.textContent.trim().toLowerCase();
              if (text.includes(partType.toLowerCase())) return true;
            }
            return false;
          } catch (e) {
            return false;
          }
        },
        { timeout: 60000 },
        partType
      );
    } catch (detailsError) {
      console.warn(
        `⚠️ Timeout waiting for part details: ${detailsError.message}`
      );
      await page.screenshot({
        path: `/tmp/part-details-timeout-${Date.now()}.png`,
      });
      // Continue anyway, might still find parts
    }

    // Extract part info with defensive programming
    console.log("🔍 Extracting part information...");
    const partInfo = await page.evaluate((partType) => {
      try {
        // Safe text normalization
        const normalize = (text) => {
          if (!text || typeof text !== "string") return "";
          return text
            .toLowerCase()
            .replace(/[^a-z0-9\s]/g, "")
            .replace(/\s+/g, " ")
            .trim();
        };

        const PART_ALIASES = {
          compressor: [
            "compressor",
            "ac compressor",
            "a/c compressor",
            "a c compressor",
          ],
          condenser: ["condenser"],
          evaporator: ["evaporator"],
          expansion: [
            "expansion",
            "expansion valve",
            "valve",
            "regulation valve",
          ],
        };

        // Safely get rows with null checks
        const detailsTable = document.querySelector("table.detailsTable");
        if (!detailsTable) {
          console.error("Details table not found");
          return null;
        }

        const rowElements = detailsTable.querySelectorAll("tr");
        if (!rowElements || rowElements.length === 0) {
          console.error("No rows in details table");
          return null;
        }

        const rows = Array.from(rowElements);
        let lastValidPart = null;

        // Process each row with defensive coding
        for (const row of rows) {
          if (!row) continue;

          const tdElements = row.querySelectorAll("td.etkTd");
          if (!tdElements || tdElements.length === 0) continue;

          const tds = Array.from(tdElements);

          for (const td of tds) {
            if (!td) continue;

            const text = normalize(td.textContent || "");
            if (td.hasAttribute("num") && text) {
              try {
                const style = window.getComputedStyle(td);
                const color = style ? style.color : null;
                if (!color) continue;

                const rgb = color.match(/\d+/g)?.map(Number);
                const hex = rgb
                  ? "#" +
                    rgb.map((v) => v.toString(16).padStart(2, "0")).join("")
                  : "";

                if (hex === "#212529") {
                  lastValidPart = {
                    num: td.getAttribute("num"),
                    numn: td.getAttribute("numn"),
                    title: td.getAttribute("title"),
                    text: td.textContent ? td.textContent.trim() : "",
                  };
                }
              } catch (e) {
                console.error("Error getting style:", e);
              }
            }

            if (lastValidPart) {
              const aliases = PART_ALIASES[partType] || [partType];
              const normText = normalize(text);

              const disallowedWords =
                {
                  compressor: ["bracket", "oil"],
                  expansion: ["evaporator"],
                }[partType] || [];

              const containsDisallowed = disallowedWords.some((w) =>
                normText.includes(w)
              );

              for (const alias of aliases) {
                const normAlias = normalize(alias);
                if (!normAlias) continue;

                const isMatch =
                  partType === "expansion"
                    ? normText.startsWith(normAlias) && !containsDisallowed
                    : normText.includes(normAlias) && !containsDisallowed;

                if (isMatch) {
                  return lastValidPart;
                }
              }
            }
          }
        }
        return null;
      } catch (err) {
        console.error("Error extracting part info:", err);
        return null;
      }
    }, partType);

    console.log(`🔩 ${partType} Part Number:`, partInfo?.num || "Not found");

    // Close page to free resources
    if (page) {
      await page.close();
      page = null;
    }

    return partInfo?.num;
  } catch (error) {
    console.error(`❌ Scraping error: ${error.message}`);
    console.error(error.stack);

    // Take error screenshot if possible
    if (page) {
      try {
        const timestamp = Date.now();
        await page.screenshot({ path: `/tmp/error-${timestamp}.png` });
      } catch (screenshotError) {
        console.error(
          `Failed to take error screenshot: ${screenshotError.message}`
        );
      } finally {
        await page.close();
      }
    }

    throw error;
  }
}

app.post("/superetka/scrape", async (req, res) => {
  const { vin, part } = req.body;

  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  try {
    const result = await Promise.race([
      scrapeSuperEtka(vin, part.toLowerCase()),
      new Promise(
        (_, reject) =>
          setTimeout(() => reject(new Error("Scraping Timeout")), 120000) // 2 min timeout
      ),
    ]);

    if (result) {
      return res.json({ success: true, part: result });
    } else {
      return res
        .status(404)
        .json({ success: false, message: "Part not found" });
    }
  } catch (err) {
    console.error("❌ Scraper Error:", err.message);
    console.error("❌ Scraper Error:", err?.stack || err);
    return res
      .status(500)
      .json({ success: false, error: err.message || "Internal error" });
  }
});

// const PORT = 3000;
// app.listen(PORT, async () => {
//   await initBrowser(); // ✅ Launch browser on startup
//   console.log(`🚀 SuperETKA scraper listening on port ${PORT}`);
// });
