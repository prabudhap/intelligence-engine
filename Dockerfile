# ==========================================
# Stage 1: Build & Compile Dependencies
# ==========================================
FROM python:3.12.10-slim AS builder

WORKDIR /code

# Install system dependencies needed for compiling C-based Python extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment to isolate dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python requirements
COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download and install the spaCy English NLP model inside the virtual environment
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0.tar.gz

# ==========================================
# Stage 2: Clean Runtime Environment
# ==========================================
FROM python:3.12.10-slim AS runner

WORKDIR /code

# Copy compiled virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the application source code
COPY ./app /code/app

# Expose FastAPI default port
EXPOSE 8000

# Set environment variable defaults
ENV NEO4J_URI=bolt://neo4j_db:7687 \
    NEO4J_USER=neo4j \
    NEO4J_PASSWORD=secure_password_123

# Run uvicorn server (production mode, reload disabled by default)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]