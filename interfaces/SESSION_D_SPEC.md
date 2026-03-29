# Session D: Frontend Worker — Interface Specification

## Status
- **Assigned:** Not yet started
- **Dependencies:** BLOCKED — needs API contract from Session E (but can scaffold UI immediately)
- **Last updated:** March 29, 2026

---

## Your Mission
Build a React web app where students can paste a YouTube lecture URL, enter a timestamp and question, and receive an AI-generated educational answer with quality scores.

## Context
We're building an AI Teaching Assistant for YouTube lectures (EduVidQA paper, EMNLP 2025). The backend (Session E) exposes a REST API. You build the user-facing frontend that talks to it.

## Hardware
- MacBook Air M2 16GB (local dev)
- Vercel free tier (production hosting)

## Files You Create
```
frontend/
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts            # API client (talks to backend)
│   ├── components/
│   │   ├── Header.tsx
│   │   ├── VideoInput.tsx        # URL + timestamp + question form
│   │   ├── AnswerDisplay.tsx     # Shows AI answer with formatting
│   │   ├── QualityBadges.tsx     # Clarity/ECT/UPT score badges
│   │   ├── SourceTimestamps.tsx  # Shows which video segments were used
│   │   ├── LoadingState.tsx      # Animated loading during inference
│   │   └── ErrorState.tsx
│   ├── hooks/
│   │   └── useAskQuestion.ts    # React Query hook for the API call
│   └── types/
│       └── index.ts             # TypeScript types matching API
```

## API Contract (Backend endpoints from Session E)

### POST `/api/ask`
```typescript
// Request
interface AskRequest {
  youtube_url: string;       // "https://www.youtube.com/watch?v=..."
  timestamp: number;         // Seconds (e.g., 930 for 15:30)
  question: string;          // "How does backpropagation work?"
}

// Response  
interface AskResponse {
  question: string;
  answer: string;            // Markdown-formatted educational answer
  video_id: string;
  sources: Array<{
    start_time: number;
    end_time: number;
    relevance_score: number;
  }>;
  quality_scores: {
    clarity: number;         // 1-5
    ect: number;             // 1-5
    upt: number;             // 1-5
  } | null;
  model_name: string;
  generation_time_seconds: number;
}
```

### GET `/api/health`
```typescript
interface HealthResponse {
  status: "ok" | "loading" | "error";
  model_loaded: boolean;
  gpu_available: boolean;
}
```

### POST `/api/process-video`
```typescript
// Request — pre-process a video (download + index) ahead of time
interface ProcessRequest {
  youtube_url: string;
}

// Response
interface ProcessResponse {
  video_id: string;
  title: string;
  duration: number;
  segment_count: number;
  status: "processed" | "already_cached";
}
```

## UI Requirements

### 1. Main Page Layout
```
┌─────────────────────────────────────────────┐
│  🎓 EduVidQA — AI Teaching Assistant        │
│  "Ask questions about any YouTube lecture"   │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─ Video Input ──────────────────────────┐ │
│  │ YouTube URL: [________________________]│ │
│  │ Timestamp:   [__:__] (or click slider) │ │
│  │ Question:    [________________________]│ │
│  │              [________________________]│ │
│  │                                        │ │
│  │         [ 🔍 Ask Question ]            │ │
│  └────────────────────────────────────────┘ │
│                                             │
│  ┌─ Answer ───────────────────────────────┐ │
│  │ 📝 AI Answer (rendered markdown)       │ │
│  │ ...                                    │ │
│  │                                        │ │
│  │ ┌── Quality Scores ─────────────────┐  │ │
│  │ │ Clarity: ████░ 4.2  ECT: ██░░░ 2.1│  │ │
│  │ │ UPT: ███░░ 3.5                    │  │ │
│  │ └───────────────────────────────────┘  │ │
│  │                                        │ │
│  │ 📎 Sources: 2:00-4:00 (92%), ...      │ │
│  │ ⚡ Generated in 8.3s using Qwen2.5-VL │ │
│  └────────────────────────────────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

### 2. Component Details

**VideoInput.tsx:**
- URL field with YouTube URL validation (regex)
- Timestamp: either type "MM:SS" or use a slider (if video duration is known after processing)
- Question: multi-line textarea, placeholder: "What concept from the lecture would you like explained?"
- "Ask Question" button with loading state
- Show video thumbnail (YouTube oEmbed API, no key needed: `https://img.youtube.com/vi/{VIDEO_ID}/hqdefault.jpg`)

**AnswerDisplay.tsx:**
- Render the answer as Markdown (use `react-markdown` + `remark-gfm`)
- Syntax highlighting for code blocks (if CS lectures)
- Smooth fade-in animation when answer loads

**QualityBadges.tsx:**
- 3 horizontal badges: Clarity, ECT, UPT
- Each shows: label + progress bar (filled proportional to score/5) + number
- Color coding: ≥4 = green, 3-4 = amber, <3 = red
- Tooltip on hover explaining what each metric means

**SourceTimestamps.tsx:**
- Show which video segments were used to generate the answer
- Format: "Sources: 2:00-4:00 (92% relevant), 8:00-10:00 (78% relevant)"
- Clickable — opens YouTube at that timestamp in a new tab: `https://youtube.com/watch?v={id}&t={seconds}`

**LoadingState.tsx:**
- Show when waiting for API response
- Animated steps: "📥 Downloading transcript..." → "🔍 Finding relevant sections..." → "🧠 Generating answer..."
- Estimated time: "This usually takes 10-30 seconds"

### 3. Design
- Dark theme (match the tracker/explainer sites we already built)
- Background: `#0a0e1a`, cards: `#111827`, accent: `#6366f1`
- TailwindCSS for styling
- Framer Motion for animations (fade in, slide up)
- Mobile responsive (Pixel 10 friendly)
- No authentication needed

## Dependencies (npm)
```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-markdown": "^9",
    "remark-gfm": "^4",
    "framer-motion": "^11",
    "@tanstack/react-query": "^5"
  },
  "devDependencies": {
    "vite": "^5",
    "@vitejs/plugin-react": "^4",
    "tailwindcss": "^3",
    "typescript": "^5",
    "autoprefixer": "^10",
    "postcss": "^8"
  }
}
```

## Test Criteria
1. `npm run dev` starts without errors
2. Can enter a URL + timestamp + question and see a loading state
3. Mock API response renders correctly (markdown, scores, sources)
4. Mobile responsive at 412px width (Pixel 10)
5. All quality badges render with correct colors
6. Source timestamps link to correct YouTube URL

## Important Notes
- Use environment variable `VITE_API_URL` for the backend URL (defaults to `http://localhost:8000` in dev)
- The backend will have CORS enabled for your Vercel domain
- You CAN scaffold the entire UI with mock data before the backend exists — use a mock API client that returns fake responses

---

## Worker Updates (Session D fills this in)

### Progress Log
<!-- Worker: Add your updates below this line -->

