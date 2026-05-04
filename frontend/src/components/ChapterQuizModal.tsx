import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  getChapterQuiz,
  submitAttempt,
} from '../api/client';
import type {
  AttemptResponse,
  QuizQuestion,
  QuizType,
} from '../types';

const TYPE_THEME: Record<QuizType, {
  emoji: string;
  title: string;
  blurb: string;
  ring: string;
  badge: string;
  cta: string;
}> = {
  pretest: {
    emoji: '🤔',
    title: 'Warm-up — what do you think?',
    blurb: "Don't worry about being wrong — that's the point. These questions prime your brain for what's coming.",
    ring: 'ring-amber-500/40',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    cta: 'bg-amber-600 hover:bg-amber-500',
  },
  mid_recall: {
    emoji: '🧠',
    title: 'Quick check',
    blurb: "Lock in what you just learned.",
    ring: 'ring-blue-500/40',
    badge: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
    cta: 'bg-blue-600 hover:bg-blue-500',
  },
  end_recall: {
    emoji: '✅',
    title: 'Chapter complete — lock it in',
    blurb: "Final recall to seal the chapter into memory.",
    ring: 'ring-emerald-500/40',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    cta: 'bg-emerald-600 hover:bg-emerald-500',
  },
  remediation: {
    emoji: '🎯',
    title: 'Targeted practice',
    blurb: "Quick drill on what you missed earlier.",
    ring: 'ring-purple-500/40',
    badge: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
    cta: 'bg-purple-600 hover:bg-purple-500',
  },
};

interface Props {
  videoId: string;
  chapterId: string;
  chapterTitle: string;
  quizType: QuizType;
  blocking: boolean;     // if true, no close button until done
  onClose: () => void;
}

interface AttemptState {
  result: AttemptResponse;
  selected: string;
}

export function ChapterQuizModal({
  videoId,
  chapterId,
  chapterTitle,
  quizType,
  blocking,
  onClose,
}: Props) {
  const theme = TYPE_THEME[quizType];

  const [questions, setQuestions] = useState<QuizQuestion[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [attempt, setAttempt] = useState<AttemptState | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showWrong, setShowWrong] = useState(false);  // accordion for "why are these wrong"
  const [score, setScore] = useState({ correct: 0, total: 0 });

  useEffect(() => {
    let cancelled = false;
    getChapterQuiz(videoId, chapterId, quizType)
      .then((data) => {
        if (!cancelled) setQuestions(data.questions);
      })
      .catch((e) => {
        toast.error(e instanceof Error ? e.message : 'Failed to load questions');
        if (!cancelled) onClose();
      });
    return () => { cancelled = true; };
  }, [videoId, chapterId, quizType, onClose]);

  const q = questions?.[idx];
  const total = questions?.length ?? 0;

  function letterFromOption(opt: string): string {
    // Options are formatted "A: ..."
    const m = opt.match(/^([A-D])\s*[:.\-]/);
    return m ? m[1] : opt[0]?.toUpperCase() ?? '?';
  }

  async function handleSubmit() {
    if (!q || !selected || submitting) return;
    setSubmitting(true);
    try {
      const result = await submitAttempt(q.id, selected);
      setAttempt({ result, selected });
      setScore((s) => ({
        correct: s.correct + (result.is_correct ? 1 : 0),
        total: s.total + 1,
      }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  }

  function handleNext() {
    if (idx + 1 < total) {
      setIdx(idx + 1);
      setSelected(null);
      setAttempt(null);
      setShowWrong(false);
    } else {
      // Last question — done
      onClose();
    }
  }

  // Loading state
  if (questions === null) {
    return (
      <Backdrop>
        <Card themeRing={theme.ring}>
          <div className="text-center py-10 text-gray-300">Loading questions...</div>
        </Card>
      </Backdrop>
    );
  }

  if (questions.length === 0) {
    return (
      <Backdrop onClick={blocking ? undefined : onClose}>
        <Card themeRing={theme.ring}>
          <div className="text-center py-10">
            <p className="text-gray-300 text-sm">No questions available for this chapter yet.</p>
            <button
              onClick={onClose}
              className="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg"
            >
              Close
            </button>
          </div>
        </Card>
      </Backdrop>
    );
  }

  if (!q) return null;

  const isAnswered = attempt !== null;
  const isLast = idx + 1 === total;
  const correct = attempt?.result.correct_answer ?? '?';
  const optExpl = attempt?.result.option_explanations ?? null;

  return (
    <Backdrop onClick={blocking ? undefined : onClose}>
      <Card themeRing={theme.ring}>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border ${theme.badge}`}>
              <span>{theme.emoji}</span>
              <span>{theme.title}</span>
            </div>
            <h3 className="text-white text-sm mt-1.5 font-medium truncate" title={chapterTitle}>
              {chapterTitle}
            </h3>
          </div>
          <div className="text-right shrink-0">
            <div className="text-xs text-gray-400">
              Q {idx + 1} of {total}
            </div>
            {score.total > 0 && (
              <div className="text-[11px] text-gray-500 mt-0.5">
                {score.correct} / {score.total}
              </div>
            )}
          </div>
        </div>

        <p className="text-[12px] text-gray-400 italic mb-4">{theme.blurb}</p>

        {/* Question */}
        <div className="mb-4">
          <p className="text-gray-100 text-[15px] leading-relaxed">{q.question_text}</p>
        </div>

        {/* Options */}
        <div className="space-y-2 mb-4">
          {q.options.map((opt, i) => {
            const letter = letterFromOption(opt);
            const isThis = selected === letter;
            const isCorrectOpt = isAnswered && letter === correct;
            const isPickedWrong = isAnswered && letter === attempt!.selected && !attempt!.result.is_correct;

            const base = 'w-full text-left rounded-lg border px-3 py-2 text-sm transition-colors';
            let cls = '';
            if (isAnswered) {
              if (isCorrectOpt) cls = 'border-emerald-500 bg-emerald-500/10 text-emerald-100';
              else if (isPickedWrong) cls = 'border-red-500 bg-red-500/10 text-red-100';
              else cls = 'border-dark-border bg-dark-bg/50 text-gray-400';
            } else if (isThis) {
              cls = 'border-accent bg-accent/10 text-white';
            } else {
              cls = 'border-dark-border bg-dark-bg hover:border-accent/50 text-gray-200';
            }

            return (
              <button
                key={i}
                onClick={() => !isAnswered && setSelected(letter)}
                disabled={isAnswered}
                className={`${base} ${cls}`}
              >
                {opt}
                {isAnswered && isCorrectOpt && <span className="ml-2">✅</span>}
                {isPickedWrong && <span className="ml-2">❌</span>}
              </button>
            );
          })}
        </div>

        {/* Explanation block, after answering */}
        {isAnswered && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-dark-bg/70 border border-dark-border rounded-lg p-3 text-sm space-y-2 mb-3"
          >
            {/* Correct option explanation */}
            {optExpl && optExpl[correct as 'A'|'B'|'C'|'D'] && (
              <div className="flex gap-2">
                <span className="text-emerald-400 shrink-0">✅ {correct}:</span>
                <span className="text-emerald-50">{optExpl[correct as 'A'|'B'|'C'|'D']}</span>
              </div>
            )}
            {/* Picked-wrong explanation */}
            {!attempt!.result.is_correct && optExpl && optExpl[attempt!.selected as 'A'|'B'|'C'|'D'] && (
              <div className="flex gap-2">
                <span className="text-red-400 shrink-0">❌ {attempt!.selected}:</span>
                <span className="text-red-100">{optExpl[attempt!.selected as 'A'|'B'|'C'|'D']}</span>
              </div>
            )}
            {/* Other distractors collapsed */}
            {optExpl && (() => {
              const others = (['A','B','C','D'] as const).filter(
                (l) => l !== correct && l !== attempt!.selected && optExpl[l],
              );
              if (others.length === 0) return null;
              return (
                <div className="border-t border-dark-border pt-2">
                  <button
                    onClick={() => setShowWrong((v) => !v)}
                    className="text-[12px] text-gray-400 hover:text-gray-200 underline-offset-2 hover:underline"
                  >
                    {showWrong ? '▲ Hide' : '▼ Why are the other options wrong?'}
                  </button>
                  {showWrong && (
                    <div className="mt-2 space-y-2">
                      {others.map((l) => (
                        <div key={l} className="flex gap-2 text-xs">
                          <span className="text-gray-500 shrink-0">{l}:</span>
                          <span className="text-gray-300">{optExpl[l]}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}
            {/* Fallback to legacy single-explanation if option_explanations is missing */}
            {!optExpl && attempt!.result.explanation && (
              <p className="text-gray-200">{attempt!.result.explanation}</p>
            )}
          </motion.div>
        )}

        {/* Footer */}
        <div className="flex justify-between items-center mt-2">
          {!blocking && !isAnswered ? (
            <button
              onClick={onClose}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              Skip for now
            </button>
          ) : <span />}
          {!isAnswered ? (
            <button
              onClick={handleSubmit}
              disabled={!selected || submitting}
              className={`px-5 py-2 text-white text-sm font-medium rounded-lg disabled:opacity-40 ${theme.cta}`}
            >
              {submitting ? 'Checking...' : 'Submit'}
            </button>
          ) : (
            <button
              onClick={handleNext}
              className={`px-5 py-2 text-white text-sm font-medium rounded-lg ${theme.cta}`}
            >
              {isLast ? 'Done — back to video ▶' : 'Next question →'}
            </button>
          )}
        </div>
      </Card>
    </Backdrop>
  );
}

// ── tiny presentational helpers ─────────────────────────────────

function Backdrop({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClick}
        className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

function Card({
  children,
  themeRing,
}: {
  children: React.ReactNode;
  themeRing: string;
}) {
  return (
    <motion.div
      initial={{ scale: 0.95, opacity: 0, y: 10 }}
      animate={{ scale: 1, opacity: 1, y: 0 }}
      exit={{ scale: 0.95, opacity: 0 }}
      onClick={(e) => e.stopPropagation()}
      className={`bg-dark-card border border-dark-border rounded-2xl shadow-2xl ring-2 ${themeRing} max-w-xl w-full p-5`}
    >
      {children}
    </motion.div>
  );
}
