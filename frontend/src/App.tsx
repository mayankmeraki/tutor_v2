import { AppRoutes } from './routes';
import { AuthProvider } from './features/auth/AuthProvider';
import { ConfigProvider } from './features/config/ConfigProvider';
import { ToastProvider } from './components/ui/Toast';

export function App() {
  return (
    <ConfigProvider>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </ConfigProvider>
  );
}
