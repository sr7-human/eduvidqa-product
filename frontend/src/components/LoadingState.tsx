import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';

const STEPS = [
  { emoji: '📥', text: 'Downloading transcript...' },
  { emoji: '🔍', text: 'Finding relevant sections...' },
  { emoji: '🧠', text: 'Generating answer...' },
];

export default function LoadingState() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => (s < STEPS.length - 1 ? s + 1 : s));
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="bg-dark-card border border-dark-border rounded-2xl p-8 text-center"
    >
      <div className="flex flex-col items-center gap-4">
        {/* Animated dots */}
        <div className="flex gap-1.5">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-3 h-3 bg-accent rounded-full"
              animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </div>

        {/* Step indicator */}
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="text-lg"
          >
            <span className="mr-2">{STEPS[step].emoji}</span>
            <span className="text-gray-300">{STEPS[step].text}</span>
          </motion.div>
        </AnimatePresence>

        {/* Progress bar */}
        <div className="w-full max-w-xs bg-dark-bg rounded-full h-1.5 overflow-hidden">
          <motion.div
            className="h-full bg-accent rounded-full"
            initial={{ width: '0%' }}
            animate={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>

        <p className="text-gray-500 text-sm">
          This usually takes 10–30 seconds
        </p>
      </div>
    </motion.div>
  );
}
