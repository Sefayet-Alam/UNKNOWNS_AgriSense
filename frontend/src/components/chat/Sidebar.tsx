"use client";

import { LogOut, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { LeafMark } from "@/components/ui/LeafMark";
import { useAuth } from "@/lib/auth";
import { useDeleteSession, useSessions } from "@/lib/hooks";
import { formatBdPhone } from "@/lib/phone";
import type { Session } from "@/lib/types";

interface Props {
  activeSessionId: number | null;
  onNewChat: () => void;
  onSelect: (id: number) => void;
  onDeleted: (id: number) => void;
}

function initials(name?: string | null) {
  return (name || "")
    .split(" ")
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase() || "·";
}

function Avatar({ name, size = 32 }: { name?: string | null; size?: number }) {
  return (
    <span
      style={{ width: size, height: size, fontSize: size * 0.4 }}
      className="flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary-500 to-primary-700 font-semibold text-white"
    >
      {initials(name)}
    </span>
  );
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
      className={`group flex items-center gap-2 rounded-xl border px-2.5 py-2.5 text-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-card ${
        active
          ? "border-field-300 bg-field-100 text-field-900"
          : "border-transparent text-text-primary hover:border-jute-300/55 hover:bg-paper-50"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
      >
        <MessageSquare size={16} strokeWidth={1.75} className="shrink-0 text-primary-600" />
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

export function Sidebar({ activeSessionId, onNewChat, onSelect, onDeleted }: Props) {
  const { user, logout } = useAuth();
  const { data: sessions, isLoading } = useSessions();
  const del = useDeleteSession();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(max-width: 767px)").matches) {
      setCollapsed(true);
    }
  }, []);

  const handleDelete = async (id: number) => {
    await del.mutateAsync(id);
    onDeleted(id);
  };

  if (collapsed) {
    return (
      <>
        <div className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-jute-300/55 bg-paper-100/95 px-3 backdrop-blur sm:hidden">
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label="Open chats"
            className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition hover:bg-paper-50 hover:text-field-700"
          >
            <PanelLeftOpen size={18} />
          </button>
          <LeafMark size="sm" showWordmark={false} />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onNewChat}
              title="New chat"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-field-700 text-white shadow-card transition hover:bg-field-900"
            >
              <Plus size={18} strokeWidth={2} />
            </button>
            <Link href="/profile?tab=info" title={user?.username ?? "Profile"} className="transition hover:-translate-y-0.5">
              <Avatar name={user?.username} size={34} />
            </Link>
          </div>
        </div>
        <aside className="hidden h-full w-14 shrink-0 flex-col items-center border-r border-jute-300/55 bg-paper-100 py-3 sm:flex">
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label="Expand sidebar"
            className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition hover:-translate-y-0.5 hover:bg-paper-50 hover:text-field-700 hover:shadow-card"
          >
            <PanelLeftOpen size={18} />
          </button>
          <button
            type="button"
            onClick={onNewChat}
            title="New chat"
            className="mt-3 flex h-9 w-9 items-center justify-center rounded-full bg-field-700 text-white shadow-card transition hover:-translate-y-1 hover:bg-field-900 hover:shadow-lift"
          >
            <Plus size={18} strokeWidth={2} />
          </button>
          <div className="flex-1" />
          <Link href="/profile?tab=info" title={user?.username ?? "Profile"} className="mb-2 transition hover:-translate-y-1">
            <Avatar name={user?.username} size={34} />
          </Link>
          <button
            type="button"
            onClick={() => logout()}
            aria-label="Log out"
            className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition hover:-translate-y-0.5 hover:bg-paper-50 hover:text-status-error"
          >
            <LogOut size={17} />
          </button>
        </aside>
      </>
    );
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close chats"
        onClick={() => setCollapsed(true)}
        className="fixed inset-0 z-40 bg-field-950/25 backdrop-blur-[1px] sm:hidden"
      />
      <aside className="fixed inset-y-0 left-0 z-50 flex h-[100dvh] w-[min(320px,calc(100vw-2rem))] shrink-0 flex-col border-r border-jute-300/55 bg-paper-100 shadow-2xl sm:relative sm:z-auto sm:h-full sm:w-[280px] sm:shadow-none">
      <div className="flex items-center justify-between px-4 py-4">
        <LeafMark size="sm" />
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse sidebar"
          className="rounded-full p-1.5 text-text-muted transition hover:-translate-y-0.5 hover:bg-paper-50 hover:text-field-700 hover:shadow-card"
        >
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="px-3 pb-3">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-full bg-field-700 px-3 py-2.5 text-sm font-semibold text-white shadow-card transition duration-200 hover:-translate-y-1 hover:bg-field-900 hover:shadow-lift active:translate-y-0"
        >
          <Plus size={18} strokeWidth={1.75} /> New chat
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
        {isLoading && <p className="px-2.5 py-2 text-sm text-text-muted">Loading…</p>}
        {!isLoading && (!sessions || sessions.length === 0) && (
          <p className="px-2.5 py-2 text-sm text-text-muted">No chats yet. Start one above.</p>
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
        <Link
          href="/profile?tab=info"
          className="mb-2 flex items-center gap-2 rounded-xl border border-transparent px-1.5 py-1.5 transition hover:-translate-y-0.5 hover:border-jute-300/55 hover:bg-paper-50 hover:shadow-card"
        >
          <Avatar name={user?.username} size={34} />
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-text-primary">
              {user?.username ?? "…"}
            </span>
            {user?.phone && (
              <span className="block truncate text-xs text-text-muted">
                {formatBdPhone(user.phone)}
              </span>
            )}
          </span>
        </Link>
        <button
          type="button"
          onClick={() => logout()}
          className="flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-sm text-text-primary transition hover:-translate-y-0.5 hover:bg-paper-50 hover:shadow-card"
        >
          <LogOut size={16} strokeWidth={1.75} className="text-primary-600" /> Log out
        </button>
      </div>
      </aside>
    </>
  );
}
