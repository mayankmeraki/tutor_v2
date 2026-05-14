import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { useState } from 'react';
import { Button } from './Button';
import { Modal } from './Modal';
import { Tabs } from './Tabs';
import { ToastProvider, useToast } from './Toast';

describe('Button', () => {
  it('renders text and triggers onClick', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Submit</Button>);
    fireEvent.click(screen.getByText('Submit'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('respects disabled state', () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Save
      </Button>,
    );
    const btn = screen.getByText('Save').closest('button')!;
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('shows spinner and disables when loading', () => {
    render(<Button loading>Working</Button>);
    const btn = screen.getByText('Working').closest('button')!;
    expect(btn).toBeDisabled();
  });
});

describe('Modal', () => {
  it('renders nothing when closed', () => {
    const { queryByText } = render(
      <Modal open={false} onClose={() => {}} title="Hi">
        body
      </Modal>,
    );
    expect(queryByText('Hi')).toBeNull();
  });

  it('shows content when open', () => {
    render(
      <Modal open onClose={() => {}} title="Hi">
        <p>body text</p>
      </Modal>,
    );
    expect(screen.getByText('Hi')).toBeInTheDocument();
    expect(screen.getByText('body text')).toBeInTheDocument();
  });

  it('locks body scroll while open', () => {
    const { unmount } = render(
      <Modal open onClose={() => {}} title="Hi">
        body
      </Modal>,
    );
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('calls onClose on Escape', () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Hi">
        x
      </Modal>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop clicked', () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Hi">
        x
      </Modal>,
    );
    // Click on the role=presentation backdrop
    const backdrop = document.querySelector('[role="presentation"]')!;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });
});

describe('Tabs', () => {
  function setup() {
    return render(
      <Tabs
        tabs={[
          { id: 'a', label: 'Alpha', content: <div>alpha-content</div> },
          { id: 'b', label: 'Beta', content: <div>beta-content</div> },
        ]}
      />,
    );
  }

  it('shows the first tab by default', () => {
    setup();
    expect(screen.getByText('alpha-content')).toBeInTheDocument();
    expect(screen.queryByText('beta-content')).toBeNull();
  });

  it('switches when a tab is clicked', () => {
    setup();
    fireEvent.click(screen.getByText('Beta'));
    expect(screen.getByText('beta-content')).toBeInTheDocument();
    expect(screen.queryByText('alpha-content')).toBeNull();
  });
});

describe('ToastProvider', () => {
  function Trigger() {
    const { toast } = useToast();
    return (
      <button type="button" onClick={() => toast('hello there', 'success', 0)}>
        push
      </button>
    );
  }

  it('renders a toast when toast() is called', () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText('push'));
    expect(screen.getByText('hello there')).toBeInTheDocument();
  });

  it('caps stack at 5 toasts', () => {
    function Many() {
      const { toast } = useToast();
      return (
        <button onClick={() => {
          for (let i = 0; i < 10; i++) toast(`t${i}`, 'info', 0);
        }}>spam</button>
      );
    }
    render(
      <ToastProvider>
        <Many />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText('spam'));
    // Last 5 (t5..t9) should be visible.
    expect(screen.queryByText('t0')).toBeNull();
    expect(screen.queryByText('t4')).toBeNull();
    expect(screen.getByText('t5')).toBeInTheDocument();
    expect(screen.getByText('t9')).toBeInTheDocument();
  });

  it('auto-dismisses after duration', async () => {
    vi.useFakeTimers();
    function Auto() {
      const { toast } = useToast();
      return (
        <button onClick={() => toast('soon gone', 'info', 100)}>go</button>
      );
    }
    render(
      <ToastProvider>
        <Auto />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText('go'));
    expect(screen.getByText('soon gone')).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(150);
    });
    expect(screen.queryByText('soon gone')).toBeNull();
    vi.useRealTimers();
  });
});

// Smoke test: stateful Modal via consumer state — exercises focus trap setup.
describe('Modal — focus management', () => {
  function App({ withTitle }: { withTitle: boolean }) {
    const [open, setOpen] = useState(true);
    return (
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={withTitle ? 'Form' : undefined}
      >
        <input data-testid="m-1" />
        <input data-testid="m-2" />
        <button data-testid="m-3">Submit</button>
      </Modal>
    );
  }
  it('focuses the first focusable child on open (no title → first input)', async () => {
    render(<App withTitle={false} />);
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(() => r(undefined)));
    });
    expect(document.activeElement).toBe(screen.getByTestId('m-1'));
  });

  it('with a title, focus lands on the close button (first focusable)', async () => {
    render(<App withTitle={true} />);
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(() => r(undefined)));
    });
    const closeBtn = screen.getByLabelText('Close');
    expect(document.activeElement).toBe(closeBtn);
  });
});
