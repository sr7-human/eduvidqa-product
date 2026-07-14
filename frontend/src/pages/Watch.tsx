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
  getChapterQuiz,
  getQuiz,
  getQuizSchedule,
  getVideoStatus,
  getMyVideos,
  whoami,
  adminRegenerateQuiz,
  saveWatchProgress,
  startIngest,
  VideoProcessingError,
} from '../api/client';
import type { ChatMessage, Checkpoint, QuizQuestion, QuizScheduleEvent, QuizSchedule, YTPlayer } from '../types';
import { CheckpointMarkers } from '../components/CheckpointMarkers';
import { TestMeButton } from '../components/TestMeButton';
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
  const [statusText, setStatusText] = useState<string | undefined>();
  const [playerReady, setPlayerReady] = useState(false);

  // Processing state (when /api/ask returns 202)
  const [processingStatus, setProcessingStatus] = useState<string | null>(null);

  // Quiz state
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  // Question scope: single timestamp (point), a [start, end) interval (range),
  // or the whole lecture ('all' = search everywhere for relevant parts).
  const [questionScope, setQuestionScope] = useState<'point' | 'range' | 'all'>('point');
  const [rangeStart, setRangeStart] = useState<number | null>(null);
  const [rangeEnd, setRangeEnd] = useState<number | null>(null);
  const [videoDuration, setVideoDuration] = useState(0);
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[] | null>(null);
  const [showQuiz, setShowQuiz] = useState(false);  const [playerState, setPlayerState] = useState<'playing' | 'paused' | 'other'>('other');
  const [isAdmin, setIsAdmin] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  // Chapter quiz schedule state
  const [quizSchedule, setQuizSchedule] = useState<QuizSchedule | null>(null);
  const [activeQuizEvent, setActiveQuizEvent] = useState<QuizScheduleEvent | null>(null);
  const [chapterQuizOpen, setChapterQuizOpen] = useState(false);
  const completedEventsRef = useRef<Set<string>>(new Set());
  const prevTimeRef = useRef<number>(0);
  // Checkpoints already auto-popped (so we never re-interrupt or flood on seek).
  const autoCheckpointRef = useRef<Set<number>>(new Set());
  // Chapter quizzes already prefetched (warmed in the background so they're
  // cached before the learner reaches them — no wait, esp. for vision quizzes).
  const prefetchedRef = useRef<Set<string>>(new Set());
  // Video-time (s) of the last auto quiz, to enforce a cooldown between popups
  // so a chapter event and a nearby checkpoint never interrupt back-to-back.
  const lastAutoQuizRef = useRef<number>(-1e9);
  // Wall-clock (ms) of the last watch-progress save, throttled to ~10s.
  const lastProgressSaveRef = useRef<number>(0);
  // Where to resume playback from (seconds). Also used to suppress quizzes the
  // user has already passed on a previous watch.
  const [resumeAt, setResumeAt] = useState<number>(0);
  const resumeAppliedRef = useRef(false);
  // In-flight answer stream, so the user can Stop it or fire a new query
  // without waiting for the previous response to finish.
  const abortRef = useRef<AbortController | null>(null);

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
    // Persist watch progress at most once every ~20s (best-effort, non-blocking).
    const nowMs = Date.now();
    if (videoId && time > 0 && nowMs - lastProgressSaveRef.current > 20000) {
      lastProgressSaveRef.current = nowMs;
      const dur = playerRef.current?.getDuration?.() || undefined;
      saveWatchProgress(videoId, Math.floor(time), dur).catch(() => {});
    }
    const prev = prevTimeRef.current;
    // Only react to forward crossings within a small delta (avoid seek floods).
    const forwardCross = time > prev && time - prev < 3;
    // Cooldown so closing one quiz doesn't immediately trigger another nearby
    // one (the "quiz pops again right after I close it" bug).
    const cooled = time - lastAutoQuizRef.current > 60;

    // Detect chapter quiz-schedule crossings (pretest / mid / end)
    if (quizSchedule && quizSchedule.events.length > 0 && !chapterQuizOpen && !showQuiz && forwardCross && cooled) {
      for (const evt of quizSchedule.events) {
        const key = `${evt.chapter_id}:${evt.type}:${evt.timestamp}`;
        if (completedEventsRef.current.has(key)) continue;
        // Check if we just crossed this timestamp
        if (prev < evt.timestamp && time >= evt.timestamp) {
          completedEventsRef.current.add(key);
          lastAutoQuizRef.current = time;
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

    // Auto-popup the Test-me quiz at each semantic checkpoint. Every processed
    // video has checkpoints (many have no chapters), so this is what makes a
    // quiz appear on its own as you watch. Each checkpoint fires at most once;
    // dismissing/skipping does not re-trigger it.
    if (checkpoints.length > 0 && !chapterQuizOpen && !showQuiz && forwardCross && cooled) {
      for (const cp of checkpoints) {
        const cpTs = Math.floor(cp.timestamp_seconds);
        if (autoCheckpointRef.current.has(cpTs)) continue;
        if (prev < cp.timestamp_seconds && time >= cp.timestamp_seconds) {
          autoCheckpointRef.current.add(cpTs);
          lastAutoQuizRef.current = time;
          (playerRef.current as unknown as { pauseVideo(): void })?.pauseVideo?.();
          getQuiz(videoId, cpTs)
            .then(({ questions }) => {
              if (questions && questions.length > 0) {
                setQuizQuestions(questions);
                setShowQuiz(true);
              }
            })
            .catch((err) => console.error('Auto checkpoint quiz failed:', err));
          break; // one quiz at a time
        }
      }
    }
    prevTimeRef.current = time;

    // Prefetch: warm the next 1-2 upcoming chapter quizzes in the background so
    // they're already cached (esp. vision quizzes that take ~20s to build)
    // before the learner reaches them — no wait on arrival.
    if (quizSchedule && quizSchedule.events.length > 0) {
      const upcoming = quizSchedule.events
        .filter((e) => e.timestamp > time)
        .sort((a, b) => a.timestamp - b.timestamp)
        .slice(0, 1);
      for (const evt of upcoming) {
        const key = `${evt.chapter_id}:${evt.type}`;
        if (prefetchedRef.current.has(key)) continue;
        prefetchedRef.current.add(key);
        getChapterQuiz(videoId, evt.chapter_id, evt.type).catch(() => {
          prefetchedRef.current.delete(key); // allow a retry later on failure
        });
      }
    }
  }, [quizSchedule, chapterQuizOpen, checkpoints, showQuiz, videoId]);

  const handlePlayerReady = useCallback(() => {
    setPlayerReady(true);
  }, []);

  // Save the final watch position when leaving the page (prevTimeRef holds the
  // last known video time from handleTimeUpdate).
  useEffect(() => {
    return () => {
      const t = prevTimeRef.current;
      if (videoId && t > 0) {
        const dur = playerRef.current?.getDuration?.() || undefined;
        saveWatchProgress(videoId, Math.floor(t), dur).catch(() => {});
      }
    };
  }, [videoId]);

  // Fetch this video's last watched position (for resume + quiz suppression).
  useEffect(() => {
    resumeAppliedRef.current = false;
    setResumeAt(0);
    if (!videoId) return;
    getMyVideos()
      .then((vids) => {
        const me = vids.find((v) => v.video_id === videoId);
        const pos = typeof me?.last_position === 'number' ? me.last_position : 0;
        setResumeAt(pos > 5 ? pos : 0);
      })
      .catch(() => {});
  }, [videoId]);

  // Once the player is ready AND we know where to resume, seek there once.
  useEffect(() => {
    if (!playerReady || resumeAppliedRef.current || resumeAt <= 5) return;
    if (playerRef.current) {
      resumeAppliedRef.current = true;
      playerRef.current.seekTo(resumeAt, true);
      setCurrentTime(resumeAt);
      prevTimeRef.current = resumeAt;
    }
  }, [playerReady, resumeAt]);

  // Suppress auto-quizzes (chapter pretest/mid/end + checkpoints) for the part
  // of the video the user already watched — no re-popping on a rewatch.
  useEffect(() => {
    if (resumeAt <= 0) return;
    if (quizSchedule) {
      for (const evt of quizSchedule.events) {
        if (evt.timestamp <= resumeAt) {
          completedEventsRef.current.add(`${evt.chapter_id}:${evt.type}:${evt.timestamp}`);
        }
      }
    }
    for (const cp of checkpoints) {
      if (cp.timestamp_seconds <= resumeAt) {
        autoCheckpointRef.current.add(Math.floor(cp.timestamp_seconds));
      }
    }
  }, [resumeAt, quizSchedule, checkpoints]);
  // A pretest at the very start (timestamp ≈ 0) can't be caught by the forward-
  // crossing detector (there's nothing to "cross"), and the video is paused at
  // 0:00 so no time updates fire. Trigger it once the schedule is loaded — this
  // is the intended "prime me on what's ahead" moment, before pressing play.
  useEffect(() => {
    if (!quizSchedule || quizSchedule.events.length === 0) return;
    if (chapterQuizOpen || showQuiz || currentTime > 2) return;
    const startEvt = quizSchedule.events.find(
      (e) => e.type === 'pretest' && e.timestamp <= 1,
    );
    if (!startEvt) return;
    const key = `${startEvt.chapter_id}:${startEvt.type}:${startEvt.timestamp}`;
    if (completedEventsRef.current.has(key)) return;
    completedEventsRef.current.add(key);
    lastAutoQuizRef.current = currentTime;
    setActiveQuizEvent(startEvt);
    setChapterQuizOpen(true);
    (playerRef.current as unknown as { pauseVideo(): void })?.pauseVideo?.();
  }, [quizSchedule, currentTime, chapterQuizOpen, showQuiz]);

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
    // Reuse the polished chapter-quiz modal for the normal "Test me" quizzes.
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
    if (!videoId) return;
    // Reset the per-video "already shown" dedup SYNCHRONOUSLY when the video
    // changes — NOT inside the async .then below. If we reset it after the
    // fetch resolves, a second resolution (React StrictMode / re-fetch) can
    // wipe the record of an already-shown pretest and make it pop up twice.
    completedEventsRef.current = new Set();
    prefetchedRef.current = new Set();
    prevTimeRef.current = 0;
    getCheckpoints(videoId)
      .then(setCheckpoints)
      .catch(() => {
        /* no checkpoints available */
      });
    getQuizSchedule(videoId)
      .then(setQuizSchedule)
      .catch(() => {
        /* no quiz schedule — video may not have chapters yet */
      });
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

  // Initial status on load — so we can show the right ingest buttons for a
  // deferred/stub video (added to library but not yet processed).
  useEffect(() => {
    if (!videoId) return;
    getVideoStatus(videoId).then(({ status }) => setProcessingStatus(status)).catch(() => {});
  }, [videoId]);

  const [ingesting, setIngesting] = useState(false);
  const handleStartIngest = useCallback(async (phase: 'all' | 'transcript' | 'visuals') => {
    setIngesting(true);
    try {
      await startIngest(videoId, youtubeUrl, phase);
      setProcessingStatus('processing');
      toast.success(phase === 'visuals' ? 'Adding visual understanding…' : 'Ingest started…');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not start ingest');
    } finally {
      setIngesting(false);
    }
  }, [videoId, youtubeUrl]);

  // Timeline markers: use real (legacy) checkpoints if the video has them,
  // otherwise derive markers from CHAPTER starts (pretest events). Semantic
  // checkpoints are no longer created — chapters are the single quiz structure —
  // so this keeps the timeline populated for new videos.
  const timelineMarkers: Checkpoint[] = checkpoints.length > 0
    ? checkpoints
    : (quizSchedule?.events ?? [])
        .filter((e) => e.type === 'pretest')
        .map((e) => ({
          id: e.chapter_id || `ch-${Math.floor(e.timestamp)}`,
          timestamp_seconds: e.timestamp,
          topic_label: e.chapter_title || 'Chapter',
        }));

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

  function fmtClock(s: number): string {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  }
  // Set a range boundary (from a slider or the "now" button), keeping start <= end.
  function setRangeFrom(which: 'start' | 'end', seconds: number) {
    const s = Math.max(0, Math.floor(seconds));
    if (which === 'start') {
      setRangeStart(s);
      setRangeEnd((e) => (e !== null && e < s ? s : e));
    } else {
      setRangeEnd(s);
      setRangeStart((st) => (st !== null && st > s ? s : st));
    }
  }

  async function handleSend(question: string, imageB64?: string) {
    const ts = effectiveTimestamp;
    if (questionScope === 'range') {
      if (rangeStart === null || rangeEnd === null) { toast.error('Set both the start and end of the range first.'); return; }
      if (rangeEnd <= rangeStart) { toast.error('Range end must be after the start.'); return; }
      if (rangeEnd - rangeStart > 1800) { toast.error('Range must be 30 minutes or less.'); return; }
    }
    const useRange = questionScope === 'range' && rangeStart !== null && rangeEnd !== null;
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
    setStatusText(undefined);

    // Cancel any answer already streaming so a new query starts immediately.
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

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
          skip_quality_eval: true,
          ...(imageB64 ? { image_b64: imageB64 } : {}),
          ...(questionScope === 'all'
            ? { scope: 'all' as const }
            : useRange
            ? { scope: 'range' as const, start_timestamp: Math.floor(rangeStart!), end_timestamp: Math.floor(rangeEnd!) }
            : {}),
        },
        {
          onSources: (sources) => {
            updateAssistant((m) => ({ ...m, sources }));
          },
          onStatus: (text) => {
            setStatusText(text);
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
        controller.signal,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User pressed Stop (or fired a new query) — keep any partial text.
        updateAssistant((m) => ({
          ...m,
          content: m.content ? `${m.content}\n\n_⏹️ stopped_` : '_⏹️ stopped_',
        }));
      } else if (err instanceof VideoProcessingError) {
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
      // Only the CURRENT stream should clear the loading state — a stale abort
      // from a superseded query must not wipe the new query's spinner.
      if (abortRef.current === controller) {
        abortRef.current = null;
        setIsLoading(false);
        setAutoMode(true);
      }
    }
  }

  // Stop the in-flight answer without sending a new one.
  function handleStop() {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsLoading(false);
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
          <span className="ml-4 inline-flex gap-2 items-center">
            <span className="text-yellow-700">⏳ Preparing…</span>
            <button
              onClick={() => handleStartIngest('all')}
              disabled={ingesting}
              className="px-2.5 py-0.5 rounded-full border border-yellow-500 text-yellow-700 hover:bg-yellow-50 disabled:opacity-50 text-xs"
              title="If it seems stuck (e.g. after a server restart), restart processing from where it left off"
            >
              Stuck? Resume
            </button>
          </span>
        )}
        {processingStatus === 'stub' && (
          <span className="ml-4 inline-flex flex-wrap gap-2 items-center">
            <span className="text-gray-600">Not processed yet.</span>
            <button
              onClick={() => handleStartIngest('transcript')}
              disabled={ingesting}
              className="px-3 py-1 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 text-xs"
              title="Fast: index the transcript so you can ask questions (no video download)"
            >
              ▶️ Ingest (Q&A ready)
            </button>
            <button
              onClick={() => handleStartIngest('all')}
              disabled={ingesting}
              className="px-3 py-1 rounded-full border border-blue-600 text-blue-700 hover:bg-blue-50 disabled:opacity-50 text-xs"
              title="Full: transcript + keyframes + chapters + visual quizzes"
            >
              🎬 Full ingest (Q&A + visuals)
            </button>
          </span>
        )}
        {processingStatus === 'transcript_ready' && (
          <span className="ml-4 inline-flex flex-wrap gap-2 items-center">
            <span className="text-blue-700">📝 Transcript ready — Q&A works.</span>
            <button
              onClick={() => handleStartIngest('visuals')}
              disabled={ingesting}
              className="px-3 py-1 rounded-full bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 text-xs"
              title="Download the video, extract keyframes, and build visual (board-reading) chapter quizzes"
            >
              🖼️ Add visual understanding
            </button>
          </span>
        )}
        {processingStatus === 'failed' && (
          <span className="ml-4 inline-flex gap-2 items-center">
            <span className="text-red-700">⚠️ Processing failed.</span>
            <button
              onClick={() => handleStartIngest('all')}
              disabled={ingesting}
              className="px-3 py-1 rounded-full bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 text-xs"
            >
              🔄 Resume / retry
            </button>
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
              checkpoints={timelineMarkers}
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
          {/* Point / Range scope for questions */}
          <div className="px-3 pt-2 flex flex-wrap items-center gap-2 text-xs">
            <div className="inline-flex rounded-md border border-dark-border overflow-hidden">
              <button
                type="button"
                onClick={() => setQuestionScope('point')}
                className={`px-2.5 py-1 ${questionScope === 'point' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
              >Point</button>
              <button
                type="button"
                onClick={() => setQuestionScope('range')}
                className={`px-2.5 py-1 ${questionScope === 'range' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
              >Range</button>
              <button
                type="button"
                onClick={() => setQuestionScope('all')}
                className={`px-2.5 py-1 ${questionScope === 'all' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
                title="Search the entire lecture for parts relevant to your question"
              >Whole</button>
            </div>
            {questionScope === 'all' && (
              <span className="text-[11px] text-gray-500">Searches the whole lecture for wherever your topic is covered.</span>
            )}
            {questionScope === 'range' && (() => {
              const dur = Math.max(1, Math.floor(videoDuration || 0));
              const startVal = rangeStart ?? 0;
              const endVal = rangeEnd ?? dur;
              return (
                <div className="flex flex-col gap-1.5 w-full sm:flex-1 min-w-[220px]">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 w-9">Start</span>
                    <input
                      type="range" aria-label="Range start"
                      min={0} max={dur} value={startVal}
                      onChange={(e) => setRangeFrom('start', Number(e.target.value))}
                      className="flex-1 accent-emerald-500 cursor-pointer"
                    />
                    <span className="font-mono text-gray-300 w-12 text-right">{rangeStart !== null ? fmtClock(rangeStart) : '--:--'}</span>
                    <button type="button" onClick={() => setRangeFrom('start', effectiveTimestamp)} className="text-blue-400 hover:text-blue-300" title="Use current time">now</button>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 w-9">End</span>
                    <input
                      type="range" aria-label="Range end"
                      min={0} max={dur} value={endVal}
                      onChange={(e) => setRangeFrom('end', Number(e.target.value))}
                      className="flex-1 accent-emerald-500 cursor-pointer"
                    />
                    <span className="font-mono text-gray-300 w-12 text-right">{rangeEnd !== null ? fmtClock(rangeEnd) : '--:--'}</span>
                    <button type="button" onClick={() => setRangeFrom('end', effectiveTimestamp)} className="text-blue-400 hover:text-blue-300" title="Use current time">now</button>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-gray-500">
                    <span>Drag the handles, or tap “now” to set from the current moment.</span>
                    <button type="button" onClick={() => { setRangeStart(null); setRangeEnd(null); }} className="text-gray-400 hover:text-gray-200">clear</button>
                  </div>
                </div>
              );
            })()}
          </div>
          <ChatInterface
            messages={messages}
            isLoading={isLoading}
            statusText={statusText}
            timestamp={effectiveTimestamp}
            autoMode={autoMode}
            onSend={handleSend}
            onStop={handleStop}
            onSeek={handleSeek}
            onInputFocus={handleInputFocus}
          />
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

      {/* Normal "Test me" / checkpoint quiz — reuses the same modal UI, always closeable */}
      {showQuiz && quizQuestions && (
        <ChapterQuizModal
          videoId={videoId}
          quizType="checkpoint"
          chapterTitle="Test yourself"
          preloadedQuestions={quizQuestions}
          blocking={false}
          onClose={handleQuizClose}
        />
      )}
    </div>
  );
}
