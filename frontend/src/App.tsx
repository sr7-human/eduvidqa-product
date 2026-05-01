import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './contexts/AuthContext';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { Library } from './pages/Library';
import { Watch } from './pages/Watch';
import { Review } from './pages/Review';
import { Privacy } from './pages/Privacy';
import { Terms } from './pages/Terms';
import { ProtectedRoute } from './components/ProtectedRoute';
import { CookieBanner } from './components/CookieBanner';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="bottom-right" />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/library" element={<ProtectedRoute><Library /></ProtectedRoute>} />
          <Route path="/watch/:videoId" element={<ProtectedRoute><Watch /></ProtectedRoute>} />
          <Route path="/review" element={<ProtectedRoute><Review /></ProtectedRoute>} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/terms" element={<Terms />} />
        </Routes>
        <CookieBanner />
      </BrowserRouter>
    </AuthProvider>
  );
}
