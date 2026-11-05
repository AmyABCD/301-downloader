FROM python:3.11-slim

# Install system dependencies, ffmpeg, curl, git, ca-certificates, unzip, and Deno (required for yt-dlp JS challenges and PO token generation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl git ca-certificates unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /root/bgutil-ytdlp-pot-provider && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.deno/bin:$PATH"

# Run deno install in server directory so generate_once.ts dependencies are pre-installed
RUN cd /root/bgutil-ytdlp-pot-provider/server && deno install

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

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
