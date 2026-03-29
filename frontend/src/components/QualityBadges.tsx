import { motion } from 'framer-motion';
import type { QualityScores } from '../types';

const METRICS: { key: keyof QualityScores; label: string; tooltip: string }[] = [
  {
    key: 'clarity',
    label: 'Clarity',
    tooltip: 'How clear and understandable the answer is (1–5)',
  },
  {
    key: 'ect',
    label: 'ECT',
    tooltip: 'Educational Content Thoroughness — depth of explanation (1–5)',
  },
  {
    key: 'upt',
    label: 'UPT',
    tooltip: 'Use of Pedagogical Techniques — teaching quality (1–5)',
  },
];

function scoreColor(score: number): string {
  if (score >= 4) return 'bg-emerald-500';
  if (score >= 3) return 'bg-amber-500';
  return 'bg-red-500';
}

function scoreBorderColor(score: number): string {
  if (score >= 4) return 'border-emerald-500/30';
  if (score >= 3) return 'border-amber-500/30';
  return 'border-red-500/30';
}

interface Props {
  scores: QualityScores;
}

export default function QualityBadges({ scores }: Props) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {METRICS.map(({ key, label, tooltip }) => {
        const value = scores[key];
        return (
          <motion.div
            key={key}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`bg-dark-bg border ${scoreBorderColor(value)} rounded-xl p-3 text-center group relative`}
          >
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">
              {label}
            </p>
            <p className="text-xl font-bold text-gray-100">
              {value.toFixed(1)}
            </p>
            {/* Progress bar */}
            <div className="mt-2 h-1.5 bg-dark-border rounded-full overflow-hidden">
              <motion.div
                className={`h-full rounded-full ${scoreColor(value)}`}
                initial={{ width: 0 }}
                animate={{ width: `${(value / 5) * 100}%` }}
                transition={{ duration: 0.6, delay: 0.2 }}
              />
            </div>
            {/* Tooltip */}
            <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-gray-800 text-xs text-gray-300 px-3 py-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
              {tooltip}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
