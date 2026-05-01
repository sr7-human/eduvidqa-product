# EduVidQA

AI tutor for YouTube lectures. Every answer is traceable to a moment in the lecture.

## Features

- **Timestamped RAG answers** — citations link to the exact second in the lecture
- **Vision-language model** — reads slides + transcript together
- **Quiz checkpoints** — auto-generated at topic boundaries
- **On-demand quizzes** — test yourself anytime while watching
- **Spaced review** — SM-2 algorithm resurfaces missed questions
- **Quality scoring** — Clarity / ECT / UPT ratings on every answer

## Quick Start

```bash
git clone <repo-url>
cd eduvidqa-product

# 1. Backend
cp .env.example .env                            # then fill in API keys
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## Environment Variables

See [.env.example](.env.example) for the full list.

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for Llama models |
| `GEMINI_API_KEY` | Yes | Google Gemini API key (vision + fallback) |
| `DATABASE_URL` | Yes | Supabase Postgres connection string (use the pooler) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase private key (backend only) |
| `SUPABASE_JWT_SECRET` | Yes | JWT verification secret |
| `HF_TOKEN` | No | Hugging Face token (for HF Space deploy) |
| `INFERENCE_ENGINE` | No | `groq` (default) / `gemini` / `local` |
| `LAZY_LOAD` | No | `true` defers heavy model loading on startup |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | No | System status |
| POST | `/api/process-video` | JWT | Submit video for processing |
| POST | `/api/ask` | Optional | Ask a question (demo video is free) |
| GET | `/api/videos/{id}/status` | No | Poll processing status |
| GET | `/api/users/me/videos` | JWT | User's video library |
| GET | `/api/videos/{id}/checkpoints` | JWT | Quiz checkpoints |
| POST | `/api/videos/{id}/quiz` | JWT | Generate quiz questions |
| POST | `/api/quizzes/{id}/attempt` | JWT | Submit quiz answer |
| GET | `/api/users/me/review` | JWT | Due review questions |
| POST | `/api/review/{id}/attempt` | JWT | Submit review answer |
| DELETE | `/api/users/me` | JWT | Delete all user data (GDPR) |

## Architecture

```
React (Vite + Tailwind)
        ↓
FastAPI (uvicorn)
        ↓
Supabase (Postgres + pgvector + Auth + Storage)
        ↓
Groq / Google Gemini  (LLM + vision inference)
```

## Testing

```bash
pytest -q                              # backend tests
cd frontend && npm run build           # frontend type check + build
```

## Deployment

- **Frontend:** Vercel (Vite build) — see [vercel.json](vercel.json)
- **Backend:** Hugging Face Space (Docker) — see [Dockerfile](Dockerfile) and [README_HF.md](README_HF.md)
- **Database:** Supabase (free tier works for MVP)

## Based On

EMNLP 2025 EduVidQA paper — [Paper Explainer](https://sr7-human.github.io/eduvidqa-explained/)

## License

See [docs/archive/](docs/archive/) for the original handoff and design docs.
