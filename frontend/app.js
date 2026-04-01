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

  async function createSession(courseId, studentName, intent, coursePosition, sessionNumber, scenario) {
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
      intent: { raw: intent || '', scenario: scenario || 'course' },
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
      const currentSegment = Math.floor((Date.now() - state.sessionStartTime) / 1000);
      session.durationSec = (state._accumulatedDuration || 0) + currentSegment;
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
        // Widget interaction state (slider values, etc.) — restored so tutor knows what student changed
        widgetLiveState: state.widget.liveState || {},
        // Active board-draw content (in case it was streaming when save occurred)
        activeBoardDrawContent: state.boardDraw.rawContent || null,
        // Voice mode state
        teachingMode: state.teachingMode,
        voiceSpeed: state.voiceSpeed,
        // Video state — for resuming watch-along sessions
        videoState: state.video.active ? {
          lessonId: state.video.lessonId,
          lessonTitle: state.video.lessonTitle,
          currentTimestamp: state.video.currentTimestamp,
          currentSectionIndex: state.video.currentSectionIndex,
          sectionTitle: state.video.sectionTitle,
          isPaused: state.video.isPaused,
          lessonIndex: state.video.lessonIndex,
        } : null,
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
      const currentSegment = Math.floor((Date.now() - state.sessionStartTime) / 1000);
      session.durationSec = (state._accumulatedDuration || 0) + currentSegment;
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
        widgetLiveState: state.widget.liveState || {},
        activeBoardDrawContent: state.boardDraw.rawContent || null,
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
          widgetLiveState: state.widget.liveState || {},
          activeBoardDrawContent: state.boardDraw.rawContent || null,
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
    parts.push({ description: 'Session context — plan & section statuses', value: overviewStr });

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
  detourStack: [],

  // Voice mode
  teachingMode: 'voice', // voice mode is the default
  voiceSpeed: 1,
  voiceAudioCtx: null,
  voiceCurrentSrc: null,
  voiceCurrentAudio: null,
  voiceQueue: [], // queued text segments for TTS
  voiceHandVisible: false,

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
    clearBoard: true,
    commandQueue: [],
    isProcessing: false,
    cancelFlag: false,
    _instantReplayCount: 0,
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
  const res = await fetch(`${state.apiUrl}/api/v1/content${path}`, {
    headers: AuthManager.authHeaders()
  });
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
      const res = await fetch(`${state.apiUrl}/api/v1/content/lessons/${l.lesson_id}/sections`, {
        headers: AuthManager.authHeaders(),
      });
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
    const res = await fetch(`${state.apiUrl}/api/v1/learning-tools/course/${courseId}`, {
      headers: AuthManager.authHeaders(),
    });
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
    const res = await fetch(`${state.apiUrl}/api/v1/content/courses/${courseId}/concepts`, {
      headers: AuthManager.authHeaders(),
    });
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
  const courseTitle = map.title || (map.course && map.course.title) || 'Course';
  const lines = [`${courseTitle}\n`];

  for (const mod of (map.modules || [])) {
    lines.push(`Module: ${mod.title}`);
    const modLessons = mod.lessons || (map.lessons || []).filter(l => l.module_id === mod.id);
    for (const lesson of modLessons) {
      const lid = lesson.lesson_id || lesson.id;
      const dur = (lesson.duration_seconds || lesson.duration) ? `${Math.round((lesson.duration_seconds || lesson.duration) / 60)} min` : '';
      const isCurrent = lid === cp.currentLessonId;
      const marker = isCurrent ? ' << CURRENT LESSON' : '';
      const videoTag = lesson.video_url ? ` [video: ${lesson.video_url}]` : ' [no video]';
      lines.push(`  Lesson ${lid}: ${lesson.title} (${dur})${videoTag}${marker}`);

      // Only show sections for current lesson (keeps context compact)
      if (isCurrent && lesson.sections) {
        for (const sec of lesson.sections) {
          const key = `${lid}:${sec.index}`;
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

let _streamGeneration = 0;  // Increments on each new stream — prevents old cleanup from interfering

async function streamADK(userMessageContent, isSystemTrigger = false, isSessionStart = false) {
  if (state.isStreaming) {
    // Visual feedback — don't silently swallow
    if (!isSystemTrigger) {
      const bar = document.getElementById('voice-bar-main');
      if (bar) { bar.style.borderColor = 'rgba(251,191,36,0.4)'; setTimeout(() => { bar.style.borderColor = ''; }, 400); }
    }
    return;
  }
  const _now = Date.now();
  if (!isSystemTrigger && state._lastChatRequestAt && _now - state._lastChatRequestAt < 1000) {
    // Throttled — brief amber flash so user knows something happened
    const bar = document.getElementById('voice-bar-main');
    if (bar) { bar.style.borderColor = 'rgba(251,191,36,0.4)'; setTimeout(() => { bar.style.borderColor = ''; }, 400); }
    return;
  }
  state._lastChatRequestAt = _now;
  state.isStreaming = true;
  state._stopRequested = false;
  state._streamReader = null;
  state._lastSSETimestamp = Date.now();
  const thisGen = ++_streamGeneration;  // Track this stream's generation
  _showStopButton(true);

  // Voice mode: restore full-screen board if we were in interactive mode
  if (state.teachingMode === 'voice') {
    const mainLayout = $('#main-layout');
    if (mainLayout) {
      mainLayout.classList.remove('voice-mode-interactive');
      mainLayout.classList.add('voice-mode');
    }
    const micFloat = $('#voice-mic-float');
    if (micFloat) micFloat.style.display = '';
    voiceBarSetThinking(true);
  }

  // Disable quick actions during streaming
  document.querySelectorAll('.quick-action-btn').forEach(b => b.disabled = true);

  // Safety timeout: force-reset after 120s of total streaming
  if (state._streamingTimeout) clearTimeout(state._streamingTimeout);
  state._streamingTimeout = setTimeout(() => {
    if (state.isStreaming) {
      console.warn('[streamADK] Safety timeout — force-resetting streaming state');
      stopGeneration();
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

  // Sliding window: send last N messages + summary of older ones
  const windowedMessages = _windowMessages(state.messages);

  const body = {
    messages: windowedMessages,
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
    state._streamReader = reader;
    const decoder = new TextDecoder();
    let buffer = '';

    state.accumulatedText = '';
    state.currentMessageId = null;

    while (true) {
      if (state._stopRequested) {
        reader.cancel();
        break;
      }
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
          if (!state._stopRequested) handleSSEEvent(event);
        } catch (e) {
          // Skip unparseable events
        }
      }
    }

    if (!state._stopRequested && buffer.startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.slice(6).trim());
        handleSSEEvent(event);
      } catch (e) {}
    }
  } catch (err) {
    if (!state._stopRequested) {
      removeStreamingIndicator();
      removeAssessmentTransition();
      hideSessionPrep(); // Dismiss loading overlay on error
      renderAIError(err.message);
      console.error('[Stream] Error:', err.message);
    }
  }

  // Clean up after stop or normal completion
  // Only if this is still the active stream (prevents stale cleanup from killing a new stream)
  if (_streamGeneration !== thisGen) return;
  const wasStopped = state._stopRequested;
  state.isStreaming = false;
  state._streamReader = null;
  state._stopRequested = false;
  hideSessionPrep();
  if (state._streamingTimeout) { clearTimeout(state._streamingTimeout); state._streamingTimeout = null; }
  _showStopButton(false);
  // Re-enable quick actions
  document.querySelectorAll('.quick-action-btn').forEach(b => b.disabled = false);

  // Voice mode: reset thinking state and show input
  if (state.teachingMode === 'voice') {
    voiceBarSetThinking(false);

    if (wasStopped) {
      // Stop requested: discard the streaming message, remove from history
      removeStreamingIndicator();
      removeAssessmentTransition();
      const streamMsg = document.getElementById('ai-stream-msg');
      if (streamMsg) streamMsg.remove();
      // Remove the last assistant message from state if partially accumulated
      if (state.messages.length && state.messages[state.messages.length - 1].role === 'assistant') {
        state.messages.pop();
      }
      voiceShowBoardQuestion('Type your response...');
    } else {
      setTimeout(() => {
        const voiceInput = $('#voice-bar-input');
        const isTyping = voiceInput && voiceInput === document.activeElement && voiceInput.value.trim();
        if (!isTyping) {
          try { voiceHandleRunFinished(); } catch (e) {
            console.warn('voiceHandleRunFinished failed:', e);
            voiceShowBoardQuestion('Type your response...');
          }
        }
      }, 500);
    }
  }

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
      // DON'T reset boardDraw.active — board panel stays open across turns
      // Only reset the streaming parse state for the new message
      state.boardDraw.processedLines = 0;
      state.boardDraw.contentStartIdx = 0;
      state.boardDraw.complete = false;
      state.boardDraw.dismissed = false;
      state.boardDraw._streamingHandled = false;
      state.widget = { active: false, contentStartIdx: 0, complete: false, title: '', code: '', ready: false, pendingParams: null, liveState: {}, assetId: null };
      removeStreamingIndicator();
      hideSessionPrep();
      // Safety net: if onboarding overlay is still showing when tutor starts talking, remove it
      const staleOnboard = $('#onboarding-block');
      if (staleOnboard) {
        staleOnboard.style.transition = 'opacity 0.3s ease';
        staleOnboard.style.opacity = '0';
        setTimeout(() => staleOnboard.remove(), 300);
      }
      startAIMessageStream();
      // Hide the chat message during assessment — content renders on board only
      if (state.assessment.active) {
        const stream = document.getElementById('ai-stream-msg');
        if (stream) stream.style.display = 'none';
      }
      break;

    case 'TEXT_MESSAGE_CONTENT':
      state.accumulatedText += event.delta || '';
      // Debounce re-parsing — don't parse on every 10-char delta
      if (!state._streamUpdateTimer) {
        state._streamUpdateTimer = setTimeout(() => {
          state._streamUpdateTimer = null;
          updateAIMessageStream(state.accumulatedText);
        }, 80);
      }
      break;

    case 'TEXT_MESSAGE_END':
      // Clear debounced stream update and do final parse
      if (state._streamUpdateTimer) { clearTimeout(state._streamUpdateTimer); state._streamUpdateTimer = null; }
      updateAIMessageStream(state.accumulatedText); // final parse
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
      // Voice mode: show question input if the run ended with a question
      if (typeof voiceHandleRunFinished === 'function') {
        try { voiceHandleRunFinished(); } catch {}
      }
      break;

    case 'RUN_ERROR':
      removeStreamingIndicator();
      removeAssessmentTransition();
      cleanupToolIndicators();
      hideSessionPrep();
      _showStopButton(false);
      // Clear voice/speaking indicators
      const voiceBar = document.querySelector('.bd-voice-indicator, .voice-status');
      if (voiceBar) voiceBar.style.display = 'none';
      document.querySelectorAll('.euler-is-speaking, [class*="speaking"]').forEach(el => el.style.display = 'none');
      // Show error with retry on the board
      renderAIError(event.message || 'Something went wrong. Try again.');
      break;

    case 'PLAN_UPDATE':
      console.log('[PLAN_UPDATE] received, plan:', event.plan);
      handlePlanFromAgent(event.plan, event.sessionObjective);
      console.log('[PLAN_UPDATE] state.plan after:', state.plan.length, 'sections');
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

    case 'PLAN_DETOUR_START':
      state.detourStack.push({
        prereqTopics: event.prereq_topics,
        reason: event.reason,
        returnTopic: event.return_topic,
      });
      updateHeadingBar();
      break;

    case 'PLAN_DETOUR_END':
      state.detourStack.pop();
      updateHeadingBar();
      break;

    case 'SIM_CONTROL':
      handleSimControl(event.steps);
      break;

    case 'VIDEO_RESUME':
      if (typeof vmResumeVideo === 'function') vmResumeVideo();
      break;

    case 'VIDEO_SEEK':
      if (typeof vmSeekVideo === 'function') vmSeekVideo(event.timestamp);
      break;

    case 'VIDEO_CAPTURE_FRAME':
      // Agent requested a screenshot — capture and store for next context
      if (typeof vmCaptureFrame === 'function') {
        const frame = vmCaptureFrame();
        if (frame) state.video._pendingFrame = frame;
      }
      break;

    case 'VISUAL_READY':
      state.generatedVisuals[event.id] = { title: event.title, html: event.html };
      break;

    case 'BOARD_CAPTURE_REQUEST':
      state.pendingBoardCaptureRequest = true;
      break;

    case 'ASSESSMENT_START':
      state.assessment.active = true;
      state.assessment.sectionTitle = event.section?.title || '';
      state.assessment.concepts = event.concepts || [];
      state.assessment.questionNumber = 0;
      state.assessment.maxQuestions = event.maxQuestions || 5;
      // Remove ALL recent AI messages with handoff/internal language
      {
        const allAI = document.querySelectorAll('#canvas-stream .canvas-block[data-type="ai"]');
        const leakWords = ['assessment', 'hand off', 'checkpoint', 'hand this', 'assessment agent',
          'let me check', 'craft the first', 'targeting', 'misconception', 'mcq', 'difficulty'];
        // Check last 3 messages
        const recent = Array.from(allAI).slice(-3);
        recent.forEach(el => {
          const text = (el.textContent || '').toLowerCase();
          if (leakWords.some(w => text.includes(w))) {
            el.style.transition = 'opacity 0.2s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 200);
          }
        });
      }
      // Assessment renders ON THE BOARD — hide chat panel, full-width board
      document.body.classList.add('assessment-mode');
      break;

    case 'ASSESSMENT_END': {
      state.assessment.active = false;
      state.assessment.questionNumber = 0;
      document.body.classList.remove('assessment-mode');
      const score = event.score || {};
      const isHandback = event.reason && event.reason !== 'complete';
      const sectionTitle = event.section || state.assessment.sectionTitle || '';

      // Legacy spotlight cleanup (no-op if not open)
      if (state.spotlightActive && state.spotlightInfo?.type === 'assessment') {
        window.hideSpotlight({ agentInitiated: true });
      }
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
// Module 6b: Message Windowing — limit conversation history sent to LLM
// ═══════════════════════════════════════════════════════════

// Message windowing is handled by the backend (Haiku summarization + compression).
// Frontend sends all messages; backend applies smart context window before LLM call.
// Safety cap: if messages exceed 60, only send the last 60 to avoid huge payloads.
const MAX_FRONTEND_MESSAGES = 30; // Backend handles windowing; this is a payload size cap

function _windowMessages(messages) {
  if (messages.length <= MAX_FRONTEND_MESSAGES) return messages;
  return messages.slice(-MAX_FRONTEND_MESSAGES);
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
      teachingMode: state.teachingMode, // 'text' or 'voice'
    }),
  });

  // Course Map, Concepts, Simulations — NO LONGER sent every turn.
  // The planner gets these at session start. The tutor calls content_map tool on demand.
  // This saves ~1700 tokens per turn.

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

  // Simulations — only send if student has one open (active state), not the full catalog
  if (state.simulations && state.simulations.length > 0 && false) { // DISABLED — moved to content_map tool
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

  // Course Concepts — REMOVED from per-turn context. Available via content_map tool.

  // Context: Video State (if in video follow-along mode)
  if (state.video && state.video.active) {
    const videoCtx = {
      lessonId: state.video.lessonId,
      lessonTitle: state.video.lessonTitle,
      currentTimestamp: state.video.currentTimestamp,
      currentSectionIndex: state.video.currentSectionIndex,
      sectionTitle: state.video.sectionTitle,
    };
    items.push({ description: 'Video State', value: JSON.stringify(videoCtx) });

    // Capture video frame if paused OR if agent requested capture
    if (state.video.isPaused || state.video._pendingFrame) {
      const frame = state.video._pendingFrame || vmCaptureFrame();
      state.video._pendingFrame = null;  // clear after use
      if (frame) {
        items.push({
          description: 'Video Frame — screenshot of what student sees on the video',
          value: frame,
        });
      }
    }
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

  // Context: Active Board — element IDs on the board (for beside:/below: references)
  if (state.spotlightActive && state.spotlightInfo?.type === 'board-draw') {
    const ids = Array.from(BoardEngine.state.elements.keys()).filter(id => !id.startsWith('_auto_'));
    if (ids.length > 0) {
      items.push({
        description: 'BOARD — element IDs currently on the board. Use beside:ID or below:ID to place content relative to these.',
        value: `Board: "${state.spotlightInfo.title || 'Board'}"\nElement IDs: ${ids.join(', ')}\nNew content auto-flows below existing content. Use placement tags, not coordinates.`,
      });
    }
  }

  // Context: Board History — boards with asset IDs for resuming
  const boardHistory = state.spotlightHistory.filter(h => h.type === 'board-draw');
  if (boardHistory.length > 0) {
    const boardList = boardHistory.map(h =>
      `"${h.title}" (asset_id="${h.id}")`
    ).join(', ');
    items.push({
      description: 'Previous Boards — resume instead of redrawing',
      value: 'Available boards: ' + boardList + '\nTo resume: <teaching-board-draw-resume asset="ID" title="New Title">',
    });
  }

  // Widget history — reusable widgets with asset IDs
  const widgetHistory = state.spotlightHistory.filter(h => h.type === 'widget');
  if (widgetHistory.length > 0) {
    const widgetList = widgetHistory.map(h =>
      `"${h.title}" (asset_id="${h.id}")`
    ).join(', ');
    items.push({
      description: 'Reusable Widgets — update instead of regenerating',
      value: 'Available widgets: ' + widgetList + '\nTo update parameters: <teaching-widget-update asset="ID" params=\'{"key": value}\' />',
    });
  }

  // Current widget interaction state
  if (state.spotlightInfo?.type === 'widget' && state.widget.liveState && Object.keys(state.widget.liveState).length > 0) {
    items.push({
      description: 'Widget Interaction State — what the student changed',
      value: JSON.stringify(state.widget.liveState),
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
    const isBoardOrWidget = state.spotlightInfo.type === 'board-draw' || state.spotlightInfo.type === 'widget';
    // Board-draws and widgets are primary teaching tools — longer thresholds
    const staleThreshold = isSim ? 5 : isBoardOrWidget ? 4 : 2;
    const mandatoryThreshold = isSim ? 7 : isBoardOrWidget ? 6 : 3;
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
        `⚠ STALE SPOTLIGHT: "${state.spotlightInfo.title}" open for ${turnsOpen} turns. If you are NOT referencing this specific visual right now, either: (a) draw a NEW <teaching-board-draw> which auto-clears the old one, or (b) emit <teaching-spotlight-dismiss /> BEFORE any text. Do NOT emit dismiss AND a new board-draw in the same message — the new board-draw handles clearing automatically.`
      );
    }
    if (turnsOpen >= mandatoryThreshold) {
      spotlightCtx.rules.push(
        `🚨 STALE — replace with a new visual. Either emit a new <teaching-board-draw> or <teaching-widget> (auto-clears), or dismiss with <teaching-spotlight-dismiss />. Do NOT dismiss then immediately redraw — just emit the new board-draw directly.`
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

  // Directive: Teaching plan (always send — even when empty, so tutor knows to generate one)
  items.push({
    description: 'Teaching Plan Directive — YOUR CURRENT TASK',
    value: buildPlanDirective(),
  });

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
  // No plan yet — tell tutor to generate one
  if (state.plan.length === 0) {
    return 'NO TEACHING PLAN EXISTS YET. You MUST spawn a planning agent NOW: spawn_agents to generate a <teaching-plan>. Do this in your FIRST response while also teaching.';
  }

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
  'Superposing ideas...',
  'Connecting the quanta...',
  'Every photon counts...',
  'Schrödinger\'s cat says hi...',
  'E = mc² — always...',
  'The universe is under no obligation to make sense...',
  'Entropy only goes one way...',
  'Nature abhors a vacuum...',
  'All models are wrong, some are useful...',
  'Feynman would be proud...',
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
  const startPhrase = _thinkingPhrases[Math.floor(Math.random() * _thinkingPhrases.length)];
  block.innerHTML = `<div class="board-text" style="color:var(--text-dim);"><span class="loading-spinner"></span> <span class="thinking-text">${startPhrase}</span></div>`;
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

// ── Plan polling — independent of chat stream ──
let _planPollTimer = null;
let _planPollAttempts = 0;
const _PLAN_POLL_MAX = 20; // max 20 attempts = ~60 seconds, then give up

function startPlanPolling() {
  stopPlanPolling();
  if (!state.sessionId || state.plan.length > 0) return;
  _planPollAttempts = 0;

  _planPollTimer = setInterval(async () => {
    if (state.plan.length > 0) { stopPlanPolling(); return; }
    _planPollAttempts++;

    // Bail out after max attempts — try auto-repair via lightweight endpoint
    if (_planPollAttempts > _PLAN_POLL_MAX) {
      console.warn('[PlanPoll] Max attempts reached, trying auto-repair');
      stopPlanPolling();
      _autoRepairPlan();
      return;
    }

    try {
      const res = await fetch(`${state.apiUrl}/api/session/${state.sessionId}/plan`, {
        headers: AuthManager.authHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === 'ready' && data.plan) {
        handlePlanFromAgent(data.plan, data.sessionObjective);
        stopPlanPolling();
      } else if (data.status === 'error') {
        console.warn('[PlanPoll] Plan generation failed:', data.error);
        stopPlanPolling();
        _autoRepairPlan();
      }
      // 'pending'/'building' — continue polling (capped by max attempts)
    } catch (e) { /* ignore poll errors */ }
  }, 3000); // poll every 3 seconds
}

function stopPlanPolling() {
  if (_planPollTimer) { clearInterval(_planPollTimer); _planPollTimer = null; }
}

async function _autoRepairPlan() {
  // Lightweight plan repair — asks the backend to generate a quick plan via fast model
  const intent = state.studentIntent || '';
  if (!intent || !state.sessionId) {
    const body = document.getElementById('psb-body');
    if (body) body.innerHTML = '<div class="psb-generating"><span>Plan unavailable — tutor will teach freely.</span></div>';
    return;
  }

  console.log('[PlanRepair] Attempting auto-repair for:', intent);
  const body = document.getElementById('psb-body');
  if (body) body.innerHTML = '<div class="psb-generating"><div class="psb-gen-pulse"></div><span>Rebuilding plan...</span></div>';

  try {
    const res = await fetch(`${state.apiUrl}/api/session/${state.sessionId}/plan/repair`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify({ intent }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.plan) {
        handlePlanFromAgent(data.plan, data.sessionObjective || intent);
        return;
      }
    }
  } catch (e) {
    console.warn('[PlanRepair] Failed:', e);
  }

  // Final fallback
  if (body) body.innerHTML = '<div class="psb-generating"><span>Plan unavailable — tutor will teach freely.</span></div>';
}

function connectAgentEvents() {
  disconnectAgentEvents();
  if (!state.sessionId) return;

  const _evtToken = localStorage.getItem('mockup_auth_token') || '';
  const url = `${state.apiUrl}/api/events/${state.sessionId}${_evtToken ? '?token=' + encodeURIComponent(_evtToken) : ''}`;
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
  stopPlanPolling();
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

function cleanupActiveSession() {
  // Force save before cleanup so nothing is lost
  if (typeof SessionManager !== 'undefined' && SessionManager.saveSession) {
    try { SessionManager.saveSession(); } catch(e) {}
  }
  if (state.voiceCurrentAudio) { try { state.voiceCurrentAudio.pause(); state.voiceCurrentAudio.src = ''; } catch(e) {} state.voiceCurrentAudio = null; }
  if (state.voiceCurrentSrc) { try { state.voiceCurrentSrc.stop(); } catch(e) {} state.voiceCurrentSrc = null; }
  if (state._currentTTSAudio) { try { state._currentTTSAudio.pause(); } catch(e) {} state._currentTTSAudio = null; }
  if (state._streamReader) { try { state._streamReader.cancel(); } catch(e) {} state._streamReader = null; }
  state.isStreaming = false; state._stopRequested = false; state._voiceSceneActive = false;
  if (typeof _eagerReset === 'function') _eagerReset();
  if (state._streamingTimeout) { clearTimeout(state._streamingTimeout); state._streamingTimeout = null; }
  disconnectAgentEvents();
  if (typeof BoardEngine !== 'undefined') BoardEngine.cleanup();
  // Reset board canvas ref so next session triggers fresh BoardEngine.init
  if (state.boardDraw) {
    state.boardDraw.canvas = null;
    state.boardDraw.ctx = null;
    state.boardDraw.active = false;
    state.boardDraw._streamingHandled = false;
    state.boardDraw.commandQueue = [];
    state.boardDraw.isProcessing = false;
    state.boardDraw.cancelFlag = false;
    state.boardDraw.dismissed = false;
    state.boardDraw.complete = false;
    state.boardDraw.processedLines = 0;
    _sceneSnapshots.length = 0;
  }
  state.spotlightActive = false; state.spotlightInfo = null;
  state._videoWatchAlong = false;
  // Clean up YouTube player
  if (state.video?._ytTimerInterval) { clearInterval(state.video._ytTimerInterval); state.video._ytTimerInterval = null; }
  if (state.video?._ytPlayer) { try { state.video._ytPlayer.destroy(); } catch(e) {} state.video._ytPlayer = null; }
  state._startingSession = false; state._resumingSession = false;
  state._videoPlaylist = null; state._videoPlaylistIndex = 0;
  if (typeof _hideVideoPlaylist === 'function') _hideVideoPlaylist();
  if (typeof removeStreamingIndicator === 'function') removeStreamingIndicator();
  if (typeof voiceBarSetThinking === 'function') voiceBarSetThinking(false);
  if (typeof hideSessionPrep === 'function') hideSessionPrep();

  // Hide plan sidebar
  hidePlanSidebar();

  // ── Clear DOM content from previous session ──
  const spotlightContent = document.getElementById('spotlight-content');
  if (spotlightContent) spotlightContent.innerHTML = '';
  const canvasStream = document.getElementById('canvas-stream');
  if (canvasStream) canvasStream.innerHTML = '';
  const boardFrameStrip = document.getElementById('board-frame-strip');
  if (boardFrameStrip) boardFrameStrip.innerHTML = '';
  const boardEmpty = document.getElementById('board-empty-state');
  if (boardEmpty) boardEmpty.style.display = '';
  // Reset board header
  const spotlightTitle = document.getElementById('spotlight-title');
  if (spotlightTitle) spotlightTitle.textContent = 'Board';
  const spotlightBadge = document.getElementById('spotlight-type-badge');
  if (spotlightBadge) spotlightBadge.textContent = '';
  // Hide pen toolbar
  const penToolbar = document.getElementById('pen-draw-toolbar');
  if (penToolbar) penToolbar.classList.add('hidden');
  const penBtn = document.getElementById('board-pen-toggle');
  if (penBtn) penBtn.classList.remove('active');
  // Reset plan heading
  const planBar = document.getElementById('plan-heading-bar');
  if (planBar) planBar.classList.add('hidden');
  // Clear session messages array
  state.messages = [];
  state.sessionId = null;
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
  if (!plan) {
    // Even with no plan, stop polling so we don't loop forever
    stopPlanPolling();
    return;
  }
  state.currentPlan = plan;

  // Build sections from plan — planning agent may output sections or flat topics
  let newSections = [];
  console.log('[PLAN] sections:', plan.sections?.length, '_topics:', plan._topics?.length, 'topics:', plan.topics?.length);
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

  // If plan data was received but has no usable sections, stop polling and show fallback
  if (newSections.length === 0) {
    stopPlanPolling();
    const body = document.getElementById('psb-body');
    if (body) body.innerHTML = '<div class="psb-generating"><span>Plan unavailable — tutor will teach freely.</span></div>';
    return;
  }

  // Append or replace sections
  const hasExistingSections = state.plan.length > 0 && state.plan.some(s => s.status === 'done' || s.status === 'active');
  if (hasExistingSections && newSections.length > 0) {
    const maxN = Math.max(...state.plan.map(s => s.n));
    newSections.forEach((sec, i) => { sec.n = maxN + 1 + i; });
    state.plan.push(...newSections);
  } else {
    state.plan = newSections;
  }

  // Deactivate any previously active sections before activating new one
  state.plan.forEach(s => {
    if (s.status === 'active') s.status = 'done';
    if (s.topics) s.topics.forEach(t => { if (t.status === 'active') t.status = 'done'; });
  });

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

  SessionManager.setPlan(plan);
  updateHeadingBar();
  updatePlanSidebar({ sections: state.plan });

  // Show the plan sidebar (it starts hidden)
  const psb = document.getElementById('plan-sidebar');
  if (psb) psb.classList.remove('hidden');

  state.planCallCount++;
}

function handlePlanReset(reason, keepScope) {
  state.plan = [];
  state.planActiveStep = null;
  state.currentPlan = {};
  updateHeadingBar();
  updatePlanSidebar({ sections: [] });
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
      // Activate next pending topic — but DON'T insert heading yet
      // The tutor's next response will naturally introduce the new topic
      const nextTopic = step.topics.find(t => t.status === 'pending');
      if (nextTopic) {
        nextTopic.status = 'active';
      }
    }
  }
  SessionManager.completeTopic(sectionIndex, topicIndex);
  updateHeadingBar();
  updatePlanSidebar({ sections: state.plan });
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
  SessionManager.completeSection(index);
  updateHeadingBar();
  updatePlanSidebar({ sections: state.plan });
}

function startAIMessageStream() {
  removeStreamingIndicator();
  removeAssessmentTransition();
  // Safety: clean up any stale streaming block from a prior turn that wasn't finalized
  // (e.g. multi-round agentic loop, or error before TEXT_MESSAGE_END).
  // Without this, a duplicate #ai-stream-text causes querySelector to find the OLD one
  // and new text streams into the wrong position (top of chat instead of bottom).
  const staleStream = $('#ai-stream-msg');
  if (staleStream) {
    // Finalize the orphaned content so it isn't lost
    const orphanedText = staleStream.querySelector('#ai-stream-text');
    if (orphanedText && orphanedText.textContent.trim()) {
      // Convert to a finalized block (strip the streaming cursor)
      orphanedText.classList.remove('streaming-cursor');
      staleStream.removeAttribute('id');
      staleStream.querySelector('#ai-stream-text')?.removeAttribute('id');
    } else {
      staleStream.remove();
    }
  }
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

function showBoardLoadingSkeleton(type) {
  const content = $('#spotlight-content');
  const empty = $('#board-empty-state');
  if (!content) return;
  if (empty) empty.style.display = 'none';
  // Don't duplicate
  if (document.getElementById('board-loading-skeleton')) return;
  const label = type === 'widget' ? 'Building interactive...'
    : type === '3d' ? 'Rendering 3D scene...'
    : type === 'code' ? 'Writing code...'
    : 'Drawing on the board...';
  const skeleton = document.createElement('div');
  skeleton.id = 'board-loading-skeleton';
  skeleton.className = 'board-skeleton';
  skeleton.innerHTML = `
    <div class="board-skeleton-glow"></div>
    <div class="board-skeleton-content">
      <div class="board-skeleton-line w60"></div>
      <div class="board-skeleton-line w80"></div>
      <div class="board-skeleton-block"></div>
      <div class="board-skeleton-line w40"></div>
      <div class="board-skeleton-line w70"></div>
    </div>
    <div class="board-skeleton-label">${label}</div>
  `;
  content.appendChild(skeleton);
}

function hideBoardLoadingSkeleton() {
  const skel = document.getElementById('board-loading-skeleton');
  if (skel) skel.remove();
}

function updateAIMessageStream(text) {
  // Always target the element INSIDE #ai-stream-msg to avoid stale orphaned elements
  const container = $('#ai-stream-msg');
  const el = container?.querySelector('#ai-stream-text') || $('#ai-stream-text');
  if (!el) return;

  // Show board loading skeleton when a visual tag is detected but not yet rendered
  if (!state.boardDraw.active && text.includes('<teaching-board-draw')) {
    showBoardLoadingSkeleton('board');
  }
  if (!state.widget?.ready && text.includes('<teaching-widget') && !text.includes('<teaching-widget-update')) {
    showBoardLoadingSkeleton('widget');
  }
  // Also show skeleton for voice scenes (which render on the board)
  if (!state.boardDraw.active && text.includes('<teaching-voice-scene') && !text.includes('</teaching-voice-scene')) {
    showBoardLoadingSkeleton('board');
  }

  // Eager voice beat detection — parse and execute beats as they stream in
  if (state.teachingMode === 'voice' && text.includes('<vb ')) {
    _eagerBeatWatcher(text);
  }

  bdProcessStreaming(text);
  widgetProcessStreaming(text);

  // Check if board/widget is actively being built
  const boardActive = state.boardDraw.active && !state.boardDraw.complete;
  const widgetLoading = state.widget.active && !state.widget.complete;

  let displayHtml = renderMarkdownBasic(stripTeachingTags(text));

  // Add focus indicator when board is drawing (appended, not replacing)
  if (boardActive || widgetLoading) {
    const label = widgetLoading ? 'Building interactive...' : 'Drawing on the board...';
    // Only show if not already in the HTML
    if (!displayHtml.includes('board-focus-indicator')) {
      displayHtml += `<div class="board-focus-indicator">
        <div class="board-focus-arrow">\u2192</div>
        <div class="board-focus-text">${label}</div>
      </div>`;
    }
  }

  // Show generating indicator when widget is streaming
  if (widgetLoading) {
    const wTitle = state.widget.title || 'Interactive Widget';
    const codeLen = state.widget.code?.length || 0;
    const progress = codeLen < 500 ? 'Setting up structure...'
      : codeLen < 2000 ? 'Adding styles...'
      : 'Writing simulation logic...';
    displayHtml += `<div class="widget-gen-indicator">
      <div class="widget-gen-icon">\u26A1</div>
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

  // Voice mode: don't create text input fallbacks — voice mic + board question handles input
  if (state.teachingMode === 'voice') {
    // Skip all fallback input creation
  } else if (lastInteractiveTag) {
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

  // Voice mode: speak the finalized text (non-blocking — don't await)
  if (typeof voiceHandleFinalizedText === 'function') {
    try { voiceHandleFinalizedText(fullText); } catch {}
  }
}

function ensureFallbackInput() {
  // Voice mode: don't create text fallback — mic + board question handle input
  if (state.teachingMode === 'voice') return;
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

  const canvasCol = document.getElementById('chat-panel');
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
  const structuralTags = new Set(['teaching-plan', 'teaching-plan-update', 'teaching-checkpoint', 'teaching-spotlight-dismiss', 'teaching-notebook-step', 'teaching-notebook-comment', 'teaching-voice-scene']);

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

  // Voice mode: if this is an interactive tag, temporarily show chat pane
  // so the MCQ/freetext controls are visible (they render in #canvas-stream)
  // Only assessment/input tags trigger chat pane slide-in.
  // Videos, sims, widgets render on the board — no layout switch.
  const _voiceInteractiveTags = new Set([
    'teaching-mcq', 'teaching-freetext', 'teaching-agree-disagree',
    'teaching-fillblank', 'teaching-spot-error', 'teaching-confidence',
    'teaching-canvas', 'teaching-teachback',
  ]);
  if (state.teachingMode === 'voice' && _voiceInteractiveTags.has(tag.name)) {
    const mainLayout = $('#main-layout');
    if (mainLayout) {
      mainLayout.classList.remove('voice-mode');
      mainLayout.classList.add('voice-mode-interactive');
    }
    // Hide subtitle and mic during interaction
    voiceHideSubtitle();
    const micFloat = $('#voice-mic-float');
    if (micFloat) micFloat.style.display = 'none';
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
      const shouldClear = tag.attrs.clear !== 'false';
      if (tag.content) {
        tag._boardDrawContent = tag.content;
      }

      if (state.boardDraw._streamingHandled) {
        // This is the board-draw that streaming already parsed commands for.
        // Consume the flag so subsequent board-draw tags are treated fresh.
        state.boardDraw._streamingHandled = false;
        if (tag.content) state.boardDraw.rawContent = tag.content;

        // Open the board panel if streaming didn't (canvas is null).
        // Save/restore the queued commands because openBoardDrawSpotlight
        // may call bdCleanup which wipes them.
        if (!state.boardDraw.canvas) {
          const savedQueue = [...state.boardDraw.commandQueue];
          const savedRaw = state.boardDraw.rawContent;
          const savedComplete = state.boardDraw.complete;
          openBoardDrawSpotlight(bdTitle, null, { clear: shouldClear, skipReference: true });
          state.boardDraw.commandQueue = savedQueue;
          state.boardDraw.rawContent = savedRaw;
          state.boardDraw.active = true;
          state.boardDraw.complete = savedComplete;
          state.boardDraw.dismissed = false;
          state.boardDraw.cancelFlag = false;
        } else {
          const titleEl = $('#spotlight-title');
          if (titleEl) titleEl.textContent = bdTitle;
          if (state.spotlightInfo) state.spotlightInfo.title = bdTitle;
        }
        const refTag = { name: 'teaching-board-draw', attrs: { title: bdTitle } };
        if (state.boardDraw.rawContent) refTag._boardDrawContent = state.boardDraw.rawContent;
        appendSpotlightReference('board-draw', bdTitle, refTag);
      } else {
        // Fresh board-draw: either a second/subsequent board in the same message,
        // history replay, or non-streaming path. Clear and draw from scratch.
        openBoardDrawSpotlight(bdTitle, tag.content || null, { clear: shouldClear });
        state.boardDraw.commandQueue = [];
        const bdLines = (tag.content || '').split('\n');
        for (const bdLine of bdLines) {
          const trimmed = bdLine.trim();
          if (!trimmed) continue;
          try { state.boardDraw.commandQueue.push(JSON.parse(trimmed)); } catch (e) {}
        }
      }
      state.boardDraw.active = true;
      break;
    }
    case 'teaching-board-draw-resume': {
      handleBoardDrawResume(tag);
      break;
    }
    case 'teaching-widget-update': {
      handleWidgetUpdate(tag);
      break;
    }
    case 'teaching-widget': {
      const wTitle = tag.attrs.title || 'Interactive Widget';
      const wCode = tag.content || state.widget.code || '';
      openWidgetSpotlight(wTitle, wCode, state.replayMode);
      // Reset widget streaming state
      state.widget = { active: false, contentStartIdx: 0, complete: false, title: '', code: '', ready: false, pendingParams: null, liveState: {}, assetId: null };
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
    case 'teaching-voice-scene':
      if (state.teachingMode === 'voice') {
        // If eager executor is running, it already set _voiceSceneActive
        if (!_eager.sceneInited) state._voiceSceneActive = true;
        executeVoiceScene(tag).finally(() => {
          state._voiceSceneActive = false;
          _eagerReset();
        });
      }
      // In text mode, voice scenes are ignored — tutor shouldn't generate them
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

  // Voice mode: render inline on board with expand/minimize/close
  if (state.teachingMode === 'voice') {
    renderInlineMedia('video', { lessonId, start, end, label });
    return;
  }

  // Text mode: open in spotlight panel
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

// openAssessmentSpotlight — REMOVED. Assessment renders inline on the board.

function renderAssessmentQuestion(tag, type) {
  // Assessment renders ON THE BOARD as board commands
  state.assessment.questionNumber++;

  // Convert teaching tag to board command and push to board engine
  if (typeof BoardEngine !== 'undefined' && BoardEngine.queueCommand) {
    const progress = { done: state.assessment.questionNumber - 1, total: state.assessment.maxQuestions || 5 };

    switch (type) {
      case 'mcq': {
        const options = [];
        // Parse <option> from tag.content (same regex as renderMCQTag)
        const optRegex = /<option\s+value=(?:"([^"]*)"|'([^']*)')([^>]*)>([^<]*)<\/option>/g;
        let om;
        while ((om = optRegex.exec(tag.content || '')) !== null) {
          options.push({
            value: om[1] || om[2],
            text: om[4],
            correct: (om[3] || '').includes('correct'),
          });
        }
        // Fallback: pipe-separated
        if (!options.length && tag.attrs?.options) {
          tag.attrs.options.split('|').forEach((t, i) => {
            options.push({ value: String.fromCharCode(97 + i), text: t.trim() });
          });
        }
        BoardEngine.queueCommand({
          cmd: 'assess-mcq',
          prompt: tag.attrs?.prompt || tag.attrs?.question || '',
          options: options,
          progress: progress,
        });
        break;
      }
      case 'freetext':
        BoardEngine.queueCommand({
          cmd: 'assess-freetext',
          prompt: tag.attrs?.prompt || '',
          placeholder: tag.attrs?.placeholder || 'Type your answer...',
          progress: progress,
        });
        break;
      case 'spot-error':
        BoardEngine.queueCommand({
          cmd: 'assess-spot-error',
          prompt: tag.attrs?.prompt || 'What\'s wrong?',
          quote: tag.attrs?.quote || '',
          hint: tag.attrs?.hint || '',
          progress: progress,
        });
        break;
      case 'teachback':
        BoardEngine.queueCommand({
          cmd: 'assess-teachback',
          prompt: tag.attrs?.prompt || '',
          placeholder: tag.attrs?.placeholder || '',
          progress: progress,
        });
        break;
      case 'confidence':
        BoardEngine.queueCommand({
          cmd: 'assess-confidence',
          prompt: tag.attrs?.prompt || 'How confident are you?',
        });
        break;
      case 'agree-disagree':
        BoardEngine.queueCommand({
          cmd: 'assess-freetext',
          prompt: (tag.attrs?.prompt || '') + '\n\nDo you agree or disagree? Explain why.',
          placeholder: 'Agree or disagree — explain your reasoning...',
          progress: progress,
        });
        break;
      case 'fillblank':
        BoardEngine.queueCommand({
          cmd: 'assess-freetext',
          prompt: tag.attrs?.prompt || tag.content || '',
          placeholder: 'Fill in the blank...',
          progress: progress,
        });
        break;
      default:
        // Fallback for other types — render inline
        _renderInlineAssessmentFallback(tag, type);
        break;
    }
  } else {
    // Board engine not available — fallback to inline
    _renderInlineAssessmentFallback(tag, type);
  }
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
  if (state.isStreaming) return;
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

  // Voice mode: render inline on board
  if (state.teachingMode === 'voice') {
    renderInlineMedia('simulation', { simId });
    return;
  }

  // Text mode: open in spotlight panel
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
    const res = await fetch(`${state.apiUrl}/api/v1/learning-tools/${simId}`, { headers: AuthManager.authHeaders() });
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
    // Security: only accept messages from our own origin or same-origin iframes
    if (event.origin !== window.location.origin && event.origin !== 'null') return;
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

  updateHeadingBar();
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

  updateHeadingBar();
}

function updateHeadingBar() {
  const bar = $('#plan-heading-bar');
  if (!bar) { console.warn('[HeadingBar] #plan-heading-bar not found'); return; }

  if (state.plan.length === 0) {
    console.log('[HeadingBar] no plan, hiding');
    bar.classList.add('hidden');
    return;
  }
  console.log('[HeadingBar] showing, plan sections:', state.plan.length);
  bar.classList.remove('hidden');

  const current = state.plan.find(s => s.status === 'active');
  const currentTopic = current?.topics?.find(t => t.status === 'active');
  const isDetour = state.detourStack && state.detourStack.length > 0;

  // Section + topic breadcrumb
  const sectionEl = $('#plan-hb-section');
  const topicEl = $('#plan-hb-topic');
  if (sectionEl) sectionEl.textContent = current?.title || '';
  if (topicEl) topicEl.textContent = currentTopic?.title || '';

  // Progress
  let totalTopics = 0, doneTopics = 0;
  for (const step of state.plan) {
    if (step.topics?.length > 0) {
      totalTopics += step.topics.length;
      doneTopics += step.topics.filter(t => t.status === 'done').length;
    } else {
      totalTopics += 1;
      if (step.status === 'done') doneTopics += 1;
    }
  }
  const pct = totalTopics > 0 ? Math.round((doneTopics / totalTopics) * 100) : 0;

  const metaEl = $('#plan-hb-meta');
  if (metaEl) metaEl.textContent = `${doneTopics}/${totalTopics} topics`;
  const fillEl = $('#plan-hb-fill');
  if (fillEl) fillEl.style.width = pct + '%';

  // Detour state
  const detourBadge = $('#plan-hb-detour');
  if (detourBadge) {
    if (isDetour) {
      detourBadge.classList.remove('hidden');
      bar.classList.add('detour');
    } else {
      detourBadge.classList.add('hidden');
      bar.classList.remove('detour');
    }
  }
}

function togglePlanPanel() {
  const overlay = $('#plan-panel-overlay');
  if (!overlay) return;
  const isOpen = !overlay.classList.contains('hidden');
  if (isOpen) {
    overlay.classList.add('hidden');
  } else {
    renderPlanProgress();
    overlay.classList.remove('hidden');
  }
}

function renderPlanProgress() {
  const body = $('#plan-panel-body');
  if (!body) return;

  if (state.plan.length === 0) {
    body.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-dim);font-size:12px;">No plan yet</div>';
    return;
  }

  // Count topics
  let totalTopics = 0, doneTopics = 0;
  for (const step of state.plan) {
    if (step.topics?.length > 0) {
      totalTopics += step.topics.length;
      doneTopics += step.topics.filter(t => t.status === 'done').length;
    } else {
      totalTopics += 1;
      if (step.status === 'done') doneTopics += 1;
    }
  }
  const pct = totalTopics > 0 ? Math.round((doneTopics / totalTopics) * 100) : 0;

  // Objective
  const objective = state.currentPlan?.session_objective || state.currentPlan?.section_title || '';
  let html = '';
  if (objective) {
    html += `<div class="pp-objective">${escapeHtml(objective)}</div>`;
  }

  // Progress bar
  html += `<div class="pp-progress">
    <span>${doneTopics} of ${totalTopics} topics</span>
    <div class="pp-progress-bar"><div class="fill" style="width:${pct}%"></div></div>
    <span>${pct}%</span>
  </div>`;

  // Sections
  const covered = state.plan.filter(s => s.status === 'done');
  const current = state.plan.find(s => s.status === 'active');
  const upcoming = state.plan.filter(s => s.status === 'pending');

  function renderSection(step, badge, badgeClass, headerClass) {
    const icon = step.status === 'done' ? '✓' : step.status === 'active' ? '▸' : '○';
    const title = step.studentLabel || step.title || 'Section ' + step.n;
    let s = `<div class="pp-section">
      <div class="pp-section-header ${headerClass}">
        <span class="icon">${icon}</span>
        <span>${escapeHtml(title)}</span>
        <span class="pp-badge ${badgeClass}">${badge}</span>
      </div>`;
    if (step.topics?.length > 0) {
      s += '<div class="pp-topics">';
      for (const topic of step.topics) {
        const ts = topic.status || 'pending';
        const ti = ts === 'done' ? '✓' : ts === 'active' ? '›' : '○';
        s += `<div class="pp-topic ${ts}"><span class="icon">${ti}</span> ${escapeHtml(topic.title || '')}</div>`;
      }
      s += '</div>';
    }
    // Detour reason
    if (step._detourReason) {
      s += `<div class="pp-detour-reason">${escapeHtml(step._detourReason)}</div>`;
    }
    s += '</div>';
    return s;
  }

  if (covered.length > 0) {
    for (const step of covered) html += renderSection(step, 'DONE', 'done', 'done');
  }
  if (current) {
    html += renderSection(current, 'NOW', 'now', 'active');
  }
  for (const step of upcoming) {
    html += renderSection(step, 'UP NEXT', 'next', 'pending');
  }

  body.innerHTML = html;
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
    'spawn_agents', 'check_agents', 'advance_topic', 'delegate_teaching',
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
      const res = await fetch(`${state.apiUrl}/api/v1/learning-tools/${simId}`, { headers: AuthManager.authHeaders() });
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
  var typeIcons = { video: '\u25B6', simulation: '\u2697', notebook: '\u{1F4D3}', image: '\u25A3', 'board-draw': '\u270E', widget: '\u26A1' };
  var icon = typeIcons[type] || '\u25C6';

  const historyEntry = { id: refId, type, title, tag: reopenTag };
  if (type === 'board-draw' && reopenTag._boardDrawContent) {
    historyEntry.boardDrawContent = reopenTag._boardDrawContent;
  }
  if (type === 'board-draw' && reopenTag._snapshot) {
    historyEntry.snapshot = reopenTag._snapshot; // PNG fallback for voice scenes
  }
  if (type === 'widget' && reopenTag._widgetCode) {
    historyEntry.widgetCode = reopenTag._widgetCode;
  }
  state.spotlightHistory.push(historyEntry);

  // Track assetId on current spotlight
  if (state.spotlightInfo) {
    state.spotlightInfo.assetId = refId;
  }

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

  // Capture thumbnail from board content before it gets cleared
  let thumbDataUrl = null;
  try {
    const content = $('#spotlight-content');
    if (content) {
      const canvas = content.querySelector('canvas');
      if (canvas) {
        thumbDataUrl = canvas.toDataURL('image/png', 0.3);
      }
    }
  } catch (e) {}

  // Also add to board frame strip
  addBoardFrameThumb(refId, type, title, thumbDataUrl);
}

// ── Board history overlay (voice mode) ──────────────────────
// Shows a previous board as an overlay WITHOUT destroying the live board.
// The live canvas + animations stay hidden underneath.

function _showBoardHistoryOverlay(entry) {
  const content = $('#spotlight-content');
  if (!content) return;

  // Create or get the history overlay div
  let overlay = document.getElementById('board-history-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'board-history-overlay';
    overlay.style.cssText = 'position:absolute;inset:0;z-index:30;background:#1a1d2e;display:flex;flex-direction:column;';
    content.style.position = 'relative';
    content.appendChild(overlay);
  }

  // Hide the live board content (canvas, animations) behind the overlay
  const bdContainer = content.querySelector('.bd-container');
  if (bdContainer) bdContainer.style.visibility = 'hidden';

  // Build overlay content
  let imgSrc = entry.snapshot || '';
  if (!imgSrc && entry.boardDrawContent) {
    // No snapshot but has draw content — show placeholder
    imgSrc = '';
  }

  overlay.innerHTML = `
    <div style="padding:8px 12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid rgba(255,255,255,0.07)">
      <span style="font-size:11px;color:var(--text-dim)">Viewing: ${escapeHtml(entry.title || 'Previous board')}</span>
      <button onclick="returnToLiveBoard()" style="margin-left:auto;padding:4px 12px;border-radius:6px;border:1px solid var(--accent-dim);background:var(--accent-dim);color:var(--accent);font-size:11px;font-weight:600;cursor:pointer;font-family:var(--font-sans)">&#9654; Return to Live</button>
    </div>
    <div style="flex:1;display:flex;align-items:center;justify-content:center;overflow:auto;padding:16px">
      ${imgSrc
        ? `<img src="${imgSrc}" style="max-width:100%;max-height:100%;object-fit:contain;border-radius:6px" alt="Board history"/>`
        : '<div style="color:var(--text-dim);font-size:13px">Board snapshot not available</div>'
      }
    </div>
  `;
  overlay.style.display = 'flex';

  // Update title
  const titleEl = $('#spotlight-title');
  if (titleEl) titleEl.textContent = entry.title || 'Previous Board';
}

// Return to live board — remove the history overlay, show live canvas again
window.returnToLiveBoard = function() {
  // Remove history overlay
  const overlay = document.getElementById('board-history-overlay');
  if (overlay) overlay.remove();

  // Unhide the live board content
  const content = $('#spotlight-content');
  if (content) {
    const bdContainer = content.querySelector('.bd-container');
    if (bdContainer) bdContainer.style.visibility = '';
  }

  // Restore title
  if (state.spotlightInfo?.title) {
    const titleEl = $('#spotlight-title');
    if (titleEl) titleEl.textContent = state.spotlightInfo.title;
  }

  // Deactivate all frame strip thumbs
  const strip = $('#board-frame-strip');
  if (strip) strip.querySelectorAll('.board-frame-thumb').forEach(t => t.classList.remove('active'));

  // Hide the header "Live" button (no longer needed)
  const liveBtn = $('#board-live-btn');
  if (liveBtn) liveBtn.classList.add('hidden');
};

function addBoardFrameThumb(refId, type, title, thumbDataUrl) {
  const strip = $('#board-frame-strip');
  if (!strip) return;

  const thumb = document.createElement('div');
  thumb.className = 'board-frame-thumb';
  thumb.title = title;
  thumb.onclick = () => {
    strip.querySelectorAll('.board-frame-thumb').forEach(t => t.classList.remove('active'));
    thumb.classList.add('active');
    reopenSpotlight(refId);
  };

  if (thumbDataUrl) {
    // Real canvas thumbnail
    thumb.innerHTML = `
      <img src="${thumbDataUrl}" style="width:100%;height:100%;object-fit:cover" />
      <div style="position:absolute;bottom:0;left:0;right:0;font-size:7px;color:#fff;background:rgba(0,0,0,0.75);padding:1px 3px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${escapeHtml(title)}</div>`;
  } else {
    // Icon fallback
    const icons = { video: '\u25B6', simulation: '\u2697', 'board-draw': '\u270E', widget: '\u26A1', image: '\u25A3' };
    const ic = icons[type] || '\u25C6';
    thumb.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;font-size:16px;color:var(--text-dim)">' + ic + '</div>' +
      '<div style="position:absolute;bottom:0;left:0;right:0;font-size:7px;color:var(--text-dim);background:rgba(0,0,0,0.7);padding:1px 3px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">' + escapeHtml(title) + '</div>';
  }
  thumb.style.position = 'relative';
  strip.appendChild(thumb);

  // Auto-scroll strip to show latest
  strip.scrollLeft = strip.scrollWidth;
}

window.reopenSpotlight = function(refId) {
  const entry = state.spotlightHistory.find(e => e.id === refId);
  if (!entry) return;

  // Voice mode: use overlay approach — hide live board, show history on top
  if (state.teachingMode === 'voice') {
    voiceStopCurrent();
    voiceHideSubtitle();
    voiceHideHand();

    // Show history overlay (snapshot or replay) — live board stays hidden underneath
    if (entry.type === 'board-draw') {
      _showBoardHistoryOverlay(entry);
      return;
    }
  }

  if (entry.type === 'video' && entry.tag.lessonId !== undefined) {
    openVideoInSpotlight(entry.tag.lessonId, entry.tag.start, entry.tag.end, entry.tag.label, { skipReference: true });
  } else if (entry.type === 'board-draw' && entry.boardDrawContent) {
    // Text mode: replay board-draw with stored commands (instant replay)
    const bdTitle = entry.title || 'Board';
    openBoardDrawSpotlight(bdTitle, entry.boardDrawContent, { skipReference: true });
    state.boardDraw.commandQueue = [];
    state.boardDraw._instantReplayCount = 999;
    const bdLines = entry.boardDrawContent.split('\n');
    for (const ln of bdLines) {
      const trimmed = ln.trim();
      if (!trimmed) continue;
      try { state.boardDraw.commandQueue.push(JSON.parse(trimmed)); } catch (e) {}
    }
    state.boardDraw.active = true;
  } else if (entry.type === 'board-draw' && entry.snapshot) {
    // Text mode fallback: show snapshot
    const content = $('#spotlight-content');
    if (content) {
      content.innerHTML = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#1a1d2e">
        <img src="${entry.snapshot}" style="max-width:100%;max-height:100%;object-fit:contain" alt="Board snapshot"/></div>`;
    }
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
  // Split view: board panel is already visible — no fullscreen toggle needed
  // The old notebook-fullscreen class breaks the split layout, so skip it
}

function exitSpotlightFullscreen() {
  // Split view: no-op (see enterSpotlightFullscreen)
  const mainLayout = $('#main-layout');
  if (mainLayout) mainLayout.classList.remove('notebook-fullscreen');
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

  // Capture thumbnail before clearing (for board frame strip)
  if (content) {
    try {
      var captureCanvas = content.querySelector('canvas');
      if (captureCanvas && state.spotlightHistory.length > 0) {
        var lastEntry = state.spotlightHistory[state.spotlightHistory.length - 1];
        var thumbUrl = captureCanvas.toDataURL('image/png', 0.3);
        // Update the frame strip thumbnail
        var strip = document.getElementById('board-frame-strip');
        if (strip && strip.lastElementChild) {
          var img = strip.lastElementChild.querySelector('img');
          if (!img) {
            // Replace icon with real thumbnail
            strip.lastElementChild.innerHTML = '<img src="' + thumbUrl + '" style="width:100%;height:100%;object-fit:cover" />' +
              '<div style="position:absolute;bottom:0;left:0;right:0;font-size:7px;color:#fff;background:rgba(0,0,0,0.75);padding:1px 3px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">' +
              (lastEntry.title || '') + '</div>';
          }
        }
      }
    } catch (e) {}
  }

  // Clean up widget iframe bridge listener before clearing content
  if (state.spotlightInfo?.type === 'widget') {
    var wIframe = content ? content.querySelector('.widget-iframe') : null;
    if (wIframe && wIframe._bridgeCleanup) wIframe._bridgeCleanup();
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
  updateBoardEmptyState();

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
  if (state.isStreaming) return;
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
  if (state.isStreaming) return;
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
// Split View: Quick Actions, Board Fullscreen, Resize Handle
// ═══════════════════════════════════════════════════════════

// Quick action buttons
window.quickAction = function(action) {
  if (state.isStreaming) return;
  const topic = state.spotlightInfo?.title || 'current topic';
  var messages = {
    got_it: "[Confirms understanding of: " + topic + "] Got it, I understand this.",
    not_sure: "[Unsure about: " + topic + "] I'm not sure I fully get this. Can you explain differently?",
    stuck: "[Stuck on: " + topic + "] I'm stuck. Can we try a different approach or watch a video clip?",
  };
  const msg = messages[action];
  if (msg) sendStudentResponse(msg);
};

// Board fullscreen toggle
window.toggleBoardFullscreen = function() {
  const panel = $('#board-panel');
  if (!panel) return;
  panel.classList.toggle('fullscreen');
  const btn = $('#board-fullscreen');
  if (btn) btn.textContent = panel.classList.contains('fullscreen') ? '✕' : '⛶';
};

// Split resize handle
(function initSplitResize() {
  const handle = document.getElementById('split-handle');
  if (!handle) return;
  let dragging = false;
  let startX, startChatW, startBoardW;

  handle.addEventListener('mousedown', e => {
    dragging = true;
    startX = e.clientX;
    const chat = document.getElementById('chat-panel');
    const board = document.getElementById('board-panel');
    if (chat && board) {
      startChatW = chat.offsetWidth;
      startBoardW = board.offsetWidth;
    }
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const dx = e.clientX - startX;
    const chat = document.getElementById('chat-panel');
    const board = document.getElementById('board-panel');
    if (chat && board) {
      const newChatW = Math.max(280, startChatW + dx);
      const newBoardW = Math.max(300, startBoardW - dx);
      chat.style.flex = `0 0 ${newChatW}px`;
      board.style.flex = `0 0 ${newBoardW}px`;
    }
  });

  document.addEventListener('mouseup', () => {
    if (dragging) {
      dragging = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  });
})();

// Hide/show board empty state based on spotlight content
function updateBoardEmptyState() {
  const content = $('#spotlight-content');
  const empty = $('#board-empty-state');
  if (!empty) return;
  empty.style.display = (content && content.innerHTML.trim()) ? 'none' : '';
}

// Auto-detect when board content changes
setTimeout(() => {
  const content = document.getElementById('spotlight-content');
  if (content) {
    new MutationObserver(updateBoardEmptyState).observe(content, { childList: true, subtree: true });
  }
  updateBoardEmptyState();
}, 500);

// ═══════════════════════════════════════════════════════════
// Module 19: Timer & Stats
// ═══════════════════════════════════════════════════════════

let timerInterval = null;

function startTimer() {
  if (timerInterval) clearInterval(timerInterval);
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
  if (statEl) {
    const svg = statEl.querySelector('svg');
    const svgHTML = svg ? svg.outerHTML + ' ' : '';
    statEl.innerHTML = svgHTML + timeStr;
  }
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

    // Always show session panel
    listPanel.classList.remove('hidden');
    firstTime.classList.add('hidden');

    // Show/hide empty state
    const emptyMsg = document.getElementById('dash-session-empty');

    if (sessions.length === 0) {
      if (emptyMsg) emptyMsg.style.display = '';
      const activeContainer = document.getElementById('session-list-active');
      if (activeContainer) activeContainer.innerHTML = '';
      return;
    }

    if (emptyMsg) emptyMsg.style.display = 'none';

    const active = sessions.filter(s => s.status === 'active');
    const completed = sessions.filter(s => s.status === 'complete');
    renderSessionCards(active, completed);
  } catch (e) {
    console.warn('Failed to fetch sessions:', e);
    setStatus('');
    // Still show session panel with empty state
    listPanel.classList.remove('hidden');
    firstTime.classList.add('hidden');
    const emptyMsg = document.getElementById('dash-session-empty');
    if (emptyMsg) emptyMsg.style.display = '';
    const activeContainer = document.getElementById('session-list-active');
    if (activeContainer) activeContainer.innerHTML = '';
  }
}

const SESSIONS_PER_PAGE = 4;
let _allSessions = { active: [], completed: [] };

function renderSessionCards(active, completed) {
  const activeContainer = $('#session-list-active');
  const completedItemsContainer = $('#session-list-completed-items');
  const completedToggle = $('#btn-show-completed');
  if (!activeContainer) return;

  _allSessions.active = active.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));
  _allSessions.completed = completed.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));

  const emptyMsg = document.getElementById('dash-session-empty');
  if (emptyMsg) emptyMsg.style.display = 'none';

  activeContainer.innerHTML = '';

  // Search box — rendered above the grid, inside session-list-panel
  const existingSearch = document.getElementById('dash-session-search');
  if (existingSearch) existingSearch.remove();
  if (active.length + completed.length > 4) {
    const searchEl = document.createElement('input');
    searchEl.type = 'text';
    searchEl.className = 'dash-session-search';
    searchEl.id = 'dash-session-search';
    searchEl.placeholder = 'Search sessions...';
    activeContainer.parentElement.insertBefore(searchEl, activeContainer);
  }

  _renderSessionBatch(activeContainer, _allSessions.active, true, SESSIONS_PER_PAGE);

  if (completedItemsContainer && completedToggle) {
    if (completed.length > 0) {
      completedToggle.classList.remove('hidden');
      completedItemsContainer.innerHTML = '';
      _renderSessionBatch(completedItemsContainer, _allSessions.completed, false, SESSIONS_PER_PAGE);
      completedToggle.onclick = () => {
        completedItemsContainer.classList.toggle('hidden');
        completedToggle.classList.toggle('expanded', !completedItemsContainer.classList.contains('hidden'));
      };
    } else {
      completedToggle.classList.add('hidden');
      completedItemsContainer.innerHTML = '';
    }
  }

  // Wire search — client-side instant + server semantic for 3+ chars
  const searchInput = document.getElementById('dash-session-search');
  if (searchInput) {
    let _searchDebounce = null;
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.trim();
      const qLower = q.toLowerCase();

      // Instant client-side filter
      const fActive = _allSessions.active.filter(s => _sessionMatchesQuery(s, qLower));
      const fCompleted = _allSessions.completed.filter(s => _sessionMatchesQuery(s, qLower));
      activeContainer.querySelectorAll('.dash-sessions-grid-inner, .dash-show-more').forEach(el => el.remove());
      _renderSessionBatch(activeContainer, fActive, true, q ? 100 : SESSIONS_PER_PAGE);
      if (completedItemsContainer) {
        completedItemsContainer.innerHTML = '';
        _renderSessionBatch(completedItemsContainer, fCompleted, false, q ? 100 : SESSIONS_PER_PAGE);
      }

      // Debounced semantic search for 3+ chars
      if (_searchDebounce) clearTimeout(_searchDebounce);
      if (q.length >= 3 && state.courseId) {
        _searchDebounce = setTimeout(async () => {
          try {
            const url = `${state.apiUrl}/api/v1/sessions/search/${state.courseId}?q=${encodeURIComponent(q)}`;
            const opts = AuthManager.isLoggedIn() ? { headers: AuthManager.authHeaders() } : {};
            const res = await fetch(url, opts);
            if (!res.ok) return;
            const results = await res.json();
            if (searchInput.value.trim() !== q) return; // stale
            if (results.length > 0) {
              const semanticActive = results.filter(s => s.status === 'active');
              const semanticCompleted = results.filter(s => s.status !== 'active');
              activeContainer.querySelectorAll('.dash-sessions-grid-inner, .dash-show-more').forEach(el => el.remove());
              _renderSessionBatch(activeContainer, semanticActive, true, 100);
              if (completedItemsContainer) {
                completedItemsContainer.innerHTML = '';
                _renderSessionBatch(completedItemsContainer, semanticCompleted, false, 100);
              }
            }
          } catch (e) { console.debug('Semantic search failed:', e); }
        }, 400);
      }
    });
  }
}

function _sessionMatchesQuery(s, q) {
  if (!q) return true;
  return [s.headline, s.headlineDescription, s.intent?.raw, ...(s.sections || []).map(x => x.title)]
    .filter(Boolean).join(' ').toLowerCase().includes(q);
}

function _renderSessionBatch(container, sessions, isActive, limit) {
  const shown = sessions.slice(0, limit);
  const grid = document.createElement('div');
  grid.className = 'dash-sessions-grid-inner';
  grid.innerHTML = shown.map(s => _buildCard(s, isActive)).join('');
  container.appendChild(grid);

  if (sessions.length > limit) {
    const btn = document.createElement('button');
    btn.className = 'dash-show-more';
    btn.textContent = `Show more (${sessions.length - limit} remaining)`;
    btn.onclick = () => {
      const count = container.querySelectorAll('.dash-session-card').length;
      const next = sessions.slice(count, count + SESSIONS_PER_PAGE);
      next.forEach(s => grid.insertAdjacentHTML('beforeend', _buildCard(s, isActive)));
      const rem = sessions.length - container.querySelectorAll('.dash-session-card').length;
      if (rem > 0) { btn.textContent = `Show more (${rem} remaining)`; }
      else btn.remove();
    };
    container.appendChild(btn);
  }
}

function _buildCard(s, isActive) {
  let title = s.headline || '';
  if (!title || /^Session \d+$/.test(title)) {
    title = (s.intent && s.intent.raw) || '';
  }
  if (!title) {
    // Use first section title as fallback
    const sec = (s.sections || [])[0];
    title = sec ? sec.title : 'Untitled session';
  }
  title = escapeHtml(title);
  const desc = escapeHtml(s.headlineDescription || '');
  const ago = _timeAgo(s.startedAt);
  const dur = _fmtDur(s.durationSec);
  const cls = isActive ? 'active' : 'done';
  const click = s.sessionId ? ` onclick="Router.navigate('/session/${escapeAttr(s.sessionId)}')"` : '';

  // Tooltip
  const sections = s.sections || [];
  let tip = '';
  if (sections.length > 0) {
    tip = '<div class="dash-session-tooltip"><div class="dash-tooltip-topics">';
    sections.slice(0, 5).forEach(sec => {
      const ic = sec.status === 'done' ? '\u2713' : sec.status === 'active' ? '\u25CF' : '\u25CB';
      const c2 = sec.status === 'done' ? 'done' : sec.status === 'active' ? 'active' : '';
      tip += '<div class="dash-tooltip-topic ' + c2 + '"><span>' + ic + '</span> ' + escapeHtml(sec.title || '') + '</div>';
    });
    if (sections.length > 5) tip += '<div class="dash-tooltip-more">+' + (sections.length - 5) + ' more</div>';
    tip += '</div></div>';
  }

  return `<div class="dash-session-card dash-session-${cls}"${click}>
    <div class="dash-session-card-top">
      <span class="dash-session-ago">${ago}</span>
      ${dur ? `<span class="dash-session-dur-inline">${dur}</span>` : ''}
    </div>
    <div class="dash-session-headline">${title}</div>
    ${desc ? `<div class="dash-session-desc">${desc}</div>` : ''}
    <div class="dash-session-resume">${isActive ? 'Continue' : 'Review'} <span>&rarr;</span></div>
    ${tip}
  </div>`;
}

function _timeAgo(d) {
  if (!d) return '';
  const ms = Date.now() - new Date(d).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return m + 'm ago';
  const h = Math.floor(m / 60);
  if (h < 24) return h + 'h ago';
  const dy = Math.floor(h / 24);
  if (dy === 1) return 'Yesterday';
  if (dy < 7) return dy + 'd ago';
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function _fmtDur(sec) {
  if (!sec) return '';
  const m = Math.round(sec / 60);
  if (m < 60) return m + 'm';
  const h = Math.floor(m / 60), r = m % 60;
  return r > 0 ? h + 'h ' + r + 'm' : h + 'h';
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

// ─── Init & Screen Management ─────────────────────────────

const ALL_SCREENS = ['landing-screen', 'login-panel', 'browse-screen', 'course-screen', 'ondemand-screen', 'business-screen'];

function _hideAllScreens() {
  ALL_SCREENS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  document.getElementById('teaching-layout')?.classList.add('hidden');
  // Stop BYO materials polling when switching screens
  if (typeof _byoPollTimer !== 'undefined' && _byoPollTimer) {
    clearInterval(_byoPollTimer); _byoPollTimer = null;
  }
}

function _updateUserPills() {
  const user = AuthManager.getUser();
  if (!user) return;
  const initial = user.name.charAt(0).toUpperCase();
  const firstName = user.name.split(' ')[0];
  // Update all avatar/name elements across screens
  ['dash-avatar', 'course-avatar', 'od-avatar'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = initial;
  });
  ['dash-user-name', 'course-user-name', 'od-user-name'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = firstName;
  });
}

function showScreen(screenName, param) {
  UIHints.removeAll();
  cleanupActiveSession();
  disconnectAgentEvents();
  if (timerInterval) clearInterval(timerInterval);
  // Stop BYO materials poll when leaving home/materials
  if (_byoPollTimer) { clearInterval(_byoPollTimer); _byoPollTimer = null; }
  _hideAllScreens();

  const user = AuthManager.getUser();
  if (screenName !== 'landing' && !user) {
    return Router.navigate('/login', { replace: true });
  }

  if (user) {
    state.studentName = user.name;
    state.userEmail = user.email;
    _updateUserPills();
  }

  switch (screenName) {
    case 'landing':
      document.getElementById('landing-screen').style.display = 'block';
      document.body.style.overflow = 'auto';
      document.body.style.height = 'auto';
      _loadLandingCourses();
      break;

    case 'business':
      document.getElementById('business-screen').style.display = 'block';
      document.body.style.overflow = 'auto';
      document.body.style.height = 'auto';
      break;

    case 'browse':
      document.getElementById('browse-screen').style.display = 'block';
      document.body.style.overflow = 'auto';
      document.body.style.height = 'auto';
      // Set greeting with name
      const browseGreeting = document.getElementById('browse-greeting');
      if (browseGreeting && user) {
        const firstName = user.name.split(' ')[0];
        const hour = new Date().getHours();
        const timeGreeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
        browseGreeting.textContent = `${timeGreeting}, ${firstName}`;
      }
      // Restore Euler state — keeps chat if there's history
      _eulerResetToIdle();
      // Load home sections (sessions, courses, videos)
      _loadHomeSections();
      _fetchCourses();
      break;

    case 'course':
      document.getElementById('course-screen').style.display = 'block';
      document.body.style.overflow = 'auto';
      document.body.style.height = 'auto';
      // Reset start button
      const modeBtn = document.getElementById('cd-mode-start-btn');
      if (modeBtn) { modeBtn.disabled = false; modeBtn.innerHTML = 'Start learning <span>&rarr;</span>'; }
      if (param) _loadCourseDetail(parseInt(param));
      break;

    case 'ondemand':
      document.getElementById('ondemand-screen').style.display = 'block';
      document.body.style.overflow = 'auto';
      document.body.style.height = 'auto';
      break;
  }

  window.scrollTo({ top: 0, behavior: 'instant' });
}

// Keep old names for backward compat
function showLandingPanel() { showScreen('landing'); }
function showSetupPanel() { showScreen('browse'); }

function showLoginPanel() {
  UIHints.removeAll();
  _hideAllScreens();
  if (typeof DashBg !== 'undefined') DashBg.start();
  document.getElementById('login-panel').style.display = 'flex';
  document.body.style.overflow = 'hidden';
  document.body.style.height = '100vh';
}

function updateCourseCardSelection() { /* no-op — old dashboard compat */ }

// ─── Dynamic course loading ──────────────────────────────

let _cachedCourses = null;
const _COURSE_CACHE_KEY = 'capacity_courses';
const _COURSE_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function _fetchCourses() {
  if (_cachedCourses) return _cachedCourses;

  // Check sessionStorage first — instant on navigation
  try {
    const cached = sessionStorage.getItem(_COURSE_CACHE_KEY);
    if (cached) {
      const { data, ts } = JSON.parse(cached);
      if (Date.now() - ts < _COURSE_CACHE_TTL) {
        _cachedCourses = data;
        return _cachedCourses;
      }
    }
  } catch (e) { /* ignore */ }

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/content/courses`, {
      headers: AuthManager.authHeaders(),
    });
    if (res.ok) {
      _cachedCourses = await res.json();
      try { sessionStorage.setItem(_COURSE_CACHE_KEY, JSON.stringify({ data: _cachedCourses, ts: Date.now() })); } catch (e) { /* quota */ }
      return _cachedCourses;
    }
  } catch (e) { console.warn('Failed to fetch courses:', e); }
  // Fallback static list (used when API is unavailable)
  return [
    { id: 2, title: 'MIT 8.04 Quantum Physics I', description: 'Wave mechanics, Schrodinger equation in one and three dimensions.', lesson_count: 24, module_count: 5, subject: 'Physics', thumbnail: 'https://img.youtube.com/vi/lZ3bPUKo5zc/hqdefault.jpg' },
    { id: 7, title: 'Calculus 1: Pre-Calc to Differentiation', description: 'Complete calculus course from pre-calculus review through derivatives.', lesson_count: 15, module_count: 4, subject: 'Mathematics', thumbnail: 'https://img.youtube.com/vi/fYyARMqiaag/hqdefault.jpg' },
    { id: 5, title: 'Electricity & Magnetism', description: 'Electric fields, Gauss\'s law, circuits, and magnetic fields.', lesson_count: 2, module_count: 1, subject: 'Physics', thumbnail: '' },
    { id: 4, title: 'Quantum Mechanics', description: 'Operators, eigenvalues, measurement, and the hydrogen atom.', lesson_count: 4, module_count: 1, subject: 'Physics', thumbnail: '' },
    { id: 3, title: 'Classical Mechanics', description: "Newton's laws, energy conservation, rotational dynamics.", lesson_count: 3, module_count: 1, subject: 'Physics', thumbnail: 'https://img.youtube.com/vi/oduZsA0Tk58/hqdefault.jpg' },
  ];
}

function _courseThumbStyle(course) {
  // Returns just the CSS value (no "background:" prefix — callers add that)
  const thumb = (course.thumbnail || '').trim().replace(/^\s+/, '');
  if (thumb && thumb.startsWith('http')) {
    return `url('${thumb}') center/cover no-repeat, linear-gradient(135deg,#151530,#111113)`;
  }
  const s = (course.subject || course.title || '').toLowerCase();
  if (s.includes('math')) return 'linear-gradient(135deg,#152015,#111113)';
  if (s.includes('electr') || s.includes('magnet')) return 'linear-gradient(135deg,#251515,#111113)';
  if (s.includes('computer') || s.includes('dsa')) return 'linear-gradient(135deg,#151520,#111113)';
  return 'linear-gradient(135deg,#151530,#111113)';
}

function _courseTagClass(course) {
  const s = (course.subject || '').toLowerCase();
  if (s.includes('math')) return 'tag-math';
  if (s.includes('computer')) return 'tag-cs';
  return 'tag-physics';
}

function _guessSubject(title) {
  const t = (title || '').toLowerCase();
  if (/calculus|algebra|math|geometry/.test(t)) return 'Mathematics';
  if (/quantum|physics|mechanic|electr|magnet/.test(t)) return 'Physics';
  if (/computer|algorithm|dsa|programming/.test(t)) return 'Computer Science';
  return 'Course';
}

async function _loadLandingCourses() {
  const grid = document.getElementById('lp-courses-grid');
  if (!grid || grid.dataset.loaded) return;
  // Show skeleton immediately
  grid.innerHTML = Array.from({ length: 3 }, () =>
    `<div class="pcard"><div class="pcard-thumb skeleton-pulse"></div><div class="pcard-body"><div class="skeleton-line w60"></div><div class="skeleton-line w40"></div></div></div>`
  ).join('');
  const courses = await _fetchCourses();
  grid.dataset.loaded = '1';
  grid.innerHTML = courses.slice(0, 3).map(c => `
    <div class="pcard" data-course-id="${c.id}">
      <div class="pcard-thumb" style="background:${_courseThumbStyle(c)}">

        <span class="count">${c.lesson_count || '?'} lessons</span>
      </div>
      <div class="pcard-body">
        <h4>${c.title}</h4>
        <span>${c.subject || ''} &middot; ~${Math.round((c.lesson_count || 1) * 1.3)} hrs</span>
      </div>
    </div>
  `).join('');
  grid.querySelectorAll('.pcard').forEach(card => {
    card.addEventListener('click', () => {
      if (AuthManager.isLoggedIn()) Router.navigate('/courses/' + card.dataset.courseId);
      else Router.navigate('/login');
    });
  });
}

function _skeletonCards(n, container) {
  container.innerHTML = Array.from({ length: n }, () =>
    `<div class="ccard ccard-skeleton"><div class="ccard-thumb skeleton-pulse"></div><div class="ccard-body"><div class="skeleton-line w60"></div><div class="skeleton-line w90"></div></div></div>`
  ).join('');
}

async function _loadBrowseCourses() {
  const grid = document.getElementById('browse-courses-grid');
  if (!grid) return;

  // Show skeletons immediately
  _skeletonCards(4, grid);

  const courses = await _fetchCourses();
  const countEl = document.getElementById('browse-course-count');
  if (countEl) countEl.textContent = `${courses.length} courses`;

  grid.innerHTML = courses.map(c => `
    <div class="ccard" data-course-id="${c.id}">
      <div class="ccard-thumb" style="background:${_courseThumbStyle(c)}">

        <span class="tag ${_courseTagClass(c)}">${c.subject || 'Course'}</span>
        <div class="meta"><span>${c.lesson_count || '?'} lessons</span><span>~${Math.round((c.lesson_count || 1) * 1.3)} hrs</span></div>
      </div>
      <div class="ccard-body">
        <h3>${c.title}</h3>
        <p>${c.description || ''}</p>
      </div>
      <div class="ccard-cta">
        <span class="ccard-lessons">${c.lesson_count || '?'} lessons &middot; ${c.subject || 'Course'}</span>
        <span>Start learning &rarr;</span>
      </div>
    </div>
  `).join('');
  grid.querySelectorAll('.ccard').forEach(card => {
    card.addEventListener('click', () => Router.navigate('/courses/' + card.dataset.courseId));
  });

  // Show "Show all" button if more than 3 courses
  const showAllEl = document.getElementById('browse-show-all');
  if (showAllEl) {
    showAllEl.style.display = courses.length > 3 ? '' : 'none';
  }
}

let _courseDetailData = null; // raw API data for current course detail

// ═══════════════════════════════════════════════════════════════
//   Euler — Home screen AI companion
// ═══════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════
//   Home tabs
// ═══════════════════════════════════════════════════════════════

function _initHomeTabs() {
  document.querySelectorAll('.home-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.home-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.home-tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById('tab-' + tab.dataset.homeTab);
      if (target) target.classList.add('active');
      // Load content for the tab if needed
      if (tab.dataset.homeTab === 'home') { _loadHomeSections(); }
      if (tab.dataset.homeTab === 'content') { _loadByoMaterials(); _loadLearningAids(); }
      // Legacy compat
      if (tab.dataset.homeTab === 'explore') { _loadBrowseCourses(); _loadRecentSessions(); _loadMyVideos(); }
      if (tab.dataset.homeTab === 'materials') { _loadByoMaterials(); _loadLearningAids(); }
    });
  });

  // Explore tab search
  const searchInput = document.getElementById('explore-search-input');
  if (searchInput) {
    let _timer = null;
    searchInput.addEventListener('input', () => {
      clearTimeout(_timer);
      _timer = setTimeout(() => _filterBrowseCourses(searchInput.value), 200);
    });
  }
}

function _loadHomeSections() {
  // Show skeleton placeholders immediately, then load real data with staggered reveal
  _showHomeSkeletons();
  _loadHomeSessions();
  _loadHomeVideos();
  _loadHomeCourses();
}

function _showHomeSkeletons() {
  const sessSection = document.getElementById('home-sessions-section');
  const sessRow = document.getElementById('home-sessions-row');
  const vidSection = document.getElementById('home-videos-section');
  const vidRow = document.getElementById('home-videos-row');
  const courseSection = document.getElementById('home-courses-section');
  const courseGrid = document.getElementById('home-courses-grid');

  // Sessions skeleton
  if (sessSection && sessRow) {
    sessRow.innerHTML = Array(3).fill('<div class="skeleton-card"></div>').join('');
    sessSection.style.display = '';
    sessSection.style.opacity = '0.5';
  }
  // Videos skeleton
  if (vidSection && vidRow) {
    vidRow.innerHTML = Array(2).fill('<div class="skeleton-card"></div>').join('');
    vidSection.style.display = '';
    vidSection.style.opacity = '0.5';
  }
  // Courses skeleton
  if (courseSection && courseGrid) {
    courseGrid.innerHTML = Array(3).fill('<div class="skeleton-course"></div>').join('');
    courseSection.style.display = '';
    courseSection.style.opacity = '0.5';
  }
}

function _revealHomeSection(section, delay) {
  if (!section) return;
  setTimeout(() => {
    section.style.opacity = '';
    section.classList.add('home-section-reveal');
  }, delay);
}

async function _loadHomeSessions() {
  const section = document.getElementById('home-sessions-section');
  const row = document.getElementById('home-sessions-row');
  if (!section || !row) return;

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/sessions/me/all`, { headers: AuthManager.authHeaders() });
    if (!res.ok) { section.style.display = 'none'; return; }
    const sessions = await res.json();
    if (!sessions.length) { section.style.display = 'none'; return; }

    row.innerHTML = '';
    for (const s of sessions.slice(0, 6)) {
      row.appendChild(_buildSessionCard(s, !!s.courseId));
    }
    _revealHomeSection(section, 0);
  } catch (e) { section.style.display = 'none'; }
}

async function _loadHomeCourses() {
  const section = document.getElementById('home-courses-section');
  const grid = document.getElementById('home-courses-grid');
  if (!section || !grid) return;

  const courses = await _fetchCourses();
  if (!courses || !courses.length) { section.style.display = 'none'; return; }

  const countEl = document.getElementById('home-course-count');
  if (countEl) countEl.textContent = `${courses.length} courses`;

  // Reuse the same card HTML as _loadBrowseCourses
  grid.innerHTML = courses.slice(0, 4).map(c => `
    <div class="ccard" data-course-id="${c.id}">
      <div class="ccard-thumb" style="background:${_courseThumbStyle(c)}">
        <span class="tag ${_courseTagClass(c)}">${c.subject || 'Course'}</span>
        <div class="meta"><span>${c.lesson_count || '?'} lessons</span><span>~${Math.round((c.lesson_count || 1) * 1.3)} hrs</span></div>
      </div>
      <div class="ccard-body">
        <h3>${c.title}</h3>
        <p>${(c.description || '').slice(0, 100)}${(c.description || '').length > 100 ? '...' : ''}</p>
      </div>
    </div>
  `).join('');
  grid.querySelectorAll('.ccard').forEach(card => {
    card.addEventListener('click', () => Router.navigate('/courses/' + card.dataset.courseId));
  });
  _revealHomeSection(section, 150);
}

async function _loadHomeVideos() {
  const section = document.getElementById('home-videos-section');
  const row = document.getElementById('home-videos-row');
  if (!section || !row) return;

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections`, { headers: AuthManager.authHeaders() });
    if (!res.ok) { section.style.display = 'none'; return; }
    const collections = await res.json();

    const videos = collections.filter(c => {
      const t = (c.title || '').toLowerCase();
      const d = (c.description || '').toLowerCase();
      const tags = c.tags || [];
      return t.includes('video') || t.includes('youtube') || d.includes('youtube') ||
        tags.includes('video') || tags.includes('watch_along');
    });

    if (!videos.length) { section.style.display = 'none'; return; }

    row.innerHTML = '';
    for (const v of videos.slice(0, 4)) {
      const card = document.createElement('div');
      const isReady = v.status === 'ready';
      card.className = 'session-card session-card-video';
      card.innerHTML = `
        <div class="session-card-top">
          <span class="video-card-badge">&#127916; Video</span>
          <span class="session-card-time">${_timeAgo(v.created_at || v.updated_at)}</span>
        </div>
        <div class="session-card-title">${_escHtml(v.title || 'Video')}</div>
        <div class="session-card-cta" style="color:${isReady ? '#a78bfa' : 'var(--text-dim)'}">
          ${isReady ? 'Watch with tutor &rarr;' : 'Processing...'}</div>`;
      if (isReady) {
        card.addEventListener('click', async () => {
          try {
            const rRes = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections/${v.collection_id}/resources`, { headers: AuthManager.authHeaders() });
            if (!rRes.ok) return;
            const resources = await rRes.json();
            const videoRes = resources.find(r => r.mime_type?.includes('youtube') || r.mime_type?.includes('video'));
            if (videoRes) {
              state.sessionId = generateId();
              state.studentName = AuthManager.getUser()?.name || 'Student';
              vmStartBYOVideo(videoRes.resource_id, v.collection_id, v.title, videoRes.source_url || '');
            }
          } catch (e) {}
        });
      }
      row.appendChild(card);
    }
    _revealHomeSection(section, 80);
  } catch (e) { section.style.display = 'none'; }
}

async function _loadRecentSessions() {
  const courseSection = document.getElementById('explore-course-sessions-section');
  const courseRow = document.getElementById('explore-course-sessions-row');
  const freeSection = document.getElementById('explore-free-sessions-section');
  const freeRow = document.getElementById('explore-free-sessions-row');
  if (!courseSection || !freeSection) return;

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/sessions/me/all`, {
      headers: AuthManager.authHeaders(),
    });
    if (!res.ok) {
      courseSection.style.display = 'none';
      freeSection.style.display = 'none';
      return;
    }
    const sessions = await res.json();
    if (!sessions.length) {
      courseSection.style.display = 'none';
      freeSection.style.display = 'none';
      return;
    }

    // Split into course sessions vs free/on-demand
    const courseSessions = sessions.filter(s => s.courseId);
    const freeSessions = sessions.filter(s => !s.courseId);

    // Render course sessions
    if (courseSessions.length && courseRow) {
      courseSection.style.display = '';
      courseRow.innerHTML = '';
      for (const s of courseSessions.slice(0, 6)) {
        courseRow.appendChild(_buildSessionCard(s, true));
      }
    } else {
      courseSection.style.display = 'none';
    }

    // Render free sessions
    if (freeSessions.length && freeRow) {
      freeSection.style.display = '';
      freeRow.innerHTML = '';
      const countEl = document.getElementById('explore-free-sessions-count');
      if (countEl) countEl.textContent = `${freeSessions.length} session${freeSessions.length !== 1 ? 's' : ''}`;
      for (const s of freeSessions.slice(0, 6)) {
        freeRow.appendChild(_buildSessionCard(s, false));
      }
    } else {
      freeSection.style.display = 'none';
    }

    // Session search is handled by the unified explore search bar
    if (false) { // legacy — kept for reference
    }
  } catch (e) {
    console.warn('Failed to load sessions:', e);
    courseSection.style.display = 'none';
    freeSection.style.display = 'none';
  }
}

function _buildSessionCard(s, isCourse) {
  const card = document.createElement('div');
  card.className = 'session-card' + (isCourse ? ' session-card-course' : ' session-card-free');
  const ago = _timeAgo(s.startedAt);
  const headline = s.headline || s.plan?.sessionObjective || s.intent?.raw || 'Teaching session';
  const desc = s.headlineDescription || '';
  const dur = s.durationSec ? `${Math.round(s.durationSec / 60)} min` : '';
  const isActive = s.status === 'active';
  const topics = (s.sections || []).filter(sec => sec.status === 'done').map(sec => sec.title).slice(0, 3);
  const courseName = s.courseName || '';

  // Score badge
  const score = s.metrics?.assessmentScore;
  const scoreBadge = score?.total
    ? `<span class="session-card-score${score.pct >= 80 ? ' good' : score.pct >= 50 ? ' ok' : ''}">${score.pct}%</span>`
    : '';

  card.innerHTML = `
    <div class="session-card-top">
      <span class="session-card-time">${ago}</span>
      <div class="session-card-meta-right">
        ${scoreBadge}
        ${dur ? `<span class="session-card-dur">${dur}</span>` : ''}
      </div>
    </div>
    ${isCourse && courseName ? `<div class="session-card-badge">${_escHtml(courseName)}</div>` : ''}
    <div class="session-card-title">${_escHtml(headline)}</div>
    ${desc ? `<div class="session-card-desc">${_escHtml(desc)}</div>` : ''}
    ${topics.length ? `<div class="session-card-topics">${topics.map(t => `<span class="session-card-topic">${_escHtml(t)}</span>`).join('')}</div>` : ''}
    <div class="session-card-cta">${isActive ? 'Continue' : 'Review'} &rarr;</div>`;
  card.addEventListener('click', () => {
    state.courseId = s.courseId;
    Router.navigate('/session/' + s.sessionId);
  });
  return card;
}

async function _searchSessions(query) {
  const courseRow = document.getElementById('explore-course-sessions-row');
  const freeRow = document.getElementById('explore-free-sessions-row');
  const freeSection = document.getElementById('explore-free-sessions-section');
  if (!query.trim()) { _loadRecentSessions(); return; }

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/sessions/search/all?q=${encodeURIComponent(query)}`, {
      headers: AuthManager.authHeaders(),
    });
    if (!res.ok) return;
    const results = await res.json();

    // Show all search results in the free sessions row, hide course section
    const courseSection = document.getElementById('explore-course-sessions-section');
    if (courseSection) courseSection.style.display = 'none';

    if (!results.length) {
      if (freeSection) freeSection.style.display = '';
      if (freeRow) freeRow.innerHTML = '<div class="session-empty">No sessions match your search.</div>';
      return;
    }

    if (freeSection) freeSection.style.display = '';
    if (freeRow) {
      freeRow.innerHTML = '';
      for (const s of results.slice(0, 8)) {
        freeRow.appendChild(_buildSessionCard(s, !!s.courseId));
      }
    }
  } catch (e) { console.warn('Session search failed:', e); }
}

function _timeAgo(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
  return d.toLocaleDateString();
}

async function _loadMyVideos() {
  const section = document.getElementById('explore-my-videos-section');
  const row = document.getElementById('explore-my-videos-row');
  if (!section || !row) return;

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections`, {
      headers: AuthManager.authHeaders(),
    });
    if (!res.ok) { section.style.display = 'none'; return; }
    const collections = await res.json();

    // Filter to video collections (YouTube or video uploads)
    const videos = collections.filter(c => {
      const t = (c.title || '').toLowerCase();
      const d = (c.description || '').toLowerCase();
      const tags = c.tags || [];
      return t.includes('video') || t.includes('youtube') || t.includes('lecture') ||
        d.includes('youtube') || d.includes('youtu.be') || d.includes('video') ||
        tags.includes('video') || tags.includes('watch_along');
    });

    if (!videos.length) { section.style.display = 'none'; return; }

    section.style.display = '';
    row.innerHTML = '';
    const countEl = document.getElementById('explore-my-videos-count');
    if (countEl) countEl.textContent = `${videos.length} video${videos.length !== 1 ? 's' : ''}`;

    for (const v of videos.slice(0, 8)) {
      const card = document.createElement('div');
      card.className = 'session-card session-card-video';
      const isReady = v.status === 'ready';
      const isProcessing = v.status === 'processing';
      const chunks = v.stats?.chunks || 0;

      card.innerHTML = `
        <div class="session-card-top">
          <span class="video-card-badge">&#127916; Video</span>
          <span class="session-card-time">${_timeAgo(v.created_at || v.updated_at)}</span>
        </div>
        <div class="session-card-title">${_escHtml(v.title || 'Video')}</div>
        <div class="session-card-desc">${isReady ? `${chunks} transcript segments` : isProcessing ? 'Transcript processing...' : 'Processing failed'}</div>
        <div class="session-card-cta" style="color:${isReady ? '#a78bfa' : 'var(--text-dim)'}">
          ${isReady ? 'Watch with tutor &rarr;' : isProcessing ? 'Processing...' : 'Retry'}</div>`;

      if (isReady) {
        card.addEventListener('click', async () => {
          // Fetch resources to find the video resource
          try {
            const rRes = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections/${v.collection_id}/resources`, { headers: AuthManager.authHeaders() });
            if (!rRes.ok) return;
            const resources = await rRes.json();
            const videoRes = resources.find(r => r.mime_type?.includes('youtube') || r.mime_type?.includes('video'));
            if (videoRes) {
              state.sessionId = generateId();
              state.studentName = AuthManager.getUser()?.name || 'Student';
              vmStartBYOVideo(videoRes.resource_id, v.collection_id, v.title, videoRes.source_url || '');
            }
          } catch (e) { console.warn('Failed to start video:', e); }
        });
      }
      row.appendChild(card);
    }
  } catch (e) {
    section.style.display = 'none';
  }
}

async function _loadLearningAids() {
  const grid = document.getElementById('aids-grid');
  const empty = document.getElementById('aids-empty');
  const section = document.getElementById('mat-generated-section');
  if (!grid) return;

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/artifacts`, {
      headers: AuthManager.authHeaders(),
    });
    if (!res.ok) return;
    const artifacts = await res.json();

    if (!artifacts.length) {
      if (section) section.style.display = 'none';
      return;
    }
    if (section) section.style.display = '';
    if (empty) empty.style.display = 'none';

    // Remove old aid cards (keep empty state element)
    grid.querySelectorAll('.aid-card').forEach(c => c.remove());

    for (const a of artifacts) {
      const card = document.createElement('div');
      card.className = 'aid-card';
      card.dataset.artifactId = a.artifact_id;

      const typeIcons = {
        flashcards: '&#x1F4C7;', revision_notes: '&#x1F4DD;', study_plan: '&#x1F4CB;',
        summary: '&#x1F4D6;', cheat_sheet: '&#x1F4DC;', practice_problems: '&#x270F;',
      };
      const icon = typeIcons[a.type] || '&#x1F4C4;';
      const preview = a.preview || {};
      let meta = a.type;
      if (preview.card_count) meta = `${preview.card_count} cards`;
      if (preview.step_count) meta = `${preview.step_count} steps`;

      // Spaced repetition badge for flashcards
      let srBadge = '';
      if (a.type === 'flashcards' && a.sr_stats) {
        const due = a.sr_stats.due_now || 0;
        const mastered = a.sr_stats.mastered || 0;
        srBadge = due > 0
          ? `<div class="aid-sr-badge aid-sr-due">${due} due for review</div>`
          : `<div class="aid-sr-badge aid-sr-ok">${mastered} mastered</div>`;
      }

      card.innerHTML = `
        <div class="aid-icon">${icon}</div>
        <div class="aid-title">${_escHtml(a.title)}</div>
        <div class="aid-meta">${meta}</div>
        ${srBadge}`;

      card.addEventListener('click', () => _openAidDetail(a.artifact_id, a.type, a.title));
      grid.insertBefore(card, empty);
    }
  } catch (e) {
    console.warn('Failed to load learning aids:', e);
  }
}

async function _openAidDetail(artifactId, type, title) {
  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/artifacts/${artifactId}`, {
      headers: AuthManager.authHeaders(),
    });
    if (!res.ok) return;
    const artifact = await res.json();
    openArtifactViewer(type, title, artifact.content || {});
  } catch (e) {
    console.warn('Failed to load artifact:', e);
  }
}

// ═══════════════════════════════════════════════════════════════

let _eulerStream = null;       // current SSE connection
let _eulerHistory = [];        // conversation history sent to backend [{role, content}]
let _eulerBusy = false;
let _eulerStarted = false;     // has conversation started?
let _eulerCurrentResponse = ''; // accumulates current assistant response for history
let _eulerActions = [];         // tracks tool actions taken this turn (for history enrichment)
let _eulerSeenToolsSinceText = false; // tracks if tools ran since last text bubble
let _eulerSuppressText = false; // suppress text after permission/session cards

function _initEuler() {
  // Wire both idle and active inputs
  _wireEulerInput('euler-input', 'euler-send-btn');
  _wireEulerInput('euler-input-active', 'euler-send-btn-active');

  // Check for pending prompt from landing page (saved before login redirect)
  const pendingPrompt = sessionStorage.getItem('capacity_pending_prompt');
  if (pendingPrompt) {
    sessionStorage.removeItem('capacity_pending_prompt');
    setTimeout(() => {
      const input = document.getElementById('euler-input');
      if (input) { input.value = pendingPrompt; }
      _eulerSend();
    }, 500);
  }

  // Attachment buttons
  _wireAttachments('euler-attach-btn', 'euler-file-input', 'euler-attach-preview');
  _wireAttachments('euler-attach-btn-active', 'euler-file-input-active', 'euler-attach-preview-active');

  // Drag & drop on the chat messages area
  const msgArea = document.getElementById('euler-messages');
  if (msgArea) {
    msgArea.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
    msgArea.addEventListener('drop', (e) => {
      e.preventDefault();
      if (e.dataTransfer.files?.length) _handleEulerAttachFiles(e.dataTransfer.files, 'euler-attach-preview-active');
    });
  }

  // Preview panel close
  document.getElementById('ep-close')?.addEventListener('click', _closePreviewPanel);

  // Home button — back to browse
  document.getElementById('euler-home-btn')?.addEventListener('click', () => {
    _eulerFullReset();
    Router.navigate('/home');
  });

  // Clear chat button
  document.getElementById('euler-clear-btn')?.addEventListener('click', () => {
    _eulerFullReset();
  });

  // BYO upload wiring — browse button + drag & drop + link input
  document.getElementById('byo-browse-link')?.addEventListener('click', (e) => {
    e.stopPropagation();
    document.getElementById('byo-file-input')?.click();
  });
  document.getElementById('byo-drop-area')?.addEventListener('click', () => {
    document.getElementById('byo-file-input')?.click();
  });
  document.getElementById('byo-file-input')?.addEventListener('change', _handleByoUpload);

  // Materials search
  const byoSearchInput = document.getElementById('byo-search-input');
  if (byoSearchInput) {
    let _bTimer = null;
    byoSearchInput.addEventListener('input', () => {
      clearTimeout(_bTimer);
      _bTimer = setTimeout(() => _searchByoMaterials(byoSearchInput.value), 300);
    });
  }

  // Drag & drop on the drop area
  const dropArea = document.getElementById('byo-drop-area');
  if (dropArea) {
    let byoDragCount = 0;
    dropArea.addEventListener('dragenter', (e) => { e.preventDefault(); byoDragCount++; dropArea.classList.add('byo-drag-over'); });
    dropArea.addEventListener('dragleave', (e) => { e.preventDefault(); byoDragCount--; if (byoDragCount <= 0) { byoDragCount = 0; dropArea.classList.remove('byo-drag-over'); } });
    dropArea.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
    dropArea.addEventListener('drop', (e) => {
      e.preventDefault();
      byoDragCount = 0;
      dropArea.classList.remove('byo-drag-over');
      const files = e.dataTransfer.files;
      if (files && files.length) _handleByoDroppedFiles(files);
    });
  }

  // Link input
  document.getElementById('byo-link-btn')?.addEventListener('click', _handleByoLinkAdd);
  document.getElementById('byo-link-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') _handleByoLinkAdd();
  });

  // Back button — return to idle/home
  document.getElementById('euler-back-btn')?.addEventListener('click', () => {
    _eulerResetToIdle();
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
  });

  // Chip clicks fill idle input
  document.querySelectorAll('#euler-chips .euler-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const input = document.getElementById('euler-input');
      if (input) { input.value = chip.textContent; input.focus(); }
    });
  });

  // Capability card clicks — fill input and send
  document.querySelectorAll('.cap-card').forEach(card => {
    card.addEventListener('click', () => {
      const prompt = card.dataset.prompt;
      if (prompt) {
        const input = document.getElementById('euler-input');
        if (input) { input.value = prompt; }
        _eulerSend();
      }
    });
  });
}

// ── Euler attachment handling ──
let _eulerAttachments = []; // [{name, type, dataUrl, base64}]

function _wireAttachments(btnId, fileInputId, previewId) {
  const btn = document.getElementById(btnId);
  const fileInput = document.getElementById(fileInputId);
  if (!btn || !fileInput) return;

  btn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => {
    if (e.target.files?.length) _handleEulerAttachFiles(e.target.files, previewId);
    e.target.value = '';
  });
}

const MAX_ATTACHMENTS = 5;

function _handleEulerAttachFiles(files, previewId) {
  for (const file of files) {
    if (_eulerAttachments.length >= MAX_ATTACHMENTS) {
      alert(`Maximum ${MAX_ATTACHMENTS} attachments allowed`); break;
    }
    if (file.size > 20 * 1024 * 1024) { alert('File too large (max 20MB)'); continue; }

    const reader = new FileReader();
    reader.onload = () => {
      const attachment = {
        name: file.name,
        type: file.type,
        dataUrl: reader.result,
        base64: reader.result.split(',')[1],
      };
      _eulerAttachments.push(attachment);
      _renderAttachPreview(previewId);
    };
    reader.readAsDataURL(file);
  }
}

function _renderAttachPreview(previewId) {
  const preview = document.getElementById(previewId);
  if (!preview) return;
  if (!_eulerAttachments.length) { preview.style.display = 'none'; return; }

  preview.style.display = 'flex';
  preview.innerHTML = _eulerAttachments.map((a, i) => {
    const isImage = a.type.startsWith('image/');
    const thumb = isImage ? `<img src="${a.dataUrl}" alt="">` : '';
    const icon = isImage ? '' : '&#128196; ';
    return `<div class="euler-attach-item">${thumb}${icon}${_escHtml(a.name)}<span class="euler-attach-remove" data-idx="${i}">&times;</span></div>`;
  }).join('');

  preview.querySelectorAll('.euler-attach-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      _eulerAttachments.splice(parseInt(btn.dataset.idx), 1);
      _renderAttachPreview(previewId);
    });
  });
}

function _wireEulerInput(inputId, btnId) {
  const input = document.getElementById(inputId);
  const sendBtn = document.getElementById(btnId);
  if (!input || !sendBtn) return;

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      _eulerSend();
    }
  });

  sendBtn.addEventListener('click', _eulerSend);
}

function _eulerSend() {
  // Read from whichever input is active
  const idleInput = document.getElementById('euler-input');
  const chatInput = document.getElementById('euler-input-active');
  const input = _eulerStarted ? chatInput : idleInput;
  if (!input) return;
  const text = input.value.trim();
  if (!text || _eulerBusy) return;

  // Switch from idle → chat on first message
  if (!_eulerStarted) {
    _eulerStarted = true;
    const idle = document.getElementById('euler-idle');
    const chat = document.getElementById('euler-chat');
    if (idle) idle.style.display = 'none';
    if (chat) chat.style.display = 'flex';
  }

  // Build attachment thumbnails for the message bubble
  let attachHtml = '';
  if (_eulerAttachments.length > 0) {
    attachHtml = '<div class="euler-msg-attachments">' +
      _eulerAttachments.map(a => {
        if (a.type.startsWith('image/')) {
          return `<div class="euler-msg-attach"><img src="${a.dataUrl}" alt="${_escHtml(a.name)}"></div>`;
        }
        return `<div class="euler-msg-attach euler-msg-attach-file"><span>&#128196;</span><span class="euler-msg-attach-name">${_escHtml(a.name)}</span></div>`;
      }).join('') + '</div>';
  }

  // Add user message to UI + history
  _eulerAddMessage('user', text + attachHtml);
  _eulerHistory.push({ role: 'user', content: text });

  // Clear input
  input.value = '';
  input.style.height = 'auto';

  // Stream response from Euler
  _eulerStreamResponse(text);
}

function _eulerAddMessage(role, content, extra) {
  const container = document.getElementById('euler-messages');
  if (!container) return;

  const msg = document.createElement('div');
  msg.className = `euler-msg euler-msg-${role}`;

  if (role === 'user') {
    msg.innerHTML = `<div class="euler-msg-bubble euler-user-bubble">${_escHtml(content)}</div>`;
  } else if (role === 'euler') {
    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar">E</div>
        <div class="euler-msg-content">
          <div class="euler-msg-bubble euler-euler-bubble">${content}</div>
        </div>
      </div>`;
  } else if (role === 'thinking') {
    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar">E</div>
        <div class="euler-thinking"><span></span><span></span><span></span></div>
      </div>`;
    msg.id = 'euler-thinking-indicator';
  } else if (role === 'artifact') {
    const a = extra || {};
    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar">E</div>
        <div class="euler-artifact-card" style="cursor:pointer" data-artifact-type="${_escHtml(a.artifactType || 'artifact')}" data-artifact-title="${_escHtml(a.title || 'Untitled')}">
          <div class="euler-artifact-header">
            <span class="euler-artifact-type">${_escHtml(a.artifactType || 'artifact')}</span>
            <span class="euler-artifact-title">${_escHtml(a.title || 'Untitled')}</span>
            <span class="euler-artifact-saved">Saved</span>
          </div>
          <div class="euler-artifact-preview">${_renderArtifactPreview(a)}</div>
        </div>
      </div>`;
    // Store content for viewer and wire click
    const card = msg.querySelector('.euler-artifact-card');
    if (card) {
      card._artifactContent = a.content || {};
      card.addEventListener('click', () => {
        _openPreviewPanel(a.artifactType || 'artifact', a.title || 'Untitled', card._artifactContent);
      });
    }
  } else if (role === 'document') {
    const d = extra || {};
    const docUrl = d.downloadUrl || '#';
    const docId = 'doc-' + Math.random().toString(36).slice(2, 8);
    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar">E</div>
        <div class="euler-document-card" id="${docId}">
          <div class="euler-doc-icon">&#128196;</div>
          <div class="euler-doc-info">
            <div class="euler-doc-title">${_escHtml(d.title || 'Document')}</div>
            <div class="euler-doc-format">${(d.format || 'html').toUpperCase()}</div>
          </div>
          <button class="euler-doc-download" data-url="${_escHtml(docUrl)}">Open</button>
          <a href="${_escHtml(docUrl)}" target="_blank" class="euler-doc-external" title="Open in new tab">&#8599;</a>
        </div>
      </div>`;
    // Wire inline viewer
    setTimeout(() => {
      const card = document.getElementById(docId);
      if (!card) return;
      const btn = card.querySelector('.euler-doc-download');
      if (btn) btn.addEventListener('click', () => {
        const url = btn.dataset.url;
        // Open in artifact viewer as HTML/PDF
        const fmt = (d.format || 'html').toLowerCase();
        if (fmt === 'pdf') {
          openArtifactViewer('document', d.title || 'Document', { pdf_url: url });
        } else {
          // HTML document — fetch and show inline
          fetch(url).then(r => r.text()).then(html => {
            openArtifactViewer('document', d.title || 'Document', { html });
          }).catch(() => window.open(url, '_blank'));
        }
      });
    }, 50);
  } else if (role === 'permission') {
    const p = extra || {};
    const ctx = p.context || {};
    const isWatchAlong = ctx.mode === 'watch_along' || ctx.skill === 'watch_along';
    const actionType = ctx.action_type || (isWatchAlong ? 'watch_along' : 'tutor');

    // Card appearance based on action type
    const cardConfig = {
      watch_along:    { icon: '&#127916;', label: 'Video Follow-Along', cls: 'euler-perm-video' },
      tutor:          { icon: '&#9997;',   label: 'Live Tutoring',      cls: 'euler-perm-tutor' },
      study_plan:     { icon: '&#128203;', label: 'Study Plan',         cls: 'euler-perm-plan' },
      artifact:       { icon: '&#128221;', label: 'Create Resource',    cls: 'euler-perm-artifact' },
      document:       { icon: '&#128196;', label: 'Document',           cls: 'euler-perm-artifact' },
    };
    const cfg = cardConfig[actionType] || cardConfig.tutor;
    const icon = cfg.icon;
    const typeLabel = cfg.label;
    const typeCls = cfg.cls;

    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar">E</div>
        <div class="euler-permission-card ${typeCls}" data-permission-id="${p.permissionId || ''}">
          <div class="euler-perm-header">
            <span class="euler-perm-icon">${icon}</span>
            <span class="euler-perm-type">${typeLabel}</span>
          </div>
          <div class="euler-perm-question">${_escHtml(p.question || '')}</div>
          <div class="euler-perm-actions">
            <button class="euler-perm-btn euler-perm-yes" data-action="yes">${_escHtml(p.actionLabel || "Let's go!")}</button>
            <button class="euler-perm-btn euler-perm-no" data-action="no">${_escHtml(p.denyLabel || 'Not now')}</button>
          </div>
        </div>
      </div>`;
    // Store permission context on the card element
    const permCard = msg.querySelector('.euler-permission-card');
    if (permCard) permCard._permContext = p.context || {};

    // Wire permission buttons — "yes" starts session directly, "no" sends decline to Euler
    setTimeout(() => {
      msg.querySelectorAll('.euler-perm-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const card = btn.closest('.euler-permission-card');
          card.classList.add('euler-perm-answered');
          card.querySelectorAll('.euler-perm-btn').forEach(b => b.disabled = true);
          btn.classList.add('euler-perm-selected');
          const approved = btn.dataset.action === 'yes';

          if (approved) {
            // Directly start the session — no round-trip to Euler
            const ctx = card._permContext || {};
            const intent = ctx.enriched_intent || _eulerCurrentResponse || '';
            const courseId = ctx.course_id;
            document.body.style.overflow = 'auto';
            document.body.style.height = 'auto';

            // BYO video watch-along
            if ((ctx.mode === 'watch_along' || ctx.skill === 'watch_along') && (ctx.resource_id || ctx.collection_id)) {
              state.sessionId = ctx.session_id || generateId();
              state.studentName = AuthManager.getUser()?.name || 'Student';

              // If source_url is already in action_data (YouTube URL), use it directly
              if (ctx.source_url) {
                vmStartBYOVideo(ctx.resource_id || '', ctx.collection_id || '', ctx.title || 'Video', ctx.source_url);
              } else if (ctx.resource_id) {
                // Try to fetch resource info for the source_url
                fetch(`${state.apiUrl}/api/v1/byo/resources/${ctx.resource_id}/info`, { headers: AuthManager.authHeaders() })
                  .then(r => r.ok ? r.json() : null)
                  .then(info => {
                    if (info) {
                      vmStartBYOVideo(ctx.resource_id, ctx.collection_id || info.collection_id || '', info.original_name || 'Video', info.source_url || '');
                    } else {
                      // Info failed — try getting resources from collection
                      _fetchVideoFromCollection(ctx.collection_id, ctx.resource_id);
                    }
                  })
                  .catch(() => _fetchVideoFromCollection(ctx.collection_id, ctx.resource_id));
              } else if (ctx.collection_id) {
                // No resource_id — look up from collection
                _fetchVideoFromCollection(ctx.collection_id, '');
              }
            } else if (courseId) {
              const courseIdEl = document.getElementById('course-id');
              if (courseIdEl) courseIdEl.value = courseId;
              const user = AuthManager.getUser();
              if (user) startNewSession(user.name, courseId, intent, ctx.skill || 'free');
            } else {
              _startOnDemandSession(intent);
            }
          } else {
            // Decline — tell Euler
            _eulerHistory.push({ role: 'user', content: 'No, skip that.' });
            _eulerAddMessage('user', 'Not now');
            _eulerStreamResponse('No, skip that for now.');
          }
        });
      });
    }, 0);
  } else if (role === 'navigate') {
    const n = extra || {};
    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar">E</div>
        <div class="euler-navigate-card" onclick="_eulerNavigateTo('${n.target || '/home'}')">
          <span>${_escHtml(n.label || 'Go')}</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </div>
      </div>`;
  } else if (role === 'session_start') {
    const s = extra || {};
    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar">E</div>
        <div class="euler-session-card" onclick="_startOnDemandSession('${_escHtml(s.context?.enriched_intent || '')}')">
          <div class="euler-session-label">Starting teaching session</div>
          <div class="euler-session-intent">${_escHtml(s.context?.enriched_intent || 'Teaching session')}</div>
          <span class="euler-session-go">Enter session &rarr;</span>
        </div>
      </div>`;
  } else if (role === 'actions') {
    const actions = extra || [];
    msg.innerHTML = `
      <div class="euler-msg-row">
        <div class="euler-msg-avatar" style="visibility:hidden">E</div>
        <div class="euler-actions">
          ${actions.map(a => `<button class="euler-action-btn" data-action="${_escHtml(a.action || '')}" data-data='${JSON.stringify(a.data || {})}'>${_escHtml(a.label || '')}</button>`).join('')}
        </div>
      </div>`;
    setTimeout(() => {
      msg.querySelectorAll('.euler-action-btn').forEach(btn => {
        btn.addEventListener('click', () => _handleEulerAction(btn.dataset.action, JSON.parse(btn.dataset.data || '{}')));
      });
    }, 0);
  }

  container.appendChild(msg);
  msg.scrollIntoView({ behavior: 'smooth', block: 'end' });

  return msg;
}

function _renderArtifactPreview(artifact) {
  const content = artifact.content || {};
  const type = artifact.artifactType || '';

  if (type === 'flashcards' && content.cards) {
    const cards = content.cards.slice(0, 3);
    return cards.map(c => `<div class="euler-fc"><div class="euler-fc-q">${_escHtml(c.front || '')}</div><div class="euler-fc-a">${_escHtml(c.back || '')}</div></div>`).join('') +
      (content.cards.length > 3 ? `<div class="euler-fc-more">+${content.cards.length - 3} more cards</div>` : '');
  }
  if (content.markdown) {
    return `<div class="euler-md-preview">${_escHtml(content.markdown.slice(0, 200))}${content.markdown.length > 200 ? '...' : ''}</div>`;
  }
  if (content.steps) {
    return content.steps.slice(0, 3).map((s, i) => `<div class="euler-step-preview">${i + 1}. ${_escHtml(s.title || s.description || '')}</div>`).join('');
  }
  return `<div class="euler-md-preview">${_escHtml(JSON.stringify(content).slice(0, 150))}...</div>`;
}

function _handleEulerAction(action, data) {
  if (action === 'start_session') {
    _startOnDemandSession(data.intent || data.enriched_intent || '');
  } else if (action === 'navigate') {
    Router.navigate(data.target || '/home');
  } else if (action === 'create_artifact') {
    // Re-send to Euler with the create request
    const input = document.getElementById('euler-input');
    if (input) { input.value = data.prompt || 'Create it'; _eulerSend(); }
  }
}

async function _eulerStreamResponse(text) {
  _eulerBusy = true;
  const sendBtn = document.getElementById(_eulerStarted ? 'euler-send-btn-active' : 'euler-send-btn');
  if (sendBtn) sendBtn.disabled = true;

  // Show thinking indicator
  _eulerAddMessage('thinking');

  _eulerCurrentResponse = '';  // reset accumulator
  _eulerActions = [];           // reset actions tracker
  _eulerSeenToolsSinceText = false;
  _eulerSuppressText = false;  // new message, allow text again

  // Show processing indicator above input
  _eulerShowProcessing('Euler is thinking...');

  try {
    // Include attachments as multimodal content
    const attachments = _eulerAttachments.length > 0
      ? _eulerAttachments.map(a => ({
          filename: a.name,
          mime_type: a.type,
          data: a.base64,
        }))
      : undefined;

    // Clear attachments after sending
    _eulerAttachments = [];
    _renderAttachPreview('euler-attach-preview');
    _renderAttachPreview('euler-attach-preview-active');

    const res = await fetch(`${state.apiUrl || ''}/api/euler`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify({ message: text, history: _eulerHistory, attachments }),
    });

    if (!res.ok) {
      _eulerRemoveThinking();
      _eulerAddMessage('euler', `Sorry, something went wrong (${res.status}).`);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          _handleEulerEvent(evt);
        } catch (e) { /* ignore parse errors */ }
      }
    }
  } catch (e) {
    _eulerRemoveThinking();
    _eulerAddMessage('euler', 'Connection error. Please try again.');
  } finally {
    _eulerBusy = false;
    if (sendBtn) sendBtn.disabled = false;
    // Always clean up streaming cursors — prevents orphaned blinking cursors
    // if stream ends without a DONE event (network error, early close, etc.)
    _eulerRemoveStreamingCursors();
  }
}

/** Find or create the current assistant message's content column for inline inserts. */
function _getOrCreateCurrentContentCol() {
  const allMsgs = document.querySelectorAll('#euler-messages .euler-msg-euler');
  let parentMsg = allMsgs.length ? allMsgs[allMsgs.length - 1] : null;
  if (parentMsg) {
    let sibling = parentMsg.nextElementSibling;
    while (sibling) {
      if (sibling.classList.contains('euler-msg-user')) { parentMsg = null; break; }
      sibling = sibling.nextElementSibling;
    }
  }
  let contentCol = parentMsg?.querySelector('.euler-msg-content');
  if (!contentCol) {
    _eulerAddMessage('euler', '');
    const freshMsgs = document.querySelectorAll('#euler-messages .euler-msg-euler');
    parentMsg = freshMsgs.length ? freshMsgs[freshMsgs.length - 1] : null;
    contentCol = parentMsg?.querySelector('.euler-msg-content');
    const emptyBubble = contentCol?.querySelector('.euler-euler-bubble');
    if (emptyBubble && !emptyBubble._rawText) emptyBubble.style.display = 'none';
  }
  return contentCol;
}

/** Insert an element inline within the current assistant message's content column. */
function _insertInlineInCurrentMsg(el) {
  const contentCol = _getOrCreateCurrentContentCol();
  if (contentCol) {
    // Collapse any active tool indicator row
    const activeToolRow = document.getElementById('euler-tool-active');
    if (activeToolRow) {
      activeToolRow.classList.add('euler-tools-collapsed');
      activeToolRow.removeAttribute('id');
    }
    contentCol.appendChild(el);
    el.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
}

/** Build an artifact card DOM element (not a full message). */
function _buildArtifactCardEl(a) {
  const card = document.createElement('div');
  card.className = 'euler-artifact-card euler-inline-card';
  card.style.cursor = 'pointer';
  card.dataset.artifactType = a.artifactType || 'artifact';
  card.dataset.artifactTitle = a.title || 'Untitled';
  card.innerHTML = `
    <div class="euler-artifact-header">
      <span class="euler-artifact-type">${_escHtml(a.artifactType || 'artifact')}</span>
      <span class="euler-artifact-title">${_escHtml(a.title || 'Untitled')}</span>
      <span class="euler-artifact-saved">Saved</span>
    </div>
    <div class="euler-artifact-preview">${_renderArtifactPreview(a)}</div>`;
  card._artifactContent = a.content || {};
  card.addEventListener('click', () => {
    _openPreviewPanel(a.artifactType || 'artifact', a.title || 'Untitled', card._artifactContent);
  });
  return card;
}

/** Build a document card DOM element (not a full message). */
function _buildDocumentCardEl(d) {
  const card = document.createElement('div');
  card.className = 'euler-document-card euler-inline-card';
  const docUrl = d.downloadUrl || '#';
  card.innerHTML = `
    <div class="euler-doc-icon">&#128196;</div>
    <div class="euler-doc-info">
      <div class="euler-doc-title">${_escHtml(d.title || 'Document')}</div>
      <div class="euler-doc-format">${(d.format || 'html').toUpperCase()}</div>
    </div>
    <button class="euler-doc-download">Open</button>
    <a href="${_escHtml(docUrl)}" target="_blank" class="euler-doc-external" title="Open in new tab">&#8599;</a>`;
  const btn = card.querySelector('.euler-doc-download');
  if (btn) btn.addEventListener('click', () => {
    const fmt = (d.format || 'html').toLowerCase();
    if (fmt === 'pdf') {
      openArtifactViewer('document', d.title || 'Document', { pdf_url: docUrl });
    } else {
      fetch(docUrl).then(r => r.text()).then(html => {
        openArtifactViewer('document', d.title || 'Document', { html });
      }).catch(() => window.open(docUrl, '_blank'));
    }
  });
  return card;
}

function _handleEulerEvent(evt) {
  switch (evt.type) {
    case 'CONNECTED':
      break;

    case 'TEXT_DELTA': {
      if (!evt.text) break;
      _eulerRemoveThinking();
      _eulerHideProcessing();
      _eulerCurrentResponse += evt.text;

      // Suppress text after permission/session cards
      if (_eulerSuppressText) break;

      // Collapse tool pills when text arrives — they're done, hide them like Claude
      const activeToolRow = document.getElementById('euler-tool-active');
      if (activeToolRow && _eulerSeenToolsSinceText) {
        activeToolRow.classList.add('euler-tools-collapsed');
        activeToolRow.removeAttribute('id'); // detach so next tool batch gets a fresh row
      }

      // Find the current assistant message for this turn.
      // Look for the last euler message with a .euler-msg-content, and only
      // reuse it if no user message appeared after it (same-turn check).
      const allMsgs = document.querySelectorAll('#euler-messages .euler-msg-euler');
      let currentMsg = allMsgs.length ? allMsgs[allMsgs.length - 1] : null;
      if (currentMsg) {
        let sibling = currentMsg.nextElementSibling;
        while (sibling) {
          if (sibling.classList.contains('euler-msg-user')) { currentMsg = null; break; }
          sibling = sibling.nextElementSibling;
        }
      }
      let contentCol = currentMsg?.querySelector('.euler-msg-content');

      // No current assistant message for this turn — create one
      if (!contentCol) {
        _eulerRemoveStreamingCursors();
        _eulerAddMessage('euler', '');
        const freshMsgs = document.querySelectorAll('#euler-messages .euler-msg-euler');
        currentMsg = freshMsgs.length ? freshMsgs[freshMsgs.length - 1] : null;
        contentCol = currentMsg?.querySelector('.euler-msg-content');
      }

      // After tool calls, create a new bubble segment so text appears BELOW the tool indicators
      let last;
      if (_eulerSeenToolsSinceText && contentCol) {
        _eulerRemoveStreamingCursors();
        const newBubble = document.createElement('div');
        newBubble.className = 'euler-msg-bubble euler-euler-bubble';
        contentCol.appendChild(newBubble);
        last = newBubble;
      } else {
        // Reuse the last bubble in the content column
        const bubbles = contentCol?.querySelectorAll('.euler-euler-bubble');
        last = bubbles?.length ? bubbles[bubbles.length - 1] : null;
      }

      // Unhide bubble if it was hidden (created empty by TOOL_START)
      if (last && last.style.display === 'none') last.style.display = '';

      _eulerSeenToolsSinceText = false;
      if (last) {
        last._rawText = (last._rawText || '') + evt.text;
        last.innerHTML = _renderMarkdown(last._rawText);
        last.classList.add('streaming');
        currentMsg?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
      break;
    }

    case 'TOOL_START': {
      _eulerRemoveThinking();
      _eulerSeenToolsSinceText = true;
      // Update processing bar with tool label
      const _procLabels = { search_courses:'Searching courses...', create_artifact:'Creating...', generate_document:'Generating document...', spawn_agents:'Researching...', background_generate:'Generating...' };
      _eulerShowProcessing(_procLabels[evt.tool] || 'Working on it...');
      // Track tool usage for history (so backend knows what was already done)
      const toolQuery = evt.input?.query || evt.input?.title || evt.input?.question || '';
      if (evt.tool === 'search_courses') _eulerActions.push(`[Searched courses: "${toolQuery}"]`);
      else if (evt.tool === 'search_sessions') _eulerActions.push(`[Searched past sessions]`);
      else if (evt.tool === 'process_video_url') _eulerActions.push(`[Processed video URL]`);
      const toolLabels = {
        search_courses: 'Searching courses',
        search_materials: 'Searching your materials',
        get_student_context: 'Checking learning history',
        spawn_agents: 'Working on it',
        background_generate: 'Generating in background',
        byo_read: 'Reading your materials',
        byo_list: 'Listing your materials',
        create_artifact: 'Creating study aid',
        generate_document: 'Generating document',
        start_tutor_session: 'Starting session',
        navigate_ui: 'Navigating',
        ask_permission: 'Confirming',
        respond_inline: 'Preparing',
      };
      const label = toolLabels[evt.tool] || evt.tool;
      const inputPreview = evt.input?.query || evt.input?.title || evt.input?.question || '';

      let toolRow = document.getElementById('euler-tool-active');
      if (!toolRow) {
        // Find the current assistant message's content column to insert tools inline
        const allMsgs = document.querySelectorAll('#euler-messages .euler-msg-euler');
        let parentMsg = allMsgs.length ? allMsgs[allMsgs.length - 1] : null;
        // Only reuse if no user message came after it (same turn check)
        if (parentMsg) {
          let sibling = parentMsg.nextElementSibling;
          while (sibling) {
            if (sibling.classList.contains('euler-msg-user')) { parentMsg = null; break; }
            sibling = sibling.nextElementSibling;
          }
        }
        let contentCol = parentMsg?.querySelector('.euler-msg-content');
        // If no current assistant message exists, create one
        if (!contentCol) {
          const container = document.getElementById('euler-messages');
          if (container) {
            _eulerAddMessage('euler', '');
            const freshMsgs = document.querySelectorAll('#euler-messages .euler-msg-euler');
            parentMsg = freshMsgs.length ? freshMsgs[freshMsgs.length - 1] : null;
            contentCol = parentMsg?.querySelector('.euler-msg-content');
            // Hide the empty bubble since there's no text yet
            const emptyBubble = contentCol?.querySelector('.euler-euler-bubble');
            if (emptyBubble && !emptyBubble._rawText) emptyBubble.style.display = 'none';
          }
        }
        if (contentCol) {
          toolRow = document.createElement('div');
          toolRow.id = 'euler-tool-active';
          toolRow.className = 'euler-tool-row-inline';
          toolRow.innerHTML = `<div class="euler-tool-calls"></div>`;
          contentCol.appendChild(toolRow);
        }
      }
      if (toolRow) {
        const calls = toolRow.querySelector('.euler-tool-calls');
        if (calls) {
          const tc = document.createElement('div');
          tc.className = 'euler-tool-call';
          tc.dataset.callId = evt.call_id || '';
          tc.innerHTML = `
            <div class="euler-tool-header" onclick="this.parentElement.classList.toggle('open')">
              <div class="euler-tool-spinner">
                <div class="euler-tool-spinner-anim"><span></span><span></span><span></span></div>
              </div>
              <span class="euler-tool-label">${label}${inputPreview ? ' — ' + _escHtml(inputPreview.slice(0, 40)) : ''}...</span>
              <span class="euler-tool-chevron">&#x203A;</span>
            </div>
            <div class="euler-tool-detail"></div>`;
          calls.appendChild(tc);
          tc.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
      }
      // Remove streaming cursor while tools are running
      _eulerRemoveStreamingCursors();
      break;
    }

    case 'TOOL_RESULT': {
      const toolRow = document.getElementById('euler-tool-active');
      if (toolRow) {
        const calls = toolRow.querySelectorAll('.euler-tool-call:not(.euler-tool-done)');
        if (calls.length) {
          const tc = calls[0];
          tc.classList.add('euler-tool-done');
          // Show result preview in the detail section
          const detail = tc.querySelector('.euler-tool-detail');
          if (detail && evt.result) {
            detail.textContent = evt.result.slice(0, 300) + (evt.result.length > 300 ? '...' : '');
          }
        }
      }
      // Course cards are NOT auto-rendered from search results — they're internal context.
      // The orchestrator shows courses via navigate_ui or text links when appropriate.

      // Show thinking indicator after tool completes — model is processing results
      _eulerShowThinkingInline();
      break;
    }

    case 'ARTIFACT': {
      _eulerRemoveThinking();
      _eulerRemoveStreamingCursors();
      const artContent = evt.content || evt.preview || {};
      const artCard = _buildArtifactCardEl({
        artifactId: evt.artifactId,
        artifactType: evt.artifactType,
        title: evt.title,
        content: artContent,
      });
      _insertInlineInCurrentMsg(artCard);
      _eulerSeenToolsSinceText = true;
      _eulerActions.push(`[Created ${evt.artifactType || 'artifact'}: "${evt.title || 'Untitled'}"]`);
      // Auto-open preview panel
      _openPreviewPanel(evt.artifactType || 'artifact', evt.title || 'Untitled', artContent);
      break;
    }

    case 'DOCUMENT': {
      _eulerRemoveThinking();
      _eulerRemoveStreamingCursors();
      const docCard = _buildDocumentCardEl({
        title: evt.title,
        format: evt.format,
        downloadUrl: evt.downloadUrl,
      });
      _insertInlineInCurrentMsg(docCard);
      _eulerSeenToolsSinceText = true;
      _eulerActions.push(`[Generated document: "${evt.title || 'Document'}"]`);
      break;
    }

    case 'SESSION_START': {
      _eulerRemoveThinking();
      _eulerRemoveToolIndicator();
      _eulerRemoveStreamingCursors();
      _eulerSuppressText = true;  // No more text — session is starting
      _eulerActions.push(`[Started teaching session]`);
      const ctx = evt.context || {};
      const intent = ctx.enriched_intent || '';
      const courseId = ctx.course_id;
      document.body.style.overflow = 'auto';
      document.body.style.height = 'auto';

      // BYO video watch-along — launch video player
      if (ctx.mode === 'watch_along' && ctx.resource_id) {
        state.sessionId = ctx.session_id || generateId();
        state.studentName = AuthManager.getUser()?.name || 'Student';
        // Fetch resource info to get source_url + title
        fetch(`${state.apiUrl}/api/v1/byo/resources/${ctx.resource_id}/info`, { headers: AuthManager.authHeaders() })
          .then(r => r.ok ? r.json() : null)
          .then(info => {
            const title = info?.original_name || 'Video';
            const srcUrl = info?.source_url || '';
            vmStartBYOVideo(ctx.resource_id, ctx.collection_id || info?.collection_id || '', title, srcUrl);
          })
          .catch(() => {
            // Fallback — start with what we have
            vmStartBYOVideo(ctx.resource_id, ctx.collection_id || '', 'Video', '');
          });
      } else if (courseId) {
        const courseIdEl = document.getElementById('course-id');
        if (courseIdEl) courseIdEl.value = courseId;
        const user = AuthManager.getUser();
        if (user) startNewSession(user.name, courseId, intent, ctx.skill || 'free');
      } else {
        _startOnDemandSession(intent);
      }
      break;
    }

    case 'NAVIGATE':
      _eulerRemoveThinking();
      _eulerRemoveToolIndicator();
      _eulerRemoveStreamingCursors();
      _eulerSuppressText = true;
      _eulerActions.push(`[Navigated to ${evt.target || 'page'}]`);
      _eulerAddMessage('navigate', '', {
        target: evt.target,
        label: evt.label,
      });
      break;

    case 'PERMISSION':
      _eulerRemoveThinking();
      _eulerRemoveStreamingCursors();
      _eulerSuppressText = true;  // Card IS the message
      _eulerActions.push(`[Asked permission: "${evt.question || ''}"]`);
      _eulerAddMessage('permission', '', {
        permissionId: evt.permissionId,
        question: evt.question,
        actionLabel: evt.actionLabel,
        denyLabel: evt.denyLabel,
        context: evt.context || {},  // session config for direct start
      });
      break;

    case 'DONE':
      _eulerRemoveThinking();
      _eulerRemoveToolIndicator();
      _eulerRemoveStreamingCursors();
      _eulerHideProcessing();
      {
        // Build history entry with text + action summaries so the backend
        // knows what tools were called and what was created this turn
        let historyContent = _eulerCurrentResponse.trim();
        if (_eulerActions.length) {
          const actionSummary = '\n' + _eulerActions.join('\n');
          historyContent = historyContent ? historyContent + actionSummary : actionSummary;
        }
        if (historyContent) {
          _eulerHistory.push({ role: 'assistant', content: historyContent });
        }
      }
      break;

    case 'ERROR':
      _eulerRemoveThinking();
      _eulerRemoveToolIndicator();
      _eulerRemoveStreamingCursors();
      _eulerHideProcessing();
      _eulerAddMessage('euler', `Error: ${evt.message || 'Something went wrong.'}`);
      break;
  }
}

function _eulerShowThinkingInline() {
  // Show a thinking animation inside the current message content
  _eulerRemoveThinking(); // remove any existing
  const container = document.querySelector('#euler-messages .euler-msg-euler:last-child .euler-msg-content');
  if (!container) return;
  const indicator = document.createElement('div');
  indicator.id = 'euler-thinking-indicator';
  indicator.className = 'euler-thinking';
  indicator.innerHTML = '<span></span><span></span><span></span>';
  container.appendChild(indicator);
  // Auto-scroll
  const msgs = document.getElementById('euler-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function _eulerRemoveThinking() {
  const el = document.getElementById('euler-thinking-indicator');
  if (el) el.remove();
}

function _eulerRemoveToolIndicator() {
  const el = document.getElementById('euler-tool-active');
  if (el) el.remove();
}

function _eulerRemoveStreamingCursors() {
  document.querySelectorAll('#euler-messages .euler-euler-bubble.streaming').forEach(b => b.classList.remove('streaming'));
}

function _eulerShowProcessing(label) {
  const bar = document.getElementById('euler-processing-bar');
  const lbl = document.getElementById('euler-processing-label');
  if (bar) bar.classList.add('active');
  if (lbl && label) lbl.textContent = label;
}

function _eulerHideProcessing() {
  const bar = document.getElementById('euler-processing-bar');
  if (bar) bar.classList.remove('active');
}

// ═══════════════════════════════════════════════════════════════
//   BYO — Student materials upload
// ═══════════════════════════════════════════════════════════════

let _byoPollTimer = null;
let _byoPollCount = 0;
const _BYO_POLL_MAX = 30; // max 30 attempts = ~2 minutes, then stop

async function _loadByoMaterials() {
  const grid = document.getElementById('byo-grid');
  const uploadsSection = document.getElementById('mat-uploads-section');
  if (!grid) return;

  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections`, {
      headers: AuthManager.authHeaders(),
    });
    if (!res.ok) return;
    const collections = await res.json();

    grid.innerHTML = '';
    let hasProcessing = false;

    if (!collections.length) {
      if (uploadsSection) uploadsSection.style.display = 'none';
      return;
    }
    if (uploadsSection) uploadsSection.style.display = '';

    // Classify collections by type
    const groups = { videos: [], documents: [], other: [] };
    for (const col of collections) {
      const tags = col.tags || [];
      const t = (col.title || '').toLowerCase();
      if (tags.includes('video') || tags.includes('youtube') || t.includes('video') || t.includes('youtube')) {
        groups.videos.push(col);
      } else if (t.endsWith('.pdf') || t.includes('pdf') || t.endsWith('.docx') || t.includes('.txt') || t.includes('.md')) {
        groups.documents.push(col);
      } else {
        groups.other.push(col);
      }
    }

    // Render each group
    const typeConfig = [
      { key: 'videos', label: 'Videos', icon: '&#127916;', color: '#a78bfa', items: groups.videos },
      { key: 'documents', label: 'Documents', icon: '&#128196;', color: '#60a5fa', items: groups.documents },
      { key: 'other', label: 'Other', icon: '&#128218;', color: 'var(--text-dim)', items: groups.other },
    ];

    for (const group of typeConfig) {
      if (!group.items.length) continue;

      const header = document.createElement('div');
      header.className = 'byo-group-header';
      header.innerHTML = `<span style="color:${group.color}">${group.icon}</span> ${group.label} <span class="byo-group-count">${group.items.length}</span>`;
      grid.appendChild(header);

      for (const col of group.items) {
        const isReady = col.status === 'ready';
        const isError = col.status === 'error';
        if (!isReady && !isError) hasProcessing = true;

        const fileCount = col.stats?.resources || 0;
        const chunkCount = col.stats?.chunks || 0;

        const statusHtml = isReady
          ? '<span class="byo-status-label byo-status-ready">Ready</span>'
          : isError
          ? '<span class="byo-status-label byo-status-error">Error</span>'
          : '<span class="byo-status-label byo-status-processing">Processing</span>';

        const row = document.createElement('div');
        row.className = 'byo-list-item' + (isError ? ' byo-list-error' : '');
        row.innerHTML = `
          <div class="byo-list-info">
            <span class="byo-list-title">${_escHtml(col.title || 'Untitled')}</span>
            <span class="byo-list-meta">${fileCount} file${fileCount !== 1 ? 's' : ''}${chunkCount ? ` · ${chunkCount} segments` : ''}</span>
          </div>
          ${statusHtml}`;
        row.addEventListener('click', () => _openByoCollection(col));
        grid.appendChild(row);
      }
    }

    // Auto-poll while any collection is still processing (capped)
    if (hasProcessing && !_byoPollTimer) {
      _byoPollCount = 0;
      _byoPollTimer = setInterval(() => {
        _byoPollCount++;
        if (_byoPollCount > _BYO_POLL_MAX) {
          console.warn('[BYO] Max poll attempts reached, stopping');
          clearInterval(_byoPollTimer); _byoPollTimer = null;
          return;
        }
        _loadByoMaterials();
      }, 4000);
    } else if (!hasProcessing && _byoPollTimer) {
      clearInterval(_byoPollTimer);
      _byoPollTimer = null;
      _byoPollCount = 0;
    }
  } catch (e) {
    console.warn('Failed to load BYO materials:', e);
  }
}

async function _searchByoMaterials(query) {
  if (!query.trim()) { _loadByoMaterials(); return; }
  try {
    const res = await fetch(
      `${state.apiUrl || ''}/api/v1/byo/collections/search?q=${encodeURIComponent(query)}`,
      { headers: AuthManager.authHeaders() },
    );
    if (!res.ok) return;
    const collections = await res.json();

    const grid = document.getElementById('byo-grid');
    const uploadZone = document.getElementById('byo-upload-zone');
    if (!grid) return;
    grid.querySelectorAll('.byo-material-card').forEach(c => c.remove());

    if (!collections.length) {
      const empty = document.createElement('div');
      empty.className = 'byo-material-card';
      empty.innerHTML = '<div class="byo-card-body"><div class="byo-card-title">No matches</div><div class="byo-card-meta">Try a different search term</div></div>';
      grid.insertBefore(empty, uploadZone);
      return;
    }

    // Reuse the same card rendering as _loadByoMaterials
    for (const col of collections) {
      const card = document.createElement('div');
      card.className = 'byo-material-card';
      const fileCount = col.stats?.resources || 0;
      const tags = (col.tags || []).slice(0, 3);
      const t = (col.title || '').toLowerCase();
      const typeIcon = t.includes('.pdf') ? '&#128196;' : t.includes('video') ? '&#127909;' : '&#128218;';
      card.innerHTML = `
        <div class="byo-card-header"><span class="byo-card-icon">${typeIcon}</span></div>
        <div class="byo-card-body">
          <div class="byo-card-title">${_escHtml(col.title || 'Untitled')}</div>
          <div class="byo-card-meta">${fileCount} file${fileCount !== 1 ? 's' : ''}</div>
          ${tags.length ? `<div class="byo-card-tags">${tags.map(t => `<span class="byo-tag">${_escHtml(t)}</span>`).join('')}</div>` : ''}
        </div>`;
      card.addEventListener('click', () => _openByoCollection(col));
      grid.insertBefore(card, uploadZone);
    }
  } catch (e) { console.warn('BYO search failed:', e); }
}

async function _openByoCollection(col) {
  // Fetch resources in this collection and open the first one in preview panel
  try {
    const res = await fetch(
      `${state.apiUrl || ''}/api/v1/byo/collections/${col.collection_id}/resources`,
      { headers: AuthManager.authHeaders() },
    );
    if (!res.ok) return;
    const resources = await res.json();

    if (!resources.length) {
      _openPreviewPanel('collection', col.title || 'Collection', {
        markdown: `*No files in this collection yet.*`,
      });
      return;
    }

    // If single resource, open it directly
    if (resources.length === 1) {
      _openByoResource(resources[0]);
      return;
    }

    // Multiple resources — show a list, each clickable
    const listHtml = resources.map(r => {
      const icon = _mimeIcon(r.mime_type);
      const size = r.file_size ? `${(r.file_size / 1024).toFixed(0)} KB` : '';
      return `<div class="ep-resource-item" data-rid="${r.resource_id}" data-mime="${_escHtml(r.mime_type || '')}">
        <span class="ep-resource-icon">${icon}</span>
        <span class="ep-resource-name">${_escHtml(r.original_name || 'file')}</span>
        <span class="ep-resource-size">${size}</span>
      </div>`;
    }).join('');

    _openPreviewPanel('collection', col.title || 'Collection', { markdown: '' });
    const body = document.getElementById('ep-body');
    if (body) {
      body.innerHTML = `<div class="ep-resource-list">${listHtml}</div>`;
      body.querySelectorAll('.ep-resource-item').forEach(item => {
        item.addEventListener('click', () => {
          const r = resources.find(r => r.resource_id === item.dataset.rid);
          if (r) _openByoResource(r);
        });
      });
    }
  } catch (e) {
    console.warn('Failed to open collection:', e);
  }
}

function _openByoResource(resource) {
  const fileUrl = `${state.apiUrl || ''}/api/v1/byo/resources/${resource.resource_id}/file`;
  _openPreviewPanel(
    resource.mime_type || 'file',
    resource.original_name || 'File',
    { _fileUrl: fileUrl, _mimeType: resource.mime_type || '' },
  );
}

function _mimeIcon(mime) {
  if (!mime) return '&#128196;';
  if (mime === 'application/pdf') return '&#128196;';
  if (mime.startsWith('video/')) return '&#127909;';
  if (mime.startsWith('audio/')) return '&#127925;';
  if (mime.startsWith('image/')) return '&#128247;';
  if (mime.includes('word') || mime.includes('docx')) return '&#128196;';
  if (mime === 'text/plain' || mime === 'text/markdown') return '&#128221;';
  return '&#128218;';
}

function _byoIcon(col) {
  const t = (col.title || '').toLowerCase();
  if (t.includes('.pdf') || t.includes('pdf')) return '&#128196;';
  if (t.includes('video') || t.includes('.mp4')) return '&#127909;';
  if (t.includes('note')) return '&#128221;';
  return '&#128218;';
}

async function _handleByoDroppedFiles(files) {
  // Wrap FileList into a synthetic event-like call to reuse _handleByoUpload logic
  const title = files.length === 1 ? files[0].name : `Upload (${files.length} files)`;
  try {
    const createRes = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify({ title }),
    });
    if (!createRes.ok) { alert('Failed to create collection'); return; }
    const col = await createRes.json();
    const colId = col.collection_id;

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      await fetch(`${state.apiUrl || ''}/api/v1/byo/collections/${colId}/resources`, {
        method: 'POST',
        headers: AuthManager.authHeaders(),
        body: formData,
      });
    }
    _loadByoMaterials();
  } catch (err) {
    console.error('Drop upload failed:', err);
    alert('Upload failed. Please try again.');
  }
}

async function _handleByoLinkAdd() {
  const input = document.getElementById('byo-link-input');
  const btn = document.getElementById('byo-link-btn');
  if (!input) return;
  const url = input.value.trim();
  if (!url) return;

  // Basic URL validation
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    alert('Please enter a valid URL starting with http:// or https://');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Adding...';
  try {
    // Create collection titled after the URL
    const title = url.includes('youtube') || url.includes('youtu.be')
      ? 'YouTube video'
      : new URL(url).hostname.replace('www.', '');
    const createRes = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify({ title }),
    });
    if (!createRes.ok) { alert('Failed to create collection'); return; }
    const col = await createRes.json();

    // Add URL as resource
    const formData = new FormData();
    formData.append('url', url);
    formData.append('title', title);
    await fetch(`${state.apiUrl || ''}/api/v1/byo/collections/${col.collection_id}/resources`, {
      method: 'POST',
      headers: AuthManager.authHeaders(),
      body: formData,
    });

    input.value = '';
    _loadByoMaterials();
  } catch (err) {
    console.error('Link add failed:', err);
    alert('Failed to add link. Please try again.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Add link';
  }
}

async function _handleByoUpload(e) {
  const files = e.target.files;
  if (!files || !files.length) return;

  // Create a collection first
  const title = files.length === 1 ? files[0].name : `Upload (${files.length} files)`;
  try {
    const createRes = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify({ title }),
    });
    if (!createRes.ok) { alert('Failed to create collection'); return; }
    const col = await createRes.json();
    const colId = col.collection_id;

    // Upload each file
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      await fetch(`${state.apiUrl || ''}/api/v1/byo/collections/${colId}/resources`, {
        method: 'POST',
        headers: AuthManager.authHeaders(),
        body: formData,
      });
    }

    // Refresh the materials grid
    _loadByoMaterials();
  } catch (err) {
    console.error('Upload failed:', err);
    alert('Upload failed. Please try again.');
  }

  // Reset file input
  e.target.value = '';
}

// ═══════════════════════════════════════════════════════════════
//   Preview Panel (split view in chat — like Claude's artifacts)
// ═══════════════════════════════════════════════════════════════

function _openPreviewPanel(type, title, content) {
  const panel = document.getElementById('euler-preview');
  const body = document.getElementById('ep-body');
  const typeEl = document.getElementById('ep-type');
  const titleEl = document.getElementById('ep-title');
  if (!panel || !body) return;

  typeEl.textContent = type;
  titleEl.textContent = title;

  // ── File-based content (from materials page or BYO resources) ──
  if (content._fileUrl) {
    const mime = content._mimeType || '';
    const url = content._fileUrl;

    if (mime === 'application/pdf') {
      body.innerHTML = `<iframe src="${_escHtml(url)}" class="ep-file-viewer ep-pdf" title="PDF viewer"></iframe>`;
    } else if (mime.startsWith('video/')) {
      body.innerHTML = `<video controls class="ep-file-viewer ep-video" src="${_escHtml(url)}">
        Your browser does not support video playback.</video>`;
    } else if (mime.startsWith('audio/')) {
      body.innerHTML = `<div class="ep-audio-wrap">
        <div class="ep-audio-icon">&#127925;</div>
        <audio controls class="ep-audio" src="${_escHtml(url)}">
          Your browser does not support audio playback.</audio>
      </div>`;
    } else if (mime.startsWith('image/')) {
      body.innerHTML = `<img src="${_escHtml(url)}" class="ep-file-viewer ep-image" alt="${_escHtml(title)}">`;
    } else if (mime === 'text/plain' || mime === 'text/markdown') {
      // Fetch and render as markdown
      fetch(url).then(r => r.text()).then(text => {
        body.innerHTML = `<div class="av-markdown">${_renderMarkdownFull(text)}</div>`;
        _renderKatexIn(body);
      }).catch(() => {
        body.innerHTML = `<div class="ep-unsupported">Could not load text file.</div>`;
      });
    } else {
      body.innerHTML = `<div class="ep-unsupported">
        <div class="ep-unsupported-icon">&#128196;</div>
        <div class="ep-unsupported-text">Preview not available for ${_escHtml(mime || 'this file type')}.</div>
        <a href="${_escHtml(url)}" download class="ep-download-btn">Download file</a>
      </div>`;
    }

    panel.style.display = 'flex';
    return;
  }

  // ── Audio artifact (from TTS) ──
  if (content.audio_url) {
    const duration = content.duration_estimate ? Math.round(content.duration_estimate) : '';
    const durationStr = duration ? `${Math.floor(duration / 60)}:${String(duration % 60).padStart(2, '0')}` : '';
    body.innerHTML = `<div class="ep-audio-wrap">
      <div class="ep-audio-icon">&#127911;</div>
      <div class="ep-audio-title">${_escHtml(title)}</div>
      ${durationStr ? `<div class="ep-audio-duration">~${durationStr}</div>` : ''}
      <audio controls class="ep-audio" src="${_escHtml(content.audio_url)}" preload="auto">
        Your browser does not support audio playback.</audio>
    </div>`;
    panel.style.display = 'flex';
    return;
  }

  // ── Artifact content (from Euler) ──
  if (type === 'flashcards' && content.cards) {
    body.innerHTML = content.cards.map((c, i) => `
      <div class="ep-fc" data-index="${i}">
        <div class="ep-fc-q">${_renderKatexStr(c.front || '')}</div>
        <div class="ep-fc-a">${_renderKatexStr(c.back || '')}</div>
      </div>
    `).join('') + `<div class="ep-fc-count">${content.cards.length} cards</div>`;
  } else if (content.markdown) {
    body.innerHTML = `<div class="av-markdown">${_renderMarkdownFull(content.markdown)}</div>`;
    _renderKatexIn(body);
  } else if (content.steps) {
    body.innerHTML = content.steps.map((s, i) => `
      <div class="ep-step">
        <div class="ep-step-n">${i + 1}</div>
        <div>
          <div class="ep-step-title">${_escHtml(s.title || '')}</div>
          <div class="ep-step-desc">${_renderMarkdownFull(s.description || '')}</div>
        </div>
      </div>
    `).join('');
    _renderKatexIn(body);
  } else if (content.problems) {
    body.innerHTML = content.problems.map((p, i) => `
      <div class="ep-problem">
        <div class="ep-problem-q"><strong>Q${i + 1}.</strong> ${_renderMarkdownFull(p.question || '')}</div>
        <details class="ep-problem-sol"><summary>Show solution</summary>${_renderMarkdownFull(p.solution || '')}</details>
      </div>
    `).join('');
    _renderKatexIn(body);
  } else {
    // Try to render as markdown for any content with a text-like field
    const textish = content.text || content.body || content.summary || content.description || '';
    if (textish) {
      body.innerHTML = `<div class="av-markdown">${_renderMarkdownFull(textish)}</div>`;
      _renderKatexIn(body);
    } else {
      body.innerHTML = `<pre class="av-generic">${_escHtml(JSON.stringify(content, null, 2))}</pre>`;
    }
  }

  panel.style.display = 'flex';
}

function _closePreviewPanel() {
  const panel = document.getElementById('euler-preview');
  if (panel) panel.style.display = 'none';
}

// Also open preview when ARTIFACT event fires (auto-open)
// This is wired in _handleEulerEvent

// ═══════════════════════════════════════════════════════════════
//   Artifact Viewer
// ═══════════════════════════════════════════════════════════════

let _avCards = [];    // current flashcard set
let _avIndex = 0;     // current card index
let _avData = null;   // full artifact data

function openArtifactViewer(artifactType, title, content, artifactId) {
  _avData = { type: artifactType, title, content, artifactId };
  const overlay = document.getElementById('artifact-viewer');
  const typeEl = document.getElementById('av-type');
  const titleEl = document.getElementById('av-title');
  if (!overlay) return;

  typeEl.textContent = artifactType;
  titleEl.textContent = title;

  // Hide all modes
  ['av-flashcards', 'av-markdown', 'av-pdf', 'av-html', 'av-image', 'av-generic'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.add('hidden'); if (el.tagName === 'IFRAME') el.src = ''; }
  });

  // Route to the right renderer based on content type
  if (artifactType === 'flashcards' && content.cards) {
    _avCards = content.cards;
    _avIndex = 0;
    document.getElementById('av-flashcards').classList.remove('hidden');
    _renderAVCard();

  } else if (content.pdf_url || content.pdf_base64) {
    // PDF — render in iframe
    const pdf = document.getElementById('av-pdf');
    pdf.classList.remove('hidden');
    pdf.src = content.pdf_url || `data:application/pdf;base64,${content.pdf_base64}`;

  } else if (content.html) {
    // HTML — render in sandboxed iframe
    const html = document.getElementById('av-html');
    html.classList.remove('hidden');
    html.srcdoc = content.html;

  } else if (content.image_url || content.image_base64) {
    // Image — render in container
    const img = document.getElementById('av-image');
    img.classList.remove('hidden');
    const src = content.image_url || `data:image/png;base64,${content.image_base64}`;
    img.innerHTML = `<img src="${_escHtml(src)}" style="max-width:100%;max-height:100%;object-fit:contain;border-radius:8px" alt="${_escHtml(title)}">`;

  } else if (content.audio_url) {
    // Audio — inline player
    const md = document.getElementById('av-markdown');
    md.classList.remove('hidden');
    md.innerHTML = `<div style="text-align:center;padding:40px 20px">
      <div style="font-size:48px;margin-bottom:16px">&#127911;</div>
      <div style="font-size:16px;font-weight:600;margin-bottom:16px">${_escHtml(title)}</div>
      <audio controls style="width:100%;max-width:400px" src="${_escHtml(content.audio_url)}" preload="auto"></audio>
    </div>`;

  } else if (content.code) {
    // Code file — syntax highlighted
    const lang = content.language || content.lang || _guessLangFromTitle(title) || '';
    const md = document.getElementById('av-markdown');
    md.classList.remove('hidden');
    md.innerHTML = `<div class="av-code-viewer">
      <div class="av-code-header">
        <span class="av-code-lang">${_escHtml(lang.toUpperCase() || 'CODE')}</span>
        <button class="av-code-copy" onclick="navigator.clipboard.writeText(this.closest('.av-code-viewer').querySelector('code').textContent)">Copy</button>
      </div>
      <pre class="av-code-block"><code class="language-${_escHtml(lang)}">${_escHtml(content.code)}</code></pre>
    </div>`;

  } else if (content.markdown) {
    _avShowMarkdown(content.markdown);

  } else if (content.steps || content.problems) {
    const items = content.steps || content.problems || [];
    const html = items.map((s, i) => {
      const t = s.title || s.question || `Item ${i + 1}`;
      const body = s.description || s.solution || s.content || '';
      return `<h3>${i + 1}. ${_escHtml(t)}</h3>${_renderMarkdownFull(body)}`;
    }).join('');
    _avShowMarkdown(html, true);

  } else if (content.content_markdown) {
    // Alternative markdown field name
    _avShowMarkdown(content.content_markdown);

  } else {
    // Auto-detect: try text-like fields as markdown, fall back to JSON
    const textish = content.text || content.body || content.summary || content.description || '';
    if (textish) {
      _avShowMarkdown(textish);
    } else {
      const gen = document.getElementById('av-generic');
      gen.classList.remove('hidden');
      gen.textContent = JSON.stringify(content, null, 2);
    }
  }

  overlay.classList.remove('hidden');
}

function _guessLangFromTitle(title) {
  if (!title) return '';
  const t = title.toLowerCase();
  if (t.endsWith('.py') || t.includes('python')) return 'python';
  if (t.endsWith('.js') || t.includes('javascript')) return 'javascript';
  if (t.endsWith('.ts') || t.includes('typescript')) return 'typescript';
  if (t.endsWith('.html')) return 'html';
  if (t.endsWith('.css')) return 'css';
  if (t.endsWith('.java')) return 'java';
  if (t.endsWith('.cpp') || t.endsWith('.c')) return 'cpp';
  if (t.endsWith('.go')) return 'go';
  if (t.endsWith('.rs')) return 'rust';
  if (t.endsWith('.sql')) return 'sql';
  if (t.endsWith('.json')) return 'json';
  return '';
}

function _avShowMarkdown(text, isPreRendered) {
  const md = document.getElementById('av-markdown');
  md.classList.remove('hidden');
  md.innerHTML = isPreRendered ? text : _renderMarkdownFull(text);
  _renderKatexIn(md);
}

window.closeArtifactViewer = function() {
  document.getElementById('artifact-viewer')?.classList.add('hidden');
};

// Spaced repetition rating for flashcards
window.rateFlashcard = async function(rating) {
  if (!_avData || !_avData.artifactId) {
    // No artifact ID — just advance to next card
    navArtifactCard(1);
    return;
  }
  try {
    await fetch(`${state.apiUrl || ''}/api/v1/artifacts/${_avData.artifactId}/sr`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify({ card_index: _avIndex, rating }),
    });
  } catch (e) { /* ignore */ }
  // Show SR buttons after flip, advance after rating
  navArtifactCard(1);
};

// Keyboard: Escape closes, arrows navigate flashcards, space flips
document.addEventListener('keydown', (e) => {
  const viewer = document.getElementById('artifact-viewer');
  if (!viewer || viewer.classList.contains('hidden')) return;
  if (e.key === 'Escape') closeArtifactViewer();
  else if (e.key === 'ArrowLeft') navArtifactCard(-1);
  else if (e.key === 'ArrowRight') navArtifactCard(1);
  else if (e.key === ' ') { e.preventDefault(); flipArtifactCard(); }
});

window.flipArtifactCard = function() {
  document.getElementById('av-fc-inner')?.classList.toggle('flipped');
};

window.navArtifactCard = function(dir) {
  _avIndex = Math.max(0, Math.min(_avCards.length - 1, _avIndex + dir));
  document.getElementById('av-fc-inner')?.classList.remove('flipped');
  _renderAVCard();
};

function _renderAVCard() {
  if (!_avCards.length) return;
  const card = _avCards[_avIndex];
  const front = document.getElementById('av-fc-front');
  const back = document.getElementById('av-fc-back');
  const counter = document.getElementById('av-fc-counter');

  if (front) { front.innerHTML = _renderKatexStr(card.front || ''); }
  if (back) { back.innerHTML = _renderKatexStr(card.back || ''); }
  if (counter) counter.textContent = `${_avIndex + 1} / ${_avCards.length}`;

  // Disable prev/next at bounds
  const prev = document.querySelector('.av-fc-prev');
  const next = document.querySelector('.av-fc-next');
  if (prev) prev.disabled = _avIndex === 0;
  if (next) next.disabled = _avIndex === _avCards.length - 1;
}

function _renderKatexStr(text) {
  // Render $...$ and $$...$$ inline with KaTeX
  if (typeof katex === 'undefined') return _escHtml(text);
  return text.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
    try { return katex.renderToString(expr.trim(), { displayMode: true, throwOnError: false }); }
    catch { return `<code>${_escHtml(expr)}</code>`; }
  }).replace(/\$([^$\n]+?)\$/g, (_, expr) => {
    try { return katex.renderToString(expr.trim(), { displayMode: false, throwOnError: false }); }
    catch { return `<code>${_escHtml(expr)}</code>`; }
  });
}

function _renderKatexIn(el) {
  // Find text nodes with $...$ and render KaTeX
  if (typeof katex === 'undefined') return;
  el.innerHTML = el.innerHTML.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
    try { return katex.renderToString(expr.trim(), { displayMode: true, throwOnError: false }); }
    catch { return `<code>${expr}</code>`; }
  }).replace(/\$([^$\n]+?)\$/g, (_, expr) => {
    try { return katex.renderToString(expr.trim(), { displayMode: false, throwOnError: false }); }
    catch { return `<code>${expr}</code>`; }
  });
}

function _renderMarkdownFull(text) {
  // Parse pipe tables BEFORE escaping HTML
  const lines = text.split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    // Detect pipe table: current line has |, next line is separator (|---|---|)
    if (lines[i].includes('|') && i + 1 < lines.length && /^\|?\s*[-:]+[-|:\s]+$/.test(lines[i + 1])) {
      const headerCells = lines[i].split('|').map(c => c.trim()).filter(Boolean);
      const alignRow = lines[i + 1].split('|').map(c => c.trim()).filter(Boolean);
      const aligns = alignRow.map(c => {
        if (c.startsWith(':') && c.endsWith(':')) return 'center';
        if (c.endsWith(':')) return 'right';
        return 'left';
      });
      let table = '<table><thead><tr>';
      headerCells.forEach((c, ci) => {
        table += `<th style="text-align:${aligns[ci] || 'left'}">${_escHtml(c)}</th>`;
      });
      table += '</tr></thead><tbody>';
      i += 2; // skip header + separator
      while (i < lines.length && lines[i].includes('|')) {
        const cells = lines[i].split('|').map(c => c.trim()).filter(Boolean);
        table += '<tr>';
        cells.forEach((c, ci) => {
          table += `<td style="text-align:${aligns[ci] || 'left'}">${_inlineMarkdown(_escHtml(c))}</td>`;
        });
        table += '</tr>';
        i++;
      }
      table += '</tbody></table>';
      out.push(table);
    } else {
      // Escape HTML for non-table lines (tables already escaped above)
      out.push(lines[i].replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'));
      i++;
    }
  }

  // Now render the non-table lines as markdown
  return out.join('\n')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^---$/gm, '<hr>')
    .replace(/^\- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

function _inlineMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

// ═══════════════════════════════════════════════════════════════

function _renderEulerCourseCards(toolResult) {
  // Extract course IDs and their matched lessons from tool result
  const idMatches = toolResult.match(/id=(\d+)/g);
  if (!idMatches || !_cachedCourses) return;

  const ids = [...new Set(idMatches.map(m => parseInt(m.split('=')[1])))];
  const courses = ids.map(id => _cachedCourses.find(c => c.id === id)).filter(Boolean);
  if (!courses.length) return;

  // Parse matched lessons per course: "Course: ... (id=X)\n  lesson:Y — Title"
  const lessonsByCoursId = {};
  const blocks = toolResult.split(/\nCourse[: ]/);
  for (const block of blocks) {
    const cidMatch = block.match(/id=(\d+)/);
    if (!cidMatch) continue;
    const cid = parseInt(cidMatch[1]);
    const lessons = [];
    const lessonMatches = block.matchAll(/lesson:(\d+)\s*[—–-]\s*(.+)/g);
    for (const m of lessonMatches) {
      lessons.push({ id: parseInt(m[1]), title: m[2].trim() });
    }
    if (lessons.length) lessonsByCoursId[cid] = lessons;
  }

  const container = document.getElementById('euler-messages');
  if (!container) return;

  const msg = document.createElement('div');
  msg.className = 'euler-msg euler-msg-euler';
  msg.innerHTML = `
    <div class="euler-msg-row">
      <div class="euler-msg-avatar" style="visibility:hidden">E</div>
      <div class="euler-course-cards">
        ${courses.map(c => {
          const thumb = _courseThumbStyle(c);
          const tag = c.subject || _guessSubject(c.title);
          const matched = lessonsByCoursId[c.id] || [];
          const lessonsHtml = matched.length
            ? `<div class="euler-ccard-matches">
                <div class="euler-ccard-matches-label">Matching lessons:</div>
                ${matched.slice(0, 4).map(l =>
                  `<div class="euler-ccard-match">
                    <span class="euler-ccard-match-dot"></span>
                    <span>${_escHtml(l.title)}</span>
                  </div>`
                ).join('')}
                ${matched.length > 4 ? `<div class="euler-ccard-match-more">+${matched.length - 4} more</div>` : ''}
              </div>`
            : '';
          return `<div class="euler-ccard" data-course-id="${c.id}" onclick="_eulerNavigateTo('/courses/${c.id}')">
            <div class="euler-ccard-thumb" style="background:${thumb}">
              <span class="euler-ccard-tag">${_escHtml(tag)}</span>
              <span class="euler-ccard-lessons">${c.lesson_count || '?'} lessons</span>
            </div>
            <div class="euler-ccard-body">
              <div class="euler-ccard-title">${_escHtml(c.title)}</div>
              <div class="euler-ccard-desc">${_escHtml((c.description || '').slice(0, 100))}${(c.description || '').length > 100 ? '...' : ''}</div>
            </div>
            ${lessonsHtml}
            <div class="euler-ccard-action">Explore course &rarr;</div>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  container.appendChild(msg);
  msg.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

window._eulerNavigateTo = function(target) {
  Router.navigate(target);
};

function _eulerResetToIdle() {
  const idle = document.getElementById('euler-idle');
  const chat = document.getElementById('euler-chat');
  const msgs = document.getElementById('euler-messages');
  const hasHistory = msgs && msgs.children.length > 0;

  if (hasHistory) {
    if (idle) idle.style.display = 'none';
    if (chat) chat.style.display = 'flex';
    _eulerStarted = true;
  } else {
    if (idle) idle.style.display = 'flex';
    if (chat) chat.style.display = 'none';
    _eulerStarted = false;
  }
}

function _eulerFullReset() {
  const idle = document.getElementById('euler-idle');
  const chat = document.getElementById('euler-chat');
  const msgs = document.getElementById('euler-messages');
  if (idle) idle.style.display = 'flex';
  if (chat) chat.style.display = 'none';
  if (msgs) msgs.innerHTML = '';
  _eulerStarted = false;
  _eulerHistory = [];
  _eulerBusy = false;
  _eulerSuppressText = false;
}

function _renderMarkdown(text) {
  // Minimal markdown: bold, italic, code, links, line breaks
  // Also detect course references like (course 4) or (id=4) and make them clickable
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\[(.+?)\]\((.+?)\)/g, function(_, text, url) {
      if (url.startsWith('/')) {
        // Internal link — use router navigation
        return `<a href="${url}" class="euler-internal-link" onclick="event.preventDefault();Router.navigate('${url}')">${text}</a>`;
      }
      return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
    })
    .replace(/\n/g, '<br>');
}

function _escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

// ═══════════════════════════════════════════════════════════════

function _filterBrowseCourses(query) {
  const grid = document.getElementById('browse-courses-grid');
  if (!grid) return;
  const q = query.toLowerCase().trim();
  const cards = grid.querySelectorAll('.ccard');

  if (!q) {
    // Show all cards + hide the "no match" hint
    cards.forEach(c => c.style.display = '');
    const hint = document.getElementById('browse-no-match');
    if (hint) hint.style.display = 'none';
    return;
  }

  let visible = 0;
  cards.forEach(card => {
    const title = (card.querySelector('h3')?.textContent || '').toLowerCase();
    const desc = (card.querySelector('p')?.textContent || '').toLowerCase();
    const match = title.includes(q) || desc.includes(q) || q.split(' ').some(w => w.length > 2 && (title.includes(w) || desc.includes(w)));
    card.style.display = match ? '' : 'none';
    if (match) visible++;
  });

  // Show/create "no match" hint with on-demand CTA
  let hint = document.getElementById('browse-no-match');
  if (visible === 0) {
    if (!hint) {
      hint = document.createElement('div');
      hint.id = 'browse-no-match';
      hint.className = 'browse-no-match';
      grid.parentElement.insertBefore(hint, grid.nextSibling);
    }
    hint.innerHTML = `
      <p>No courses match "<strong>${q}</strong>"</p>
      <button class="sc-btn sc-btn-sm sc-btn-accent" onclick="_startOnDemandSession('${q.replace(/'/g, "\\'")}')">
        Let your tutor teach you this &rarr;
      </button>
      <p class="browse-no-match-sub">Your tutor can teach any topic — even without a structured course.</p>
    `;
    hint.style.display = '';
  } else if (hint) {
    hint.style.display = 'none';
  }
}

async function _loadCourseDetail(courseId) {
  state.courseId = courseId;
  const courseIdEl = document.getElementById('course-id');
  if (courseIdEl) courseIdEl.value = courseId;

  // Show skeleton while loading
  const curEl = document.getElementById('cd-curriculum');
  if (curEl) curEl.innerHTML = Array.from({ length: 3 }, () =>
    `<div class="mod-block"><div class="mod-head skeleton-pulse" style="height:44px;border-radius:10px"></div></div>`
  ).join('');

  try {
    // Check sessionStorage cache first
    const cacheKey = `capacity_course_${courseId}`;
    let data = null;
    try {
      const cached = sessionStorage.getItem(cacheKey);
      if (cached) {
        const { d, ts } = JSON.parse(cached);
        if (Date.now() - ts < _COURSE_CACHE_TTL) data = d;
      }
    } catch (e) { /* ignore */ }

    if (!data) {
      const res = await fetch(`${state.apiUrl || ''}/api/v1/content/courses/${courseId}`, {
        headers: AuthManager.authHeaders(),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      data = await res.json();
      try { sessionStorage.setItem(cacheKey, JSON.stringify({ d: data, ts: Date.now() })); } catch (e) { /* quota */ }
    }
    _courseDetailData = data;

    const course = data.course || {};
    const modules = data.modules || [];
    const lessons = data.lessons || [];

    // Header
    document.getElementById('cd-title').textContent = course.title || 'Course';
    document.getElementById('cd-description').textContent = course.description || '';
    document.getElementById('cd-lessons-count').textContent = lessons.length;
    document.getElementById('cd-modules-count').textContent = modules.length;
    const totalMin = lessons.reduce((s, l) => s + (l.duration || 50), 0);
    document.getElementById('cd-hours').textContent = '~' + Math.round(totalMin / 60);

    // Tag — use subject from API
    const tagEl = document.getElementById('cd-tag');
    if (tagEl) {
      const subj = course.tags?.[0] || _guessSubject(course.title);
      tagEl.textContent = subj;
      tagEl.className = 'sc-tag ' + _courseTagClass({ subject: subj });
    }

    // Banner — use course thumbnail or gradient
    const banner = document.getElementById('cd-banner');
    if (banner) banner.style.background = _courseThumbStyle(course);

    // Reset tabs to first tab
    document.querySelectorAll('.cd-tab').forEach((t, i) => t.classList.toggle('active', i === 0));
    document.querySelectorAll('.cd-tab-content').forEach((c, i) => c.classList.toggle('active', i === 0));

    // Curriculum
    const curEl = document.getElementById('cd-curriculum');
    if (curEl) {
      let lessonNum = 0;
      curEl.innerHTML = modules.map(mod => {
        const modLessons = lessons
          .filter(l => l.module_id === mod.id)
          .sort((a, b) => (a.order || 0) - (b.order || 0));
        return `
          <div class="mod-block">
            <div class="mod-head"><span>${mod.title}</span><span>${modLessons.length} lessons</span></div>
            <div class="les-list">${modLessons.map(l => {
              lessonNum++;
              const thumb = _ytThumb(l.video_url);
              const thumbHtml = thumb
                ? `<div class="les-thumb"><img src="${thumb}" loading="lazy"><span class="les-thumb-dur">${l.duration || '?'}m</span></div>`
                : `<div class="les-n">${lessonNum}</div>`;
              return `<div class="les" data-lesson-id="${l.id}" data-lesson-title="${l.title}">
                ${thumbHtml}
                <div class="les-info"><h4>${l.title}</h4><span>${l.duration || '?'} min</span></div>
                <span class="les-go">Start &rarr;</span>
              </div>`;
            }).join('')}</div>
          </div>`;
      }).join('');

      // Wire lesson clicks → start session for that lesson
      curEl.querySelectorAll('.les').forEach(row => {
        row.addEventListener('click', () => {
          _startFromLesson(courseId, parseInt(row.dataset.lessonId), row.dataset.lessonTitle);
        });
      });
    }

    // Populate mode expansion panels with lesson checkboxes
    _buildModeExpansions(modules, lessons);

  } catch (e) {
    console.error('Failed to load course detail:', e);
    document.getElementById('cd-title').textContent = 'Course not found';
    document.getElementById('cd-description').textContent = 'This course doesn\'t exist or couldn\'t be loaded.';
    // Auto-redirect after 2s
    setTimeout(() => Router.navigate('/home'), 2000);
  }
}

function _buildModeExpansions(modules, lessons) {
  // Build lesson list HTML for both modes
  let num = 0;
  const lessonCheckboxes = lessons
    .sort((a, b) => (a.order || 0) - (b.order || 0))
    .map(l => {
      num++;
      const hasVideo = l.video_url ? ' <span class="les-video-badge">video</span>' : '';
      return `<label class="mode-les-row">
        <input type="checkbox" value="${l.id}" data-title="${l.title}" checked>
        <span class="mode-les-num">${num}</span>
        <span class="mode-les-title">${l.title}${hasVideo}</span>
        <span class="mode-les-dur">${l.duration || '?'}m</span>
      </label>`;
    }).join('');

  // Tutor mode expansion
  const tutorExp = document.getElementById('mode-tutor-expand');
  if (tutorExp) {
    tutorExp.innerHTML = `
      <div class="mode-intent-row">
        <input type="text" class="mode-intent" id="mode-tutor-intent"
          placeholder="What do you want to focus on? (optional)">
      </div>
      <div class="mode-les-header">
        <span>Lessons to cover</span>
        <button class="mode-les-toggle" onclick="this.closest('.mode-expand').querySelectorAll('input[type=checkbox]').forEach(c=>c.checked=!c.checked)">Toggle all</button>
      </div>
      <div class="mode-les-list">${lessonCheckboxes}</div>`;
  }

  // Video mode expansion
  const videoExp = document.getElementById('mode-video-expand');
  if (videoExp) {
    const videoLessons = lessons.filter(l => l.video_url);
    if (videoLessons.length === 0) {
      videoExp.innerHTML = `<p class="mode-no-video">No video lectures available for this course.</p>`;
    } else {
      let vNum = 0;
      const videoCheckboxes = videoLessons
        .sort((a, b) => (a.order || 0) - (b.order || 0))
        .map(l => {
          vNum++;
          return `<label class="mode-les-row">
            <input type="checkbox" value="${l.id}" data-title="${l.title}" checked>
            <span class="mode-les-num">${vNum}</span>
            <span class="mode-les-title">${l.title}</span>
            <span class="mode-les-dur">${l.duration || '?'}m</span>
          </label>`;
        }).join('');
      videoExp.innerHTML = `
        <div class="mode-les-header">
          <span>Lectures to watch</span>
          <button class="mode-les-toggle" onclick="this.closest('.mode-expand').querySelectorAll('input[type=checkbox]').forEach(c=>c.checked=!c.checked)">Toggle all</button>
        </div>
        <div class="mode-les-list">${videoCheckboxes}</div>`;
    }
  }
}

function _getSelectedLessons(modeId) {
  const expand = document.getElementById(modeId + '-expand');
  if (!expand) return [];
  return Array.from(expand.querySelectorAll('input[type=checkbox]:checked'))
    .map(cb => ({ id: parseInt(cb.value), title: cb.dataset.title }));
}

async function _startFromLesson(courseId, lessonId, lessonTitle) {
  const user = AuthManager.getUser();
  if (!user) return Router.navigate('/login');

  const videoMode = document.getElementById('mode-video');
  const isVideo = videoMode?.classList.contains('on');

  if (isVideo) {
    vmStartVideoForLesson(courseId, lessonId);
    return;
  }

  const courseIdEl = document.getElementById('course-id');
  if (courseIdEl) courseIdEl.value = courseId;
  await startNewSession(user.name, courseId, `Teach me: ${lessonTitle}`, 'course');
}

function _startFromMode() {
  const user = AuthManager.getUser();
  if (!user) return Router.navigate('/login');
  if (state._startingSession) return;
  const courseId = state.courseId;

  // Disable the button immediately
  const btn = document.getElementById('cd-mode-start-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Starting...'; }

  const isTutor = document.getElementById('mode-tutor')?.classList.contains('on');
  const scenario = isTutor ? 'course' : 'video_follow';
  const modeId = isTutor ? 'mode-tutor' : 'mode-video';

  const selected = _getSelectedLessons(modeId);
  if (selected.length === 0) return;

  // Build intent from selection
  const intentInput = document.getElementById('mode-tutor-intent');
  const customIntent = intentInput?.value?.trim();
  let intent;
  if (customIntent) {
    intent = customIntent + ` (Lessons: ${selected.map(l => l.title).join(', ')})`;
  } else if (selected.length === 1) {
    intent = `Teach me: ${selected[0].title}`;
  } else {
    intent = `Teach me these lessons: ${selected.map(l => l.title).join(', ')}`;
  }

  const courseIdEl = document.getElementById('course-id');
  if (courseIdEl) courseIdEl.value = courseId;

  if (scenario === 'video_follow') {
    // Video follow-along uses its own flow with custom video player
    const firstLesson = selected[0];
    if (firstLesson) {
      // Show playlist sidebar after video loads
      if (_courseDetailData) {
        const allLessons = (_courseDetailData.lessons || [])
          .filter(l => l.video_url)
          .sort((a, b) => (a.order || 0) - (b.order || 0));
        const selectedIds = new Set(selected.map(s => s.id));
        const playlistLessons = allLessons.filter(l => selectedIds.has(l.id));
        if (playlistLessons.length > 0) {
          setTimeout(() => _showVideoPlaylist(playlistLessons, 0), 800);
        }
      }
      vmStartVideoForLesson(courseId, firstLesson.id);
    }
    return;
  }

  _hideVideoPlaylist();
  startNewSession(user.name, courseId, intent, scenario);
}

// ─── Video playlist sidebar ──────────────────────────────

function _ytThumb(videoUrl) {
  if (!videoUrl) return '';
  const m = videoUrl.match(/(?:embed\/|watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  return m ? `https://img.youtube.com/vi/${m[1]}/mqdefault.jpg` : '';
}

const VPL_PAGE_SIZE = 5;

function _renderVplItems(lessons, activeIndex, startIdx, count) {
  const end = Math.min(startIdx + count, lessons.length);
  let html = '';
  for (let i = startIdx; i < end; i++) {
    const l = lessons[i];
    const cls = i === activeIndex ? 'vpl-item active' : (i < activeIndex ? 'vpl-item done' : 'vpl-item');
    const thumb = _ytThumb(l.video_url);
    const thumbHtml = thumb
      ? `<div class="vpl-thumb"><img src="${thumb}" alt="" loading="lazy"><span class="vpl-dur">${l.duration || '?'}m</span>${i === activeIndex ? '<span class="vpl-playing-badge">NOW PLAYING</span>' : ''}</div>`
      : `<div class="vpl-thumb vpl-thumb-empty"><span>${i + 1}</span></div>`;
    html += `<div class="${cls}" data-vpl-idx="${i}" data-lesson-id="${l.id}">
      ${thumbHtml}
      <div class="vpl-item-info">
        <div class="vpl-item-title">${l.title}</div>
        <div class="vpl-item-meta">${l.duration || '?'} min${i < activeIndex ? ' &middot; Watched' : ''}</div>
      </div>
    </div>`;
  }
  return html;
}

function _showVideoPlaylist(lessons, activeIndex) {
  const panel = document.getElementById('video-playlist');
  const list = document.getElementById('vpl-list');
  const count = document.getElementById('vpl-count');
  if (!panel || !list) return;

  panel.classList.remove('hidden');
  if (count) count.textContent = `${lessons.length} lessons`;

  state._videoPlaylist = lessons;
  state._videoPlaylistIndex = activeIndex;
  state._vplRendered = 0;

  // Start from active item (show a couple before it + page after)
  const startFrom = Math.max(0, activeIndex - 1);
  const initialCount = Math.min(VPL_PAGE_SIZE, lessons.length - startFrom);
  list.innerHTML = _renderVplItems(lessons, activeIndex, startFrom, initialCount);
  state._vplRendered = startFrom + initialCount;

  // Lazy load on scroll
  list.onscroll = () => {
    if (state._vplRendered >= lessons.length) return;
    const { scrollTop, scrollHeight, clientHeight } = list;
    if (scrollTop + clientHeight >= scrollHeight - 80) {
      const batch = _renderVplItems(lessons, activeIndex, state._vplRendered, VPL_PAGE_SIZE);
      list.insertAdjacentHTML('beforeend', batch);
      state._vplRendered = Math.min(state._vplRendered + VPL_PAGE_SIZE, lessons.length);
    }
  };
}

function _hideVideoPlaylist() {
  const panel = document.getElementById('video-playlist');
  if (panel) panel.classList.add('hidden');
}

function _advanceVideoPlaylist() {
  if (!state._videoPlaylist) return;
  const next = (state._videoPlaylistIndex || 0) + 1;
  if (next < state._videoPlaylist.length) {
    _showVideoPlaylist(state._videoPlaylist, next);
  }
}

/** Fallback: fetch video resource from collection when resource_id is missing/invalid */
async function _fetchVideoFromCollection(collectionId, fallbackResourceId) {
  if (!collectionId) {
    vmStartBYOVideo(fallbackResourceId || '', '', 'Video', '');
    return;
  }
  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/byo/collections/${collectionId}/resources`, { headers: AuthManager.authHeaders() });
    if (!res.ok) { vmStartBYOVideo(fallbackResourceId || '', collectionId, 'Video', ''); return; }
    const resources = await res.json();
    const videoRes = resources.find(r => r.mime_type?.includes('youtube') || r.mime_type?.includes('video') || r.source_url);
    if (videoRes) {
      vmStartBYOVideo(videoRes.resource_id, collectionId, videoRes.original_name || 'Video', videoRes.source_url || '');
    } else {
      vmStartBYOVideo(fallbackResourceId || '', collectionId, 'Video', '');
    }
  } catch (e) {
    vmStartBYOVideo(fallbackResourceId || '', collectionId, 'Video', '');
  }
}

async function _startOnDemandSession(intentText) {
  const user = AuthManager.getUser();
  if (!user) return Router.navigate('/login');
  if (!intentText.trim()) return;

  // Backend resolves the best matching course for this intent
  let courseId = 2; // fallback
  try {
    const res = await fetch(
      `${state.apiUrl || ''}/api/v1/content/resolve-course?q=${encodeURIComponent(intentText)}`,
      { headers: AuthManager.authHeaders() }
    );
    if (res.ok) {
      const data = await res.json();
      if (data.courseId) courseId = data.courseId;
    }
  } catch (e) {
    console.warn('Course resolve failed, using fallback:', e);
  }

  const courseIdEl = document.getElementById('course-id');
  if (courseIdEl) courseIdEl.value = courseId;

  await startNewSession(user.name, courseId, intentText, 'free');
}

// ─── Plan sidebar ─────────────────────────────────────────

function showPlanSidebar() {
  if (state._videoWatchAlong) return; // No plan in video watch-along mode
  const sb = document.getElementById('plan-sidebar');
  if (sb) sb.classList.remove('hidden');
}

function hidePlanSidebar() {
  const sb = document.getElementById('plan-sidebar');
  if (sb) sb.classList.add('hidden');
}

window.togglePlanSidebar = function() {
  const sb = document.getElementById('plan-sidebar');
  if (sb) sb.classList.toggle('collapsed');
};

function updatePlanSidebar(plan) {
  const body = document.getElementById('psb-body');
  const progressFill = document.getElementById('psb-progress-fill');
  const progressText = document.getElementById('psb-progress-text');
  if (!body) return;

  const sections = plan?.sections || plan?.steps || [];
  if (!sections.length) {
    // Still generating
    body.innerHTML = '<div class="psb-generating"><div class="psb-gen-pulse"></div><span>Building your plan...</span></div>';
    return;
  }

  // Hide generating indicator
  const genEl = document.getElementById('psb-generating');
  if (genEl) genEl.style.display = 'none';

  // Determine done/active from the status field on each section and topic
  let doneCount = 0;

  body.innerHTML = sections.map((sec, i) => {
    const isDone = sec.status === 'done';
    const isActive = sec.status === 'active';
    if (isDone) doneCount++;
    const cls = isDone ? 'psb-section done' : isActive ? 'psb-section active open' : 'psb-section';
    const title = sec.title || sec.topic || `Section ${i + 1}`;
    const topics = sec.topics || sec.steps || [];

    let topicsHtml = '';
    if (topics.length) {
      topicsHtml = `<div class="psb-topics">${topics.map((t, j) => {
        const tIsDone = isDone || t.status === 'done';
        const tIsActive = isActive && t.status === 'active';
        return `<div class="psb-topic ${tIsDone ? 'done' : ''} ${tIsActive ? 'active' : ''}" data-section="${i}" data-topic="${j}">
          <span class="psb-topic-icon">${tIsDone ? '&#10003;' : tIsActive ? '&#9654;' : '&#9675;'}</span>
          <span>${t.title || t.concept || t}</span>
          <span class="psb-jump">Jump &rarr;</span>
        </div>`;
      }).join('')}</div>`;
    }

    return `<div class="${cls}">
      <div class="psb-section-head" onclick="this.parentElement.classList.toggle('open')">
        <span class="psb-section-dot"></span>
        <span class="psb-section-title">${title}</span>
        <span class="psb-section-chevron">&#9654;</span>
      </div>
      ${topicsHtml}
    </div>`;
  }).join('');

  // Update progress — count at topic level for accuracy
  let totalTopics = 0, doneTopics = 0;
  for (const sec of sections) {
    const topics = sec.topics || sec.steps || [];
    if (topics.length > 0) {
      totalTopics += topics.length;
      doneTopics += topics.filter(t => t.status === 'done').length;
    } else {
      totalTopics += 1;
      if (sec.status === 'done') doneTopics += 1;
    }
  }
  const pct = totalTopics > 0 ? Math.round((doneTopics / totalTopics) * 100) : 0;
  if (progressFill) progressFill.style.width = pct + '%';
  if (progressText) progressText.innerHTML = `<span>${doneTopics} of ${totalTopics}</span><span>${pct}%</span>`;

  // Wire jump clicks with debounce guard
  let _lastJumpAt = 0;
  body.querySelectorAll('.psb-topic').forEach(el => {
    el.addEventListener('click', () => {
      // Guard: skip if streaming or recently jumped
      if (state.isStreaming) return;
      const now = Date.now();
      if (now - _lastJumpAt < 2000) return;
      _lastJumpAt = now;

      const secIdx = parseInt(el.dataset.section);
      const topIdx = parseInt(el.dataset.topic);
      const sec = sections[secIdx];
      const topic = sec?.topics?.[topIdx] || sec?.steps?.[topIdx];
      const title = topic?.title || topic?.concept || sec?.title || '';
      if (title) {
        streamADK(`I want to jump to: ${title}. Skip ahead to this topic in the plan.`);
      }
    });
  });

  showPlanSidebar();
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
      Router.navigate('/home');
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
    if (password.length < 8) {
      signupStatus.textContent = 'Password must be at least 8 characters.';
      signupStatus.className = 'setup-status error';
      return;
    }
    signupBtn.disabled = true;
    signupStatus.textContent = 'Creating account...';
    signupStatus.className = 'setup-status';
    try {
      await AuthManager.signup(name, email, password);
      signupStatus.textContent = '';
      Router.navigate('/home');
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
  $('#lp-signin')?.addEventListener('click', () => Router.navigate('/login'));
  $('#lp-getstarted')?.addEventListener('click', () => Router.navigate('/login'));
  $('#lp-hero-btn')?.addEventListener('click', () => {
    const input = document.getElementById('lp-hero-input');
    _lpTryIt(input?.value || 'Teach me something new');
  });
  document.getElementById('lp-hero-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') _lpTryIt(e.target.value || 'Teach me something new');
  });
  $('#lp-cta-bottom')?.addEventListener('click', () => {
    AuthManager.isLoggedIn() ? Router.navigate('/home') : Router.navigate('/login');
  });

  // Try-it input on landing page — check auth, then send to Euler
  function _lpTryIt(prompt) {
    if (!prompt || !prompt.trim()) return;
    if (AuthManager.isLoggedIn()) {
      // Go to home, fill Euler input, and send
      Router.navigate('/home');
      setTimeout(() => {
        const input = document.getElementById('euler-input');
        if (input) { input.value = prompt; }
        _eulerSend();
      }, 300);
    } else {
      // Save prompt, send to login, after login it'll auto-send
      sessionStorage.setItem('capacity_pending_prompt', prompt);
      Router.navigate('/login');
    }
  }
  $('#lp-try-btn')?.addEventListener('click', () => {
    const input = document.getElementById('lp-try-input');
    _lpTryIt(input?.value || '');
  });
  document.getElementById('lp-try-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { _lpTryIt(e.target.value); }
  });
  document.querySelectorAll('.lp-try-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const input = document.getElementById('lp-try-input');
      if (input) input.value = chip.dataset.prompt;
      _lpTryIt(chip.dataset.prompt);
    });
  });

  // ─── Home screen tabs + Euler ─────────────────────────────
  _initHomeTabs();
  _initEuler();

  // ─── Course detail wiring ─────────────────────────────
  $('#cd-back')?.addEventListener('click', () => Router.navigate('/home'));
  $('#cd-mode-start-btn')?.addEventListener('click', () => _startFromMode());

  // Tab switching
  document.querySelectorAll('.cd-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.cd-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.cd-tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById('cd-tab-' + tab.dataset.tab);
      if (target) target.classList.add('active');
    });
  });

  // Mode toggle — click header area (not expansion panel)
  document.querySelectorAll('.mode').forEach(m => {
    m.addEventListener('click', (e) => {
      if (e.target.closest('.mode-expand')) return;
      document.querySelectorAll('.mode').forEach(x => x.classList.remove('on'));
      m.classList.add('on');
    });
  });
  // Nav links back to courses
  document.querySelectorAll('[data-nav="courses"]').forEach(a => {
    a.addEventListener('click', (e) => { e.preventDefault(); Router.navigate('/home'); });
  });

  // ─── On-demand wiring ─────────────────────────────────
  $('#od-send-btn')?.addEventListener('click', () => {
    const input = document.getElementById('od-intent-input');
    if (input?.value.trim()) _startOnDemandSession(input.value.trim());
  });
  document.getElementById('od-intent-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const v = e.target.value.trim();
      if (v) _startOnDemandSession(v);
    }
  });
  // Chip click fills input
  document.querySelectorAll('#od-chips .chip').forEach(c => {
    c.addEventListener('click', () => {
      const input = document.getElementById('od-intent-input');
      if (input) { input.value = c.textContent; input.focus(); }
    });
  });

  // ─── Logout buttons on all screens ─────────────────────
  ['btn-logout', 'course-logout', 'od-logout'].forEach(id => {
    document.getElementById(id)?.addEventListener('click', () => {
      AuthManager.logout();
      state.studentName = '';
      state.userEmail = '';
      _cachedCourses = null;
      Router.navigate('/');
    });
  });

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

  // Arrow button → trigger search (not session start)
  if (startBtn) startBtn.addEventListener('click', () => {
    const intentInput = $('#student-intent-first');
    const q = (intentInput?.value || '').trim();
    if (q) _nlDoSearch(q);
  });

  // Enter key → trigger search (not session start)
  const dashInput = $('#student-intent-first');
  if (dashInput) {
    dashInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const q = dashInput.value.trim();
        if (q) _nlDoSearch(q);
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

  // ─── Dashboard course pill click ──────────────────────────
  document.querySelectorAll('.dash-course-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const cid = pill.dataset.course;
      if (!cid || cid === 'byo') return;
      if (courseIdInput) {
        courseIdInput.value = cid;
        courseIdInput.dispatchEvent(new Event('change'));
      }
      updateCourseCardSelection(parseInt(cid));
    });
  });

  $('#btn-back')?.addEventListener('click', () => {
    Router.navigate('/home');
  });

  // Plan heading bar toggle
  $('#plan-hb-toggle')?.addEventListener('click', () => togglePlanPanel());
  $('#plan-panel-close')?.addEventListener('click', () => togglePlanPanel());
  $('#plan-panel-overlay')?.addEventListener('click', (e) => {
    if (e.target.id === 'plan-panel-overlay') togglePlanPanel();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const overlay = $('#plan-panel-overlay');
      if (overlay && !overlay.classList.contains('hidden')) togglePlanPanel();
    }
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

async function startNewSession(name, courseId, intent, scenario) {
  if (!name || !courseId) return;
  scenario = scenario || 'course';

  // Block multiple clicks
  if (state._startingSession) return;
  state._startingSession = true;

  // Clean up any active session (board, agents, streaming)
  if (typeof cleanupActiveSession === 'function') cleanupActiveSession();

  // Show loading state on button
  const startBtn = $('#btn-start-session');
  const dashInput = $('#student-intent-first');
  if (startBtn) {
    startBtn.disabled = true;
    startBtn.dataset.origHtml = startBtn.innerHTML;
    startBtn.innerHTML = '<span class="dash-send-spinner"></span>';
  }
  if (dashInput) dashInput.disabled = true;

  // Disable chips
  document.querySelectorAll('.dash-chip').forEach(c => c.style.pointerEvents = 'none');

  state.studentName = name;
  state.studentIntent = intent;
  state.courseId = courseId;

  showSessionPrep();

  try {
    updateSessionPrep('Loading course materials...');
    const courseMap = await loadCourseMap(state.courseId);
    updateSessionPrep('Fetching simulations & concepts...');
    await Promise.all([
      fetchSimulations(state.courseId),
      fetchConcepts(state.courseId),
    ]);

    updateSessionPrep('Checking your progress...');
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

    updateSessionPrep('Organizing your lesson plan...');
    showTeachingLayout(courseMap);

    // Reset ALL session state for fresh start
    state.messages = [];
    state.plan = [];
    state.currentPlan = {};
    state.planCallCount = 0;
    state.planActiveStep = null;
    state._pendingFirstHeadings = false;
    state.totalAssistantTurns = 0;
    state.responses = 0;
    state.lastVisualTurn = 0;
    state.visualAssetCount = 0;
    state.lastEngagementTurn = 0;
    state.accumulatedText = '';
    state.spotlightActive = false;
    state.spotlightInfo = null;
    state.spotlightHistory = [];
    state.activeSimulation = null;
    state.simulationLiveState = null;
    state.assessment = { active: false, sectionTitle: '', concepts: [], questionNumber: 0, maxQuestions: 5 };
    state.pendingSpotlightEvent = null;
    state.recentlyClosedSim = null;

    // Reset plan UI
    updateHeadingBar();

    // Clear board panel
    const boardContent = $('#spotlight-content');
    if (boardContent) boardContent.innerHTML = '';
    const frameStrip = $('#board-frame-strip');
    if (frameStrip) frameStrip.innerHTML = '';
    const resHistory = $('#resource-history-list');
    if (resHistory) resHistory.innerHTML = '';
    updateBoardEmptyState();

    // Generate session ID and create in MongoDB
    state.sessionId = generateId();
    state.currentScript = null;

    Router.navigate('/session/' + state.sessionId, { skipHandler: true });

    // Connect persistent SSE for agent events + plan polling
    connectAgentEvents();
    startPlanPolling();

    try {
      const coursePosition = {
        lessonId: state.checkpoint.currentLessonId,
        sectionIndex: state.checkpoint.currentSectionIndex,
        completedCourseSections: [...state.checkpoint.completedSections],
      };
      await SessionManager.createSession(
        state.courseId, state.studentName, state.studentIntent,
        coursePosition, state.checkpoint.sessionCount, scenario,
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

    // Build time context for natural greeting
    const now = new Date();
    const hour = now.getHours();
    const timeOfDay = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
    const dayName = now.toLocaleDateString('en-US', { weekday: 'long' });
    const timeCtx = `Current time: ${dayName} ${timeOfDay}.`;

    let trigger;
    if (state.studentIntent) {
      const progressNote = hasProgress
        ? ` They have completed ${completed} sections so far (session ${state.checkpoint.sessionCount}).`
        : '';
      trigger = `[SYSTEM] ${timeCtx} Student "${state.studentName}" has joined.${progressNote} The student said: "${state.studentIntent}".

OPENING INSTRUCTIONS:
- Greet warmly (1 short sentence, use their name, acknowledge what they want).
- Check your current MODE in the system prompt. If you see [CURRENT MODE: TRIAGE], follow those instructions first — quick diagnostic questions using the board, then call complete_triage when done. The planner will be spawned AFTER triage.
- If NOT in triage mode: A planning agent is running in the background. Start TEACHING with a board-draw immediately. Keep chat brief, the visual does the teaching.
- DO NOT give formal MCQs on the opening message.`;
    } else if (hasProgress) {
      trigger = `[SYSTEM] ${timeCtx} Returning student "${state.studentName}" — session ${state.checkpoint.sessionCount}. Completed ${completed} sections. Position: lesson ${state.checkpoint.currentLessonId}, section ${state.checkpoint.currentSectionIndex}. The student said: "${state.studentIntent}".

OPENING INSTRUCTIONS:
- Greet warmly using their name. Reference what you covered last time from [Student Notes].
- Check your current MODE. If [CURRENT MODE: TRIAGE]: run diagnostic first, call complete_triage when done.
- If NOT in triage: Start teaching with a visual. A planning agent is running in background.
- DO NOT mention lesson numbers or section numbers.`;
    } else {
      trigger = `[SYSTEM] ${timeCtx} New student "${state.studentName}" — first session. The student said: "${state.studentIntent}".

OPENING INSTRUCTIONS:
- Greet warmly using their name.
- Check your current MODE in the system prompt. If you see [CURRENT MODE: TRIAGE], follow those instructions — ask diagnostic questions, use the board, and call complete_triage when done. Do NOT start teaching content until triage is complete.
- If NOT in triage mode: Start teaching with a board-draw. The board should NOT be empty.
- DO NOT mention course structure, lessons, or sections. You're a tutor.`;
    }

    updateSessionPrep('Starting your session...');
    await streamADK(trigger, true, true);
  } catch (err) {
    hideSessionPrep();
    setStatus(`Failed: ${err.message}`, 'error');
    // Reset loading state so user can retry
    state._startingSession = false;
    const _startBtn = $('#btn-start-session');
    const _dashInput = $('#student-intent-first');
    if (_startBtn) { _startBtn.disabled = false; if (_startBtn.dataset.origHtml) _startBtn.innerHTML = _startBtn.dataset.origHtml; }
    if (_dashInput) _dashInput.disabled = false;
    document.querySelectorAll('.dash-chip').forEach(c => c.style.pointerEvents = '');
  }
}

window.continueSession = async function(sessionId) {
  // Block duplicate calls (double-click, etc.)
  if (state._resumingSession) return;
  state._resumingSession = true;

  // Show a loading state immediately — hide all screens
  _hideAllScreens();
  if (typeof DashBg !== 'undefined') DashBg.stop();
  // Show full-screen loading overlay while session loads
  if (!document.getElementById('session-resume-overlay')) {
    const overlay = document.createElement('div');
    overlay.id = 'session-resume-overlay';
    overlay.className = 'session-resume-overlay';
    overlay.innerHTML = `
      <div class="session-resume-card">
        <div class="session-resume-spinner"></div>
        <div class="session-resume-text">Restoring your session...</div>
        <div class="session-resume-sub">Loading conversation, boards, and progress</div>
      </div>
    `;
    document.getElementById('app').appendChild(overlay);
  }

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

    showTeachingLayout(courseMap, { skipBoardInit: true });

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
      // Assessment renders inline — no spotlight to reopen
    }
    if (sessionData.conceptNotes) {
      state.assessment.conceptNotes = sessionData.conceptNotes;
    }

    // Restore widget interaction state
    if (sessionData.widgetLiveState && Object.keys(sessionData.widgetLiveState).length > 0) {
      state.widget.liveState = sessionData.widgetLiveState;
    }

    // Restore active board-draw content
    if (sessionData.activeBoardDrawContent) {
      state.boardDraw.rawContent = sessionData.activeBoardDrawContent;
    }

    // Open the board for ANY session that used voice mode or had board content
    const transcript = sessionData.transcript || [];
    const isVoiceMode = sessionData.teachingMode === 'voice';
    const hasBoardContent = sessionData.activeBoardDrawContent ||
      transcript.some(m => m.role === 'assistant' && m.content && (
        m.content.includes('teaching-board-draw') ||
        m.content.includes('teaching-voice-scene') ||
        m.content.includes('<vb draw=')
      ));

    if (isVoiceMode || hasBoardContent) {
      const rawTitle = sessionData.headline || courseMap?.title || 'Session';
      const lastTitle = rawTitle.length > 40 ? rawTitle.slice(0, 40) + '...' : rawTitle;
      openBoardDrawSpotlight(lastTitle, null, { clear: true, skipReference: true });
      // Wait for BoardEngine.init — requestAnimationFrame + DOM layout + init
      // Poll until liveScene exists (max 500ms) instead of fixed timeout
      await new Promise(resolve => {
        let tries = 0;
        const check = () => {
          tries++;
          if ((typeof BoardEngine !== 'undefined' && BoardEngine.state?.liveScene) || tries > 25) {
            resolve();
          } else {
            setTimeout(check, 20);
          }
        };
        check();
      });
    }

    // Restore voice/video mode state
    if (sessionData.teachingMode) {
      state.teachingMode = sessionData.teachingMode;
    }
    if (sessionData.voiceSpeed) {
      state.voiceSpeed = sessionData.voiceSpeed;
    }
    // Video follow-along: hide plan sidebar
    if (state.teachingMode === 'video_follow') {
      state._videoWatchAlong = true;
      hidePlanSidebar();
    }

    // Save active spotlight info for restoration after canvas rebuild
    const savedSpotlight = sessionData.activeSpotlight || null;

    // Restore plan from session data — reuse handlePlanFromAgent logic
    if (sessionData.plan && sessionData.plan.raw) {
      const rawPlan = sessionData.plan.raw;
      state.currentPlan = rawPlan;

      // Build sections with nested topics (same structure as PLAN_UPDATE handler)
      if (rawPlan.sections && rawPlan.sections.length > 0) {
        state.plan = rawPlan.sections.map((sec, i) => ({
          n: sec.n || i + 1,
          title: sec.title || `Section ${i + 1}`,
          modality: sec.modality || '',
          covers: sec.covers || '',
          learningOutcome: sec.learning_outcome || '',
          studentLabel: sec.title || '',
          description: sec.activity || sec.covers || '',
          status: 'pending',
          performance: null,
          topics: (sec.topics || []).map((t, j) => ({
            t: t.t || j + 1,
            title: t.title || '',
            concept: t.concept || '',
            status: 'pending',
          })),
        }));
      } else {
        // Flat topics (older plan format)
        const topics = rawPlan._topics || rawPlan.topics || rawPlan.steps || [];
        if (topics.length > 0) {
          state.plan = [{
            n: 1,
            title: rawPlan.section_title || rawPlan.session_objective || 'Section',
            modality: '',
            covers: '',
            learningOutcome: rawPlan.learning_outcome || '',
            studentLabel: rawPlan.section_title || 'Section',
            description: rawPlan.learning_outcome || '',
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

      updateHeadingBar();
      updatePlanSidebar({ sections: state.plan });
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

    // Carry forward accumulated duration from previous visits
    state._accumulatedDuration = sessionData.durationSec || 0;
    state.sessionStartTime = Date.now();

    // Fade out and remove the loading overlay
    const resumeOverlay = document.getElementById('session-resume-overlay');
    if (resumeOverlay) {
      resumeOverlay.style.opacity = '0';
      setTimeout(() => resumeOverlay.remove(), 400);
    }

    const completed = state.checkpoint.completedSections.length;
    const now = new Date();
    const hour = now.getHours();
    const timeOfDay = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
    const dayName = now.toLocaleDateString('en-US', { weekday: 'long' });

    state._resumingSession = false;

    // Session is restored — board shows previous content, plan is loaded.
    // DO NOT auto-trigger a tutor response. Wait for the student to send a message.
    // This prevents: voice replay, duplicate content, tutor re-narrating what's on the board.
    // The student can type or speak to continue from where they left off.
    showStreamingIndicator();
    setTimeout(() => removeStreamingIndicator(), 500); // brief flash to show it's ready
  } catch (err) {
    state._resumingSession = false;
    const _overlay = document.getElementById('session-resume-overlay');
    if (_overlay) _overlay.remove();
    setStatus(`Failed to resume: ${err.message}`, 'error');
    Router.navigate('/home', { replace: true });
  }
};

// ── Canvas Rebuild (Session Resume) ──────────────────────────────

function rebuildCanvasFromTranscript(transcript) {
  const stream = document.getElementById('canvas-stream');
  // Keep the welcome header that showTeachingLayout already added

  // Prevent spotlights from opening during replay (only render ref cards)
  state.replayMode = true;
  // Tell board engine to skip animation delays during replay and clear cancel flag
  if (typeof BoardEngine !== 'undefined' && BoardEngine.state) {
    BoardEngine.state.replayMode = true;
    BoardEngine.state.cancelFlag = false;
  }
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
  if (typeof BoardEngine !== 'undefined' && BoardEngine.state) BoardEngine.state.replayMode = false;

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

  // Skip tags that should NEVER replay — plans, structural
  const skipTags = new Set([
    'teaching-plan', 'teaching-plan-update', 'teaching-checkpoint',
    'teaching-spotlight-dismiss', 'teaching-notebook-step', 'teaching-notebook-comment',
    'teaching-video',        // don't auto-play videos
    'teaching-simulation',   // don't restart simulations
  ]);

  if (skipTags.has(tag.name)) return;

  // Voice scenes: extract and render board-draw commands WITHOUT audio
  if (tag.name === 'teaching-voice-scene') {
    _replayVoiceSceneBoardOnly(tag);
    return;
  }

  // Render the tag using normal renderer (board-draw renders instantly in replayMode)
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

function _replayVoiceSceneBoardOnly(tag) {
  // Extract board-draw commands AND spoken text from voice scene — render instantly, skip audio
  const content = tag.content || tag.attrs?.content || '';
  if (!content) return;

  // Parse <vb> tags and extract draw + say attributes
  const vbRegex = /<vb\s+([\s\S]*?)\/>/g;
  let match;
  const commands = [];
  const spokenParts = [];
  while ((match = vbRegex.exec(content)) !== null) {
    const attrs = match[1];
    // Extract draw attribute
    const drawMatch = attrs.match(/draw='([^']+)'/) || attrs.match(/draw="([^"]+)"/);
    if (drawMatch) {
      try { commands.push(JSON.parse(drawMatch[1])); } catch (e) {}
    }
    // Extract spoken text (for rendering as board text on restore)
    const sayMatch = attrs.match(/say="([^"]*)"/) || attrs.match(/say='([^']*)'/);
    if (sayMatch && sayMatch[1].trim()) {
      spokenParts.push(sayMatch[1].trim());
    }
  }

  if (commands.length === 0 && spokenParts.length === 0) return;

  // Ensure board is open and snapshot previous scene if needed
  if (!state.boardDraw.active) {
    const title = tag.attrs?.title || 'Board';
    openBoardDrawSpotlight(title, null, { clear: true, skipReference: true });
  } else if (typeof BoardEngine !== 'undefined' && BoardEngine.snapshotScene) {
    BoardEngine.snapshotScene();
  }

  // Hide the empty state placeholder
  const emptyState = document.getElementById('board-empty-state');
  if (emptyState) emptyState.style.display = 'none';

  // Queue draw commands
  if (typeof BoardEngine !== 'undefined') {
    for (const cmd of commands) {
      BoardEngine.queueCommand(cmd);
    }
  }

  // Render spoken text as board text (since TTS won't replay on restore)
  if (spokenParts.length > 0) {
    const combined = spokenParts.join(' ');
    // Show as a condensed transcript below the board drawings
    const stream = document.getElementById('canvas-stream');
    if (stream) {
      const block = document.createElement('div');
      block.className = 'canvas-block board-text-block fade-in';
      block.dataset.type = 'ai';
      block.innerHTML = `<div class="board-text board-voice-transcript">${escapeHtml(combined)}</div>`;
      stream.appendChild(block);
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

// ── Session Prep Overlay ──────────────────────────────────────
let _prepMsgTimer = null;
const _prepMessages = [
  'Preparing your study session...',
  'Loading course materials...',
  'Fetching simulations & concepts...',
  'Checking your progress...',
  'Organizing your lesson plan...',
  'Starting your session...',
  'Almost ready...',
];

function showSessionPrep() {
  const overlay = $('#session-prep-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden', 'fade-out');
  const msg = $('#session-prep-msg');
  const sub = $('#session-prep-sub');
  if (msg) msg.textContent = 'Preparing your study session...';
  if (sub) sub.textContent = '';
}

function updateSessionPrep(text) {
  const msg = $('#session-prep-msg');
  const sub = $('#session-prep-sub');
  if (msg) {
    msg.style.animation = 'none';
    void msg.offsetWidth; // trigger reflow
    msg.style.animation = '';
    msg.textContent = text;
  }
  // Show a subtle sub-message
  const subs = [
    'This should only take a moment',
    'Setting things up for you',
    'Getting everything in order',
  ];
  if (sub && !sub.textContent) {
    sub.textContent = subs[Math.floor(Math.random() * subs.length)];
  }
}

function hideSessionPrep() {
  const overlay = $('#session-prep-overlay');
  if (!overlay || overlay.classList.contains('hidden')) return;
  overlay.classList.add('fade-out');
  setTimeout(() => overlay.classList.add('hidden'), 500);
  if (_prepMsgTimer) { clearInterval(_prepMsgTimer); _prepMsgTimer = null; }
}

function showTeachingLayout(courseMap, opts) {
  const skipBoardInit = opts?.skipBoardInit || false;
  document.title = courseMap.title + ' — Capacity';
  $('#course-title').textContent = courseMap.title;
  const sidebarLabel = $('#sidebar-section-label');
  if (sidebarLabel) sidebarLabel.textContent = 'SESSION';
  const sidebarStatus = $('#sidebar-status');
  if (sidebarStatus) sidebarStatus.textContent = state.studentName;

  _hideAllScreens();
  $('#teaching-layout').classList.remove('hidden');
  if (typeof DashBg !== 'undefined') DashBg.stop();

  // Show plan sidebar (will show "Building your plan..." until plan arrives)
  showPlanSidebar();
  // Hide video playlist (will show if video mode)
  _hideVideoPlaylist();

  // Apply teaching mode (text or voice) — locked for this session
  applyTeachingMode();

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

  // Initialize board with a welcome heading (skip for session restore — board will be rebuilt from transcript)
  if (!skipBoardInit) {
    setTimeout(() => {
      const sc = document.getElementById('spotlight-content');
      if (!sc) return;
      state.boardDraw.active = false;
      state.boardDraw.dismissed = false;
      state.boardDraw.complete = false;
      state.boardDraw.processedLines = 0;

      const intent = state.studentIntent || courseMap.title || 'Session';
      const title = intent.length > 40 ? intent.slice(0, 40) + '...' : intent;
      const cmds = [
        `{"cmd":"h1","text":"${title.replace(/"/g, '\\\\"')}"}`,
        `{"cmd":"gap","height":20}`,
      ];
      const fakeTag = `<teaching-board-draw title="${title.replace(/"/g, '&quot;')}">\n${cmds.join('\n')}\n</teaching-board-draw>`;
      bdProcessStreaming(fakeTag);
    }, 300);
  }
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
  const col = document.getElementById('chat-panel');
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
  const col = document.getElementById('chat-panel');
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
  white: '#e8e8e0', yellow: '#f5d97a', gold: '#fbbf24', green: '#7ed99a',
  blue: '#7eb8da', red: '#ff6b6b', cyan: '#53d8fb',
  dim: '#94a3b8',
};
const BD_VIRTUAL_W = 800;
const BD_INITIAL_H = 500;
function bdGetFontScale() {
  // Floor at 0.7 — prevents illegible text on small screens (400px → 8px body)
  return Math.max(state.boardDraw.scale, 0.7);
}

// ── Placement Engine ────────────────────────────────────────
// Resolves relative placement tags to x,y coordinates.
// The LLM outputs "center", "below", "row-start", "beside:id" etc.
// The engine tracks a cursor and resolves deterministically.

const BD_MARGIN = 25;
const BD_ROW_GAP = 12;
const BD_SIDE_GAP = 12;

const bdLayout = {
  cursorY: 12,
  inRow: false,
  rowY: 0,
  rowX: BD_MARGIN,
  rowH: 0,
  // Animation exclusion zones — prevent text from being placed behind animations
  animZones: [], // [{ y, h, x, w }] in virtual coords
};

function bdLayoutReset() {
  bdLayout.cursorY = 12;
  bdLayout.inRow = false;
  bdLayout.rowY = 0;
  bdLayout.rowX = BD_MARGIN;
  bdLayout.rowH = 0;
  bdLayout.animZones = [];
}

function bdLayoutEndRow() {
  if (bdLayout.inRow) {
    bdLayout.cursorY = bdLayout.rowY + bdLayout.rowH + BD_ROW_GAP;
    bdLayout.inRow = false;
    bdLayout.rowX = BD_MARGIN;
    bdLayout.rowH = 0;
  }
}

function bdLayoutResolve(placement, estW, estH) {
  const usable = BD_VIRTUAL_W - BD_MARGIN * 2;
  let x, y;

  if (!placement || placement === 'below') {
    if (bdLayout.inRow) bdLayoutEndRow();
    x = BD_MARGIN; y = bdLayout.cursorY;

  } else if (placement === 'center') {
    if (bdLayout.inRow) bdLayoutEndRow();
    x = BD_MARGIN + Math.max(0, (usable - estW) / 2);
    y = bdLayout.cursorY;

  } else if (placement === 'right') {
    if (bdLayout.inRow) bdLayoutEndRow();
    x = Math.max(BD_MARGIN, BD_VIRTUAL_W - BD_MARGIN - estW);
    y = bdLayout.cursorY;

  } else if (placement === 'full-width') {
    if (bdLayout.inRow) bdLayoutEndRow();
    x = BD_MARGIN; y = bdLayout.cursorY;

  } else if (placement === 'row-start') {
    if (bdLayout.inRow) bdLayoutEndRow();
    bdLayout.inRow = true;
    bdLayout.rowY = bdLayout.cursorY;
    bdLayout.rowX = BD_MARGIN;
    bdLayout.rowH = 0;
    x = BD_MARGIN; y = bdLayout.cursorY;

  } else if (placement === 'row-next') {
    if (!bdLayout.inRow) {
      bdLayout.inRow = true;
      bdLayout.rowY = bdLayout.cursorY;
      bdLayout.rowX = BD_MARGIN;
      bdLayout.rowH = 0;
    }
    // Auto-wrap: if element would exceed board width, start new row
    if (bdLayout.rowX + estW > BD_VIRTUAL_W - BD_MARGIN) {
      bdLayoutEndRow();
      bdLayout.inRow = true;
      bdLayout.rowY = bdLayout.cursorY;
      bdLayout.rowX = BD_MARGIN;
      bdLayout.rowH = 0;
    }
    x = bdLayout.rowX; y = bdLayout.rowY;

  } else if (placement === 'indent') {
    if (bdLayout.inRow) bdLayoutEndRow();
    x = BD_MARGIN + 20; y = bdLayout.cursorY;

  } else if (placement.startsWith('beside:')) {
    const refId = placement.split(':')[1];
    const ref = bdElementRegistry[refId];
    // Only use refs from current scene (scene index matches current snapshot count)
    if (ref && ref.scene === _sceneSnapshots.length) {
      x = ref.x + ref.w + BD_SIDE_GAP;
      y = ref.y;
      if (x + estW > BD_VIRTUAL_W - BD_MARGIN) {
        x = ref.x;
        y = ref.y + ref.h + 6;
      }
    } else {
      if (bdLayout.inRow) bdLayoutEndRow();
      x = BD_MARGIN; y = bdLayout.cursorY;
    }

  } else if (placement.startsWith('below:')) {
    const refId = placement.split(':')[1];
    const ref = bdElementRegistry[refId];
    if (ref && ref.scene === _sceneSnapshots.length) {
      x = ref.x;
      y = Math.max(ref.y + ref.h + 6, bdLayout.cursorY);
    } else {
      if (bdLayout.inRow) bdLayoutEndRow();
      x = BD_MARGIN; y = bdLayout.cursorY;
    }

  } else {
    if (bdLayout.inRow) bdLayoutEndRow();
    x = BD_MARGIN; y = bdLayout.cursorY;
  }

  // Clamp X to valid range
  x = Math.max(BD_MARGIN, Math.min(x, BD_VIRTUAL_W - BD_MARGIN - 20));
  // Ensure Y never goes negative
  y = Math.max(0, y);

  // Animation collision avoidance — if this element would overlap an animation zone,
  // push it below the animation. This prevents text from being hidden behind
  // opaque animation containers that live on a higher z-layer.
  for (const zone of bdLayout.animZones) {
    const overlapX = x < zone.x + zone.w && x + estW > zone.x;
    const overlapY = y < zone.y + zone.h && y + estH > zone.y;
    if (overlapX && overlapY) {
      // Push below the animation zone
      y = zone.y + zone.h + BD_ROW_GAP;
    }
  }

  return { x, y };
}

function bdLayoutCommit(x, y, w, h) {
  const bottom = y + h + BD_ROW_GAP;
  if (bdLayout.inRow) {
    // Only advance rowX for row-start/row-next (not below:id items stacked in a row)
    if (y === bdLayout.rowY) bdLayout.rowX = x + w + BD_SIDE_GAP;
    // Track full depth from row start — below:id items stack deeper
    const depthFromRowStart = (y - bdLayout.rowY) + h;
    bdLayout.rowH = Math.max(bdLayout.rowH, depthFromRowStart);
  } else {
    bdLayout.cursorY = bottom;
  }
  // Always keep cursorY at least at this element's bottom
  if (bottom > bdLayout.cursorY && !bdLayout.inRow) {
    bdLayout.cursorY = bottom;
  }
}

// Active p5 animation instances on the board overlay
const bdActiveAnimations = [];

// Element registry — tracks drawn elements by ID for referencing/scrolling
const bdElementRegistry = {}; // { id: { cmd, x, y, w, h } }

// Content bottom tracker — tracks the lowest Y coordinate of drawn content
// Used to auto-offset new voice scene beats below previous content
let bdContentBottomY = 0; // virtual coords

function bdUpdateContentBottom(y, h) {
  // Legacy function — kept for compatibility but bdContentBottomY
  // is now primarily synced from bdLayout.cursorY in bdRunCommand
  const bottom = (y || 0) + (h || 20);
  if (bottom > bdContentBottomY) bdContentBottomY = bottom;
}

function bdResetContentBottom() {
  bdContentBottomY = 0;
}

function bdRegisterElement(cmd) {
  if (!cmd || !cmd.id) return;
  const entry = { cmd: cmd.cmd, x: cmd.x || 0, y: cmd.y || 0 };
  const resolveSize = (s) => {
    if (typeof s === 'number') return s;
    if (typeof s === 'string' && BD_SEMANTIC_SIZES[s.toLowerCase()]) return BD_SEMANTIC_SIZES[s.toLowerCase()];
    return typeof s === 'string' ? (parseInt(s) || 16) : 16;
  };
  if (cmd.cmd === 'text' || cmd.cmd === 'latex') {
    const fontSize = resolveSize(cmd.size);
    const text = cmd.text || cmd.tex || '';
    // Measure width using canvas if available, else estimate
    const bd = state.boardDraw;
    if (bd.ctx) {
      bd.ctx.save();
      bd.ctx.font = `${fontSize}px Caveat, cursive`;
      entry.w = bd.ctx.measureText(text).width / (bd.DPR || 1) + 10;
      bd.ctx.restore();
    } else {
      entry.w = Math.min(text.length * fontSize * 0.65, 750);
    }
    entry.h = fontSize * 1.5;
  } else if (cmd.cmd === 'rect' || cmd.cmd === 'fillrect') {
    entry.w = cmd.w || 100; entry.h = cmd.h || 50;
  } else if (cmd.cmd === 'circle' || cmd.cmd === 'arc') {
    entry.x = (cmd.cx || 0) - (cmd.r || 30);
    entry.y = (cmd.cy || 0) - (cmd.r || 30);
    entry.w = (cmd.r || 30) * 2; entry.h = (cmd.r || 30) * 2;
  } else if (cmd.cmd === 'animation') {
    entry.w = cmd.w || 300; entry.h = cmd.h || 200;
  } else if (cmd.cmd === 'line' || cmd.cmd === 'arrow') {
    entry.x = cmd.x1 || 0; entry.y = cmd.y1 || 0;
    entry.w = Math.abs((cmd.x2||0) - (cmd.x1||0)) || 20;
    entry.h = Math.abs((cmd.y2||0) - (cmd.y1||0)) || 20;
  } else {
    entry.w = cmd.w || 80; entry.h = cmd.h || 30;
  }
  bdElementRegistry[cmd.id] = entry;
}

function bdControlAnimation(params) {
  // Send control params to the most recent active animation (via BoardEngine)
  const anims = BoardEngine.state.animations;
  if (!anims || anims.length === 0) return;
  const entry = anims[anims.length - 1];
  if (entry.instance && typeof entry.instance._onControl === 'function') {
    entry.instance._onControl(params);
  }
}

function bdZoomPulse_LEGACY(elementId) {
  const entry = bdElementRegistry[elementId];
  if (!entry) {
    console.warn('[Ref] Element not found in registry:', elementId, '— available:', Object.keys(bdElementRegistry).join(', '));
    return;
  }
  const bd = state.boardDraw;
  const s = bd.scale || 1;

  // Find the right container for the highlight
  let highlightParent;
  if (entry.scene !== undefined && entry.scene < _sceneSnapshots.length) {
    highlightParent = _sceneSnapshots[entry.scene]?.element?.querySelector('.bd-scene-highlight-overlay');
  }
  if (!highlightParent) {
    highlightParent = document.getElementById('bd-anim-layer');
  }
  if (!highlightParent) return;

  // Simple CSS ellipse highlight — no SVG clipping issues
  const pad = 10 * s;
  const elW = (entry.w || 80) * s;
  const elH = (entry.h || 25) * s;
  const left = entry.x * s - pad;
  const top = entry.y * s - pad;
  const w = elW + pad * 2;
  const h = elH + pad * 2;

  const ring = document.createElement('div');
  ring.style.cssText = `
    position:absolute; left:${left}px; top:${top}px;
    width:${w}px; height:${h}px;
    border: ${2*s}px solid rgba(251,191,36,0.45);
    border-radius: 50%;
    pointer-events:none; z-index:24;
    opacity:0;
    transition: opacity 0.4s ease-in;
  `;
  highlightParent.appendChild(ring);

  // Fade in
  requestAnimationFrame(() => { ring.style.opacity = '1'; });

  // Hold 3.5s, then fade out smoothly — gives student time to look
  setTimeout(() => {
    ring.style.transition = 'opacity 0.8s ease-out';
    ring.style.opacity = '0';
    setTimeout(() => ring.remove(), 850);
  }, 3500);

  // Scroll to element with margin above and below — show context
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap) return;

  let scrollTarget;
  if (entry.scene !== undefined && entry.scene < _sceneSnapshots.length) {
    const snapEl = _sceneSnapshots[entry.scene].element;
    if (snapEl) scrollTarget = snapEl.offsetTop + entry.y * s;
  } else {
    const scenesStack = document.getElementById('bd-scenes-stack');
    const stackH = scenesStack ? scenesStack.offsetHeight : 0;
    scrollTarget = stackH + entry.y * s;
  }

  if (scrollTarget !== undefined) {
    // Position so element is at ~35% from top — leaves margin above AND below
    const targetScroll = scrollTarget - wrap.clientHeight * 0.35;
    const viewTop = wrap.scrollTop;
    const viewBottom = viewTop + wrap.clientHeight;
    const elTop = scrollTarget;

    if (elTop < viewTop + 50 || elTop > viewBottom - 50) {
      wrap.scrollTo({ top: Math.max(0, targetScroll), behavior: 'smooth' });
    }
  }
}

function bdClearElementRegistry() {
  Object.keys(bdElementRegistry).forEach(k => delete bdElementRegistry[k]);
}

function bdScrollToElement_LEGACY(id) {
  const entry = bdElementRegistry[id];
  if (!entry) return;
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap) return;
  const bd = state.boardDraw;
  const zoom = bd._zoom || 1;
  const targetY = entry.y * bd.scale * zoom - 40;
  wrap.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });
}

function bdScrollToY(virtualY) {
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap) return;
  const bd = state.boardDraw;
  const zoom = bd._zoom || 1;
  const targetY = virtualY * bd.scale * zoom - 40;
  wrap.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });
}

function bdAutoScrollToCmd(cmd) {
  const wrap = document.getElementById('bd-canvas-wrap');
  const bd = state.boardDraw;
  if (!wrap) return;

  // Respect student's manual scroll — unless tutor is actively teaching
  const forceFollow = state._voiceSceneActive || state.isStreaming;
  if (!forceFollow && bd._studentScrolledRecently) return;

  const ys = [cmd.y, cmd.y1, cmd.y2, cmd.cy].filter(v => v != null);
  if (!ys.length) return;

  const minCmdY = Math.min(...ys);
  const maxCmdY = Math.max(...ys);
  const cmdH = cmd.h || (typeof cmd.size === 'number' ? cmd.size : null) || cmd.r || 30;
  const zoom = bd._zoom || 1;
  const s = bd.scale * zoom;

  // Calculate absolute scroll position including snapshot stack height
  const scenesStack = document.getElementById('bd-scenes-stack');
  const stackHeight = scenesStack ? scenesStack.offsetHeight : 0;

  const contentTop = stackHeight + minCmdY * s;
  const contentBottom = stackHeight + (maxCmdY + cmdH) * s;
  const viewTop = wrap.scrollTop;
  const viewBottom = viewTop + wrap.clientHeight;

  if (contentTop >= viewTop && contentBottom <= viewBottom) return;

  if (contentBottom > viewBottom) {
    wrap.scrollTo({ top: Math.max(0, contentBottom - wrap.clientHeight * 0.7), behavior: 'smooth' });
  } else if (contentTop < viewTop) {
    wrap.scrollTo({ top: Math.max(0, contentTop - 40), behavior: 'smooth' });
  }
}

// ── Board Zoom + Drag-to-Pan ──────────────────────────────────

function bdInitZoom() {
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap || wrap._bdZoomInit) return;
  wrap._bdZoomInit = true;
  const bd = state.boardDraw;

  function applyZoom() {
    const z = bd._zoom;
    // Single zoom wrapper — ALL content (snapshots + live) scales together
    const boardContent = document.getElementById('bd-board-content');
    if (boardContent) {
      boardContent.style.transformOrigin = 'top left';
      boardContent.style.transform = z === 1 ? '' : `scale(${z})`;
    }
    bdUpdateZoomSpacer();
    const label = document.getElementById('bd-zoom-level');
    if (label) label.textContent = Math.round(bd._zoom * 100) + '%';
  }

  // Pinch-to-zoom
  let lastPinchDist = 0;
  wrap.addEventListener('touchstart', e => { if (e.touches.length === 2) { lastPinchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY); } }, { passive: true });
  wrap.addEventListener('touchmove', e => { if (e.touches.length === 2) { const dist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY); if (lastPinchDist > 0) { const oldZ = bd._zoom; bd._zoom = Math.max(0.4, Math.min(4, bd._zoom * dist / lastPinchDist)); const rect = wrap.getBoundingClientRect(); const cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left + wrap.scrollLeft; const cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top + wrap.scrollTop; const r = bd._zoom / oldZ; wrap.scrollLeft = cx * r - (cx - wrap.scrollLeft); wrap.scrollTop = cy * r - (cy - wrap.scrollTop); applyZoom(); } lastPinchDist = dist; } }, { passive: true });
  wrap.addEventListener('touchend', () => { lastPinchDist = 0; }, { passive: true });

  // Ctrl+scroll zoom
  wrap.addEventListener('wheel', e => { if (e.ctrlKey || e.metaKey) { e.preventDefault(); const oldZ = bd._zoom; bd._zoom = Math.max(0.4, Math.min(4, oldZ * (1 - e.deltaY * 0.003))); const rect = wrap.getBoundingClientRect(); const cx = e.clientX - rect.left + wrap.scrollLeft; const cy = e.clientY - rect.top + wrap.scrollTop; const r = bd._zoom / oldZ; wrap.scrollLeft = cx * r - (e.clientX - rect.left); wrap.scrollTop = cy * r - (e.clientY - rect.top); applyZoom(); } }, { passive: false });

  // Drag to pan (Space+drag or middle-click)
  let isPanning = false, panSX = 0, panSY = 0, panSSX = 0, panSSY = 0, spaceHeld = false;
  document.addEventListener('keydown', e => { if (e.code === 'Space' && !spaceHeld && bd.canvas && !['INPUT','TEXTAREA'].includes(document.activeElement?.tagName) && !bd.studentDrawing) { spaceHeld = true; wrap.style.cursor = 'grab'; } });
  document.addEventListener('keyup', e => { if (e.code === 'Space') { spaceHeld = false; if (!isPanning) wrap.style.cursor = ''; } });
  wrap.addEventListener('mousedown', e => { if (e.button === 1 || (spaceHeld && e.button === 0)) { e.preventDefault(); isPanning = true; panSX = e.clientX; panSY = e.clientY; panSSX = wrap.scrollLeft; panSSY = wrap.scrollTop; wrap.style.cursor = 'grabbing'; } });
  window.addEventListener('mousemove', e => { if (isPanning) { wrap.scrollLeft = panSSX - (e.clientX - panSX); wrap.scrollTop = panSSY - (e.clientY - panSY); } });
  window.addEventListener('mouseup', () => { if (isPanning) { isPanning = false; wrap.style.cursor = spaceHeld ? 'grab' : ''; } });

  // Keyboard zoom
  document.addEventListener('keydown', e => { if (!bd.canvas) return; const rect = wrap.getBoundingClientRect(); const cx = rect.width/2+wrap.scrollLeft, cy = rect.height/2+wrap.scrollTop; if ((e.ctrlKey||e.metaKey) && (e.key==='='||e.key==='+')) { e.preventDefault(); const oldZ=bd._zoom; bd._zoom=Math.min(4,bd._zoom*1.2); const r=bd._zoom/oldZ; wrap.scrollLeft=cx*r-rect.width/2; wrap.scrollTop=cy*r-rect.height/2; applyZoom(); } else if ((e.ctrlKey||e.metaKey) && e.key==='-') { e.preventDefault(); const oldZ=bd._zoom; bd._zoom=Math.max(0.4,bd._zoom/1.2); const r=bd._zoom/oldZ; wrap.scrollLeft=cx*r-rect.width/2; wrap.scrollTop=cy*r-rect.height/2; applyZoom(); } else if ((e.ctrlKey||e.metaKey) && e.key==='0') { e.preventDefault(); bd._zoom=1; wrap.scrollLeft=0; applyZoom(); } });

  // Toolbar buttons
  window.bdZoomIn = () => { const oldZ=bd._zoom; bd._zoom=Math.min(4,bd._zoom*1.25); const rect=wrap.getBoundingClientRect(); const cx=rect.width/2+wrap.scrollLeft,cy=rect.height/2+wrap.scrollTop; const r=bd._zoom/oldZ; wrap.scrollLeft=cx*r-rect.width/2; wrap.scrollTop=cy*r-rect.height/2; applyZoom(); };
  window.bdZoomOut = () => { const oldZ=bd._zoom; bd._zoom=Math.max(0.4,bd._zoom/1.25); const rect=wrap.getBoundingClientRect(); const cx=rect.width/2+wrap.scrollLeft,cy=rect.height/2+wrap.scrollTop; const r=bd._zoom/oldZ; wrap.scrollLeft=cx*r-rect.width/2; wrap.scrollTop=cy*r-rect.height/2; applyZoom(); };
  window.bdZoomReset = () => { bd._zoom=1; wrap.scrollLeft=0; applyZoom(); };
}

function bdInit(canvasEl, voiceEl) {
  hideBoardLoadingSkeleton();
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
  bd._studentScrolledRecently = false;
  bd._zoom = 1;
  bdResizeCanvas();
  bdDrawGrid();
  bdInitStudentDrawing(canvasEl);
  bdInitToolbar();
  bdInitScrollDetection();
  bdInitZoom();
  // Start processing commands that were queued during streaming
  if (bd.commandQueue.length > 0 && !bd.isProcessing) {
    bdProcessQueue();
  }
}

function bdInitScrollDetection() {
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap || wrap._bdScrollListenerAttached) return;
  wrap._bdScrollListenerAttached = true;
  let scrollTimer = null;
  let lastProgrammaticScroll = 0;
  const origScrollBy = wrap.scrollBy.bind(wrap);
  const origScrollTo = wrap.scrollTo.bind(wrap);
  wrap.scrollBy = function(...args) {
    lastProgrammaticScroll = Date.now();
    return origScrollBy(...args);
  };
  wrap.scrollTo = function(...args) {
    lastProgrammaticScroll = Date.now();
    return origScrollTo(...args);
  };
  wrap.addEventListener('scroll', () => {
    // Update animation visibility on scroll (pause off-screen, resume visible)
    _onBoardScroll();

    if (Date.now() - lastProgrammaticScroll < 800) return;
    state.boardDraw._studentScrolledRecently = true;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      state.boardDraw._studentScrolledRecently = false;
    }, 1500);
  }, { passive: true });
}

function bdInitToolbar() {
  const toolbar = document.getElementById('bd-toolbar');
  if (!toolbar) return;
  const bd = state.boardDraw;
  bd.drawingEnabled = false;  // Drawing OFF by default

  toolbar.querySelectorAll('.bd-tool-btn[data-color]').forEach(btn => {
    btn.addEventListener('click', () => {
      const wasActive = btn.classList.contains('active');
      toolbar.querySelectorAll('.bd-tool-btn[data-color]').forEach(b => b.classList.remove('active'));

      const studentCanvas = document.getElementById('bd-student-canvas');
      if (wasActive) {
        // Toggle off — disable drawing
        bd.drawingEnabled = false;
        document.getElementById('bd-canvas-wrap')?.style.setProperty('cursor', 'default');
        if (studentCanvas) studentCanvas.style.pointerEvents = 'none';
      } else {
        // Toggle on — enable drawing with this color
        btn.classList.add('active');
        bd.drawingEnabled = true;
        document.getElementById('bd-canvas-wrap')?.style.setProperty('cursor', 'crosshair');
        if (studentCanvas) studentCanvas.style.pointerEvents = 'auto';
        const color = btn.dataset.color;
        if (color === 'eraser') {
          bd.studentColor = '#1a1d2e';
          bd.studentStrokeW = 12;
        } else {
          bd.studentColor = color;
          bd.studentStrokeW = 2.5;
        }
      }
    });
  });
}

function bdInitStudentDrawing(canvasEl) {
  const bd = state.boardDraw;
  let drawing = false;
  let lastX = 0, lastY = 0;

  // Find the drawing context — use bd.ctx if available, else get from the canvas directly
  function getCtx() {
    if (bd.ctx) return bd.ctx;
    return canvasEl.getContext('2d');
  }

  function getPos(e) {
    const rect = canvasEl.getBoundingClientRect();
    // Account for CSS scaling and DPR
    const dpr = bd.DPR || (window.devicePixelRatio || 1);
    const scaleX = canvasEl.width / rect.width;
    const scaleY = canvasEl.height / rect.height;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    // Also account for scroll position of the canvas wrapper
    const wrap = canvasEl.closest('#bd-canvas-wrap') || canvasEl.parentElement;
    const scrollTop = wrap ? wrap.scrollTop : 0;
    return {
      x: (clientX - rect.left) * scaleX,
      y: (clientY - rect.top + scrollTop) * scaleY
    };
  }

  function startDraw(e) {
    if (!bd.drawingEnabled) return;
    e.preventDefault();
    e.stopPropagation();
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
    const ctx = getCtx();
    if (!ctx) return;
    ctx.save();
    ctx.strokeStyle = bd.studentColor;
    ctx.lineWidth = bd.studentStrokeW * (bd.DPR || 1);
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
  const containerH = wrap.clientHeight;
  const scaledH = bd.currentH * bd.scale;
  const actualH = Math.max(scaledH, containerH);

  const bitmapW = Math.round(actualW * bd.DPR);
  const bitmapH = Math.round(actualH * bd.DPR);
  const needsBitmapResize = bd.canvas.width !== bitmapW || bd.canvas.height !== bitmapH;

  if (needsBitmapResize && !bd._resizeCSSOnly) {
    // Use drawImage (GPU-accelerated) instead of getImageData/putImageData (CPU, O(n²))
    let oldCanvas = null;
    if (bd.canvas.width > 0 && bd.canvas.height > 0) {
      oldCanvas = document.createElement('canvas');
      oldCanvas.width = bd.canvas.width;
      oldCanvas.height = bd.canvas.height;
      oldCanvas.getContext('2d').drawImage(bd.canvas, 0, 0);
    }
    bd.canvas.width = bitmapW;
    bd.canvas.height = bitmapH;
    bd.ctx = bd.canvas.getContext('2d', { willReadFrequently: true });
    bd.ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
    bd.ctx.fillStyle = '#1a1d2e';
    bd.ctx.fillRect(0, 0, actualW, actualH);
    if (oldCanvas) {
      bd.ctx.save();
      bd.ctx.setTransform(1, 0, 0, 1, 0, 0);
      bd.ctx.drawImage(oldCanvas, 0, 0); // GPU-accelerated copy
      bd.ctx.restore();
      oldCanvas = null; // free memory
    }
  }

  bd.canvas.style.width = actualW + 'px';
  bd.canvas.style.height = actualH + 'px';
  bdSyncAnimLayer();
}

// Window resize — DOM board handles layout automatically via CSS flow.
// No canvas resize or animation repositioning needed.
window.addEventListener('resize', () => {
  // Nothing to do — DOM engine handles responsive layout via CSS
});

function bdExpandIfNeeded(maxY) {
  const bd = state.boardDraw;
  if (maxY > bd.currentH - 60) {
    bd.currentH = maxY + 200;
    bdResizeCanvas();
    bdDrawGrid();
    bdUpdateZoomSpacer();
  }
}

function bdUpdateZoomSpacer() {
  const bd = state.boardDraw;
  const wrap = document.getElementById('bd-canvas-wrap');
  const content = document.getElementById('bd-board-content');
  if (!wrap || !content) return;
  const z = bd._zoom || 1;
  // Content dimensions come from the single wrapper
  const totalH = content.scrollHeight;
  const totalW = content.scrollWidth || wrap.clientWidth;
  let spacer = wrap.querySelector('.bd-zoom-spacer');
  if (z <= 1) {
    // No spacer needed at 100% or below
    if (spacer) spacer.style.cssText = 'display:none';
    return;
  }
  if (!spacer) { spacer = document.createElement('div'); spacer.className = 'bd-zoom-spacer'; spacer.style.cssText = 'pointer-events:none;visibility:hidden;'; wrap.appendChild(spacer); }
  spacer.style.display = 'block';
  spacer.style.width = Math.round(totalW * z) + 'px';
  spacer.style.height = Math.round(totalH * z) + 'px';
}

function bdSyncAnimLayer() {
  const layer = document.getElementById('bd-anim-layer');
  const canvas = document.getElementById('bd-canvas');
  if (layer && canvas) {
    layer.style.height = canvas.style.height || (canvas.clientHeight + 'px');
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

// Semantic size mapping — LLM can use "h1", "h2", "text", "small", "label" or numbers
const BD_SEMANTIC_SIZES = { h1: 26, h2: 21, h3: 18, text: 16, body: 16, small: 13, label: 12, caption: 10 };

function bdResolveSize(size) {
  if (typeof size === 'string' && BD_SEMANTIC_SIZES[size.toLowerCase()]) {
    return BD_SEMANTIC_SIZES[size.toLowerCase()];
  }
  return typeof size === 'number' ? size : 14;
}

async function bdAnimText(text, x, y, color, size, charDelay) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return 0;
  const s = bd.scale;
  size = bdResolveSize(size);
  const fontScale = bdGetFontScale();
  const fs = size * fontScale;
  const lineH = size * 1.4;
  const maxX = (BD_VIRTUAL_W - BD_MARGIN) * s; // right boundary in CSS px
  bdExpandIfNeeded(y + size);
  // Adaptive char delay — faster when CPU is constrained (many animations or late in session)
  const animLoad = bdActiveAnimations.length;
  const queueLen = bd.commandQueue?.length || 0;
  let linesRendered = 1;
  if (queueLen > 5 || animLoad > 4) {
    // Queue backed up or too many animations — instant text (no animation)
    bdChalkStyle(color, 1);
    bd.ctx.font = `${fs}px 'Caveat', cursive`;
    bd.ctx.textBaseline = 'middle';
    // Word-wrap: split into lines that fit within board width
    const words = text.split(' ');
    let line = '';
    let curY = y;
    for (const word of words) {
      const testLine = line ? line + ' ' + word : word;
      const testW = bd.ctx.measureText(testLine).width;
      if (line && (x * s + testW) > maxX) {
        bd.ctx.fillText(line, x * s, curY * s);
        line = word;
        curY += lineH;
        linesRendered++;
        bdExpandIfNeeded(curY + size);
      } else {
        line = testLine;
      }
    }
    if (line) bd.ctx.fillText(line, x * s, curY * s);
    bdClearShadow();
    return linesRendered;
  }
  charDelay = charDelay || (animLoad > 2 ? 15 : animLoad > 0 ? 25 : 35);
  bdChalkStyle(color, 1);
  bd.ctx.font = `${fs}px 'Caveat', cursive`;
  bd.ctx.textBaseline = 'middle';
  let cx = x * s;
  let curY = y;
  for (let i = 0; i < text.length; i++) {
    if (bd.cancelFlag) return linesRendered;
    const charW = bd.ctx.measureText(text[i]).width;
    // Wrap at word boundary (space) or hard-wrap if single word exceeds width
    if (cx + charW > maxX && text[i] === ' ') {
      cx = x * s;
      curY += lineH;
      linesRendered++;
      bdExpandIfNeeded(curY + size);
      continue; // skip the space at line break
    }
    bd.ctx.fillText(text[i], cx, curY * s);
    cx += charW;
    await bdSleep(charDelay);
  }
  bdClearShadow();
  return linesRendered;
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
  // \frac{a}{b} and \dfrac{a}{b} → a/b (clean, no parens for short fracs)
  s = s.replace(/\\d?frac\{([^}]*)\}\{([^}]*)\}/g, (_, num, den) => {
    // Short numerator/denominator (single symbol) → no parens
    const n = num.trim(), d = den.trim();
    if (n.length <= 3 && d.length <= 3) return n + '/' + d;
    return '(' + n + ')/(' + d + ')';
  });
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
  size = bdResolveSize(size || 16);
  const fontScale = bdGetFontScale();
  const fs = size * fontScale;
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
  const fontScale = bdGetFontScale();
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
  // Default to semi-transparent to avoid covering content behind
  const opacity = cmd.opacity || 0.15;
  bd.ctx.globalAlpha = opacity;
  bd.ctx.fillStyle = c;
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
  bdClearElementRegistry();
  bdResetContentBottom();
  bdLayoutReset();
  state._voiceSceneYOffset = 0;
  bd._studentScrolledRecently = false;
  bdClearAllAnimations();
  // Clear scene snapshots — prevents memory leak and stale scene index references
  _sceneSnapshots.length = 0;
  const scenesStack = document.getElementById('bd-scenes-stack');
  if (scenesStack) scenesStack.innerHTML = '';
  bdResizeCanvas();
  bd.ctx.fillStyle = '#1a1d2e';
  bd.ctx.fillRect(0, 0, BD_VIRTUAL_W * bd.scale, bd.currentH * bd.scale);
  bdDrawGrid();
  bdHideVoice();
  // Reset scroll to top so the fresh board starts visible from the top
  const wrap = document.getElementById('bd-canvas-wrap');
  if (wrap) wrap.scrollTop = 0;
}

async function bdRunCommand(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag || !bd.canvas || !bd.ctx) return;

  // ── Placement engine: ALL commands go through the layout resolver ──
  // If no placement specified, default to "below" (sequential flow)
  {
    // Content commands get auto-placement. Decorative shapes (circle, line, arrow) DON'T —
    // they're drawn at the current cursor position but don't advance it.
    const contentCmds = ['text', 'latex', 'animation', 'equation', 'compare', 'step', 'check', 'cross', 'callout', 'list', 'divider', 'result'];
    if (!cmd.placement && contentCmds.includes(cmd.cmd)) {
      cmd.placement = 'below';
    }

    if (cmd.placement) {
      const resolveH = (s) => {
        if (typeof s === 'number') return s * 1.4;
        if (typeof s === 'string' && BD_SEMANTIC_SIZES[s.toLowerCase()]) return BD_SEMANTIC_SIZES[s.toLowerCase()] * 1.4;
        return 22;
      };

      // Estimate dimensions based on command type
      let estW, estH;
      if (cmd.cmd === 'text' || cmd.cmd === 'latex') {
        const charW = bdResolveSize(cmd.size) * 0.55;
        const textPixelW = cmd.text ? (cmd.text.length || 10) * charW : 300;
        const usableTextW = BD_VIRTUAL_W - BD_MARGIN * 2;
        estW = cmd.w || Math.min(textPixelW, usableTextW);
        // Estimate wrapped lines: if text exceeds usable width, it wraps
        const estLines = Math.max(1, Math.ceil(textPixelW / usableTextW));
        estH = cmd.h || (resolveH(cmd.size) * estLines);
      } else if (cmd.cmd === 'animation') {
        // Engine owns sizing — AI w/h ignored. Size derived from layout context.
        const availVW = bdLayout.inRow ? BD_VIRTUAL_W - bdLayout.rowX - BD_MARGIN : BD_VIRTUAL_W - BD_MARGIN * 2;
        const isRow = bdLayout.inRow || (cmd.placement && cmd.placement === 'row-start');
        if (isRow) {
          // Leave enough room for legend beside animation (at least 40% for text)
          estW = Math.min(Math.round(availVW * 0.42), 320);
        } else {
          estW = Math.min(Math.round(availVW * 0.55), 420);
        }
        // Match renderer caps: min 150/s, max boardH*0.55/s (use conservative estimate)
        const animMinH = Math.ceil(150 / Math.max(bd.scale || 1, 0.7));
        estH = Math.max(Math.min(Math.round(estW * 0.6), 250), animMinH);
        cmd._layoutW = estW;
        cmd._layoutH = estH;
      } else if (cmd.cmd === 'circle' || cmd.cmd === 'arc') {
        const r = Math.min(cmd.r || 30, 40); // cap radius at 40 virtual px
        estW = r * 2; estH = r * 2;
      } else if (cmd.cmd === 'line' || cmd.cmd === 'arrow' || cmd.cmd === 'dashed' || cmd.cmd === 'curvedarrow') {
        estW = Math.min(Math.abs((cmd.x2 || 0) - (cmd.x1 || 0)) || 40, 200);
        estH = Math.min(Math.abs((cmd.y2 || 0) - (cmd.y1 || 0)) || 15, 50);
      } else if (cmd.cmd === 'equation') {
        estW = BD_VIRTUAL_W - BD_MARGIN * 2;
        // Match renderer: size*1.4 without note, size*1.4 + noteSize*1.4 + 4 with note below
        const eqSize = bdResolveSize(cmd.size || 'text');
        estH = cmd.note ? eqSize * 1.4 + bdResolveSize('small') * 1.4 + 4 : eqSize * 1.4;
      } else if (cmd.cmd === 'compare') {
        const itemCount = Math.max((cmd.left?.items?.length || 0), (cmd.right?.items?.length || 0));
        estW = BD_VIRTUAL_W - BD_MARGIN * 2;
        estH = 30 + itemCount * 22;
      } else if (cmd.cmd === 'step' || cmd.cmd === 'check' || cmd.cmd === 'cross') {
        estW = 400; estH = 24;
      } else if (cmd.cmd === 'callout') {
        // Estimate wrapping: rough chars-per-line based on available width
        const calloutSize = bdResolveSize(cmd.size || 'text');
        const calloutCharsPerLine = Math.floor((BD_VIRTUAL_W - BD_MARGIN * 2 - 12) / (calloutSize * 0.55));
        const calloutLines = Math.max(1, Math.ceil((cmd.text?.length || 20) / calloutCharsPerLine));
        estW = 500; estH = calloutLines * calloutSize * 1.4 + 8;
      } else if (cmd.cmd === 'list') {
        // Renderer advances curY by itemSpacing(22) for each item, totalH = items * 22
        estW = 400; estH = (cmd.items?.length || 1) * 22;
      } else if (cmd.cmd === 'divider') {
        estW = BD_VIRTUAL_W - BD_MARGIN * 2; estH = 18;
      } else if (cmd.cmd === 'result') {
        estW = BD_VIRTUAL_W - BD_MARGIN * 2;
        estH = bdResolveSize(cmd.size || 'text') * 1.6 + 20;
      } else {
        estW = cmd.w || 100; estH = cmd.h || 30;
      }

      const { x, y } = bdLayoutResolve(cmd.placement, estW, estH);

      // Commit to layout in LOCAL coords — layout engine never sees yOffset
      bdLayoutCommit(x, y, estW, estH);

      // Track animation exclusion zones — text must not be placed behind these
      if (cmd.cmd === 'animation') {
        bdLayout.animZones.push({ x, y, w: estW, h: estH });
      }

      // Register element in LOCAL coords for beside:/below: refs + scene index for highlights
      if (cmd.id) {
        bdElementRegistry[cmd.id] = { x, y, w: estW, h: estH, cmd: cmd.cmd, scene: _sceneSnapshots.length };
      }

      // Apply yOffset ONCE for rendering — this is the ONLY place it's added
      const yOffset = state._voiceSceneYOffset || 0;
      cmd.x = x;
      cmd.y = y + yOffset;

      // contentBottomY synced AFTER command executes (see below switch block)
      cmd._yOffset = yOffset; // store for post-render sync
    }
  }

  // Enforce minimum left margin
  if (cmd.x !== undefined && cmd.x < 15) cmd.x = 15;
  if (cmd.x1 !== undefined && cmd.x1 < 10) cmd.x1 = 10;

  // contentBottomY sync handled inside placement resolver above

  // Element registration handled by placement resolver above (in LOCAL coords)
  // Only register non-placement commands here (decorative shapes)
  if (cmd.id && !cmd.placement) {
    bdRegisterElement(cmd);
  }
  // Hand cursor disabled — was causing positioning issues
  // if (typeof voiceHandFollowCommand === 'function') voiceHandFollowCommand(cmd);
  // Auto-scroll to keep new content visible
  bdAutoScrollToCmd(cmd);

  // Skip ALL raw shape commands — they use LLM's absolute coords which create
  // diagonal line artifacts and gaps. The tutor should use compound commands
  // (compare, equation, callout, etc.) for all visual structure.
  const skipShapes = ['line', 'arrow', 'rect', 'circle', 'arc', 'freehand', 'dashed', 'dot', 'curvedarrow', 'fillrect', 'brace', 'matrix'];
  if (skipShapes.includes(cmd.cmd)) {
    console.log(`[Skip] Blocked shape: ${cmd.cmd} at (${cmd.x1||cmd.cx||cmd.x},${cmd.y1||cmd.cy||cmd.y})`);
    return;
  }

  switch (cmd.cmd) {
    case 'line': await bdAnimLine(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.color, cmd.w, cmd.dur); break;
    case 'arrow': await bdAnimArrow(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.color, cmd.w, cmd.dur); break;
    case 'rect': await bdAnimRect(cmd.x, cmd.y, cmd.w, cmd.h, cmd.color, cmd.lw); break;
    case 'circle': await bdAnimCircle(cmd.cx, cmd.cy, cmd.r, cmd.color, cmd.lw, cmd.dur); break;
    case 'arc': await bdAnimArc(cmd.cx, cmd.cy, cmd.r, cmd.sa, cmd.ea, cmd.color, cmd.lw, cmd.dur); break;
    case 'text': {
      const lines = await bdAnimText(cmd.text, cmd.x, cmd.y, cmd.color, cmd.size, cmd.charDelay);
      // Correct cursor if text wrapped to multiple lines (estimator assumes single line)
      if (lines > 1 && cmd._yOffset !== undefined) {
        const size = bdResolveSize(cmd.size);
        const actualH = lines * size * 1.4;
        _correctCursor(cmd.y, actualH);
      }
      break;
    }
    case 'latex': await bdAnimLatex(cmd.tex, cmd.x, cmd.y, cmd.color, cmd.size); break;
    case 'freehand': await bdAnimFreehand(cmd.pts, cmd.color, cmd.w, cmd.dur); break;
    case 'dashed': await bdAnimDashed(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.color, cmd.w); break;
    case 'dot': bdDrawDot(cmd.x, cmd.y, cmd.r, cmd.color); break;
    case 'matrix': await bdAnimMatrix(cmd); break;
    case 'brace': await bdAnimBrace(cmd); break;
    case 'fillrect': await bdAnimFillRect(cmd); break;
    case 'curvedarrow': await bdAnimCurvedArrow(cmd); break;
    case 'animation': await bdRunAnimation(cmd); break;
    case 'voice':
      bdShowVoice(cmd.text);
      if (cmd.dur) { await bdSleep(cmd.dur); bdHideVoice(); }
      break;
    case 'pause': await bdSleep(cmd.ms || 500); break;
    case 'clear': bdClearBoard(); break;

    // ── Compound commands — expand into primitives ──

    case 'equation': await bdCompoundEquation(cmd); break;
    case 'compare': await bdCompoundCompare(cmd); break;
    case 'step': await bdCompoundStep(cmd); break;
    case 'check': await bdCompoundCheckCross(cmd, true); break;
    case 'cross': await bdCompoundCheckCross(cmd, false); break;
    case 'callout': await bdCompoundCallout(cmd); break;
    case 'list': await bdCompoundList(cmd); break;
    case 'divider': await bdCompoundDivider(cmd); break;
    case 'result': await bdCompoundResult(cmd); break;

    // ── Board editing commands — modify existing content ──
    case 'strikeout': bdStrikeoutElement(cmd); break;
    case 'update': await bdUpdateElement(cmd); break;
    case 'delete': bdDeleteElement(cmd); break;
    case 'clone': await bdCloneElement(cmd); break;
  }

  // Sync contentBottomY AFTER render (compound commands may have corrected cursor)
  if (cmd._yOffset !== undefined) {
    const absBottom = bdLayout.cursorY + cmd._yOffset;
    if (absBottom > bdContentBottomY) bdContentBottomY = absBottom;
  }
}

// ═══ Compound Command Renderers ═══
// Each decomposes a single semantic command into multiple canvas draws.
// cmd.x/cmd.y are ABSOLUTE (yOffset applied). Use _localY() for cursor math.

function _localY(absY) {
  return absY - (state._voiceSceneYOffset || 0);
}

function _correctCursor(absY, height) {
  const localBottom = _localY(absY) + height + BD_ROW_GAP;
  if (localBottom > bdLayout.cursorY) bdLayout.cursorY = localBottom;
}

function _registerElement(id, x, absY, w, h) {
  if (id) bdElementRegistry[id] = { x, y: _localY(absY), w, h, scene: _sceneSnapshots.length };
}
// They use the CURRENT layout cursor position (cmd.x, cmd.y already resolved).

async function bdCompoundEquation(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const size = bdResolveSize(cmd.size || 'text');
  const fontScale = bdGetFontScale();
  const fs = size * fontScale;
  const x = cmd.x, y = cmd.y;
  const color = cmd.color || 'cyan';

  bdExpandIfNeeded(y + size + 10);
  await bdAnimText(cmd.text, x, y, color, cmd.size || 'text', cmd.charDelay);

  let eqTotalH = size * 1.4;
  if (cmd.note) {
    const eqWidth = bd.ctx.measureText(cmd.text).width / s + 15;
    const noteX = x + eqWidth + BD_SIDE_GAP;
    const noteY = y + 2;
    const noteSize = bdResolveSize('small');
    if (noteX + 100 < BD_VIRTUAL_W - BD_MARGIN) {
      bdExpandIfNeeded(noteY + noteSize);
      await bdAnimText('← ' + cmd.note, noteX, noteY, 'dim', 'small', 25);
      _registerElement(cmd.id, x, y, eqWidth + BD_SIDE_GAP + 150, size * 1.4);
    } else {
      const belowY = y + size * 1.4 + 4;
      bdExpandIfNeeded(belowY + noteSize);
      await bdAnimText(cmd.note, x + 10, belowY, 'dim', 'small', 25);
      eqTotalH = size * 1.4 + noteSize * 1.4 + 4;
    }
  }
  _correctCursor(y, eqTotalH);
}

async function bdCompoundCompare(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const x = cmd.x, y = cmd.y;
  const left = cmd.left || {}; const right = cmd.right || {};
  const colW = (BD_VIRTUAL_W - BD_MARGIN * 2 - 30) / 2;
  const leftX = x; const rightX = x + colW + 30;
  const leftColor = left.color || 'green';
  const rightColor = right.color || 'red';
  let curY = y;

  // Headers
  if (left.title) {
    bdExpandIfNeeded(curY + 20);
    await bdAnimText(left.title, leftX, curY, leftColor, 'h2', 30);
  }
  if (right.title) {
    bdExpandIfNeeded(curY + 20);
    await bdAnimText(right.title, rightX, curY, rightColor, 'h2', 30);
  }
  curY += 30;

  const s = bd.scale;
  const sepX = x + colW + 15;
  const sepStartY = curY - 5;

  const leftItems = left.items || []; const rightItems = right.items || [];
  const maxItems = Math.max(leftItems.length, rightItems.length);
  const itemSpacing = 22;

  // Draw items row by row
  for (let i = 0; i < maxItems; i++) {
    if (bd.cancelFlag) return;
    bdExpandIfNeeded(curY + 16);
    if (i < leftItems.length) {
      const marker = left.check ? '✓ ' : '• ';
      await bdAnimText(marker + leftItems[i], leftX + 5, curY, leftColor, 'text', 25);
    }
    if (i < rightItems.length) {
      const marker = right.check === false ? '✗ ' : '• ';
      await bdAnimText(marker + rightItems[i], rightX + 5, curY, rightColor, 'text', 25);
    }
    curY += itemSpacing;
  }

  // Draw separator line AFTER all text (fresh path — text draws break context path)
  bd.ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  bd.ctx.lineWidth = 1;
  bd.ctx.beginPath();
  bd.ctx.moveTo(sepX * s, sepStartY * s);
  bd.ctx.lineTo(sepX * s, (curY - 5) * s);
  bd.ctx.stroke();

  const totalH = curY - y;
  _registerElement(cmd.id, x, y, BD_VIRTUAL_W - BD_MARGIN * 2, totalH);
  _correctCursor(y, totalH);
}

async function bdCompoundStep(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const x = cmd.x, y = cmd.y;
  const n = cmd.n || 1;
  const color = cmd.color || 'cyan';
  const circleR = 10;
  const circleX = x + circleR;
  const circleY = y + circleR;

  bdExpandIfNeeded(y + 25);

  // Draw circled number
  bd.ctx.strokeStyle = (BD_COLORS[color] || color) ;
  bd.ctx.lineWidth = 1.5 * s;
  bd.ctx.beginPath();
  bd.ctx.arc(circleX * s, circleY * s, circleR * s, 0, Math.PI * 2);
  bd.ctx.stroke();
  const numFS = 11 * bdGetFontScale();
  bd.ctx.font = `${numFS}px 'Caveat', cursive`;
  bd.ctx.fillStyle = BD_COLORS[color] || color;
  bd.ctx.textAlign = 'center';
  bd.ctx.textBaseline = 'middle';
  bd.ctx.fillText(String(n), circleX * s, circleY * s);
  bd.ctx.textAlign = 'start';
  bd.ctx.textBaseline = 'alphabetic';
  bdClearShadow();

  // Draw step text beside the circle
  const textX = x + circleR * 2 + 8;
  const stepLines = await bdAnimText(cmd.text, textX, y + 3, 'white', cmd.size || 'text', cmd.charDelay);
  const stepH = stepLines > 1 ? stepLines * bdResolveSize(cmd.size || 'text') * 1.4 : 22;
  _registerElement(cmd.id, x, y, 400, stepH);
  _correctCursor(y, stepH + 2);
}

async function bdCompoundCheckCross(cmd, isCheck) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const x = cmd.x, y = cmd.y;
  const marker = isCheck ? '✓' : '✗';
  const markerColor = isCheck ? 'green' : 'red';
  const textColor = cmd.color || 'white';

  bdExpandIfNeeded(y + 18);
  await bdAnimText(marker, x, y, markerColor, cmd.size || 'text', 0);
  const chkLines = await bdAnimText(' ' + cmd.text, x + 18, y, textColor, cmd.size || 'text', cmd.charDelay || 25);
  const chkH = chkLines > 1 ? chkLines * bdResolveSize(cmd.size || 'text') * 1.4 : 20;
  _registerElement(cmd.id, x, y, 350, chkH);
  _correctCursor(y, chkH + 2);
}

async function bdCompoundCallout(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const x = cmd.x, y = cmd.y;
  const color = cmd.color || 'gold';
  const borderColor = BD_COLORS[color] || color;
  const textSize = bdResolveSize(cmd.size || 'text');
  const lineH = textSize * 1.6;
  const padL = 12;

  bdExpandIfNeeded(y + lineH + 4);

  // Draw left border accent
  bd.ctx.strokeStyle = borderColor;
  bd.ctx.lineWidth = 3 * s;
  bd.ctx.lineCap = 'round';
  bd.ctx.beginPath();
  bd.ctx.moveTo((x + 2) * s, (y - 2) * s);
  bd.ctx.lineTo((x + 2) * s, (y + lineH + 2) * s);
  bd.ctx.stroke();
  bdClearShadow();

  // Draw text after the border
  const calloutLines = await bdAnimText(cmd.text, x + padL, y + 2, color, cmd.size || 'text', cmd.charDelay);
  const actualCalloutH = calloutLines > 1 ? calloutLines * textSize * 1.4 + 4 : lineH;
  // Extend border for wrapped text
  if (calloutLines > 1) {
    bd.ctx.strokeStyle = borderColor;
    bd.ctx.lineWidth = 3 * s;
    bd.ctx.lineCap = 'round';
    bd.ctx.beginPath();
    bd.ctx.moveTo((x + 2) * s, (y + lineH + 2) * s);
    bd.ctx.lineTo((x + 2) * s, (y + actualCalloutH + 2) * s);
    bd.ctx.stroke();
    bdClearShadow();
  }
  _registerElement(cmd.id, x, y, 500, actualCalloutH);
  _correctCursor(y, actualCalloutH + 4);
}

async function bdCompoundList(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const x = cmd.x, y = cmd.y;
  const items = cmd.items || [];
  const style = cmd.style || 'bullet';
  const color = cmd.color || 'white';
  const itemSpacing = 22;
  let curY = y;

  for (let i = 0; i < items.length; i++) {
    if (bd.cancelFlag) return;
    bdExpandIfNeeded(curY + 16);
    let prefix;
    if (style === 'number') prefix = `${i + 1}. `;
    else if (style === 'check') prefix = '✓ ';
    else prefix = '• ';
    await bdAnimText(prefix + items[i], x + 5, curY, color, cmd.size || 'text', 25);
    curY += itemSpacing;
  }

  const totalH = curY - y;
  _registerElement(cmd.id, x, y, 400, totalH);
  _correctCursor(y, totalH);
}

async function bdCompoundDivider(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const y = cmd.y != null ? cmd.y : bdLayout.cursorY;
  const lineY = y + 6;
  bdExpandIfNeeded(lineY + 4);

  bd.ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  bd.ctx.lineWidth = 1;
  bd.ctx.beginPath();
  bd.ctx.moveTo(BD_MARGIN * s, lineY * s);
  bd.ctx.lineTo((BD_VIRTUAL_W - BD_MARGIN) * s, lineY * s);
  bd.ctx.stroke();

  // Don't double-commit — placement resolver already handled it
}

async function bdCompoundResult(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag) return;
  const s = bd.scale;
  const x = cmd.x, y = cmd.y;
  const color = cmd.color || 'gold';
  const borderColor = BD_COLORS[color] || color;
  const textSize = bdResolveSize(cmd.size || 'text');
  const fontScale = bdGetFontScale();
  const fs = textSize * fontScale;
  bd.ctx.font = `${fs}px 'Caveat', cursive`;
  const textW = bd.ctx.measureText(cmd.text).width / s;
  const padX = 16, padY = 8;
  const usableW = BD_VIRTUAL_W - BD_MARGIN * 2;
  const boxW = Math.min(textW + padX * 2, usableW);
  const boxH = textSize * 1.6 + padY * 2;
  const boxX = x + Math.max(0, (usableW - boxW) / 2);

  bdExpandIfNeeded(y + boxH + 4);

  // Draw subtle bordered box
  bd.ctx.strokeStyle = borderColor;
  bd.ctx.lineWidth = 1.5 * s;
  bd.ctx.globalAlpha = 0.4;
  bd.ctx.strokeRect((boxX) * s, (y) * s, boxW * s, boxH * s);
  bd.ctx.globalAlpha = 1.0;

  // Optional label badge
  if (cmd.label) {
    const labelFS = 9 * fontScale;
    bd.ctx.font = `${labelFS}px 'Caveat', cursive`;
    bd.ctx.fillStyle = 'rgba(26,29,46,1)';
    const labelW = bd.ctx.measureText(cmd.label).width / s + 8;
    bd.ctx.fillRect((boxX + 8) * s, (y - 5) * s, labelW * s, 11 * s);
    bd.ctx.fillStyle = borderColor;
    bd.ctx.globalAlpha = 0.7;
    bd.ctx.textBaseline = 'middle';
    bd.ctx.font = `${labelFS}px 'Caveat', cursive`;
    bd.ctx.fillText(cmd.label, (boxX + 12) * s, (y + 0.5) * s);
    bd.ctx.globalAlpha = 1.0;
  }

  // Draw the main text centered in the box (clip to box bounds for long text)
  const textOverflows = textW + padX * 2 > usableW;
  if (textOverflows) {
    bd.ctx.save();
    bd.ctx.beginPath();
    bd.ctx.rect(boxX * s, y * s, boxW * s, boxH * s);
    bd.ctx.clip();
  }
  await bdAnimText(cmd.text, boxX + padX, y + padY + 2, color, cmd.size || 'text', cmd.charDelay);
  if (textOverflows) {
    bd.ctx.restore();
  }

  // Note beside the box
  if (cmd.note) {
    const noteX = boxX + boxW + BD_SIDE_GAP;
    if (noteX + 80 < BD_VIRTUAL_W - BD_MARGIN) {
      await bdAnimText('← ' + cmd.note, noteX, y + padY + 4, 'dim', 'small', 20);
    }
  }

  _registerElement(cmd.id, boxX, y, boxW, boxH);
  _correctCursor(y, boxH);
}

// ── Board Editing Commands ──

function bdStrikeoutElement(cmd) {
  // Draw a diagonal line through a referenced element: {"cmd":"strikeout","target":"eq1"}
  const bd = state.boardDraw;
  if (!bd.ctx || !cmd.target) return;
  const ref = bdElementRegistry[cmd.target];
  if (!ref) return;
  const s = bd.scale;
  const yOff = state._voiceSceneYOffset || 0;
  const x = ref.x * s, y = (ref.y + yOff) * s;
  const w = (ref.w || 80) * s, h = (ref.h || 20) * s;
  bd.ctx.save();
  bd.ctx.strokeStyle = 'rgba(255, 107, 107, 0.7)';
  bd.ctx.lineWidth = 2.5 * s;
  bd.ctx.beginPath();
  bd.ctx.moveTo(x - 4 * s, y + h * 0.5);
  bd.ctx.lineTo(x + w + 4 * s, y + h * 0.5);
  bd.ctx.stroke();
  bd.ctx.restore();
}

async function bdUpdateElement(cmd) {
  // Overwrite an existing element with new text: {"cmd":"update","target":"eq1","text":"new text","color":"green"}
  const bd = state.boardDraw;
  if (!bd.ctx || !cmd.target || !cmd.text) return;
  const ref = bdElementRegistry[cmd.target];
  if (!ref) return;
  const s = bd.scale;
  const yOff = state._voiceSceneYOffset || 0;
  const x = ref.x * s, y = (ref.y + yOff) * s;
  const w = (ref.w || 80) * s, h = (ref.h || 20) * s;
  // Clear the old content area
  bd.ctx.save();
  bd.ctx.fillStyle = '#1a1d2e';
  bd.ctx.fillRect(x - 2 * s, y - h * 0.3, w + 4 * s, h * 1.3);
  bd.ctx.restore();
  // Draw the new text in place
  await bdAnimText(cmd.text, ref.x, ref.y + yOff, cmd.color || 'green', cmd.size || 'text', 20);
}

async function bdCloneElement(cmd) {
  // Clone an element to a new position: {"cmd":"clone","source":"eq1","placement":"below","id":"eq1-copy"}
  const bd = state.boardDraw;
  if (!bd.ctx || !cmd.source) return;
  const ref = bdElementRegistry[cmd.source];
  if (!ref) return;
  // Get the original command's text/content from registry
  const origCmd = ref.cmd;
  // Re-draw at the new placement with the clone's id
  const cloneCmd = {
    cmd: origCmd === 'animation' ? 'text' : (origCmd || 'text'), // can't clone animations — draw label instead
    text: ref.text || cmd.text || `[${cmd.source}]`,
    placement: cmd.placement || 'below',
    id: cmd.id || cmd.source + '-copy',
    color: cmd.color || ref.color || 'cyan',
    size: cmd.size || ref.size || 'text',
  };
  // Use the existing command runner for proper layout
  await bdRunCommand(cloneCmd);
}

function bdDeleteElement(cmd) {
  // Clear an element from the board: {"cmd":"delete","target":"eq1"}
  const bd = state.boardDraw;
  if (!bd.ctx || !cmd.target) return;
  const ref = bdElementRegistry[cmd.target];
  if (!ref) return;
  const s = bd.scale;
  const yOff = state._voiceSceneYOffset || 0;
  const x = ref.x * s, y = (ref.y + yOff) * s;
  const w = (ref.w || 80) * s, h = (ref.h || 20) * s;
  bd.ctx.save();
  bd.ctx.fillStyle = '#1a1d2e';
  bd.ctx.fillRect(x - 4 * s, y - h * 0.4, w + 8 * s, h * 1.5);
  bd.ctx.restore();
  bdDrawGrid(); // redraw grid over cleared area
  delete bdElementRegistry[cmd.target];
}

// ── p5.js Animation Engine ──

function bdRecoverMissedAnimations(bd) {
  // Check if any animation commands are already in the queue
  const hasAnim = BoardEngine.state.commandQueue.some(c => c.cmd === 'animation');
  if (hasAnim) return; // already got them

  // Scan raw content for animation commands using bracket-matching
  // This handles the case where the AI put newlines inside the "code" JSON string
  const raw = bd.rawContent || '';
  const marker = '"cmd":"animation"';
  const marker2 = '"cmd": "animation"';
  let searchFrom = 0;

  while (searchFrom < raw.length) {
    let idx = raw.indexOf(marker, searchFrom);
    if (idx < 0) idx = raw.indexOf(marker2, searchFrom);
    if (idx < 0) break;

    // Walk backwards to find the opening { of this JSON object
    let objStart = raw.lastIndexOf('{', idx);
    if (objStart < 0) { searchFrom = idx + 10; continue; }

    // Walk forward with bracket matching to find the closing }
    let depth = 0;
    let inStr = false;
    let escaped = false;
    let objEnd = -1;

    for (let i = objStart; i < raw.length; i++) {
      const ch = raw[i];
      if (escaped) { escaped = false; continue; }
      if (ch === '\\') { escaped = true; continue; }
      if (ch === '"') { inStr = !inStr; continue; }
      if (inStr) continue;
      if (ch === '{') depth++;
      if (ch === '}') { depth--; if (depth === 0) { objEnd = i; break; } }
    }

    if (objEnd < 0) { searchFrom = idx + 10; continue; }

    const jsonStr = raw.slice(objStart, objEnd + 1);
    try {
      const parsed = JSON.parse(jsonStr);
      if (parsed.cmd === 'animation' && parsed.code) {
        // Queue recovered animation command via BoardEngine
        BoardEngine.queueCommand(parsed);
      }
    } catch (e) {
      // Try to fix: the code field might have unescaped newlines
      // Replace literal newlines inside string values with spaces
      const fixed = jsonStr.replace(/\n/g, ' ');
      try {
        const parsed = JSON.parse(fixed);
        if (parsed.cmd === 'animation' && parsed.code) {
          BoardEngine.queueCommand(parsed);
        }
      } catch (e2) {
        console.warn('Board: could not recover animation command:', e2.message);
      }
    }
    searchFrom = objEnd + 1;
  }
  bd._pendingAnimLines = null;
}

function bdSanitizeAnimCode(code) {
  // Replace smart/curly quotes with straight quotes
  code = code.replace(/[\u2018\u2019\u201A\u2032]/g, "'");
  code = code.replace(/[\u201C\u201D\u201E\u2033]/g, '"');
  // Replace en/em dashes with minus
  code = code.replace(/[\u2013\u2014\u2212]/g, '-');
  // Remove zero-width characters
  code = code.replace(/[\u200B\u200C\u200D\uFEFF]/g, '');
  // Replace Unicode math operators with JS equivalents
  code = code.replace(/\u00D7/g, '*');  // × → *
  code = code.replace(/\u00F7/g, '/');  // ÷ → /
  code = code.replace(/\u2264/g, '<='); // ≤ → <=
  code = code.replace(/\u2265/g, '>='); // ≥ → >=
  code = code.replace(/\u2260/g, '!='); // ≠ → !=
  code = code.replace(/\u03C0/g, 'Math.PI'); // π → Math.PI
  // Replace non-breaking spaces with regular spaces
  code = code.replace(/\u00A0/g, ' ');
  // Strip markdown code fence wrappers if AI accidentally included them
  code = code.replace(/^```(?:javascript|js)?\s*/i, '').replace(/\s*```\s*$/, '');

  // Balance brackets: track the stack and append missing closers
  const stack = [];
  let inSingle = false, inDouble = false, inTemplate = false, esc = false;
  for (let i = 0; i < code.length; i++) {
    const ch = code[i];
    if (esc) { esc = false; continue; }
    if (ch === '\\') { esc = true; continue; }
    if (inSingle) { if (ch === "'") inSingle = false; continue; }
    if (inDouble) { if (ch === '"') inDouble = false; continue; }
    if (inTemplate) { if (ch === '`') inTemplate = false; continue; }
    if (ch === "'") { inSingle = true; continue; }
    if (ch === '"') { inDouble = true; continue; }
    if (ch === '`') { inTemplate = true; continue; }
    if (ch === '{') stack.push('}');
    else if (ch === '(') stack.push(')');
    else if (ch === '[') stack.push(']');
    else if (ch === '}' || ch === ')' || ch === ']') stack.pop();
  }
  if (stack.length > 0) {
    code += stack.reverse().join('');
  }
  return code;
}

async function bdRunAnimation(cmd) {
  const bd = state.boardDraw;
  if (bd.cancelFlag || !bd.canvas) return;
  const layer = document.getElementById('bd-anim-layer');
  if (!layer) return;

  const s = bd.scale || 1;
  const wrap = document.getElementById('bd-canvas-wrap');
  const boardW = (wrap && wrap.clientWidth > 0) ? wrap.clientWidth : 800;
  const boardH = (wrap && wrap.clientHeight > 0) ? wrap.clientHeight : 500;

  // Position from placement engine (virtual coords * scale)
  const x = (cmd.x || 20) * s;
  const y = (cmd.y || 0) * s;

  // Layout engine dimensions (virtual px * scale). Cap to prevent oversized animations.
  const maxW = boardW * 0.65;
  const maxH = boardH * 0.55;
  const w = Math.min(Math.max((cmd._layoutW || 350) * s, 200), maxW);
  const h = Math.min(Math.max((cmd._layoutH || 200) * s, 150), maxH);
  // Voice mode: NEVER rasterize animations via timer — keep them alive
  // Text mode: use LLM-specified duration or default 6000ms
  const duration = state.teachingMode === 'voice' ? 0 : (cmd.duration || 0);

  bdExpandIfNeeded((cmd.y || 0) + h / s + 10);

  if (!cmd.code) {
    console.warn('Board animation: no "code" field provided');
    return;
  }

  let code = bdSanitizeAnimCode(cmd.code);
  // Inject onControl bridge so tutor can change animation parameters at runtime
  // Scale factor so animation text/strokes are proportional to container size
  // Base: 300px wide container. If actual is 600px, scale = 2x.
  const baseW = 300;
  const animScale = Math.round(w) / baseW;
  // Detect if this is a WEBGL animation (check the code for p.WEBGL)
  const isWebGL = /p\.WEBGL|, *WEBGL/.test(cmd.code);
  const controlBridge = `
    var _controlParams = {};
    var _elements = {};
    var S = ${animScale.toFixed(2)}; // scale factor for text/strokes
    function onControl(params) {
      if (params._unhighlight) { _controlParams._highlight = null; }
      Object.assign(_controlParams, params);
    }
    p._onControl = function(params) { onControl(params); };
    // Helper: scale-aware text size
    function sTextSize(sz) { return sz * S; }
    // Helper: scale-aware stroke weight
    function sStroke(w) { return Math.max(1, w * S); }
    // Helper: apply highlight glow to drawing context
    function applyHighlight(p, color, isHighlighted) {
      if (isHighlighted) {
        p.strokeWeight(sStroke(3));
        p.drawingContext.shadowColor = color || '#34d399';
        p.drawingContext.shadowBlur = 18 * S;
      } else {
        p.strokeWeight(sStroke(1.5));
        p.drawingContext.shadowBlur = 0;
      }
    }
    // ── SAFETY NET: proxy unknown methods to drawingContext ──
    // LLMs often call native Canvas2D methods (setLineDash, clip, save, etc.)
    // directly on p instead of p.drawingContext. Instead of polyfilling each one,
    // use a Proxy-like approach: intercept property access and delegate.
    var _p5Proto = Object.getPrototypeOf(p);
    var _origGet = p.__proto__;
    var _proxied = new Set();
    function _ensureMethod(name) {
      if (_proxied.has(name)) return;
      _proxied.add(name);
      if (typeof p[name] === 'undefined' && p.drawingContext && typeof p.drawingContext[name] === 'function') {
        p[name] = function() { return p.drawingContext[name].apply(p.drawingContext, arguments); };
      }
    }
    // Pre-proxy the most common Canvas2D methods LLMs use
    ['setLineDash','getLineDash','setTransform','resetTransform','clip','clearRect',
     'createLinearGradient','createRadialGradient','measureText','isPointInPath',
     'fillRect','strokeRect','roundRect','moveTo','lineTo','quadraticCurveTo','bezierCurveTo',
     'arcTo','closePath','getImageData','putImageData','createPattern'].forEach(_ensureMethod);
    ${isWebGL ? `
    // WEBGL safe wrappers — p.text() and p.textFont() require loadFont() in WEBGL.
    // Silently no-op these calls so animations don't break or spam console.
    var _origText = p.text.bind(p);
    var _origTextFont = p.textFont.bind(p);
    var _origTextSize = p.textSize.bind(p);
    var _origTextAlign = p.textAlign.bind(p);
    p.text = function() {}; // no-op in WEBGL — labels go outside via legend
    p.textFont = function() {};
    p.textSize = function() {};
    p.textAlign = function() {};
    ` : ''}
  `;
  // Auto-scale hardcoded text sizes and stroke weights in the AI-generated code
  code = code.replace(/p\.textSize\((\d+(?:\.\d+)?)\)/g, (_, n) => `p.textSize(${n} * S)`);
  code = code.replace(/p\.strokeWeight\((\d+(?:\.\d+)?)\)/g, (_, n) => `p.strokeWeight(Math.max(1, ${n} * S))`);
  // Strip re-declarations of W, H, S that conflict with function params / injected bridge
  code = code.replace(/\b(let|const|var)\s+(W|H)\b\s*=/g, '$2 =');
  code = code.replace(/\b(let|const|var)\s+S\b\s*=/g, 'S =');
  code = controlBridge + '\n' + code;
  let sketchFn;
  try {
    sketchFn = new Function('p', 'W', 'H', code);
  } catch (e) {
    // Try stripping non-ASCII chars from code
    const asciiCode = code.replace(/[^\x00-\x7F]/g, '');
    try {
      sketchFn = new Function('p', 'W', 'H', asciiCode);
      console.info('Board animation recovered by stripping non-ASCII');
    } catch (e2) {
      // Show skeleton placeholder + call Haiku to fix
      console.warn('Board animation compile error — showing skeleton, calling Haiku fix');
      const origCode = cmd.code; // original LLM code (before bridge injection)
      bdShowAnimSkeleton(layer, x, y, Math.round(w), Math.round(h), s, cmd, origCode, e.message, controlBridge, isWebGL);
      return;
    }
  }

  // Animation container with expand/minimize controls
  const compactH = Math.round(h);
  const expandedH = Math.round(Math.min(h * 1.5, boardH * 0.75));
  const containerW = Math.round(w);
  const expandedW = Math.round(Math.min(w * 1.3, boardW * 0.85));

  const container = document.createElement('div');
  container.className = 'bd-anim-box';
  container.style.left = x + 'px';
  container.style.top = y + 'px';
  container.style.width = containerW + 'px';
  container.style.height = compactH + 'px';
  container.style.opacity = '0';
  container.style.transition = 'opacity 0.4s, width 0.3s ease, height 0.3s ease';
  container.dataset.compactH = compactH;
  container.dataset.expandedH = expandedH;
  container.dataset.compactW = containerW;
  container.dataset.expandedW = expandedW;

  // Expand/minimize button — uses addEventListener (not inline onclick which CSP can block)
  const controls = document.createElement('div');
  controls.style.cssText = 'position:absolute;top:6px;right:6px;z-index:10;pointer-events:auto;';
  const expandBtn = document.createElement('button');
  expandBtn.textContent = '⛶';
  expandBtn.title = 'Expand animation';
  expandBtn.style.cssText = 'width:28px;height:28px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:rgba(0,0,0,0.5);color:rgba(255,255,255,0.7);cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px);transition:all 0.15s;pointer-events:auto;';
  expandBtn.addEventListener('click', (e) => { e.stopPropagation(); bdToggleAnimSize(expandBtn); });
  expandBtn.addEventListener('mouseover', () => { expandBtn.style.background = 'rgba(52,211,153,0.3)'; });
  expandBtn.addEventListener('mouseout', () => { expandBtn.style.background = 'rgba(0,0,0,0.5)'; });
  controls.appendChild(expandBtn);

  // Canvas wrapper (p5 renders inside this)
  const canvasWrap = document.createElement('div');
  canvasWrap.className = 'bd-anim-canvas-wrap';
  canvasWrap.style.cssText = 'width:100%;height:100%;overflow:hidden;border-radius:4px;';

  container.appendChild(controls);
  container.appendChild(canvasWrap);
  layer.appendChild(container);

  const pw = containerW;
  const ph = compactH;

  const BOARD_FONT = "'Caveat', cursive";

  let inst;
  try {
    inst = new p5(p => {
      try {
        sketchFn(p, pw, ph);
      } catch (sketchErr) {
        console.error('[Animation] Sketch function error:', sketchErr.message);
        canvasWrap.innerHTML = `<div style="padding:8px;font-size:${10*s}px;color:rgba(248,113,113,0.5);font-family:monospace;word-break:break-all">Animation error: ${sketchErr.message}</div>`;
        return;
      }
      // ── SAFETY NET: wrap draw() in error boundary ──
      // Any runtime error in draw() would spam 60x/sec forever.
      // Catch errors, log ONCE, let animation continue running.
      const userDraw = p.draw;
      if (userDraw) {
        let _drawErrors = 0;
        p.draw = function() {
          try {
            userDraw.call(p);
          } catch (drawErr) {
            _drawErrors++;
            if (_drawErrors === 1) console.warn('[Animation] draw() error (will suppress repeats):', drawErr.message);
            if (_drawErrors >= 60) { p.noLoop(); console.warn('[Animation] Too many draw errors — stopped'); }
            // Don't re-throw — let animation keep trying (some errors are transient)
          }
        };
      }
      const userSetup = p.setup;
      p.setup = function() {
        if (userSetup) userSetup.call(p);
        try { if (!p._renderer.isP3D) p.textFont('Caveat'); } catch(e) {}
      };
    }, canvasWrap);
  } catch (e) {
    console.error('[Animation] p5 init error:', e.message);
    canvasWrap.innerHTML = `<div style="padding:8px;font-size:${10*s}px;color:rgba(248,113,113,0.5);font-family:monospace">Init error: ${e.message}</div>`;
    return;
  }

  requestAnimationFrame(() => { container.style.opacity = '1'; });

  // Correct layout cursor if actual animation height > estimated height
  // This prevents subsequent content from overlapping the animation
  const actualVirtualH = h / s;
  if (cmd._yOffset !== undefined) {
    _correctCursor(cmd.y, actualVirtualH);
  }

  // Store p5 instance reference for runtime control
  container._p5Instance = inst;
  const layoutW = cmd._layoutW || cmd.w || 300;
  const layoutH = cmd._layoutH || cmd.h || 200;
  const entry = {
    container, inst,
    vx: cmd.x || 0, vy: cmd.y || 0,
    vw: layoutW, vh: layoutH,
    p5Instance: inst,
  };
  // Register animation element if it has an ID
  // Don't overwrite — placement resolver already registered with correct LOCAL coords (line 9598)
  if (cmd.id && !bdElementRegistry[cmd.id]) {
    bdElementRegistry[cmd.id] = { cmd: 'animation', x: cmd.x||0, y: cmd.y||0, w: layoutW, h: layoutH, animEntry: entry };
  } else if (cmd.id) {
    // Attach animEntry to existing registry entry for runtime control
    bdElementRegistry[cmd.id].animEntry = entry;
  }
  bdActiveAnimations.push(entry);

  // Blank animation detection — max 1 Haiku attempt, then give up
  const retryKey = cmd.id || 'anon';
  if (!bd._animRetries) bd._animRetries = {};
  const attemptNum = bd._animRetries[retryKey] || 0;
  if (attemptNum < 1) {
    setTimeout(() => {
      try {
        const p5c = canvasWrap.querySelector('canvas');
        if (!p5c || p5c.width === 0) return;
        // Check if canvas has ANY visible content (sample 50 pixels)
        const ctx2 = p5c.getContext('2d', { willReadFrequently: true });
        if (!ctx2) return;
        const data = ctx2.getImageData(0, 0, p5c.width, p5c.height).data;
        const step = Math.max(4, Math.floor(data.length / 200)) & ~3; // ~50 samples
        let nonBgCount = 0;
        for (let i = 0; i < data.length; i += step) {
          if (data[i] > 25 || data[i+1] > 30 || data[i+2] > 25) nonBgCount++;
        }
        if (nonBgCount >= 3) return; // has content — animation is working

        bd._animRetries[retryKey] = attemptNum + 1;
        console.warn(`[Animation] Blank detected — calling Haiku fix:`, retryKey);
        fetch(`${state.apiUrl}/api/fix-animation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
          body: JSON.stringify({ code: cmd.code, error: 'Canvas all black. Fix drawing logic: use W,H for coords, visible colors, call stroke/fill before shapes.' }),
        })
        .then(r => r.ok ? r.json() : null)
        .then(fixData => {
          if (!fixData || !fixData.code) throw new Error('No code');
          try { entry.inst.remove(); } catch(e) {}
          if (entry.container?.parentNode) entry.container.parentNode.removeChild(entry.container);
          const idx = bdActiveAnimations.indexOf(entry);
          if (idx >= 0) bdActiveAnimations.splice(idx, 1);
          bdRunAnimation({ ...cmd, code: fixData.code });
        })
        .catch(() => {
          // Fix failed — remove animation, show fallback
          bdAnimGiveUp(entry, container, retryKey);
        });
      } catch (e) { /* ignore */ }
    }, 2500);
  } else if (attemptNum >= 1) {
    // Already tried — give up after checking
    setTimeout(() => {
      try {
        const p5c = canvasWrap.querySelector('canvas');
        if (!p5c) return;
        const ctx2 = p5c.getContext('2d', { willReadFrequently: true });
        if (!ctx2) return;
        const data = ctx2.getImageData(0, 0, p5c.width, p5c.height).data;
        const step = Math.max(4, Math.floor(data.length / 200)) & ~3;
        let nonBgCount = 0;
        for (let i = 0; i < data.length; i += step) {
          if (data[i] > 25 || data[i+1] > 30 || data[i+2] > 25) nonBgCount++;
        }
        if (nonBgCount >= 3) return; // fixed animation works!
        bdAnimGiveUp(entry, container, retryKey);
      } catch(e) { bdAnimGiveUp(entry, container, retryKey); }
    }, 2500);
  }

  if (duration > 0) {
    await new Promise(resolve => {
      const timer = setTimeout(() => {
        bdRasterizeAnimation(entry);
        resolve();
      }, duration);
      entry._timer = timer;
    });
  }
}

function bdAnimGiveUp(entry, container, retryKey) {
  console.warn('[Animation] Giving up after max retries:', retryKey);
  try { entry.inst.remove(); } catch(e) {}
  const idx = bdActiveAnimations.indexOf(entry);
  if (idx >= 0) bdActiveAnimations.splice(idx, 1);
  // Remove the animation container entirely — don't leave a huge empty box
  if (container && container.parentNode) {
    container.parentNode.removeChild(container);
  }
}

async function bdSilentAnimRetry(errors) {
  const bd = state.boardDraw;
  if (!bd.canvas || bd.cancelFlag) return;
  if (bd._retryInFlight) return;
  bd._retryInFlight = true;

  const errorDescs = errors.map((e, i) => {
    const c = e.cmd;
    return `Animation ${i + 1} at (x:${c.x},y:${c.y},w:${c.w},h:${c.h}):\n` +
      `  Error: ${e.error}\n  Code: ${(c.code || '').slice(0, 600)}`;
  }).join('\n\n');

  const repairPrompt =
    `[SYSTEM — HIDDEN FROM STUDENT]\n` +
    `Your board animation code had JavaScript errors and failed to run.\n` +
    `Fix ONLY the broken animation commands and return them as JSONL lines ` +
    `(one {"cmd":"animation",...} per line). Return NOTHING else — no text, no XML tags, ` +
    `just the corrected JSONL animation commands.\n\n` +
    `ERRORS:\n${errorDescs}`;

  try {
    const res = await fetch(`${state.apiUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...AuthManager.authHeaders(),
      },
      body: JSON.stringify({
        messages: [
          ...state.messages,
          { id: generateId(), role: 'user', content: repairPrompt },
        ],
        context: buildContext(),
        sessionId: state.sessionId,
      }),
    });

    if (!res.ok) { bd._retryInFlight = false; return; }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue;
        try {
          const evt = JSON.parse(line.slice(6).trim());
          if (evt.type === 'TEXT_MESSAGE_CONTENT' && evt.delta) fullText += evt.delta;
          else if (evt.type === 'TEXT_DELTA' && evt.text) fullText += evt.text;
        } catch (e) {}
      }
    }

    const corrected = [];
    for (const ln of fullText.split('\n')) {
      const trimmed = ln.trim();
      if (!trimmed || !trimmed.startsWith('{')) continue;
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed.cmd === 'animation' && parsed.code) corrected.push(parsed);
      } catch (e) {}
    }

    bd._animErrors = null; // clear so retried failures don't re-trigger
    for (const cmd of corrected) {
      if (bd.cancelFlag || !bd.canvas) break;
      BoardEngine.queueCommand(cmd);
    }
  } catch (e) {
    console.warn('Silent animation retry failed:', e.message);
  }
  bd._retryInFlight = false;
}

// ── Skeleton placeholder + Haiku code fix ──

function bdShowAnimSkeleton(layer, x, y, w, h, s, cmd, origCode, errorMsg, controlBridge, isWebGL) {
  // 1. Show a pulsing skeleton placeholder immediately
  const container = document.createElement('div');
  container.className = 'bd-anim-box';
  container.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${h}px;overflow:hidden;border-radius:6px;`;
  container.innerHTML = `
    <div style="width:100%;height:100%;background:#0f1410;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px">
      <div style="width:40px;height:40px;border:2px solid rgba(52,211,153,0.3);border-top-color:rgba(52,211,153,0.8);border-radius:50%;animation:spin 1s linear infinite"></div>
      <div style="color:rgba(52,211,153,0.5);font-size:${11*s}px;font-family:monospace">fixing animation...</div>
    </div>
    <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
  `;
  layer.appendChild(container);

  // 2. Call Haiku to fix the code
  fetch(`${state.apiUrl}/api/fix-animation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
    body: JSON.stringify({ code: origCode, error: errorMsg }),
  })
  .then(r => r.ok ? r.json() : Promise.reject(new Error(`${r.status}`)))
  .then(data => {
    if (!data.code) throw new Error('No fixed code returned');
    // 3. Try compiling the fixed code
    let fixedCode = bdSanitizeAnimCode(data.code);
    fixedCode = fixedCode.replace(/p\.textSize\((\d+(?:\.\d+)?)\)/g, (_, n) => `p.textSize(${n} * S)`);
    fixedCode = fixedCode.replace(/p\.strokeWeight\((\d+(?:\.\d+)?)\)/g, (_, n) => `p.strokeWeight(Math.max(1, ${n} * S))`);
    fixedCode = fixedCode.replace(/\b(let|const|var)\s+(W|H)\b\s*=/g, '$2 =');
    fixedCode = fixedCode.replace(/\b(let|const|var)\s+S\b\s*=/g, 'S =');
    const fullCode = controlBridge + '\n' + fixedCode;
    const fn = new Function('p', 'W', 'H', fullCode);

    // 4. Replace skeleton with real animation
    container.innerHTML = '';
    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'bd-anim-canvas-wrap';
    canvasWrap.style.cssText = 'width:100%;height:100%;overflow:hidden;border-radius:4px;';
    container.appendChild(canvasWrap);

    const inst = new p5(p => {
      try { fn(p, w, h); } catch(e) {
        console.warn('[Animation] Fixed code also errored:', e.message);
        canvasWrap.innerHTML = `<div style="padding:12px;color:rgba(248,113,113,0.5);font-size:11px;font-family:monospace">Animation unavailable</div>`;
        return;
      }
      const userSetup = p.setup;
      p.setup = function() {
        if (userSetup) userSetup.call(p);
        try { if (!p._renderer.isP3D) p.textFont('Caveat'); } catch(e) {}
      };
    }, canvasWrap);
    container._p5Instance = inst;
    container.style.opacity = '1';

    // Add expand button (addEventListener, not inline onclick)
    const controls = document.createElement('div');
    controls.style.cssText = 'position:absolute;top:6px;right:6px;z-index:10;pointer-events:auto;';
    const ebtn = document.createElement('button');
    ebtn.textContent = '⛶';
    ebtn.title = 'Expand animation';
    ebtn.style.cssText = 'width:28px;height:28px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:rgba(0,0,0,0.5);color:rgba(255,255,255,0.7);cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;pointer-events:auto;';
    ebtn.addEventListener('click', (e) => { e.stopPropagation(); bdToggleAnimSize(ebtn); });
    controls.appendChild(ebtn);
    container.appendChild(controls);

    const layoutW = cmd._layoutW || cmd.w || 300;
    const layoutH = cmd._layoutH || cmd.h || 200;
    bdActiveAnimations.push({ container, inst, vx: cmd.x||0, vy: cmd.y||0, vw: layoutW, vh: layoutH, p5Instance: inst });
    console.info('[Animation] Haiku fix succeeded — animation replaced');
  })
  .catch(err => {
    console.warn('[Animation] Haiku fix failed:', err.message);
    container.innerHTML = `
      <div style="width:100%;height:100%;background:#0f1410;display:flex;align-items:center;justify-content:center">
        <div style="color:rgba(255,255,255,0.25);font-size:${12*s}px;font-family:'Caveat',cursive">animation unavailable</div>
      </div>`;
  });
}

function bdRasterizeAnimation(entry) {
  const bd = state.boardDraw;
  if (!bd.canvas || !bd.ctx) { bdRemoveAnimation(entry); return; }

  const p5Canvas = entry.container.querySelector('canvas');
  if (p5Canvas && p5Canvas.width > 0 && p5Canvas.height > 0) {
    const s = bd.scale || 1;
    const dw = (entry.vw || 300) * s;
    const dh = (entry.vh || 200) * s;
    if (dw > 0 && dh > 0) {
      bd.ctx.save();
      bd.ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
      try {
        bd.ctx.drawImage(p5Canvas, (entry.vx || 0) * s, (entry.vy || 0) * s, dw, dh);
      } catch (e) {
        console.warn('Animation rasterize failed:', e.message);
      }
      bd.ctx.restore();
    }
  }
  bdRemoveAnimation(entry);
}

function bdRemoveAnimation(entry) {
  try { entry.inst.remove(); } catch (e) {}
  try { entry.container.remove(); } catch (e) {}
  if (entry._timer) clearTimeout(entry._timer);
  const idx = bdActiveAnimations.indexOf(entry);
  if (idx !== -1) bdActiveAnimations.splice(idx, 1);
}

function bdRasterizeAllAnimations() {
  [...bdActiveAnimations].forEach(entry => bdRasterizeAnimation(entry));
}

window.bdToggleAnimSize = function(btn) {
  const box = btn.closest('.bd-anim-box');
  if (!box) return;

  // Open fullscreen modal with the animation
  let modal = document.getElementById('bd-anim-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'bd-anim-modal';
    modal.style.cssText = `
      position:fixed;inset:0;z-index:500;
      background:rgba(0,0,0,0.85);
      display:flex;align-items:center;justify-content:center;
      backdrop-filter:blur(8px);
      opacity:0;transition:opacity 0.25s ease;
    `;
    modal.innerHTML = `
      <div id="bd-anim-modal-content" style="position:relative;width:85vw;height:75vh;background:#0f1410;border:1px solid rgba(255,255,255,0.1);border-radius:12px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.5)">
        <button id="bd-anim-modal-close" style="position:absolute;top:10px;right:10px;z-index:10;width:36px;height:36px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(0,0,0,0.5);color:rgba(255,255,255,0.8);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px);transition:all 0.15s" onmouseover="this.style.background='rgba(248,113,113,0.3)'" onmouseout="this.style.background='rgba(0,0,0,0.5)'">✕</button>
        <div id="bd-anim-modal-canvas" style="width:100%;height:100%"></div>
      </div>
    `;
    document.body.appendChild(modal);
    document.getElementById('bd-anim-modal-close').onclick = () => bdCloseAnimModal();
    modal.onclick = (e) => { if (e.target === modal) bdCloseAnimModal(); };
  }

  // Move the p5 canvas wrapper into the modal
  const canvasWrap = box.querySelector('.bd-anim-canvas-wrap');
  if (!canvasWrap) return;

  const modalCanvas = document.getElementById('bd-anim-modal-canvas');
  modal._sourceBox = box;
  modal._sourceCanvasWrap = canvasWrap;

  // Store original size
  canvasWrap._origWidth = canvasWrap.style.width;
  canvasWrap._origHeight = canvasWrap.style.height;

  // Move canvas to modal
  modalCanvas.innerHTML = '';
  modalCanvas.appendChild(canvasWrap);
  canvasWrap.style.width = '100%';
  canvasWrap.style.height = '100%';

  // Resize p5 to fill modal
  const inst = box._p5Instance;
  if (inst && typeof inst.resizeCanvas === 'function') {
    requestAnimationFrame(() => {
      const rect = modalCanvas.getBoundingClientRect();
      try { inst.resizeCanvas(Math.round(rect.width), Math.round(rect.height)); } catch(e) {}
    });
  }

  // Show modal
  modal.style.display = 'flex';
  requestAnimationFrame(() => { modal.style.opacity = '1'; });
};

function bdCloseAnimModal() {
  const modal = document.getElementById('bd-anim-modal');
  if (!modal) return;

  const box = modal._sourceBox;
  const canvasWrap = modal._sourceCanvasWrap;

  if (box && canvasWrap) {
    // Move canvas back to the original box
    box.appendChild(canvasWrap);
    canvasWrap.style.width = canvasWrap._origWidth || '100%';
    canvasWrap.style.height = canvasWrap._origHeight || '100%';

    // Resize p5 back to compact
    const inst = box._p5Instance;
    if (inst && typeof inst.resizeCanvas === 'function') {
      const compactW = parseInt(box.dataset.compactW) || parseInt(box.style.width);
      const compactH = parseInt(box.dataset.compactH) || parseInt(box.style.height);
      try { inst.resizeCanvas(compactW, compactH); } catch(e) {}
    }
  }

  modal.style.opacity = '0';
  setTimeout(() => { modal.style.display = 'none'; }, 250);
}

function bdClearAllAnimations() {
  [...bdActiveAnimations].forEach(entry => bdRemoveAnimation(entry));
}

// ── Scene Snapshot System ─────────────────────────────────────
// Captures current canvas as JPEG snapshot, inserts as <img>,
// clears canvas for new scene. Solves memory: only one live canvas.

let _sceneSnapshots = []; // track snapshot elements for ref highlighting

function bdSnapshotCurrentScene_LEGACY() {
  const bd = state.boardDraw;
  if (!bd.canvas || !bd.ctx) return;

  const wrap = document.getElementById('bd-scenes-stack');
  if (!wrap) return;

  // Crop canvas to content area only (no empty space below)
  const contentH = Math.max(bdLayout.cursorY + 20, 100); // virtual content height
  const cropH = Math.round(contentH * bd.scale); // pixel height to capture
  const canvasW = bd.canvas.width;
  const actualCropH = Math.min(cropH * bd.DPR, bd.canvas.height);

  // Create a cropped canvas for the snapshot
  let dataUrl;
  try {
    const cropCanvas = document.createElement('canvas');
    cropCanvas.width = canvasW;
    cropCanvas.height = actualCropH;
    const cropCtx = cropCanvas.getContext('2d');
    cropCtx.drawImage(bd.canvas, 0, 0, canvasW, actualCropH, 0, 0, canvasW, actualCropH);
    dataUrl = cropCanvas.toDataURL('image/jpeg', 0.92);
  } catch (e) {
    console.warn('[Snapshot] Failed to capture canvas:', e.message);
    return;
  }

  const captureW = parseFloat(bd.canvas.style.width) || bd.canvas.clientWidth;
  const captureScale = bd.scale;

  // Create snapshot container with EXPLICIT aspect ratio so height is deterministic
  const sceneDiv = document.createElement('div');
  sceneDiv.className = 'bd-scene-snapshot';
  sceneDiv.style.cssText = `position:relative;width:100%;`;
  sceneDiv.dataset.sceneIndex = _sceneSnapshots.length;

  const img = document.createElement('img');
  img.src = dataUrl;
  // Explicit aspect-ratio prevents browser rounding drift across scenes
  const aspectRatio = canvasW / actualCropH;
  img.style.cssText = `width:100%;display:block;aspect-ratio:${aspectRatio.toFixed(6)};`;
  sceneDiv.appendChild(img);

  // MOVE animation containers into snapshot — convert positions to PERCENTAGES
  // so they scale with the container when its width changes (scrollbar, resize, zoom)
  const animLayer = document.getElementById('bd-anim-layer');
  if (animLayer && animLayer.children.length > 0) {
    const animWrap = document.createElement('div');
    animWrap.style.cssText = `position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;overflow:hidden;`;
    while (animLayer.firstChild) {
      const child = animLayer.firstChild;
      if (child.classList && child.classList.contains('bd-anim-box')) {
        // Convert fixed pixel positions → percentages of snapshot dimensions
        const pxLeft = parseFloat(child.style.left) || 0;
        const pxTop = parseFloat(child.style.top) || 0;
        const pxW = parseFloat(child.style.width) || 300;
        const pxH = parseFloat(child.style.height) || 200;
        child.style.left = (pxLeft / captureW * 100).toFixed(2) + '%';
        child.style.top = (pxTop / cropH * 100).toFixed(2) + '%';
        child.style.width = (pxW / captureW * 100).toFixed(2) + '%';
        child.style.height = (pxH / cropH * 100).toFixed(2) + '%';
        child.style.pointerEvents = 'auto';
      }
      animWrap.appendChild(child);
    }
    sceneDiv.appendChild(animWrap);
    bdActiveAnimations.forEach(entry => {
      try { entry.inst.noLoop(); } catch(e) {}
    });
  }

  // Highlight overlay for {ref:} on old scenes
  const overlay = document.createElement('div');
  overlay.className = 'bd-scene-highlight-overlay';
  overlay.style.cssText = `position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10;`;
  sceneDiv.appendChild(overlay);

  wrap.appendChild(sceneDiv);
  _sceneSnapshots.push({
    element: sceneDiv,
    width: captureW,
    height: cropH,
    scale: captureScale,
  });

  console.log(`[Snapshot] Scene ${_sceneSnapshots.length - 1} captured (${bd.canvas.style.width} × ${bd.canvas.style.height})`);

  // Clear the live canvas for the new scene
  bd.currentH = BD_INITIAL_H;
  bdResizeCanvas();
  bd.ctx.fillStyle = '#1a1d2e';
  bd.ctx.fillRect(0, 0, BD_VIRTUAL_W * bd.scale, bd.currentH * bd.scale);
  bdDrawGrid();

  // Reset layout for new scene
  bdLayoutReset();
  bdClearElementRegistry();
  // Clear active animation tracking — old entries were moved to snapshot div
  bdActiveAnimations.length = 0;
}

function bdUpdateAnimationVisibility() {
  // Pause animations not in viewport, resume ones that are.
  // Only visible animations run draw() — saves CPU after many scenes.
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap) return;
  const viewTop = wrap.scrollTop;
  const viewBottom = viewTop + wrap.clientHeight;
  const margin = 200; // keep running slightly outside viewport for smooth scroll

  for (const entry of bdActiveAnimations) {
    if (!entry.container || !entry.inst) continue;
    const rect = entry.container.getBoundingClientRect();
    const wrapRect = wrap.getBoundingClientRect();
    const elTop = rect.top - wrapRect.top + viewTop;
    const elBottom = elTop + rect.height;

    const isVisible = elBottom > (viewTop - margin) && elTop < (viewBottom + margin);

    if (isVisible && entry._paused) {
      entry.inst.loop();
      entry._paused = false;
    } else if (!isVisible && !entry._paused) {
      entry.inst.noLoop();
      entry._paused = true;
    }
  }
}

// Throttled scroll listener for animation visibility
let _animVisTimer = null;
function _onBoardScroll() {
  if (_animVisTimer) return;
  _animVisTimer = setTimeout(() => {
    _animVisTimer = null;
    bdUpdateAnimationVisibility();
  }, 200);
}

async function bdProcessQueue() {
  // Delegate all command processing to BoardEngine
  await BoardEngine.processQueue();

  const bd = state.boardDraw;

  // Voice mode: hide hand cursor when drawing queue finishes
  if (typeof voiceHideHand === 'function') voiceHideHand();

  // Board animation finished — glow the last AI message to draw student's attention
  if (!bd.cancelFlag && bd.complete && state.spotlightActive) {
    highlightLastChatMessage();
  }

  // Capture tutor-only snapshot after all commands finish (DOM-based — use html2canvas if available)
  if (!bd.cancelFlag && bd.canvas && !bd.tutorSnapshot) {
    const liveScene = document.getElementById('bd-live-scene');
    if (liveScene && typeof html2canvas !== 'undefined') {
      setTimeout(() => {
        try {
          html2canvas(liveScene, { backgroundColor: '#1a1d2e', scale: 1 }).then(canvas => {
            bd.tutorSnapshot = canvas.toDataURL('image/png');
          }).catch(() => {});
        } catch (e) {}
      }, 500);
    }
  }
}

function bdEnqueueCommand(cmd) {
  BoardEngine.queueCommand(cmd);
}

function bdProcessStreaming(fullText) {
  const bd = state.boardDraw;
  if (bd.dismissed) return;
  if (!bd.active) {
    const m = fullText.match(/<teaching-board-draw(?:-resume)?([^>]*)>/);
    if (!m) return;
    // Parse clear attribute (defaults to true)
    const attrStr = m[1] || '';
    const clearMatch = attrStr.match(/clear\s*=\s*["']?(false|true)["']?/);
    bd.clearBoard = clearMatch ? clearMatch[1] !== 'false' : true;

    // If board already exists and should clear, reset command state (but keep DOM content)
    if (bd.active && bd.clearBoard) {
      BoardEngine.cancel();
      bd.cancelFlag = false;
      bd.commandQueue = [];
      bd.isProcessing = false;
      bd.tutorSnapshot = null;
    }

    // Open the board panel if not already open
    if (!bd.active) {
      const titleMatch = attrStr.match(/title\s*=\s*["']([^"']*)["']/);
      let streamTitle = titleMatch ? titleMatch[1] : 'Board';
      // Fix unicode escapes in title
      if (streamTitle.includes('\\u')) {
        streamTitle = streamTitle.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
      }
      openBoardDrawSpotlight(streamTitle, null, { clear: true, skipReference: true });
    }
    bd.active = true;
    bd._streamingHandled = true;
    bd.dismissed = false;
    // Reset cancel flag in case a previous stop left it on
    if (typeof BoardEngine !== 'undefined' && BoardEngine.state) {
      BoardEngine.state.cancelFlag = false;
    }
    bd.contentStartIdx = m.index + m[0].length;
    bd.processedLines = 0;
    bd.complete = false;
    bd.commandQueue = [];
    bd.isProcessing = false;
    bd.cancelFlag = false;
  }
  // Match both </teaching-board-draw> and </teaching-board-draw-resume>
  let closeIdx = fullText.indexOf('</teaching-board-draw>', bd.contentStartIdx);
  const closeIdx2 = fullText.indexOf('</teaching-board-draw-resume>', bd.contentStartIdx);
  if (closeIdx < 0 || (closeIdx2 >= 0 && closeIdx2 < closeIdx)) closeIdx = closeIdx2;
  const end = closeIdx >= 0 ? closeIdx : fullText.length;
  const lines = fullText.slice(bd.contentStartIdx, end).split('\n');
  const count = closeIdx >= 0 ? lines.length : Math.max(0, lines.length - 1);
  for (let i = bd.processedLines; i < count; i++) {
    const ln = lines[i].trim();
    if (!ln) continue;
    // Skip voice beat tags — they're handled by the voice scene parser, not JSONL
    if (ln.startsWith('<vb') || ln.startsWith('</vb') || ln.startsWith('<teaching-voice')) continue;
    try {
      const cmd = JSON.parse(ln);
      // Fix double-escaped unicode (LLM sometimes outputs \\u0027 instead of ')
      if (cmd.text && cmd.text.includes('\\u')) {
        cmd.text = cmd.text.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
      }
      if (cmd.note && cmd.note.includes('\\u')) {
        cmd.note = cmd.note.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
      }
      BoardEngine.queueCommand(cmd);
    } catch (e) {
      if (ln.includes('"animation"') || ln.includes('"cmd":"animation"')) {
        console.warn('Board: failed to parse animation JSONL, will retry on completion.\nLine:', ln.slice(0, 300), '\nError:', e.message);
        if (!bd._pendingAnimLines) bd._pendingAnimLines = [];
        bd._pendingAnimLines.push(ln);
      }
    }
  }
  bd.processedLines = count;
  if (closeIdx >= 0) {
    bd.complete = true;
    bd.rawContent = fullText.slice(bd.contentStartIdx, closeIdx);
    // Re-parse: find animation commands that may have been split across lines
    // (AI sometimes puts newlines inside the "code" field, breaking line-by-line parse)
    bdRecoverMissedAnimations(bd);
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
  state.spotlightInfo = { type: 'widget', title, widgetCode, assetId: options.assetId || null };

  // Reset widget bridge state for new iframe
  state.widget.ready = false;
  state.widget.liveState = {};

  if (!options.skipReference) {
    const refTag = { name: 'teaching-widget', attrs: { title }, _widgetCode: widgetCode };
    appendSpotlightReference('widget', title, refTag);
  }
}

function renderWidgetIframe(container, widgetCode, title) {
  hideBoardLoadingSkeleton();
  // Inject Capacity Widget Bridge into every widget
  const bridgeScript = `<script>
// Capacity Widget Bridge
window.addEventListener('message', function(ev) {
  if (ev.data && ev.data.type === 'capacity-widget-params') {
    if (typeof onParamUpdate === 'function') onParamUpdate(ev.data.payload);
  }
});
window._capacityReport = function(key, value) {
  parent.postMessage({ type: 'capacity-widget-state', payload: { key: key, value: value } }, '*');
};
parent.postMessage({ type: 'capacity-widget-ready' }, '*');
<\/script>`;

  const injectedCode = bridgeScript + widgetCode;
  const fullDoc = injectedCode.includes('<html') ? injectedCode :
    `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>${injectedCode}</body></html>`;

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
    } else if (d.type === 'capacity-widget-ready') {
      state.widget.ready = true;
      // Flush any pending params
      if (state.widget.pendingParams) {
        const pending = state.widget.pendingParams;
        state.widget.pendingParams = null;
        sendWidgetParams(pending);
      }
    } else if (d.type === 'capacity-widget-state') {
      if (d.payload && d.payload.key !== undefined) {
        if (!state.widget.liveState) state.widget.liveState = {};
        state.widget.liveState[d.payload.key] = d.payload.value;
      }
    }
  };
  window.addEventListener('message', handler);
  iframe._bridgeCleanup = () => window.removeEventListener('message', handler);
}

function handleWidgetUpdate(tag) {
  const assetId = tag.attrs.asset;
  const paramsStr = tag.attrs.params || '{}';
  let params;
  try { params = JSON.parse(paramsStr); } catch { return; }

  // If this widget is currently open, send params directly
  if (state.spotlightInfo?.assetId === assetId) {
    sendWidgetParams(params);
    return;
  }

  // Otherwise, find in history and reopen it
  const entry = state.spotlightHistory.find(h => h.id === assetId && h.type === 'widget');
  if (!entry) return; // asset not found

  // Reopen the widget from history, then send params
  state.widget.pendingParams = params;
  openWidgetSpotlight(entry.title, entry.widgetCode, false, { assetId: assetId });
}

function sendWidgetParams(params) {
  const iframe = document.querySelector('#spotlight-content iframe');
  if (!iframe) return;
  if (state.widget.ready) {
    iframe.contentWindow.postMessage({ type: 'capacity-widget-params', payload: params }, '*');
  } else {
    state.widget.pendingParams = params;
  }
}

function handleBoardDrawResume(tag) {
  const assetId = tag.attrs.asset;
  const title = tag.attrs.title || 'Board';
  const newContent = (tag.content || '').trim();

  const entry = state.spotlightHistory.find(h => h.id === assetId && h.type === 'board-draw');
  if (!entry || !entry.boardDrawContent) {
    // Fallback: regular board-draw
    openBoardDrawSpotlight(title, newContent || null, { clear: true });
    if (newContent) {
      state.boardDraw.commandQueue = [];
      for (const ln of newContent.split('\n')) {
        const t = ln.trim();
        if (t) try { state.boardDraw.commandQueue.push(JSON.parse(t)); } catch {}
      }
    }
    state.boardDraw.active = true;
    return;
  }

  const originalCmds = [];
  for (const ln of entry.boardDrawContent.split('\n')) {
    const t = ln.trim();
    if (t) try { originalCmds.push(JSON.parse(t)); } catch {}
  }
  const newCmds = [];
  for (const ln of newContent.split('\n')) {
    const t = ln.trim();
    if (t) try { newCmds.push(JSON.parse(t)); } catch {}
  }

  const combinedContent = entry.boardDrawContent + (newContent ? '\n' + newContent : '');
  openBoardDrawSpotlight(title, combinedContent, { clear: true });

  state.boardDraw.commandQueue = [];
  state.boardDraw._instantReplayCount = originalCmds.length;
  for (const cmd of originalCmds) state.boardDraw.commandQueue.push(cmd);
  for (const cmd of newCmds) state.boardDraw.commandQueue.push(cmd);
  state.boardDraw.active = true;
}

function openBoardDrawSpotlight(title, rawContent, options = {}) {
  const shouldClear = options.clear !== false; // default: true

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

  // If board-draw is already open, KEEP the content — just update title
  if (state.spotlightActive && state.spotlightInfo?.type === 'board-draw') {
    if (titleEl) titleEl.textContent = title;
    state.spotlightInfo.title = title;
    if (rawContent) {
      state.boardDraw.rawContent = (state.boardDraw.rawContent || '') + '\n' + rawContent;
    }
    if (!options.skipReference) {
      const refTag = { name: 'teaching-board-draw', attrs: { title } };
      if (state.boardDraw.rawContent) refTag._boardDrawContent = state.boardDraw.rawContent;
      appendSpotlightReference('board-draw', title, refTag);
    }
    return; // Keep existing board — scenes stack via snapshotScene, never clear
  }

  // Different spotlight type was open — close it first
  if (state.spotlightActive) {
    if (state.activeSimulation) { stopSimBridge(); state.activeSimulation = null; state.simulationLiveState = null; }
    if (state.spotlightInfo?.type === 'notebook') {
      saveNotebookStepsToHistory();
      if (state.notebookCleanup) { state.notebookCleanup(); state.notebookCleanup = null; }
      state.notebookSteps = [];
    }
    // Don't call bdCleanup for board-draw — we never reach here for board-draw
    content.innerHTML = '';
  }

  // Store raw JSONL content AFTER cleanup (bdCleanup wipes rawContent)
  if (rawContent) state.boardDraw.rawContent = rawContent;
  // Reset dismissed flag so next streaming can activate (bdCleanup sets it true)
  state.boardDraw.dismissed = false;

  if (titleEl) titleEl.textContent = title;
  if (typeBadge) { typeBadge.textContent = 'Board'; typeBadge.setAttribute('data-type', 'board-draw'); typeBadge.style.display = ''; }

  // Hide empty state
  const emptyState = document.getElementById('board-empty-state');
  if (emptyState) emptyState.style.display = 'none';

  content.innerHTML = `
    <div class="bd-container" id="bd-container">
      <div class="bd-toolbar" id="bd-toolbar">
        <button class="bd-tool-btn" data-color="#22ee66" title="Green pen">
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
        <span class="bd-toolbar-divider"></span>
        <button class="bd-tool-btn" onclick="bdZoomOut()" title="Zoom out (Ctrl+-)">&#8722;</button>
        <button class="bd-tool-btn" onclick="bdZoomReset()" title="Reset zoom (Ctrl+0)" id="bd-zoom-level" style="min-width:36px;font-size:10px;text-align:center">100%</button>
        <button class="bd-tool-btn" onclick="bdZoomIn()" title="Zoom in (Ctrl++)">&#43;</button>
      </div>
      <div class="bd-canvas-wrap" id="bd-canvas-wrap">
        <div id="bd-board-content">
          <div id="bd-scenes-stack"></div>
          <div id="bd-live-scene" class="bd-scene">
            <div class="bd-grid-bg"></div>
          </div>
        </div>
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

  // Init board synchronously — DOM is already created above.
  // DO NOT use setTimeout here: board commands from the tutor can arrive within
  // milliseconds of session start. Any delay causes commands to queue before
  // liveScene exists, silently dropping the first draw operations.
  requestAnimationFrame(() => {
    hideBoardLoadingSkeleton();
    BoardEngine.init(state.apiUrl);

    // Create a transparent canvas overlay for student drawing on top of the DOM board
    const canvasWrap = document.getElementById('bd-canvas-wrap');
    let drawCanvas = document.getElementById('bd-student-canvas');
    if (!drawCanvas && canvasWrap) {
      drawCanvas = document.createElement('canvas');
      drawCanvas.id = 'bd-student-canvas';
      drawCanvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10;';
      canvasWrap.style.position = 'relative';
      canvasWrap.appendChild(drawCanvas);
      // Size the canvas to match the wrap
      const rect = canvasWrap.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 3);
      drawCanvas.width = rect.width * dpr;
      drawCanvas.height = Math.max(rect.height, 800) * dpr;
      drawCanvas.style.width = rect.width + 'px';
      drawCanvas.style.height = Math.max(rect.height, 800) + 'px';
    }

    // Set up drawing context for student drawing
    state.boardDraw.canvas = drawCanvas || document.getElementById('bd-live-scene');
    state.boardDraw.ctx = drawCanvas ? drawCanvas.getContext('2d', { willReadFrequently: true }) : null;
    state.boardDraw.DPR = Math.min(window.devicePixelRatio || 1, 3);
    state.boardDraw.studentColor = '#22ee66';
    state.boardDraw.studentStrokeW = 2.5;
    state.boardDraw.active = true;

    // Init student drawing + toolbar if canvas exists
    if (drawCanvas) {
      bdInitStudentDrawing(drawCanvas);
      bdInitToolbar();
    }
    const v = document.getElementById('bd-voice-text');
    state.boardDraw.voiceEl = v;
    // Ensure new board starts scrolled to the top
    const initWrap = document.getElementById('bd-canvas-wrap');
    if (initWrap) initWrap.scrollTop = 0;

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
  });
}

function bdCleanup() {
  const bd = state.boardDraw;
  bd.cancelFlag = true;
  bd.active = false;
  bd.dismissed = true;
  bd._streamingHandled = false;
  bd.commandQueue = [];
  bd.isProcessing = false;
  BoardEngine.cleanup();
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
  bd._animErrors = null;
  bd._retryInFlight = false;
  bd._pendingAnimLines = null;
}

function bdReplayCommandsInstant(cmds) {
  const bd = state.boardDraw;
  if (!bd.ctx) return;
  const s = bd.scale;
  const fontScale = bdGetFontScale();
  const ctx = bd.ctx;

  // Pre-expand canvas to fit all commands so nothing gets clipped
  let maxY = 0;
  for (const cmd of cmds) {
    const y = cmd.y || cmd.y1 || cmd.cy || 0;
    const h = cmd.h || (typeof cmd.size === 'number' ? cmd.size : null) || cmd.r || 30;
    maxY = Math.max(maxY, y + h);
    if (cmd.y2) maxY = Math.max(maxY, cmd.y2);
  }
  if (maxY > 0) bdExpandIfNeeded(maxY);

  for (const cmd of cmds) {
    if (bd.cancelFlag) return;
    if (cmd.cmd === 'voice' || cmd.cmd === 'animation') continue;
    ctx.save();
    ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
    const c = BD_COLORS[cmd.color] || cmd.color || BD_COLORS.white;
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
      const sz = bdResolveSize(cmd.size || 18) * fontScale;
      ctx.fillStyle = c;
      ctx.font = `${cmd.style || ''} ${sz}px 'Caveat', cursive`.trim();
      ctx.fillText(cmd.text, cmd.x * s, cmd.y * s);
    } else if (cmd.cmd === 'latex') {
      const sz = bdResolveSize(cmd.size || 16) * fontScale;
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
      const fs = (cmd.size || 22) * fontScale;
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
        const bfs = (cmd.size||18) * fontScale;
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
    } else if (cmd.cmd === 'path' && cmd.points) {
      // Smooth path through points using quadratic curves
      const pts = cmd.points; // [[x,y], [x,y], ...]
      if (pts.length >= 2) {
        ctx.beginPath();
        ctx.moveTo(pts[0][0] * s, pts[0][1] * s);
        if (pts.length === 2) {
          ctx.lineTo(pts[1][0] * s, pts[1][1] * s);
        } else if (cmd.smooth !== false) {
          // Smooth curve: use midpoints as control points
          for (let i = 0; i < pts.length - 1; i++) {
            const xm = (pts[i][0] + pts[i+1][0]) / 2;
            const ym = (pts[i][1] + pts[i+1][1]) / 2;
            if (i === 0) {
              ctx.lineTo(xm * s, ym * s);
            } else if (i === pts.length - 2) {
              ctx.quadraticCurveTo(pts[i][0] * s, pts[i][1] * s, pts[i+1][0] * s, pts[i+1][1] * s);
            } else {
              ctx.quadraticCurveTo(pts[i][0] * s, pts[i][1] * s, xm * s, ym * s);
            }
          }
        } else {
          // Straight line segments
          for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0] * s, pts[i][1] * s);
        }
        if (cmd.closed) ctx.closePath();
        if (cmd.fill) { ctx.fillStyle = cmd.fill; ctx.fill(); }
        ctx.stroke();
      }
    } else if (cmd.cmd === 'graph') {
      // Draw axes + function curve for physics graphs
      const gx = (cmd.x || 50) * s, gy = (cmd.y || 200) * s;
      const gw = (cmd.w || 300) * s, gh = (cmd.h || 150) * s;
      const axisColor = cmd.axisColor || 'rgba(255,255,255,0.4)';
      // Draw axes
      ctx.strokeStyle = axisColor; ctx.lineWidth = 1.5 * s;
      ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx + gw, gy); ctx.stroke(); // x-axis
      ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx, gy - gh); ctx.stroke(); // y-axis
      // Arrowheads
      const ah = 6 * s;
      ctx.beginPath(); ctx.moveTo(gx + gw, gy); ctx.lineTo(gx + gw - ah, gy - ah/2); ctx.lineTo(gx + gw - ah, gy + ah/2); ctx.closePath(); ctx.fillStyle = axisColor; ctx.fill();
      ctx.beginPath(); ctx.moveTo(gx, gy - gh); ctx.lineTo(gx - ah/2, gy - gh + ah); ctx.lineTo(gx + ah/2, gy - gh + ah); ctx.closePath(); ctx.fill();
      // Axis labels
      if (cmd.xlabel) { ctx.fillStyle = cmd.labelColor || 'rgba(255,255,255,0.6)'; ctx.font = (14 * s) + 'px Inter, sans-serif'; ctx.textAlign = 'center'; ctx.fillText(cmd.xlabel, gx + gw/2, gy + 22*s); }
      if (cmd.ylabel) { ctx.save(); ctx.fillStyle = cmd.labelColor || 'rgba(255,255,255,0.6)'; ctx.font = (14 * s) + 'px Inter, sans-serif'; ctx.translate(gx - 18*s, gy - gh/2); ctx.rotate(-Math.PI/2); ctx.textAlign = 'center'; ctx.fillText(cmd.ylabel, 0, 0); ctx.restore(); }
      // Plot curves
      const curves = cmd.curves || (cmd.points ? [{ points: cmd.points, color: cmd.color }] : []);
      for (const curve of curves) {
        const cpts = curve.points || [];
        if (cpts.length < 2) continue;
        ctx.strokeStyle = curve.color || c;
        ctx.lineWidth = (curve.w || cmd.w_line || 2.5) * s;
        bdChalkStyle(curve.color || c, ctx.lineWidth / s);
        ctx.beginPath();
        // Map normalized [0-1] coords to graph area
        const mapX = v => gx + v * gw;
        const mapY = v => gy - v * gh;
        ctx.moveTo(mapX(cpts[0][0]), mapY(cpts[0][1]));
        for (let i = 0; i < cpts.length - 1; i++) {
          const xm = (cpts[i][0] + cpts[i+1][0]) / 2;
          const ym = (cpts[i][1] + cpts[i+1][1]) / 2;
          if (i === cpts.length - 2) {
            ctx.quadraticCurveTo(mapX(cpts[i][0]), mapY(cpts[i][1]), mapX(cpts[i+1][0]), mapY(cpts[i+1][1]));
          } else {
            ctx.quadraticCurveTo(mapX(cpts[i][0]), mapY(cpts[i][1]), mapX(xm), mapY(ym));
          }
        }
        ctx.stroke();
        bdClearShadow();
      }
    }
    ctx.restore();
  }
}

function bdCaptureBoard() {
  // DOM board capture — use html2canvas to screenshot the board content
  const boardContent = document.getElementById('bd-board-content');
  if (!boardContent) return null;

  // html2canvas is async, but this function is called sync.
  // Use a synchronous fallback: render to an offscreen clone.
  if (typeof html2canvas === 'undefined') return null;

  // Return a promise-like: caller (bdCaptureAndSend) will be updated to handle async
  let result = null;
  try {
    // Create a temporary clone to capture
    const tempCanvas = document.createElement('canvas');
    const rect = boardContent.getBoundingClientRect();
    tempCanvas.width = Math.round(rect.width);
    tempCanvas.height = Math.round(rect.height);
    // html2canvas is loaded — use it asynchronously
    // Store the promise on state for the caller to await
    state.boardDraw._capturePromise = html2canvas(boardContent, {
      backgroundColor: '#1a1d2e',
      scale: Math.min(2, 800 / rect.width),
      useCORS: true,
    }).then(canvas => {
      return canvas.toDataURL('image/png');
    }).catch(() => null);
  } catch (e) {
    return null;
  }
  return null; // async result via state.boardDraw._capturePromise
}

async function bdCaptureAndSend() {
  // Trigger async capture
  bdCaptureBoard();
  const capturePromise = state.boardDraw._capturePromise;
  if (!capturePromise) return;

  const combinedUrl = await capturePromise;
  state.boardDraw._capturePromise = null;
  if (!combinedUrl) return;

  const combinedBase64 = combinedUrl.split(',')[1];
  renderUserMessage('[Board drawing sent to tutor]');

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
    // Use cached tutor snapshot if available (DOM board — async capture)
    const bd = state.boardDraw;
    if (bd.tutorSnapshot) {
      return {
        type: 'board-draw',
        title: info.title,
        base64: bd.tutorSnapshot.split(',')[1],
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
  window.addEventListener('beforeunload', () => cleanupActiveSession());

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

// ═══════════════════════════════════════════════════════════
// Module 23: Voice Mode — TTS, Hand Cursor, Board Interaction
// ═══════════════════════════════════════════════════════════

const ELEVENLABS_VOICE_ID = 'UgBBYS2sOqTuMpoF3BR0';
const ELEVENLABS_MODEL_DIALOGUE = 'eleven_v3'; // Text to Dialogue — natural emotion tags
const ELEVENLABS_MODEL_FALLBACK = 'eleven_turbo_v2_5'; // Fallback streaming TTS

// ── Voice mode is the default and only mode ────

// Called once when session starts — always voice mode
function applyTeachingMode() {
  state.teachingMode = 'voice';
  const mainLayout = $('#main-layout');
  const subtitleBar = $('#voice-subtitle-bar');
  const voiceInd = $('#voice-indicator');
  const speedWrap = $('#speed-wrap');
  const micFloat = $('#voice-mic-float');

  mainLayout?.classList.add('voice-mode');
  subtitleBar?.classList.remove('hidden');
  voiceInd?.classList.remove('hidden');
  speedWrap?.classList.remove('hidden');
  micFloat?.classList.remove('hidden');
}

// ── ElevenLabs Streaming TTS (chunked playback for low latency) ──

// Stop whichever TTS playback source is active
function voiceStopCurrent() {
  if (state.voiceCurrentSrc) {
    try { state.voiceCurrentSrc.disconnect(); } catch {}
    try { state.voiceCurrentSrc.stop(); } catch {}
    state.voiceCurrentSrc = null;
  }
  if (state.voiceCurrentAudio) {
    try { state.voiceCurrentAudio.pause(); } catch {}
    try { state.voiceCurrentAudio.src = ''; state.voiceCurrentAudio.load(); } catch {} // release media resources
    state.voiceCurrentAudio = null;
  }
}

function voiceCleanText(text) {
  return text
    .replace(/\{ref:[^}]+\}/g, '')  // strip {ref:elementId} markers
    .replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1').replace(/<[^>]+>/g, '')
    .replace(/\$\$[\s\S]+?\$\$/g, '').replace(/\$(.+?)\$/g, '$1')
    .replace(/\[[^\]]*\]\s*/g, '').trim();
}

// Pre-fetch TTS response without consuming the body — used for lookahead prefetching
async function voiceFetchTTS(text) {
  if (state._stopRequested) return null; // Don't fetch TTS after stop
  const clean = voiceCleanText(text);
  if (!clean || clean.length < 3) return null;
  // Truncate to 490 chars to stay within TTS 500 char limit
  const truncated = clean.length > 490 ? clean.slice(0, 487) + '...' : clean;
  try {
    const resp = await fetch(`${state.apiUrl}/api/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
      body: JSON.stringify({ text: truncated, voice_id: ELEVENLABS_VOICE_ID }),
    });
    return resp.ok ? resp : null;
  } catch { return null; }
}

async function voiceSpeak(text, prefetchedResp) {
  if (state._stopRequested || state.teachingMode !== 'voice' || !text.trim()) return;

  if (!state.voiceAudioCtx) state.voiceAudioCtx = new AudioContext({ sampleRate: 44100 });
  if (state.voiceAudioCtx.state === 'suspended') await state.voiceAudioCtx.resume();
  voiceStopCurrent();

  const cleanText = voiceCleanText(text);
  if (!cleanText || cleanText.length < 3) return;

  try {
    let resp = prefetchedResp;
    if (!resp) {
      resp = await fetch(`${state.apiUrl}/api/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
        body: JSON.stringify({ text: cleanText, voice_id: ELEVENLABS_VOICE_ID }),
      });
    }

    if (!resp.ok) {
      console.warn('TTS error:', resp.status);
      await voiceSleep(estimateVoiceDuration(cleanText) * 1000);
      return;
    }

    // Streaming playback via MediaSource (start playing from first chunk)
    // Falls back to buffered AudioContext decode if MSE unsupported
    const canStreamMSE = typeof MediaSource !== 'undefined'
      && MediaSource.isTypeSupported('audio/mpeg');

    if (canStreamMSE) {
      try {
        await voiceSpeakMSE(resp);
        return;
      } catch (e) {
        console.warn('MSE streaming failed, trying buffered:', e);
        // resp body consumed — need to re-fetch
        resp = await fetch(`${state.apiUrl}/api/tts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...AuthManager.authHeaders() },
          body: JSON.stringify({ text: cleanText, voice_id: ELEVENLABS_VOICE_ID }),
        });
        if (!resp.ok) { await voiceSleep(estimateVoiceDuration(cleanText) * 1000); return; }
      }
    }

    await voiceSpeakBuffered(resp);
  } catch (e) {
    console.warn('TTS failed:', e);
    await voiceSleep(estimateVoiceDuration(cleanText) * 1000);
  }
}

// Streaming playback via MediaSource Extensions — starts audio from first chunk
async function voiceSpeakMSE(resp) {
  const ms = new MediaSource();
  const audio = new Audio();
  audio.playbackRate = state.voiceSpeed;
  const objUrl = URL.createObjectURL(ms);
  audio.src = objUrl;

  await new Promise((res, rej) => {
    ms.addEventListener('sourceopen', res, { once: true });
    setTimeout(() => rej(new Error('MSE sourceopen timeout')), 5000);
  });

  const sb = ms.addSourceBuffer('audio/mpeg');
  const reader = resp.body.getReader();
  let started = false;

  const append = (chunk) => new Promise((res, rej) => {
    const timeout = setTimeout(() => res(), 5000); // 5s append timeout
    const done = () => { clearTimeout(timeout); res(); };
    if (sb.updating) {
      sb.addEventListener('updateend', () => {
        try { sb.appendBuffer(chunk); } catch (e) { clearTimeout(timeout); rej(e); return; }
        sb.addEventListener('updateend', done, { once: true });
      }, { once: true });
    } else {
      try { sb.appendBuffer(chunk); } catch (e) { clearTimeout(timeout); rej(e); return; }
      sb.addEventListener('updateend', done, { once: true });
    }
  });

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      await append(value);
      if (!started) {
        started = true;
        await audio.play();
        state.voiceCurrentAudio = audio;
      }
    }

    if (sb.updating) await new Promise(r => sb.addEventListener('updateend', r, { once: true }));
    if (ms.readyState === 'open') ms.endOfStream();

    if (!started) return; // no data

    // Wait for playback to finish — cap timeout based on actual duration or 10s max
    if (!audio.ended) {
      await new Promise(r => {
        audio.addEventListener('ended', r, { once: true });
        const dur = audio.duration;
        const safeMs = (isFinite(dur) && dur > 0)
          ? (dur / state.voiceSpeed) * 1000 + 500
          : 10000; // 10s fallback when duration unknown
        setTimeout(r, safeMs);
      });
    }
  } finally {
    state.voiceCurrentAudio = null;
    URL.revokeObjectURL(objUrl);
  }
}

// Buffered playback via AudioContext — fallback for browsers without MSE
async function voiceSpeakBuffered(resp) {
  const reader = resp.body.getReader();
  const chunks = [];
  while (true) { const { done, value } = await reader.read(); if (done) break; chunks.push(value); }

  const buf = await new Blob(chunks, { type: 'audio/mpeg' }).arrayBuffer();
  const decoded = await state.voiceAudioCtx.decodeAudioData(buf);
  const src = state.voiceAudioCtx.createBufferSource();
  src.buffer = decoded;
  src.playbackRate.value = state.voiceSpeed;
  src.connect(state.voiceAudioCtx.destination);
  src.start();
  state.voiceCurrentSrc = src;

  await new Promise(r => {
    let ended = false;
    src.onended = () => { if (!ended) { ended = true; r(); } };
    setTimeout(() => { if (!ended) { ended = true; r(); } }, (decoded.duration / state.voiceSpeed) * 1000 + 300);
  });
}

// TTS is now proxied through backend — no API key on frontend

function estimateVoiceDuration(text) {
  return text.split(/\s+/).length / 2.8 + 0.2;
}

// ── Subtitle display ────────────────────────────────────────

function voiceShowSubtitle(text) {
  const el = $('#voice-subtitle-text');
  if (!el) return;
  let display = text
    .replace(/\{ref:[^}]+\}/g, '')  // strip {ref:elementId} markers
    .replace(/\[[^\]]*\]\s*/g, '')  // strip emotion tags like [excited], [thoughtfully]
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<em>$1</em>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\$[^$]+\$/g, '')
    .replace(/\$\$[\s\S]+?\$\$/g, '')
    .trim();
  if (!display) return;
  el.innerHTML = display;
  // Ensure subtitle bar is visible
  const bar = $('#voice-subtitle-bar');
  if (bar) bar.classList.remove('hidden');
}

function voiceHideSubtitle() {
  const el = $('#voice-subtitle-text');
  if (el) el.innerHTML = '';
}

// ── Voice indicator ─────────────────────────────────────────

function voiceShowIndicator(mode) {
  const el = $('#voice-indicator');
  const label = $('#voice-indicator-label');
  const bar = $('#voice-bar-main');
  if (!el) return;
  el.classList.remove('hidden', 'speaking', 'listening');
  el.classList.add(mode);
  if (label) label.textContent = mode === 'speaking' ? 'Euler is speaking' : 'Listening...';
  if (bar) {
    bar.classList.remove('speaking', 'recording');
    if (mode === 'speaking') bar.classList.add('speaking');
    if (mode === 'listening') bar.classList.add('recording');
  }
}

function voiceHideIndicator() {
  const el = $('#voice-indicator');
  const bar = $('#voice-bar-main');
  if (el) { el.classList.remove('speaking', 'listening'); el.classList.add('hidden'); }
  if (bar) bar.classList.remove('speaking', 'recording');
}

// ── Hand cursor ─────────────────────────────────────────────

function voiceMoveHand(x, y, writing) {
  if (state.teachingMode !== 'voice') return;
  const hand = $('#voice-hand-cursor');
  if (!hand) return;

  // Board draw commands use virtual coordinates (0-800 for x, dynamic height for y).
  // The canvas is displayed in #spotlight-content. Map virtual → screen.
  const boardContent = $('#spotlight-content');
  if (!boardContent) return;
  const rect = boardContent.getBoundingClientRect();
  const bd = state.boardDraw;
  if (!bd.canvas) return;

  // Virtual → screen: the canvas CSS size maps BD_VIRTUAL_W to rect.width
  const virtualW = 800; // BD_VIRTUAL_W
  const virtualH = bd.currentH || 500;
  const screenX = rect.left + (x / virtualW) * rect.width;
  const screenY = rect.top + (y / virtualH) * rect.height;

  hand.style.left = screenX + 'px';
  hand.style.top = screenY + 'px';
  hand.classList.remove('hidden');
  hand.classList.toggle('writing', !!writing);
  state.voiceHandVisible = true;
}

function voiceTapAt(x, y) {
  if (state.teachingMode !== 'voice') return;
  voiceMoveHand(x, y, false);

  const hand = $('#voice-hand-cursor');
  if (hand) {
    hand.classList.add('tapping');
    setTimeout(() => hand.classList.remove('tapping'), 350);
  }

  // Add tap ring on the board (using virtual coord → percentage of content area)
  const boardContent = $('#spotlight-content');
  if (!boardContent) return;
  const bd = state.boardDraw;
  const virtualW = 800;
  const virtualH = bd.currentH || 500;

  const ring = document.createElement('div');
  ring.className = 'voice-tap-ring';
  ring.style.left = ((x / virtualW) * 100) + '%';
  ring.style.top = ((y / virtualH) * 100) + '%';
  boardContent.style.position = 'relative';
  boardContent.appendChild(ring);
  requestAnimationFrame(() => ring.classList.add('pop'));
  setTimeout(() => ring.remove(), 450);
}

function voiceHideHand() {
  const hand = $('#voice-hand-cursor');
  if (hand) hand.classList.add('hidden');
  state.voiceHandVisible = false;
}

// ── Board question input (voice mode) ───────────────────────

function voiceShowBoardQuestion(questionText) {
  const isGeneric = !questionText || questionText === 'Type your response...';

  if (!isGeneric) {
    let rendered = questionText;
    if (typeof renderLatex === 'function') rendered = renderLatex(rendered);
    rendered = rendered.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>');
    voiceShowSubtitle(rendered);
  }

  // Focus the unified input bar — but NEVER clear text the student is typing
  const field = $('#voice-bar-input');
  if (field) {
    field.placeholder = isGeneric ? 'Type your response...' : 'Your answer...';
    // Only clear and focus if the student hasn't typed anything
    if (!field.value.trim()) {
      field.value = '';
      if (document.activeElement !== field) field.focus();
    }
  }
}

function voiceHideBoardQuestion() {
  const field = $('#voice-bar-input');
  if (field) {
    field.placeholder = 'Type your response...';
    // Don't clear if student has typed something
    if (!field.value.trim()) {
      field.value = '';
    }
  }
}

// ── Speed control ───────────────────────────────────────────

function toggleSpeedMenu() {
  const menu = $('#speed-menu');
  if (menu) menu.classList.toggle('hidden');
}

function pickSpeed(s) {
  state.voiceSpeed = s;
  const valEl = $('#speed-val');
  if (valEl) valEl.textContent = s + 'x';
  // Update active state
  $$('#speed-menu button').forEach(b => {
    b.classList.toggle('active', b.textContent.trim() === s + 'x');
  });
  const menu = $('#speed-menu');
  if (menu) menu.classList.add('hidden');
  // Adjust currently playing audio
  if (state.voiceCurrentSrc) state.voiceCurrentSrc.playbackRate.value = s;
  if (state.voiceCurrentAudio) state.voiceCurrentAudio.playbackRate = s;
}

// Close speed menu on outside click
document.addEventListener('click', (e) => {
  if (!e.target.closest('.speed-wrap')) {
    const menu = $('#speed-menu');
    if (menu) menu.classList.add('hidden');
  }
});

// ── Voice Scene Parser & Executor ───────────────────────────
// Parses <teaching-voice-scene> tag into beats, executes them sequentially.

// ── Eager Beat Execution ─────────────────────────────────────
// Parses <vb /> tags as they stream in and executes them immediately.
// The existing executeVoiceScene() skips if beats were already handled.

const _eager = {
  parsedCount: 0,      // how many <vb> closing tags we've seen so far
  queue: [],            // parsed beats waiting for execution
  running: false,       // is the executor loop active
  sceneInited: false,   // has board been set up for this scene
  ttsPrefetch: null,    // prefetched TTS response for next beat
  done: false,          // scene fully executed (question reached or stream ended)
};

function _eagerReset() {
  _eager.parsedCount = 0;
  _eager.queue = [];
  _eager.running = false;
  _eager.sceneInited = false;
  _eager.ttsPrefetch = null;
  _eager.done = false;
}

function _eagerBeatWatcher(text) {
  if (_eager.done || state._stopRequested) return;

  // Only parse <vb> tags from the LAST voice scene (not previous scenes in same stream)
  const lastSceneIdx = text.lastIndexOf('<teaching-voice-scene');
  const searchText = lastSceneIdx >= 0 ? text.slice(lastSceneIdx) : text;

  // Count completed <vb ... /> tags in the current scene only
  const vbRegex = /<vb\s+[\s\S]*?\/>/g;
  let match;
  let count = 0;
  const newRawBeats = [];

  while ((match = vbRegex.exec(searchText)) !== null) {
    count++;
    if (count > _eager.parsedCount) {
      newRawBeats.push(match[0]);
    }
  }

  if (newRawBeats.length === 0) return;
  _eager.parsedCount = count;

  // Parse each new beat using the existing parser
  for (const raw of newRawBeats) {
    const m = raw.match(/<vb\s+([\s\S]*?)\/>/);
    if (!m) continue;
    const beat = _parseVoiceBeatAttrs(m[1]);
    if (beat) {
      _eager.queue.push(beat);
      console.log(`[EagerBeat] Parsed beat ${_eager.parsedCount}: ${beat.say?.slice(0, 40) || '(draw)'}`);
    }
  }

  // Init scene on first beat
  if (!_eager.sceneInited && _eager.queue.length > 0) {
    _eager.sceneInited = true;
    state._voiceSceneActive = true;

    const titleMatch = text.match(/<teaching-voice-scene[^>]*title=['"]([^'"]*)['"]/);
    const title = titleMatch ? titleMatch[1] : 'Teaching';
    _eagerInitBoard(title);

    // Mark matching topic as active in the plan sidebar (fuzzy match on title)
    _markTopicActiveByTitle(title);

    // Prefetch first beat's TTS immediately
    if (_eager.queue[0]?.say?.trim()) {
      _eager.ttsPrefetch = voiceFetchTTS(_eager.queue[0].say);
    }
  }

  // Start executor if not running
  if (!_eager.running && _eager.queue.length > 0) {
    _eager.running = true;
    _eagerExecutorLoop();
  }
}

function _markTopicActiveByTitle(sceneTitle) {
  // When a voice scene starts, mark the matching topic as active in the plan
  // This gives immediate visual feedback without waiting for advance_topic
  if (!state.plan.length || !sceneTitle) return;
  const lower = sceneTitle.toLowerCase();

  for (const sec of state.plan) {
    if (!sec.topics) continue;
    for (const t of sec.topics) {
      if (t.status === 'done') continue;
      const tLower = (t.title || '').toLowerCase();
      // Fuzzy match: scene title contains topic title or vice versa
      if (tLower && (lower.includes(tLower) || tLower.includes(lower) ||
          // Also match on key words (3+ chars)
          tLower.split(/\s+/).filter(w => w.length > 3).some(w => lower.includes(w)))) {
        // Mark previous active topics in this section as done
        for (const prev of sec.topics) {
          if (prev.status === 'active' && prev !== t) prev.status = 'done';
        }
        t.status = 'active';
        if (sec.status !== 'active') sec.status = 'active';
        updatePlanSidebar({ sections: state.plan });
        updateHeadingBar();
        return;
      }
    }
  }
}

function _eagerInitBoard(title) {
  console.log(`[EagerBeat] Scene init: "${title}"`);

  // Ensure board engine is ready to accept commands (reset cancel flag from any prior stop)
  if (typeof BoardEngine !== 'undefined' && BoardEngine.state) {
    BoardEngine.state.cancelFlag = false;
  }

  if (!state.boardDraw.active) {
    openBoardDrawSpotlight(title, null, { clear: true });
    state._voiceSceneYOffset = 0;
  } else {
    // Snapshot the current scene — DOM elements move to stack (no JPEG)
    BoardEngine.snapshotScene();

    const titleEl = $('#spotlight-title');
    if (titleEl) titleEl.textContent = title;

    state._voiceSceneYOffset = 0;

    // snapshotScene already scrolls to the new scene
    // Just reset the student scroll flag so auto-scroll resumes
    state.boardDraw._studentScrolledRecently = false;
    const wrap = document.getElementById('bd-canvas-wrap');
    if (wrap) {
      requestAnimationFrame(() => {
        // Scroll to show the new live scene near the top
        const liveScene = document.getElementById('bd-live-scene');
        if (liveScene) {
          const wrapRect = wrap.getBoundingClientRect();
          const sceneRect = liveScene.getBoundingClientRect();
          const targetTop = wrap.scrollTop + (sceneRect.top - wrapRect.top) - 20;
          wrap.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
        } else {
          wrap.scrollTo({ top: wrap.scrollHeight, behavior: 'smooth' });
        }
      });
    }
  }
}

async function _eagerExecutorLoop() {
  const _loopStart = Date.now();
  const LOOP_TIMEOUT = 120000; // 2 min max per scene execution

  while (!_eager.done) {
    // Check if stopped or timed out
    if (state._stopRequested) { _eager.done = true; break; }
    if (Date.now() - _loopStart > LOOP_TIMEOUT) {
      console.warn('[EagerBeat] Executor loop timed out after 2min — breaking');
      _eager.done = true;
      break;
    }

    if (_eager.queue.length > 0) {
      const beat = _eager.queue.shift();

      // Get prefetched TTS (may be null for first beat if not ready yet)
      let myPrefetch = null;
      if (_eager.ttsPrefetch) {
        try { myPrefetch = await _eager.ttsPrefetch; } catch(e) {}
        _eager.ttsPrefetch = null;
      }

      // Prefetch NEXT beat's TTS while this one executes
      const nextBeat = _eager.queue[0];
      if (nextBeat?.say?.trim()) {
        _eager.ttsPrefetch = voiceFetchTTS(nextBeat.say);
      }

      // Execute the beat — reuse exact same logic as executeVoiceScene
      await _eagerExecBeat(beat, myPrefetch);

      // If this was a question beat, stop
      if (beat.question) {
        _eager.done = true;
        break;
      }
    } else if (state.isStreaming) {
      // Queue empty but stream still going — wait for more beats
      await new Promise(r => setTimeout(r, 80));
    } else {
      // Stream ended and queue empty — we're done
      break;
    }

    if (state._stopRequested) { _eager.done = true; break; }
  }

  _eager.running = false;

  // If not stopped by question, hide hand and subtitle
  if (!_eager.done) {
    voiceHideHand();
    voiceHideSubtitle();
  }

  // Clean up voice scene state when stream ends naturally
  if (!state.isStreaming) {
    state._voiceSceneActive = false;
  }
}

async function _eagerExecBeat(beat, prefetchedTTS) {
  // Scroll to ref
  if (beat.scrollTo) {
    BoardEngine.scrollToElement(beat.scrollTo.replace(/^id:/, ''));
    await voiceSleep(300);
  }

  // Cursor
  executeCursor(beat.cursor, beat.draw);

  // Animation control
  if (beat.animControl) bdControlAnimation(beat.animControl);

  // Annotation
  if (beat.annotate) {
    const parts = beat.annotate.split(':');
    if (parts.length >= 3 && parts[1] === 'id') {
      voiceAnnotate(parts[0], parts.slice(2).join(':'), {
        color: beat.annotateColor || '#34d399',
        duration: beat.annotateDuration || 2000,
      });
    }
  }

  // Video
  if (beat.videoLesson) {
    renderTeachingTag({ name: 'teaching-video', attrs: { lesson: beat.videoLesson, start: beat.videoStart || '0', end: beat.videoEnd || '' }, content: '' });
    if (beat.say) await executeSay(beat.say, prefetchedTTS);
    await voiceBeatGap(beat.pause);
    return;
  }

  // Simulation
  if (beat.simulation) {
    renderTeachingTag({ name: 'teaching-simulation', attrs: { id: beat.simulation }, content: '' });
    if (beat.say) await executeSay(beat.say, prefetchedTTS);
    await voiceBeatGap(beat.pause);
    return;
  }

  // Widget
  if (beat.widgetTitle && beat.widgetCode) {
    renderTeachingTag({ name: 'teaching-widget', attrs: { title: beat.widgetTitle }, content: beat.widgetCode });
    if (beat.say) await executeSay(beat.say, prefetchedTTS);
    await voiceBeatGap(beat.pause);
    return;
  }

  // Draw + say in parallel — with timeout to prevent hangs
  const beatTimeout = 15000; // 15s max per beat
  await Promise.race([
    Promise.all([
      executeDraw(beat.draw),
      executeSay(beat.say, prefetchedTTS),
    ]),
    new Promise(r => setTimeout(r, beatTimeout)),
  ]);

  // Inter-beat gap
  if (!beat.question) {
    await voiceBeatGap(beat.pause);
  }

  // Question — show input
  if (beat.question) {
    voiceHideHand();
    const qText = beat.say || 'What do you think?';
    voiceShowBoardQuestion(typeof renderLatex === 'function' ? renderLatex(qText) : qText);
  }
}

function parseVoiceBeats(sceneContent) {
  const beats = [];
  const vbRegex = /<vb\s+([\s\S]*?)\/>/g;
  let match;
  while ((match = vbRegex.exec(sceneContent)) !== null) {
    const beat = _parseVoiceBeatAttrs(match[1]);
    if (beat) beats.push(beat);
  }
  return beats;
}

// Shared beat attribute parser — used by both eager streaming and fallback paths
function _repairDrawJSON(s) {
  // Fix common LLM JSON issues:
  // 1. Unescaped quotes inside strings (Newton's → Newton\'s)
  // 2. Truncated JSON (missing closing brace/quote)
  // 3. Smart quotes → regular quotes
  // 4. Literal newlines/tabs inside "code":"..." (animation code)
  // 5. Bad escape sequences (\n, \t used as literal chars in code strings)

  // Smart quotes
  s = s.replace(/[\u201C\u201D]/g, '"').replace(/[\u2018\u2019]/g, "'");

  // Fix animation code field — the "code":"..." value often has literal newlines
  // and unescaped characters that break JSON. Extract it, escape it, put it back.
  const codeFieldMatch = s.match(/"code"\s*:\s*"/);
  if (codeFieldMatch) {
    const codeStart = codeFieldMatch.index + codeFieldMatch[0].length;
    // Walk forward to find the closing " that ends the code value
    // Must handle escaped quotes inside the code
    let i = codeStart;
    let depth = 0;
    while (i < s.length) {
      if (s[i] === '\\' && i + 1 < s.length) { i += 2; continue; } // skip escaped chars
      if (s[i] === '"') break; // found end of code string
      i++;
    }
    if (i < s.length) {
      const codeContent = s.slice(codeStart, i);
      // Escape problematic characters inside the code string
      const escaped = codeContent
        .replace(/\\/g, '\\\\')          // backslashes
        .replace(/\n/g, '\\n')           // literal newlines
        .replace(/\r/g, '\\r')           // carriage returns
        .replace(/\t/g, '\\t')           // tabs
        .replace(/"/g, '\\"');            // unescaped quotes
      s = s.slice(0, codeStart) + escaped + s.slice(i);
    }
  }

  // Try to close unclosed strings and braces
  let inStr = false, braces = 0, lastQuote = -1;
  for (let i = 0; i < s.length; i++) {
    if (s[i] === '"' && (i === 0 || s[i-1] !== '\\')) {
      inStr = !inStr;
      if (inStr) lastQuote = i;
    }
    if (!inStr) {
      if (s[i] === '{') braces++;
      if (s[i] === '}') braces--;
    }
  }

  // If string is unclosed, close it
  if (inStr) s += '"';
  // If braces unclosed, close them
  while (braces > 0) { s += '}'; braces--; }

  // Escape unescaped single quotes inside JSON string values
  s = s.replace(/"([^"]*?)'/g, (m, pre) => `"${pre}\\u0027`);

  return s;
}

function _parseVoiceBeatAttrs(attrStr) {
    const beat = {};

    // Parse say attribute (can contain quotes, so use careful extraction)
    const sayMatch = attrStr.match(/say='([^']*)'|say="([^"]*)"/);
    if (sayMatch) beat.say = sayMatch[1] || sayMatch[2] || '';

    // Parse draw attribute (JSON string — may use single or double quotes)
    // Animation code inside draw='...' often contains single quotes, so
    // we use BRACKET MATCHING to find the JSON object boundaries.
    let drawStr = null;
    const drawStart = attrStr.indexOf('draw=');
    if (drawStart >= 0) {
      // Find the opening { after draw= (skip the quote character)
      let jsonStart = attrStr.indexOf('{', drawStart);
      if (jsonStart >= 0) {
        // Bracket-match to find the closing }
        let depth = 0, inStr = false, strChar = '', esc = false;
        let jsonEnd = -1;
        for (let di = jsonStart; di < attrStr.length; di++) {
          const ch = attrStr[di];
          if (esc) { esc = false; continue; }
          if (ch === '\\') { esc = true; continue; }
          if (inStr) { if (ch === strChar) inStr = false; continue; }
          if (ch === '"') { inStr = true; strChar = '"'; continue; }
          if (ch === '{') depth++;
          if (ch === '}') { depth--; if (depth === 0) { jsonEnd = di; break; } }
        }
        if (jsonEnd > jsonStart) {
          drawStr = attrStr.slice(jsonStart, jsonEnd + 1);
        }
      }
    }
    if (!drawStr) {
      // Fallback: simple single-quote regex for non-code commands
      const drawSingleMatch = attrStr.match(/draw='([^']*)'/);
      if (drawSingleMatch) drawStr = drawSingleMatch[1];
    }
    if (drawStr) {
      drawStr = drawStr.replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#39;/g, "'");
      try {
        const cmds = drawStr.split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
        beat.draw = cmds;
      } catch {
        try { beat.draw = [JSON.parse(drawStr)]; } catch (e) {
          // Attempt JSON repair for common LLM issues
          try { beat.draw = [JSON.parse(_repairDrawJSON(drawStr))]; } catch (e2) {
            console.warn('[VoiceScene] Failed to parse draw:', e2.message, drawStr.slice(0, 100));
            beat.draw = null;
          }
        }
      }
    }

    // Parse cursor attribute
    const cursorMatch = attrStr.match(/cursor='([^']*)'|cursor="([^"]*)"/);
    if (cursorMatch) beat.cursor = cursorMatch[1] || cursorMatch[2] || 'rest';

    // Parse pause
    const pauseMatch = attrStr.match(/pause='([^']*)'|pause="([^"]*)"/);
    if (pauseMatch) beat.pause = parseFloat(pauseMatch[1] || pauseMatch[2]) || 0;

    // Parse question flag
    if (attrStr.includes('question="true"') || attrStr.includes("question='true'")) {
      beat.question = true;
    }

    // Parse widget
    const widgetTitleMatch = attrStr.match(/widget-title='([^']*)'|widget-title="([^"]*)"/);
    if (widgetTitleMatch) beat.widgetTitle = widgetTitleMatch[1] || widgetTitleMatch[2];
    const widgetCodeMatch = attrStr.match(/widget-code='([^']*)'|widget-code="([^"]*)"/);
    if (widgetCodeMatch) beat.widgetCode = widgetCodeMatch[1] || widgetCodeMatch[2];

    // Parse simulation
    const simMatch = attrStr.match(/simulation='([^']*)'|simulation="([^"]*)"/);
    if (simMatch) beat.simulation = simMatch[1] || simMatch[2];

    // Parse video
    const videoLessonMatch = attrStr.match(/video-lesson='([^']*)'|video-lesson="([^"]*)"/);
    if (videoLessonMatch) beat.videoLesson = videoLessonMatch[1] || videoLessonMatch[2];
    const videoStartMatch = attrStr.match(/video-start='([^']*)'|video-start="([^"]*)"/);
    if (videoStartMatch) beat.videoStart = videoStartMatch[1] || videoStartMatch[2];
    const videoEndMatch = attrStr.match(/video-end='([^']*)'|video-end="([^"]*)"/);
    if (videoEndMatch) beat.videoEnd = videoEndMatch[1] || videoEndMatch[2];

    // Parse image
    const imgSrcMatch = attrStr.match(/image-src='([^']*)'|image-src="([^"]*)"/);
    if (imgSrcMatch) beat.imageSrc = imgSrcMatch[1] || imgSrcMatch[2];
    const imgCapMatch = attrStr.match(/image-caption='([^']*)'|image-caption="([^"]*)"/);
    if (imgCapMatch) beat.imageCaption = imgCapMatch[1] || imgCapMatch[2];

    // Parse anim-control
    const animCtrlMatch = attrStr.match(/anim-control='([^']*)'|anim-control="([^"]*)"/);
    if (animCtrlMatch) {
      try { beat.animControl = JSON.parse(animCtrlMatch[1] || animCtrlMatch[2]); } catch {}
    }

    // Parse clear-before
    if (attrStr.includes('clear-before="true"') || attrStr.includes("clear-before='true'")) {
      beat.clearBefore = true;
    }

    // Parse scroll-to
    const scrollMatch = attrStr.match(/scroll-to='([^']*)'|scroll-to="([^"]*)"/);
    if (scrollMatch) beat.scrollTo = scrollMatch[1] || scrollMatch[2];

    // Parse annotate — ephemeral annotation: annotate="circle:id:eq-main" or "underline:id:label" or "glow:id:anim" or "box:id:eq"
    const annotateMatch = attrStr.match(/annotate='([^']*)'|annotate="([^"]*)"/);
    if (annotateMatch) beat.annotate = annotateMatch[1] || annotateMatch[2];

    // Parse annotate-color
    const annColorMatch = attrStr.match(/annotate-color='([^']*)'|annotate-color="([^"]*)"/);
    if (annColorMatch) beat.annotateColor = annColorMatch[1] || annColorMatch[2];

    // Parse annotate-duration (ms)
    const annDurMatch = attrStr.match(/annotate-duration='([^']*)'|annotate-duration="([^"]*)"/);
    if (annDurMatch) beat.annotateDuration = parseInt(annDurMatch[1] || annDurMatch[2]) || 2000;

    return beat;
}

// Execute a voice scene — the main orchestration loop
async function executeVoiceScene(sceneTag) {
  // If eager executor already handled beats during streaming, skip
  if (_eager.parsedCount > 0) {
    console.log(`[VoiceScene] Skipping — ${_eager.parsedCount} beats already executed eagerly`);
    // Wait for eager executor to finish if still running
    while (_eager.running) await new Promise(r => setTimeout(r, 50));
    _eagerReset();
    return;
  }

  const title = sceneTag.attrs?.title || 'Teaching';
  const beats = parseVoiceBeats(sceneTag.content || '');

  if (beats.length === 0) return;

  console.log(`[VoiceScene] Starting "${title}" with ${beats.length} beats (fallback path)`);

  if (!state.boardDraw.active) {
    openBoardDrawSpotlight(title, null, { clear: true });
    state._voiceSceneYOffset = 0;
  } else {
    // Snapshot current scene — DOM move (no JPEG)
    BoardEngine.snapshotScene();

    const titleEl = $('#spotlight-title');
    if (titleEl) titleEl.textContent = title;

    state._voiceSceneYOffset = 0;

    state.boardDraw._studentScrolledRecently = false;
    const wrap = document.getElementById('bd-canvas-wrap');
    if (wrap) {
      requestAnimationFrame(() => {
        wrap.scrollTo({ top: wrap.scrollHeight, behavior: 'smooth' });
      });
    }
  }

  // Pre-fetch first beat's TTS during board setup to cut initial latency
  let prefetchedResp = null;
  if (beats[0]?.say?.trim()) {
    prefetchedResp = await voiceFetchTTS(beats[0].say);
  }

  // Execute beats sequentially — with TTS lookahead prefetching
  for (let i = 0; i < beats.length; i++) {
    const beat = beats[i];
    console.log(`[VoiceScene] Beat ${i+1}/${beats.length}:`, beat.say?.slice(0, 50) || '(draw only)');

    // Grab this beat's prefetched TTS (null if none available)
    const myPrefetch = prefetchedResp;
    prefetchedResp = null;

    // Kick off NEXT beat's TTS fetch — runs concurrently with this beat
    let nextPrefetchP = null;
    if (i + 1 < beats.length && beats[i + 1]?.say?.trim()) {
      nextPrefetchP = voiceFetchTTS(beats[i + 1].say);
    }

    // 0. clear-before now just adds a separator (continuous board, no clearing)
    if (beat.clearBefore && state.boardDraw.canvas && state.boardDraw.ctx) {
      const bd = state.boardDraw;
      const sepY = bd.currentH - 40;
      bdExpandIfNeeded(sepY + 60);
      const s = bd.scale;
      bd.ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      bd.ctx.lineWidth = 1;
      bd.ctx.beginPath();
      bd.ctx.moveTo(40 * s, sepY * s);
      bd.ctx.lineTo((BD_VIRTUAL_W - 40) * s, sepY * s);
      bd.ctx.stroke();
    }

    // 0b. Scroll to referenced element
    if (beat.scrollTo) {
      const idRef = beat.scrollTo.replace(/^id:/, '');
      BoardEngine.scrollToElement(idRef);
      await voiceSleep(300);
    }

    // 1. Position cursor (supports id: references)
    executeCursor(beat.cursor, beat.draw);

    // 2. Animation control — change params on active animation
    if (beat.animControl) {
      bdControlAnimation(beat.animControl);
    }

    // 2b. Ephemeral annotation (circle, underline, glow, box)
    if (beat.annotate) {
      const annParts = beat.annotate.split(':');
      if (annParts.length >= 3 && annParts[1] === 'id') {
        const annType = annParts[0];
        const annId = annParts.slice(2).join(':');
        voiceAnnotate(annType, annId, {
          color: beat.annotateColor || '#34d399',
          duration: beat.annotateDuration || 2000,
        });
      }
    }

    // 2c. Video — render via teaching-video tag
    if (beat.videoLesson) {
      const videoTag = {
        name: 'teaching-video',
        attrs: { lesson: beat.videoLesson, start: beat.videoStart || '0', end: beat.videoEnd || '' },
        content: '',
      };
      renderTeachingTag(videoTag);
      if (beat.say) await executeSay(beat.say, myPrefetch);
      await voiceBeatGap(beat.pause);
      if (nextPrefetchP) { try { prefetchedResp = await nextPrefetchP; } catch {} }
      continue;
    }

    // 2d. Simulation — render via teaching-simulation tag
    if (beat.simulation) {
      const simTag = {
        name: 'teaching-simulation',
        attrs: { id: beat.simulation },
        content: '',
      };
      renderTeachingTag(simTag);
      if (beat.say) await executeSay(beat.say, myPrefetch);
      await voiceBeatGap(beat.pause);
      if (nextPrefetchP) { try { prefetchedResp = await nextPrefetchP; } catch {} }
      continue;
    }

    // 2e. Widget — render via teaching-widget tag
    if (beat.widgetTitle && beat.widgetCode) {
      const widgetTag = {
        name: 'teaching-widget',
        attrs: { title: beat.widgetTitle },
        content: beat.widgetCode,
      };
      renderTeachingTag(widgetTag);
      if (beat.say) await executeSay(beat.say, myPrefetch);
      await voiceBeatGap(beat.pause);
      if (nextPrefetchP) { try { prefetchedResp = await nextPrefetchP; } catch {} }
      continue;
    }

    // 3. Start draw + say in parallel (with prefetched TTS response)
    const drawPromise = executeDraw(beat.draw);
    const sayPromise = executeSay(beat.say, myPrefetch);

    // Wait for both to complete
    await Promise.all([drawPromise, sayPromise]);

    // 4. Inter-beat gap: explicit pause OR minimum natural breathing room
    if (!beat.question) {
      await voiceBeatGap(beat.pause);
    }

    // Resolve next beat's prefetched TTS (should already be done by now)
    if (nextPrefetchP) { try { prefetchedResp = await nextPrefetchP; } catch {} }

    // 5. If question, show input and stop
    if (beat.question) {
      voiceHideHand();
      const questionText = beat.say || 'What do you think?';
      const rendered = typeof renderLatex === 'function' ? renderLatex(questionText) : questionText;
      voiceShowBoardQuestion(rendered);
      return;
    }
  }

  // Scene finished without a question — show generic input
  voiceHideHand();
  voiceHideSubtitle();
}

// Execute draw commands from a beat
async function executeDraw(drawCmds) {
  if (!drawCmds || drawCmds.length === 0) {
    return;
  }
  console.log(`[VoiceScene] Drawing ${drawCmds.length} commands:`, drawCmds.map(c => c.cmd).join(', '));

  // Ensure board canvas exists
  if (!state.boardDraw.canvas) {
    openBoardDrawSpotlight('Board', null, { clear: true });
    // Wait a tick for canvas initialization
    await new Promise(r => setTimeout(r, 100));
  }

  // Queue commands via BoardEngine
  for (const origCmd of drawCmds) {
    if (!origCmd || !origCmd.cmd) continue;
    BoardEngine.queueCommand({ ...origCmd });
  }

  // Wait for the queue to fully drain before next beat/scene
  if (state.boardDraw.canvas) {
    await bdWaitForQueueDrain();
  }
}

// Wait for the command queue to fully drain (poll until isProcessing is false and queue is empty)
function bdWaitForQueueDrain() {
  return new Promise(resolve => {
    const check = () => {
      const bs = BoardEngine.state;
      if (!bs.isProcessing && bs.commandQueue.length === 0) {
        resolve();
      } else if (bs.cancelFlag) {
        resolve();
      } else {
        setTimeout(check, 50);
      }
    };
    check();
  });
}

// Execute say — TTS + subtitle (optionally with pre-fetched TTS response)
// Supports {ref:elementId} markers in text — triggers highlight on referenced board elements
async function executeSay(text, prefetchedResp) {
  if (!text || !text.trim()) return;

  // Extract {ref:id} markers — these trigger element highlights during speech
  const refs = [];
  const cleanText = text.replace(/\{ref:([^}]+)\}/g, (_, id) => {
    refs.push(id.trim());
    return ''; // remove from spoken/subtitle text
  }).trim();

  // Show subtitle (without ref markers)
  voiceShowSubtitle(cleanText);
  voiceShowIndicator('speaking');

  // Trigger highlights on referenced elements — staggered across speech duration
  // Scroll up to element, glow it, then scroll back to latest content
  if (refs.length > 0) {
    const estDuration = (cleanText.split(/\s+/).length / 2.8 + 0.2) * 1000;
    const interval = estDuration / (refs.length + 1);
    const wrap = document.getElementById('bd-canvas-wrap');
    const scrollBeforeRef = wrap ? wrap.scrollTop : 0;

    refs.forEach((refId, i) => {
      setTimeout(() => {
        if (!BoardEngine.state.elements.has(refId)) return;
        // Scroll to the referenced element and highlight with glow
        BoardEngine.zoomPulse(refId);
      }, interval * (i + 1));
    });
  }

  await voiceSpeak(cleanText, prefetchedResp);
  voiceHideIndicator();
  // Natural post-speech pause
  await new Promise(r => setTimeout(r, 300));
}

// ── Cursor System (ID-based, deterministic) ────────────────

// Resolve an element ID to its center position (virtual coords for hand cursor)
function resolveElementPos(id) {
  const entry = BoardEngine.state.elements.get(id);
  if (!entry || !entry.element || !entry.element.isConnected) return null;
  // Convert DOM rect to virtual coords that voiceMoveHand expects
  const boardContent = document.getElementById('bd-board-content');
  if (!boardContent) return null;
  const bRect = boardContent.getBoundingClientRect();
  const elRect = entry.element.getBoundingClientRect();
  const virtualW = 800;
  const virtualH = state.boardDraw.currentH || 500;
  const x = ((elRect.left + elRect.width / 2) - bRect.left) / bRect.width * virtualW;
  const y = ((elRect.top + elRect.height / 2) - bRect.top) / bRect.height * virtualH;
  return { x, y };
}

// Get bottom-center of an element (for cursor below text)
function resolveElementBottom(id) {
  const entry = BoardEngine.state.elements.get(id);
  if (!entry || !entry.element || !entry.element.isConnected) return null;
  const boardContent = document.getElementById('bd-board-content');
  if (!boardContent) return null;
  const bRect = boardContent.getBoundingClientRect();
  const elRect = entry.element.getBoundingClientRect();
  const virtualW = 800;
  const virtualH = state.boardDraw.currentH || 500;
  const x = ((elRect.left + elRect.width / 2) - bRect.left) / bRect.width * virtualW;
  const y = ((elRect.bottom + 5) - bRect.top) / bRect.height * virtualH;
  return { x, y };
}

// Execute cursor from beat attribute
function executeCursor(cursorStr, drawCmds) {
  if (!cursorStr && drawCmds && drawCmds.length > 0) cursorStr = 'write';
  if (!cursorStr || cursorStr === 'rest') { voiceHideHand(); return; }

  // cursor="write" — auto-follow the draw in this beat (uses its ID or coords)
  if (cursorStr === 'write' && drawCmds && drawCmds.length > 0) {
    const cmd = drawCmds[drawCmds.length - 1]; // last draw = where cursor ends
    if (cmd.id) {
      // Will be registered after draw — position at draw coords for now
      const pos = getCommandPosition(cmd);
      if (pos) voiceMoveHand(pos.x, pos.y + (cmd.size || 24), true);
    } else {
      const pos = getCommandPosition(cmd);
      if (pos) voiceMoveHand(pos.x, pos.y + (cmd.size || 24), true);
    }
    return;
  }

  // cursor="write:id:X" — position at bottom of element X, in writing pose
  const writeIdMatch = cursorStr.match(/^write:id:(.+)$/);
  if (writeIdMatch) {
    const pos = resolveElementBottom(writeIdMatch[1]);
    if (pos) { voiceMoveHand(pos.x, pos.y, true); BoardEngine.scrollToElement(writeIdMatch[1]); }
    return;
  }

  // cursor="tap:id:X" — tap center of element X
  const tapIdMatch = cursorStr.match(/^tap:id:(.+)$/);
  if (tapIdMatch) {
    const pos = resolveElementPos(tapIdMatch[1]);
    if (pos) { voiceTapAt(pos.x, pos.y); BoardEngine.scrollToElement(tapIdMatch[1]); }
    return;
  }

  // cursor="point:id:X" — hover at center of element X
  const pointIdMatch = cursorStr.match(/^point:id:(.+)$/);
  if (pointIdMatch) {
    const pos = resolveElementPos(pointIdMatch[1]);
    if (pos) { voiceMoveHand(pos.x, pos.y, false); BoardEngine.scrollToElement(pointIdMatch[1]); }
    return;
  }

  // Fallback: cursor="tap:x,y" or cursor="point:x,y" with raw coords
  const tapMatch = cursorStr.match(/^tap:(\d+),(\d+)$/);
  if (tapMatch) { voiceTapAt(parseInt(tapMatch[1]), parseInt(tapMatch[2])); return; }

  const pointMatch = cursorStr.match(/^point:(\d+),(\d+)$/);
  if (pointMatch) { voiceMoveHand(parseInt(pointMatch[1]), parseInt(pointMatch[2]), false); return; }
}

function getCommandPosition(cmd) {
  if (!cmd) return null;
  switch (cmd.cmd) {
    case 'text': case 'latex': return { x: cmd.x, y: cmd.y };
    case 'line': case 'arrow': case 'dashed': return { x: cmd.x1, y: cmd.y1 };
    case 'rect': case 'fillrect': return { x: cmd.x, y: cmd.y };
    case 'circle': case 'arc': return { x: cmd.cx, y: cmd.cy };
    case 'animation': return { x: cmd.x || 0, y: cmd.y || 0 };
    default: return null;
  }
}

// Hook for non-scene board draws — only follows if NOT in a voice scene
function voiceHandFollowCommand(cmd) {
  if (state.teachingMode !== 'voice' || state._voiceSceneActive) return;
  if (!cmd) return;
  if (cmd.cmd === 'pause') { voiceHideHand(); return; }
  // In non-scene mode, follow draws by ID if available
  if (cmd.id) {
    const pos = resolveElementBottom(cmd.id) || resolveElementPos(cmd.id);
    if (pos) voiceMoveHand(pos.x, pos.y, true);
  }
}

// ── Ephemeral Annotations (circle, underline, glow — fade after delay) ────

// ── Inline Media (video/sim on board for voice mode) ────────

function renderInlineMedia(type, data) {
  const boardContent = $('#spotlight-content');
  if (!boardContent) return;

  // Remove any existing inline media
  const existing = document.getElementById('inline-media-box');
  if (existing) existing.remove();

  const box = document.createElement('div');
  box.id = 'inline-media-box';
  box.className = 'inline-media-box';

  let contentHTML = '';
  let title = '';

  if (type === 'video') {
    const videoUrl = findVideoUrl(data.lessonId);
    if (!videoUrl) { console.warn('No video URL for lesson', data.lessonId); return; }
    const src = buildVideoSrc(videoUrl, data.start, data.end);
    title = data.label || 'Video';
    contentHTML = `<iframe src="${escapeAttr(src)}" allow="accelerometer; autoplay; encrypted-media; gyroscope" allowfullscreen style="width:100%;height:100%;border:none;border-radius:6px"></iframe>`;
  } else if (type === 'simulation') {
    title = 'Simulation';
    const sim = state.simulations?.find(s => s.id === data.simId || s.sim_id === data.simId);
    if (sim) {
      title = sim.title || 'Simulation';
      contentHTML = `<iframe src="${escapeAttr(sim.entry_url || sim.url || '')}" style="width:100%;height:100%;border:none;border-radius:6px"></iframe>`;
    } else {
      contentHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-dim)">Loading simulation...</div>`;
    }
  }

  box.innerHTML = `
    <div class="inline-media-header">
      <span class="inline-media-badge">${type === 'video' ? 'VIDEO' : 'SIM'}</span>
      <span class="inline-media-title">${escapeHtml(title)}</span>
      <div class="inline-media-controls">
        <button class="inline-media-btn" onclick="expandInlineMedia()" title="Fullscreen">⛶</button>
        <button class="inline-media-btn" onclick="closeInlineMedia()" title="Close">✕</button>
      </div>
    </div>
    <div class="inline-media-content">${contentHTML}</div>
  `;

  boardContent.appendChild(box);
  boardContent.style.position = 'relative';

  // Store for reference
  state._inlineMedia = { type, data, title };
}

function expandInlineMedia() {
  const box = document.getElementById('inline-media-box');
  if (!box) return;
  box.classList.toggle('fullscreen');
}

function closeInlineMedia() {
  const box = document.getElementById('inline-media-box');
  if (box) box.remove();
  state._inlineMedia = null;
  // Trigger agent response after closing
  streamADK('[Student closed the video/simulation]', true);
}

function voiceAnnotate(type, targetId, options = {}) {
  // All annotation types now use the same hand-drawn circle highlight
  // (simplified from circle/underline/box/glow — circle is the most natural)
  BoardEngine.zoomPulse(targetId);
  return;
  // Legacy code below kept for reference but not executed
  const el = bdElementRegistry[targetId];
  if (!el) return;
  const bd = state.boardDraw;
  if (!bd.canvas || !bd.ctx) return;

  const s = bd.scale;
  const color = options.color || '#34d399';
  const duration = options.duration || 2000;
  const lineWidth = (options.lineWidth || 2.5) * s;

  // Create ephemeral canvas overlay for the annotation
  const layer = document.getElementById('bd-anim-layer');
  if (!layer) return;

  const overlay = document.createElement('canvas');
  overlay.width = bd.canvas.width;
  overlay.height = bd.canvas.height;
  overlay.style.cssText = `position:absolute;top:0;left:0;width:${bd.canvas.style.width};height:${bd.canvas.style.height};pointer-events:none;z-index:5;transition:opacity 0.5s;`;
  layer.appendChild(overlay);

  const ctx = overlay.getContext('2d');
  ctx.setTransform(bd.DPR, 0, 0, bd.DPR, 0, 0);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const x = el.x * s;
  const y = el.y * s;
  const w = (el.w || 100) * s;
  const h = (el.h || 30) * s;
  const pad = 8 * s;

  if (type === 'circle') {
    // Hand-drawn circle effect (slightly wobbly ellipse)
    ctx.beginPath();
    const cx = x + w / 2, cy = y + h / 2;
    const rx = w / 2 + pad, ry = h / 2 + pad;
    for (let i = 0; i <= 64; i++) {
      const angle = (i / 64) * Math.PI * 2;
      const wobble = 1 + Math.sin(angle * 5) * 0.03;
      const px = cx + Math.cos(angle) * rx * wobble;
      const py = cy + Math.sin(angle) * ry * wobble;
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.stroke();
  } else if (type === 'underline') {
    // Wavy underline below the element
    const uy = y + h + 4 * s;
    ctx.beginPath();
    ctx.moveTo(x - pad / 2, uy);
    for (let px = x; px < x + w + pad; px += 3) {
      ctx.lineTo(px, uy + Math.sin(px * 0.1) * 2 * s);
    }
    ctx.stroke();
  } else if (type === 'box') {
    // Rounded rectangle
    const r = 6 * s;
    ctx.beginPath();
    ctx.roundRect(x - pad, y - pad, w + pad * 2, h + pad * 2, r);
    ctx.stroke();
  } else if (type === 'glow') {
    // Glow effect — filled semi-transparent rectangle
    ctx.fillStyle = color.replace(')', ',0.15)').replace('rgb', 'rgba').replace('#', '');
    // Convert hex to rgba
    const hexToRgba = (hex, alpha) => {
      const r = parseInt(hex.slice(1,3), 16);
      const g = parseInt(hex.slice(3,5), 16);
      const b = parseInt(hex.slice(5,7), 16);
      return `rgba(${r},${g},${b},${alpha})`;
    };
    ctx.fillStyle = hexToRgba(color.startsWith('#') ? color : '#34d399', 0.12);
    ctx.fillRect(x - pad, y - pad, w + pad * 2, h + pad * 2);
    ctx.strokeStyle = hexToRgba(color.startsWith('#') ? color : '#34d399', 0.4);
    ctx.lineWidth = lineWidth * 0.7;
    ctx.strokeRect(x - pad, y - pad, w + pad * 2, h + pad * 2);
  }

  // Fade out after duration
  setTimeout(() => {
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 500);
  }, duration);

  // Scroll to the annotated element
  BoardEngine.scrollToElement(targetId);
}

// ── Hook into finalizeAIMessage for voice mode ──────────────

function voiceHandleFinalizedText(text) {
  if (state.teachingMode !== 'voice') return;
  if (!text || !text.trim()) return;

  // If a voice scene exists in this message, the scene executor handles ALL audio.
  // Do NOT also speak the text — that causes double voice.
  if (text.includes('<teaching-voice-scene')) return;

  // If a voice scene is currently executing, don't speak
  if (state._voiceSceneActive) return;

  // If there's a board-draw, the board voice commands handle narration
  if (text.includes('<teaching-board-draw')) return;

  // Fallback: tutor sent plain text without voice scene or board-draw
  const stripped = stripTeachingTags(text)
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  if (stripped.length < 5) return;

  voiceShowSubtitle(stripped);
  voiceSpeak(stripped)
    .then(() => setTimeout(() => voiceHideSubtitle(), 2000))
    .catch(() => setTimeout(() => voiceHideSubtitle(), 5000));
}

// Called when the entire agentic run finishes
function voiceHandleRunFinished() {
  if (state.teachingMode !== 'voice') return;

  const lastMsg = state.messages.filter(m => m.role === 'assistant').pop();
  if (!lastMsg) return;
  const text = typeof lastMsg.content === 'string' ? lastMsg.content : '';

  // Don't show input if user is already typing
  const voiceInput = $('#voice-bar-input');
  if (voiceInput && voiceInput === document.activeElement && voiceInput.value.trim()) return;

  // Don't show input if there's an interactive tag
  const hasInteractiveTag = /<teaching-(mcq|freetext|agree-disagree|fillblank|spot-error|confidence|canvas|teachback)/i.test(text);
  if (hasInteractiveTag) return;

  // Always show board input after run finishes
  const stripped = stripTeachingTags(text).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  const sentences = stripped.split(/(?<=[.!?])\s+/);
  const lastQ = sentences.filter(s => s.endsWith('?')).pop();
  voiceShowBoardQuestion(lastQ || 'Type your response...');
}

// ── Utility ─────────────────────────────────────────────────

function voiceSleep(ms) {
  return new Promise(r => setTimeout(r, ms / state.voiceSpeed));
}

// Natural inter-beat breathing gap — ensures a perceptual pause between
// beats even when the agent omits an explicit pause attribute. Explicit
// pauses are speed-scaled; the minimum floor (350ms) is real-time so
// fast playback still feels human.
const MINIMUM_BEAT_GAP_MS = 500; // half-second breathing room between beats
function voiceBeatGap(pauseAttr) {
  const explicitMs = (pauseAttr && pauseAttr > 0)
    ? (pauseAttr * 1000) / state.voiceSpeed
    : 0;
  return new Promise(r => setTimeout(r, Math.max(explicitMs, MINIMUM_BEAT_GAP_MS)));
}

// ── Thinking state & stop generation ────────────────────────

function voiceBarSetThinking(isThinking) {
  const bar = $('#voice-bar-main');
  const input = $('#voice-bar-input');
  const micBtn = $('#voice-mic-btn');
  const sendBtn = $('#voice-bar-send');
  if (!bar) return;

  if (isThinking) {
    bar.classList.add('thinking');
    if (input) { input.disabled = true; input.placeholder = ''; }
    if (sendBtn) sendBtn.classList.remove('visible');
    // Replace mic with stop button
    if (micBtn) {
      micBtn._origHTML = micBtn.innerHTML;
      micBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
      micBtn.title = 'Stop generating';
      micBtn.onclick = stopGeneration;
    }
  } else {
    bar.classList.remove('thinking');
    if (input) { input.disabled = false; input.placeholder = 'Type your response...'; }
    if (micBtn) {
      if (micBtn._origHTML) micBtn.innerHTML = micBtn._origHTML;
      micBtn.title = 'Hold to talk';
      micBtn.onclick = null;
    }
  }
}

function stopGeneration() {
  if (!state.isStreaming) return;

  console.log('[Stop] Stopping tutor...');

  // Set stop flag FIRST — stream loop and all async handlers check this
  state._stopRequested = true;
  // NOTE: Do NOT reset _stopRequested here — the stream loop's catch block
  // needs to see it as true to suppress the error toast. The stream loop's
  // cleanup code resets it after the catch block runs.

  // 1. Cancel the HTTP stream (stops data flow from backend)
  if (state._streamReader) {
    try { state._streamReader.cancel(); } catch (e) {}
    state._streamReader = null;
  }

  // 2. Stop ALL audio immediately
  [state._currentTTSAudio, state.voiceCurrentAudio].forEach(audio => {
    if (audio) { try { audio.pause(); audio.src = ''; } catch(e) {} }
  });
  state._currentTTSAudio = null;
  state.voiceCurrentAudio = null;
  if (state.voiceCurrentSrc) {
    try { state.voiceCurrentSrc.stop(); } catch(e) {}
    state.voiceCurrentSrc = null;
  }
  // Suspend (not close!) AudioContext — stops buffered audio but allows reuse
  if (state.voiceAudioCtx && state.voiceAudioCtx.state === 'running') {
    try { state.voiceAudioCtx.suspend(); } catch(e) {}
  }

  // 3. Kill voice scene — prevent ANY further beat execution
  state._voiceSceneActive = false;
  if (typeof _eagerReset === 'function') _eagerReset();
  if (typeof _eager !== 'undefined') {
    _eager.done = true;
    _eager.queue = [];
    _eager.running = false;
    _eager.parsedCount = 999999;
  }

  // 4. Stop board queue but preserve what's drawn
  if (typeof BoardEngine !== 'undefined') {
    BoardEngine.cancel();
    setTimeout(() => {
      if (BoardEngine.state) {
        BoardEngine.state.cancelFlag = false;
        BoardEngine.state.isProcessing = false;
      }
    }, 50);
  }
  state.boardDraw.commandQueue = [];
  state.boardDraw.isProcessing = false;
  state.boardDraw.cancelFlag = false;

  // 5. Clear pending timers
  if (state._streamUpdateTimer) { clearTimeout(state._streamUpdateTimer); state._streamUpdateTimer = null; }
  if (state._streamingTimeout) { clearTimeout(state._streamingTimeout); state._streamingTimeout = null; }

  // 6. Save partial message — this becomes part of the conversation context
  if (state.accumulatedText) {
    const partialText = state.accumulatedText;
    updateAIMessageStream(partialText);
    finalizeAIMessage(partialText);
    state.messages.push({
      id: state.currentMessageId || generateId(),
      role: 'assistant',
      content: partialText + '\n\n[Student interrupted — tutor stopped here]',
      timestamp: Date.now(),
      stopped: true,
    });
    state.totalAssistantTurns++;
    state.accumulatedText = '';
  }

  // 7. Mark streaming as done (but keep _stopRequested TRUE for catch block)
  state.isStreaming = false;

  // 8. Restore UI
  voiceBarSetThinking(false);
  removeStreamingIndicator();
  voiceHideSubtitle();
  _showStopButton(false);
  hideSessionPrep();

  const field = document.getElementById('voice-bar-input');
  if (field) {
    field.disabled = false;
    field.style.opacity = '';
    field.style.pointerEvents = '';
    field.placeholder = 'Type your response...';
  }

  console.log('[Stop] Tutor stopped — board preserved, audio suspended, beats cleared');
}

function _showStopButton(show) {
  const voiceStop = document.getElementById('voice-bar-stop');
  const voiceSend = document.getElementById('voice-bar-send');
  const voiceMic = document.getElementById('voice-mic-btn');
  const vmStop = document.getElementById('vm-stop-btn');
  const vmSend = document.getElementById('vm-send-btn');

  if (show) {
    // Show stop, hide send/mic (only if not recording)
    if (voiceStop) voiceStop.classList.remove('hidden');
    if (!_pttActive) {
      if (voiceSend) voiceSend.classList.add('hidden');
      if (voiceMic) voiceMic.classList.add('hidden');
    }
    if (vmStop) vmStop.classList.remove('hidden');
    if (vmSend) vmSend.classList.add('hidden');
  } else {
    // Restore normal state
    if (voiceStop) voiceStop.classList.add('hidden');
    if (voiceSend) voiceSend.classList.remove('hidden');
    if (voiceMic) voiceMic.classList.remove('hidden');
    if (vmStop) vmStop.classList.add('hidden');
    if (vmSend) vmSend.classList.remove('hidden');
  }
}

// ── Unified voice bar submit ────────────────────────────────

function submitVoiceBarInput() {
  const field = $('#voice-bar-input');
  if (!field || !field.value.trim()) return;

  // If tutor is streaming, stop it first — student input is an interrupt
  if (state.isStreaming) {
    stopGeneration();
    // Wait for stream loop cleanup to fully complete before sending new message
    // The async cleanup (catch block + cleanup code) needs ~200ms
    setTimeout(() => {
      if (field.value.trim() && !state.isStreaming) _doSubmitVoiceBar(field);
    }, 300);
    return;
  }
  _doSubmitVoiceBar(field);
}

function _doSubmitVoiceBar(field) {
  if (state.isStreaming) return; // safety
  const text = field.value.trim();
  field.value = '';
  field.style.height = '';
  field.placeholder = 'Type your response...';

  // Show sent confirmation in subtitle — important for student to know their message went through
  const preview = text.length > 80 ? text.slice(0, 80) + '...' : text;
  voiceShowSubtitle('You: ' + preview);

  // Brief visual flash on the voice bar to confirm send
  const bar = document.getElementById('voice-bar-main');
  if (bar) {
    bar.style.borderColor = 'rgba(52,211,153,0.5)';
    setTimeout(() => { bar.style.borderColor = ''; }, 600);
  }

  const sendBtn = $('#voice-bar-send');
  if (sendBtn) sendBtn.classList.remove('visible');

  // Auto-attach board images if student drew on the board
  const bd = state.boardDraw;
  if (bd.studentDrawing && bd.canvas) {
    const parts = [];
    if (bd.tutorSnapshot) {
      const tutorBase64 = bd.tutorSnapshot.split(',')[1];
      parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: tutorBase64 } });
      parts.push({ type: 'text', text: '[BOARD — BEFORE] Tutor\'s original board.' });
    }
    const boardImages = typeof bdCaptureViewportChunks === 'function' ? bdCaptureViewportChunks() : [];
    for (let i = 0; i < boardImages.length; i++) {
      parts.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: boardImages[i] } });
      parts.push({ type: 'text', text: boardImages.length > 1 ? `[BOARD — AFTER ${i+1}/${boardImages.length}]` : '[BOARD — AFTER] With student annotations.' });
    }
    parts.push({ type: 'text', text: text });
    bd.studentDrawing = false;
    streamADK(parts);
  } else {
    streamADK(text);
  }
}

// Show/hide send button based on input content
document.addEventListener('input', (e) => {
  if (e.target.id === 'voice-bar-input') {
    const sendBtn = $('#voice-bar-send');
    if (sendBtn) sendBtn.classList.toggle('visible', e.target.value.trim().length > 0);
    // Auto-grow textarea
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    e.target.style.overflowY = e.target.scrollHeight > 120 ? 'auto' : 'hidden';
  }
});

// ── Enter key handler ───────────────────────────────────────
document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && document.activeElement?.id === 'voice-bar-input') {
    if (e.shiftKey) return; // Shift+Enter = newline
    e.preventDefault();
    submitVoiceBarInput();
  }
});

// ── Push-to-talk (Space bar) ────────────────────────────────

let _pttRecognition = null;
let _pttActive = false;

// Voice recording is click-based only — no keyboard shortcut needed

// ── Voice Input — Click-to-record flow ──
// 1. Click mic → recording starts, mic becomes ✓ button, waveform shows
// 2. Click ✓ → recording stops, transcript fills text box
// 3. User edits text → presses Enter/Send to submit

function startVoiceRecording() {
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) return;
  _pttActive = true;

  const bar = $('#voice-bar-main');
  const micBtn = $('#voice-mic-btn');
  const field = $('#voice-bar-input');
  if (bar) bar.classList.add('recording');
  // Change mic icon → tick (✓) + add cancel (×) button
  if (micBtn) {
    micBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
    micBtn.title = 'Done recording';
    // Add cancel button before the mic/tick button
    const cancelBtn = document.createElement('button');
    cancelBtn.id = 'voice-rec-cancel';
    cancelBtn.className = 'voice-bar-cancel';
    cancelBtn.innerHTML = '×';
    cancelBtn.title = 'Cancel recording';
    cancelBtn.addEventListener('click', (e) => { e.preventDefault(); cancelVoiceRecording(); });
    micBtn.parentNode.insertBefore(cancelBtn, micBtn);
  }
  if (field) { field.placeholder = 'Listening...'; field.value = ''; }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  _pttRecognition = new SpeechRecognition();
  _pttRecognition.continuous = true;
  _pttRecognition.interimResults = true;
  _pttRecognition.lang = 'en-US';

  _pttRecognition.onresult = (e) => {
    let final = '', interim = '';
    for (let i = 0; i < e.results.length; i++) {
      if (e.results[i].isFinal) final += e.results[i][0].transcript;
      else interim += e.results[i][0].transcript;
    }
    if (field) {
      field.value = final + interim;
      field.classList.add('transcript');
    }
  };
  _pttRecognition.onerror = () => { stopVoiceRecording(); };
  _pttRecognition.onend = () => {
    // Speech recognition auto-stops after silence — restart if still recording
    if (_pttActive && _pttRecognition) {
      try { _pttRecognition.start(); } catch(e) {}
    }
  };
  _pttRecognition.start();
}

function _restoreMicButton() {
  const bar = $('#voice-bar-main');
  const micBtn = $('#voice-mic-btn');
  const cancelBtn = $('#voice-rec-cancel');
  if (bar) bar.classList.remove('recording');
  if (cancelBtn) cancelBtn.remove();
  if (micBtn) {
    micBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="1" width="6" height="11" rx="3"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`;
    micBtn.title = 'Click to record';
  }
  if (_pttRecognition) {
    _pttRecognition.onend = null;
    _pttRecognition.stop();
    _pttRecognition = null;
  }
}

function stopVoiceRecording() {
  _pttActive = false;
  _restoreMicButton();
  const field = $('#voice-bar-input');
  if (field) {
    field.classList.remove('transcript');
    field.placeholder = 'Type your response...';
    if (field.value.trim()) {
      field.focus();
      field.style.height = 'auto';
      field.style.height = field.scrollHeight + 'px';
    }
  }
}

function cancelVoiceRecording() {
  _pttActive = false;
  _restoreMicButton();
  const field = $('#voice-bar-input');
  if (field) {
    field.value = '';
    field.classList.remove('transcript');
    field.placeholder = 'Type your response...';
  }
}

// Voice bar input — Enter to send + auto-resize
document.addEventListener('DOMContentLoaded', () => {
  const vbInput = document.getElementById('voice-bar-input');
  if (vbInput) {
    // Enter to send (Shift+Enter for newline)
    vbInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitVoiceBarInput();
      }
    });
    // Auto-resize textarea as user types
    vbInput.addEventListener('input', () => {
      vbInput.style.height = '';
      vbInput.style.height = Math.min(vbInput.scrollHeight, 120) + 'px';
    });
    // Show send button when text is present
    vbInput.addEventListener('input', () => {
      const sendBtn = document.getElementById('voice-bar-send');
      if (sendBtn && !state.isStreaming) {
        sendBtn.style.opacity = vbInput.value.trim() ? '1' : '';
      }
    });
  }
});

// Floating mic button — toggle click (not hold)
document.addEventListener('DOMContentLoaded', () => {
  const micBtn = document.getElementById('voice-mic-btn');
  if (micBtn) {
    micBtn.addEventListener('click', (e) => {
      e.preventDefault();

      // If tutor is streaming, stop it first (interrupt)
      if (state.isStreaming && !_pttActive) {
        stopGeneration();
      }

      if (_pttActive) {
        // Stop recording AND auto-submit if there's text
        stopVoiceRecording();
        const field = document.getElementById('voice-bar-input');
        if (field && field.value.trim()) {
          // Small delay so the final transcript chunk arrives
          setTimeout(() => submitVoiceBarInput(), 150);
        }
      } else {
        startVoiceRecording();
      }
    });
  }
});


// ═══════════════════════════════════════════════════════════════════════════════
// SEARCH-FIRST LANDING — debounced semantic search + typing animation
// ═══════════════════════════════════════════════════════════════════════════════

let _searchDebounce = null;
let _searchAbort = null;

function _extractYTThumb(url) {
  if (!url) return '';
  const m = url.match(/(?:youtu\.be\/|v=|\/embed\/)([A-Za-z0-9_-]{11})/);
  return m ? `https://img.youtube.com/vi/${m[1]}/mqdefault.jpg` : '';
}

async function _nlDoSearch(query) {
  const resultsEl = document.getElementById('nl-results');
  const aiOption = document.getElementById('nl-ai-option');
  const chipsEl = document.getElementById('nl-chips');

  if (!query || query.trim().length < 2) {
    resultsEl.innerHTML = '';
    if (aiOption) aiOption.style.display = 'none';
    if (chipsEl) chipsEl.style.display = '';
    return;
  }

  if (chipsEl) chipsEl.style.display = 'none';
  resultsEl.innerHTML = '<div class="nl-loading">Searching...</div>';
  if (aiOption) aiOption.style.display = '';

  // Abort previous request
  if (_searchAbort) _searchAbort.abort();
  _searchAbort = new AbortController();

  try {
    const res = await fetch(`${state.apiUrl}/api/v1/content/search?q=${encodeURIComponent(query.trim())}&limit=8`, {
      headers: AuthManager.authHeaders(),
      signal: _searchAbort.signal,
    });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();

    if (!data.length) {
      resultsEl.innerHTML = `<div class="nl-no-results">
        No matching courses found for "<strong>${query.trim()}</strong>"
      </div>`;
      // Show AI tutor as primary option when no courses match
      if (aiOption) {
        aiOption.style.display = '';
        aiOption.querySelector('.nl-ai-title').textContent = 'No worries — AI tutor can teach this';
        aiOption.querySelector('.nl-ai-desc').textContent = `Start an interactive session on "${query.trim()}"`;
      }
      return;
    }

    // Split into lessons and courses
    const lessons = data.filter(d => d.type === 'lesson');
    const courses = data.filter(d => d.type === 'course');

    let html = '';

    if (lessons.length) {
      html += '<div class="nl-rlabel">Lectures</div>';
      for (const l of lessons) {
        const thumb = l.metadata?.thumbnailUrl || '';
        const course = l.metadata?.courseTitle || '';
        const dur = l.metadata?.durationMin ? `${l.metadata.durationMin}m` : '';
        html += `<div class="nl-rcard" data-lesson-id="${l.lessonId}" data-course-id="${l.courseId}" onclick="_nlClickLesson(${l.courseId}, ${l.lessonId}, '${l.title.replace(/['"]/g, "")}')">
          <div class="nl-rthumb">${thumb ? `<img src="${thumb}" alt="">` : ''}<div class="nl-pbadge"><svg viewBox="0 0 24 24" fill="white"><polygon points="8 5 20 12 8 19"/></svg></div></div>
          <div class="nl-rbody"><div class="nl-rtitle">${l.title}</div><div class="nl-rmeta">${course}${dur ? ' · ' + dur : ''}</div><div class="nl-raction">Watch this lecture</div></div>
          <div class="nl-rtag lec">Lecture</div>
        </div>`;
      }
    }

    if (courses.length) {
      if (lessons.length) html += '<div class="nl-rdivider"></div>';
      html += '<div class="nl-rlabel">Courses</div>';
      for (const c of courses) {
        const thumb = c.metadata?.thumbnailUrl || '';
        const count = c.metadata?.lessonCount || 0;
        html += `<div class="nl-rcard" data-course-id="${c.courseId}" onclick="_nlClickCourse(${c.courseId}, '${c.title.replace(/['"]/g, "")}')">
          <div class="nl-rthumb">${thumb ? `<img src="${thumb}" alt="">` : ''}</div>
          <div class="nl-rbody"><div class="nl-rtitle">${c.title}</div><div class="nl-rmeta">${count} lectures · ${c.metadata?.difficulty || ''}</div><div class="nl-raction">Explore full course</div></div>
          <div class="nl-rtag crs">Course</div>
        </div>`;
      }
    }

    resultsEl.innerHTML = html;
  } catch (e) {
    if (e.name === 'AbortError') return; // cancelled
    resultsEl.innerHTML = '<div class="nl-no-results">Search failed — try again</div>';
  }
}

function _nlClickLesson(courseId, lessonId, title) {
  _nlShowChoice(courseId, lessonId, title || 'this lesson');
}

function _nlClickCourse(courseId, title) {
  _nlShowChoice(courseId, null, title || 'this course');
}

function _nlShowChoice(courseId, lessonId, title) {
  const resultsEl = document.getElementById('nl-results');
  const aiOption = document.getElementById('nl-ai-option');
  if (aiOption) aiOption.style.display = 'none';

  const courseIdInput = document.getElementById('course-id');
  if (courseIdInput) courseIdInput.value = courseId;
  state.courseId = courseId;
  if (lessonId) state.checkpoint.currentLessonId = lessonId;

  const escapedTitle = title.replace(/'/g, "\\'");

  resultsEl.innerHTML = `
    <div style="padding:20px 0;">
      <div style="font-size:15px;font-weight:600;margin-bottom:16px;text-align:center">${title}</div>
      <div style="display:flex;flex-direction:column;gap:8px;max-width:400px;margin:0 auto;">
        <button class="nl-choice-btn nl-choice-video" onclick="_nlStartVideo(${courseId}, ${lessonId || 'null'})">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Watch the lecture video
          <span style="font-size:11px;color:var(--text-dim);display:block;margin-top:2px">Pause anytime to ask the AI tutor</span>
        </button>
        <button class="nl-choice-btn nl-choice-tutor" onclick="_nlStartTutor(${courseId}, '${escapedTitle}')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
          Let AI tutor teach me
          <span style="font-size:11px;color:var(--text-dim);display:block;margin-top:2px">Interactive board teaching, personalized to you</span>
        </button>
      </div>
    </div>`;
}

function _nlStartVideo(courseId, lessonId) {
  vmStartVideoForLesson(courseId, lessonId);
}

function _nlStartTutor(courseId, title) {
  const input = document.getElementById('student-intent-first');
  const intent = (input?.value || '').trim() || title || 'Teach me';
  startNewSession(state.studentName, courseId, intent);
}

// Typing animation for search placeholder
const _nlPhrases = [
  'teach me the Schrodinger equation...',
  'I want to learn quantum physics...',
  'explain wave-particle duality...',
  'what is superposition?',
  'help me understand operators...',
  'how does tunneling work?',
];
let _nlPi = 0, _nlCi = 0, _nlDeleting = false;

function _nlTypeLoop() {
  const el = document.getElementById('nl-typed');
  const inp = document.getElementById('student-intent-first');
  if (!el) return;
  if (inp && (inp.value.length > 0 || document.activeElement === inp)) {
    el.textContent = '';
    setTimeout(_nlTypeLoop, 500);
    return;
  }
  const phrase = _nlPhrases[_nlPi];
  if (!_nlDeleting) {
    el.textContent = phrase.slice(0, _nlCi + 1);
    _nlCi++;
    if (_nlCi >= phrase.length) { _nlDeleting = true; setTimeout(_nlTypeLoop, 2200); return; }
    setTimeout(_nlTypeLoop, 50 + Math.random() * 35);
  } else {
    el.textContent = phrase.slice(0, _nlCi);
    _nlCi--;
    if (_nlCi <= 0) { _nlDeleting = false; _nlPi = (_nlPi + 1) % _nlPhrases.length; setTimeout(_nlTypeLoop, 400); return; }
    setTimeout(_nlTypeLoop, 22);
  }
}

// Wire up on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('student-intent-first');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      if (_searchDebounce) clearTimeout(_searchDebounce);
      _searchDebounce = setTimeout(() => _nlDoSearch(searchInput.value), 350);
    });
  }

  // Chips fill search and trigger
  document.querySelectorAll('.nl-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.q;
      const inp = document.getElementById('student-intent-first');
      if (inp) { inp.value = q; inp.focus(); }
      _nlDoSearch(q);
    });
  });

  // AI tutor option
  const aiOpt = document.getElementById('nl-ai-option');
  if (aiOpt) {
    aiOpt.addEventListener('click', () => {
      const inp = document.getElementById('student-intent-first');
      const intent = (inp?.value || '').trim() || 'Teach me';
      startNewSession(state.studentName, parseInt(document.getElementById('course-id')?.value) || 2, intent);
    });
  }

  // Start typing animation
  setTimeout(_nlTypeLoop, 1000);
});


// ═══════════════════════════════════════════════════════════════════════════════
// VIDEO FOLLOW-ALONG MODE
// ═══════════════════════════════════════════════════════════════════════════════

state.video = { active: false, courseId: null, lessonId: null, lessonTitle: '', currentTimestamp: 0, currentSectionIndex: 0, sectionTitle: '', isPaused: false, player: null, sections: [], lessons: [], lessonIndex: 0 };

function _extractYTVideoId(url) {
  if (!url) return null;
  const m = url.match(/(?:youtu\.be\/|v=|\/embed\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

// Get direct stream URL from YouTube via backend yt-dlp
async function _getStreamUrl(videoUrl) {
  try {
    const res = await fetch(`${state.apiUrl}/api/v1/content/video-stream?url=${encodeURIComponent(videoUrl)}`, {
      headers: AuthManager.authHeaders(),
    });
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();
    return data.streamUrl;
  } catch (e) {
    console.warn('Failed to get stream URL, falling back to thumbnail:', e);
    return null;
  }
}

// Capture current video frame as base64 image
let _frameCaptureWarned = false;
function vmCaptureFrame() {
  const video = document.getElementById('vm-video-el');
  if (!video || video.readyState < 2) return null;
  try {
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 360;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.7);
  } catch (e) {
    if (!_frameCaptureWarned) {
      console.info('Frame capture unavailable (cross-origin video) — this is expected for YouTube streams');
      _frameCaptureWarned = true;
    }
    return null;
  }
}

// Called from search results when user picks "Watch the lecture video"
async function vmStartVideoForLesson(courseId, lessonId) {
  state.video.active = true;
  state.video.courseId = courseId;
  state.video.lessonId = lessonId;

  // Load course map
  try {
    const data = await fetchJSON(`/courses/${courseId}`);
    state.courseMap = data;
    state.courseId = courseId;
    const lessons = [...(data.lessons || [])].sort((a, b) => a.module_id !== b.module_id ? a.module_id - b.module_id : a.order - b.order);
    state.video.lessons = lessons;
    const idx = lessons.findIndex(l => l.id === lessonId);
    state.video.lessonIndex = idx >= 0 ? idx : 0;
    const lesson = lessons[state.video.lessonIndex];
    state.video.lessonTitle = lesson?.title || '';
    state.video.lessonId = lesson?.id || lessonId;
  } catch (e) { console.error('Failed to load course:', e); }

  // Load sections
  try {
    state.video.sections = await fetch(`${state.apiUrl}/api/v1/content/lessons/${state.video.lessonId}/sections`, { headers: AuthManager.authHeaders() }).then(r => r.json()) || [];
  } catch (e) { state.video.sections = []; }

  // Show teaching layout (full-width board, no chat panel)
  document.body.classList.add('video-mode');
  _hideAllScreens();
  document.getElementById('teaching-layout').classList.remove('hidden');
  hidePlanSidebar(); // No plan sidebar in video mode
  document.getElementById('teaching-layout').style.display = 'flex';

  // Create session silently
  state.sessionId = generateId();
  state.sessionStartTime = Date.now();
  state.messages = [];
  state.studentIntent = `Video follow-along: ${state.video.lessonTitle}`;
  state.checkpoint.currentLessonId = state.video.lessonId;

  try {
    await SessionManager.createSession(courseId, state.studentName, state.studentIntent, { lessonId: state.video.lessonId, sectionIndex: 0, completedCourseSections: [] }, 1);
  } catch (e) {}

  Router.navigate(`/session/${state.sessionId}`, { replace: true, skipHandler: true });

  // Initialize board with session heading via a synthetic board-draw
  const courseTitle = state.courseMap?.title || state.courseMap?.course?.title || 'Course';
  const lessonTitle = state.video.lessonTitle || 'Lesson';
  const sections = state.video.sections || [];

  setTimeout(() => {
    // Ensure board panel is ready
    const spotlightContent = document.getElementById('spotlight-content');
    if (!spotlightContent) { console.warn('Board panel not ready for init'); return; }

    // Update header
    const spotlightTitle = document.getElementById('spotlight-title');
    if (spotlightTitle) spotlightTitle.textContent = lessonTitle;
    const badge = document.getElementById('spotlight-type-badge');
    if (badge) badge.textContent = 'VIDEO';

    // Reset board state for fresh draw
    state.boardDraw.active = false;
    state.boardDraw.dismissed = false;
    state.boardDraw.complete = false;
    state.boardDraw.processedLines = 0;

    // Build JSONL commands for the board
    const cmds = [
      `{"cmd":"h1","text":"${lessonTitle.replace(/"/g, '\\"')}"}`,
      `{"cmd":"gap","height":10}`,
      `{"cmd":"text","text":"${courseTitle.replace(/"/g, '\\"')}","color":"#9a9a9a"}`,
      `{"cmd":"gap","height":30}`,
      `{"cmd":"text","text":"What we'll cover:","color":"#5eead4"}`,
      `{"cmd":"gap","height":10}`,
    ];
    sections.slice(0, 6).forEach((s, i) => {
      cmds.push(`{"cmd":"text","text":"${(i + 1)}. ${(s.title || 'Section ' + (i + 1)).replace(/"/g, '\\"')}"}`);
    });
    cmds.push(`{"cmd":"gap","height":30}`);
    cmds.push(`{"cmd":"text","text":"Pause anytime to ask your tutor about what you see.","color":"#52525b"}`);

    // Simulate a board-draw tag being streamed — this triggers the full board rendering pipeline
    const fakeTag = `<teaching-board-draw title="${lessonTitle.replace(/"/g, '&quot;')}">\n${cmds.join('\n')}\n</teaching-board-draw>`;
    bdProcessStreaming(fakeTag);
  }, 600);

  // Set up custom video player
  const overlay = document.getElementById('vm-video-overlay');
  overlay.classList.remove('hidden');
  document.getElementById('vm-vid-wrap').classList.remove('vm-mini');

  const box = overlay.querySelector('.vm-vid-box');
  const lessonVideoUrl = state.video.lessons[state.video.lessonIndex]?.video_url;

  // Create <video> element with Plyr controls
  box.innerHTML = '<video id="vm-video-el" playsinline></video>';
  const video = document.getElementById('vm-video-el');
  video.style.cssText = 'width:100%;display:block;background:#000';

  // Initialize Plyr for polished controls (play/pause, progress, speed, fullscreen)
  let plyrInstance = null;
  if (typeof Plyr !== 'undefined') {
    plyrInstance = new Plyr(video, {
      controls: ['play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'settings', 'fullscreen'],
      settings: ['speed'],
      speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] },
      keyboard: { focused: true, global: false },
      tooltips: { controls: true, seek: true },
    });
  }

  // Get direct stream URL (for YouTube) or use URL directly (for hosted videos)
  const videoId = _extractYTVideoId(lessonVideoUrl);
  if (videoId) {
    // YouTube — extract stream URL via backend
    const streamUrl = await _getStreamUrl(lessonVideoUrl);
    if (streamUrl) {
      video.src = streamUrl;
    } else {
      // Fallback: show thumbnail + message
      box.innerHTML = `<div style="width:100%;aspect-ratio:16/9;background:#111;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:14px">Video loading failed — tutor will teach from transcript</div>`;
      return;
    }
  } else if (lessonVideoUrl) {
    // Direct URL (MP4, HLS, etc.)
    video.src = lessonVideoUrl;
  } else {
    box.innerHTML = '';
    overlay.classList.add('hidden');
    return;
  }

  // Store reference
  state.video.player = video;

  // Event listeners
  // Track seeking state to avoid PiP on seek
  let _isSeeking = false;
  video.addEventListener('seeking', () => { _isSeeking = true; });
  video.addEventListener('seeked', () => { setTimeout(() => { _isSeeking = false; }, 300); });

  // Only trigger PiP on intentional pause (not seeking)
  video.addEventListener('pause', () => {
    if (!state.video.active || _isSeeking) return;
    // Delay slightly — if a play event follows quickly (seeking), don't PiP
    setTimeout(() => {
      if (video.paused && !_isSeeking && state.video.active) _vmOnPause();
    }, 200);
  });
  video.addEventListener('playing', () => { if (state.video.active && state.video.isPaused) _vmOnResume(); });
  video.addEventListener('timeupdate', () => {
    if (state.video.active && video.currentTime) {
      state.video.currentTimestamp = video.currentTime;
    }
  });
}


// ── BYO Video Watch-Along ──────────────────────────────────
// Like vmStartVideoForLesson but for student's own uploaded/linked videos.
// Orchestrator calls this via SESSION_START with mode=watch_along + resource_id.

async function vmStartBYOVideo(resourceId, collectionId, title, sourceUrl) {
  state.video.active = true;
  state.video.byoResourceId = resourceId;
  state.video.byoCollectionId = collectionId;
  state.video.lessonTitle = title || 'Video';
  state.video.sections = [];

  // Show teaching layout — video mode (no plan sidebar)
  document.body.classList.add('video-mode');
  _hideAllScreens();
  document.getElementById('teaching-layout').classList.remove('hidden');
  hidePlanSidebar();
  state._videoWatchAlong = true; // Prevent plan sidebar from showing
  state.teachingMode = 'video_follow'; // Persisted to session for restore
  document.getElementById('teaching-layout').style.display = 'flex';

  // Session should already be created by the orchestrator
  if (!state.sessionId) state.sessionId = generateId();
  state.sessionStartTime = Date.now();
  state.messages = [];
  state.studentIntent = `Video watch-along: ${title}`;

  Router.navigate(`/session/${state.sessionId}`, { replace: true, skipHandler: true });

  // Init board
  setTimeout(() => {
    const spotlightTitle = document.getElementById('spotlight-title');
    if (spotlightTitle) spotlightTitle.textContent = title;
    const badge = document.getElementById('spotlight-type-badge');
    if (badge) badge.textContent = 'VIDEO';

    state.boardDraw.active = false;
    state.boardDraw.dismissed = false;
    state.boardDraw.complete = false;
    state.boardDraw.processedLines = 0;

    const cmds = [
      `{"cmd":"h1","text":"${(title || 'Video').replace(/"/g, '\\"')}"}`,
      `{"cmd":"gap","height":20}`,
      `{"cmd":"text","text":"Watching with your tutor — pause anytime to ask questions.","color":"#52525b"}`,
    ];
    const fakeTag = `<teaching-board-draw title="${(title || 'Video').replace(/"/g, '&quot;')}">\n${cmds.join('\n')}\n</teaching-board-draw>`;
    bdProcessStreaming(fakeTag);
  }, 600);

  // Set up video player
  const overlay = document.getElementById('vm-video-overlay');
  overlay.classList.remove('hidden');
  document.getElementById('vm-vid-wrap').classList.remove('vm-mini');

  const box = overlay.querySelector('.vm-vid-box');
  box.innerHTML = '<video id="vm-video-el" playsinline></video>';
  const video = document.getElementById('vm-video-el');
  video.style.cssText = 'width:100%;display:block;background:#000';

  // Initialize Plyr
  if (typeof Plyr !== 'undefined') {
    new Plyr(video, {
      controls: ['play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'settings', 'fullscreen'],
      settings: ['speed'],
      speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] },
    });
  }

  // Determine video source — YouTube uses IFrame API, uploads use <video>
  const ytId = sourceUrl ? _extractYTVideoId(sourceUrl) : null;
  if (ytId) {
    // YouTube — use IFrame API for pause/play event detection
    state.video.isYouTube = true;
    box.innerHTML = '<div id="vm-yt-player-target"></div>';

    // Load YouTube IFrame API if not already loaded
    if (!window.YT || !window.YT.Player) {
      const tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      document.head.appendChild(tag);
    }

    const initYTPlayer = () => {
      state.video._ytPlayer = new YT.Player('vm-yt-player-target', {
        videoId: ytId,
        width: '100%',
        playerVars: { autoplay: 0, rel: 0, modestbranding: 1, enablejsapi: 1 },
        events: {
          onStateChange: (e) => {
            // YT.PlayerState: PAUSED=2, PLAYING=1, BUFFERING=3
            if (e.data === YT.PlayerState.PAUSED && state.video.active) {
              state.video.currentTimestamp = state.video._ytPlayer.getCurrentTime();
              setTimeout(() => {
                // Check still paused (not just seeking)
                if (state.video._ytPlayer.getPlayerState() === YT.PlayerState.PAUSED && state.video.active) {
                  _vmOnPause();
                }
              }, 300);
            } else if (e.data === YT.PlayerState.PLAYING && state.video.isPaused) {
              _vmOnResume();
            }
          },
          onReady: () => {
            // Style the iframe
            const iframe = document.querySelector('#vm-yt-player-target iframe');
            if (iframe) {
              iframe.style.borderRadius = '8px';
              iframe.style.width = '100%';
              iframe.style.aspectRatio = '16/9';
            }
          },
        },
      });
    };

    // Init when API is ready
    if (window.YT && window.YT.Player) {
      initYTPlayer();
    } else {
      window.onYouTubeIframeAPIReady = initYTPlayer;
    }

    // Poll timestamp (YT API doesn't have timeupdate event)
    state.video._ytTimerInterval = setInterval(() => {
      if (state.video._ytPlayer && typeof state.video._ytPlayer.getCurrentTime === 'function') {
        state.video.currentTimestamp = state.video._ytPlayer.getCurrentTime();
      }
    }, 1000);

    state.video.player = null;
  } else if (sourceUrl) {
    video.src = sourceUrl;
    state.video.player = video;
  } else if (resourceId) {
    video.src = `${state.apiUrl}/api/v1/byo/resources/${resourceId}/file`;
    state.video.player = video;
  } else {
    box.innerHTML = '<div style="width:100%;aspect-ratio:16/9;background:#111;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:14px;border-radius:8px">No video source available</div>';
    state.video.player = null;
  }

  // Event listeners — only for <video> element (not YouTube iframe)
  if (state.video.player) {
    let _isSeeking = false;
    video.addEventListener('seeking', () => { _isSeeking = true; });
    video.addEventListener('seeked', () => { setTimeout(() => { _isSeeking = false; }, 300); });
    video.addEventListener('pause', () => {
      if (!state.video.active || _isSeeking) return;
      setTimeout(() => {
        if (video.paused && !_isSeeking && state.video.active) _vmOnPause();
      }, 200);
    });
    video.addEventListener('playing', () => { if (state.video.active && state.video.isPaused) _vmOnResume(); });
    video.addEventListener('timeupdate', () => {
      if (state.video.active && video.currentTime) {
        state.video.currentTimestamp = video.currentTime;
      }
    });
  }

  // Trigger first chat message to start the tutor follow-along
  const trigger = `[SYSTEM] Student is watching "${title}" — a BYO video watch-along session. ` +
    `BYO resource_id: ${resourceId}, collection_id: ${collectionId || ''}. ` +
    `Use byo_transcript_context(resource_id, timestamp) when the student pauses to understand what they just watched. ` +
    `Greet them briefly and let them know you're following along.`;
  setTimeout(() => streamADK(trigger, true, true), 1000);
}
window.vmStartBYOVideo = vmStartBYOVideo;

window.vmExitVideoSession = function() {
  // Stop video playback
  const video = document.getElementById('vm-video-el');
  if (video) { try { video.pause(); video.src = ''; } catch(e) {} }
  // Clear iframe (YouTube embed)
  const iframe = document.getElementById('vm-yt-iframe');
  if (iframe) iframe.src = '';

  state.video.active = false;
  state.video.player = null;

  // Hide overlay
  const overlay = document.getElementById('vm-video-overlay');
  if (overlay) overlay.classList.add('hidden');
  document.getElementById('vm-vid-wrap')?.classList.remove('vm-mini');

  // Clean up session
  document.body.classList.remove('video-mode');
  cleanupActiveSession();
  Router.navigate('/home');
};

function _vmOnPause() {
  if (state.video.isPaused) return;
  state.video.isPaused = true;
  if (state.video.player?.currentTime) state.video.currentTimestamp = state.video.player.currentTime;

  const t = state.video.currentTimestamp;
  const section = state.video.sections.find(s => s.start_seconds <= t && s.end_seconds >= t) || state.video.sections[state.video.sections.length - 1];
  if (section) { state.video.currentSectionIndex = section.index; state.video.sectionTitle = section.title || ''; }

  document.getElementById('vm-vid-wrap').classList.add('vm-mini');
  const chatWrap = document.getElementById('vm-chat-wrap');
  if (chatWrap) chatWrap.classList.add('vm-show');
  const input = document.getElementById('vm-chat-input');
  if (input) setTimeout(() => input.focus(), 400);
}

function _vmOnResume() {
  state.video.isPaused = false;
  document.getElementById('vm-vid-wrap').classList.remove('vm-mini');
  const chatWrap = document.getElementById('vm-chat-wrap');
  if (chatWrap) chatWrap.classList.remove('vm-show');
}

function vmResumeVideo() {
  if (state.video._ytPlayer && typeof state.video._ytPlayer.playVideo === 'function') {
    state.video._ytPlayer.playVideo();
  } else {
    const el = document.getElementById('vm-video-el');
    if (el?.play) el.play();
  }
  _vmOnResume();
}

function vmSeekVideo(timestamp) {
  if (state.video._ytPlayer && typeof state.video._ytPlayer.seekTo === 'function') {
    state.video._ytPlayer.seekTo(timestamp, true);
  } else {
    const el = document.getElementById('vm-video-el');
    if (el) el.currentTime = timestamp;
  }
  state.video.currentTimestamp = timestamp;
}

function cleanupVideoMode() {
  state.video.active = false;
  document.body.classList.remove('video-mode');
  if (state.video.player) { try { state.video.player.pause(); state.video.player.src = ''; } catch (e) {} state.video.player = null; }
  const overlay = document.getElementById('vm-video-overlay');
  if (overlay) { overlay.classList.add('hidden'); }
  document.getElementById('vm-chat-wrap')?.classList.remove('vm-show');
}

// Chat input → send via streamADK
// Board pen toggle — always accessible from header
window.toggleBoardPen = function() {
  const btn = document.getElementById('board-pen-toggle');
  const bd = state.boardDraw;
  if (!btn) return;

  if (bd.drawingEnabled) {
    bd.drawingEnabled = false;
    btn.classList.remove('active');
    document.getElementById('bd-canvas-wrap')?.style.setProperty('cursor', 'default');
    _hidePenToolbar();
  } else {
    bd.drawingEnabled = true;
    bd.studentColor = '#22ee66';
    bd.studentStrokeW = 2.5;
    btn.classList.add('active');
    document.getElementById('bd-canvas-wrap')?.style.setProperty('cursor', 'crosshair');
    _showPenToolbar();

    // Ensure drawing event listeners are attached to the board canvas
    const canvas = document.querySelector('#bd-canvas-wrap canvas') || document.querySelector('#spotlight-content canvas');
    if (canvas && !canvas._bdStudentDrawInit) {
      bdInitStudentDrawing(canvas);
      canvas._bdStudentDrawInit = true;
    }
  }
};

const PEN_COLORS = [
  { color: '#22ee66', label: 'Green' },
  { color: '#f87171', label: 'Red' },
  { color: '#60a5fa', label: 'Blue' },
  { color: '#fbbf24', label: 'Yellow' },
  { color: '#ffffff', label: 'White' },
];

function _showPenToolbar() {
  let tb = document.getElementById('pen-draw-toolbar');
  if (tb) { tb.classList.remove('hidden'); return; }

  tb = document.createElement('div');
  tb.id = 'pen-draw-toolbar';
  tb.className = 'pen-toolbar';
  tb.innerHTML = `
    <span class="pen-tb-label">Draw</span>
    ${PEN_COLORS.map((c, i) =>
      `<button class="pen-tb-color${i === 0 ? ' active' : ''}" data-color="${c.color}" title="${c.label}" style="background:${c.color}"></button>`
    ).join('')}
    <span class="pen-tb-sep"></span>
    <button class="pen-tb-btn" id="pen-tb-eraser" title="Eraser">&#9003;</button>
    <button class="pen-tb-btn" id="pen-tb-clear" title="Clear your drawings">Clear</button>
    <span class="pen-tb-sep"></span>
    <button class="pen-tb-btn pen-tb-close" title="Close pen">&#10005;</button>
  `;

  // Insert at the top of the board content area
  const boardPanel = document.getElementById('board-panel');
  const spotlightContent = document.getElementById('spotlight-content');
  if (boardPanel && spotlightContent) {
    boardPanel.insertBefore(tb, spotlightContent);
  }

  // Wire color buttons
  tb.querySelectorAll('.pen-tb-color').forEach(btn => {
    btn.addEventListener('click', () => {
      tb.querySelectorAll('.pen-tb-color').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.boardDraw.studentColor = btn.dataset.color;
      state.boardDraw.studentStrokeW = 2.5;
      document.getElementById('pen-tb-eraser')?.classList.remove('active');
      document.getElementById('bd-canvas-wrap')?.style.setProperty('cursor', 'crosshair');
    });
  });

  // Eraser
  document.getElementById('pen-tb-eraser')?.addEventListener('click', function() {
    const isErasing = this.classList.toggle('active');
    if (isErasing) {
      tb.querySelectorAll('.pen-tb-color').forEach(b => b.classList.remove('active'));
      state.boardDraw.studentColor = '#0f1012';
      state.boardDraw.studentStrokeW = 12;
      document.getElementById('bd-canvas-wrap')?.style.setProperty('cursor', 'cell');
    } else {
      const activeColor = tb.querySelector('.pen-tb-color')?.dataset.color || '#22ee66';
      state.boardDraw.studentColor = activeColor;
      state.boardDraw.studentStrokeW = 2.5;
      document.getElementById('bd-canvas-wrap')?.style.setProperty('cursor', 'crosshair');
    }
  });

  // Clear
  document.getElementById('pen-tb-clear')?.addEventListener('click', () => {
    state.boardDraw.studentDrawing = false;
    // Clear student strokes by redrawing board without them
    if (typeof BoardEngine !== 'undefined' && BoardEngine.redraw) BoardEngine.redraw();
  });

  // Close
  tb.querySelector('.pen-tb-close')?.addEventListener('click', () => toggleBoardPen());
}

function _hidePenToolbar() {
  const tb = document.getElementById('pen-draw-toolbar');
  if (tb) tb.classList.add('hidden');
}

function _vmSendMessage() {
  const input = document.getElementById('vm-chat-input');
  const text = (input?.value || '').trim();
  if (!text || state.isStreaming) return;
  input.value = '';

  // If student has drawn on the board, auto-capture and include with message
  if (state.boardDraw.studentDrawing && typeof bdCaptureAndSend === 'function') {
    // Capture board then send text + image together
    bdCaptureAndSend();
    // Also send the text message
    if (text !== '[Board drawing sent to tutor]') {
      streamADK(text, false, false);
    }
  } else {
    streamADK(text, false, false);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const sendBtn = document.getElementById('vm-send-btn');
  const chatInput = document.getElementById('vm-chat-input');
  if (sendBtn) sendBtn.addEventListener('click', _vmSendMessage);
  if (chatInput) chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _vmSendMessage(); } });
});

// ═══════════════════════════════════════════════════════════════
//   Feedback / Bug Report / Contact Form
// ═══════════════════════════════════════════════════════════════

let _fbAttachments = []; // [{filename, content (base64)}]

function openFeedbackModal(type) {
  const overlay = document.getElementById('fb-overlay');
  if (!overlay) return;
  overlay.style.display = 'flex';
  document.getElementById('fb-type').value = type || 'feedback';

  const titles = { bug: 'Report a Bug', feedback: 'Send Feedback', contact: 'Contact Us' };
  document.getElementById('fb-title').textContent = titles[type] || 'Send Feedback';

  const placeholders = {
    bug: 'Describe the bug: what happened, what you expected, and steps to reproduce...',
    feedback: 'Tell us what\'s on your mind — ideas, suggestions, or what\'s working well...',
    contact: 'How can we help?',
  };
  document.getElementById('fb-message').placeholder = placeholders[type] || placeholders.feedback;

  // Pre-fill user info if logged in
  const user = typeof AuthManager !== 'undefined' ? AuthManager.getUser() : null;
  if (user) {
    document.getElementById('fb-name').value = user.name || '';
    document.getElementById('fb-email').value = user.email || '';
  }

  // Reset state
  _fbAttachments = [];
  document.getElementById('fb-file-list').innerHTML = '';
  document.getElementById('fb-status').textContent = '';
  document.getElementById('fb-submit').disabled = false;
}
window.openFeedbackModal = openFeedbackModal;

function closeFeedbackModal() {
  const overlay = document.getElementById('fb-overlay');
  if (overlay) overlay.style.display = 'none';
  _fbAttachments = [];
}
window.closeFeedbackModal = closeFeedbackModal;

function handleFeedbackFiles(input) {
  const files = Array.from(input.files || []);
  const list = document.getElementById('fb-file-list');

  for (const file of files.slice(0, 5 - _fbAttachments.length)) {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result.split(',')[1]; // strip data:...;base64,
      _fbAttachments.push({ filename: file.name, content: base64 });

      const tag = document.createElement('span');
      tag.className = 'fb-file-tag';
      tag.innerHTML = `${file.name} <span class="fb-file-remove" onclick="this.parentElement.remove();_fbAttachments=_fbAttachments.filter(a=>a.filename!=='${file.name.replace(/'/g, "\\'")}')">&times;</span>`;
      list.appendChild(tag);
    };
    reader.readAsDataURL(file);
  }
  input.value = ''; // reset so same file can be re-selected
}
window.handleFeedbackFiles = handleFeedbackFiles;

async function submitFeedback(e) {
  e.preventDefault();
  const btn = document.getElementById('fb-submit');
  const status = document.getElementById('fb-status');
  btn.disabled = true;
  btn.textContent = 'Sending...';
  status.textContent = '';
  status.className = 'fb-status';

  const payload = {
    type: document.getElementById('fb-type').value,
    name: document.getElementById('fb-name').value.trim(),
    email: document.getElementById('fb-email').value.trim(),
    message: document.getElementById('fb-message').value.trim(),
    page: window.location.pathname,
    attachments: _fbAttachments,
  };

  try {
    const apiUrl = typeof state !== 'undefined' ? (state.apiUrl || '') : '';
    const headers = { 'Content-Type': 'application/json' };
    if (typeof AuthManager !== 'undefined') Object.assign(headers, AuthManager.authHeaders());

    const res = await fetch(`${apiUrl}/api/v1/feedback`, {
      method: 'POST', headers, body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.status === 'sent' || data.status === 'received') {
      status.textContent = 'Thank you! Your message has been sent.';
      status.className = 'fb-status success';
      btn.textContent = 'Sent!';
      setTimeout(() => closeFeedbackModal(), 2000);
    } else {
      throw new Error(data.error || 'Failed to send');
    }
  } catch (err) {
    status.textContent = 'Failed to send. Please try again.';
    status.className = 'fb-status error';
    btn.disabled = false;
    btn.textContent = 'Send';
  }
}
window.submitFeedback = submitFeedback;
