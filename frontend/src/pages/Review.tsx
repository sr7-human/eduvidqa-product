import { useState, useEffect } from 'react';
import { Navbar } from '../components/Navbar';
import { getReviewQueue, submitReviewAttempt } from '../api/client';
import type { ReviewQuestion } from '../types';

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

  const handleAnswer = async (answer: string) => {
    if (!question) return;
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
  };

  const handleNext = () => {
    setCurrentIdx((prev) => prev + 1);
    setResult(null);
    setSelected(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-2xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4 text-gray-900">Review Queue</h1>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : isDone ? (
          <div className="text-center py-16 text-gray-900">
            {stats.total > 0 ? (
              <>
                <p className="text-3xl font-bold mb-2">
                  {stats.correct}/{stats.total}
                </p>
                <p className="text-gray-500 mb-4">Questions reviewed today</p>
              </>
            ) : null}
            <p className="text-xl">🎉 All caught up!</p>
            <p className="text-gray-500">No questions due for review.</p>
          </div>
        ) : question ? (
          <div className="bg-white rounded-xl shadow p-6 text-gray-900">
            <p className="text-xs text-gray-400 mb-1">
              {question.video_title || question.video_id}
            </p>

            <p className="font-medium text-lg mb-4">{question.question_text}</p>

            <div className="space-y-2 mb-4">
              {question.options.map((opt, i) => {
                const letter = String.fromCharCode(65 + i);
                const isSelected = selected === letter;
                const isCorrect = result?.correct_answer === letter;
                const isWrong = isSelected && result && !result.is_correct;

                let bg = 'bg-gray-50 hover:bg-gray-100 border-gray-200';
                if (result) {
                  if (isCorrect) bg = 'bg-green-100 border-green-500';
                  else if (isWrong) bg = 'bg-red-100 border-red-500';
                }

                return (
                  <button
                    key={letter}
                    onClick={() => !result && !submitting && handleAnswer(letter)}
                    disabled={!!result || submitting}
                    className={`w-full text-left p-3 rounded-lg border ${bg} disabled:cursor-default`}
                  >
                    <span className="font-semibold mr-2">{letter}.</span>
                    {opt}
                  </button>
                );
              })}
            </div>

            {result && (
              <div
                className={`p-3 rounded-lg mb-4 ${
                  result.is_correct ? 'bg-green-50' : 'bg-red-50'
                }`}
              >
                <p className="font-medium">
                  {result.is_correct ? '✅ Correct!' : '❌ Incorrect'}
                </p>
                <p className="text-sm text-gray-600 mt-1">{result.explanation}</p>
              </div>
            )}

            {result && (
              <button
                onClick={handleNext}
                className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                {currentIdx === questions.length - 1 ? 'Finish' : 'Next question'}
              </button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
