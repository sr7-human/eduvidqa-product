// NOTE: This component is from the old single-page layout.
// The new split-screen layout uses ChatInterface instead.
// Keeping for potential reuse.

import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AskResponse } from '../types';
import QualityBadges from './QualityBadges';

interface Props {
  data: AskResponse;
}

export default function AnswerDisplay({ data }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-dark-card border border-dark-border rounded-2xl p-4 sm:p-6 space-y-5 sm:space-y-6"
    >
      <div className="prose prose-sm sm:prose-base prose-invert prose-indigo max-w-none overflow-x-auto prose-headings:text-gray-100 prose-p:text-gray-300 prose-strong:text-white prose-code:text-indigo-300 prose-code:bg-dark-bg prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-pre:bg-dark-bg prose-pre:border prose-pre:border-dark-border prose-pre:overflow-x-auto prose-blockquote:border-accent prose-blockquote:text-gray-400">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {data.answer}
        </ReactMarkdown>
      </div>

      {data.quality_scores && (
        <QualityBadges scores={data.quality_scores} />
      )}

      <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 pt-2 border-t border-dark-border">
        <span>⚡ Generated in {data.generation_time_seconds.toFixed(1)}s</span>
        <span>🤖 {data.model_name}</span>
      </div>
    </motion.div>
  );
}
