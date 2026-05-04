import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { ChatMessage, QualityScores } from '../types';
import { normalizeMath } from '../utils/normalizeMath';

// --- Sub-components ---

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

function QualityChip({ label, value }: { label: string; value: number }) {
  let color = 'bg-red-500/20 text-red-400';
  if (value >= 4) color = 'bg-emerald-500/20 text-emerald-400';
  else if (value >= 3) color = 'bg-amber-500/20 text-amber-400';

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}: {value.toFixed(1)}
    </span>
  );
}

function QualityBadges({ scores }: { scores: QualityScores }) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      <QualityChip label="Clarity" value={scores.clarity} />
      <QualityChip label="ECT" value={scores.ect} />
      <QualityChip label="UPT" value={scores.upt} />
    </div>
  );
}

function SourceLinks({
  sources,
  onSeek,
}: {
  sources: { start_time: number; end_time: number; relevance_score: number }[];
  onSeek: (seconds: number) => void;
}) {
  if (!sources.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {sources.map((src, i) => (
        <button
          key={i}
          onClick={() => onSeek(src.start_time)}
          className="inline-flex items-center gap-1 bg-dark-bg border border-dark-border hover:border-accent/50 rounded-lg px-2 py-1 text-xs transition-colors group"
        >
          <span className="text-gray-300 group-hover:text-accent transition-colors">
            📎 {formatTime(src.start_time)}–{formatTime(src.end_time)}
          </span>
          <span className="text-gray-500">
            ({Math.round(src.relevance_score * 100)}%)
          </span>
        </button>
      ))}
    </div>
  );
}

const LOADING_STEPS = [
  { emoji: '📥', text: 'Retrieving context...' },
  { emoji: '🧠', text: 'Generating answer...' },
  { emoji: '📊', text: 'Scoring quality...' },
];

function LoadingBubble() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, LOADING_STEPS.length - 1)), 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3 max-w-[85%]"
    >
      <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center text-sm shrink-0 mt-1">
        🤖
      </div>
      <div className="bg-dark-card border border-dark-border rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>{LOADING_STEPS[step].emoji}</span>
          <span>{LOADING_STEPS[step].text}</span>
          <span className="flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="w-1.5 h-1.5 bg-accent rounded-full"
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

// --- Main Component ---

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  timestamp: number;
  autoMode: boolean;
  onSend: (question: string) => void;
  onSeek: (seconds: number) => void;
  onInputFocus: () => void;
}

export default function ChatInterface({
  messages,
  isLoading,
  timestamp,
  autoMode,
  onSend,
  onSeek,
  onInputFocus,
}: Props) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Use 'auto' (instant) instead of 'smooth' so token-by-token streaming
    // doesn't queue up dozens of slow scroll animations.
    bottomRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [messages, isLoading]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput('');
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 py-12">
            <p className="text-3xl mb-3">💬</p>
            <p className="text-sm">Ask a question about the lecture.</p>
            <p className="text-xs mt-1 text-gray-600">
              Your current timestamp will be sent automatically.
            </p>
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center text-sm shrink-0 mt-1">
                  🤖
                </div>
              )}

              <div
                className={`max-w-[85%] ${
                  msg.role === 'user'
                    ? 'bg-accent/20 border border-accent/30 rounded-2xl rounded-tr-sm px-4 py-3'
                    : 'bg-dark-card border border-dark-border rounded-2xl rounded-tl-sm px-4 py-3'
                }`}
              >
                {/* User message */}
                {msg.role === 'user' && (
                  <>
                    <p className="text-gray-100 text-sm">{msg.content}</p>
                    {msg.timestamp !== undefined && (
                      <span className="inline-block mt-1.5 text-xs text-accent/70 bg-accent/10 px-2 py-0.5 rounded-full">
                        ⏱️ {formatTime(msg.timestamp)}
                      </span>
                    )}
                  </>
                )}

                {/* Assistant message */}
                {msg.role === 'assistant' && (
                  <>
                    <div className="prose prose-sm prose-invert prose-indigo max-w-none prose-headings:text-gray-100 prose-p:text-gray-300 prose-strong:text-white prose-code:text-indigo-300 prose-code:bg-dark-bg prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-pre:bg-dark-bg prose-pre:border prose-pre:border-dark-border prose-pre:overflow-x-auto prose-blockquote:border-accent prose-blockquote:text-gray-400 prose-li:text-gray-300">
                      {msg.content ? (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkMath]}
                          rehypePlugins={[rehypeKatex]}
                        >
                          {normalizeMath(msg.content)}
                        </ReactMarkdown>
                      ) : (
                        // Streaming placeholder — answer hasn't started yet.
                        <span className="inline-flex items-center gap-1 text-gray-400 text-sm">
                          <motion.span
                            className="w-1.5 h-1.5 bg-accent rounded-full"
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 1, repeat: Infinity }}
                          />
                          <motion.span
                            className="w-1.5 h-1.5 bg-accent rounded-full"
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
                          />
                          <motion.span
                            className="w-1.5 h-1.5 bg-accent rounded-full"
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 1, repeat: Infinity, delay: 0.4 }}
                          />
                        </span>
                      )}
                    </div>
                    {msg.quality && <QualityBadges scores={msg.quality} />}
                    {msg.sources && (
                      <SourceLinks sources={msg.sources} onSeek={onSeek} />
                    )}
                    {msg.generation_time_seconds && (
                      <p className="text-xs text-gray-600 mt-2">
                        ⚡ {msg.generation_time_seconds.toFixed(1)}s · {msg.model_name}
                      </p>
                    )}
                  </>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-full bg-emerald-500/20 flex items-center justify-center text-sm shrink-0 mt-1">
                  🧑‍🎓
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {isLoading && <LoadingBubble />}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-dark-border px-4 py-3 bg-dark-card/80 backdrop-blur-sm"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={onInputFocus}
            placeholder="Ask about the lecture..."
            disabled={isLoading}
            className="flex-1 bg-dark-bg border border-dark-border rounded-xl px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent transition disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shrink-0"
          >
            Send
          </button>
        </div>
        <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500">
          <span>⏱️ {formatTime(timestamp)}</span>
          <span>·</span>
          <span>{autoMode ? '🟢 auto' : '🔒 frozen'}</span>
        </div>
      </form>
    </div>
  );
}
