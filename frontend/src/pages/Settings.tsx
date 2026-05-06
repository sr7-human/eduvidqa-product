import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import { listMyKeys, saveMyKey, deleteMyKey, getQuizPref, setQuizPref, getLlmPref, setLlmPref, type StoredKey, type QuizPref, type LlmPref } from '../api/client';

const SERVICES: Array<{
  id: 'gemini' | 'groq';
  label: string;
  helpUrl: string;
  prefix: string;
  blurb: string;
}> = [
  {
    id: 'gemini',
    label: 'Google Gemini',
    helpUrl: 'https://aistudio.google.com/app/apikey',
    prefix: 'AIza…',
    blurb: 'Powers embeddings + answers + quizzes. Free tier: 20 chat calls/day, but embeddings are nearly unlimited. Recommended.',
  },
  {
    id: 'groq',
    label: 'Groq',
    helpUrl: 'https://console.groq.com/keys',
    prefix: 'gsk_…',
    blurb: 'Optional. Used for answers + quizzes. Free tier is much higher (thousands/day) and 5–10× faster than Gemini.',
  },
];

export function Settings() {
  const [keys, setKeys] = useState<StoredKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [quizPref, setQuizPrefState] = useState<QuizPref>('use_video_default');
  const [quizPrefLoading, setQuizPrefLoading] = useState(true);
  const [quizPrefSaving, setQuizPrefSaving] = useState(false);
  const [llmPref, setLlmPrefState] = useState<LlmPref>('auto');
  const [llmPrefLoading, setLlmPrefLoading] = useState(true);
  const [llmPrefSaving, setLlmPrefSaving] = useState(false);

  useEffect(() => {
    listMyKeys()
      .then((r) => setKeys(r.keys))
      .catch(() => {
        /* ignore */
      })
      .finally(() => setLoading(false));
    getQuizPref()
      .then((r) => setQuizPrefState(r.pref))
      .catch(() => {})
      .finally(() => setQuizPrefLoading(false));
    getLlmPref()
      .then((r) => setLlmPrefState(r.llm_pref))
      .catch(() => {})
      .finally(() => setLlmPrefLoading(false));
  }, []);

  const stored = (svc: 'gemini' | 'groq') => keys.find((k) => k.service === svc);

  async function handleSave(svc: 'gemini' | 'groq') {
    const value = (inputs[svc] || '').trim();
    if (!value) {
      toast.error('Paste a key first');
      return;
    }
    setSaving((p) => ({ ...p, [svc]: true }));
    try {
      const res = await saveMyKey(svc, value);
      toast.success('Key validated and saved');
      setKeys((prev) => [
        ...prev.filter((k) => k.service !== svc),
        { service: svc, masked: res.masked, updated_at: new Date().toISOString() },
      ]);
      setInputs((p) => ({ ...p, [svc]: '' }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save key');
    } finally {
      setSaving((p) => ({ ...p, [svc]: false }));
    }
  }

  async function handleDelete(svc: 'gemini' | 'groq') {
    if (!confirm(`Remove your ${svc} key?`)) return;
    try {
      await deleteMyKey(svc);
      setKeys((prev) => prev.filter((k) => k.service !== svc));
      toast.success(`${svc} key removed`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to remove key');
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a] overflow-y-auto">
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-6 pb-20">
        <Link to="/library" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
          ← Back to Library
        </Link>

        <h1 className="text-2xl font-bold mt-4 mb-1 text-gray-900 dark:text-white">Settings</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Bring your own API keys. Each user pays for their own usage — your keys are stored
          encrypted in your account and never shared.
        </p>

        {/* Why box */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
          <h2 className="font-semibold text-blue-900 dark:text-blue-200 mb-1 text-sm">
            Why you need a key
          </h2>
          <p className="text-sm text-blue-800 dark:text-blue-300 leading-relaxed">
            EduVidQA processes videos using AI services that charge per request. Free hosted
            instances would burn through their daily quota in minutes. Add a free Gemini or Groq
            key to get your own quota — typically <strong>thousands of free requests per day</strong>.
            The demo video works without any key.
          </p>
        </div>

        {loading ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-8">Loading…</p>
        ) : (
          <div className="space-y-5">
            {SERVICES.map((svc) => {
              const existing = stored(svc.id);
              const inputVal = inputs[svc.id] || '';
              const isSaving = saving[svc.id];
              return (
                <div
                  key={svc.id}
                  className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5"
                >
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white">{svc.label}</h3>
                    {existing ? (
                      <span className="inline-flex items-center text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-medium">
                        ✓ stored
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 font-medium">
                        not set
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 leading-relaxed">
                    {svc.blurb}
                  </p>
                  <a
                    href={svc.helpUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block text-xs text-blue-600 dark:text-blue-400 hover:underline mb-3"
                  >
                    Get a free {svc.label} key →
                  </a>

                  {existing && (
                    <div className="flex items-center justify-between bg-gray-50 dark:bg-gray-900 rounded p-2 mb-3 text-sm">
                      <code className="text-gray-700 dark:text-gray-300 font-mono">
                        {existing.masked}
                      </code>
                      <button
                        onClick={() => handleDelete(svc.id)}
                        className="text-xs text-red-600 dark:text-red-400 hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <input
                      type="password"
                      value={inputVal}
                      onChange={(e) => setInputs((p) => ({ ...p, [svc.id]: e.target.value }))}
                      placeholder={existing ? 'Paste a new key to replace' : `${svc.prefix} paste here`}
                      className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 font-mono"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSave(svc.id);
                      }}
                    />
                    <button
                      onClick={() => handleSave(svc.id)}
                      disabled={isSaving || !inputVal}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg disabled:opacity-40"
                    >
                      {isSaving ? 'Validating…' : 'Save'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Quiz preferences */}
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">Quiz preferences</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Control whether quizzes pause the video automatically.
          </p>
          {quizPrefLoading ? (
            <p className="text-gray-500 dark:text-gray-400 text-sm py-4">Loading…</p>
          ) : (
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-3">
              {([
                { value: 'use_video_default' as QuizPref, label: 'Use video default', desc: 'Follow the setting chosen by the video admin.' },
                { value: 'always_pause' as QuizPref, label: 'Always pause for quizzes', desc: 'Video pauses and a quiz modal appears at every checkpoint.' },
                { value: 'never_pause' as QuizPref, label: 'Never pause (optional quizzes)', desc: 'Quizzes appear as a small toast — click to open, or ignore.' },
              ]).map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                    quizPref === opt.value
                      ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-700/50 border border-transparent'
                  }`}
                >
                  <input
                    type="radio"
                    name="quizPref"
                    value={opt.value}
                    checked={quizPref === opt.value}
                    disabled={quizPrefSaving}
                    onChange={async () => {
                      setQuizPrefSaving(true);
                      try {
                        await setQuizPref(opt.value);
                        setQuizPrefState(opt.value);
                        toast.success('Quiz preference updated');
                      } catch (e) {
                        toast.error(e instanceof Error ? e.message : 'Failed to update preference');
                      } finally {
                        setQuizPrefSaving(false);
                      }
                    }}
                    className="mt-1"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{opt.label}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* LLM preference */}
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">Answer model</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Choose which LLM generates your answers. Embeddings always use Gemini regardless of this setting.
          </p>
          {llmPrefLoading ? (
            <p className="text-gray-500 dark:text-gray-400 text-sm py-4">Loading…</p>
          ) : (
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-3">
              {([
                { value: 'auto' as LlmPref, label: 'Auto (recommended)', desc: 'Tries Groq first (faster), falls back to Gemini if unavailable.' },
                { value: 'groq' as LlmPref, label: 'Groq only', desc: 'Llama 4 Scout via Groq — fast (2-5s), high free quota. May fail if key is missing/expired.' },
                { value: 'gemini' as LlmPref, label: 'Gemini only', desc: 'Gemini 2.5 Flash — reliable but slower (10-20s). Lower free quota.' },
              ]).map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                    llmPref === opt.value
                      ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-700/50 border border-transparent'
                  }`}
                >
                  <input
                    type="radio"
                    name="llmPref"
                    value={opt.value}
                    checked={llmPref === opt.value}
                    disabled={llmPrefSaving}
                    onChange={async () => {
                      setLlmPrefSaving(true);
                      try {
                        await setLlmPref(opt.value);
                        setLlmPrefState(opt.value);
                        toast.success('Answer model updated');
                      } catch (e) {
                        toast.error(e instanceof Error ? e.message : 'Failed to update preference');
                      } finally {
                        setLlmPrefSaving(false);
                      }
                    }}
                    className="mt-1"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{opt.label}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </div>

        <p className="text-xs text-gray-400 dark:text-gray-500 mt-8 text-center">
          Keys are validated against the provider on save. We never log or share keys.
          Delete your account in Library to wipe everything.
        </p>
      </div>
    </div>
  );
}
