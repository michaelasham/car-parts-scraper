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

// Set up proxies to internal services
app.use(
  "/superetka/scrape",
  createProxyMiddleware({
    target: "http://localhost:3000",
    changeOrigin: true,
  })
);

app.use(
  "/superetka/getVehicleInfo",
  createProxyMiddleware({
    target: "http://localhost:3001",
    changeOrigin: true,
  })
);

app.use(
  "/find-part",
  createProxyMiddleware({
    target: "http://localhost:5000",
    changeOrigin: true,
  })
);

app.use(
  "/get-car-details/:vin",
  createProxyMiddleware({
    target: "http://localhost:5000",
    changeOrigin: true,
  })
);

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Proxy server listening on port ${PORT}`);
});
