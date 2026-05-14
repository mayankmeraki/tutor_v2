import { api } from './base';

export interface JudgeTestCase {
  input?: string;
  expected_output?: string;
  expectedOutput?: string;
  [key: string]: unknown;
}

/** Backend (`/api/v1/judge/run|submit`) expects `code`, `language`, `test_cases`. */
export interface JudgeRunRequest {
  code: string;
  language: string;
  test_cases?: JudgeTestCase[];
  problem_slug?: string;
}

export interface JudgeCaseResult {
  passed: boolean;
  input?: string;
  expected?: string;
  actual?: string;
  stderr?: string;
  time?: string;
  status?: string;
}

export interface JudgeResult {
  status: string;
  stdout?: string;
  stderr?: string;
  compile_output?: string;
  time?: string;
  memory?: number;
  passed?: boolean;
  cases?: JudgeCaseResult[];
  error?: string;
}

export const judgeApi = {
  run: (body: JudgeRunRequest) =>
    api.post<JudgeResult>('/api/v1/judge/run', body),
  submit: (body: JudgeRunRequest) =>
    api.post<JudgeResult>('/api/v1/judge/submit', body),
};
