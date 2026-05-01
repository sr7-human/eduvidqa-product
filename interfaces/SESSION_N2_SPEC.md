# Session N2 — Quiz Frontend: Pause Toast + Review Page + Library Widget

## Status: � COMPLETE
## Dependencies: N1 ✅ (quiz panel + test-me + checkpoint markers on Watch page)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

Add the pause-detector toast (suggests quiz near checkpoints), build the Review page (spaced repetition queue), and add a review widget to the Library page. After this, the quiz frontend is complete.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/frontend/`  
**Dev server:** `npm run dev` → http://localhost:5173  
**Backend:** `cd .. && source .venv/bin/activate && uvicorn backend.app:app --port 8000`

**UX rules:**
- Pause toast: soft, auto-dismisses in 8s, NEVER on backward seek
- Review page: shows due questions, answer → SM-2 updates
- Library widget: shows count of due questions

---

## Current State

- **`src/pages/Watch.tsx` (272 lines)** — has checkpoints, TestMeButton, QuizPanel already wired (from N1). Has `currentTime`, `playerState` tracking.
- **`src/pages/Library.tsx` (145 lines)** — video grid + add video. No review widget yet.
- **`src/App.tsx` (42 lines)** — Review route exists but stub: "Coming soon"
- **`src/api/client.ts` (209 lines)** — has `getCheckpoints`, `getQuiz`, `submitAttempt`. **No review API functions yet.**
- **`src/types/index.ts` (117 lines)** — has `Checkpoint`, `QuizQuestion`, `AttemptResponse`. **No `ReviewQuestion` type yet.**
- **No `usePauseDetector` hook exists yet.**
- `react-hot-toast` already installed and `<Toaster>` in App.tsx.

## Backend Review Endpoints Available (from M2)

```
GET  /api/users/me/review
  → {due_count: number, questions: [{id, video_id, video_title, question_text, options, next_review_at}]}

POST /api/review/{questionId}/attempt   body: {selected_answer: "A"|"B"|"C"|"D"}
  → {is_correct, correct_answer, explanation}
```

---

## Task 1: Add ReviewQuestion Type

**File:** `src/types/index.ts` — add before the `declare global` block:

```typescript
export interface ReviewQuestion {
  id: string;
  video_id: string;
  video_title: string | null;
  question_text: string;
  options: string[];
  next_review_at: string;
}
```

---

## Task 2: Add Review API Functions

**File:** `src/api/client.ts` — add:

```typescript
import type { ReviewQuestion } from '../types';

export async function getReviewQueue(): Promise<{due_count: number; questions: ReviewQuestion[]}> {
  return request('/api/users/me/review');
}

export async function submitReviewAttempt(questionId: string, selectedAnswer: string): Promise<{is_correct: boolean; correct_answer: string; explanation: string}> {
  return request(`/api/review/${questionId}/attempt`, {
    method: 'POST',
    body: JSON.stringify({ selected_answer: selectedAnswer }),
  });
}
```

---

## Task 3: Create Pause Detector Hook

**Create file:** `src/hooks/usePauseDetector.ts`

```typescript
import { useEffect, useRef } from 'react';
import type { Checkpoint } from '../types';

export function usePauseDetector(
  playerState: 'playing' | 'paused' | 'other',
  currentTimestamp: number,
  checkpoints: Checkpoint[],
  onNearCheckpoint: (cp: Checkpoint) => void,
) {
  const shownCps = useRef<Set<string>>(new Set());
  const lastTs = useRef(currentTimestamp);

  useEffect(() => {
    // Detect backward seek — don't trigger toast
    const seekedBack = currentTimestamp < lastTs.current - 5;
    lastTs.current = currentTimestamp;
    if (seekedBack) return;

    if (playerState !== 'paused') return;

    // Find nearest unseen checkpoint within ±30 seconds
    const nearest = checkpoints.find(
      cp => Math.abs(cp.timestamp_seconds - currentTimestamp) <= 30 && !shownCps.current.has(cp.id)
    );

    if (nearest) {
      shownCps.current.add(nearest.id);
      onNearCheckpoint(nearest);
    }
  }, [playerState, currentTimestamp]);
}
```

---

## Task 4: Wire Pause Toast in Watch Page

**File:** `src/pages/Watch.tsx` — add:

```typescript
import toast from 'react-hot-toast';
import { usePauseDetector } from '../hooks/usePauseDetector';
```

The Watch page already tracks `currentTime` and player state. You need to determine `playerState` — check how the YouTubePlayer component reports state changes. Common pattern:

```typescript
// Determine player state from YT API
const [playerState, setPlayerState] = useState<'playing' | 'paused' | 'other'>('other');

// In the player state change handler:
// YT.PlayerState.PLAYING = 1, PAUSED = 2
const handleStateChange = (state: number) => {
  if (state === 1) setPlayerState('playing');
  else if (state === 2) setPlayerState('paused');
  else setPlayerState('other');
};
```

Then add the hook:

```typescript
usePauseDetector(playerState, currentTime, checkpoints, (cp) => {
  toast(
    (t) => (
      <div className="flex items-center gap-3">
        <span className="text-sm">📚 Test yourself on "{cp.topic_label}"?</span>
        <button
          className="px-3 py-1 bg-blue-600 text-white rounded text-sm whitespace-nowrap"
          onClick={() => { toast.dismiss(t.id); handleQuizReady(cp.timestamp_seconds); }}
        >
          Take quiz
        </button>
        <button className="text-gray-400 text-sm" onClick={() => toast.dismiss(t.id)}>
          ✕
        </button>
      </div>
    ),
    { duration: 8000, position: 'bottom-center' }
  );
});
```

Where `handleQuizReady` fetches the quiz and opens the panel (same as TestMeButton does).

---

## Task 5: Create Review Page

**Create file:** `src/pages/Review.tsx`

```typescript
import { useState, useEffect } from 'react';
import { Navbar } from '../components/Navbar';
import { getReviewQueue, submitReviewAttempt } from '../api/client';
import type { ReviewQuestion } from '../types';

export function Review() {
  const [questions, setQuestions] = useState<ReviewQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<{is_correct: boolean; correct_answer: string; explanation: string} | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [stats, setStats] = useState({ correct: 0, total: 0 });

  useEffect(() => {
    getReviewQueue()
      .then(data => setQuestions(data.questions))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const question = questions[currentIdx];
  const isDone = !loading && (questions.length === 0 || currentIdx >= questions.length);

  const handleAnswer = async (answer: string) => {
    if (!question) return;
    setSelected(answer);
    setSubmitting(true);
    try {
      const res = await submitReviewAttempt(question.id, answer);
      setResult(res);
      setStats(prev => ({ correct: prev.correct + (res.is_correct ? 1 : 0), total: prev.total + 1 }));
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleNext = () => {
    setCurrentIdx(prev => prev + 1);
    setResult(null);
    setSelected(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-2xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">Review Queue</h1>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : isDone ? (
          <div className="text-center py-16">
            {stats.total > 0 ? (
              <>
                <p className="text-3xl font-bold mb-2">{stats.correct}/{stats.total}</p>
                <p className="text-gray-500 mb-4">Questions reviewed today</p>
              </>
            ) : null}
            <p className="text-xl">🎉 All caught up!</p>
            <p className="text-gray-500">No questions due for review.</p>
          </div>
        ) : question ? (
          <div className="bg-white rounded-xl shadow p-6">
            {/* Video context */}
            <p className="text-xs text-gray-400 mb-1">{question.video_title || question.video_id}</p>

            {/* Question */}
            <p className="font-medium text-lg mb-4">{question.question_text}</p>

            {/* Options */}
            <div className="space-y-2 mb-4">
              {question.options.map((opt, i) => {
                const letter = String.fromCharCode(65 + i);
                const isSelected = selected === letter;
                const isCorrect = result?.correct_answer === letter;
                const isWrong = isSelected && result && !result.is_correct;

                let bg = 'bg-gray-50 hover:bg-gray-100 border-gray-200';
                if (result) {
                  if (isCorrect) bg = 'bg-green-100 border-green-500';
                  else if (isWrong) bg = 'bg-red-100 border-red-500';
                }

                return (
                  <button
                    key={letter}
                    onClick={() => !result && !submitting && handleAnswer(letter)}
                    disabled={!!result || submitting}
                    className={`w-full text-left p-3 rounded-lg border ${bg} disabled:cursor-default`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>

            {/* Result */}
            {result && (
              <div className={`p-3 rounded-lg mb-4 ${result.is_correct ? 'bg-green-50' : 'bg-red-50'}`}>
                <p className="font-medium">{result.is_correct ? '✅ Correct!' : '❌ Incorrect'}</p>
                <p className="text-sm text-gray-600 mt-1">{result.explanation}</p>
              </div>
            )}

            {/* Next */}
            {result && (
              <button onClick={handleNext} className="w-full py-2 bg-blue-600 text-white rounded-lg">
                {currentIdx === questions.length - 1 ? 'Finish' : 'Next question'}
              </button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
```

---

## Task 6: Update Router — Replace Review Stub

**File:** `src/App.tsx`

Replace the inline `Review` stub function with the real import:

```typescript
import { Review } from './pages/Review';
```

Remove the placeholder:
```typescript
// DELETE THIS:
function Review() {
  return (...Coming soon...);
}
```

---

## Task 7: Review Widget on Library Page

**File:** `src/pages/Library.tsx` — add at the top of the page content (below Navbar, above "My Library" heading):

```typescript
import { Link } from 'react-router-dom';
import { getReviewQueue } from '../api/client';

// Add state:
const [dueCount, setDueCount] = useState(0);

// Add useEffect:
useEffect(() => {
  getReviewQueue().then(data => setDueCount(data.due_count)).catch(() => {});
}, []);

// Add JSX above the video grid:
{dueCount > 0 && (
  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 flex items-center justify-between">
    <div>
      <h3 className="font-semibold text-amber-800">📚 {dueCount} question{dueCount > 1 ? 's' : ''} due for review</h3>
      <p className="text-sm text-amber-600">Keep your knowledge fresh</p>
    </div>
    <Link to="/review" className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm">
      Review now
    </Link>
  </div>
)}
```

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `src/types/index.ts` | Add `ReviewQuestion` type |
| 2 | `src/api/client.ts` | Add `getReviewQueue`, `submitReviewAttempt` |
| 3 | `src/hooks/usePauseDetector.ts` | Pause detector hook (new) |
| 4 | `src/pages/Watch.tsx` | Wire pause toast |
| 5 | `src/pages/Review.tsx` | Full review page (new) |
| 6 | `src/App.tsx` | Import real Review, remove stub |
| 7 | `src/pages/Library.tsx` | Add review widget |

---

## Self-Critical Audit Plan

### Audit 1: Build passes
```bash
cd frontend && npm run build 2>&1 | tail -5
```
**PASS:** Zero errors.

### Audit 2: ReviewQuestion type exists
```bash
grep -n "ReviewQuestion" src/types/index.ts
```
**PASS:** Interface defined.

### Audit 3: API functions exist
```bash
grep -n "getReviewQueue\|submitReviewAttempt" src/api/client.ts
```
**PASS:** Both defined.

### Audit 4: Pause detector hook exists
```bash
ls src/hooks/usePauseDetector.ts && grep -c "onNearCheckpoint" src/hooks/usePauseDetector.ts
```
**PASS:** File exists, has the callback.

### Audit 5: Watch page uses pause detector
```bash
grep -n "usePauseDetector\|pause.*toast\|📚" src/pages/Watch.tsx | head -5
```
**PASS:** Hook imported and used with toast.

### Audit 6: Review page is real (not stub)
```bash
wc -l src/pages/Review.tsx && grep -c "getReviewQueue\|submitReviewAttempt" src/pages/Review.tsx
```
**PASS:** File > 50 lines, uses both API functions.

### Audit 7: App.tsx imports real Review
```bash
grep "Review" src/App.tsx
```
**PASS:** Shows `import { Review } from './pages/Review'`. No inline stub function.

### Audit 8: Library has review widget
```bash
grep -n "dueCount\|review.*widget\|📚.*due" src/pages/Library.tsx | head -5
```
**PASS:** Shows due count state and review widget JSX.

### Audit 9: Review page renders
Navigate to `/review` in browser.  
**PASS:** Shows "Review Queue" heading. Either due questions or "All caught up!" empty state.

### Audit 10: Pause toast doesn't fire on backward seek
In Watch page: play video, seek backward past a checkpoint.  
**PASS:** No toast appears.

### Audit 11: Library widget links to review
Navigate to `/library`. If due questions exist, amber banner visible with "Review now" link.  
**PASS:** Link navigates to `/review`.

---

## Worker Log
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->

### Audit 1 — Build passes ✅
```
vite v5.4.21 building for production...
✓ 1021 modules transformed.
dist/assets/index-CMnN3NOf.css   51.70 kB │ gzip:   7.75 kB
dist/assets/index-nrwZepIh.js   759.99 kB │ gzip: 231.00 kB
✓ built in 1.74s
```

### Audit 2 — ReviewQuestion type ✅
```
95:export interface ReviewQuestion {
```

### Audit 3 — API functions ✅
```
199:export async function getReviewQueue(): Promise<{
208:export async function submitReviewAttempt(
```

### Audit 4 — Pause detector hook ✅
```
src/hooks/usePauseDetector.ts
3   (matches of onNearCheckpoint)
```

### Audit 5 — Watch wires pause detector + toast ✅
```
19:import { usePauseDetector } from '../hooks/usePauseDetector';
81:  usePauseDetector(playerState, currentTime, checkpoints, (cp) => {
86:            📚 Test yourself on "{cp.topic_label}"?
```

### Audit 6 — Review page is real ✅
```
137 src/pages/Review.tsx
3   (uses getReviewQueue + submitReviewAttempt)
```

### Audit 7 — App.tsx imports real Review (no stub) ✅
```
import { Review } from './pages/Review';
          <Route path="/review" element={<ProtectedRoute><Review /></ProtectedRoute>} />
```

### Audit 8 — Library has review widget ✅
```
19:  const [dueCount, setDueCount] = useState(0);
94:        {dueCount > 0 && (
98:                📚 {dueCount} question{dueCount > 1 ? 's' : ''} due for review
```

### Audits 9–11 (runtime / browser checks)

**Audit 9 — Review page renders ✅**
Navigated to `/review` (logged-in test user, backend offline). Page renders:
- `<h1>Review Queue</h1>`
- "🎉 All caught up!" + "No questions due for review."
- Empty state correctly triggered when API call fails (catch swallows, `questions=[]`).

**Audit 10 — Pause toast doesn't fire on backward seek**
Code-verified (no real video to drive runtime test without backend). `usePauseDetector`:
```ts
const seekedBack = currentTimestamp < lastTs.current - 5;
lastTs.current = currentTimestamp;
if (seekedBack) return;
if (playerState !== 'paused') return;
```
Backward seek branches return BEFORE the paused-check, so the toast can never fire on a backward jump.

**Audit 11 — Library widget visible + links to /review ✅**
Stubbed `getReviewQueue → {due_count: 7}`, navigated to `/library`. DOM shows:
```
heading "📚 7 questions due for review"
paragraph "Keep your knowledge fresh"
link "Review now" → /url: /review
```
Clicking the "Review now" link navigated to `/review` (verified `location.pathname === '/review'`).

### Bug found + fixed during runtime check
- **`html, body { color: #e2e8f0 }`** in `src/index.css` (intended for dark theme) leaked into the new Review page. The `<h1>Review Queue</h1>` and "All caught up!" text rendered nearly invisible on `bg-gray-50`.
- Fix: added `text-gray-900` on the Review page heading and on the empty-state + question-card containers (matches the Library page convention). Verified visually with screenshot after fix.

### Implementation notes
- Extended `YouTubePlayer` with optional `onStateChange?: (state: number) => void` prop (refs-based to avoid player re-creation), wired into `Watch.tsx` to drive `playerState`.
- Pause-toast `Take quiz` handler fetches the quiz via `getQuiz(videoId, cp.timestamp_seconds)` and reuses existing `handleQuizReady` to open the right-panel `QuizPanel`.
