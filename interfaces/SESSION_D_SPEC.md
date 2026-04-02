# Session D: Frontend (React + YouTube IFrame + Chat)

## Status
- **Assigned:** Worker Session D
- **Dependencies:** NONE — can start immediately (uses mock API)
- **Last updated:** April 1, 2026

---

## ⚠️ MANAGER INSTRUCTIONS (READ THIS FIRST)

Read `/memories/session/munimi.md` for full project context (especially section 6: Frontend UI Spec).

You are building the FRONTEND. This can be done in parallel with Sessions A and B because you'll use mock API responses until the backend is ready.

Working directory: `/Users/shubhamkumar/eduvidqa-product/frontend/`
Existing setup: React 18 + Vite 5 + Tailwind CSS 3 + TypeScript
Dev server: `npm run dev` (localhost:5173)

Test video: `https://www.youtube.com/watch?v=3OmfTIf-SOU` (Khan Academy Unit Testing)

Read the existing frontend code first — there are already components from a previous iteration. You may reuse what makes sense and rebuild the rest.

**When done:** Update the "Worker Updates" section at the bottom of THIS file.

---

## Task 1: Layout + YouTube Player

### Split-screen layout
- Left panel (60%): YouTube video player + frame preview
- Right panel (40%): Chat interface
- Header: logo, nav links (Architecture, Paper Explainer, GitHub)
- Mobile (<768px): stack vertically

### YouTube IFrame API
```html
<!-- Load the API -->
<script src="https://www.youtube.com/iframe_api"></script>
```

```typescript
// Create player
const player = new YT.Player('player', {
  videoId: videoId,
  events: {
    onReady: onPlayerReady,
    onStateChange: onPlayerStateChange,
  }
});

// Poll timestamp every 500ms
setInterval(() => {
  if (player && player.getCurrentTime) {
    const time = player.getCurrentTime(); // seconds as float
    setCurrentTimestamp(time);
  }
}, 500);
```

### Frame preview
- Below the video player, show a placeholder: "Frame at {timestamp} will be shown here"
- For MVP, this is just a visual indicator. The actual frame comes from the backend in the answer response.

---

## Task 2: Auto-Timestamp Capture

### Behavior
1. Timestamp auto-updates every 500ms as the video plays
2. Display above chat input: `⏱️ Timestamp: 12:34` with an edit icon
3. When student CLICKS on the chat input → timestamp FREEZES (stop updating)
4. Student can manually edit the timestamp (click on it to enable text input)
5. When question is SUBMITTED → timestamp is sent with the request → then RESETS to auto-mode
6. Visual states:
   - Auto mode: timestamp has a pulsing dot indicator
   - Frozen: timestamp shows a lock icon
   - Manual edit: timestamp is an editable text field

### Implementation
```typescript
const [timestamp, setTimestamp] = useState(0);
const [autoMode, setAutoMode] = useState(true);
const [isEditing, setIsEditing] = useState(false);

// In the polling interval:
if (autoMode && !isEditing) {
  setTimestamp(player.getCurrentTime());
}

// On chat input focus:
setAutoMode(false);

// On question submit:
// ... send request ...
setAutoMode(true); // reset
```

---

## Task 3: Chat Interface

### Requirements
- Full chat history preserved (React state array of messages)
- Each message: `{role: "user"|"assistant", content: string, timestamp?: number, quality?: {clarity, ect, upt}}`
- User messages show: question text + timestamp badge
- Assistant messages show: answer text (markdown) + quality badges + source timestamps
- Quality badges: colored chips (green ≥4, amber 3-4, red <3)
  - `Clarity: 4.2` `ECT: 3.8` `UPT: 4.0`
- Source timestamps: clickable links that seek the video to that time
- Loading state: "Retrieving context → Generating answer → Scoring quality" with animated dots

### Mock API (for development)
When `VITE_MOCK_API=true`, return canned responses:
```typescript
const mockResponse = {
  answer: "The professor is explaining unit testing with the `get_route_score` function...",
  sources: [{start_time: 120, end_time: 140, relevance_score: 0.92}],
  quality_scores: {clarity: 4.2, ect: 3.8, upt: 4.0},
  model_name: "llama-4-scout-17b",
  generation_time: 2.3
};
```

### Real API call (when backend is ready)
```typescript
POST /api/ask
{
  youtube_url: "https://www.youtube.com/watch?v=3OmfTIf-SOU",
  question: "What is code coverage?",
  timestamp: 136,  // seconds
  skip_quality_eval: false
}
```

---

## Task 4: Dark Theme + Styling

Match the diagrams site aesthetic:
```css
:root {
  --bg: #0a0e1a;
  --bg2: #111827;
  --bg3: #1e293b;
  --text: #e2e8f0;
  --text2: #94a3b8;
  --accent: #6366f1;
  --accent2: #818cf8;
  --green: #10b981;
  --amber: #f59e0b;
  --rose: #f43f5e;
  --cyan: #06b6d4;
}
```

Tailwind config should use these colors. The existing `tailwind.config.js` may already have them.

---

## Task 5: Verify

- `npm run dev` works, shows the split-screen layout
- YouTube player loads and plays `3OmfTIf-SOU`
- Timestamp auto-updates in real-time
- Chat input works with mock API
- Quality badges render correctly
- Mobile layout stacks properly
- No console errors

---

## Worker Updates
<!-- Worker: Write your results below this line after completing tasks -->

**April 1, 2026 — All 5 Tasks Complete**

| Task | Status | Details |
|------|--------|---------|
| Task 1: Layout + YouTube Player | ✅ | Split-screen: 60% video (left) / 40% chat (right). YouTube IFrame API loads `3OmfTIf-SOU`. Mobile stacks vertically at `<768px`. |
| Task 2: Auto-Timestamp Capture | ✅ | Polls every 500ms. Auto mode (pulsing green dot), frozen on chat focus (🔒), manual edit via click, resets to auto on submit. |
| Task 3: Chat Interface | ✅ | Full message history with user/assistant bubbles. Markdown rendering (react-markdown + remark-gfm). Quality badges as colored chips. Source timestamps seek the video. Loading animation with 3 steps. Mock API via `VITE_MOCK_API=true`. |
| Task 4: Dark Theme + Styling | ✅ | All CSS vars from spec used. Tailwind config with `@tailwindcss/typography`. Matches diagrams site aesthetic. |
| Task 5: Verify | ✅ | `npx tsc --noEmit` = 0 errors. `npm run dev` → Vite v8 on localhost:5173. YouTube player loads and plays. |

**New components created:**
- `YouTubePlayer.tsx` — IFrame API wrapper with timestamp polling
- `TimestampDisplay.tsx` — auto/frozen/edit modes
- `ChatInterface.tsx` — full chat with messages, markdown, quality badges, source links, loading bubbles

**Modified:**
- `App.tsx` — split-screen layout with video/timestamp/chat state management
- `Header.tsx` — nav bar with Architecture, Paper Explainer, GitHub links
- `types/index.ts` — added ChatMessage, YTPlayer, updated AskResponse
- `api/client.ts` — updated mock response for Khan Academy test video

---

### ⚠️ MANAGER REVIEW (April 1, 2026)

**Layout CONFIRMED CORRECT at 1440px in real Chrome browser.**
Split-screen working: video left ~60%, chat right ~40%. Auto-timestamp updating. Frame preview placeholder visible. Chat input functional.

**Note:** Playwright's headless browser rendered this differently (stacked layout) — this was a false alarm. Always trust the user's actual Chrome screenshot over Playwright screenshots for layout verification.
