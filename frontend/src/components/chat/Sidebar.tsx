"use client";

import { LogOut, MessageSquare, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useDeleteSession, useSessions } from "@/lib/hooks";
import type { Session } from "@/lib/types";
import { LeafMark } from "@/components/ui/LeafMark";

interface Props {
  activeSessionId: number | null;
  onNewChat: () => void;
  onSelect: (id: number) => void;
  onDeleted: (id: number) => void;
}

function SessionItem({
  session,
  active,
  onSelect,
  onDelete,
  deleting,
}: {
  session: Session;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div
      className={`group flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition ${
        active
          ? "bg-primary-100 text-primary-800"
          : "text-text-primary hover:bg-primary-50"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
      >
        <MessageSquare
          size={16}
          strokeWidth={1.75}
          className="shrink-0 text-primary-600"
        />
        <span className="truncate">{session.title || "New chat"}</span>
      </button>

      {confirming ? (
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="rounded px-1.5 py-0.5 text-xs font-medium text-status-error hover:bg-status-error-chip"
          >
            {deleting ? "…" : "Delete"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="rounded px-1.5 py-0.5 text-xs text-text-muted hover:bg-surface-muted"
          >
            No
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          aria-label="Delete chat"
          className="shrink-0 rounded p-1 text-text-muted opacity-0 transition hover:text-status-error group-hover:opacity-100"
        >
          <Trash2 size={15} strokeWidth={1.75} />
        </button>
      )}
    </div>
  );
}

export function Sidebar({
  activeSessionId,
  onNewChat,
  onSelect,
  onDeleted,
}: Props) {
  const { user, logout } = useAuth();
  const { data: sessions, isLoading } = useSessions();
  const del = useDeleteSession();

  const handleDelete = async (id: number) => {
    await del.mutateAsync(id);
    onDeleted(id);
  };

  return (
    <aside className="flex h-full w-[280px] shrink-0 flex-col border-r border-border bg-surface-muted">
      <div className="flex items-center justify-between px-4 py-4">
        <LeafMark size="sm" />
      </div>

      <div className="px-3 pb-3">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-3 py-2.5 text-sm font-medium text-white transition hover:bg-primary-700"
        >
          <Plus size={18} strokeWidth={1.75} />
          New chat
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
        {isLoading && (
          <p className="px-2.5 py-2 text-sm text-text-muted">Loading…</p>
        )}
        {!isLoading && (!sessions || sessions.length === 0) && (
          <p className="px-2.5 py-2 text-sm text-text-muted">
            No chats yet. Start one above.
          </p>
        )}
        {sessions?.map((s) => (
          <SessionItem
            key={s.id}
            session={s}
            active={s.id === activeSessionId}
            onSelect={() => onSelect(s.id)}
            onDelete={() => handleDelete(s.id)}
            deleting={del.isPending && del.variables === s.id}
          />
        ))}
      </nav>

      <div className="border-t border-border px-3 py-3">
        <div className="mb-2 px-1.5">
          <p className="truncate text-sm font-medium text-text-primary">
            {user?.username ?? "…"}
          </p>
          {user?.email && (
            <p className="truncate text-xs text-text-muted">{user.email}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => logout()}
          className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-text-primary transition hover:bg-primary-50"
        >
          <LogOut size={16} strokeWidth={1.75} className="text-primary-600" />
          Log out
        </button>
      </div>
    </aside>
  );
}
