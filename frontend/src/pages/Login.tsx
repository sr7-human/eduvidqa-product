import { Auth } from '@supabase/auth-ui-react';
import { ThemeSupa } from '@supabase/auth-ui-shared';
import { Navigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';

export function Login() {
  const { user } = useAuth();
  const { theme } = useTheme();
  if (user) return <Navigate to="/library" replace />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0a0e1a]">
      <div className="max-w-md w-full p-8 bg-white dark:bg-gray-900 rounded-xl shadow-lg border border-transparent dark:border-gray-700">
        <h1 className="text-2xl font-bold text-center mb-6 text-gray-900 dark:text-white">Sign in to EduVidQA</h1>
        <Auth
          supabaseClient={supabase}
          appearance={{ theme: ThemeSupa, variables: { default: { colors: { brand: '#6366f1', brandAccent: '#818cf8' } } } }}
          theme={theme === 'dark' ? 'dark' : 'default'}
          providers={['google']}
          redirectTo={window.location.origin + '/library'}
        />
      </div>
    </div>
  );
}
