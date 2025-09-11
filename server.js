import express from "express";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";
import dotenv from "dotenv";

// Basic setup
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config();

// Initialize Express
const PORT = process.env.PORT || 10000;
const app = express();
app.use(express.json());

// Configure Puppeteer
puppeteer.use(StealthPlugin());
const USERNAME = process.env.ETKA_USER;
const PASSWORD = process.env.ETKA_PASS;
let etkaScraperBrowser; // For parts scraper
let vehicleInfoBrowser; // For vehicle info scraper

// Create separate profile directories
const scraperProfileDir = path.join(__dirname, "tmp_profile_superetka_scraper");
const vehicleProfileDir = path.join(__dirname, "tmp_profile_superetka_vehicle");

// Ensure profile directories exist and clean lock files
for (const dir of [scraperProfileDir, vehicleProfileDir]) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const lockFile = path.join(dir, "SingletonLock");
  if (fs.existsSync(lockFile)) {
    fs.unlinkSync(lockFile);
  }
}

// Enhanced logging middleware
app.use((req, res, next) => {
  const reqId = Math.random().toString(36).substring(2, 8);
  console.log(
    `[${reqId}][REQUEST] ${req.method} ${req.url} ${JSON.stringify(
      req.body || {}
    )}`
  );

  const startTime = Date.now();
  res.on("finish", () => {
    const duration = Date.now() - startTime;
    console.log(`[${reqId}][RESPONSE] ${res.statusCode} (${duration}ms)`);
  });
  next();
});

// Health check endpoint
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    message: "Scraper services running",
    timestamp: new Date().toISOString(),
  });
});

// ====== BROWSER INITIALIZATION FUNCTIONS ======
async function initEtkaScraperBrowser() {
  if (!etkaScraperBrowser) {
    etkaScraperBrowser = await puppeteer.launch({
      headless: true,
      userDataDir: scraperProfileDir,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
      ],
    });
    console.log("✅ ETKA Scraper browser initialized");
  }
  return etkaScraperBrowser;
}

async function initVehicleInfoBrowser() {
  if (!vehicleInfoBrowser) {
    vehicleInfoBrowser = await puppeteer.launch({
      headless: true,
      userDataDir: vehicleProfileDir,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
      ],
    });
    console.log("✅ Vehicle Info browser initialized");
  }
  return vehicleInfoBrowser;
}

// ====== ETKA SCRAPER CONTROLLER ======
async function scrapeSuperEtka(vin, partType) {
  const browserInstance = await initEtkaScraperBrowser();
  const page = await browserInstance.newPage();

  try {
    await page.goto("https://superetka.com/etka", {
      waitUntil: "networkidle0",
    });

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
    await page.keyboard.press("Escape");
    await page.waitForSelector("div.modal-content.ui-draggable", {
      hidden: true,
      timeout: 15000,
    });

    // Click on Air conditioning category
    await page.waitForSelector(".etka_newImg_mainTable li", { timeout: 15000 });
    await new Promise((resolve) => setTimeout(resolve, 2000));

    await page.evaluate(() => {
      const items = Array.from(
        document.querySelectorAll(".etka_newImg_mainTable li")
      );
      const acItem = items.find((el) =>
        el.innerText.includes("Air cond. system")
      );
      if (acItem) acItem.click();
    });

    // The rest of your part scraping logic from etkaScraper.js
    // ...including clicking on part type and extracting part number

    // This is a simplified version - you should include your full logic from etkaScraper.js
    const partInfo = await page.evaluate((partType) => {
      // Your existing part evaluation logic here
      // Return the part number found
    }, partType);

    await page.close();
    return partInfo;
  } catch (error) {
    console.error(`❌ Error scraping part: ${error.message}`);
    await page.close();
    throw error;
  }
}

// ====== VEHICLE INFO CONTROLLER ======
async function scrapeVehicleInfo(vin) {
  const browserInstance = await initVehicleInfoBrowser();
  const page = await browserInstance.newPage();

  try {
    await page.goto("https://superetka.com/etka", {
      waitUntil: "networkidle0",
    });

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

    await page.close();
    return vehicleInfo;
  } catch (error) {
    console.error(`❌ Error scraping vehicle info: ${error.message}`);
    await page.close();
    throw error;
  }
}

// ====== ENDPOINTS ======

// ETKA Scraper endpoint
app.post("/superetka/scrape", async (req, res) => {
  const { vin, part } = req.body;

  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  try {
    const result = await Promise.race([
      scrapeSuperEtka(vin, part.toLowerCase()),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Scraping Timeout")), 120000)
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
    return res
      .status(500)
      .json({ success: false, error: err.message || "Internal error" });
  }
});

// Vehicle Info endpoint
app.post("/superetka/getVehicleInfo", async (req, res) => {
  const { vin } = req.body;

  if (!vin) {
    return res.status(400).json({ success: false, error: "VIN is required." });
  }

  try {
    const result = await Promise.race([
      scrapeVehicleInfo(vin),
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

// BMW Scraper - Find Part
app.post("/find-part", (req, res) => {
  const { vin, part } = req.body;
  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  // Call the Python script with vin and part as arguments
  const pythonProcess = spawn("python", [
    path.join(__dirname, "bmw-scraper", "get_parts.py"),
    vin,
    part,
  ]);

  let output = "";
  let error = "";

  pythonProcess.stdout.on("data", (data) => {
    output += data.toString();
  });

  pythonProcess.stderr.on("data", (data) => {
    error += data.toString();
  });

  pythonProcess.on("close", (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: error || "Python script error." });
    }
    try {
      const resultObj = JSON.parse(output.trim());
      res.json(resultObj);
    } catch (e) {
      res.status(500).json({
        error: "Invalid JSON from Python script.",
        details: output.trim(),
      });
    }
  });
});

// BMW Scraper - Get Car Details
app.get("/get-car-details/:vin", (req, res) => {
  const { vin } = req.params;
  if (!vin) {
    return res.status(400).json({ error: "VIN is required." });
  }

  // Call the Python script to get car details
  const pythonProcess = spawn("python", [
    path.join(__dirname, "bmw-scraper", "get_car_details.py"),
    vin,
  ]);

  pythonProcess.stdout.setEncoding("utf8");
  let output = "";
  let error = "";

  pythonProcess.stdout.on("data", (data) => {
    output += data.toString();
  });

  pythonProcess.stderr.on("data", (data) => {
    error += data.toString();
  });

  pythonProcess.on("close", (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: error || "Python script error." });
    }
    try {
      const resultObj = JSON.parse(output.trim());
      res.json(resultObj);
    } catch (e) {
      res.status(500).json({
        error: "Invalid JSON from Python script.",
        details: output.trim(),
      });
    }
  });
});

// Support direct VIN access
app.get("/:vin", (req, res, next) => {
  const vin = req.params.vin;
  if (/^[A-Z0-9]{5,17}$/.test(vin)) {
    // Forward to get-car-details endpoint
    const pythonProcess = spawn("python", [
      path.join(__dirname, "bmw-scraper", "get_car_details.py"),
      vin,
    ]);

    let output = "";
    let error = "";

    pythonProcess.stdout.on("data", (data) => {
      output += data.toString();
    });

    pythonProcess.stderr.on("data", (data) => {
      error += data.toString();
    });

    pythonProcess.on("close", (code) => {
      if (code !== 0) {
        return res.status(500).json({ error: error || "Python script error." });
      }
      try {
        const resultObj = JSON.parse(output.trim());
        res.json(resultObj);
      } catch (e) {
        res.status(500).json({
          error: "Invalid JSON from Python script.",
          details: output.trim(),
        });
      }
    });
  } else {
    next();
  }
});

// 404 Handler
app.use((req, res) => {
  res.status(404).json({
    error: "Not Found",
    message: `No handler for ${req.method} ${req.url}`,
  });
});

// Start server
app.listen(PORT, "0.0.0.0", async () => {
  console.log(`[SERVER] Server running on port ${PORT}`);

  // Initialize browsers
  await initEtkaScraperBrowser();
  await initVehicleInfoBrowser();
});

// Handle shutdown gracefully
process.on("SIGTERM", async () => {
  console.log("[SERVER] SIGTERM received, shutting down gracefully");

  // Close browser instances
  if (etkaScraperBrowser) await etkaScraperBrowser.close();
  if (vehicleInfoBrowser) await vehicleInfoBrowser.close();

  process.exit(0);
});
