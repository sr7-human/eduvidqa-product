import type {
  AskRequest,
  AskResponse,
  AttemptResponse,
  Chapter,
  Checkpoint,
  HealthResponse,
  ProcessRequest,
  ProcessResponse,
  QualityScores,
  QuizQuestion,
  QuizSchedule,
  QuizType,
  ReviewQuestion,
  Source,
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
  // Guard: HF Spaces returns HTML when sleeping/waking
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('text/html')) {
    throw new Error(
      'Backend is waking up — please wait ~30 seconds and try again.',
    );
  }
  if (!res.ok) {
    const body = await res.text();
    // FastAPI returns {"detail": "..."} — surface that as the error message.
    let msg = body;
    try {
      const parsed = JSON.parse(body);
      if (parsed && typeof parsed.detail === 'string') msg = parsed.detail;
    } catch { /* not JSON, keep raw */ }
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
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

// ── Streaming ask ─────────────────────────────────────────────────

export interface StreamCallbacks {
  /** Sources from retrieval, sent before any tokens. */
  onSources?: (sources: Source[]) => void;
  /** A new text fragment from the LLM. Append to the current bubble. */
  onToken: (text: string) => void;
  /** Progress status update (e.g. "Retrieving context…"). */
  onStatus?: (text: string) => void;
  /** Final event with model name, total time, and (optional) quality scores. */
  onDone: (meta: {
    model_name: string;
    generation_time_seconds: number;
    quality_scores: QualityScores | null;
  }) => void;
  /** Server-reported error (after stream began). */
  onError?: (err: Error) => void;
}

/**
 * Streaming counterpart of {@link askQuestion}. Reads Server-Sent Events
 * from `/api/ask/stream` and invokes the supplied callbacks as data arrives.
 *
 * Throws `VideoProcessingError` if the backend returns 202 (video still
 * being indexed) or `Error` for other non-OK statuses BEFORE the stream
 * begins. Once streaming has started, errors are reported via `onError`.
 */
export async function askQuestionStream(
  req: AskRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  if (USE_MOCK) {
    // Simulate token-by-token typing on the mock answer
    const mock = await mockAsk(req);
    callbacks.onSources?.(mock.sources);
    const words = mock.answer.split(/(\s+)/);
    for (const w of words) {
      if (signal?.aborted) return;
      await new Promise((r) => setTimeout(r, 20));
      callbacks.onToken(w);
    }
    callbacks.onDone({
      model_name: mock.model_name,
      generation_time_seconds: mock.generation_time_seconds,
      quality_scores: mock.quality_scores,
    });
    return;
  }

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
    Accept: 'text/event-stream',
    ...(geminiKey ? { 'X-Gemini-Key': geminiKey } : {}),
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };

  const res = await fetch(`${API_URL}/api/ask/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
    signal,
  });

  if (res.status === 202) {
    const body = await res.json().catch(() => ({}));
    throw new VideoProcessingError(
      extractVideoId(req.youtube_url),
      body?.detail ?? 'Video is being processed. Try again shortly.',
    );
  }
  if (!res.ok || !res.body) {
    const body = await res.text();
    let msg = body;
    try {
      const parsed = JSON.parse(body);
      if (parsed && typeof parsed.detail === 'string') msg = parsed.detail;
    } catch { /* not JSON */ }
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }

  // Guard: HF Spaces returns HTML when sleeping/waking — detect and throw
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('text/html')) {
    throw new Error(
      'Backend is waking up — please wait ~30 seconds and try again.',
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // SSE parser: events are separated by a blank line (\n\n). Each event has
  // one or more "data:" lines whose payloads are concatenated with newlines.
  const dispatch = (rawEvent: string) => {
    const dataLines = rawEvent
      .split('\n')
      .filter((l) => l.startsWith('data:'))
      .map((l) => l.slice(5).replace(/^ /, ''));
    if (dataLines.length === 0) return;
    const data = dataLines.join('\n');
    let parsed: { type?: string; [k: string]: unknown };
    try {
      parsed = JSON.parse(data);
    } catch {
      return;
    }
    switch (parsed.type) {
      case 'sources':
        callbacks.onSources?.((parsed.sources as Source[]) ?? []);
        break;
      case 'status':
        callbacks.onStatus?.((parsed.text as string) ?? '');
        break;
      case 'token':
        callbacks.onToken((parsed.text as string) ?? '');
        break;
      case 'done':
        callbacks.onDone({
          model_name: (parsed.model_name as string) ?? 'unknown',
          generation_time_seconds: (parsed.generation_time_seconds as number) ?? 0,
          quality_scores: (parsed.quality_scores as QualityScores | null) ?? null,
        });
        break;
      case 'error':
        callbacks.onError?.(new Error((parsed.detail as string) ?? 'Stream error'));
        break;
      default:
        /* ignore unknown event types — forward-compatible */
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Split on blank line — SSE event boundary
      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const evt = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        if (evt.trim()) dispatch(evt);
      }
    }
    // Flush any remaining buffered event (shouldn't normally happen)
    if (buffer.trim()) dispatch(buffer);
  } finally {
    try {
      reader.releaseLock();
    } catch { /* ignore */ }
  }
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

export interface VideoPreview {
  video_id: string;
  title: string;
  duration_seconds: number;
  estimated_chapters: number;
  has_youtube_chapters: boolean;
}

export async function getVideoPreview(youtubeUrl: string): Promise<VideoPreview> {
  const params = new URLSearchParams({ youtube_url: youtubeUrl });
  return request<VideoPreview>(`/api/video-preview?${params.toString()}`);
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

export async function removeVideo(
  videoId: string,
): Promise<{ video_id: string; removed: boolean }> {
  return request(`/api/users/me/videos/${videoId}`, { method: 'DELETE' });
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

export async function getChapters(videoId: string): Promise<Chapter[]> {
  return request<Chapter[]>(`/api/videos/${videoId}/chapters`);
}

export async function getQuizSchedule(videoId: string): Promise<QuizSchedule> {
  return request<QuizSchedule>(`/api/videos/${videoId}/quiz-schedule`);
}

export async function getChapterQuiz(
  videoId: string,
  chapterId: string,
  quizType: QuizType,
): Promise<{ questions: QuizQuestion[] }> {
  const params = new URLSearchParams({ chapter_id: chapterId, quiz_type: quizType });
  return request<{ questions: QuizQuestion[] }>(
    `/api/videos/${videoId}/chapter-quiz?${params.toString()}`,
  );
}

export type QuizPref = 'use_video_default' | 'always_pause' | 'never_pause';

export async function getQuizPref(): Promise<{ pref: QuizPref }> {
  return request<{ pref: QuizPref }>('/api/users/me/quiz-pref');
}

export async function setQuizPref(pref: QuizPref): Promise<{ pref: QuizPref }> {
  return request<{ pref: QuizPref }>('/api/users/me/quiz-pref', {
    method: 'PUT',
    body: JSON.stringify({ pref }),
  });
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

// ── User API keys (BYOK) ─────────────────────────────────────────

export interface StoredKey {
  service: 'gemini' | 'groq';
  masked: string;
  updated_at: string;
}

export async function listMyKeys(): Promise<{ keys: StoredKey[] }> {
  return request<{ keys: StoredKey[] }>(`/api/users/me/keys`);
}

export async function saveMyKey(
  service: 'gemini' | 'groq',
  keyValue: string,
): Promise<{ service: string; masked: string; ok: boolean }> {
  return request(`/api/users/me/keys`, {
    method: 'POST',
    body: JSON.stringify({ service, key_value: keyValue }),
  });
}

export async function deleteMyKey(
  service: 'gemini' | 'groq',
): Promise<{ service: string; deleted: boolean }> {
  return request(`/api/users/me/keys/${service}`, { method: 'DELETE' });
}

// ── Identity / admin ─────────────────────────────────────────────

export interface WhoAmI {
  authenticated: boolean;
  is_admin: boolean;
  email: string | null;
  user_id?: string;
}

export async function whoami(): Promise<WhoAmI> {
  return request<WhoAmI>(`/api/users/me/whoami`);
}

export async function adminRegenerateQuiz(
  videoId: string,
): Promise<{ video_id: string; checkpoints: number; questions_generated: number; message: string }> {
  return request(`/api/admin/videos/${videoId}/quiz/regenerate`, { method: 'POST' });
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
