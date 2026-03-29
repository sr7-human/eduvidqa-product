import { AnimatePresence } from 'framer-motion';
import Header from './components/Header';
import VideoInput from './components/VideoInput';
import AnswerDisplay from './components/AnswerDisplay';
import LoadingState from './components/LoadingState';
import ErrorState from './components/ErrorState';
import { useAskQuestion } from './hooks/useAskQuestion';

export default function App() {
  const { mutate, data, isPending, isError, error, reset } = useAskQuestion();

  function handleSubmit(url: string, timestamp: number, question: string) {
    mutate({ youtube_url: url, timestamp, question });
  }

  return (
    <div className="min-h-screen px-4 pb-12">
      <div className="max-w-2xl mx-auto">
        <Header />

        <div className="space-y-6">
          <VideoInput onSubmit={handleSubmit} isLoading={isPending} />

          <AnimatePresence mode="wait">
            {isPending && <LoadingState key="loading" />}
            {isError && (
              <ErrorState
                key="error"
                message={error?.message ?? 'Unknown error'}
                onRetry={reset}
              />
            )}
            {data && !isPending && (
              <AnswerDisplay key="answer" data={data} />
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
