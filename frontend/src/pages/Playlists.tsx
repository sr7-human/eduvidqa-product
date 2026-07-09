import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import {
  getPlaylists,
  getPlaylist,
  resumePlaylist,
  deletePlaylist,
  processVideo,
  type Playlist,
  type PlaylistDetail,
} from '../api/client';

const statusColor = (s: string) =>
  s === 'ready'
    ? 'bg-green-600'
    : s === 'failed'
    ? 'bg-red-600'
    : s === 'transcript_ready'
    ? 'bg-blue-600'
    : s === 'processing'
    ? 'bg-yellow-500'
    : 'bg-gray-400';

export function Playlists() {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [urlInput, setUrlInput] = useState('');
  const [adding, setAdding] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, PlaylistDetail>>({});

  const load = () => {
    getPlaylists()
      .then(setPlaylists)
      .catch((e) => toast.error(`Failed to load playlists: ${e.message}`))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  // Poll while any playlist is still ingesting.
  useEffect(() => {
    const anyProcessing = playlists.some((p) => p.ready + p.failed < p.total);
    if (!anyProcessing) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [playlists]);

  const handleAdd = async () => {
    if (!/[?&]list=/.test(urlInput)) {
      toast.error('Paste a playlist URL (it must contain &list=…)');
      return;
    }
    setAdding(true);
    try {
      const res = (await processVideo({ youtube_url: urlInput })) as unknown as Record<string, unknown>;
      toast.success(String(res.message ?? 'Playlist queued'));
      setUrlInput('');
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to add playlist');
    } finally {
      setAdding(false);
    }
  };

  const toggle = async (id: string) => {
    if (expanded[id]) {
      setExpanded((p) => {
        const c = { ...p };
        delete c[id];
        return c;
      });
      return;
    }
    try {
      const d = await getPlaylist(id);
      setExpanded((p) => ({ ...p, [id]: d }));
    } catch {
      toast.error('Failed to load playlist details');
    }
  };

  const handleResume = async (id: string) => {
    try {
      const r = await resumePlaylist(id);
      toast.success(r.message);
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Resume failed');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Remove this playlist? (The videos stay in your library.)')) return;
    const prev = playlists;
    setPlaylists((p) => p.filter((x) => x.id !== id));
    try {
      await deletePlaylist(id);
    } catch {
      setPlaylists(prev);
      toast.error('Delete failed');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a]">
      <Navbar />
      <div className="max-w-3xl mx-auto p-6 pb-32">
        <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Playlists</h1>

        <div className="flex gap-2 mb-2">
          <input
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Paste a YouTube playlist URL (…&list=…)"
            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
          />
          <button
            onClick={handleAdd}
            disabled={adding || !urlInput.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 whitespace-nowrap"
          >
            {adding ? 'Adding…' : 'Add playlist'}
          </button>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-6">
          Videos ingest one-by-one. If it stops on a daily API limit, click <b>Resume</b> later —
          finished videos are skipped automatically.
        </p>

        {loading ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-12">Loading…</p>
        ) : playlists.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-12">
            No playlists yet. Paste one above.
          </p>
        ) : (
          <div className="space-y-4">
            {playlists.map((p) => {
              const pct = p.total ? Math.round((p.ready / p.total) * 100) : 0;
              return (
                <div
                  key={p.id}
                  className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <button onClick={() => toggle(p.id)} className="text-left flex-1 min-w-0">
                      <div className="font-semibold text-gray-900 dark:text-white truncate">
                        {p.title || p.youtube_playlist_id}
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        {p.ready}/{p.total} ready
                        {p.failed ? ` · ${p.failed} failed` : ''}
                        {p.processing ? ` · ${p.processing} processing` : ''}
                      </div>
                    </button>
                    <div className="flex items-center gap-2 shrink-0">
                      {p.ready < p.total && (
                        <button
                          onClick={() => handleResume(p.id)}
                          className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
                        >
                          Resume
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(p.id)}
                        className="px-2 py-1.5 text-sm text-gray-400 hover:text-red-500"
                        aria-label="Remove playlist"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  <div className="mt-3 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div className="h-full bg-green-600 transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  {expanded[p.id] && (
                    <div className="mt-4 space-y-1 max-h-72 overflow-y-auto">
                      {expanded[p.id].videos.map((v) => (
                        <div key={v.video_id} className="flex items-center gap-2 text-sm">
                          <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${statusColor(v.status)}`} />
                          <span className="text-gray-400 w-7 shrink-0">{v.position + 1}.</span>
                          <span className="flex-1 truncate text-gray-700 dark:text-gray-300">
                            {v.title || v.video_id}
                          </span>
                          <span className="text-xs text-gray-500 shrink-0">{v.status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
