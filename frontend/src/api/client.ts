import type { AskRequest, AskResponse, HealthResponse, ProcessRequest, ProcessResponse } from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? '';

const MOCK_DELAY = 3000;

const MOCK_RESPONSE: AskResponse = {
  question: 'How does backpropagation work?',
  answer: `## Backpropagation Explained

Backpropagation is the **core algorithm** for training neural networks. It works in two phases:

### 1. Forward Pass
The input flows through the network layer by layer. Each neuron applies:
- A **weighted sum** of its inputs
- An **activation function** (e.g., ReLU, sigmoid)

### 2. Backward Pass
The error (loss) is propagated backward using the **chain rule** of calculus:

\`\`\`
∂L/∂w = ∂L/∂a · ∂a/∂z · ∂z/∂w
\`\`\`

Where:
- \`L\` = loss function
- \`a\` = activation output  
- \`z\` = weighted sum (pre-activation)
- \`w\` = weight

### Key Insight
Each weight is updated proportional to how much it contributed to the error:

\`\`\`
w_new = w_old - learning_rate × ∂L/∂w
\`\`\`

> The professor emphasizes at **15:30** that backpropagation is essentially just repeated application of the chain rule — nothing magical about it.`,
  video_id: 'dQw4w9WgXcQ',
  sources: [
    { start_time: 120, end_time: 240, relevance_score: 0.92 },
    { start_time: 480, end_time: 600, relevance_score: 0.78 },
    { start_time: 900, end_time: 960, relevance_score: 0.65 },
  ],
  quality_scores: {
    clarity: 4.2,
    ect: 3.1,
    upt: 3.8,
  },
  model_name: 'Qwen2.5-VL-7B',
  generation_time_seconds: 8.3,
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function askQuestion(req: AskRequest): Promise<AskResponse> {
  try {
    return await request<AskResponse>('/api/ask', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  } catch {
    // Fallback to mock when backend is unavailable
    console.warn('Backend unavailable — returning mock response');
    await new Promise((r) => setTimeout(r, MOCK_DELAY));
    return { ...MOCK_RESPONSE, question: req.question };
  }
}

export async function checkHealth(): Promise<HealthResponse> {
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
