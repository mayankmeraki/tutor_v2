/**
 * Path Journey — frontend module for learning paths.
 *
 * Handles:
 *   - Scope hint chip (shown when classifier detects broad intent)
 *   - Path wizard modal (4 directed taps → path generation)
 *   - Path cards on home screen (active paths, progress, up-next)
 *   - Path detail view (node list, progress, refine chat)
 *   - Path breadcrumb in session (position, what's next)
 *   - Reflection overlay (after node completes)
 *   - Path completion screen
 */

/* global state, AuthManager, Router, _showTransitionLoader, _hideTransitionLoader,
   _startOnDemandSession, startNewSession, _escHtml */

// ── Markdown helper ──────────────────────────────────────────────
// Parse and render path-node/path-phase tags from streaming text
let _streamedNodes = [];
let _streamedPhase = 'General';
let _streamedPhasePlanned = false;
let _parsedUpTo = 0; // Track how much text we've already parsed

function _parsePathTags(text) {
  // Only parse NEW text beyond what we've already processed
  if (text.length <= _parsedUpTo) {
    // Strip already-parsed tags from display
    return text.replace(/<path-(phase|node)\s+[^>]+\/>/g, '').trim();
  }
  const newPart = text.slice(_parsedUpTo);
  _parsedUpTo = text.length;

  let cleaned = text;
  let changed = false;

  // Parse phases from new part only
  newPart.replace(/<path-phase\s+([^>]+)\/>/g, (_, attrs) => {
    const nameMatch = attrs.match(/name="([^"]+)"/);
    _streamedPhase = nameMatch ? nameMatch[1] : 'General';
    _streamedPhasePlanned = attrs.includes('planned="true"');
    changed = true;
    return '';
  });

  // Parse nodes from new part only
  newPart.replace(/<path-node\s+([^>]+)\/>/g, (_, attrs) => {
    const get = (key) => { const m = attrs.match(new RegExp(`${key}="([^"]+)"`)); return m ? m[1] : ''; };
    const node = {
      title: get('title'),
      type: get('type') || 'learn',
      targetMin: parseInt(get('targetMin')) || 30,
      topics: (get('topics') || '').split(',').map(t => t.trim()).filter(Boolean),
      milestone: get('milestone') === 'true',
      placeholder: get('placeholder') === 'true' || _streamedPhasePlanned,
      phase: _streamedPhase,
      order: _streamedNodes.length + 1,
      nodeId: `ns${_streamedNodes.length + 1}`,
      status: 'pending',
    };
    _streamedNodes.push(node);
    _renderStreamedNode(node);
    changed = true;
    return '';
  });

  if (changed) {
    _saveStreamedNodes();
  }

  // Always strip ALL path tags from display text
  return text.replace(/<path-(phase|node)\s+[^>]+\/>/g, '').trim();
}

function _renderStreamedNode(node) {
  const el = document.getElementById('wiz-artifact') || document.getElementById('path-artifact-panel');
  if (!el) return;

  if (_streamedNodes.length === 1) {
    el.innerHTML = `<div id="wiz-streamed-nodes" style="padding:4px 0"></div>`;
  }

  const container = document.getElementById('wiz-streamed-nodes') || el;
  const tc = { learn: '#34d399', drill: '#fb923c', quiz: '#a78bfa', build: '#fbbf24' }[node.type] || '#60a5fa';

  // Phase header
  const prevNode = _streamedNodes[_streamedNodes.length - 2];
  const isNewPhase = !prevNode || prevNode.phase !== node.phase;
  const phaseCount = new Set(_streamedNodes.map(n => n.phase)).size;
  const isFirstPhase = phaseCount <= 1;

  if (isNewPhase) {
    const phId = `wiz-ph-${phaseCount}`;
    container.innerHTML += `<div style="margin:${prevNode ? '14px' : '0'} 0 6px">
      <div onclick="var e=document.getElementById('${phId}');if(e)e.style.display=e.style.display==='none'?'':'none'"
        style="font-size:9px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;
        color:rgba(255,255,255,.25);cursor:pointer;display:flex;align-items:center;gap:5px;
        padding:4px 0;user-select:none">
        <span style="width:8px;height:8px;border-radius:50%;background:rgba(52,211,153,.15);flex-shrink:0"></span>
        ${_escHtml(node.phase)}
        <span style="font-size:8px;color:rgba(255,255,255,.1);margin-left:auto">${isFirstPhase ? '&#9660;' : '&#9654;'}</span>
      </div>
      <div id="${phId}" style="${isFirstPhase ? '' : 'display:none'}"></div>
    </div>`;
  }

  const phContainer = document.getElementById(`wiz-ph-${phaseCount}`) || container;

  // Subtopics as vertical connected list
  const topics = node.topics || [];
  const topicHtml = topics.length ? `<div style="padding-left:28px;margin-top:4px">
    ${topics.map(t => `<div style="display:flex;align-items:baseline;gap:6px;padding:2px 0">
      <span style="width:4px;height:4px;border-radius:50%;background:rgba(255,255,255,.1);flex-shrink:0;margin-top:4px"></span>
      <span style="font-size:10px;color:rgba(255,255,255,.3);line-height:1.4">${_escHtml(t)}</span>
    </div>`).join('')}
  </div>` : '';

  if (node.placeholder) {
    phContainer.innerHTML += `<div style="padding:8px 10px;border-radius:8px;border:1px dashed rgba(255,255,255,.05);
      margin-bottom:4px;opacity:.4;animation:scopeHintIn .2s ease">
      <span style="font-size:11px;color:rgba(255,255,255,.3);font-style:italic">${_escHtml(node.title)}</span>
    </div>`;
  } else {
    phContainer.innerHTML += `<div style="padding:8px 10px;border-radius:8px;background:rgba(255,255,255,.015);
      border:1px solid rgba(255,255,255,.04);margin-bottom:4px;animation:scopeHintIn .2s ease">
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:20px;height:20px;border-radius:50%;background:${tc}12;color:${tc};
          display:grid;place-items:center;font-size:9px;font-weight:700;flex-shrink:0">${node.milestone ? '★' : node.order}</div>
        <span style="font-size:12px;font-weight:600;color:rgba(255,255,255,.8);flex:1">${_escHtml(node.title)}</span>
        <span style="font-size:9px;color:rgba(255,255,255,.15);flex-shrink:0">${node.targetMin}m</span>
      </div>
      ${topicHtml}
    </div>`;
  }

  el.scrollTop = el.scrollHeight;
}

async function _saveStreamedNodes() {
  const path = PathState.activePath;
  if (!path || !_streamedNodes.length) return;
  // Debounce — save after 500ms of no new nodes
  if (_saveStreamedNodes._timer) clearTimeout(_saveStreamedNodes._timer);
  _saveStreamedNodes._timer = setTimeout(async () => {
    try {
      const nodes = _streamedNodes.map((n, i) => ({...n, nodeId: `n${i+1}`, order: i+1}));
      await fetch(`${state.apiUrl || ''}/api/v1/paths/${path.pathId}`, {
        method: 'PATCH', headers: _pathHeaders(),
        body: JSON.stringify({
          status: 'active',
          title: path.title || PathState.wizardData.intent || 'Learning path',
        }),
      });
      // Save nodes directly
      const fullPath = await PathAPI.get(path.pathId);
      if (fullPath && (!fullPath.nodes || !fullPath.nodes.length)) {
        await fetch(`${state.apiUrl || ''}/api/v1/paths/${path.pathId}`, {
          method: 'PATCH', headers: _pathHeaders(),
          body: JSON.stringify({ status: 'active' }),
        });
        // Use the reorder endpoint to set nodes (or create via add)
        for (const n of nodes) {
          await fetch(`${state.apiUrl || ''}/api/v1/paths/${path.pathId}/nodes/add`, {
            method: 'POST', headers: _pathHeaders(),
            body: JSON.stringify(n),
          });
        }
      }
      PathState.activePath = await PathAPI.get(path.pathId);
      if (PathState.activePath?.nodes?.length) {
        // Show finalize button
        const el = document.getElementById('wiz-artifact');
        if (el && !el.querySelector('.wiz-finalize')) {
          el.innerHTML += `<div class="wiz-finalize" style="margin-top:10px;text-align:center">
            <div style="font-size:9px;color:rgba(255,255,255,.2);margin-bottom:4px">Keep chatting to adjust, or:</div>
            <button onclick="PathUI.closeWizard();PathUI.openPathDetail('${_escHtml(path.pathId)}')" style="
              padding:9px 20px;border-radius:8px;border:none;background:linear-gradient(135deg,#34d399,#22c584);
              color:#0a0f1a;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit">Finalize path &rarr;</button>
          </div>`;
        }
      }
    } catch(e) { console.warn('[Path] Save streamed nodes failed:', e); }
  }, 800);
}

function _md(text) {
  if (!text) return '';
  // Parse path tags first (renders nodes on artifact)
  text = _parsePathTags(text);
  // Strip leaked tool call XML/JSON
  text = text.replace(/<function_calls>[\s\S]*?<\/function_calls>/g, '');
  text = text.replace(/<invoke[\s\S]*?<\/invoke>/g, '');
  text = text.replace(/<parameter[\s\S]*?<\/parameter>/g, '');
  text = text.replace(/<[^>]*<\/antml:[^>]+>/g, '');
  text = text.replace(/\{\s*"type"\s*:\s*"(learn|drill|quiz|build)"[\s\S]*?\}\s*,?\s*/g, '');
  text = text.replace(/\[\s*\{\s*"type"\s*:\s*"(learn|drill)[\s\S]*?\]\s*/g, '');
  text = text.trim();
  if (!text) return '';
  let html = _escHtml(text);
  // Bold & italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#fff">$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Code
  html = html.replace(/`(.+?)`/g, '<code style="background:rgba(255,255,255,.06);padding:1px 4px;border-radius:3px;font-size:10px">$1</code>');
  // Arrows & hr
  html = html.replace(/→/g, '&rarr;');
  html = html.replace(/---+/g, '<hr style="border:none;border-top:1px solid rgba(255,255,255,.06);margin:6px 0">');
  // Bullet points: lines starting with - or •
  html = html.replace(/^[\-•]\s+(.+)/gm, '<div style="display:flex;gap:6px;padding:1px 0 1px 8px"><span style="color:#34d399;flex-shrink:0">•</span><span>$1</span></div>');
  // Numbered lists
  html = html.replace(/^(\d+)\.\s+(.+)/gm, '<div style="display:flex;gap:6px;padding:1px 0 1px 8px"><span style="color:#34d399;font-weight:600;flex-shrink:0">$1.</span><span>$2</span></div>');
  // Paragraphs
  html = html.replace(/\n\n/g, '</p><p style="margin:5px 0">');
  html = html.replace(/\n/g, '<br>');
  return html;
}

// ── State ────────────────────────────────────────────────────────
const PathState = {
  paths: [],
  activePath: null,        // Full path doc when viewing detail
  wizardData: {},          // Accumulates wizard answers
  isCreating: false,
  currentPathSession: null, // { pathId, nodeId } when inside a path session
  chatHistory: [],         // Persists chat messages across wizard → split-screen
};

// ── Chat history helpers ─────────────────────────────────────────
function _chatBubble(role, html) {
  if (role === 'user') {
    return `<div style="display:flex;justify-content:flex-end;margin-bottom:8px">
      <div style="padding:7px 11px;border-radius:10px 10px 4px 10px;background:rgba(96,165,250,.1);
        border:1px solid rgba(96,165,250,.15);font-size:11.5px;color:#fff;max-width:80%">${html}</div></div>`;
  }
  return `<div style="display:flex;align-items:flex-start;gap:7px;margin-bottom:8px">
    <div style="width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
      display:grid;place-items:center;font-size:8px;font-weight:800;color:#0a0f1a;flex-shrink:0;margin-top:1px">E</div>
    <div style="font-size:11.5px;color:rgba(255,255,255,.8);line-height:1.5;flex:1">${html}</div></div>`;
}

function _addChatMsg(role, text) {
  // Render only — backend handles persistence via the refine endpoint
  PathState.chatHistory.push({ role, text });
  const el = document.getElementById('path-refine-msgs');
  if (el) {
    const html = role === 'user' ? _escHtml(text) : _md(text);
    el.innerHTML += _chatBubble(role, html);
    el.scrollTop = el.scrollHeight;
  }
}

function _loadChatHistory(path) {
  // Load from path doc and restore to state + DOM
  PathState.chatHistory = (path.chatHistory || []).slice(-50);
  const el = document.getElementById('path-refine-msgs');
  if (!el) return;
  el.innerHTML = '';
  for (const m of PathState.chatHistory) {
    const html = m.role === 'user' ? _escHtml(m.text || '') : _md(m.text || '');
    el.innerHTML += _chatBubble(m.role, html);
  }
  el.scrollTop = el.scrollHeight;
}

function _updateArtifactPanel(path) {
  // Re-render the artifact inner (hero + timeline) without touching the chat
  const panel = document.getElementById('path-artifact-panel');
  const inner = panel?.querySelector('.path-artifact-inner');
  if (!inner) return;

  const nodes = path.nodes || [];
  const done = nodes.filter(n => n.status === 'completed').length;
  const total = nodes.length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const next = nodes.find(n => n.status === 'pending' || n.status === 'active');
  const _pid = _escHtml(path.pathId);
  const timelineHtml = _buildTimeline(path, nodes, next);

  // Reflection banner
  const recentNotes = (path.pathNotes || []).slice(-3);
  const lastStrength = recentNotes.filter(n => n.kind === 'strength').slice(-1)[0];
  const lastGap = recentNotes.filter(n => n.kind === 'gap').slice(-1)[0];
  let reflBanner = '';
  if (lastStrength || lastGap) {
    const parts = [];
    if (lastStrength) parts.push(`<strong>${_escHtml(lastStrength.concept)}</strong> is solid`);
    if (lastGap) parts.push(`<strong>${_escHtml(lastGap.concept)}</strong> needs work`);
    reflBanner = `<div style="margin-bottom:14px;padding:10px 12px;border-radius:9px;background:rgba(251,191,36,.04);
      border:1px solid rgba(251,191,36,.12);display:flex;gap:8px;font-size:11px;color:rgba(251,191,36,.85);line-height:1.5">
      <span>&#128161;</span><span>From recent sessions: ${parts.join('. ')}.</span>
      <button onclick="this.parentElement.remove()" style="font-size:10px;color:rgba(255,255,255,.2);background:none;border:none;cursor:pointer;flex-shrink:0">&times;</button>
    </div>`;
  }

  inner.innerHTML = `
    ${next ? `<div style="padding:18px 20px;border-radius:14px;margin-bottom:16px;
      background:linear-gradient(135deg,rgba(52,211,153,.06),rgba(96,165,250,.03));border:1px solid rgba(52,211,153,.18)">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <div style="font-size:8px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
          color:rgba(52,211,153,.85);display:flex;align-items:center;gap:5px">
          <span style="width:5px;height:5px;border-radius:50%;background:#34d399"></span>
          Up next &middot; ${next.type}</div>
        <span style="font-size:11px;color:rgba(255,255,255,.25)">~${next.targetMin}m</span>
      </div>
      <div style="font-size:18px;font-weight:800;color:#fff;letter-spacing:-.3px;margin-bottom:3px">${_escHtml(next.title)}</div>
      ${next.subtitle ? `<div style="font-size:11px;color:rgba(255,255,255,.4);margin-bottom:10px">${_escHtml(next.subtitle)}</div>` : ''}
      <button onclick="PathUI.continueNode('${_pid}','${_escHtml(next.nodeId)}')" style="width:100%;padding:11px;
        border-radius:10px;border:none;background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
        font-size:13px;font-weight:700;cursor:pointer;font-family:inherit">Start session ${done + 1} &rarr;</button>
    </div>` : ''}
    ${reflBanner}
    ${timelineHtml}
  `;

  // Update the action button
  const actBtn = document.getElementById('path-action-btn');
  if (actBtn && next) {
    actBtn.setAttribute('onclick', `PathUI.continueNode('${_escHtml(path.pathId)}','${_escHtml(next.nodeId)}')`);
  }
}

// ── API helpers ──────────────────────────────────────────────────
function _pathHeaders() {
  return { ...AuthManager.authHeaders(), 'Content-Type': 'application/json' };
}

const PathAPI = {
  async list(status) {
    const url = `${state.apiUrl || ''}/api/v1/paths${status ? `?status=${status}` : ''}`;
    const res = await fetch(url, { headers: _pathHeaders() });
    return res.ok ? res.json() : [];
  },

  async get(pathId) {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}`, { headers: _pathHeaders() });
    return res.ok ? res.json() : null;
  },

  // plan() is handled directly in _generatePath() with SSE streaming.
  // This method is kept for non-streaming fallback.
  async plan(wizardData) {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/plan`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify(wizardData),
    });
    if (!res.ok) throw new Error('Path planning failed');
    return res;  // Returns raw response (SSE stream or JSON)
  },

  async startNode(pathId, nodeId, sessionId) {
    return fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/${nodeId}/start`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify({ sessionId }),
    });
  },

  async completeNode(pathId, nodeId) {
    return fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/${nodeId}/complete`, {
      method: 'POST', headers: _pathHeaders(),
    });
  },

  async reflect(pathId, nodeId, sessionId) {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/reflect`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify({ nodeId, sessionId }),
    });
    return res.ok ? res.json() : null;
  },

  async refine(pathId, message) {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/refine`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify({ message }),
    });
    return res.ok ? res.json() : null;
  },

  async applyPivot(pathId, pivotIndex, nodes) {
    return fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/pivots/${pivotIndex}/apply`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify({ nodes }),
    });
  },

  async nextNode(pathId) {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/next`, { headers: _pathHeaders() });
    return res.ok ? res.json() : null;
  },

  async deletePath(pathId) {
    return fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}`, {
      method: 'DELETE', headers: _pathHeaders(),
    });
  },
};


// ── Scope hint chip (Stage 1 from mockup) ────────────────────────
function showScopeHint(intentText, blueprint) {
  const wrap = document.getElementById('euler-scope-chip-wrap');
  if (!wrap) return;

  const scope = blueprint.scope || 'narrow';
  const confidence = blueprint.scope_confidence || 0;

  // Only show for broad/medium with decent confidence
  if (scope === 'narrow' || confidence < 0.6) {
    wrap.style.display = 'none';
    return;
  }

  wrap.style.display = 'flex';
  wrap.innerHTML = `
    <div class="scope-hint" style="
      display:flex;gap:10px;align-items:center;padding:12px 14px;border-radius:11px;
      background:rgba(52,211,153,.06);border:1px solid rgba(52,211,153,.2);
      animation:scopeHintIn .3s ease;width:100%;
    ">
      <div style="
        width:28px;height:28px;border-radius:50%;flex-shrink:0;
        background:linear-gradient(135deg,#34d399,#22c584);
        display:grid;place-items:center;font-size:12px;font-weight:800;color:#0a0f1a;
      ">E</div>
      <div style="flex:1;text-align:left">
        <div style="font-size:12px;color:rgba(255,255,255,.9)">
          <strong style="color:#34d399">${_escHtml(intentText.slice(0, 40))}</strong>
          ${intentText.length > 40 ? '...' : ''} — that's a multi-session topic.
          I can set up a <strong style="color:#34d399">learning path</strong> to pace it for you.
        </div>
        <div style="font-size:10.5px;color:rgba(255,255,255,.35);margin-top:2px">
          Detected: <strong style="color:#60a5fa">${blueprint.mode}</strong> ·
          ${scope} scope · ~30s setup
        </div>
      </div>
      <button onclick="PathUI.dismissScopeHint();_startOnDemandSession('${_escHtml(intentText)}')"
        class="scope-hint-btn-secondary" style="
        padding:7px 13px;border-radius:8px;border:1px solid rgba(255,255,255,.1);
        background:none;color:rgba(255,255,255,.6);font-size:11px;font-weight:600;
        cursor:pointer;font-family:inherit;flex-shrink:0;white-space:nowrap;
      ">Just one session</button>
      <button onclick="PathUI.startWizard('${_escHtml(intentText)}', '${blueprint.mode}')"
        style="
        padding:7px 13px;border-radius:8px;border:none;
        background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
        font-size:11px;font-weight:700;cursor:pointer;font-family:inherit;
        flex-shrink:0;white-space:nowrap;
      ">Set up path &rarr;</button>
    </div>
  `;
}

// ── Path wizard modal (Stage 2) — agent-driven ──────────────────
// Questions are fetched from POST /api/v1/paths/wizard (Haiku generates
// them dynamically based on intent). No hardcoded steps.

let _wizardQuestions = []; // Populated by API call

async function _renderWizardModal(intentText, mode) {
  // Remove existing if any
  document.getElementById('path-wizard-modal')?.remove();

  const modal = document.createElement('div');
  modal.id = 'path-wizard-modal';
  modal.className = 'path-wizard-overlay';
  modal.innerHTML = `
    <div class="path-wizard-card">
      <div class="path-wizard-header">
        <div class="path-wizard-header-ic">E</div>
        <div>
          <div style="font-size:9px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:rgba(52,211,153,.85)">Path setup</div>
          <div style="font-size:15px;font-weight:700;color:#fff">${_escHtml(intentText.slice(0, 50))}</div>
        </div>
        <button onclick="PathUI.closeWizard()" style="
          margin-left:auto;width:28px;height:28px;border-radius:50%;border:1px solid rgba(255,255,255,.1);
          background:none;color:rgba(255,255,255,.4);cursor:pointer;font-size:14px;
          display:grid;place-items:center;
        ">&times;</button>
      </div>
      <div class="path-wizard-body" id="path-wizard-body">
        <div style="text-align:center;padding:30px 20px">
          <div class="path-gen-spinner"></div>
          <div style="font-size:12px;color:rgba(255,255,255,.4);margin-top:10px">Tailoring questions to your topic...</div>
        </div>
      </div>
      <div class="path-wizard-footer" id="path-wizard-footer"></div>
    </div>
  `;
  document.body.appendChild(modal);

  PathState.wizardData = { intent: intentText, mode };
  PathState._wizardStep = 0;

  // Fetch dynamic wizard questions (with 8s timeout)
  try {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 8000);
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/wizard`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify({ intent: intentText }),
      signal: ac.signal,
    });
    clearTimeout(timer);
    if (res.ok) {
      const data = await res.json();
      _wizardQuestions = data.questions || [];
    }
  } catch (e) {
    console.warn('[Path] Wizard questions failed (using defaults):', e.name === 'AbortError' ? 'timeout' : e);
  }

  // Fallback — always works, no LLM needed
  if (!_wizardQuestions.length) {
    _wizardQuestions = [
      { key: "starting_point", question: "What do you already know about this?", chips: [
        {label: "Starting fresh", value: "none"},
        {label: "Know the basics", value: "basics"},
        {label: "Been doing this", value: "intermediate"},
        {label: "Want advanced only", value: "advanced"},
      ]},
      { key: "motivation", question: "Why are you learning this?", chips: [
        {label: "Job / interviews", value: "job"},
        {label: "Building something", value: "project"},
        {label: "Course / exam", value: "course"},
        {label: "Just curious", value: "curiosity"},
      ]},
      { key: "pace", question: "How deep do you want to go?", chips: [
        {label: "Quick sprint", value: "quick"},
        {label: "Solid foundation", value: "thorough"},
        {label: "Full deep dive", value: "deep"},
      ]},
    ];
  }

  _renderWizardStep(0);
}

function _renderWizardStep(stepIndex) {
  const body = document.getElementById('path-wizard-body');
  const footer = document.getElementById('path-wizard-footer');
  if (!body || !footer) return;

  if (stepIndex >= _wizardQuestions.length) {
    _startWizardChat();
    return;
  }

  const step = _wizardQuestions[stepIndex];
  const chips = step.chips || [];
  const isFreeText = step.freeText || false;

  let html = `<div style="font-size:13px;color:rgba(255,255,255,.9);margin-bottom:14px;font-weight:600">${_escHtml(step.question)}</div>`;

  if (isFreeText) {
    html += `<input type="text" id="wizard-free-input" placeholder="${_escHtml(step.placeholder || 'Type here...')}"
      style="width:100%;padding:12px 14px;border-radius:10px;border:1px solid rgba(255,255,255,.08);
      background:rgba(255,255,255,.03);color:#fff;font-size:13px;font-family:inherit;outline:none">`;
  } else {
    html += '<div style="display:flex;flex-wrap:wrap;gap:6px">';
    for (const chip of chips) {
      const label = chip.label || chip;
      const value = chip.value || label;
      const sub = chip.sub || null;
      html += `<button class="wizard-chip" onclick="PathUI._selectWizardChip(${stepIndex}, '${_escHtml(value)}')" style="
        padding:${sub ? '10px 14px' : '8px 14px'};border-radius:9px;border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.03);color:rgba(255,255,255,.8);font-size:12px;font-weight:600;
        cursor:pointer;font-family:inherit;text-align:left;transition:all .12s;
      ">${_escHtml(label)}${sub ? `<br><span style="font-size:10px;color:rgba(255,255,255,.35);font-weight:400">${_escHtml(sub)}</span>` : ''}</button>`;
    }
    html += '</div>';
  }

  body.innerHTML = html;
  footer.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 0 0">
      <span style="font-size:10px;color:rgba(255,255,255,.3)">Step ${stepIndex + 1} of ${_wizardQuestions.length}</span>
      ${isFreeText ? `<button onclick="PathUI._nextWizardStep(${stepIndex})" style="
        padding:8px 16px;border-radius:8px;border:none;background:linear-gradient(135deg,#34d399,#22c584);
        color:#0a0f1a;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;
      ">${stepIndex === _wizardQuestions.length - 1 ? 'Generate path' : 'Next'} &rarr;</button>` : ''}
    </div>
  `;
}

let _wizTurnId = 0; // Unique per-turn ID to avoid duplicate DOM issues

function _startWizardChat() {
  // Expand modal to split: chat left + artifact preview right
  const card = document.querySelector('.path-wizard-card');
  if (card) { card.style.maxWidth = '820px'; card.style.maxHeight = '85vh'; }

  const body = document.getElementById('path-wizard-body');
  const footer = document.getElementById('path-wizard-footer');
  if (!body || !footer) return;

  const answers = Object.entries(PathState.wizardData)
    .filter(([k, v]) => v && k !== 'mode' && k !== 'intent')
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ');

  body.style.padding = '0';
  body.innerHTML = `
    <div style="display:flex;height:420px">
      <!-- Chat side -->
      <div style="width:360px;display:flex;flex-direction:column;border-right:1px solid rgba(255,255,255,.05)">
        <div id="wiz-msgs" style="flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:10px"></div>
        <div style="padding:8px 12px;border-top:1px solid rgba(255,255,255,.04);display:flex;gap:5px;align-items:center">
          <input id="wiz-input" type="text" placeholder="Tell Euler more, or say &quot;go&quot; to create..."
            onkeydown="if(event.key==='Enter'&&!event.shiftKey)PathUI._sendWizardChat()"
            style="flex:1;padding:9px 11px;border-radius:8px;border:1px solid rgba(255,255,255,.05);
            background:rgba(255,255,255,.02);color:#fff;font-size:11.5px;font-family:inherit;outline:none">
          <button id="wiz-stop-btn" onclick="PathUI._stopWizard()" title="Stop" style="display:none;width:28px;height:28px;
            border-radius:7px;border:1px solid rgba(248,113,113,.15);background:rgba(248,113,113,.06);
            color:rgba(248,113,113,.6);cursor:pointer;place-items:center;flex-shrink:0;font-size:10px">&#9632;</button>
          <button id="wiz-send-btn" onclick="PathUI._sendWizardChat()" style="width:28px;height:28px;border-radius:7px;border:none;
            background:rgba(52,211,153,.12);color:#34d399;cursor:pointer;display:grid;place-items:center;flex-shrink:0">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg></button>
        </div>
      </div>
      <!-- Artifact preview side -->
      <div id="wiz-artifact" style="flex:1;overflow-y:auto;padding:16px;background:rgba(0,0,0,.1)">
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;text-align:center;opacity:.4">
          <div style="font-size:24px;margin-bottom:8px">&#128218;</div>
          <div style="font-size:12px;font-weight:600;color:rgba(255,255,255,.4)">Your path will build here</div>
          <div style="font-size:10px;color:rgba(255,255,255,.2);margin-top:4px;max-width:200px">
            Chat with Euler, then it'll design your sessions in real time
          </div>
        </div>
      </div>
    </div>
  `;
  footer.innerHTML = '';

  _wizTurnId = 0;
  _streamedNodes = [];
  _streamedPhase = 'General';
  _streamedPhasePlanned = false;
  _parsedUpTo = 0;
  _createDraftPath().then(() => {
    _wizSendToAgent(
      `I want to learn: "${PathState.wizardData.intent}". Here's what I told you: ${answers || 'nothing specific yet'}.`
    );
  });
}

function _wizAddUserMsg(text) {
  const el = document.getElementById('wiz-msgs');
  if (!el) return;
  el.innerHTML += `<div style="display:flex;justify-content:flex-end">
    <div style="padding:7px 11px;border-radius:10px 10px 3px 10px;background:rgba(96,165,250,.1);
      border:1px solid rgba(96,165,250,.1);font-size:12px;color:#fff;max-width:85%">${_escHtml(text)}</div></div>`;
  el.scrollTop = el.scrollHeight;
}

function _wizAddAgentBubble() {
  const el = document.getElementById('wiz-msgs');
  if (!el) return;
  const id = ++_wizTurnId;
  el.innerHTML += `<div id="wiz-turn-${id}" style="display:flex;gap:8px;align-items:flex-start">
    <div style="width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
      display:grid;place-items:center;font-size:9px;font-weight:800;color:#0a0f1a;flex-shrink:0;margin-top:1px">E</div>
    <div id="wiz-content-${id}" style="flex:1;min-width:0">
      <div id="wiz-status-${id}" style="display:flex;align-items:center;gap:6px">
        <span style="display:inline-block;width:12px;height:12px;border:2px solid rgba(52,211,153,.2);
          border-top-color:#34d399;border-radius:50%;animation:spin .7s linear infinite"></span>
        <span id="wiz-status-text-${id}" style="font-size:10px;color:rgba(255,255,255,.25)">Thinking...</span>
      </div>
    </div></div>`;
  el.scrollTop = el.scrollHeight;
  return id;
}

async function _wizSendToAgent(msg) {
  const path = PathState.activePath;
  if (!path) return;
  const turnId = _wizAddAgentBubble();
  const contentEl = () => document.getElementById(`wiz-content-${turnId}`);
  const statusEl = () => document.getElementById(`wiz-status-${turnId}`);
  const scroll = () => { const el = document.getElementById('wiz-msgs'); if (el) el.scrollTop = el.scrollHeight; };
  // We'll track a running text element that tool calls interrupt
  let _curTextId = 0;

  // Show stop button, hide send
  const stopBtn = document.getElementById('wiz-stop-btn');
  const sendBtn = document.getElementById('wiz-send-btn');
  if (stopBtn) stopBtn.style.display = 'grid';
  if (sendBtn) sendBtn.style.display = 'none';

  const ac = new AbortController();
  PathState._wizAbort = ac;

  try {
    const timer = setTimeout(() => ac.abort(), 60000);
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/${path.pathId}/refine`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify({ message: msg }),
      signal: ac.signal,
    });
    clearTimeout(timer);

    let agentText = '';
    const ct = res.headers.get('content-type') || '';

    if (ct.includes('text/event-stream') && res.body) {
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const ev = JSON.parse(line.slice(6));

            if (ev.type === 'agent_text') {
              agentText += ev.text;
              const se = statusEl(); if (se) se.style.display = 'none';
              // Append to current text span (or create one)
              let span = document.getElementById(`wiz-tspan-${turnId}-${_curTextId}`);
              if (!span) {
                const ce = contentEl();
                if (ce) { ce.insertAdjacentHTML('beforeend', `<div id="wiz-tspan-${turnId}-${_curTextId}" style="font-size:12px;color:rgba(255,255,255,.8);line-height:1.6"></div>`); }
                span = document.getElementById(`wiz-tspan-${turnId}-${_curTextId}`);
              }
              if (span) span.innerHTML = _md(agentText);
              scroll();

            } else if (ev.type === 'status') {
              const st = document.getElementById(`wiz-status-text-${turnId}`);
              if (st) st.textContent = ev.message;

            } else if (ev.type === 'tool_call') {
              const se = statusEl(); if (se) se.style.display = 'none';
              // Insert tool call INLINE after current text
              _curTextId++; agentText = ''; // new text span after this tool call
              const ce = contentEl();
              if (ce) {
                ce.insertAdjacentHTML('beforeend', `<div class="wiz-tc" style="display:flex;align-items:center;gap:6px;
                  padding:4px 8px;margin:4px 0;border-radius:6px;background:rgba(96,165,250,.04);
                  border:1px solid rgba(96,165,250,.08);font-size:10px;color:rgba(96,165,250,.75)">
                  <span style="display:inline-block;width:12px;height:12px;border:2px solid rgba(96,165,250,.25);
                    border-top-color:#60a5fa;border-radius:50%;animation:spin .7s linear infinite;flex-shrink:0"></span>
                  ${_escHtml(ev.message)}</div>`);
              }
              scroll();

            } else if (ev.type === 'tool_result') {
              const ce = contentEl();
              if (ce) {
                const items = ce.querySelectorAll('.wiz-tc');
                const last = items.length ? items[items.length - 1].querySelector('span') : null;
                if (last) last.style.cssText = 'width:8px;height:8px;border-radius:50%;background:#34d399;flex-shrink:0;animation:none;border:none';
              }

            } else if (ev.type === 'artifact_update' || ev.type === 'refine_ready') {
              // Path was created or modified — load and render artifact
              try {
                const updated = await PathAPI.get(ev.pathId || path.pathId);
                if (updated?.nodes?.length) {
                  PathState.activePath = updated;
                  _renderWizArtifact(updated);
                  // Mark all remaining spinners as done
                  const ce = contentEl();
                  if (ce) ce.querySelectorAll('.wiz-tc span').forEach(sp => {
                    if (sp.style.animation !== 'none') sp.style.cssText = 'width:8px;height:8px;border-radius:50%;background:#34d399;flex-shrink:0;animation:none;border:none';
                  });
                  // Hide status
                  const se = statusEl(); if (se) se.style.display = 'none';
                }
              } catch(e2) {}
            }
          } catch(e) {}
        }
      }
    } else {
      const r = await res.json();
      agentText = r?.message || r?.reason || r?._chat_response || '';
    }

    // Final render
    const se = statusEl(); if (se) se.style.display = 'none';
    if (agentText) {
      let span = document.getElementById(`wiz-tspan-${turnId}-${_curTextId}`);
      if (!span) {
        const ce = contentEl();
        if (ce) { ce.insertAdjacentHTML('beforeend', `<div id="wiz-tspan-${turnId}-${_curTextId}" style="font-size:12px;color:rgba(255,255,255,.8);line-height:1.6"></div>`); }
        span = document.getElementById(`wiz-tspan-${turnId}-${_curTextId}`);
      }
      if (span && !span.innerHTML.trim()) span.innerHTML = _md(agentText);
    }
    scroll();

    // Also try loading path one final time in case we missed an event
    try {
      const final = await PathAPI.get(path.pathId);
      if (final?.nodes?.length && !document.getElementById('wiz-artifact')?.querySelector('button')) {
        PathState.activePath = final;
        _renderWizArtifact(final);
      }
    } catch(e) {}

    setTimeout(() => document.getElementById('wiz-input')?.focus(), 200);
  } catch (e) {
    if (e.name === 'AbortError') {
      const se = statusEl(); if (se) se.innerHTML = `<span style="font-size:10px;color:rgba(255,255,255,.3)">Stopped</span>`;
    } else {
      const se = statusEl(); if (se) se.innerHTML = `<span style="font-size:10px;color:rgba(248,113,113,.6)">Failed — try again</span>`;
    }
  }
  // Restore buttons
  const stopBtn2 = document.getElementById('wiz-stop-btn');
  const sendBtn2 = document.getElementById('wiz-send-btn');
  if (stopBtn2) stopBtn2.style.display = 'none';
  if (sendBtn2) sendBtn2.style.display = 'grid';
}

function _renderWizArtifact(path) {
  const el = document.getElementById('wiz-artifact');
  if (!el) return;
  const nodes = path.nodes || [];
  const totalMin = nodes.reduce((s, n) => s + (n.targetMin || 30), 0);
  const hours = (totalMin / 60).toFixed(1).replace('.0', '');
  const milestones = nodes.filter(n => n.milestone).length;

  // Group by phase
  const phases = [];
  let cur = null;
  for (const n of nodes) {
    const ph = n.phase || 'General';
    if (!cur || cur.name !== ph) { cur = { name: ph, nodes: [] }; phases.push(cur); }
    cur.nodes.push(n);
  }

  let phHtml = '';
  for (const p of phases) {
    phHtml += `<div style="margin-bottom:10px">
      <div style="font-size:7.5px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;
        color:rgba(255,255,255,.2);margin-bottom:4px">${_escHtml(p.name)} &middot; ${p.nodes.length} sessions</div>`;
    for (const n of p.nodes) {
      const tc = { learn: '#34d399', drill: '#fb923c', quiz: '#a78bfa', build: '#fbbf24' }[n.type] || '#60a5fa';
      const nTopics = (n.topics || []).slice(0, 5);
      const ntDots = nTopics.length ? nTopics.map(t =>
        `<div style="display:flex;align-items:center;gap:4px;padding:0.5px 0"><div style="width:3px;height:3px;border-radius:50%;background:rgba(255,255,255,.1);flex-shrink:0"></div><span style="font-size:7.5px;color:rgba(255,255,255,.2)">${_escHtml(t)}</span></div>`).join('') : '';
      phHtml += `<div style="padding:5px 7px;border-radius:6px;background:rgba(255,255,255,.02);
        border:1px solid rgba(255,255,255,.03);margin-bottom:3px">
        <div style="display:flex;align-items:center;gap:6px">
          <div style="width:16px;height:16px;border-radius:50%;background:${tc}15;color:${tc};
            display:grid;place-items:center;font-size:7px;font-weight:700;flex-shrink:0">${n.milestone ? '★' : (n.order || '')}</div>
          <span style="font-size:10px;font-weight:600;color:rgba(255,255,255,.75);flex:1;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_escHtml(n.title)}</span>
          <span style="font-size:8px;color:rgba(255,255,255,.15);flex-shrink:0">${n.targetMin}m</span>
        </div>
        ${ntDots ? `<div style="padding-left:22px;margin-top:2px">${ntDots}</div>` : ''}
      </div>`;
    }
    phHtml += '</div>';
  }

  el.innerHTML = `
    <div style="font-size:8px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:rgba(52,211,153,.6);margin-bottom:4px">Your path</div>
    <div style="font-size:13px;font-weight:800;color:#fff;margin-bottom:2px">${_escHtml(path.title)}</div>
    <div style="font-size:9.5px;color:rgba(255,255,255,.3);margin-bottom:8px;line-height:1.4">${_escHtml(path.description)}</div>
    <div style="display:flex;gap:12px;font-size:9px;color:rgba(255,255,255,.25);margin-bottom:8px">
      <span><strong style="color:#fff">${nodes.length}</strong> sessions</span>
      <span><strong style="color:#fff">~${hours}h</strong></span>
      <span><strong style="color:#fff">${milestones}</strong> milestones</span>
    </div>
    <div style="height:3px;border-radius:2px;background:rgba(255,255,255,.04);margin-bottom:12px">
      <div style="height:100%;width:0%;background:#34d399;border-radius:2px"></div>
    </div>
    ${phHtml}
    <div style="font-size:9px;color:rgba(255,255,255,.2);text-align:center;margin-top:8px">
      Keep chatting on the left to adjust &middot; or finalize below
    </div>
    <button onclick="PathUI.closeWizard();PathUI.openPathDetail('${_escHtml(path.pathId)}')" style="
      width:100%;padding:10px;border-radius:8px;border:none;margin-top:6px;
      background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
      font-size:12px;font-weight:700;cursor:pointer;font-family:inherit">
      Finalize path &rarr;</button>
  `;
}

function _openWizardChat() {
  // Close wizard modal, open split-screen with chat active + empty artifact
  PathUI.closeWizard();

  const screen = document.getElementById('path-screen');
  const container = document.getElementById('path-screen-content');
  if (!screen || !container) return;

  if (typeof _hideAllScreens === 'function') _hideAllScreens();
  const tl = document.getElementById('teaching-layout');
  if (tl) tl.classList.add('hidden');
  screen.style.display = 'flex';

  // Build a summary of wizard answers for the agent
  const answers = Object.entries(PathState.wizardData)
    .filter(([k, v]) => v && k !== 'mode')
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ');

  container.innerHTML = `
    <div style="display:flex;height:100vh">
      <!-- LEFT: empty artifact placeholder -->
      <div style="flex:1;overflow-y:auto">
        <div style="position:sticky;top:0;z-index:40;padding:12px 20px;background:rgba(10,15,26,.92);
          backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.05);display:flex;align-items:center;gap:10px">
          <button onclick="PathUI.closePathDetail()" style="width:28px;height:28px;border-radius:7px;
            border:1px solid rgba(255,255,255,.06);background:none;color:rgba(255,255,255,.3);cursor:pointer;
            display:grid;place-items:center;font-size:12px">&larr;</button>
          <div style="font-size:13px;font-weight:700;color:#fff;flex:1">${_escHtml(PathState.wizardData.intent || 'New path')}</div>
        </div>
        <div id="path-artifact-panel" style="max-width:680px;margin:0 auto;padding:40px 24px">
          <div class="path-artifact-inner" style="text-align:center;padding:60px 20px">
            <div style="font-size:28px;margin-bottom:12px;opacity:.3">&#128218;</div>
            <div style="font-size:14px;font-weight:600;color:rgba(255,255,255,.35);margin-bottom:6px">Your path will appear here</div>
            <div style="font-size:11px;color:rgba(255,255,255,.2);line-height:1.5;max-width:300px;margin:0 auto">
              Chat with Euler on the right to refine what you need. When ready, say "let's go" or Euler will suggest creating the path.
            </div>
          </div>
        </div>
      </div>

      <!-- RIGHT: Chat — active, agent starts the conversation -->
      <div style="width:300px;border-left:1px solid rgba(255,255,255,.05);display:flex;flex-direction:column;background:rgba(0,0,0,.12)">
        <div style="padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.05);display:flex;align-items:center;gap:8px">
          <div style="width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
            display:grid;place-items:center;font-size:10px;font-weight:800;color:#0a0f1a;flex-shrink:0">E</div>
          <div><div style="font-size:12px;font-weight:700;color:#fff">Euler</div>
          <div style="font-size:9px;color:rgba(255,255,255,.25)">Building your path</div></div>
        </div>

        <div id="path-refine-msgs" style="flex:1;overflow-y:auto;padding:14px 14px 10px"></div>

        <div style="padding:10px 12px;border-top:1px solid rgba(255,255,255,.05)">
          <div style="display:flex;gap:5px;align-items:center">
            <button onclick="document.getElementById('path-page-file')?.click()" title="Attach" style="width:28px;height:28px;border-radius:7px;
              border:1px solid rgba(255,255,255,.05);background:none;display:grid;place-items:center;cursor:pointer;flex-shrink:0;color:rgba(255,255,255,.2)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg></button>
            <input type="file" id="path-page-file" style="display:none" accept="image/*,.pdf,.txt,.md,.docx">
            <input id="path-refine-input" type="text" placeholder="Tell Euler more or say &quot;let's go&quot;..."
              onkeydown="if(event.key==='Enter')PathUI._sendRefine()"
              style="flex:1;padding:9px 12px;border-radius:9px;border:1px solid rgba(255,255,255,.05);
              background:rgba(255,255,255,.02);color:#fff;font-size:11.5px;font-family:inherit;outline:none">
            <button onclick="PathUI._sendRefine()" style="width:28px;height:28px;border-radius:7px;border:none;
              background:rgba(52,211,153,.12);color:#34d399;cursor:pointer;display:grid;place-items:center;flex-shrink:0">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg></button>
          </div>
          <div style="margin-top:8px;text-align:center">
            <button onclick="PathUI._createPathNow()" style="padding:8px 16px;border-radius:8px;border:none;
              background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;font-size:11px;font-weight:700;
              cursor:pointer;font-family:inherit">Create path now &rarr;</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // Start the agent conversation — it has the wizard answers and will ask follow-ups
  PathState.chatHistory = [];
  _addChatMsg('agent', `Got it — you want to learn **${_escHtml(PathState.wizardData.intent || 'this topic')}**. ${answers ? 'Based on what you told me (' + answers + '), ' : ''}let me ask a couple of things to make sure I build the right path for you.`);

  // Auto-send the wizard context to the planning agent for follow-up
  setTimeout(() => {
    const input = document.getElementById('path-refine-input');
    if (input) input.focus();
  }, 300);

  // Send wizard data to the refine endpoint so the agent can follow up
  // We need a path ID first — create a draft path
  _createDraftPath();
}

async function _createDraftPath() {
  // Create a minimal path with no nodes — just so we have a pathId for the chat
  try {
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths`, {
      method: 'POST', headers: _pathHeaders(),
      body: JSON.stringify({
        title: PathState.wizardData.intent || 'New path',
        description: 'Draft — being planned',
        wizard: PathState.wizardData,
        nodes: [],
      }),
    });
    if (res.ok) {
      const path = await res.json();
      PathState.activePath = path;
      console.log('[Path] Draft created:', path.pathId);
    }
  } catch (e) {
    console.warn('[Path] Draft creation failed:', e);
  }
}

async function _generatePath() {
  // Show progress in the chat panel (split-screen is already open)
  const msgsEl = document.getElementById('path-refine-msgs');
  if (msgsEl) {
    msgsEl.innerHTML += `
      <div id="path-gen-thinking" style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px">
        <div style="width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
          display:grid;place-items:center;font-size:8px;font-weight:800;color:#0a0f1a;flex-shrink:0;margin-top:2px">E</div>
        <div style="flex:1">
          <div id="path-gen-agent-text" style="font-size:11.5px;color:rgba(255,255,255,.8);line-height:1.5"></div>
          <div style="display:flex;align-items:center;gap:6px;margin-top:4px">
            <div class="path-gen-spinner" style="width:14px;height:14px;border-width:2px"></div>
            <span id="path-gen-status" style="font-size:10px;color:rgba(255,255,255,.3)">Designing your path...</span>
          </div>
          <div id="path-gen-events" style="display:flex;flex-direction:column;gap:2px;margin-top:4px"></div>
        </div>
      </div>
    `;
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }
  // Wizard modal body/footer might not exist anymore (we're in split screen)
  const body = null;
  const footer = null;

  try {
    // Stream SSE events from the planner (60s timeout — agent may call web_search)
    const planAc = new AbortController();
    const planTimer = setTimeout(() => planAc.abort(), 60000);
    const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/plan`, {
      method: 'POST',
      headers: _pathHeaders(),
      body: JSON.stringify(PathState.wizardData),
      signal: planAc.signal,
    });
    clearTimeout(planTimer);

    if (!res.ok) throw new Error('Path planning failed');

    const contentType = res.headers.get('content-type') || '';

    if (contentType.includes('text/event-stream')) {
      // SSE streaming response
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let pathDoc = null;
      let agentText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            const statusEl = document.getElementById('path-gen-status');
            const eventsEl = document.getElementById('path-gen-events');

            const agentTextEl = document.getElementById('path-gen-agent-text');
            if (event.type === 'status' && statusEl) {
              statusEl.textContent = event.message;
            } else if (event.type === 'tool_call' && eventsEl) {
              eventsEl.innerHTML += `<div style="font-size:11px;color:rgba(96,165,250,.8);display:flex;align-items:center;gap:6px;
                padding:3px 0;animation:scopeHintIn .2s ease">
                <span style="width:14px;height:14px;border-radius:50%;background:rgba(96,165,250,.12);color:#60a5fa;
                  display:grid;place-items:center;font-size:8px;flex-shrink:0">&#9906;</span>
                ${_escHtml(event.message)}</div>`;
            } else if (event.type === 'tool_result' && eventsEl) {
              const last = eventsEl.lastElementChild;
              if (last) last.innerHTML += ' <span style="color:rgba(52,211,153,.7)">&#10003;</span>';
            } else if (event.type === 'agent_text') {
              agentText += event.text;
              if (agentTextEl) agentTextEl.innerHTML = `<p style="margin:0">${_md(agentText)}</p>`;
            } else if (event.type === 'path_ready') {
              pathDoc = event.path;
            } else if (event.type === 'error') {
              throw new Error(event.message);
            }
          } catch (e) {
            if (e.message !== 'Path planning failed' && !e.message.startsWith('Path')) continue;
            throw e;
          }
        }
      }

      if (pathDoc) {
        PathState.activePath = pathDoc;
        document.getElementById('path-gen-thinking')?.remove();
        _addChatMsg('agent', `Path ready! ${pathDoc.nodes?.length || '?'} sessions. Check it out on the left.`);
        _updateArtifactPanel(pathDoc);
        return;
      }
    } else {
      const pathDoc = await res.json();
      PathState.activePath = pathDoc;
      document.getElementById('path-gen-thinking')?.remove();
      _addChatMsg('agent', `Path ready! ${pathDoc.nodes?.length || '?'} sessions.`);
      _updateArtifactPanel(pathDoc);
      return;
    }

    throw new Error('No path received from planner');
  } catch (e) {
    console.error('[Path] Planning failed:', e);
    document.getElementById('path-gen-thinking')?.remove();
    _addChatMsg('agent', `Path generation failed: ${e.message || 'unknown error'}. You can try again with "create path now".`);
  }
}

function _renderPathPreview(path, agentMessage) {
  const body = document.getElementById('path-wizard-body');
  const footer = document.getElementById('path-wizard-footer');
  if (!body || !footer) return;

  const nodes = path.nodes || [];
  const totalMin = nodes.reduce((s, n) => s + (n.targetMin || 30), 0);
  const milestones = nodes.filter(n => n.milestone).length;
  const hours = Math.round(totalMin / 60);

  // Group nodes by phase
  const phases = [];
  let currentPhase = null;
  for (const n of nodes) {
    const phaseName = n.phase || 'General';
    if (!currentPhase || currentPhase.name !== phaseName) {
      currentPhase = { name: phaseName, nodes: [], totalMin: 0 };
      phases.push(currentPhase);
    }
    currentPhase.nodes.push(n);
    currentPhase.totalMin += (n.targetMin || 30);
  }

  // Build phase HTML
  let phasesHtml = '';
  for (let pi = 0; pi < phases.length; pi++) {
    const p = phases[pi];
    const phaseHours = p.totalMin >= 60 ? `${Math.round(p.totalMin / 60)}h` : `${p.totalMin}m`;
    phasesHtml += `
      <div style="margin-bottom:16px">
        <div style="font-size:8.5px;font-weight:700;letter-spacing:1.3px;text-transform:uppercase;
          color:rgba(255,255,255,.3);margin-bottom:8px;padding-left:2px">
          Phase ${pi + 1} &middot; ${_escHtml(p.name)} &middot; ${p.nodes.length} sessions &middot; ${phaseHours}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">`;

    for (const n of p.nodes) {
      const typeColor = { learn: '#34d399', drill: '#fb923c', quiz: '#a78bfa', build: '#fbbf24' }[n.type] || '#60a5fa';
      const typeIcon = { learn: '', drill: '', quiz: '?', build: '' }[n.type] || '';
      const isMilestone = n.milestone;
      phasesHtml += `
          <div style="padding:10px 12px;border-radius:9px;overflow:hidden;min-width:0;
            background:${isMilestone ? 'rgba(52,211,153,.04)' : 'rgba(255,255,255,.02)'};
            border:1px solid ${isMilestone ? 'rgba(52,211,153,.2)' : 'rgba(255,255,255,.05)'}">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
              <div style="width:20px;height:20px;border-radius:50%;background:${typeColor}18;color:${typeColor};
                display:grid;place-items:center;font-size:9px;font-weight:700;flex-shrink:0">
                ${isMilestone ? '★' : (n.order || '')}</div>
              <span style="font-size:12px;font-weight:600;color:#fff;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                ${isMilestone ? '★ ' : ''}${_escHtml(n.title)}</span>
              <span style="font-size:10px;color:rgba(255,255,255,.25);flex-shrink:0">${n.targetMin}m</span>
            </div>
            ${n.subtitle ? `<div style="font-size:10px;color:rgba(255,255,255,.3);padding-left:28px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_escHtml(n.subtitle)}</div>` : ''}
          </div>`;
    }

    phasesHtml += '</div></div>';
  }

  // Agent summary message — render with markdown
  const summaryMsg = agentMessage || `Built it. ${nodes.length} sessions, ~${hours}h — paced for you.`;

  body.innerHTML = `
    <div style="display:flex;align-items:flex-start;gap:9px;margin-bottom:16px">
      <div style="width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
        display:grid;place-items:center;font-size:10px;font-weight:800;color:#0a0f1a;flex-shrink:0;margin-top:1px">E</div>
      <div style="font-size:12.5px;color:rgba(255,255,255,.8);line-height:1.6">${_md(summaryMsg)}</div>
    </div>

    <div style="padding:16px 18px;border-radius:12px;background:rgba(52,211,153,.03);
      border:1px solid rgba(52,211,153,.15);margin-bottom:14px">
      <div style="font-size:8.5px;font-weight:700;letter-spacing:1.3px;text-transform:uppercase;
        color:rgba(52,211,153,.75);margin-bottom:4px">Your custom track</div>
      <div style="font-size:16px;font-weight:800;color:#fff;margin-bottom:3px">${_escHtml(path.title)}</div>
      <div style="font-size:11px;color:rgba(255,255,255,.4);margin-bottom:12px">${_escHtml(path.description)}</div>

      <div style="display:flex;gap:20px;margin-bottom:14px">
        <div><span style="font-size:20px;font-weight:800;color:#fff">${nodes.length}</span>
          <span style="font-size:9px;font-weight:600;letter-spacing:.5px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-left:3px">sessions</span></div>
        <div><span style="font-size:20px;font-weight:800;color:#fff">~${hours}h</span>
          <span style="font-size:9px;font-weight:600;letter-spacing:.5px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-left:3px">total</span></div>
        <div><span style="font-size:20px;font-weight:800;color:#fff">${milestones}</span>
          <span style="font-size:9px;font-weight:600;letter-spacing:.5px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-left:3px">milestones</span></div>
      </div>

      <div style="max-height:340px;overflow-y:auto">${phasesHtml}</div>
    </div>

    <div id="path-refine-chat" style="margin-top:8px">
      <div id="path-refine-msgs"></div>
      <div style="display:flex;align-items:flex-start;gap:9px;margin-bottom:4px">
        <div style="width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
          display:grid;place-items:center;font-size:10px;font-weight:800;color:#0a0f1a;flex-shrink:0;margin-top:1px">E</div>
        <div style="font-size:11.5px;color:rgba(255,255,255,.45);line-height:1.5">
          Looks right? Type below to refine — e.g. "make it shorter", "drop the RTOS section", "add more practice".
        </div>
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        <label for="path-refine-file" style="
          width:32px;height:32px;border-radius:8px;border:1px solid rgba(255,255,255,.08);
          background:rgba(255,255,255,.03);display:grid;place-items:center;cursor:pointer;flex-shrink:0;
          color:rgba(255,255,255,.35);font-size:14px;transition:all .12s;
        " title="Attach file for context (syllabus, notes, etc.)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
        </label>
        <input type="file" id="path-refine-file" style="display:none"
          accept="image/*,.pdf,.txt,.md,.docx"
          onchange="if(this.files.length){var n=document.createElement('span');n.id='path-refine-file-name';n.style.cssText='font-size:10px;color:rgba(96,165,250,.8);max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex-shrink:0';n.textContent=this.files[0].name;this.parentElement.insertBefore(n,this.nextSibling)}">
        <input id="path-refine-input" type="text"
          placeholder="Refine: &quot;shorter please&quot;, &quot;add more drills&quot;, &quot;drop the RTOS part&quot;..."
          onkeydown="if(event.key==='Enter')PathUI._sendRefine()"
          style="flex:1;padding:10px 14px;border-radius:10px;border:1px solid rgba(255,255,255,.08);
          background:rgba(255,255,255,.03);color:#fff;font-size:12.5px;font-family:inherit;outline:none">
        <button onclick="PathUI._sendRefine()" style="
          padding:8px 14px;border-radius:8px;border:none;
          background:rgba(52,211,153,.15);color:#34d399;
          font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;flex-shrink:0;
        "><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg></button>
      </div>
    </div>
  `;

  footer.innerHTML = `
    <div style="display:flex;justify-content:flex-end;align-items:center;gap:8px;padding:14px 0 0;border-top:1px solid rgba(255,255,255,.05)">
      <button onclick="PathUI.closeWizard()" style="
        padding:9px 16px;border-radius:9px;border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.03);color:rgba(255,255,255,.6);
        font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;
      ">Save</button>
      <button onclick="PathUI.startPath('${_escHtml(path.pathId)}')" style="
        padding:9px 18px;border-radius:9px;border:none;
        background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
        font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;
      ">Create path &rarr;</button>
    </div>
  `;
}


// ── Home screen path cards (Stage 3) ─────────────────────────────
async function renderPathCards() {
  // No-op — paths are now rendered in the unified activity section by _loadHomeSessions in app.js
}


// ── Path full-page view ──────────────────────────────────────────
function _renderPathPage(path) {
  const screen = document.getElementById('path-screen');
  const container = document.getElementById('path-screen-content');
  if (!screen || !container) {
    _renderPathDetailModal(path);
    return;
  }

  if (typeof cleanupActiveSession === 'function') cleanupActiveSession();
  if (typeof _hideAllScreens === 'function') _hideAllScreens();
  const tl = document.getElementById('teaching-layout');
  if (tl) tl.classList.add('hidden');
  screen.style.display = 'flex';

  const nodes = path.nodes || [];
  const done = nodes.filter(n => n.status === 'completed').length;
  const total = nodes.length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const totalMin = nodes.reduce((s, n) => s + (n.targetMin || 30), 0);
  const hours = (totalMin / 60).toFixed(1).replace('.0', '');
  const next = nodes.find(n => n.status === 'pending' || n.status === 'active');
  const _pid = _escHtml(path.pathId);

  // Progress ring SVG
  const circumference = 94.2;
  const offset = circumference - (pct / 100) * circumference;

  // Build timeline HTML
  const timelineHtml = _buildTimeline(path, nodes, next);

  // Reflection notes for banner
  const recentNotes = (path.pathNotes || []).slice(-3);
  const lastStrength = recentNotes.filter(n => n.kind === 'strength').slice(-1)[0];
  const lastGap = recentNotes.filter(n => n.kind === 'gap').slice(-1)[0];
  let reflBanner = '';
  if (lastStrength || lastGap) {
    const parts = [];
    if (lastStrength) parts.push(`<strong>${_escHtml(lastStrength.concept)}</strong> is solid`);
    if (lastGap) parts.push(`<strong>${_escHtml(lastGap.concept)}</strong> needs work`);
    reflBanner = `<div style="margin-bottom:14px;padding:10px 12px;border-radius:9px;background:rgba(251,191,36,.04);
      border:1px solid rgba(251,191,36,.12);display:flex;gap:8px;font-size:11px;color:rgba(251,191,36,.85);line-height:1.5">
      <span>&#128161;</span><span>From recent sessions: ${parts.join('. ')}.</span>
      <button onclick="this.parentElement.remove()" style="font-size:10px;color:rgba(255,255,255,.2);background:none;border:none;cursor:pointer;flex-shrink:0">&times;</button>
    </div>`;
  }

  container.innerHTML = `
    <div style="display:flex;height:100vh;overflow:hidden;position:fixed;inset:0;z-index:10;background:#0a0f1a">
      <!-- LEFT: Path timeline -->
      <div style="flex:1;overflow-y:auto;min-width:0">
        <!-- Topbar -->
        <div style="position:sticky;top:0;z-index:40;padding:12px 20px;background:rgba(10,15,26,.92);
          backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.05);display:flex;align-items:center;gap:10px">
          <button onclick="PathUI.closePathDetail()" style="width:28px;height:28px;border-radius:7px;
            border:1px solid rgba(255,255,255,.06);background:none;color:rgba(255,255,255,.3);cursor:pointer;
            display:grid;place-items:center;font-size:12px">&larr;</button>
          <div style="flex:1;font-size:13px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_escHtml(path.title)}</div>
          <div style="width:28px;height:28px;position:relative;flex-shrink:0">
            <svg width="28" height="28" viewBox="0 0 36 36" style="transform:rotate(-90deg)">
              <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,.06)" stroke-width="3"/>
              <circle cx="18" cy="18" r="15" fill="none" stroke="#34d399" stroke-width="3"
                stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round"/>
            </svg>
            <div style="position:absolute;inset:0;display:grid;place-items:center;font-size:7px;font-weight:800;color:#34d399">${pct}%</div>
          </div>
          <span style="font-size:13px;font-weight:800;color:#34d399;flex-shrink:0">${done}<span style="color:rgba(255,255,255,.25);font-weight:600">/${total}</span></span>
        </div>

        <div id="path-artifact-panel" style="max-width:680px;margin:0 auto;padding:16px 20px 40px">
          <div class="path-artifact-inner">
            <!-- Hero: next session -->
            ${next ? `<div style="padding:14px 16px;border-radius:12px;margin-bottom:14px;
              background:linear-gradient(135deg,rgba(52,211,153,.05),rgba(96,165,250,.02));
              border:1px solid rgba(52,211,153,.15);display:flex;gap:14px;align-items:flex-start">
              <div style="flex:1;min-width:0">
                <div style="font-size:7.5px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;
                  color:rgba(52,211,153,.8);margin-bottom:4px;display:flex;align-items:center;gap:4px">
                  <span style="width:4px;height:4px;border-radius:50%;background:#34d399"></span>
                  Up next &middot; ${next.type} &middot; ~${next.targetMin}m</div>
                <div style="font-size:15px;font-weight:800;color:#fff;letter-spacing:-.2px;margin-bottom:6px">${_escHtml(next.title)}</div>
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;padding:5px 8px;border-radius:6px;
                  background:rgba(96,165,250,.03);border:1px solid rgba(96,165,250,.06)">
                  <span style="font-size:10px;color:rgba(96,165,250,.5)">&#9998;</span>
                  <input type="text" value="${_escHtml(next.studentNote || '')}"
                    placeholder="Optional — e.g. &quot;I know the basics&quot; to calibrate Euler"
                    onblur="PathUI._saveNodeNote('${_pid}','${_escHtml(next.nodeId)}',this.value)"
                    onkeydown="if(event.key==='Enter')this.blur()"
                    style="flex:1;background:none;border:none;color:#fff;font-size:10px;font-family:inherit;outline:none">
                </div>
              </div>
              <button onclick="PathUI.continueNode('${_pid}','${_escHtml(next.nodeId)}')" style="padding:10px 18px;
                border-radius:9px;border:none;background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
                font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;flex-shrink:0;white-space:nowrap;
                margin-top:18px">Start &rarr;</button>
            </div>` : '<div style="padding:12px;text-align:center;color:#34d399;font-weight:700;font-size:13px;margin-bottom:14px">Path complete &#10003;</div>'}

            ${reflBanner}

            <!-- Timeline -->
            ${timelineHtml}
          </div>
        </div>
      </div>

      <!-- RIGHT: Chat -->
      <div style="width:300px;min-width:300px;flex-shrink:0;border-left:1px solid rgba(255,255,255,.05);display:flex;flex-direction:column;background:rgba(0,0,0,.12)">
        <div style="padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.05);display:flex;align-items:center;gap:8px">
          <div style="width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
            display:grid;place-items:center;font-size:10px;font-weight:800;color:#0a0f1a;flex-shrink:0">E</div>
          <div><div style="font-size:12px;font-weight:700;color:#fff">Euler</div>
          <div style="font-size:9px;color:rgba(255,255,255,.25)">Path advisor &middot; can adjust your plan</div></div>
        </div>

        <div id="path-refine-msgs" style="flex:1;overflow-y:auto;padding:14px 14px 10px">
          <div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:10px">
            <div style="width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
              display:grid;place-items:center;font-size:8px;font-weight:800;color:#0a0f1a;flex-shrink:0;margin-top:2px">E</div>
            <div style="font-size:12px;color:rgba(255,255,255,.7);line-height:1.6">
              ${done > 0
                ? `You're <strong style="color:#fff">${done} sessions in</strong>. ${next ? _escHtml(next.title) + ' is up next.' : 'All done!'} Need anything?`
                : `Your path is ready &mdash; <strong style="color:#fff">${total} sessions, ~${hours}h</strong>. Want to adjust before starting?`}
            </div>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;padding-left:28px;margin-bottom:8px">
            <button onclick="document.getElementById('path-refine-input').value='make it shorter';PathUI._sendRefine()"
              style="font-size:9.5px;padding:5px 10px;border-radius:7px;border:1px solid rgba(255,255,255,.06);
              background:rgba(255,255,255,.02);color:rgba(255,255,255,.4);cursor:pointer;font-family:inherit;
              transition:all .1s" onmouseenter="this.style.color='#fff';this.style.borderColor='rgba(96,165,250,.2)'"
              onmouseleave="this.style.color='rgba(255,255,255,.4)';this.style.borderColor='rgba(255,255,255,.06)'">Make it shorter</button>
            <button onclick="document.getElementById('path-refine-input').value='add more practice';PathUI._sendRefine()"
              style="font-size:9.5px;padding:5px 10px;border-radius:7px;border:1px solid rgba(255,255,255,.06);
              background:rgba(255,255,255,.02);color:rgba(255,255,255,.4);cursor:pointer;font-family:inherit;
              transition:all .1s" onmouseenter="this.style.color='#fff';this.style.borderColor='rgba(96,165,250,.2)'"
              onmouseleave="this.style.color='rgba(255,255,255,.4)';this.style.borderColor='rgba(255,255,255,.06)'">More practice</button>
            <button onclick="document.getElementById('path-refine-input').value='what will I build?';PathUI._sendRefine()"
              style="font-size:9.5px;padding:5px 10px;border-radius:7px;border:1px solid rgba(255,255,255,.06);
              background:rgba(255,255,255,.02);color:rgba(255,255,255,.4);cursor:pointer;font-family:inherit;
              transition:all .1s" onmouseenter="this.style.color='#fff';this.style.borderColor='rgba(96,165,250,.2)'"
              onmouseleave="this.style.color='rgba(255,255,255,.4)';this.style.borderColor='rgba(255,255,255,.06)'">What will I build?</button>
          </div>
        </div>

        <div style="padding:10px 12px;border-top:1px solid rgba(255,255,255,.05)">
          <div style="display:flex;gap:5px;align-items:center">
            <button onclick="document.getElementById('path-page-file').click()" title="Attach file" style="width:28px;height:28px;border-radius:7px;
              border:1px solid rgba(255,255,255,.05);background:none;display:grid;place-items:center;cursor:pointer;
              flex-shrink:0;color:rgba(255,255,255,.2)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg></button>
            <input type="file" id="path-page-file" style="display:none" accept="image/*,.pdf,.txt,.md,.docx"
              onchange="if(this.files.length){var nm=this.files[0].name;var el=document.getElementById('path-refine-input');if(el)el.placeholder='Attached: '+nm+'  — type your message...'}">
            <button onclick="if(typeof _openResourcePicker==='function')_openResourcePicker()" title="Your materials" style="
              width:28px;height:28px;border-radius:7px;border:1px solid rgba(255,255,255,.05);background:none;
              display:grid;place-items:center;cursor:pointer;flex-shrink:0;color:rgba(255,255,255,.2)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg></button>
            <input id="path-refine-input" type="text" placeholder="Ask Euler anything about your path..."
              onkeydown="if(event.key==='Enter')PathUI._sendRefine()"
              style="flex:1;padding:9px 12px;border-radius:9px;border:1px solid rgba(255,255,255,.05);
              background:rgba(255,255,255,.02);color:#fff;font-size:11.5px;font-family:inherit;outline:none">
            <button onclick="PathUI._sendRefine()" style="width:28px;height:28px;border-radius:7px;border:none;
              background:rgba(52,211,153,.12);color:#34d399;cursor:pointer;display:grid;place-items:center;flex-shrink:0">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg></button>
          </div>
        </div>
      </div>
    </div>
  `;
}

// ── Timeline builder (vertical, collapsible phases) ─────────────
function _buildTimeline(path, nodes, next) {
  const phases = [];
  let curPhase = null;
  for (const n of nodes) {
    const phaseName = n.phase || 'General';
    if (!curPhase || curPhase.name !== phaseName) {
      curPhase = { name: phaseName, nodes: [], totalMin: 0 };
      phases.push(curPhase);
    }
    curPhase.nodes.push(n);
    curPhase.totalMin += (n.targetMin || 30);
  }

  // Find active phase
  let activePhaseIdx = 0;
  for (let i = 0; i < phases.length; i++) {
    if (phases[i].nodes.some(n => next && n.nodeId === next.nodeId)) { activePhaseIdx = i; break; }
  }

  const _pid = _escHtml(path.pathId);
  let html = '<div style="position:relative;padding-left:24px">';
  html += '<div style="position:absolute;left:9px;top:0;bottom:0;width:2px;background:rgba(255,255,255,.04);border-radius:1px"></div>';

  for (let pi = 0; pi < phases.length; pi++) {
    const p = phases[pi];
    const phaseDone = p.nodes.every(n => n.status === 'completed');
    const isActive = pi === activePhaseIdx;
    const isOpen = isActive || pi === activePhaseIdx + 1;
    const phDone = p.nodes.filter(n => n.status === 'completed').length;
    const colId = `tl-phase-${pi}`;

    // Phase dot
    const dotClass = phaseDone ? 'done' : isActive ? 'active' : '';
    const dotBorder = phaseDone ? '#34d399' : isActive ? '#60a5fa' : 'rgba(255,255,255,.08)';
    const dotBg = phaseDone ? 'rgba(52,211,153,.15)' : isActive ? 'rgba(96,165,250,.15)' : '#0a0f1a';
    const dotInner = (phaseDone || isActive) ? `<span style="width:4px;height:4px;border-radius:50%;background:${phaseDone ? '#34d399' : '#60a5fa'}"></span>` : '';

    const labelColor = phaseDone ? 'rgba(52,211,153,.45)' : isActive ? 'rgba(96,165,250,.65)' : 'rgba(255,255,255,.25)';

    html += `<div style="margin-bottom:2px">
      <div onclick="var n=document.getElementById('${colId}');if(n)n.style.display=n.style.display==='none'?'':'none'"
        style="display:flex;align-items:center;gap:6px;padding:6px 0;cursor:pointer;user-select:none;position:relative">
        <div style="position:absolute;left:-20px;width:10px;height:10px;border-radius:50%;background:${dotBg};
          border:2px solid ${dotBorder};display:grid;place-items:center">${dotInner}</div>
        ${phaseDone ? '<span style="font-size:8px;color:rgba(52,211,153,.5)">&#10003;</span>' : ''}
        <span style="font-size:9px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:${labelColor}">
          Phase ${pi + 1} &middot; ${_escHtml(p.name)}</span>
        <span style="font-size:9px;color:rgba(255,255,255,.2);margin-left:auto">${phDone}/${p.nodes.length}</span>
        <span style="font-size:8px;color:rgba(255,255,255,.15)">${isOpen ? '&#9660;' : '&#9654;'}</span>
      </div>
      <div id="${colId}" style="${isOpen ? '' : 'display:none'}">
        <div style="display:flex;flex-direction:column;gap:3px;padding:4px 0 6px">`;

    for (const n of p.nodes) {
      const _nid = _escHtml(n.nodeId);
      const isDone = n.status === 'completed';
      const isNext = next && n.nodeId === next.nodeId;
      const tc = { learn: '#34d399', drill: '#fb923c', quiz: '#a78bfa', build: '#fbbf24' }[n.type] || '#60a5fa';
      const numBg = isDone ? 'rgba(52,211,153,.1)' : `${tc}15`;
      const numColor = isDone ? '#34d399' : tc;
      const borderColor = isNext ? 'rgba(96,165,250,.2)' : 'rgba(255,255,255,.04)';
      const bg = isNext ? 'rgba(96,165,250,.03)' : 'rgba(255,255,255,.015)';

      let tag = '';
      if (isDone) tag = `<span onclick="event.stopPropagation();PathUI._undoNodeDone('${_pid}','${_nid}')" title="Click to undo"
        style="font-size:7px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:#34d399;background:rgba(52,211,153,.1);
        padding:2px 5px;border-radius:3px;cursor:pointer;flex-shrink:0">&#10003; Done</span>`;
      else if (isNext) tag = `<span style="font-size:7px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:#60a5fa;
        background:rgba(96,165,250,.1);padding:2px 5px;border-radius:3px;flex-shrink:0">Next</span>`;

      const isPlaceholder = n.placeholder || n.targetMin === 0;

      // Placeholder nodes render differently
      if (isPlaceholder) {
        html += `<div style="padding:7px 9px;border-radius:7px;background:rgba(255,255,255,.01);
          border:1px dashed rgba(255,255,255,.05);opacity:.5">
          <div style="display:flex;align-items:center;gap:7px">
            <div style="width:18px;height:18px;border-radius:50%;background:rgba(255,255,255,.03);color:rgba(255,255,255,.15);
              display:grid;place-items:center;font-size:8px;flex-shrink:0">~</div>
            <span style="font-size:11px;color:rgba(255,255,255,.3);flex:1;font-style:italic">${_escHtml(n.title)}</span>
            <button onclick="event.stopPropagation();PathUI._planPhase('${_pid}','${_escHtml(n.phase || '')}')"
              style="font-size:8px;padding:2px 8px;border-radius:4px;border:1px solid rgba(96,165,250,.15);
              background:rgba(96,165,250,.05);color:rgba(96,165,250,.6);cursor:pointer;font-family:inherit;flex-shrink:0">Plan</button>
          </div></div>`;
        continue;
      }

      const expandId = `tl-expand-${_nid}`;
      const topics = (n.topics || []).slice(0, 5);

      // Collapsed: title + number only. Expanded: subtopics + start button
      html += `<div style="border-radius:8px;background:${bg};border:1px solid ${borderColor};
        transition:border-color .12s;${isDone ? 'opacity:.5;' : ''}overflow:hidden;margin-bottom:4px"
        onmouseenter="this.style.borderColor='rgba(96,165,250,.12)';this.querySelectorAll('.subtopic-start').forEach(b=>b.style.opacity='1')"
        onmouseleave="this.style.borderColor='${borderColor}';this.querySelectorAll('.subtopic-start').forEach(b=>b.style.opacity='0')"

        <div onclick="var ex=document.getElementById('${expandId}');if(ex)ex.style.display=ex.style.display==='none'?'':'none'"
          style="padding:10px 12px;cursor:pointer;display:flex;align-items:center;gap:8px">
          <div style="width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:9px;font-weight:700;
            flex-shrink:0;background:${numBg};color:${numColor}">${isDone ? '&#10003;' : (n.milestone ? '&#9733;' : (n.order || ''))}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;color:${isDone ? 'rgba(255,255,255,.4)' : '#fff'};
              ${isDone ? 'text-decoration:line-through;' : ''}">${_escHtml(n.title)}</div>
          </div>
          ${tag}
          <span style="font-size:9px;color:rgba(255,255,255,.12);flex-shrink:0">${n.targetMin}m</span>
        </div>

        <div id="${expandId}" style="display:${isNext ? '' : 'none'};padding:0 12px 12px">
          ${topics.length ? `<div style="padding-left:30px;margin-bottom:8px;position:relative">
            <div style="position:absolute;left:32px;top:8px;bottom:8px;width:1px;background:rgba(255,255,255,.04)"></div>
            ${topics.map((t, ti) => `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;position:relative"
              onclick="event.stopPropagation()">
              <span style="width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.1);flex-shrink:0;z-index:1"></span>
              <span style="font-size:11.5px;color:rgba(255,255,255,.4);flex:1;line-height:1.3">${_escHtml(t)}</span>
              <button onclick="PathUI._startAtSubtopic('${_pid}','${_nid}','${_escHtml(t)}')"
                style="padding:3px 10px;border-radius:5px;border:1px solid rgba(52,211,153,.15);
                background:rgba(52,211,153,.04);color:rgba(52,211,153,.6);font-size:9px;font-weight:600;
                cursor:pointer;font-family:inherit;flex-shrink:0;opacity:0;transition:opacity .1s"
                onmouseenter="this.style.opacity='1'" class="subtopic-start">Start</button>
            </div>`).join('')}
          </div>` : ''}
          <div style="padding-left:30px">
            <input type="text" value="${_escHtml(n.studentNote || '')}" placeholder="Optional — add context to calibrate Euler, e.g. &quot;I know basics of this&quot;"
              onblur="PathUI._saveNodeNote('${_pid}','${_nid}',this.value)" onkeydown="if(event.key==='Enter')this.blur()"
              onclick="event.stopPropagation()"
              style="width:100%;padding:6px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.04);
              background:rgba(255,255,255,.015);color:#fff;font-size:10.5px;font-family:inherit;outline:none">
          </div>
        </div>
      </div>`;
    }

    html += '</div></div></div>';
  }

  html += '</div>';
  return html;
}


// Shared phase grid builder (used by both page and modal)
function _buildPhaseGrid(path, nodes, next, readOnly) {
  const phases = [];
  let curPhase = null;
  for (const n of nodes) {
    const phaseName = n.phase || 'General';
    if (!curPhase || curPhase.name !== phaseName) {
      curPhase = { name: phaseName, nodes: [], totalMin: 0 };
      phases.push(curPhase);
    }
    curPhase.nodes.push(n);
    curPhase.totalMin += (n.targetMin || 30);
  }

  // Find which phase is active (contains the next/active node)
  let activePhaseIdx = 0;
  for (let pi = 0; pi < phases.length; pi++) {
    if (phases[pi].nodes.some(n => next && n.nodeId === next.nodeId)) { activePhaseIdx = pi; break; }
    if (phases[pi].nodes.some(n => n.status === 'active')) { activePhaseIdx = pi; break; }
  }

  let html = '';
  for (let pi = 0; pi < phases.length; pi++) {
    const p = phases[pi];
    const phTime = p.totalMin >= 60 ? `${Math.round(p.totalMin / 60)}h` : `${p.totalMin}m`;
    const phaseDone = p.nodes.every(n => n.status === 'completed');
    // Show active phase + one ahead expanded, collapse rest
    const isExpanded = readOnly || pi === activePhaseIdx || pi === activePhaseIdx + 1;
    const collapseId = `phase-collapse-${pi}`;
    html += `<div style="margin-bottom:14px">
      <div onclick="var el=document.getElementById('${collapseId}');if(el){el.style.display=el.style.display==='none'?'':'none'};"
        style="font-size:8px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;
        color:${phaseDone ? 'rgba(52,211,153,.4)' : pi === activePhaseIdx ? 'rgba(96,165,250,.7)' : 'rgba(255,255,255,.25)'};
        margin-bottom:6px;cursor:pointer;display:flex;align-items:center;gap:6px;user-select:none">
        ${phaseDone ? '<span style="color:#34d399">&#10003;</span>' : ''}
        Phase ${pi + 1} &middot; ${_escHtml(p.name)} &middot; ${p.nodes.length} sessions &middot; ${phTime}
        <span style="margin-left:auto;font-size:9px;color:rgba(255,255,255,.12)">${isExpanded ? '&#9660;' : '&#9654;'}</span>
      </div>
      <div id="${collapseId}" style="${isExpanded ? '' : 'display:none'}">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">`;
    for (const n of p.nodes) {
      const tc = { learn: '#34d399', drill: '#fb923c', quiz: '#a78bfa', build: '#fbbf24' }[n.type] || '#60a5fa';
      const isDone = n.status === 'completed';
      const isActive = n.status === 'active';
      const isNext = next && n.nodeId === next.nodeId;
      const border = isDone ? 'rgba(52,211,153,.3)' : isNext ? 'rgba(96,165,250,.35)' : 'rgba(255,255,255,.05)';
      const bg = isDone ? 'rgba(52,211,153,.05)' : isNext ? 'rgba(96,165,250,.04)' : 'rgba(255,255,255,.02)';

      const _pid = _escHtml(path.pathId);
      const _nid = _escHtml(n.nodeId);
      const topicHint = (n.topics || []).length ? `e.g. know ${n.topics[0]}, focus on ${n.topics.slice(-1)[0]}` : '';
      const clickAttr = readOnly ? '' : `onclick="PathUI.continueNode('${_pid}','${_nid}')"`;
      const dragAttr = readOnly ? '' : `draggable="true" ondragstart="PathUI._onDragStart(event,'${_nid}')" ondragover="event.preventDefault();this.style.borderColor='#34d399'" ondragleave="this.style.borderColor='${border}'" ondrop="PathUI._onDrop(event,'${_pid}','${_nid}');this.style.borderColor='${border}'"`;

      // Inline status tag — clickable for done toggle
      let tag = '';
      if (isDone) tag = `<span onclick="event.stopPropagation();PathUI._undoNodeDone('${_pid}','${_nid}')" title="Click to undo"
        style="font-size:7px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:#34d399;background:rgba(52,211,153,.12);
        padding:2px 6px;border-radius:3px;flex-shrink:0;cursor:pointer">&#10003; DONE</span>`;
      else if (isActive) tag = `<span onclick="event.stopPropagation();PathUI._markNodeDone('${_pid}','${_nid}')" title="Mark done"
        style="font-size:7px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:#fb923c;background:rgba(251,146,60,.1);
        padding:2px 6px;border-radius:3px;flex-shrink:0;cursor:pointer">ACTIVE</span>`;
      else if (isNext) tag = `<span style="font-size:7px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:#60a5fa;
        background:rgba(96,165,250,.1);padding:2px 6px;border-radius:3px;flex-shrink:0">NEXT</span>`;
      else if (!readOnly) tag = `<span onclick="event.stopPropagation();PathUI._markNodeDone('${_pid}','${_nid}')" title="Mark done"
        style="font-size:7px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:rgba(255,255,255,.15);background:rgba(255,255,255,.03);
        padding:2px 6px;border-radius:3px;flex-shrink:0;cursor:pointer;opacity:0;transition:opacity .1s" class="node-done-ghost">&#9675;</span>`;

      // Only delete button on hover, mark done is always visible via the tag
      const deleteBtn = readOnly ? '' : `
        <div class="node-card-controls" style="display:none;position:absolute;top:6px;right:6px" onclick="event.stopPropagation()">
          <button onclick="PathUI._deleteNode('${_pid}','${_nid}')" title="Remove"
            style="font-size:9px;width:18px;height:18px;border-radius:50%;border:1px solid rgba(248,113,113,.15);
            background:rgba(248,113,113,.06);color:rgba(248,113,113,.5);cursor:pointer;display:grid;place-items:center">&times;</button>
        </div>`;

      html += `
        <div ${clickAttr} ${dragAttr}
          style="padding:8px 10px;border-radius:8px;background:${bg};border:1px solid ${border};
          overflow:visible;min-width:0;position:relative;${readOnly ? '' : 'cursor:pointer;'}transition:border-color .1s"
          onmouseenter="this.style.borderColor='rgba(96,165,250,.2)';var c=this.querySelector('.node-card-controls');if(c)c.style.display='';var g=this.querySelector('.node-done-ghost');if(g)g.style.opacity='1'"
          onmouseleave="this.style.borderColor='${border}';var c=this.querySelector('.node-card-controls');if(c)c.style.display='none';var g=this.querySelector('.node-done-ghost');if(g)g.style.opacity='0'">
          <div style="display:flex;align-items:center;gap:6px">
            <div style="width:18px;height:18px;border-radius:50%;background:${tc}18;color:${tc};
              display:grid;place-items:center;font-size:8px;font-weight:700;flex-shrink:0">${n.milestone ? '★' : (n.order || '')}</div>
            <span style="font-size:10.5px;font-weight:600;color:${isDone ? 'rgba(255,255,255,.4)' : '#fff'};
              flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;${isDone ? 'text-decoration:line-through;' : ''}">${_escHtml(n.title)}</span>
            ${tag}
            <span style="font-size:8.5px;color:rgba(255,255,255,.15);flex-shrink:0">${n.targetMin}m</span>
          </div>
          ${n.subtitle ? `<div style="font-size:8.5px;color:rgba(255,255,255,.18);padding-left:24px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_escHtml(n.subtitle)}</div>` : ''}
          <div style="padding-left:24px;margin-top:3px" onclick="event.stopPropagation()">
            <input type="text" value="${_escHtml(n.studentNote || '')}" placeholder="Help Euler calibrate: what do you know here?"
              style="width:100%;padding:2px 5px;border-radius:3px;border:1px solid ${n.studentNote ? 'rgba(96,165,250,.15)' : 'rgba(255,255,255,.03)'};
              background:${n.studentNote ? 'rgba(96,165,250,.03)' : 'transparent'};color:${n.studentNote ? 'rgba(96,165,250,.55)' : 'rgba(255,255,255,.15)'};
              font-size:8.5px;font-family:inherit;outline:none;font-style:italic;transition:all .1s"
              onfocus="this.style.borderColor='rgba(96,165,250,.2)';this.style.background='rgba(96,165,250,.03)';this.style.color='#fff';this.style.fontStyle='normal'"
              onblur="PathUI._saveNodeNote('${_pid}','${_nid}',this.value);if(!this.value){this.style.borderColor='rgba(255,255,255,.03)';this.style.background='transparent';this.style.color='rgba(255,255,255,.15)';this.style.fontStyle='italic'}"
              onkeydown="if(event.key==='Enter')this.blur()">
          </div>
          ${deleteBtn}
        </div>`;
    }
    // Add session button at end of phase (only if not readOnly)
    if (!readOnly) {
      const lastNodeId = p.nodes.length ? p.nodes[p.nodes.length - 1].nodeId : '';
      html += `<div onclick="event.stopPropagation();PathUI._showAddNodeForm('${_escHtml(path.pathId)}','${_escHtml(lastNodeId)}',this)"
        style="padding:7px 12px;border-radius:7px;border:1px dashed rgba(255,255,255,.05);
        background:transparent;cursor:pointer;font-size:9px;color:rgba(255,255,255,.18);
        text-align:center;transition:all .12s;grid-column:1/-1"
        onmouseenter="this.style.borderColor='rgba(52,211,153,.2)';this.style.color='rgba(52,211,153,.5)'"
        onmouseleave="this.style.borderColor='rgba(255,255,255,.05)';this.style.color='rgba(255,255,255,.18)'"
        >+ Add session</div>`;
    }
    html += '</div></div></div>';  // grid + collapse wrapper + phase container
  }
  return html;
}


// ── Path detail modal (fallback) ────────────────────────────────
function _renderPathDetailModal(path) {
  document.getElementById('path-detail-modal')?.remove();

  const nodes = path.nodes || [];
  const done = nodes.filter(n => n.status === 'completed').length;
  const total = nodes.length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const totalMin = nodes.reduce((s, n) => s + (n.targetMin || 30), 0);
  const hours = Math.round(totalMin / 60);
  const milestones = nodes.filter(n => n.milestone).length;
  const next = nodes.find(n => n.status === 'pending');

  // Group by phase
  const phases = [];
  let curPhase = null;
  for (const n of nodes) {
    const phaseName = n.phase || 'General';
    if (!curPhase || curPhase.name !== phaseName) {
      curPhase = { name: phaseName, nodes: [], totalMin: 0 };
      phases.push(curPhase);
    }
    curPhase.nodes.push(n);
    curPhase.totalMin += (n.targetMin || 30);
  }

  let phasesHtml = '';
  for (let pi = 0; pi < phases.length; pi++) {
    const p = phases[pi];
    const phTime = p.totalMin >= 60 ? `${Math.round(p.totalMin / 60)}h` : `${p.totalMin}m`;
    phasesHtml += `<div style="margin-bottom:18px">
      <div style="font-size:8.5px;font-weight:700;letter-spacing:1.3px;text-transform:uppercase;
        color:rgba(255,255,255,.3);margin-bottom:8px">
        Phase ${pi + 1} &middot; ${_escHtml(p.name)} &middot; ${p.nodes.length} sessions &middot; ${phTime}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">`;
    for (const n of p.nodes) {
      const tc = { learn: '#34d399', drill: '#fb923c', quiz: '#a78bfa', build: '#fbbf24' }[n.type] || '#60a5fa';
      const isDone = n.status === 'completed';
      const isActive = n.status === 'active';
      const isNext = next && n.nodeId === next.nodeId;
      const border = isDone ? 'rgba(52,211,153,.3)' : isNext ? 'rgba(96,165,250,.35)' : 'rgba(255,255,255,.05)';
      const bg = isDone ? 'rgba(52,211,153,.05)' : isNext ? 'rgba(96,165,250,.04)' : 'rgba(255,255,255,.02)';
      // Top-right: status + actions
      const _pid = _escHtml(path.pathId);
      const _nid = _escHtml(n.nodeId);
      let badge = '';
      if (isDone) {
        badge = `<div style="position:absolute;top:5px;right:6px;display:flex;gap:4px;align-items:center">
          <button onclick="event.stopPropagation();PathUI._undoNodeDone('${_pid}','${_nid}')"
            style="font-size:8px;padding:1px 5px;border-radius:3px;border:1px solid rgba(52,211,153,.25);
            background:rgba(52,211,153,.1);color:#34d399;cursor:pointer;font-family:inherit;font-weight:600"
            title="Unmark — not done yet">&#10003; Done</button>
        </div>`;
      } else if (isActive) {
        badge = `<div style="position:absolute;top:5px;right:6px;display:flex;gap:4px;align-items:center">
          <button onclick="event.stopPropagation();PathUI._markNodeDone('${_pid}','${_nid}')"
            style="font-size:8px;padding:1px 5px;border-radius:3px;border:1px solid rgba(255,255,255,.1);
            background:rgba(255,255,255,.04);color:rgba(255,255,255,.4);cursor:pointer;font-family:inherit;font-weight:600"
            title="Mark as completed">Mark done</button>
        </div>`;
      } else if (isNext) {
        badge = `<div style="position:absolute;top:5px;right:6px;font-size:8px;font-weight:700;letter-spacing:.5px;
          text-transform:uppercase;color:#60a5fa;background:rgba(96,165,250,.12);padding:1px 5px;border-radius:3px">NEXT</div>`;
      }

      // Every card is clickable to start/resume
      phasesHtml += `
        <div onclick="PathUI.continueNode('${_pid}','${_nid}')"
          style="padding:10px 12px;border-radius:9px;background:${bg};border:1px solid ${border};
          overflow:hidden;min-width:0;position:relative;cursor:pointer;transition:border-color .12s"
          onmouseenter="this.style.borderColor='rgba(96,165,250,.35)'"
          onmouseleave="this.style.borderColor='${border}'">
          ${badge}
          <div style="display:flex;align-items:center;gap:7px;margin-bottom:2px">
            <div style="width:20px;height:20px;border-radius:50%;background:${tc}18;color:${tc};
              display:grid;place-items:center;font-size:9px;font-weight:700;flex-shrink:0">
              ${n.milestone ? '★' : (n.order || '')}</div>
            <span style="font-size:11.5px;font-weight:600;color:${isDone ? 'rgba(255,255,255,.5)' : '#fff'};
              flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:55px">${_escHtml(n.title)}</span>
            <span style="font-size:10px;color:rgba(255,255,255,.2);flex-shrink:0">${n.targetMin}m</span>
          </div>
          ${n.subtitle ? `<div style="font-size:10px;color:rgba(255,255,255,.25);padding-left:27px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_escHtml(n.subtitle)}</div>` : ''}
        </div>`;
    }
    phasesHtml += '</div></div>';
  }

  // Notes pills
  const strengths = (path.pathNotes || []).filter(n => n.kind === 'strength').slice(-3);
  const gaps = (path.pathNotes || []).filter(n => n.kind === 'gap').slice(-3);
  let notesHtml = '';
  if (strengths.length || gaps.length) {
    notesHtml = '<div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:14px">' +
      strengths.map(s => `<span style="padding:3px 8px;border-radius:999px;font-size:10px;font-weight:600;
        background:rgba(52,211,153,.1);color:rgba(52,211,153,.95);border:1px solid rgba(52,211,153,.2)">&#10003; ${_escHtml(s.concept)}</span>`).join('') +
      gaps.map(g => `<span style="padding:3px 8px;border-radius:999px;font-size:10px;font-weight:600;
        background:rgba(251,191,36,.1);color:rgba(251,191,36,.95);border:1px solid rgba(251,191,36,.2)">&#9888; ${_escHtml(g.concept)}</span>`).join('') +
      '</div>';
  }

  const modal = document.createElement('div');
  modal.id = 'path-detail-modal';
  modal.className = 'path-wizard-overlay';
  modal.innerHTML = `
    <div class="path-wizard-card" style="max-width:720px">
      <div class="path-wizard-header">
        <div class="path-wizard-header-ic">E</div>
        <div style="flex:1">
          <div style="font-size:8.5px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:rgba(52,211,153,.85)">
            ${path.status === 'completed' ? 'Completed path' : 'Your path'}
          </div>
          <div style="font-size:15px;font-weight:700;color:#fff">${_escHtml(path.title)}</div>
        </div>
        <div style="font-size:20px;font-weight:800;color:#34d399;margin-right:8px">${done}<span style="font-size:13px;color:rgba(255,255,255,.3)">/${total}</span></div>
        <button onclick="PathUI.closePathDetail()" style="
          width:28px;height:28px;border-radius:50%;border:1px solid rgba(255,255,255,.1);
          background:none;color:rgba(255,255,255,.4);cursor:pointer;font-size:14px;
          display:grid;place-items:center;
        ">&times;</button>
      </div>

      <div class="path-wizard-body">
        <div style="font-size:11.5px;color:rgba(255,255,255,.45);margin-bottom:12px">${_escHtml(path.description)}</div>

        <div style="display:flex;gap:20px;margin-bottom:14px">
          <div><span style="font-size:18px;font-weight:800;color:#fff">${total}</span>
            <span style="font-size:9px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-left:3px">sessions</span></div>
          <div><span style="font-size:18px;font-weight:800;color:#fff">~${hours}h</span>
            <span style="font-size:9px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-left:3px">total</span></div>
          <div><span style="font-size:18px;font-weight:800;color:#fff">${milestones}</span>
            <span style="font-size:9px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-left:3px">milestones</span></div>
        </div>

        <div style="height:4px;border-radius:2px;background:rgba(255,255,255,.05);overflow:hidden;margin-bottom:14px">
          <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,#34d399,#22c584);border-radius:2px"></div>
        </div>

        ${notesHtml}
        ${phasesHtml}
      </div>

      <div class="path-wizard-footer">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 0 0;border-top:1px solid rgba(255,255,255,.05)">
          <button onclick="PathUI.closePathDetail()" style="
            padding:9px 16px;border-radius:9px;border:1px solid rgba(255,255,255,.08);
            background:rgba(255,255,255,.03);color:rgba(255,255,255,.6);
            font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;
          ">Close</button>
          ${next ? `<button onclick="PathUI.continueNode('${_escHtml(path.pathId)}','${_escHtml(next.nodeId)}')" style="
            padding:9px 18px;border-radius:9px;border:none;
            background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
            font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;
          ">Start session ${done + 1} &rarr;</button>` : `<span style="font-size:12px;color:#34d399;font-weight:600">Path complete &#10003;</span>`}
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}


// ── Path breadcrumb in session (Stage 4) ─────────────────────────
function renderPathBreadcrumb(pathId, nodeId) {
  // Defer slightly so teaching layout DOM is ready
  setTimeout(() => _insertPathBreadcrumb(pathId, nodeId), 100);
}

function _insertPathBreadcrumb(pathId, nodeId) {
  // Remove existing
  document.getElementById('path-session-bar')?.remove();

  const path = PathState.activePath;
  if (!path) return;

  const nodes = path.nodes || [];
  const current = nodes.find(n => n.nodeId === nodeId);
  if (!current) return;

  const done = nodes.filter(n => n.status === 'completed').length;
  const total = nodes.length;

  const bar = document.createElement('div');
  bar.id = 'path-session-bar';
  bar.style.cssText = `
    height:38px;padding:0 16px;display:flex;align-items:center;gap:10px;
    background:rgba(52,211,153,.04);border-bottom:1px solid rgba(52,211,153,.12);
    font-size:12px;flex-shrink:0;z-index:10;
  `;
  bar.innerHTML = `
    <span onclick="PathUI.openPathDetail('${_escHtml(pathId)}')" style="
      color:rgba(52,211,153,.85);cursor:pointer;display:flex;align-items:center;gap:4px;font-weight:600;
      white-space:nowrap;
    ">&larr; ${_escHtml(path.title.length > 35 ? path.title.slice(0, 35) + '...' : path.title)}</span>
    <span style="width:1px;height:14px;background:rgba(255,255,255,.08);flex-shrink:0"></span>
    <span style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(52,211,153,.12);
      color:#34d399;font-weight:700;flex-shrink:0">${current.order}/${total}</span>
    <span style="font-weight:600;color:#fff;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_escHtml(current.title)}</span>
    <span style="font-size:11px;color:rgba(255,255,255,.3);flex-shrink:0">${current.targetMin}m</span>
  `;

  // Insert AFTER the top-bar header, not before it
  const topBar = document.getElementById('top-bar');
  if (topBar && topBar.parentElement) {
    topBar.parentElement.insertBefore(bar, topBar.nextSibling);
  }
}


// ── Reflection overlay (Stage 5) ─────────────────────────────────
function showReflectionOverlay(reflectionData) {
  document.getElementById('path-reflection-overlay')?.remove();

  const { strengths = [], gaps = [], pivot, sessionSummary, nodeId } = reflectionData;
  const path = PathState.activePath;
  const node = path?.nodes?.find(n => n.nodeId === nodeId);

  let pivotHtml = '';
  if (pivot && pivot.diff) {
    const diff = pivot.diff;
    pivotHtml = `
      <div style="padding:12px 14px;border-radius:10px;background:rgba(96,165,250,.04);
        border:1px solid rgba(96,165,250,.18);margin-top:8px">
        <div style="font-size:12px;font-weight:700;color:#60a5fa;margin-bottom:8px;
          display:flex;align-items:center;gap:6px">&#9881; Proposed path update</div>
        ${(diff.added || []).map(a => `<div style="padding:5px 8px;border-radius:5px;font-size:11px;
          color:rgba(52,211,153,.95);background:rgba(52,211,153,.06);margin-bottom:3px;
          border-left:2px solid #34d399">+ ${_escHtml(a)}</div>`).join('')}
        ${(diff.removed || []).map(r => `<div style="padding:5px 8px;border-radius:5px;font-size:11px;
          color:rgba(248,113,113,.85);background:rgba(248,113,113,.05);margin-bottom:3px;
          text-decoration:line-through;opacity:.7">- ${_escHtml(r)}</div>`).join('')}
        ${(diff.modified || []).map(m => `<div style="padding:5px 8px;border-radius:5px;font-size:11px;
          color:rgba(96,165,250,.9);background:rgba(96,165,250,.04);margin-bottom:3px">~ ${_escHtml(m)}</div>`).join('')}
      </div>
    `;
  }

  const overlay = document.createElement('div');
  overlay.id = 'path-reflection-overlay';
  overlay.style.cssText = `
    position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.7);
    display:grid;place-items:center;padding:20px;backdrop-filter:blur(6px);
  `;
  overlay.innerHTML = `
    <div style="max-width:520px;width:100%;background:#0f172a;border:1px solid rgba(255,255,255,.08);
      border-radius:16px;overflow:hidden;box-shadow:0 25px 60px rgba(0,0,0,.5)">

      <div style="padding:16px 22px;display:flex;align-items:center;gap:12px;
        background:linear-gradient(135deg,rgba(52,211,153,.07),transparent);
        border-bottom:1px solid rgba(255,255,255,.05)">
        <div style="width:34px;height:34px;border-radius:9px;background:rgba(52,211,153,.14);
          color:#34d399;display:grid;place-items:center;font-size:14px;flex-shrink:0">&#10003;</div>
        <div style="flex:1">
          <div style="font-size:9px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;
            color:rgba(52,211,153,.85)">Node ${node?.order || '?'} complete</div>
          <div style="font-size:15px;font-weight:800;color:#fff">${_escHtml(node?.title || 'Session')}</div>
        </div>
        <button onclick="PathUI.dismissReflection()" style="
          width:28px;height:28px;border-radius:50%;border:1px solid rgba(255,255,255,.1);
          background:none;color:rgba(255,255,255,.4);cursor:pointer;font-size:14px;
          display:grid;place-items:center;flex-shrink:0;
        ">&times;</button>
      </div>

      <div style="padding:18px 22px;display:flex;flex-direction:column;gap:10px">
        <div style="font-size:12px;color:rgba(255,255,255,.6);line-height:1.5">${_escHtml(sessionSummary || '')}</div>

        ${strengths.length ? `
          <div style="font-size:9px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;
            color:rgba(255,255,255,.3);margin-top:4px">Strengths</div>
          ${strengths.map(s => `
            <div style="padding:10px 12px;border-radius:9px;background:rgba(52,211,153,.04);
              border:1px solid rgba(52,211,153,.15)">
              <div style="font-size:12px;font-weight:700;color:#fff">${_escHtml(s.title)}</div>
              <div style="font-size:11px;color:rgba(255,255,255,.5);margin-top:2px">${_escHtml(s.detail)}</div>
              ${s.tags?.length ? `<div style="display:flex;gap:3px;margin-top:5px">${s.tags.map(t =>
                `<span style="font-size:9px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,.05);
                  color:rgba(255,255,255,.5)">${_escHtml(t)}</span>`).join('')}</div>` : ''}
            </div>
          `).join('')}
        ` : ''}

        ${gaps.length ? `
          <div style="font-size:9px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;
            color:rgba(255,255,255,.3);margin-top:4px">Gaps</div>
          ${gaps.map(g => `
            <div style="padding:10px 12px;border-radius:9px;background:rgba(251,191,36,.04);
              border:1px solid rgba(251,191,36,.15)">
              <div style="font-size:12px;font-weight:700;color:#fff">${_escHtml(g.title)}</div>
              <div style="font-size:11px;color:rgba(255,255,255,.5);margin-top:2px">${_escHtml(g.detail)}</div>
            </div>
          `).join('')}
        ` : ''}

        ${pivotHtml}
      </div>

      <div style="padding:14px 22px;display:flex;gap:8px;justify-content:flex-end;
        border-top:1px solid rgba(255,255,255,.05);background:rgba(0,0,0,.15)">
        ${pivot ? `
          <button onclick="PathUI.dismissReflection()" style="
            padding:9px 16px;border-radius:9px;border:1px solid rgba(255,255,255,.08);
            background:rgba(255,255,255,.03);color:rgba(255,255,255,.6);
            font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;
          ">Don't change</button>
          <button onclick="PathUI.applyPivot(${pivot.pivotIndex})" style="
            padding:9px 16px;border-radius:9px;border:none;
            background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
            font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;
          ">Apply &middot; continue</button>
        ` : `
          <button onclick="PathUI.dismissReflection()" style="
            padding:9px 16px;border-radius:9px;border:none;
            background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
            font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;
          ">Continue to next &rarr;</button>
        `}
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
}


// ── Helpers ──────────────────────────────────────────────────────
function _timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}


// ── Public API (exposed to window) ──────────────────────────────
const PathUI = {
  dismissScopeHint() {
    const wrap = document.getElementById('euler-scope-chip-wrap');
    if (wrap) { wrap.style.display = 'none'; wrap.innerHTML = ''; }
  },

  async startWizard(intentText, mode) {
    this.dismissScopeHint();
    await _renderWizardModal(intentText, mode || 'general');
  },

  closeWizard() {
    document.getElementById('path-wizard-modal')?.remove();
    PathState.wizardData = {};
  },

  _selectWizardChip(stepIndex, value) {
    const step = _wizardQuestions[stepIndex];
    if (step) PathState.wizardData[step.key] = value;
    PathState._wizardStep = stepIndex + 1;
    _renderWizardStep(stepIndex + 1);
  },

  _nextWizardStep(stepIndex) {
    const step = _wizardQuestions[stepIndex];
    if (step && step.freeText) {
      const input = document.getElementById('wizard-free-input');
      PathState.wizardData[step.key] = input?.value || '';
    }
    PathState._wizardStep = stepIndex + 1;
    _renderWizardStep(stepIndex + 1);
  },

  async _startAtSubtopic(pathId, nodeId, subtopic) {
    // Start session at a specific subtopic within a chapter
    const path = PathState.activePath;
    if (!path) return;
    const node = (path.nodes || []).find(n => n.nodeId === nodeId);
    if (!node) return;
    // Save the subtopic as the student note so tutor starts there
    await this._saveNodeNote(pathId, nodeId, `Start from: ${subtopic}`);
    await this.continueNode(pathId, nodeId);
  },

  async _planPhase(pathId, phaseName) {
    // Auto-send a refine message asking the agent to detail this phase
    const input = document.getElementById('path-refine-input');
    if (input) {
      input.value = `Detail the "${phaseName}" phase — break it into granular sessions with subtopics`;
      await this._sendRefine();
    }
  },

  _stopWizard() {
    if (PathState._wizAbort) { try { PathState._wizAbort.abort(); } catch(e) {} }
    const stopBtn = document.getElementById('wiz-stop-btn');
    const sendBtn = document.getElementById('wiz-send-btn');
    if (stopBtn) stopBtn.style.display = 'none';
    if (sendBtn) sendBtn.style.display = 'grid';
    // Clean up any spinning status
    document.querySelectorAll(`#wiz-status-${_wizTurnId}`).forEach(s => s.style.display = 'none');
  },

  async _sendWizardChat() {
    const input = document.getElementById('wiz-input');
    if (!input) return;
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    _wizAddUserMsg(msg);

    // If user says "go"/"create"/"yes" — tell agent to create the path
    const goWords = ['go', 'create', 'yes', 'start', 'build', 'do it', 'looks good', 'let\'s go', 'ready'];
    const isGo = goWords.some(w => msg.toLowerCase().includes(w)) && msg.length < 30;

    if (isGo) {
      // Show building indicator on artifact immediately
      const artEl = document.getElementById('wiz-artifact');
      if (artEl) artEl.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:10px">
        <div style="width:24px;height:24px;border:3px solid rgba(52,211,153,.15);border-top-color:#34d399;border-radius:50%;animation:spin .8s linear infinite"></div>
        <div style="font-size:12px;color:rgba(255,255,255,.4)">Building your path...</div>
        <div style="font-size:10px;color:rgba(255,255,255,.2)">Researching curriculum &middot; designing sessions</div>
      </div>`;
      await _wizSendToAgent(msg + '\n\n[The student wants you to create the path now. Call emit_path.]');
    } else {
      await _wizSendToAgent(msg);
    }
  },

  async _createPathNow() {
    // Trigger path generation from wizard chat
    _addChatMsg('user', "Let's create the path");
    _addChatMsg('agent', 'Building your path...');
    await _generatePath();
  },

  async startPath(pathId) {
    this.closeWizard();
    // Navigate to full-page path view
    await this.openPathDetail(pathId);
  },

  async continueNode(pathId, nodeId) {
    // Close any open path detail modal
    document.getElementById('path-detail-modal')?.remove();

    // Load path if needed
    if (!PathState.activePath || PathState.activePath.pathId !== pathId) {
      PathState.activePath = await PathAPI.get(pathId);
    }

    const path = PathState.activePath;
    if (!path) return;

    const node = path.nodes.find(n => n.nodeId === nodeId);
    if (!node) return;

    // Store path session context
    PathState.currentPathSession = { pathId, nodeId };

    // Mark node as active (don't generate a separate sessionId — startNewSession does that)
    try { await PathAPI.startNode(pathId, nodeId, null); } catch(e) { console.warn('[Path] startNode failed:', e); }

    // Build a clear, specific intent so triage doesn't misclassify
    // Include path title + node title + topics for grounding
    const topics = (node.topics || []).join(', ');
    const intentText = `Teach me: ${node.title}` +
      (topics ? ` (covering: ${topics})` : '') +
      ` — this is session ${node.order || '?'} of my "${path.title}" learning path.`;

    const user = AuthManager.getUser();
    if (!user) return;

    state.studentIntent = intentText;
    state._sessionPathContext = { pathId, nodeId };

    // Start session with path context — the pathContext ensures the tutor
    // gets full path notes, prior strengths/gaps, and node-type instructions
    await startNewSession(user.name, null, intentText, 'free', {
      pathId,
      nodeId,
      nodeType: node.type,
    });

    // Link the generated session ID back to the path node
    if (state.sessionId) {
      try { await PathAPI.startNode(pathId, nodeId, state.sessionId); } catch(e) {}
    }
  },

  async openPathDetail(pathId) {
    if (!pathId) return;

    const path = await PathAPI.get(pathId);
    if (!path) return;
    PathState.activePath = path;

    // Render into full-page path screen
    _renderPathPage(path);

    // Restore chat history from path doc
    setTimeout(() => _loadChatHistory(path), 100);

    // Show pending reflections after a beat
    setTimeout(() => this._showPendingReflections(pathId), 500);
  },

  closePathDetail() {
    // Navigate back to home
    document.getElementById('path-detail-modal')?.remove();
    if (typeof Router !== 'undefined') Router.navigate('/home');
  },

  async dismissReflection() {
    document.getElementById('path-reflection-overlay')?.remove();
    PathState.currentPathSession = null;
    // Go home — let user decide next step
    if (typeof Router !== 'undefined') {
      Router.navigate('/home');
    }
  },

  async applyPivot(pivotIndex) {
    const ps = PathState.currentPathSession;
    if (!ps || !PathState.activePath) return;
    const pivots = PathState.activePath.pivots || [];
    const pivot = pivots[pivotIndex];
    if (pivot?.proposedNodes) {
      await PathAPI.applyPivot(ps.pathId, pivotIndex, pivot.proposedNodes);
    }
    await this.dismissReflection();
  },

  // Queue reflection for when the user next opens the path detail — NOT inline during cleanup
  _queueReflection(pathId, nodeId, sessionId) {
    if (!pathId || !nodeId || !sessionId) return;
    // Store pending reflection in localStorage so it survives page navigation
    const pending = JSON.parse(localStorage.getItem('_pathPendingReflections') || '[]');
    // Avoid duplicates
    if (pending.some(p => p.sessionId === sessionId)) return;
    pending.push({ pathId, nodeId, sessionId, queuedAt: Date.now() });
    localStorage.setItem('_pathPendingReflections', JSON.stringify(pending.slice(-10)));
    console.log('[Path] Reflection queued for', pathId, nodeId);

    // Also fire the reflection API in background (don't await, don't show overlay)
    PathAPI.reflect(pathId, nodeId, sessionId).then(result => {
      if (result) {
        // Store result so path detail can show it
        const results = JSON.parse(localStorage.getItem('_pathReflectionResults') || '{}');
        results[`${pathId}_${nodeId}`] = result;
        localStorage.setItem('_pathReflectionResults', JSON.stringify(results));
      }
    }).catch(e => console.warn('[Path] Background reflection failed:', e));

    PathState.currentPathSession = null;
  },

  // Show pending reflections when user opens path detail
  async _showPendingReflections(pathId) {
    const results = JSON.parse(localStorage.getItem('_pathReflectionResults') || '{}');
    const pending = JSON.parse(localStorage.getItem('_pathPendingReflections') || '[]');
    const pathPending = pending.filter(p => p.pathId === pathId);

    for (const p of pathPending) {
      const key = `${p.pathId}_${p.nodeId}`;
      const result = results[key];
      if (result) {
        showReflectionOverlay(result);
        // Remove from pending
        delete results[key];
        localStorage.setItem('_pathReflectionResults', JSON.stringify(results));
        const remaining = pending.filter(pp => pp.sessionId !== p.sessionId);
        localStorage.setItem('_pathPendingReflections', JSON.stringify(remaining));
        return; // Show one at a time
      }
    }
  },

  async onSessionEnd(sessionId) {
    // Legacy — kept for any direct calls. Queues instead of showing overlay.
    const ps = PathState.currentPathSession;
    if (ps) {
      this._queueReflection(ps.pathId, ps.nodeId, sessionId);
    }
  },

  // ── Node notes ──────────────────────────────────────────────
  async _saveNodeNote(pathId, nodeId, note) {
    if (!note || !note.trim()) return;
    try {
      await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/${nodeId}/note`, {
        method: 'PATCH', headers: _pathHeaders(),
        body: JSON.stringify({ note: note.trim() }),
      });
      // Update local state
      if (PathState.activePath) {
        const node = (PathState.activePath.nodes || []).find(n => n.nodeId === nodeId);
        if (node) node.studentNote = note.trim();
      }
    } catch(e) { console.warn('[Path] Save note failed:', e); }
  },

  // ── Drag and drop ───────────────────────────────────────────
  _dragNodeId: null,
  _onDragStart(e, nodeId) {
    this._dragNodeId = nodeId;
    e.dataTransfer.effectAllowed = 'move';
    e.target.style.opacity = '0.4';
    setTimeout(() => { if (e.target) e.target.style.opacity = ''; }, 200);
  },
  async _onDrop(e, pathId, targetNodeId) {
    e.preventDefault();
    const fromId = this._dragNodeId;
    if (!fromId || fromId === targetNodeId) return;
    this._dragNodeId = null;

    const path = PathState.activePath;
    if (!path) return;
    const ids = path.nodes.map(n => n.nodeId);
    const fromIdx = ids.indexOf(fromId);
    const toIdx = ids.indexOf(targetNodeId);
    if (fromIdx < 0 || toIdx < 0) return;

    // Move fromIdx to toIdx position
    ids.splice(fromIdx, 1);
    ids.splice(toIdx, 0, fromId);

    try {
      await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/reorder`, {
        method: 'POST', headers: _pathHeaders(),
        body: JSON.stringify({ nodeIds: ids }),
      });
      PathState.activePath = await PathAPI.get(pathId);
      _updateArtifactPanel(PathState.activePath);
    } catch(e) { console.warn('[Path] Reorder failed:', e); }
  },

  // ── Node manipulation ────────────────────────────────────────
  async _deleteNode(pathId, nodeId) {
    try {
      await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/${nodeId}`, {
        method: 'DELETE', headers: _pathHeaders(),
      });
      PathState.activePath = await PathAPI.get(pathId);
      _updateArtifactPanel(PathState.activePath);
    } catch(e) { console.warn('[Path] Delete node failed:', e); }
  },

  async _moveNode(pathId, nodeId, direction) {
    const path = PathState.activePath;
    if (!path) return;
    const nodes = path.nodes || [];
    const idx = nodes.findIndex(n => n.nodeId === nodeId);
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= nodes.length) return;
    const ids = nodes.map(n => n.nodeId);
    [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];
    try {
      await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/reorder`, {
        method: 'POST', headers: _pathHeaders(),
        body: JSON.stringify({ nodeIds: ids }),
      });
      PathState.activePath = await PathAPI.get(pathId);
      _updateArtifactPanel(PathState.activePath);
    } catch(e) { console.warn('[Path] Reorder failed:', e); }
  },

  _showAddNodeForm(pathId, afterNodeId, btnEl) {
    // Remove any existing add form
    document.querySelectorAll('.path-add-form').forEach(f => f.remove());
    const form = document.createElement('div');
    form.className = 'path-add-form';
    form.style.cssText = 'grid-column:1/-1;padding:8px 10px;border-radius:8px;border:1px solid rgba(52,211,153,.2);background:rgba(52,211,153,.03);display:flex;gap:6px;align-items:center;animation:scopeHintIn .15s ease';
    form.onclick = (e) => e.stopPropagation();
    form.innerHTML = `
      <input type="text" placeholder="Session title..." autofocus
        style="flex:1;padding:6px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.03);color:#fff;font-size:11px;font-family:inherit;outline:none"
        onkeydown="if(event.key==='Enter')this.parentElement.querySelector('.add-go').click();if(event.key==='Escape')this.parentElement.remove()">
      <select style="padding:5px 6px;border-radius:6px;border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.03);color:rgba(255,255,255,.7);font-size:10px;font-family:inherit;outline:none">
        <option value="learn">Learn</option><option value="drill">Drill</option>
        <option value="quiz">Quiz</option><option value="build">Build</option>
      </select>
      <button class="add-go" onclick="PathUI._doAddNode('${_escHtml(pathId)}','${_escHtml(afterNodeId)}',this.parentElement)" style="
        padding:5px 10px;border-radius:6px;border:none;background:#34d399;color:#0a0f1a;
        font-size:10px;font-weight:700;cursor:pointer;font-family:inherit">Add</button>
      <button onclick="this.parentElement.remove()" style="
        padding:5px 8px;border-radius:6px;border:1px solid rgba(255,255,255,.08);background:none;
        color:rgba(255,255,255,.4);font-size:10px;cursor:pointer;font-family:inherit">&times;</button>
    `;
    // Insert after the button's parent grid
    if (btnEl) btnEl.replaceWith(form);
    else document.getElementById('path-artifact-panel')?.querySelector('.path-artifact-inner')?.appendChild(form);
    form.querySelector('input').focus();
  },

  async _doAddNode(pathId, afterNodeId, formEl) {
    const title = formEl.querySelector('input')?.value.trim();
    const type = formEl.querySelector('select')?.value || 'learn';
    if (!title) { formEl.querySelector('input').style.borderColor = '#f87171'; return; }
    formEl.innerHTML = '<span style="font-size:10px;color:rgba(255,255,255,.4)">Adding...</span>';
    try {
      await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/add`, {
        method: 'POST', headers: _pathHeaders(),
        body: JSON.stringify({ afterNodeId, title, type, targetMin: 30, topics: [] }),
      });
      PathState.activePath = await PathAPI.get(pathId);
      _updateArtifactPanel(PathState.activePath);
    } catch(e) { console.warn('[Path] Add node failed:', e); }
  },

  // ── Node actions ─────────────────────────────────────────────
  async _markNodeDone(pathId, nodeId) {
    await PathAPI.completeNode(pathId, nodeId);
    PathState.activePath = await PathAPI.get(pathId);
    _renderPathPage(PathState.activePath);
  },

  async _undoNodeDone(pathId, nodeId) {
    try {
      await fetch(`${state.apiUrl || ''}/api/v1/paths/${pathId}/nodes/${nodeId}/start`, {
        method: 'POST', headers: _pathHeaders(),
        body: JSON.stringify({ sessionId: null }),
      });
    } catch(e) {}
    PathState.activePath = await PathAPI.get(pathId);
    _renderPathPage(PathState.activePath);
  },

  // ── Refine chat ──────────────────────────────────────────────
  async _sendRefine() {
    const input = document.getElementById('path-refine-input');
    if (!input) return;
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    input.disabled = true;

    const path = PathState.activePath;
    if (!path) return;

    const msgsEl = document.getElementById('path-refine-msgs');

    // Save user message to persistent chat
    _addChatMsg('user', msg);

    // Attachment note
    const fileInput = document.getElementById('path-page-file') || document.getElementById('path-refine-file');
    let attachmentNote = '';
    if (fileInput && fileInput.files.length) {
      attachmentNote = ` [Attached: ${fileInput.files[0].name}]`;
      fileInput.value = '';
      document.getElementById('path-refine-file-name')?.remove();
    }

    // Show thinking with streaming status
    if (msgsEl) {
      msgsEl.innerHTML += `
        <div id="path-refine-thinking" style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px">
          <div style="width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,#34d399,#22c584);
            display:grid;place-items:center;font-size:8px;font-weight:800;color:#0a0f1a;flex-shrink:0;margin-top:2px">E</div>
          <div style="flex:1">
            <div id="path-refine-agent-text" style="font-size:12px;color:rgba(255,255,255,.8);line-height:1.5"></div>
            <div style="display:flex;align-items:center;gap:6px;margin-top:4px">
              <div class="path-gen-spinner" style="width:14px;height:14px;border-width:2px"></div>
              <span id="path-refine-status" style="font-size:10.5px;color:rgba(255,255,255,.35)">Thinking...</span>
            </div>
          </div>
        </div>`;
    }

    try {
      const res = await fetch(`${state.apiUrl || ''}/api/v1/paths/${path.pathId}/refine`, {
        method: 'POST', headers: _pathHeaders(),
        body: JSON.stringify({ message: msg + attachmentNote }),
      });

      let finalResult = null;
      let agentText = '';
      const contentType = res.headers.get('content-type') || '';

      if (contentType.includes('text/event-stream') && res.body) {
        // Stream SSE events
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
              const event = JSON.parse(line.slice(6));
              const statusEl = document.getElementById('path-refine-status');
              const textEl = document.getElementById('path-refine-agent-text');

              if (event.type === 'status' && statusEl) statusEl.textContent = event.message;
              else if (event.type === 'agent_text' && textEl) {
                agentText += event.text;
                textEl.innerHTML = _md(agentText);
                // Hide spinner once text starts flowing
                if (statusEl) statusEl.parentElement.style.display = 'none';
                // Auto-scroll chat to follow streaming text
                if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
              }
              else if (event.type === 'tool_call' && statusEl) statusEl.textContent = event.message;
              else if (event.type === 'artifact_update') {
                // Agent directly modified nodes — refresh artifact panel
                PathAPI.get(event.pathId || path.pathId).then(p => {
                  if (p) { PathState.activePath = p; _updateArtifactPanel(p); }
                });
              }
              else if (event.type === 'refine_ready') finalResult = event.result;
              else if (event.type === 'error') throw new Error(event.message);
            } catch (e) { if (e.message && !e.message.startsWith('Unexpected')) throw e; }
          }
        }
      } else {
        finalResult = await res.json();
      }

      document.getElementById('path-refine-thinking')?.remove();

      if (finalResult?.type === 'chat') {
        _addChatMsg('agent', finalResult.message || agentText);
      } else if (finalResult?.type === 'changes' && finalResult.proposedNodes) {
        // Structural changes via emit_path — persist the text + show apply buttons
        const reason = finalResult.reason || agentText || 'Here are the proposed changes:';
        _addChatMsg('agent', reason);
        // Show apply/keep buttons (not persisted — ephemeral UI)
        if (msgsEl) {
          msgsEl.innerHTML += `
            <div style="display:flex;gap:6px;margin-bottom:10px;padding-left:27px">
              <button onclick="PathUI._applyRefine(${finalResult.pivotIndex})" style="
                padding:5px 11px;border-radius:6px;border:none;
                background:linear-gradient(135deg,#34d399,#22c584);color:#0a0f1a;
                font-size:10px;font-weight:700;cursor:pointer;font-family:inherit;
              ">Apply changes</button>
              <button onclick="this.parentElement.remove()" style="
                padding:5px 11px;border-radius:6px;border:1px solid rgba(255,255,255,.08);
                background:none;color:rgba(255,255,255,.4);
                font-size:10px;font-weight:600;cursor:pointer;font-family:inherit;
              ">Keep current</button>
            </div>`;
        }
        PathState._pendingRefine = finalResult;
      } else if (agentText) {
        _addChatMsg('agent', agentText);
      }
    } catch (e) {
      document.getElementById('path-refine-thinking')?.remove();
      if (msgsEl) {
        msgsEl.innerHTML += `
          <div style="font-size:11px;color:#f87171;margin-bottom:8px;padding-left:28px">${_escHtml(e.message || 'Refinement failed')}</div>`;
      }
    }

    input.disabled = false;
    input.focus();
  },

  async _applyRefine(pivotIndex) {
    const path = PathState.activePath;
    if (!path || !PathState._pendingRefine) return;

    const proposed = PathState._pendingRefine.proposedNodes;
    await PathAPI.applyPivot(path.pathId, pivotIndex, proposed);

    // Reload and re-render into the current view
    PathState.activePath = await PathAPI.get(path.pathId);
    // Update artifact in-place (preserves chat history)
    _updateArtifactPanel(PathState.activePath);
    PathState._pendingRefine = null;
  },

  renderHomeCards: renderPathCards,
  showScopeHint,
  renderBreadcrumb: renderPathBreadcrumb,
};

// Diff pills helper
function _renderDiffPills(diff) {
  if (!diff) return '';
  let html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">';
  for (const a of (diff.added || [])) {
    html += `<span style="font-size:10px;padding:2px 7px;border-radius:999px;background:rgba(52,211,153,.1);
      color:#34d399;border:1px solid rgba(52,211,153,.2)">+ ${_escHtml(a)}</span>`;
  }
  for (const r of (diff.removed || [])) {
    html += `<span style="font-size:10px;padding:2px 7px;border-radius:999px;background:rgba(248,113,113,.08);
      color:#f87171;border:1px solid rgba(248,113,113,.15);text-decoration:line-through">- ${_escHtml(r)}</span>`;
  }
  for (const m of (diff.modified || [])) {
    html += `<span style="font-size:10px;padding:2px 7px;border-radius:999px;background:rgba(96,165,250,.08);
      color:#60a5fa;border:1px solid rgba(96,165,250,.15)">~ ${_escHtml(m)}</span>`;
  }
  html += '</div>';
  return html;
}

window.PathUI = PathUI;
window.PathState = PathState;
window.PathAPI = PathAPI;
