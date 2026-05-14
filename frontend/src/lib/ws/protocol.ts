import type { ChatFrame, ChatFrameType, ScribeFrame } from './types';

export function frame<T extends Record<string, unknown>>(
  type: ChatFrameType,
  payload?: T,
): ChatFrame {
  return { type, ...(payload ?? {}) };
}

export const chatFrames = {
  message: (text: string, extra?: Record<string, unknown>): ChatFrame =>
    ({ type: 'MESSAGE', text, ...(extra ?? {}) }) as ChatFrame,
  interrupt: (extra?: Record<string, unknown>): ChatFrame =>
    ({ type: 'INTERRUPT', ...(extra ?? {}) }) as ChatFrame,
  cancel: (): ChatFrame => ({ type: 'CANCEL' }) as ChatFrame,
  voiceMode: (mode: 'on' | 'off'): ChatFrame =>
    ({ type: 'VOICE_MODE', mode }) as ChatFrame,
  injectContext: (ctx: Record<string, unknown>): ChatFrame =>
    ({ type: 'INJECT_CONTEXT', context: ctx }) as ChatFrame,
  ping: (): ChatFrame => ({ type: 'PING' }) as ChatFrame,
};

export type { ChatFrame, ScribeFrame };
