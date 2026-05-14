export type ChatFrameType =
  | 'MESSAGE'
  | 'INTERRUPT'
  | 'CANCEL'
  | 'VOICE_MODE'
  | 'INJECT_CONTEXT'
  | 'PING'
  | 'PONG';

export interface ChatFrame {
  type: ChatFrameType;
  payload?: unknown;
  [key: string]: unknown;
}

export interface ScribeFrame {
  type: string;
  text?: string;
  [key: string]: unknown;
}

export type WsReadyState =
  | 'connecting'
  | 'open'
  | 'closing'
  | 'closed'
  | 'error';
