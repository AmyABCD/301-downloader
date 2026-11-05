FROM python:3.11-slim

# Install system dependencies, ffmpeg, curl, ca-certificates, unzip, and deno (required for yt-dlp JS challenges)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl ca-certificates unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.deno/bin:$PATH"

# Copy prebuilt BgUtil POT provider binary and client plugin from official container
COPY --from=ghcr.io/jim60105/bgutil-pot:latest /bgutil-pot /usr/local/bin/bgutil-pot
COPY --from=ghcr.io/jim60105/bgutil-pot:latest /client /etc/yt-dlp-plugins/bgutil-ytdlp-pot-provider
RUN chmod +x /usr/local/bin/bgutil-pot

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
