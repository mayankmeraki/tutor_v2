/* ═══════════════════════════════════════════════════════════
   AI-First Teaching Experience v3 — Infinity Canvas Engine
   ═══════════════════════════════════════════════════════════

   Single unified stream: all content (AI messages, videos,
   diagrams, interactive controls) flows in #canvas-stream
   as connected blocks with a vertical timeline.
   ═══════════════════════════════════════════════════════════ */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

// ═══════════════════════════════════════════════════════════
// Module 0: Auth Manager
// ═══════════════════════════════════════════════════════════

const AuthManager = (() => {
  const TOKEN_KEY = 'mockup_auth_token';
  const USER_KEY = 'mockup_auth_user';

  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function getUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  }
  function isLoggedIn() { return !!getToken() && !!getUser(); }
  function setAuth(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
  function authHeaders() {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function login(email, password) {
    const apiUrl = $('#api-url')?.value?.trim() || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (res.status === 401) throw new Error('Invalid email or password');
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text.slice(0, 200) || `Login failed (${res.status})`);
    }
    const data = await res.json();
    setAuth(data.token, data.user);
    return data;
  }

  function logout() {
    clearAuth();
  }

  async function validateSession() {
    if (!isLoggedIn()) return false;
    const apiUrl = $('#api-url')?.value?.trim() || 'http://localhost:3001';
    try {
      const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
        headers: authHeaders(),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  return { getToken, getUser, isLoggedIn, setAuth, clearAuth, authHeaders, login, logout, validateSession };
})();

// ═══════════════════════════════════════════════════════════
// Module 1: Session Manager (MongoDB-backed)
// ═══════════════════════════════════════════════════════════

const SessionManager = (() => {
  let session = null;
  let flushInterval = null;
  const FLUSH_INTERVAL_MS = 30000;

  function now() { return new Date().toISOString(); }
  function estimateTokens(text) { return Math.ceil((text || '').length / 4); }

  function getActiveSection() {
    if (!session) return null;
    return session.sections.find(s => s.status === 'active') || null;
  }

  function getActiveSectionIndex() {
    const sec = getActiveSection();
    return sec ? sec.index : null;
  }

  // ─── API helpers ─────────────────────────────────────────

  async function apiPost(path, body) {
    const res = await fetch(`${state.apiUrl}/api/v1/sessions${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Sessions API POST ${res.status}`);
    return res.json();
  }

  async function apiPatch(path, body) {
    const res = await fetch(`${state.apiUrl}/api/v1/sessions${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Sessions API PATCH ${res.status}`);
    return res.json();
  }

  async function apiGet(path) {
    const res = await fetch(`${state.apiUrl}/api/v1/sessions${path}`, {
      headers: { ...AuthManager.authHeaders() },
    });
    if (!res.ok) { if (res.status === 404) return null; throw new Error(`Sessions API GET ${res.status}`); }
    return res.json();
  }

  // ─── Lifecycle ───────────────────────────────────────────

  async function createSession(courseId, studentName, intent, coursePosition, sessionNumber) {
    session = {
      sessionId: state.sessionId,
      courseId,
      studentName,
      userEmail: state.userEmail || '',
      number: sessionNumber,
      status: 'active',
      startedAt: now(),
      endedAt: null,
      durationSec: 0,
      intent: { raw: intent || '', scenario: 'course' },
      coursePosition: {
        startedAt: { lessonId: coursePosition.lessonId, sectionIndex: coursePosition.sectionIndex },
        current: { lessonId: coursePosition.lessonId, sectionIndex: coursePosition.sectionIndex },
        completedCourseSections: coursePosition.completedCourseSections || [],
      },
      plan: {},
      sections: [],
      transcript: [],
      metrics: {
        totalTurns: 0, studentResponses: 0,
        sectionsCompleted: 0, sectionsTotal: 0,
        planningCalls: 0,
        assessmentScore: { correct: 0, total: 0, pct: 0 },
      },
      summaries: {
        sectionDigests: [], sessionSummary: '',
        totalRawTokens: 0, totalSummarizedTokens: 0,
      },
      previousSessions: [],
    };

    try { await apiPost('', session); } catch (e) { console.warn('Failed to create session in MongoDB:', e); }

    if (flushInterval) clearInterval(flushInterval);
    flushInterval = setInterval(() => saveSession(), FLUSH_INTERVAL_MS);
    window.addEventListener('beforeunload', handleBeforeUnload);

    return session;
  }

  async function saveSession() {
    if (!session) return;
    if (state.sessionStartTime) {
      session.durationSec = Math.floor((Date.now() - state.sessionStartTime) / 1000);
    }
    session.metrics.totalTurns = session.transcript.length;
    session.metrics.studentResponses = session.transcript.filter(m => m.role === 'user').length;
    session.metrics.sectionsCompleted = session.sections.filter(s => s.status === 'done').length;
    session.metrics.sectionsTotal = session.sections.length;
    session.metrics.planningCalls = state.planCallCount;

    try {
      await apiPatch(`/${session.sessionId}`, {
        transcript: session.transcript,
        sections: session.sections,
        metrics: session.metrics,
        coursePosition: session.coursePosition,
        plan: session.plan,
        durationSec: session.durationSec,
        summaries: session.summaries,
        generatedVisuals: state.generatedVisuals,
        spotlightHistory: state.spotlightHistory,
        notebookSteps: state.notebookSteps,
      });
    } catch (e) { console.warn('Failed to save session to MongoDB:', e); }
  }

  async function loadPreviousSessions(courseId, studentName) {
    try {
      if (AuthManager.isLoggedIn()) {
        return await apiGet(`/me/${courseId}`);
      }
      return await apiGet(`/student/${courseId}/${encodeURIComponent(studentName)}`);
    } catch (e) {
      console.warn('Failed to load previous sessions:', e);
      return [];
    }
  }

  async function archiveSession() {
    if (!session) return;
    session.status = 'complete';
    session.endedAt = now();
    if (state.sessionStartTime) {
      session.durationSec = Math.floor((Date.now() - state.sessionStartTime) / 1000);
    }
    try {
      await apiPatch(`/${session.sessionId}`, {
        status: 'complete', endedAt: session.endedAt,
        durationSec: session.durationSec, metrics: session.metrics,
        transcript: session.transcript, sections: session.sections,
        summaries: session.summaries,
      });
    } catch (e) { console.warn('Failed to archive session:', e); }
    if (flushInterval) clearInterval(flushInterval);
  }

  function handleBeforeUnload() {
    if (!session) return;
    try {
      session.durationSec = state.sessionStartTime ? Math.floor((Date.now() - state.sessionStartTime) / 1000) : 0;
      fetch(`${state.apiUrl}/api/v1/sessions/${session.sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
        body: JSON.stringify({
          transcript: session.transcript, sections: session.sections,
          metrics: session.metrics, durationSec: session.durationSec,
          coursePosition: session.coursePosition,
        }),
        keepalive: true,
      });
    } catch (e) { /* best-effort on unload */ }
  }

  // ─── Recording ───────────────────────────────────────────

  function recordMessage(role, content) {
    if (!session) return;
    const msg = { id: generateId(), role, content, timestamp: now(), sectionIndex: getActiveSectionIndex() };
    session.transcript.push(msg);
    const sec = getActiveSection();
    if (sec) sec.transcript.push(msg);
  }

  function recordAsset(tag) {
    if (!session) return;
    const sec = getActiveSection();
    if (!sec) return;
    sec.assets.push({
      type: tag.name.replace('teaching-', ''),
      tag: { name: tag.name, attrs: tag.attrs || {} },
      timestamp: now(),
    });
  }

  function recordAssessment(assessment) {
    if (!session) return;
    const sec = getActiveSection();
    if (!sec) return;
    assessment.timestamp = now();
    sec.assessments.push(assessment);
    session.metrics.assessmentScore.total++;
    if (assessment.correct) session.metrics.assessmentScore.correct++;
    const { correct: c, total: t } = session.metrics.assessmentScore;
    session.metrics.assessmentScore.pct = t > 0 ? Math.round((c / t) * 100) : 0;
  }

  function recordVideoChunk(url, start, end, label) {
    if (!session) return;
    const sec = getActiveSection();
    if (sec) sec.videoChunks.push({ videoUrl: url, startSec: start, endSec: end, label: label || '' });
  }

  function recordSimulation(simId, title) {
    if (!session) return;
    const sec = getActiveSection();
    if (sec) sec.simulations.push({ simId, title: title || '', openedAt: now(), interactionCount: 0 });
  }

  // ─── Plan & Section Lifecycle ────────────────────────────

  function setPlan(planData) {
    if (!session) return;
    session.plan = {
      sessionObjective: planData.session_objective || planData.objective || '',
      scenario: planData.scenario || 'course',
      learningOutcomes: planData.learning_outcomes || [],
      raw: planData,
    };
    const planSections = planData.sections || planData.steps || [];
    session.sections = planSections.map((sec, i) => {
      // Build topics sub-array from plan outline
      const topicOutlines = sec.topics || [];
      const topics = topicOutlines.map((t, ti) => ({
        index: ti,
        title: t.title || `Topic ${ti + 1}`,
        concept: t.concept || '',
        status: (i === 0 && ti === 0) ? 'active' : 'pending',
        startedAt: (i === 0 && ti === 0) ? now() : null,
        completedAt: null,
      }));

      return {
        index: i,
        title: sec.title || sec.student_label || `Section ${i + 1}`,
        modality: sec.modality || sec.type || '',
        covers: sec.covers || sec.concept || '',
        learningOutcome: sec.learning_outcome || sec.objective || '',
        activity: sec.activity || sec.do || '',
        status: i === 0 ? 'active' : 'pending',
        startedAt: i === 0 ? now() : null,
        completedAt: null,
        topics,
        courseRef: null,
        videoChunks: [], transcript: [], assets: [],
        assessments: [], simulations: [], summary: null,
      };
    });
    session.metrics.sectionsTotal = session.sections.length;
  }

  function completeTopic(sectionIndex, topicIndex) {
    if (!session) return;
    const sec = session.sections.find(s => s.index === sectionIndex);
    if (!sec || !sec.topics) return;
    const topic = sec.topics.find(t => t.index === topicIndex);
    if (topic) {
      topic.status = 'done';
      topic.completedAt = now();
    }
    // Activate next pending topic in same section
    const nextTopic = sec.topics.find(t => t.status === 'pending');
    if (nextTopic) {
      nextTopic.status = 'active';
      nextTopic.startedAt = now();
    }
  }

  function startSection(index) {
    if (!session) return;
    const sec = session.sections.find(s => s.index === index);
    if (sec) { sec.status = 'active'; sec.startedAt = now(); }
  }

  async function completeSection(index) {
    if (!session) return;
    const sec = session.sections.find(s => s.index === index);
    if (sec) { sec.status = 'done'; sec.completedAt = now(); }
    session.metrics.sectionsCompleted = session.sections.filter(s => s.status === 'done').length;

    // Save first so backend has the transcript for summarization
    await saveSession();

    // Generate LLM summary (fire and forget for UI, but we await for data)
    try {
      const result = await apiPost(`/${session.sessionId}/summarize-section`, { sectionIndex: index });
      if (result && result.summary && sec) {
        sec.summary = result.summary;
        session.summaries.sectionDigests.push({
          sectionIndex: index, title: sec.title,
          digest: result.summary.text || '',
          conceptsCovered: result.summary.conceptsCovered || [],
          studentPerformance: result.summary.studentPerformance || 'unknown',
          rawTokenCount: estimateTokens(sec.transcript.map(m => m.content).join(' ')),
        });
      }
    } catch (e) { console.warn('Section summary generation failed:', e); }

    // Activate next pending section
    const next = session.sections.find(s => s.status === 'pending');
    if (next) startSection(next.index);
  }

  function updateCoursePosition(lessonId, sectionIndex) {
    if (!session) return;
    const prev = session.coursePosition.current;
    if (prev.lessonId) {
      const key = `${prev.lessonId}:${prev.sectionIndex}`;
      if (!session.coursePosition.completedCourseSections.includes(key)) {
        session.coursePosition.completedCourseSections.push(key);
      }
    }
    session.coursePosition.current = { lessonId, sectionIndex };
  }

  // ─── Context Building ───────────────────────────────────

  function buildContextForAI(tokenBudget = 4000) {
    if (!session || session.sections.length === 0) return null;
    const parts = [];
    let tokensUsed = 0;

    // Session state overview
    const overview = {
      sessionNumber: session.number,
      intent: session.intent,
      planObjective: session.plan.sessionObjective || '',
      sectionsOverview: session.sections.map(s => ({
        index: s.index, title: s.title, status: s.status, modality: s.modality,
        topics: (s.topics || []).map(t => ({ title: t.title, concept: t.concept, status: t.status })),
      })),
    };
    const overviewStr = JSON.stringify(overview);
    tokensUsed += estimateTokens(overviewStr);
    parts.push({ description: 'Session State — plan & section statuses', value: overviewStr });

    // Completed sections: newest raw, older summaries
    const remaining = tokenBudget - tokensUsed;
    const doneSections = session.sections.filter(s => s.status === 'done').sort((a, b) => b.index - a.index);
    if (doneSections.length > 0) {
      const sectionParts = [];
      let sectionTokens = 0;
      for (let i = 0; i < doneSections.length; i++) {
        const s = doneSections[i];
        if (i === 0) {
          // Most recent completed: try raw if fits
          const rawStr = JSON.stringify({ index: s.index, title: s.title, transcript: s.transcript.map(m => ({ role: m.role, content: m.content })) });
          const rawTk = estimateTokens(rawStr);
          if (sectionTokens + rawTk < remaining * 0.6) { sectionParts.push(rawStr); sectionTokens += rawTk; continue; }
        }
        if (s.summary) {
          const sumStr = `Section ${s.index} "${s.title}": ${s.summary.text} [${s.summary.studentPerformance}]`;
          const sumTk = estimateTokens(sumStr);
          if (sectionTokens + sumTk < remaining) { sectionParts.push(sumStr); sectionTokens += sumTk; }
        }
      }
      if (sectionParts.length > 0) {
        parts.push({ description: 'Completed Sections (recent raw, older summaries)', value: sectionParts.join('\n\n') });
      }
    }

    // Previous sessions
    if (session.previousSessions && session.previousSessions.length > 0) {
      const prevStr = session.previousSessions.map(ps => `Session ${ps.number} (${ps.scenario}): ${ps.summary}`).join('\n');
      parts.push({ description: 'Previous Sessions (summaries)', value: prevStr });
    }

    return parts;
  }

  function resumeSession(sessionData) {
    session = sessionData;
    session.status = 'active';
    if (flushInterval) clearInterval(flushInterval);
    flushInterval = setInterval(() => saveSession(), FLUSH_INTERVAL_MS);
    window.addEventListener('beforeunload', handleBeforeUnload);
    return session;
  }

  return {
    get session() { return session; },
    createSession, saveSession, loadPreviousSessions, archiveSession, resumeSession,
    recordMessage, recordAsset, recordAssessment, recordVideoChunk, recordSimulation,
    setPlan, startSection, completeSection, completeTopic, updateCoursePosition,
    buildContextForAI, getActiveSectionIndex,
  };
})();

// ═══════════════════════════════════════════════════════════
// Module 2: Config & State
// ═══════════════════════════════════════════════════════════

const state = {
  apiUrl: 'http://localhost:3001',
  courseId: null,
  studentName: '',
  userEmail: '',

  // Course map from REST
  courseMap: null,

  // Checkpoint
  checkpoint: {
    currentLessonId: null,
    currentSectionIndex: 0,
    completedSections: [],
    lastVideoTimestamp: 0,
    sessionCount: 1,
    lastPlanJSON: null,
  },

  // Session
  sessionStartTime: null,
  responses: 0,

  // Conversation history
  messages: [],

  // Teaching plan
  plan: [],
  planActiveStep: null,

  // Available simulations (from REST API)
  simulations: [],
  // Course concepts (from REST API)
  concepts: [],

  // Streaming
  isStreaming: false,
  currentMessageId: null,
  accumulatedText: '',

  // Tool call tracking
  activeToolCalls: {},

  // Session state
  sessionId: null,
  currentScript: null,

  // Simulation state
  activeSimulation: null,      // { simId, blockId, title, entryUrl }
  simulationLiveState: null,   // Latest params/state from sim bridge
  simBridgeListener: null,     // postMessage listener reference

  // Plan call tracking
  planCallCount: 0,
  pendingFallbackTimer: null,
  sessionStatus: 'active',
  completionReason: null,

  // Generated visuals (from visual_gen agents)
  generatedVisuals: {},  // { visId: { title, html } }

  // Agent event system
  agentEventSource: null,    // EventSource for /api/events/{sessionId}
  runningAgents: {},         // { agentId: { type, description, startTime } }
  autoTriggerTimer: null,    // Debounce timer for graceful auto-trigger

  // Spotlight panel
  spotlightActive: false,
  spotlightInfo: null,   // { type, title, id?, notebookId? } — what's currently pinned
  notebookSteps: [],     // Steps accumulated in derivation notebook
  spotlightHistory: [],  // { id, type, title, tag } — clickable reference cards
  inactivityTimer: null,  // Auto-send timer for notebook workspace
  notebookCleanup: null,  // Cleanup function for current notebook

  // Board Draw (tutor live drawing)
  boardDraw: {
    active: false,
    contentStartIdx: 0,
    processedLines: 0,
    complete: false,
    dismissed: false,
    commandQueue: [],
    isProcessing: false,
    cancelFlag: false,
    currentH: 500,
    canvas: null,
    ctx: null,
    voiceEl: null,
    DPR: 1,
    scale: 1,
  },

};

// ═══════════════════════════════════════════════════════════
// Module 3: Course Map (REST)
// ═══════════════════════════════════════════════════════════

async function fetchJSON(path) {
  const res = await fetch(`${state.apiUrl}/api/v1/content${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function loadCourseMap(courseId) {
  const data = await fetchJSON(`/courses/${courseId}`);

  // API returns { course, modules[], lessons[] } — reshape into nested format
  // that buildCourseContext expects: { title, modules: [{ title, lessons: [{ sections }] }] }
  const lessonsById = {};
  for (const l of data.lessons || []) {
    lessonsById[l.lesson_id] = { ...l, sections: [] };
  }

  // Fetch sections for each lesson in parallel
  const sectionFetches = (data.lessons || []).map(async (l) => {
    try {
      const res = await fetch(`${state.apiUrl}/api/v1/content/lessons/${l.lesson_id}/sections`);
      if (res.ok) {
        const sections = await res.json();
        lessonsById[l.lesson_id].sections = sections.map(s => ({
          index: s.index,
          title: s.title,
          start_seconds: s.start_seconds,
          end_seconds: s.end_seconds,
        }));
      }
    } catch (e) {
      console.warn(`Failed to fetch sections for lesson ${l.lesson_id}:`, e);
    }
  });
  await Promise.all(sectionFetches);

  const courseMap = {
    title: data.course.title,
    modules: (data.modules || []).map(mod => ({
      title: mod.title,
      lessons: (mod.lesson_ids || []).map(lid => lessonsById[lid]).filter(Boolean),
    })),
  };

  state.courseMap = courseMap;
  return courseMap;
}

async function fetchSimulations(courseId) {
  try {
    const res = await fetch(`${state.apiUrl}/api/v1/learning-tools/course/${courseId}`);
    if (!res.ok) {
      console.warn(`Failed to fetch simulations: ${res.status}`);
      state.simulations = [];
      return;
    }
    state.simulations = await res.json();
    console.log(`Loaded ${state.simulations.length} simulations for course ${courseId}`);
  } catch (e) {
    console.warn('Failed to fetch simulations:', e);
    state.simulations = [];
  }
}

async function fetchConcepts(courseId) {
  try {
    const res = await fetch(`${state.apiUrl}/api/v1/content/courses/${courseId}/concepts`);
    if (!res.ok) {
      console.warn(`Failed to fetch concepts: ${res.status}`);
      state.concepts = [];
      return;
    }
    state.concepts = await res.json();
    console.log(`Loaded ${state.concepts.length} concepts for course ${courseId}`);
  } catch (e) {
    console.warn('Failed to fetch concepts:', e);
    state.concepts = [];
  }
}

function buildCourseContext() {
  const map = state.courseMap;
  if (!map) return 'No course map loaded.';

  const cp = state.checkpoint;
  const lines = [`${map.title}\n`];

  for (const mod of map.modules) {
    lines.push(`Module: ${mod.title}`);
    for (const lesson of mod.lessons) {
      const dur = lesson.duration_seconds ? `${Math.round(lesson.duration_seconds / 60)} min` : '';
      const isCurrent = lesson.lesson_id === cp.currentLessonId;
      const marker = isCurrent ? ' << CURRENT LESSON' : '';
      const videoTag = lesson.video_url ? ` [video: ${lesson.video_url}]` : ' [no video]';
      lines.push(`  Lesson ${lesson.lesson_id}: ${lesson.title} (${dur})${videoTag}${marker}`);

      // Only show sections for current lesson (keeps context compact)
      if (isCurrent && lesson.sections) {
        for (const sec of lesson.sections) {
          const key = `${lesson.lesson_id}:${sec.index}`;
          const isDone = cp.completedSections.includes(key);
          const isCurrentSec = sec.index === cp.currentSectionIndex;

          const startFmt = formatTimestamp(sec.start_seconds);
          const endFmt = formatTimestamp(sec.end_seconds);
          const secMarker = isDone ? ' DONE' : isCurrentSec ? ' << CURRENT' : '';

          lines.push(`    [${sec.index}] ${sec.title} [${startFmt}-${endFmt}]${secMarker}`);
        }
      }
    }
  }

  return lines.join('\n');
}

function formatTimestamp(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = Math.round(totalSeconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// ═══════════════════════════════════════════════════════════
// Module 4: Course Progress Sidebar Renderer
// ═══════════════════════════════════════════════════════════

function renderCourseProgress() {
  const container = $('#course-progress-list');
  if (!container || !state.courseMap) return;

  const cp = state.checkpoint;
  let html = '';

  for (const mod of state.courseMap.modules) {
    html += `<div class="progress-module">`;
    html += `<div class="progress-module-title">${escapeHtml(mod.title)}</div>`;

    for (const lesson of mod.lessons) {
      const isActiveLesson = lesson.lesson_id === cp.currentLessonId;
      const allDone = lesson.sections.length > 0 &&
        lesson.sections.every(s => cp.completedSections.includes(`${lesson.lesson_id}:${s.index}`));
      const lessonClass = allDone ? 'completed' : isActiveLesson ? 'active' : '';
      const icon = allDone ? '&#10003;' : isActiveLesson ? '&#9679;' : '&#9675;';

      html += `<div class="progress-lesson ${lessonClass}">`;
      html += `<div class="progress-lesson-title"><span class="lesson-icon">${icon}</span>${escapeHtml(lesson.title)}</div>`;

      if (isActiveLesson || allDone) {
        html += `<div class="progress-sections">`;
        for (const sec of lesson.sections) {
          const key = `${lesson.lesson_id}:${sec.index}`;
          const isDone = cp.completedSections.includes(key);
          const isCurrent = isActiveLesson && sec.index === cp.currentSectionIndex && !isDone;
          const secClass = isDone ? 'completed' : isCurrent ? 'current' : '';
          html += `<div class="progress-section ${secClass}">`;
          html += `<span class="section-dot"></span>`;
          html += `<span>${escapeHtml(sec.title)}</span>`;
          html += `</div>`;
        }
        html += `</div>`;
      }

      html += `</div>`;
    }

    html += `</div>`;
  }

  container.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════
// Module 5a: Input Builder (inline send + mic)
// ═══════════════════════════════════════════════════════════

const SVG_SEND = `<svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;
const SVG_MIC = `<svg viewBox="0 0 24 24"><rect x="9" y="1" width="6" height="12" rx="3"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`;
const SVG_DRAW = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z"/><path d="M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>`;
const SVG_TEXT = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M2.5 4v3h5v12h3V7h5V4h-13z"/><path d="M21.5 9h-9v3h3v7h3v-7h3V9z"/></svg>`;

function buildTextInput(id, placeholder, submitFnStr) {
  return `
    <div class="input-wrapper">
      <textarea class="text-input" id="${id}" placeholder="${escapeAttr(placeholder)}" rows="1"></textarea>
      <div class="input-icons">
        <button class="input-icon-btn input-mic-btn" onclick="startVoiceInput('${id}')" title="Voice input">${SVG_MIC}</button>
        <button class="input-icon-btn input-send-btn" onclick="${submitFnStr}" title="Send">${SVG_SEND}</button>
      </div>
    </div>`;
}

window.startVoiceInput = function(targetId) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn('Speech recognition not supported');
    return;
  }

  const textarea = $(`#${targetId}`);
  if (!textarea) return;

  // Find the mic button near this input
  const wrapper = textarea.closest('.input-wrapper');
  const micBtn = wrapper?.querySelector('.input-mic-btn');

  // Toggle off if already recording
  if (micBtn?.classList.contains('recording')) {
    micBtn._recognition?.stop();
    micBtn.classList.remove('recording');
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  if (micBtn) {
    micBtn.classList.add('recording');
    micBtn._recognition = recognition;
  }

  let finalTranscript = textarea.value;

  recognition.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        finalTranscript += (finalTranscript ? ' ' : '') + event.results[i][0].transcript;
      } else {
        interim += event.results[i][0].transcript;
      }
    }
    textarea.value = finalTranscript + (interim ? ' ' + interim : '');
  };

  recognition.onend = () => {
    if (micBtn) micBtn.classList.remove('recording');
    textarea.value = finalTranscript;
    textarea.focus();
  };

  recognition.onerror = () => {
    if (micBtn) micBtn.classList.remove('recording');
  };

  recognition.start();
};

// ═══════════════════════════════════════════════════════════
// Module 5: Unified Block System (Infinity Canvas)
// ═══════════════════════════════════════════════════════════

function appendBlock(type, html, options = {}) {
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = `canvas-block ${options.className || ''} fade-in`;
  block.dataset.type = type;
  if (options.id) block.id = options.id;
  if (options.interactive) block.dataset.interactive = 'true';
  block.innerHTML = `<div class="block-card">${html}</div>`;
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;
  return block;
}

function disablePreviousInteractive() {
  $$('.canvas-block[data-interactive="true"]:not([data-resolved])').forEach(block => {
    block.dataset.resolved = 'true';
    block.querySelectorAll('button, input, textarea, select').forEach(el => {
      el.disabled = true;
    });
    block.classList.add('resolved');
  });
}

// ═══════════════════════════════════════════════════════════
// Module 6: SSE Streaming Client
// ═══════════════════════════════════════════════════════════

function generateId() {
  return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
}

async function streamADK(userMessageContent, isSystemTrigger = false, isSessionStart = false) {
  if (state.isStreaming) return;
  state.isStreaming = true;

  const userMsg = {
    id: generateId(),
    role: 'user',
    content: userMessageContent,
  };
  state.messages.push(userMsg);

  // For session recording, extract text portion
  const recordText = typeof userMessageContent === 'string'
    ? userMessageContent
    : (userMessageContent.find(b => b.type === 'text')?.text || '[image content]');
  SessionManager.recordMessage('user', recordText);

  if (!isSystemTrigger) {
    state.responses++;
    updateStats();
    // Only render user message for text (canvas drawings render their own image)
    if (typeof userMessageContent === 'string') {
      renderUserMessage(userMessageContent);
    }
  }

  // Disable previous interactive blocks
  disablePreviousInteractive();

  const context = buildContext();

  const body = {
    messages: state.messages,
    context,
    sessionId: state.sessionId,
    isSessionStart,
  };

  showStreamingIndicator();

  try {
    const res = await fetch(`${state.apiUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...AuthManager.authHeaders(),
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`API ${res.status}: ${errText.slice(0, 200)}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    state.accumulatedText = '';
    state.currentMessageId = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);
          handleSSEEvent(event);
        } catch (e) {
          // Skip unparseable events
        }
      }
    }

    if (buffer.startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.slice(6).trim());
        handleSSEEvent(event);
      } catch (e) {}
    }
  } catch (err) {
    removeStreamingIndicator();
    renderAIError(err.message);
  }

  state.isStreaming = false;

  SessionManager.saveSession();
}

function handleSSEEvent(event) {
  const type = event.type;

  switch (type) {
    case 'TEXT_MESSAGE_START':
      state.currentMessageId = event.messageId || event.message_id;
      state.accumulatedText = '';
      state.boardDraw.active = false;
      state.boardDraw.processedLines = 0;
      state.boardDraw.contentStartIdx = 0;
      state.boardDraw.complete = false;
      state.boardDraw.dismissed = false;
      removeStreamingIndicator();
      // Safety net: if onboarding overlay is still showing when tutor starts talking, remove it
      const staleOnboard = $('#onboarding-block');
      if (staleOnboard) {
        staleOnboard.style.transition = 'opacity 0.3s ease';
        staleOnboard.style.opacity = '0';
        setTimeout(() => staleOnboard.remove(), 300);
      }
      startAIMessageStream();
      break;

    case 'TEXT_MESSAGE_CONTENT':
      state.accumulatedText += event.delta || '';
      updateAIMessageStream(state.accumulatedText);
      break;

    case 'TEXT_MESSAGE_END':
      finalizeAIMessage(state.accumulatedText);
      state.messages.push({
        id: state.currentMessageId || generateId(),
        role: 'assistant',
        content: state.accumulatedText,
      });
      SessionManager.recordMessage('assistant', state.accumulatedText);
      state.currentMessageId = null;
      break;

    case 'TOOL_CALL_START':
      handleToolCallStart(event);
      break;

    case 'TOOL_CALL_ARGS':
      handleToolCallArgs(event);
      break;

    case 'TOOL_CALL_END':
      handleToolCallEnd(event);
      break;

    case 'TOOL_CALL_RESULT':
      break;

    case 'RUN_FINISHED':
      removeStreamingIndicator();
      cleanupToolIndicators();
      break;

    case 'RUN_ERROR':
      removeStreamingIndicator();
      cleanupToolIndicators();
      renderAIError(event.message || 'Unknown error');
      break;

    case 'PLAN_UPDATE':
      console.log('[SSE] PLAN_UPDATE received —', event.plan?.session_objective || event.sessionObjective || '?');
      handlePlanFromAgent(event.plan, event.sessionObjective);
      break;

    case 'TEACHING_DELEGATION_START':
      console.log('[SSE] TEACHING_DELEGATION_START — topic:', event.topic, 'type:', event.agentType);
      break;

    case 'TEACHING_DELEGATION_END':
      console.log('[SSE] TEACHING_DELEGATION_END — reason:', event.reason);
      break;

    case 'TOPIC_COMPLETE':
      console.log('[SSE] TOPIC_COMPLETE —', event.topic_index, event.title || '');
      handleTopicComplete(event.section_index, event.topic_index);
      break;

    case 'SECTION_COMPLETE':
      console.log('[SSE] SECTION_COMPLETE — index:', event.index);
      handleSectionComplete(event.index);
      break;

    case 'PLAN_RESET':
      console.log('[SSE] PLAN_RESET — reason:', event.reason);
      handlePlanReset(event.reason, event.keep_scope);
      break;

    case 'SIM_CONTROL':
      handleSimControl(event.steps);
      break;

    case 'VISUAL_READY':
      console.log('[SSE] VISUAL_READY —', event.id, event.title);
      state.generatedVisuals[event.id] = { title: event.title, html: event.html };
      break;
  }
}

// ═══════════════════════════════════════════════════════════
// Module 7: Context Building
// ═══════════════════════════════════════════════════════════

function buildContext() {
  const items = [];

  // Context 1: Student Profile & Course Progress
  const cp = state.checkpoint;
  items.push({
    description: 'Student Profile & Course Progress',
    value: JSON.stringify({
      studentName: state.studentName,
      courseId: state.courseId,
      userEmail: state.userEmail || '',
      currentLessonId: cp.currentLessonId,
      currentSectionIndex: cp.currentSectionIndex,
      completedSections: cp.completedSections,
      sessionCount: cp.sessionCount,
      isReturning: cp.sessionCount > 1,
      studentIntent: state.studentIntent || null,
    }),
  });

  // Context 2: Course Map
  items.push({
    description: 'Course Map — full course structure with modules, lessons, sections, timestamps, and video URLs',
    value: buildCourseContext(),
  });

  // Context 3: Session Metrics
  const elapsed = state.sessionStartTime
    ? Math.floor((Date.now() - state.sessionStartTime) / 1000)
    : 0;
  items.push({
    description: 'Session Metrics',
    value: JSON.stringify({
      sessionTurnCount: state.responses,
      sessionMinutes: Math.floor(elapsed / 60),
      planSummary: buildPlanSummary(),
    }),
  });

  // Context 5: Available Simulations — only current lesson + nearby
  if (state.simulations && state.simulations.length > 0) {
    const relevant = state.simulations.filter(s =>
      s.lesson_id === cp.currentLessonId ||
      s.lesson_id === cp.currentLessonId + 1 ||
      s.lesson_id === cp.currentLessonId - 1
    );
    if (relevant.length > 0) {
      const simLines = relevant.map(s => {
        const tag = s.lesson_id === cp.currentLessonId ? ' [CURRENT]' : '';
        return `  - ID: "${s.id}" | "${s.title}" (${s.tool_type})${tag}`;
      });
      items.push({
        description: 'Available Simulations & Interactive Tools — use ONLY these IDs with <teaching-simulation>',
        value: `${relevant.length} tools for current lesson:\n${simLines.join('\n')}`,
      });
    }
  }

  // Context 6: Course Concepts — compact (names grouped by category)
  if (state.concepts && state.concepts.length > 0) {
    const byCategory = {};
    for (const c of state.concepts) {
      const cat = c.category || 'general';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(c.name);
    }
    const lines = Object.entries(byCategory).map(([cat, names]) =>
      `  ${cat}: ${names.join(', ')}`
    );
    items.push({
      description: 'Course Concepts — all concepts taught in this course',
      value: `${state.concepts.length} concepts by category:\n${lines.join('\n')}`,
    });
  }

  // Context: Active Simulation State (if student has a simulation open)
  if (state.activeSimulation && state.simulationLiveState) {
    const simState = state.simulationLiveState;
    const recentInteractions = simState.interactions.slice(-5).map(i => i.detail).filter(Boolean);
    items.push({
      description: 'Active Simulation State — student is currently viewing an interactive simulation',
      value: JSON.stringify({
        isViewingSimulation: true,
        simulationId: state.activeSimulation.simId,
        simulationTitle: state.activeSimulation.title,
        ready: simState.ready,
        parameters: simState.parameters,
        stateDescription: simState.description,
        recentInteractions,
      }),
    });
  }

  // Context: Spotlight state (if an asset is pinned in the spotlight panel)
  if (state.spotlightActive && state.spotlightInfo) {
    const spotlightCtx = {
      spotlightOpen: true,
      type: state.spotlightInfo.type,
      title: state.spotlightInfo.title,
      id: state.spotlightInfo.id || null,
      rules: [
        'Student can see this asset RIGHT NOW. Reference it naturally.',
        'CLOSE IT when done: emit <teaching-spotlight-dismiss /> when discussion moves past this asset.',
        'REPLACE IT: emitting a new <teaching-video>, <teaching-simulation>, or <teaching-spotlight> tag will auto-replace this content.',
        'Do NOT leave stale assets open — if you are no longer discussing this, close it first.',
      ],
    };

    // Include notebook step history for collaborative context
    if (state.spotlightInfo.type === 'notebook') {
      spotlightCtx.mode = state.spotlightInfo.mode;
      spotlightCtx.stepCount = state.notebookSteps.length;
      if (state.notebookSteps.length > 0) {
        spotlightCtx.steps = state.notebookSteps.map(s => ({
          n: s.n,
          author: s.author || 'tutor',
          type: s.type || 'step',
          annotation: s.annotation || '',
          content: s.math || s.content || '',
          hasDrawing: s.hasDrawing || false,
        }));
      }
      spotlightCtx.rules = [
        ...spotlightCtx.rules,
        'NOTEBOOK IS OPEN — you are collaborating on a shared blackboard.',
        'Three chalk colors: white (your equations via <teaching-notebook-step>), blue (your words via <teaching-notebook-comment>), green (student work).',
        'Use <teaching-notebook-comment>text</teaching-notebook-comment> to write hints, nudges, praise, or explanations on the board in blue chalk.',
        'Use <teaching-notebook-step n="N" annotation="label">$$math$$</teaching-notebook-step> for equation steps in white chalk.',
        'Use <teaching-notebook-step n="N" annotation="label" correction>$$math$$</teaching-notebook-step> for corrections in blue chalk.',
        'When student submits work (appears as a step with author=student), give constructive feedback via <teaching-notebook-comment>.',
        'Do NOT cross out or erase. Everything stays visible — the journey IS the lesson.',
        'After adding a step, ask the student to continue. After student work, give feedback then continue.',
        'When the derivation/problem is complete, dismiss the notebook with <teaching-spotlight-dismiss />.',
      ];
    }

    items.push({
      description: 'ACTIVE SPOTLIGHT — asset currently pinned above chat',
      value: JSON.stringify(spotlightCtx),
    });
  }

  // Teaching Plan Directive — tells the Tutor which step is active and how to advance
  if (state.plan.length > 0) {
    items.push({
      description: 'Teaching Plan Directive — YOUR CURRENT TASK',
      value: buildPlanDirective(),
    });
  }

  // Session History — completed sections & previous sessions (from SessionManager)
  const sessionCtx = SessionManager.buildContextForAI(4000);
  if (sessionCtx) {
    items.push(...sessionCtx);
  }

  return items;
}

function serializePlanState() {
  if (state.plan.length === 0) return 'No plan generated yet.';
  const lines = ['Teaching Plan:'];
  for (const step of state.plan) {
    const status = step.status === 'done' ? '[DONE]' :
                   step.status === 'active' ? '[ACTIVE]' : '[PENDING]';
    lines.push(`  Section ${step.n}: ${status} (${step.modality || step.type}) ${step.title || step.description}`);
    if (step.topics && step.topics.length > 0) {
      for (const topic of step.topics) {
        const tStatus = topic.status === 'done' ? '[DONE]' :
                        topic.status === 'active' ? '[ACTIVE]' : '[PENDING]';
        lines.push(`    Topic: ${tStatus} ${topic.title}${topic.concept ? ` [${topic.concept}]` : ''}`);
      }
    }
    if (step.performance) lines.push(`    Performance: ${step.performance}`);
  }
  return lines.join('\n');
}

function buildPlanSummary() {
  if (state.plan.length === 0) return 'No plan yet';
  const doneSections = state.plan.filter(s => s.status === 'done').length;
  const totalSections = state.plan.length;
  const activeSection = state.plan.find(s => s.status === 'active');
  let summary = `${doneSections}/${totalSections} sections done`;
  if (activeSection) {
    const activeTopic = activeSection.topics ? activeSection.topics.find(t => t.status === 'active') : null;
    summary += `, currently: ${activeSection.title}`;
    if (activeTopic) summary += ` → ${activeTopic.title}`;
  }
  return summary;
}

function buildPlanDirective() {
  const activeSection = state.plan.find(s => s.status === 'active');
  if (!activeSection) {
    const allDone = state.plan.every(s => s.status === 'done');
    if (allDone) {
      return 'All sections and topics complete. Generate a recap or advance with <teaching-checkpoint>.';
    }
    return 'No active section. Generate a <teaching-plan> if one does not exist.';
  }

  const doneSections = state.plan.filter(s => s.status === 'done').length;
  const totalSections = state.plan.length;

  // Find active topic within active section
  const activeTopic = activeSection.topics ? activeSection.topics.find(t => t.status === 'active') : null;
  const doneTopics = activeSection.topics ? activeSection.topics.filter(t => t.status === 'done').length : 0;
  const totalTopics = activeSection.topics ? activeSection.topics.length : 0;

  let directive = `YOU ARE ON SECTION ${activeSection.n} OF ${totalSections} (${doneSections} done).
CURRENT SECTION: ${activeSection.title}
${activeSection.modality ? `MODALITY: ${activeSection.modality}` : ''}`;

  if (activeTopic) {
    directive += `\n\nACTIVE TOPIC: ${activeTopic.title} (${doneTopics}/${totalTopics} topics in this section done)
${activeTopic.concept ? `CONCEPT: ${activeTopic.concept}` : ''}

YOUR TASK THIS TURN: Execute the current topic's steps. When complete, the system will advance via get_next_topic.`;
  } else {
    directive += `\n\nYOUR TASK THIS TURN: Execute step ${activeSection.n}. When the student demonstrates understanding, emit <teaching-plan-update><complete step="${activeSection.n}" /></teaching-plan-update> to advance.`;
  }

  const upcoming = state.plan.filter(s => s.status === 'pending').slice(0, 2);
  if (upcoming.length > 0) {
    directive += `\nUp next: ${upcoming.map(s => `${s.title} (${s.modality})`).join(', ')}`;
  }

  return directive;
}

// ═══════════════════════════════════════════════════════════
// Module 8: Streaming & AI Message Rendering
// ═══════════════════════════════════════════════════════════

function showStreamingIndicator() {
  removeStreamingIndicator();
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block board-text-block fade-in';
  block.dataset.type = 'ai';
  block.id = 'streaming-indicator';
  block.innerHTML = '<div class="board-text" style="color:var(--text-dim);"><span class="loading-spinner"></span> Thinking...</div>';
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;
}

function removeStreamingIndicator() {
  const el = $('#streaming-indicator');
  if (el) el.remove();
}

// ═══════════════════════════════════════════════════════════
// Module 8b: Agent Event System (persistent SSE)
// ═══════════════════════════════════════════════════════════

function connectAgentEvents() {
  disconnectAgentEvents();
  if (!state.sessionId) return;

  const url = `${state.apiUrl}/api/events/${state.sessionId}`;
  const es = new EventSource(url);
  state.agentEventSource = es;

  es.onmessage = (evt) => {
    try {
      const event = JSON.parse(evt.data);
      handleAgentEvent(event);
    } catch (e) {
      // skip unparseable
    }
  };

  es.onerror = () => {
    // EventSource auto-reconnects; just log
    console.warn('[AgentEvents] SSE connection error, will auto-reconnect');
  };

  console.log('[AgentEvents] Connected —', state.sessionId.slice(0, 8));
}

function disconnectAgentEvents() {
  if (state.agentEventSource) {
    state.agentEventSource.close();
    state.agentEventSource = null;
  }
  if (state.autoTriggerTimer) {
    clearTimeout(state.autoTriggerTimer);
    state.autoTriggerTimer = null;
  }
  state.runningAgents = {};
  updateAgentIndicators();
}

function handleAgentEvent(event) {
  switch (event.type) {
    case 'AGENT_SPAWNED':
      state.runningAgents[event.agent_id] = {
        type: event.agent_type,
        description: event.description,
        startTime: Date.now(),
      };
      updateAgentIndicators();
      break;

    case 'AGENT_COMPLETE':
      delete state.runningAgents[event.agent_id];
      updateAgentIndicators();
      handleAgentCompletion(event);
      break;

    case 'AGENT_ERROR':
      delete state.runningAgents[event.agent_id];
      updateAgentIndicators();
      break;

    case 'HEARTBEAT':
    case 'EVENTS_CONNECTED':
      break;
  }
}

function handleAgentCompletion(event) {
  // For visual_gen: cache the HTML immediately (idempotent with VISUAL_READY from chat SSE)
  if (event.agent_type === 'visual_gen' && event.visual_id) {
    state.generatedVisuals[event.visual_id] = { title: event.title, html: event.html };
  }

  // Only auto-trigger for visual_gen (planning/asset are consumed silently on next turn)
  if (event.agent_type !== 'visual_gen') return;

  // Don't trigger if a chat stream is already active — results will be picked up naturally
  if (state.isStreaming) return;

  // Graceful trigger: respect the student's flow
  scheduleGracefulTrigger();
}

function scheduleGracefulTrigger() {
  if (state.autoTriggerTimer) clearTimeout(state.autoTriggerTimer);

  // Check if student is actively typing
  const activeInput = document.querySelector('.text-input:focus, .board-ws-input:focus');
  if (activeInput && activeInput.value.trim().length > 0) {
    // Student is mid-thought — wait 3s of idle, then retry
    state.autoTriggerTimer = setTimeout(() => scheduleGracefulTrigger(), 3000);
    return;
  }

  // Nobody is typing — show typing indicator first, then trigger after a beat
  showStreamingIndicator();
  disableActiveInputs();

  state.autoTriggerTimer = setTimeout(() => {
    state.autoTriggerTimer = null;
    if (state.isStreaming) { reenableInputs(); return; }  // Race check

    // Fire synthetic turn — hidden from student, tutor picks up agent results
    streamADK('[Agent results ready]', true);
  }, 800);
}

function disableActiveInputs() {
  const inputs = document.querySelectorAll('.canvas-block[data-interactive="true"]:not([data-resolved])');
  inputs.forEach(block => {
    block.dataset.agentPaused = 'true';
  });
}

function reenableInputs() {
  document.querySelectorAll('[data-agent-paused="true"]').forEach(block => {
    delete block.dataset.agentPaused;
  });
}

function updateAgentIndicators() {
  const el = document.getElementById('agent-indicators');
  if (!el) return;
  const running = Object.values(state.runningAgents);
  if (!running.length) { el.innerHTML = ''; return; }

  const labels = {
    planning: 'Planning lesson...',
    visual_gen: 'Creating interactive visual...',
    asset: 'Gathering materials...',
    research: 'Researching...',
  };
  el.innerHTML = running.map(a =>
    `<div class="agent-indicator"><span class="loading-spinner small"></span> ${labels[a.type] || a.type}</div>`
  ).join('');
}

function showOnboardingSequence() {
  removeStreamingIndicator();
  appendBlock('system', `
    <div class="onboarding-sequence" id="onboarding-sequence">
      <div class="onboarding-title">Setting up your lesson...</div>
      <div class="onboarding-steps">
        <div class="onboarding-step active" id="onboard-step-1">
          <span class="onboarding-icon"><span class="loading-spinner"></span></span>
          <span>Analyzing your learning profile...</span>
        </div>
        <div class="onboarding-step pending" id="onboard-step-2">
          <span class="onboarding-icon">○</span>
          <span>Creating lesson plan...</span>
        </div>
        <div class="onboarding-step pending" id="onboard-step-3">
          <span class="onboarding-icon">○</span>
          <span>Preparing materials...</span>
        </div>
      </div>
    </div>
  `, { id: 'onboarding-block' });

  // Auto-advance step 1 after 1.5s
  setTimeout(() => {
    const step1 = $('#onboard-step-1');
    const step2 = $('#onboard-step-2');
    if (step1) {
      step1.classList.remove('active');
      step1.classList.add('done');
      step1.querySelector('.onboarding-icon').innerHTML = '✓';
    }
    if (step2) {
      step2.classList.remove('pending');
      step2.classList.add('active');
      step2.querySelector('.onboarding-icon').innerHTML = '<span class="loading-spinner"></span>';
    }
  }, 1500);
}

function transitionOnboardingToTeaching() {
  const step2 = $('#onboard-step-2');
  const step3 = $('#onboard-step-3');

  if (step2) {
    step2.classList.remove('active');
    step2.classList.add('done');
    step2.querySelector('.onboarding-icon').innerHTML = '✓';
  }
  if (step3) {
    step3.classList.remove('pending');
    step3.classList.add('active');
    step3.querySelector('.onboarding-icon').innerHTML = '<span class="loading-spinner"></span>';
  }

  // Complete step 3 and fade out after 800ms
  setTimeout(() => {
    if (step3) {
      step3.classList.remove('active');
      step3.classList.add('done');
      step3.querySelector('.onboarding-icon').innerHTML = '✓';
    }
    const block = $('#onboarding-block');
    if (block) {
      block.style.transition = 'opacity 0.4s ease';
      block.style.opacity = '0';
      setTimeout(() => {
        block.remove();
        // Insert deferred headings from the first plan
        if (state._pendingFirstHeadings && state.plan.length > 0) {
          insertTopicHeading(state.plan[0].title, null, 'section');
          if (state.plan[0].topics && state.plan[0].topics[0]) {
            insertTopicHeading(state.plan[0].topics[0].title, state.plan[0].topics[0].concept, 'topic');
          }
          state._pendingFirstHeadings = false;
        }
        // Show streaming indicator so user knows tutor is about to start
        showStreamingIndicator();
      }, 400);
    }
  }, 800);
}

function handlePlanFromAgent(plan, sessionObjective) {
  if (!plan) return;
  console.log('[Plan Update]', {
    objective: sessionObjective || plan.session_objective || plan.section_title,
    sections: (plan.sections || []).map(s => {
      const topics = (s.topics || []).map(t => t.title).join(', ');
      return `${s.n}. ${s.title} (${s.modality || ''}) [${topics}]`;
    }),
    topics: (plan._topics || plan.topics || []).map(t => t.title),
  });
  state.currentPlan = plan;

  // Build sections from plan — planning agent may output sections or flat topics
  let newSections = [];
  if (plan.sections && plan.sections.length > 0) {
    newSections = plan.sections.map(sec => ({
      n: sec.n || 1,
      title: sec.title || '',
      modality: sec.modality || '',
      covers: sec.covers || '',
      learningOutcome: sec.learning_outcome || '',
      activity: sec.activity || '',
      studentLabel: sec.title || '',
      description: sec.activity || sec.covers || '',
      status: 'pending',
      performance: null,
      topics: (sec.topics || []).map((t, i) => ({
        t: t.t || i + 1,
        title: t.title || '',
        concept: t.concept || '',
        status: 'pending',
      })),
    }));
  } else {
    // Flat topics from planning agent (_topics array)
    const topics = plan._topics || plan.topics || [];
    if (topics.length > 0) {
      newSections = [{
        n: 1,
        title: plan.section_title || plan.session_objective || 'Section',
        modality: '',
        covers: '',
        learningOutcome: plan.learning_outcome || '',
        studentLabel: plan.section_title || 'Section',
        description: plan.learning_outcome || '',
        status: 'pending',
        performance: null,
        topics: topics.map((t, i) => ({
          t: i + 1,
          title: t.title || '',
          concept: t.concept || '',
          status: 'pending',
        })),
      }];
    }
  }

  // Append or replace sections
  const hasExistingSections = state.plan.length > 0 && state.plan.some(s => s.status === 'done' || s.status === 'active');
  if (hasExistingSections && newSections.length > 0) {
    const maxN = Math.max(...state.plan.map(s => s.n));
    newSections.forEach((sec, i) => { sec.n = maxN + 1 + i; });
    state.plan.push(...newSections);
    console.log(`[Plan Update] Appended ${newSections.length} section(s) — total now ${state.plan.length}`);
  } else if (newSections.length > 0) {
    state.plan = newSections;
  }

  // Activate the first pending section + its first topic
  const firstPending = state.plan.find(s => s.status === 'pending');
  if (firstPending) {
    firstPending.status = 'active';
    state.planActiveStep = firstPending.n;
    if (firstPending.topics && firstPending.topics.length > 0) {
      firstPending.topics[0].status = 'active';
    }
    if (state.planCallCount > 0) {
      insertTopicHeading(firstPending.title, null, 'section');
      if (firstPending.topics && firstPending.topics[0]) {
        insertTopicHeading(firstPending.topics[0].title, firstPending.topics[0].concept, 'topic');
      }
    } else {
      state._pendingFirstHeadings = true;
    }
  }

  // Show session objective
  const objEl = $('#plan-objective');
  const sessionObj = sessionObjective || plan.session_objective || plan.section_title;
  if (objEl && sessionObj) {
    objEl.innerHTML = `<div class="plan-objective-text">${escapeHtml(sessionObj)}</div>`;
  }

  SessionManager.setPlan(plan);
  renderPlanProgress();
  state.planCallCount++;
}

function handlePlanReset(reason, keepScope) {
  console.log('[Plan Reset] Clearing plan sidebar — reason:', reason);

  // Clear plan state
  state.plan = [];
  state.planActiveStep = null;
  state.currentPlan = {};

  // Show "replanning" indicator in sidebar
  const stepsEl = $('#plan-steps');
  const container = $('#plan-progress');
  if (stepsEl && container) {
    container.classList.remove('hidden');
    stepsEl.innerHTML = `
      <div class="plan-replanning">
        <div class="plan-replanning-spinner"></div>
        <div class="plan-replanning-text">Replanning...</div>
      </div>
    `;
  }

  // Clear objective if scope is also being reset
  if (!keepScope) {
    const objEl = $('#plan-objective');
    if (objEl) objEl.innerHTML = '';
  }
}

function handleTopicComplete(sectionIndex, topicIndex) {
  // Find the section — try exact match first, then fall back to active section.
  // (One-section-at-a-time: backend TopicManager resets indices to 0 for each new section,
  // but the frontend accumulates sections with incrementing n values.)
  let step = state.plan.find(s => s.n === sectionIndex + 1);
  if (!step || !step.topics) {
    step = state.plan.find(s => s.status === 'active');
  }
  if (step && step.topics) {
    const topic = step.topics.find(t => (t.t - 1) === topicIndex || t.t === topicIndex);
    if (topic) {
      console.log(`[Topic Complete] Section ${step.n}, Topic "${topic.title}" → done`);
      topic.status = 'done';
      // Activate next pending topic in this section
      const nextTopic = step.topics.find(t => t.status === 'pending');
      if (nextTopic) {
        nextTopic.status = 'active';
        console.log(`[Topic Complete] Next active topic: "${nextTopic.title}"`);
        insertTopicHeading(nextTopic.title, nextTopic.concept, 'topic');
      }
    }
  }
  // Record in session DB (fire-and-forget)
  SessionManager.completeTopic(sectionIndex, topicIndex);
  renderPlanProgress();
}

function handleSectionComplete(index) {
  // Find the section — try exact match first, then fall back to active section.
  // (One-section-at-a-time: backend resets indices for each new TopicManager.)
  let step = state.plan.find(s => s.n === index + 1);
  if (!step) {
    step = state.plan.find(s => s.status === 'active');
  }
  if (step) {
    console.log(`[Section Complete] Section ${step.n}: "${step.title}" → done`);
    step.status = 'done';
    const nextPending = state.plan.find(s => s.status === 'pending');
    if (nextPending) {
      nextPending.status = 'active';
      state.planActiveStep = nextPending.n;
      console.log(`[Section Complete] Next active: Section ${nextPending.n}: "${nextPending.title}"`);
      // Auto-insert section heading + first topic heading on the board
      insertTopicHeading(nextPending.title, null, 'section');
      if (nextPending.topics && nextPending.topics[0]) {
        nextPending.topics[0].status = 'active';
        insertTopicHeading(nextPending.topics[0].title, nextPending.topics[0].concept, 'topic');
      }
    } else {
      console.log('[Section Complete] No more pending sections — all done');
    }
    // Stage stays open — tutor controls dismiss via <teaching-spotlight-dismiss>
  } else {
    console.warn(`[Section Complete] No step found for index ${index} (n=${index + 1})`);
  }
  // Record section completion in session (async, fire-and-forget)
  SessionManager.completeSection(index);
  renderPlanProgress();
}

function startAIMessageStream() {
  removeStreamingIndicator();
  // Safety: insert any deferred headings before tutor starts writing
  if (state._pendingFirstHeadings && state.plan.length > 0) {
    insertTopicHeading(state.plan[0].title, null, 'section');
    if (state.plan[0].topics && state.plan[0].topics[0]) {
      insertTopicHeading(state.plan[0].topics[0].title, state.plan[0].topics[0].concept, 'topic');
    }
    state._pendingFirstHeadings = false;
  }
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block board-text-block fade-in';
  block.dataset.type = 'ai';
  block.id = 'ai-stream-msg';
  block.innerHTML = '<div class="board-text streaming-cursor" id="ai-stream-text"></div>';
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;
}

function updateAIMessageStream(text) {
  const el = $('#ai-stream-text');
  if (!el) return;
  bdProcessStreaming(text);
  el.innerHTML = renderMarkdownBasic(stripTeachingTags(text));
  const stream = $('#canvas-stream');
  stream.scrollTop = stream.scrollHeight;
}

function finalizeAIMessage(fullText) {
  const streamEl = $('#ai-stream-msg');
  if (streamEl) streamEl.remove();

  // Disable previous interactive blocks
  disablePreviousInteractive();

  // Strip backend artifacts before parsing
  const cleanedText = fullText.replace(/\[TOOL_STEPS:[^\]]*\]/g, '');
  const segments = parseTeachingTags(cleanedText);

  // Collect tags for controls logic
  const allTags = segments.filter(s => s.type === 'tag').map(s => s.tag);

  // Interactive assessment tags that render their own input controls
  const interactiveTagNames = new Set([
    'teaching-mcq', 'teaching-freetext', 'teaching-agree-disagree',
    'teaching-fillblank', 'teaching-spot-error', 'teaching-confidence',
    'teaching-canvas', 'teaching-teachback'
  ]);

  // Source-order rendering — stop after the first interactive assessment tag
  // (the AI shouldn't send content after an assessment, but if it does, drop it)
  let interactiveRendered = false;
  for (const seg of segments) {
    if (interactiveRendered) break; // nothing renders after an assessment input
    if (seg.type === 'text') {
      const parts = splitTextAtHeadings(seg.content);
      for (const part of parts) {
        if (part.type === 'heading') {
          insertTopicHeading(part.text, null, part.level === 2 ? 'topic' : 'sub');
        } else if (part.content.trim()) {
          appendBoardText(part.content);
        }
      }
    } else if (seg.type === 'tag') {
      renderTeachingTag(seg.tag);
      if (interactiveTagNames.has(seg.tag.name)) {
        interactiveRendered = true;
      }
    }
  }

  // Determine what controls to show
  const lastInteractiveTag = allTags.filter(t =>
    ['teaching-mcq', 'teaching-freetext', 'teaching-agree-disagree',
     'teaching-fillblank', 'teaching-spot-error', 'teaching-confidence',
     'teaching-canvas', 'teaching-teachback'].includes(t.name)
  ).pop();

  const hasRecap = allTags.some(t => t.name === 'teaching-recap');
  const hasVideo = allTags.some(t => t.name === 'teaching-video');

  const fallbackId = 'fallback-' + generateId().slice(0, 8);

  if (lastInteractiveTag) {
    // Interactive tag already rendered its own controls — done
  } else if (hasVideo) {
    // Video but no interactive tag — show "Done watching" + free input (deferred to avoid flash)
    state.pendingFallbackTimer = setTimeout(() => {
      state.pendingFallbackTimer = null;
      appendBlock('ai', `
        <div class="text-input-area">
          ${buildTextInput(fallbackId, 'Type your response...', `submitFreetext('${fallbackId}')`)}
        </div>
      `, { interactive: true });
    }, 120);
  } else if (!hasRecap) {
    // No special tags — full fallback input (deferred to avoid flash before tool calls)
    state.pendingFallbackTimer = setTimeout(() => {
      state.pendingFallbackTimer = null;
      appendBlock('ai', `
        <div class="text-input-area">
          ${buildTextInput(fallbackId, 'Type your response...', `submitFreetext('${fallbackId}')`)}
        </div>
      `, { interactive: true });
    }, 120);
  }
}

function renderUserMessage(text) {
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block board-response fade-in';
  block.dataset.type = 'user';
  block.innerHTML = `<span class="response-label">You</span> <span class="response-text">${escapeHtml(text)}</span>`;
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;
}

function renderAIError(message) {
  appendBlock('system', `
    <div class="ai-label" style="color:var(--red)">Error</div>
    <div class="ai-message" style="color:var(--red)">${escapeHtml(message)}</div>
    <div style="margin-top:12px;text-align:right;">
      <button class="btn btn-primary" onclick="handleRetry()">Retry</button>
    </div>
  `);
}

// ═══════════════════════════════════════════════════════════
// Module 9: Teaching Tag Parser & Renderer
// ═══════════════════════════════════════════════════════════

function parseTeachingTags(text) {
  // Returns ordered array of segments preserving source order:
  // [{ type: 'text', content }, { type: 'tag', tag: { name, attrs, content } }, ...]
  const segments = [];

  // Attribute pattern handles both double-quoted and single-quoted values
  const attrPat = `(?:\\s+[\\w-]+(?:=(?:"[^"]*"|'[^']*'))?)*`;
  const tagRegex = new RegExp(
    `<(teaching-[\\w-]+)(${attrPat})\\s*\\/>`
    + `|<(teaching-[\\w-]+)(${attrPat})\\s*>([\\s\\S]*?)<\\/\\3>`,
    'g'
  );
  let lastIndex = 0;
  let match;

  while ((match = tagRegex.exec(text)) !== null) {
    const before = text.slice(lastIndex, match.index).trim();
    if (before) segments.push({ type: 'text', content: before });

    const name = match[1] || match[3];
    const attrStr = match[2] || match[4] || '';
    const innerContent = match[5] || '';

    const attrs = {};
    // Parse both double-quoted and single-quoted attribute values
    const attrRegex = /([\w-]+)=(?:"([^"]*)"|'([^']*)')/g;
    let attrMatch;
    while ((attrMatch = attrRegex.exec(attrStr)) !== null) {
      attrs[attrMatch[1]] = attrMatch[2] !== undefined ? attrMatch[2] : attrMatch[3];
    }
    // Boolean attributes (no value)
    const boolRegex = /\s([\w-]+)(?=\s|$)(?!=)/g;
    let boolMatch;
    const attrStrClean = attrStr.replace(/[\w-]+=(?:"[^"]*"|'[^']*')/g, '');
    while ((boolMatch = boolRegex.exec(attrStrClean)) !== null) {
      if (!attrs[boolMatch[1]]) attrs[boolMatch[1]] = true;
    }

    segments.push({ type: 'tag', tag: { name, attrs, content: innerContent.trim() } });
    lastIndex = match.index + match[0].length;
  }

  const trailing = text.slice(lastIndex).trim();
  if (trailing) segments.push({ type: 'text', content: trailing });

  return segments;
}

function splitTextAtHeadings(text) {
  // Splits text at markdown ## and ### headings, returns ordered parts
  const parts = [];
  const headingRegex = /^(#{2,3})\s+(.+)$/gm;
  let lastIndex = 0;
  let match;

  while ((match = headingRegex.exec(text)) !== null) {
    const before = text.slice(lastIndex, match.index).trim();
    if (before) parts.push({ type: 'text', content: before });
    parts.push({ type: 'heading', level: match[1].length, text: match[2].trim() });
    lastIndex = match.index + match[0].length;
  }

  const trailing = text.slice(lastIndex).trim();
  if (trailing) parts.push({ type: 'text', content: trailing });

  return parts;
}

function appendBoardText(text) {
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block board-text-block fade-in';
  block.dataset.type = 'ai';
  block.innerHTML = `<div class="board-text">${renderMarkdownBasic(text)}</div>`;
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;
  return block;
}

function insertTopicHeading(title, concept, level = 'topic') {
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = `board-${level}-heading fade-in`;
  const conceptBadge = concept ? `<span class="heading-concept">${escapeHtml(concept)}</span>` : '';
  block.innerHTML = level === 'section'
    ? `<span class="heading-text">${escapeHtml(title)}</span>`
    : `<span class="heading-indicator">\u25b8</span><span class="heading-text">${escapeHtml(title)}</span>${conceptBadge}`;
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;
}

function stripTeachingTags(text) {
  return text
    .replace(/\[TOOL_STEPS:[^\]]*\]/g, '')
    .replace(/<teaching-[\w-]+(?:\s+[\w-]+=(?:"[^"]*"|'[^']*')|\s+[\w-]+)*\s*\/>/g, '')  // self-closing tags
    .replace(/<teaching-([\w-]+)(?:\s+[\w-]+=(?:"[^"]*"|'[^']*')|\s+[\w-]+)*\s*>[\s\S]*?<\/teaching-\1>/g, '')  // content tags
    .replace(/<teaching-[\w-]+[\s\S]*$/g, '')  // trailing unclosed tag (streaming)
    .trim();
}


function renderTeachingTag(tag) {
  // Record visual assets in session (exclude structural/navigation tags)
  const structuralTags = new Set(['teaching-plan', 'teaching-plan-update', 'teaching-checkpoint', 'teaching-spotlight-dismiss', 'teaching-notebook-step', 'teaching-notebook-comment']);

  // Don't record images that fail URL validation — they shouldn't become tutor assets
  let skipAssetRecord = false;
  if (tag.name === 'teaching-image') {
    const src = tag.attrs.src || '';
    const check = validateExternalUrl(src);
    if (!check.valid) {
      console.warn(`[Image blocked] ${check.reason}: ${src}`);
      skipAssetRecord = true;
    }
  }

  if (!structuralTags.has(tag.name) && !skipAssetRecord) {
    SessionManager.recordAsset(tag);
  }

  switch (tag.name) {
    case 'teaching-plan':
      handleTeachingPlan(tag);
      break;
    case 'teaching-plan-update':
      handlePlanUpdateTag(tag);
      break;
    case 'teaching-checkpoint':
      handleTeachingCheckpoint(tag);
      break;
    case 'teaching-video':
      renderVideoTag(tag);
      break;
    case 'teaching-mcq':
      renderMCQTag(tag);
      break;
    case 'teaching-freetext':
      renderFreetextTag(tag);
      break;
    case 'teaching-confidence':
      renderConfidenceTag(tag);
      break;
    case 'teaching-agree-disagree':
      renderAgreeDisagreeTag(tag);
      break;
    case 'teaching-fillblank':
      renderFillBlankTag(tag);
      break;
    case 'teaching-spot-error':
      renderSpotErrorTag(tag);
      break;
    case 'teaching-image':
      renderImageTag(tag);
      break;
    case 'teaching-simulation':
      renderSimulationTag(tag);
      break;
    case 'teaching-recap':
      renderRecapTag(tag);
      break;
    case 'teaching-canvas':
      // Legacy: redirect to spotlight notebook with problem mode
      showSpotlight({
        name: 'teaching-spotlight',
        attrs: {
          type: 'notebook',
          mode: 'problem',
          title: tag.attrs.prompt || 'Drawing Workspace',
          problem: tag.attrs.prompt || 'Draw your answer',
        },
      });
      break;
    case 'teaching-teachback':
      renderTeachbackTag(tag);
      break;
    case 'teaching-board-draw': {
      if (!state.boardDraw.active) {
        const bdTitle = tag.attrs.title || 'Board';
        openBoardDrawSpotlight(bdTitle);
        const bdLines = (tag.content || '').split('\n');
        for (const bdLine of bdLines) {
          const trimmed = bdLine.trim();
          if (!trimmed) continue;
          try { bdEnqueueCommand(JSON.parse(trimmed)); } catch (e) {}
        }
        state.boardDraw.active = true;
      }
      break;
    }
    case 'teaching-interactive':
      showSpotlight({
        name: 'teaching-spotlight',
        attrs: { type: 'interactive', id: tag.attrs.id, title: tag.attrs.title || 'Interactive Visual' },
      });
      break;
    case 'teaching-spotlight':
      showSpotlight(tag);
      break;
    case 'teaching-spotlight-dismiss':
      hideSpotlight({ agentInitiated: true });
      break;
    case 'teaching-notebook-step':
      appendNotebookStep(tag);
      break;
    case 'teaching-notebook-comment':
      appendNotebookComment(tag);
      break;
  }
}

// ═══════════════════════════════════════════════════════════
// Module 10: Teaching Checkpoint Handler
// ═══════════════════════════════════════════════════════════

function handleTeachingCheckpoint(tag) {
  const lessonId = parseInt(tag.attrs.lesson);
  const sectionIndex = parseInt(tag.attrs.section);
  if (isNaN(lessonId) || isNaN(sectionIndex)) return;

  const cp = state.checkpoint;

  if (cp.currentLessonId && cp.currentSectionIndex !== null) {
    const key = `${cp.currentLessonId}:${cp.currentSectionIndex}`;
    if (!cp.completedSections.includes(key)) {
      cp.completedSections.push(key);
    }
  }

  cp.currentLessonId = lessonId;
  cp.currentSectionIndex = sectionIndex;

  SessionManager.updateCoursePosition(lessonId, sectionIndex);
  renderCourseProgress();
}

// ═══════════════════════════════════════════════════════════
// Module 11: Video Tag Renderer
// ═══════════════════════════════════════════════════════════

function buildVideoSrc(videoUrl, startSec, endSec) {
  if (!videoUrl.includes('/embed/')) {
    const match = videoUrl.match(/(?:youtu\.be\/|v=|\/embed\/)([^&?\s]+)/);
    if (match) videoUrl = `https://www.youtube.com/embed/${match[1]}`;
  }
  // Strip any existing query string (e.g. ?list=...) to avoid double-? in the URL
  videoUrl = videoUrl.split('?')[0];
  return `${videoUrl}?start=${startSec}&end=${endSec}&rel=0&modestbranding=1&enablejsapi=1`;
}

function findVideoUrl(lessonId) {
  if (!state.courseMap) return '';
  for (const mod of state.courseMap.modules) {
    for (const lesson of mod.lessons) {
      if (lesson.lesson_id === lessonId) return lesson.video_url || '';
    }
  }
  return '';
}

function renderVideoTag(tag) {
  const start = parseInt(tag.attrs.start || 0);
  const end = parseInt(tag.attrs.end || start + 120);
  const label = tag.attrs.label || 'Watch this segment';
  const lessonId = parseInt(tag.attrs.lesson) || state.checkpoint.currentLessonId;

  // Open directly in spotlight — no inline card
  openVideoInSpotlight(lessonId, start, end, label);
}

function openVideoInSpotlight(lessonId, start, end, label, options = {}) {
  const panel = $('#spotlight-panel');
  const content = $('#spotlight-content');
  const titleEl = $('#spotlight-title');
  const typeBadge = $('#spotlight-type-badge');
  if (!panel || !content) return;

  // Auto-cleanup previous spotlight content
  if (state.spotlightActive) {
    if (state.activeSimulation && state.activeSimulation.blockId.startsWith('spotlight-sim-')) {
      stopSimBridge();
      state.activeSimulation = null;
      state.simulationLiveState = null;
    }
    if (state.spotlightInfo?.type === 'notebook') {
      if (state.notebookCleanup) { state.notebookCleanup(); state.notebookCleanup = null; }
      state.notebookSteps = [];
    }
    content.innerHTML = '';
  }

  const videoUrl = findVideoUrl(lessonId);

  if (!videoUrl) {
    // No video URL for this lesson — skip spotlight entirely, log warning
    console.warn(`teaching-video skipped: no video URL for lesson ${lessonId}`);
    return;
  }

  if (titleEl) titleEl.textContent = label || 'Video segment';
  if (typeBadge) {
    typeBadge.textContent = 'Video';
    typeBadge.setAttribute('data-type', 'video');
    typeBadge.style.display = '';
  }

  const iframeSrc = buildVideoSrc(videoUrl, start, end);
  content.innerHTML = `<iframe src="${escapeAttr(iframeSrc)}" allow="accelerometer; autoplay; encrypted-media; gyroscope" allowfullscreen></iframe>`;

  panel.classList.add('stage-active');
  state.spotlightInfo = { type: 'video', title: label, lessonId, start, end };
  state.spotlightActive = true;
  enterSpotlightFullscreen();

  // Append reference card in chat stream (skip on reopen to prevent duplicates)
  if (!options.skipReference) {
    appendSpotlightReference('video', label || 'Video segment', { lessonId, start, end, label });
  }
}

// ═══════════════════════════════════════════════════════════
// Module 12: Interactive Tag Renderers
// ═══════════════════════════════════════════════════════════

function renderMCQTag(tag) {
  const prompt = tag.attrs.prompt || tag.attrs.question || '';
  const options = [];

  // Strategy 1: Parse <option> elements from content
  const optionRegex = /<option\s+value=(?:"([^"]*)"|'([^']*)')([^>]*)>([^<]*)<\/option>/g;
  let optMatch;
  while ((optMatch = optionRegex.exec(tag.content)) !== null) {
    options.push({
      value: optMatch[1] || optMatch[2],
      correct: optMatch[3].includes('correct'),
      text: optMatch[4],
    });
  }

  // Strategy 2: Pipe-separated "options" attribute (e.g., options="A|B|C|D")
  if (options.length === 0 && tag.attrs.options) {
    const correctIdx = parseInt(tag.attrs.correct || tag.attrs.answer || '0', 10);
    tag.attrs.options.split('|').forEach((text, i) => {
      options.push({
        value: String.fromCharCode(97 + i), // a, b, c, d
        correct: i === correctIdx || i === correctIdx - 1, // support 0-based or 1-based
        text: text.trim(),
      });
    });
  }

  // Strategy 3: Plain text content lines (one option per non-empty line)
  if (options.length === 0 && tag.content) {
    const lines = tag.content.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length >= 2) {
      const correctIdx = parseInt(tag.attrs.correct || tag.attrs.answer || '0', 10);
      lines.forEach((text, i) => {
        // Strip leading letter/number markers like "A)" or "1."
        const cleaned = text.replace(/^[A-Da-d1-4][.):\s]+/, '').trim();
        options.push({
          value: String.fromCharCode(97 + i),
          correct: i === correctIdx || i === correctIdx - 1,
          text: cleaned || text,
        });
      });
    }
  }

  const mcqId = 'mcq-' + generateId().slice(0, 8);
  let optionsHtml = options.map(o => `
    <div class="mcq-option" data-value="${escapeAttr(o.value)}" data-correct="${o.correct}">
      <div class="mcq-radio"></div>
      <span>${renderMarkdownBasic(o.text)}</span>
    </div>
  `).join('');

  appendBlock('mcq', `
    ${prompt ? `<div class="ai-message">${renderMarkdownBasic(prompt)}</div>` : ''}
    <div class="mcq-options" id="${mcqId}">${optionsHtml}</div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${mcqId}" disabled>Submit</button>
    </div>
  `, { interactive: true });

  setTimeout(() => {
    let selected = null;
    $$(`#${mcqId} .mcq-option`).forEach(opt => {
      opt.addEventListener('click', () => {
        $$(`#${mcqId} .mcq-option`).forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        selected = opt.dataset.value;
        const btn = $(`#submit-${mcqId}`);
        if (btn) btn.disabled = false;
      });
    });

    const submitBtn = $(`#submit-${mcqId}`);
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        if (!selected) return;
        $$(`#${mcqId} .mcq-option`).forEach(o => {
          if (o.dataset.correct === 'true') o.classList.add('correct');
          else if (o.classList.contains('selected')) o.classList.add('incorrect');
        });
        submitBtn.disabled = true;
        const selectedText = $$(`#${mcqId} .mcq-option`).find(o => o.dataset.value === selected)?.textContent?.trim();
        const isCorrect = options.find(o => o.value === selected)?.correct === true;
        SessionManager.recordAssessment({
          type: 'mcq',
          question: prompt,
          options: options.map(o => o.text),
          studentAnswer: selectedText || '',
          correctAnswer: options.find(o => o.correct)?.text || '',
          correct: isCorrect,
        });
        setTimeout(() => {
          sendStudentResponse(`[MCQ answer: ${selected}] ${selectedText || ''}`);
        }, 800);
      });
    }
  }, 50);
}

function renderFreetextTag(tag) {
  const prompt = tag.attrs.prompt || '';
  const placeholder = tag.attrs.placeholder || 'Type your answer...';
  const ftId = 'ft-' + generateId().slice(0, 8);

  appendBlock('freetext', `
    ${prompt ? `<div class="ai-message">${renderMarkdownBasic(prompt)}</div>` : ''}
    <div class="freetext-input-container" id="${ftId}-container">
      <div class="input-mode-toggle">
        <button class="mode-btn active" data-mode="text" title="Type answer">${SVG_TEXT}</button>
        <button class="mode-btn" data-mode="draw" title="Draw answer">${SVG_DRAW}</button>
      </div>
      <div class="text-mode" id="${ftId}-text-mode">
        <div class="text-input-area">
          ${buildTextInput(ftId, placeholder, `submitFreetext('${ftId}')`)}
        </div>
      </div>
      <div class="draw-mode" id="${ftId}-draw-mode" style="display:none;"></div>
    </div>
  `, { interactive: true });

  setTimeout(() => { initFreetextToggle(ftId, prompt); }, 50);
}

function initFreetextToggle(ftId, prompt) {
  const container = $(`#${ftId}-container`);
  if (!container) return;

  const toggleBtns = container.querySelectorAll('.mode-btn');
  const textMode = $(`#${ftId}-text-mode`);
  const drawMode = $(`#${ftId}-draw-mode`);
  let canvasInitialized = false;

  toggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      toggleBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      if (mode === 'text') {
        textMode.style.display = '';
        drawMode.style.display = 'none';
      } else {
        textMode.style.display = 'none';
        drawMode.style.display = '';
        if (!canvasInitialized) {
          canvasInitialized = true;
          initFreetextCanvas(ftId, prompt, drawMode);
        }
      }
    });
  });
}

function initFreetextCanvas(ftId, prompt, drawModeEl) {
  const canvasId = ftId + '-canvas';
  drawModeEl.innerHTML = `
    <div class="canvas-toolbar" id="${canvasId}-toolbar">
      <button class="canvas-tool-btn active" data-tool="pen" data-color="#ffffff" title="White pen">
        <span style="color:#ffffff;">&#9679;</span>
      </button>
      <button class="canvas-tool-btn" data-tool="pen" data-color="var(--accent)" title="Blue pen">
        <span style="color:var(--accent);">&#9679;</span>
      </button>
      <button class="canvas-tool-btn" data-tool="pen" data-color="var(--green)" title="Green pen">
        <span style="color:var(--green);">&#9679;</span>
      </button>
      <button class="canvas-tool-btn" data-tool="eraser" title="Eraser">&#9003;</button>
      <span class="canvas-separator"></span>
      <button class="canvas-tool-btn" data-action="linewidth" title="Toggle line width">&#9644;</button>
      <button class="canvas-tool-btn" data-action="clear" title="Clear canvas">&#10005;</button>
    </div>
    <canvas id="${canvasId}" width="640" height="400"></canvas>
    <div class="strip-actions" style="margin-top:12px;">
      <button class="btn btn-primary" id="submit-${canvasId}">Submit Drawing</button>
    </div>
  `;

  const canvas = $(`#${canvasId}`);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = '#1a1d27';
  ctx.fillRect(0, 0, 640, 400);

  let drawing = false;
  let currentColor = '#ffffff';
  let currentTool = 'pen';
  let lineWidth = 2;

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = 640 / rect.width;
    const scaleY = 400 / rect.height;
    if (e.touches) {
      return { x: (e.touches[0].clientX - rect.left) * scaleX, y: (e.touches[0].clientY - rect.top) * scaleY };
    }
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }

  function startDraw(e) {
    e.preventDefault();
    drawing = true;
    const pos = getPos(e);
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
  }

  function draw(e) {
    if (!drawing) return;
    e.preventDefault();
    const pos = getPos(e);
    ctx.lineWidth = currentTool === 'eraser' ? lineWidth * 5 : lineWidth;
    ctx.strokeStyle = currentTool === 'eraser' ? '#1a1d27' : currentColor;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
  }

  function stopDraw() { drawing = false; }

  canvas.addEventListener('mousedown', startDraw);
  canvas.addEventListener('mousemove', draw);
  canvas.addEventListener('mouseup', stopDraw);
  canvas.addEventListener('mouseleave', stopDraw);
  canvas.addEventListener('touchstart', startDraw, { passive: false });
  canvas.addEventListener('touchmove', draw, { passive: false });
  canvas.addEventListener('touchend', stopDraw);

  const toolbar = $(`#${canvasId}-toolbar`);
  toolbar.querySelectorAll('.canvas-tool-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.action === 'clear') {
        ctx.fillStyle = '#1a1d27';
        ctx.fillRect(0, 0, 640, 400);
        return;
      }
      if (btn.dataset.action === 'linewidth') {
        lineWidth = lineWidth === 2 ? 4 : lineWidth === 4 ? 6 : 2;
        return;
      }
      toolbar.querySelectorAll('.canvas-tool-btn[data-tool]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (btn.dataset.tool === 'eraser') {
        currentTool = 'eraser';
      } else {
        currentTool = 'pen';
        currentColor = btn.dataset.color || '#ffffff';
      }
    });
  });

  const submitBtn = $(`#submit-${canvasId}`);
  if (submitBtn) {
    submitBtn.addEventListener('click', () => {
      submitBtn.disabled = true;
      const dataUrl = canvas.toDataURL('image/png');
      const base64Data = dataUrl.split(',')[1];

      const imgBlock = document.createElement('div');
      imgBlock.className = 'canvas-block fade-in';
      imgBlock.dataset.type = 'user';
      imgBlock.innerHTML = `
        <span class="response-label">Your drawing</span>
        <img src="${dataUrl}" alt="Student drawing" style="max-width:100%;border-radius:var(--radius);margin-top:6px;display:block;" />
      `;
      $('#canvas-stream').appendChild(imgBlock);

      // Send as multimodal content (image FIRST to reduce context-anchoring bias)
      if (!state.isStreaming) {
        streamADK([
          { type: 'image', source: { type: 'base64', media_type: 'image/png', data: base64Data } },
          { type: 'text', text: `[Canvas drawing] Student drew a response to: "${prompt}". FIRST describe exactly what you see in the drawing before interpreting it.` },
        ]);
      }
    });
  }
}

function renderConfidenceTag(tag) {
  const prompt = tag.attrs.prompt || 'How confident are you?';
  const confId = 'conf-' + generateId().slice(0, 8);

  appendBlock('confidence', `
    <div class="confidence-container">
      <span class="confidence-label">${escapeHtml(prompt)}</span>
      <input type="range" class="confidence-slider" id="${confId}" min="0" max="100" value="50">
      <span class="confidence-value" id="${confId}-val">50%</span>
    </div>
    <div class="strip-actions">
      <button class="btn btn-primary" onclick="submitConfidence('${confId}')">Submit</button>
    </div>
  `, { interactive: true });

  setTimeout(() => {
    const slider = $(`#${confId}`);
    const valEl = $(`#${confId}-val`);
    if (slider && valEl) {
      slider.addEventListener('input', () => {
        valEl.textContent = slider.value + '%';
      });
    }
  }, 50);
}

window.submitConfidence = function(confId) {
  const slider = $(`#${confId}`);
  if (!slider) return;
  sendStudentResponse(`[Confidence: ${slider.value}%]`);
};

function renderAgreeDisagreeTag(tag) {
  const prompt = tag.attrs.prompt || '';
  const adId = 'ad-' + generateId().slice(0, 8);

  appendBlock('agree', `
    ${prompt ? `<div class="ai-message">${renderMarkdownBasic(prompt)}</div>` : ''}
    <div class="agree-toggle" id="${adId}">
      <button class="agree-btn agree" data-value="agree">Agree</button>
      <button class="agree-btn disagree" data-value="disagree">Disagree</button>
    </div>
    <div class="text-input-area">
      <textarea class="text-input" id="${adId}-reason" placeholder="Explain your reasoning..."></textarea>
    </div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${adId}" disabled>Submit</button>
    </div>
  `, { interactive: true });

  setTimeout(() => {
    let choice = null;
    $$(`#${adId} .agree-btn`).forEach(btn => {
      btn.addEventListener('click', () => {
        $$(`#${adId} .agree-btn`).forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        choice = btn.dataset.value;
        const submitBtn = $(`#submit-${adId}`);
        if (submitBtn) submitBtn.disabled = false;
      });
    });

    const submitBtn = $(`#submit-${adId}`);
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        if (!choice) return;
        submitBtn.disabled = true;
        const reason = $(`#${adId}-reason`)?.value?.trim() || '';
        sendStudentResponse(`[${choice}] ${reason}`);
      });
    }
  }, 50);
}

function renderFillBlankTag(tag) {
  const fbId = 'fb-' + generateId().slice(0, 8);
  let content = tag.content;

  let blankCount = 0;
  content = content.replace(/<blank\s+id="([^"]*)"([^>]*)\s*\/>/g, (_, id, attrs) => {
    blankCount++;
    const optionsMatch = attrs.match(/options="([^"]*)"/);

    if (optionsMatch) {
      const opts = optionsMatch[1].split(',').map(o => o.trim());
      return `<select class="blank-select" id="${fbId}-${id}">
        <option value="">Select...</option>
        ${opts.map(o => `<option value="${o}">${o}</option>`).join('')}
      </select>`;
    } else {
      return `<input type="text" class="blank-input" id="${fbId}-${id}" placeholder="..." style="width:120px;">`;
    }
  });

  appendBlock('fillblank', `
    <div class="blank-container">${content}</div>
    <div class="strip-actions">
      <button class="btn btn-primary" onclick="submitFillBlank('${fbId}', ${blankCount})">Check</button>
    </div>
  `, { interactive: true });
}

function renderSpotErrorTag(tag) {
  const quote = tag.attrs.quote || '';
  const prompt = tag.attrs.prompt || 'What\'s wrong with this?';
  const seId = 'se-' + generateId().slice(0, 8);

  appendBlock('spot-error', `
    <h3 style="font-size:15px;font-weight:600;margin-bottom:12px;">Spot the Error</h3>
    <div class="error-quote">
      <div class="error-quote-label">Student Explanation</div>
      ${escapeHtml(quote)}
    </div>
    <div class="ai-message">${renderMarkdownBasic(prompt)}</div>
    <div class="text-input-area">
      ${buildTextInput(seId, 'The flaw is...', `submitFreetext('${seId}')`)}
    </div>
  `, { interactive: true });
}


function renderImageTag(tag) {
  const src = tag.attrs.src || '';
  const caption = tag.attrs.caption || '';
  if (!src) return;

  // Validate external URL before rendering — silently drop invalid images
  const check = validateExternalUrl(src);
  if (!check.valid) {
    // Don't render anything — invalid images are silently dropped
    // (already logged in renderTeachingTag, not recorded as asset)
    return;
  }

  const isVideo = src.endsWith('.mp4') || src.endsWith('.webm');
  const mediaEl = isVideo
    ? `<video src="${escapeAttr(src)}" autoplay loop muted playsinline
             style="max-width:100%;max-height:500px;border-radius:8px;"
             onerror="this.parentElement.innerHTML='<div class=\\'image-error\\'>Animation unavailable</div>'"
             onloadeddata="this.style.opacity='1'" />`
    : `<img src="${escapeAttr(src)}" alt="${escapeAttr(caption)}"
           loading="lazy"
           onerror="this.parentElement.innerHTML='<div class=\\'image-error\\'>Image unavailable</div>'"
           onload="this.style.opacity='1'" />`;
  appendBlock('image', `
    <div class="teaching-image-card">
      ${mediaEl}
      ${caption ? `<div class="image-caption">${escapeHtml(caption)}</div>` : ''}
    </div>
  `);
}

function renderSimulationTag(tag) {
  const simId = tag.attrs.id || 'unknown';

  // Open directly in spotlight — no inline card
  showSpotlight({ attrs: { type: 'simulation', id: simId } });
}

// ═══════════════════════════════════════════════════════════
// Simulation: Open / Close / Fullscreen
// ═══════════════════════════════════════════════════════════

window.openSimulation = async function(simId, blockId) {
  const openBtn = $(`#${blockId}-open`);
  if (openBtn) {
    openBtn.disabled = true;
    openBtn.innerHTML = '<span class="loading-spinner"></span> Loading simulation...';
  }

  try {
    // Fetch entry_url from backend
    const res = await fetch(`${state.apiUrl}/api/v1/learning-tools/${simId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const entryUrl = data.content?.entry_url || data.entry_url;
    if (!entryUrl) throw new Error('No entry URL found for this simulation');

    const simData = state.simulations.find(s => s.id === simId);
    const displayTitle = simData ? simData.title : simId;

    // Open in spotlight panel instead of inline
    const panel = $('#spotlight-panel');
    const spotlightContent = $('#spotlight-content');
    const titleEl = $('#spotlight-title');

    if (panel && spotlightContent) {
      const spotlightBlockId = 'spotlight-sim-' + generateId().slice(0, 8);
      if (titleEl) titleEl.textContent = displayTitle;
      spotlightContent.innerHTML = `<iframe id="${spotlightBlockId}-iframe" src="${escapeAttr(entryUrl)}" allow="accelerometer; autoplay; encrypted-media; gyroscope" allowfullscreen></iframe>`;
      panel.classList.add('stage-active');

      // Start simulation bridge
      startSimBridge(simId, spotlightBlockId);

      // Track active simulation + spotlight (keep reference to inline card blockId)
      state.activeSimulation = { simId, blockId: spotlightBlockId, title: displayTitle, entryUrl };
      state.spotlightInfo = { type: 'simulation', title: displayTitle, id: simId, inlineBlockId: blockId };
      state.spotlightActive = true;
    }

    // Show "open above" state on inline card
    const cardEl = $(`#${blockId}-card`);
    if (cardEl) {
      cardEl.innerHTML = `
        <div class="sim-open-above">
          <div class="sim-open-above-icon">&#8593;</div>
          <div class="sim-open-above-text">Simulation open above</div>
          <button class="sim-toolbar-btn" onclick="hideSpotlight(); closeSimulation('${blockId}')">Close simulation</button>
        </div>
      `;
    }

  } catch (err) {
    if (openBtn) {
      openBtn.disabled = false;
      openBtn.innerHTML = '&#9654; Open Simulation';
    }
    console.error('Failed to open simulation:', err);
    appendBlock('system', `
      <div class="ai-label" style="color:var(--red)">Simulation Error</div>
      <div class="ai-message" style="color:var(--text-muted)">${escapeHtml(err.message)}</div>
    `);
  }
};

window.closeSimulation = function(blockId) {
  const cardEl = $(`#${blockId}-card`);
  if (cardEl) {
    // Restore original card with open button
    const simContainer = $(`#${blockId}`);
    const simId = state.activeSimulation?.simId || '';
    const simData = state.simulations.find(s => s.id === simId);
    const displayTitle = simData ? simData.title : simId;
    const thumbnailUrl = simData ? simData.thumbnail_url : '';
    const displayDesc = simData ? simData.description : '';
    const toolType = simData ? simData.tool_type : 'simulation';

    const thumbHtml = thumbnailUrl
      ? `<img src="${escapeHtml(thumbnailUrl)}" alt="${escapeHtml(displayTitle)}" style="width:100%;max-height:200px;object-fit:cover;border-radius:8px;margin-bottom:12px;" />`
      : `<div style="padding:40px;text-align:center;color:var(--text-dim);background:rgba(255,255,255,0.03);border-radius:8px;margin-bottom:12px;">
          <div style="font-size:32px;margin-bottom:8px;">&#9881;</div>
          Interactive ${escapeHtml(toolType)}
        </div>`;

    cardEl.innerHTML = `
      ${thumbHtml}
      ${displayDesc ? `<div style="font-size:13px;color:var(--text-muted);margin-bottom:12px;line-height:1.5;">${escapeHtml(displayDesc)}</div>` : ''}
      <button class="sim-open-btn" id="${blockId}-open" onclick="openSimulation('${escapeAttr(simId)}', '${blockId}')">
        &#9654; Open Simulation
      </button>
    `;
  }

  // Clean up bridge
  stopSimBridge();
  state.activeSimulation = null;
  state.simulationLiveState = null;
};

window.openSimFullscreen = function(blockId, title) {
  const iframe = $(`#${blockId}-iframe`);
  if (!iframe) return;

  const overlay = $('#sim-fullscreen-overlay');
  const fsIframe = $('#sim-fullscreen-iframe');
  const fsTitle = $('#sim-fullscreen-title');

  if (overlay && fsIframe) {
    fsIframe.src = iframe.src;
    if (fsTitle) fsTitle.textContent = title || 'Simulation';
    overlay.classList.remove('hidden');
  }
};

function closeSimFullscreen() {
  const overlay = $('#sim-fullscreen-overlay');
  const fsIframe = $('#sim-fullscreen-iframe');
  if (overlay) overlay.classList.add('hidden');
  if (fsIframe) fsIframe.src = '';
}

// ═══════════════════════════════════════════════════════════
// Simulation Bridge (postMessage communication)
// ═══════════════════════════════════════════════════════════

function startSimBridge(simId, blockId) {
  stopSimBridge(); // clean up any existing listener

  state.simulationLiveState = {
    ready: false,
    parameters: {},
    description: null,
    interactions: [],
    lastInteraction: null,
  };

  const listener = (event) => {
    const data = event.data;
    if (!data || typeof data.type !== 'string') return;

    switch (data.type) {
      case 'capacity-sim-ready':
        state.simulationLiveState.ready = true;
        console.log(`[SimBridge] Simulation ${simId} ready`);
        break;

      case 'capacity-sim-state':
        if (data.payload) {
          state.simulationLiveState.parameters = data.payload.parameters || {};
          state.simulationLiveState.description = data.payload.description || null;
        }
        break;

      case 'capacity-sim-interaction':
        if (data.payload) {
          const interaction = {
            action: data.payload.action || '',
            detail: data.payload.detail || '',
            ts: Date.now(),
          };
          state.simulationLiveState.interactions.push(interaction);
          // Keep rolling window of last 25
          if (state.simulationLiveState.interactions.length > 25) {
            state.simulationLiveState.interactions.shift();
          }
          state.simulationLiveState.lastInteraction = interaction.detail;
        }
        break;

      case 'capacity-sim-ack':
        // Acknowledgment of a command — log for debugging
        if (data.payload && !data.payload.success) {
          console.warn('[SimBridge] Command failed:', data.payload.error);
        }
        break;
    }
  };

  window.addEventListener('message', listener);
  state.simBridgeListener = listener;
}

function stopSimBridge() {
  if (state.simBridgeListener) {
    window.removeEventListener('message', state.simBridgeListener);
    state.simBridgeListener = null;
  }
}

function sendToSimulation(type, payload) {
  if (!state.activeSimulation) return;
  const blockId = state.activeSimulation.blockId;

  // Try inline iframe first, then fullscreen iframe
  const iframe = $(`#${blockId}-iframe`) || $('#sim-fullscreen-iframe');
  if (iframe && iframe.contentWindow) {
    iframe.contentWindow.postMessage({ type, payload }, '*');
  }
}

// Handle SIM_CONTROL SSE events from server (ControlSimulation tool results)
function handleSimControl(steps) {
  if (!state.activeSimulation || !Array.isArray(steps)) return;

  for (const step of steps) {
    if (step.action === 'set_parameter') {
      sendToSimulation('capacity-parent-set-param', {
        name: step.name,
        value: step.value,
      });
    } else if (step.action === 'click_button') {
      sendToSimulation('capacity-parent-click-button', {
        label: step.label,
      });
    }
  }
}

function renderRecapTag(tag) {
  const content = tag.content || '';

  const recapFbId = 'recap-' + generateId().slice(0, 8);
  appendBlock('recap', `
    <div class="recap-header">SESSION RECAP</div>
    <div class="recap-section">
      <div style="font-size:14px;line-height:1.7;color:var(--text-muted);">
        ${renderMarkdownBasic(content)}
      </div>
    </div>
    <div class="text-input-area" style="margin-top:12px;">
      ${buildTextInput(recapFbId, 'Continue, ask a question, or take a break...', `submitFreetext('${recapFbId}')`)}
    </div>
  `, { interactive: true });
}

// ═══════════════════════════════════════════════════════════
// Module 13: Canvas Tag Renderer
// ═══════════════════════════════════════════════════════════

// renderCanvasTag and renderCanvasGrid removed — teaching-canvas now routes to spotlight notebook

// ═══════════════════════════════════════════════════════════
// Module 15: Teachback Tag Renderer
// ═══════════════════════════════════════════════════════════

function renderTeachbackTag(tag) {
  const prompt = tag.attrs.prompt || 'Explain this concept in your own words.';
  const concept = tag.attrs.concept || 'this concept';
  const tbId = 'tb-' + generateId().slice(0, 8);

  appendBlock('teachback', `
    <div class="teaching-teachback-card">
      <div class="teachback-header">
        <span class="teachback-icon">&#9997;</span>
        <span>Teach Me Back: <strong>${escapeHtml(concept)}</strong></span>
      </div>
      <div class="ai-message">${renderMarkdownBasic(prompt)}</div>
      <div class="teachback-helper">Use your own words. Imagine I'm a classmate who missed this lecture.</div>
      <div class="text-input-area">
        ${buildTextInput(tbId, 'Explain it in your own words...', `submitTeachback('${tbId}', '${escapeAttr(concept)}')`)}
      </div>
    </div>
  `, { interactive: true });
}

window.submitTeachback = function(tbId, concept) {
  const el = $(`#${tbId}`);
  if (!el) return;
  const val = el.value.trim();
  if (!val) return;
  sendStudentResponse(`[Teach-back: ${concept}] ${val}`);
};

// ═══════════════════════════════════════════════════════════
// Module 16: Teaching Plan Manager
// ═══════════════════════════════════════════════════════════

function handleTeachingPlan(tag) {
  const stepOpenRegex = /<step\b([^>]*)>([\s\S]*?)<\/step>/g;
  state.plan = [];
  let stepMatch;
  while ((stepMatch = stepOpenRegex.exec(tag.content)) !== null) {
    const attrStr = stepMatch[1];
    const desc = stepMatch[2].trim();
    const n = attrStr.match(/n="(\d+)"/);
    const type = attrStr.match(/type="([^"]*)"/);
    const concept = attrStr.match(/concept="([^"]*)"/);
    const modality = attrStr.match(/modality="([^"]*)"/);

    if (n) {
      state.plan.push({
        n: parseInt(n[1]),
        type: type ? type[1] : '',
        concept: concept ? concept[1] : '',
        modality: modality ? modality[1] : '',
        description: desc,
        status: 'pending',
        performance: null,
      });
    }
  }

  if (state.plan.length > 0) {
    state.plan[0].status = 'active';
    state.planActiveStep = 1;
  }

  // Sync to session — convert parsed plan to plan data format
  if (state.plan.length > 0) {
    SessionManager.setPlan({
      sections: state.plan.map(s => ({
        n: s.n, title: s.description || `Step ${s.n}`,
        modality: s.modality || s.type || '',
        covers: s.concept || '', learning_outcome: s.description || '',
      })),
    });
  }

  renderPlanProgress();
}

function handlePlanUpdateTag(tag) {
  const completeRegex = /<complete\s+step="(\d+)"[^>]*\/>/g;
  let completeMatch;
  while ((completeMatch = completeRegex.exec(tag.content)) !== null) {
    const n = parseInt(completeMatch[1]);
    const step = state.plan.find(s => s.n === n);
    if (step) {
      step.status = 'done';
      const nextPending = state.plan.find(s => s.status === 'pending');
      if (nextPending) {
        nextPending.status = 'active';
        state.planActiveStep = nextPending.n;
      }
      // Auto-dismiss spotlight when step completes
      if (state.spotlightActive) {
        hideSpotlight();
      }
    }
  }

  const removeRegex = /<remove\s+step="(\d+)"[^>]*\/>/g;
  let removeMatch;
  while ((removeMatch = removeRegex.exec(tag.content)) !== null) {
    const n = parseInt(removeMatch[1]);
    state.plan = state.plan.filter(s => s.n !== n);
  }

  const insertRegex = /<insert\b([^>]*)(?:>([\s\S]*?)<\/insert>|\/>)/g;
  let insertMatch;
  while ((insertMatch = insertRegex.exec(tag.content)) !== null) {
    const attrStr = insertMatch[1];
    const desc = (insertMatch[2] || '').trim();
    const afterN = attrStr.match(/after="(\d+)"/);
    const type = attrStr.match(/type="([^"]*)"/);
    const concept = attrStr.match(/concept="([^"]*)"/);

    if (afterN) {
      const idx = state.plan.findIndex(s => s.n === parseInt(afterN[1]));
      if (idx >= 0) {
        const newStep = {
          n: parseInt(afterN[1]) + 0.5,
          type: type ? type[1] : '',
          concept: concept ? concept[1] : '',
          modality: '',
          description: desc,
          status: 'pending',
          performance: null,
        };
        state.plan.splice(idx + 1, 0, newStep);
      }
    }
  }

  state.plan.forEach((s, i) => s.n = i + 1);

  const active = state.plan.find(s => s.status === 'active');
  state.planActiveStep = active ? active.n : null;

  renderPlanProgress();
}

function renderPlanProgress() {
  const container = $('#plan-progress');
  const stepsEl = $('#plan-steps');
  if (!container || !stepsEl) return;

  if (state.plan.length === 0) {
    container.classList.add('hidden');
    return;
  }

  container.classList.remove('hidden');

  // Count total topics for progress
  let totalTopics = 0;
  let doneTopics = 0;
  for (const step of state.plan) {
    if (step.topics && step.topics.length > 0) {
      totalTopics += step.topics.length;
      doneTopics += step.topics.filter(t => t.status === 'done').length;
    } else {
      // No topic sub-items — count section itself
      totalTopics += 1;
      if (step.status === 'done') doneTopics += 1;
    }
  }
  const pct = totalTopics > 0 ? Math.round((doneTopics / totalTopics) * 100) : 0;

  let html = `
    <div class="plan-progress-bar-container">
      <div class="plan-progress-bar">
        <div class="plan-progress-fill" style="width:${pct}%"></div>
      </div>
      <div class="plan-progress-label">${doneTopics} of ${totalTopics} complete</div>
    </div>
  `;

  for (const step of state.plan) {
    const statusClass = step.status; // 'done', 'active', or 'pending'
    const icon = step.status === 'done' ? '✓'
      : step.status === 'active' ? '●'
      : '○';
    const title = step.studentLabel || step.title || step.description || `Step ${step.n}`;
    const tooltip = step.objective || step.learningOutcome
      ? ` title="${escapeAttr(step.objective || step.learningOutcome || '')}"` : '';
    const modalityBadge = step.modality
      ? `<span class="plan-step-modality">${escapeHtml(step.modality.replace(/_/g, ' '))}</span>`
      : '';

    html += `
      <div class="plan-step ${statusClass}">
        <div class="plan-step-indicator">${icon}</div>
        <div class="plan-step-text">
          <div class="plan-step-title"${tooltip}>${escapeHtml(title)} ${modalityBadge}</div>
        </div>
      </div>
    `;

    // Render nested topics within this section
    if (step.topics && step.topics.length > 0) {
      for (const topic of step.topics) {
        const topicStatus = topic.status || 'pending';
        const topicIcon = topicStatus === 'done' ? '✓'
          : topicStatus === 'active' ? '›'
          : '·';
        const topicTitle = topic.title || `Topic ${topic.t}`;
        const conceptBadge = topic.concept
          ? `<span class="plan-topic-concept">${escapeHtml(topic.concept)}</span>`
          : '';

        html += `
          <div class="plan-topic ${topicStatus}">
            <div class="plan-topic-indicator">${topicIcon}</div>
            <div class="plan-topic-text">
              <div class="plan-topic-title">${escapeHtml(topicTitle)} ${conceptBadge}</div>
            </div>
          </div>
        `;
      }
    }
  }

  stepsEl.innerHTML = html;
}


// ═══════════════════════════════════════════════════════════
// Module 17: Tool Call Handlers
// ═══════════════════════════════════════════════════════════

function handleToolCallStart(event) {
  const toolId = event.toolCallId || event.tool_call_id;
  const toolName = event.toolCallName || event.tool_call_name;
  state.activeToolCalls[toolId] = { name: toolName, args: '' };

  // Internal orchestration tools run in the background while the student
  // interacts with an assessment. Do NOT disable interactive elements or
  // show "Thinking..." — the assessment IS the student-facing activity.
  const internalTools = ['spawn_agent', 'check_agents', 'advance_topic', 'delegate_teaching'];
  if (internalTools.includes(toolName)) {
    // Internal tools run in background — do NOT cancel fallback input timer.
    return;
  }

  // Disable any fallback input areas — the Tutor is executing a tool, not waiting for student input
  disablePreviousInteractive();

  // Cancel pending fallback timer — tool is starting, no need for fallback input
  if (state.pendingFallbackTimer) {
    clearTimeout(state.pendingFallbackTimer);
    state.pendingFallbackTimer = null;
  }

  if (toolName) {
    // For visible tools, show a user-friendly indicator
    removeStreamingIndicator();
    const friendlyNames = {
      'search_images': 'Searching for images...',
      'get_section_content': 'Reading course materials...',
      'get_simulation_details': 'Loading simulation...',
      'control_simulation': 'Adjusting simulation...',
    };
    const label = friendlyNames[toolName] || 'Working...';
    appendBlock('system', `
      <div class="tool-indicator active" id="tool-${toolId}">
        <span class="loading-spinner"></span>
        ${escapeHtml(label)}
      </div>
    `);
  }
}

function handleToolCallArgs(event) {
  const toolId = event.toolCallId || event.tool_call_id;
  if (state.activeToolCalls[toolId]) {
    state.activeToolCalls[toolId].args += event.delta || '';
  }
}

function handleToolCallEnd(event) {
  const toolId = event.toolCallId || event.tool_call_id;
  const call = state.activeToolCalls[toolId];
  if (!call) return;

  const indicator = $(`#tool-${toolId}`);
  if (indicator) {
    indicator.classList.remove('active');
    indicator.querySelector('.loading-spinner')?.remove();
    setTimeout(() => {
      const block = indicator.closest('.canvas-block');
      if (block) block.remove();
    }, 2000);
  }
}

function cleanupToolIndicators() {
  document.querySelectorAll('.tool-indicator').forEach(el => {
    const block = el.closest('.canvas-block');
    if (block) block.remove();
  });
  state.activeToolCalls = {};
}

// ═══════════════════════════════════════════════════════════
// Module 17b: Spotlight Panel
// ═══════════════════════════════════════════════════════════

async function showSpotlight(tag, options = {}) {
  const panel = $('#spotlight-panel');
  const content = $('#spotlight-content');
  const titleEl = $('#spotlight-title');
  const typeBadge = $('#spotlight-type-badge');
  if (!panel || !content) return;

  // Auto-cleanup: if spotlight already has content, close it first
  if (state.spotlightActive) {
    // Clean up simulation bridge if previous was a sim or interactive visual
    if (state.activeSimulation && (state.activeSimulation.blockId.startsWith('spotlight-sim-') || state.activeSimulation.blockId.startsWith('spotlight-vis-'))) {
      stopSimBridge();
      state.activeSimulation = null;
      state.simulationLiveState = null;
    }
    // Clean up notebook state
    if (state.spotlightInfo?.type === 'notebook') {
      if (state.notebookCleanup) { state.notebookCleanup(); state.notebookCleanup = null; }
      state.notebookSteps = [];
    }
    content.innerHTML = '';
  }

  const type = tag.attrs.type || '';

  // Set type badge
  const typeLabels = { simulation: 'Simulation', video: 'Video', image: 'Image', notebook: 'Notebook', 'board-draw': 'Board', interactive: 'Interactive' };
  if (typeBadge) {
    typeBadge.textContent = typeLabels[type] || type;
    typeBadge.setAttribute('data-type', type);
    typeBadge.style.display = type ? '' : 'none';
  }

  if (type === 'simulation') {
    const simId = tag.attrs.id;
    if (!simId) return;

    const simData = state.simulations.find(s => s.id === simId);
    const displayTitle = simData ? simData.title : simId;
    if (titleEl) titleEl.textContent = displayTitle;

    content.innerHTML = '<div style="text-align:center;padding:20px;"><span class="loading-spinner"></span> Loading simulation...</div>';
    panel.classList.add('stage-active');

    try {
      const res = await fetch(`${state.apiUrl}/api/v1/learning-tools/${simId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const entryUrl = data.content?.entry_url || data.entry_url;
      if (!entryUrl) throw new Error('No entry URL');

      const spotlightBlockId = 'spotlight-sim-' + generateId().slice(0, 8);
      content.innerHTML = `<iframe id="${spotlightBlockId}-iframe" src="${escapeAttr(entryUrl)}" allow="accelerometer; autoplay; encrypted-media; gyroscope" allowfullscreen></iframe>`;

      // Start sim bridge for spotlight
      startSimBridge(simId, spotlightBlockId);
      state.activeSimulation = { simId, blockId: spotlightBlockId, title: displayTitle, entryUrl };
      state.spotlightInfo = { type: 'simulation', title: displayTitle, id: simId };
    } catch (err) {
      content.innerHTML = `<div style="padding:20px;color:var(--text-dim);text-align:center;">Failed to load simulation: ${escapeHtml(err.message)}</div>`;
    }

  } else if (type === 'image') {
    const src = tag.attrs.src || '';
    const caption = tag.attrs.caption || '';
    if (!src) return;

    // Validate external URL before rendering in spotlight
    const check = validateExternalUrl(src);
    if (!check.valid) {
      console.warn(`[Spotlight image blocked] ${check.reason}: ${src}`);
      if (titleEl) titleEl.textContent = caption || 'Image';
      content.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-dim);">Image unavailable — ${escapeHtml(check.reason)}</div>`;
      panel.classList.add('stage-active');
      state.spotlightInfo = { type: 'image', title: caption || 'Image' };
      return;
    }

    if (titleEl) titleEl.textContent = caption || 'Image';

    const isVideo = src.endsWith('.mp4') || src.endsWith('.webm');
    const mediaEl = isVideo
      ? `<video src="${escapeAttr(src)}" autoplay loop muted playsinline />`
      : `<img src="${escapeAttr(src)}" alt="${escapeAttr(caption)}" />`;
    content.innerHTML = `${mediaEl}${caption ? `<div class="spotlight-caption">${escapeHtml(caption)}</div>` : ''}`;
    panel.classList.add('stage-active');
    state.spotlightInfo = { type: 'image', title: caption || 'Image' };

  } else if (type === 'video') {
    const lessonId = parseInt(tag.attrs.lesson) || state.checkpoint.currentLessonId;
    const start = parseInt(tag.attrs.start || 0);
    const end = parseInt(tag.attrs.end || start + 120);
    const label = tag.attrs.label || 'Video segment';

    const videoUrl = findVideoUrl(lessonId);
    if (titleEl) titleEl.textContent = label;

    if (videoUrl) {
      const iframeSrc = buildVideoSrc(videoUrl, start, end);
      content.innerHTML = `<iframe src="${escapeAttr(iframeSrc)}" allow="accelerometer; autoplay; encrypted-media; gyroscope" allowfullscreen></iframe>`;
    } else {
      const startFmt = formatTimestamp(start);
      const endFmt = formatTimestamp(end);
      content.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-dim);">Video: ${startFmt} - ${endFmt}</div>`;
    }
    panel.classList.add('stage-active');
    state.spotlightInfo = { type: 'video', title: label };

  } else if (type === 'interactive') {
    // ═══ GENERATED INTERACTIVE VISUAL ═══
    const visId = tag.attrs.id;
    const visual = state.generatedVisuals[visId];
    if (!visual) {
      const iTitle = tag.attrs.title || 'Interactive Visual';
      if (titleEl) titleEl.textContent = iTitle;
      content.innerHTML = '<div style="padding:20px;color:var(--text-dim);text-align:center;">Visual not ready yet — it may still be generating.</div>';
      panel.classList.add('stage-active');
      state.spotlightActive = true;
      state.spotlightInfo = { type: 'interactive', title: iTitle };
    } else {
      const iTitle = tag.attrs.title || visual.title || 'Interactive Visual';
      if (titleEl) titleEl.textContent = iTitle;

      const spotlightBlockId = 'spotlight-vis-' + generateId().slice(0, 8);
      const iframe = document.createElement('iframe');
      iframe.id = spotlightBlockId + '-iframe';
      iframe.srcdoc = visual.html;
      iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin');
      iframe.setAttribute('allow', 'accelerometer');
      iframe.style.cssText = 'width:100%;height:100%;border:none;';

      content.innerHTML = '';
      content.appendChild(iframe);
      panel.classList.add('stage-active');
      state.spotlightActive = true;

      // Reuse simulation bridge for interaction tracking
      startSimBridge(visId, spotlightBlockId);
      state.activeSimulation = { simId: visId, blockId: spotlightBlockId, title: iTitle, isGenerated: true };
      state.spotlightInfo = { type: 'interactive', title: iTitle, id: visId };
    }

  } else if (type === 'notebook') {
    // ═══ NOTEBOOK / SHARED BOARD (derivation or problem workspace) ═══
    const mode = tag.attrs.mode || 'derivation';
    const title = tag.attrs.title || (mode === 'derivation' ? 'Derivation' : 'Problem');
    const problem = tag.attrs.problem || '';

    if (titleEl) titleEl.textContent = title;

    const notebookId = 'notebook-' + generateId().slice(0, 8);

    // Problem header (only for problem mode)
    const problemHeader = mode === 'problem' ? `
      <div class="board-problem-header">
        <div class="board-problem-label">Problem</div>
        <div class="board-problem-text">${renderMarkdownBasic(problem)}</div>
      </div>` : '';

    // Board layout: header, surface (steps), workspace (student input)
    content.innerHTML = `
      <div class="board" id="${notebookId}">
        <div class="board-header">
          <div class="board-header-left">
            <span class="board-badge">${escapeHtml(mode)}</span>
            <span class="board-title">${escapeHtml(title)}</span>
          </div>
        </div>
        ${problemHeader}
        <div class="board-surface" id="${notebookId}-steps">
        </div>
        <div class="board-workspace" id="${notebookId}-workspace">
          <div class="board-ws-label">\u270E Your workspace</div>
          <div class="board-ws-canvas-wrap">
            <canvas id="${notebookId}-draw-canvas"></canvas>
            <div class="board-ws-toolbar" id="${notebookId}-draw-toolbar"></div>
          </div>
          <div class="board-ws-text-row">
            <textarea class="board-ws-input" id="${notebookId}-type-input" placeholder="Type your work... use $...$ for math" rows="1"></textarea>
            <button class="board-ws-submit" id="${notebookId}-submit-btn">Submit</button>
          </div>
          <div class="board-ws-hint">Draw or type — both are sent to the tutor. Use $...$ for LaTeX math.</div>
          <div class="board-auto-send-indicator" id="${notebookId}-auto-send" style="display:none;"></div>
        </div>
      </div>
    `;
    panel.classList.add('stage-active');
    state.spotlightInfo = { type: 'notebook', mode, title, notebookId };
    state.notebookSteps = [];

    // Initialize interactive controls
    setTimeout(() => { initNotebookInteractive(notebookId, mode, problem ? title + ': ' + problem : title); }, 50);
  }

  state.spotlightActive = true;
  enterSpotlightFullscreen();

  // Append reference card in chat stream (skip on reopen to prevent duplicates)
  if (!options.skipReference) {
    const refTitle = (state.spotlightInfo && state.spotlightInfo.title) || type || 'Spotlight';
    appendSpotlightReference(type, refTitle, tag);
  }
}

// ── Notebook step appender (chalk-style — works for both derivation and problem modes) ──
const CIRCLED_NUMS = ['\u2460','\u2461','\u2462','\u2463','\u2464','\u2465','\u2466','\u2467','\u2468','\u2469'];

function appendNotebookStep(tag) {
  const info = state.spotlightInfo;
  if (!info || info.type !== 'notebook') {
    console.warn('[Notebook] No notebook open — ignoring step');
    return;
  }

  const stepsEl = $(`#${info.notebookId}-steps`);
  if (!stepsEl) return;

  const n = parseInt(tag.attrs.n || tag.attrs.step || (state.notebookSteps.length + 1));
  const annotation = tag.attrs.annotation || tag.attrs.label || '';
  const feedback = tag.attrs.feedback || '';
  const mathContent = (tag.content || '').trim();
  const isCorrection = tag.attrs.correction !== undefined;

  // Render math via KaTeX
  const renderedMath = renderLatex(mathContent);
  const circled = CIRCLED_NUMS[n - 1] || String(n);
  const stepType = isCorrection ? 'correction' : 'step';

  const stepEl = document.createElement('div');
  stepEl.className = `step fade-in${isCorrection ? ' correction' : ''}`;
  stepEl.dataset.stepN = n;
  const renderedAnnotation = renderLatex(escapeHtml(annotation));
  stepEl.innerHTML = `
    <div class="step-label"><span class="step-num">${circled}</span> ${renderedAnnotation}</div>
    <div class="step-math">${renderedMath}</div>
  `;
  stepsEl.appendChild(stepEl);

  // If there's inline feedback, render it as a .tutor-says element after the step
  if (feedback) {
    const feedbackEl = document.createElement('div');
    feedbackEl.className = 'tutor-says fade-in';
    feedbackEl.innerHTML = renderLatex(escapeHtml(feedback));
    stepsEl.appendChild(feedbackEl);
  }

  // Chalk-line separator
  const lineEl = document.createElement('div');
  lineEl.className = 'chalk-line';
  stepsEl.appendChild(lineEl);

  // Track step
  state.notebookSteps.push({ n, annotation, math: mathContent, author: 'tutor', type: stepType });
  if (feedback) {
    state.notebookSteps.push({ n: null, content: feedback, author: 'tutor', type: 'comment' });
  }

  // Scroll to newest step
  const surface = $(`#${info.notebookId}-steps`);
  if (surface) surface.scrollTop = surface.scrollHeight;
}

// ── Notebook comment appender (blue chalk — tutor hints/nudges/praise) ──
function appendNotebookComment(tag) {
  const info = state.spotlightInfo;
  if (!info || info.type !== 'notebook') {
    console.warn('[Notebook] No notebook open — ignoring comment');
    return;
  }

  const stepsEl = $(`#${info.notebookId}-steps`);
  if (!stepsEl) return;

  const text = (tag.content || '').trim();
  if (!text) return;

  // Render as blue chalk text (with LaTeX support)
  const commentEl = document.createElement('div');
  commentEl.className = 'tutor-says fade-in';
  commentEl.innerHTML = renderLatex(escapeHtml(text));
  stepsEl.appendChild(commentEl);

  // Chalk-line separator
  const lineEl = document.createElement('div');
  lineEl.className = 'chalk-line';
  stepsEl.appendChild(lineEl);

  // Track in state
  state.notebookSteps.push({ n: null, content: text, author: 'tutor', type: 'comment' });

  // Scroll to newest
  const surface = $(`#${info.notebookId}-steps`);
  if (surface) surface.scrollTop = surface.scrollHeight;
}

// ── Add student step to notebook (green chalk) ──
// aiImageUrl: preprocessed white-bg image for the AI (separate from display image)
function addStudentStepToNotebook(content, drawingDataUrl, aiImageUrl) {
  const info = state.spotlightInfo;
  if (!info || info.type !== 'notebook') return;

  const stepsEl = $(`#${info.notebookId}-steps`);
  if (!stepsEl) return;

  const lastNumbered = [...state.notebookSteps].reverse().find(s => s.n != null);
  const n = lastNumbered ? lastNumbered.n + 1 : state.notebookSteps.length + 1;

  const renderedContent = content ? renderLatex(content) : '';
  const circled = CIRCLED_NUMS[n - 1] || String(n);

  const stepEl = document.createElement('div');
  stepEl.className = 'step student fade-in';
  stepEl.dataset.stepN = n;

  let innerHtml = `<div class="step-label"><span class="step-num">${circled}</span> Your work</div>`;
  if (renderedContent) {
    innerHtml += `<div class="step-math">${renderedContent}</div>`;
  }
  if (drawingDataUrl) {
    innerHtml += `<div class="step-drawing"><img src="${drawingDataUrl}" alt="Your drawing" /></div>`;
  }

  stepEl.innerHTML = innerHtml;
  stepsEl.appendChild(stepEl);

  const lineEl = document.createElement('div');
  lineEl.className = 'chalk-line';
  stepsEl.appendChild(lineEl);

  state.notebookSteps.push({ n, content, hasDrawing: !!drawingDataUrl, author: 'student', type: 'step' });

  const surface = $(`#${info.notebookId}-steps`);
  if (surface) surface.scrollTop = surface.scrollHeight;

  // Build board state for context
  const boardState = state.notebookSteps.map(s => {
    if (s.type === 'comment') return `[Tutor comment] ${s.content}`;
    if (s.author === 'student') return `[Student step ${s.n}] ${s.content || ''}${s.hasDrawing ? ' [+drawing attached]' : ''}`;
    if (s.type === 'correction') return `[Tutor correction ${s.n}] ${s.annotation ? s.annotation + ': ' : ''}${s.math || s.content}`;
    return `[Tutor step ${s.n}] ${s.annotation ? s.annotation + ': ' : ''}${s.math || s.content}`;
  }).join('\n');

  // Find what the student was asked to write for vision context
  const lastTutorStep = [...state.notebookSteps].reverse().find(s => s.author === 'tutor' && s.type !== 'comment');
  const promptHint = lastTutorStep
    ? `The student was asked to work on: "${lastTutorStep.annotation || lastTutorStep.math || ''}"`
    : '';

  // Build message to AI
  // IMPORTANT: image goes FIRST to reduce context-anchoring bias.
  // If the text (with board state, expected answer) comes before the image,
  // the model "sees" what it expects rather than what the student actually drew.
  const msgParts = [];

  if (aiImageUrl || drawingDataUrl) {
    const imgSrc = aiImageUrl || drawingDataUrl;
    const base64 = imgSrc.split(',')[1];
    msgParts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: base64 } });
  }

  const textLines = [`[Notebook step ${n}] Student submitted work on the derivation notebook.`];
  if (content) textLines.push(`Student typed: "${content}"`);

  if (drawingDataUrl) {
    textLines.push('');
    textLines.push('IMPORTANT — The attached image above shows the student\'s handwritten mathematical work (preprocessed to dark strokes on white background for clarity).');
    textLines.push('FIRST: describe EXACTLY what symbols, characters, and equations you see in the image — report the raw visual content literally (e.g. "I see the characters 2, x, +, y") BEFORE interpreting what they might mean in the physics context.');
    textLines.push('Do NOT assume the student wrote the expected answer. Students often write wrong or unrelated things. Read the actual strokes.');
    if (!content) textLines.push('The student did not type anything — their full response is in the drawing.');
  }

  if (promptHint) {
    textLines.push('');
    textLines.push(promptHint);
  }
  textLines.push('', '[Current board state]', boardState);

  msgParts.push({ type: 'text', text: textLines.join('\n') });

  streamADK(msgParts);
}

// ── Notebook interactive initializer (unified workspace — canvas + text always visible) ──
function initNotebookInteractive(notebookId, mode, promptText) {
  // ── HiDPI Canvas setup ──
  const DPR = Math.min(window.devicePixelRatio || 1, 3);
  const CSS_W = 800;
  const MIN_CSS_H = 200;
  let cssH = MIN_CSS_H;
  let drawCtx = null;
  let drawing = false, currentColor = '#7ed99a', currentTool = 'pen', lineWidth = 5;
  let undoStack = [];
  let blankImageData = null;
  let needsExpand = false;

  const canvas = $(`#${notebookId}-draw-canvas`);
  const toolbar = $(`#${notebookId}-draw-toolbar`);

  function resizeCanvas(newCssH) {
    if (!canvas) return;
    // Save old pixels before resize clears them
    const oldW = canvas.width;
    const oldH = canvas.height;
    let oldData = null;
    if (drawCtx && oldW && oldH) {
      drawCtx.save();
      drawCtx.setTransform(1, 0, 0, 1, 0, 0);
      oldData = drawCtx.getImageData(0, 0, oldW, oldH);
      drawCtx.restore();
    }

    cssH = newCssH || cssH;
    canvas.width = CSS_W * DPR;
    canvas.height = cssH * DPR;
    canvas.style.width = '100%';
    canvas.style.height = cssH + 'px';
    drawCtx = canvas.getContext('2d');
    drawCtx.scale(DPR, DPR);

    // Fill entire canvas with dark background first
    drawCtx.fillStyle = '#1e2130';
    drawCtx.fillRect(0, 0, CSS_W, cssH);

    // Restore old drawing on top
    if (oldData) {
      drawCtx.save();
      drawCtx.setTransform(1, 0, 0, 1, 0, 0);
      drawCtx.putImageData(oldData, 0, 0);
      drawCtx.restore();
    }
  }

  if (canvas && toolbar) {
    resizeCanvas(MIN_CSS_H);
    clearDrawCanvas();

    toolbar.innerHTML = `
      <button class="board-ws-color active" data-tool="pen" data-color="#7ed99a" title="Green" style="background:#7ed99a;"></button>
      <button class="board-ws-color" data-tool="pen" data-color="#d4dbd4" title="White" style="background:#d4dbd4;"></button>
      <button class="board-ws-color" data-tool="pen" data-color="#7eb8da" title="Blue" style="background:#7eb8da;"></button>
      <button class="board-ws-color" data-tool="pen" data-color="#ff6b6b" title="Red" style="background:#ff6b6b;"></button>
      <div class="board-ws-sep"></div>
      <button class="board-ws-btn" data-tool="eraser" title="Eraser">&#9003;</button>
      <button class="board-ws-btn" data-action="undo" title="Undo">↩</button>
      <button class="board-ws-btn" data-action="clear" title="Clear">✕</button>
      <div class="board-ws-sep"></div>
      <button class="board-ws-btn" data-action="expand" title="Expand canvas">↕</button>
    `;

    toolbar.querySelectorAll('[data-tool], [data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.action;
        if (action === 'clear') { clearDrawCanvas(); return; }
        if (action === 'undo') { undoDraw(); return; }
        if (action === 'expand') { expandCanvas(); return; }
        const tool = btn.dataset.tool;
        if (tool) {
          currentTool = tool;
          if (tool === 'pen') currentColor = btn.dataset.color || '#7ed99a';
          toolbar.querySelectorAll('.board-ws-color').forEach(b => b.classList.remove('active'));
          if (tool === 'pen') btn.classList.add('active');
        }
      });
    });

    function getPos(e) {
      const rect = canvas.getBoundingClientRect();
      const touch = e.touches ? e.touches[0] : e;
      return {
        x: (touch.clientX - rect.left) * (CSS_W / rect.width),
        y: (touch.clientY - rect.top) * (cssH / rect.height)
      };
    }

    function startDraw(e) {
      e.preventDefault();
      drawing = true;
      drawCtx.save();
      drawCtx.setTransform(1, 0, 0, 1, 0, 0);
      undoStack.push(drawCtx.getImageData(0, 0, canvas.width, canvas.height));
      drawCtx.restore();
      if (undoStack.length > 20) undoStack.shift();
      const pos = getPos(e);
      drawCtx.beginPath();
      drawCtx.moveTo(pos.x, pos.y);
      resetInactivityTimer();
    }

    function draw(e) {
      if (!drawing) return;
      e.preventDefault();
      const pos = getPos(e);
      drawCtx.lineWidth = currentTool === 'eraser' ? lineWidth * 4 : lineWidth;
      drawCtx.strokeStyle = currentTool === 'eraser' ? '#1e2130' : currentColor;
      drawCtx.lineCap = 'round';
      drawCtx.lineJoin = 'round';
      drawCtx.lineTo(pos.x, pos.y);
      drawCtx.stroke();
      drawCtx.beginPath();
      drawCtx.moveTo(pos.x, pos.y);

      // Flag for expansion — don't resize mid-stroke (causes stray lines)
      if (pos.y > cssH - 30) {
        needsExpand = true;
      }
    }

    function stopDraw() {
      drawing = false;
      // Expand now that the stroke is done
      if (needsExpand) {
        needsExpand = false;
        expandCanvas();
      }
      resetInactivityTimer();
    }

    canvas.addEventListener('mousedown', startDraw);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDraw);
    canvas.addEventListener('mouseleave', stopDraw);
    canvas.addEventListener('touchstart', startDraw, { passive: false });
    canvas.addEventListener('touchmove', draw, { passive: false });
    canvas.addEventListener('touchend', stopDraw);
  }

  function expandCanvas() {
    const oldH = cssH;
    const newH = Math.min(cssH + 120, 600);
    if (newH === oldH) return;
    resizeCanvas(newH);
    // Draw grid only in the newly added area (old area preserved by putImageData)
    drawGrid(oldH);
  }

  function drawGrid(fromY) {
    if (!drawCtx) return;
    drawCtx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
    drawCtx.lineWidth = 1;
    const gridSpacing = 40;
    const startY = fromY ? Math.ceil(fromY / gridSpacing) * gridSpacing : gridSpacing;
    for (let y = startY; y < cssH; y += gridSpacing) {
      drawCtx.beginPath(); drawCtx.moveTo(0, y); drawCtx.lineTo(CSS_W, y); drawCtx.stroke();
    }
  }

  function clearDrawCanvas() {
    if (!canvas || !drawCtx) return;
    resizeCanvas(MIN_CSS_H);
    drawCtx.fillStyle = '#1e2130';
    drawCtx.fillRect(0, 0, CSS_W, cssH);
    drawGrid();
    drawCtx.save();
    drawCtx.setTransform(1, 0, 0, 1, 0, 0);
    blankImageData = drawCtx.getImageData(0, 0, canvas.width, canvas.height).data;
    drawCtx.restore();
    undoStack = [];
  }

  function undoDraw() {
    if (undoStack.length === 0 || !canvas || !drawCtx) return;
    drawCtx.save();
    drawCtx.setTransform(1, 0, 0, 1, 0, 0);
    drawCtx.putImageData(undoStack.pop(), 0, 0);
    drawCtx.restore();
  }

  function canvasHasContent() {
    if (!canvas || !drawCtx) return false;
    drawCtx.save();
    drawCtx.setTransform(1, 0, 0, 1, 0, 0);
    const currentData = drawCtx.getImageData(0, 0, canvas.width, canvas.height).data;
    drawCtx.restore();
    // Check for any pixel that differs from background (#1e2130)
    const BG_R = 30, BG_G = 33, BG_B = 48;
    for (let i = 0; i < currentData.length; i += 160) {
      const r = currentData[i], g = currentData[i + 1], b = currentData[i + 2];
      const dist = Math.abs(r - BG_R) + Math.abs(g - BG_G) + Math.abs(b - BG_B);
      if (dist > 60) return true;
    }
    return false;
  }

  // ── Preprocess canvas for AI: white background + dark strokes ──
  function processCanvasForAI() {
    if (!canvas) return null;
    const w = canvas.width, h = canvas.height;
    const offscreen = document.createElement('canvas');
    offscreen.width = w;
    offscreen.height = h;
    const ctx = offscreen.getContext('2d');

    const srcCtx = canvas.getContext('2d');
    const imgData = srcCtx.getImageData(0, 0, w, h);
    const data = imgData.data;

    // Background color of the canvas (#1e2130 ≈ 30,33,48)
    const BG_R = 30, BG_G = 33, BG_B = 48;

    // Crop to the actual content bounding box (skip empty space)
    let minY = h, maxY = 0, minX = w, maxX = 0;
    let hasContent = false;

    for (let py = 0; py < h; py++) {
      for (let px = 0; px < w; px++) {
        const i = (py * w + px) * 4;
        const r = data[i], g = data[i + 1], b = data[i + 2];
        const dist = Math.sqrt((r - BG_R) ** 2 + (g - BG_G) ** 2 + (b - BG_B) ** 2);
        if (dist > 50) {
          hasContent = true;
          if (py < minY) minY = py;
          if (py > maxY) maxY = py;
          if (px < minX) minX = px;
          if (px > maxX) maxX = px;
        }
      }
    }

    if (!hasContent) return null;

    // Add padding around the content
    const pad = Math.round(20 * DPR);
    minX = Math.max(0, minX - pad);
    minY = Math.max(0, minY - pad);
    maxX = Math.min(w - 1, maxX + pad);
    maxY = Math.min(h - 1, maxY + pad);
    const cropW = maxX - minX + 1;
    const cropH = maxY - minY + 1;

    // Create a tightly cropped output canvas
    const out = document.createElement('canvas');
    out.width = cropW;
    out.height = cropH;
    const outCtx = out.getContext('2d');
    outCtx.fillStyle = '#ffffff';
    outCtx.fillRect(0, 0, cropW, cropH);

    // Copy and remap pixels: background → white, strokes → dark
    const cropData = srcCtx.getImageData(minX, minY, cropW, cropH);
    const cd = cropData.data;

    for (let i = 0; i < cd.length; i += 4) {
      const r = cd[i], g = cd[i + 1], b = cd[i + 2];
      const dist = Math.sqrt((r - BG_R) ** 2 + (g - BG_G) ** 2 + (b - BG_B) ** 2);
      if (dist <= 50) {
        cd[i] = 255; cd[i + 1] = 255; cd[i + 2] = 255; cd[i + 3] = 255;
      } else {
        // Make strokes pure black for maximum contrast and clarity
        cd[i] = 0;
        cd[i + 1] = 0;
        cd[i + 2] = 0;
        cd[i + 3] = 255;
      }
    }

    outCtx.putImageData(cropData, 0, 0);
    return out.toDataURL('image/png');
  }

  // ── Type input: auto-resize textarea ──
  const typeInput = $(`#${notebookId}-type-input`);
  if (typeInput) {
    typeInput.addEventListener('input', () => {
      typeInput.style.height = 'auto';
      typeInput.style.height = Math.min(typeInput.scrollHeight, 160) + 'px';
      resetInactivityTimer();
    });
    typeInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitNotebookWork();
      }
    });
  }

  // ── Submit work (always collects BOTH canvas + text) ──
  function submitNotebookWork() {
    if (state.isStreaming) return;
    clearInactivityTimer();

    let textContent = '';
    let drawingDataUrl = null;
    let aiImageUrl = null;

    if (canvasHasContent()) {
      drawingDataUrl = canvas.toDataURL('image/png');
      aiImageUrl = processCanvasForAI();
      console.log('[Notebook] Canvas captured — display:', drawingDataUrl?.length, 'bytes, AI:', aiImageUrl?.length, 'bytes');
      clearDrawCanvas();
    }

    const input = $(`#${notebookId}-type-input`);
    if (input && input.value.trim()) {
      textContent = input.value.trim();
      input.value = '';
      input.style.height = 'auto';
    }

    if (!textContent && !drawingDataUrl) return;

    addStudentStepToNotebook(textContent, drawingDataUrl, aiImageUrl);
  }

  // ── Inactivity auto-send ──
  function resetInactivityTimer() {
    clearInactivityTimer();
    state.inactivityTimer = setTimeout(() => {
      if (state.isStreaming) {
        state.inactivityTimer = setTimeout(() => resetInactivityTimer(), 2000);
        return;
      }
      const hasContent = canvasHasContent() || (typeInput && typeInput.value.trim());
      if (hasContent) {
        autoSendNotebookWork();
      }
    }, 15000);
  }

  function clearInactivityTimer() {
    if (state.inactivityTimer) {
      clearTimeout(state.inactivityTimer);
      state.inactivityTimer = null;
    }
  }

  function autoSendNotebookWork() {
    const indicator = $(`#${notebookId}-auto-send`);
    if (indicator) {
      indicator.style.display = '';
      indicator.textContent = 'Sending your work...';
      indicator.className = 'board-auto-send-indicator sending';
    }
    submitNotebookWork();
    if (indicator) {
      setTimeout(() => {
        indicator.textContent = 'Sent!';
        indicator.className = 'board-auto-send-indicator sent';
        setTimeout(() => { indicator.style.display = 'none'; }, 2000);
      }, 500);
    }
  }

  state.notebookCleanup = () => { clearInactivityTimer(); };

  const submitBtn = $(`#${notebookId}-submit-btn`);
  if (submitBtn) {
    submitBtn.addEventListener('click', submitNotebookWork);
  }
}

// ── Spotlight reference cards (clickable history in chat stream) ──
function appendSpotlightReference(type, title, reopenTag) {
  const refId = 'spot-ref-' + generateId().slice(0, 8);
  const typeIcons = { video: '▶', simulation: '⚗', notebook: '📓', image: '🖼', 'board-draw': '✎' };
  const icon = typeIcons[type] || '◆';

  state.spotlightHistory.push({ id: refId, type, title, tag: reopenTag });

  appendBlock('spotlight-ref', `
    <div class="spotlight-ref-card" data-type="${escapeAttr(type)}" onclick="reopenSpotlight('${refId}')">
      <span class="spotlight-ref-icon">${icon}</span>
      <span class="spotlight-ref-title">${escapeHtml(title)}</span>
      <span class="spotlight-ref-hint">Click to reopen</span>
    </div>
  `);
}

window.reopenSpotlight = function(refId) {
  const entry = state.spotlightHistory.find(e => e.id === refId);
  if (!entry) return;

  if (entry.type === 'video' && entry.tag.lessonId !== undefined) {
    openVideoInSpotlight(entry.tag.lessonId, entry.tag.start, entry.tag.end, entry.tag.label, { skipReference: true });
  } else {
    showSpotlight(entry.tag, { skipReference: true });
  }
};

// ── Spotlight fullscreen helpers ──
function enterSpotlightFullscreen() {
  const mainLayout = $('#main-layout');
  if (!mainLayout) return;
  mainLayout.classList.add('notebook-fullscreen');
  const fsBtn = $('#spotlight-fullscreen');
  if (fsBtn) fsBtn.textContent = '⛶';
}

function exitSpotlightFullscreen() {
  const mainLayout = $('#main-layout');
  if (!mainLayout) return;
  mainLayout.classList.remove('notebook-fullscreen');
  const fsBtn = $('#spotlight-fullscreen');
  if (fsBtn) fsBtn.textContent = '⛶';
}

// ── Spotlight fullscreen toggle (side-by-side: spotlight left, chat right) ──
window.toggleNotebookFullscreen = function() {
  const mainLayout = $('#main-layout');
  if (!mainLayout) return;
  if (mainLayout.classList.contains('notebook-fullscreen')) {
    exitSpotlightFullscreen();
  } else {
    enterSpotlightFullscreen();
  }
};

window.hideSpotlight = function(options = {}) {
  const wasVideo = state.spotlightInfo?.type === 'video';
  const wasBoardDraw = state.spotlightInfo?.type === 'board-draw';
  const prevTitle = state.spotlightInfo?.title || '';

  const panel = $('#spotlight-panel');
  if (panel) panel.classList.remove('stage-active');

  const content = $('#spotlight-content');
  if (content) content.innerHTML = '';

  const typeBadge = $('#spotlight-type-badge');
  if (typeBadge) {
    typeBadge.textContent = '';
    typeBadge.style.display = 'none';
  }

  exitSpotlightFullscreen();

  if (state.spotlightActive && state.activeSimulation) {
    stopSimBridge();
    state.activeSimulation = null;
    state.simulationLiveState = null;
  }

  if (state.spotlightInfo?.type === 'notebook') {
    if (state.notebookCleanup) { state.notebookCleanup(); state.notebookCleanup = null; }
    state.notebookSteps = [];
  }

  if (wasBoardDraw) bdCleanup();

  state.spotlightActive = false;
  state.spotlightInfo = null;

  // Auto-trigger agent when student closes video or board-draw
  if (!options.agentInitiated && !state.isStreaming) {
    if (wasVideo) {
      setTimeout(() => {
        if (!state.isStreaming) streamADK('[I\'m done watching "' + prevTitle + '"]');
      }, 400);
    } else if (wasBoardDraw) {
      setTimeout(() => {
        if (!state.isStreaming) streamADK('[I\'ve seen the board drawing "' + prevTitle + '"]');
      }, 400);
    }
  }
};

// ═══════════════════════════════════════════════════════════
// Module 18: User Actions & Handlers
// ═══════════════════════════════════════════════════════════

function sendStudentResponse(text) {
  if (state.isStreaming) return;
  streamADK(text);
}

// sendCanvasDrawing removed — canvas drawing now handled via notebook workspace

window.submitFreetext = function(inputId) {
  const el = $(`#${inputId}`);
  if (!el) return;
  const val = el.value.trim();
  if (!val) return;
  sendStudentResponse(val);
};

window.submitFillBlank = function(fbId, count) {
  const answers = [];
  for (let i = 1; i <= 10; i++) {
    const el = $(`#${fbId}-${i}`);
    if (el) answers.push(`blank${i}: ${el.value}`);
  }
  if (answers.length === 0) return;
  sendStudentResponse(`[Fill-in-blank] ${answers.join(', ')}`);
};

window.handleContinue = function() {
  if (state.isStreaming) return;
  streamADK('Continue to the next step.');
};

window.handleDoneWatching = function() {
  if (state.isStreaming) return;
  sendStudentResponse('Done watching the video segment.');
};

window.handleRetry = function() {
  if (state.isStreaming) return;
  const lastUserMsg = [...state.messages].reverse().find(m => m.role === 'user');
  if (lastUserMsg) {
    state.messages.pop();
    streamADK(lastUserMsg.content);
  }
};

window.handleBreak = function() {
  SessionManager.archiveSession();
  appendBlock('system', `
    <div class="ai-message" style="text-align:center;padding:20px;">
      Session paused. Your progress has been saved. Refresh to continue.
    </div>
  `);
};

window.handleLost = function() {
  if (state.isStreaming) return;
  const stepInfo = state.planActiveStep ? ` on step ${state.planActiveStep} of the plan` : '';
  sendStudentResponse(`[I'm lost${stepInfo}] I don't understand. Can you explain this differently?`);
};

// ═══════════════════════════════════════════════════════════
// Module 19: Timer & Stats
// ═══════════════════════════════════════════════════════════

let timerInterval = null;

function startTimer() {
  state.sessionStartTime = Date.now();
  timerInterval = setInterval(updateTimer, 1000);
  updateTimer();
}

function updateTimer() {
  if (!state.sessionStartTime) return;
  const elapsed = Math.floor((Date.now() - state.sessionStartTime) / 1000);
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  const timeStr = `${min}:${sec.toString().padStart(2, '0')}`;
  const timerEl = $('#session-timer');
  const statEl = $('#stat-time');
  if (timerEl) timerEl.textContent = timeStr;
  if (statEl) statEl.textContent = timeStr;
}

function updateStats() {
  const el = $('#stat-responses');
  if (el) el.textContent = `${state.responses} responses`;
}

// ═══════════════════════════════════════════════════════════
// Module 20: Utilities
// ═══════════════════════════════════════════════════════════

// ── External resource URL validation ──
// Only allow URLs from trusted sources. The search_images tool returns
// Wikimedia thumbnail URLs (containing /thumb/). Direct Wikimedia file
// URLs are almost always hallucinated by the model.
function validateExternalUrl(url) {
  if (!url || typeof url !== 'string') return { valid: false, reason: 'Empty URL' };

  // Block dangerous schemes
  const lower = url.trim().toLowerCase();
  if (lower.startsWith('javascript:') || lower.startsWith('data:') || lower.startsWith('blob:')) {
    return { valid: false, reason: 'Blocked URL scheme' };
  }

  // Must be http(s)
  if (!lower.startsWith('http://') && !lower.startsWith('https://')) {
    return { valid: false, reason: 'Invalid URL scheme' };
  }

  try {
    const parsed = new URL(url);

    // Wikimedia/Wikipedia: only allow thumbnail URLs (from the search_images API tool)
    // Thumbnail URLs contain /thumb/ and have a width-prefixed filename at the end
    // Direct file URLs (e.g. /commons/3/3e/File.gif) are likely hallucinated
    if (parsed.hostname.includes('wikimedia.org') || parsed.hostname.includes('wikipedia.org')) {
      if (!parsed.pathname.includes('/thumb/')) {
        return { valid: false, reason: 'Unverified image source — use search_images tool for Wikimedia content' };
      }
    }

    return { valid: true };
  } catch {
    return { valid: false, reason: 'Malformed URL' };
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function renderLatex(text) {
  if (typeof katex === 'undefined') return text;
  // Display math: $$...$$ (must come before inline to avoid partial matches)
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: true, throwOnError: false });
    } catch { return `$$${math}$$`; }
  });
  // Inline math: $...$  (but not \$ escaped dollars)
  text = text.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: false, throwOnError: false });
    } catch { return `$${math}$`; }
  });
  return text;
}

function renderMarkdownBasic(text) {
  // Process LaTeX before markdown to protect math from markdown transforms
  text = renderLatex(text);
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code style="background:var(--bg-elevated);padding:1px 4px;border-radius:3px;font-family:var(--font-mono);font-size:13px;">$1</code>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

// ═══════════════════════════════════════════════════════════
// Module 21: Setup Panel & Boot
// ═══════════════════════════════════════════════════════════

function setStatus(text, type = '') {
  const el = $('#setup-status');
  if (!el) return;
  el.textContent = text;
  el.className = 'setup-status' + (type ? ` ${type}` : '');
}

// ─── Session List Helpers ─────────────────────────────────

let sessionFetchDebounce = null;

async function fetchAndRenderSessions(name, courseId) {
  const listPanel = $('#session-list-panel');
  const firstTime = $('#session-first-time');
  if (!listPanel || !firstTime) return;

  if (!courseId) {
    listPanel.classList.add('hidden');
    firstTime.classList.add('hidden');
    return;
  }

  setStatus('Loading sessions...');

  try {
    let url;
    const fetchOpts = {};
    if (AuthManager.isLoggedIn()) {
      url = `${state.apiUrl}/api/v1/sessions/me/${courseId}/with-headlines`;
      fetchOpts.headers = AuthManager.authHeaders();
    } else {
      url = `${state.apiUrl}/api/v1/sessions/student/${courseId}/${encodeURIComponent(name)}/with-headlines`;
    }
    const res = await fetch(url, fetchOpts);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const sessions = await res.json();

    setStatus('');

    if (sessions.length === 0) {
      listPanel.classList.add('hidden');
      firstTime.classList.remove('hidden');
      return;
    }

    firstTime.classList.add('hidden');
    listPanel.classList.remove('hidden');

    const active = sessions.filter(s => s.status === 'active');
    const completed = sessions.filter(s => s.status === 'complete');
    renderSessionCards(active, completed);
  } catch (e) {
    console.warn('Failed to fetch sessions:', e);
    setStatus('');
    // Fall back to first-time view
    listPanel.classList.add('hidden');
    firstTime.classList.remove('hidden');
  }
}

function renderSessionCards(active, completed) {
  const activeContainer = $('#session-list-active');
  const completedContainer = $('#session-list-completed');
  if (!activeContainer || !completedContainer) return;

  let activeHtml = '';
  if (active.length > 0) {
    activeHtml += '<div class="session-list-label">Active</div>';
    for (const s of active) {
      const headline = escapeHtml(s.headline || `Session ${s.number || '?'}`);
      const desc = s.headlineDescription ? `<div class="session-card-desc">${escapeHtml(s.headlineDescription)}</div>` : '';
      const date = s.startedAt ? new Date(s.startedAt).toLocaleDateString() : '';
      const dur = s.durationSec ? `${Math.round(s.durationSec / 60)}m` : '';
      const sections = (s.metrics?.sectionsCompleted || 0) + '/' + (s.metrics?.sectionsTotal || 0) + ' sections';
      activeHtml += `
        <div class="session-card active" onclick="continueSession('${escapeAttr(s.sessionId)}')">
          <div class="session-card-top">
            <span class="session-card-headline">${headline}</span>
            <span class="session-card-badge active">Active</span>
          </div>
          ${desc}
          <div class="session-card-meta">
            <span>#${s.number || '?'}</span>
            ${date ? `<span>${date}</span>` : ''}
            ${dur ? `<span>${dur}</span>` : ''}
            <span>${sections}</span>
          </div>
          <div class="session-card-actions">
            <button class="btn btn-primary">Continue</button>
          </div>
        </div>
      `;
    }
  }
  activeContainer.innerHTML = activeHtml;

  let completedHtml = '';
  if (completed.length > 0) {
    completedHtml += '<div class="session-list-label">History</div>';
    for (const s of completed) {
      const headline = escapeHtml(s.headline || `Session ${s.number || '?'}`);
      const desc = s.headlineDescription ? `<div class="session-card-desc">${escapeHtml(s.headlineDescription)}</div>` : '';
      const date = s.startedAt ? new Date(s.startedAt).toLocaleDateString() : '';
      const dur = s.durationSec ? `${Math.round(s.durationSec / 60)}m` : '';
      const sections = (s.metrics?.sectionsCompleted || 0) + '/' + (s.metrics?.sectionsTotal || 0) + ' sections';
      completedHtml += `
        <div class="session-card completed">
          <div class="session-card-top">
            <span class="session-card-headline">${headline}</span>
            <span class="session-card-badge complete">Complete</span>
          </div>
          ${desc}
          <div class="session-card-meta">
            <span>#${s.number || '?'}</span>
            ${date ? `<span>${date}</span>` : ''}
            ${dur ? `<span>${dur}</span>` : ''}
            <span>${sections}</span>
          </div>
        </div>
      `;
    }
  }
  completedContainer.innerHTML = completedHtml;
}

function deriveCheckpointFromSession(session) {
  const pos = session.coursePosition || {};
  const current = pos.current || {};
  return {
    currentLessonId: current.lessonId || null,
    currentSectionIndex: current.sectionIndex ?? 0,
    completedSections: [...(pos.completedCourseSections || [])],
    lastVideoTimestamp: 0,
    sessionCount: session.number || 1,
    lastPlanJSON: null,
  };
}

// ─── Init & Session Lifecycle ─────────────────────────────

function showLoginPanel() {
  $('#login-panel').style.display = 'flex';
  $('#setup-panel').style.display = 'none';
}

function showSetupPanel() {
  const user = AuthManager.getUser();
  if (!user) return showLoginPanel();

  state.studentName = user.name;
  state.userEmail = user.email;

  const greeting = $('#setup-greeting');
  if (greeting) greeting.textContent = `Welcome, ${user.name}`;

  $('#login-panel').style.display = 'none';
  $('#setup-panel').style.display = 'flex';
}

function handleAuthExpired() {
  AuthManager.clearAuth();
  showLoginPanel();
  const el = $('#login-status');
  if (el) {
    el.textContent = 'Session expired. Please sign in again.';
    el.className = 'setup-status error';
  }
}

function initLoginForm() {
  const emailInput = $('#login-email');
  const passwordInput = $('#login-password');
  const loginBtn = $('#btn-login');
  const statusEl = $('#login-status');

  async function doLogin() {
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) {
      statusEl.textContent = 'Please enter email and password.';
      statusEl.className = 'setup-status error';
      return;
    }
    loginBtn.disabled = true;
    statusEl.textContent = 'Signing in...';
    statusEl.className = 'setup-status';
    try {
      await AuthManager.login(email, password);
      statusEl.textContent = '';
      showSetupPanel();
      // Trigger session fetch for pre-selected course
      const courseId = parseInt($('#course-id')?.value);
      if (courseId) fetchAndRenderSessions(state.studentName, courseId);
    } catch (e) {
      statusEl.textContent = e.message || 'Login failed';
      statusEl.className = 'setup-status error';
    } finally {
      loginBtn.disabled = false;
    }
  }

  loginBtn.addEventListener('click', doLogin);
  passwordInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });
  emailInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') passwordInput.focus(); });
}

async function initSetup() {
  const courseIdInput = $('#course-id');
  const apiUrlInput = $('#api-url');
  const startBtn = $('#btn-start-session');
  const newBtn = $('#btn-new-session');

  state.apiUrl = apiUrlInput?.value?.trim() || 'http://localhost:3001';

  // ─── Login form ────────────────────────────────────────
  initLoginForm();

  // ─── Logout ────────────────────────────────────────────
  $('#btn-logout')?.addEventListener('click', () => {
    AuthManager.logout();
    state.studentName = '';
    state.userEmail = '';
    $('#session-list-panel')?.classList.add('hidden');
    $('#session-first-time')?.classList.add('hidden');
    showLoginPanel();
  });

  // ─── Auth gate ─────────────────────────────────────────
  if (AuthManager.isLoggedIn()) {
    showSetupPanel();
  } else {
    showLoginPanel();
  }

  // ─── Course change → fetch sessions ────────────────────
  function onCourseChange() {
    const courseId = parseInt(courseIdInput.value);

    if (startBtn) startBtn.disabled = !courseId;
    if (newBtn) newBtn.disabled = !courseId;

    if (sessionFetchDebounce) clearTimeout(sessionFetchDebounce);
    if (courseId && state.studentName) {
      sessionFetchDebounce = setTimeout(() => {
        fetchAndRenderSessions(state.studentName, courseId);
      }, 500);
    } else {
      $('#session-list-panel')?.classList.add('hidden');
      $('#session-first-time')?.classList.add('hidden');
    }
  }

  courseIdInput.addEventListener('change', onCourseChange);

  // First-time "Start Session"
  if (startBtn) startBtn.addEventListener('click', () => {
    const intentInput = $('#student-intent-first');
    startNewSession(state.studentName, parseInt(courseIdInput.value), (intentInput?.value || '').trim());
  });

  // Returning "New Session"
  if (newBtn) newBtn.addEventListener('click', () => {
    const intentInput = $('#student-intent');
    startNewSession(state.studentName, parseInt(courseIdInput.value), (intentInput?.value || '').trim());
  });

  $('#btn-back')?.addEventListener('click', () => {
    $('#teaching-layout').classList.add('hidden');
    $('#setup-panel').style.display = 'flex';
    if (timerInterval) clearInterval(timerInterval);
    disconnectAgentEvents();
  });

  // Sidebar toggle
  $('#btn-toggle-sidebar')?.addEventListener('click', () => {
    const sidebar = $('#knowledge-sidebar');
    if (sidebar) sidebar.classList.toggle('collapsed');
  });

  // Course outline toggle
  $('#btn-toggle-course-outline')?.addEventListener('click', () => {
    const list = $('#course-progress-list');
    const icon = document.querySelector('#btn-toggle-course-outline .toggle-icon');
    if (list) {
      list.classList.toggle('collapsed');
      if (icon) icon.innerHTML = list.classList.contains('collapsed') ? '&#9656;' : '&#9662;';
    }
  });

  // Overlay close handlers
  $('#lost-close')?.addEventListener('click', () => {
    $('#lost-overlay').classList.add('hidden');
  });
  $('#lost-got-it')?.addEventListener('click', () => {
    $('#lost-overlay').classList.add('hidden');
  });

  // Simulation fullscreen close
  $('#sim-fullscreen-close')?.addEventListener('click', closeSimFullscreen);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSimFullscreen();
  });

  // Trigger initial check (course may be pre-selected)
  if (AuthManager.isLoggedIn()) {
    onCourseChange();
  }
}

async function startNewSession(name, courseId, intent) {
  if (!name || !courseId) return;

  state.studentName = name;
  state.studentIntent = intent;
  state.courseId = courseId;

  setStatus('Loading course...');

  try {
    const courseMap = await loadCourseMap(state.courseId);
    await Promise.all([
      fetchSimulations(state.courseId),
      fetchConcepts(state.courseId),
    ]);

    // Fetch previous sessions — find the one with most actual progress
    const prevSessions = await SessionManager.loadPreviousSessions(state.courseId, state.studentName) || [];

    // Pick the session with the most completed sections (not just newest)
    const bestSession = prevSessions.reduce((best, s) => {
      const completed = (s.coursePosition?.completedCourseSections || []).length;
      const bestCompleted = (best?.coursePosition?.completedCourseSections || []).length;
      return completed > bestCompleted ? s : best;
    }, null);

    const highestNumber = prevSessions.length > 0
      ? Math.max(...prevSessions.map(s => s.number || 0))
      : 0;

    if (bestSession && bestSession.coursePosition &&
        (bestSession.coursePosition.completedCourseSections || []).length > 0) {
      const cp = deriveCheckpointFromSession(bestSession);
      cp.sessionCount = highestNumber + 1;
      state.checkpoint = cp;
    } else {
      const firstLesson = courseMap.modules[0]?.lessons[0];
      state.checkpoint = {
        currentLessonId: firstLesson?.lesson_id || null,
        currentSectionIndex: 0,
        completedSections: [],
        lastVideoTimestamp: 0,
        sessionCount: highestNumber + 1,
        lastPlanJSON: null,
      };
    }

    showTeachingLayout(courseMap);

    // Generate session ID and create in MongoDB
    state.messages = [];
    state.sessionId = generateId();
    state.currentScript = null;

    // Connect persistent SSE for agent events
    connectAgentEvents();

    try {
      const coursePosition = {
        lessonId: state.checkpoint.currentLessonId,
        sectionIndex: state.checkpoint.currentSectionIndex,
        completedCourseSections: [...state.checkpoint.completedSections],
      };
      await SessionManager.createSession(
        state.courseId, state.studentName, state.studentIntent,
        coursePosition, state.checkpoint.sessionCount,
      );
      // Attach previous session summaries for AI context
      if (prevSessions.length > 0) {
        SessionManager.session.previousSessions = prevSessions
          .filter(s => s.status === 'complete')
          .slice(0, 5)
          .map(ps => ({
            sessionId: ps.sessionId,
            number: ps.number || 0,
            date: ps.startedAt,
            objective: (ps.plan && ps.plan.sessionObjective) || '',
            scenario: (ps.intent && ps.intent.scenario) || 'course',
            sectionsCompleted: (ps.metrics && ps.metrics.sectionsCompleted) || 0,
            summary: (ps.summaries && ps.summaries.sessionSummary) || '',
          }));
      }
    } catch (e) {
      console.warn('Session creation failed (non-blocking):', e);
    }

    const hasProgress = state.checkpoint.completedSections.length > 0;
    const completed = state.checkpoint.completedSections.length;

    let trigger;
    if (state.studentIntent) {
      // Student provided specific intent — skip probing, go straight to planning
      const progressNote = hasProgress
        ? ` They have completed ${completed} sections so far (session ${state.checkpoint.sessionCount}).`
        : '';
      trigger = `[SYSTEM] Student "${state.studentName}" has joined.${progressNote} The student pre-stated their intent: "${state.studentIntent}". IMPORTANT: The student has already told you what they want. Do NOT ask diagnostic or probing questions — skip the probing phase entirely. Greet them with ONE short sentence acknowledging their goal, then IMMEDIATELY call spawn_agent("planning", ...) with their stated intent as the starting point, and give them a warm-up assessment in the same message. The student's intent IS your probe result.`;
    } else if (hasProgress) {
      trigger = `[SYSTEM] The student "${state.studentName}" is returning for session ${state.checkpoint.sessionCount}. They have completed ${completed} sections. Current position: lesson ${state.checkpoint.currentLessonId}, section ${state.checkpoint.currentSectionIndex}. Welcome them back briefly, state where you're picking up, and continue teaching following the current script. Do NOT ask what they want to do — you are the teacher, take charge.`;
    } else {
      trigger = `[SYSTEM] New student "${state.studentName}" has joined for their first session. Greet them with one warm sentence, state the objective, and start teaching immediately following the current script. Do NOT ask what they want to learn — you are the teacher, take charge.`;
    }

    await streamADK(trigger, true, true);
  } catch (err) {
    setStatus(`Failed: ${err.message}`, 'error');
  }
}

window.continueSession = async function(sessionId) {
  setStatus('Resuming session...');

  try {
    // Fetch the full session
    const res = await fetch(`${state.apiUrl}/api/v1/sessions/${sessionId}`, {
      headers: { ...AuthManager.authHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const sessionData = await res.json();

    state.studentName = sessionData.studentName;
    state.courseId = sessionData.courseId;
    state.sessionId = sessionData.sessionId;
    state.studentIntent = (sessionData.intent && sessionData.intent.raw) || '';

    // Connect persistent SSE for agent events
    connectAgentEvents();

    const courseMap = await loadCourseMap(state.courseId);
    await Promise.all([
      fetchSimulations(state.courseId),
      fetchConcepts(state.courseId),
    ]);

    // Derive checkpoint from session's course position
    state.checkpoint = deriveCheckpointFromSession(sessionData);

    showTeachingLayout(courseMap);

    // Resume the SessionManager
    SessionManager.resumeSession(sessionData);

    // Restore generated visuals (HTML blobs from visual_gen)
    state.generatedVisuals = sessionData.generatedVisuals || {};

    // Restore spotlight history (reference cards)
    state.spotlightHistory = sessionData.spotlightHistory || [];

    // Restore notebook steps (derivation context)
    state.notebookSteps = sessionData.notebookSteps || [];

    // Restore plan from session data
    if (sessionData.plan && sessionData.plan.raw) {
      const rawPlan = sessionData.plan.raw;
      state.plan = (rawPlan.sections || rawPlan.steps || []).map((sec, i) => ({
        n: i + 1,
        title: sec.title || sec.student_label || `Section ${i + 1}`,
        modality: sec.modality || sec.type || '',
        covers: sec.covers || sec.concept || '',
        learningOutcome: sec.learning_outcome || sec.objective || '',
        activity: sec.activity || sec.do || '',
        studentLabel: sec.title || '',
        description: sec.activity || sec.covers || '',
        status: 'pending',
        performance: null,
      }));

      // Mark sections as done/active based on session sections
      const sessionSections = sessionData.sections || [];
      for (const ss of sessionSections) {
        const planStep = state.plan[ss.index];
        if (planStep) {
          if (ss.status === 'done') planStep.status = 'done';
          else if (ss.status === 'active') planStep.status = 'active';
        }
      }

      const active = state.plan.find(s => s.status === 'active');
      state.planActiveStep = active ? active.n : null;

      const objEl = $('#plan-objective');
      if (objEl && sessionData.plan.sessionObjective) {
        objEl.innerHTML = `<div class="plan-objective-text">${escapeHtml(sessionData.plan.sessionObjective)}</div>`;
      }

      renderPlanProgress();
    }

    // Rebuild historical canvas content from transcript
    if (sessionData.transcript && sessionData.transcript.length > 0) {
      rebuildCanvasFromTranscript(sessionData.transcript);
    }

    // Populate messages from transcript (gives AI full context)
    state.messages = (sessionData.transcript || []).map(m => ({
      role: m.role,
      content: m.content,
    }));

    // Restore conversation start time offset
    if (sessionData.durationSec) {
      state.sessionStartTime = Date.now() - (sessionData.durationSec * 1000);
    }

    const completed = state.checkpoint.completedSections.length;
    const intentClause = state.studentIntent
      ? ` The student said: "${state.studentIntent}".`
      : '';

    const trigger = `[SYSTEM] The student "${state.studentName}" is returning to continue session ${state.checkpoint.sessionCount}. They have completed ${completed} sections. Current position: lesson ${state.checkpoint.currentLessonId}, section ${state.checkpoint.currentSectionIndex}.${intentClause} Welcome them back briefly, state where you're picking up, and continue teaching following the current script. Do NOT ask what they want to do — you are the teacher, take charge.`;

    await streamADK(trigger, true, true);
  } catch (err) {
    setStatus(`Failed to resume: ${err.message}`, 'error');
  }
};

// ── Canvas Rebuild (Session Resume) ──────────────────────────────

function rebuildCanvasFromTranscript(transcript) {
  const stream = document.getElementById('canvas-stream');
  // Keep the welcome header that showTeachingLayout already added

  for (const msg of transcript) {
    if (msg.role === 'assistant') {
      renderHistoricalTutorMessage(msg.content);
    } else if (msg.role === 'user') {
      // Skip system triggers (internal messages)
      const c = msg.content || '';
      if (c.startsWith('[SYSTEM]') || c.startsWith('[') || c.startsWith('The student')) {
        continue;
      }
      renderHistoricalStudentMessage(c);
    }
  }

  // Scroll to bottom
  stream.scrollTop = stream.scrollHeight;
}

function renderHistoricalTutorMessage(text) {
  if (!text) return;

  // Strip backend artifacts
  const cleanedText = text.replace(/\[TOOL_STEPS:[^\]]*\]/g, '');
  const segments = parseTeachingTags(cleanedText);

  for (const seg of segments) {
    if (seg.type === 'text') {
      const parts = splitTextAtHeadings(seg.content);
      for (const part of parts) {
        if (part.type === 'heading') {
          insertTopicHeading(part.text, null, part.level === 2 ? 'topic' : 'sub');
        } else if (part.content.trim()) {
          appendBoardText(part.content);
        }
      }
    } else if (seg.type === 'tag') {
      renderHistoricalTag(seg.tag);
    }
  }
}

function renderHistoricalTag(tag) {
  // For historical rendering, we render tags but mark interactive ones as resolved
  const interactiveTags = new Set([
    'teaching-mcq', 'teaching-freetext', 'teaching-agree-disagree',
    'teaching-fillblank', 'teaching-spot-error', 'teaching-confidence',
    'teaching-canvas', 'teaching-teachback'
  ]);

  // Skip tags that don't render well in history
  const skipTags = new Set([
    'teaching-plan', 'teaching-plan-update', 'teaching-checkpoint',
    'teaching-spotlight-dismiss', 'teaching-notebook-step', 'teaching-notebook-comment'
  ]);

  if (skipTags.has(tag.name)) return;

  // Render the tag using normal renderer
  renderTeachingTag(tag);

  // Mark interactive blocks as resolved so they can't be interacted with
  if (interactiveTags.has(tag.name)) {
    // Find the most recently added interactive block and resolve it
    const blocks = document.querySelectorAll('.canvas-block[data-interactive="true"]:not([data-resolved])');
    const lastBlock = blocks[blocks.length - 1];
    if (lastBlock) {
      lastBlock.dataset.resolved = 'true';
      lastBlock.classList.add('resolved');
      lastBlock.querySelectorAll('button, input, textarea, select').forEach(el => {
        el.disabled = true;
      });
    }
  }
}

function renderHistoricalStudentMessage(text) {
  if (!text || !text.trim()) return;
  const stream = document.getElementById('canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block board-response fade-in';
  block.dataset.type = 'user';
  block.dataset.resolved = 'true';
  block.innerHTML = `<span class="response-label">You</span> <span class="response-text">${escapeHtml(text)}</span>`;
  stream.appendChild(block);
}

function showTeachingLayout(courseMap) {
  $('#course-title').textContent = courseMap.title;
  $('#sidebar-section-label').textContent = 'COURSE PROGRESS';
  $('#sidebar-status').textContent = `${state.studentName} - Session ${state.checkpoint.sessionCount}`;
  $('#stat-session').textContent = `Session ${state.checkpoint.sessionCount}`;

  $('#setup-panel').style.display = 'none';
  $('#teaching-layout').classList.remove('hidden');

  renderCourseProgress();
  startTimer();

  const stream = $('#canvas-stream');
  stream.innerHTML = '';
  appendBlock('system', `
    <h2 style="font-size:18px;font-weight:700;margin-bottom:8px;">${escapeHtml(courseMap.title)}</h2>
    <div style="font-size:14px;color:var(--text-muted);line-height:1.7;">
      Starting teaching session for ${escapeHtml(state.studentName)}...
    </div>
  `);
}

// ═══════════════════════════════════════════════════════════
// Module 21: Board Draw — Live Tutor Drawing Engine
// ═══════════════════════════════════════════════════════════

const BD_COLORS = {
  white: '#e8e8e0', yellow: '#f5d97a', green: '#7ed99a',
  blue: '#7eb8da', red: '#ff6b6b', cyan: '#53d8fb',
  dim: 'rgba(255,255,255,0.15)',
};
const BD_VIRTUAL_W = 800;
const BD_INITIAL_H = 500;

function bdInit(canvasEl, voiceEl) {
  const bd = state.boardDraw;
  bd.canvas = canvasEl;
  bd.ctx = canvasEl.getContext('2d');
  bd.voiceEl = voiceEl;
  bd.cancelFlag = false;
  bd.currentH = BD_INITIAL_H;
  bd.DPR = Math.min(window.devicePixelRatio || 1, 3);
  bdResizeCanvas();
  bdDrawGrid();
}

function bdResizeCanvas() {
  const bd = state.boardDraw;
  if (!bd.canvas) return;
  const wrap = bd.canvas.parentElement;
  if (!wrap) return;
  const w = wrap.clientWidth;
  bd.scale = w / BD_VIRTUAL_W;
  const actualW = w;
  const actualH = bd.currentH * bd.scale;
  let oldData = null;
  if (bd.ctx && bd.canvas.width && bd.canvas.height) {
    oldData = bd.ctx.getImageData(0, 0, bd.canvas.width, bd.canvas.height);
  }
  bd.canvas.width = actualW * bd.DPR;
  bd.canvas.height = actualH * bd.DPR;
  bd.canvas.style.width = actualW + 'px';
  bd.canvas.style.height = actualH + 'px';
  bd.ctx = bd.canvas.getContext('2d');
  bd.ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
  bd.ctx.fillStyle = '#1a1d2e';
  bd.ctx.fillRect(0, 0, actualW, actualH);
  if (oldData) {
    bd.ctx.save();
    bd.ctx.setTransform(1, 0, 0, 1, 0, 0);
    bd.ctx.putImageData(oldData, 0, 0);
    bd.ctx.restore();
  }
}

function bdExpandIfNeeded(maxY) {
  const bd = state.boardDraw;
  if (maxY > bd.currentH - 60) {
    bd.currentH = maxY + 200;
    bdResizeCanvas();
    bdDrawGrid();
    const wrap = document.getElementById('bd-canvas-wrap');
    if (wrap) wrap.scrollTop = wrap.scrollHeight;
  }
}

function bdDrawGrid() {
  const bd = state.boardDraw;
  if (!bd.ctx) return;
  const s = bd.scale;
  bd.ctx.strokeStyle = 'rgba(255,255,255,0.025)';
  bd.ctx.lineWidth = 1;
  for (let x = 40; x < BD_VIRTUAL_W; x += 40) {
    bd.ctx.beginPath(); bd.ctx.moveTo(x * s, 0); bd.ctx.lineTo(x * s, bd.currentH * s); bd.ctx.stroke();
  }
  for (let y = 40; y < bd.currentH; y += 40) {
    bd.ctx.beginPath(); bd.ctx.moveTo(0, y * s); bd.ctx.lineTo(BD_VIRTUAL_W * s, y * s); bd.ctx.stroke();
  }
}

function bdChalkStyle(color, width) {
  const bd = state.boardDraw;
  const c = BD_COLORS[color] || color || BD_COLORS.white;
  bd.ctx.strokeStyle = c;
  bd.ctx.fillStyle = c;
  bd.ctx.lineWidth = (width || 2.5) * bd.scale;
  bd.ctx.lineCap = 'round';
  bd.ctx.lineJoin = 'round';
  bd.ctx.shadowColor = c;
  bd.ctx.shadowBlur = 3;
}

function bdClearShadow() {
  const bd = state.boardDraw;
  bd.ctx.shadowColor = 'transparent';
  bd.ctx.shadowBlur = 0;
}

function bdSleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function bdAnimLine(x1, y1, x2, y2, color, width, duration) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  bdExpandIfNeeded(Math.max(y1, y2));
  duration = duration || 400;
  bdChalkStyle(color, width);
  const steps = Math.max(Math.ceil(duration / 16), 8);
  const dx = x2 - x1, dy = y2 - y1;
  bd.ctx.beginPath();
  bd.ctx.moveTo(x1 * s, y1 * s);
  for (let i = 1; i <= steps; i++) {
    if (bd.cancelFlag) return;
    const t = i / steps;
    const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    const wobble = (1 - t) * (Math.random() - 0.5) * 1.5;
    const px = x1 + dx * ease + wobble * (dy !== 0 ? 1 : 0);
    const py = y1 + dy * ease + wobble * (dx !== 0 ? 1 : 0);
    bd.ctx.lineTo(px * s, py * s);
    bd.ctx.stroke();
    bd.ctx.beginPath();
    bd.ctx.moveTo(px * s, py * s);
    await new Promise(r => requestAnimationFrame(r));
  }
  bd.ctx.lineTo(x2 * s, y2 * s);
  bd.ctx.stroke();
  bdClearShadow();
}

async function bdAnimArrow(x1, y1, x2, y2, color, width, duration) {
  await bdAnimLine(x1, y1, x2, y2, color, width, duration);
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const hl = 12;
  bdChalkStyle(color, width);
  bd.ctx.beginPath();
  bd.ctx.moveTo(x2 * s, y2 * s);
  bd.ctx.lineTo((x2 - hl * Math.cos(angle - 0.4)) * s, (y2 - hl * Math.sin(angle - 0.4)) * s);
  bd.ctx.stroke();
  bd.ctx.beginPath();
  bd.ctx.moveTo(x2 * s, y2 * s);
  bd.ctx.lineTo((x2 - hl * Math.cos(angle + 0.4)) * s, (y2 - hl * Math.sin(angle + 0.4)) * s);
  bd.ctx.stroke();
  bdClearShadow();
}

async function bdAnimRect(x, y, w, h, color, lw) {
  await bdAnimLine(x, y, x + w, y, color, lw, 250);
  await bdAnimLine(x + w, y, x + w, y + h, color, lw, 250);
  await bdAnimLine(x + w, y + h, x, y + h, color, lw, 250);
  await bdAnimLine(x, y + h, x, y, color, lw, 250);
}

async function bdAnimCircle(cx, cy, r, color, lw, duration) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  bdExpandIfNeeded(cy + r);
  duration = duration || 600;
  bdChalkStyle(color, lw);
  const steps = Math.max(Math.ceil(duration / 16), 20);
  bd.ctx.beginPath();
  bd.ctx.moveTo((cx + r) * s, cy * s);
  for (let i = 1; i <= steps; i++) {
    if (bd.cancelFlag) return;
    const a = (i / steps) * Math.PI * 2;
    const wb = (Math.random() - 0.5) * 1.2;
    const px = cx + (r + wb) * Math.cos(a);
    const py = cy + (r + wb) * Math.sin(a);
    bd.ctx.lineTo(px * s, py * s);
    bd.ctx.stroke();
    bd.ctx.beginPath();
    bd.ctx.moveTo(px * s, py * s);
    await new Promise(r => requestAnimationFrame(r));
  }
  bdClearShadow();
}

async function bdAnimArc(cx, cy, r, sa, ea, color, lw, duration) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  bdExpandIfNeeded(cy + r);
  duration = duration || 400;
  bdChalkStyle(color, lw);
  const steps = Math.max(Math.ceil(duration / 16), 12);
  const da = ea - sa;
  bd.ctx.beginPath();
  bd.ctx.moveTo((cx + r * Math.cos(sa)) * s, (cy + r * Math.sin(sa)) * s);
  for (let i = 1; i <= steps; i++) {
    if (bd.cancelFlag) return;
    const a = sa + da * (i / steps);
    bd.ctx.lineTo((cx + r * Math.cos(a)) * s, (cy + r * Math.sin(a)) * s);
    bd.ctx.stroke();
    bd.ctx.beginPath();
    bd.ctx.moveTo((cx + r * Math.cos(a)) * s, (cy + r * Math.sin(a)) * s);
    await new Promise(r => requestAnimationFrame(r));
  }
  bdClearShadow();
}

async function bdAnimText(text, x, y, color, size, charDelay) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const fs = (size || 22) * s;
  bdExpandIfNeeded(y + (size || 22));
  charDelay = charDelay || 40;
  bdChalkStyle(color, 1);
  bd.ctx.font = `${fs}px 'Caveat', cursive`;
  bd.ctx.textBaseline = 'middle';
  let cx = x * s;
  for (let i = 0; i < text.length; i++) {
    if (bd.cancelFlag) return;
    bd.ctx.fillText(text[i], cx, y * s);
    cx += bd.ctx.measureText(text[i]).width;
    await bdSleep(charDelay);
  }
  bdClearShadow();
}

async function bdAnimLatex(latex, x, y, color, size) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const c = BD_COLORS[color] || color || BD_COLORS.white;
  const fs = (size || 24) * s;
  bdExpandIfNeeded(y + (size || 24) * 2);

  const tmp = document.createElement('span');
  tmp.style.cssText = `position:absolute;visibility:hidden;font-size:${fs}px;color:${c};`;
  document.body.appendChild(tmp);
  try { katex.render(latex, tmp, { throwOnError: false, displayMode: false }); }
  catch (e) {
    bd.ctx.font = `${fs}px 'Caveat', cursive`;
    bd.ctx.fillStyle = c;
    bd.ctx.fillText(latex, x * s, y * s);
    document.body.removeChild(tmp);
    return;
  }
  const html = tmp.innerHTML, tw = tmp.offsetWidth, th = tmp.offsetHeight;
  document.body.removeChild(tmp);

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${tw}" height="${th}"><foreignObject width="100%" height="100%"><div xmlns="http://www.w3.org/1999/xhtml" style="font-size:${fs}px;color:${c};line-height:1;">${html}</div></foreignObject></svg>`;
  const img = new Image();
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  await new Promise(resolve => {
    img.onload = resolve;
    img.onerror = () => {
      bd.ctx.font = `${fs}px 'Caveat', cursive`;
      bd.ctx.fillStyle = c;
      bd.ctx.fillText(latex, x * s, y * s);
      resolve();
    };
    img.src = url;
  });
  if (bd.cancelFlag) { URL.revokeObjectURL(url); return; }

  const slW = 4, total = Math.ceil(tw / slW), delay = Math.max(8, 300 / total);
  for (let i = 0; i < total; i++) {
    if (bd.cancelFlag) break;
    bd.ctx.drawImage(img, i * slW * bd.DPR, 0, slW * bd.DPR, img.height,
      x * s + i * slW, y * s - th * 0.7, slW, th);
    await bdSleep(delay);
  }
  URL.revokeObjectURL(url);
}

async function bdAnimFreehand(points, color, width, duration) {
  const bd = state.boardDraw;
  if (bd.cancelFlag || !points || points.length < 2) return;
  const s = bd.scale;
  bdExpandIfNeeded(Math.max(...points.map(p => p[1])));
  duration = duration || 600;
  bdChalkStyle(color, width);
  const dl = duration / points.length;
  bd.ctx.beginPath();
  bd.ctx.moveTo(points[0][0] * s, points[0][1] * s);
  for (let i = 1; i < points.length; i++) {
    if (bd.cancelFlag) return;
    bd.ctx.lineTo(points[i][0] * s, points[i][1] * s);
    bd.ctx.stroke();
    bd.ctx.beginPath();
    bd.ctx.moveTo(points[i][0] * s, points[i][1] * s);
    await bdSleep(dl);
  }
  bdClearShadow();
}

async function bdAnimDashed(x1, y1, x2, y2, color, width) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  bdExpandIfNeeded(Math.max(y1, y2));
  bdChalkStyle(color, width || 1.5);
  bd.ctx.setLineDash([6 * s, 6 * s]);
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.sqrt(dx * dx + dy * dy);
  const steps = Math.ceil(len / 8);
  const dl = Math.max(4, 200 / steps);
  bd.ctx.beginPath();
  bd.ctx.moveTo(x1 * s, y1 * s);
  for (let i = 1; i <= steps; i++) {
    if (bd.cancelFlag) return;
    const t = i / steps;
    bd.ctx.lineTo((x1 + dx * t) * s, (y1 + dy * t) * s);
    bd.ctx.stroke();
    bd.ctx.beginPath();
    bd.ctx.moveTo((x1 + dx * t) * s, (y1 + dy * t) * s);
    await bdSleep(dl);
  }
  bd.ctx.setLineDash([]);
  bdClearShadow();
}

function bdDrawDot(x, y, r, color) {
  const bd = state.boardDraw;
  const s = bd.scale;
  bdExpandIfNeeded(y + (r || 3));
  bdChalkStyle(color);
  bd.ctx.beginPath();
  bd.ctx.arc(x * s, y * s, (r || 3) * s, 0, Math.PI * 2);
  bd.ctx.fill();
  bdClearShadow();
}

function bdShowVoice(text) {
  const el = state.boardDraw.voiceEl;
  if (!el) return;
  el.textContent = text;
  el.classList.add('visible');
}

function bdHideVoice() {
  const el = state.boardDraw.voiceEl;
  if (!el) return;
  el.classList.remove('visible');
}

function bdClearBoard() {
  const bd = state.boardDraw;
  if (!bd.ctx) return;
  bd.currentH = BD_INITIAL_H;
  bdResizeCanvas();
  bd.ctx.fillStyle = '#1a1d2e';
  bd.ctx.fillRect(0, 0, BD_VIRTUAL_W * bd.scale, bd.currentH * bd.scale);
  bdDrawGrid();
  bdHideVoice();
}

async function bdRunCommand(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  switch (cmd.cmd) {
    case 'line': await bdAnimLine(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.color, cmd.w, cmd.dur); break;
    case 'arrow': await bdAnimArrow(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.color, cmd.w, cmd.dur); break;
    case 'rect': await bdAnimRect(cmd.x, cmd.y, cmd.w, cmd.h, cmd.color, cmd.lw); break;
    case 'circle': await bdAnimCircle(cmd.cx, cmd.cy, cmd.r, cmd.color, cmd.lw, cmd.dur); break;
    case 'arc': await bdAnimArc(cmd.cx, cmd.cy, cmd.r, cmd.sa, cmd.ea, cmd.color, cmd.lw, cmd.dur); break;
    case 'text': await bdAnimText(cmd.text, cmd.x, cmd.y, cmd.color, cmd.size, cmd.charDelay); break;
    case 'latex': await bdAnimLatex(cmd.tex, cmd.x, cmd.y, cmd.color, cmd.size); break;
    case 'freehand': await bdAnimFreehand(cmd.pts, cmd.color, cmd.w, cmd.dur); break;
    case 'dashed': await bdAnimDashed(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.color, cmd.w); break;
    case 'dot': bdDrawDot(cmd.x, cmd.y, cmd.r, cmd.color); break;
    case 'voice':
      bdShowVoice(cmd.text);
      if (cmd.dur) { await bdSleep(cmd.dur); bdHideVoice(); }
      break;
    case 'pause': await bdSleep(cmd.ms || 500); break;
    case 'clear': bdClearBoard(); break;
  }
}

async function bdProcessQueue() {
  const bd = state.boardDraw;
  if (bd.isProcessing) return;
  bd.isProcessing = true;
  while (bd.commandQueue.length > 0) {
    if (bd.cancelFlag) break;
    await bdRunCommand(bd.commandQueue.shift());
  }
  bd.isProcessing = false;
}

function bdEnqueueCommand(cmd) {
  state.boardDraw.commandQueue.push(cmd);
  if (!state.boardDraw.isProcessing) bdProcessQueue();
}

function bdProcessStreaming(fullText) {
  const bd = state.boardDraw;
  if (bd.dismissed) return;
  if (!bd.active) {
    const m = fullText.match(/<teaching-board-draw([^>]*)>/);
    if (!m) return;
    const title = (m[1].match(/title="([^"]*)"/) || [])[1] || 'Board';
    openBoardDrawSpotlight(title);
    bd.active = true;
    bd.contentStartIdx = m.index + m[0].length;
    bd.processedLines = 0;
    bd.complete = false;
    bd.commandQueue = [];
    bd.isProcessing = false;
    bd.cancelFlag = false;
  }
  const closeIdx = fullText.indexOf('</teaching-board-draw>', bd.contentStartIdx);
  const end = closeIdx >= 0 ? closeIdx : fullText.length;
  const lines = fullText.slice(bd.contentStartIdx, end).split('\n');
  const count = closeIdx >= 0 ? lines.length : Math.max(0, lines.length - 1);
  for (let i = bd.processedLines; i < count; i++) {
    const ln = lines[i].trim();
    if (!ln) continue;
    try { bdEnqueueCommand(JSON.parse(ln)); } catch (e) {}
  }
  bd.processedLines = count;
  if (closeIdx >= 0) bd.complete = true;
}

function openBoardDrawSpotlight(title) {
  const panel = $('#spotlight-panel');
  const content = $('#spotlight-content');
  const titleEl = $('#spotlight-title');
  const typeBadge = $('#spotlight-type-badge');
  if (!panel || !content) return;

  if (state.spotlightActive) {
    if (state.activeSimulation) { stopSimBridge(); state.activeSimulation = null; state.simulationLiveState = null; }
    if (state.spotlightInfo?.type === 'notebook') {
      if (state.notebookCleanup) { state.notebookCleanup(); state.notebookCleanup = null; }
      state.notebookSteps = [];
    }
    if (state.spotlightInfo?.type === 'board-draw') bdCleanup();
    content.innerHTML = '';
  }

  if (titleEl) titleEl.textContent = title;
  if (typeBadge) { typeBadge.textContent = 'Board'; typeBadge.setAttribute('data-type', 'board-draw'); typeBadge.style.display = ''; }

  content.innerHTML = `
    <div class="bd-container" id="bd-container">
      <div class="bd-canvas-wrap" id="bd-canvas-wrap">
        <canvas id="bd-canvas"></canvas>
      </div>
      <div class="bd-voice" id="bd-voice">
        <span class="bd-voice-text" id="bd-voice-text"></span>
      </div>
    </div>`;

  panel.classList.add('stage-active');
  state.spotlightActive = true;
  state.spotlightInfo = { type: 'board-draw', title };
  enterSpotlightFullscreen();
  appendSpotlightReference('board-draw', title, { name: 'teaching-board-draw', attrs: { title } });

  setTimeout(() => {
    const c = document.getElementById('bd-canvas');
    const v = document.getElementById('bd-voice-text');
    if (c) bdInit(c, v);
  }, 30);
}

function bdCleanup() {
  const bd = state.boardDraw;
  bd.cancelFlag = true;
  bd.active = false;
  bd.dismissed = true;
  bd.commandQueue = [];
  bd.isProcessing = false;
  bd.canvas = null;
  bd.ctx = null;
  bd.voiceEl = null;
  bd.processedLines = 0;
  bd.contentStartIdx = 0;
  bd.complete = false;
}

// ═══════════════════════════════════════════════════════════
// Boot
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initSetup();

  // Clean up agent event SSE on page unload
  window.addEventListener('beforeunload', () => disconnectAgentEvents());
});
