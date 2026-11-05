FROM python:3.11-slim

# Install system dependencies, ffmpeg, curl, ca-certificates, unzip, and deno (required for yt-dlp JS challenges)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl ca-certificates unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    curl -L -o /usr/local/bin/bgutil-pot https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/latest/download/bgutil-pot-linux-x86_64 && \
    chmod +x /usr/local/bin/bgutil-pot && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.deno/bin:$PATH"

WORKDIR /app

# Install Python packages & latest yt-dlp + pot provider plugin
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp bgutil-ytdlp-pot-provider

# Copy source code
COPY . .

EXPOSE 8000
EXPOSE 10000

ENV PORT=8000

# Start PO Token provider daemon in background on port 4416, then start FastAPI web server
CMD ["sh", "-c", "bgutil-pot server --host 127.0.0.1 --port 4416 & uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
