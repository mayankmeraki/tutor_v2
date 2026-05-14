import { describe, it, expect } from 'vitest';
import { cn } from './cn';

describe('cn() class merger', () => {
  it('joins strings with spaces', () => {
    expect(cn('a', 'b', 'c')).toBe('a b c');
  });

  it('drops falsy values', () => {
    expect(cn('a', false, undefined, null, 0, '')).toBe('a');
  });

  it('handles arrays and conditionals', () => {
    expect(cn(['a', 'b'], { c: true, d: false })).toBe('a b c');
  });
});
