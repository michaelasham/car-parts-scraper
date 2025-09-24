import express from "express";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import dotenv from "dotenv";
import { scrapeSuperEtka, initBrowser } from "./etkaScraper.js";
import { scrapeVehicleInfo } from "./etkaVehicleInfo.js";
import axios from "axios";

// Basic setup
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config();

// Initialize Express
const PORT = process.env.PORT || 10000;
const app = express();
app.use(express.json());

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
      return res.json({
        success: true,
        vin,
        vehicleInfo: result, // The result is already normalized in the imported function
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
  const pythonProcess = spawn("python3", [
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
  const pythonProcess = spawn("python3", [
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
    const pythonProcess = spawn("python3", [
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

//autodoc
app.get("/autodoc/:part_number/", async (req, res) => {
  const { part_number } = req.params;
  const format = req.query.format || "json"; // Default to JSON if not specified

  if (!part_number) {
    return res.status(400).json({ error: "part_number is required." });
  }

  const pythonProcess = spawn("python3", [
    path.join(__dirname, "autodoc", "autodoc.py"),
    part_number,
  ]);

  let output = "";
  let error = "";

  pythonProcess.stdout.on("data", (data) => {
    output += data.toString();
  });
  pythonProcess.stderr.on("data", (data) => {
    error += data.toString();
  });

  pythonProcess.on("close", async (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: error || "Python script error." });
    }
    try {
      const resultObj = JSON.parse(output.trim());

      // Return JSON with OE numbers and image URL
      if (format === "json") {
        return res.json({
          success: true,
          oe_numbers: resultObj.oe_numbers || [],
          image_url: resultObj.image || null,
        });
      }

      // Return image directly
      if (format === "image") {
        if (!resultObj.image) {
          return res
            .status(404)
            .json({ error: "No image found for this part" });
        }

        try {
          const imageResponse = await axios.get(resultObj.image, {
            responseType: "arraybuffer",
          });
          const contentType =
            imageResponse.headers["content-type"] || "image/jpeg";
          res.set("Content-Type", contentType);
          return res.send(Buffer.from(imageResponse.data));
        } catch (imageError) {
          return res.status(500).json({
            error: "Failed to fetch image",
            details: imageError.message,
          });
        }
      }
    } catch (e) {
      res.status(500).json({
        error: "Invalid JSON from Python script.",
        details: output.trim(),
      });
    }
  });
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
  await initBrowser();
  console.log(`[SERVER] Server running on port ${PORT}`);
});

// Handle shutdown gracefully
process.on("SIGTERM", () => {
  console.log("[SERVER] SIGTERM received, shutting down gracefully");
  process.exit(0);
});
