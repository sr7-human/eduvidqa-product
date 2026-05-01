import { Navbar } from '../components/Navbar';

export function Privacy() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="max-w-3xl mx-auto px-6 py-12 prose prose-gray">
        <h1>Privacy Policy</h1>
        <p className="text-sm text-gray-500">Last updated: 1 May 2026</p>

        <p>
          EduVidQA ("we", "us") is an AI tutoring service for YouTube lectures. This policy
          explains what data we collect, how we use it, and the rights you have over it.
        </p>

        <h2>1. Data We Collect</h2>
        <ul>
          <li>
            <strong>Account information.</strong> When you sign up we store your email address
            via our authentication provider (Supabase Auth).
          </li>
          <li>
            <strong>Watch history.</strong> Videos you submit for processing are saved against
            your account in the <code>user_videos</code> table so you can return to them.
          </li>
          <li>
            <strong>Quiz attempts.</strong> Each answer you submit (selected option, whether it
            was correct, timestamp) is stored to power your progress view.
          </li>
          <li>
            <strong>Review queue.</strong> Questions you got wrong are scheduled for spaced
            repetition (SM-2 algorithm) — we store the next-due date and ease factor per
            question, per user.
          </li>
        </ul>

        <h2>2. How We Use It</h2>
        <ul>
          <li>To personalize your library and continue-watching list.</li>
          <li>To schedule spaced-repetition reviews of questions you struggled with.</li>
          <li>To improve quiz quality (aggregated, anonymized signal only).</li>
        </ul>

        <h2>3. Third-Party Services</h2>
        <ul>
          <li>
            <strong>Supabase</strong> — authentication, Postgres database, file storage. Hosted
            in <code>ap-south-1</code>.
          </li>
          <li>
            <strong>Groq</strong> — LLM inference for answers and quiz generation. Your question
            text is sent to Groq for processing.
          </li>
          <li>
            <strong>Google Gemini</strong> — fallback LLM and vision model. Question text and
            relevant transcript/keyframe excerpts may be sent.
          </li>
          <li>
            <strong>YouTube</strong> — videos are embedded via the YouTube IFrame Player API.
            YouTube may set its own cookies; refer to{' '}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">
              Google's privacy policy
            </a>
            .
          </li>
        </ul>

        <h2>4. Bring Your Own Key (BYOK)</h2>
        <p>
          If you provide your own Gemini API key in the Settings dialog, that key is sent with
          your requests so the call is billed to your account. <strong>We do not store your
          API key on our servers.</strong> It lives only in your browser's local storage.
        </p>

        <h2>5. Data Retention</h2>
        <p>
          We retain your data for as long as your account exists. When you delete your account,
          all rows in <code>user_videos</code>, <code>quiz_attempts</code>, and{' '}
          <code>review_queue</code> tied to your user ID are removed.
        </p>

        <h2>6. Your GDPR Rights</h2>
        <ul>
          <li><strong>Access</strong> — request a copy of the data we hold about you.</li>
          <li>
            <strong>Deletion</strong> — call <code>DELETE /api/users/me</code> from the app, or
            email us, and all your personal data is wiped.
          </li>
          <li>
            <strong>Portability</strong> — your watch history and review queue can be exported
            on request as JSON.
          </li>
        </ul>

        <h2>7. Cookies</h2>
        <p>
          We use a single first-party cookie/local-storage entry to keep you signed in
          (Supabase session) and one entry (<code>cookie_consent</code>) to remember that you
          dismissed the cookie banner. We do not run third-party analytics or advertising
          trackers.
        </p>

        <h2>8. Contact</h2>
        <p>
          Questions or requests: <a href="mailto:privacy@eduvidqa.app">privacy@eduvidqa.app</a>
        </p>
      </main>
    </div>
  );
}
