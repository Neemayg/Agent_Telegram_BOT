# --- Build Stage ---
FROM python:3.12-slim AS builder

WORKDIR /workspace

# Install system dependencies needed for compiling certain python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# --- Run Stage ---
FROM python:3.12-slim AS runner

WORKDIR /workspace

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy project files
COPY app/ ./app/
COPY logs/ ./logs/

# Set Python path to find app module
ENV PYTHONPATH=/workspace

# Set environment defaults
ENV PYTHONUNBUFFERED=1

# Expose port (metadata documentation)
EXPOSE 8000

# Start server using the python entrypoint which dynamically resolves PORT
CMD ["python", "app/main.py"]
