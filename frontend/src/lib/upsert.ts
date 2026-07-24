import type { Message } from "./types";

/**
 * find-by-id replace or append. Used for both `message` and `message_update`
 * frames so the live buffer stays a single source of truth per bubble id.
 */
export function upsertMessage(list: Message[], msg: Message): Message[] {
  const idx = list.findIndex((m) => m.id === msg.id);
  if (idx === -1) return [...list, msg];
  const next = list.slice();
  next[idx] = msg;
  return next;
}

/**
 * Merge a fetched (persisted) list with any live-buffer messages, deduping by
 * id and preserving chronological order. Persisted rows win on conflict.
 */
export function mergeById(persisted: Message[], live: Message[]): Message[] {
  const seen = new Set(persisted.map((m) => m.id));
  const extra = live.filter((m) => !seen.has(m.id));
  return [...persisted, ...extra].sort((a, b) => a.id - b.id);
}
