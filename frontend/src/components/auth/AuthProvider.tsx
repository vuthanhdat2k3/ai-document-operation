'use client';

import { createContext, useContext, type ReactNode } from 'react';
import { useAuth } from '@/lib/hooks/useAuth';
import type { User, TokenResponse } from '@/types';


interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (data: { email: string; password: string }) => Promise<TokenResponse>;
  loginError: Error | null;
  isLoggingIn: boolean;
  register: (data: { email: string; password: string; full_name: string }) => Promise<User>;
  registerError: Error | null;
  isRegistering: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider');
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();

  if (auth.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="relative flex h-8 w-8 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
          </div>
          <p className="text-sm text-muted-foreground/70">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={auth}>
      {children}
    </AuthContext.Provider>
  );
}
