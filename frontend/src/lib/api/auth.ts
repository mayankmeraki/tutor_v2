import { api } from './base';
import type { AuthUser } from '@/stores/auth';

export interface LoginResponse {
  token: string;
  user: AuthUser;
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/api/v1/auth/login', { email, password }),
  google: (credential: string) =>
    api.post<LoginResponse>('/api/v1/auth/google', { credential }),
  me: () => api.get<AuthUser>('/api/v1/auth/me'),
  logout: () => api.post<{ ok: boolean }>('/api/v1/auth/logout'),
};
