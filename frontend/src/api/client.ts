import type {
  AskRequest,
  AskResponse,
  AttemptResponse,
  Checkpoint,
  HealthResponse,
  ProcessRequest,
  ProcessResponse,
  QuizQuestion,
  ReviewQuestion,
} from '../types';
import { getGeminiKey } from '../components/SettingsModal';
import { supabase } from '../lib/supabase';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const USE_MOCK = import.meta.env.VITE_MOCK_API === 'true';

const MOCK_DELAY = 2000;

const MOCK_RESPONSE: AskResponse = {
  answer: `## Unit Testing Explained

The professor is explaining unit testing with the \`get_route_score\` function. Here's the breakdown:

### What is Unit Testing?
Unit testing is the practice of testing **individual functions or methods** in isolation to verify they produce the correct output for given inputs.

### The \`get_route_score\` Example
\`\`\`python
def get_route_score(route):
    score = 0
    for segment in route:
        score += segment.distance * segment.difficulty
    return score
\`\`\`

Key points:
- Each test case provides a **known input** and checks for an **expected output**
- Tests should cover **edge cases**: empty routes, single segments, very long routes
- The professor emphasizes that **code coverage** measures what percentage of your code is executed by tests

> ⚠️ High code coverage doesn't guarantee correctness — you also need meaningful assertions.`,
  sources: [
    { start_time: 120, end_time: 140, relevance_score: 0.92 },
    { start_time: 200, end_time: 230, relevance_score: 0.78 },
  ],
  quality_scores: {
    clarity: 4.2,
    ect: 3.8,
    upt: 4.0,
  },
  model_name: 'llama-4-scout-17b',
  generation_time_seconds: 2.3,
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const geminiKey = getGeminiKey();

  // Get Supabase JWT (if user is signed in)
  let authToken = '';
  try {
    const { data: { session } } = await supabase.auth.getSession();
    authToken = session?.access_token ?? '';
  } catch {
    /* no auth available */
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(geminiKey ? { 'X-Gemini-Key': geminiKey } : {}),
    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}),
    ...(options?.headers as Record<string, string> ?? {}),
  };
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

async function mockAsk(req: AskRequest): Promise<AskResponse> {
  console.info('[mock] Returning mock response for:', req.question);
  await new Promise((r) => setTimeout(r, MOCK_DELAY));
  return { ...MOCK_RESPONSE };
}

export class VideoProcessingError extends Error {
  constructor(public videoId: string | null, message: string) {
    super(message);
    this.name = 'VideoProcessingError';
  }
}

export async function askQuestion(req: AskRequest): Promise<AskResponse> {
  if (USE_MOCK) return mockAsk(req);

  const geminiKey = getGeminiKey();
  let authToken = '';
  try {
    const { data: { session } } = await supabase.auth.getSession();
    authToken = session?.access_token ?? '';
  } catch {
    /* no auth available */
  }
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(geminiKey ? { 'X-Gemini-Key': geminiKey } : {}),
    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}),
  };
  const res = await fetch(`${API_URL}/api/ask`, {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
  });
  if (res.status === 202) {
    const body = await res.json().catch(() => ({}));
    throw new VideoProcessingError(
      extractVideoId(req.youtube_url),
      body?.detail ?? 'Video is being processed. Try again shortly.',
    );
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<AskResponse>;
}

export async function checkHealth(): Promise<HealthResponse> {
  if (USE_MOCK) return { status: 'ok', model_loaded: true, model_name: 'mock', gpu_available: false };
  try {
    return await request<HealthResponse>('/api/health');
  } catch {
    return { status: 'error', model_loaded: false, model_name: '', gpu_available: false };
  }
}

export async function processVideo(req: ProcessRequest): Promise<ProcessResponse> {
  return request<ProcessResponse>('/api/process-video', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export interface UserVideo {
  video_id: string;
  status: string;
  title?: string | null;
  [key: string]: unknown;
}

export async function getMyVideos(): Promise<UserVideo[]> {
  return request<UserVideo[]>('/api/users/me/videos');
}

export async function getVideoStatus(
  videoId: string,
): Promise<{ video_id: string; status: string }> {
  return request<{ video_id: string; status: string }>(
    `/api/videos/${videoId}/status`,
  );
}

export async function getCheckpoints(videoId: string): Promise<Checkpoint[]> {
  return request<Checkpoint[]>(`/api/videos/${videoId}/checkpoints`);
}

export async function getQuiz(
  videoId: string,
  endTs: number,
  count = 10,
): Promise<{ questions: QuizQuestion[] }> {
  return request<{ questions: QuizQuestion[] }>(
    `/api/videos/${videoId}/quiz`,
    {
      method: 'POST',
      body: JSON.stringify({ end_ts: endTs, count }),
    },
  );
}

export async function submitAttempt(
  questionId: string,
  selectedAnswer: string,
): Promise<AttemptResponse> {
  return request<AttemptResponse>(
    `/api/quizzes/${questionId}/attempt`,
    {
      method: 'POST',
      body: JSON.stringify({ selected_answer: selectedAnswer }),
    },
  );
}

export async function getReviewQueue(): Promise<{
  due_count: number;
  questions: ReviewQuestion[];
}> {
  return request<{ due_count: number; questions: ReviewQuestion[] }>(
    '/api/users/me/review',
  );
}

export async function submitReviewAttempt(
  questionId: string,
  selectedAnswer: string,
): Promise<{ is_correct: boolean; correct_answer: string; explanation: string }> {
  return request<{ is_correct: boolean; correct_answer: string; explanation: string }>(
    `/api/review/${questionId}/attempt`,
    {
      method: 'POST',
      body: JSON.stringify({ selected_answer: selectedAnswer }),
    },
  );
}

export function extractVideoId(url: string): string | null {
  const patterns = [
    /(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
    /(?:youtu\.be\/)([a-zA-Z0-9_-]{11})/,
    /(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return null;
}
