/* ═══════════════════════════════════════════════════════════
   Client-Side Router — History API routing for Capacity SPA
   ═══════════════════════════════════════════════════════════ */

const Router = (() => {
  const routes = [
    { path: '/',              title: 'Capacity',               auth: false, handler: handleLanding },
    { path: '/login',         title: 'Sign In — Capacity',     auth: false, handler: handleLogin },
    { path: '/dashboard',     title: 'Dashboard — Capacity',   auth: true,  handler: handleDashboard },
    { path: '/session',       title: 'Dashboard — Capacity',   auth: true,  handler: handleSessionBare },
    { path: '/session/:id',   title: 'Session — Capacity',     auth: true,  handler: handleSession },
  ];

  // ─── Path matching ──────────────────────────────────────

  function matchPath(pattern, pathname) {
    const paramNames = [];
    const regexStr = pattern.replace(/:([^/]+)/g, (_, name) => {
      paramNames.push(name);
      return '([^/]+)';
    });
    const match = new RegExp('^' + regexStr + '$').exec(pathname);
    if (!match) return null;
    const params = {};
    paramNames.forEach((name, i) => { params[name] = match[i + 1]; });
    return params;
  }

  // ─── Navigation ─────────────────────────────────────────

  function navigate(path, opts = {}) {
    const { replace = false, skipHandler = false } = opts;
    if (replace) {
      history.replaceState(null, '', path);
    } else {
      history.pushState(null, '', path);
    }
    if (!skipHandler) resolve(path);
  }

  // ─── Route resolution ──────────────────────────────────

  function resolve(pathname) {
    if (!pathname) pathname = location.pathname;

    // Normalize trailing slashes (except root)
    if (pathname !== '/' && pathname.endsWith('/')) {
      return navigate(pathname.slice(0, -1), { replace: true });
    }

    for (const route of routes) {
      const params = matchPath(route.path, pathname);
      if (params === null) continue;

      // Auth guards
      if (route.auth && !AuthManager.isLoggedIn()) {
        return navigate('/', { replace: true });
      }
      if (pathname === '/login' && AuthManager.isLoggedIn()) {
        return navigate('/dashboard', { replace: true });
      }

      document.title = route.title;
      route.handler(params);
      return;
    }

    // No match — redirect to dashboard if logged in, otherwise landing
    navigate(AuthManager.isLoggedIn() ? '/dashboard' : '/', { replace: true });
  }

  // ─── Route handlers ─────────────────────────────────────

  function handleLanding() {
    if (AuthManager.isLoggedIn()) {
      return navigate('/dashboard', { replace: true });
    }
    showLandingPanel();
  }

  function handleLogin() {
    showLoginPanel();
  }

  function handleDashboard() {
    showSetupPanel();
  }

  function handleSessionBare() {
    return navigate('/dashboard', { replace: true });
  }

  function handleSession(params) {
    if (typeof continueSession === 'function') {
      continueSession(params.id);
    }
  }

  // ─── Popstate (browser back/forward) ────────────────────

  function onPopState() {
    const path = location.pathname;

    // If leaving a session route, clean up teaching state
    if (!path.startsWith('/session/')) {
      const tl = document.getElementById('teaching-layout');
      if (tl && !tl.classList.contains('hidden')) {
        tl.classList.add('hidden');
        if (typeof cleanupActiveSession === 'function') cleanupActiveSession();
        if (typeof timerInterval !== 'undefined' && timerInterval) clearInterval(timerInterval);
      }
    }

    resolve(path);
  }

  // ─── Init ───────────────────────────────────────────────

  function init() {
    window.addEventListener('popstate', onPopState);
  }

  return { init, navigate, resolve };
})();
