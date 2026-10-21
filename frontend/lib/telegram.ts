// Тонкая обёртка над официальным SDK Telegram (telegram-web-app.js).
// initDataUnsafe никогда не используется для авторизации: на backend
// уходит только сырая строка initData, подпись проверяет сервер.
// Методы новых версий SDK вызываются с проверкой: старые клиенты их не знают.

type BackButton = {
  show: () => void;
  hide: () => void;
  onClick: (cb: () => void) => void;
  offClick: (cb: () => void) => void;
};

type HapticFeedback = {
  impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
  notificationOccurred: (type: "error" | "success" | "warning") => void;
  selectionChanged: () => void;
};

type TelegramWebApp = {
  initData: string;
  version: string;
  platform: string;
  ready: () => void;
  expand: () => void;
  close?: () => void;
  isVersionAtLeast?: (version: string) => boolean;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  setBottomBarColor?: (color: string) => void;
  disableVerticalSwipes?: () => void;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  BackButton?: BackButton;
  HapticFeedback?: HapticFeedback;
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

/** Подписанные данные запуска — есть только при открытии из Telegram. */
export function getInitData(): string | null {
  const data = getWebApp()?.initData;
  return data && data.length > 0 ? data : null;
}

function supports(version: string): boolean {
  const app = getWebApp();
  return Boolean(app?.isVersionAtLeast?.(version));
}

function safely(fn: () => void): void {
  try {
    fn();
  } catch {
    // Метод есть, но клиент его не поддерживает — не критично
  }
}

export function initWebApp(): void {
  const app = getWebApp();
  if (!app) return;
  safely(() => app.ready());
  safely(() => app.expand());
  if (supports("6.1")) {
    safely(() => app.setHeaderColor?.("#0D0F12"));
    safely(() => app.setBackgroundColor?.("#0D0F12"));
  }
  if (supports("7.10")) safely(() => app.setBottomBarColor?.("#0D0F12"));
  // Свайп вниз в чате не должен закрывать приложение
  if (supports("7.7")) safely(() => app.disableVerticalSwipes?.());
}

export function showBackButton(onClick: () => void): () => void {
  const button = getWebApp()?.BackButton;
  if (!button || !supports("6.1")) return () => {};
  safely(() => {
    button.onClick(onClick);
    button.show();
  });
  return () =>
    safely(() => {
      button.offClick(onClick);
      button.hide();
    });
}

export function setClosingConfirmation(enabled: boolean): void {
  const app = getWebApp();
  if (!app || !supports("6.2")) return;
  safely(() => (enabled ? app.enableClosingConfirmation?.() : app.disableClosingConfirmation?.()));
}

export function haptic(kind: "tap" | "success" | "error"): void {
  const feedback = getWebApp()?.HapticFeedback;
  if (!feedback || !supports("6.1")) return;
  safely(() => {
    if (kind === "tap") feedback.impactOccurred("light");
    else feedback.notificationOccurred(kind);
  });
}
