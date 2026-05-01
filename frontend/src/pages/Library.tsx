import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import {
  getMyVideos,
  getReviewQueue,
  processVideo,
  getVideoStatus,
  extractVideoId,
  type UserVideo,
} from '../api/client';

export function Library() {
  const [videos, setVideos] = useState<UserVideo[]>([]);
  const [loading, setLoading] = useState(true);
  const [urlInput, setUrlInput] = useState('');
  const [adding, setAdding] = useState(false);
  const [dueCount, setDueCount] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const PAGE_SIZE = 12;
  const navigate = useNavigate();

  // Fuzzy filter: keep videos whose title (or video_id) contains every word
  // of the search query in order — also tolerates 1 typo per word via a
  // simple edit-distance check on each word.
  const filteredVideos = (() => {
    const q = search.trim().toLowerCase();
    if (!q) return videos;
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
    return videos.filter((v) => {
      const hay = `${(v.title || '').toLowerCase()} ${v.video_id.toLowerCase()}`;
      return tokens.every((tok) => fuzzyMatch(hay, tok));
    });
  })();

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
    setAdding(true);
    try {
      const res = (await processVideo({ youtube_url: urlInput })) as unknown as Record<string, unknown>;
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

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a]">
      <Navbar />
      <div className="max-w-5xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">My Library</h1>

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
        <div className="flex gap-2 mb-4">
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
            disabled={adding || !urlInput}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {adding ? 'Adding...' : 'Add Video'}
          </button>
        </div>

        {/* Search box */}
        {videos.length > 0 && (
          <div className="mb-6">
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              placeholder="🔍 Search your videos..."
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
            />
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
            No videos match “{search}”.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
              {filteredVideos.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((v) => {
                const watchable = v.status === 'ready' || v.status === 'transcript_ready';
                const thumb = `https://i.ytimg.com/vi/${v.video_id}/mqdefault.jpg`;
                return (
                  <div
                    key={v.video_id}
                    onClick={() => watchable && navigate(`/watch/${v.video_id}`)}
                    className={`bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden transition group ${
                      watchable
                        ? 'cursor-pointer hover:shadow-lg hover:border-blue-400 dark:hover:border-blue-500'
                        : 'opacity-60'
                    }`}
                  >
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
                      {/* Play icon overlay on hover (only if watchable) */}
                      {watchable && (
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/30">
                          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center text-blue-600 text-2xl">
                            ▶
                          </div>
                        </div>
                      )}
                      {/* Status badge over thumbnail */}
                      <span
                        className={`absolute top-2 right-2 text-[10px] font-medium px-2 py-0.5 rounded ${
                          v.status === 'ready'
                            ? 'bg-green-600 text-white'
                            : v.status === 'transcript_ready'
                            ? 'bg-blue-600 text-white'
                            : v.status === 'processing'
                            ? 'bg-yellow-500 text-white'
                            : 'bg-red-600 text-white'
                        }`}
                      >
                        {v.status === 'transcript_ready'
                          ? 'watch now'
                          : v.status === 'ready'
                          ? 'ready'
                          : v.status === 'processing'
                          ? 'processing'
                          : 'failed'}
                      </span>
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
