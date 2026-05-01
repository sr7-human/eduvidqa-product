CREATE TABLE videos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id VARCHAR(11) NOT NULL,
    title TEXT,
    duration_seconds FLOAT,
    channel_name TEXT,
    pipeline_version INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    status_detail TEXT,
    digest TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (video_id, pipeline_version)
);

CREATE TABLE video_chunks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id VARCHAR(11) NOT NULL,
    chunk_id VARCHAR(20) NOT NULL,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1024),
    linked_keyframe_ids TEXT[],
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (video_id, chunk_id)
);

CREATE TABLE keyframe_embeddings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id VARCHAR(11) NOT NULL,
    keyframe_id VARCHAR(20) NOT NULL,
    timestamp_seconds FLOAT NOT NULL,
    storage_path TEXT NOT NULL,
    embedding vector(1024),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (video_id, keyframe_id)
);

CREATE TABLE user_videos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    video_id VARCHAR(11) NOT NULL,
    added_at TIMESTAMPTZ DEFAULT now(),
    last_watched_at TIMESTAMPTZ,
    last_position_seconds FLOAT DEFAULT 0,
    deleted_at TIMESTAMPTZ,
    UNIQUE (user_id, video_id)
);

CREATE INDEX idx_video_chunks_video_id ON video_chunks(video_id);
CREATE INDEX idx_videos_video_id ON videos(video_id);
CREATE INDEX idx_user_videos_user_id ON user_videos(user_id);
CREATE INDEX idx_video_chunks_embedding ON video_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_keyframe_embeddings_embedding ON keyframe_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
