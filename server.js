import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";

// Use Render's PORT or default to 10000
const PORT = process.env.PORT || 10000;

// Import services
import "./etkaScraper.js";
import "./etkaVehicleInfo.js";
import "./bmw-scraper/realoem.js";

const app = express();

// Health check endpoint
app.get("/", (req, res) => {
  res.json({ status: "ok", message: "Scraper services running" });
});

// Add debug logging middleware
app.use((req, res, next) => {
  console.log(`[DEBUG] Incoming request: ${req.method} ${req.url}`);
  next();
});

// Set up proxies to internal services with debugging
const createDebugProxy = (target, pathRewrite = {}) => {
  return createProxyMiddleware({
    target,
    changeOrigin: true,
    pathRewrite,
    onProxyReq: (proxyReq, req) => {
      console.log(
        `[PROXY] ${req.method} ${req.url} -> ${target}${proxyReq.path}`
      );
    },
    onError: (err, req, res) => {
      console.error(`[PROXY ERROR] ${req.method} ${req.url}:`, err);
      res.status(500).json({ error: "Proxy error", message: err.message });
    },
  });
};

// ETKA Scraper proxy
app.use("/superetka/scrape", createDebugProxy("http://localhost:3000"));

// ETKA Vehicle Info proxy
app.use("/superetka/getVehicleInfo", createDebugProxy("http://localhost:3001"));

// BMW Find Part proxy
app.use("/find-part", createDebugProxy("http://localhost:5000"));

// BMW Car Details proxy - FIXED: Use path pattern without parameters
app.use(
  "/get-car-details", // Changed from "/get-car-details/:vin"
  createDebugProxy("http://localhost:5000")
);

// Start listening
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Proxy server listening on port ${PORT}`);
});
