// --- Request types ---

export interface AskRequest {
  youtube_url: string;
  question: string;
  timestamp: number;
  skip_quality_eval?: boolean;
}

export interface ProcessRequest {
  youtube_url: string;
}

// --- Response types ---

export interface AskResponse {
  answer: string;
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
  model_name: string;
  gpu_available: boolean;
}

export interface ProcessResponse {
  video_id: string;
  title: string;
  duration: number;
  segment_count: number;
  message: string;
}

// --- Chat types ---

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
  quality?: QualityScores;
  sources?: Source[];
  model_name?: string;
  generation_time_seconds?: number;
}

// --- YouTube IFrame API types ---

export interface YTPlayer {
  getCurrentTime(): number;
  getDuration(): number;
  seekTo(seconds: number, allowSeekAhead?: boolean): void;
  getPlayerState(): number;
  destroy(): void;
}

// --- Quiz types ---

export interface Checkpoint {
  id: string;
  timestamp_seconds: number;
  topic_label: string;
}

export interface QuizQuestion {
  id: string;
  question_text: string;
  options: string[];
  difficulty: 'easy' | 'medium' | 'hard';
  bloom_level?: 'remember' | 'understand' | 'apply' | 'analyse' | 'evaluate';
}

export interface AttemptResponse {
  is_correct: boolean;
  correct_answer: string;
  explanation: string;
  added_to_review: boolean;
}

export interface ReviewQuestion {
  id: string;
  video_id: string;
  video_title: string | null;
  question_text: string;
  options: string[];
  next_review_at: string;
  bloom_level?: 'remember' | 'understand' | 'apply' | 'analyse' | 'evaluate';
}

declare global {
  interface Window {
    YT: {
      Player: new (
        elementId: string,
        config: {
          videoId: string;
          playerVars?: Record<string, unknown>;
          events?: {
            onReady?: (event: { target: YTPlayer }) => void;
            onStateChange?: (event: { data: number }) => void;
          };
        },
      ) => YTPlayer;
      PlayerState: {
        PLAYING: number;
        PAUSED: number;
        ENDED: number;
      };
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}
