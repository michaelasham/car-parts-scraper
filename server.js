import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";
import http from "http";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Use Render's PORT or default to 10000
const PORT = process.env.PORT || 10000;
const app = express();

// Support JSON requests
app.use(express.json());

// Health check endpoint
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    message: "Scraper services running",
    timestamp: new Date().toISOString(),
  });
});

// Enhanced debug logging middleware
app.use((req, res, next) => {
  const reqId = Math.random().toString(36).substring(2, 8);
  console.log(
    `[${reqId}][DEBUG] ${req.method} ${req.url} ${JSON.stringify(
      req.body || {}
    )}`
  );

  // Track response time
  const startTime = Date.now();
  res.on("finish", () => {
    const duration = Date.now() - startTime;
    console.log(`[${reqId}][RESPONSE] ${res.statusCode} (${duration}ms)`);
  });

  next();
});

// Improved proxy middleware creator
function createBetterProxy(target, options = {}) {
  return createProxyMiddleware({
    target,
    changeOrigin: true,
    secure: false,
    xfwd: true,
    // Don't modify the path - important for parameter paths
    pathRewrite: (path, req) => path,
    onProxyReq: (proxyReq, req) => {
      const reqId = Math.random().toString(36).substring(2, 8);
      console.log(
        `[${reqId}][PROXY] ${req.method} ${req.url} -> ${target}${proxyReq.path}`
      );

      // If it's a POST/PUT with a body, we need to handle the body
      if (req.body && ["POST", "PUT"].includes(req.method)) {
        const bodyData = JSON.stringify(req.body);
        proxyReq.setHeader("Content-Type", "application/json");
        proxyReq.setHeader("Content-Length", Buffer.byteLength(bodyData));
        proxyReq.write(bodyData);
      }
    },
    onProxyRes: (proxyRes, req, res) => {
      const reqId = Math.random().toString(36).substring(2, 8);
      console.log(
        `[${reqId}][PROXY-RES] ${proxyRes.statusCode} for ${req.method} ${req.url}`
      );
    },
    onError: (err, req, res) => {
      console.error(`[ERROR] Proxy error for ${req.method} ${req.url}:`, err);
      res.status(502).json({
        error: "Proxy error",
        message: err.message,
        url: req.url,
        method: req.method,
      });
    },
    ...options,
  });
}

// Service management - start the services if they're not imported
let etkaScraperStarted = false;
let etkaVehicleInfoStarted = false;
let bmwScraperStarted = false;

function startServices() {
  console.log("[STARTUP] Starting required services...");

  try {
    // Start each service
    import("./etkaScraper.js")
      .then(() => {
        etkaScraperStarted = true;
        console.log("[STARTUP] ETKA Scraper loaded");
      })
      .catch((err) =>
        console.error("[ERROR] Failed to load ETKA Scraper:", err)
      );

    import("./etkaVehicleInfo.js")
      .then(() => {
        etkaVehicleInfoStarted = true;
        console.log("[STARTUP] ETKA Vehicle Info loaded");
      })
      .catch((err) =>
        console.error("[ERROR] Failed to load ETKA Vehicle Info:", err)
      );

    import("./bmw-scraper/realoem.js")
      .then(() => {
        bmwScraperStarted = true;
        console.log("[STARTUP] BMW Scraper loaded");
      })
      .catch((err) =>
        console.error("[ERROR] Failed to load BMW Scraper:", err)
      );
  } catch (err) {
    console.error("[ERROR] Error starting services:", err);
  }
}

// Set up proxies to internal services
app.use("/superetka/scrape", createBetterProxy("http://localhost:3000"));
app.use(
  "/superetka/getVehicleInfo",
  createBetterProxy("http://localhost:3001")
);
app.use("/find-part", createBetterProxy("http://localhost:5000"));
app.use("/get-car-details", createBetterProxy("http://localhost:5000"));

// Support direct VIN access for convenience
app.get("/:vin", (req, res, next) => {
  const vin = req.params.vin;
  // Only handle requests that look like VINs (alphanumeric, length 5-17)
  if (/^[A-Z0-9]{5,17}$/.test(vin)) {
    console.log(`[VIN] Redirecting direct VIN access: ${vin}`);

    // Forward directly to internal service
    const proxyReq = http.request(
      {
        host: "localhost",
        port: 5000,
        path: `/get-car-details/${vin}`,
        method: "GET",
      },
      (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      }
    );

    proxyReq.on("error", (e) => {
      console.error(`[ERROR] Direct VIN proxy error: ${e.message}`);
      res.status(502).json({ error: "Gateway Error", message: e.message });
    });

    proxyReq.end();
  } else {
    next(); // Not a VIN, let other handlers process it
  }
});

// Add a catch-all route handler
app.use((req, res) => {
  console.log(`[404] No route for ${req.method} ${req.url}`);
  res.status(404).json({
    error: "Not Found",
    message: `No handler for ${req.method} ${req.url}`,
  });
});

// Start listening
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[SERVER] Proxy server listening on port ${PORT}`);
  startServices();
});

// Handle shutdown gracefully
process.on("SIGTERM", () => {
  console.log("[SERVER] SIGTERM received, shutting down gracefully");
  // Add any cleanup logic here
  process.exit(0);
});
