import { motion } from 'framer-motion';

interface Props {
  message: string;
  onRetry?: () => void;
}

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-dark-card border border-red-500/30 rounded-2xl p-6 text-center"
    >
      <p className="text-3xl mb-3">😕</p>
      <p className="text-red-400 font-medium mb-1">Something went wrong</p>
      <p className="text-gray-500 text-sm mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="bg-accent hover:bg-accent-hover text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
        >
          Try Again
        </button>
      )}
    </motion.div>
  );
}
