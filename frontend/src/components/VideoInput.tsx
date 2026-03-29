import { useState, type FormEvent } from 'react';
import { motion } from 'framer-motion';
import { extractVideoId } from '../api/client';

interface Props {
  onSubmit: (url: string, timestamp: number, question: string) => void;
  isLoading: boolean;
}

export default function VideoInput({ onSubmit, isLoading }: Props) {
  const [url, setUrl] = useState('');
  const [minutes, setMinutes] = useState('');
  const [seconds, setSeconds] = useState('');
  const [question, setQuestion] = useState('');
  const [urlError, setUrlError] = useState('');

  const videoId = extractVideoId(url);
  const thumbnailUrl = videoId
    ? `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`
    : null;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!videoId) {
      setUrlError('Please enter a valid YouTube URL');
      return;
    }
    setUrlError('');
    const ts = (parseInt(minutes || '0', 10) * 60) + parseInt(seconds || '0', 10);
    onSubmit(url, ts, question);
  }

  return (
    <motion.form
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      onSubmit={handleSubmit}
      className="bg-dark-card border border-dark-border rounded-2xl p-6 space-y-5"
    >
      {/* YouTube URL */}
      <div>
        <label htmlFor="url" className="block text-sm font-medium text-gray-300 mb-1.5">
          YouTube URL
        </label>
        <input
          id="url"
          type="url"
          value={url}
          onChange={(e) => { setUrl(e.target.value); setUrlError(''); }}
          placeholder="https://www.youtube.com/watch?v=..."
          className="w-full bg-dark-bg border border-dark-border rounded-lg px-4 py-2.5 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent transition"
        />
        {urlError && <p className="text-red-400 text-sm mt-1">{urlError}</p>}
      </div>

      {/* Thumbnail preview */}
      {thumbnailUrl && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-xl overflow-hidden border border-dark-border"
        >
          <img
            src={thumbnailUrl}
            alt="Video thumbnail"
            className="w-full h-auto"
          />
        </motion.div>
      )}

      {/* Timestamp */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1.5">
          Timestamp
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0"
            max="999"
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
            placeholder="MM"
            className="w-20 bg-dark-bg border border-dark-border rounded-lg px-3 py-2.5 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent transition text-center"
          />
          <span className="text-gray-400 text-xl font-bold">:</span>
          <input
            type="number"
            min="0"
            max="59"
            value={seconds}
            onChange={(e) => setSeconds(e.target.value)}
            placeholder="SS"
            className="w-20 bg-dark-bg border border-dark-border rounded-lg px-3 py-2.5 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent transition text-center"
          />
          <span className="text-gray-500 text-sm ml-2">
            {minutes || seconds
              ? `= ${(parseInt(minutes || '0', 10) * 60) + parseInt(seconds || '0', 10)}s`
              : '(optional)'}
          </span>
        </div>
      </div>

      {/* Question */}
      <div>
        <label htmlFor="question" className="block text-sm font-medium text-gray-300 mb-1.5">
          Question
        </label>
        <textarea
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="What concept from the lecture would you like explained?"
          className="w-full bg-dark-bg border border-dark-border rounded-lg px-4 py-2.5 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent transition resize-none"
          required
        />
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={isLoading || !question.trim()}
        className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <span className="animate-spin">⏳</span> Processing...
          </>
        ) : (
          <>🔍 Ask Question</>
        )}
      </button>
    </motion.form>
  );
}
