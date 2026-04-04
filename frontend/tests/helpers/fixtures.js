/**
 * Shared test fixtures: mock data for courses, sessions, etc.
 */

export const MOCK_COURSES = [
  {
    course_id: 1,
    name: 'Introduction to Calculus',
    description: 'Learn derivatives and integrals from scratch.',
    tag: 'Mathematics',
    total_lessons: 12,
    total_modules: 4,
    estimated_hours: 8,
  },
  {
    course_id: 2,
    name: 'Cell Biology Fundamentals',
    description: 'Explore the building blocks of life.',
    tag: 'Biology',
    total_lessons: 10,
    total_modules: 3,
    estimated_hours: 6,
  },
];

export const MOCK_COURSE_DETAIL = {
  course_id: 1,
  name: 'Introduction to Calculus',
  description: 'Learn derivatives and integrals from scratch.',
  tag: 'Mathematics',
  total_lessons: 12,
  total_modules: 4,
  estimated_hours: 8,
  outcomes: ['Understand limits', 'Compute derivatives', 'Solve integrals'],
  prerequisites: ['Algebra', 'Trigonometry'],
  lessons: [
    {
      lesson_id: 1,
      lesson_number: 1,
      title: 'What is a Limit?',
      description: 'Introduction to the concept of limits.',
      module_name: 'Foundations',
      duration_minutes: 30,
      thumbnail_url: null,
      video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    },
    {
      lesson_id: 2,
      lesson_number: 2,
      title: 'Computing Limits',
      description: 'Techniques for evaluating limits.',
      module_name: 'Foundations',
      duration_minutes: 45,
      thumbnail_url: null,
      video_url: null,
    },
  ],
};

export const MOCK_SESSION = {
  session_id: 'test-session-001',
  course_id: 1,
  course_name: 'Introduction to Calculus',
  lesson_id: 1,
  lesson_title: 'What is a Limit?',
  status: 'active',
  scenario: 'course',
  created_at: new Date().toISOString(),
  transcript: [],
  plan: null,
  assessment: null,
};

export const MOCK_SESSIONS_LIST = [
  {
    session_id: 'session-a',
    course_name: 'Introduction to Calculus',
    lesson_title: 'What is a Limit?',
    status: 'active',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    last_message: 'Let me explain the concept of limits...',
  },
  {
    session_id: 'session-b',
    course_name: 'Cell Biology',
    lesson_title: 'Cell Structure',
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
