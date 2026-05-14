import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Editor from '@monaco-editor/react';
import { TopNav } from '@/components/layout/TopNav';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { dsaApi, judgeApi, type JudgeResult } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { cn } from '@/components/ui/cn';

const MONACO_LANG_MAP: Record<string, string> = {
  python: 'python',
  python3: 'python',
  javascript: 'javascript',
  js: 'javascript',
  typescript: 'typescript',
  ts: 'typescript',
  java: 'java',
  cpp: 'cpp',
  'c++': 'cpp',
  c: 'c',
  go: 'go',
  rust: 'rust',
};

function monacoLang(lang: string): string {
  return MONACO_LANG_MAP[lang.toLowerCase()] ?? 'plaintext';
}

export function DSAProblemPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const problemQ = useQuery({
    queryKey: ['dsa', 'problem', slug],
    queryFn: () => dsaApi.getProblem(slug!),
    enabled: !!slug,
  });

  const langs = useMemo(
    () => Object.keys(problemQ.data?.starterCode ?? { python: '' }),
    [problemQ.data?.starterCode],
  );

  const [language, setLanguage] = useState('python');
  const [source, setSource] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<JudgeResult | null>(null);

  useEffect(() => {
    if (problemQ.data?.starterCode) {
      const map = problemQ.data.starterCode;
      const lang = langs.includes(language) ? language : (langs[0] ?? 'python');
      if (lang !== language) setLanguage(lang);
      const first = map[lang] ?? map.python ?? Object.values(map)[0] ?? '';
      setSource(first);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [problemQ.data?.slug]);

  useEffect(() => {
    if (problemQ.data?.starterCode?.[language]) {
      setSource(problemQ.data.starterCode[language]);
    }
  }, [language, problemQ.data?.starterCode]);

  const onRun = async (submit = false) => {
    if (!source.trim()) {
      toast('Write some code first.', 'warning');
      return;
    }
    setRunning(true);
    setResult(null);
    try {
      const fn = submit ? judgeApi.submit : judgeApi.run;
      const res = await fn({
        code: source,
        language,
        problem_slug: slug,
        // The backend hydrates test_cases from the slug if not provided. We pass
        // any client-side test cases too so legacy fixtures still work.
        test_cases:
          (problemQ.data?.testCases as { input?: string; expected_output?: string }[]) ??
          undefined,
      });
      setResult(res);
      if (res.passed) {
        toast(submit ? 'All tests passed!' : 'Sample tests passed', 'success');
      } else if (res.error) {
        toast(res.error, 'error');
      } else {
        toast('Some tests failed.', 'warning');
      }
    } catch (err) {
      toast((err as Error).message, 'error');
    } finally {
      setRunning(false);
    }
  };

  const onAskTutor = () => {
    if (!problemQ.data) return;
    const ctx = `Help me with: ${problemQ.data.name}\n\nCurrent code (${language}):\n\`\`\`${language}\n${source}\n\`\`\``;
    sessionStorage.setItem('lp_prompt', ctx);
    sessionStorage.setItem('tutor_problem_slug', problemQ.data.slug);
    navigate('/tutor');
  };

  return (
    <div className="flex flex-col h-full">
      <TopNav />
      <div className="flex flex-1 min-h-0">
        <aside className="w-[420px] shrink-0 overflow-y-auto border-r border-border bg-bg-surface p-5">
          <button
            type="button"
            onClick={() => navigate('/dsa')}
            className="text-xs text-text-muted hover:text-text mb-3"
          >
            ← All problems
          </button>
          {problemQ.isLoading ? (
            <div className="flex items-center gap-2 text-text-muted">
              <Spinner /> Loading...
            </div>
          ) : problemQ.data ? (
            <>
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <h1 className="text-lg font-bold">
                  {problemQ.data.num ? `${problemQ.data.num}. ` : ''}
                  {problemQ.data.name}
                </h1>
                {problemQ.data.difficulty && (
                  <span
                    className={cn(
                      'text-[10px] px-2 py-0.5 rounded-full font-semibold',
                      problemQ.data.difficulty === 'Easy' && 'bg-good/15 text-good',
                      problemQ.data.difficulty === 'Medium' && 'bg-warn/15 text-warn',
                      problemQ.data.difficulty === 'Hard' && 'bg-bad/15 text-bad',
                    )}
                  >
                    {problemQ.data.difficulty}
                  </span>
                )}
              </div>
              {problemQ.data.topics && problemQ.data.topics.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {problemQ.data.topics.map((t) => (
                    <span key={t} className="text-[10px] text-text-muted bg-bg-hover rounded-full px-2 py-0.5">
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <div className="text-sm text-text-muted leading-relaxed whitespace-pre-wrap mb-4">
                {problemQ.data.description}
              </div>
              {problemQ.data.examples && problemQ.data.examples.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider mb-2">
                    Examples
                  </h3>
                  <div className="space-y-2">
                    {problemQ.data.examples.map((ex, i) => (
                      <div
                        key={i}
                        className="bg-bg-elevated border border-border rounded-md p-2.5 text-xs font-mono"
                      >
                        {ex.input != null && (
                          <div>
                            <span className="text-text-dim">Input: </span>
                            {ex.input}
                          </div>
                        )}
                        {ex.output != null && (
                          <div>
                            <span className="text-text-dim">Output: </span>
                            {ex.output}
                          </div>
                        )}
                        {ex.explanation && (
                          <div className="text-text-dim mt-1 font-sans">{ex.explanation}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {problemQ.data.constraints && problemQ.data.constraints.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider mb-2">
                    Constraints
                  </h3>
                  <ul className="text-xs text-text-muted leading-relaxed list-disc list-inside font-mono">
                    {problemQ.data.constraints.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {problemQ.data.hints && problemQ.data.hints.length > 0 && (
                <details className="mb-4">
                  <summary className="text-xs font-semibold uppercase tracking-wider cursor-pointer">
                    Hints ({problemQ.data.hints.length})
                  </summary>
                  <ul className="text-xs text-text-muted leading-relaxed mt-2 list-disc list-inside">
                    {problemQ.data.hints.map((h, i) => (
                      <li key={i} className="mb-1">
                        {h}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              <Button variant="accent" className="w-full" onClick={onAskTutor}>
                Ask the tutor
              </Button>
            </>
          ) : (
            <p className="text-text-muted">Problem not found.</p>
          )}
        </aside>
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-bg-surface">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="h-8 bg-bg-elevated border border-border rounded-[6px] text-xs px-2"
              data-testid="dsa-language-select"
            >
              {langs.length > 0 ? (
                langs.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))
              ) : (
                <option value="python">python</option>
              )}
            </select>
            <Button size="sm" onClick={() => onRun(false)} loading={running} data-testid="dsa-run-btn">
              Run
            </Button>
            <Button size="sm" variant="accent" onClick={() => onRun(true)} loading={running} data-testid="dsa-submit-btn">
              Submit
            </Button>
          </div>
          <div className="flex-1 min-h-0">
            <Editor
              theme="vs-dark"
              language={monacoLang(language)}
              value={source}
              onChange={(v) => setSource(v ?? '')}
              options={{
                fontSize: 14,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 4,
                insertSpaces: true,
              }}
            />
          </div>
          {result && <ResultPanel result={result} />}
        </div>
      </div>
    </div>
  );
}

function ResultPanel({ result }: { result: JudgeResult }) {
  return (
    <div className="border-t border-border bg-bg-elevated max-h-[260px] overflow-auto" data-testid="dsa-result-panel">
      <div className="px-4 py-2 flex items-center gap-3 border-b border-border">
        <span
          className={cn(
            'text-xs uppercase tracking-wider px-2 py-0.5 rounded-full font-semibold',
            result.passed ? 'bg-good/15 text-good' : 'bg-bad/15 text-bad',
          )}
        >
          {result.passed ? 'Passed' : 'Failed'}
        </span>
        {result.time && <span className="text-xs text-text-dim">{result.time}</span>}
        {result.cases && (
          <span className="text-xs text-text-dim">
            {result.cases.filter((c) => c.passed).length}/{result.cases.length} cases
          </span>
        )}
      </div>
      {result.compile_output && (
        <div className="p-3 text-xs font-mono text-bad whitespace-pre-wrap">
          {result.compile_output}
        </div>
      )}
      {result.cases && result.cases.length > 0 && (
        <div className="p-3 space-y-2">
          {result.cases.map((c, i) => (
            <div
              key={i}
              className={cn(
                'border rounded p-2 text-xs font-mono',
                c.passed ? 'border-good/30 bg-good/5' : 'border-bad/30 bg-bad/5',
              )}
            >
              <div className="flex justify-between font-sans not-italic mb-1">
                <span className="font-semibold">Case {i + 1}</span>
                <span className={c.passed ? 'text-good' : 'text-bad'}>
                  {c.passed ? '✓ pass' : '✗ fail'}
                </span>
              </div>
              {c.input != null && (
                <div className="text-text-muted">
                  <span className="text-text-dim">Input: </span>
                  {c.input}
                </div>
              )}
              {c.expected != null && (
                <div className="text-text-muted">
                  <span className="text-text-dim">Expected: </span>
                  {c.expected}
                </div>
              )}
              {c.actual != null && (
                <div className={c.passed ? 'text-text-muted' : 'text-bad'}>
                  <span className="text-text-dim">Got: </span>
                  {c.actual}
                </div>
              )}
              {c.stderr && (
                <div className="text-bad whitespace-pre-wrap mt-1">{c.stderr}</div>
              )}
            </div>
          ))}
        </div>
      )}
      {result.error && !result.cases?.length && (
        <div className="p-3 text-xs text-bad whitespace-pre-wrap">{result.error}</div>
      )}
    </div>
  );
}
