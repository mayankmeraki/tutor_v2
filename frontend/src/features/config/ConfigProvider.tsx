import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { configApi, type AppConfig } from '@/lib/api';

interface ConfigContextValue {
  config: AppConfig | null;
  loading: boolean;
  error: Error | null;
}

const ConfigContext = createContext<ConfigContextValue>({
  config: null,
  loading: true,
  error: null,
});

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    configApi
      .get()
      .then((c) => {
        if (!cancelled) setConfig(c);
      })
      .catch((e) => {
        if (!cancelled) setError(e as Error);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ConfigContext.Provider value={{ config, loading, error }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useConfig(): ConfigContextValue {
  return useContext(ConfigContext);
}
