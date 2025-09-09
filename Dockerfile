FROM node:20-slim

RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates \
    libasound2 libatk1.0-0 libc6 libcairo2 libcups2 \
    libdbus-1-3 libexpat1 libfontconfig1 \
    libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 \
    libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 \
    libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 \
    libxrender1 libxss1 libxtst6 fonts-liberation \
    libnss3 lsb-release xdg-utils \
    libgbm1 \
    python3 python3-pip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python development tools and upgrade pip
RUN apt-get update && apt-get install -y \
    python3-dev \
    build-essential \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install playwright with debugging info
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --verbose --no-cache-dir playwright==1.40.0

# Install only Chromium browser to reduce size
RUN python3 -m playwright install chromium


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