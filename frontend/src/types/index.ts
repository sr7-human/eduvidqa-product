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
  generation_time: number;
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

// --- Chat types ---

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
  quality?: QualityScores;
  sources?: Source[];
  model_name?: string;
  generation_time?: number;
}

// --- YouTube IFrame API types ---

export interface YTPlayer {
  getCurrentTime(): number;
  seekTo(seconds: number, allowSeekAhead?: boolean): void;
  getPlayerState(): number;
  destroy(): void;
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
