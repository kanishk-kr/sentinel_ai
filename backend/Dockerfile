FROM python:3.11-slim

# Install system dependencies (for LibreOffice, Tesseract OCR, psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    libreoffice \
    poppler-utils \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/pyproject.toml .
# Normally we would use poetry or pip to install from pyproject.toml
# For this setup, we'll install directly using pip
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio && \
    pip install --no-cache-dir \
    fastapi uvicorn sqlalchemy asyncpg psycopg2-binary pydantic pydantic-settings \
    "python-jose[cryptography]" passlib "bcrypt<4.0.0" groq google-genai qdrant-client \
    python-docx openpyxl python-pptx PyPDF2 PyYAML python-multipart \
    pytesseract Pillow pdf2image sentence-transformers httpx aiofiles orjson

# Copy source code
COPY backend/src /app/src
COPY docker/configs /app/configs

# Set environment variables
ENV PYTHONPATH=/app
ENV APP_ENV=production
ENV SOVEREIGN_MODE=true

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
