"use client";

import React, { createContext, useContext, useState, useEffect } from 'react';
import { ensureAuthenticated, getToken, clearAuth, type AuthUser } from '@/lib/auth';

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  isLoading: true,
  error: null,
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const authedUser = await ensureAuthenticated();
        if (!cancelled) {
          setUser(authedUser);
          setError(null);
        }
      } catch (e: any) {
        console.error("Auth initialization failed:", e);
        if (!cancelled) {
          // 如果认证失败，清除旧数据并重试一次
          clearAuth();
          try {
            const retryUser = await ensureAuthenticated();
            if (!cancelled) {
              setUser(retryUser);
              setError(null);
            }
          } catch (retryErr: any) {
            if (!cancelled) {
              setError(retryErr.message || "认证失败");
            }
          }
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, []);

  return (
    <AuthContext.Provider value={{ user, token: user?.token ?? null, isLoading, error }}>
      {isLoading ? (
        <div className="flex items-center justify-center h-screen bg-background">
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
            <p className="text-sm text-muted-foreground animate-pulse">Connecting to BioAgent...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-screen bg-background">
          <div className="flex flex-col items-center gap-4 text-center p-8">
            <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center">
              <span className="text-destructive text-xl">!</span>
            </div>
            <p className="text-sm font-medium text-destructive">连接失败: {error}</p>
            <p className="text-xs text-muted-foreground">请确认后端服务已在 localhost:8000 启动</p>
            <button
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm mt-2"
              onClick={() => window.location.reload()}
            >
              重试
            </button>
          </div>
        </div>
      ) : (
        children
      )}
    </AuthContext.Provider>
  );
}
