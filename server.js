// server.js
import express from "express";
import proxy from "express-http-proxy";

const PORT = 10000;

import "./etkaScraper.js";
import "./etkaVehicleInfo.js"; // This will launch the scraper server
import "./bmw-scraper/realoem.js"; // This will launch the BMW scraper server

const app = express();
// Simple health check endpoint
app.get("/", (req, res) => {
  res.json({ status: "ok", message: "Scraper services running" });
});

// Forward requests to appropriate services
app.use("/superetka/scrape", proxy("http://localhost:3000/superetka/scrape"));
app.use(
  "/superetka/getVehicleInfo",
  proxy("http://localhost:3001/superetka/getVehicleInfo")
);
app.use("/find-part", proxy("http://localhost:5000/find-part"));
app.use("/get-car-details", proxy("http://localhost:5000/get-car-details"));

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Proxy server listening on port ${PORT}`);
});
