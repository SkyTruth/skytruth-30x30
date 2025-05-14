# Use the official Python base image
FROM python:3.13-slim

# Set environment vars
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install OS dependencies
RUN apt-get update && apt-get install -y \
    g++ \
    gcc \
    git \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libspatialindex-dev \
    python3-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt src/ .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your function code
COPY . .

CMD ["python", "main.py"]
