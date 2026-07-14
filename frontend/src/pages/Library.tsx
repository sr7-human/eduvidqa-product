import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import { ProcessingModal } from '../components/ProcessingModal';
import {
  getMyVideos,
  getReviewQueue,
  processVideo,
  getVideoPreview,
  getVideoStatus,
  extractVideoId,
  listMyKeys,
  removeVideo,
  suggestVideoType,
  type UserVideo,
  type VideoPreview,
} from '../api/client';
import type { VideoQualityType } from '../types';

export function Library() {
  const [videos, setVideos] = useState<UserVideo[]>([]);
  const [loading, setLoading] = useState(true);
  const [urlInput, setUrlInput] = useState('');
  const [mode, setMode] = useState<'lecture' | 'podcast'>('lecture');
  const [videoType, setVideoType] = useState<VideoQualityType>('auto');
  const [suggesting, setSuggesting] = useState(false);
  const [progressVideo, setProgressVideo] = useState<UserVideo | null>(null);
  const [adding, setAdding] = useState(false);
  const [dueCount, setDueCount] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [hasKey, setHasKey] = useState<boolean | null>(null); // null = unknown
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showFailed, setShowFailed] = useState(false);
  const [preview, setPreview] = useState<VideoPreview | null>(null);
  const [fetchingPreview, setFetchingPreview] = useState(false);
  const PAGE_SIZE = 12;
  const navigate = useNavigate();

  // Failed videos are hidden by default — they're noise. User can opt in.
  const failedCount = videos.filter((v) => v.status === 'failed').length;
  const visibleVideos = showFailed ? videos : videos.filter((v) => v.status !== 'failed');

  // Fuzzy filter: keep videos whose title (or video_id) contains every word
  // of the search query in order — also tolerates 1 typo per word via a
  // simple edit-distance check on each word.
  const filteredVideos = (() => {
    const q = search.trim().toLowerCase();
    if (!q) return visibleVideos;
    const tokens = q.split(/\s+/).filter(Boolean);
    const fuzzyMatch = (haystack: string, needle: string): boolean => {
      if (haystack.includes(needle)) return true;
      // tolerate 1 char of typo for needles >= 4 chars
      if (needle.length < 4) return false;
      for (let i = 0; i <= haystack.length - needle.length; i++) {
        let mismatches = 0;
        for (let j = 0; j < needle.length; j++) {
          if (haystack[i + j] !== needle[j]) mismatches++;
          if (mismatches > 1) break;
        }
        if (mismatches <= 1) return true;
      }
      return false;
    };
    return visibleVideos.filter((v) => {
      const hay = `${(v.title || '').toLowerCase()} ${v.video_id.toLowerCase()}`;
      return tokens.every((tok) => fuzzyMatch(hay, tok));
    });
  })();

  // Remove a single video from this user's library.
  const handleRemove = async (videoId: string) => {
    // Optimistic update — drop from local state immediately.
    const prev = videos;
    setVideos((curr) => curr.filter((v) => v.video_id !== videoId));
    try {
      await removeVideo(videoId);
    } catch (e) {
      // Roll back on failure
      setVideos(prev);
      toast.error(e instanceof Error ? e.message : 'Failed to remove video');
    }
  };

  // Fetch videos on mount
  useEffect(() => {
    getMyVideos()
      .then(setVideos)
      .catch((e) => toast.error(`Failed to load videos: ${e.message}`))
      .finally(() => setLoading(false));
  }, []);

  // Fetch review-queue due count on mount
  useEffect(() => {
    getReviewQueue()
      .then((data) => setDueCount(data.due_count))
      .catch(() => {
        /* no review data */
      });
  }, []);

  // Check whether user has any API key stored (BYOK)
  useEffect(() => {
    listMyKeys()
      .then((r) => {
        const has = r.keys.length > 0;
        setHasKey(has);
        // Show onboarding modal once per browser session if no keys
        if (!has && !sessionStorage.getItem('byok-onboarding-seen')) {
          setShowOnboarding(true);
          sessionStorage.setItem('byok-onboarding-seen', '1');
        }
      })
      .catch(() => setHasKey(null));
  }, []);

  // Poll videos that aren't fully ready yet (processing OR transcript_ready)
  useEffect(() => {
    const stillProcessing = videos.filter(
      (v) => v.status === 'processing' || v.status === 'transcript_ready',
    );
    if (stillProcessing.length === 0) return;
    const interval = setInterval(async () => {
      for (const v of stillProcessing) {
        try {
          const { status } = await getVideoStatus(v.video_id);
          if (status !== v.status) {
            setVideos((prev) =>
              prev.map((pv) =>
                pv.video_id === v.video_id ? { ...pv, status } : pv,
              ),
            );
          }
        } catch {
          /* ignore polling errors */
        }
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [videos]);

  const handleAdd = async () => {
    const isPlaylist = /[?&]list=([A-Za-z0-9_-]+)/.test(urlInput);
    if (!isPlaylist && !extractVideoId(urlInput)) {
      toast.error('Invalid YouTube URL');
      return;
    }
    // For playlists, skip preview and go straight to processing
    if (isPlaylist) {
      return handleConfirmAdd();
    }
    // For single videos, fetch preview first — but never block the add flow on
    // it. The preview is cosmetic; if it's slow or unavailable, add directly.
    setFetchingPreview(true);
    try {
      const p = await Promise.race([
        getVideoPreview(urlInput),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('preview-timeout')), 8000),
        ),
      ]);
      setPreview(p as VideoPreview);
      setFetchingPreview(false);
    } catch {
      // Preview slow or failed → skip the confirm modal and add directly.
      setFetchingPreview(false);
      await handleConfirmAdd();
    }
  };

  const handleConfirmAdd = async () => {
    setPreview(null);
    setAdding(true);    try {
      const res = (await processVideo({ youtube_url: urlInput, mode, video_type: mode === 'lecture' ? videoType : undefined })) as unknown as Record<string, unknown>;
      toast.success(String(res.message ?? 'Video submitted'));
      setUrlInput('');
      // Reload library so any new videos (single or playlist) show up
      try {
        const fresh = await getMyVideos();
        setVideos(fresh);
        setPage(0);
      } catch {
        /* ignore reload error */
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to add video');
    } finally {
      setAdding(false);
    }
  };

  const handleSuggest = async () => {
    if (!urlInput) return;
    setSuggesting(true);
    try {
      const r = await suggestVideoType(urlInput);
      setVideoType(r.video_type);
      toast.success(`AI suggests: ${r.video_type}`);
    } catch {
      toast.error('Could not analyse the video — pick a type manually.');
    } finally {
      setSuggesting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a]">
      <Navbar />

      {progressVideo && (
        <ProcessingModal
          videoId={progressVideo.video_id}
          title={progressVideo.title ?? undefined}
          onClose={() => setProgressVideo(null)}
        />
      )}

      {/* Onboarding modal (shows once per session for users without keys) */}
      {showOnboarding && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowOnboarding(false)}
        >
          <div
            className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-5xl mb-3">👋</div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              Welcome to EduVidQA!
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed mb-4">
              Before adding your first video, please add a free <strong>Google Gemini</strong>{' '}
              or <strong>Groq</strong> API key in Settings. Your key is used to:
            </p>
            <ul className="text-sm text-gray-600 dark:text-gray-300 space-y-1.5 mb-5 ml-4 list-disc">
              <li>Generate embeddings to search your videos</li>
              <li>Answer your questions intelligently</li>
              <li>Create personalised quizzes</li>
            </ul>
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-5">
              <p className="text-xs text-blue-800 dark:text-blue-300 leading-relaxed">
                <strong>Free.</strong> Both Gemini and Groq have generous free tiers — your
                key, your quota. We never share or store keys against other users.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <button
                onClick={() => {
                  setShowOnboarding(false);
                  navigate('/settings');
                }}
                className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
              >
                Add API Key
              </button>
              <button
                onClick={() => setShowOnboarding(false)}
                className="flex-1 px-4 py-2.5 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg text-sm"
              >
                Try the demo first
              </button>
            </div>
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-4 text-center">
              You can still watch + ask questions on the demo video without a key.
            </p>
          </div>
        </div>
      )}

      {/* Video preview modal — shown after metadata fetch, before confirming ingest */}
      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setPreview(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl max-w-md w-full p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-3xl mb-2">✓</div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1 leading-snug">
              {preview.title}
            </h3>
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-4">
              {preview.duration_seconds > 0 && (
                <>
                  <span>
                    {preview.duration_seconds >= 3600
                      ? `${Math.floor(preview.duration_seconds / 3600)}h ${Math.round((preview.duration_seconds % 3600) / 60)}m`
                      : `${Math.round(preview.duration_seconds / 60)} min`}
                  </span>
                  <span>·</span>
                  <span>~{preview.estimated_chapters} section{preview.estimated_chapters !== 1 ? 's' : ''}</span>
                  <span>·</span>
                </>
              )}
              <span className="text-gray-400 dark:text-gray-500">warm-up + recall quizzes throughout</span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-5">
              Processing transcript and visuals — you can start watching in about a minute.
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleConfirmAdd}
                disabled={adding}
                className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm disabled:opacity-50"
              >
                {adding ? 'Adding…' : 'Add to library'}
              </button>
              <button
                onClick={() => setPreview(null)}
                className="px-4 py-2.5 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto p-6 pb-32">
        <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">My Library</h1>

        {/* Persistent banner if no key (always shown until they add one) */}
        {hasKey === false && (
          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 mb-6 flex items-start sm:items-center justify-between gap-3 flex-col sm:flex-row">
            <div className="flex-1">
              <h3 className="font-semibold text-amber-900 dark:text-amber-200 text-sm">
                🔑 No API key yet
              </h3>
              <p className="text-xs text-amber-800 dark:text-amber-300 mt-0.5">
                Add a free Gemini or Groq key to process your own videos. The demo video works without one.
              </p>
            </div>
            <Link
              to="/settings"
              className="px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm whitespace-nowrap font-medium"
            >
              Add Key
            </Link>
          </div>
        )}

        {dueCount > 0 && (
          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 mb-6 flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-amber-800 dark:text-amber-300">
                📚 {dueCount} question{dueCount > 1 ? 's' : ''} due for review
              </h3>
              <p className="text-sm text-amber-600 dark:text-amber-400">Keep your knowledge fresh</p>
            </div>
            <Link
              to="/review"
              className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm"
            >
              Review now
            </Link>
          </div>
        )}

        {/* Add video input */}
        <div className="flex gap-2 mb-2">
          <input
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Paste YouTube URL or playlist..."
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAdd();
            }}
          />
          <button
            onClick={handleAdd}
            disabled={adding || fetchingPreview || !urlInput}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {fetchingPreview ? 'Checking…' : adding ? 'Adding...' : 'Add Video'}
          </button>
        </div>

        {/* Ingest-mode toggle (applies to the video or the whole playlist) */}
        <div className="flex flex-wrap items-center gap-2 mb-4 text-sm">
          <span className="text-gray-500 dark:text-gray-400">Processing:</span>
          <button
            type="button"
            onClick={() => setMode('lecture')}
            className={`px-3 py-1 rounded-full border transition ${
              mode === 'lecture'
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-transparent text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-blue-500'
            }`}
          >
            🎓 Lecture (full)
          </button>
          <button
            type="button"
            onClick={() => setMode('podcast')}
            className={`px-3 py-1 rounded-full border transition ${
              mode === 'podcast'
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-transparent text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-blue-500'
            }`}
          >
            🎧 Podcast (transcript-only)
          </button>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {mode === 'lecture'
              ? 'Extracts on-screen frames — best for slides, whiteboards, diagrams & code.'
              : 'Skips video download & keyframes — faster & cheaper for talks and interviews.'}
          </span>
        </div>

        {/* Keyframe quality (lecture mode only — podcast has no frames) */}
        {mode === 'lecture' && (
          <div className="flex flex-wrap items-center gap-2 mb-4 text-sm">
            <span className="text-gray-500 dark:text-gray-400">Quality:</span>
            <span className="relative group inline-flex items-center">
              <span
                className="flex items-center justify-center w-4 h-4 rounded-full border border-gray-400 dark:border-gray-500 text-gray-500 dark:text-gray-400 text-[10px] font-semibold cursor-help select-none"
                aria-label="What do these quality types mean?"
              >
                i
              </span>
              {/* Hover tooltip explaining each type in plain English */}
              <div className="pointer-events-none absolute left-0 top-6 z-20 hidden group-hover:block w-72 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-3 text-xs text-gray-600 dark:text-gray-300 shadow-lg">
                <p className="mb-2 font-medium text-gray-800 dark:text-gray-100">
                  Which one should I pick?
                </p>
                <p className="mb-1.5">
                  <span className="font-semibold">Standard lecture (720p)</span> — Normal
                  class: teacher with a board or slides. Good for most videos. Pick this if unsure.
                  <span className="text-gray-400 dark:text-gray-500"> 💾 Medium storage.</span>
                </p>
                <p className="mb-1.5">
                  <span className="font-semibold">Handheld / moving camera (1080p)</span> —
                  Camera moves around and the board looks far or small. Sharpest quality so the
                  writing stays readable.
                  <span className="text-gray-400 dark:text-gray-500"> 💾 Highest storage (~2× Standard).</span>
                </p>
                <p className="mb-1.5">
                  <span className="font-semibold">Slides / screen-share / PiP (480p)</span> —
                  A fixed screen or slides fill the frame (maybe a small teacher in a corner).
                  Clear even at lower quality.
                  <span className="text-gray-400 dark:text-gray-500"> 💾 Low storage (~½ of Standard).</span>
                </p>
                <p>
                  <span className="font-semibold">Pure animation (360p)</span> — Fully animated,
                  big clean visuals. Lowest quality is plenty.
                  <span className="text-gray-400 dark:text-gray-500"> 💾 Lowest storage.</span>
                </p>
                <p className="mt-2 text-gray-400 dark:text-gray-500">
                  Lower quality saves storage — pick the lowest that's still readable. Not sure?
                  Tap 🤖 Suggest and the AI picks for you.
                </p>
              </div>
            </span>
            <select
              value={videoType}
              onChange={(e) => setVideoType(e.target.value as VideoQualityType)}
              className="px-3 py-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="auto">Standard lecture (720p)</option>
              <option value="handheld">Handheld / moving camera (1080p)</option>
              <option value="slides">Slides / screen-share / PiP (480p)</option>
              <option value="animation">Pure animation (360p)</option>
            </select>
            <button
              type="button"
              onClick={handleSuggest}
              disabled={suggesting || !urlInput}
              className="px-3 py-1 rounded-full border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-blue-500 disabled:opacity-50 transition"
              title="Let AI look at a few frames and pick the best quality"
            >
              {suggesting ? 'Analysing…' : '🤖 Suggest'}
            </button>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              Higher = sharper on-screen text, more storage. Applies to the whole playlist.
            </span>
          </div>
        )}

        {/* Search box */}
        {videos.length > 0 && (
          <div className="mb-3">
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              placeholder="🔍 Search your videos..."
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
            />
          </div>
        )}

        {/* "Show failed" toggle — only shown when there are some */}
        {failedCount > 0 && (
          <div className="mb-6 flex items-center gap-2 text-xs">
            <button
              onClick={() => setShowFailed((s) => !s)}
              className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline-offset-2 hover:underline"
            >
              {showFailed
                ? `Hide ${failedCount} failed video${failedCount > 1 ? 's' : ''}`
                : `Show ${failedCount} failed video${failedCount > 1 ? 's' : ''}`}
            </button>
            <span className="text-gray-400 dark:text-gray-500">·</span>
            <span className="text-gray-400 dark:text-gray-500">
              Failed videos usually mean YouTube blocks transcripts or the API quota was hit.
            </span>
          </div>
        )}

        {/* Video gallery */}
        {loading ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-12">Loading...</p>
        ) : videos.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-12">
            No videos yet. Add your first lecture!
          </p>
        ) : filteredVideos.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-12">
            {search
              ? `No videos match “${search}”.`
              : 'No videos to show. (Failed videos are hidden — toggle them above.)'}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
              {filteredVideos.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((v) => {
                // Always allow clicking — Watch page handles every status
                // gracefully (shows "still ingesting" banner for processing).
                const isFailed = v.status === 'failed';
                const thumb = `https://i.ytimg.com/vi/${v.video_id}/mqdefault.jpg`;
                const statusLabel =
                  v.status === 'transcript_ready'
                    ? 'watch now'
                    : v.status === 'ready'
                    ? 'ready'
                    : v.status === 'processing'
                    ? 'processing'
                    : v.status === 'failed'
                    ? 'failed'
                    : v.status;
                const statusClass =
                  v.status === 'ready'
                    ? 'bg-green-600 text-white'
                    : v.status === 'transcript_ready'
                    ? 'bg-blue-600 text-white'
                    : v.status === 'processing'
                    ? 'bg-yellow-500 text-white'
                    : 'bg-red-600 text-white';
                return (
                  <div
                    key={v.video_id}
                    onClick={() => !isFailed && navigate(`/watch/${v.video_id}`)}
                    className={`relative bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden transition group ${
                      isFailed
                        ? 'opacity-60 cursor-default'
                        : 'cursor-pointer hover:shadow-lg hover:border-blue-400 dark:hover:border-blue-500'
                    }`}
                  >
                    {/* Remove (✕) button — top-left, shown on hover */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Remove "${v.title || v.video_id}" from your library?`)) {
                          handleRemove(v.video_id);
                        }
                      }}
                      className="absolute top-2 left-2 z-10 w-6 h-6 rounded-full bg-black/60 hover:bg-red-600 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                      title="Remove from library"
                      aria-label="Remove from library"
                    >
                      ✕
                    </button>
                    {/* Thumbnail with 16:9 aspect ratio */}
                    <div className="relative w-full bg-gray-200 dark:bg-gray-900" style={{ paddingTop: '56.25%' }}>
                      <img
                        src={thumb}
                        alt={v.title || v.video_id}
                        className="absolute inset-0 w-full h-full object-cover"
                        loading="lazy"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).style.display = 'none';
                        }}
                      />
                      {/* Play icon overlay on hover (only if not failed) */}
                      {!isFailed && (
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/30">
                          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center text-blue-600 text-2xl">
                            ▶
                          </div>
                        </div>
                      )}
                      {/* Status badge over thumbnail (click to see live progress) */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (v.status === 'processing' || v.status === 'transcript_ready' || v.status === 'failed') {
                            setProgressVideo(v);
                          }
                        }}
                        className={`absolute top-2 right-2 text-[10px] font-medium px-2 py-0.5 rounded ${statusClass} ${
                          v.status === 'processing' || v.status === 'transcript_ready' || v.status === 'failed'
                            ? 'cursor-pointer hover:brightness-110'
                            : 'cursor-default'
                        }`}
                        title={
                          v.status === 'processing' || v.status === 'transcript_ready'
                            ? 'View processing progress'
                            : v.status === 'failed' ? 'See why it failed' : ''
                        }
                      >
                        {statusLabel}
                      </button>
                      {/* Watch-progress bar (YouTube-style) along the bottom of the thumbnail */}
                      {!isFailed && typeof v.last_position === 'number' && typeof v.duration === 'number' && v.duration > 0 && v.last_position > 5 && (
                        <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/40" title={`Watched ${Math.round((v.last_position / v.duration) * 100)}%`}>
                          <div
                            className="h-full bg-red-500"
                            style={{ width: `${Math.min(100, (v.last_position / v.duration) * 100)}%` }}
                          />
                        </div>
                      )}
                    </div>
                    {/* Title */}
                    <div className="p-3">
                      <p className="text-sm font-medium text-gray-900 dark:text-white line-clamp-2 leading-snug" title={v.title || v.video_id}>
                        {v.title || v.video_id}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            {filteredVideos.length > PAGE_SIZE && (
              <div className="flex items-center justify-center gap-3 mt-8">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-200 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  ← Prev
                </button>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Page {page + 1} of {Math.ceil(filteredVideos.length / PAGE_SIZE)}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(Math.ceil(filteredVideos.length / PAGE_SIZE) - 1, p + 1))}
                  disabled={(page + 1) * PAGE_SIZE >= filteredVideos.length}
                  className="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-200 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
