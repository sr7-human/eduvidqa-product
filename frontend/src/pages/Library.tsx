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
  const navigate = useNavigate();

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

  // Poll processing videos every 2s
  useEffect(() => {
    const processing = videos.filter((v) => v.status === 'processing');
    if (processing.length === 0) return;
    const interval = setInterval(async () => {
      for (const v of processing) {
        try {
          const { status } = await getVideoStatus(v.video_id);
          if (status !== 'processing') {
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
    const vid = extractVideoId(urlInput);
    if (!vid) {
      toast.error('Invalid YouTube URL');
      return;
    }
    setAdding(true);
    try {
      const res = await processVideo({ youtube_url: urlInput });
      toast.success(res.message || 'Video submitted');
      setVideos((prev) => [
        {
          video_id: res.video_id,
          status: 'processing',
          title: res.title ?? null,
        },
        ...prev.filter((v) => v.video_id !== res.video_id),
      ]);
      setUrlInput('');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to add video');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-5xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4 text-gray-900">My Library</h1>

        {dueCount > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-amber-800">
                📚 {dueCount} question{dueCount > 1 ? 's' : ''} due for review
              </h3>
              <p className="text-sm text-amber-600">Keep your knowledge fresh</p>
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
        <div className="flex gap-2 mb-6">
          <input
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Paste YouTube URL..."
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
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

        {/* Video grid */}
        {loading ? (
          <p className="text-gray-500 text-center py-12">Loading...</p>
        ) : videos.length === 0 ? (
          <p className="text-gray-500 text-center py-12">
            No videos yet. Add your first lecture!
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {videos.map((v) => (
              <div
                key={v.video_id}
                onClick={() =>
                  v.status === 'ready' && navigate(`/watch/${v.video_id}`)
                }
                className={`bg-white border border-gray-200 rounded-lg p-4 transition ${
                  v.status === 'ready'
                    ? 'cursor-pointer hover:shadow-md hover:border-blue-300'
                    : 'opacity-60'
                }`}
              >
                <p className="font-medium text-gray-900 mb-2 break-all">
                  {v.title || v.video_id}
                </p>
                <span
                  className={`inline-block text-xs px-2 py-1 rounded ${
                    v.status === 'ready'
                      ? 'bg-green-100 text-green-700'
                      : v.status === 'processing'
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {v.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
