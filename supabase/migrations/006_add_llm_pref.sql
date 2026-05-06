ALTER TABLE user_quiz_prefs
ADD COLUMN IF NOT EXISTS llm_pref VARCHAR(20) NOT NULL DEFAULT 'auto';

COMMENT ON COLUMN user_quiz_prefs.llm_pref IS 'Preferred LLM for answers: auto (Groq→Gemini fallback), groq, gemini';
