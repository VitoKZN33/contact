"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { NetworkBanner } from "@/components/NetworkBanner";
import { Button } from "@/components/ui/Button";
import { FullScreenLoader } from "@/components/ui/States";
import { AuthProvider, useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/lib/api";
import { initWebApp } from "@/lib/telegram";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Ошибки 4xx не повторяем: они не исправятся сами
            retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
            refetchOnWindowFocus: false,
            staleTime: 30_000,
          },
          mutations: { retry: false },
        },
      }),
  );

  useEffect(() => {
    initWebApp();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <NetworkBanner />
        <AuthGate>{children}</AuthGate>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function AuthGate({ children }: { children: ReactNode }) {
  const { state, retry } = useAuth();

  if (state.status === "loading") return <FullScreenLoader label="Подключаемся" />;

  if (state.status === "outside") {
    return (
      <Centered
        title="Откройте в Telegram"
        text="«Контакт» работает внутри Telegram: найдите нашего бота и нажмите «Открыть «Контакт»»."
      />
    );
  }

  if (state.status === "error") {
    return (
      <Centered title="Не удалось войти" text={state.message}>
        {state.retryable ? (
          <Button variant="secondary" onClick={retry}>
            Повторить
          </Button>
        ) : null}
      </Centered>
    );
  }

  return <>{children}</>;
}

function Centered({ title, text, children }: { title: string; text: string; children?: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
      <h1 className="text-display font-semibold tracking-[-0.02em]">{title}</h1>
      <p className="mt-3 text-body text-muted text-pretty">{text}</p>
      {children ? <div className="mt-8">{children}</div> : null}
    </div>
  );
}
