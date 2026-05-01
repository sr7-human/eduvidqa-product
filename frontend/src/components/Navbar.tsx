import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';

export function Navbar() {
  const { user, signOut } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  return (
    <nav className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-3 flex items-center justify-between">
      <Link to="/library" className="text-xl font-bold text-blue-600 dark:text-blue-400">EduVidQA</Link>
      <div className="flex items-center gap-4">
        <Link to="/library" className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">Library</Link>
        <Link to="/review" className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">Review</Link>
        {user?.email && <span className="text-sm text-gray-500 dark:text-gray-400">{user.email}</span>}
        {/* Theme toggle */}
        <button
          onClick={toggle}
          aria-label="Toggle theme"
          className="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-lg"
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
        <button
          onClick={handleSignOut}
          className="text-sm text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
