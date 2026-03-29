FROM python:3.10-slim

# System deps for yt-dlp, ffmpeg, and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
