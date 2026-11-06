FROM python:3.11-slim

# Install system dependencies: ffmpeg, curl, ca-certificates, unzip, and Deno (yt-dlp's default JS engine)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl ca-certificates unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.deno/bin:$PATH"

WORKDIR /app

# Install Python packages & latest yt-dlp + ejs solver + curl-cffi for browser TLS impersonation
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp yt-dlp-ejs yt-dlp-youtube-oauth2 curl-cffi

# Copy source code
COPY . .

EXPOSE 8000
EXPOSE 10000

ENV PORT=8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
