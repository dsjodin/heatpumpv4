FROM python:3.11-slim

# Set UTF-8 locale to fix character encoding issues
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

WORKDIR /app

# Install dependencies
COPY collector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy providers module (shared between collector and dashboard)
COPY providers/ ./providers/

# Copy application files
COPY collector/collector.py .

# Run the API collector
CMD ["python", "-u", "collector.py"]
