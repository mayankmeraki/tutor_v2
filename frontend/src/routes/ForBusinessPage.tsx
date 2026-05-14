import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { Input, TextArea } from '@/components/ui/Input';
import { useToast } from '@/components/ui/Toast';
import { feedbackApi } from '@/lib/api';

export function ForBusinessPage() {
  const [contactOpen, setContactOpen] = useState(false);
  const { toast } = useToast();
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const send = async () => {
    if (!message.trim()) return;
    setSubmitting(true);
    try {
      await feedbackApi.send({
        type: 'business_contact',
        email,
        message,
      });
      toast('Thanks — we will be in touch.', 'success');
      setContactOpen(false);
      setEmail('');
      setMessage('');
    } catch (err) {
      toast((err as Error).message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="app-screen max-w-[860px] mx-auto px-6 pt-12 text-center">
        <div className="mb-16">
          <div className="text-[11px] font-semibold text-accent uppercase tracking-[1.2px] mb-2.5">
            For Institutions
          </div>
          <h1 className="text-[38px] font-extrabold tracking-[-1px] leading-[1.15] mb-4 text-white">
            Your curriculum.
            <br />
            Taught by AI. <em className="not-italic text-accent">Live.</em>
          </h1>
          <p className="text-base text-text-muted leading-[1.6] max-w-[520px] mx-auto mb-7">
            Upload your courses and lecture videos. Euler teaches each student 1-on-1
            with a live board, voice, and animations — following your syllabus, not
            ours.
          </p>
          <div className="flex gap-2.5 justify-center flex-wrap">
            <Button variant="accent" size="lg" onClick={() => setContactOpen(true)}>
              Schedule a Demo
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-left">
          <Card>
            <h3 className="text-base font-semibold mb-1.5 text-white">
              Your syllabus
            </h3>
            <p className="text-sm text-text-muted leading-relaxed">
              Upload curriculum, lecture notes, problem sets. Euler teaches strictly
              from your material.
            </p>
          </Card>
          <Card>
            <h3 className="text-base font-semibold mb-1.5 text-white">
              Per-student tutoring
            </h3>
            <p className="text-sm text-text-muted leading-relaxed">
              Every learner gets a 1-on-1 live tutor — board, voice, animations,
              quizzes — no waiting rooms.
            </p>
          </Card>
          <Card>
            <h3 className="text-base font-semibold mb-1.5 text-white">
              Insights & progress
            </h3>
            <p className="text-sm text-text-muted leading-relaxed">
              Track completion, mastery, and where students get stuck — across every
              chapter.
            </p>
          </Card>
        </div>
      </div>

      <Modal
        open={contactOpen}
        onClose={() => setContactOpen(false)}
        title="Get in touch"
      >
        <div className="flex flex-col gap-3">
          <label className="block">
            <span className="text-xs text-text-muted block mb-1">Your email</span>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@school.edu"
            />
          </label>
          <label className="block">
            <span className="text-xs text-text-muted block mb-1">Message</span>
            <TextArea
              rows={5}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Tell us about your institution..."
            />
          </label>
          <Button variant="accent" onClick={send} loading={submitting}>
            Send
          </Button>
        </div>
      </Modal>
    </AppShell>
  );
}
