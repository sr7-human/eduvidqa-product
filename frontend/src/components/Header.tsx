import { motion } from 'framer-motion';

export default function Header() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center py-8"
    >
      <h1 className="text-4xl font-bold tracking-tight">
        <span className="mr-2">🎓</span>
        <span className="bg-gradient-to-r from-accent to-purple-400 bg-clip-text text-transparent">
          EduVidQA
        </span>
      </h1>
      <p className="mt-2 text-gray-400 text-lg">
        Ask questions about any YouTube lecture
      </p>
    </motion.header>
  );
}
