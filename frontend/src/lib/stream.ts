// SSE chat streaming over raw fetch + ReadableStream (EventSource can't send a
// Bearer header or a POST body). Handles a single 401 -> refresh -> reconnect.

import { BASE, refreshTokens } from "./api";
import { getAccess } from "./tokens";
import type { StreamFrame } from "./types";

export interface StreamArgs {
  message: string;
  sessionId: number | null;
  signal: AbortSignal;
  onEvent: (frame: StreamFrame) => void;
}

async function openStream(
  message: string,
  sessionId: number | null,
  access: string | null,
  signal: AbortSignal,
): Promise<Response> {
  return fetch(`${BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream, */*",
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId ?? null }),
    signal,
  });
}

/**
 * Stream a chat turn. Resolves when the server closes the stream (after `done`
 * or `error`) or the caller aborts. Frames are delivered via `onEvent`.
 */
export async function streamChat({
  message,
  sessionId,
  signal,
  onEvent,
}: StreamArgs): Promise<void> {
  let res = await openStream(message, sessionId, getAccess(), signal);

  // One refresh + reconnect on an unauthorized stream.
  if (res.status === 401) {
    const access = await refreshTokens();
    res = await openStream(message, sessionId, access, signal);
  }

  if (!res.ok || !res.body) {
    let detail = `Stream failed (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch {
      /* ignore */
    }
    onEvent({ type: "error", detail });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let i = buffer.indexOf("\n\n");
      while (i !== -1) {
        const frame = buffer.slice(0, i);
        buffer = buffer.slice(i + 2);
        const line = frame.split("\n").find((l) => l.startsWith("data:"));
        if (line) {
          const raw = line.slice(line.indexOf(":") + 1).trim();
          if (raw) {
            try {
              onEvent(JSON.parse(raw) as StreamFrame);
            } catch {
              /* skip malformed frame */
            }
          }
        }
        i = buffer.indexOf("\n\n");
      }
    }
  } catch (err) {
    if ((err as Error)?.name !== "AbortError") {
      onEvent({ type: "error", detail: (err as Error).message });
    }
  } finally {
    reader.releaseLock();
  }
}
