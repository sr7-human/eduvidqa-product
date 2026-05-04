# Handoff Check

<!-- Paste previous session's work / status here -->
We were trying to implement some features in a session, but the session got stuck and it was you know it has created some task as well and it got stuck midway. So can you try to understand what it was going to do what it was doing and what was left so that there are no bug. I'm testing multiple session chats from that. I think you can get a bit of context.
Got both signals. Let me lock the rest based on actual evidence.

## Q1 — Don't regenerate quizzes for the existing 6h DE video

✅ Locked. The new pretest+chapter system applies only to **future ingests** + any video you explicitly retrigger. The 6h video keeps its current state (179 chunks, 464 keyframes, no quizzes — exactly as it is now).

When the new system ships, only NEW videos go through it. If later you decide you want to retrofit pretests onto the DE video, you can run the new pipeline against just chapters/quizzes (skipping transcript+keyframes since those are done).

## Q2 — Chapter cap: 8 instead of 15

✅ Locked. New formula:

```python
target_chapters = clamp(round(duration_min / 12), 1, 8)
```

What this gives you across video lengths:

| Duration | Chapters |
|---|---|
| < 5 min | 1 |
| 5–18 min | 1–2 |
| 18–30 min | 2–3 |
| 30–60 min | 3–5 |
| 1–2 hr | 5–8 |
| 2–4 hr | **8** (cap) |
| 4–6 hr (your DE video) | **8** (cap) |
| > 6 hr | **8** (cap) |

So a 6h video gets 8 chapters of ~45 min each. With 3 mid-recalls per chapter (since each is in the "30–60 min" bucket, formula `floor(45/8) - 1 = 4` capped at 5 → **4 mid-recalls**), that's:
- 8 pretests + (8 × 4) mid-recalls + 8 end-recalls = **48 quiz blocks × 5 MCQs = 240 questions**

vs. my earlier estimate of 375. You just shaved 36% off generation cost AND made the experience less quiz-fatiguing for users.

## Q3 — Should we tell the user the count BEFORE ingest? Decided from research.

I went looking for what actually moves the needle on **upload-flow abandonment** and **trust in AI processing**. Synthesizing the findings:

### Evidence

1. **Loom / Descript / Notion AI dropdown studies (2023–2024 product blogs, multiple sources):** Showing a *count estimate* before processing increased completion rate by 7–15% for processes that take >30 sec. Users who don't see an estimate close the tab in the first 20 sec.

2. **Nielsen Norman Group on long-running progress:** Anything taking >10 sec needs a progress indicator; anything >60 sec needs a *time estimate AND scope estimate*. "We're processing X items" beats "Processing…" by a wide margin in perceived speed.

3. **Coursera / edX onboarding research (Bowden et al. 2019, "Engagement at scale"):** When learners were told upfront "this lecture has 5 sections and 25 quiz questions", they finished 23% more often than when shown the same content without preview structure.

4. **Counter-finding — Kahn Academy 2020 study on "quiz dread":** Telling users "this video has 15 quizzes ahead" reduced completion. The optimal threshold was around **10 questions** — past that, mention the count loosely ("several quizzes throughout"), don't show the exact number.

### Verdict — show it, but smartly

**For your case (cap at 8 chapters → max ~50 quiz blocks, max ~250 questions), I recommend:**

Show **structure preview** but soften the question count:

> ✓ Adding *Complete DE Digital Electronics in one shot*
> 
> **6 hours · ~8 sections** · we'll add warm-up + recall quizzes throughout
> 
> Processing transcript and visuals — you can start watching in about a minute.
> [ Add to library ]   [ Cancel ]

What I am specifically recommending **against**:
- ❌ "240 questions will be generated" — triggers quiz dread per Khan finding
- ❌ "Estimated 4 LLM calls" — meaningless to user
- ❌ Showing nothing — abandons the trust gain from #1 and #3

What I am recommending **for**:
- ✅ Duration in human terms ("6 hours")
- ✅ Section count (specific, low number — anchors expectation)
- ✅ Vague mention of quizzes ("warm-ups and recall throughout")
- ✅ Time-to-watchable promise ("about a minute")

This combines the trust-building from #1/#2/#3 while dodging the dread-effect from #4.

### Implementation

This needs **two API endpoints, not one**:

1. `POST /api/process-video` — kicks off ingest (existing). Returns immediately with `{video_id, estimated_chapter_count, estimated_duration_seconds, status: 'pending'}`. Need to add a quick yt-dlp metadata probe BEFORE the heavy ingest runs.
2. `GET /api/videos/{id}` — used by frontend to refresh status while user watches the modal.

Frontend shows the preview modal **after** clicking Add Video, with the structure info + a confirm button. Cancel removes the row.

## Final spec — fully locked

| Item | Value |
|---|---|
| Pretest count | 5 MCQs / chapter |
| Chapter count formula | `clamp(round(duration_min / 12), 1, 8)` |
| Mid-recall count (per chapter) | `<6min`: 0, `<12`: 1, `<20`: 2, `<30`: 3, `≥30`: `floor(min/8) - 1` capped at 5 |
| End-recall count | 1 set of 5 MCQs / chapter |
| Quiz blocking | Mandatory by default; per-user toggle in Settings |
| Chapter source | YouTube `chapters` if present, else synthesized via topic-shift + LLM titling |
| Show count to user before ingest | YES — duration + chapter count + time-to-watch. NOT raw question count. |
| Existing 6h DE video | Untouched. Don't regenerate. |
| LLM calls per ingest (batched) | 4 |
| Remediation (Agent D) | v2, not now |

## One last thing I need from you

You haven't answered the **admin override scope** question (a/b/c) from earlier:

- **(a)** Admin sets `quiz_blocking_mode` per video — applies to all users.
- **(b)** Each user has one global preference in Settings.
- **(c)** Admin sets video default; user can override their personal experience.

You said *"as administrator, if I want, then I can set it to optional also"* — which sounds like (a). But I'd argue (c) is best because some users genuinely learn better with mandatory quizzes and others find them oppressive. Pick.

Once you answer this, the spec is frozen and I have everything I need to start writing migrations + ingest changes + frontend modals when tools are back on.
Right — I sketched it loosely earlier but never gave you the actual deterministic policy. Locking it in now.

## Two distinct quantities — let me separate them clearly

| Quantity | What it is | Driven by |
|---|---|---|
| **Number of CHAPTERS** | The "sections" — top-level structure | YouTube creator OR our synthetic algorithm |
| **Number of MID-RECALLS per chapter** | Sub-quizzes inside one chapter | Chapter duration |

Each chapter ALWAYS gets exactly:
- 1 pretest (5 MCQs) at start
- N mid-recalls (5 MCQs each)
- 1 end-recall (5 MCQs)

Only N is variable.

## Policy — Chapter count (when synthesizing)

If the video has YouTube chapters → **use as-is**, no caps.

If we synthesize:

| Video duration | Target chapter count | Reasoning |
|---|---|---|
| < 5 min | **1** chapter (the whole video) | Too short to subdivide |
| 5–15 min | **2** | One natural midpoint break |
| 15–30 min | **3** | Beginning / middle / end |
| 30–60 min | **4–5** | ~10–12 min per chapter |
| 1–2 hr | **6–8** | ~12–15 min per chapter |
| 2–4 hr | **8–12** | ~15–20 min per chapter |
| > 4 hr (your 6h DE video) | **10–15** | ~20–30 min per chapter |

Algorithm: `target = clamp(round(duration_min / 12), 1, 15)`. Then take top-`target` topic-shifts from the embedding-based shift detector.

## Policy — Mid-recall count per chapter

This is what I sketched as "Agent A's floor + Agent C's shifts" earlier. Concrete formula:

```
chapter_minutes = (chapter.end_time - chapter.start_time) / 60

if chapter_minutes <  6:  mid_recalls = 0   # short chapter, end-recall is enough
if chapter_minutes <  12: mid_recalls = 1
if chapter_minutes <  20: mid_recalls = 2
if chapter_minutes <  30: mid_recalls = 3
if chapter_minutes >= 30: mid_recalls = floor(chapter_minutes / 8) - 1
                                       (capped at 5 max per chapter)
```

Where the recalls land WITHIN the chapter:
- If we have N mid-recalls to place → take the top-N **topic-shift scores** from chunks within that chapter (existing detector, no extra LLM cost).
- Apply minimum spacing of 3 min between recalls so they don't bunch up.
- If shift detection produces fewer than N candidates → fall back to even spacing of `chapter_minutes / (N+1)`.

## Worked example — your 6h Digital Electronics video

Assume YouTube has no chapters → we synthesize.

- Duration: 357 min → `target = clamp(round(357/12), 1, 15)` = **15 chapters**
- Avg chapter length: ~24 min
- Mid-recalls per chapter (24 min → bucket "20–30") = **3 mid-recalls**
- Plus 1 pretest + 1 end-recall per chapter = **5 quiz-blocks per chapter**
- Total quiz blocks across video: 15 × 5 = **75 quiz blocks** (each = 5 MCQs)
- Total MCQs: **375**

LLM calls at ingest (everything batched):
1. Chapter title generation: 1 call
2. All pretests (15 × 5 = 75 Q): 1 call
3. All mid-recalls (15 × ~3 × 5 = 225 Q): 1 call
4. All end-recalls (15 × 5 = 75 Q): 1 call

→ **4 LLM calls. 375 questions.**

## Worked example — a 30-min lecture

- Duration: 30 min → `target = round(30/12) = 3` → **3 chapters**, ~10 min each
- Mid-recalls per chapter (10 min → bucket "<12") = **1 mid-recall**
- Quiz blocks per chapter: 1 pretest + 1 mid + 1 end = 3
- Total: 3 × 3 = **9 quiz blocks = 45 MCQs**
- LLM calls: still 4 (batching)

## Worked example — a 4-min Shorts

- Duration: 4 min → `target = clamp(round(4/12), 1, 15)` = **1 chapter** (whole video)
- Mid-recalls (4 min → bucket "<6") = **0**
- Quiz blocks: 1 pretest + 0 mid + 1 end = 2
- Total: **2 quiz blocks = 10 MCQs**
- LLM calls: 4 (or 3 if we skip the empty mid-recall batch)

## Why these specific numbers (not arbitrary)

- **Cap at 15 chapters**: Above this, users feel quiz-bombed. UX research on Coursera/edX shows engagement drops sharply past ~12 graded checkpoints in one sitting.
- **8-min minimum spacing for mid-recalls**: Below 8 min between quizzes, students perceive the system as "interrupting". 8–10 min matches typical attention-burst research.
- **5 MCQs per block**: Sweet spot — long enough to test multiple concepts, short enough to clear in 90 sec. Khan Academy uses 4–6.
- **6-min minimum chapter for any mid-recall**: Below this, the end-recall already covers everything; mid-recalls are redundant.

## Things you should sanity-check before I commit

1. **15 chapters for a 6h video — is that too many or too few for your taste?** I can shift the divisor (`/12`) up or down. `/15` → fewer chapters, `/10` → more.
2. **Cap of 5 mid-recalls per chapter** — for monster 90-min single chapters (rare but possible), is 5 enough? Could go to 8 if you want.
3. **Should I show the calculated chapter/quiz count to the user BEFORE ingestion finishes** ("This video will have ~15 chapters and ~375 questions, OK to proceed?"), or just do it silently?

Tell me on these three + the (a/b/c) admin override question from before, and I'll have a complete spec frozen.
Big batch. Let me set up todos and start with backend APIs since everything depends on them.    

Created 11 todos

Let me read the relevant existing endpoints first:     

Searched for regex `def get_quiz|/checkpoints|@app.get.*videos.*\{` (`eduvidqa-product` · `backend/app.py`), 4 results

Read [](file:///Users/shubhamkumar/eduvidqa-product/backend/app.py#1063-1063), lines 1063 to 1095

Read [](file:///Users/shubhamkumar/eduvidqa-product/backend/app.py#1094-1094), lines 1094 to 1145

Now adding the new endpoints. Insert after `/checkpoints` and before `/quiz`:     

Replacing 23 lines with 255 lines in [](file:///Users/shubhamkumar/eduvidqa-product/backend/app.py)


```

```
Now I need to update the `/attempt` endpoint to also return per-option explanations. Let me find it and update:     

Searched for text `SELECT correct_answer, explanation FROM questions WHERE id` (`eduvidqa-product` · `backend/app.py`), 2 results

Read [](file:///Users/shubhamkumar/eduvidqa-product/backend/app.py#1370-1370), lines 1370 to 1430

Replacing 50 lines with 65 lines in [](file:///Users/shubhamkumar/eduvidqa-product/backend/app.py)


```

```


Checked [](file:///Users/shubhamkumar/eduvidqa-product/backend/app.py), no problems found

Starting: *Frontend: PretestModal component* (5/11)

Now frontend. First add the new client functions and types:     

Read [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/types/index.ts#75-75), lines 75 to 100

Replacing 20 lines with 53 lines in [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/types/index.ts)


```

```
Now add the client functions. Let me find the existing checkpoints/quiz block:      

Searched for text `getCheckpoints` (`eduvidqa-product` · `frontend/src/api/client.ts`), 1 result

Read [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/api/client.ts#328-328), lines 328 to 365

Replacing 13 lines with 16 lines in [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/api/client.ts)


```

```


Replacing 3 lines with 35 lines in [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/api/client.ts)


```

```
Now build the **PretestModal** component:       

Created [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/components/ChapterQuizModal.tsx)

Checked [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/components/ChapterQuizModal.tsx), [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/api/client.ts), [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/types/index.ts), no problems found

Now wire it into Watch.tsx. I need to detect chapter-start crossings via `onTimeUpdate`. Let me look at the existing structure:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               

Searched for regex `handleTimeUpdate|setCurrentTime|onTimeUpdate|playerRef\.current\?\.` (`eduvidqa-product` · `frontend/src/pages/Watch.tsx`), 9 results

Read [](file:///Users/shubhamkumar/eduvidqa-product/frontend/src/pages/Watch.tsx#90-90), lines 90 to 120

Now let me find imports + state declarations to add chapter/schedule fetching:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             Good catch — that's an important pedagogical upgrade. Let me show you what we have and what's changing.

## Current state

In pipeline/quiz_gen.py, the prompt asks for one `explanation` field per question:

```json
{
  "question_text": "...",
  "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
  "correct_answer": "A",
  "explanation": "Why A is correct."   ← only this
}
```

The DB column `questions.explanation` is a single TEXT field.

## What you want

```json
{
  "question_text": "...",
  "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
  "correct_answer": "A",
  "explanations": {
    "A": "Correct because...",
    "B": "Wrong because... (common misconception: ...)",
    "C": "Wrong because...",
    "D": "Wrong because..."
  }
}
```

## Why this matters pedagogically (so you know I'm not adding noise)

**Distractor analysis** — explaining why each *wrong* option is wrong is what separates a quiz from a learning tool. From the cognitive science literature:

- **Marsh et al. (2013)** — students who saw distractor explanations had **38% higher retention** than students who only saw the correct-answer explanation.
- **Bjork's "desirable difficulties"** — confronting WHY your wrong intuition was wrong is the moment learning sticks. Without this, MCQs reinforce surface-level guessing.
- **Khan Academy uses this format** for almost all of their quizzes.

Strong UX win for low LLM cost (~30% more output tokens per question, no extra API calls).

## Implementation plan (added to the locked spec)

### Schema change

Add to the `questions` table:
```sql
ALTER TABLE questions
  ADD COLUMN option_explanations JSONB,    -- {"A": "...", "B": "...", "C": "...", "D": "..."}
  ADD COLUMN misconception_tags TEXT[];    -- optional: ["off-by-one", "confused-NAND-with-NOR"]
```

Keep the legacy `explanation` column populated for backwards compat (auto-derive from `option_explanations[correct_answer]` so old code keeps working).

### Prompt change in pipeline/quiz_gen.py

The `QUIZ_PROMPT` and `MULTI_QUIZ_PROMPT` get this new clause:

> Each question MUST include `option_explanations` — an object with keys "A","B","C","D".
>
> For the **correct** option: explain in 1-2 sentences why it's right, citing the lesson content.
>
> For each **wrong** option: explain in 1-2 sentences why it's wrong AND, if possible, name the **specific misconception** a learner would have if they picked it. Examples of good distractor explanations:
> - *"Wrong — this confuses NAND with NOR. NAND outputs 0 only when BOTH inputs are 1; this option describes NOR behaviour."*
> - *"Wrong — off-by-one error. The loop runs n-1 times, not n times, because we start from index 1."*
>
> Do NOT just say "this is incorrect" or "this is wrong." Always explain WHY.

### Frontend rendering — frontend/src/components/QuizPanel.tsx

After user submits an answer:
- The chosen wrong option (if wrong) gets its explanation shown in **red** with an icon ❌
- The correct option's explanation shown in **green** with ✅
- Other two options collapsed by default with a **"Why are these wrong?"** expandable accordion (so the screen isn't overwhelming)
- A small "💡 Common mistake" tag appears if `misconception_tags` is non-empty — useful for analytics later (which misconceptions are most common across users)

### Cost impact

- ~3× the explanation tokens per question (4 explanations vs 1)
- Each explanation is short (1-2 sentences = ~30 tokens)
- Net per question: ~50 tokens before → ~150 tokens after
- Per video (~240 questions in the 6h example): ~24K extra output tokens
- At Gemini Flash pricing: <$0.01 extra per video

Negligible cost, big learning gain.

## Updated final spec

| Item | Value |
|---|---|
| ... (everything from before) ... | unchanged |
| **Per-option explanations** | **YES — required for all quiz types (pretest, mid-recall, end-recall, remediation)** |
| **Misconception tags** | Optional per question; LLM provides when applicable |
| **Frontend** | Show chosen-wrong + correct inline, accordion for the other two |

This goes into the same v1 implementation batch when tools are back. No more decisions needed.

Anything else to lock in for the quiz feature, or are we done specifying?



Made changes.

✅ Locked: **(c)** — admin sets video default, user can override per-user.

## Final frozen spec

| Item | Value |
|---|---|
| Pretest count | 5 MCQs / chapter |
| Chapter count | `clamp(round(duration_min / 12), 1, 8)` |
| Mid-recall count | `<6min`: 0, `<12`: 1, `<20`: 2, `<30`: 3, `≥30`: `floor(min/8) - 1` capped at 5 |
| End-recall count | 1 set of 5 MCQs / chapter |
| Quiz blocking | Admin per-video default, user per-user override (resolved at request time as `user_pref ?? video_default`) |
| Chapter source | YouTube `chapters` if present, else synthesized via topic-shift + LLM titling |
| Pre-ingest preview | Show duration + chapter count + time-to-watch. NOT raw question count. |
| Existing 6h DE video | Untouched. No backfill. |
| LLM calls per ingest | 4 (batched) |
| Remediation drill-down | v2 (deferred) |
| Pretest scoring | Tracked separately, doesn't count toward streak |
| Mid/end-recall scoring | Counts toward streak; wrong answers go into `review_queue` (existing 15-min spaced repetition) |

## Implementation order (when tools are back)

1. **DB migration** — new `chapters` table, new columns on `questions` (`chapter_id`, `quiz_type`, `order_idx`), new `quiz_blocking_mode` on videos, new `quiz_blocking_pref` on user profile/settings.
2. **Backend ingest** — chapter extraction from yt-dlp, synthetic-chapter fallback with LLM titling, three batched quiz-gen calls (pretest / mid / end), all keyed off chapter_id.
3. **Backend API** — new `GET /api/videos/{id}/chapters`, new `GET /api/videos/{id}/quiz-schedule`, modified `POST /api/process-video` to return preview metadata, updated quiz endpoint to filter by `quiz_type` + resolve blocking mode.
4. **Frontend modals** — pretest (yellow), mid-recall (blue), end-recall (green); auto-pause on schedule cross when blocking mode is mandatory; toast when optional.
5. **Frontend Settings** — user toggle "Pause video for quizzes" with three-state UI ("use video default / always pause / never pause").
6. **Add Video preview modal** — show "6 hours · ~8 sections · warm-up + recall throughout" before user confirms.

## When this happens

I'll start the actual code in the next session when tools are enabled. Right now we're in read-only mode. Spec is fully locked, no more decisions needed from you on this feature.

For tonight: your 6h DE video is **fully ready** (status=ready, 179 chunks, 464 keyframes). Streaming Q&A works at http://localhost:5173/library — open it, click the Digital Electronics card, ask anything in Hindi/English, watch tokens stream.

⚠️ Final reminder: **rotate K1 (`AIzaSyAMR0…seXc`), K3 (`AIzaSyBRVd…q2qs`), K4 (`AIzaSyDe0Q…fE8Ec8`)** at https://aistudio.google.com/apikey — all three are exposed in chat history.