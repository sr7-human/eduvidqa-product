FROM python:3.10-slim

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Install deno — the JS runtime yt-dlp uses (with yt-dlp-ejs) to solve
# YouTube's "n" signature challenge. Node is NOT supported by yt-dlp's EJS
# challenge solver, so deno is required for video/frame downloads to work.
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- -y \
    && deno --version

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=300 -r requirements.txt

COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/health')"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
