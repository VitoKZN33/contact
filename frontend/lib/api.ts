import { z } from "zod";

// Клиент API. Backend на том же домене за Nginx. Токен сессии — в памяти и
// в sessionStorage (живёт, пока открыт Mini App). При 401 один раз выполняется
// повторный вход по initData, затем запрос повторяется.

const errorSchema = z.object({
  error: z.object({ code: z.string(), message: z.string(), request_id: z.string().optional() }),
});

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const TOKEN_KEY = "contact.session";
let memoryToken: string | null = null;
let reauthHandler: (() => Promise<boolean>) | null = null;

export function getToken(): string | null {
  if (memoryToken) return memoryToken;
  try {
    memoryToken = window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    memoryToken = null;
  }
  return memoryToken;
}

export function setToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Хранилище недоступно — токен остаётся в памяти
  }
}

export function setReauthHandler(handler: (() => Promise<boolean>) | null): void {
  reauthHandler = handler;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  auth?: boolean;
};

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const token = options.auth === false ? null : getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    return await fetch(path, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("network", "Нет соединения с сервером. Проверьте интернет.", 0);
  }
}

export async function api<T>(path: string, schema: z.ZodType<T> | null, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options);

  if (response.status === 401 && options.auth !== false && reauthHandler) {
    if (await reauthHandler()) response = await send(path, options);
  }

  if (response.status === 204) return undefined as T;

  const json: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = errorSchema.safeParse(json);
    if (parsed.success) throw new ApiError(parsed.data.error.code, parsed.data.error.message, response.status);
    if (response.status === 502 || response.status === 504) {
      throw new ApiError("ai_timeout", "Сервер не ответил вовремя. Попробуйте ещё раз.", response.status);
    }
    throw new ApiError("http_error", `Ошибка сервера (${response.status})`, response.status);
  }
  if (schema === null) return json as T;
  const parsed = schema.safeParse(json);
  if (!parsed.success) throw new ApiError("bad_response", "Сервер вернул неожиданный ответ", response.status);
  return parsed.data;
}

export function newId(): string {
  try {
    return crypto.randomUUID().replace(/-/g, "");
  } catch {
    // Старые WebView без randomUUID
    return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  }
}

/** Человеческий текст ошибки для экрана. Сообщения backend уже на русском. */
export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Что-то пошло не так. Попробуйте ещё раз.";
}

export function errorCode(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null;
}
