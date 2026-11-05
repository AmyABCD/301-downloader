FROM python:3.11-slim

# Install system dependencies, ffmpeg, curl, and nodejs for YouTube JS challenge solving
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

# Copy source code
COPY . .

EXPOSE 8000
EXPOSE 10000

ENV PORT=8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
