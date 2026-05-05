-- 005: Dual-dimension embedding support (1024 → 3072)
-- Adds embedding_v2 vector(3072) columns alongside existing vector(1024).
-- New videos write to v2 only. Old videos keep using v1.
-- Retrieval checks v2 first, falls back to v1.

ALTER TABLE video_chunks ADD COLUMN IF NOT EXISTS embedding_v2 vector(3072);
ALTER TABLE keyframe_embeddings ADD COLUMN IF NOT EXISTS embedding_v2 vector(3072);

-- NOTE: pgvector HNSW index max 2000 dims. ivfflat supports 3072 but needs
-- existing rows to build. Create ivfflat indexes AFTER first video is ingested:
-- CREATE INDEX idx_video_chunks_embedding_v2 ON video_chunks
--     USING ivfflat (embedding_v2 vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_keyframe_embeddings_v2 ON keyframe_embeddings
--     USING ivfflat (embedding_v2 vector_cosine_ops) WITH (lists = 100);
