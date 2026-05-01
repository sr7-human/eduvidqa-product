import { Link } from 'react-router-dom';

export function Landing() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      {/* Header */}
      <header className="border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold tracking-tight">
            EduVidQA
          </Link>
          <Link
            to="/login"
            className="text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            Sign in
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 py-24 text-center">
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-6">
          AI Tutor for YouTube Lectures
        </h1>
        <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto">
          Every answer is traceable to a moment in the lecture.
        </p>
        <Link
          to="/login"
          className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-8 py-3 rounded-lg transition-colors"
        >
          Get started free
        </Link>
      </section>

      {/* How it works */}
      <section className="max-w-5xl mx-auto px-6 py-16 border-t border-gray-200">
        <h2 className="text-3xl font-bold text-center mb-12">How it works</h2>
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { n: 1, t: 'Paste a YouTube URL', d: 'Drop in any lecture link. We index transcripts and keyframes.' },
            { n: 2, t: 'Ask a question', d: 'Type what you don’t understand at any moment in the video.' },
            { n: 3, t: 'Get timestamped answers', d: 'Every claim links back to the exact second it was said.' },
          ].map((s) => (
            <div key={s.n} className="text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-lg">
                {s.n}
              </div>
              <h3 className="font-semibold text-lg mb-2">{s.t}</h3>
              <p className="text-gray-600 text-sm">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-gray-200 py-8 text-center text-sm text-gray-500">
        <div>EduVidQA · Built for learners</div>
        <div className="mt-2">
          <Link to="/privacy" className="hover:text-gray-700 mr-4">Privacy Policy</Link>
          <Link to="/terms" className="hover:text-gray-700">Terms of Service</Link>
        </div>
      </footer>
    </div>
  );
}
