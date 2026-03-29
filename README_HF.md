---
title: EduVidQA
emoji: 🎓
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# EduVidQA — AI Teaching Assistant for YouTube Lectures

**EMNLP 2025** | Multimodal RAG pipeline using Qwen2.5-VL-7B

## What it does

Paste a YouTube lecture URL + ask a question → get an accurate, pedagogically rich answer grounded in the lecture content (transcript + video frames).

## Pipeline

1. **Ingest** — downloads transcript (captions or Whisper fallback) + extracts key frames
2. **RAG** — embeds segments with BGE-M3, retrieves top-K via ChromaDB
3. **Inference** — Qwen2.5-VL-7B generates an educational answer using transcript + frames

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/process-video` | Pre-index a video |
| `POST` | `/api/ask` | Ask a question about a lecture |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `Qwen/Qwen2.5-VL-7B-Instruct` | HuggingFace model ID |
| `QUANTIZE_4BIT` | `true` | Use 4-bit quantisation (CUDA only) |
| `LAZY_LOAD` | `false` | Defer model loading to first request |
| `DATA_DIR` | `./data` | Cache directory for transcripts/frames |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
