import { useState, useCallback, useRef, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import YouTubePlayer from '../components/YouTubePlayer';
import TimestampDisplay from '../components/TimestampDisplay';
import ChatInterface from '../components/ChatInterface';
import {
  askQuestion,
  getCheckpoints,
  getQuiz,
  getVideoStatus,
  VideoProcessingError,
} from '../api/client';
import type { ChatMessage, Checkpoint, QuizQuestion, YTPlayer } from '../types';
import { CheckpointMarkers } from '../components/CheckpointMarkers';
import { TestMeButton } from '../components/TestMeButton';
import { QuizPanel } from '../components/QuizPanel';
import { usePauseDetector } from '../hooks/usePauseDetector';

export function Watch() {
  const { videoId: paramVideoId } = useParams<{ videoId: string }>();
  const videoId = paramVideoId ?? '3OmfTIf-SOU';
  const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;

  // Timestamp state
  const [currentTime, setCurrentTime] = useState(0);
  const [frozenTime, setFrozenTime] = useState(0);
  const [autoMode, setAutoMode] = useState(true);
  const playerRef = useRef<YTPlayer | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [, setPlayerReady] = useState(false);

  // Processing state (when /api/ask returns 202)
  const [processingStatus, setProcessingStatus] = useState<string | null>(null);

  // Quiz state
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [videoDuration, setVideoDuration] = useState(0);
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[] | null>(null);
  const [showQuiz, setShowQuiz] = useState(false);
  const [playerState, setPlayerState] = useState<'playing' | 'paused' | 'other'>('other');

  const effectiveTimestamp = autoMode ? currentTime : frozenTime;

  const handleTimeUpdate = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handlePlayerReady = useCallback(() => {
    setPlayerReady(true);
  }, []);

  const handlePlayerRef = useCallback((player: YTPlayer) => {
    playerRef.current = player;
    // Capture duration once the player is available
    const tryDuration = () => {
      const d = player.getDuration?.() ?? 0;
      if (d > 0) setVideoDuration(d);
      else setTimeout(tryDuration, 500);
    };
    tryDuration();
  }, []);

  const handleQuizReady = useCallback((questions: QuizQuestion[]) => {
    setQuizQuestions(questions);
    setShowQuiz(true);
  }, []);

  const handlePlayerStateChange = useCallback((state: number) => {
    // YT.PlayerState: PLAYING=1, PAUSED=2
    if (state === 1) setPlayerState('playing');
    else if (state === 2) setPlayerState('paused');
    else setPlayerState('other');
  }, []);

  // Pause-near-checkpoint toast suggesting a quiz
  usePauseDetector(playerState, currentTime, checkpoints, (cp) => {
    toast(
      (t) => (
        <div className="flex items-center gap-3">
          <span className="text-sm">
            📚 Test yourself on “{cp.topic_label}”?
          </span>
          <button
            className="px-3 py-1 bg-blue-600 text-white rounded text-sm whitespace-nowrap"
            onClick={async () => {
              toast.dismiss(t.id);
              try {
                const { questions } = await getQuiz(
                  videoId,
                  Math.floor(cp.timestamp_seconds),
                );
                handleQuizReady(questions);
              } catch (err) {
                console.error('Quiz generation failed:', err);
              }
            }}
          >
            Take quiz
          </button>
          <button
            className="text-gray-400 text-sm"
            onClick={() => toast.dismiss(t.id)}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      ),
      { duration: 8000, position: 'bottom-center' },
    );
  });

  const handleQuizClose = useCallback(() => {
    setShowQuiz(false);
    setQuizQuestions(null);
  }, []);

  const handleCheckpointClick = useCallback((cp: Checkpoint) => {
    if (playerRef.current) {
      playerRef.current.seekTo(cp.timestamp_seconds, true);
    }
    setCurrentTime(cp.timestamp_seconds);
  }, []);

  function handleFreeze() {
    setFrozenTime(currentTime);
    setAutoMode(false);
  }

  function handleManualSet(seconds: number) {
    setFrozenTime(seconds);
    setAutoMode(false);
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
    const now = playerRef.current?.getCurrentTime?.() ?? currentTime;
    setFrozenTime(now);
    setCurrentTime(now);
    setAutoMode(false);
  }

  // Fetch checkpoints on mount / when videoId changes
  useEffect(() => {
    if (videoId) {
      getCheckpoints(videoId)
        .then(setCheckpoints)
        .catch(() => {
          /* no checkpoints available */
        });
    }
  }, [videoId]);

  // Poll video status while processing
  useEffect(() => {
    if (!processingStatus || processingStatus === 'ready') return;
    const interval = setInterval(async () => {
      try {
        const { status } = await getVideoStatus(videoId);
        if (status !== 'processing') {
          setProcessingStatus(status);
          if (status === 'ready') {
            toast.success('Video ready! You can now ask questions.');
          } else if (status === 'failed') {
            toast.error('Video processing failed.');
          }
        }
      } catch {
        /* ignore */
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [processingStatus, videoId]);

  async function handleSend(question: string) {
    const ts = effectiveTimestamp;
    const userMsg: ChatMessage = {
      role: 'user',
      content: question,
      timestamp: ts,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await askQuestion({
        youtube_url: youtubeUrl,
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
        generation_time_seconds: res.generation_time_seconds,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      if (err instanceof VideoProcessingError) {
        setProcessingStatus('processing');
        toast(
          'Video is being processed in the background. Please retry in a minute.',
          { icon: '⏳' },
        );
        const noticeMsg: ChatMessage = {
          role: 'assistant',
          content:
            '⏳ This video is still being ingested. We are processing it now — please try again shortly.',
        };
        setMessages((prev) => [...prev, noticeMsg]);
      } else {
        const errorMsg: ChatMessage = {
          role: 'assistant',
          content: `**Error:** ${err instanceof Error ? err.message : 'Failed to get response'}`,
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    } finally {
      setIsLoading(false);
      setAutoMode(true);
    }
  }

  return (
    <div className="flex flex-col h-screen">
      <Navbar />

      {/* Breadcrumb */}
      <div className="bg-white border-b border-gray-200 px-6 py-2 text-sm">
        <Link to="/library" className="text-blue-600 hover:underline">
          ← Back to Library
        </Link>
        {processingStatus === 'processing' && (
          <span className="ml-4 text-yellow-700">
            ⏳ Video is being processed...
          </span>
        )}
      </div>

      <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
        {/* Left panel — Video (60%) */}
        <div className="w-full md:w-[60%] flex flex-col border-b md:border-b-0 md:border-r border-dark-border overflow-y-auto">
          <div className="p-4 space-y-3">
            <YouTubePlayer
              videoId={videoId}
              onTimeUpdate={handleTimeUpdate}
              onReady={handlePlayerReady}
              onSeek={handlePlayerRef}
              onStateChange={handlePlayerStateChange}
            />

            <CheckpointMarkers
              checkpoints={checkpoints}
              videoDuration={videoDuration}
              onCheckpointClick={handleCheckpointClick}
            />

            <div className="flex justify-end">
              <TestMeButton
                videoId={videoId}
                currentTimestamp={Math.floor(effectiveTimestamp)}
                onQuizReady={handleQuizReady}
              />
            </div>

            <TimestampDisplay
              currentTime={effectiveTimestamp}
              autoMode={autoMode}
              onFreeze={handleFreeze}
              onManualSet={handleManualSet}
              onResetAuto={handleResetAuto}
            />

            <div className="bg-dark-card border border-dark-border rounded-lg p-3 text-center text-xs text-gray-500">
              🖼️ Frame at {Math.floor(effectiveTimestamp)}s will be shown here
            </div>
          </div>
        </div>

        {/* Right panel — Chat or Quiz (40%) */}
        <div className="w-full md:w-[40%] flex flex-col min-h-0 h-[50vh] md:h-auto">
          {showQuiz && quizQuestions ? (
            <QuizPanel questions={quizQuestions} onClose={handleQuizClose} />
          ) : (
            <ChatInterface
              messages={messages}
              isLoading={isLoading}
              timestamp={effectiveTimestamp}
              autoMode={autoMode}
              onSend={handleSend}
              onSeek={handleSeek}
              onInputFocus={handleInputFocus}
            />
          )}
        </div>
      </div>
    </div>
  );
}
