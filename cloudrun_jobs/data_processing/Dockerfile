# Use the official Python base image
FROM python:3.13-slim

# Set environment vars
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Poetry specific vars
ENV POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  POETRY_HOME='/usr/local'

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
  curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN poetry self add poetry-plugin-export

# Set working directory
WORKDIR /app

# Copy Poetry files from the Cloud Function folder (shared deps)
COPY cloud_functions/data_processing/poetry.lock cloud_functions/data_processing/pyproject.toml ./

# Export requirements and install
RUN poetry export -f requirements.txt --without-hashes > requirements.txt

RUN pip install --upgrade pip && \
    pip install -r ./requirements.txt

# Copy shared code (src) and the job entrypoint
COPY cloud_functions/data_processing/src/ ./src/
COPY cloudrun_jobs/data_processing/main.py ./main.py

# Ensure Python can import from /app/src
ENV PYTHONPATH="/app/src"

# For Jobs: run the script and exit
CMD ["python", "main.py"]
