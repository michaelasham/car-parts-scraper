FROM node:20-slim

# Install system dependencies (for Puppeteer & Playwright browsers)
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates curl python3 python3-pip python3-venv \
    gconf-service libasound2 libatk1.0-0 libc6 libcairo2 libcups2 \
    libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 \
    libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 \
    libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 \
    libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 \
    libxrender1 libxss1 libxtst6 fonts-liberation \
    libnss3 lsb-release xdg-utils \
    libgbm1 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright for Python (this also installs browsers by default)
RUN pip3 install --no-cache-dir playwright && playwright install --with-deps

# Set working directory
WORKDIR /app

# Copy package files first for caching
COPY package*.json ./

# Install Node dependencies (for Puppeteer & Node app)
RUN npm install

# Copy remaining project files
COPY . .

# Puppeteer environment variables
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false

# Expose port (Render expects this)
EXPOSE 10000

RUN mkdir -p /data/chrome-profile && chmod -R 777 /data

# Start server
CMD ["npm", "start"]
