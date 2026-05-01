import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { getReviewQueue, submitReviewAttempt } from '../api/client';
import type { ReviewQuestion } from '../types';

const BLOOM_STYLES: Record<string, string> = {
  remember:   'bg-gray-700 text-gray-100',
  understand: 'bg-blue-700 text-blue-100',
  apply:      'bg-green-700 text-green-100',
  analyse:    'bg-yellow-700 text-yellow-100',
  evaluate:   'bg-purple-700 text-purple-100',
};

/** Strip a leading "A: " / "A. " / "A) " prefix that the LLM sometimes embeds in option text. */
function cleanOption(opt: string): string {
  return opt.replace(/^\s*[A-D]\s*[:.\)]\s*/i, '').trim();
}

export function Review() {
  const [questions, setQuestions] = useState<ReviewQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<{
    is_correct: boolean;
    correct_answer: string;
    explanation: string;
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [stats, setStats] = useState({ correct: 0, total: 0 });

  useEffect(() => {
    getReviewQueue()
      .then((data) => setQuestions(data.questions))
      .catch(() => {
        /* leave empty */
      })
      .finally(() => setLoading(false));
  }, []);

  const question = questions[currentIdx];
  const isDone = !loading && (questions.length === 0 || currentIdx >= questions.length);
  const progressPct = questions.length > 0 ? (currentIdx / questions.length) * 100 : 0;

  const handleAnswer = useCallback(
    async (answer: string) => {
      if (!question || result || submitting) return;
      setSelected(answer);
      setSubmitting(true);
      try {
        const res = await submitReviewAttempt(question.id, answer);
        setResult(res);
        setStats((prev) => ({
          correct: prev.correct + (res.is_correct ? 1 : 0),
          total: prev.total + 1,
        }));
      } catch (err) {
        console.error(err);
      } finally {
        setSubmitting(false);
      }
    },
    [question, result, submitting],
  );

  const handleNext = useCallback(() => {
    setCurrentIdx((prev) => prev + 1);
    setResult(null);
    setSelected(null);
  }, []);

  // Keyboard shortcuts: 1-4 → A-D, Enter/Space → Next
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (loading || isDone) return;
      if (!result && e.key >= '1' && e.key <= '4') {
        const letter = String.fromCharCode(64 + parseInt(e.key, 10));
        handleAnswer(letter);
      } else if (result && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        handleNext();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [loading, isDone, result, handleAnswer, handleNext]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a]">
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-6">
        {/* Header row: back + progress */}
        <div className="flex items-center justify-between mb-6">
          <Link to="/library" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            ← Back to Library
          </Link>
          {!isDone && questions.length > 0 && (
            <div className="text-sm text-gray-500 dark:text-gray-400">
              Question{' '}
              <span className="font-semibold text-gray-900 dark:text-white">{currentIdx + 1}</span> of{' '}
              <span className="font-semibold text-gray-900 dark:text-white">{questions.length}</span>
            </div>
          )}
        </div>

        <h1 className="text-2xl font-bold mb-1 text-gray-900 dark:text-white">Review Queue</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Spaced repetition — questions you got wrong, served back when you're most likely to forget.
        </p>

        {/* Progress bar */}
        {!isDone && questions.length > 0 && (
          <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full mb-6 overflow-hidden">
            <div className="h-full bg-blue-500 transition-all duration-300" style={{ width: `${progressPct}%` }} />
          </div>
        )}

        {loading ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-12">Loading…</p>
        ) : isDone ? (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-10 text-center">
            <div className="text-6xl mb-4">🎉</div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">All caught up!</h2>
            {stats.total > 0 ? (
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                You answered{' '}
                <span className="font-semibold text-gray-900 dark:text-white">
                  {stats.correct}/{stats.total}
                </span>{' '}
                correctly this session.
              </p>
            ) : (
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                No questions are due for review right now. Come back later — wrong answers from quizzes will appear here.
              </p>
            )}
            <Link
              to="/library"
              className="inline-block px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium"
            >
              Back to Library
            </Link>
          </div>
        ) : question ? (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 sm:p-8 shadow-sm">
            {/* Source video link + bloom badge */}
            <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
              <Link
                to={`/watch/${question.video_id}`}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline truncate max-w-[70%]"
                title={question.video_title || question.video_id}
              >
                ↳ {question.video_title || question.video_id}
              </Link>
              {question.bloom_level && (
                <span
                  className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded font-semibold ${
                    BLOOM_STYLES[question.bloom_level] || 'bg-gray-600 text-gray-100'
                  }`}
                >
                  {question.bloom_level}
                </span>
              )}
            </div>

            <p className="font-medium text-lg text-gray-900 dark:text-white mb-5 leading-relaxed">
              {question.question_text}
            </p>

            <div className="space-y-2 mb-5">
              {question.options.map((opt, i) => {
                const letter = String.fromCharCode(65 + i);
                const isSelected = selected === letter;
                const isCorrect = result?.correct_answer === letter;
                const isWrong = isSelected && result && !result.is_correct;

                let cls =
                  'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-gray-800 text-gray-900 dark:text-gray-100';
                if (result) {
                  if (isCorrect)
                    cls = 'bg-green-50 dark:bg-green-900/30 border-green-500 text-green-900 dark:text-green-100';
                  else if (isWrong)
                    cls = 'bg-red-50 dark:bg-red-900/30 border-red-500 text-red-900 dark:text-red-100';
                  else
                    cls = 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-500';
                }

                return (
                  <button
                    key={letter}
                    onClick={() => handleAnswer(letter)}
                    disabled={!!result || submitting}
                    className={`w-full text-left px-4 py-3 rounded-lg border-2 transition flex items-start gap-3 disabled:cursor-default ${cls}`}
                  >
                    <span
                      className={`flex-shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                        result && isCorrect
                          ? 'bg-green-500 text-white'
                          : result && isWrong
                          ? 'bg-red-500 text-white'
                          : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      {letter}
                    </span>
                    <span className="flex-1 text-sm sm:text-base leading-snug">{cleanOption(opt)}</span>
                  </button>
                );
              })}
            </div>

            {result && (
              <div
                className={`p-4 rounded-lg mb-4 border ${
                  result.is_correct
                    ? 'bg-green-50 dark:bg-green-900/20 border-green-300 dark:border-green-800'
                    : 'bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-800'
                }`}
              >
                <p
                  className={`font-semibold mb-1 ${
                    result.is_correct ? 'text-green-800 dark:text-green-300' : 'text-red-800 dark:text-red-300'
                  }`}
                >
                  {result.is_correct
                    ? '✅ Correct!'
                    : `❌ Incorrect — correct answer is ${result.correct_answer}`}
                </p>
                {result.explanation && (
                  <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{result.explanation}</p>
                )}
              </div>
            )}

            {result ? (
              <button
                onClick={handleNext}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
              >
                {currentIdx === questions.length - 1 ? 'Finish' : 'Next question'}
                <span className="ml-2 text-xs opacity-75">(Enter)</span>
              </button>
            ) : (
              <p className="text-xs text-gray-400 dark:text-gray-500 text-center">
                Tip: press{' '}
                <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-mono">
                  1
                </kbd>
                –
                <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-mono">
                  4
                </kbd>{' '}
                to pick an answer
              </p>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
