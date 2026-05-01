import { Link } from 'react-router-dom';

export function Footer() {
  return (
    <footer className="border-t border-gray-200 py-4 px-6 text-center text-sm text-gray-500">
      <Link to="/privacy" className="hover:text-gray-700 mr-4">Privacy Policy</Link>
      <Link to="/terms" className="hover:text-gray-700">Terms of Service</Link>
    </footer>
  );
}
