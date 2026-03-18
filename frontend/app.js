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
    const apiUrl = $('#api-url')?.value?.trim() || window.location.origin;
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

  async function signup(name, email, password) {
    const apiUrl = $('#api-url')?.value?.trim() || window.location.origin;
    const res = await fetch(`${apiUrl}/api/v1/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    if (res.status === 409) throw new Error('An account with this email already exists');
    if (res.status === 400) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Please fill in all fields');
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text.slice(0, 200) || `Signup failed (${res.status})`);
    }
    const data = await res.json();
    setAuth(data.token, data.user);
    return data;
  }

  async function validateSession() {
    if (!isLoggedIn()) return false;
    const apiUrl = $('#api-url')?.value?.trim() || window.location.origin;
    try {
      const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
        headers: authHeaders(),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  return { getToken, getUser, isLoggedIn, setAuth, clearAuth, authHeaders, login, signup, logout, validateSession };
})();

// ═══════════════════════════════════════════════════════════
// Module 0b: First-time UI Hints
// ═══════════════════════════════════════════════════════════

const UIHints = (() => {
  const STORAGE_KEY = 'capacity_hints_seen';

  function getSeen() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
  }
  function markSeen(id) {
    const seen = getSeen();
    seen[id] = true;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(seen));
  }
  function hasSeen(id) { return !!getSeen()[id]; }

  function dismiss(id) {
    markSeen(id);
    const el = document.getElementById('ui-hint-' + id);
    if (el) {
      el.style.opacity = '0';
      el.style.transform = 'translateY(6px)';
      el.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
      setTimeout(() => el.remove(), 250);
    }
  }

  /**
   * Show a hint tooltip anchored to a target element.
   * @param {string} id - Unique hint ID (for dismiss/seen tracking)
   * @param {HTMLElement} anchor - Element to position near
   * @param {string} title - Bold title line
   * @param {string} body - Description text
   * @param {string} arrow - 'top'|'bottom'|'left'|'right' — where the arrow points
   * @param {object} offset - { top, left } pixel offsets from anchor
   */
  function show(id, anchor, title, body, arrow = 'top', offset = {}) {
    if (hasSeen(id) || document.getElementById('ui-hint-' + id)) return;
    if (!anchor) return;

    const hint = document.createElement('div');
    hint.className = 'ui-hint arrow-' + arrow;
    hint.id = 'ui-hint-' + id;
    hint.innerHTML = `
      <div class="ui-hint-title">${title}</div>
      <div>${body}</div>
      <span class="ui-hint-dismiss" onclick="UIHints.dismiss('${id}')">Got it</span>
    `;
    document.body.appendChild(hint);

    // Position relative to anchor
    const rect = anchor.getBoundingClientRect();
    const hintRect = hint.getBoundingClientRect();
    let top, left;

    if (arrow === 'top') {
      top = rect.bottom + 8 + (offset.top || 0);
      left = rect.left + (offset.left || 0);
    } else if (arrow === 'bottom') {
      top = rect.top - hintRect.height - 8 + (offset.top || 0);
      left = rect.left + (offset.left || 0);
    } else if (arrow === 'left') {
      top = rect.top + (offset.top || 0);
      left = rect.right + 8 + (offset.left || 0);
    } else {
      top = rect.top + (offset.top || 0);
      left = rect.left - hintRect.width - 8 + (offset.left || 0);
    }

    // Clamp to viewport
    top = Math.max(8, Math.min(top, window.innerHeight - hintRect.height - 8));
    left = Math.max(8, Math.min(left, window.innerWidth - hintRect.width - 8));

    hint.style.position = 'fixed';
    hint.style.top = top + 'px';
    hint.style.left = left + 'px';

    // Auto-dismiss after 12s
    setTimeout(() => dismiss(id), 12000);
  }

  function removeAll() {
    document.querySelectorAll('.ui-hint').forEach(el => el.remove());
  }

  return { show, dismiss, hasSeen, markSeen, removeAll };
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
        activeSpotlight: state.spotlightActive ? {
          active: true,
          info: state.spotlightInfo,
          openedAtTurn: state.spotlightOpenedAtTurn,
        } : null,
        scribbleStrokes: state.scribble.strokes.map(s => ({
          points: s.points,
          color: s.color,
          width: s.width,
          isHighlighter: s.isHighlighter,
        })),
        teachingCounters: {
          totalAssistantTurns: state.totalAssistantTurns,
          lastVisualTurn: state.lastVisualTurn,
          visualAssetCount: state.visualAssetCount,
          lastEngagementTurn: state.lastEngagementTurn,
        },
        assessment: state.assessment.active ? {
          active: true,
          sectionTitle: state.assessment.sectionTitle,
          concepts: state.assessment.concepts,
          questionNumber: state.assessment.questionNumber,
          maxQuestions: state.assessment.maxQuestions,
        } : null,
        conceptNotes: state.assessment.conceptNotes,
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
        plan: session.plan,
        coursePosition: session.coursePosition,
        summaries: session.summaries,
        generatedVisuals: state.generatedVisuals,
        spotlightHistory: state.spotlightHistory,
        notebookSteps: state.notebookSteps,
        activeSpotlight: state.spotlightActive ? {
          active: true,
          info: state.spotlightInfo,
          openedAtTurn: state.spotlightOpenedAtTurn,
        } : null,
        scribbleStrokes: state.scribble.strokes.map(s => ({
          points: s.points, color: s.color, width: s.width, isHighlighter: s.isHighlighter,
        })),
        teachingCounters: {
          totalAssistantTurns: state.totalAssistantTurns,
          lastVisualTurn: state.lastVisualTurn,
          visualAssetCount: state.visualAssetCount,
          lastEngagementTurn: state.lastEngagementTurn,
        },
        assessment: state.assessment.active ? {
          active: true,
          sectionTitle: state.assessment.sectionTitle,
          concepts: state.assessment.concepts,
          questionNumber: state.assessment.questionNumber,
          maxQuestions: state.assessment.maxQuestions,
        } : null,
        conceptNotes: state.assessment.conceptNotes,
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
          plan: session.plan,
          coursePosition: session.coursePosition,
          spotlightHistory: state.spotlightHistory,
          notebookSteps: state.notebookSteps,
          generatedVisuals: state.generatedVisuals,
          activeSpotlight: state.spotlightActive ? {
            active: true, info: state.spotlightInfo, openedAtTurn: state.spotlightOpenedAtTurn,
          } : null,
          scribbleStrokes: state.scribble.strokes.map(s => ({
            points: s.points, color: s.color, width: s.width, isHighlighter: s.isHighlighter,
          })),
          teachingCounters: {
            totalAssistantTurns: state.totalAssistantTurns,
            lastVisualTurn: state.lastVisualTurn,
            visualAssetCount: state.visualAssetCount,
            lastEngagementTurn: state.lastEngagementTurn,
          },
          assessment: state.assessment.active ? {
            active: true, sectionTitle: state.assessment.sectionTitle,
            concepts: state.assessment.concepts,
            questionNumber: state.assessment.questionNumber,
            maxQuestions: state.assessment.maxQuestions,
          } : null,
          conceptNotes: state.assessment.conceptNotes,
        }),
        keepalive: true,
      });
    } catch (e) { /* best-effort on unload */ }
  }

  // ─── Recording ───────────────────────────────────────────

  function recordMessage(role, content, multipartContent) {
    if (!session) return;
    const msg = { id: generateId(), role, content, timestamp: now(), sectionIndex: getActiveSectionIndex() };
    if (multipartContent && Array.isArray(multipartContent)) {
      msg.hasImages = true;
      msg.parts = multipartContent.map(p =>
        p.type === 'image' ? { type: 'image', source_type: p.source?.type, media_type: p.source?.media_type } : p
      );
    }
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
  apiUrl: window.location.origin,
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
  _lastSSETimestamp: 0,
  _streamingTimeout: null,
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
    studentDrawing: false,
    studentColor: '#22ee66',
    studentStrokeW: 2.5,
    rawContent: null,
    tutorSnapshot: null,
  },

  // Widget streaming state
  widget: {
    active: false,
    contentStartIdx: 0,
    complete: false,
    title: '',
    code: '',
  },

  // Pending spotlight close event (included as context in next message)
  pendingSpotlightEvent: null,
  recentlyClosedSim: null,
  pendingBoardCaptureRequest: false,
  pendingBoardCapture: null,

  // Visual engagement tracking
  totalAssistantTurns: 0,
  lastVisualTurn: 0,
  visualAssetCount: 0,
  spotlightOpenedAtTurn: 0,
  lastEngagementTurn: 0,

  // Replay mode flag — true during transcript rebuild (prevents spotlight opening)
  replayMode: false,

  // Scribble annotation system
  scribble: {
    active: false,
    canvas: null,
    ctx: null,
    strokes: [],
    currentStroke: null,
    color: '#22ee66',
    lineWidth: 3,
    isHighlighter: false,
    visible: true,
    dirty: false,
    beforeSnapshot: null,
    capturePromise: null,
  },

  // Assessment checkpoint system
  assessment: {
    active: false,          // true while assessment agent is in control (set by SSE events)
    sectionTitle: '',       // section being assessed (from ASSESSMENT_START)
    concepts: [],           // concepts being tested (from ASSESSMENT_START)
    conceptNotes: {},       // persisted concept notes from assessments
    questionNumber: 0,      // current question (1-based, incremented on each question render)
    maxQuestions: 5,        // from ASSESSMENT_START SSE event
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
const SVG_IMAGE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>`;

function buildTextInput(id, placeholder, submitFnStr) {
  return `
    <div class="input-wrapper">
      <div class="input-image-preview" id="${id}-img-preview" style="display:none">
        <img id="${id}-img-thumb" />
        <button class="img-preview-remove" onclick="removeInputImage('${id}')">&times;</button>
      </div>
      <textarea class="text-input" id="${id}" placeholder="${escapeAttr(placeholder)}" rows="1"></textarea>
      <div class="input-icons">
        <input type="file" id="${id}-file" accept="image/*,application/pdf" style="display:none" onchange="handleImageSelect('${id}', this)" />
        <button class="input-icon-btn input-img-btn" onclick="document.getElementById('${id}-file').click()" title="Upload image">${SVG_IMAGE}</button>
        <button class="input-icon-btn input-mic-btn" onclick="startVoiceInput('${id}')" title="Voice input">${SVG_MIC}</button>
        <button class="input-icon-btn input-send-btn" onclick="${submitFnStr}" title="Send (Shift+Enter)">${SVG_SEND}</button>
      </div>
    </div>`;
}

// Pending image attachment for input fields { inputId: { dataUrl, mediaType } }
const _pendingImages = {};

window.handleImageSelect = function(inputId, fileInput) {
  const file = fileInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = reader.result;
    const mediaType = file.type || 'image/png';
    const base64 = dataUrl.split(',')[1];
    _pendingImages[inputId] = { base64, mediaType };
    const preview = $(`#${inputId}-img-preview`);
    const thumb = $(`#${inputId}-img-thumb`);
    if (preview && thumb) {
      thumb.src = dataUrl;
      preview.style.display = 'flex';
    }
  };
  reader.readAsDataURL(file);
};

window.removeInputImage = function(inputId) {
  delete _pendingImages[inputId];
  const preview = $(`#${inputId}-img-preview`);
  if (preview) preview.style.display = 'none';
};

// Bind Shift+Enter to send + paste image support on any text input after it's created
function bindInputHandlers(inputId, submitFnStr) {
  const el = $(`#${inputId}`);
  if (!el) return;

  // First-time hint for chat input
  setTimeout(() => {
    UIHints.show('chat-input', el,
      'Respond to Euler here',
      'Euler will ask you questions in the chat. Type your answer and press <b>Shift+Enter</b> or tap the send button.',
      'bottom', { left: 0 });
  }, 500);

  el.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault();
      // Trigger the submit function
      const fn = new Function(submitFnStr);
      fn();
    }
  });
  el.addEventListener('paste', (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = reader.result;
          const base64 = dataUrl.split(',')[1];
          _pendingImages[inputId] = { base64, mediaType: item.type };
          const preview = $(`#${inputId}-img-preview`);
          const thumb = $(`#${inputId}-img-thumb`);
          if (preview && thumb) {
            thumb.src = dataUrl;
            preview.style.display = 'flex';
          }
        };
        reader.readAsDataURL(file);
        break;
      }
    }
  });
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
  state._lastSSETimestamp = Date.now();

  // Safety timeout: force-reset after 120s of total streaming
  if (state._streamingTimeout) clearTimeout(state._streamingTimeout);
  state._streamingTimeout = setTimeout(() => {
    if (state.isStreaming) {
      console.warn('[streamADK] Safety timeout — force-resetting streaming state');
      state.isStreaming = false;
      removeStreamingIndicator();
      renderAIError('Response timed out. Please try again.');
    }
  }, 120000);

  const userMsg = {
    id: generateId(),
    role: 'user',
    content: userMessageContent,
  };
  state.messages.push(userMsg);

  const recordText = typeof userMessageContent === 'string'
    ? userMessageContent
    : (userMessageContent.find(b => b.type === 'text')?.text || '[image content]');
  const multipart = Array.isArray(userMessageContent) ? userMessageContent : null;
  SessionManager.recordMessage('user', recordText, multipart);

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
    removeAssessmentTransition();
    renderAIError(err.message);
  }

  state.isStreaming = false;
  if (state._streamingTimeout) { clearTimeout(state._streamingTimeout); state._streamingTimeout = null; }

  SessionManager.saveSession();

  // Handle deferred board capture request from tutor tool
  if (state.pendingBoardCaptureRequest) {
    state.pendingBoardCaptureRequest = false;
    setTimeout(() => {
      if (state.boardDraw.canvas) {
        const combinedUrl = bdCaptureBoard();
        if (combinedUrl) {
          const bd = state.boardDraw;
          const parts = [];
          if (bd.tutorSnapshot) {
            const tutorB64 = bd.tutorSnapshot.split(',')[1];
            parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: tutorB64 } });
            parts.push({ type: 'text', text: '[IMAGE 1 — TUTOR ORIGINAL] This is what YOU drew originally.' });
          }
          const combinedB64 = combinedUrl.split(',')[1];
          parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: combinedB64 } });
          parts.push({ type: 'text', text: bd.tutorSnapshot
            ? '[IMAGE 2 — COMBINED] Your drawing + student additions. Compare with IMAGE 1 to see what the student added.'
            : '[Board capture] Current state of the shared board.' });
          streamADK(parts, true);
        }
      }
    }, 200);
  }
}

function handleSSEEvent(event) {
  state._lastSSETimestamp = Date.now();
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
      state.widget = { active: false, contentStartIdx: 0, complete: false, title: '', code: '' };
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
      state.totalAssistantTurns++;
      finalizeAIMessage(state.accumulatedText);
      state.messages.push({
        id: state.currentMessageId || generateId(),
        role: 'assistant',
        content: state.accumulatedText,
      });
      SessionManager.recordMessage('assistant', state.accumulatedText);
      state.currentMessageId = null;
      // Show indicator if still streaming (more tool calls / messages coming)
      if (state.isStreaming && !$('#streaming-indicator')) {
        showStreamingIndicator();
      }
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
      removeAssessmentTransition();
      cleanupToolIndicators();
      ensureFallbackInput();
      break;

    case 'RUN_ERROR':
      removeStreamingIndicator();
      removeAssessmentTransition();
      cleanupToolIndicators();
      renderAIError(event.message || 'Unknown error');
      break;

    case 'PLAN_UPDATE':
      handlePlanFromAgent(event.plan, event.sessionObjective);
      break;

    case 'COST_UPDATE':
      updateSessionCost(event.costCents);
      break;

    case 'TEACHING_DELEGATION_START':
      break;

    case 'TEACHING_DELEGATION_END':
      break;

    case 'TOPIC_COMPLETE':
      handleTopicComplete(event.section_index, event.topic_index);
      break;

    case 'SECTION_COMPLETE':
      handleSectionComplete(event.index);
      break;

    case 'PLAN_RESET':
      handlePlanReset(event.reason, event.keep_scope);
      break;

    case 'SIM_CONTROL':
      handleSimControl(event.steps);
      break;

    case 'VISUAL_READY':
      state.generatedVisuals[event.id] = { title: event.title, html: event.html };
      break;

    case 'BOARD_CAPTURE_REQUEST':
      state.pendingBoardCaptureRequest = true;
      break;

    case 'ASSESSMENT_START':
      state.assessment.active = true;
      state.assessment.sectionTitle = event.section?.title || 'Section Checkpoint';
      state.assessment.concepts = event.concepts || [];
      state.assessment.questionNumber = 0;
      state.assessment.maxQuestions = event.maxQuestions || 5;
      // Remove the tutor's last message if it leaked handoff language
      // (tutor is instructed to not write text, but safety net)
      {
        const lastAI = document.querySelector('#canvas-stream .canvas-block[data-type="ai"]:last-of-type');
        if (lastAI) {
          lastAI.style.transition = 'opacity 0.2s ease';
          lastAI.style.opacity = '0';
          setTimeout(() => lastAI.remove(), 200);
        }
      }
      // Dismiss any open spotlight (clean slate for assessment)
      if (state.spotlightActive) {
        window.hideSpotlight({ agentInitiated: true });
      }
      // Insert visual transition divider
      appendBlock('system', `
        <div class="assessment-divider">
          <div class="assessment-badge">Section Checkpoint</div>
        </div>
      `, { className: 'assessment-divider-block' });
      // Open assessment spotlight
      openAssessmentSpotlight();
      break;

    case 'ASSESSMENT_END': {
      state.assessment.active = false;
      state.assessment.questionNumber = 0;
      const score = event.score || {};
      const isHandback = event.reason && event.reason !== 'complete';
      const sectionTitle = event.section || state.assessment.sectionTitle || 'Section Checkpoint';

      // Close assessment spotlight
      if (state.spotlightActive && state.spotlightInfo?.type === 'assessment') {
        window.hideSpotlight({ agentInitiated: true });
      }
      // Restore close/fullscreen buttons (in case they were hidden)
      const closeBtn = document.querySelector('.spotlight-close-btn');
      const fsBtn = document.querySelector('.spotlight-fullscreen-btn');
      if (closeBtn) closeBtn.style.display = '';
      if (fsBtn) fsBtn.style.display = '';

      // Build contextual assessment summary card
      const pct = score.pct != null ? score.pct : (score.total ? Math.round((score.correct / score.total) * 100) : 0);
      const cardClass = isHandback ? 'handback' : 'complete';
      const statusLabel = isHandback ? 'Paused' : 'Complete';
      const mastery = event.overallMastery || '';

      // Per-concept breakdown
      let conceptsHtml = '';
      const perConcept = event.perConcept || [];
      if (perConcept.length > 0) {
        const conceptItems = perConcept.map(pc => {
          const cMastery = pc.mastery || 'developing';
          const cLabel = (pc.concept || '').replace(/_/g, ' ');
          return `<span class="assessment-concept-chip ${cMastery}">${cLabel} ${pc.correct || 0}/${pc.total || 0}</span>`;
        }).join('');
        conceptsHtml = `<div class="assessment-concepts-row">${conceptItems}</div>`;
      }

      // Mastery indicator
      let masteryHtml = '';
      if (mastery && !isHandback) {
        const masteryLabels = { strong: 'Strong', developing: 'Developing', weak: 'Needs Review' };
        masteryHtml = `<div class="assessment-mastery ${mastery}">${masteryLabels[mastery] || mastery}</div>`;
      }

      // Handback reason
      let reasonHtml = '';
      if (isHandback && event.reason) {
        const reasonLabels = {
          student_struggling: 'Let\'s review this together',
          declined: 'Checkpoint skipped',
          needs_help: 'Let\'s work through this step by step',
          disengaged: 'We\'ll come back to this later',
          max_turns: 'Checkpoint paused',
        };
        reasonHtml = `<div class="assessment-reason">${reasonLabels[event.reason] || ''}</div>`;
      }

      const cardHtml = `
        <div class="assessment-summary-card ${cardClass}">
          <div class="assessment-summary-header">
            <span class="assessment-summary-icon">${isHandback ? '⏸' : '✓'}</span>
            <span class="assessment-summary-title">${escapeHtml(sectionTitle)}</span>
            <span class="assessment-summary-status">${statusLabel}</span>
          </div>
          ${score.total ? `
            <div class="assessment-summary-score">
              <div class="assessment-score-bar">
                <div class="assessment-score-fill" style="width: ${pct}%"></div>
              </div>
              <span class="assessment-score-text">${score.correct || 0}/${score.total || 0} (${pct}%)</span>
            </div>
          ` : ''}
          ${conceptsHtml}
          ${masteryHtml}
          ${reasonHtml}
        </div>
      `;
      appendBlock('system', cardHtml, { className: 'assessment-divider-block' });

      // Add to spotlight history for serialization
      state.spotlightHistory.push({
        id: 'assessment-' + generateId().slice(0, 8),
        type: 'assessment',
        title: sectionTitle,
        assessmentResult: {
          reason: event.reason,
          score,
          overallMastery: mastery,
          perConcept,
          section: sectionTitle,
          isHandback,
        },
      });

      // Show intermediate transition message while tutor prepares
      showAssessmentTransition(isHandback);

      // Auto-trigger tutor handoff after transition appears
      setTimeout(() => {
        if (state.isStreaming) return;
        disableActiveInputs();
        setTimeout(() => {
          if (state.isStreaming) { reenableInputs(); return; }
          streamADK('[Assessment checkpoint completed — resume teaching]', true);
        }, 800);
      }, 600);

      break;
    }
  }
}

// ═══════════════════════════════════════════════════════════
// Module 7: Context Building
// ═══════════════════════════════════════════════════════════

function buildContext() {
  const items = [];

  // Include pending spotlight close event if any
  if (state.pendingSpotlightEvent) {
    items.push({
      description: 'Spotlight Event',
      value: state.pendingSpotlightEvent,
    });
    state.pendingSpotlightEvent = null;
  }

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

  // Context 5: Available Simulations
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

  // Context: Visual Engagement tracking — only during explanation/discussion mode
  const turnsSinceLastVisual = state.totalAssistantTurns - state.lastVisualTurn;
  const turnsSinceLastEngagement = state.totalAssistantTurns - state.lastEngagementTurn;
  const inExplanationMode = turnsSinceLastEngagement >= 2 && !state.spotlightActive;
  if (state.totalAssistantTurns >= 3 && turnsSinceLastVisual >= 2 && inExplanationMode) {
    const urgency = turnsSinceLastVisual >= 4 ? 'URGENT' : 'NOTICE';
    items.push({
      description: `Visual Engagement — ${urgency}`,
      value: JSON.stringify({
        turnsSinceLastVisual,
        totalVisualAssets: state.visualAssetCount,
        action: turnsSinceLastVisual >= 4
          ? 'Your last 4+ explanation messages were pure text. Use a visual asset in this response.'
          : 'Consider adding a visual — board drawing, image, or diagram — to keep engagement high.',
        note: 'This alert is suppressed during MCQs, problem-solving, notebook work, and active spotlight viewing. It only applies to explanation and discussion turns.',
        quickOptions: [
          '<teaching-board-draw> — draw a diagram live (fastest)',
          '<teaching-widget> — interactive simulation (sliders, animation)',
          'search_images() — find a reference image',
          '<teaching-video> — show a lecture clip',
          '<teaching-simulation> — open a pre-built experiment',
        ],
      }),
    });
  }

  // Context: Spotlight state (if an asset is pinned in the spotlight panel)
  if (state.spotlightActive && state.spotlightInfo) {
    const turnsOpen = state.totalAssistantTurns - state.spotlightOpenedAtTurn;
    const isSim = state.spotlightInfo.type === 'simulation';
    const staleThreshold = isSim ? 5 : 2;
    const mandatoryThreshold = isSim ? 7 : 3;
    const spotlightCtx = {
      spotlightOpen: true,
      type: state.spotlightInfo.type,
      title: state.spotlightInfo.title,
      id: state.spotlightInfo.id || null,
      turnsOpen,
      rules: [
        'Student can see this asset RIGHT NOW. Reference it naturally.',
        'SPOTLIGHT SNAPSHOT: A snapshot of the spotlight content is automatically attached to every student message while open — you can see what the student sees.',
        'CLOSE IT when done: emit <teaching-spotlight-dismiss /> when discussion moves past this asset.',
        '"Actively discussing" means you are POINTING AT or DESCRIBING specific elements in the spotlight content RIGHT NOW. General topic overlap is NOT enough — if you are asking questions or explaining without referencing the visual, CLOSE IT.',
      ],
    };

    // Simulations are interactive and long-lived — relax stale rules
    if (isSim) {
      spotlightCtx.rules.push(
        'SIMULATION IS INTERACTIVE — student may still be exploring. Keep it open while discussion relates to this simulation.',
        'DO NOT open a board-draw or widget while this simulation is open. Explain in chat text instead, or close the simulation first with <teaching-spotlight-dismiss /> then open the new asset.',
        'If the student asks about the simulation or you want to reference it, it is ALREADY OPEN — just discuss it. Do NOT emit a new <teaching-simulation> tag for the same sim.'
      );
    }

    if (turnsOpen >= staleThreshold) {
      spotlightCtx.rules.push(
        `⚠ STALE SPOTLIGHT: "${state.spotlightInfo.title}" open for ${turnsOpen} turns. Ask yourself: "Am I pointing at something IN the spotlight right now?" If NO → emit <teaching-spotlight-dismiss /> as the FIRST TAG in your response, BEFORE any text. You can always reopen or draw a new one later.`
      );
    }
    if (turnsOpen >= mandatoryThreshold) {
      spotlightCtx.rules.push(
        `🚨 MANDATORY CLOSE: Spotlight open ${turnsOpen} turns — this is too long. Emit <teaching-spotlight-dismiss /> as the VERY FIRST thing in your response. No exceptions. If you still need a visual, close this one and open a fresh one.`
      );
    }

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

    // Board-draw collaborative: let tutor know the student can draw on the board
    if (state.spotlightInfo.type === 'board-draw') {
      spotlightCtx.collaborative = true;
      spotlightCtx.studentCanDraw = true;
      spotlightCtx.rules.push(
        'SHARED BOARD: The student has drawing tools and can annotate on the SAME canvas you drew on.',
        'Student strokes appear in green/red/white over your drawing.',
        'AUTOMATIC SNAPSHOT: A board image is auto-attached to every student message while the board is open — you can SEE what the student sees without asking.',
        'If you need an immediate capture between student messages, use request_board_image tool.',
        'Encourage the student to draw, annotate, or mark things on the board: "Try drawing the force vectors yourself!" or "Mark where you think the equilibrium point is."',
      );
    }

    items.push({
      description: 'ACTIVE SPOTLIGHT — asset currently pinned above chat',
      value: JSON.stringify(spotlightCtx),
    });
  }

  // Context: Recently closed simulation — tutor can reopen if discussing it
  if (!state.spotlightActive && state.recentlyClosedSim) {
    const turnsSinceClosed = state.totalAssistantTurns - state.recentlyClosedSim.closedAtTurn;
    if (turnsSinceClosed <= 3) {
      items.push({
        description: 'RECENTLY CLOSED SIMULATION — available to reopen',
        value: JSON.stringify({
          simId: state.recentlyClosedSim.id,
          title: state.recentlyClosedSim.title,
          turnsSinceClosed,
          instruction: `The simulation "${state.recentlyClosedSim.title}" was recently closed ${turnsSinceClosed} turn(s) ago. If you want to discuss or reference this simulation, REOPEN IT by emitting <teaching-simulation id="${state.recentlyClosedSim.id}" /> — do NOT talk about a simulation the student cannot see. If the student asks about it or you need to reference it, open it first.`,
        }),
      });
    } else {
      state.recentlyClosedSim = null; // expired
    }
  }

  // Auto-include board snapshot when board is active and student has drawn
  if (state.boardDraw.studentDrawing && state.boardDraw.canvas && state.spotlightInfo?.type === 'board-draw') {
    items.push({
      description: 'Board Draw — Student Activity',
      value: 'The student has been drawing on the shared board. Use request_board_image if you want to see the current state, or wait for the student to click Send.',
    });
  }

  // Include pending board capture if set
  if (state.pendingBoardCapture) {
    items.push({
      description: 'Board Capture — Current Board Image',
      value: state.pendingBoardCapture,
    });
    state.pendingBoardCapture = null;
  }

  // Directive: Teaching plan
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

  // Assessment handoff: when all topics in the active section are done
  return directive;
}

// Assessment protocol and directive functions removed — all agent logic is now in the backend.
// The backend assessment agent has its own system prompt and tools.
// The tutor's backend prompt includes handoff_to_assessment tool instructions.

// ═══════════════════════════════════════════════════════════
// Module 8: Streaming & AI Message Rendering
// ═══════════════════════════════════════════════════════════

const _thinkingPhrases = [
  'Thinking...',
  'Preparing the next step...',
  'Working on it...',
  'Putting ideas together...',
  'Setting things up...',
  'Almost there...',
];
let _thinkingRotateTimer = null;

function showStreamingIndicator() {
  // If assessment transition is visible, it serves as the indicator — skip
  if ($('#assessment-transition')) return;
  removeStreamingIndicator();
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block board-text-block fade-in';
  block.dataset.type = 'ai';
  block.id = 'streaming-indicator';
  block.innerHTML = '<div class="board-text" style="color:var(--text-dim);"><span class="loading-spinner"></span> <span class="thinking-text">Thinking...</span></div>';
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;

  // Rotate phrases every 3s
  let idx = 0;
  if (_thinkingRotateTimer) clearInterval(_thinkingRotateTimer);
  _thinkingRotateTimer = setInterval(() => {
    const textEl = block.querySelector('.thinking-text');
    if (!textEl || !document.contains(block)) {
      clearInterval(_thinkingRotateTimer);
      _thinkingRotateTimer = null;
      return;
    }
    idx = (idx + 1) % _thinkingPhrases.length;
    textEl.style.opacity = '0';
    setTimeout(() => {
      if (textEl) {
        textEl.textContent = _thinkingPhrases[idx];
        textEl.style.opacity = '1';
      }
    }, 200);
  }, 3000);
}

function removeStreamingIndicator() {
  if (_thinkingRotateTimer) { clearInterval(_thinkingRotateTimer); _thinkingRotateTimer = null; }
  const el = $('#streaming-indicator');
  if (el) el.remove();
}

function showAssessmentTransition(isHandback) {
  removeAssessmentTransition();
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block assessment-divider-block fade-in';
  block.dataset.type = 'system';
  block.id = 'assessment-transition';

  const messages = isHandback
    ? ['Handing back to your tutor...', 'Preparing to continue...']
    : ['Reviewing your results...', 'Preparing feedback...', 'Getting ready to discuss...'];

  block.innerHTML = `
    <div class="block-card" style="background:transparent;border:none;box-shadow:none;padding:0;">
      <div class="assessment-transition-msg">
        <span class="assessment-transition-spinner"></span>
        <span class="assessment-transition-text">${messages[0]}</span>
      </div>
    </div>`;
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;

  // Rotate through messages
  if (messages.length > 1) {
    let idx = 0;
    const interval = setInterval(() => {
      idx = (idx + 1) % messages.length;
      const textEl = block.querySelector('.assessment-transition-text');
      if (textEl) {
        textEl.style.opacity = '0';
        setTimeout(() => {
          textEl.textContent = messages[idx];
          textEl.style.opacity = '1';
        }, 200);
      } else {
        clearInterval(interval);
      }
    }, 2000);
    block._transitionInterval = interval;
  }
}

function removeAssessmentTransition() {
  const el = $('#assessment-transition');
  if (el) {
    if (el._transitionInterval) clearInterval(el._transitionInterval);
    el.remove();
  }
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

  // Only show visual_gen indicator — planning/asset/research are invisible to student
  const labels = {
    visual_gen: 'Creating interactive visual...',
  };

  // Deduplicate by agent type — show only one indicator per type
  const seen = new Set();
  const unique = running.filter(a => {
    if (!labels[a.type]) return false;  // Hide non-student-facing agents
    if (seen.has(a.type)) return false;
    seen.add(a.type);
    return true;
  });

  el.innerHTML = unique.map(a =>
    `<div class="agent-indicator"><span class="loading-spinner small"></span> ${labels[a.type]}</div>`
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
      topic.status = 'done';
      // Activate next pending topic in this section
      const nextTopic = step.topics.find(t => t.status === 'pending');
      if (nextTopic) {
        nextTopic.status = 'active';
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
    step.status = 'done';
    const nextPending = state.plan.find(s => s.status === 'pending');
    if (nextPending) {
      nextPending.status = 'active';
      state.planActiveStep = nextPending.n;
      // Auto-insert section heading + first topic heading on the board
      insertTopicHeading(nextPending.title, null, 'section');
      if (nextPending.topics && nextPending.topics[0]) {
        nextPending.topics[0].status = 'active';
        insertTopicHeading(nextPending.topics[0].title, nextPending.topics[0].concept, 'topic');
      }
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
  removeAssessmentTransition();
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
  widgetProcessStreaming(text);

  let displayHtml = renderMarkdownBasic(stripTeachingTags(text));

  // Show generating indicator when widget is streaming
  if (state.widget.active && !state.widget.complete) {
    const wTitle = state.widget.title || 'Interactive Widget';
    const codeLen = state.widget.code?.length || 0;
    const progress = codeLen < 500 ? 'Setting up structure...'
      : codeLen < 2000 ? 'Adding styles...'
      : 'Writing simulation logic...';
    displayHtml += `<div class="widget-gen-indicator">
      <div class="widget-gen-icon">⚡</div>
      <div class="widget-gen-info">
        <div class="widget-gen-title">Generating: ${escapeHtml(wTitle)}</div>
        <div class="widget-gen-progress">${progress}</div>
      </div>
      <div class="widget-gen-spinner"></div>
    </div>`;
  }

  el.innerHTML = displayHtml;
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
    state.pendingFallbackTimer = setTimeout(() => {
      state.pendingFallbackTimer = null;
      appendBlock('ai', `
        <div class="text-input-area">
          ${buildTextInput(fallbackId, 'Type your response...', `submitFreetext('${fallbackId}')`)}
        </div>
      `, { interactive: true });
      bindInputHandlers(fallbackId, `submitFreetext('${fallbackId}')`);
    }, 800);
  } else if (!hasRecap) {
    state.pendingFallbackTimer = setTimeout(() => {
      state.pendingFallbackTimer = null;
      appendBlock('ai', `
        <div class="text-input-area">
          ${buildTextInput(fallbackId, 'Type your response...', `submitFreetext('${fallbackId}')`)}
        </div>
      `, { interactive: true });
      bindInputHandlers(fallbackId, `submitFreetext('${fallbackId}')`);
    }, 800);
  }

  // Highlight last chat message when spotlight is active — draws student's eye back to chat
  if (state.spotlightActive) {
    highlightLastChatMessage();
  }
}

function ensureFallbackInput() {
  // After RUN_FINISHED, ensure there's an active input for the student.
  // If the 120ms timer from finalizeAIMessage is still pending, let it handle it.
  if (state.pendingFallbackTimer) return;

  // Small delay to let any pending DOM updates settle (timer-created inputs, etc.)
  setTimeout(() => {
    if (state.pendingFallbackTimer) return;
    if (state.isStreaming) return;

    const stream = $('#canvas-stream');
    if (!stream) return;
    const activeInput = stream.querySelector('.canvas-block[data-interactive="true"]:not([data-resolved])');
    if (activeInput) return;

    const fallbackId = 'fallback-' + generateId().slice(0, 8);
    appendBlock('ai', `
      <div class="text-input-area">
        ${buildTextInput(fallbackId, 'Type your response...', `submitFreetext('${fallbackId}')`)}
      </div>
    `, { interactive: true });
    bindInputHandlers(fallbackId, `submitFreetext('${fallbackId}')`);
  }, 150);
}

function showChatAttentionHopper(fullText) {
  // Remove any existing hopper
  const old = document.getElementById('chat-attention-hopper');
  if (old) old.remove();

  // Extract a preview — find the last question or meaningful text
  const stripped = fullText.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  let preview = '';
  const questionMatch = stripped.match(/([^.!?]*\?)\s*$/);
  if (questionMatch) {
    preview = questionMatch[1].trim();
    if (preview.length > 80) preview = preview.slice(-80);
  } else {
    preview = stripped.slice(-60).trim();
  }

  const hopper = document.createElement('div');
  hopper.id = 'chat-attention-hopper';
  hopper.innerHTML = `
    <div class="hopper-pulse"></div>
    <div class="hopper-content">
      <span class="hopper-icon">💬</span>
      <span class="hopper-text">${preview ? escapeHtml(preview) : 'New message below'}</span>
    </div>
    <span class="hopper-arrow">↓</span>
  `;
  hopper.addEventListener('click', () => {
    const stream = $('#canvas-stream');
    if (stream) stream.scrollIntoView({ behavior: 'smooth', block: 'start' });
    hopper.classList.add('hopper-dismissed');
    setTimeout(() => hopper.remove(), 300);
  });

  const canvasCol = document.getElementById('canvas-column');
  if (canvasCol) canvasCol.appendChild(hopper);

  // Auto-dismiss when user scrolls the chat stream
  const stream = $('#canvas-stream');
  if (stream) {
    const onScroll = () => {
      const el = document.getElementById('chat-attention-hopper');
      if (!el) { stream.removeEventListener('scroll', onScroll); return; }
      // Check if any chat content is visible
      const streamRect = stream.getBoundingClientRect();
      const lastBlock = stream.lastElementChild;
      if (lastBlock) {
        const blockRect = lastBlock.getBoundingClientRect();
        if (blockRect.top < streamRect.bottom) {
          el.classList.add('hopper-dismissed');
          setTimeout(() => el.remove(), 300);
          stream.removeEventListener('scroll', onScroll);
        }
      }
    };
    stream.addEventListener('scroll', onScroll);
  }

  // Auto-dismiss after 15 seconds
  setTimeout(() => {
    const el = document.getElementById('chat-attention-hopper');
    if (el) {
      el.classList.add('hopper-dismissed');
      setTimeout(() => el.remove(), 300);
    }
  }, 15000);
}

function highlightLastChatMessage() {
  // Remove any existing glow
  document.querySelectorAll('.chat-attention-glow').forEach(el => {
    // Unwrap: move children out and remove the span
    const parent = el.parentNode;
    while (el.firstChild) parent.insertBefore(el.firstChild, el);
    el.remove();
  });
  const stream = document.getElementById('canvas-stream');
  if (!stream) return;
  // Find the last .board-text element (the actual text content)
  const textEls = stream.querySelectorAll('.board-text');
  const lastText = textEls.length ? textEls[textEls.length - 1] : null;
  if (!lastText) return;
  // Find the last paragraph — split at <br><br>
  const html = lastText.innerHTML;
  const splitIdx = html.lastIndexOf('<br><br>');
  if (splitIdx >= 0) {
    // Wrap only the last paragraph in a glow span
    const before = html.slice(0, splitIdx + 8); // include the <br><br>
    const after = html.slice(splitIdx + 8);
    lastText.innerHTML = before + '<span class="chat-attention-glow">' + after + '</span>';
  } else {
    // Single paragraph — wrap the whole text
    lastText.innerHTML = '<span class="chat-attention-glow">' + html + '</span>';
  }
  // Scroll chat to show the glowing text
  lastText.scrollIntoView({ behavior: 'smooth', block: 'end' });
  // Dismiss glow when user focuses any input or clicks in the chat
  const dismissGlow = () => {
    document.querySelectorAll('.chat-attention-glow').forEach(el => {
      const parent = el.parentNode;
      while (el.firstChild) parent.insertBefore(el.firstChild, el);
      el.remove();
    });
    stream.removeEventListener('focusin', dismissGlow);
    stream.removeEventListener('click', dismissGlow);
  };
  stream.addEventListener('focusin', dismissGlow, { once: true });
  stream.addEventListener('click', dismissGlow, { once: true });
  // Auto-dismiss after 20 seconds
  setTimeout(dismissGlow, 20000);
}

function renderUserMessage(text, imageDataUrl) {
  const stream = $('#canvas-stream');
  const block = document.createElement('div');
  block.className = 'canvas-block board-response fade-in';
  block.dataset.type = 'user';
  let imgHtml = '';
  if (imageDataUrl) {
    imgHtml = `<div class="user-image-preview"><img src="${imageDataUrl}" alt="User image" /></div>`;
  }
  block.innerHTML = `<span class="response-label">You</span> <span class="response-text">${escapeHtml(text)}</span>${imgHtml}`;
  stream.appendChild(block);
  stream.scrollTop = stream.scrollHeight;
}

function renderAIError(message) {
  const isBilling = /credit|billing|balance/i.test(message);
  const icon = isBilling ? '💳' : '⚠';
  const title = isBilling ? 'API Credits Exhausted' : 'Something went wrong';
  const hint = isBilling
    ? 'The AI service needs more credits to continue. Please top up and retry.'
    : message;

  appendBlock('system', `
    <div class="error-card">
      <div class="error-card-header">
        <span class="error-card-icon">${icon}</span>
        <span class="error-card-title">${escapeHtml(title)}</span>
      </div>
      <div class="error-card-body">${escapeHtml(hint)}</div>
      <div class="error-card-actions">
        <button class="btn btn-primary" onclick="handleRetry()">Retry</button>
      </div>
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
  block.innerHTML = `<span class="heading-text">${escapeHtml(title)}</span>`;
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
      if (state.assessment.active) renderAssessmentQuestion(tag, 'mcq');
      else renderMCQTag(tag);
      break;
    case 'teaching-freetext':
      if (state.assessment.active) renderAssessmentQuestion(tag, 'freetext');
      else renderFreetextTag(tag);
      break;
    case 'teaching-confidence':
      if (state.assessment.active) renderAssessmentQuestion(tag, 'confidence');
      else renderConfidenceTag(tag);
      break;
    case 'teaching-agree-disagree':
      if (state.assessment.active) renderAssessmentQuestion(tag, 'agree-disagree');
      else renderAgreeDisagreeTag(tag);
      break;
    case 'teaching-fillblank':
      if (state.assessment.active) renderAssessmentQuestion(tag, 'fillblank');
      else renderFillBlankTag(tag);
      break;
    case 'teaching-spot-error':
      if (state.assessment.active) renderAssessmentQuestion(tag, 'spot-error');
      else renderSpotErrorTag(tag);
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
      if (state.assessment.active) renderAssessmentQuestion(tag, 'teachback');
      else renderTeachbackTag(tag);
      break;
    case 'teaching-board-draw': {
      const bdTitle = tag.attrs.title || 'Board';
      // Store raw commands for replay on reopen
      if (tag.content) {
        tag._boardDrawContent = tag.content;
      }
      openBoardDrawSpotlight(bdTitle, tag.content || null);
      if (!state.boardDraw.active) {
        // Non-streaming path (e.g. message history) — parse commands from tag content
        state.boardDraw.commandQueue = [];
        const bdLines = (tag.content || '').split('\n');
        for (const bdLine of bdLines) {
          const trimmed = bdLine.trim();
          if (!trimmed) continue;
          try { state.boardDraw.commandQueue.push(JSON.parse(trimmed)); } catch (e) {}
        }
      }
      // Commands (queued during streaming or parsed above) execute when canvas is ready
      state.boardDraw.active = true;
      break;
    }
    case 'teaching-widget': {
      const wTitle = tag.attrs.title || 'Interactive Widget';
      const wCode = tag.content || state.widget.code || '';
      openWidgetSpotlight(wTitle, wCode, state.replayMode);
      // Reset widget streaming state
      state.widget = { active: false, contentStartIdx: 0, complete: false, title: '', code: '' };
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
    // Assessment tags removed — backend now uses tools (handoff_to_assessment,
    // complete_assessment, handback_to_tutor) and emits ASSESSMENT_START/END SSE events.
  }

  // Track visual asset usage for engagement enforcement
  const _visualTags = new Set([
    'teaching-video', 'teaching-simulation', 'teaching-interactive',
    'teaching-image', 'teaching-board-draw', 'teaching-spotlight',
    'teaching-widget',
  ]);
  if (_visualTags.has(tag.name)) {
    state.lastVisualTurn = state.totalAssistantTurns;
    state.visualAssetCount++;
  }

  // Track assessment/interactive engagement (suppresses visual alert)
  const _engagementTags = new Set([
    'teaching-mcq', 'teaching-freetext', 'teaching-agree-disagree',
    'teaching-teachback', 'teaching-canvas',
    'teaching-notebook-step', 'teaching-notebook-comment',
  ]);
  if (_engagementTags.has(tag.name)) {
    state.lastEngagementTurn = state.totalAssistantTurns;
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
  // Extract just the video ID from any YouTube URL format
  const match = videoUrl.match(/(?:youtu\.be\/|v=|\/embed\/)([A-Za-z0-9_-]{11})/);
  if (match) {
    videoUrl = `https://www.youtube.com/embed/${match[1]}`;
  }
  // Safety: strip any query string or stray parameters after the video ID
  videoUrl = videoUrl.split('?')[0].split('&')[0];
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
      saveNotebookStepsToHistory();
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
// Assessment Spotlight — questions render inside spotlight panel
// ═══════════════════════════════════════════════════════════

function openAssessmentSpotlight() {
  const panel = $('#spotlight-panel');
  const content = $('#spotlight-content');
  const titleEl = $('#spotlight-title');
  const typeBadge = $('#spotlight-type-badge');
  if (!panel || !content) return;

  // Set spotlight header
  if (titleEl) titleEl.textContent = state.assessment.sectionTitle || 'Section Checkpoint';
  if (typeBadge) {
    typeBadge.textContent = 'Checkpoint';
    typeBadge.setAttribute('data-type', 'assessment');
    typeBadge.style.display = '';
  }

  // Hide close/fullscreen buttons during assessment
  const closeBtn = document.querySelector('.spotlight-close-btn');
  const fsBtn = document.querySelector('.spotlight-fullscreen-btn');
  if (closeBtn) closeBtn.style.display = 'none';
  if (fsBtn) fsBtn.style.display = 'none';

  // Render assessment container with progress indicator + empty question area
  const maxQ = state.assessment.maxQuestions || 5;
  content.innerHTML = `
    <div class="assessment-spotlight-container">
      <div class="assessment-progress">
        <div class="assessment-progress-bar">
          <div class="assessment-progress-fill" id="assessment-progress-fill" style="width: 0%"></div>
        </div>
        <div class="assessment-progress-text" id="assessment-progress-text">Question 0 of ${maxQ}</div>
      </div>
      <div class="assessment-question-area" id="assessment-question-area"></div>
    </div>
  `;

  // Activate spotlight
  panel.classList.add('stage-active');
  state.spotlightActive = true;
  state.spotlightInfo = { type: 'assessment', title: state.assessment.sectionTitle };
}

function renderAssessmentQuestion(tag, type) {
  const questionArea = $('#assessment-question-area');
  if (!questionArea) {
    // Spotlight not open (resilience) — try reopening
    if (state.assessment.active) {
      openAssessmentSpotlight();
      const retryArea = $('#assessment-question-area');
      if (!retryArea) {
        // Fallback to inline rendering
        console.warn('[Assessment] Could not open spotlight, falling back to inline');
        _renderInlineAssessmentFallback(tag, type);
        return;
      }
      return renderAssessmentQuestion(tag, type);
    }
    _renderInlineAssessmentFallback(tag, type);
    return;
  }

  // Increment question number and update progress
  state.assessment.questionNumber++;
  const qNum = state.assessment.questionNumber;
  const maxQ = state.assessment.maxQuestions || 5;

  const progressFill = $('#assessment-progress-fill');
  const progressText = $('#assessment-progress-text');
  if (progressFill) progressFill.style.width = `${(qNum / maxQ) * 100}%`;
  if (progressText) progressText.textContent = `Question ${qNum} of ${maxQ}`;

  // Fade out old question, render new one
  questionArea.style.opacity = '0';
  setTimeout(() => {
    questionArea.innerHTML = '';

    switch (type) {
      case 'mcq': renderAssessmentMCQ(tag, questionArea); break;
      case 'freetext': renderAssessmentFreetext(tag, questionArea); break;
      case 'agree-disagree': renderAssessmentAgreeDisagree(tag, questionArea); break;
      case 'confidence': renderAssessmentConfidence(tag, questionArea); break;
      case 'fillblank': renderAssessmentFillBlank(tag, questionArea); break;
      case 'spot-error': renderAssessmentSpotError(tag, questionArea); break;
      case 'teachback': renderAssessmentTeachback(tag, questionArea); break;
      default: renderAssessmentFreetext(tag, questionArea); break;
    }

    questionArea.style.opacity = '1';
  }, 200);
}

function _renderInlineAssessmentFallback(tag, type) {
  // Fall back to normal inline renderers if spotlight isn't available
  switch (type) {
    case 'mcq': renderMCQTag(tag); break;
    case 'freetext': renderFreetextTag(tag); break;
    case 'agree-disagree': renderAgreeDisagreeTag(tag); break;
    case 'confidence': renderConfidenceTag(tag); break;
    case 'fillblank': renderFillBlankTag(tag); break;
    case 'spot-error': renderSpotErrorTag(tag); break;
    case 'teachback': renderTeachbackTag(tag); break;
  }
}

// ── Assessment MCQ (no correctness feedback) ──
function renderAssessmentMCQ(tag, container) {
  const prompt = tag.attrs.prompt || tag.attrs.question || '';
  const options = [];

  // Parse <option> elements from content
  const optionRegex = /<option\s+value=(?:"([^"]*)"|'([^']*)')([^>]*)>([^<]*)<\/option>/g;
  let optMatch;
  while ((optMatch = optionRegex.exec(tag.content)) !== null) {
    options.push({
      value: optMatch[1] || optMatch[2],
      text: optMatch[4],
    });
  }

  // Pipe-separated fallback
  if (options.length === 0 && tag.attrs.options) {
    tag.attrs.options.split('|').forEach((text, i) => {
      options.push({ value: String.fromCharCode(97 + i), text: text.trim() });
    });
  }

  // Plain text lines fallback
  if (options.length === 0 && tag.content) {
    const lines = tag.content.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length >= 2) {
      lines.forEach((text, i) => {
        const cleaned = text.replace(/^[A-Da-d1-4][.):\s]+/, '').trim();
        options.push({ value: String.fromCharCode(97 + i), text: cleaned || text });
      });
    }
  }

  const mcqId = 'aq-' + generateId().slice(0, 8);
  // NOTE: No data-correct attribute in DOM — prevents student inspecting
  const optionsHtml = options.map(o => `
    <div class="mcq-option" data-value="${escapeAttr(o.value)}">
      <div class="mcq-radio"></div>
      <span>${renderMarkdownBasic(o.text)}</span>
    </div>
  `).join('');

  container.innerHTML = `
    ${prompt ? `<div class="ai-message">${renderMarkdownBasic(prompt)}</div>` : ''}
    <div class="mcq-options" id="${mcqId}">${optionsHtml}</div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${mcqId}" disabled>Submit</button>
    </div>
  `;

  setTimeout(() => {
    let selected = null;
    const allOpts = container.querySelectorAll(`#${mcqId} .mcq-option`);
    allOpts.forEach(opt => {
      opt.addEventListener('click', () => {
        allOpts.forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        selected = opt.dataset.value;
        const btn = container.querySelector(`#submit-${mcqId}`);
        if (btn) btn.disabled = false;
      });
    });

    const submitBtn = container.querySelector(`#submit-${mcqId}`);
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        if (!selected) return;
        // Highlight selected with accent (no green/red), dim others
        allOpts.forEach(o => {
          o.classList.add('submitted');
          o.style.pointerEvents = 'none';
        });
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitted';
        const selectedText = allOpts[Array.from(allOpts).findIndex(o => o.dataset.value === selected)]?.textContent?.trim();
        SessionManager.recordAssessment({
          type: 'mcq',
          question: prompt,
          options: options.map(o => o.text),
          studentAnswer: selectedText || '',
          correctAnswer: '',
          correct: null, // unknown to frontend
        });
        setTimeout(() => {
          sendStudentResponse(`[MCQ answer: ${selected}] ${selectedText || ''}`);
        }, 500);
      });
    }
  }, 50);
}

// ── Assessment Freetext (no draw mode in spotlight) ──
function renderAssessmentFreetext(tag, container) {
  const prompt = tag.attrs.prompt || '';
  const placeholder = tag.attrs.placeholder || 'Type your answer...';
  const ftId = 'aft-' + generateId().slice(0, 8);

  container.innerHTML = `
    ${prompt ? `<div class="ai-message">${renderMarkdownBasic(prompt)}</div>` : ''}
    <div class="text-input-area">
      <textarea class="text-input" id="${ftId}" placeholder="${escapeAttr(placeholder)}" style="padding-right:12px;"></textarea>
    </div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${ftId}">Submit</button>
    </div>
  `;

  setTimeout(() => {
    const submitBtn = container.querySelector(`#submit-${ftId}`);
    const textarea = container.querySelector(`#${ftId}`);
    if (submitBtn && textarea) {
      submitBtn.addEventListener('click', () => {
        const val = textarea.value.trim();
        if (!val) return;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitted';
        textarea.disabled = true;
        SessionManager.recordAssessment({
          type: 'freetext',
          question: prompt,
          studentAnswer: val,
          correct: null,
        });
        setTimeout(() => sendStudentResponse(val), 500);
      });
      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          submitBtn.click();
        }
      });
    }
  }, 50);
}

// ── Assessment Agree/Disagree ──
function renderAssessmentAgreeDisagree(tag, container) {
  const prompt = tag.attrs.prompt || '';
  const adId = 'aad-' + generateId().slice(0, 8);

  container.innerHTML = `
    ${prompt ? `<div class="ai-message">${renderMarkdownBasic(prompt)}</div>` : ''}
    <div class="agree-toggle" id="${adId}">
      <button class="agree-btn agree" data-value="agree">Agree</button>
      <button class="agree-btn disagree" data-value="disagree">Disagree</button>
    </div>
    <div class="text-input-area">
      <textarea class="text-input" id="${adId}-reason" placeholder="Explain your reasoning..." style="padding-right:12px;"></textarea>
    </div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${adId}" disabled>Submit</button>
    </div>
  `;

  setTimeout(() => {
    let choice = null;
    container.querySelectorAll(`#${adId} .agree-btn`).forEach(btn => {
      btn.addEventListener('click', () => {
        container.querySelectorAll(`#${adId} .agree-btn`).forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        choice = btn.dataset.value;
        const submitBtn = container.querySelector(`#submit-${adId}`);
        if (submitBtn) submitBtn.disabled = false;
      });
    });

    const submitBtn = container.querySelector(`#submit-${adId}`);
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        if (!choice) return;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitted';
        container.querySelectorAll(`#${adId} .agree-btn`).forEach(b => b.style.pointerEvents = 'none');
        const reason = container.querySelector(`#${adId}-reason`)?.value?.trim() || '';
        const reasonEl = container.querySelector(`#${adId}-reason`);
        if (reasonEl) reasonEl.disabled = true;
        SessionManager.recordAssessment({
          type: 'agree-disagree',
          question: prompt,
          studentAnswer: `${choice}: ${reason}`,
          correct: null,
        });
        setTimeout(() => sendStudentResponse(`[${choice}] ${reason}`), 500);
      });
    }
  }, 50);
}

// ── Assessment Confidence ──
function renderAssessmentConfidence(tag, container) {
  const prompt = tag.attrs.prompt || 'How confident are you?';
  const confId = 'acf-' + generateId().slice(0, 8);

  container.innerHTML = `
    <div class="confidence-container">
      <span class="confidence-label">${escapeHtml(prompt)}</span>
      <input type="range" class="confidence-slider" id="${confId}" min="0" max="100" value="50">
      <span class="confidence-value" id="${confId}-val">50%</span>
    </div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${confId}">Submit</button>
    </div>
  `;

  setTimeout(() => {
    const slider = container.querySelector(`#${confId}`);
    const valEl = container.querySelector(`#${confId}-val`);
    if (slider && valEl) {
      slider.addEventListener('input', () => {
        valEl.textContent = slider.value + '%';
      });
    }
    const submitBtn = container.querySelector(`#submit-${confId}`);
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitted';
        slider.disabled = true;
        SessionManager.recordAssessment({
          type: 'confidence',
          question: prompt,
          studentAnswer: slider.value + '%',
          correct: null,
        });
        setTimeout(() => sendStudentResponse(`[Confidence: ${slider.value}%]`), 500);
      });
    }
  }, 50);
}

// ── Assessment Fill-in-the-Blank ──
function renderAssessmentFillBlank(tag, container) {
  const fbId = 'afb-' + generateId().slice(0, 8);
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

  container.innerHTML = `
    <div class="blank-container">${content}</div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${fbId}">Submit</button>
    </div>
  `;

  setTimeout(() => {
    const submitBtn = container.querySelector(`#submit-${fbId}`);
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        const answers = [];
        for (let i = 1; i <= 10; i++) {
          const el = container.querySelector(`#${fbId}-${i}`);
          if (el) {
            answers.push(`blank${i}: ${el.value}`);
            el.disabled = true;
          }
        }
        if (answers.length === 0) return;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitted';
        SessionManager.recordAssessment({
          type: 'fillblank',
          question: tag.content,
          studentAnswer: answers.join(', '),
          correct: null,
        });
        setTimeout(() => sendStudentResponse(`[Fill-in-blank] ${answers.join(', ')}`), 500);
      });
    }
  }, 50);
}

// ── Assessment Spot-the-Error ──
function renderAssessmentSpotError(tag, container) {
  const quote = tag.attrs.quote || '';
  const prompt = tag.attrs.prompt || 'What\'s wrong with this?';
  const seId = 'ase-' + generateId().slice(0, 8);

  container.innerHTML = `
    <h3 style="font-size:15px;font-weight:600;margin-bottom:12px;">Spot the Error</h3>
    <div class="error-quote">
      <div class="error-quote-label">Statement</div>
      ${escapeHtml(quote)}
    </div>
    <div class="ai-message">${renderMarkdownBasic(prompt)}</div>
    <div class="text-input-area">
      <textarea class="text-input" id="${seId}" placeholder="The flaw is..." style="padding-right:12px;"></textarea>
    </div>
    <div class="strip-actions">
      <button class="btn btn-primary" id="submit-${seId}">Submit</button>
    </div>
  `;

  setTimeout(() => {
    const submitBtn = container.querySelector(`#submit-${seId}`);
    const textarea = container.querySelector(`#${seId}`);
    if (submitBtn && textarea) {
      submitBtn.addEventListener('click', () => {
        const val = textarea.value.trim();
        if (!val) return;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitted';
        textarea.disabled = true;
        SessionManager.recordAssessment({
          type: 'spot-error',
          question: `${quote} — ${prompt}`,
          studentAnswer: val,
          correct: null,
        });
        setTimeout(() => sendStudentResponse(`[Spot error] ${val}`), 500);
      });
      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          submitBtn.click();
        }
      });
    }
  }, 50);
}

// ── Assessment Teachback ──
function renderAssessmentTeachback(tag, container) {
  const prompt = tag.attrs.prompt || 'Explain this concept in your own words.';
  const tbId = 'atb-' + generateId().slice(0, 8);

  container.innerHTML = `
    <div class="teaching-teachback-card" style="background:transparent;border:none;padding:0;">
      <div class="teachback-header">
        <span class="teachback-icon">&#128172;</span>
        <span>Teach it back</span>
      </div>
      <div class="ai-message">${renderMarkdownBasic(prompt)}</div>
      <div class="text-input-area">
        <textarea class="text-input teachback-textarea" id="${tbId}" placeholder="Explain as if teaching a friend..." style="padding-right:12px;"></textarea>
      </div>
      <div class="strip-actions">
        <button class="btn btn-primary" id="submit-${tbId}">Submit</button>
      </div>
    </div>
  `;

  setTimeout(() => {
    const submitBtn = container.querySelector(`#submit-${tbId}`);
    const textarea = container.querySelector(`#${tbId}`);
    if (submitBtn && textarea) {
      submitBtn.addEventListener('click', () => {
        const val = textarea.value.trim();
        if (!val) return;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitted';
        textarea.disabled = true;
        SessionManager.recordAssessment({
          type: 'teachback',
          question: prompt,
          studentAnswer: val,
          correct: null,
        });
        setTimeout(() => sendStudentResponse(`[Teachback] ${val}`), 500);
      });
    }
  }, 50);
}

// ═══════════════════════════════════════════════════════════
// Module 12: Interactive Tag Renderers
// ═══════════════════════════════════════════════════════════

function renderMCQTag(tag) {
  const prompt = tag.attrs.prompt || tag.attrs.question || '';
  const options = [];

  // Detect if a correct answer was explicitly specified
  const hasCorrectAttr = tag.attrs.correct !== undefined || tag.attrs.answer !== undefined;
  const isProbe = !hasCorrectAttr;

  // Strategy 1: Parse <option> elements from content
  const optionRegex = /<option\s+value=(?:"([^"]*)"|'([^']*)')([^>]*)>([^<]*)<\/option>/g;
  let optMatch;
  let hasInlineCorrect = false;
  while ((optMatch = optionRegex.exec(tag.content)) !== null) {
    const optCorrect = optMatch[3].includes('correct');
    if (optCorrect) hasInlineCorrect = true;
    options.push({
      value: optMatch[1] || optMatch[2],
      correct: optCorrect,
      text: optMatch[4],
    });
  }

  // Strategy 2: Pipe-separated "options" attribute (e.g., options="A|B|C|D")
  if (options.length === 0 && tag.attrs.options) {
    const correctIdx = hasCorrectAttr ? parseInt(tag.attrs.correct || tag.attrs.answer, 10) : -1;
    tag.attrs.options.split('|').forEach((text, i) => {
      options.push({
        value: String.fromCharCode(97 + i),
        correct: correctIdx >= 0 && (i === correctIdx || i === correctIdx - 1),
        text: text.trim(),
      });
    });
  }

  // Strategy 3: Plain text content lines (one option per non-empty line)
  if (options.length === 0 && tag.content) {
    const lines = tag.content.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length >= 2) {
      const correctIdx = hasCorrectAttr ? parseInt(tag.attrs.correct || tag.attrs.answer, 10) : -1;
      lines.forEach((text, i) => {
        const cleaned = text.replace(/^[A-Da-d1-4][.):\s]+/, '').trim();
        options.push({
          value: String.fromCharCode(97 + i),
          correct: correctIdx >= 0 && (i === correctIdx || i === correctIdx - 1),
          text: cleaned || text,
        });
      });
    }
  }

  const isProbeMode = isProbe && !hasInlineCorrect && !options.some(o => o.correct);

  const mcqId = 'mcq-' + generateId().slice(0, 8);
  let optionsHtml = options.map(o => `
    <div class="mcq-option" data-value="${escapeAttr(o.value)}" data-correct="${o.correct}">
      <div class="mcq-radio"></div>
      <span>${renderMarkdownBasic(o.text)}</span>
    </div>
  `).join('');

  if (isProbeMode) {
    appendBlock('mcq', `
      ${prompt ? `<div class="probe-prompt">${renderMarkdownBasic(prompt)}</div>` : ''}
      <div class="mcq-options mcq-probe" id="${mcqId}">${optionsHtml}</div>
    `, { interactive: true });

    setTimeout(() => {
      $$(`#${mcqId} .mcq-option`).forEach(opt => {
        opt.addEventListener('click', () => {
          $$(`#${mcqId} .mcq-option`).forEach(o => {
            o.classList.remove('selected');
            o.style.pointerEvents = 'none';
            o.style.opacity = '0.55';
          });
          opt.classList.add('selected', 'probe-selected');
          opt.style.opacity = '1';
          const selectedText = opt.textContent?.trim();
          SessionManager.recordAssessment({
            type: 'probe',
            question: prompt,
            options: options.map(o => o.text),
            studentAnswer: selectedText || '',
            correctAnswer: '',
            correct: null,
          });
          setTimeout(() => {
            sendStudentResponse(`[MCQ answer: ${opt.dataset.value}] ${selectedText || ''}`);
          }, 500);
        });
      });
    }, 50);
  } else {
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
}

function renderFreetextTag(tag) {
  const prompt = tag.attrs.prompt || '';
  const placeholder = tag.attrs.placeholder || 'Type your answer...';
  const ftId = 'ft-' + generateId().slice(0, 8);

  appendBlock('freetext', `
    ${prompt ? `<div class="ai-message">${renderMarkdownBasic(prompt)}</div>` : ''}
    <div class="freetext-input-container" id="${ftId}-container">
      <div class="input-mode-toggle">
        <button class="mode-btn active" data-mode="text" title="Type answer">${SVG_TEXT} Type</button>
        <button class="mode-btn" data-mode="draw" title="Draw answer">${SVG_DRAW} Draw</button>
      </div>
      <div class="text-mode" id="${ftId}-text-mode">
        <div class="text-input-area">
          ${buildTextInput(ftId, placeholder, `submitFreetext('${ftId}')`)}
        </div>
      </div>
      <div class="draw-mode" id="${ftId}-draw-mode" style="display:none;"></div>
    </div>
  `, { interactive: true });

  setTimeout(() => {
    initFreetextToggle(ftId, prompt);
    bindInputHandlers(ftId, `submitFreetext('${ftId}')`);
  }, 50);
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

        html += `
          <div class="plan-topic ${topicStatus}">
            <div class="plan-topic-indicator">${topicIcon}</div>
            <div class="plan-topic-text">
              <div class="plan-topic-title">${escapeHtml(topicTitle)}</div>
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

  // Cancel pending fallback timer for ANY tool call — more content is coming
  if (state.pendingFallbackTimer) {
    clearTimeout(state.pendingFallbackTimer);
    state.pendingFallbackTimer = null;
  }

  // Internal/background tools run silently — no UI indicators
  const silentTools = [
    'spawn_agent', 'check_agents', 'advance_topic', 'delegate_teaching',
    'update_student_model', 'upsert_concept_note', 'log_knowledge',
    'request_board_image', 'reset_plan',
  ];
  if (silentTools.includes(toolName)) {
    return;
  }

  disablePreviousInteractive();

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

  // Show a "generating" indicator between tool rounds so the UI isn't blank
  if (state.isStreaming && !$('#streaming-indicator')) {
    showStreamingIndicator();
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

// Save current notebook steps into the matching spotlightHistory entry before clearing
function saveNotebookStepsToHistory() {
  if (state.spotlightInfo?.type !== 'notebook' || state.notebookSteps.length === 0) return;
  const title = state.spotlightInfo.title;
  const entry = [...state.spotlightHistory].reverse().find(
    e => e.type === 'notebook' && e.title === title
  );
  if (entry) {
    entry.notebookSteps = [...state.notebookSteps];
  }
}

async function showSpotlight(tag, options = {}) {
  // In replay mode, only render the reference card — don't open the spotlight
  if (state.replayMode) {
    const type = tag.attrs?.type || tag.name?.replace('teaching-', '') || 'spotlight';
    const title = tag.attrs?.title || tag.attrs?.label || type;
    if (!options.skipReference) {
      appendSpotlightReference(type, title, tag);
    }
    return;
  }

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
      saveNotebookStepsToHistory();
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
  state.spotlightOpenedAtTurn = state.totalAssistantTurns;
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

// ── Restore notebook steps from saved state (for session resume / reopen) ──
function restoreNotebookSteps() {
  const info = state.spotlightInfo;
  if (!info || info.type !== 'notebook') return;
  const stepsEl = $(`#${info.notebookId}-steps`);
  if (!stepsEl) return;

  for (const step of state.notebookSteps) {
    if (step.type === 'comment') {
      const commentEl = document.createElement('div');
      commentEl.className = 'tutor-says';
      commentEl.innerHTML = renderLatex(escapeHtml(step.content || ''));
      stepsEl.appendChild(commentEl);
      const lineEl = document.createElement('div');
      lineEl.className = 'chalk-line';
      stepsEl.appendChild(lineEl);
    } else {
      const n = step.n || 0;
      const circled = CIRCLED_NUMS[n - 1] || String(n);
      const isCorrection = step.type === 'correction';
      const isStudent = step.author === 'student';
      const renderedMath = renderLatex(step.math || step.content || '');
      const renderedAnnotation = renderLatex(escapeHtml(step.annotation || ''));

      const stepEl = document.createElement('div');
      stepEl.className = `step${isCorrection ? ' correction' : ''}${isStudent ? ' student-step' : ''}`;
      stepEl.dataset.stepN = n;
      stepEl.innerHTML = `
        <div class="step-label"><span class="step-num">${circled}</span> ${renderedAnnotation}</div>
        <div class="step-math">${renderedMath}</div>
      `;
      if (isStudent && step.hasDrawing && step.drawingDataUrl) {
        const img = document.createElement('img');
        img.src = step.drawingDataUrl;
        img.className = 'student-drawing-preview';
        stepEl.appendChild(img);
      }
      stepsEl.appendChild(stepEl);
      const lineEl = document.createElement('div');
      lineEl.className = 'chalk-line';
      stepsEl.appendChild(lineEl);
    }
  }
  stepsEl.scrollTop = stepsEl.scrollHeight;
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

  state.notebookSteps.push({ n, content, hasDrawing: !!drawingDataUrl, drawingDataUrl: drawingDataUrl || null, author: 'student', type: 'step' });

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
  const typeIcons = { video: '▶', simulation: '⚗', notebook: '📓', image: '🖼', 'board-draw': '✎', widget: '⚡' };
  const icon = typeIcons[type] || '◆';

  const historyEntry = { id: refId, type, title, tag: reopenTag };
  if (type === 'board-draw' && reopenTag._boardDrawContent) {
    historyEntry.boardDrawContent = reopenTag._boardDrawContent;
  }
  if (type === 'widget' && reopenTag._widgetCode) {
    historyEntry.widgetCode = reopenTag._widgetCode;
  }
  state.spotlightHistory.push(historyEntry);

  const stream = $('#canvas-stream');
  const cardHtml = `
    <div class="spotlight-ref-card" data-type="${escapeAttr(type)}" onclick="reopenSpotlight('${refId}')">
      <span class="spotlight-ref-icon">${icon}</span>
      <span class="spotlight-ref-title">${escapeHtml(title)}</span>
      <span class="spotlight-ref-hint">Click to reopen</span>
    </div>
  `;
  const block = document.createElement('div');
  block.className = 'canvas-block fade-in';
  block.dataset.type = 'spotlight-ref';
  block.innerHTML = `<div class="block-card">${cardHtml}</div>`;

  // Insert BEFORE the last interactive input block so cards don't displace the text input
  const lastInteractive = stream.querySelector('.canvas-block[data-interactive="true"]:last-of-type');
  if (lastInteractive && !lastInteractive.dataset.resolved) {
    stream.insertBefore(block, lastInteractive);
  } else {
    stream.appendChild(block);
  }
  stream.scrollTop = stream.scrollHeight;
}

window.reopenSpotlight = function(refId) {
  const entry = state.spotlightHistory.find(e => e.id === refId);
  if (!entry) return;

  if (entry.type === 'video' && entry.tag.lessonId !== undefined) {
    openVideoInSpotlight(entry.tag.lessonId, entry.tag.start, entry.tag.end, entry.tag.label, { skipReference: true });
  } else if (entry.type === 'board-draw' && entry.boardDrawContent) {
    // Replay board-draw with stored commands
    const bdTitle = entry.title || 'Board';
    openBoardDrawSpotlight(bdTitle, entry.boardDrawContent, { skipReference: true });
    state.boardDraw.commandQueue = [];
    const bdLines = entry.boardDrawContent.split('\n');
    for (const ln of bdLines) {
      const trimmed = ln.trim();
      if (!trimmed) continue;
      try { state.boardDraw.commandQueue.push(JSON.parse(trimmed)); } catch (e) {}
    }
    state.boardDraw.active = true;
  } else if (entry.type === 'widget' && entry.widgetCode) {
    openWidgetSpotlight(entry.title, entry.widgetCode, false, { skipReference: true });
  } else if (entry.type === 'notebook') {
    // Reopen notebook and restore saved steps from history entry
    const savedSteps = entry.notebookSteps || [];
    showSpotlight(entry.tag, { skipReference: true });
    if (savedSteps.length > 0) {
      state.notebookSteps = savedSteps;
      setTimeout(() => restoreNotebookSteps(), 100);
    }
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
  // Prevent student from closing spotlight during assessment
  if (state.assessment.active && state.spotlightInfo?.type === 'assessment' && !options.agentInitiated) {
    const panel = $('#spotlight-panel');
    if (panel) {
      // Show brief "hang in there" notice
      let notice = panel.querySelector('.assessment-close-notice');
      if (!notice) {
        notice = document.createElement('div');
        notice.className = 'assessment-close-notice';
        notice.textContent = 'Almost done — hang in there!';
        panel.style.position = 'relative';
        panel.appendChild(notice);
        setTimeout(() => notice.remove(), 2000);
      }
    }
    return;
  }

  const wasVideo = state.spotlightInfo?.type === 'video';
  const wasBoardDraw = state.spotlightInfo?.type === 'board-draw';
  const wasSim = state.spotlightInfo?.type === 'simulation';
  const prevTitle = state.spotlightInfo?.title || '';
  const prevSimId = state.spotlightInfo?.id || state.activeSimulation?.simId || null;

  const panel = $('#spotlight-panel');
  if (panel) panel.classList.remove('stage-active');

  const content = $('#spotlight-content');

  // Clean up widget iframe bridge listener before clearing content
  if (state.spotlightInfo?.type === 'widget') {
    const wIframe = content?.querySelector('.widget-iframe');
    if (wIframe?._bridgeCleanup) wIframe._bridgeCleanup();
  }

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
    saveNotebookStepsToHistory();
    if (state.notebookCleanup) { state.notebookCleanup(); state.notebookCleanup = null; }
    state.notebookSteps = [];
  }

  if (wasBoardDraw) bdCleanup();

  state.spotlightActive = false;
  state.spotlightInfo = null;
  dismissChatHopper();

  // Store close event as context for the student's next message (no auto-trigger)
  if (!options.agentInitiated) {
    if (wasVideo) {
      state.pendingSpotlightEvent = 'Student closed the video "' + prevTitle + '"';
    } else if (wasBoardDraw) {
      state.pendingSpotlightEvent = 'Student viewed the board drawing "' + prevTitle + '"';
    }
  }

  // Track recently closed simulation so tutor knows it can be reopened
  if (wasSim && prevSimId) {
    state.recentlyClosedSim = { id: prevSimId, title: prevTitle, closedAtTurn: state.totalAssistantTurns };
  }
};

// ═══════════════════════════════════════════════════════════
// Module 18: User Actions & Handlers
// ═══════════════════════════════════════════════════════════

async function sendStudentResponse(text) {
  if (state.isStreaming) return;
  dismissChatHopper();

  const sc = state.scribble;

  // If scribble has annotations, open the review overlay so student can preview
  if (sc.active && sc.dirty) {
    const promptEl = document.getElementById('scribble-review-prompt');
    if (promptEl) promptEl.value = text;
    scribbleShowReview();
    return;
  }

  const snapParts = buildSpotlightSnapshotParts();
  if (snapParts.length > 0) {
    renderUserMessage(text);
    streamADK([{ type: 'text', text }, ...snapParts]);
  } else {
    streamADK(text);
  }
}

function dismissChatHopper() {
  const el = document.getElementById('chat-attention-hopper');
  if (el) {
    el.classList.add('hopper-dismissed');
    setTimeout(() => el.remove(), 300);
  }
}

// sendCanvasDrawing removed — canvas drawing now handled via notebook workspace

window.submitFreetext = async function(inputId) {
  const el = $(`#${inputId}`);
  if (!el) return;
  const val = el.value.trim();
  const img = _pendingImages[inputId];
  if (!val && !img) return;

  if (img) {
    const parts = [];
    parts.push({ type: 'image', source: { type: 'base64', media_type: img.mediaType, data: img.base64 } });
    parts.push({ type: 'text', text: val || '[Student sent an image]' });
    const snapParts = buildSpotlightSnapshotParts();
    parts.push(...snapParts);
    const thumbUrl = `data:${img.mediaType};base64,${img.base64}`;
    delete _pendingImages[inputId];
    const preview = $(`#${inputId}-img-preview`);
    if (preview) preview.style.display = 'none';
    renderUserMessage(val || '[Image]', thumbUrl);
    streamADK(parts);
  } else {
    sendStudentResponse(val);
  }
};

window.toggleScribbleMode = function() {
  // Scribble feature removed
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

function updateSessionCost(costCents) {
  const costEl = $('#session-cost');
  if (!costEl) return;
  const dollars = costCents / 100;
  costEl.textContent = dollars < 0.01 ? '<$0.01' : `$${dollars.toFixed(2)}`;
  costEl.title = `Estimated LLM cost: $${dollars.toFixed(4)} (${costCents.toFixed(1)}¢)`;
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
  // Extract math expressions FIRST to protect KaTeX SVG from markdown transforms
  const mathSlots = [];
  if (typeof katex !== 'undefined') {
    text = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, math) => {
      const i = mathSlots.length;
      try { mathSlots.push(katex.renderToString(math.trim(), { displayMode: true, throwOnError: false })); }
      catch { mathSlots.push(match); }
      return `\x00M${i}\x00`;
    });
    text = text.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, (match, math) => {
      const i = mathSlots.length;
      try { mathSlots.push(katex.renderToString(math.trim(), { displayMode: false, throwOnError: false })); }
      catch { mathSlots.push(match); }
      return `\x00M${i}\x00`;
    });
  }
  // Apply markdown transforms safely (no KaTeX HTML to corrupt)
  text = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code style="background:var(--bg-elevated);padding:1px 4px;border-radius:3px;font-family:var(--font-mono);font-size:13px;">$1</code>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
  // Restore math expressions
  text = text.replace(/\x00M(\d+)\x00/g, (_, i) => mathSlots[parseInt(i)]);
  return text;
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

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return days === 1 ? 'Yesterday' : `${days}d ago`;
  }

  let activeHtml = '';
  for (const s of active) {
    const headline = escapeHtml(s.headline || `Session ${s.number || '?'}`);
    const dur = s.durationSec ? `${Math.round(s.durationSec / 60)} min` : '';
    const ago = timeAgo(s.startedAt);
    const meta = [dur, ago].filter(Boolean).join(' · ');
    activeHtml += `
      <div class="dash-session-row" onclick="Router.navigate('/session/${escapeAttr(s.sessionId)}')">
        <div class="dash-session-dot active"></div>
        <div class="dash-session-info">
          <div class="dash-session-title">${headline}</div>
          <div class="dash-session-meta">${meta}</div>
        </div>
        <span class="dash-session-arrow">&rsaquo;</span>
      </div>
    `;
  }
  activeContainer.innerHTML = activeHtml;

  let completedHtml = '';
  for (const s of completed) {
    const headline = escapeHtml(s.headline || `Session ${s.number || '?'}`);
    const dur = s.durationSec ? `${Math.round(s.durationSec / 60)} min` : '';
    const ago = timeAgo(s.startedAt);
    const meta = [dur, ago].filter(Boolean).join(' · ');
    completedHtml += `
      <div class="dash-session-row">
        <div class="dash-session-dot done"></div>
        <div class="dash-session-info">
          <div class="dash-session-title">${headline}</div>
          <div class="dash-session-meta">${meta}</div>
        </div>
        <span class="dash-session-arrow">&rsaquo;</span>
      </div>
    `;
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

function showLandingPanel() {
  UIHints.removeAll();
  const lp = $('#landing-panel');
  if (lp) lp.style.display = 'block';
  $('#login-panel').style.display = 'none';
  $('#setup-panel').style.display = 'none';
  $('#teaching-layout').classList.add('hidden');
  document.body.style.overflow = 'auto';
  document.body.style.height = 'auto';
}

function showLoginPanel() {
  UIHints.removeAll();
  const lp = $('#landing-panel');
  if (lp) lp.style.display = 'none';
  $('#login-panel').style.display = 'flex';
  $('#setup-panel').style.display = 'none';
  $('#teaching-layout').classList.add('hidden');
  document.body.style.overflow = 'hidden';
  document.body.style.height = '100vh';
}

function updateCourseCardSelection(courseId) {
  document.querySelectorAll('.dash-course-card').forEach(card => {
    const cid = card.dataset.course;
    card.classList.toggle('selected', cid === String(courseId));
  });
}

function showSetupPanel() {
  UIHints.removeAll();
  const user = AuthManager.getUser();
  if (!user) return Router.navigate('/', { replace: true });

  state.studentName = user.name;
  state.userEmail = user.email;

  const firstName = user.name.split(' ')[0];
  const greeting = $('#setup-greeting');
  if (greeting) greeting.textContent = `Hey ${firstName}`;

  // Update nav user pill
  const avatar = $('#dash-avatar');
  if (avatar) avatar.textContent = user.name.charAt(0).toUpperCase();
  const userName = $('#dash-user-name');
  if (userName) userName.textContent = firstName;

  const lp = $('#landing-panel');
  if (lp) lp.style.display = 'none';
  $('#login-panel').style.display = 'none';
  $('#setup-panel').style.display = 'flex';
  $('#teaching-layout').classList.add('hidden');
  disconnectAgentEvents();
  if (timerInterval) clearInterval(timerInterval);
  document.body.style.overflow = 'hidden';
  document.body.style.height = '100vh';

  // Enable/disable buttons and fetch sessions for selected course
  const courseId = parseInt($('#course-id')?.value);
  const startBtn = $('#btn-start-session');
  const newBtn = $('#btn-new-session');
  if (startBtn) startBtn.disabled = !courseId;
  if (newBtn) newBtn.disabled = !courseId;
  if (courseId) fetchAndRenderSessions(state.studentName, courseId);

  // Highlight selected course card
  updateCourseCardSelection(courseId);
}

function handleAuthExpired() {
  AuthManager.clearAuth();
  Router.navigate('/login', { replace: true });
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

  // ─── Tab switching ─────────────────────────────────────
  const tabs = $$('.auth-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      tabs.forEach(t => t.classList.toggle('active', t === tab));
      $('#auth-signin').style.display = target === 'signin' ? '' : 'none';
      $('#auth-signup').style.display = target === 'signup' ? '' : 'none';
      // Clear status messages on tab switch
      if (statusEl) { statusEl.textContent = ''; statusEl.className = 'setup-status'; }
      const signupStatus = $('#signup-status');
      if (signupStatus) { signupStatus.textContent = ''; signupStatus.className = 'setup-status'; }
    });
  });

  // ─── Login handler ─────────────────────────────────────
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
      Router.navigate('/dashboard');
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

  // ─── Signup handler ────────────────────────────────────
  const signupNameInput = $('#signup-name');
  const signupEmailInput = $('#signup-email');
  const signupPasswordInput = $('#signup-password');
  const signupBtn = $('#btn-signup');
  const signupStatus = $('#signup-status');

  async function doSignup() {
    const name = signupNameInput.value.trim();
    const email = signupEmailInput.value.trim();
    const password = signupPasswordInput.value;
    if (!name || !email || !password) {
      signupStatus.textContent = 'Please fill in all fields.';
      signupStatus.className = 'setup-status error';
      return;
    }
    if (password.length < 6) {
      signupStatus.textContent = 'Password must be at least 6 characters.';
      signupStatus.className = 'setup-status error';
      return;
    }
    signupBtn.disabled = true;
    signupStatus.textContent = 'Creating account...';
    signupStatus.className = 'setup-status';
    try {
      await AuthManager.signup(name, email, password);
      signupStatus.textContent = '';
      Router.navigate('/dashboard');
    } catch (e) {
      signupStatus.textContent = e.message || 'Signup failed';
      signupStatus.className = 'setup-status error';
    } finally {
      signupBtn.disabled = false;
    }
  }

  if (signupBtn) signupBtn.addEventListener('click', doSignup);
  if (signupPasswordInput) signupPasswordInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') doSignup(); });
  if (signupEmailInput) signupEmailInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') signupPasswordInput.focus(); });
  if (signupNameInput) signupNameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') signupEmailInput.focus(); });
}

async function initSetup() {
  const courseIdInput = $('#course-id');
  const apiUrlInput = $('#api-url');
  const startBtn = $('#btn-start-session');
  const newBtn = $('#btn-new-session');

  state.apiUrl = apiUrlInput?.value?.trim() || window.location.origin;

  // ─── Login form ────────────────────────────────────────
  initLoginForm();

  // ─── Logout ────────────────────────────────────────────
  $('#btn-logout')?.addEventListener('click', () => {
    AuthManager.logout();
    state.studentName = '';
    state.userEmail = '';
    $('#session-list-panel')?.classList.add('hidden');
    $('#session-first-time')?.classList.add('hidden');
    Router.navigate('/');
  });

  // ─── Landing page CTA wiring ─────────────────────────────
  const lpSignin = $('#lp-signin');
  const lpGetStarted = $('#lp-getstarted');
  const lpCtaStart = $('#lp-cta-start');
  const lpCtaHow = $('#lp-cta-how');
  const lpCourseCard = $('#lp-course-card');

  if (lpSignin) lpSignin.addEventListener('click', () => Router.navigate('/login'));
  if (lpGetStarted) lpGetStarted.addEventListener('click', () => Router.navigate('/login'));
  if (lpCtaStart) lpCtaStart.addEventListener('click', () => Router.navigate('/login'));
  if (lpCtaHow) lpCtaHow.addEventListener('click', () => {
    const howSection = document.getElementById('lp-how');
    if (howSection) howSection.scrollIntoView({ behavior: 'smooth' });
  });
  if (lpCourseCard) lpCourseCard.addEventListener('click', () => Router.navigate('/login'));

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

  // ─── Dashboard chips — prefill input, don't auto-start ───
  document.querySelectorAll('.dash-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const intent = chip.dataset.intent || chip.textContent.trim();
      const intentInput = $('#student-intent-first');
      if (intentInput) {
        intentInput.value = intent;
        intentInput.focus();
      }
    });
  });

  // ─── Dashboard input Enter key ────────────────────────────
  const dashInput = $('#student-intent-first');
  if (dashInput) {
    dashInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        startNewSession(state.studentName, parseInt(courseIdInput.value), dashInput.value.trim());
      }
    });
  }

  // ─── Dashboard course card click ──────────────────────────
  document.querySelectorAll('.dash-course-card').forEach(card => {
    card.addEventListener('click', () => {
      const cid = card.dataset.course;
      if (!cid || cid === 'byo') return; // BYO is disabled
      if (courseIdInput) {
        courseIdInput.value = cid;
        courseIdInput.dispatchEvent(new Event('change'));
      }
      updateCourseCardSelection(parseInt(cid));
    });
  });

  $('#btn-back')?.addEventListener('click', () => {
    Router.navigate('/dashboard');
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

    Router.navigate('/session/' + state.sessionId, { skipHandler: true });

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

    if (location.pathname !== '/session/' + sessionData.sessionId) {
      Router.navigate('/session/' + sessionData.sessionId, { skipHandler: true });
    }

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

    // Restore engagement tracking counters
    const tc = sessionData.teachingCounters || {};
    state.totalAssistantTurns = tc.totalAssistantTurns || 0;
    state.lastVisualTurn = tc.lastVisualTurn || 0;
    state.visualAssetCount = tc.visualAssetCount || 0;
    state.lastEngagementTurn = tc.lastEngagementTurn || 0;

    // Restore scribble strokes from MongoDB
    if (sessionData.scribbleStrokes && sessionData.scribbleStrokes.length > 0) {
      state.scribble.strokes = sessionData.scribbleStrokes;
    }

    // Restore assessment state (UI tracking only — backend owns agent routing)
    if (sessionData.assessment && sessionData.assessment.active) {
      state.assessment.active = true;
      state.assessment.sectionTitle = sessionData.assessment.sectionTitle || '';
      state.assessment.concepts = sessionData.assessment.concepts || [];
      state.assessment.questionNumber = sessionData.assessment.questionNumber || 0;
      state.assessment.maxQuestions = sessionData.assessment.maxQuestions || 5;
      // Reopen assessment spotlight after a brief delay (DOM needs to be ready)
      setTimeout(() => openAssessmentSpotlight(), 300);
    }
    if (sessionData.conceptNotes) {
      state.assessment.conceptNotes = sessionData.conceptNotes;
    }

    // Save active spotlight info for restoration after canvas rebuild
    const savedSpotlight = sessionData.activeSpotlight || null;

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

    // Reopen the spotlight that was active when session was saved
    if (savedSpotlight && savedSpotlight.active && savedSpotlight.info) {
      const sInfo = savedSpotlight.info;
      const matchingEntry = [...(state.spotlightHistory)].reverse().find(
        e => e.type === sInfo.type && e.title === sInfo.title
      );
      if (matchingEntry) {
        setTimeout(() => reopenSpotlight(matchingEntry.id), 200);
      }
    }

    // Redraw scribble strokes after canvas rebuild
    if (state.scribble.strokes.length > 0) {
      setTimeout(() => scribbleRedraw(), 300);
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

    // Backend handles routing — if assessment was active, it will resume automatically
    const trigger = `[SYSTEM] The student "${state.studentName}" is returning to continue session ${state.checkpoint.sessionCount}. They have completed ${completed} sections. Current position: lesson ${state.checkpoint.currentLessonId}, section ${state.checkpoint.currentSectionIndex}.${intentClause} Welcome them back briefly, state where you're picking up, and continue teaching following the current script. Do NOT ask what they want to do — you are the teacher, take charge.`;

    await streamADK(trigger, true, true);
  } catch (err) {
    setStatus(`Failed to resume: ${err.message}`, 'error');
    Router.navigate('/dashboard', { replace: true });
  }
};

// ── Canvas Rebuild (Session Resume) ──────────────────────────────

function rebuildCanvasFromTranscript(transcript) {
  const stream = document.getElementById('canvas-stream');
  // Keep the welcome header that showTeachingLayout already added

  // Prevent spotlights from opening during replay (only render ref cards)
  state.replayMode = true;
  const savedHistory = state.spotlightHistory || [];
  state.spotlightHistory = [];

  for (const msg of transcript) {
    if (msg.role === 'assistant') {
      renderHistoricalTutorMessage(msg.content);
    } else if (msg.role === 'user') {
      const c = msg.content || '';
      if (c.startsWith('[SYSTEM]') || c.startsWith('[') || c.startsWith('The student')) {
        continue;
      }
      renderHistoricalStudentMessage(c);
    }
  }

  // Merge saved history data (boardDrawContent, widgetCode) into replay-generated entries.
  // Replay entries have DOM-matching IDs; saved entries may have richer data.
  for (const saved of savedHistory) {
    const match = state.spotlightHistory.find(
      e => e.type === saved.type && e.title === saved.title
    );
    if (match) {
      if (saved.boardDrawContent && !match.boardDrawContent) match.boardDrawContent = saved.boardDrawContent;
      if (saved.widgetCode && !match.widgetCode) match.widgetCode = saved.widgetCode;
    }
  }
  state.replayMode = false;

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
  document.title = courseMap.title + ' — Capacity';
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

  setTimeout(() => { initDragDrop(); }, 100);
}

// ═══════════════════════════════════════════════════════════
// Module 22: Scribble Annotations on Canvas Stream
// ═══════════════════════════════════════════════════════════

function scribbleInit() {
  const sc = state.scribble;
  sc.canvas = document.getElementById('scribble-overlay');
  if (!sc.canvas) return;
  sc.ctx = sc.canvas.getContext('2d');

  const stream = document.getElementById('canvas-stream');
  const col = document.getElementById('canvas-column');
  if (!stream || !col) return;

  function resize() {
    const rect = stream.getBoundingClientRect();
    const colRect = col.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    sc.canvas.style.top = (rect.top - colRect.top) + 'px';
    sc.canvas.style.left = (rect.left - colRect.left) + 'px';
    sc.canvas.style.width = rect.width + 'px';
    sc.canvas.style.height = rect.height + 'px';
    sc.canvas.width = rect.width * dpr;
    sc.canvas.height = rect.height * dpr;
    sc.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    scribbleRedraw();
  }

  resize();
  window.addEventListener('resize', resize);
  new ResizeObserver(resize).observe(stream);
  stream.addEventListener('scroll', () => scribbleRedraw());

  // Drawing handlers
  let drawing = false;
  let lastX = 0, lastY = 0;

  function getPos(e) {
    const rect = sc.canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      canvasX: clientX - rect.left,
      canvasY: clientY - rect.top,
      absY: clientY - rect.top + stream.scrollTop,
    };
  }

  sc.canvas.addEventListener('mousedown', (e) => {
    if (!sc.active) return;
    e.preventDefault();
    drawing = true;
    const pos = getPos(e);
    lastX = pos.canvasX;
    lastY = pos.canvasY;
    sc.currentStroke = {
      points: [{ x: pos.canvasX, y: pos.absY }],
      color: sc.color,
      width: sc.lineWidth,
      isHighlighter: sc.isHighlighter,
      scrollBase: stream.scrollTop,
    };
    if (!sc.beforeSnapshot && !sc.capturePromise) {
      scribbleCaptureBeforeSnapshot();
    }
  });

  sc.canvas.addEventListener('mousemove', (e) => {
    if (!drawing || !sc.active) return;
    e.preventDefault();
    const pos = getPos(e);
    const ctx = sc.ctx;
    ctx.save();
    if (sc.isHighlighter) {
      ctx.globalAlpha = 0.3;
      ctx.strokeStyle = sc.color;
      ctx.lineWidth = 16;
    } else if (sc.color === '#1a1d2e') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.strokeStyle = 'rgba(0,0,0,1)';
      ctx.lineWidth = 20;
    } else {
      ctx.strokeStyle = sc.color;
      ctx.lineWidth = sc.lineWidth;
    }
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(pos.canvasX, pos.canvasY);
    ctx.stroke();
    ctx.restore();
    lastX = pos.canvasX;
    lastY = pos.canvasY;
    if (sc.currentStroke) {
      sc.currentStroke.points.push({ x: pos.canvasX, y: pos.absY });
    }
  });

  function stopDraw() {
    if (!drawing) return;
    drawing = false;
    if (sc.currentStroke && sc.currentStroke.points.length > 1) {
      sc.strokes.push(sc.currentStroke);
      sc.dirty = true;
      scribblePersist();
      scribbleSyncDoneBtn();
    }
    sc.currentStroke = null;
  }
  sc.canvas.addEventListener('mouseup', stopDraw);
  sc.canvas.addEventListener('mouseleave', stopDraw);

  // Touch support
  sc.canvas.addEventListener('touchstart', (e) => {
    if (!sc.active) return;
    e.preventDefault();
    drawing = true;
    const pos = getPos(e);
    lastX = pos.canvasX;
    lastY = pos.canvasY;
    sc.currentStroke = {
      points: [{ x: pos.canvasX, y: pos.absY }],
      color: sc.color,
      width: sc.lineWidth,
      isHighlighter: sc.isHighlighter,
      scrollBase: stream.scrollTop,
    };
    if (!sc.beforeSnapshot && !sc.capturePromise) scribbleCaptureBeforeSnapshot();
  }, { passive: false });
  sc.canvas.addEventListener('touchmove', (e) => {
    if (!drawing || !sc.active) return;
    e.preventDefault();
    const pos = getPos(e);
    const ctx = sc.ctx;
    ctx.save();
    if (sc.isHighlighter) { ctx.globalAlpha = 0.3; ctx.strokeStyle = sc.color; ctx.lineWidth = 16; }
    else if (sc.color === '#1a1d2e') { ctx.globalCompositeOperation = 'destination-out'; ctx.strokeStyle = 'rgba(0,0,0,1)'; ctx.lineWidth = 20; }
    else { ctx.strokeStyle = sc.color; ctx.lineWidth = sc.lineWidth; }
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath(); ctx.moveTo(lastX, lastY); ctx.lineTo(pos.canvasX, pos.canvasY); ctx.stroke();
    ctx.restore();
    lastX = pos.canvasX; lastY = pos.canvasY;
    if (sc.currentStroke) sc.currentStroke.points.push({ x: pos.canvasX, y: pos.absY });
  }, { passive: false });
  sc.canvas.addEventListener('touchend', stopDraw);

  // Toolbar
  const toolbar = document.getElementById('scribble-toolbar');
  if (toolbar) {
    toolbar.querySelectorAll('.scribble-btn[data-color]').forEach(btn => {
      btn.addEventListener('click', () => {
        toolbar.querySelectorAll('.scribble-btn[data-color]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const c = btn.dataset.color;
        if (c === 'eraser') {
          sc.color = '#1a1d2e';
          sc.lineWidth = 20;
          sc.isHighlighter = false;
        } else if (btn.dataset.highlight) {
          sc.color = c;
          sc.lineWidth = 16;
          sc.isHighlighter = true;
        } else {
          sc.color = c;
          sc.lineWidth = 3;
          sc.isHighlighter = false;
        }
      });
    });
    const clearBtn = document.getElementById('scribble-clear');
    if (clearBtn) clearBtn.addEventListener('click', scribbleClear);
    const toggleBtn = document.getElementById('scribble-toggle-vis');
    if (toggleBtn) toggleBtn.addEventListener('click', scribbleToggleVisibility);
    const closeBtn = document.getElementById('scribble-close');
    if (closeBtn) closeBtn.addEventListener('click', () => scribbleSetActive(false));
  }

  // "Done" button in toolbar → opens review
  const doneBtn = document.getElementById('scribble-done');
  if (doneBtn) doneBtn.addEventListener('click', scribbleShowReview);

  // Review overlay bindings
  const reviewSend = document.getElementById('scribble-review-send');
  if (reviewSend) reviewSend.addEventListener('click', scribbleSendFromReview);
  const reviewClose = document.getElementById('scribble-review-close');
  if (reviewClose) reviewClose.addEventListener('click', () => {
    document.getElementById('scribble-review')?.classList.add('hidden');
  });

  scribbleRestore();
}

function scribbleSetActive(on) {
  const sc = state.scribble;
  sc.active = on;
  if (sc.canvas) sc.canvas.classList.toggle('active', on);
  const toolbar = document.getElementById('scribble-toolbar');
  if (toolbar) toolbar.classList.toggle('hidden', !on);
  if (!on) {
    sc.beforeSnapshot = null;
    sc.capturePromise = null;
    const reviewEl = document.getElementById('scribble-review');
    if (reviewEl) reviewEl.classList.add('hidden');
  }
  // Sync all scribble toggle buttons in input boxes + placeholders
  document.querySelectorAll('.input-scribble-btn').forEach(b => b.classList.toggle('active', on));
  document.querySelectorAll('#canvas-stream .text-input').forEach(input => {
    input.placeholder = on ? 'Draw on canvas, then send...' : 'Type your response...';
  });
}

function scribbleRedraw() {
  const sc = state.scribble;
  if (!sc.ctx || !sc.canvas) return;
  const stream = document.getElementById('canvas-stream');
  if (!stream) return;
  const scrollTop = stream.scrollTop;
  const w = parseFloat(sc.canvas.style.width);
  const h = parseFloat(sc.canvas.style.height);
  sc.ctx.clearRect(0, 0, w, h);
  for (const stroke of sc.strokes) {
    if (stroke.points.length < 2) continue;
    const ctx = sc.ctx;
    ctx.save();
    if (stroke.isHighlighter) { ctx.globalAlpha = 0.3; ctx.lineWidth = 16; }
    else { ctx.lineWidth = stroke.width || 3; }
    if (stroke.color === '#1a1d2e') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.strokeStyle = 'rgba(0,0,0,1)';
      ctx.lineWidth = 20;
    } else {
      ctx.strokeStyle = stroke.color;
    }
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    let first = true;
    for (const pt of stroke.points) {
      const screenY = pt.y - scrollTop;
      if (screenY < -50 || screenY > h + 50) { first = true; continue; }
      if (first) { ctx.moveTo(pt.x, screenY); first = false; }
      else ctx.lineTo(pt.x, screenY);
    }
    ctx.stroke();
    ctx.restore();
  }
}

function scribbleSyncDoneBtn() {
  const btn = document.getElementById('scribble-done');
  if (btn) btn.classList.toggle('hidden', !state.scribble.dirty);
}

function scribbleClear() {
  const sc = state.scribble;
  sc.strokes = [];
  sc.dirty = false;
  sc.beforeSnapshot = null;
  sc.capturePromise = null;
  scribbleRedraw();
  scribblePersist();
  scribbleSyncDoneBtn();
}

async function scribbleShowReview() {
  const sc = state.scribble;
  if (!sc.dirty) return;
  if (sc.capturePromise) await sc.capturePromise;

  const afterUrl = await scribbleBuildAfterImage();
  if (!sc.beforeSnapshot || !afterUrl) return;

  const reviewEl = document.getElementById('scribble-review');
  const beforeImg = document.getElementById('scribble-thumb-before');
  const afterImg = document.getElementById('scribble-thumb-after');
  const promptEl = document.getElementById('scribble-review-prompt');

  beforeImg.src = sc.beforeSnapshot;
  afterImg.src = afterUrl;
  if (promptEl) promptEl.value = '';
  reviewEl.classList.remove('hidden');
}

async function scribbleSendFromReview() {
  const sc = state.scribble;
  if (!sc.dirty || state.isStreaming) return;
  const parts = await scribbleBuildMessageParts();
  if (parts.length === 0) return;

  const promptEl = document.getElementById('scribble-review-prompt');
  const extraNote = promptEl ? promptEl.value.trim() : '';
  const textPart = extraNote || '[Student sent an annotation on the canvas]';

  renderUserMessage(extraNote || '[Annotation]');
  streamADK([{ type: 'text', text: textPart }, ...parts]);

  const reviewEl = document.getElementById('scribble-review');
  if (reviewEl) reviewEl.classList.add('hidden');
  scribbleClear();
}

function scribblePersist() {
  try {
    const key = 'scribble_' + (state.sessionId || 'default');
    const data = state.scribble.strokes.map(s => ({
      points: s.points,
      color: s.color,
      width: s.width,
      isHighlighter: s.isHighlighter,
    }));
    sessionStorage.setItem(key, JSON.stringify(data));
  } catch (e) {}
}

function scribbleRestore() {
  try {
    const key = 'scribble_' + (state.sessionId || 'default');
    const raw = sessionStorage.getItem(key);
    if (!raw) return;
    state.scribble.strokes = JSON.parse(raw);
    scribbleRedraw();
  } catch (e) {}
}

function scribbleToggleVisibility() {
  const sc = state.scribble;
  sc.visible = !sc.visible;
  if (sc.canvas) sc.canvas.classList.toggle('hidden-strokes', !sc.visible);
  const btn = document.getElementById('scribble-toggle-vis');
  if (btn) btn.textContent = sc.visible ? '👁' : '👁‍🗨';
}

function scribbleCaptureBeforeSnapshot() {
  const sc = state.scribble;
  const stream = document.getElementById('canvas-stream');
  if (!stream || typeof html2canvas === 'undefined') return;
  sc.canvas.style.display = 'none';
  sc.capturePromise = html2canvas(stream, {
    backgroundColor: '#0f1117',
    scale: 1,
    useCORS: true,
    logging: false,
    width: stream.clientWidth,
    height: stream.clientHeight,
    scrollX: 0,
    scrollY: -stream.scrollTop,
    windowWidth: stream.clientWidth,
    windowHeight: stream.clientHeight,
  }).then(canvas => {
    sc.beforeSnapshot = canvas.toDataURL('image/png');
    sc.canvas.style.display = '';
  }).catch(() => {
    sc.canvas.style.display = '';
  });
}

function scribbleBuildAfterImage() {
  const sc = state.scribble;
  if (!sc.beforeSnapshot || !sc.canvas) return null;
  try {
    const w = parseInt(sc.canvas.style.width);
    const h = parseInt(sc.canvas.style.height);
    const offscreen = document.createElement('canvas');
    offscreen.width = w;
    offscreen.height = h;
    const ctx = offscreen.getContext('2d');
    const img = new Image();
    return new Promise((resolve) => {
      img.onload = () => {
        ctx.drawImage(img, 0, 0, w, h);
        ctx.drawImage(sc.canvas, 0, 0, sc.canvas.width, sc.canvas.height, 0, 0, w, h);
        resolve(offscreen.toDataURL('image/png'));
      };
      img.onerror = () => resolve(null);
      img.src = sc.beforeSnapshot;
    });
  } catch (e) {
    return null;
  }
}

async function scribbleBuildMessageParts() {
  const sc = state.scribble;
  if (!sc.dirty || sc.strokes.length === 0) return [];

  if (sc.capturePromise) await sc.capturePromise;

  const parts = [];
  if (sc.beforeSnapshot) {
    const beforeB64 = sc.beforeSnapshot.split(',')[1];
    parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: beforeB64 } });
    parts.push({ type: 'text', text: '[IMAGE 1 — BEFORE] The chat canvas as the student was viewing it.' });

    const afterUrl = await scribbleBuildAfterImage();
    if (afterUrl) {
      const afterB64 = afterUrl.split(',')[1];
      parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: afterB64 } });
      parts.push({ type: 'text', text: '[IMAGE 2 — AFTER] Same view with student annotations (circles, highlights, arrows). Compare with IMAGE 1 to see what the student marked.' });
    }
  } else {
    try {
      const overlayUrl = sc.canvas.toDataURL('image/png');
      const overlayB64 = overlayUrl.split(',')[1];
      parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: overlayB64 } });
      parts.push({ type: 'text', text: '[Student drew annotations on the chat canvas — circles, highlights, or arrows marking areas of interest on recent content.]' });
    } catch (e) {}
  }

  sc.dirty = false;
  return parts;
}

// ═══════════════════════════════════════════════════════════
// Module 22b: Drag & Drop file upload on canvas
// ═══════════════════════════════════════════════════════════

function initDragDrop() {
  const col = document.getElementById('canvas-column');
  if (!col) return;
  let dragCounter = 0;
  let overlay = null;

  function showOverlay() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.className = 'drop-zone-overlay';
    overlay.innerHTML = '<span>Drop image here</span>';
    col.appendChild(overlay);
  }
  function hideOverlay() {
    if (overlay) { overlay.remove(); overlay = null; }
  }

  col.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    if (dragCounter === 1) showOverlay();
  });
  col.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) { dragCounter = 0; hideOverlay(); }
  });
  col.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });
  col.addEventListener('drop', (e) => {
    e.preventDefault();
    dragCounter = 0;
    hideOverlay();
    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    if (!file.type.startsWith('image/') && file.type !== 'application/pdf') return;
    handleDroppedFile(file);
  });
}

function handleDroppedFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = reader.result;
    const mediaType = file.type || 'image/png';
    const base64 = dataUrl.split(',')[1];

    // Find the most recent active text input
    const stream = document.getElementById('canvas-stream');
    if (!stream) return;
    const activeInput = stream.querySelector(
      '.canvas-block[data-interactive="true"]:not([data-resolved]) .text-input'
    );
    if (activeInput) {
      const inputId = activeInput.id;
      _pendingImages[inputId] = { base64, mediaType };
      const preview = $(`#${inputId}-img-preview`);
      const thumb = $(`#${inputId}-img-thumb`);
      if (preview && thumb) {
        thumb.src = dataUrl;
        preview.style.display = 'flex';
      }
    } else {
      // No active input — send as standalone image message
      const parts = [
        { type: 'image', source: { type: 'base64', media_type: mediaType, data: base64 } },
        { type: 'text', text: '[Student uploaded an image]' },
      ];
      renderUserMessage('[Image]', dataUrl);
      streamADK(parts);
    }
  };
  reader.readAsDataURL(file);
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
const BD_MIN_FONT_SCALE = 1.4;  // Minimum font scaling to keep text readable

function bdInit(canvasEl, voiceEl) {
  const bd = state.boardDraw;
  bd.canvas = canvasEl;
  bd.ctx = canvasEl.getContext('2d', { willReadFrequently: true });
  bd.voiceEl = voiceEl;
  bd.cancelFlag = false;
  bd.currentH = BD_INITIAL_H;
  bd.DPR = Math.min(window.devicePixelRatio || 1, 3);
  bd.studentDrawing = false;
  bd.studentColor = '#22ee66';
  bd.studentStrokeW = 2.5;
  bdResizeCanvas();
  bdDrawGrid();
  bdInitStudentDrawing(canvasEl);
  bdInitToolbar();
  // Start processing commands that were queued during streaming
  if (bd.commandQueue.length > 0 && !bd.isProcessing) {
    bdProcessQueue();
  }
}

function bdInitToolbar() {
  const toolbar = document.getElementById('bd-toolbar');
  if (!toolbar) return;
  const bd = state.boardDraw;
  toolbar.querySelectorAll('.bd-tool-btn[data-color]').forEach(btn => {
    btn.addEventListener('click', () => {
      toolbar.querySelectorAll('.bd-tool-btn[data-color]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const color = btn.dataset.color;
      if (color === 'eraser') {
        bd.studentColor = '#1a1d2e';
        bd.studentStrokeW = 12;
      } else {
        bd.studentColor = color;
        bd.studentStrokeW = 2.5;
      }
    });
  });
}

function bdInitStudentDrawing(canvasEl) {
  const bd = state.boardDraw;
  let drawing = false;
  let lastX = 0, lastY = 0;

  function getPos(e) {
    const rect = canvasEl.getBoundingClientRect();
    const scaleX = canvasEl.width / (bd.DPR * rect.width);
    const scaleY = canvasEl.height / (bd.DPR * rect.height);
    if (e.touches) {
      return { x: (e.touches[0].clientX - rect.left) * scaleX, y: (e.touches[0].clientY - rect.top) * scaleY };
    }
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }

  function startDraw(e) {
    e.preventDefault();
    drawing = true;
    const pos = getPos(e);
    lastX = pos.x;
    lastY = pos.y;
    bd.studentDrawing = true;
  }

  function doDraw(e) {
    if (!drawing) return;
    e.preventDefault();
    const pos = getPos(e);
    const ctx = bd.ctx;
    if (!ctx) return;
    ctx.save();
    ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
    ctx.strokeStyle = bd.studentColor;
    ctx.lineWidth = bd.studentStrokeW;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    ctx.restore();
    lastX = pos.x;
    lastY = pos.y;
  }

  function stopDraw() {
    drawing = false;
  }

  canvasEl.addEventListener('mousedown', startDraw);
  canvasEl.addEventListener('mousemove', doDraw);
  canvasEl.addEventListener('mouseup', stopDraw);
  canvasEl.addEventListener('mouseleave', stopDraw);
  canvasEl.addEventListener('touchstart', startDraw, { passive: false });
  canvasEl.addEventListener('touchmove', doDraw, { passive: false });
  canvasEl.addEventListener('touchend', stopDraw);
}

window.bdClearStudentDrawing = function() {
  const bd = state.boardDraw;
  if (!bd.canvas || !bd.ctx) return;
  bd.ctx.save();
  bd.ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
  bd.ctx.fillStyle = '#1a1d2e';
  bd.ctx.fillRect(0, 0, bd.canvas.width / bd.DPR, bd.canvas.height / bd.DPR);
  bd.ctx.restore();
  bdDrawGrid();
  bd.studentDrawing = false;
  // Re-run tutor commands (without animation) from rawContent or spotlightHistory
  const raw = bd.rawContent
    || (state.spotlightHistory.find(e => e.type === 'board-draw' && e.boardDrawContent) || {}).boardDrawContent;
  if (raw) {
    const cmds = [];
    for (const ln of raw.split('\n')) {
      const t = ln.trim();
      if (!t) continue;
      try { cmds.push(JSON.parse(t)); } catch (e) {}
    }
    bdReplayCommandsInstant(cmds);
  }
  // Re-capture tutor snapshot after clearing student work
  try { bd.tutorSnapshot = bd.canvas.toDataURL('image/png'); } catch (e) {}
};

window.bdSendDrawing = function() {
  bdCaptureAndSend();
};

function bdResizeCanvas() {
  const bd = state.boardDraw;
  if (!bd.canvas) return;
  const wrap = bd.canvas.parentElement;
  if (!wrap) return;
  const w = wrap.clientWidth;
  bd.scale = w / BD_VIRTUAL_W;
  const actualW = w;
  // Fill available container height, but allow growth beyond if content needs it
  const containerH = wrap.clientHeight;
  const scaledH = bd.currentH * bd.scale;
  const actualH = Math.max(scaledH, containerH);
  let oldData = null;
  if (bd.ctx && bd.canvas.width && bd.canvas.height) {
    oldData = bd.ctx.getImageData(0, 0, bd.canvas.width, bd.canvas.height);
  }
  bd.canvas.width = actualW * bd.DPR;
  bd.canvas.height = actualH * bd.DPR;
  bd.canvas.style.width = actualW + 'px';
  bd.canvas.style.height = actualH + 'px';
  bd.ctx = bd.canvas.getContext('2d', { willReadFrequently: true });
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
  const fontScale = Math.max(s, s * BD_MIN_FONT_SCALE);
  const fs = (size || 22) * fontScale;
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

// LaTeX to readable Unicode text for canvas rendering (avoids SVG foreignObject which taints canvas)
const _LATEX_GREEK = {
  alpha:'α',beta:'β',gamma:'γ',delta:'δ',epsilon:'ε',zeta:'ζ',eta:'η',theta:'θ',
  iota:'ι',kappa:'κ',lambda:'λ',mu:'μ',nu:'ν',xi:'ξ',pi:'π',rho:'ρ',sigma:'σ',
  tau:'τ',upsilon:'υ',phi:'φ',chi:'χ',psi:'ψ',omega:'ω',
  Gamma:'Γ',Delta:'Δ',Theta:'Θ',Lambda:'Λ',Xi:'Ξ',Pi:'Π',Sigma:'Σ',
  Upsilon:'Υ',Phi:'Φ',Psi:'Ψ',Omega:'Ω',varepsilon:'ε',varphi:'φ',
};
const _LATEX_SYMS = {
  infty:'∞',partial:'∂',nabla:'∇',hbar:'ℏ',ell:'ℓ',forall:'∀',exists:'∃',
  in:'∈',notin:'∉',subset:'⊂',supset:'⊃',cup:'∪',cap:'∩',
  times:'×',cdot:'·',pm:'±',mp:'∓',leq:'≤',geq:'≥',neq:'≠',approx:'≈',
  equiv:'≡',propto:'∝',sim:'∼',ll:'≪',gg:'≫',
  rightarrow:'→',leftarrow:'←',Rightarrow:'⇒',Leftarrow:'⇐',
  leftrightarrow:'↔',uparrow:'↑',downarrow:'↓',
  int:'∫',sum:'∑',prod:'∏',sqrt:'√',langle:'⟨',rangle:'⟩',
  dagger:'†',otimes:'⊗',oplus:'⊕',circ:'∘',bullet:'•',star:'⋆',
  ldots:'…',cdots:'⋯',vdots:'⋮',ddots:'⋱',
  Re:'ℜ',Im:'ℑ',aleph:'ℵ',wp:'℘',emptyset:'∅',
  land:'∧',lor:'∨',neg:'¬',angle:'∠',triangle:'△',
  prime:'′',
};
const _LATEX_SUP = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹',
  '+':'⁺','-':'⁻','=':'⁼','(':'⁽',')':'⁾','n':'ⁿ','i':'ⁱ','*':'*','T':'ᵀ',
};
const _LATEX_SUB = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉',
  '+':'₊','-':'₋','=':'₌','(':'₍',')':'₎','a':'ₐ','e':'ₑ','i':'ᵢ','j':'ⱼ',
  'k':'ₖ','n':'ₙ','o':'ₒ','p':'ₚ','r':'ᵣ','s':'ₛ','t':'ₜ','u':'ᵤ','v':'ᵥ','x':'ₓ',
};

function latexToUnicode(tex) {
  let s = tex;
  // \text{...} → plain text
  s = s.replace(/\\text\{([^}]*)\}/g, '$1');
  s = s.replace(/\\mathrm\{([^}]*)\}/g, '$1');
  s = s.replace(/\\textbf\{([^}]*)\}/g, '$1');
  s = s.replace(/\\mathbf\{([^}]*)\}/g, '$1');
  s = s.replace(/\\operatorname\{([^}]*)\}/g, '$1');
  // \frac{a}{b} → a/b
  s = s.replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, '($1)/($2)');
  // \sqrt{x} → √(x), \sqrt[n]{x} → ⁿ√(x)
  s = s.replace(/\\sqrt\[([^\]]*)\]\{([^}]*)\}/g, (_, n, body) => (_LATEX_SUP[n] || n) + '√(' + body + ')');
  s = s.replace(/\\sqrt\{([^}]*)\}/g, '√($1)');
  // \vec{x} → x⃗, \hat{x} → x̂, \bar{x} → x̄, \dot{x} → ẋ, \tilde{x} → x̃
  s = s.replace(/\\vec\{([^}]*)\}/g, '$1\u20D7');
  s = s.replace(/\\hat\{([^}]*)\}/g, '$1\u0302');
  s = s.replace(/\\bar\{([^}]*)\}/g, '$1\u0304');
  s = s.replace(/\\dot\{([^}]*)\}/g, '$1\u0307');
  s = s.replace(/\\tilde\{([^}]*)\}/g, '$1\u0303');
  // Ket/Bra notation
  s = s.replace(/\\ket\{([^}]*)\}/g, '|$1⟩');
  s = s.replace(/\\bra\{([^}]*)\}/g, '⟨$1|');
  s = s.replace(/\\braket\{([^}]*)\}\{([^}]*)\}/g, '⟨$1|$2⟩');
  s = s.replace(/\\langle/g, '⟨');
  s = s.replace(/\\rangle/g, '⟩');
  // Superscripts: ^{...} or ^x
  s = s.replace(/\^\{([^}]*)\}/g, (_, inner) => {
    return inner.split('').map(ch => _LATEX_SUP[ch] || ch).join('');
  });
  s = s.replace(/\^([a-zA-Z0-9+\-*])/g, (_, ch) => _LATEX_SUP[ch] || '^' + ch);
  // Subscripts: _{...} or _x
  s = s.replace(/_\{([^}]*)\}/g, (_, inner) => {
    return inner.split('').map(ch => _LATEX_SUB[ch] || ch).join('');
  });
  s = s.replace(/_([a-zA-Z0-9])/g, (_, ch) => _LATEX_SUB[ch] || '_' + ch);
  // Greek letters
  for (const [cmd, sym] of Object.entries(_LATEX_GREEK)) {
    s = s.replace(new RegExp('\\\\' + cmd + '(?![a-zA-Z])', 'g'), sym);
  }
  // Symbols
  for (const [cmd, sym] of Object.entries(_LATEX_SYMS)) {
    s = s.replace(new RegExp('\\\\' + cmd + '(?![a-zA-Z])', 'g'), sym);
  }
  // Matrix environments: \begin{pmatrix}...\end{pmatrix} etc.
  s = s.replace(/\\begin\{([pbBvV]?)matrix\}([\s\S]*?)\\end\{\1matrix\}/g, (_, bracket, body) => {
    const brk = { p: ['(', ')'], b: ['[', ']'], B: ['{', '}'], v: ['|', '|'], V: ['‖', '‖'], '': ['', ''] };
    const [l, r] = brk[bracket] || ['(', ')'];
    const rows = body.split('\\\\').map(row => row.split('&').map(c => c.trim()).join('  '));
    return l + rows.join(' ; ') + r;
  });
  // Common remaining commands
  s = s.replace(/\\left\s*/g, '');
  s = s.replace(/\\right\s*/g, '');
  s = s.replace(/\\big\s*/g, '');
  s = s.replace(/\\Big\s*/g, '');
  s = s.replace(/\\bigg\s*/g, '');
  s = s.replace(/\\Bigg\s*/g, '');
  s = s.replace(/\\,/g, ' ');
  s = s.replace(/\\;/g, ' ');
  s = s.replace(/\\!/g, '');
  s = s.replace(/\\quad/g, '  ');
  s = s.replace(/\\qquad/g, '    ');
  s = s.replace(/\\\\/g, '\n');
  // Strip remaining backslash commands (e.g. \displaystyle)
  s = s.replace(/\\[a-zA-Z]+/g, '');
  // Clean up braces and extra spaces
  s = s.replace(/[{}]/g, '');
  s = s.replace(/\s{2,}/g, ' ');
  return s.trim();
}

async function bdAnimLatex(latex, x, y, color, size) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const c = BD_COLORS[color] || color || BD_COLORS.white;
  const fontScale = Math.max(s, s * BD_MIN_FONT_SCALE);
  const fs = (size || 24) * fontScale;
  bdExpandIfNeeded(y + (size || 24) * 2);

  const text = latexToUnicode(latex);
  bd.ctx.font = `italic ${fs}px 'CMU Serif', 'Times New Roman', Georgia, serif`;
  bd.ctx.fillStyle = c;

  // Progressive reveal: draw characters left-to-right
  const chars = [...text];
  const totalW = bd.ctx.measureText(text).width;
  const delay = Math.max(12, Math.min(40, 600 / chars.length));
  let drawn = '';
  for (let i = 0; i < chars.length; i++) {
    if (bd.cancelFlag) break;
    drawn += chars[i];
    // Clear previous partial draw and redraw
    const prevW = i > 0 ? bd.ctx.measureText(drawn.slice(0, -1)).width : 0;
    bd.ctx.fillStyle = c;
    bd.ctx.fillText(chars[i], x * s + prevW, y * s);
    await bdSleep(delay);
  }
}

async function bdAnimMatrix(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const rows = cmd.rows || [];
  if (rows.length === 0) return;
  const nRows = rows.length;
  const nCols = Math.max(...rows.map(r => r.length));
  const fontScale = Math.max(s, s * BD_MIN_FONT_SCALE);
  const fs = (cmd.size || 22) * fontScale;
  const c = BD_COLORS[cmd.color] || cmd.color || BD_COLORS.white;
  const font = `italic ${fs}px 'CMU Serif', 'Times New Roman', Georgia, serif`;
  bd.ctx.font = font;

  const cellPadX = 12 * s;
  const cellPadY = 8 * s;
  const colWidths = [];
  for (let col = 0; col < nCols; col++) {
    let maxW = 0;
    for (let row = 0; row < nRows; row++) {
      const entry = latexToUnicode(String((rows[row] || [])[col] || ''));
      maxW = Math.max(maxW, bd.ctx.measureText(entry).width);
    }
    colWidths.push(maxW);
  }
  const rowH = fs + cellPadY;
  const totalW = colWidths.reduce((a, b) => a + b, 0) + (nCols - 1) * cellPadX;
  const totalH = nRows * rowH;
  const bracketW = 8 * s;
  const ox = (cmd.x || 0) * s;
  const oy = (cmd.y || 0) * s;
  bdExpandIfNeeded((cmd.y || 0) + totalH / s + 20);

  const bracket = cmd.bracket || 'round';
  bdChalkStyle(cmd.color, 2);
  if (bracket === 'round' || bracket === 'paren') {
    const midY = oy + totalH / 2;
    const halfH = totalH / 2 + 4 * s;
    bd.ctx.beginPath();
    bd.ctx.moveTo(ox + bracketW, oy - 4 * s);
    bd.ctx.quadraticCurveTo(ox, midY, ox + bracketW, oy + totalH + 4 * s);
    bd.ctx.stroke();
    const rx = ox + bracketW + totalW + cellPadX;
    bd.ctx.beginPath();
    bd.ctx.moveTo(rx, oy - 4 * s);
    bd.ctx.quadraticCurveTo(rx + bracketW, midY, rx, oy + totalH + 4 * s);
    bd.ctx.stroke();
  } else if (bracket === 'square') {
    const lx = ox;
    const rx2 = ox + bracketW * 2 + totalW + cellPadX;
    bd.ctx.beginPath();
    bd.ctx.moveTo(lx + bracketW, oy - 4 * s);
    bd.ctx.lineTo(lx, oy - 4 * s);
    bd.ctx.lineTo(lx, oy + totalH + 4 * s);
    bd.ctx.lineTo(lx + bracketW, oy + totalH + 4 * s);
    bd.ctx.stroke();
    bd.ctx.beginPath();
    bd.ctx.moveTo(rx2 - bracketW, oy - 4 * s);
    bd.ctx.lineTo(rx2, oy - 4 * s);
    bd.ctx.lineTo(rx2, oy + totalH + 4 * s);
    bd.ctx.lineTo(rx2 - bracketW, oy + totalH + 4 * s);
    bd.ctx.stroke();
  } else if (bracket === 'pipe') {
    bd.ctx.beginPath();
    bd.ctx.moveTo(ox, oy - 4 * s); bd.ctx.lineTo(ox, oy + totalH + 4 * s);
    bd.ctx.stroke();
    const rx3 = ox + bracketW + totalW + cellPadX;
    bd.ctx.beginPath();
    bd.ctx.moveTo(rx3 + bracketW, oy - 4 * s); bd.ctx.lineTo(rx3 + bracketW, oy + totalH + 4 * s);
    bd.ctx.stroke();
  }
  bdClearShadow();

  const startX = ox + bracketW + 2 * s;
  for (let row = 0; row < nRows; row++) {
    let cx = startX;
    const cy = oy + row * rowH + fs * 0.85;
    for (let col = 0; col < nCols; col++) {
      if (bd.cancelFlag) return;
      const entry = latexToUnicode(String((rows[row] || [])[col] || ''));
      const entryW = bd.ctx.measureText(entry).width;
      const colCenter = cx + colWidths[col] / 2;
      bd.ctx.fillStyle = c;
      bd.ctx.font = font;
      bd.ctx.fillText(entry, colCenter - entryW / 2, cy);
      cx += colWidths[col] + cellPadX;
      await bdSleep(Math.max(15, 80 / nCols));
    }
  }
}

async function bdAnimBrace(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const x = (cmd.x || 0) * s;
  const y1 = (cmd.y1 || 0) * s;
  const y2 = (cmd.y2 || 0) * s;
  const dir = cmd.dir === 'right' ? 1 : -1;
  const w = (cmd.w || 10) * s * dir;
  const midY = (y1 + y2) / 2;
  bdExpandIfNeeded(Math.max(cmd.y1 || 0, cmd.y2 || 0));
  bdChalkStyle(cmd.color, cmd.lw || 2);
  bd.ctx.beginPath();
  bd.ctx.moveTo(x, y1);
  bd.ctx.quadraticCurveTo(x + w, y1, x + w, midY);
  bd.ctx.stroke();
  bd.ctx.beginPath();
  bd.ctx.moveTo(x + w, midY);
  bd.ctx.quadraticCurveTo(x + w, y2, x, y2);
  bd.ctx.stroke();
  bdClearShadow();
  if (cmd.label) {
    const c = BD_COLORS[cmd.color] || cmd.color || BD_COLORS.white;
    const fs = (cmd.size || 18) * s;
    bd.ctx.fillStyle = c;
    bd.ctx.font = `italic ${fs}px 'CMU Serif', 'Times New Roman', Georgia, serif`;
    bd.ctx.fillText(latexToUnicode(cmd.label), x + w + 6 * s * dir, midY + fs / 3);
  }
}

async function bdAnimFillRect(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  bdExpandIfNeeded((cmd.y || 0) + (cmd.h || 0));
  const c = BD_COLORS[cmd.color] || cmd.color || BD_COLORS.white;
  bd.ctx.fillStyle = cmd.opacity ? c.replace(')', `,${cmd.opacity})`) .replace('rgb', 'rgba') : c;
  if (cmd.opacity && !c.startsWith('rgb')) {
    bd.ctx.globalAlpha = cmd.opacity;
  }
  bd.ctx.fillRect((cmd.x || 0) * s, (cmd.y || 0) * s, (cmd.w || 0) * s, (cmd.h || 0) * s);
  bd.ctx.globalAlpha = 1;
}

async function bdAnimCurvedArrow(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  bdExpandIfNeeded(Math.max(cmd.y1 || 0, cmd.y2 || 0, cmd.cy || 0));
  bdChalkStyle(cmd.color, cmd.w || 2);
  const steps = 30;
  bd.ctx.beginPath();
  bd.ctx.moveTo((cmd.x1 || 0) * s, (cmd.y1 || 0) * s);
  for (let i = 1; i <= steps; i++) {
    if (bd.cancelFlag) return;
    const t = i / steps;
    const px = (1 - t) * (1 - t) * (cmd.x1 || 0) + 2 * (1 - t) * t * (cmd.cx || 0) + t * t * (cmd.x2 || 0);
    const py = (1 - t) * (1 - t) * (cmd.y1 || 0) + 2 * (1 - t) * t * (cmd.cy || 0) + t * t * (cmd.y2 || 0);
    bd.ctx.lineTo(px * s, py * s);
    bd.ctx.stroke();
    bd.ctx.beginPath();
    bd.ctx.moveTo(px * s, py * s);
    await bdSleep(12);
  }
  const angle = Math.atan2((cmd.y2 - (cmd.cy || 0)), (cmd.x2 - (cmd.cx || 0)));
  const hl = 10 * s;
  bdChalkStyle(cmd.color, cmd.w || 2);
  bd.ctx.beginPath();
  bd.ctx.moveTo((cmd.x2 || 0) * s, (cmd.y2 || 0) * s);
  bd.ctx.lineTo(((cmd.x2 || 0) - hl / s * Math.cos(angle - 0.4)) * s, ((cmd.y2 || 0) - hl / s * Math.sin(angle - 0.4)) * s);
  bd.ctx.stroke();
  bd.ctx.beginPath();
  bd.ctx.moveTo((cmd.x2 || 0) * s, (cmd.y2 || 0) * s);
  bd.ctx.lineTo(((cmd.x2 || 0) - hl / s * Math.cos(angle + 0.4)) * s, ((cmd.y2 || 0) - hl / s * Math.sin(angle + 0.4)) * s);
  bd.ctx.stroke();
  bdClearShadow();
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
    case 'matrix': await bdAnimMatrix(cmd); break;
    case 'brace': await bdAnimBrace(cmd); break;
    case 'fillrect': await bdAnimFillRect(cmd); break;
    case 'curvedarrow': await bdAnimCurvedArrow(cmd); break;
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
  // Board animation finished — glow the last AI message to draw student's attention
  if (!bd.cancelFlag && bd.complete && state.spotlightActive) {
    highlightLastChatMessage();
  }
  // Capture tutor-only snapshot after all commands finish (before student draws)
  if (!bd.cancelFlag && bd.canvas && !bd.tutorSnapshot) {
    try {
      bd.tutorSnapshot = bd.canvas.toDataURL('image/png');
    } catch (e) {
      console.warn('Could not capture tutor snapshot:', e);
    }
  }
}

function bdEnqueueCommand(cmd) {
  state.boardDraw.commandQueue.push(cmd);
  if (state.boardDraw.canvas && !state.boardDraw.isProcessing) bdProcessQueue();
}

function bdProcessStreaming(fullText) {
  const bd = state.boardDraw;
  if (bd.dismissed) return;
  if (!bd.active) {
    const m = fullText.match(/<teaching-board-draw([^>]*)>/);
    if (!m) return;
    // Parse commands during streaming but defer spotlight opening to finalizeAIMessage
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
    try { bd.commandQueue.push(JSON.parse(ln)); } catch (e) {}
  }
  bd.processedLines = count;
  if (closeIdx >= 0) {
    bd.complete = true;
    bd.rawContent = fullText.slice(bd.contentStartIdx, closeIdx);
  }
}

// ── Widget Streaming ────────────────────────────────────────────────────
function widgetProcessStreaming(fullText) {
  const w = state.widget;
  if (!w.active) {
    const m = fullText.match(/<teaching-widget([^>]*)>/);
    if (!m) return;
    w.active = true;
    w.contentStartIdx = m.index + m[0].length;
    w.complete = false;
    w.code = '';
    // Parse title from attrs
    const titleMatch = m[1].match(/title="([^"]*)"/);
    w.title = titleMatch ? titleMatch[1] : 'Interactive Widget';

    // Open spotlight immediately with loading skeleton
    widgetOpenLoadingSkeleton(w.title);
  }
  const closeIdx = fullText.indexOf('</teaching-widget>', w.contentStartIdx);
  if (closeIdx >= 0) {
    w.complete = true;
    w.code = fullText.slice(w.contentStartIdx, closeIdx);
  } else {
    w.code = fullText.slice(w.contentStartIdx);
  }
}

function widgetOpenLoadingSkeleton(title) {
  const panel = $('#spotlight-panel');
  const content = $('#spotlight-content');
  const titleEl = $('#spotlight-title');
  const typeBadge = $('#spotlight-type-badge');
  if (!panel || !content) return;

  if (state.spotlightActive) {
    hideSpotlight({ silent: true });
  }

  if (titleEl) titleEl.textContent = title;
  if (typeBadge) {
    typeBadge.textContent = 'Widget';
    typeBadge.setAttribute('data-type', 'widget');
    typeBadge.style.display = '';
  }

  content.innerHTML = `<div class="widget-loading">
    <div class="widget-loading-anim">
      <div class="widget-skel-row">
        <div class="widget-skel-btn"></div>
        <div class="widget-skel-btn"></div>
        <div class="widget-skel-btn short"></div>
      </div>
      <div class="widget-skel-canvas"></div>
      <div class="widget-skel-row">
        <div class="widget-skel-slider"></div>
        <div class="widget-skel-slider"></div>
      </div>
      <div class="widget-skel-text"></div>
    </div>
    <div class="widget-loading-label">
      <div class="widget-loading-spinner"></div>
      <span>Building interactive widget...</span>
    </div>
  </div>`;

  panel.classList.add('stage-active');
  state.spotlightActive = true;
  state.spotlightInfo = { type: 'widget', title, widgetCode: '' };
}

function openWidgetSpotlight(title, widgetCode, isReplay, options = {}) {
  const panel = $('#spotlight-panel');
  const content = $('#spotlight-content');
  const titleEl = $('#spotlight-title');
  const typeBadge = $('#spotlight-type-badge');
  if (!panel || !content) return;

  if (isReplay) {
    const refTag = { name: 'teaching-widget', attrs: { title }, _widgetCode: widgetCode };
    appendSpotlightReference('widget', title, refTag);
    return;
  }

  // If spotlight already showing widget skeleton from streaming, just upgrade to iframe
  const alreadyShowingSkeleton = state.spotlightActive && state.spotlightInfo?.type === 'widget';

  if (!alreadyShowingSkeleton) {
    if (state.spotlightActive) {
      hideSpotlight({ silent: true });
    }

    if (titleEl) titleEl.textContent = title;
    if (typeBadge) {
      typeBadge.textContent = 'Widget';
      typeBadge.setAttribute('data-type', 'widget');
      typeBadge.style.display = '';
    }
  }

  if (widgetCode && widgetCode.trim()) {
    renderWidgetIframe(content, widgetCode, title);
  }

  panel.classList.add('stage-active');
  state.spotlightActive = true;
  state.spotlightInfo = { type: 'widget', title, widgetCode };

  if (!options.skipReference) {
    const refTag = { name: 'teaching-widget', attrs: { title }, _widgetCode: widgetCode };
    appendSpotlightReference('widget', title, refTag);
  }
}

function renderWidgetIframe(container, widgetCode, title) {
  const fullDoc = widgetCode.includes('<html') ? widgetCode :
    `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>${widgetCode}</body></html>`;

  const iframe = document.createElement('iframe');
  iframe.className = 'widget-iframe';
  iframe.srcdoc = fullDoc;
  iframe.setAttribute('sandbox', 'allow-scripts');
  iframe.setAttribute('title', title || 'Interactive Widget');

  container.innerHTML = '';
  container.appendChild(iframe);

  // Bridge: listen for sim-ready and interaction events
  const handler = (ev) => {
    if (ev.source !== iframe.contentWindow) return;
    const d = ev.data;
    if (!d || !d.type) return;
    if (d.type === 'capacity-sim-ready') {
      // no-op
    } else if (d.type === 'capacity-sim-state' || d.type === 'capacity-sim-interaction') {
      // no-op
    }
  };
  window.addEventListener('message', handler);
  iframe._bridgeCleanup = () => window.removeEventListener('message', handler);
}

function openBoardDrawSpotlight(title, rawContent, options = {}) {
  // In replay mode, only render the reference card
  if (state.replayMode) {
    if (rawContent) state.boardDraw.rawContent = rawContent;
    const refTag = { name: 'teaching-board-draw', attrs: { title } };
    if (state.boardDraw.rawContent) refTag._boardDrawContent = state.boardDraw.rawContent;
    appendSpotlightReference('board-draw', title, refTag);
    return;
  }

  const panel = $('#spotlight-panel');
  const content = $('#spotlight-content');
  const titleEl = $('#spotlight-title');
  const typeBadge = $('#spotlight-type-badge');
  if (!panel || !content) return;

  if (state.spotlightActive) {
    if (state.activeSimulation) { stopSimBridge(); state.activeSimulation = null; state.simulationLiveState = null; }
    if (state.spotlightInfo?.type === 'notebook') {
      saveNotebookStepsToHistory();
      if (state.notebookCleanup) { state.notebookCleanup(); state.notebookCleanup = null; }
      state.notebookSteps = [];
    }
    if (state.spotlightInfo?.type === 'board-draw') bdCleanup();
    content.innerHTML = '';
  }

  // Store raw JSONL content AFTER cleanup (bdCleanup wipes rawContent)
  if (rawContent) state.boardDraw.rawContent = rawContent;

  if (titleEl) titleEl.textContent = title;
  if (typeBadge) { typeBadge.textContent = 'Board'; typeBadge.setAttribute('data-type', 'board-draw'); typeBadge.style.display = ''; }

  content.innerHTML = `
    <div class="bd-container" id="bd-container">
      <div class="bd-toolbar" id="bd-toolbar">
        <button class="bd-tool-btn active" data-color="#22ee66" title="Green pen">
          <span style="color:#22ee66;">&#9679;</span>
        </button>
        <button class="bd-tool-btn" data-color="#ff6666" title="Red pen">
          <span style="color:#ff6666;">&#9679;</span>
        </button>
        <button class="bd-tool-btn" data-color="#ffffff" title="White pen">
          <span style="color:#ffffff;">&#9679;</span>
        </button>
        <button class="bd-tool-btn bd-eraser-btn" data-color="eraser" title="Eraser">&#9003;</button>
        <span class="bd-toolbar-divider"></span>
        <button class="bd-tool-btn bd-clear-btn" onclick="bdClearStudentDrawing()" title="Clear my drawing">Clear</button>
        <button class="bd-tool-btn bd-send-btn" onclick="bdSendDrawing()" title="Send board to tutor">Send &#x2192;</button>
      </div>
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
  state.spotlightOpenedAtTurn = state.totalAssistantTurns;
  enterSpotlightFullscreen();
  if (!options.skipReference) {
    const refTag = { name: 'teaching-board-draw', attrs: { title } };
    if (state.boardDraw.rawContent) refTag._boardDrawContent = state.boardDraw.rawContent;
    appendSpotlightReference('board-draw', title, refTag);
  }

  setTimeout(() => {
    const c = document.getElementById('bd-canvas');
    const v = document.getElementById('bd-voice-text');
    if (c) bdInit(c, v);

    // First-time hint on Send button
    setTimeout(() => {
      const sendBtn = document.querySelector('.bd-send-btn');
      if (sendBtn) {
        UIHints.show('board-send', sendBtn,
          'Scribble on the board',
          'Draw, circle, or highlight anything on the board — then hit <b>Send</b> to share your work with Euler. He\'ll see what you drew.',
          'bottom', { left: -60 });
      }
    }, 600);
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
  bd.zoom = 1;
  bd.complete = false;
  bd.studentDrawing = false;
  bd.rawContent = null;
  bd.tutorSnapshot = null;
}

function bdReplayCommandsInstant(cmds) {
  const bd = state.boardDraw;
  if (!bd.ctx) return;
  const s = bd.scale;
  const ctx = bd.ctx;
  for (const cmd of cmds) {
    if (cmd.cmd === 'voice') continue;
    ctx.save();
    ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
    const c = cmd.color || 'white';
    const w = (cmd.w || 2) * s;
    ctx.strokeStyle = c;
    ctx.lineWidth = w;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (cmd.cmd === 'line' || cmd.cmd === 'dashed') {
      if (cmd.cmd === 'dashed') ctx.setLineDash([6 * s, 4 * s]);
      ctx.beginPath();
      ctx.moveTo(cmd.x1 * s, cmd.y1 * s);
      ctx.lineTo(cmd.x2 * s, cmd.y2 * s);
      ctx.stroke();
      if (cmd.cmd === 'dashed') ctx.setLineDash([]);
    } else if (cmd.cmd === 'arrow') {
      ctx.beginPath();
      ctx.moveTo(cmd.x1 * s, cmd.y1 * s);
      ctx.lineTo(cmd.x2 * s, cmd.y2 * s);
      ctx.stroke();
      const angle = Math.atan2((cmd.y2 - cmd.y1) * s, (cmd.x2 - cmd.x1) * s);
      const headLen = 12 * s;
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.moveTo(cmd.x2 * s, cmd.y2 * s);
      ctx.lineTo(cmd.x2 * s - headLen * Math.cos(angle - 0.4), cmd.y2 * s - headLen * Math.sin(angle - 0.4));
      ctx.lineTo(cmd.x2 * s - headLen * Math.cos(angle + 0.4), cmd.y2 * s - headLen * Math.sin(angle + 0.4));
      ctx.closePath();
      ctx.fill();
    } else if (cmd.cmd === 'rect') {
      ctx.strokeRect(cmd.x * s, cmd.y * s, (cmd.w || cmd.w2) * s, cmd.h * s);
    } else if (cmd.cmd === 'circle') {
      ctx.beginPath();
      ctx.arc(cmd.cx * s, cmd.cy * s, cmd.r * s, 0, Math.PI * 2);
      ctx.stroke();
    } else if (cmd.cmd === 'text') {
      const sz = (cmd.size || 18) * s;
      ctx.fillStyle = c;
      ctx.font = `${cmd.style || ''} ${sz}px 'Patrick Hand', cursive`.trim();
      ctx.fillText(cmd.text, cmd.x * s, cmd.y * s);
    } else if (cmd.cmd === 'latex') {
      const sz = (cmd.size || 22) * s;
      const text = latexToUnicode(cmd.tex);
      ctx.fillStyle = c;
      ctx.font = `italic ${sz}px 'CMU Serif', 'Times New Roman', Georgia, serif`;
      ctx.fillText(text, cmd.x * s, cmd.y * s);
    } else if (cmd.cmd === 'dot') {
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.arc(cmd.x * s, cmd.y * s, (cmd.r || 4) * s, 0, Math.PI * 2);
      ctx.fill();
    } else if (cmd.cmd === 'freehand' && cmd.points) {
      ctx.beginPath();
      for (let i = 0; i < cmd.points.length; i++) {
        const [px, py] = cmd.points[i];
        if (i === 0) ctx.moveTo(px * s, py * s);
        else ctx.lineTo(px * s, py * s);
      }
      ctx.stroke();
    } else if (cmd.cmd === 'matrix') {
      const rows = cmd.rows || [];
      if (rows.length === 0) { ctx.restore(); continue; }
      const nRows = rows.length;
      const nCols = Math.max(...rows.map(r => r.length));
      const fs = (cmd.size || 22) * s;
      const font = `italic ${fs}px 'CMU Serif', 'Times New Roman', Georgia, serif`;
      ctx.font = font;
      const cellPadX = 12 * s, cellPadY = 8 * s;
      const colWidths = [];
      for (let col = 0; col < nCols; col++) {
        let maxW = 0;
        for (let row = 0; row < nRows; row++) {
          maxW = Math.max(maxW, ctx.measureText(latexToUnicode(String((rows[row]||[])[col]||''))).width);
        }
        colWidths.push(maxW);
      }
      const rowH = fs + cellPadY;
      const totalW = colWidths.reduce((a, b) => a + b, 0) + (nCols - 1) * cellPadX;
      const totalH = nRows * rowH;
      const bracketW = 8 * s;
      const ox = (cmd.x || 0) * s, oy = (cmd.y || 0) * s;
      ctx.strokeStyle = c; ctx.lineWidth = 2 * s; ctx.lineCap = 'round';
      const bracket = cmd.bracket || 'round';
      if (bracket === 'round' || bracket === 'paren') {
        const midY = oy + totalH / 2;
        ctx.beginPath();
        ctx.moveTo(ox + bracketW, oy - 4*s);
        ctx.quadraticCurveTo(ox, midY, ox + bracketW, oy + totalH + 4*s);
        ctx.stroke();
        const rx = ox + bracketW + totalW + cellPadX;
        ctx.beginPath();
        ctx.moveTo(rx, oy - 4*s);
        ctx.quadraticCurveTo(rx + bracketW, midY, rx, oy + totalH + 4*s);
        ctx.stroke();
      } else if (bracket === 'square') {
        const lx = ox, rx2 = ox + bracketW*2 + totalW + cellPadX;
        ctx.beginPath();
        ctx.moveTo(lx+bracketW, oy-4*s); ctx.lineTo(lx, oy-4*s);
        ctx.lineTo(lx, oy+totalH+4*s); ctx.lineTo(lx+bracketW, oy+totalH+4*s);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(rx2-bracketW, oy-4*s); ctx.lineTo(rx2, oy-4*s);
        ctx.lineTo(rx2, oy+totalH+4*s); ctx.lineTo(rx2-bracketW, oy+totalH+4*s);
        ctx.stroke();
      } else if (bracket === 'pipe') {
        ctx.beginPath(); ctx.moveTo(ox, oy-4*s); ctx.lineTo(ox, oy+totalH+4*s); ctx.stroke();
        const rx3 = ox + bracketW + totalW + cellPadX;
        ctx.beginPath(); ctx.moveTo(rx3+bracketW, oy-4*s); ctx.lineTo(rx3+bracketW, oy+totalH+4*s); ctx.stroke();
      }
      const startX = ox + bracketW + 2*s;
      ctx.fillStyle = c;
      ctx.font = font;
      for (let row = 0; row < nRows; row++) {
        let cx = startX;
        const cy = oy + row * rowH + fs * 0.85;
        for (let col = 0; col < nCols; col++) {
          const entry = latexToUnicode(String((rows[row]||[])[col]||''));
          const entryW = ctx.measureText(entry).width;
          ctx.fillText(entry, cx + colWidths[col]/2 - entryW/2, cy);
          cx += colWidths[col] + cellPadX;
        }
      }
    } else if (cmd.cmd === 'fillrect') {
      ctx.fillStyle = c;
      if (cmd.opacity) ctx.globalAlpha = cmd.opacity;
      ctx.fillRect((cmd.x||0)*s, (cmd.y||0)*s, (cmd.w||0)*s, (cmd.h||0)*s);
      ctx.globalAlpha = 1;
    } else if (cmd.cmd === 'brace') {
      const bx = (cmd.x||0)*s, by1 = (cmd.y1||0)*s, by2 = (cmd.y2||0)*s;
      const dir = cmd.dir === 'right' ? 1 : -1;
      const bw = (cmd.w||10)*s*dir;
      const midY = (by1+by2)/2;
      ctx.beginPath(); ctx.moveTo(bx, by1); ctx.quadraticCurveTo(bx+bw, by1, bx+bw, midY); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(bx+bw, midY); ctx.quadraticCurveTo(bx+bw, by2, bx, by2); ctx.stroke();
      if (cmd.label) {
        const bfs = (cmd.size||18)*s;
        ctx.fillStyle = c; ctx.font = `italic ${bfs}px 'CMU Serif', 'Times New Roman', Georgia, serif`;
        ctx.fillText(latexToUnicode(cmd.label), bx+bw+6*s*dir, midY+bfs/3);
      }
    } else if (cmd.cmd === 'curvedarrow') {
      ctx.beginPath();
      ctx.moveTo((cmd.x1||0)*s, (cmd.y1||0)*s);
      ctx.quadraticCurveTo((cmd.cx||0)*s, (cmd.cy||0)*s, (cmd.x2||0)*s, (cmd.y2||0)*s);
      ctx.stroke();
      const angle = Math.atan2(((cmd.y2||0)-(cmd.cy||0))*s, ((cmd.x2||0)-(cmd.cx||0))*s);
      const hl = 10*s;
      ctx.beginPath(); ctx.moveTo((cmd.x2||0)*s, (cmd.y2||0)*s);
      ctx.lineTo((cmd.x2||0)*s-hl*Math.cos(angle-0.4), (cmd.y2||0)*s-hl*Math.sin(angle-0.4)); ctx.stroke();
      ctx.beginPath(); ctx.moveTo((cmd.x2||0)*s, (cmd.y2||0)*s);
      ctx.lineTo((cmd.x2||0)*s-hl*Math.cos(angle+0.4), (cmd.y2||0)*s-hl*Math.sin(angle+0.4)); ctx.stroke();
    }
    ctx.restore();
  }
}

function bdCaptureBoard() {
  const bd = state.boardDraw;
  if (!bd.canvas) return null;
  const ctx = bd.ctx;
  const w = bd.canvas.width;
  const h = bd.canvas.height;
  let imageData;
  try {
    imageData = ctx.getImageData(0, 0, w, h);
  } catch (e) {
    console.warn('Canvas tainted, using toDataURL fallback');
    try { return bd.canvas.toDataURL('image/png'); } catch (e2) { return null; }
  }
  const data = imageData.data;
  const bgR = 0x1a, bgG = 0x1d, bgB = 0x2e;
  let minX = w, minY = h, maxX = 0, maxY = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const dr = data[i] - bgR, dg = data[i + 1] - bgG, db = data[i + 2] - bgB;
      if (Math.sqrt(dr * dr + dg * dg + db * db) > 30) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (maxX <= minX || maxY <= minY) return null;
  const pad = 20;
  minX = Math.max(0, minX - pad);
  minY = Math.max(0, minY - pad);
  maxX = Math.min(w - 1, maxX + pad);
  maxY = Math.min(h - 1, maxY + pad);
  const cropW = maxX - minX + 1;
  const cropH = maxY - minY + 1;

  // Create output canvas with white background
  const out = document.createElement('canvas');
  out.width = cropW;
  out.height = cropH;
  const outCtx = out.getContext('2d');
  outCtx.fillStyle = '#ffffff';
  outCtx.fillRect(0, 0, cropW, cropH);
  const cropped = ctx.getImageData(minX, minY, cropW, cropH);
  const cd = cropped.data;
  for (let i = 0; i < cd.length; i += 4) {
    const dr = cd[i] - bgR, dg = cd[i + 1] - bgG, db = cd[i + 2] - bgB;
    if (Math.sqrt(dr * dr + dg * dg + db * db) > 30) {
      // Keep the original colors for contrast
    } else {
      cd[i] = 255; cd[i + 1] = 255; cd[i + 2] = 255; cd[i + 3] = 255;
    }
  }
  outCtx.putImageData(cropped, 0, 0);

  const quality = Math.min(1, 800 / Math.max(cropW, cropH));
  if (quality < 1) {
    const scaled = document.createElement('canvas');
    scaled.width = Math.round(cropW * quality);
    scaled.height = Math.round(cropH * quality);
    const sCtx = scaled.getContext('2d');
    sCtx.drawImage(out, 0, 0, scaled.width, scaled.height);
    return scaled.toDataURL('image/png');
  }
  return out.toDataURL('image/png');
}

function bdCaptureAndSend() {
  const combinedUrl = bdCaptureBoard();
  if (!combinedUrl) return;
  const combinedBase64 = combinedUrl.split(',')[1];
  renderUserMessage('[Board drawing sent to tutor]', combinedUrl);

  const bd = state.boardDraw;
  const parts = [];

  // Image 1: Tutor-only drawing (what AI originally drew — before student touched it)
  if (bd.tutorSnapshot) {
    const tutorBase64 = bd.tutorSnapshot.split(',')[1];
    parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: tutorBase64 } });
    parts.push({ type: 'text', text: '[IMAGE 1 — TUTOR ORIGINAL] This is what YOU (the tutor) drew. This is YOUR drawing, not the student\'s work.' });
  }

  // Image 2: Combined drawing (tutor + student annotations)
  parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: combinedBase64 } });

  if (bd.tutorSnapshot) {
    parts.push({ type: 'text', text: '[IMAGE 2 — COMBINED BOARD] This shows YOUR original drawing PLUS the student\'s additions. The student drew in green/red/white on top of your work. Compare with IMAGE 1 to see exactly what the STUDENT added. ONLY describe and respond to what the STUDENT drew — do NOT attribute your own drawing to the student.' });
  } else {
    parts.push({ type: 'text', text: '[Board drawing] The student has drawn/annotated on the shared board. Student strokes are in green/red/white.' });
  }

  streamADK(parts);
}

// ═══════════════════════════════════════════════════════════
// Module: Spotlight Snapshot — auto-capture for AI context
// ═══════════════════════════════════════════════════════════

function captureSpotlightSnapshot() {
  if (!state.spotlightActive || !state.spotlightInfo) return null;

  const info = state.spotlightInfo;

  if (info.type === 'board-draw') {
    const dataUrl = bdCaptureBoard();
    if (dataUrl) {
      return {
        type: 'board-draw',
        title: info.title,
        base64: dataUrl.split(',')[1],
        mediaType: 'image/png',
        description: `[SPOTLIGHT SNAPSHOT — Board: "${info.title}"] This is what the student currently sees on the shared drawing board.`,
      };
    }
  }

  if (info.type === 'widget') {
    const iframe = document.querySelector('#spotlight-content .widget-iframe');
    if (iframe) {
      try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
        if (iframeDoc) {
          const bodyText = iframeDoc.body?.innerText?.slice(0, 500) || '';
          return {
            type: 'widget',
            title: info.title,
            base64: null,
            description: `[SPOTLIGHT — Widget: "${info.title}"] Interactive widget is open. Visible text: ${bodyText}`,
          };
        }
      } catch (e) { /* cross-origin */ }
    }
    return {
      type: 'widget',
      title: info.title,
      base64: null,
      description: `[SPOTLIGHT — Widget: "${info.title}"] Interactive widget is currently open.`,
    };
  }

  if (info.type === 'notebook') {
    const steps = state.notebookSteps.slice(-5).map(
      s => `Step ${s.n} (${s.author || 'tutor'}): ${s.math || s.content || ''}`
    ).join('\n');
    return {
      type: 'notebook',
      title: info.title,
      base64: null,
      description: `[SPOTLIGHT — Notebook: "${info.title}"] ${state.notebookSteps.length} steps.\nRecent:\n${steps}`,
    };
  }

  if (info.type === 'simulation') {
    return {
      type: 'simulation',
      title: info.title,
      base64: null,
      description: `[SPOTLIGHT — Simulation: "${info.title}"] Student is viewing the interactive simulation.`,
    };
  }

  if (info.type === 'video') {
    return {
      type: 'video',
      title: info.title,
      base64: null,
      description: `[SPOTLIGHT — Video: "${info.title}"] Student is watching a lecture video clip.`,
    };
  }

  if (info.type === 'image') {
    return {
      type: 'image',
      title: info.title,
      base64: null,
      description: `[SPOTLIGHT — Image: "${info.title}"] Student is viewing a reference image.`,
    };
  }

  return null;
}

function buildSpotlightSnapshotParts() {
  const snap = captureSpotlightSnapshot();
  if (!snap) return [];
  const parts = [];
  if (snap.base64) {
    parts.push({ type: 'image', source: { type: 'base64', media_type: snap.mediaType || 'image/png', data: snap.base64 } });
  }
  parts.push({ type: 'text', text: snap.description });
  return parts;
}

// ═══════════════════════════════════════════════════════════
// Boot
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  Router.init();
  initSetup();
  Router.resolve(location.pathname);

  // Clean up agent event SSE on page unload
  window.addEventListener('beforeunload', () => disconnectAgentEvents());

  // Stale streaming recovery when tab returns from background
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && state.isStreaming) {
      const staleSec = (Date.now() - state._lastSSETimestamp) / 1000;
      if (staleSec > 60) {
        console.warn(`[visibility] Streaming stale for ${staleSec.toFixed(0)}s — force-resetting`);
        state.isStreaming = false;
        if (state._streamingTimeout) { clearTimeout(state._streamingTimeout); state._streamingTimeout = null; }
        removeStreamingIndicator();
        renderAIError('Connection lost while tab was in background. Please resend your message.');
      }
    }
  });
});
