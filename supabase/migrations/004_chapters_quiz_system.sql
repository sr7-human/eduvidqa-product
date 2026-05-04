-- 004: Chapter-based quiz system
-- Adds: chapters table, new question columns for chapter-aware quizzes,
--        quiz_blocking_mode on videos, user_quiz_prefs table.

-- 1. Chapters table
CREATE TABLE chapters (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id VARCHAR(11) NOT NULL,
    idx INT NOT NULL,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    title TEXT NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'synthetic'
        CHECK (source IN ('youtube', 'synthetic')),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (video_id, idx)
);

CREATE INDEX idx_chapters_video_id ON chapters(video_id);

-- 2. New columns on questions for chapter-aware quiz types
ALTER TABLE questions
    ADD COLUMN chapter_id UUID REFERENCES chapters(id),
    ADD COLUMN quiz_type VARCHAR(20) DEFAULT 'checkpoint'
        CHECK (quiz_type IN ('checkpoint', 'pretest', 'mid_recall', 'end_recall', 'remediation')),
    ADD COLUMN order_idx INT DEFAULT 0,
    ADD COLUMN bloom_level VARCHAR(20) DEFAULT 'understand'
        CHECK (bloom_level IN ('remember', 'understand', 'apply', 'analyse', 'evaluate')),
    ADD COLUMN option_explanations JSONB,
    ADD COLUMN misconception_tags TEXT[];

CREATE INDEX idx_questions_chapter_type ON questions(chapter_id, quiz_type);

-- 3. Quiz blocking mode on videos (admin per-video default)
ALTER TABLE videos
    ADD COLUMN quiz_blocking_mode VARCHAR(20) DEFAULT 'mandatory'
        CHECK (quiz_blocking_mode IN ('mandatory', 'optional'));

-- 4. User quiz preferences (user overrides video default)
CREATE TABLE user_quiz_prefs (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    pref VARCHAR(30) NOT NULL DEFAULT 'use_video_default'
        CHECK (pref IN ('use_video_default', 'always_pause', 'never_pause')),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 5. RLS policies for new tables
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_quiz_prefs ENABLE ROW LEVEL SECURITY;

-- Chapters: authenticated read, service_role write
CREATE POLICY "chapters_select" ON chapters FOR SELECT TO authenticated USING (true);
CREATE POLICY "chapters_insert" ON chapters FOR INSERT WITH CHECK (true);

-- User quiz prefs: owner-only
CREATE POLICY "uqp_owner" ON user_quiz_prefs FOR ALL TO authenticated
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
