// Тонкая обёртка над официальным SDK Telegram (telegram-web-app.js).
// initDataUnsafe никогда не используется для авторизации: на backend
// уходит только сырая строка initData, подпись проверяет сервер.

type TelegramWebApp = {
  initData: string;
  version: string;
  platform: string;
  colorScheme: "light" | "dark";
  ready: () => void;
  expand: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getWebApp(): TelegramWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

/** Есть ли подписанные данные запуска — признак открытия из Telegram. */
export function getInitData(): string | null {
  const data = getWebApp()?.initData;
  return data && data.length > 0 ? data : null;
}

export function initWebApp(): void {
  const app = getWebApp();
  if (!app) return;
  app.ready();
  app.expand();
  try {
    app.setHeaderColor("#0D0F12");
    app.setBackgroundColor("#0D0F12");
  } catch {
    // Старые клиенты Telegram не поддерживают смену цвета
  }
}
