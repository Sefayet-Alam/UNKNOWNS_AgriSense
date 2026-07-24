"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getAccess, getStoredSessionId, setStoredSessionId } from "@/lib/tokens";
import { ChatColumn } from "@/components/chat/ChatColumn";
import { Sidebar } from "@/components/chat/Sidebar";

export default function ChatPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  // null = a new (unsaved) chat.
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [ready, setReady] = useState(false);

  // Guard: no token -> login. Restore last active session id.
  useEffect(() => {
    if (!getAccess()) {
      router.replace("/login");
      return;
    }
    setSessionId(getStoredSessionId());
    setReady(true);
  }, [router]);

  // If bootstrap resolved with no user (invalid/expired token), bounce to login.
  useEffect(() => {
    if (!loading && !user && !getAccess()) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  const handleNewChat = () => {
    setSessionId(null);
    setStoredSessionId(null);
  };

  const handleSelect = (id: number) => {
    setSessionId(id);
    setStoredSessionId(id);
  };

  const handleSessionCreated = (id: number) => {
    setSessionId(id);
    setStoredSessionId(id);
  };

  const handleDeleted = (id: number) => {
    if (id === sessionId) {
      setSessionId(null);
      setStoredSessionId(null);
    }
  };

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-text-muted">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        activeSessionId={sessionId}
        onNewChat={handleNewChat}
        onSelect={handleSelect}
        onDeleted={handleDeleted}
      />
      <ChatColumn
        key={sessionId ?? "new"}
        sessionId={sessionId}
        onSessionCreated={handleSessionCreated}
      />
    </div>
  );
}
