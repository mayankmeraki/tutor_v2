/* ═══════════════════════════════════════════════════════════
   Client-Side Router — History API routing for Capacity SPA

   Routes:
     /             Landing page (visitors). Logged-in → /home
     /login        Sign in / Create account
     /home         Browse courses + continue learning (logged-in home)
     /courses/:id  Course detail page
     /tutor        On-demand tutor (free-form intent)
     /session/:id  Active teaching session
     /dashboard    Back-compat alias for /home
   ═══════════════════════════════════════════════════════════ */

const Router = (() => {
  const routes = [
    { path: '/',              title: 'Capacity',               auth: false, handler: handleLanding },
    { path: '/login',         title: 'Sign In — Capacity',     auth: false, handler: handleLogin },
    { path: '/home',          title: 'Home — Capacity',        auth: true,  handler: handleHome },
    { path: '/courses/:id',   title: 'Course — Capacity',      auth: true,  handler: handleCourse },
    { path: '/tutor',         title: 'Tutor — Capacity',       auth: true,  handler: handleTutor },
    { path: '/dashboard',     title: 'Home — Capacity',        auth: true,  handler: handleHome },
    { path: '/courses',       title: 'Home — Capacity',        auth: true,  handler: handleHome },
    { path: '/session/:id',   title: 'Session — Capacity',     auth: true,  handler: handleSession },
    { path: '/session',       title: 'Home — Capacity',        auth: true,  handler: () => navigate('/home', { replace: true }) },
    { path: '/for-business',  title: 'For Institutions — Euler', auth: false, handler: handleBusiness },
  ];

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

  function navigate(path, opts = {}) {
    const { replace = false, skipHandler = false } = opts;
    if (replace) history.replaceState(null, '', path);
    else history.pushState(null, '', path);
    if (!skipHandler) resolve(path);
  }

  function resolve(pathname) {
    if (!pathname) pathname = location.pathname;
    if (pathname !== '/' && pathname.endsWith('/'))
      return navigate(pathname.slice(0, -1), { replace: true });

    for (const route of routes) {
      const params = matchPath(route.path, pathname);
      if (params === null) continue;

      if (route.auth && !AuthManager.isLoggedIn())
        return navigate('/login', { replace: true });
      if (pathname === '/login' && AuthManager.isLoggedIn())
        return navigate('/home', { replace: true });

      document.title = route.title;
      route.handler(params);
      return;
    }

    navigate(AuthManager.isLoggedIn() ? '/home' : '/', { replace: true });
  }

  // ─── Route handlers ─────────────────────────────────────

  function handleLanding() {
    if (AuthManager.isLoggedIn()) return navigate('/home', { replace: true });
    showScreen('landing');
  }

  function handleLogin() { showLoginPanel(); }

  function handleHome() { showScreen('browse'); }

  function handleCourse(params) { showScreen('course', params.id); }

  function handleTutor() { showScreen('browse'); }

  function handleSession(params) {
    if (typeof continueSession === 'function') continueSession(params.id);
  }

  function handleBusiness() { showScreen('business'); }

  // ─── Popstate ─────────────────────────────────────────────

  function onPopState() {
    const path = location.pathname;
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

  function init() { window.addEventListener('popstate', onPopState); }

  return { init, navigate, resolve };
})();
