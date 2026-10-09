FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with UID 1000 (standard for Hugging Face Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Create cache directory and pre-cache DistilBERT weights during build
RUN mkdir -p /app/.cache/huggingface && \
    python -c "from transformers import AutoTokenizer, AutoModel; AutoTokenizer.from_pretrained('distilbert/distilbert-base-uncased'); AutoModel.from_pretrained('distilbert/distilbert-base-uncased')"

# Copy application source and artifacts
COPY . /app

# Ensure directories are writable by user
RUN mkdir -p /app/data/interim && \
    chown -R user:user /app

# Switch to non-root user
USER user

# Expose Hugging Face Space default port
EXPOSE 7860

# Launch ContextBind REST API and Interactive UI
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "7860"]
