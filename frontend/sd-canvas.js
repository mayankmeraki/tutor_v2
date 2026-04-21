/**
 * System Design Canvas — Excalidraw-inspired Fabric.js Canvas
 *
 * Features: colored shapes, hand-drawn font, natural arrows,
 * shape presets (service, DB, queue, client), pan/zoom gestures
 */

const SDCanvas = (() => {
  let canvas = null;
  let _tool = 'select';
  let _drawing = false;
  let _start = null;
  let _temp = null;
  let _syncing = false;
  let _spaceDown = false;
  let _colorIdx = 0;

  // Excalidraw-inspired color palette
  const PALETTE = [
    { stroke: '#6C8EBF', fill: 'rgba(108,142,191,0.08)', name: 'blue' },     // services
    { stroke: '#82B366', fill: 'rgba(130,179,102,0.08)', name: 'green' },    // databases
    { stroke: '#D6B656', fill: 'rgba(214,182,86,0.08)', name: 'amber' },     // cache/queue
    { stroke: '#B85450', fill: 'rgba(184,84,80,0.08)', name: 'red' },        // clients
    { stroke: '#9673A6', fill: 'rgba(150,115,166,0.08)', name: 'purple' },   // external
    { stroke: '#D79B00', fill: 'rgba(215,155,0,0.08)', name: 'orange' },     // workers
  ];
  const TUTOR_STYLE = { stroke: 'rgba(255,255,255,0.2)', fill: 'rgba(255,255,255,0.02)', text: 'rgba(255,255,255,0.4)' };
  const FONT = "'Caveat', 'Segoe Print', cursive";
  const MONO = "'JetBrains Mono', monospace";

  function _nextColor() { return PALETTE[_colorIdx++ % PALETTE.length]; }

  function init() {
    if (canvas) { try { canvas.dispose(); } catch(e) {} canvas = null; }
    if (typeof fabric === 'undefined') { console.warn('[SD] Fabric.js not loaded'); return; }
    var area = document.getElementById('ws-canvas-area');
    var el = document.getElementById('ws-fabric-canvas');
    if (!area || !el) return;
    el.width = area.offsetWidth;
    el.height = area.offsetHeight;
    _colorIdx = 0;

    canvas = new fabric.Canvas('ws-fabric-canvas', {
      backgroundColor: 'transparent',
      selection: true,
      selectionColor: 'rgba(108,142,191,0.08)',
      selectionBorderColor: 'rgba(108,142,191,0.3)',
      selectionLineWidth: 1,
      preserveObjectStacking: true,
      rotationCursor: 'crosshair',
    });

    // Enable rotation and better control styling on all objects
    fabric.Object.prototype.set({
      transparentCorners: false,
      cornerColor: 'rgba(108,142,191,0.6)',
      cornerStrokeColor: 'rgba(108,142,191,0.8)',
      cornerSize: 8,
      cornerStyle: 'circle',
      borderColor: 'rgba(108,142,191,0.4)',
      hasRotatingPoint: true,
      rotatingPointOffset: 20,
    });

    // Resize
    new ResizeObserver(function() {
      if (!canvas) return;
      canvas.setWidth(area.offsetWidth);
      canvas.setHeight(area.offsetHeight);
      canvas.renderAll();
    }).observe(area);

    _setupToolbar();
    _setupKeyboard();
    _setupMouse();
    _setupPanZoom(area);

    // Show the empty state hint
    var emptyHint = document.getElementById('ws-canvas-empty');
    if (emptyHint) { emptyHint.style.display = ''; emptyHint.style.opacity = '1'; }

    console.log('[SD] Canvas initialized');
  }

  // ── Toolbar ──
  function _setupToolbar() {
    var tb = document.getElementById('ws-canvas-toolbar');
    if (!tb) return;
    tb.addEventListener('click', function(e) {
      var btn = e.target.closest('[data-tool]');
      if (!btn) return;
      var t = btn.dataset.tool;
      if (t === 'delete') { _deleteSelected(); return; }
      _setTool(t);
      tb.querySelectorAll('.ws-tool').forEach(function(b) { b.classList.remove('sel'); });
      btn.classList.add('sel');
    });
  }

  // ── Keyboard ──
  function _setupKeyboard() {
    document.addEventListener('keydown', function(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
      var pane = document.getElementById('ws-canvas-pane');
      if (!pane || pane.style.display === 'none') return;
      var map = { r: 'rect', d: 'diamond', e: 'ellipse', a: 'arrow', l: 'line', t: 'text', v: 'select', f: 'freehand', h: 'pan' };
      if (map[e.key]) { var b = document.querySelector('#ws-canvas-toolbar [data-tool="' + map[e.key] + '"]'); if (b) b.click(); }
      if (e.key === 'Delete' || e.key === 'Backspace') { _deleteSelected(); e.preventDefault(); }
      if (e.code === 'Space' && !e.target.matches('input,textarea,[contenteditable]')) { _spaceDown = true; if (canvas) canvas.defaultCursor = 'grab'; }
    });
    document.addEventListener('keyup', function(e) {
      if (e.code === 'Space') { _spaceDown = false; if (canvas) canvas.defaultCursor = _tool === 'select' ? 'default' : 'crosshair'; }
    });
  }

  // ── Mouse drawing ──
  function _setupMouse() {
    canvas.on('mouse:down', function(opt) {
      // Hide empty state hint on first interaction
      var emptyHint = document.getElementById('ws-canvas-empty');
      if (emptyHint && emptyHint.style.opacity !== '0') { emptyHint.style.opacity = '0'; setTimeout(function() { emptyHint.style.display = 'none'; }, 500); }

      if (canvas._panning || _tool === 'select' || _tool === 'freehand' || _tool === 'pan') return;

      // Text tool: can click anywhere on canvas (even on existing objects)
      if (_tool === 'text') {
        var p = canvas.getPointer(opt.e);
        var c = _nextColor();
        var t = new fabric.IText('', {
          left: p.x, top: p.y, fontSize: 22, fill: c.stroke,
          fontFamily: FONT, _src: 'student', _color: c.name,
        });
        canvas.add(t);
        canvas.setActiveObject(t);
        t.enterEditing();
        _drawing = false;
        _toSelect();
        return;
      }

      // For shape/arrow/line tools: don't draw on top of existing objects
      if (opt.target && !opt.target._isTemp) return;
      var p = canvas.getPointer(opt.e);
      _drawing = true;
      _start = { x: p.x, y: p.y };

      if (_tool === 'arrow' || _tool === 'line') {
        _temp = new fabric.Line([p.x, p.y, p.x, p.y], {
          stroke: 'rgba(108,142,191,0.5)', strokeWidth: 2,
          selectable: false, evented: false, _isTemp: true,
          strokeDashArray: _tool === 'line' ? null : [5, 3],
        });
        canvas.add(_temp);
        return;
      }

      // Shape tools
      var c = _nextColor();
      if (_tool === 'rect') {
        _temp = new fabric.Rect({ left: p.x, top: p.y, width: 0, height: 0, fill: c.fill, stroke: c.stroke, strokeWidth: 2, rx: 8, ry: 8, _src: 'student', _color: c.name, _isTemp: true });
      } else if (_tool === 'ellipse') {
        _temp = new fabric.Ellipse({ left: p.x, top: p.y, rx: 0, ry: 0, fill: c.fill, stroke: c.stroke, strokeWidth: 2, _src: 'student', _color: c.name, _isTemp: true });
      } else if (_tool === 'diamond') {
        _temp = new fabric.Rect({ left: p.x, top: p.y, width: 0, height: 0, fill: c.fill, stroke: c.stroke, strokeWidth: 2, angle: 45, _src: 'student', _color: c.name, _isTemp: true });
      }
      if (_temp) canvas.add(_temp);
    });

    canvas.on('mouse:move', function(opt) {
      if (!_drawing || !_temp || _tool === 'select') return;
      var p = canvas.getPointer(opt.e);
      if (_tool === 'arrow' || _tool === 'line') {
        _temp.set({ x2: p.x, y2: p.y });
      } else {
        var l = Math.min(_start.x, p.x), t = Math.min(_start.y, p.y);
        var w = Math.abs(p.x - _start.x), h = Math.abs(p.y - _start.y);
        if (_tool === 'ellipse') _temp.set({ left: l, top: t, rx: w / 2, ry: h / 2 });
        else _temp.set({ left: l, top: t, width: w, height: h });
      }
      canvas.renderAll();
    });

    canvas.on('mouse:up', function(opt) {
      if (!_drawing) return;
      _drawing = false;
      var p = canvas.getPointer(opt.e);

      // Arrow/line completion — single path with arrowhead, not separate objects
      if ((_tool === 'arrow' || _tool === 'line') && _temp && _start) {
        canvas.remove(_temp);
        var dx = p.x - _start.x, dy = p.y - _start.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > 15) {
          if (_tool === 'arrow') {
            // Draw arrow as a path: line + arrowhead in one object
            var angle = Math.atan2(dy, dx);
            var headLen = 12;
            var hx1 = p.x - headLen * Math.cos(angle - Math.PI / 6);
            var hy1 = p.y - headLen * Math.sin(angle - Math.PI / 6);
            var hx2 = p.x - headLen * Math.cos(angle + Math.PI / 6);
            var hy2 = p.y - headLen * Math.sin(angle + Math.PI / 6);
            var pathStr = 'M ' + _start.x + ' ' + _start.y + ' L ' + p.x + ' ' + p.y +
              ' M ' + hx1 + ' ' + hy1 + ' L ' + p.x + ' ' + p.y + ' L ' + hx2 + ' ' + hy2;
            var arrow = new fabric.Path(pathStr, {
              fill: '', stroke: 'rgba(148,163,184,0.6)', strokeWidth: 2,
              strokeLineCap: 'round', strokeLineJoin: 'round',
              _src: 'student', _type: 'arrow',
            });
            canvas.add(arrow);
          } else {
            var line = new fabric.Line([_start.x, _start.y, p.x, p.y], {
              stroke: 'rgba(148,163,184,0.6)', strokeWidth: 2,
              _src: 'student', _type: 'line',
            });
            canvas.add(line);
          }
        }
        _temp = null; _start = null;
        _toSelect();
        return;
      }

      // Shape completion
      if (_temp) {
        _temp._isTemp = false;
        var w = _temp.width || 0, h = _temp.height || 0;
        if (_tool === 'ellipse') { w = (_temp.rx || 0) * 2; h = (_temp.ry || 0) * 2; }
        if (w < 20 && h < 20) {
          if (_tool === 'ellipse') _temp.set({ rx: 50, ry: 30 });
          else _temp.set({ width: 140, height: 60 });
        }
        _temp.setCoords();
        canvas.setActiveObject(_temp);
        canvas.renderAll();
      }
      _temp = null; _start = null;
      _toSelect();
    });

    // Double-click to add/edit label
    canvas.on('mouse:dblclick', function(opt) {
      var target = opt.target;
      if (!target) return;
      if (target.type === 'i-text') { target.enterEditing(); return; }
      // Add text label at center of shape
      var c = target.getCenterPoint();
      var color = target._color ? PALETTE.find(function(p) { return p.name === target._color; }) : PALETTE[0];
      var t = new fabric.IText(target._label || '', {
        left: c.x, top: c.y,
        fontSize: 16, fill: (color || PALETTE[0]).stroke,
        fontFamily: FONT, fontWeight: '600',
        originX: 'center', originY: 'center',
        _src: 'student', textAlign: 'center',
      });
      canvas.add(t);
      canvas.setActiveObject(t);
      t.enterEditing();
    });
  }

  // ── Pan & Zoom ──
  function _setupPanZoom(area) {
    // Pan: alt+drag, middle click, space+drag
    canvas.on('mouse:down', function(o) {
      if (o.e.altKey || o.e.button === 1 || _spaceDown || _tool === 'pan') {
        canvas._panning = true; canvas._panX = o.e.clientX; canvas._panY = o.e.clientY;
        canvas.selection = false; canvas.defaultCursor = 'grabbing';
      }
    });
    canvas.on('mouse:move', function(o) {
      if (canvas._panning) {
        var vpt = canvas.viewportTransform;
        vpt[4] += o.e.clientX - canvas._panX; vpt[5] += o.e.clientY - canvas._panY;
        canvas._panX = o.e.clientX; canvas._panY = o.e.clientY;
        canvas.requestRenderAll();
      }
    });
    canvas.on('mouse:up', function() {
      canvas._panning = false; canvas.selection = (_tool === 'select');
      canvas.defaultCursor = (_spaceDown || _tool === 'pan') ? 'grab' : (_tool === 'select' ? 'default' : 'crosshair');
    });

    // Zoom: ctrl+scroll (pinch) and scroll wheel
    canvas.on('mouse:wheel', function(o) {
      if (!o.e.ctrlKey) {
        // Two-finger trackpad pan
        var vpt = canvas.viewportTransform;
        vpt[4] -= o.e.deltaX; vpt[5] -= o.e.deltaY;
        canvas.requestRenderAll();
      } else {
        // Pinch zoom
        var z = canvas.getZoom() * (0.99 ** o.e.deltaY);
        z = Math.min(Math.max(0.15, z), 5);
        canvas.zoomToPoint({ x: o.e.offsetX, y: o.e.offsetY }, z);
      }
      o.e.preventDefault(); o.e.stopPropagation();
    });

    // Touch: pinch zoom + two-finger pan
    var _lastDist = 0, _lastCenter = null;
    area.addEventListener('touchstart', function(e) {
      if (e.touches.length === 2) {
        e.preventDefault();
        var dx = e.touches[0].clientX - e.touches[1].clientX;
        var dy = e.touches[0].clientY - e.touches[1].clientY;
        _lastDist = Math.sqrt(dx * dx + dy * dy);
        _lastCenter = { x: (e.touches[0].clientX + e.touches[1].clientX) / 2, y: (e.touches[0].clientY + e.touches[1].clientY) / 2 };
      }
    }, { passive: false });
    area.addEventListener('touchmove', function(e) {
      if (e.touches.length === 2 && _lastDist > 0) {
        e.preventDefault();
        var dx = e.touches[0].clientX - e.touches[1].clientX;
        var dy = e.touches[0].clientY - e.touches[1].clientY;
        var dist = Math.sqrt(dx * dx + dy * dy);
        var center = { x: (e.touches[0].clientX + e.touches[1].clientX) / 2, y: (e.touches[0].clientY + e.touches[1].clientY) / 2 };
        var z = Math.min(Math.max(0.15, canvas.getZoom() * (dist / _lastDist)), 5);
        var rect = area.getBoundingClientRect();
        canvas.zoomToPoint({ x: center.x - rect.left, y: center.y - rect.top }, z);
        if (_lastCenter) {
          var vpt = canvas.viewportTransform;
          vpt[4] += center.x - _lastCenter.x; vpt[5] += center.y - _lastCenter.y;
        }
        _lastDist = dist; _lastCenter = center;
        canvas.requestRenderAll();
      }
    }, { passive: false });
    area.addEventListener('touchend', function() { _lastDist = 0; _lastCenter = null; });
  }

  // ── Tool management ──
  function _setTool(t) {
    _tool = t; _drawing = false; _temp = null; _start = null;
    if (!canvas) return;
    canvas.isDrawingMode = (t === 'freehand');
    if (t === 'freehand' && canvas.freeDrawingBrush) {
      canvas.freeDrawingBrush.color = PALETTE[0].stroke;
      canvas.freeDrawingBrush.width = 2;
    }
    if (t === 'pan') {
      canvas.selection = false;
      canvas.defaultCursor = 'grab';
      canvas.forEachObject(function(o) { o.selectable = false; o.evented = false; });
    } else {
      canvas.selection = (t === 'select');
      canvas.defaultCursor = t === 'select' ? 'default' : 'crosshair';
      canvas.forEachObject(function(o) { o.selectable = (t === 'select'); o.evented = (t === 'select'); });
    }
    canvas.renderAll();
  }

  function _toSelect() {
    _tool = 'select'; _drawing = false; _temp = null; _start = null;
    if (canvas) {
      canvas.isDrawingMode = false; canvas.selection = true;
      canvas.defaultCursor = 'default';
      canvas.forEachObject(function(o) { o.selectable = true; o.evented = true; });
    }
    var tb = document.getElementById('ws-canvas-toolbar');
    if (tb) {
      tb.querySelectorAll('.ws-tool').forEach(function(b) { b.classList.remove('sel'); });
      var s = tb.querySelector('[data-tool="select"]'); if (s) s.classList.add('sel');
    }
  }

  function _deleteSelected() {
    if (!canvas) return;
    canvas.getActiveObjects().forEach(function(o) { canvas.remove(o); });
    canvas.discardActiveObject(); canvas.renderAll();
    _debouncedSync();
  }

  // ── State sync ──
  var _syncTimer = null;
  function _debouncedSync() { if (_syncing) return; if (_syncTimer) clearTimeout(_syncTimer); _syncTimer = setTimeout(syncState, 300); }

  function syncState() {
    if (!canvas || _syncing) return;
    _syncing = true;
    try {
      var els = [];
      canvas.forEachObject(function(o) {
        els.push({
          id: o._sdId || '', type: o.type === 'i-text' ? 'text' : o.type,
          label: o.text || o._label || '', source: o._src || 'student',
          color: o._color || '',
        });
      });
      window._sdCanvasState = { elements: els };
    } finally { _syncing = false; }
  }

  function getSnapshot() {
    if (!canvas) return null;
    try { return canvas.toDataURL({ format: 'png', quality: 0.6, multiplier: 0.5 }); } catch (e) { return null; }
  }

  function clear() {
    if (!canvas) return;
    canvas.clear(); canvas.backgroundColor = 'transparent';
    canvas.renderAll(); _colorIdx = 0; _tutorX = 40; _tutorY = 40; _tutorRowH = 0;
  }

  // ── Tutor drawing ──
  var _tutorX = 40, _tutorY = 40, _tutorRowH = 0;

  function addTutorShape(s) {
    if (!canvas) return;
    var w = s.w || 140, h = s.h || 55;
    var hasContent = s.content && s.content.trim();
    if (hasContent) { var lines = s.content.split('\n'); h = Math.max(h, 34 + lines.length * 14); }

    var cw = canvas.getWidth() || 600;
    if (_tutorX + w + 30 > cw) { _tutorX = 40; _tutorY += _tutorRowH + 35; _tutorRowH = 0; }
    var x = _tutorX, y = _tutorY;
    _tutorX += w + 35; _tutorRowH = Math.max(_tutorRowH, h);

    var parts = [];
    if (s.type === 'ellipse' || s.type === 'circle')
      parts.push(new fabric.Ellipse({ left: 0, top: 0, rx: w / 2, ry: h / 2, fill: TUTOR_STYLE.fill, stroke: TUTOR_STYLE.stroke, strokeWidth: 1.5 }));
    else if (s.type === 'diamond')
      parts.push(new fabric.Rect({ left: 0, top: 0, width: w * .7, height: h * .7, fill: TUTOR_STYLE.fill, stroke: TUTOR_STYLE.stroke, strokeWidth: 1.5, angle: 45 }));
    else
      parts.push(new fabric.Rect({ left: 0, top: 0, width: w, height: h, fill: TUTOR_STYLE.fill, stroke: TUTOR_STYLE.stroke, strokeWidth: 1.5, rx: 6, ry: 6 }));

    if (s.label) parts.push(new fabric.Text(s.label, { left: 0, top: hasContent ? (-h / 2 + 14) : 0, fontSize: hasContent ? 13 : 14, fill: TUTOR_STYLE.text, fontFamily: FONT, fontWeight: '600', originX: 'center', originY: hasContent ? 'top' : 'center' }));
    if (hasContent) parts.push(new fabric.Text(s.content, { left: -w / 2 + 10, top: -h / 2 + 30, fontSize: 10, fill: 'rgba(255,255,255,0.2)', fontFamily: MONO, lineHeight: 1.3, originX: 'left', originY: 'top' }));
    if (s.sublabel && !hasContent) parts.push(new fabric.Text(s.sublabel, { left: 0, top: 12, fontSize: 10, fill: 'rgba(255,255,255,0.15)', fontFamily: FONT, originX: 'center', originY: 'center' }));

    var group = new fabric.Group(parts, { left: x, top: y, _src: 'tutor', _sdId: s.id, _label: s.label || '' });
    canvas.add(group); canvas.renderAll();
  }

  function addTutorConnection(c) {
    if (!canvas) return;
    var from = null, to = null;
    canvas.forEachObject(function(o) { if (o._sdId === c.from) from = o; if (o._sdId === c.to) to = o; });
    if (!from || !to) return;
    var fc = from.getCenterPoint(), tc = to.getCenterPoint();
    var dx = tc.x - fc.x, dy = tc.y - fc.y;
    var angle = Math.atan2(dy, dx);
    var hl = 10;
    var hx1 = tc.x - hl * Math.cos(angle - Math.PI / 6);
    var hy1 = tc.y - hl * Math.sin(angle - Math.PI / 6);
    var hx2 = tc.x - hl * Math.cos(angle + Math.PI / 6);
    var hy2 = tc.y - hl * Math.sin(angle + Math.PI / 6);
    var pathStr = 'M ' + fc.x + ' ' + fc.y + ' L ' + tc.x + ' ' + tc.y +
      ' M ' + hx1 + ' ' + hy1 + ' L ' + tc.x + ' ' + tc.y + ' L ' + hx2 + ' ' + hy2;
    var arrow = new fabric.Path(pathStr, {
      fill: '', stroke: 'rgba(148,163,184,0.25)', strokeWidth: 1.5,
      strokeLineCap: 'round', strokeLineJoin: 'round',
      selectable: false, evented: false, _src: 'tutor',
    });
    canvas.add(arrow);
    canvas.renderAll();
  }

  function handleTutorDraw(data) {
    if (!canvas) return;
    if (data.clear) clear();
    (data.add_nodes || []).forEach(function(n) { addTutorShape({ id: n.id, type: n.type || 'rect', label: n.label, sublabel: n.sublabel, content: n.content }); });
    (data.add_edges || []).forEach(function(e) { addTutorConnection({ from: e.from, to: e.to }); });
    (data.remove || []).forEach(function(id) { var rm = []; canvas.forEachObject(function(o) { if (o._sdId === id) rm.push(o); }); rm.forEach(function(o) { canvas.remove(o); }); });
    if (data.highlight && data.highlight.length) {
      var ids = new Set(data.highlight);
      canvas.forEachObject(function(o) {
        if (ids.has(o._sdId)) {
          var os = o.stroke; o.set('stroke', '#f5d89a'); canvas.renderAll();
          setTimeout(function() { o.set('stroke', os); canvas.renderAll(); }, 2000);
        }
      });
    }
    (data.annotate || []).forEach(function(a) {
      var target = null; canvas.forEachObject(function(o) { if (o._sdId === a.near) target = o; });
      if (target) {
        var cp = target.getCenterPoint();
        canvas.add(new fabric.Text(a.text, { left: cp.x + (target.width || 60) / 2 + 15, top: cp.y, fontSize: 12, fill: 'rgba(108,142,191,0.6)', fontFamily: FONT, originY: 'center', _src: 'tutor' }));
        canvas.renderAll();
      }
    });
    syncState();
  }

  return { init, syncState, getSnapshot, clear, handleTutorDraw, addTutorShape, addTutorConnection };
})();
