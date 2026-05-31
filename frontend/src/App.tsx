/**
 * OpenNotebook — Main application with client-side routing.
 *
 * Uses simple state-based routing instead of TanStack Router for simplicity
 * (TanStack Router requires file-based route generation which is heavy for MVP).
 * This keeps the build simple while providing full navigation.
 */

import { useState, useCallback, useEffect } from 'react';
import { isAuthenticated } from '@/stores/auth';
import { AppShell } from '@/components/ui/AppShell';
import { LandingPage } from '@/pages/LandingPage';
import { AuthPage } from '@/pages/AuthPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { NotebookDashboard } from '@/components/notebook/NotebookDashboard';
import { NotebookWorkspace } from '@/components/notebook/NotebookWorkspace';

type Route =
  | { page: 'landing' }
  | { page: 'auth' }
  | { page: 'notebooks' }
  | { page: 'notebook'; id: string }
  | { page: 'settings' };

function parseRoute(path: string): Route {
  if (path === '/auth') return { page: 'auth' };
  if (path === '/settings') return { page: 'settings' };
  if (path === '/notebooks') return { page: 'notebooks' };
  const nbMatch = path.match(/^\/notebooks\/(.+)/);
  if (nbMatch) return { page: 'notebook', id: nbMatch[1] };
  return { page: 'landing' };
}

export function App() {
  const [route, setRoute] = useState<Route>(() => {
    // On load, redirect authenticated users to notebooks
    if (isAuthenticated()) return { page: 'notebooks' };
    return { page: 'landing' };
  });

  const navigate = useCallback((path: string) => {
    const newRoute = parseRoute(path);
    setRoute(newRoute);
    // Update browser URL without reload
    window.history.pushState(null, '', path);
  }, []);

  // Handle browser back/forward
  useEffect(() => {
    const handlePopState = () => {
      setRoute(parseRoute(window.location.pathname));
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const currentPath = routeToPath(route);

  // Unauthenticated routes
  if (route.page === 'landing') {
    return (
      <LandingPage
        onGetStarted={() => navigate('/auth')}
      />
    );
  }

  if (route.page === 'auth') {
    return (
      <AuthPage
        onSuccess={() => navigate('/notebooks')}
        onBack={() => navigate('/')}
      />
    );
  }

  // Require auth for everything else
  if (!isAuthenticated()) {
    return (
      <AuthPage
        onSuccess={() => navigate('/notebooks')}
        onBack={() => navigate('/')}
      />
    );
  }

  // Authenticated routes
  return (
    <AppShell onNavigate={navigate} currentPath={currentPath}>
      {route.page === 'notebooks' && (
        <NotebookDashboard
          onSelectNotebook={(id) => navigate(`/notebooks/${id}`)}
        />
      )}
      {route.page === 'notebook' && (
        <NotebookWorkspace
          notebookId={route.id}
          onBack={() => navigate('/notebooks')}
        />
      )}
      {route.page === 'settings' && <SettingsPage />}
    </AppShell>
  );
}

function routeToPath(route: Route): string {
  switch (route.page) {
    case 'landing':
      return '/';
    case 'auth':
      return '/auth';
    case 'notebooks':
      return '/notebooks';
    case 'notebook':
      return `/notebooks/${route.id}`;
    case 'settings':
      return '/settings';
  }
}
