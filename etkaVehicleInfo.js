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

const profileDir = path.join(__dirname, "tmp_profile_superetka_vehicle");
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

async function initBrowser() {
  if (!browser) {
    browser = await puppeteer.launch({
      headless: true,
      userDataDir: profileDir, // ✅ Persistent session
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
      ],
    });
    console.log("✅ Puppeteer launched with persistent session");
  }
  return browser;
}

async function scrapeSuperEtka(vin) {
  const browserInstance = await initBrowser();
  const page = await browserInstance.newPage();

  await page.goto("https://superetka.com/etka", { waitUntil: "networkidle0" });

  // Login if needed
  if (await page.$('input[name="lgn"]')) {
    await page.type('input[name="lgn"]', USERNAME);
    await page.type('input[name="pwd"]', PASSWORD);
    await Promise.all([
      page.click('button[name="go"]'),
      page.waitForNavigation({ waitUntil: "networkidle0" }),
    ]);
  }

  // Enter VIN
  await page.waitForSelector("#vinSearch");
  await page.type("#vinSearch", vin);
  await page.click("#buttonVinSearch");

  await page.waitForSelector("div.modal-content.ui-draggable", {
    timeout: 30000,
  });
  await new Promise((resolve) => setTimeout(resolve, 1000));

  const vehicleInfo = await page.evaluate(() => {
    const table = document.querySelector("table.prTable0 tbody");
    const result = {};

    if (!table) return result;

    for (const row of table.querySelectorAll("tr")) {
      const cells = row.querySelectorAll("td");
      if (cells.length === 2) {
        const key = cells[0].innerText.trim();
        const value = cells[1].innerText.trim();
        result[key] = value;
      }
    }

    return result;
  });

  return vehicleInfo;
}

app.post("/superetka/getVehicleInfo", async (req, res) => {
  const { vin } = req.body;

  if (!vin) {
    return res.status(400).json({ success: false, error: "VIN is required." });
  }

  try {
    const result = await Promise.race([
      scrapeSuperEtka(vin),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Scraping Timeout")), 120000)
      ),
    ]);

    if (result && Object.keys(result).length > 0) {
      const normalizeKeys = (obj) => {
        const formatted = {};
        for (const key in obj) {
          const newKey = key
            .toLowerCase()
            .replace(/\s+/g, "_")
            .replace(/[^a-z0-9_]/g, "");
          formatted[newKey] = obj[key];
        }
        return formatted;
      };

      return res.json({
        success: true,
        vin,
        vehicleInfo: normalizeKeys(result),
      });
    } else {
      return res
        .status(404)
        .json({ success: false, message: "No vehicle details found." });
    }
  } catch (err) {
    console.error("❌ Scraper Error:", err.message);
    return res
      .status(500)
      .json({ success: false, error: err.message || "Internal error" });
  }
});

const PORT = 3001;
app.listen(PORT, "0.0.0.0", async () => {
  await initBrowser(); // ✅ Launch browser on startup
  console.log(`🚀 SuperETKA scraper listening on port ${PORT}`);
});
