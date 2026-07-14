# EduVidQA — Upgrade Backlog (observations → structured requirements)

> **Captured:** 2026-07-12 · **Baseline:** Jul 10 commit `23da893` (post-revert)
> **Status of everything below:** PROPOSED — not yet implemented. This doc structures
> and polishes the user's raw observations into actionable requirements so we can
> implement them one-by-one, incrementally and flag-guarded.

> **UPDATE 2026-07-12:** ✅ **All 11 items are now IMPLEMENTED and verified** (see MUNIMJI Session 3).
> The `video_ingest_jobs` table was applied to production Supabase (additive only);
> all other changes are local + uncommitted, with `DURABLE_JOBS_V1` dark until deploy.

Legend: **DONE** = shipped · **PARTIAL** = some code exists but incomplete · **PROPOSED** = not started.

---

## 1. Per-video resume record
**Status:** PARTIAL (only incremental skip exists today)

**Observed:** "There should be a record for each video to resume from where it left off."

**Current behaviour:** Ingest saves transcript chunks + keyframe embeddings incrementally and skips already-embedded ones on re-run. But there is no durable per-video *job* record — no stage cursor, owner, heartbeat, or attempt count. A restart can't reliably tell which stage to resume, and two workers could act on the same video.

**Desired behaviour:**
- One durable record per video with: current stage (transcript → embed → download → keyframes → digest → checkpoints → chapters → ready), per-stage state (pending/running/paused/complete/failed), completed/total counts, last error, retry-after.
- Resume from the first incomplete stage; never redo a completed stage.
- Only one active worker per video at a time.

---

## 2. Ask about a point OR a time range
**Status:** PROPOSED

**Observed:** "A user can ask a question not only for a particular timestamp but also a time range — and keyframes **within this range** plus the transcript should be taken into account."

**Desired behaviour:**
- Two modes: **Point** (single timestamp, as today) and **Range** (start–end).
- In Range mode, build context from **only** the transcript chunks *and* keyframes that fall inside `[start, end)`. Do not pull evidence from outside the interval.
- Cap the number of frames/tokens for large ranges; show which sub-ranges were used as citations.
- UI: a compact Point/Range toggle near the timestamp, "set start/end from current time", manual `mm:ss` editing, and a highlight band on the timeline.

---

## 3. Checkpoint quiz = 10 questions, Bloom-ordered
**Status:** PARTIAL (currently shrinks to ~5-6; Bloom not enforced)

**Observed:** "Checkpoint questions are reduced to 5-6 and Bloom's taxonomy isn't followed. Keep 10 questions — start with 2-3 at Bloom levels 1-2, and the majority of the rest as conceptual testing/evaluation."

**Current behaviour:** Prompts *mention* Bloom, but the final count and distribution aren't validated. Some paths default to fewer questions; truncated/older sets end up with 5-6.

**Desired behaviour:**
- Exactly **10** questions per checkpoint quiz, ordered easy → hard.
- Distribution target: **~1 Remember + 2 Understand** first (Bloom L1-L2), then **majority higher-order** (Apply / Analyse / Evaluate).
- **Validate** the generated count and Bloom mix; regenerate only the missing/invalid ones (see item 9).
- Store `order_idx` and render in that order.

---

## 4. Previous-question button on the quiz interface
**Status:** PROPOSED

**Observed:** "Introduce a previous-question button on the quiz interface."

**Desired behaviour:**
- Add **Previous** to the quiz modal.
- Preserve the selected answer + shown explanation for each visited question.
- Going back must **not** resubmit an attempt or change the score.
- Disabled only on question 1.

---

## 5. Auto-popup quiz at every checkpoint
**Status:** PARTIAL / BUG (not firing as expected)

**Observed:** "The test quiz should pop up on its own at every checkpoint — why isn't it happening?"

**Current behaviour:** Semantic checkpoints only show a suggestion/toast on pause; the automatic interruption belongs to the **chapter** flow (pretest/mid/end). The two systems overlap and the auto-popup isn't reliably triggering.

**Desired behaviour (decision needed):**
- Decide the single source of automatic interruptions (recommended: the chapter start/mid/end flow) and make it fire reliably when playback crosses an event timestamp.
- Persist completed/dismissed so a reload doesn't repeat the same popup.
- Seeking across many events must not flood popups.

---

## 6. Explanations for wrong options
**Status:** PARTIAL (chapter quizzes have it; checkpoint cache doesn't)

**Observed:** "Options which are wrong — explanation should be there."

**Desired behaviour:**
- Every question stores `option_explanations` for **A/B/C/D**.
- Correct option: why it's right. Each wrong option: why it's wrong + the specific misconception.
- Preserve explanations when options are shuffled.

---

## 7. Answer system prompt — concise + structured (not a wall of text)
**Status:** PROPOSED

**Observed:** Current answers are too long. Wants a Gemini-style, structured-but-concise prompt. User's reference template (to be adapted, not used verbatim):

> Start with a difficulty tag + 1-2 line TL;DR. Plain-language explanation with real-life analogies (Indian context where it fits, not forced). Full technical depth with varied examples/edge cases. 2-3 common misconceptions. One mnemonic/acronym/short story. Exam angle (MCQ traps, conceptual vs numerical). Research frontier + key terms/papers. 3-5 Bloom questions (answers as keywords at the end). 3-5 quick revision Q&A. 1-2 follow-up topics. Bullet points, no long paragraphs. Images where useful.

**Desired behaviour:**
- Default answer = **concise**: difficulty tag + TL;DR + short bulleted answer.
- Heavy sections (misconceptions, mnemonic, exam patterns, research, Bloom questions, revision Q&A, follow-ups) appear **only** in a "Deep dive" mode or when the user asks for more.
- Keep bullet formatting; Bloom-question answers as keywords at the very end.
- Offer response-depth control: **Quick / Standard / Deep dive** (Standard default).

---

## 8. Increase checkpoint interval (reduce clutter)
**Status:** PARTIAL

**Observed:** "Interval of checkpoints should be increased — see how cluttered it is."

**Current behaviour:** `checkpoints.py` targets **~1 per 8 min** with a 3-min minimum spacing and **no maximum cap** → a 7-hour video gets 50+ markers → cluttered.

**Desired behaviour:**
- Adaptive spacing: shorter videos ~8-10 min, long videos ~12-20 min between checkpoints.
- Hard cap of ~20-24 visible markers per video.
- Still prefer strong semantic topic boundaries over exact clock intervals.

---

## 9. Incremental / resumable quiz generation
**Status:** PARTIAL

**Observed:** "Incremental saving should be there for quiz generation too, so if an API quota is hit we can resume the other checkpoints' quizzes instead of starting again and wasting already-generated ones."

**Desired behaviour:**
- Per `(video, checkpoint/chapter, quiz_type)` generation record: target count, saved count, status, attempt, last error, retry-after.
- Save each valid question immediately.
- On resume, generate only the **missing** questions/Bloom levels — never re-do completed checkpoints.
- A quota hit pauses safely; it does not discard already-saved questions.

---

## 10. OpenRouter key onboarding guide
**Status:** PARTIAL

**Observed:** "Make an OpenRouter key addition guide."

**Desired behaviour:**
- In Settings: a "How to get this key" expandable guide + link.
- Key format hint `sk-or-…`, note that it's **paid / needs credits**, and that a valid key with zero credits still returns HTTP 402.
- Save / validate / test / remove controls (some already exist).

---

## 11. Fast Settings (root cause fix)
**Status:** ROOT CAUSE CONFIRMED

**Observed:** "Why does the content inside Settings load so slowly? First tell me the reason."

**Root cause:** Opening Settings calls `GET /api/models`, which makes **live** network calls to Google *and* OpenRouter, **sequentially**, each with a **15 s timeout** (~30 s worst case), with **no caching**. Backend cold-start adds more.

**Desired behaviour:**
- Render keys + preferences immediately.
- Fetch Google + OpenRouter catalogs **in parallel**, short timeouts, cache 30-60 min, keep stale data on error.
- Lazy-load model catalogs only when the "Advanced" section is opened.

---

## Reference — current quiz strategy (as-is, for context)
- **Semantic checkpoints** (`checkpoints.py`): topic-shift markers on the timeline; optional manual "Test me" quiz.
- **Chapter learning flow** (`chapters.py`): **pretest** at chapter start (priming) · **mid_recall** mid-chapter (lock-in) · **end_recall** at chapter end (synthesis). Current counts: pretest 4, mid_recall 3, end_recall 4.
- The overlap between these two systems is the source of item 5 (auto-popup confusion) and needs a single clear decision.
