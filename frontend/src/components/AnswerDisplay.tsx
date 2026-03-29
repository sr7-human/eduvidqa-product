import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AskResponse } from '../types';
import QualityBadges from './QualityBadges';
import SourceTimestamps from './SourceTimestamps';

interface Props {
  data: AskResponse;
}

export default function AnswerDisplay({ data }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-dark-card border border-dark-border rounded-2xl p-6 space-y-6"
    >
      {/* Answer */}
      <div className="prose prose-invert prose-indigo max-w-none prose-headings:text-gray-100 prose-p:text-gray-300 prose-strong:text-white prose-code:text-indigo-300 prose-code:bg-dark-bg prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-pre:bg-dark-bg prose-pre:border prose-pre:border-dark-border prose-blockquote:border-accent prose-blockquote:text-gray-400">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {data.answer}
        </ReactMarkdown>
      </div>

      {/* Quality scores */}
      {data.quality_scores && (
        <QualityBadges scores={data.quality_scores} />
      )}

      {/* Sources */}
      <SourceTimestamps videoId={data.video_id} sources={data.sources} />

      {/* Footer meta */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 pt-2 border-t border-dark-border">
        <span>⚡ Generated in {data.generation_time_seconds.toFixed(1)}s</span>
        <span>🤖 {data.model_name}</span>
      </div>
    </motion.div>
  );
}
