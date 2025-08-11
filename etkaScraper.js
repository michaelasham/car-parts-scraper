import fs from 'fs';
import path, { dirname } from 'path';
import { fileURLToPath } from 'url';
import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import axios from 'axios';
import express from 'express';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const profileDir = path.join(__dirname, 'tmp_profile_superetka_scraper');
const lockFile = path.join(profileDir, 'SingletonLock');

// Ensure profile folder exists
if (!fs.existsSync(profileDir)) {
  fs.mkdirSync(profileDir, { recursive: true });
}

// Remove leftover lock file
if (fs.existsSync(lockFile)) {
  fs.unlinkSync(lockFile);
  console.log('🔓 Removed leftover SingletonLock file');
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
      userDataDir: profileDir,   // ✅ Persistent session
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-software-rasterizer'
      ]
    });
    console.log('✅ Puppeteer launched with persistent session');
  }
  return browser;
}



async function scrapeSuperEtka(vin, partType) {
  const singletonLockPath = './tmp_profile_superetka/SingletonLock';

  if (fs.existsSync(singletonLockPath)) {
    fs.unlinkSync(singletonLockPath);
  }


const browserInstance = await initBrowser();
const page = await browserInstance.newPage();







  await page.goto('https://superetka.com/etka', { waitUntil: 'networkidle0' });

  // Only login if needed
  if (await page.$('input[name="lgn"]')) {
    console.log("🔐 Not logged in. Logging in...");
    await page.type('input[name="lgn"]', USERNAME);
    await page.type('input[name="pwd"]', PASSWORD);
    await Promise.all([
      page.click('button[name="go"]'),
      page.waitForNavigation({ waitUntil: 'networkidle0' })
    ]);
    console.log("✅ Logged in successfully.");
  } else {
    console.log("✅ Already logged in.");
  }

  console.log('✅ Checking for VIN modal...');

  await page.waitForSelector('#vinSearch');
  await page.type('#vinSearch', vin);
  await page.click('#buttonVinSearch');

  await page.waitForSelector('div.modal-content.ui-draggable', { timeout: 30000 });
  console.log("✅ VIN modal content appeared");
  await new Promise(resolve => setTimeout(resolve, 1000));
  await page.keyboard.press('Escape');
  console.log("✅ Pressed Escape to close VIN modal");
  await page.waitForSelector('div.modal-content.ui-draggable', { hidden: true, timeout: 15000 });

  await page.waitForSelector('.etka_newImg_mainTable li', { timeout: 15000 });
  await new Promise(resolve => setTimeout(resolve, 2000));

  await page.evaluate(() => {
    const items = Array.from(document.querySelectorAll('.etka_newImg_mainTable li'));
    const acItem = items.find(el => el.innerText.includes('Air cond. system'));
    if (acItem) acItem.click();
  });
  console.log("✅ Clicked Air Conditioning category.");

  await page.evaluate(() => {
    const el = document.querySelector('table.subGrTable');
    if (el) el.scrollIntoView();
  });
  await new Promise(resolve => setTimeout(resolve, 1000));

  await page.evaluate((partType) => {
    const normalize = (text) => text.toLowerCase().replace(/\s+/g, ' ').trim();
    const rows = Array.from(document.querySelectorAll('table.subGrTable tr'));

    function getHexColor(td) {
      const color = window.getComputedStyle(td).color;
      const rgb = color.match(/\d+/g)?.map(Number);
      return rgb ? '#' + rgb.map(v => v.toString(16).padStart(2, '0')).join('') : '';
    }

    function isRowActive(row) {
      const tds = Array.from(row.querySelectorAll('td'));
      return tds.some(td => getHexColor(td) === '#212529');
    }

    function findByMatch(method) {
      return rows.find(row => {
        const text = normalize(row.textContent);
        return method(text) && isRowActive(row);
      });
    }

    const tryKeywords = (keywords) => {
      for (const keyword of keywords) {
        const target =
          findByMatch(t => t === keyword) ||
          findByMatch(t => t.startsWith(keyword)) ||
          findByMatch(t => t.includes(keyword));
        if (target) return target;
      }
      return null;
    };

    const keyword = normalize(partType);
    let targetRow = tryKeywords([keyword]);

    if (!targetRow && keyword === 'expansion') {
      targetRow = tryKeywords(['evaporator', 'electronic regulation']);
    }

    if (!targetRow && keyword === 'evaporator') {
      targetRow = tryKeywords(['electronic regulation']);
    }

    if (targetRow) targetRow.click();
  }, partType);

  console.log("🖱️ Clicked on partType row.");

  await page.waitForFunction((partType) => {
    return Array.from(document.querySelectorAll('table.detailsTable td.etkTd'))
      .some(td => td.textContent.trim().toLowerCase().includes(partType));
  }, { timeout: 30000 }, partType);

const partInfo = await page.evaluate((partType) => {
  const normalize = (text) =>
    text?.toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ').trim() || '';

  const PART_ALIASES = {
    compressor: ['compressor', 'ac compressor', 'a/c compressor', 'a c compressor'],
    condenser: ['condenser'],
    evaporator: ['evaporator'],
    expansion: ['expansion', 'expansion valve', 'valve', 'regulation valve']
  };

  const rows = Array.from(document.querySelectorAll('table.detailsTable tr'));
  let lastValidPart = null;

  for (const row of rows) {
    const tds = Array.from(row.querySelectorAll('td.etkTd'));

    for (const td of tds) {
      const text = normalize(td.textContent || '');
      if (td.hasAttribute('num') && text) {
        const color = window.getComputedStyle(td).color;
        const rgb = color.match(/\d+/g)?.map(Number);
        const hex = rgb ? '#' + rgb.map(v => v.toString(16).padStart(2, '0')).join('') : '';

        if (hex === '#212529') {
          lastValidPart = {
            num: td.getAttribute('num'),
            numn: td.getAttribute('numn'),
            title: td.getAttribute('title'),
            text: td.textContent.trim()
          };
        }
      }

      if (lastValidPart) {
        const aliases = PART_ALIASES[partType] || [partType];
        const normText = normalize(text);
        const disallowedWords = {
          compressor: ['bracket', 'oil'],
          expansion: ['evaporator']
        }[partType] || [];

        const containsDisallowed = disallowedWords.some(w => normText.includes(w));

        // ✅ `normAlias` never leaks outside this block
        for (let alias of aliases) {
          const normAlias = normalize(alias);
          const isMatch =
            partType === 'expansion'
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
}, partType);



  console.log(`🔩 ${partType} Part Number:`, partInfo?.num || 'Not found');

  await page.close();
  return partInfo?.num;
}

app.post('/superetka/scrape', async (req, res) => {
  const { vin, part } = req.body;

  if (!vin || !part) {
    return res.status(400).json({ error: 'vin and part are required.' });
  }

  try {
    const result = await Promise.race([
      scrapeSuperEtka(vin, part.toLowerCase()),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Scraping Timeout')), 120000) // 2 min timeout
      )
    ]);

    if (result) {
      return res.json({ success: true, part: result });
    } else {
      return res.status(404).json({ success: false, message: 'Part not found' });
    }
  } catch (err) {
    console.error('❌ Scraper Error:', err.message);
    return res.status(500).json({ success: false, error: err.message || 'Internal error' });
  }
});


const PORT =  3000;
app.listen(PORT, async () => {
  await initBrowser(); // ✅ Launch browser on startup
  console.log(`🚀 SuperETKA scraper listening on port ${PORT}`);
});
