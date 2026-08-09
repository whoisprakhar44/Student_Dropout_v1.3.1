FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including those required for PostgreSQL and Kerberos/Impyla
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    libkrb5-dev \
    krb5-user \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=8080

EXPOSE 8080

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
