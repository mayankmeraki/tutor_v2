import { useEffect, useRef } from 'react';
import { useAuth } from './AuthProvider';
import { useConfig } from '@/features/config/ConfigProvider';

declare global {
  interface Window {
    google?: {
      accounts?: {
        id: {
          initialize: (cfg: {
            client_id: string;
            callback: (resp: { credential: string }) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (
            el: HTMLElement,
            options: Record<string, unknown>,
          ) => void;
          prompt: () => void;
        };
      };
    };
  }
}

interface Props {
  text?: 'signin_with' | 'continue_with' | 'signup_with';
  onError?: (err: Error) => void;
  onSuccess?: () => void;
}

export function GoogleSignIn({ text = 'continue_with', onError, onSuccess }: Props) {
  const { config } = useConfig();
  const { loginWithGoogle } = useAuth();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!config?.googleClientId) return;
    let cancelled = false;

    const init = () => {
      const goog = window.google?.accounts?.id;
      if (!goog || !ref.current || cancelled) return;
      goog.initialize({
        client_id: config.googleClientId!,
        callback: async (resp) => {
          try {
            await loginWithGoogle(resp.credential);
            onSuccess?.();
          } catch (e) {
            onError?.(e as Error);
          }
        },
      });
      goog.renderButton(ref.current, {
        theme: 'filled_black',
        size: 'large',
        type: 'standard',
        shape: 'pill',
        text,
        width: 280,
      });
    };

    if (window.google?.accounts?.id) {
      init();
    } else {
      const id = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(id);
          init();
        }
      }, 200);
      return () => clearInterval(id);
    }
    return () => {
      cancelled = true;
    };
  }, [config?.googleClientId, loginWithGoogle, text, onError, onSuccess]);

  if (!config?.googleClientId) {
    return (
      <div className="text-text-dim text-sm">
        Google Sign-In not configured.
      </div>
    );
  }

  return <div ref={ref} className="flex justify-center" />;
}
