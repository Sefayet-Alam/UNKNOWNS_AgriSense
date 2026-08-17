// Central API client: base URL, bearer attach, and 401 -> refresh(rotation) -> retry-once.

import { upload as uploadBlob } from "@vercel/blob/client";

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
  CaasQuote,
  CaasReceipt,
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
  // FormData sets its own multipart boundary — never force JSON on it.
  if (
    !finalHeaders.has("Content-Type") &&
    rest.body &&
    !(rest.body instanceof FormData)
  ) {
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
  union_name: string;
  union_code: string;
}

export interface UnionOption {
  code: string;
  name: string;
  name_bn: string;
}

/** Unions under an upazila (public gazetteer endpoint, no auth). */
export async function apiUnions(upazilaCode: string): Promise<UnionOption[]> {
  const res = await apiFetch(`/api/geo/unions/${upazilaCode}`, {
    method: "GET",
    auth: false,
  });
  const data = await json<{ results: UnionOption[] }>(res);
  return data.results;
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

export async function apiCaasQuote(): Promise<CaasQuote> {
  const res = await apiFetch("/api/billing/caas/quote", { method: "GET" });
  return json<CaasQuote>(res);
}

export async function apiCaasDebit(productId: string): Promise<CaasReceipt> {
  const res = await apiFetch("/api/billing/caas/debit", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, confirm: true }),
  });
  return json<CaasReceipt>(res);
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

// ---------------------------------------------------------------------------
// Uploads (Tier 2: leaf photo + voice note)
// ---------------------------------------------------------------------------

export interface UploadResult {
  id: number;
  kind: "image" | "audio";
  mime_type: string;
  transcript: string | null;
  warning: string | null;
}

export async function apiUpload(file: File): Promise<UploadResult> {
  if (process.env.NEXT_PUBLIC_UPLOAD_STORAGE === "vercel-blob") {
    // A cheap /me request also refreshes an expired access token through the
    // existing single-flight rotation path before the Blob token request.
    const user = await apiMe();
    const access = getAccess();
    if (!access) throw new ApiError(401, "Authentication required");
    const extensionByMime: Record<string, string> = {
      "image/jpeg": "jpg",
      "image/jpg": "jpg",
      "image/png": "png",
      "image/webp": "webp",
      "audio/mpeg": "mp3",
      "audio/mp3": "mp3",
      "audio/mp4": "m4a",
      "audio/ogg": "ogg",
      "audio/wav": "wav",
      "audio/x-wav": "wav",
      "audio/webm": "webm",
    };
    const extension = extensionByMime[file.type.toLowerCase()] || "bin";
    const pathname = `uploads/${user.id}/${crypto.randomUUID()}.${extension}`;
    const blob = await uploadBlob(pathname, file, {
      access: "private",
      handleUploadUrl: "/api/blob/upload",
      headers: { Authorization: `Bearer ${access}` },
      contentType: file.type,
    });
    const finalized = await apiFetch("/api/uploads/from-blob", {
      method: "POST",
      body: JSON.stringify({ url: blob.url, mime_type: file.type }),
    });
    return json<UploadResult>(finalized);
  }

  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch("/api/uploads", { method: "POST", body: form });
  if (!res.ok) {
    let detail = `Upload failed (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return json<UploadResult>(res);
}

export async function apiAttachmentContent(id: number): Promise<Response> {
  if (process.env.NEXT_PUBLIC_UPLOAD_STORAGE !== "vercel-blob") {
    return apiFetch(`/api/uploads/${id}/content`);
  }

  const open = () => {
    const access = getAccess();
    return fetch(`/api/blob/download/${id}`, {
      headers: access ? { Authorization: `Bearer ${access}` } : {},
    });
  };
  let response = await open();
  if (response.status === 401) {
    await refreshTokens();
    response = await open();
  }
  return response;
}
