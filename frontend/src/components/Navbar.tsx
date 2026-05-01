import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function Navbar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <Link to="/library" className="text-xl font-bold text-blue-600">EduVidQA</Link>
      <div className="flex items-center gap-4">
        <Link to="/library" className="text-gray-600 hover:text-gray-900">Library</Link>
        <Link to="/review" className="text-gray-600 hover:text-gray-900">Review</Link>
        {user?.email && <span className="text-sm text-gray-500">{user.email}</span>}
        <button
          onClick={handleSignOut}
          className="text-sm text-red-500 hover:text-red-700"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
