FROM node:20-slim

# Install dependencies in smaller batches to isolate issues
RUN apt-get update && \
    # Install basic tools first
    apt-get install -y wget gnupg ca-certificates python3 python3-pip --no-install-recommends && \
    # Install standard libraries
    apt-get install -y \
    libasound2 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    --no-install-recommends && \
    # Try to install potentially problematic packages separately
    apt-get install -y \
    fonts-liberation \
    libnss3 \
    --no-install-recommends && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Playwright with only necessary browser
RUN pip install playwright && python -m playwright install chromium

# Set working directory
WORKDIR /app

# Copy package files first for caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy bmw-scraper package.json and install its dependencies
COPY bmw-scraper/package*.json ./bmw-scraper/
WORKDIR /app/bmw-scraper
RUN npm install
WORKDIR /app

# Copy remaining project files
COPY . .

# Puppeteer environment variables
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false

# Expose ports (Render expects this)
EXPOSE 10000

RUN mkdir -p /data/chrome-profile && chmod -R 777 /data

# Start server
CMD ["npm", "start"]