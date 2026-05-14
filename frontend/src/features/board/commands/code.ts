import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';
import type { BoardCommand } from '../engine/state';

interface CodeCmd extends BoardCommand {
  code?: string;
  text?: string;
  language?: string;
  editable?: boolean;
}

let monacoLoaderPromise: Promise<typeof import('monaco-editor')> | null = null;
async function loadMonaco() {
  if (!monacoLoaderPromise) {
    monacoLoaderPromise = import('monaco-editor').catch(() => {
      // Monaco failed to load (e.g. in offline tests); fall back to plain pre.
      return null as unknown as typeof import('monaco-editor');
    });
  }
  return monacoLoaderPromise;
}

export async function renderCodeCommand(cmd: BoardCommand): Promise<void> {
  const c = cmd as CodeCmd;
  const code = c.code ?? c.text ?? '';
  const language = c.language ?? 'javascript';
  if (!code) return;

  const el = createElement('div', cmd, 'bd-code');
  el.style.minHeight = '180px';
  placeElement(el, cmd.placement ?? 'below', cmd);

  const monaco = await loadMonaco();
  if (!monaco?.editor) {
    // Fallback for environments without monaco (jsdom etc.).
    const pre = document.createElement('pre');
    pre.className = 'bd-code-pre';
    pre.dataset.language = language;
    const codeEl = document.createElement('code');
    codeEl.textContent = code;
    pre.appendChild(codeEl);
    el.appendChild(pre);
    return;
  }

  const editor = monaco.editor.create(el, {
    value: code,
    language,
    theme: 'vs-dark',
    readOnly: !c.editable,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    automaticLayout: true,
    fontSize: 13,
    lineNumbers: 'on',
  });
  // Auto-size to content
  const lineHeight = editor.getOption(monaco.editor.EditorOption.lineHeight);
  const lineCount = code.split('\n').length;
  el.style.height = `${Math.min(lineCount * lineHeight + 24, 460)}px`;
}
