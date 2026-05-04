import { useState, useCallback, useRef, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import YouTubePlayer from '../components/YouTubePlayer';
import TimestampDisplay from '../components/TimestampDisplay';
import ChatInterface from '../components/ChatInterface';
import {
  askQuestionStream,
  getCheckpoints,
  getQuiz,
  getQuizSchedule,
  getVideoStatus,
  whoami,
  adminRegenerateQuiz,
  VideoProcessingError,
} from '../api/client';
import type { ChatMessage, Checkpoint, QuizQuestion, QuizScheduleEvent, QuizSchedule, YTPlayer } from '../types';
import { CheckpointMarkers } from '../components/CheckpointMarkers';
import { TestMeButton } from '../components/TestMeButton';
import { QuizPanel } from '../components/QuizPanel';
import { ChapterQuizModal } from '../components/ChapterQuizModal';
import { usePauseDetector } from '../hooks/usePauseDetector';

export function Watch() {
  const { videoId: paramVideoId } = useParams<{ videoId: string }>();
  const videoId = paramVideoId ?? '3OmfTIf-SOU';
  const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;
  const navigate = useNavigate();

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
  const [isAdmin, setIsAdmin] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  // Chapter quiz schedule state
  const [quizSchedule, setQuizSchedule] = useState<QuizSchedule | null>(null);
  const [activeQuizEvent, setActiveQuizEvent] = useState<QuizScheduleEvent | null>(null);
  const [chapterQuizOpen, setChapterQuizOpen] = useState(false);
  const completedEventsRef = useRef<Set<string>>(new Set());
  const prevTimeRef = useRef<number>(0);

  // Layout state: chat panel width as a % of total (default 40%, range 20–70%).
  const [chatPct, setChatPct] = useState<number>(() => {
    const saved = Number(localStorage.getItem('eduvidqa.chatPct'));
    return Number.isFinite(saved) && saved >= 20 && saved <= 70 ? saved : 40;
  });
  const dragRef = useRef<{ active: boolean; rectLeft: number; rectWidth: number }>({
    active: false, rectLeft: 0, rectWidth: 0,
  });
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    localStorage.setItem('eduvidqa.chatPct', String(chatPct));
  }, [chatPct]);

  const startDrag = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = { active: true, rectLeft: rect.left, rectWidth: rect.width };
    e.preventDefault();
  }, []);

  useEffect(() => {
    function onMove(e: MouseEvent | TouchEvent) {
      if (!dragRef.current.active) return;
      const clientX = 'touches' in e ? e.touches[0]?.clientX : (e as MouseEvent).clientX;
      if (clientX == null) return;
      const { rectLeft, rectWidth } = dragRef.current;
      const offsetFromLeft = clientX - rectLeft;
      const videoPct = Math.max(30, Math.min(80, (offsetFromLeft / rectWidth) * 100));
      setChatPct(100 - videoPct);
    }
    function onUp() { dragRef.current.active = false; }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchmove', onMove);
    window.addEventListener('touchend', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onUp);
    };
  }, []);

  const effectiveTimestamp = autoMode ? currentTime : frozenTime;

  const handleTimeUpdate = useCallback((time: number) => {
    setCurrentTime(time);

    // Detect quiz-schedule crossings
    if (quizSchedule && quizSchedule.events.length > 0 && !chapterQuizOpen) {
      const prev = prevTimeRef.current;
      // Only detect forward crossings within a reasonable delta (avoid seek-triggered floods)
      if (time > prev && time - prev < 3) {
        for (const evt of quizSchedule.events) {
          const key = `${evt.chapter_id}:${evt.type}:${evt.timestamp}`;
          if (completedEventsRef.current.has(key)) continue;
          // Check if we just crossed this timestamp
          if (prev < evt.timestamp && time >= evt.timestamp) {
            completedEventsRef.current.add(key);
            setActiveQuizEvent(evt);
            setChapterQuizOpen(true);
            // Pause the player
            if (playerRef.current) {
              playerRef.current.seekTo(evt.timestamp, true);
              // YT API: pauseVideo is available on the player object
              (playerRef.current as unknown as { pauseVideo(): void }).pauseVideo?.();
            }
            break; // one quiz at a time
          }
        }
      }
    }
    prevTimeRef.current = time;
  }, [quizSchedule, chapterQuizOpen]);

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

  const handleCheckpointClick = useCallback(async (cp: Checkpoint) => {
    if (playerRef.current) {
      playerRef.current.seekTo(cp.timestamp_seconds, true);
    }
    setCurrentTime(cp.timestamp_seconds);
    // Also load the quiz for THIS checkpoint
    try {
      const { questions } = await getQuiz(videoId, Math.floor(cp.timestamp_seconds));
      if (questions && questions.length > 0) {
        handleQuizReady(questions);
      } else {
        toast('No quiz cached for this checkpoint yet.', { icon: 'ℹ️' });
      }
    } catch (err) {
      console.error('Quiz load failed for checkpoint:', err);
      const status = (err as { status?: number })?.status;
      const msg = err instanceof Error ? err.message : 'Failed to load quiz';
      if (status === 402) {
        toast(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="text-sm">{msg}</span>
              <button
                className="px-3 py-1 bg-blue-600 text-white rounded text-sm whitespace-nowrap"
                onClick={() => {
                  toast.dismiss(t.id);
                  navigate('/settings');
                }}
              >
                Add Key
              </button>
            </div>
          ),
          { duration: 8000 },
        );
      } else {
        toast.error(msg);
      }
    }
  }, [videoId, handleQuizReady, navigate]);

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

  // Fetch checkpoints + chapter quiz schedule on mount / when videoId changes
  useEffect(() => {
    if (videoId) {
      getCheckpoints(videoId)
        .then(setCheckpoints)
        .catch(() => {
          /* no checkpoints available */
        });
      getQuizSchedule(videoId)
        .then((schedule) => {
          setQuizSchedule(schedule);
          // Reset completed events on video change
          completedEventsRef.current = new Set();
        })
        .catch(() => {
          /* no quiz schedule — video may not have chapters yet */
        });
    }
  }, [videoId]);

  const handleChapterQuizClose = useCallback(() => {
    setChapterQuizOpen(false);
    setActiveQuizEvent(null);
    // Resume playback
    if (playerRef.current) {
      (playerRef.current as unknown as { playVideo(): void }).playVideo?.();
    }
  }, []);

  // Determine if current user is admin (controls visibility of regenerate button)
  useEffect(() => {
    whoami()
      .then((w) => setIsAdmin(w.is_admin))
      .catch(() => setIsAdmin(false));
  }, []);

  // Poll video status while still ingesting (processing OR transcript_ready)
  useEffect(() => {
    if (!processingStatus || processingStatus === 'ready' || processingStatus === 'failed') return;
    const interval = setInterval(async () => {
      try {
        const { status } = await getVideoStatus(videoId);
        if (status !== processingStatus) {
          setProcessingStatus(status);
          if (status === 'ready') {
            toast.success('Visual analysis ready — answers will now include keyframes!');
          } else if (status === 'transcript_ready') {
            toast('Transcript ready — you can ask questions now!', { icon: '📝' });
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
    // Append the user message AND an empty assistant placeholder atomically.
    // Tokens will accumulate into the placeholder as they stream in.
    setMessages((prev) => [
      ...prev,
      userMsg,
      { role: 'assistant', content: '' },
    ]);
    setIsLoading(true);

    let firstTokenSeen = false;
    const updateAssistant = (
      mutator: (m: ChatMessage) => ChatMessage,
    ) =>
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === 'assistant') {
            next[i] = mutator(next[i]);
            break;
          }
        }
        return next;
      });

    try {
      await askQuestionStream(
        {
          youtube_url: youtubeUrl,
          question,
          timestamp: Math.floor(ts),
          skip_quality_eval: false,
        },
        {
          onSources: (sources) => {
            updateAssistant((m) => ({ ...m, sources }));
          },
          onToken: (text) => {
            if (!firstTokenSeen) {
              firstTokenSeen = true;
              // Hide the "Retrieving / Generating..." bubble — the answer
              // is already streaming into its own bubble now.
              setIsLoading(false);
            }
            updateAssistant((m) => ({ ...m, content: m.content + text }));
          },
          onDone: (meta) => {
            updateAssistant((m) => {
              let content = m.content;
              if (processingStatus === 'transcript_ready') {
                content = `${content}\n\n_\u26a0\ufe0f Visual analysis is still loading in the background \u2014 this answer is based on the transcript only. Ask again in a minute for a more visual answer._`;
              }
              return {
                ...m,
                content,
                model_name: meta.model_name,
                generation_time_seconds: meta.generation_time_seconds,
                quality: meta.quality_scores ?? undefined,
              };
            });
          },
          onError: (err) => {
            updateAssistant((m) => ({
              ...m,
              content: m.content
                ? `${m.content}\n\n**Error:** ${err.message}`
                : `**Error:** ${err.message}`,
            }));
          },
        },
      );
    } catch (err) {
      if (err instanceof VideoProcessingError) {
        setProcessingStatus('processing');
        toast(
          'Video is being processed in the background. Please retry in a minute.',
          { icon: '⏳' },
        );
        updateAssistant((m) => ({
          ...m,
          content:
            '⏳ This video is still being ingested. We are processing it now — please try again shortly.',
        }));
      } else {
        updateAssistant((m) => ({
          ...m,
          content: `**Error:** ${err instanceof Error ? err.message : 'Failed to get response'}`,
        }));
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
            ⏳ Preparing transcript…
          </span>
        )}
        {processingStatus === 'transcript_ready' && (
          <span className="ml-4 text-blue-700">
            📝 Transcript ready — visual analysis still loading. Answers may not reference on-screen visuals yet.
          </span>
        )}
      </div>

      <div ref={containerRef} className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden relative">
        {/* Left panel — Video */}
        <div
          className="w-full flex flex-col border-b md:border-b-0 md:border-r border-dark-border overflow-y-auto"
          style={{ flexBasis: `${100 - chatPct}%`, flexShrink: 0, flexGrow: 0 }}
        >
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

            <div className="flex justify-end gap-2">
              {isAdmin && (
                <button
                  onClick={async () => {
                    if (!confirm('Regenerate ALL quizzes for this video? This wipes existing questions for every user and uses YOUR API keys to create new ones.')) return;
                    setRegenerating(true);
                    try {
                      const r = await adminRegenerateQuiz(videoId);
                      toast.success(r.message);
                    } catch (e) {
                      toast.error(e instanceof Error ? e.message : 'Regenerate failed');
                    } finally {
                      setRegenerating(false);
                    }
                  }}
                  disabled={regenerating}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs rounded-full disabled:opacity-50 flex items-center gap-1.5 shadow-md"
                  title="Admin: regenerate quiz cache for all users"
                >
                  {regenerating ? (
                    <span className="animate-spin h-3 w-3 border-2 border-white border-t-transparent rounded-full" />
                  ) : (
                    '🔄'
                  )}{' '}
                  Regenerate
                </button>
              )}
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

        {/* Drag handle (desktop only) */}
        <div
          onMouseDown={startDrag}
          onTouchStart={startDrag}
          className="hidden md:block w-1.5 cursor-col-resize bg-dark-border hover:bg-blue-500/60 active:bg-blue-500/80 flex-shrink-0"
          title="Drag to resize"
        />

        {/* Right panel — Chat or Quiz */}
        <div
          className="w-full flex flex-col min-h-0 h-[50vh] md:h-auto"
          style={{ flexBasis: `${chatPct}%`, flexShrink: 0, flexGrow: 0 }}
        >
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

      {/* Chapter Quiz Modal (pretest / mid-recall / end-recall) */}
      {chapterQuizOpen && activeQuizEvent && (
        <ChapterQuizModal
          videoId={videoId}
          chapterId={activeQuizEvent.chapter_id}
          chapterTitle={activeQuizEvent.chapter_title}
          quizType={activeQuizEvent.type}
          blocking={quizSchedule?.blocking_mode === 'mandatory'}
          onClose={handleChapterQuizClose}
        />
      )}
    </div>
  );
}
