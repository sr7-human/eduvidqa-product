import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

export function CookieBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('cookie_consent')) setShow(true);
  }, []);

  if (!show) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 text-white p-4 z-50">
      <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
        <p className="text-sm">
          We use cookies for authentication and to improve your experience.{' '}
          <Link to="/privacy" className="underline">Learn more</Link>
        </p>
        <button
          className="px-4 py-2 bg-white text-gray-900 rounded text-sm font-medium whitespace-nowrap"
          onClick={() => {
            localStorage.setItem('cookie_consent', 'true');
            setShow(false);
          }}
        >
          Accept
        </button>
      </div>
    </div>
  );
}
