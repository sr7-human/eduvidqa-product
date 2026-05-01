import { useEffect, useRef, useCallback } from 'react';
import type { YTPlayer } from '../types';

interface Props {
  videoId: string;
  onTimeUpdate: (time: number) => void;
  onReady: () => void;
  onSeek?: (player: YTPlayer) => void;
  onStateChange?: (state: number) => void;
}

let apiLoaded = false;
let apiReady = false;
const readyCallbacks: (() => void)[] = [];

function loadYouTubeAPI(): Promise<void> {
  if (apiReady) return Promise.resolve();
  return new Promise((resolve) => {
    readyCallbacks.push(resolve);
    if (apiLoaded) return;
    apiLoaded = true;
    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(tag);
    window.onYouTubeIframeAPIReady = () => {
      apiReady = true;
      readyCallbacks.forEach((cb) => cb());
      readyCallbacks.length = 0;
    };
  });
}

export default function YouTubePlayer({ videoId, onTimeUpdate, onReady, onSeek, onStateChange }: Props) {
  const playerRef = useRef<YTPlayer | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Store callbacks in refs so they don't trigger re-creation of the player
  const onTimeUpdateRef = useRef(onTimeUpdate);
  const onReadyRef = useRef(onReady);
  const onSeekRef = useRef(onSeek);
  const onStateChangeRef = useRef(onStateChange);
  onTimeUpdateRef.current = onTimeUpdate;
  onReadyRef.current = onReady;
  onSeekRef.current = onSeek;
  onStateChangeRef.current = onStateChange;

  const startPolling = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      if (playerRef.current?.getCurrentTime) {
        onTimeUpdateRef.current(playerRef.current.getCurrentTime());
      }
    }, 500);
  }, []);

  useEffect(() => {
    let destroyed = false;

    loadYouTubeAPI().then(() => {
      if (destroyed || !containerRef.current) return;

      // Clear container and create a fresh div for the player
      const el = document.createElement('div');
      el.id = 'yt-player-target';
      containerRef.current.innerHTML = '';
      containerRef.current.appendChild(el);

      playerRef.current = new window.YT.Player('yt-player-target', {
        videoId,
        playerVars: {
          autoplay: 0,
          modestbranding: 1,
          rel: 0,
        },
        events: {
          onReady: (event) => {
            onReadyRef.current();
            if (onSeekRef.current) onSeekRef.current(event.target);
            startPolling();
          },
          onStateChange: (event) => {
            onStateChangeRef.current?.(event.data);
          },
        },
      });
    });

    return () => {
      destroyed = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (playerRef.current?.destroy) {
        try { playerRef.current.destroy(); } catch { /* ignore */ }
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]); // Only re-create player when videoId changes

  return (
    <div className="w-full">
      <div
        ref={containerRef}
        className="aspect-video w-full rounded-xl overflow-hidden bg-dark-card border border-dark-border [&>iframe]:w-full [&>iframe]:h-full"
      />
    </div>
  );
}
