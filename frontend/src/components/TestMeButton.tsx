import { useState } from 'react';
import type { QuizQuestion } from '../types';
import { getQuiz } from '../api/client';

interface Props {
  videoId: string;
  currentTimestamp: number;
  onQuizReady: (questions: QuizQuestion[]) => void;
}

export function TestMeButton({ videoId, currentTimestamp, onQuizReady }: Props) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const { questions } = await getQuiz(videoId, currentTimestamp);
      onQuizReady(questions);
    } catch (err) {
      console.error('Quiz generation failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded-full hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1.5 shadow-md"
    >
      {loading ? (
        <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
      ) : (
        '🧪'
      )}{' '}
      Test me
    </button>
  );
}
