# Heat Pump Dashboard - Flask + WebSocket + ECharts
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy providers module (shared between collector and dashboard)
COPY providers/ ./providers/

# Copy application code
COPY dashboard/app.py .
COPY dashboard/data_query.py .
COPY dashboard/config_colors.py .
COPY dashboard/templates/ templates/
COPY dashboard/static/ static/

# Expose port
EXPOSE 8050

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8050/api/config', timeout=5)"

# Run application
CMD ["python", "app.py"]
