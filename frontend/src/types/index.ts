// --- Request types ---

export interface AskRequest {
  youtube_url: string;
  timestamp: number;
  question: string;
}

export interface ProcessRequest {
  youtube_url: string;
}

// --- Response types ---

export interface AskResponse {
  question: string;
  answer: string;
  video_id: string;
  sources: Source[];
  quality_scores: QualityScores | null;
  model_name: string;
  generation_time_seconds: number;
}

export interface Source {
  start_time: number;
  end_time: number;
  relevance_score: number;
}

export interface QualityScores {
  clarity: number;
  ect: number;
  upt: number;
}

export interface HealthResponse {
  status: 'ok' | 'loading' | 'error';
  model_loaded: boolean;
  gpu_available: boolean;
}

export interface ProcessResponse {
  video_id: string;
  title: string;
  duration: number;
  segment_count: number;
  status: 'processed' | 'already_cached';
}
