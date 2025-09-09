FROM node:20-slim

# Install dependencies for Puppeteer + Python + Playwright + required shared libraries
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates \
    gconf-service libasound2 libatk1.0-0 libc6 libcairo2 libcups2 \
    libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 \
    libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 \
    libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 \
    libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 \
    libxrender1 libxss1 libxtst6 fonts-liberation \
    libnss3 lsb-release xdg-utils \
    libgbm1 \
    python3 python3-pip python3-venv \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /app

# Copy package files first for caching
COPY package*.json ./

# Install Node.js dependencies
RUN npm install

# Upgrade pip and install Python dependencies
RUN pip3 install --upgrade pip setuptools wheel

# Install Python dependencies (create requirements.txt if needed)
# COPY requirements.txt ./
# RUN pip3 install -r requirements.txt

# Install Playwright for Python only
RUN pip3 install playwright
RUN python3 -m playwright install --with-deps

# Copy remaining project files
COPY . .

# Environment variables
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Expose port (Render expects this)
EXPOSE 10000

# Create directories with proper permissions
RUN mkdir -p /data/chrome-profile && chmod -R 777 /data
RUN mkdir -p /ms-playwright && chmod -R 777 /ms-playwright

# Start server
CMD ["npm", "start"]