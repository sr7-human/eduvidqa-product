import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Navbar } from '../components/Navbar';
import { listMyKeys, saveMyKey, deleteMyKey, getQuizPref, setQuizPref, getLlmPref, setLlmPref, getAvailableModels, getModelPrefs, setModelPrefs, getUsage, testKey, type StoredKey, type QuizPref, type LlmPref, type ModelOption, type ModelFeature, type ModelPrefs, type UsageInfo } from '../api/client';

const SERVICES: Array<{
  id: 'gemini' | 'groq' | 'openrouter';
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
  {
    id: 'openrouter',
    label: 'OpenRouter',
    helpUrl: 'https://openrouter.ai/keys',
    prefix: 'sk-or-…',
    blurb: 'Optional (paid). A reliable fallback for answers + quizzes with access to many models. You bring your own credits — your usage never affects other users.',
  },
];

export function Settings({ embedded = false, onClose }: { embedded?: boolean; onClose?: () => void } = {}) {
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
  const [models, setModels] = useState<{ gemini: ModelOption[]; openrouter: ModelOption[] } | null>(null);
  const [modelPrefs, setModelPrefsState] = useState<ModelPrefs>({});
  const [modelsLoading, setModelsLoading] = useState(true);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [testResult, setTestResult] = useState<Record<string, { ok: boolean; detail: string }>>({});

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
    Promise.all([getAvailableModels(), getModelPrefs()])
      .then(([m, p]) => { setModels(m); setModelPrefsState(p.model_prefs || {}); })
      .catch(() => {})
      .finally(() => setModelsLoading(false));
    getUsage().then(setUsage).catch(() => {});
  }, []);

  async function handleTestKey(service: 'gemini' | 'groq' | 'openrouter') {
    setTesting((t) => ({ ...t, [service]: true }));
    try {
      const r = await testKey(service);
      setTestResult((tr) => ({ ...tr, [service]: r }));
    } catch (e) {
      setTestResult((tr) => ({ ...tr, [service]: { ok: false, detail: e instanceof Error ? e.message : 'Failed' } }));
    } finally {
      setTesting((t) => ({ ...t, [service]: false }));
    }
  }

  async function updateModelPref(feature: ModelFeature, value: string) {
    const next = { ...modelPrefs, [feature]: value };
    setModelPrefsState(next);
    try {
      await setModelPrefs(next);
      toast.success('Model preference saved');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save model preference');
    }
  }

  const stored = (svc: 'gemini' | 'groq' | 'openrouter') => keys.find((k) => k.service === svc);

  async function handleSave(svc: 'gemini' | 'groq' | 'openrouter') {
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

  async function handleDelete(svc: 'gemini' | 'groq' | 'openrouter') {
    if (!confirm(`Remove your ${svc} key?`)) return;
    try {
      await deleteMyKey(svc);
      setKeys((prev) => prev.filter((k) => k.service !== svc));
      toast.success(`${svc} key removed`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to remove key');
    }
  }

  const content = (
      <div className="max-w-3xl mx-auto px-4 py-6 pb-20">
        {!embedded && (
          <Link to="/library" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            ← Back to Library
          </Link>
        )}

        <h1 className="text-2xl font-bold mt-4 mb-1 text-gray-900 dark:text-white">Settings</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Bring your own API keys. Each user pays for their own usage — your keys are stored
          encrypted in your account and never shared.
        </p>

        {/* Today's usage meter */}
        {usage && (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold text-gray-900 dark:text-white text-sm">Today's API usage</h2>
              <span className="text-xs text-gray-400">counting is passive — it doesn't spend quota</span>
            </div>
            {usage.total === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">No requests yet today.</p>
            ) : (
              <div className="space-y-2">
                {Object.entries(usage.by_provider).map(([prov, count]) => {
                  const cap = usage.free_rpd[prov];
                  const pct = cap ? Math.min(100, Math.round((count / cap) * 100)) : 0;
                  const near = cap && count >= cap * 0.8;
                  return (
                    <div key={prov}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="capitalize text-gray-700 dark:text-gray-300">{prov}</span>
                        <span className={near ? 'text-red-500 font-medium' : 'text-gray-500 dark:text-gray-400'}>
                          {count}{cap ? ` / ~${cap} free/day` : ' calls'}
                        </span>
                      </div>
                      {cap ? (
                        <div className="h-1.5 w-full rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                          <div className={`h-full rounded-full ${near ? 'bg-red-500' : 'bg-blue-600'}`} style={{ width: `${pct}%` }} />
                        </div>
                      ) : null}
                    </div>
                  );
                })}
                <p className="text-[11px] text-gray-400 dark:text-gray-500 pt-1">
                  Free-tier Gemini Flash is ~20 requests/day. One video (watching + quizzes) can use that up — enable billing or add another key for more.
                </p>
              </div>
            )}
          </div>
        )}

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
                    <div className="bg-gray-50 dark:bg-gray-900 rounded p-2 mb-3 text-sm">
                      <div className="flex items-center justify-between">
                        <code className="text-gray-700 dark:text-gray-300 font-mono">
                          {existing.masked}
                        </code>
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleTestKey(svc.id)}
                            disabled={testing[svc.id]}
                            className="text-xs text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50"
                          >
                            {testing[svc.id] ? 'Testing…' : 'Test key'}
                          </button>
                          <button
                            onClick={() => handleDelete(svc.id)}
                            className="text-xs text-red-600 dark:text-red-400 hover:underline"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                      {testResult[svc.id] && (
                        <p className={`text-xs mt-1 ${testResult[svc.id].ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                          {testResult[svc.id].ok ? '✓' : '✕'} {testResult[svc.id].detail}
                        </p>
                      )}
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

        {/* Per-feature model picker */}
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">Advanced: model per feature</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Pick the exact model for each feature. The list auto-updates with the latest models your key can use. "Auto" uses the recommended default with automatic fallback.
          </p>
          {modelsLoading ? (
            <p className="text-gray-500 dark:text-gray-400 text-sm py-4">Loading models…</p>
          ) : (
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-4">
              {([
                { feature: 'answers' as ModelFeature, label: 'Answers (Q&A chat)' },
                { feature: 'quizzes' as ModelFeature, label: 'Quizzes & pretests' },
                { feature: 'digest' as ModelFeature, label: 'Lecture digest' },
              ]).map(({ feature, label }) => (
                <div key={feature} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                  <label className="text-sm font-medium text-gray-900 dark:text-white sm:w-48 shrink-0">{label}</label>
                  <select
                    value={modelPrefs[feature] ?? 'auto'}
                    onChange={(e) => updateModelPref(feature, e.target.value)}
                    className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
                  >
                    <option value="auto">Auto (recommended)</option>
                    {models && models.gemini.length > 0 && (
                      <optgroup label="Gemini (your key)">
                        {models.gemini.map((m) => (
                          <option key={`g:${m.id}`} value={`gemini:${m.id}`}>{m.label}</option>
                        ))}
                      </optgroup>
                    )}
                    {models && models.openrouter.length > 0 && (
                      <optgroup label="OpenRouter">
                        {models.openrouter.map((m) => (
                          <option key={`o:${m.id}`} value={`openrouter:${m.id}`}>{m.label}</option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </div>
              ))}
              <p className="text-xs text-gray-400 dark:text-gray-500">
                Note: OpenRouter models require credits on the shared key. If a chosen model fails, the app automatically falls back.
              </p>
            </div>
          )}
        </div>

        <p className="text-xs text-gray-400 dark:text-gray-500 mt-8 text-center">
          Keys are validated against the provider on save. We never log or share keys.
          Delete your account in Library to wipe everything.
        </p>
      </div>
  );

  if (embedded) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 overflow-y-auto"
        onClick={onClose}
      >
        <div
          className="relative bg-gray-50 dark:bg-[#0a0e1a] rounded-2xl shadow-2xl w-full max-w-3xl my-8 max-h-[92vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="absolute top-3 right-4 text-gray-400 hover:text-gray-700 dark:hover:text-white text-2xl z-10"
          >
            ✕
          </button>
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a] overflow-y-auto">
      <Navbar />
      {content}
    </div>
  );
}
