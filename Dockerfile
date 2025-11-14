# Dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# System deps for Playwright + pdfplumber
RUN apt-get update && apt-get install -y \
    curl git wget libglib2.0-0 libnss3 libgtk-3-0 libxss1 libasound2 \
    fonts-liberation libatk1.0-0 libdrm2 libxkbcommon0 libgbm1 \
    libxcomposite1 libxrandr2 libxdamage1 libpangocairo-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium

COPY server.py .
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

