import { describe, it, expect } from 'vitest';
import { chatFrames, frame } from './protocol';

describe('chatFrames helpers', () => {
  it('message frame carries text and merges extra', () => {
    const f = chatFrames.message('hi', { sessionId: 's1' });
    expect(f.type).toBe('MESSAGE');
    expect((f as Record<string, unknown>).text).toBe('hi');
    expect((f as Record<string, unknown>).sessionId).toBe('s1');
  });

  it('interrupt and cancel frames have only their type', () => {
    expect(chatFrames.interrupt()).toEqual({ type: 'INTERRUPT' });
    expect(chatFrames.cancel()).toEqual({ type: 'CANCEL' });
  });

  it('voiceMode frame carries the mode', () => {
    expect(chatFrames.voiceMode('on')).toEqual({ type: 'VOICE_MODE', mode: 'on' });
    expect(chatFrames.voiceMode('off')).toEqual({ type: 'VOICE_MODE', mode: 'off' });
  });

  it('injectContext frame wraps payload under context', () => {
    const f = chatFrames.injectContext({ source: 'tutor', topic: 'graphs' });
    expect(f.type).toBe('INJECT_CONTEXT');
    expect((f as Record<string, unknown>).context).toEqual({
      source: 'tutor',
      topic: 'graphs',
    });
  });

  it('frame() builder spreads payload onto type', () => {
    const f = frame('PING', { ts: 123 });
    expect(f).toEqual({ type: 'PING', ts: 123 });
  });

  it('frame() with no payload only has type', () => {
    expect(frame('PING')).toEqual({ type: 'PING' });
  });
});
