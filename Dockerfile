# ==========================================
# Stage 1: Build Frontend (Node.js)
# ==========================================
FROM node:18-alpine as frontend-build

WORKDIR /app/frontend

# Install dependencies carefully (caching)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Build the app
COPY frontend/ ./
# This produces a /dist folder with index.html and assets
RUN npm run build


# ==========================================
# Stage 2: Build Backend (Python) & Serve
# ==========================================
FROM python:3.11-slim as backend

WORKDIR /app

# Install system dependencies if needed (e.g. for postgres drivers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY backend/ .

# Copy Built Frontend Assets from Stage 1
# We place them in /app/static so main.py can find them
COPY --from=frontend-build /app/frontend/dist /app/static

# Env vars
ENV PYTHONPATH=/app
ENV PORT=8000

# Expose port
EXPOSE 8000

# Start command using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
