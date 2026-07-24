// Central API client: base URL, bearer attach, and 401 -> refresh(rotation) -> retry-once.

import {
  clearTokens,
  getAccess,
  getRefresh,
  setStoredSessionId,
  setTokens,
} from "./tokens";
import type {
  AuthUser,
  BillingOtpStart,
  BillingPlansResponse,
  MessagesResponse,
  SessionsResponse,
  Subscription,
  TokenPair,
} from "./types";

export const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

// Single-flight refresh: many concurrent 401s share one refresh round-trip.
let refreshInFlight: Promise<string> | null = null;

function redirectToLogin(): void {
  clearTokens();
  setStoredSessionId(null);
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

/**
 * Exchange the stored refresh token for a fresh pair (rotation: BOTH tokens
 * change). Returns the new access token. Throws + redirects on failure.
 */
export async function refreshTokens(): Promise<string> {
  if (refreshInFlight) return refreshInFlight;

  const refresh_token = getRefresh();
  if (!refresh_token) {
    redirectToLogin();
    throw new ApiError(401, "No refresh token");
  }

  refreshInFlight = (async () => {
    const res = await fetch(`${BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });
    if (!res.ok) {
      redirectToLogin();
      throw new ApiError(res.status, "Refresh failed");
    }
    const data = (await res.json()) as TokenPair;
    // Rotation: persist BOTH new tokens.
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

interface ApiFetchOptions extends RequestInit {
  /** When false, do not attach bearer nor auto-refresh (login/register/refresh). */
  auth?: boolean;
  /** Internal guard to prevent infinite retry loops. */
  _retried?: boolean;
}

/**
 * fetch() wrapper. Attaches Authorization automatically; on 401 refreshes the
 * token pair once and retries the original request a single time.
 */
export async function apiFetch(
  path: string,
  opts: ApiFetchOptions = {},
): Promise<Response> {
  const { auth = true, _retried = false, headers, ...rest } = opts;

  const finalHeaders = new Headers(headers);
  if (!finalHeaders.has("Content-Type") && rest.body) {
    finalHeaders.set("Content-Type", "application/json");
  }
  if (auth) {
    const access = getAccess();
    if (access) finalHeaders.set("Authorization", `Bearer ${access}`);
  }

  const res = await fetch(`${BASE}${path}`, { ...rest, headers: finalHeaders });

  if (res.status === 401 && auth && !_retried) {
    // Try one refresh + retry cycle. refreshTokens throws (and redirects) on fail.
    await refreshTokens();
    return apiFetch(path, { ...opts, _retried: true });
  }

  return res;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown;
    let message = res.statusText;
    try {
      body = await res.json();
      if (body && typeof body === "object") {
        const b = body as Record<string, unknown>;
        message =
          (b.detail as string) || (b.message as string) || JSON.stringify(b);
      }
    } catch {
      /* non-JSON body */
    }
    throw new ApiError(res.status, message, body);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export async function apiLogin(
  phone: string,
  password: string,
): Promise<TokenPair> {
  const res = await apiFetch("/api/auth/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ phone, password }),
  });
  return json<TokenPair>(res);
}

export interface RegisterPayload {
  username: string; // display name
  phone: string;
  password1: string;
  password2: string;
  division_name: string;
  division_code: string;
  district_name: string;
  district_code: string;
  upazila_name: string;
  upazila_code: string;
}

export async function apiRegister(payload: RegisterPayload): Promise<AuthUser> {
  const res = await apiFetch("/api/auth/register", {
    method: "POST",
    auth: false,
    body: JSON.stringify(payload),
  });
  return json<AuthUser>(res);
}

export async function apiLogout(refresh_token: string): Promise<void> {
  // Best-effort: server blacklists the refresh (+ access) jti.
  await apiFetch("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token }),
  }).catch(() => undefined);
}

export async function apiMe(): Promise<AuthUser> {
  const res = await apiFetch("/api/auth/me", { method: "GET" });
  return json<AuthUser>(res);
}

export async function apiChangePassword(
  currentPassword: string,
  newPassword: string,
): Promise<{ message: string }> {
  const res = await apiFetch("/api/auth/password/change", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  return json<{ message: string }>(res);
}

export async function apiRequestPasswordReset(
  phone: string,
): Promise<{
  challenge_id: string;
  expires_in_seconds: number;
  message: string;
  demo_otp: string | null;
}> {
  const res = await apiFetch("/api/auth/password/reset/request", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ phone }),
  });
  return json(res);
}

export async function apiConfirmPasswordReset(
  challengeId: string,
  otp: string,
  newPassword: string,
): Promise<{ message: string }> {
  const res = await apiFetch("/api/auth/password/reset/confirm", {
    method: "POST",
    auth: false,
    body: JSON.stringify({
      challenge_id: challengeId,
      otp,
      new_password: newPassword,
    }),
  });
  return json<{ message: string }>(res);
}

// ---------------------------------------------------------------------------
// Billing endpoints
// ---------------------------------------------------------------------------

export async function apiBillingPlans(): Promise<BillingPlansResponse> {
  const res = await apiFetch("/api/billing/plans", { method: "GET" });
  return json<BillingPlansResponse>(res);
}

export async function apiSubscription(): Promise<Subscription> {
  const res = await apiFetch("/api/billing/subscription", { method: "GET" });
  return json<Subscription>(res);
}

export async function apiRequestBillingOtp(
  planId: string,
): Promise<BillingOtpStart> {
  const res = await apiFetch("/api/billing/otp/request", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
  });
  return json<BillingOtpStart>(res);
}

export async function apiVerifyBillingOtp(
  challengeId: string,
  otp: string,
): Promise<Subscription> {
  const res = await apiFetch("/api/billing/otp/verify", {
    method: "POST",
    body: JSON.stringify({ challenge_id: challengeId, otp }),
  });
  return json<Subscription>(res);
}

export async function apiCancelSubscription(): Promise<{
  subscription: Subscription;
  status_code: string;
  status_detail: string;
}> {
  const res = await apiFetch("/api/billing/subscription/cancel", {
    method: "POST",
  });
  return json(res);
}

// ---------------------------------------------------------------------------
// Chat endpoints
// ---------------------------------------------------------------------------

export async function apiSessions(): Promise<SessionsResponse> {
  const res = await apiFetch("/api/chat/sessions", { method: "GET" });
  return json<SessionsResponse>(res);
}

export async function apiMessages(
  sessionId: number,
): Promise<MessagesResponse> {
  const res = await apiFetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: "GET",
  });
  return json<MessagesResponse>(res);
}

export async function apiDeleteSession(sessionId: number): Promise<void> {
  const res = await apiFetch(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) {
    throw new ApiError(res.status, "Delete failed");
  }
}
