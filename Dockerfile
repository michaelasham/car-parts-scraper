FROM mcr.microsoft.com/playwright:v1.47.0-jammy

# Install Node.js 20 (the base comes with Node 18 by default)
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*


# Copy bmw-scraper package.json and install its dependencies
COPY bmw-scraper/package*.json ./bmw-scraper/
WORKDIR /app/bmw-scraper
RUN npm install


# Set working directory
WORKDIR /app

# Copy package files first
COPY package*.json ./

# Install Node deps
RUN npm install

# Copy app files
COPY . .

# Expose port
EXPOSE 10000

# Start app
CMD ["npm", "start"]
