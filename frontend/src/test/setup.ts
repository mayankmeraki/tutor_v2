import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom under Node 25/Cursor's electron-as-node sometimes ships a Storage
// object that only implements length/key but not setItem/getItem. Provide a
// drop-in polyfill so zustand's `persist` middleware works in tests.
function ensureStorage(name: 'localStorage' | 'sessionStorage') {
  const w = window as unknown as Record<string, unknown>;
  const existing = w[name] as Storage | undefined;
  if (existing && typeof existing.setItem === 'function') return;
  const map = new Map<string, string>();
  const stub: Storage = {
    get length() {
      return map.size;
    },
    key: (i: number) => Array.from(map.keys())[i] ?? null,
    getItem: (k: string) => (map.has(k) ? (map.get(k) as string) : null),
    setItem: (k: string, v: string) => {
      map.set(k, String(v));
    },
    removeItem: (k: string) => {
      map.delete(k);
    },
    clear: () => {
      map.clear();
    },
  };
  Object.defineProperty(window, name, {
    configurable: true,
    enumerable: true,
    value: stub,
    writable: true,
  });
  Object.defineProperty(globalThis, name, {
    configurable: true,
    enumerable: true,
    value: stub,
    writable: true,
  });
}
ensureStorage('localStorage');
ensureStorage('sessionStorage');

if (typeof (globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver === 'undefined') {
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {
      /* noop */
    }
    unobserve() {
      /* noop */
    }
    disconnect() {
      /* noop */
    }
  };
}

if (typeof (globalThis as unknown as { IntersectionObserver?: unknown }).IntersectionObserver === 'undefined') {
  (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
    root = null;
    rootMargin = '';
    thresholds = [];
  };
}

if (typeof URL.createObjectURL === 'undefined') {
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: () => 'blob:test',
  });
}
if (typeof URL.revokeObjectURL === 'undefined') {
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    value: () => undefined,
  });
}

// scrollIntoView isn't implemented in jsdom; engine auto-scroll calls it.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {
    /* noop */
  };
}

// matchMedia for components that gate animations on prefers-reduced-motion.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }) as unknown as MediaQueryList;
}

// Reset DOM after each test
afterEach(() => {
  cleanup();
  document.body.innerHTML = '';
  // Reset zustand-persisted auth store between tests.
  try {
    window.localStorage.clear();
    window.sessionStorage.clear();
  } catch {
    /* ignore */
  }
});
