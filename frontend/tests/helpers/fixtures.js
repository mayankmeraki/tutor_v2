/**
 * Shared test fixtures: mock data for sessions, users, etc.
 */

export const MOCK_SESSION = {
  session_id: 'test-session-001',
  status: 'active',
  scenario: 'general',
  created_at: new Date().toISOString(),
  transcript: [],
  plan: null,
  assessment: null,
};

export const MOCK_SESSIONS_LIST = [
  {
    session_id: 'session-a',
    headline: 'Limits intro',
    status: 'active',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    last_message: 'Let me explain the concept of limits...',
  },
  {
    session_id: 'session-b',
    headline: 'Cell structure',
    status: 'active',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    last_message: 'The cell membrane is a phospholipid bilayer...',
  },
];

export const MOCK_SSE_TEACHING = [
  'data: {"type":"status","content":"thinking"}',
  'data: {"type":"text","content":"<teaching-text>Let me explain the concept of limits.\\n\\nA limit describes the value that a function approaches as the input approaches a certain value.</teaching-text>"}',
  'data: {"type":"text","content":"<teaching-mcq id=\\"q1\\"><q>What does a limit describe?</q><o correct=\\"true\\">The value a function approaches</o><o>The maximum of a function</o><o>The derivative</o></teaching-mcq>"}',
  'data: {"type":"plan","content":{"topic":"Limits","steps":["Define limits","Show examples","Practice problems"]}}',
  'data: [DONE]',
];

export const MOCK_USER = {
  user_id: 'usr-test-001',
  name: 'Test User',
  email: 'testuser@capacity.test',
};
