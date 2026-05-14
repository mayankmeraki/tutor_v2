import { useNavigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card } from '@/components/ui/Card';
import { useAuth } from '@/features/auth/AuthProvider';
import { useEffect, useState } from 'react';

export function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [prompt, setPrompt] = useState('');

  useEffect(() => {
    if (isAuthenticated) navigate('/home', { replace: true });
  }, [isAuthenticated, navigate]);

  const onStart = () => {
    if (prompt.trim()) {
      sessionStorage.setItem('lp_prompt', prompt.trim());
    }
    navigate('/login');
  };

  return (
    <AppShell>
      <div className="app-screen max-w-[960px] mx-auto px-6 pt-12">
        <section className="max-w-[620px] mx-auto mb-12 text-center">
          <h1 className="text-[42px] font-extrabold tracking-[-1px] leading-[1.15] mb-4 text-white">
            One tutor. Every subject.
            <br />
            Taught <em className="not-italic text-accent">live</em>.
          </h1>
          <p className="text-base text-text-muted leading-[1.6] max-w-[480px] mx-auto mb-8">
            An AI tutor that draws on a board, speaks, and adapts to you in real time.
            Upload your notes, follow any video, or just ask.
          </p>
          <div className="max-w-[500px] mx-auto flex gap-2 items-center bg-bg-surface border border-border rounded-[14px] p-2">
            <Input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="What do you want to learn?"
              className="border-0 bg-transparent flex-1"
              onKeyDown={(e) => {
                if (e.key === 'Enter') onStart();
              }}
            />
            <Button variant="accent" onClick={onStart}>
              Try it now &rarr;
            </Button>
          </div>
          <div className="mt-3 text-[11px] text-text-dim">
            Free to try. No credit card.
          </div>
        </section>

        <div className="text-center mb-7">
          <div className="text-[11px] font-semibold text-accent uppercase tracking-[1.2px] mb-1.5">
            How it works
          </div>
          <div className="text-[15px] text-text-muted">
            Three ways to learn with Euler
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
          <DemoCard
            title="Ask the tutor anything"
            description="Type a topic — live board, voice, animations, step by step"
            tone="accent"
          />
          <DemoCard
            title="Video follow-along"
            description="Paste a lecture — pause anytime, ask a question, tutor explains on the board"
            tone="purple"
          />
          <DemoCard
            title="Bring your own materials"
            description="Upload homework, notes, or PDFs — ask anything, the tutor explains from your content"
            tone="blue"
          />
        </div>

        <section className="max-w-[860px] mx-auto pt-14 pb-6">
          <div className="text-center mb-10">
            <div className="text-[11px] font-semibold text-accent uppercase tracking-[1.2px] mb-2.5">
              Study your way
            </div>
            <h2 className="text-[28px] font-bold tracking-[-0.3px] text-white mb-3">
              Your materials. Organized. Taught.
            </h2>
            <p className="text-sm text-text-muted leading-[1.7] max-w-[540px] mx-auto">
              Group your study materials into{' '}
              <strong className="text-white/80">collections</strong> — exam papers,
              lecture notes, textbooks, YouTube playlists — and let Euler teach you
              directly from them.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <Card>
              <h3 className="text-sm font-semibold text-white/90 mb-1.5">
                Collections
              </h3>
              <p className="text-xs text-text-muted leading-relaxed">
                Group files by subject, exam, or topic. Each collection is a
                self-contained study pack the tutor searches when you ask a question.
              </p>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold text-white/90 mb-1.5">
                Any format
              </h3>
              <p className="text-xs text-text-muted leading-relaxed">
                PDFs, lecture slides, handwritten notes, YouTube links, images, audio
                recordings — even scanned exam papers are processed via AI vision.
              </p>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold text-white/90 mb-1.5">
                Smart retrieval
              </h3>
              <p className="text-xs text-text-muted leading-relaxed">
                Euler finds the right page, the right paragraph, the right equation
                — then explains it with a live board, voice, and step-by-step
                animation.
              </p>
            </Card>
          </div>
        </section>

        <footer className="text-center py-6 border-t border-border mt-12 text-[10px] text-text-dim">
          <a
            href="mailto:mayank@seekcapacity.ai"
            className="text-text-dim hover:text-text-muted"
          >
            mayank@seekcapacity.ai
          </a>
          <span className="mx-1.5">·</span>
          <a href="tel:+919772187848" className="text-text-dim hover:text-text-muted">
            +91 97721 87848
          </a>
        </footer>
      </div>
    </AppShell>
  );
}

interface DemoCardProps {
  title: string;
  description: string;
  tone: 'accent' | 'purple' | 'blue';
}

function DemoCard({ title, description, tone }: DemoCardProps) {
  const toneClasses = {
    accent: 'bg-accent/10 text-accent',
    purple: 'bg-[#a78bfa]/10 text-[#a78bfa]',
    blue: 'bg-[#60a5fa]/10 text-[#60a5fa]',
  };
  return (
    <Card className="hover:border-border-active transition-colors">
      <div
        className={`w-10 h-10 rounded-[10px] grid place-items-center mb-3 ${toneClasses[tone]}`}
      >
        <span className="text-lg">●</span>
      </div>
      <h3 className="text-base font-semibold text-white/90 mb-1">{title}</h3>
      <p className="text-xs text-text-muted leading-relaxed">{description}</p>
    </Card>
  );
}
