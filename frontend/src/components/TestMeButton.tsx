import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import type { QuizQuestion } from '../types';
import { getQuiz } from '../api/client';

interface Props {
  videoId: string;
  currentTimestamp: number;
  onQuizReady: (questions: QuizQuestion[]) => void;
}

export function TestMeButton({ videoId, currentTimestamp, onQuizReady }: Props) {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleClick = async () => {
    setLoading(true);
    try {
      const { questions } = await getQuiz(videoId, currentTimestamp);
      if (!questions || questions.length === 0) {
        toast.error('No quiz available for this checkpoint yet. Try a different timestamp.');
        return;
      }
      onQuizReady(questions);
    } catch (err) {
      console.error('Quiz generation failed:', err);
      const status = (err as { status?: number })?.status;
      const msg = err instanceof Error ? err.message : 'Failed to load quiz';
      if (status === 402) {
        toast(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="text-sm">{msg}</span>
              <button
                className="px-3 py-1 bg-blue-600 text-white rounded text-sm whitespace-nowrap"
                onClick={() => {
                  toast.dismiss(t.id);
                  navigate('/settings');
                }}
              >
                Add Key
              </button>
            </div>
          ),
          { duration: 8000 },
        );
      } else {
        toast.error(msg);
      }
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
