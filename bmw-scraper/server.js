const express = require("express");
const { spawn } = require("child_process");
const path = require("path");

const app = express();
app.use(express.json());

app.post("/find-part", (req, res) => {
  const { vin, part } = req.body;
  if (!vin || !part) {
    return res.status(400).json({ error: "vin and part are required." });
  }

  // Call the Python script with vin and part as arguments
  const pythonProcess = spawn("python", [
    path.join(__dirname, "get_parts.py"),
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

app.get("/get-car-details/:vin", (req, res) => {
  const { vin } = req.params;
  if (!vin) {
    return res.status(400).json({ error: "VIN is required." });
  }
  // Call the Python script to get car details
  const pythonProcess = spawn("python", [
    path.join(__dirname, "get_car_details.py"),
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

const PORT = 10001;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
