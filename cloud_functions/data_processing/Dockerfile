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

# Copy requirements and install
COPY poetry.lock pyproject.toml ./

# Export the requirements to a requirements.txt file
RUN poetry export -f requirements.txt --without-hashes  > requirements.txt

RUN pip install --upgrade pip && \
    pip install -r ./requirements.txt

# Copy the rest of your function code
COPY . .

ENTRYPOINT ["functions-framework", "--target=main", "--debug", "--port=8080"]
