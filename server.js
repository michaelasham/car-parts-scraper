import express from "express";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import dotenv from "dotenv";
import axios from "axios";

// Basic setup
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config();

// Initialize Express
const PORT = process.env.PORT || 10000;
const app = express();
app.use(express.json());

// Accept JSON, URL-encoded, and raw text (e.g., Postman "Text" tab)
app.use(express.json({ limit: "1mb" }));
app.use(express.urlencoded({ extended: true, limit: "1mb" }));
app.use(
  express.text({ type: ["text/*", "application/octet-stream"], limit: "1mb" })
);

// If body came in as text, but looks like JSON, parse it.
app.use((req, _res, next) => {
  if (typeof req.body === "string") {
    try {
      const maybe = JSON.parse(req.body);
      if (maybe && typeof maybe === "object") req.body = maybe;
    } catch {
      // leave as string; routes will validate and 400 gracefully
    }
  }
  next();
});

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

// etka Scraper - Get Car Details
app.get("/superetka/get-car-details/:vin", (req, res) => {
  const { vin } = req.params;
  if (!vin) {
    return res.status(400).json({ error: "VIN is required." });
  }

  // Call the Python script to get car details
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "etka", "get_vehicle_data.py"),
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

// etka Scraper - Find Part
app.post("/superetka/find-part", (req, res) => {
  const { vin, part } = req.body;
  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  const ac_keywords = [
    "compressor",
    "evaporator",
    "compressor bracket",
    "expansion valve",
  ];
  const quick_service_keywords = [
    "oil-filter",
    "engine oil",
    "engine oil filter",
    "air filter",
    "air-filter",
    "spark plugs",
    "spark-plugs",
    "dust filter",
    "pollen filter",
    "ac filter",
    "insert filter",
    "harmful substance filter",
    "transmission oil",
    "brake discs",
    "brake-discs",
    "disc brake pads",
    "toothed belt",
    "assembly belt",
    "timing belt",
    "timing belt kit",
  ];

  let selected_operation = "";
  try {
    if (ac_keywords.includes(part)) {
      selected_operation = "get_ac_parts.py";
    } else if (quick_service_keywords.includes(part)) {
      selected_operation = "get_maintenance_parts.py";
    } else {
      throw new Error("Unsupported Keyword!");
    }
  } catch (e) {
    res.status(500).json({
      error: "Unsupported Keyword",
    });
  }

  // Call the Python script with vin and part as arguments
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "etka", selected_operation),
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
// BMW Scraper - Find Part
const ALLOWED_GROUP_KEYS = [
  "parts repair service",
  "engine",
  "engine electrical system",
  "fuel preparation system",
  "fuel supply",
  "radiator",
  "exhaust system",
  "clutch",
  "engine and transmission suspension",
  "manual transmission",
  "automatic transmission",
  "gearshift",
  "drive shaft",
  "front axle",
  "steering",
  "rear axle",
  "brakes",
  "pedals",
  "wheels",
  "bodywork",
  "vehicle trim",
  "seats",
  "sliding roof / folding top",
  "vehicle electrical system",
  "instruments measuring systems",
  "lighting",
  "audio navigation electronic systems",
  "distance systems cruise control",
  "equipment parts",
  "restraint system and accessories",
  "communication systems",
  "value part sparepackages service and repair",
  "auxiliary materials fluidscolorsystem",
];

app.post("/realoem/find-part", (req, res) => {
  const { vin, part } = req.body;
  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  const ac_keywords = [
    "compressor",
    "evaporator",
    "compressor bracket",
    "expansion valve",
    "condenser",
  ];
  const quick_service_keywords = [
    "oil-filter",
    "air filter",
    "spark plugs",
    "spark plug",
    "brake disc",
    "brake discs",
  ];

  const brake_keywords = [
    "front brake disc",
    "rear brake disc",
    "brake pads",
    "front brake pad wear sensor",
  ];

  const radiator_keywords = [
    "expansion tank",
    "radiator",
    "fan housing w/ fan",
  ];
  let selected_operation = "";
  try {
    if (ac_keywords.includes(part.toLowerCase())) {
      selected_operation = "get_ac_parts.py";
    } else if (quick_service_keywords.includes(part.toLowerCase())) {
      selected_operation = "get_maintenance_parts.py";
    } else if (brake_keywords.includes(part.toLowerCase())) {
      selected_operation = "get_brakes.py";
    } else if (radiator_keywords.includes(part.toLowerCase())) {
      selected_operation = "get_radiator_parts.py";
    } else {
      throw new Error("Unsupported Keyword!");
    }
  } catch (e) {
    res.status(500).json({
      error: "Unsupported Keyword",
    });
  }

  // Call the Python script with vin and part as arguments
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "bmw-scraper", selected_operation),
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
app.post("/realoem/query-group", (req, res) => {
  const { vin, group } = req.body;
  if (!vin || !group) {
    return res.status(400).json({ error: "vin and group are required." });
  }

  let selected_operation = "";
  try {
    if (ALLOWED_GROUP_KEYS.includes(group)) {
      selected_operation = "get_main_group.py";
    } else {
      throw new Error("Unsupported Keyword!");
    }
  } catch (e) {
    res.status(500).json({
      error: "Unsupported Keyword",
    });
  }

  // Call the Python script with vin and part as arguments
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "bmw-scraper", selected_operation),
    vin,
    group,
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
app.get("/realoem/get-car-details/:vin", (req, res) => {
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

app.get("/7zap/get-car-details/:vin", (req, res) => {
  const { vin } = req.params;
  if (!vin) {
    return res.status(400).json({ error: "VIN is required." });
  }

  // Call the Python script to get car details
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "7zap", "get_car_details.py"),
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
app.post("/7zap/find-part", (req, res) => {
  const { vin, part } = req.body;
  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  // Call the Python script with vin and part as arguments
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "7zap", "get_ac_parts.py"),
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
app.post("/mercedes/find-part", (req, res) => {
  const { vin, part } = req.body;
  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  // Call the Python script with vin and part as arguments
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "mercedes-scraper", "get_ac_parts.py"),
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

app.get("/mercedes/get-car-details/:vin", (req, res) => {
  const { vin } = req.params;
  if (!vin) {
    return res.status(400).json({ error: "VIN is required." });
  }

  // Call the Python script to get car details
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "mercedes-scraper", "get_vehicle_data.py"),
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

app.get("/ssg/get-car-details/:vin", (req, res) => {
  const { vin } = req.params;
  if (!vin) {
    return res.status(400).json({ error: "VIN is required." });
  }

  // Call the Python script to get car details
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "ssg", "get_vehicle_data.py"),
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

// 404 Handler
app.use((req, res) => {
  res.status(404).json({
    error: "Not Found",
    message: `No handler for ${req.method} ${req.url}`,
  });
});

// Start server
app.listen(PORT, "0.0.0.0", async () => {
  //await initBrowser();
  console.log(`[SERVER] Server running on port ${PORT}`);
});

// Handle shutdown gracefully
process.on("SIGTERM", () => {
  console.log("[SERVER] SIGTERM received, shutting down gracefully");
  process.exit(0);
});
