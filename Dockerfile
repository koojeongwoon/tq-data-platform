# Multi-stage build for optimal image size
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install -e .

# Download BGE-M3 model (~2GB)
# This runs during build time, so the model is included in the image
RUN . /app/.venv/bin/activate && \
    python -c "from sentence_transformers import SentenceTransformer; \
               print('Downloading BGE-M3 model...'); \
               model = SentenceTransformer('BAAI/bge-m3'); \
               print(f'Model ready! Dimension: {model.get_sentence_embedding_dimension()}')"

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy virtual environment from builder (includes downloaded model)
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

# Copy application code (only app directory, not batch)
COPY app ./app
COPY shared ./shared
COPY pyproject.toml ./

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
