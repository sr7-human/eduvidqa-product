import { motion } from 'framer-motion';

const NAV_LINKS = [
  { label: 'Architecture', href: '/diagrams/index.html' },
  { label: 'Tracker', href: '/tracker.html' },
  { label: 'Paper', href: 'https://sr7-human.github.io/eduvidqa-explained/' },
  { label: 'GitHub', href: 'https://github.com/sr7-human/eduvidqa-product' },
];

export default function Header() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-dark-border bg-dark-card/80 backdrop-blur-sm"
    >
      <div className="flex items-center gap-2">
        <span className="text-xl">🎓</span>
        <span className="text-lg font-bold bg-gradient-to-r from-accent to-purple-400 bg-clip-text text-transparent">
          EduVidQA
        </span>
      </div>
      <nav className="hidden sm:flex items-center gap-4">
        {NAV_LINKS.map((link) => (
          <a
            key={link.label}
            href={link.href}
            target={link.href.startsWith('http') ? '_blank' : undefined}
            rel={link.href.startsWith('http') ? 'noopener noreferrer' : undefined}
            className="text-sm text-gray-400 hover:text-gray-100 transition-colors"
          >
            {link.label}
          </a>
        ))}
      </nav>
    </motion.header>
  );
}
