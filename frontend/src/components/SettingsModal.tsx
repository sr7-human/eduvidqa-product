import { useState, useEffect } from 'react';

const STORAGE_KEY = 'eduvidqa_gemini_key';

export function getGeminiKey(): string {
  return localStorage.getItem(STORAGE_KEY) ?? '';
}

export function setGeminiKey(key: string) {
  if (key.trim()) {
    localStorage.setItem(STORAGE_KEY, key.trim());
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export function hasGeminiKey(): boolean {
  return !!getGeminiKey();
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: Props) {
  const [key, setKey] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setKey(getGeminiKey());
      setSaved(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  function handleSave() {
    setGeminiKey(key);
    setSaved(true);
    setTimeout(() => onClose(), 800);
  }

  function handleClear() {
    setKey('');
    setGeminiKey('');
    setSaved(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-dark-card border border-dark-border rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-100">⚙️ Settings</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-xl">×</button>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Gemini API Key
          </label>
          <p className="text-xs text-gray-500 mb-3">
            Get a free key at{' '}
            <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
              aistudio.google.com/apikey
            </a>
            . Stored locally in your browser. Sent with your requests but never saved on our server.
          </p>
          <input
            type="password"
            value={key}
            onChange={(e) => { setKey(e.target.value); setSaved(false); }}
            placeholder="AIzaSy..."
            className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-200 text-sm placeholder-gray-600 focus:outline-none focus:border-accent"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            className="flex-1 px-4 py-2 bg-accent hover:bg-accent/80 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saved ? '✓ Saved' : 'Save Key'}
          </button>
          {key && (
            <button
              onClick={handleClear}
              className="px-4 py-2 bg-dark-bg hover:bg-dark-border text-gray-400 rounded-lg text-sm transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        <div className="mt-4 pt-4 border-t border-dark-border">
          <p className="text-xs text-gray-600">
            🔒 Your key stays in localStorage. It's sent directly to Google's API via our backend, never logged or stored server-side.
          </p>
        </div>
      </div>
    </div>
  );
}
