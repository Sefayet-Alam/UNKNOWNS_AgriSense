"use client";

// react-query data hooks bound to the frozen contract endpoints.

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ApiError,
  apiDeleteSession,
  apiMessages,
  apiSessions,
} from "./api";
import { setStoredSessionId } from "./tokens";
import type { Message, Session } from "./types";

export const qk = {
  sessions: ["chat", "sessions"] as const,
  messages: (sessionId: number | null) =>
    ["chat", "messages", sessionId] as const,
};

export function useSessions(enabled = true) {
  return useQuery<Session[]>({
    queryKey: qk.sessions,
    queryFn: async () => (await apiSessions()).results,
    enabled,
    staleTime: 10_000,
  });
}

export function useMessages(sessionId: number | null) {
  return useQuery<Message[]>({
    queryKey: qk.messages(sessionId),
    enabled: sessionId !== null,
    queryFn: async () => {
      if (sessionId === null) return [];
      try {
        return (await apiMessages(sessionId)).results;
      } catch (err) {
        // A 404 means the stored session is gone/not owned — clear it.
        if (err instanceof ApiError && err.status === 404) {
          setStoredSessionId(null);
        }
        throw err;
      }
    },
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: number) => apiDeleteSession(sessionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.sessions });
    },
  });
}
