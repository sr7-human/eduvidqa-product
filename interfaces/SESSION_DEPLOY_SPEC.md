# Session DEPLOY — Deploy EduVidQA to Production

## Status: 🔴 NOT STARTED
## Dependencies: ALL code sessions complete (F–O ✅)
## This is a GUIDED session — follow step-by-step with the user.

---

## What You're Doing

Deploy the fully-built EduVidQA app to free-tier hosting:
- **Frontend** → Vercel (free)
- **Backend** → Hugging Face Spaces (free Docker CPU)
- **Database** → Supabase (already provisioned ✅)
- **CI** → GitHub Actions (already configured, needs secrets)

**Total cost: $0/month.**

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`

---

## Pre-flight Checklist

Before starting, confirm:
- [ ] GitHub repo exists and code is pushed
- [ ] Supabase project is live (it is — `xucwewnohhucheyqkdjs.supabase.co`)
- [ ] Docker builds locally (`docker images eduvidqa-test` shows the image)
- [ ] Frontend builds clean (`cd frontend && npm run build`)
- [ ] You have accounts on: GitHub, Vercel, Hugging Face

---

## PART 1: Push Code to GitHub

### Step 1: Create GitHub repo (if not done)

```bash
cd /Users/shubhamkumar/eduvidqa-product

# Check if git is initialized
git status

# If not initialized:
git init
git add .
git commit -m "EduVidQA: Full MVP — RAG + Quiz + Auth + Frontend"

# Create repo on GitHub (use CLI or web):
# https://github.com/new → name: eduvidqa-product → private → create

# Add remote and push:
git remote add origin https://github.com/YOUR_USERNAME/eduvidqa-product.git
git branch -M main
git push -u origin main
```

### Step 2: Verify `.gitignore` includes sensitive files

```bash
cat .gitignore | grep -E "\.env|\.venv|data/|__pycache__|node_modules"
```

Must include: `.env`, `.venv/`, `data/`, `__pycache__/`, `node_modules/`, `media/`

**CRITICAL:** Run this before pushing:
```bash
# Make sure .env is NOT tracked
git ls-files .env  # must return empty
# Make sure no keys in history
git log --all -p -- .env | head -5  # must return empty
```

---

## PART 2: Deploy Frontend to Vercel

### Step 3: Connect to Vercel

**Option A: Vercel CLI**
```bash
npm install -g vercel
cd /Users/shubhamkumar/eduvidqa-product
vercel login
vercel link  # link to the repo
```

**Option B: Vercel Dashboard (easier)**
1. Go to https://vercel.com/new
2. Import your GitHub repo `eduvidqa-product`
3. Configure:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`

### Step 4: Set Vercel Environment Variables

In Vercel Dashboard → Project Settings → Environment Variables, add:

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_URL` | `https://YOUR-SPACE.hf.space` | Fill after HF deploy (Part 3) |
| `VITE_SUPABASE_URL` | `https://xucwewnohhucheyqkdjs.supabase.co` | From your .env |
| `VITE_SUPABASE_ANON_KEY` | `eyJ...gLg` | From your frontend/.env |
| `VITE_DEFAULT_VIDEO_URL` | `https://www.youtube.com/watch?v=3OmfTIf-SOU` | Demo video |

### Step 5: Deploy

```bash
vercel --prod
# Or just push to main — Vercel auto-deploys
```

Note the preview URL: `https://eduvidqa-xxxxx.vercel.app`

### Step 6: Update Supabase Auth redirect

In Supabase Dashboard → Authentication → URL Configuration:
- **Site URL:** `https://YOUR-APP.vercel.app`
- **Redirect URLs:** Add `https://YOUR-APP.vercel.app/library`

---

## PART 3: Deploy Backend to Hugging Face Spaces

### Step 7: Create HF Space

1. Go to https://huggingface.co/new-space
2. Settings:
   - **Space name:** `eduvidqa`
   - **SDK:** Docker
   - **Hardware:** CPU basic (free)
   - **Visibility:** Public (required for free tier)

### Step 8: Set HF Space Secrets

In your Space → Settings → Repository secrets, add ALL of these:

| Secret | Value | Where to find |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | Your `.env` |
| `GEMINI_API_KEY` | `AIza...` | Your `.env` |
| `HF_TOKEN` | `hf_...` | Your `.env` |
| `DATABASE_URL` | `postgresql://...` | Your `.env` |
| `SUPABASE_URL` | `https://xucw...supabase.co` | Your `.env` |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | Your `.env` |
| `SUPABASE_JWT_SECRET` | The JWT secret | Your `.env` |
| `CORS_ORIGINS` | `https://YOUR-APP.vercel.app` | Your Vercel URL from Step 5 |
| `LAZY_LOAD` | `true` | Defer model loading |
| `SENTRY_DSN` | (optional) | Leave empty if no Sentry |

### Step 9: Push code to HF Space

```bash
cd /Users/shubhamkumar/eduvidqa-product

# Add HF remote
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/eduvidqa

# Push (HF builds from Dockerfile automatically)
git push hf main
```

**⚠️ The image is ~10GB — first build will take 10-20 minutes on HF.**

### Step 10: Verify HF Space is running

Wait for build to finish in the HF Space logs tab, then:
```bash
curl https://YOUR_USERNAME-eduvidqa.hf.space/api/health
```

Should return: `{"status": "ok", "model_loaded": true, "model_name": "groq/llama-4-scout-17b", ...}`

---

## PART 4: Wire Everything Together

### Step 11: Update Vercel with actual HF URL

Now that HF Space is live, go back to Vercel:
1. Project Settings → Environment Variables
2. Update `VITE_API_URL` → `https://YOUR_USERNAME-eduvidqa.hf.space`
3. Redeploy: `vercel --prod` or push a dummy commit

### Step 12: Update CORS on backend

The `CORS_ORIGINS` secret in HF Space should already point to your Vercel domain. Verify by checking the HF Space logs for CORS headers.

### Step 13: Update Supabase Auth URLs

In Supabase Dashboard → Authentication → URL Configuration:
- **Site URL:** Your Vercel URL
- **Redirect URLs:** `https://YOUR-APP.vercel.app/library`, `https://YOUR-APP.vercel.app/login`

---

## PART 5: GitHub Actions CI

### Step 14: Add GitHub Secrets

In GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `DATABASE_URL` | Your Postgres connection string |
| `GROQ_API_KEY` | Your Groq key |
| `GEMINI_API_KEY` | Your Gemini key |

### Step 15: Trigger CI

```bash
git commit --allow-empty -m "trigger CI"
git push origin main
```

Check Actions tab — all 3 jobs (backend, frontend, docker) should pass.

---

## PART 6: Smoke Test Production

### Step 16: End-to-end verification

Run each check:

```bash
# 1. Landing page loads
curl -sI https://YOUR-APP.vercel.app/ | head -3

# 2. Health check
curl -s https://YOUR-SPACE.hf.space/api/health | python3 -m json.tool

# 3. Demo video works without login
curl -s -X POST https://YOUR-SPACE.hf.space/api/ask \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=3OmfTIf-SOU","question":"What is unit testing?","timestamp":60,"skip_quality_eval":true}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Answer: {d[\"answer\"][:100]}...')"

# 4. Non-demo requires auth
curl -s -o /dev/null -w "%{http_code}" -X POST https://YOUR-SPACE.hf.space/api/ask \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=VRcixOuG-TU","question":"test","timestamp":0}'
# Should return 401

# 5. Open browser → sign up → add video → ask question → take quiz
```

---

## Troubleshooting

### HF Space build fails
- Check logs in the Space → Logs tab
- Common: pip install timeout → add `--default-timeout=300` (already in Dockerfile)
- Common: out of disk → `.dockerignore` must exclude `data/`, `media/`, `.venv/`

### Vercel build fails
- Check Build Logs in Vercel Dashboard
- Common: missing env vars → add all `VITE_*` variables
- Common: TypeScript errors → run `cd frontend && npm run build` locally first

### CORS errors in browser
- Check that `CORS_ORIGINS` in HF Space secrets matches your Vercel domain exactly
- No trailing slash: `https://app.vercel.app` not `https://app.vercel.app/`

### Auth redirect fails
- Check Supabase → Authentication → URL Configuration
- Redirect URL must match exactly (including https://)

### CI fails on GitHub
- Missing secrets → add all 3 in repo settings
- Backend tests need live DB → `DATABASE_URL` secret must point to Supabase

---

## Success Criteria

After this session, you should have:
- [ ] Frontend live at `https://YOUR-APP.vercel.app`
- [ ] Backend live at `https://YOUR-SPACE.hf.space`
- [ ] Health endpoint returns 200
- [ ] Demo video (3OmfTIf-SOU) works without login
- [ ] Sign up with email works
- [ ] Add video + ask question works for logged-in user
- [ ] GitHub Actions CI passes (3 green checks)
- [ ] Total hosting cost: $0/month

---

## URLs to Record (fill in during session)

```
Frontend:  https://_____________________.vercel.app
Backend:   https://_____________________.hf.space
GitHub:    https://github.com/_____/eduvidqa-product
Supabase:  https://xucwewnohhucheyqkdjs.supabase.co
```
