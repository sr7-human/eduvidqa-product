import { useState } from 'react';
import type { QuizQuestion, AttemptResponse } from '../types';
import { submitAttempt } from '../api/client';

interface Props {
  questions: QuizQuestion[];
  onClose: () => void;
}

export function QuizPanel({ questions, onClose }: Props) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [score, setScore] = useState({ correct: 0, total: 0 });

  const question = questions[currentIdx];
  const isLast = currentIdx === questions.length - 1;
  const isDone = currentIdx >= questions.length;

  const handleAnswer = async (answer: string) => {
    setSelected(answer);
    setSubmitting(true);
    try {
      const res = await submitAttempt(question.id, answer);
      setResult(res);
      setScore((prev) => ({
        correct: prev.correct + (res.is_correct ? 1 : 0),
        total: prev.total + 1,
      }));
    } catch (err) {
      console.error('Submit failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleNext = () => {
    setCurrentIdx((prev) => prev + 1);
    setResult(null);
    setSelected(null);
  };

  if (isDone) {
    return (
      <div className="flex flex-col h-full p-4 bg-dark-card text-gray-100 border-l border-dark-border">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold">Quiz Complete</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            ✕
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-3xl font-bold mb-2">
              {score.correct}/{score.total}
            </p>
            <p className="text-gray-400">
              {score.correct === score.total
                ? '🎉 Perfect!'
                : score.correct > 0
                  ? '👍 Good effort!'
                  : '📚 Keep studying!'}
            </p>
            {score.total - score.correct > 0 && (
              <p className="text-sm text-amber-400 mt-2">
                {score.total - score.correct} question(s) added to review queue
              </p>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-full py-2 bg-accent hover:bg-accent-hover text-white rounded-lg mt-4"
        >
          Back to video
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full p-4 bg-dark-card text-gray-100 border-l border-dark-border overflow-y-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold">
          Quiz ({currentIdx + 1}/{questions.length})
        </h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
          ✕
        </button>
      </div>

      {/* Question */}
      <p className="font-medium mb-4 text-gray-100">{question.question_text}</p>

      {/* Options */}
      <div className="space-y-2 mb-4">
        {question.options.map((opt, i) => {
          const letter = String.fromCharCode(65 + i); // A, B, C, D
          const isSelected = selected === letter;
          const isCorrect = result?.correct_answer === letter;
          const isWrong = isSelected && result && !result.is_correct;

          let bg =
            'bg-dark-bg hover:bg-dark-border border-dark-border text-gray-100';
          if (result) {
            if (isCorrect)
              bg = 'bg-emerald-500/20 border-emerald-500 text-emerald-100';
            else if (isWrong)
              bg = 'bg-red-500/20 border-red-500 text-red-100';
            else bg = 'bg-dark-bg border-dark-border text-gray-400';
          }

          return (
            <button
              key={letter}
              onClick={() => !result && !submitting && handleAnswer(letter)}
              disabled={!!result || submitting}
              className={`w-full text-left p-3 rounded-lg border ${bg} disabled:cursor-default transition-colors`}
            >
              <span className="font-semibold mr-2">{letter}.</span>
              {opt}
            </button>
          );
        })}
      </div>

      {/* Result feedback */}
      {result && (
        <div
          className={`p-3 rounded-lg mb-4 border ${result.is_correct ? 'bg-emerald-500/10 border-emerald-500/40' : 'bg-red-500/10 border-red-500/40'}`}
        >
          <p className="font-medium text-gray-100">
            {result.is_correct ? '✅ Correct!' : '❌ Incorrect'}
          </p>
          <p className="text-sm text-gray-300 mt-1">{result.explanation}</p>
          {result.added_to_review && (
            <p className="text-xs text-amber-400 mt-1">Added to review queue</p>
          )}
        </div>
      )}

      {/* Next button */}
      {result && (
        <button
          onClick={handleNext}
          className="w-full py-2 bg-accent hover:bg-accent-hover text-white rounded-lg"
        >
          {isLast ? 'See results' : 'Next question'}
        </button>
      )}
    </div>
  );
}
