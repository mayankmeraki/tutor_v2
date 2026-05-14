import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '@/features/auth/ProtectedRoute';
import { LandingPage } from './LandingPage';
import { LoginPage } from './LoginPage';
import { HomePage } from './HomePage';
import { ForBusinessPage } from './ForBusinessPage';
import { TutorPage } from './TutorPage';
import { SessionPage } from './SessionPage';
import { DSAPage } from './DSAPage';
import { DSAProblemPage } from './DSAProblemPage';
import { SDProblemPage } from './SDProblemPage';
import { MockPage } from './MockPage';
import { PathsPage } from './PathsPage';
import { ByoPage } from './ByoPage';
import { ArtifactsPage } from './ArtifactsPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/for-business" element={<ForBusinessPage />} />

      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tutor"
        element={
          <ProtectedRoute>
            <TutorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/session"
        element={<Navigate to="/home" replace />}
      />
      <Route
        path="/session/:sessionId"
        element={
          <ProtectedRoute>
            <SessionPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dsa"
        element={
          <ProtectedRoute>
            <DSAPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dsa/:slug"
        element={
          <ProtectedRoute>
            <DSAProblemPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sd/:slug"
        element={
          <ProtectedRoute>
            <SDProblemPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mock"
        element={
          <ProtectedRoute>
            <MockPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/paths"
        element={
          <ProtectedRoute>
            <PathsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/byo"
        element={
          <ProtectedRoute>
            <ByoPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/artifacts"
        element={
          <ProtectedRoute>
            <ArtifactsPage />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
