import type { Source } from '../types';

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

interface Props {
  videoId: string;
  sources: Source[];
}

export default function SourceTimestamps({ videoId, sources }: Props) {
  if (sources.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-gray-400 flex items-center gap-1.5">
        📎 Sources
      </p>
      <div className="flex flex-wrap gap-2">
        {sources.map((src, i) => (
          <a
            key={i}
            href={`https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}&t=${Math.floor(src.start_time)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 bg-dark-bg border border-dark-border hover:border-accent/50 rounded-lg px-3 py-1.5 text-sm transition-colors group"
          >
            <span className="text-gray-300 group-hover:text-accent transition-colors">
              {formatTime(src.start_time)}–{formatTime(src.end_time)}
            </span>
            <span className="text-gray-500 text-xs">
              ({Math.round(src.relevance_score * 100)}%)
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}
