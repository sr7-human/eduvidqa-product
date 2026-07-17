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
  // Only show sources the retriever actually scored as relevant. Zero-relevance
  // chips (poor retrieval) look broken, so we hide them rather than confuse the
  // learner with a "(0%)" badge.
  const shown = sources.filter((s) => (s.relevance_score ?? 0) > 0.01);
  if (!shown.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {shown.map((src, i) => (
        <button
          key={i}
          onClick={() => onSeek(src.start_time)}
          className="inline-flex items-center gap-1 bg-dark-bg border border-dark-border hover:border-accent/50 rounded-lg px-2 py-1 text-xs transition-colors group"
        >
          <span className="text-gray-300 group-hover:text-accent transition-colors">
            📎 {formatTime(src.start_time)}–{formatTime(src.end_time)}
          </span>
        </button>
      ))}
    </div>
  );
}

function LoadingBubble({ statusText }: { statusText?: string }) {
  const text = statusText || 'Retrieving context…';

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
          <span>{text}</span>
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
  statusText?: string;
  timestamp: number;
  autoMode: boolean;
  onSend: (question: string, imageB64?: string) => void;
  onStop?: () => void;
  onSeek: (seconds: number) => void;
  onInputFocus: () => void;
}

export default function ChatInterface({
  messages,
  isLoading,
  statusText,
  timestamp,
  autoMode,
  onSend,
  onStop,
  onSeek,
  onInputFocus,
}: Props) {
  const [input, setInput] = useState('');
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Read an image File, downscale to ≤1280px JPEG (keeps payload small), and
  // stash it as a data URL to send alongside the next question.
  function readImageFile(file: File | null | undefined) {
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = () => {
      const src = reader.result as string;
      const img = new Image();
      img.onload = () => {
        const maxW = 1280;
        const scale = Math.min(1, maxW / img.width);
        const w = Math.round(img.width * scale);
        const h = Math.round(img.height * scale);
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        if (!ctx) { setPendingImage(src); return; }
        ctx.drawImage(img, 0, 0, w, h);
        setPendingImage(canvas.toDataURL('image/jpeg', 0.85));
      };
      img.onerror = () => setPendingImage(src);
      img.src = src;
    };
    reader.readAsDataURL(file);
  }

  function handlePaste(e: React.ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        readImageFile(items[i].getAsFile());
        e.preventDefault();
        break;
      }
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = Array.from(e.dataTransfer?.files ?? []).find((f) => f.type.startsWith('image/'));
    if (file) readImageFile(file);
  }

  useEffect(() => {
    // Use 'auto' (instant) instead of 'smooth' so token-by-token streaming
    // doesn't queue up dozens of slow scroll animations.
    bottomRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [messages, isLoading]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Allow sending even while a previous answer is still streaming — the
    // parent aborts the in-flight request and starts this one.
    if (!input.trim()) return;
    onSend(input.trim(), pendingImage ?? undefined);
    setInput('');
    setPendingImage(null);
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

        {isLoading && <LoadingBubble statusText={statusText} />}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <form
        onSubmit={handleSubmit}
        onDragOver={(e) => { e.preventDefault(); if (!dragOver) setDragOver(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
        onDrop={handleDrop}
        className={`border-t px-4 py-3 bg-dark-card/80 backdrop-blur-sm transition-colors ${dragOver ? 'border-accent ring-2 ring-accent/40' : 'border-dark-border'}`}
      >
        {dragOver && (
          <div className="mb-2 text-xs text-accent text-center py-2 border border-dashed border-accent/50 rounded-lg">
            🖼️ Drop your screenshot here
          </div>
        )}
        {pendingImage && (
          <div className="mb-2 flex items-center gap-2">
            <div className="relative">
              <img src={pendingImage} alt="attached" className="h-16 rounded-lg border border-dark-border object-cover" />
              <button
                type="button"
                onClick={() => setPendingImage(null)}
                className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-black/80 hover:bg-red-600 text-white text-xs flex items-center justify-center"
                title="Remove image"
                aria-label="Remove image"
              >
                ✕
              </button>
            </div>
            <span className="text-xs text-gray-500">Screenshot attached — sent with your question</span>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => { readImageFile(e.target.files?.[0]); e.target.value = ''; }}
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="px-3 py-2.5 rounded-xl border border-dark-border text-gray-400 hover:text-gray-100 hover:border-accent transition shrink-0"
            title="Attach a screenshot (or just paste one)"
            aria-label="Attach a screenshot"
          >
            📎
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={onInputFocus}
            onPaste={handlePaste}
            placeholder="Ask about the lecture..."
            className="flex-1 bg-dark-bg border border-dark-border rounded-xl px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent transition disabled:opacity-50"
          />
          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shrink-0 flex items-center gap-1.5"
              title="Stop generating"
            >
              <span className="w-2.5 h-2.5 bg-white rounded-[2px]" />
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shrink-0"
            >
              Send
            </button>
          )}
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
