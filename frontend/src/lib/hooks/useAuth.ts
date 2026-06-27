'use client';

import { useCallback, useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import type { User, TokenResponse, LoginRequest, RegisterRequest } from '@/types';

const ACCESS_TOKEN_KEY = 'docops_access_token';
const REFRESH_TOKEN_KEY = 'docops_refresh_token';

function getStoredTokens(): { accessToken: string | null; refreshToken: string | null } {
  if (typeof window === 'undefined') return { accessToken: null, refreshToken: null };
  return {
    accessToken: localStorage.getItem(ACCESS_TOKEN_KEY),
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
  };
}

function storeTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function useAuth() {
  const { user, setUser } = useAppStore();
  const queryClient = useQueryClient();
  const [tokens, setTokens] = useState<{ accessToken: string | null; refreshToken: string | null }>(getStoredTokens);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: try to load user from token
  useEffect(() => {
    const init = async () => {
      const stored = getStoredTokens();
      if (stored.accessToken) {
        setTokens(stored);
        try {
          const userData = await api.get<User>('/auth/me');
          setUser(userData);
        } catch {
          // Token expired or invalid — try refresh
          if (stored.refreshToken) {
            try {
              const refreshed = await api.post<TokenResponse>('/auth/refresh', {
                refresh_token: stored.refreshToken,
              });
              storeTokens(refreshed.access_token, refreshed.refresh_token);
              setTokens({ accessToken: refreshed.access_token, refreshToken: refreshed.refresh_token });
              const userData = await api.get<User>('/auth/me');
              setUser(userData);
            } catch {
              clearTokens();
              setTokens({ accessToken: null, refreshToken: null });
              setUser(null);
            }
          } else {
            clearTokens();
            setTokens({ accessToken: null, refreshToken: null });
            setUser(null);
          }
        }
      } else {
        setUser(null);
      }
      setIsLoading(false);
    };
    init();
  }, [setUser]);

  const loginMutation = useMutation({
    mutationFn: (data: LoginRequest) => api.post<TokenResponse>('/auth/login', data),
    onSuccess: async (tokens) => {
      storeTokens(tokens.access_token, tokens.refresh_token);
      setTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
      const userData = await api.get<User>('/auth/me');
      setUser(userData);
    },
  });

  const registerMutation = useMutation({
    mutationFn: (data: RegisterRequest) => api.post<User>('/auth/register', data),
  });

  const logout = useCallback(() => {
    clearTokens();
    setTokens({ accessToken: null, refreshToken: null });
    setUser(null);
    queryClient.clear();
  }, [setUser, queryClient]);

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    accessToken: tokens.accessToken,
    login: loginMutation.mutateAsync,
    loginError: loginMutation.error,
    isLoggingIn: loginMutation.isPending,
    register: registerMutation.mutateAsync,
    registerError: registerMutation.error,
    isRegistering: registerMutation.isPending,
    logout,
  };
}
