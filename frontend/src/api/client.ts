import type { AskRequest, AskResponse, HealthResponse, ProcessRequest, ProcessResponse } from '../types';

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
  generation_time: 2.3,
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
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

export async function askQuestion(req: AskRequest): Promise<AskResponse> {
  if (USE_MOCK) return mockAsk(req);
  return await request<AskResponse>('/api/ask', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function checkHealth(): Promise<HealthResponse> {
  if (USE_MOCK) return { status: 'ok', model_loaded: true, gpu_available: false };
  try {
    return await request<HealthResponse>('/api/health');
  } catch {
    return { status: 'error', model_loaded: false, gpu_available: false };
  }
}

export async function processVideo(req: ProcessRequest): Promise<ProcessResponse> {
  return request<ProcessResponse>('/api/process-video', {
    method: 'POST',
    body: JSON.stringify(req),
  });
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
