CREATE TABLE checkpoints (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id VARCHAR(11) NOT NULL,
    timestamp_seconds FLOAT NOT NULL,
    topic_label TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (video_id, timestamp_seconds)
);

CREATE TABLE questions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id VARCHAR(11) NOT NULL,
    checkpoint_id UUID REFERENCES checkpoints(id),
    ts_bucket_30s INT NOT NULL,
    prompt_version INT NOT NULL DEFAULT 1,
    question_text TEXT NOT NULL,
    options JSONB,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    difficulty VARCHAR(10) DEFAULT 'medium'
        CHECK (difficulty IN ('easy', 'medium', 'hard')),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (video_id, ts_bucket_30s, prompt_version, question_text)
);

CREATE TABLE quiz_attempts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES questions(id),
    selected_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    attempted_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE review_queue (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES questions(id),
    next_review_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    interval_days INT NOT NULL DEFAULT 1,
    ease_factor FLOAT NOT NULL DEFAULT 2.5,
    repetitions INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, question_id)
);

CREATE INDEX idx_questions_video_bucket ON questions(video_id, ts_bucket_30s);
CREATE INDEX idx_quiz_attempts_user ON quiz_attempts(user_id);
CREATE INDEX idx_review_queue_user_due ON review_queue(user_id, next_review_at);
