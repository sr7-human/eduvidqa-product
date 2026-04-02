import { useState, useCallback, useRef } from 'react';
import Header from './components/Header';
import YouTubePlayer from './components/YouTubePlayer';
import TimestampDisplay from './components/TimestampDisplay';
import ChatInterface from './components/ChatInterface';
import { askQuestion, extractVideoId } from './api/client';
import type { ChatMessage, YTPlayer } from './types';

const DEFAULT_VIDEO_URL = 'https://www.youtube.com/watch?v=3OmfTIf-SOU';

export default function App() {
  const [videoUrl, setVideoUrl] = useState(DEFAULT_VIDEO_URL);
  const [urlInput, setUrlInput] = useState(DEFAULT_VIDEO_URL);

  const videoId = extractVideoId(videoUrl) ?? '3OmfTIf-SOU';

  // Timestamp state
  const [currentTime, setCurrentTime] = useState(0);
  const [frozenTime, setFrozenTime] = useState(0);
  const [autoMode, setAutoMode] = useState(true);
  const playerRef = useRef<YTPlayer | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [playerReady, setPlayerReady] = useState(false);

  const effectiveTimestamp = autoMode ? currentTime : frozenTime;

  const handleTimeUpdate = useCallback(
    (time: number) => {
      // Always track the player's current time
      setCurrentTime(time);
    },
    [],
  );

  const handlePlayerReady = useCallback(() => {
    setPlayerReady(true);
  }, []);

  const handlePlayerRef = useCallback((player: YTPlayer) => {
    playerRef.current = player;
  }, []);

  function handleFreeze() {
    setFrozenTime(currentTime);
    setAutoMode(false);
  }

  function handleManualSet(seconds: number) {
    setFrozenTime(seconds);
    setAutoMode(false);
    // Also seek the video
    if (playerRef.current) {
      playerRef.current.seekTo(seconds, true);
    }
  }

  function handleResetAuto() {
    setAutoMode(true);
  }

  function handleSeek(seconds: number) {
    if (playerRef.current) {
      playerRef.current.seekTo(seconds, true);
    }
    setCurrentTime(seconds);
  }

  function handleInputFocus() {
    // Always capture the CURRENT player time when input is focused
    // Even if already frozen, the user may have seeked to a new position
    const now = playerRef.current?.getCurrentTime?.() ?? currentTime;
    setFrozenTime(now);
    setCurrentTime(now);
    setAutoMode(false);
  }

  async function handleSend(question: string) {
    const ts = effectiveTimestamp;

    // Add user message
    const userMsg: ChatMessage = {
      role: 'user',
      content: question,
      timestamp: ts,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await askQuestion({
        youtube_url: videoUrl,
        question,
        timestamp: Math.floor(ts),
        skip_quality_eval: false,
      });

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: res.answer,
        quality: res.quality_scores ?? undefined,
        sources: res.sources,
        model_name: res.model_name,
        generation_time: res.generation_time,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        role: 'assistant',
        content: `**Error:** ${err instanceof Error ? err.message : 'Failed to get response'}`,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setAutoMode(true); // reset to auto after submit
    }
  }

  function handleLoadVideo(e: React.FormEvent) {
    e.preventDefault();
    if (extractVideoId(urlInput)) {
      setVideoUrl(urlInput);
      setMessages([]);
      setCurrentTime(0);
      setAutoMode(true);
      setPlayerReady(false);
    }
  }

  return (
    <div className="flex flex-col h-screen">
      <Header />

      <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
        {/* Left panel — Video (60%) */}
        <div className="w-full md:w-[60%] flex flex-col border-b md:border-b-0 md:border-r border-dark-border overflow-y-auto">
          <div className="p-4 space-y-3">
            {/* URL input */}
            <form onSubmit={handleLoadVideo} className="flex gap-2">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="YouTube URL..."
                className="flex-1 bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent transition"
              />
              <button
                type="submit"
                className="bg-accent hover:bg-accent-hover text-white text-sm px-4 py-2 rounded-lg transition-colors shrink-0"
              >
                Load
              </button>
            </form>

            {/* YouTube player */}
            <YouTubePlayer
              videoId={videoId}
              onTimeUpdate={handleTimeUpdate}
              onReady={handlePlayerReady}
              onSeek={handlePlayerRef}
            />

            {/* Timestamp display — always show */}
            <TimestampDisplay
              currentTime={effectiveTimestamp}
              autoMode={autoMode}
              onFreeze={handleFreeze}
              onManualSet={handleManualSet}
              onResetAuto={handleResetAuto}
            />

            {/* Frame preview placeholder */}
            <div className="bg-dark-card border border-dark-border rounded-lg p-3 text-center text-xs text-gray-500">
              🖼️ Frame at {Math.floor(effectiveTimestamp)}s will be shown here
            </div>
          </div>
        </div>

        {/* Right panel — Chat (40%) */}
        <div className="w-full md:w-[40%] flex flex-col min-h-0 h-[50vh] md:h-auto">
          <ChatInterface
            messages={messages}
            isLoading={isLoading}
            timestamp={effectiveTimestamp}
            autoMode={autoMode}
            onSend={handleSend}
            onSeek={handleSeek}
            onInputFocus={handleInputFocus}
          />
        </div>
      </div>
    </div>
  );
}
