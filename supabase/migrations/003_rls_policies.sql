ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyframe_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_queue ENABLE ROW LEVEL SECURITY;

-- Global tables: authenticated read, service_role write
CREATE POLICY "videos_select" ON videos FOR SELECT TO authenticated USING (true);
CREATE POLICY "videos_insert" ON videos FOR INSERT WITH CHECK (true);
CREATE POLICY "videos_update" ON videos FOR UPDATE USING (true);
CREATE POLICY "chunks_select" ON video_chunks FOR SELECT TO authenticated USING (true);
CREATE POLICY "chunks_insert" ON video_chunks FOR INSERT WITH CHECK (true);
CREATE POLICY "kf_select" ON keyframe_embeddings FOR SELECT TO authenticated USING (true);
CREATE POLICY "kf_insert" ON keyframe_embeddings FOR INSERT WITH CHECK (true);
CREATE POLICY "cp_select" ON checkpoints FOR SELECT TO authenticated USING (true);
CREATE POLICY "cp_insert" ON checkpoints FOR INSERT WITH CHECK (true);
CREATE POLICY "q_select" ON questions FOR SELECT TO authenticated USING (true);
CREATE POLICY "q_insert" ON questions FOR INSERT WITH CHECK (true);

-- User-owned tables: owner-only
CREATE POLICY "uv_owner" ON user_videos FOR ALL TO authenticated
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "qa_owner" ON quiz_attempts FOR ALL TO authenticated
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "rq_owner" ON review_queue FOR ALL TO authenticated
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
