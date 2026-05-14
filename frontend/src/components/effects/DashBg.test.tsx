import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { DashBg } from './DashBg';

beforeEach(() => {
  // jsdom's getContext returns null by default; provide a stub that records
  // calls so we can assert the canvas effect ran without rendering pixels.
  const ctx2d = {
    clearRect: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    setTransform: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    arc: vi.fn(),
    ellipse: vi.fn(),
    rect: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    fillRect: vi.fn(),
    translate: vi.fn(),
    rotate: vi.fn(),
    scale: vi.fn(),
    createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
    createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
    quadraticCurveTo: vi.fn(),
    bezierCurveTo: vi.fn(),
    fillText: vi.fn(),
    strokeText: vi.fn(),
    arcTo: vi.fn(),
    measureText: vi.fn(() => ({ width: 0 })),
    set fillStyle(_v: unknown) {},
    set strokeStyle(_v: unknown) {},
    set lineWidth(_v: unknown) {},
    set globalAlpha(_v: unknown) {},
    set lineCap(_v: unknown) {},
    set lineJoin(_v: unknown) {},
    set globalCompositeOperation(_v: unknown) {},
    set font(_v: unknown) {},
    set textAlign(_v: unknown) {},
  };
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx2d as unknown as CanvasRenderingContext2D) as never;
});

describe('DashBg', () => {
  it('mounts a fixed canvas without throwing', () => {
    const { container } = render(<DashBg />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeTruthy();
    expect(canvas?.getAttribute('aria-hidden')).toBe('true');
    cleanup();
  });

  it('cleans up the rAF loop on unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const { unmount } = render(<DashBg />);
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });
});
