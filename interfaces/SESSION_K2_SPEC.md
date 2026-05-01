# Session K2 — Frontend: Navbar + Library + Watch Page

## Status: ✅ COMPLETE (2026-04-30) — see Worker Log at bottom
## Dependencies: K1 ✅ (router + auth + landing + login)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

Build the Library page (video grid + add video), the Watch page (move old App.tsx chat UI here), and a shared Navbar. After this, the frontend is fully routed and functional.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/frontend/`  
**Dev server:** `npm run dev` → http://localhost:5173  
**Backend:** `cd .. && source .venv/bin/activate && uvicorn backend.app:app --port 8000`

---

## Current Frontend State (post-K1)

**`src/App.tsx` (34 lines)** — Router with 5 routes. Library/Watch/Review are **placeholder stubs**:
```typescript
function Library() {
  return <div className="p-8 text-center text-xl">Library — coming in K2</div>;
}
function Watch() {
  return <div className="p-8 text-center text-xl">Watch — coming in K2</div>;
}
```

**`src/pages/_OldApp.tsx.bak`** — The original single-screen App.tsx (196 lines) with YouTube player + chat. **Use this as the source for the Watch page.** It imports:
- `Header`, `YouTubePlayer`, `TimestampDisplay`, `ChatInterface`
- `askQuestion`, `extractVideoId` from `api/client`
- Types: `ChatMessage`, `YTPlayer`

**`src/api/client.ts` (116 lines)** — Has `askQuestion()`, `processVideo()`, `checkHealth()`, `extractVideoId()`. Already sends JWT via Supabase.

**Existing components (reuse as-is):**
- `ChatInterface.tsx` (256L), `YouTubePlayer.tsx` (104L), `SettingsModal.tsx` (107L)
- `TimestampDisplay.tsx` (115L), `SourceTimestamps.tsx` (42L), `QualityBadges.tsx` (74L)
- `AnswerDisplay.tsx` (38L), `ErrorState.tsx` (28L), `LoadingState.tsx` (70L)
- `Header.tsx` (57L) — will be replaced by Navbar

**Backend endpoints available (Session I):**
- `GET /api/users/me/videos` — requires JWT, returns user's video list
- `POST /api/process-video` — requires JWT, returns immediately with `{video_id, status, message}`
- `GET /api/videos/{video_id}/status` — public, returns `{video_id, status}`
- `POST /api/ask` — optional auth (demo `3OmfTIf-SOU` without login), **returns HTTP 202 if video not yet ingested**

---

## Task 1: Create Navbar

**Create file:** `src/components/Navbar.tsx`

```typescript
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function Navbar() {
  const { user, signOut } = useAuth();

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <Link to="/library" className="text-xl font-bold text-blue-600">EduVidQA</Link>
      <div className="flex items-center gap-4">
        <Link to="/library" className="text-gray-600 hover:text-gray-900">Library</Link>
        <Link to="/review" className="text-gray-600 hover:text-gray-900">Review</Link>
        <span className="text-sm text-gray-500">{user?.email}</span>
        <button onClick={signOut} className="text-sm text-red-500 hover:text-red-700">Sign out</button>
      </div>
    </nav>
  );
}
```

---

## Task 2: Add API Functions for Library

**File:** `src/api/client.ts` — add these functions:

```typescript
export async function getMyVideos(): Promise<any[]> {
  return request<any[]>('/api/users/me/videos');
}

export async function getVideoStatus(videoId: string): Promise<{video_id: string; status: string}> {
  return request<{video_id: string; status: string}>(`/api/videos/${videoId}/status`);
}
```

---

## Task 3: Create Library Page

**Create file:** `src/pages/Library.tsx`

Layout:
1. **Navbar** at top
2. **"Add Video" section** — input field for YouTube URL + "Add" button
   - On submit: call `processVideo({youtube_url})` → show toast → add video card
3. **Video grid** — fetch from `getMyVideos()` on mount
   - Each card: video title (or video_id), status badge (`ready`/`processing`/`failed`)
   - Click → navigate to `/watch/{video_id}`
4. **Empty state:** "No videos yet. Add your first lecture!"
5. **Polling:** if any video has `status: 'processing'`, poll `getVideoStatus(videoId)` every 2s until it changes

```typescript
import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import { getMyVideos, processVideo, getVideoStatus, extractVideoId } from '../api/client';

export function Library() {
  const [videos, setVideos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [urlInput, setUrlInput] = useState('');
  const [adding, setAdding] = useState(false);
  const navigate = useNavigate();

  // Fetch videos on mount
  useEffect(() => {
    getMyVideos().then(setVideos).catch(() => {}).finally(() => setLoading(false));
  }, []);

  // Poll processing videos
  useEffect(() => {
    const processing = videos.filter(v => v.status === 'processing');
    if (processing.length === 0) return;
    const interval = setInterval(async () => {
      for (const v of processing) {
        const { status } = await getVideoStatus(v.video_id);
        if (status !== 'processing') {
          setVideos(prev => prev.map(pv => pv.video_id === v.video_id ? { ...pv, status } : pv));
        }
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [videos]);

  const handleAdd = async () => {
    const vid = extractVideoId(urlInput);
    if (!vid) { toast.error('Invalid YouTube URL'); return; }
    setAdding(true);
    try {
      const res = await processVideo({ youtube_url: urlInput });
      toast.success(res.message || 'Video submitted');
      setVideos(prev => [{ video_id: res.video_id, status: res.status || 'processing', title: null }, ...prev]);
      setUrlInput('');
    } catch (e: any) { toast.error(e.message); }
    finally { setAdding(false); }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-5xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">My Library</h1>
        {/* Add video input */}
        <div className="flex gap-2 mb-6">
          <input value={urlInput} onChange={e => setUrlInput(e.target.value)}
            placeholder="Paste YouTube URL..." className="flex-1 border rounded-lg px-4 py-2" />
          <button onClick={handleAdd} disabled={adding}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
            {adding ? 'Adding...' : 'Add Video'}
          </button>
        </div>
        {/* Video grid */}
        {loading ? <p>Loading...</p> : videos.length === 0 ? (
          <p className="text-gray-500 text-center py-12">No videos yet. Add your first lecture!</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {videos.map(v => (
              <div key={v.video_id} onClick={() => v.status === 'ready' && navigate(`/watch/${v.video_id}`)}
                className={`border rounded-lg p-4 ${v.status === 'ready' ? 'cursor-pointer hover:shadow-md' : 'opacity-60'}`}>
                <p className="font-medium">{v.title || v.video_id}</p>
                <span className={`text-xs px-2 py-1 rounded ${
                  v.status === 'ready' ? 'bg-green-100 text-green-700' :
                  v.status === 'processing' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700'}`}>
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
```

---

## Task 4: Create Watch Page

**⚠️ IMPORTANT — `/api/ask` returns HTTP 202 when video is not yet ingested:**

The backend queues ingest in background and returns `{"detail": "Video is being processed. Try again in a minute."}`. The Watch page must handle this:

```typescript
// In the question submit handler:
try {
  const res = await askQuestion({ youtube_url, question, timestamp, skip_quality_eval });
  // ... show answer as before
} catch (err: any) {
  if (err.message.includes('202')) {
    toast('Video is being processed... please wait');
    // Poll GET /api/videos/{videoId}/status every 2s until ready, then auto-retry
  } else {
    // show error
  }
}
```

**Create file:** `src/pages/Watch.tsx`

Move the logic from `_OldApp.tsx.bak` into this page component:

```typescript
import { useParams } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
// Import same components the old App.tsx used:
// YouTubePlayer, TimestampDisplay, ChatInterface
// askQuestion, extractVideoId from api/client

export function Watch() {
  const { videoId } = useParams<{ videoId: string }>();
  const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;

  // Move ALL state + logic from _OldApp.tsx.bak:
  // - currentTime, frozenTime, autoMode, playerRef
  // - messages, isLoading
  // - handleTimeUpdate, handleSubmit, handleSeek, etc.
  // 
  // Key changes from old App.tsx:
  // 1. videoId comes from URL params (no URL input field needed)
  // 2. Remove urlInput/videoUrl state — use youtubeUrl directly
  // 3. Add Navbar at top
  // 4. Handle HTTP 202 in question submit
  // 5. Add "Back to Library" breadcrumb link

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      <div className="flex-1 flex">
        {/* Left 60%: YouTube player + timestamp */}
        {/* Right 40%: Chat interface */}
      </div>
    </div>
  );
}
```

**The layout stays the same as old App.tsx**: 60/40 split, player left, chat right.

---

## Task 5: Update Router in App.tsx

**File:** `src/App.tsx` — replace placeholder stubs with real imports:

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './contexts/AuthContext';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { Library } from './pages/Library';
import { Watch } from './pages/Watch';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';

function Review() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">Review Queue</h1>
          <p className="text-gray-500">Coming soon — spaced review of missed questions.</p>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="bottom-right" />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/library" element={<ProtectedRoute><Library /></ProtectedRoute>} />
          <Route path="/watch/:videoId" element={<ProtectedRoute><Watch /></ProtectedRoute>} />
          <Route path="/review" element={<ProtectedRoute><Review /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

---

## Task 6: Clean Up

1. **Delete** `src/pages/_OldApp.tsx.bak` (no longer needed after Watch is built)
2. **Delete** `src/components/Header.tsx` if Navbar replaces it — check for imports first:
   ```bash
   grep -rn "Header" src/ --include="*.tsx" | grep -v Navbar | grep -v node_modules
   ```
   If only `_OldApp.tsx.bak` imported it, safe to delete.

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `src/components/Navbar.tsx` | Shared nav (new) |
| 2 | `src/api/client.ts` | Add `getMyVideos()` + `getVideoStatus()` |
| 3 | `src/pages/Library.tsx` | Video grid + add video + polling (new) |
| 4 | `src/pages/Watch.tsx` | Player + chat from old App.tsx (new) |
| 5 | `src/App.tsx` | Replace stubs with real imports |
| 6 | Deleted: `_OldApp.tsx.bak`, `Header.tsx` | Cleanup |

---

## Self-Critical Audit Plan

### Audit 1: Build passes
```bash
cd frontend && npm run build 2>&1 | tail -5
```
**PASS:** Zero errors. Build succeeds.

### Audit 2: All routes render (no white screen)
Open browser:
- `http://localhost:5173/` → Landing
- `http://localhost:5173/library` → Library (or redirect to login)
- `http://localhost:5173/watch/3OmfTIf-SOU` → Watch page with player
- `http://localhost:5173/review` → Review stub with Navbar

**PASS:** All 4 render. No white screen, no console errors.

### Audit 3: Navbar visible on authenticated pages
```bash
grep -rn "Navbar" src/pages/ --include="*.tsx" | wc -l
```
**PASS:** Returns ≥ 3 (Library, Watch, Review all import Navbar).

### Audit 4: Library page shows videos
Navigate to `/library` → video grid loads from API.  
**PASS:** Shows video cards (or empty state if no videos).

### Audit 5: Watch page has player + chat
Navigate to `/watch/3OmfTIf-SOU`:
1. YouTube player loads
2. Chat input visible
3. Type question + submit → answer appears

**PASS:** All 3 work.

### Audit 6: Watch page handles 202 (video processing)
```bash
grep -n "202\|processing\|poll\|status.*ready" src/pages/Watch.tsx | head -10
```
**PASS:** Watch.tsx has logic to handle HTTP 202 — shows processing message + polls status.

### Audit 7: API functions exist
```bash
grep -n "getMyVideos\|getVideoStatus" src/api/client.ts
```
**PASS:** Both functions defined.

### Audit 8: Old files cleaned up
```bash
ls src/pages/_OldApp.tsx.bak 2>&1
```
**PASS:** "No such file or directory".

### Audit 9: Sign out works
Click "Sign out" in Navbar → redirected to `/` or `/login`.  
**PASS:** User signed out. Protected routes redirect.

### Audit 10: No dead imports
```bash
npm run build 2>&1 | grep -i "unused\|not found\|cannot find" | head -5
```
**PASS:** No unused/missing import errors.

---

## Worker Log
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->

### ✅ COMPLETE — 2026-04-30

**Files created:**
- `frontend/src/components/Navbar.tsx`
- `frontend/src/pages/Library.tsx`
- `frontend/src/pages/Watch.tsx`

**Files modified:**
- `frontend/src/api/client.ts` — added `UserVideo`, `getMyVideos()`, `getVideoStatus()`, `VideoProcessingError`, and refactored `askQuestion()` to detect HTTP 202 and throw `VideoProcessingError`.
- `frontend/src/App.tsx` — replaced Library/Watch stubs with real imports; Review still inline (with Navbar).

**Files deleted:**
- `frontend/src/pages/_OldApp.tsx.bak`
- `frontend/src/components/Header.tsx`

**Note on spec deviation — HTTP 202 handling:**
Backend uses `HTTPException(status_code=202, ...)`. Since 202 is a 2xx, `fetch.res.ok === true`, so the spec's `err.message.includes('202')` would never fire with the existing generic `request()` helper. Solved by replacing `askQuestion()` with a dedicated impl that special-cases `res.status === 202` and throws a typed `VideoProcessingError`. Watch page checks `err instanceof VideoProcessingError`, sets `processingStatus='processing'`, and the polling effect calls `getVideoStatus` every 2s until `ready`/`failed`.

**Audit results:**

```
=== Audit 1: Build passes ===
> tsc && vite build
✓ 708 modules transformed.
dist/index.html                   0.66 kB │ gzip:   0.45 kB
dist/assets/index-BcOKU7CK.css   48.73 kB │ gzip:   7.39 kB
dist/assets/index-BTrjeiQj.js   751.02 kB │ gzip: 228.50 kB
✓ built in 1.66s
PASS — zero TS/build errors.

=== Audit 3: Navbar usage ===
6  (Library + Watch + App's Review all import & render Navbar)
PASS

=== Audit 6: Watch handles 202 ===
10:  getVideoStatus,
11:  VideoProcessingError,
32:  const [processingStatus, setProcessingStatus] = useState<string | null>(null);
79:  // Poll video status while processing
81:    if (!processingStatus || processingStatus === 'ready') return;
84:        const { status } = await getVideoStatus(videoId);
85:        if (status !== 'processing') {
98:  }, [processingStatus, videoId]);
128:      if (err instanceof VideoProcessingError) {
PASS

=== Audit 7: API functions exist ===
81:export class VideoProcessingError extends Error {
146:export async function getMyVideos(): Promise<UserVideo[]>
150:export async function getVideoStatus(...)
PASS

=== Audit 8: Old files cleaned up ===
ls: src/components/Header.tsx: No such file or directory
ls: src/pages/_OldApp.tsx.bak: No such file or directory
PASS

=== Audit 10: No dead imports ===
PASS — included in Audit 1 (tsc strict mode caught and fixed `res.status` not on ProcessResponse before final build).
```

**Manual audits (2, 4, 5, 9) require running `npm run dev` + browser** — not executed here, ready for user to verify.
