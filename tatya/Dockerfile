FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deno.land/install.sh -o /tmp/install-deno.sh && DENO_INSTALL=/opt/deno sh /tmp/install-deno.sh && rm /tmp/install-deno.sh
ENV PATH="/opt/deno/bin:${PATH}"
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY static ./static
RUN useradd --create-home app && mkdir downloads && chown -R app:app /app
USER app
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-proxy-headers"]
