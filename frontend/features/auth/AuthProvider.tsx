"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { api, ApiError, getToken, setReauthHandler, setToken } from "@/lib/api";
import { loginSchema, meSchema, type User } from "@/lib/schemas";
import { getInitData } from "@/lib/telegram";

type AuthState =
  | { status: "loading" }
  | { status: "outside" }
  | { status: "error"; message: string; retryable: boolean }
  | { status: "ready"; user: User };

type AuthContextValue = {
  state: AuthState;
  retry: () => void;
  setUser: (user: User) => void;
  signOutLocal: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function loginWithInitData(initData: string): Promise<User> {
  const result = await api("/api/v1/auth/telegram", loginSchema, {
    method: "POST",
    body: { init_data: initData },
    auth: false,
  });
  setToken(result.token);
  return result.user;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const loginInFlight = useRef<Promise<boolean> | null>(null);

  const authenticate = useCallback(async () => {
    setState({ status: "loading" });
    // Telegram SDK грузится до гидрации, но даём ему мгновение на инициализацию
    await new Promise((resolve) => setTimeout(resolve, 50));
    const initData = getInitData();
    if (!initData) {
      setState({ status: "outside" });
      return;
    }
    try {
      if (getToken()) {
        try {
          const me = await api("/api/v1/auth/me", meSchema);
          setState({ status: "ready", user: me.user });
          return;
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 401) throw error;
          setToken(null);
        }
      }
      const user = await loginWithInitData(initData);
      setState({ status: "ready", user });
    } catch (error) {
      if (error instanceof ApiError && error.code === "init_data_expired") {
        setState({ status: "error", message: "Сессия устарела. Закройте и снова откройте приложение.", retryable: false });
      } else if (error instanceof ApiError && error.status === 401) {
        setState({ status: "error", message: "Не удалось подтвердить вход через Telegram.", retryable: false });
      } else if (error instanceof ApiError && error.status === 403) {
        setState({ status: "error", message: "Доступ к приложению ограничен.", retryable: false });
      } else {
        const message = error instanceof ApiError ? error.message : "Не удалось подключиться к серверу.";
        setState({ status: "error", message, retryable: true });
      }
    }
  }, []);

  useEffect(() => {
    // Если токен истёк во время работы — тихо входим заново по тем же initData
    setReauthHandler(async () => {
      const initData = getInitData();
      if (!initData) return false;
      if (!loginInFlight.current) {
        loginInFlight.current = loginWithInitData(initData)
          .then(() => true)
          .catch(() => false)
          .finally(() => {
            loginInFlight.current = null;
          });
      }
      return loginInFlight.current;
    });
    void authenticate();
    return () => setReauthHandler(null);
  }, [authenticate]);

  const value: AuthContextValue = {
    state,
    retry: () => void authenticate(),
    setUser: (user) => setState({ status: "ready", user }),
    signOutLocal: () => {
      setToken(null);
      setState({ status: "error", message: "Данные удалены. Закройте приложение.", retryable: false });
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth вне AuthProvider");
  return ctx;
}

export function useUser(): User {
  const { state } = useAuth();
  if (state.status !== "ready") throw new Error("useUser до входа");
  return state.user;
}
