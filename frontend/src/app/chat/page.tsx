"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/chat/Sidebar";
import { ChatColumn } from "@/components/chat/ChatColumn";
import { useAuth } from "@/lib/auth";
import { useChat } from "@/lib/chat/ChatProvider";
import { getAccess } from "@/lib/tokens";

export default function ChatPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  // Chat state lives in the app-level ChatProvider so the stream survives
  // navigation to other pages (#1).
  const { sessionId, selectSession, newChat } = useChat();

  useEffect(() => {
    if (!getAccess()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    if (!loading && !user && !getAccess()) router.replace("/login");
  }, [loading, user, router]);

  const handleDeleted = (id: number) => {
    if (id === sessionId) newChat();
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        activeSessionId={sessionId}
        onNewChat={newChat}
        onSelect={selectSession}
        onDeleted={handleDeleted}
      />
      <ChatColumn />
    </div>
  );
}
