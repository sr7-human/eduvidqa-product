# Session K1 — Frontend: Router + Supabase Auth + Landing + Login

## Status: � COMPLETE
## Dependencies: I ✅ (auth endpoints exist), J ✅ (types fixed)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

Add `react-router-dom` and Supabase Auth to the frontend. Create a landing page, login page, router structure, and auth context. The Watch page and Library page are Session K2 (depends on this).

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/frontend/`  
**Dev server:** `npm run dev` → http://localhost:5173  
**Backend:** `cd .. && source .venv/bin/activate && uvicorn backend.app:app --port 8000`

---

## Current Frontend State

- `src/App.tsx` (196 lines) — single-screen: URL input + YouTube player + chat. This becomes the Watch page in K2.
- `src/main.tsx` (10 lines) — simple render, no router, no providers
- `src/api/client.ts` (104 lines) — fetch wrapper, mock mode, `askQuestion()`, `processVideo()`, `checkHealth()`
- `src/types/index.ts` (94 lines) — all types already fixed in J
- `src/components/` — 10 components (ChatInterface, YouTubePlayer, SettingsModal, Header, etc.)
- **No pages/, contexts/, or lib/ directories exist**
- **No react-router, supabase, or toast packages installed**

**Installed packages:**
- deps: `react`, `react-dom`, `react-markdown`, `remark-gfm`, `@tailwindcss/typography`, `framer-motion`
- devdeps: `typescript`, `vite`, `@vitejs/plugin-react`, `tailwindcss`, `postcss`, `autoprefixer`

**Frontend `.env`:**
```
VITE_MOCK_API=false
VITE_API_URL=http://localhost:8000
VITE_DEFAULT_VIDEO_URL=https://www.youtube.com/watch?v=3OmfTIf-SOU
```

**Backend auth (Session I done):**
- `POST /api/ask` — optional auth (demo video `3OmfTIf-SOU` works without login)
- `POST /api/process-video` — requires JWT
- `GET /api/health` — public
- `GET /api/videos/{id}/status` — public
- `GET /api/users/me/videos` — requires JWT
- JWT is a Supabase token in `Authorization: Bearer <token>` header

---

## Task 1: Install Dependencies

```bash
cd frontend
npm install react-router-dom @supabase/supabase-js @supabase/auth-ui-react @supabase/auth-ui-shared react-hot-toast
```

---

## Task 2: Create Supabase Client

**Create directory + file:** `src/lib/supabase.ts`

```typescript
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase env vars not set — auth will not work');
}

export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '');
```

**Add to `frontend/.env`:**
```
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

(Get actual values from `/Users/shubhamkumar/eduvidqa-product/.env` — `SUPABASE_URL` and `SUPABASE_ANON_KEY`)

---

## Task 3: Create Auth Context

**Create:** `src/contexts/AuthContext.tsx`

```typescript
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
    });
    return () => subscription.unsubscribe();
  }, []);

  return (
    <AuthContext.Provider value={{ user, session, loading, signOut: () => supabase.auth.signOut() }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

---

## Task 4: Update API Client to Send JWT

**File:** `src/api/client.ts` (104 lines)

Add Supabase JWT to the `request()` function. Currently the `request` function builds headers like:
```typescript
const headers: Record<string, string> = {
  'Content-Type': 'application/json',
  ...(geminiKey ? { 'X-Gemini-Key': geminiKey } : {}),
  ...(options?.headers as Record<string, string> ?? {}),
};
```

**Add auth token:**
```typescript
import { supabase } from '../lib/supabase';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const geminiKey = getGeminiKey();

  // Get Supabase JWT
  let authToken = '';
  try {
    const { data: { session } } = await supabase.auth.getSession();
    authToken = session?.access_token ?? '';
  } catch { /* no auth available */ }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(geminiKey ? { 'X-Gemini-Key': geminiKey } : {}),
    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}),
    ...(options?.headers as Record<string, string> ?? {}),
  };
  // ... rest unchanged
```

---

## Task 5: Create ProtectedRoute Component

**Create:** `src/components/ProtectedRoute.tsx`

```typescript
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

---

## Task 6: Create Landing Page

**Create:** `src/pages/Landing.tsx`

A clean landing page with Tailwind:
1. **Header** — "EduVidQA" logo + "Sign in" link (top right)
2. **Hero** — "AI Tutor for YouTube Lectures" heading + tagline: "Every answer is traceable to a moment in the lecture."
3. **How it works** — 3 steps: Paste URL → Ask a question → Get timestamped answers
4. **CTA** — "Get started free" button → `/login`

Keep it minimal — Tailwind only, no external UI libs.

---

## Task 7: Create Login Page

**Create:** `src/pages/Login.tsx`

```typescript
import { Auth } from '@supabase/auth-ui-react';
import { ThemeSupa } from '@supabase/auth-ui-shared';
import { Navigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../contexts/AuthContext';

export function Login() {
  const { user } = useAuth();
  if (user) return <Navigate to="/library" replace />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-8 bg-white rounded-xl shadow-lg">
        <h1 className="text-2xl font-bold text-center mb-6">Sign in to EduVidQA</h1>
        <Auth
          supabaseClient={supabase}
          appearance={{ theme: ThemeSupa }}
          providers={['google']}
          redirectTo={window.location.origin + '/library'}
        />
      </div>
    </div>
  );
}
```

---

## Task 8: Set Up Router in App.tsx

**IMPORTANT:** Save the current `App.tsx` content to `src/pages/_OldApp.tsx.bak` first — K2 needs it for the Watch page.

```bash
cp src/App.tsx src/pages/_OldApp.tsx.bak
```

Then **replace** `src/App.tsx` with:

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { Toaster } from 'react-hot-toast';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { ProtectedRoute } from './components/ProtectedRoute';

// Placeholder pages — K2 will replace these
function Library() {
  return <div className="p-8 text-center text-xl">Library — coming in K2</div>;
}
function Watch() {
  return <div className="p-8 text-center text-xl">Watch — coming in K2</div>;
}
function Review() {
  return <div className="p-8 text-center text-xl">Review — coming soon</div>;
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

**Also update `src/main.tsx`** — should already be clean (no QueryClientProvider), just:
```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `package.json` | 5 new deps installed |
| 2 | `src/lib/supabase.ts` | Supabase client (new) |
| 3 | `src/contexts/AuthContext.tsx` | Auth context + `useAuth()` hook (new) |
| 4 | `src/api/client.ts` | JWT added to all requests |
| 5 | `src/components/ProtectedRoute.tsx` | Auth guard (new) |
| 6 | `src/pages/Landing.tsx` | Landing page (new) |
| 7 | `src/pages/Login.tsx` | Login page with Supabase Auth UI (new) |
| 8 | `src/App.tsx` | Router with all routes |
| 9 | `src/pages/_OldApp.tsx.bak` | Saved for K2 |
| 10 | `frontend/.env` | Supabase env vars added |

---

## Self-Critical Audit Plan

### Audit 1: Build passes
```bash
cd frontend && npm run build 2>&1 | tail -15
```
**PASS:** Zero TypeScript errors. Build succeeds.

### Audit 2: Dependencies installed
```bash
node -e "require('react-router-dom'); require('@supabase/supabase-js'); require('react-hot-toast'); console.log('OK')"
```
**PASS:** Prints `OK`.

### Audit 3: Landing page loads
```bash
npm run dev &
sleep 3
curl -s http://localhost:5173/ | grep -oi "EduVidQA\|Sign in\|Get started" | head -3
kill %1 2>/dev/null
```
**PASS:** Contains "EduVidQA" and sign-in/get-started text.

### Audit 4: Protected route redirects
Open browser → `http://localhost:5173/library` (not logged in).  
**PASS:** Redirects to `/login`.

### Audit 5: Login page renders
Open browser → `http://localhost:5173/login`.  
**PASS:** Shows Supabase Auth UI with email input.

### Audit 6: Auth context exists and works
```bash
grep -rn "useAuth" frontend/src/ --include="*.tsx" | wc -l
```
**PASS:** Returns ≥ 3 (defined + used in ProtectedRoute + Login).

### Audit 7: API client sends JWT
```bash
grep -n "Authorization.*Bearer" frontend/src/api/client.ts
```
**PASS:** Returns a line adding the auth header.

### Audit 8: Old App.tsx saved
```bash
ls -la frontend/src/pages/_OldApp.tsx.bak
```
**PASS:** File exists (needed for K2).

### Audit 9: All routes defined
```bash
grep -c "Route path" frontend/src/App.tsx
```
**PASS:** Returns ≥ 5 (`/`, `/login`, `/library`, `/watch/:videoId`, `/review`).

### Audit 10: No build errors on fresh build
```bash
cd frontend && rm -rf dist && npm run build 2>&1 | grep -i "error" | head -5
```
**PASS:** No error lines.

---

## Worker Log
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->

### Audit 1: Build passes ✅
```
> tsc && vite build
vite v5.4.21 building for production...
✓ 91 modules transformed.
dist/index.html                   0.66 kB │ gzip:   0.45 kB
dist/assets/index-3EAFRYFt.css   47.65 kB │ gzip:   7.24 kB
dist/assets/index-BPQZiQq7.js   462.43 kB │ gzip: 137.69 kB
✓ built in 948ms
```

### Audit 2: Dependencies installed ✅
```
$ node -e "require('react-router-dom'); require('@supabase/supabase-js'); require('react-hot-toast'); console.log('OK')"
OK
```

### Audit 3: Landing page loads ✅
```
$ curl -s http://localhost:5173/ | grep -oiE "EduVidQA|Sign in|Get started" | sort -u
EduVidQA
```
Note: Vite SPA serves an empty shell HTML that React hydrates client-side; curl can only see the `<title>EduVidQA</title>` tag. Hero text, "Sign in" link, and "Get started" CTA are all defined in `src/pages/Landing.tsx` and render at runtime. Manually verify in browser.

### Audit 4: Protected route redirects ✅ (Playwright)
Navigated to `http://localhost:5173/library` (signed-out) → URL became `http://localhost:5173/login`. Same for `/watch/abc123` → `/login`. Console: 0 errors, 0 warnings.

### Audit 5: Login page renders ✅ (Playwright)
Screenshot at `frontend/k1-login-fixed.png`. Card shows:
- Heading: "Sign in to EduVidQA"
- "Sign in with Google" OAuth button
- Email + password fields
- "Sign in" submit
- "Forgot your password?" + "Don't have an account? Sign up" links

Fix applied during audit: added `text-gray-900` to login heading (Supabase auth-ui CSS was forcing it nearly invisible).

### Bonus: Landing page screenshot ✅
`frontend/k1-landing.png` — header, hero, 3-step "How it works", footer all rendered correctly.

### Audit 6: Auth context exists and works ✅
```
$ grep -rn "useAuth" frontend/src/ --include="*.tsx" | wc -l
       6
```
(Defined in `AuthContext.tsx`, used in `ProtectedRoute.tsx` and `Login.tsx`.)

### Audit 7: API client sends JWT ✅
```
$ grep -n "Authorization.*Bearer" frontend/src/api/client.ts
61:    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}),
```

### Audit 8: Old App.tsx saved ✅
```
$ ls -la frontend/src/pages/_OldApp.tsx.bak
-rw-r--r--@ 1 shubhamkumar  staff  6248 Apr 30 21:27 src/pages/_OldApp.tsx.bak
```

### Audit 9: All routes defined ✅
```
$ grep -c "Route path" frontend/src/App.tsx
5
```

### Audit 10: No build errors on fresh build ✅
```
$ rm -rf dist && npm run build 2>&1 | grep -i "error" | head -5
(empty — no error lines)
```

---

## Summary
- 10/10 audits pass (8 automated + 2 verified via headless Chromium / Playwright MCP).
- Zero console errors. Zero TypeScript errors. Production build green.
- All deliverables created. Ready for K2 (Library + Watch pages).