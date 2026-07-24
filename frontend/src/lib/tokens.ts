// localStorage-backed token store. Keys are fixed by the frontend spec.

export const ACCESS_KEY = "argi_access";
export const REFRESH_KEY = "argi_refresh";
export const SESSION_KEY = "argi_session";

const isBrowser = typeof window !== "undefined";

export function getAccess(): string | null {
  if (!isBrowser) return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function getRefresh(): string | null {
  if (!isBrowser) return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  if (!isBrowser) return;
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  if (!isBrowser) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export function getStoredSessionId(): number | null {
  if (!isBrowser) return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function setStoredSessionId(id: number | null): void {
  if (!isBrowser) return;
  if (id === null) {
    window.localStorage.removeItem(SESSION_KEY);
  } else {
    window.localStorage.setItem(SESSION_KEY, String(id));
  }
}
