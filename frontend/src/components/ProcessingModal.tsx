import { useEffect, useState, useRef } from 'react';
import { getVideoStatus, getActivity, humanizeError, type VideoProgress, type ActivityEvent } from '../api/client';

const STEPS: { key: string; label: string }[] = [
  { key: 'starting', label: 'Fetching transcript' },
  { key: 'embedding', label: 'Creating embeddings (Gemini)' },
  { key: 'transcript_ready', label: 'Transcript indexed' },
  { key: 'download', label: 'Downloading video' },
  { key: 'keyframes', label: 'Extracting keyframes' },
  { key: 'digest', label: 'Summarising lecture' },
  { key: 'checkpoints', label: 'Placing checkpoints' },
  { key: 'quizzes', label: 'Organising chapters' },
  { key: 'ready', label: 'Ready to watch' },
];

interface Props {
  videoId: string;
  title?: string;
  onClose: () => void;
}

/** Live-polls a video's ingest progress so the user can see what's happening
 *  and whether it's stuck. */
export function ProcessingModal({ videoId, title, onClose }: Props) {
  const [status, setStatus] = useState<string>('processing');
  const [progress, setProgress] = useState<VideoProgress>({});
  const [detail, setDetail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastChangeRef = useRef<number>(Date.now());
  const lastKeyRef = useRef<string>('');
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const activitySeqRef = useRef<number>(0);

  // Poll the live API-activity feed so a "stuck" step is legible (which
  // provider is being called, whether it's rate-limited, how long it took).
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const { events } = await getActivity(activitySeqRef.current);
        if (cancelled || events.length === 0) return;
        activitySeqRef.current = events[events.length - 1].seq;
        setActivity((prev) => [...prev, ...events].slice(-20));
      } catch { /* ignore */ }
    };
    poll();
    const id = setInterval(poll, 1500);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const r = await getVideoStatus(videoId);
        if (cancelled) return;
        setStatus(r.status);
        setProgress(r.progress ?? {});
        setDetail(r.status_detail ?? r.progress?.detail ?? null);
        // Track when progress last actually changed (for stuck detection)
        const key = `${r.status}:${r.progress?.step ?? ''}:${r.progress?.detail ?? ''}`;
        if (key !== lastKeyRef.current) {
          lastKeyRef.current = key;
          lastChangeRef.current = Date.now();
        }
        setError(null);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to fetch status');
      }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(id); };
  }, [videoId]);

  const isDone = status === 'ready';
  const isFailed = status === 'failed';
  const pct = isDone ? 100 : Math.max(0, Math.min(100, progress.pct ?? 0));
  const currentStep = progress.step ?? (status === 'processing' ? 'starting' : status);
  const secsSinceChange = Math.floor((Date.now() - lastChangeRef.current) / 1000);
  const stuck = !isDone && !isFailed && secsSinceChange > 150;

  const activeIdx = STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Processing video</h3>
            {title && <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[20rem]">{title}</p>}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 dark:hover:text-white text-xl leading-none">✕</button>
        </div>

        {/* Progress bar */}
        <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden mb-2">
          <div
            className={`h-full rounded-full transition-all duration-500 ${isFailed ? 'bg-red-500' : 'bg-blue-600'}`}
            style={{ width: `${isFailed ? 100 : pct}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
          {isFailed ? 'Failed' : isDone ? 'Complete' : `${pct}%`} · {isFailed ? humanizeError(detail) : (detail ?? '…')}
        </p>

        {/* Step list */}
        <ol className="space-y-1.5 mb-4">
          {STEPS.map((s, i) => {
            const done = isDone || (activeIdx >= 0 && i < activeIdx);
            const active = i === activeIdx && !isDone;
            return (
              <li key={s.key} className="flex items-center gap-2 text-sm">
                <span className={
                  done ? 'text-emerald-500' : active ? 'text-blue-500' : 'text-gray-300 dark:text-gray-600'
                }>
                  {done ? '✓' : active ? '◐' : '○'}
                </span>
                <span className={
                  active ? 'text-gray-900 dark:text-white font-medium'
                    : done ? 'text-gray-500 dark:text-gray-400'
                    : 'text-gray-400 dark:text-gray-500'
                }>
                  {s.label}
                </span>
              </li>
            );
          })}
        </ol>

        {/* Live API-activity feed — shows which provider is being called so a
            "stuck" step is legible instead of a frozen bar. */}
        {activity.length > 0 && (
          <div className="mb-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-2">
            <p className="text-[11px] uppercase tracking-wide text-gray-400 mb-1">Live API activity</p>
            <div className="max-h-28 overflow-y-auto space-y-0.5 font-mono text-[11px]">
              {activity.slice().reverse().map((e) => {
                const icon = e.status === 'ok' ? '✅' : e.status === 'rate_limited' ? '⏳' : '❌';
                const color = e.status === 'ok'
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : e.status === 'rate_limited'
                  ? 'text-amber-600 dark:text-amber-400'
                  : 'text-red-600 dark:text-red-400';
                const t = new Date(e.ts * 1000).toLocaleTimeString();
                return (
                  <div key={e.seq} className={`flex items-center gap-1.5 ${color}`}>
                    <span>{icon}</span>
                    <span className="text-gray-400">{t}</span>
                    <span className="font-semibold">{e.provider}</span>
                    <span className="text-gray-500">{e.purpose}</span>
                    {e.status === 'rate_limited' && <span>rate-limited</span>}
                    {typeof e.ms === 'number' && e.status === 'ok' && (
                      <span className="text-gray-400">{(e.ms / 1000).toFixed(1)}s</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {isFailed && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300">
            ⚠️ {humanizeError(detail)}
          </div>
        )}
        {stuck && (
          <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-3 text-sm text-amber-700 dark:text-amber-300">
            ⏳ No update for {secsSinceChange}s — this step may be slow (large video / rate-limited API) or stuck. You can keep this open or check back later.
          </div>
        )}
        {isDone && (
          <div className="rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 p-3 text-sm text-emerald-700 dark:text-emerald-300">
            ✅ Done — you can open the video now.
          </div>
        )}
        {error && !isFailed && (
          <p className="text-xs text-gray-400 mt-2">Status check error: {error} (retrying…)</p>
        )}
      </div>
    </div>
  );
}
