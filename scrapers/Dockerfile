FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright (optional, for JS-heavy sites)
RUN apt-get update && apt-get install -y \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY scrapers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scraper code
COPY scrapers/ .

CMD ["python", "scheduler.py"]
